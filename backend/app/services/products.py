"""Products, services, courses, travel programmes and offers read from any link the company gives.

The link can be a whole site, a listing page (offers, courses, programmes…) or one product page, and
the site can be a store (Shopify, WooCommerce, Shopee…), a travel agency, a training centre or any
other business. What is tried, in order (the first that finds items wins):

1. The page itself: schema.org data (ItemList, Product, Course, TouristTrip, Service, Event…).
2. Data the page carries for its scripts (Next.js data, `window.X = {…}`, the site's data files).
3. Repeated links to item pages (cards in a listing): each item page is then read for its details.
4. A single item page: its share tags (og:title / og:image / price tags).
5. A whole site: Shopify / WooCommerce stores, then the sitemap and the home page's item links.
Pages built in the browser (JavaScript sites) are opened in a real headless browser: the rendered
page and the data it loads (JSON) are read the same way. As a last step the AI reads the page and
lists what it offers. Everything has a time limit, so a slow or blocking site never hangs the server.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import json
import logging
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
MAX_ITEMS = 80
MAX_PAGES = 40
STATIC_BUDGET = 60          # seconds for reading pages over HTTP
RENDER_TIMEOUT = 35         # seconds for the headless browser
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": BROWSER_UA, "Accept-Language": "ar,en;q=0.8",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
ITEM_PATH = re.compile(r"/(product|products|shop|store|item|items|course|courses|training|program|programs|programme|"
                       r"programmes|package|packages|tour|tours|trip|trips|service|services|event|events|offer|offers|"
                       r"deal|deals|menu|dish|listing|listings|property|properties|car|cars|vehicle|vehicles|"
                       r"collection|p|dp|منتج|منتجات|خدمة|خدمات|دورة|دورات|برنامج|برامج|عرض|عروض|باقة|باقات|رحلة|رحلات)"
                       r"/[^/?#]+", re.I)
SCHEMA_KIND = {"product": "product", "productgroup": "product", "individualproduct": "product", "vehicle": "product",
               "car": "product", "book": "product", "menuitem": "product", "course": "course",
               "courseinstance": "course", "educationalprogram": "course", "service": "service",
               "event": "event", "educationevent": "event", "businessevent": "event", "offer": "offer",
               "touristtrip": "offer", "trip": "offer", "touristattraction": "offer", "hotel": "service",
               "residence": "product", "accommodation": "product", "apartment": "product", "house": "product",
               "singlefamilyresidence": "product", "vacationrental": "product", "lodgingbusiness": "service",
               "foodestablishment": "service", "restaurant": "service"}
NAV_WORDS = re.compile(r"(login|signin|sign-in|register|cart|checkout|account|wishlist|contact|about|privacy|terms|"
                       r"faq|blog|news|careers|tag|category|categories|search|booking|book-now|inquiry|enquiry|"
                       r"طلب|حجز|تواصل|اتصل|من-نحن|سياسة|شروط|تسجيل|سلة|الصفحة|التصنيف)", re.I)
# marketplaces that refuse automated reading from servers (their offers are added by hand)
PROTECTED_HOSTS = ("shopee.", "lazada.", "amazon.", "aliexpress.", "temu.", "noon.com", "tiktok.com")
IMG_EXT = re.compile(r"\.(jpe?g|png|webp|avif|gif)(\?|$)", re.I)


# ---------------------------------------------------------------- helpers
def _clean(text: Any, limit: int = 1500) -> str:
    if text is None:
        return ""
    text = BeautifulSoup(str(text), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()[:limit]


def _normalise(url: str) -> str:
    url = (url or "").strip()
    return url if url.startswith("http") else "https://" + url.lstrip("/")


def _base(url: str) -> str:
    p = urlparse(_normalise(url))
    return f"{p.scheme}://{p.netloc}"


def _client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=httpx.Timeout(15, connect=8), follow_redirects=True)


def _get(client: httpx.Client, url: str, limit: int = 6_000_000) -> httpx.Response | None:
    try:
        r = client.get(url)
        if r.status_code != 200 or len(r.content) > limit:
            return None
        return r
    except Exception:  # noqa: BLE001
        return None


def _is_html(r: httpx.Response | None) -> bool:
    return bool(r) and ("html" in r.headers.get("content-type", "html") or r.text.lstrip()[:15].lower().startswith("<"))


def _same_site(a: str, b: str) -> bool:
    ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
    return ha.removeprefix("www.") == hb.removeprefix("www.")


def _price_text(value: Any) -> tuple[str, str]:
    """A price from a number, a string or a nested object ({"USD": 1350} / {"adult": {"amount": …}})."""
    if value is None or value == "":
        return "", ""
    if isinstance(value, (int, float)):
        return (f"{value:g}" if isinstance(value, float) else str(value)), ""
    if isinstance(value, str):
        v = value.strip()
        return (v[:40], "") if re.search(r"\d", v) else ("", "")
    if isinstance(value, list):
        return _price_text(value[0]) if value else ("", "")
    if isinstance(value, dict):
        cur = str(value.get("currency") or value.get("priceCurrency") or value.get("currency_code") or "")
        for key in ("amount", "price", "value", "min", "from", "adult", "lowPrice"):
            if key in value:
                p, c = _price_text(value[key])
                if p:
                    return p, cur or c
        for key, v in value.items():
            p, c = _price_text(v)
            if p:
                return p, cur or c or (key if re.fullmatch(r"[A-Z]{3}", str(key)) else "")
    return "", ""


def _image(value: Any) -> str | None:
    if isinstance(value, list):
        for v in value:
            img = _image(v)
            if img:
                return img
        return None
    if isinstance(value, dict):
        return _image(value.get("url") or value.get("src") or value.get("contentUrl") or value.get("original")
                      or value.get("large") or value.get("medium"))
    if isinstance(value, str) and value.strip():
        v = value.strip()
        if v.startswith(("http", "/", "./", "../")) or IMG_EXT.search(v):
            return v
    return None


def _looks_like_logo(url: str | None) -> bool:
    return bool(url) and bool(re.search(r"logo|favicon|icon|sprite|placeholder|avatar", url, re.I))


# ---------------------------------------------------------------- schema.org
def _jsonld_nodes(soup: BeautifulSoup) -> list[tuple[str, dict]]:
    """Every item node in the page's schema.org data (inside ItemLists and @graphs too)."""
    found: list[tuple[str, dict]] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "{}", strict=False)
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop(0)
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            for key in ("@graph", "itemListElement", "item", "hasPart", "subjectOf", "mainEntity", "about",
                        "hasOfferCatalog", "itemOffered", "containsPlace", "subEvent", "workFeatured", "makesOffer"):
                inner = node.get(key)
                if isinstance(inner, (list, dict)):
                    stack.extend(inner if isinstance(inner, list) else [inner])
            types = node.get("@type")
            types = [types] if isinstance(types, str) else (types or [])
            kind = next((SCHEMA_KIND[t.lower()] for t in types if isinstance(t, str) and t.lower() in SCHEMA_KIND), None)
            if kind and kind != "offer" or (kind == "offer" and node.get("name")):
                found.append((kind, node))
    return found


