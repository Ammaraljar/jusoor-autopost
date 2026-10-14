"""Photos for posts: the article's own photo, the company's library and stock libraries
(Pexels, Pixabay, Unsplash with a key; Openverse and Wikimedia Commons free)."""
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


def search_pixabay(query: str, count: int = 8, page: int = 1) -> list[dict]:
    """Pixabay (free licence, no attribution required)."""
    key = credentials.current().get("pixabay_api_key")
    if not key or not query:
        return []
    try:
        resp = httpx.get("https://pixabay.com/api/",
                         params={"key": key, "q": query[:100], "image_type": "photo", "orientation": "vertical",
                                 "per_page": max(3, min(count, 50)), "page": page, "safesearch": "true",
                                 "min_width": 1000},
                         timeout=20)
        resp.raise_for_status()
        return [{"url": h.get("largeImageURL") or h.get("webformatURL"), "credit": ""}
                for h in resp.json().get("hits", []) if h.get("largeImageURL") or h.get("webformatURL")]
    except Exception as exc:  # noqa: BLE001
        log.warning("pixabay search failed: %s", exc)
        return []


def search_unsplash(query: str, count: int = 8, page: int = 1) -> list[dict]:
    """Unsplash (free licence; the photographer is credited)."""
    key = credentials.current().get("unsplash_api_key")
    if not key or not query:
        return []
    try:
        resp = httpx.get("https://api.unsplash.com/search/photos",
                         params={"query": query[:100], "per_page": max(3, min(count, 30)), "page": page,
                                 "orientation": "portrait", "content_filter": "high"},
                         headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"}, timeout=20)
        resp.raise_for_status()
        return [{"url": r["urls"].get("regular") or r["urls"].get("full"),
                 "credit": f"Photo: {(r.get('user') or {}).get('name', '')} / Unsplash"}
                for r in resp.json().get("results", []) if r.get("urls")]
    except Exception as exc:  # noqa: BLE001
        log.warning("unsplash search failed: %s", exc)
        return []


def search_wikimedia(query: str, count: int = 8, page: int = 1) -> list[dict]:
    """Wikimedia Commons, public-domain / CC0 photos only (no key, no attribution needed)."""
    if not query:
        return []
    try:
        resp = httpx.get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"filetype:bitmap {query[:100]}", "gsrlimit": max(5, min(count * 2, 40)),
            "gsroffset": (page - 1) * count, "prop": "imageinfo", "iiprop": "url|extmetadata|size",
            "iiurlwidth": 1600}, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        out = []
        for p in (resp.json().get("query") or {}).get("pages", {}).values():
            info = (p.get("imageinfo") or [{}])[0]
            licence = ((info.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "").lower()
            if ("public domain" in licence or "cc0" in licence) and (info.get("width") or 0) >= 900:
                out.append({"url": info.get("thumburl") or info.get("url"), "credit": ""})
        return out[:count]
    except Exception as exc:  # noqa: BLE001
        log.warning("wikimedia search failed: %s", exc)
        return []


STOCK = {"pexels": search_pexels, "pixabay": search_pixabay, "unsplash": search_unsplash,
         "openverse": search_openverse, "wikimedia": search_wikimedia}
KEYLESS = ("openverse", "wikimedia")          # free libraries used only when the keyed ones are short
ALL_SOURCES = ["article", "library", "pexels", "pixabay", "unsplash", "openverse", "wikimedia"]


def sources_of(gen: dict) -> list[str]:
    """The company's photo sources in order (from the settings; older settings are translated)."""
    chosen = [x for x in (gen.get("image_sources") or []) if x in ALL_SOURCES]
    if chosen:
        return chosen
    legacy = gen.get("image_source", "auto")
    if legacy == "source":
        return ["article", "library"]
    if legacy == "pexels":
        return ["library", "pexels", "pixabay", "unsplash", "openverse", "wikimedia"]
    return list(ALL_SOURCES)


def stock_photos(keywords: str, count: int, page: int = 1, sources: list[str] | None = None) -> list[dict]:
    """The keyed libraries (Pexels, Pixabay, Unsplash) mixed for variety; free ones when still short."""
    sources = [s for s in (sources or list(STOCK)) if s in STOCK]
    keyed = [STOCK[s](keywords, count=count, page=page) for s in sources if s not in KEYLESS]
    found: list[dict] = []
    for i in range(max((len(x) for x in keyed), default=0)):     # interleave the libraries
        found += [x[i] for x in keyed if i < len(x)]
    for s in sources:
        if s in KEYLESS and len(found) < count:
            found += STOCK[s](keywords, count=count, page=page)
    return found


def collect_backgrounds(article_image: str | None, keywords: str, mode: str, needed: int,
                        exclude: set[str] | None = None, fresh: bool = False,
                        library: list[dict] | None = None, fallback_keywords: str = "",
                        sources: list[str] | None = None) -> list[dict]:
    """Return a list of {url, bytes, hash, credit} backgrounds (may be shorter than needed).

    Order: the article's own photo, matching photos from the company's library, stock photos
    (Pexels, Pixabay, Openverse), then the rest of the library. fresh=True ("new backgrounds")
    skips every photo already used and shuffles, so the post really gets different images."""
    import random
    exclude = set(exclude or ())
    if sources is None:                      # older callers pass a mode
        sources = ["article", "library"] if mode == "source" else \
            (["library"] + list(STOCK) if mode == "pexels" else list(ALL_SOURCES))
    if "library" not in sources:
        library = []
    if "article" not in sources:
        article_image = None
    stock_sources = [s for s in sources if s in STOCK]
    mode = "source" if not stock_sources else ("pexels" if "article" not in sources else "auto")
    library = [c for c in (library or []) if c["url"] not in exclude]
    lib_match = [c for c in library if c.get("match")]
    lib_rest = [c for c in library if not c.get("match")]
    article = [{"url": article_image, "credit": ""}] if article_image and article_image not in exclude else []
    if mode == "source":
        candidates = article + lib_match + lib_rest
    else:
        # one wide search (page 1 always exists — later pages often return nothing or an error)
        kw = {} if set(stock_sources) == set(STOCK) else {"sources": stock_sources}
        stock = stock_photos(keywords, count=max(needed * 3, 18), page=1, **kw)
        if len([c for c in stock if c["url"] not in exclude]) < needed and fallback_keywords:
            stock += stock_photos(fallback_keywords, count=max(needed * 3, 18), page=1, **kw)
        if fresh:
            random.shuffle(stock)
            random.shuffle(lib_match)
        lead = [] if fresh else article
        candidates = lead + lib_match + stock + lib_rest if mode != "pexels" else lib_match + stock + lib_rest
        if fresh:
            candidates += article
    candidates = [c for c in candidates if c["url"] not in exclude]
    out: list[dict] = []
    seen: set[str] = set()
    tried: set[str] = set()
    for c in candidates:
        if c["url"] in tried:
            continue
        tried.add(c["url"])
        data = download_image(c["url"])
        if not data:
            continue
        digest = hashlib.sha1(data).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        out.append({**{k: v for k, v in c.items() if k != "match"}, "bytes": data, "hash": digest})
        if len(out) >= needed:
            break
    return out
