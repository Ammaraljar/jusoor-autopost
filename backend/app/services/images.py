"""Background image sourcing: article image and/or Pexels stock photos."""
from __future__ import annotations

import hashlib
import io
import logging

import httpx
from PIL import Image

from . import credentials
from .scraper import HEADERS

log = logging.getLogger(__name__)
MIN_WIDTH = 600


def download_image(url: str) -> bytes | None:
    """Download and normalise an image to JPEG; returns None when unusable."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        if img.width < MIN_WIDTH:
            return None
        img = img.convert("RGB")
        if img.width > 2000:
            img.thumbnail((2000, 2000))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=88)
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001
        log.warning("image download failed %s: %s", url, exc)
        return None


def search_pexels(query: str, count: int = 6) -> list[dict]:
    key = credentials.current()["pexels_api_key"]
    if not key or not query:
        return []
    try:
        resp = httpx.get("https://api.pexels.com/v1/search",
                         params={"query": query, "orientation": "portrait", "per_page": count},
                         headers={"Authorization": key}, timeout=20)
        resp.raise_for_status()
        return [{"url": p["src"].get("large2x") or p["src"]["large"],
                 "credit": f"Photo: {p.get('photographer', '')} / Pexels"} for p in resp.json().get("photos", [])]
    except Exception as exc:  # noqa: BLE001
        log.warning("pexels search failed: %s", exc)
        return []


def collect_backgrounds(article_image: str | None, keywords: str, mode: str, needed: int) -> list[dict]:
    """Return a list of {url, bytes, hash, credit} backgrounds (may be shorter than needed)."""
    article = [{"url": article_image, "credit": ""}] if article_image else []
    if mode == "source":
        candidates = article
    else:
        stock = search_pexels(keywords, count=max(needed, 4))
        # Auto: the article's own photo is the cover, stock photos fill the other slides.
        candidates = stock if mode == "pexels" else article + stock
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