def _from_jsonld(kind: str, node: dict, page_url: str) -> dict | None:
    name = _clean(node.get("name") or node.get("headline"), 300)
    if not name:
        return None
    offers = node.get("offers")
    price, currency = _price_text(offers.get("price") or offers.get("lowPrice")) if isinstance(offers, dict) else \
        _price_text(offers) if isinstance(offers, list) else ("", "")
    if isinstance(offers, dict):
        currency = currency or str(offers.get("priceCurrency") or "")
    elif isinstance(offers, list) and offers and isinstance(offers[0], dict):
        currency = currency or str(offers[0].get("priceCurrency") or "")
    if not price and node.get("price"):
        price, currency = _price_text(node.get("price"))[0], str(node.get("priceCurrency") or "")
    url = node.get("url") or node.get("@id") or ""
    url = urljoin(page_url, url) if isinstance(url, str) and url and not url.startswith("_:") else ""
    image = _image(node.get("image") or node.get("photo") or node.get("thumbnailUrl"))
    return {"url": url, "name": name, "description": _clean(node.get("description")),
            "price": price, "currency": currency, "image_url": urljoin(page_url, image) if image else None,
            "kind": kind, "origin": "jsonld"}


# ---------------------------------------------------------------- data in scripts / JSON
NAME_RE = re.compile(r"^(title|name|heading|label|product_?name|course_?name|program_?name|package_?name|trip_?name)"
                     r"(_?(ar|en|ms|fr))?$", re.I)
