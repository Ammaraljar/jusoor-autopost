"""Products, services, courses, programmes and events read from the company's own website.

Order of attempts (the first that finds items wins, then page details fill the gaps):
1. Shopify stores: /products.json
2. WooCommerce stores: /wp-json/wc/store/v1/products
3. Sitemaps and the home page: pages that look like product/service/course pages, read through
   their schema.org data (JSON-LD Product, Course, Service, Event, Offer, TouristTrip…) or their
   share tags (og:title / og:image / og:description).
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from . import scraper

log = logging.getLogger(__name__)
MAX_ITEMS = 60
MAX_PAGES = 40
ITEM_PATH = re.compile(r"/(product|products|shop|store|item|items|course|courses|training|program|programs|programme|"
                       r"programmes|package|packages|tour|tours|trip|trips|service|services|event|events|offer|offers|"
                       r"menu|dish|listing|listings|property|properties|car|cars|vehicle|vehicles|collection|"
                       r"منتج|خدمة|دورة|برنامج)/[^/?#]+", re.I)
SCHEMA_KIND = {"product": "product", "productgroup": "product", "individualproduct": "product", "vehicle": "product",
               "car": "product", "book": "product", "menuitem": "product", "course": "course",
               "courseinstance": "course", "educationalprogram": "course", "service": "service",
               "event": "event", "educationevent": "event", "businessevent": "event", "offer": "offer",
               "touristtrip": "offer", "trip": "offer", "hotel": "service", "residence": "product",
               "accommodation": "product", "apartment": "product", "house": "product", "singlefamilyresidence": "product"}


def _clean(text: str | None, limit: int = 1500) -> str:
    text = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()[:limit]


def _base(url: str) -> str:
    p = urlparse(url if url.startswith("http") else "https://" + url)
    return f"{p.scheme}://{p.netloc}"


def _client() -> httpx.Client:
    return httpx.Client(headers=scraper.HEADERS, timeout=20, follow_redirects=True)


# ---------------------------------------------------------------- store platforms
def _shopify(client: httpx.Client, base: str) -> list[dict]:
    try:
        r = client.get(f"{base}/products.json", params={"limit": 250})
        if r.status_code != 200 or "products" not in r.text[:200]:
            return []
        out = []
        for p in r.json().get("products", [])[:MAX_ITEMS]:
            variant = (p.get("variants") or [{}])[0]
            image = (p.get("images") or [{}])[0].get("src")
            out.append({"url": f"{base}/products/{p.get('handle')}", "name": p.get("title") or "",
                        "description": _clean(p.get("body_html")), "price": str(variant.get("price") or ""),
                        "currency": "", "image_url": image, "kind": "product", "origin": "shopify"})
        return out
    except Exception:  # noqa: BLE001
        return []


def _woocommerce(client: httpx.Client, base: str) -> list[dict]:
    try:
        r = client.get(f"{base}/wp-json/wc/store/v1/products", params={"per_page": 100})
        if r.status_code != 200 or not r.text.strip().startswith("["):
            return []
        out = []
        for p in r.json()[:MAX_ITEMS]:
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
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------- pages
def _sitemap_urls(client: httpx.Client, base: str, depth: int = 0, url: str | None = None) -> list[str]:
    try:
        r = client.get(url or f"{base}/sitemap.xml")
        if r.status_code != 200:
            return []
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
        pages: list[str] = []
        for loc in locs:
            if loc.endswith(".xml") and depth < 2:
                if re.search(r"product|course|service|event|tour|package|program|listing|post-type", loc, re.I) \
                        or depth == 0 and len(locs) < 8:
                    pages += _sitemap_urls(client, base, depth + 1, loc)
            elif ITEM_PATH.search(urlparse(loc).path):
                pages.append(loc)
        return list(dict.fromkeys(pages))
    except Exception:  # noqa: BLE001
        return []


def _home_links(client: httpx.Client, base: str) -> list[str]:
    out: list[str] = []
    host = urlparse(base).netloc
    for path in ("", "/shop", "/products", "/services", "/courses", "/programs", "/packages", "/tours", "/events"):
        try:
            r = client.get(base + path)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                link = urljoin(base + path, a["href"]).split("#")[0].split("?")[0]
                if urlparse(link).netloc == host and ITEM_PATH.search(urlparse(link).path):
                    out.append(link.rstrip("/"))
        except Exception:  # noqa: BLE001
            continue
        if len(set(out)) >= MAX_PAGES:
            break
    return list(dict.fromkeys(out))


def _jsonld_items(soup: BeautifulSoup) -> list[dict]:
    found = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "{}")
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
            if "@graph" in node:
                stack.extend(node["@graph"] if isinstance(node["@graph"], list) else [node["@graph"]])
            types = node.get("@type")
            types = [types] if isinstance(types, str) else (types or [])
            kind = next((SCHEMA_KIND[t.lower()] for t in types if isinstance(t, str) and t.lower() in SCHEMA_KIND), None)
            if kind:
                found.append((kind, node))
    return found


def _offer_price(node: dict) -> tuple[str, str]:
    offers = node.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    if isinstance(offers, dict):
        price = offers.get("price") or offers.get("lowPrice") or ""
        return str(price), str(offers.get("priceCurrency") or "")
    return "", ""


def _image(value) -> str | None:  # noqa: ANN001
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    return value if isinstance(value, str) else None


def read_page(client: httpx.Client, url: str) -> dict | None:
    """One product/service page → item, from its schema.org data or its share tags."""
    try:
        r = client.get(url)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return None
    except Exception:  # noqa: BLE001
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    def meta(*names):
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    items = _jsonld_items(soup)
    if items:
        kind, node = items[0]
        price, currency = _offer_price(node)
        return {"url": url, "name": _clean(node.get("name"), 300) or meta("og:title") or "",
                "description": _clean(node.get("description")) or _clean(meta("og:description")),
                "price": price or (meta("product:price:amount") or ""),
                "currency": currency or (meta("product:price:currency") or ""),
                "image_url": urljoin(url, _image(node.get("image")) or meta("og:image") or "") or None,
                "kind": kind, "origin": "jsonld"}
    og_type = (meta("og:type") or "").lower()
    title = meta("og:title") or (soup.title.get_text(strip=True) if soup.title else "")
    if not title or not (og_type.startswith("product") or ITEM_PATH.search(urlparse(url).path)):
        return None
    image = meta("og:image") or scraper.find_image(soup, url, meta)
    return {"url": url, "name": _clean(title, 300), "description": _clean(meta("og:description", "description")),
            "price": meta("product:price:amount") or "", "currency": meta("product:price:currency") or "",
            "image_url": urljoin(url, image) if image else None, "kind": "product", "origin": "page"}


def discover(site: str) -> dict:
    """Everything the company sells or offers on its site: {"items": [...], "method": str}."""
    base = _base(site)
    with _client() as client:
        items = _shopify(client, base)
        method = "shopify"
        if not items:
            items, method = _woocommerce(client, base), "woocommerce"
        if not items:
            method = "pages"
            urls = _sitemap_urls(client, base) or []
            if len(urls) < 5:
                urls += _home_links(client, base)
            urls = list(dict.fromkeys(urls))[:MAX_PAGES]
            with ThreadPoolExecutor(max_workers=6) as pool:
                items = [x for x in pool.map(lambda u: read_page(client, u), urls) if x]
    seen, out = set(), []
    for x in items:
        if x["url"] in seen or not x.get("name"):
            continue
        seen.add(x["url"])
        out.append(x)
    return {"items": out[:MAX_ITEMS], "method": method, "base": base}


def as_article(p) -> tuple[str, str]:  # noqa: ANN001
    """Title and body for the post writer."""
    lines = [p.description or ""]
    if p.price:
        lines.append(f"Price: {p.price} {p.currency}".strip())
    lines.append(f"Type: {p.kind}. Page: {p.url}")
    return p.name, "\n".join(x for x in lines if x)
