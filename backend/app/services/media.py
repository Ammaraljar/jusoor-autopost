"""The company's photo library: uploads, links and whole connected libraries — Dropbox and Google
Drive folders, OneDrive / SharePoint, Google Photos albums, gallery pages and direct image links.

When a post needs photos the library is searched by keywords (tags, title) before stock photos,
least-used photos first so the feed does not repeat itself.
"""
from __future__ import annotations

import io
import re
import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import MediaAsset, current_org, utcnow
from . import images, scraper, storage

MAX_BYTES = 15 * 1024 * 1024
_WORD = re.compile(r"[\w؀-ۿ]{3,}")


def direct_link(url: str) -> str:
    """Turn sharing links into downloadable ones (Google Drive, Dropbox)."""
    url = url.strip()
    p = urlparse(url)
    host = p.netloc.lower()
    if "drive.google.com" in host or "docs.google.com" in host:
        m = re.search(r"/d/([A-Za-z0-9_-]{10,})", p.path)
        file_id = m.group(1) if m else (parse_qs(p.query).get("id") or [""])[0]
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    if "dropbox.com" in host:
        return re.sub(r"([?&])dl=0", r"\1dl=1", url) if "dl=0" in url else url + ("&" if "?" in url else "?") + "dl=1"
    return url


def fetch_link(url: str) -> tuple[bytes, str]:
    """Image bytes from a link: a direct image, or a page whose share image (og:image) is the photo."""
    link = direct_link(url)
    with httpx.Client(headers=scraper.HEADERS, timeout=40, follow_redirects=True) as client:
        resp = client.get(link)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if ctype.startswith("image/"):
            return resp.content, link
        if "html" in ctype:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            def meta(*names):
                for n in names:
                    tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
                    if tag and tag.get("content"):
                        return tag["content"].strip()
                return None
            img = scraper.find_image(soup, link, meta)
            if not img:
                raise ValueError("الرابط لا يحتوي صورة — استخدم رابط صورة مباشر أو رابط مشاركة عام")
            img_resp = client.get(img)
            img_resp.raise_for_status()
            return img_resp.content, img
        return resp.content, link


def add_image(db: Session, data: bytes, title: str = "", tags: str = "", source_url: str | None = None) -> MediaAsset:
    if len(data) > MAX_BYTES:
        raise ValueError("الحد الأقصى 15 ميغابايت للصورة")
    try:
        jpeg = images.normalise(data, min_width=1)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("تعذّر قراءة الصورة — استخدم JPG أو PNG أو WEBP") from exc
    if not jpeg:
        raise ValueError("تعذّر قراءة الصورة")
    w, h = Image.open(io.BytesIO(jpeg)).size
    key = f"library/org{current_org.get() or 0}/{uuid.uuid4().hex}.jpg"
    url = storage.save_bytes(key, jpeg, "image/jpeg")
    asset = MediaAsset(url=url, key=key, source_url=source_url, title=title.strip()[:200],
                       tags=normalise_tags(tags), width=w, height=h)
    db.add(asset)
    db.flush()
    return asset


def normalise_tags(tags: str) -> str:
    words = [w.strip().lower() for w in re.split(r"[,\s#،]+", tags or "") if w.strip()]
    return " ".join(dict.fromkeys(words))[:2000]


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "")}