DESC_RE = re.compile(r"(desc|summary|subtitle|excerpt|overview|short_?text|intro|about|details)", re.I)
PRICE_RE = re.compile(r"(price|prices|cost|fee|amount|tuition|rate)", re.I)
IMG_RE = re.compile(r"(img|image|photo|thumb|cover|picture|banner|poster|gallery)", re.I)
DUR_RE = re.compile(r"(duration|days|nights|hours|length)", re.I)
LINK_RE = re.compile(r"^(url|link|href|permalink|path|canonical_?url|detail_?url|page_?url)$", re.I)
SLUG_RE = re.compile(r"^(slug|handle|id|code|key|uid)$", re.I)


def _pick(obj: dict, pattern: re.Pattern, lang: str, test=None) -> tuple[str, Any]:  # noqa: ANN001
    """The best key of obj matching pattern: the user's language first, then English, then any."""
    keys = [k for k in obj if isinstance(k, str) and pattern.search(k) and obj[k] not in (None, "", [], {})]
    if test:
        keys = [k for k in keys if test(obj[k])]
    if not keys:
        return "", None
    order = sorted(keys, key=lambda k: (0 if k.lower().endswith(("_" + lang, lang.upper())) else
                                        1 if not re.search(r"_(ar|en|ms|fr)$", k, re.I) else
                                        2 if k.lower().endswith("_en") else 3, len(k)))
    return order[0], obj[order[0]]


def _text_value(v: Any) -> bool:
    return isinstance(v, str) and 2 < len(v.strip()) < 400


def _item_from_object(obj: dict, page_url: str, lang: str) -> dict | None:
    """An item-like JSON object → item (a name plus at least two of price / image / description / duration)."""
    nk, name = _pick(obj, NAME_RE, lang, _text_value)
    if not nk:
        return None
    _dk, desc = _pick(obj, DESC_RE, lang, lambda v: isinstance(v, str) and len(v.strip()) > 10)
    price_obj = {k: v for k, v in obj.items() if isinstance(k, str) and not re.search(r"(note|text|label|desc|info|policy|rule)", k, re.I)}
    _pk, price_v = _pick(price_obj, PRICE_RE, lang,
                         lambda v: bool(_price_text(v)[0]) and not (isinstance(v, str) and len(v.strip()) > 30))
    price, currency = _price_text(price_v)
    _ik, img_v = _pick(obj, IMG_RE, lang, lambda v: _image(v) is not None)
    image = _image(img_v)
    _uk, dur = _pick(obj, DUR_RE, lang, lambda v: isinstance(v, (int, float, str)) and str(v).strip() != "")
    signals = sum(bool(x) for x in (price, image, desc, dur))
    if signals < 2:
        return None
    cur_k, cur = _pick(obj, re.compile(r"^(currency|price_?currency|currency_?code)$", re.I), lang,
                       lambda v: isinstance(v, str) and len(v) <= 5)
    _lk, link = _pick(obj, LINK_RE, lang, lambda v: isinstance(v, str) and len(v) > 1)
    slug = next((obj[k] for k in ("slug", "handle", "permalink_slug", "id", "code", "key", "uid")
                 if isinstance(obj.get(k), (str, int)) and str(obj[k]).strip()), None)
    extra = []
    days = next((obj[k] for k in obj if isinstance(k, str) and re.search(r"days", k, re.I)
                 and isinstance(obj[k], (int, str))), None)
    nights = next((obj[k] for k in obj if isinstance(k, str) and re.search(r"nights", k, re.I)
                   and isinstance(obj[k], (int, str))), None)
    if days or nights:
        extra.append(" / ".join(x for x in [f"{days} days" if days else "", f"{nights} nights" if nights else ""] if x))
    elif dur and not isinstance(dur, bool):
        extra.append(f"Duration: {dur}")
    description = _clean(desc) if desc else ""
    if extra:
        description = (description + "\n" + " · ".join(extra)).strip()
    keys = " ".join(obj).lower()
    kind = ("course" if re.search(r"instructor|lesson|curriculum|students|course|syllabus", keys) else
            "offer" if re.search(r"night|itinerary|destination|hotel|tour|trip|flight", keys) else
            "event" if re.search(r"start_?date|venue|event", keys) else "product")
    return {"url": urljoin(page_url, link) if link else "", "slug": str(slug) if slug is not None else "",
            "name": _clean(name, 300), "description": description, "price": price,
            "currency": str(cur or currency or ""), "image_url": urljoin(page_url, image) if image else None,
            "kind": kind, "origin": "data"}


