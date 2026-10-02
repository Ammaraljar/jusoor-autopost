"""Background image sourcing: article image and/or Pexels stock photos."""
from __future__ import annotations

import hashlib
import io
import logging

import httpx
from PIL import Image

from . import credentials, storage
from .scraper import HEADERS

log = logging.getLogger(__name__)
MIN_WIDTH = 600


def normalise(data: bytes, min_width: int = MIN_WIDTH) -> bytes | None:
    """Any supported image → RGB JPEG (max 2000px), honouring the phone's rotation."""
    from PIL import ImageOps
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.width < min_width:
        return None
    img = img.convert("RGB")
    if img.width > 2000 or img.height > 2000:
        img.thumbnail((2000, 2000))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()


def download_image(url: str) -> bytes | None:
    """Download and normalise an image to JPEG; returns None when unusable.

    Our own media (e.g. a photo the user uploaded) is read straight from storage: asking our own
    server over HTTP while it is busy rendering would wait on itself until the timeout."""
    try:
        key = storage.own_key(url)
        if key:
            return normalise(storage.read_bytes(key), min_width=1)
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        return normalise(resp.content)
    except Exception as exc:  # noqa: BLE001
        log.warning("image download failed %s: %s", url, exc)
        return None


def search_pexels(query: str, count: int = 6, page: int = 1) -> list[dict]:
    key = credentials.current()["pexels_api_key"]
    if not key or not query:
        return []
    try:
        resp = httpx.get("https://api.pexels.com/v1/search",
                         params={"query": query, "orientation": "portrait", "per_page": count, "page": page},
                         headers={"Authorization": key}, timeout=20)
        resp.raise_for_status()
        return [{"url": p["src"].get("large2x") or p["src"]["large"],
                 "credit": f"Photo: {p.get('photographer', '')} / Pexels"} for p in resp.json().get("photos", [])]
    except Exception as exc:  # noqa: BLE001
        log.warning("pexels search failed: %s", exc)
        return []


def search_openverse(query: str, count: int = 8, page: int = 1) -> list[dict]:
    """Free photos without an API key (Openverse, public-domain / CC0 only — no attribution needed)."""
    if not query:
        return []
    try:
        resp = httpx.get("https://api.openverse.org/v1/images/",
                         params={"q": query, "license": "cc0,pdm", "page_size": count, "page": page,
                                 "aspect_ratio": "tall,square", "size": "large", "mature": "false"},
                         headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return [{"url": r["url"], "credit": ""} for r in resp.json().get("results", []) if r.get("url")]
    except Exception as exc:  # noqa: BLE001
        log.warning("openverse search failed: %s", exc)
        return []


def stock_photos(keywords: str, count: int, page: int = 1) -> list[dict]:
    """Pexels when a key is set, otherwise (or in addition) Openverse."""
    found = search_pexels(keywords, count=count, page=page)
    if len(found) < count:
        found += search_openverse(keywords, count=count, page=page)
    return found


def collect_backgrounds(article_image: str | None, keywords: str, mode: str, needed: int,
                        exclude: set[str] | None = None, fresh: bool = False) -> list[dict]:
    """Return a list of {url, bytes, hash, credit} backgrounds (may be shorter than needed).

    fresh=True ("new backgrounds"): skip the photos already used and look further in the results,
    so the post really gets different images."""
    import random
    exclude = set(exclude or ())
    article = [{"url": article_image, "credit": ""}] if article_image and article_image not in exclude else []
    page = random.randint(2, 6) if fresh else 1
    if mode == "source":
        candidates = article
    else:
        stock = stock_photos(keywords, count=max(needed + 2, 6), page=page)
        if fresh and len(stock) < needed:
            stock += stock_photos(keywords, count=max(needed + 2, 6), page=1)
        if fresh:
            random.shuffle(stock)
        # Auto: the article's own photo is the cover, stock photos fill the other slides.
        candidates = stock if mode == "pexels" else article + stock
    candidates = [c for c in candidates if c["url"] not in exclude]
    out: list[dict] = []
    seen: set[str] = set()
    for c in candidates:
        data = download_image(c["url"])
        if not data:
            continue
        digest = hashlib.sha1(data).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        out.append({**c, "bytes": data, "hash": digest})
        if len(out) >= needed:
            break
    return out
