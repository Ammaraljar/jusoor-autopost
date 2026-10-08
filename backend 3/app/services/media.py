"""The company's photo library: uploads and links (Google Drive, Dropbox, photo sites, direct URLs).

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