def items_in_data(data: Any, page_url: str, lang: str = "ar", single: bool = False) -> list[dict]:
    """Walk any JSON: arrays of item-like objects become items (an item's own lists are not walked)."""
    out: list[dict] = []

    def walk(node: Any, depth: int) -> None:
        if depth > 12 or len(out) >= MAX_ITEMS:
            return
        if isinstance(node, list):
            dicts = [x for x in node if isinstance(x, dict)]
            items = [i for i in (_item_from_object(x, page_url, lang) for x in dicts) if i]
            if items and len(items) >= max(1, len(dicts) // 2):
                out.extend(items)
                return
            for x in node:
                walk(x, depth + 1)
        elif isinstance(node, dict):
            if single:
                item = _item_from_object(node, page_url, lang)
                if item:
                    out.append(item)
                    return
            for v in node.values():
                walk(v, depth + 1)

    walk(data, 0)
    return out


_ASSIGN = re.compile(r"(?:=|:|\()\s*(?=[\[{])")


def _json_blobs(text: str, limit: int = 25) -> list[Any]:
    """JSON values written into scripts (`window.DATA = {...}`, `JSON.parse('...')`, Next.js data)."""
    blobs: list[Any] = []
    for m in re.finditer(r"JSON\.parse\(\s*(['\"])(.+?)\1\s*\)", text, re.S):
        try:
            blobs.append(json.loads(json.loads(f'"{m.group(2)}"')))
        except ValueError:
            continue
    for m in _ASSIGN.finditer(text):
        if len(blobs) >= limit:
            break
        start = m.end()
        chunk = _balanced(text, start)
        if not chunk or len(chunk) < 40:
            continue
        try:
            blobs.append(json.loads(chunk))
        except ValueError:
            continue
    return blobs


def _balanced(text: str, start: int, max_len: int = 3_000_000) -> str | None:
    opening = text[start]
    closing = {"{": "}", "[": "]"}[opening]
    depth, i, in_str, esc = 0, start, False, False
    end = min(len(text), start + max_len)
    while i < end:
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1] if ch == closing else None
        i += 1
    return None


def _script_data(client: httpx.Client | None, soup: BeautifulSoup, page_url: str, lang: str,
                 deadline: float) -> list[dict]:
    texts = []
    nxt = soup.find("script", id="__NEXT_DATA__")
    if nxt and nxt.string:
        texts.append(nxt.string)
    for tag in soup.find_all("script"):
        if tag.get("src") or tag.get("type") in ("application/ld+json",):
            continue
        body = tag.string or ""
        if 60 < len(body) < 3_000_000:
            texts.append(body)
    if client:                         # the site's own small data files (data.js, products.json…)
        srcs = [urljoin(page_url, t["src"]) for t in soup.find_all("script", src=True)]
        srcs = [s for s in srcs if _same_site(s, page_url) and not re.search(r"(jquery|bootstrap|analytics|gtag|"
                                                                               r"webpack|polyfill|vendor|chunk|"
                                                                               r"framework|runtime)", s, re.I)]
        for src in srcs[:8]:
            if time.monotonic() > deadline:
                break
            r = _get(client, src, 3_000_000)
            if r is not None and len(r.text) < 3_000_000:
                texts.append(r.text)
    items: list[dict] = []
    for text in texts:
        for blob in _json_blobs(text):
            items += items_in_data(blob, page_url, lang)
        if len(items) >= MAX_ITEMS:
            break
    return items


# ---------------------------------------------------------------- links to item pages
def _template(path: str) -> str:
    parts = [p for p in unquote(path).split("/") if p]
    out = []
    for i, p in enumerate(parts):
        if re.fullmatch(r"\d+", p):
            out.append("{n}")
        elif i == len(parts) - 1 and len(parts) > 1:
            out.append("{s}")
        else:
            out.append(p.lower())
    return "/" + "/".join(out)