def pick(db: Session, keywords: str, count: int, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    """Library photos for a post: matching ones first (by tags/title), then the least used."""
    exclude = exclude or set()
    wanted = _words(keywords)
    rows = list(db.scalars(select(MediaAsset)))
    scored = []
    for a in rows:
        if a.url in exclude:
            continue
        score = len(wanted & (_words(a.tags) | _words(a.title)))
        scored.append((score, -(a.used_count or 0), a))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    picked = [a for _s, _u, a in scored[:count]]
    for a in picked:
        a.used_count = (a.used_count or 0) + 1
        a.last_used_at = utcnow()
    return [{"url": a.url, "credit": "", "match": bool(wanted & (_words(a.tags) | _words(a.title)))}
            for a in picked]


# ---------------------------------------------------------------- connected libraries
LIBRARY_KINDS = ("dropbox", "gdrive", "onedrive", "gphotos", "page", "image")
MAX_IMPORT = 80


def library_kind(url: str) -> str:
    p = urlparse(url.strip())
    host, path = p.netloc.lower(), p.path
    if "dropbox.com" in host or "dropboxusercontent.com" in host:
        return "dropbox"
    if "drive.google.com" in host or "docs.google.com" in host:
        return "gdrive"
    if "1drv.ms" in host or "onedrive.live.com" in host or "sharepoint.com" in host:
        return "onedrive"
    if "photos.app.goo.gl" in host or ("photos.google.com" in host and "/share" in path):
        return "gphotos"
    if re.search(r"\.(jpe?g|png|webp|gif|heic|avif)$", path, re.I):
        return "image"
    return "page"


def _client() -> httpx.Client:
    return httpx.Client(headers=scraper.HEADERS, timeout=httpx.Timeout(40, connect=10), follow_redirects=True)


def _is_image_name(name: str) -> bool:
    return bool(re.search(r"\.(jpe?g|png|webp|gif|heic|heif|avif|bmp|tiff?)$", name or "", re.I))


def _dropbox(client: httpx.Client, url: str, limit: int) -> list[tuple[bytes, str, str]]:
    """A shared Dropbox file, or a shared folder (downloaded as one zip)."""
    import zipfile
    link = direct_link(url)
    resp = client.get(link)
    resp.raise_for_status()
    if resp.headers.get("content-type", "").startswith("image/"):
        return [(resp.content, url, "")]
    data = resp.content
    if data[:2] != b"PK":
        raise ValueError("رابط Dropbox غير عام — اجعل المشاركة «أي شخص لديه الرابط»")
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if len(out) >= limit:
                break
            if info.is_dir() or not _is_image_name(info.filename) or info.file_size > MAX_BYTES:
                continue
            out.append((zf.read(info), f"{url}#{info.filename}", info.filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]))
    return out


def _gdrive(client: httpx.Client, url: str, limit: int) -> list[tuple[bytes, str, str]]:
    """A public Google Drive file, or every photo of a public Drive folder."""
    p = urlparse(url)
    folder = re.search(r"/folders/([A-Za-z0-9_-]{10,})", p.path)
    if not folder:
        link = direct_link(url)
        resp = client.get(link)
        resp.raise_for_status()
        if not resp.headers.get("content-type", "").startswith("image/"):
            raise ValueError("ملف Drive غير عام أو ليس صورة")
        return [(resp.content, url, "")]
    page = client.get(f"https://drive.google.com/embeddedfolderview?id={folder.group(1)}")
    page.raise_for_status()
    found = list(dict.fromkeys(re.findall(r"/file/d/([A-Za-z0-9_-]{20,})", page.text)))
    titles = dict(re.findall(r'/file/d/([A-Za-z0-9_-]{20,})[^>]*>.*?flip-entry-title">([^<]+)<', page.text, re.S))
    if not found:
        raise ValueError("المجلد فارغ أو غير عام — اجعل المشاركة «أي شخص لديه الرابط»")
    out = []
    for fid in found[:limit]:
        name = titles.get(fid, "")
        if name and not _is_image_name(name):
            continue
        for link in (f"https://lh3.googleusercontent.com/d/{fid}=w2400",
                     f"https://drive.google.com/uc?export=download&id={fid}"):
            try:
                r = client.get(link)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                    out.append((r.content, f"https://drive.google.com/file/d/{fid}", name.rsplit(".", 1)[0]))
                    break
            except Exception:  # noqa: BLE001
                continue
    return out


def _onedrive(client: httpx.Client, url: str, limit: int) -> list[tuple[bytes, str, str]]:
    """A shared OneDrive / SharePoint file or folder (through the public shares API)."""
    import base64
    token = "u!" + base64.urlsafe_b64encode(url.strip().encode()).decode().rstrip("=")
    resp = client.get(f"https://api.onedrive.com/v1.0/shares/{token}/driveItem", params={"$expand": "children"})
    if resp.status_code != 200:
        raise ValueError("تعذّر فتح رابط OneDrive — اجعل المشاركة عامة (أي شخص لديه الرابط)")
    item = resp.json()
    entries = item.get("children") if item.get("folder") else [item]
    out = []
    for e in entries or []:
        if len(out) >= limit:
            break
        link = e.get("@content.downloadUrl") or e.get("@microsoft.graph.downloadUrl")
        if not link or not (_is_image_name(e.get("name", "")) or (e.get("file") or {}).get("mimeType", "").startswith("image/")):
            continue
        r = client.get(link)
        if r.status_code == 200:
            out.append((r.content, e.get("webUrl") or f"{url}#{e.get('name')}", (e.get("name") or "").rsplit(".", 1)[0]))
    return out