def item_links(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """Links that repeat as cards (same path pattern, different item): [{url, name, image}]."""
    page_path = urlparse(page_url).path.rstrip("/")
    groups: dict[str, dict[str, dict]] = defaultdict(dict)
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:", "whatsapp:")):
            continue
        link = urljoin(page_url, href).split("#")[0]
        if not _same_site(link, page_url):
            continue
        path = urlparse(link).path.rstrip("/")
        if not path or path == page_path or NAV_WORDS.search(unquote(path)):
            continue
        if a.find_parent(["nav", "header", "footer"]):
            continue
        tpl = _template(path)
        entry = groups[tpl].setdefault(link, {"url": link, "name": "", "image": None, "score": 0})
        img = a.find("img")
        if img:
            src = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
            if src and not src.startswith("data:") and not _looks_like_logo(src):
                entry["image"] = entry["image"] or urljoin(page_url, src)
            entry["score"] += 2
        text = a.get_text(" ", strip=True)
        heading = a.find(["h1", "h2", "h3", "h4", "h5"])
        if heading:
            entry["name"] = entry["name"] or _clean(heading.get_text(" ", strip=True), 300)
            entry["score"] += 2
        elif len(text) > len(entry["name"]) and len(text) > 8:
            entry["name"] = _clean(text, 300)
            entry["score"] += 1
    best, best_score = [], 0
    for tpl, links in groups.items():
        if len(links) < 2 or tpl.count("/") < 1:
            continue
        score = len(links) * 2 + sum(x["score"] for x in links.values()) + (6 if ITEM_PATH.search(tpl) else 0) \
            + (4 if "{n}" in tpl or "{s}" in tpl else 0)
        if score > best_score:
            best, best_score = list(links.values()), score
    return best[:MAX_PAGES]


# ---------------------------------------------------------------- one page
def _meta(soup: BeautifulSoup):
    def get(*names):
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n}) \
                or soup.find("meta", attrs={"itemprop": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None
    return get


def _content_image(soup: BeautifulSoup, page_url: str) -> str | None:
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
        if not src or src.startswith("data:") or _looks_like_logo(src) or img.find_parent(["header", "nav", "footer"]):
            continue
        try:
            if int(img.get("width") or 400) < 200:
                continue
        except ValueError:
            pass
        return urljoin(page_url, src)
    return None


def page_item(soup: BeautifulSoup, page_url: str, lang: str = "ar", force: bool = False) -> dict | None:
    """The one product/service a page is about: schema.org first, then share tags."""
    meta = _meta(soup)
    nodes = _jsonld_nodes(soup)
    if nodes:
        primary = next((n for n in nodes if (n[1].get("url") or "").rstrip("/") == page_url.rstrip("/")), nodes[0])
        item = _from_jsonld(*primary, page_url)
        if item:
            item["url"] = page_url
            if not item["image_url"] or _looks_like_logo(item["image_url"]):
                og = meta("og:image")
                item["image_url"] = og if og and not _looks_like_logo(og) else _content_image(soup, page_url)
            return item
    og_type = (meta("og:type") or "").lower()
    title = meta("og:title") or (soup.title.get_text(strip=True) if soup.title else "")
    has_price = bool(meta("product:price:amount", "og:price:amount", "price"))
    if not title or not (force or has_price or og_type.startswith("product") or ITEM_PATH.search(urlparse(page_url).path)):
        return None
    image = meta("og:image", "twitter:image")
    if not image or _looks_like_logo(image):
        image = _content_image(soup, page_url) or image
    title = re.split(r"\s+[|–—-]\s+[^|–—-]{2,40}$", _clean(title, 300))[0]
    return {"url": page_url, "name": title, "description": _clean(meta("og:description", "description")),
            "price": meta("product:price:amount", "og:price:amount", "price") or "",
            "currency": meta("product:price:currency", "og:price:currency", "priceCurrency") or "",
            "image_url": urljoin(page_url, image) if image else None, "kind": "product", "origin": "page"}


def read_page(client: httpx.Client, url: str, lang: str = "ar", force: bool = False) -> dict | None:
    r = _get(client, url)
    if not _is_html(r):
        return None
    return page_item(BeautifulSoup(r.text, "html.parser"), str(r.url), lang, force)


# ---------------------------------------------------------------- stores
def _shopify(client: httpx.Client, base: str) -> list[dict]:
    r = _get(client, f"{base}/products.json?limit=250")
    if r is None or '"products"' not in r.text[:300]:
        return []
    try:
        data = r.json().get("products", [])
    except ValueError:
        return []
    out = []
    for p in data[:MAX_ITEMS]:
        variant = (p.get("variants") or [{}])[0]
        image = (p.get("images") or [{}])[0].get("src")
        out.append({"url": f"{base}/products/{p.get('handle')}", "name": p.get("title") or "",
                    "description": _clean(p.get("body_html")), "price": str(variant.get("price") or ""),
                    "currency": "", "image_url": image, "kind": "product", "origin": "shopify"})
    return out


def _woocommerce(client: httpx.Client, base: str) -> list[dict]:
    r = _get(client, f"{base}/wp-json/wc/store/v1/products?per_page=100")
    if r is None or not r.text.strip().startswith("["):
        return []
    out = []
    try:
        rows = r.json()
    except ValueError:
        return []
    for p in rows[:MAX_ITEMS]:
        prices = p.get("prices") or {}
        price = prices.get("price") or ""
        minor = int(prices.get("currency_minor_unit") or 0)
        if price and minor:
            try:
                price = f"{int(price) / 10 ** minor:.{minor}f}"
            except ValueError:
                pass
        image = (p.get("images") or [{}])[0].get("src")
        out.append({"url": p.get("permalink") or "", "name": _clean(p.get("name"), 300),
                    "description": _clean(p.get("short_description") or p.get("description")),
                    "price": price, "currency": prices.get("currency_code") or "", "image_url": image,
                    "kind": "product", "origin": "woocommerce"})
    return [x for x in out if x["url"]]


def _sitemap_urls(client: httpx.Client, base: str, deadline: float) -> list[str]:
    pages: list[str] = []
    todo, seen = [f"{base}/sitemap.xml"], 0
    while todo and seen < 6 and time.monotonic() < deadline:
        r = _get(client, todo.pop(0), 4_000_000)
        seen += 1
        if r is None:
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)[:5000]:
            if loc.endswith(".xml") or ".xml?" in loc:
                if re.search(r"product|course|service|event|tour|package|program|listing|offer|trip", loc, re.I):
                    todo.append(loc)
            elif ITEM_PATH.search(unquote(urlparse(loc).path)):
                pages.append(loc)
    return list(dict.fromkeys(pages))


# ---------------------------------------------------------------- the whole search
def _finish(items: list[dict], method: str, page_url: str, extra: dict | None = None) -> dict:
    seen, out = set(), []
    for x in items:
        name = (x.get("name") or "").strip()
        if not name:
            continue
        if not x.get("url"):
            slug = x.get("slug") or re.sub(r"\W+", "-", name.lower())[:60]
            x["url"] = f"{page_url.split('#')[0]}#item-{slug}"
        key = x["url"] if "#item-" not in x["url"] else name.lower()
        if key in seen or name.lower() in seen:
            continue
        seen.update({key, name.lower()})
        x.pop("slug", None)
        x["url"] = x["url"][:1000]
        x["name"] = name[:300]
        x["currency"] = (x.get("currency") or "")[:10]
        x["price"] = str(x.get("price") or "")[:60]
        out.append(x)
    return {"items": out[:MAX_ITEMS], "method": method, "base": _base(page_url), "page": page_url, **(extra or {})}


def _link_items_with_details(client: httpx.Client, links: list[dict], lang: str, deadline: float) -> list[dict]:
    def one(entry: dict) -> dict | None:
        if time.monotonic() > deadline:
            item = None
        else:
            item = read_page(client, entry["url"], lang, force=True)
        if item is None and entry.get("name"):
            item = {"url": entry["url"], "name": entry["name"], "description": "", "price": "", "currency": "",
                    "image_url": entry.get("image"), "kind": "product", "origin": "links"}
        elif item is not None and (not item.get("image_url") or _looks_like_logo(item["image_url"])) and entry.get("image"):
            item["image_url"] = entry["image"]
        return item
    with ThreadPoolExecutor(max_workers=6) as pool:
        return [x for x in pool.map(one, links) if x]


def from_html(html: str, page_url: str, lang: str = "ar", client: httpx.Client | None = None,
              deadline: float | None = None) -> dict:
    """Items of one page's HTML (used for pages read over HTTP and pages built in the browser)."""
    deadline = deadline or time.monotonic() + STATIC_BUDGET
    soup = BeautifulSoup(html, "html.parser")
    nodes = _jsonld_nodes(soup)
    jsonld = [i for i in (_from_jsonld(k, n, page_url) for k, n in nodes) if i]
    with_url = [i for i in jsonld if i["url"] and i["url"].rstrip("/") != page_url.rstrip("/")]
    if len(jsonld) >= 2 and (with_url or len(jsonld) >= 3):
        return _finish(jsonld, "jsonld-list", page_url)
    links = item_links(soup, page_url)
    data_items = _script_data(client, soup, page_url, lang, deadline)
    if len(data_items) >= 2 or (data_items and not links and len(jsonld) != 1):
        for it in data_items:              # data items borrow the link of their card when there is one
            if not it["url"] and it.get("slug"):
                hit = next((l["url"] for l in links if str(it["slug"]) in unquote(l["url"])), None)
                it["url"] = hit or ""
        return _finish(data_items, "data", page_url)
    if len(links) >= 2:
        if client is not None:
            return _finish(_link_items_with_details(client, links, lang, deadline), "links", page_url)
        return _finish([{"url": l["url"], "name": l["name"], "description": "", "price": "", "currency": "",
                         "image_url": l["image"], "kind": "product", "origin": "links"} for l in links if l["name"]],
                       "links", page_url)
    single = page_item(soup, page_url, lang, force=bool(jsonld) or bool(ITEM_PATH.search(urlparse(page_url).path)))
    if single:
        return _finish([single], "page", page_url)
    thin = len(soup.get_text(" ", strip=True)) < 600 or len(soup.find_all("a")) < 8
    return _finish([], "none", page_url, {"thin": thin})


def discover(site: str, lang: str = "ar") -> dict:
    """Everything a link offers (static reading over HTTP): {"items", "method", "base", "page", "thin"?}."""
    url = _normalise(site)
    base = _base(url)
    deadline = time.monotonic() + STATIC_BUDGET
    is_root = urlparse(url).path in ("", "/") and not urlparse(url).query
    with _client() as client:
        r = _get(client, url)
        page_url = str(r.url) if r is not None else url
        result = from_html(r.text, page_url, lang, client, deadline) if _is_html(r) else \
            _finish([], "none", page_url, {"thin": True, "blocked": r is None})
        if result["items"] or not is_root:
            return result
        items = _shopify(client, base)
        if items:
            return _finish(items, "shopify", page_url)
        items = _woocommerce(client, base)
        if items:
            return _finish(items, "woocommerce", page_url)
        urls = _sitemap_urls(client, base, deadline)[:MAX_PAGES]
        if urls:
            with ThreadPoolExecutor(max_workers=6) as pool:
                found = [x for x in pool.map(lambda u: read_page(client, u, lang)
                                             if time.monotonic() < deadline else None, urls) if x]
            if found:
                return _finish(found, "sitemap", page_url)
        return result


# ---------------------------------------------------------------- pages built in the browser
async def render(url: str) -> dict | None:
    """Open the page in the headless browser: its final HTML, visible text and the JSON it loaded."""
    from .renderer import renderer
    renderer._bind_loop()
    async with renderer._lock:
        browser = await renderer._ensure()
    jsons: list[Any] = []
    ctx = await browser.new_context(user_agent=BROWSER_UA, locale="ar", viewport={"width": 1366, "height": 900})
    page = await ctx.new_page()

    async def on_response(resp) -> None:  # noqa: ANN001
        try:
            if "json" in (resp.headers.get("content-type") or "") and len(jsons) < 30:
                body = await resp.body()
                if len(body) < 4_000_000:
                    jsons.append(json.loads(body))
        except Exception:  # noqa: BLE001
            pass

    page.on("response", lambda r: asyncio.ensure_future(on_response(r)))
    try:
        try:
            await page.goto(url, wait_until="networkidle", timeout=RENDER_TIMEOUT * 1000)
        except Exception:  # noqa: BLE001 - busy pages never go idle: use what has loaded
            pass
        for _ in range(4):                      # lazy lists load while scrolling
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(600)
        html = await page.content()
        text = await page.evaluate("document.body ? document.body.innerText : ''")
        images = await page.evaluate("""[...document.images].filter(i => i.naturalWidth >= 200)
            .slice(0, 40).map(i => ({src: i.currentSrc || i.src, alt: i.alt || ''}))""")
        links = await page.evaluate("""[...document.querySelectorAll('a[href]')].slice(0, 300)
            .map(a => ({href: a.href, text: (a.innerText || '').trim().slice(0, 120)}))""")
        return {"url": page.url, "html": html, "text": text or "", "images": images, "links": links, "json": jsons}
    except Exception as exc:  # noqa: BLE001
        log.warning("render failed for %s: %s", url, exc)
        return None
    finally:
        await ctx.close()


AI_TOOL = {
    "name": "list_offerings",
    "description": "List every product, service, course, travel programme or offer shown on the page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "description": {"type": "string", "description": "1-3 sentences from the page"},
                "price": {"type": "string"}, "currency": {"type": "string"},
                "image_url": {"type": "string", "description": "one of the given image URLs, or empty"},
                "url": {"type": "string", "description": "one of the given links for this item, or empty"},
                "kind": {"type": "string", "enum": ["product", "service", "course", "offer", "event"]}},
                "required": ["name"]}},
        },
        "required": ["items"],
    },
}