def _gphotos(client: httpx.Client, url: str, limit: int) -> list[tuple[bytes, str, str]]:
    """A shared Google Photos album (its public page lists the photos)."""
    page = client.get(url)
    page.raise_for_status()
    found = list(dict.fromkeys(re.findall(r"https://lh3\.googleusercontent\.com/pw/[A-Za-z0-9_\-]{40,}", page.text)))
    if not found:
        raise ValueError("الألبوم غير عام أو فارغ — شارك الألبوم برابط عام")
    out = []
    for base in found[:limit]:
        r = client.get(base + "=w2400-h2400")
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            out.append((r.content, base, ""))
    return out


def _big(data: bytes, min_side: int = 500) -> bool:
    """Real photos, not thumbnails or icons."""
    try:
        w, h = Image.open(io.BytesIO(data)).size
        return max(w, h) >= min_side
    except Exception:  # noqa: BLE001
        return False


def _page_images(client: httpx.Client, url: str, limit: int) -> list[tuple[bytes, str, str]]:
    """Every large photo of a gallery page (a site's gallery, a portfolio, a Flickr / Behance page…)."""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    resp = client.get(url)
    resp.raise_for_status()
    if resp.headers.get("content-type", "").startswith("image/"):
        return [(resp.content, url, "")]
    soup = BeautifulSoup(resp.text, "html.parser")
    links: list[tuple[str, str]] = []
    for tag in soup.find_all("meta", attrs={"property": "og:image"}):
        if tag.get("content"):
            links.append((tag["content"], ""))
    for img in soup.find_all("img"):
        if img.find_parent(["header", "nav", "footer"]):
            continue
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or img.get("src") or ""
        srcset = img.get("srcset") or img.get("data-srcset") or ""
        if srcset:
            src = srcset.split(",")[-1].strip().split(" ")[0] or src
        if src and not src.startswith("data:") and not re.search(r"logo|icon|sprite|avatar|pixel", src, re.I):
            links.append((src, img.get("alt") or ""))
    for a in soup.find_all("a", href=True):                 # galleries that link to the full-size photo
        if _is_image_name(urlparse(a["href"]).path):
            links.append((a["href"], a.get("title") or ""))
    out, seen = [], set()
    for src, alt in links:
        full = urljoin(url, src)
        if full in seen:
            continue
        seen.add(full)
        try:
            r = client.get(full)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/") and _big(r.content):
                out.append((r.content, full, alt[:200]))
        except Exception:  # noqa: BLE001
            continue
        if len(out) >= limit:
            break
    if not out:
        raise ValueError("لم نجد صورًا كبيرة في هذه الصفحة")
    return out


def collect_library(url: str, limit: int = MAX_IMPORT) -> tuple[str, list[tuple[bytes, str, str]]]:
    """(kind, [(image bytes, source link, title)]) of a library link."""
    kind = library_kind(url)
    handlers = {"dropbox": _dropbox, "gdrive": _gdrive, "onedrive": _onedrive, "gphotos": _gphotos,
                "page": _page_images, "image": _page_images}
    with _client() as client:
        return kind, handlers[kind](client, url.strip(), limit)


def import_library(db: Session, url: str, tags: str = "", title: str = "", limit: int = MAX_IMPORT) -> dict:
    """Add a library's photos (photos already in the library are skipped)."""
    kind, found = collect_library(url, limit)
    have = set(db.scalars(select(MediaAsset.source_url).where(MediaAsset.source_url.is_not(None))))
    added = skipped = 0
    errors: list[str] = []
    for data, source, name in found:
        if source in have:
            skipped += 1
            continue
        try:
            add_image(db, data, title or name, tags, source)
            have.add(source)
            added += 1
        except ValueError as exc:
            errors.append(f"{name or source}: {exc}")
    return {"kind": kind, "found": len(found), "added": added, "skipped": skipped, "errors": errors[:5]}