async def ai_items(page: dict, lang: str) -> list[dict]:
    """The AI reads the page (text, photos, links) and lists what it offers. Only facts from the page."""
    from . import generator
    if not generator.ai_available():
        return []
    imgs = "\n".join(f"- {i['src']} ({i['alt'][:60]})" for i in page.get("images", [])[:30])
    links = "\n".join(f"- {l['href']} :: {l['text'][:80]}" for l in page.get("links", [])
                      if l.get("text") and _same_site(l["href"], page["url"]))[:6000]
    user = (f"Page: {page['url']}\n\nVisible text:\n{page['text'][:12000]}\n\nImages:\n{imgs}\n\nLinks:\n{links}\n\n"
            "List each item the business offers on this page (products, services, courses, travel programmes, "
            "packages, offers). Copy names, prices and details exactly from the page; never invent anything. "
            "Skip menus, categories, blog posts and contact details. Use the list_offerings tool.")
    system = "You extract structured catalogue data from web pages. You only report what the page shows."
    try:
        data = await generator._call_model(system, user, AI_TOOL, max_tokens=4000)
    except Exception as exc:  # noqa: BLE001
        log.warning("AI product reading failed: %s", exc)
        return []
    out = []
    for x in (data.get("items") or [])[:MAX_ITEMS]:
        if not isinstance(x, dict) or not str(x.get("name") or "").strip():
            continue
        link = str(x.get("url") or "")
        img = str(x.get("image_url") or "")
        out.append({"url": link if link.startswith("http") and _same_site(link, page["url"]) else "",
                    "name": _clean(x.get("name"), 300), "description": _clean(x.get("description")),
                    "price": _clean(x.get("price"), 40), "currency": _clean(x.get("currency"), 10),
                    "image_url": img if img.startswith("http") else None,
                    "kind": x.get("kind") if x.get("kind") in ("product", "service", "course", "offer", "event")
                    else "product", "origin": "ai"})
    return out


async def discover_full(site: str, lang: str = "ar") -> dict:
    """Static reading, then the headless browser for JavaScript pages, then the AI."""
    result = await asyncio.to_thread(discover, site, lang)
    first = result["items"][0] if result["items"] else {}
    weak = result["method"] == "page" and not (first.get("image_url") and (first.get("description") or first.get("price")))
    if result["items"] and not weak:
        return result
    page = await render(result.get("page") or _normalise(site))
    if page is None:
        return {**result, "blocked": True} if not result["items"] else result
    page_url = page["url"]

    def from_rendered() -> dict:
        with _client() as client:
            found = from_html(page["html"], page_url, lang, client, time.monotonic() + 40)
        if len(found["items"]) < 2:
            data_items = []
            for blob in page["json"]:
                data_items += items_in_data(blob, page_url, lang, single=len(page["json"]) <= 3)
            if len(data_items) > len(found["items"]):
                links = [{"url": l["href"]} for l in page["links"]]
                for it in data_items:
                    if not it["url"] and it.get("slug"):
                        it["url"] = next((l["url"] for l in links if f"/{it['slug']}" in unquote(l["url"])), "")
                return _finish(data_items, "browser-data", page_url)
        return {**found, "method": "browser-" + found["method"]}

    found = await asyncio.to_thread(from_rendered)
    if found["items"] and (len(found["items"]) >= len(result["items"])):
        return found
    if result["items"]:
        return result
    items = await ai_items(page, lang)
    if items:
        return _finish(items, "ai", page_url)
    host = urlparse(page_url).netloc.lower()
    return {**found, "blocked": not page["text"].strip() or any(h in host for h in PROTECTED_HOSTS) or bool(re.search(
        r"captcha|verify you are human|access denied|robot|log ?in|sign ?in|التحقق|تسجيل الدخول", page["text"][:3000], re.I))}


def as_article(p) -> tuple[str, str]:  # noqa: ANN001
    """Title and body for the post writer."""
    lines = [p.description or ""]
    if p.price:
        lines.append(f"Price: {p.price} {p.currency}".strip())
    lines.append(f"Type: {p.kind}." + (f" Page: {p.url}" if p.url.startswith("http") else ""))
    return p.name, "\n".join(x for x in lines if x)
