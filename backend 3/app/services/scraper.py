"""Collect articles from RSS feeds and news websites."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 JusoorAutoPost/1.0")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en,ar;q=0.8"}
SKIP_PATTERNS = re.compile(r"/(tag|tags|author|authors|category|categories|video|videos|gallery|login|"
                           r"subscribe|search|about|contact|privacy|terms)(/|$)", re.I)


@dataclass
class ScrapedArticle:
    url: str
    title: str = ""
    body: str = ""
    image_url: str | None = None
    published_at: datetime | None = None
    extra: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        return title_fingerprint(self.title)


@dataclass
class ListingResult:
    links: list[str]
    http_status: int | None


def title_fingerprint(title: str) -> str:
    norm = re.sub(r"[^\w\s]", "", (title or "").lower())
    norm = " ".join(sorted(set(norm.split())))
    return hashlib.sha1(norm.encode()).hexdigest()


def _client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=25, follow_redirects=True)


def _listing_urls(source) -> list[str]:
    urls = source.listing_urls or []
    if isinstance(urls, str):
        try:
            urls = json.loads(urls)
        except ValueError:
            urls = [u.strip() for u in urls.splitlines() if u.strip()]
    return urls or ([source.base_url] if source.base_url else [])


def discover_links(source, limit: int = 20) -> ListingResult:
    """Return candidate article URLs for a website source."""
    base_host = urlparse(source.base_url or "").netloc
    found: list[str] = []
    status = None
    with _client() as client:
        for listing in _listing_urls(source):
            resp = client.get(listing)
            status = resp.status_code
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            anchors = soup.select(source.link_selector) if source.link_selector else []
            if not anchors:
                # The site changed its markup (or no selector): scan every link, the pattern still filters
                anchors = soup.find_all("a", href=True)
            listing_path = urlparse(listing).path.rstrip("/")
            for a in anchors:
                href = a.get("href")
                if not href:
                    continue
                url = urljoin(listing, href).split("#")[0]
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    continue
                if base_host and parsed.netloc and not parsed.netloc.endswith(base_host.replace("www.", "")):
                    continue
                if source.link_pattern:
                    if not re.search(source.link_pattern, url):
                        continue
                elif not source.link_selector and getattr(source, "purpose", "") == "own_site":
                    # the company's own site: any inner page of the site may be an article/offer
                    path = parsed.path.rstrip("/")
                    if path == listing_path or not path or SKIP_PATTERNS.search(path) or \
                            re.search(r"\.(jpg|jpeg|png|pdf|zip)$|/(cart|checkout|account|wp-)", path, re.I):
                        continue
                    if path.count("/") < 2 and path.split("/")[-1].count("-") < 2:
                        continue
                elif not source.link_selector:
                    # Heuristic: article URLs are deeper than the listing and usually contain a date or long slug
                    path = parsed.path.rstrip("/")
                    if path == listing_path or SKIP_PATTERNS.search(path):
                        continue
                    slug = path.split("/")[-1]
                    has_date = re.search(r"/20\d{2}/\d{1,2}/", path) is not None
                    if not (has_date or (slug.count("-") >= 3 and len(slug) > 20)):
                        continue
                if url not in found:
                    found.append(url)
                if len(found) >= limit:
                    return ListingResult(found, status)
    return ListingResult(found, status)


FEED_PATHS = ("/feed", "/rss", "/feed.xml", "/rss.xml", "/blog/feed", "/news/feed", "/atom.xml")
LISTING_PATHS = ("/blog", "/news", "/articles", "/offers", "/programs", "/events", "/media", "/ar/blog", "/en/blog")


def detect_site(url: str) -> dict:
    """Find a website's RSS feed and its news/blog listing pages."""
    out: dict = {"feed_url": None, "listing_urls": [url]}
    try:
        with _client() as client:
            resp = client.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            link = soup.find("link", attrs={"type": re.compile(r"(rss|atom)\+xml")})
            candidates = [urljoin(url, link["href"])] if link and link.get("href") else []
            candidates += [urljoin(url, p) for p in FEED_PATHS]
            for feed in candidates:
                try:
                    r = client.get(feed)
                    if r.status_code == 200 and feedparser.parse(r.content).entries:
                        out["feed_url"] = feed
                        break
                except httpx.HTTPError:
                    continue
            host = urlparse(url).netloc
            listings = [url]
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"]).split("#")[0].rstrip("/")
                if urlparse(href).netloc == host and urlparse(href).path.lower() in LISTING_PATHS:
                    listings.append(href)
            out["listing_urls"] = list(dict.fromkeys(listings))[:5]
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def fetch_article(url: str, body_selector: str | None = None) -> ScrapedArticle:
    with _client() as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text
    return parse_article(url, html, body_selector)


def parse_article(url: str, html: str, body_selector: str | None = None) -> ScrapedArticle:
    soup = BeautifulSoup(html, "html.parser")

    def meta(*names: str) -> str | None:
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    title = meta("og:title", "twitter:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
    image = find_image(soup, url, meta, body_selector)
    published = _parse_date(meta("article:published_time", "og:published_time", "pubdate", "date",
                                 "parsely-pub-date", "publish-date"))
    body = ""
    if body_selector:
        nodes = soup.select(body_selector)
        body = "\n\n".join(p.get_text(" ", strip=True) for n in nodes for p in (n.find_all("p") or [n]))
    if not body:
        body = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True) or ""
    if published is None:
        md = trafilatura.extract_metadata(html)
        if md and md.date:
            published = _parse_date(md.date)
    return ScrapedArticle(url=url, title=title, body=body.strip(), image_url=image, published_at=published)


_BAD_IMG = re.compile(r"(logo|icon|avatar|sprite|placeholder|blank|pixel|spacer|badge|emoji|gravatar|"
                      r"\.svg($|\?)|\.gif($|\?)|data:)", re.I)


def _img_src(tag) -> str:
    for attr in ("data-src", "data-lazy-src", "data-original", "src"):
        if tag.get(attr) and not str(tag[attr]).startswith("data:"):
            return str(tag[attr])
    srcset = tag.get("srcset") or tag.get("data-srcset") or ""
    if srcset:
        return srcset.split(",")[-1].strip().split(" ")[0]       # largest candidate
    return ""


def _big_enough(tag) -> bool:
    for attr in ("width", "height"):
        try:
            if int(str(tag.get(attr, "0")).rstrip("px")) and int(str(tag.get(attr)).rstrip("px")) < 300:
                return False
        except ValueError:
            pass
    return True


def find_image(soup, url: str, meta=None, body_selector: str | None = None) -> str | None:
    """The article's main photo: social-share image, structured data, then the first large photo."""
    candidates: list[str] = []
    if meta:
        for name in ("og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"):
            value = meta(name)
            if value:
                candidates.append(value)
    link = soup.find("link", rel="image_src")
    if link and link.get("href"):
        candidates.append(link["href"])
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        for node in (data if isinstance(data, list) else [data]):
            img = node.get("image") if isinstance(node, dict) else None
            if isinstance(img, dict):
                img = img.get("url")
            if isinstance(img, list) and img:
                img = img[0].get("url") if isinstance(img[0], dict) else img[0]
            if isinstance(img, str):
                candidates.append(img)
    scope = soup.select(body_selector) if body_selector else []
    for root in (scope or [soup.find("article") or soup]):
        for tag in root.find_all("img"):
            src = _img_src(tag)
            if src and _big_enough(tag):
                candidates.append(src)
    for c in candidates:
        c = urljoin(url, c.strip())
        if c.startswith(("http://", "https://")) and not _BAD_IMG.search(c):
            return c
    return None


def image_from_html(html: str, base_url: str) -> str | None:
    """First usable photo inside an HTML fragment (e.g. an RSS item's content)."""
    if not html:
        return None
    return find_image(BeautifulSoup(html, "html.parser"), base_url)


def fetch_feed(feed_url: str, limit: int = 20) -> tuple[list[ScrapedArticle], int | None]:
    with _client() as client:
        resp = client.get(feed_url)
        status = resp.status_code
        resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    items: list[ScrapedArticle] = []
    for entry in parsed.entries[:limit]:
        image = None
        for key in ("media_content", "media_thumbnail"):
            if entry.get(key):
                image = entry[key][0].get("url")
                break
        if not image:
            for enc in entry.get("enclosures", []):
                if str(enc.get("type", "")).startswith("image"):
                    image = enc.get("href")
                    break
        published = None
        if entry.get("published_parsed"):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        # Many feeds (WordPress) carry the full article in content:encoded — prefer it over the summary
        html = ""
        for part in entry.get("content") or []:
            if len(part.get("value", "")) > len(html):
                html = part.get("value", "")
        summary = BeautifulSoup(html or entry.get("summary", ""), "html.parser").get_text(" ", strip=True)
        if not image:
            image = image_from_html(html or entry.get("summary", ""), entry.get("link", ""))
        items.append(ScrapedArticle(url=entry.get("link", ""), title=entry.get("title", ""), body=summary,
                                    image_url=image, published_at=published))
    return [i for i in items if i.url], status


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_source(source) -> dict:
    """Dry-run a source: returns a preview of what would be collected."""
    try:
        if source.kind == "rss" and source.feed_url:
            items, status = fetch_feed(source.feed_url, limit=5)
            return {"ok": bool(items), "http_status": status, "count": len(items),
                    "samples": [{"url": i.url, "title": i.title} for i in items[:5]]}
        result = discover_links(source, limit=8)
        samples = []
        for url in result.links[:2]:
            art = fetch_article(url, source.body_selector)
            samples.append({"url": url, "title": art.title, "chars": len(art.body),
                            "image": art.image_url, "published_at": art.published_at.isoformat() if art.published_at else None})
        return {"ok": bool(result.links), "http_status": result.http_status, "count": len(result.links),
                "links": result.links, "samples": samples}
    except Exception as exc:  # noqa: BLE001 - report any failure to the UI
        return {"ok": False, "error": friendly_error(exc)}


def friendly_error(exc: Exception) -> str:
    """Explain the usual failures in plain Arabic."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        url = str(exc.request.url)
        if code in (401, 403, 429):
            return (f"الموقع رفض الطلب (خطأ {code}): هذا الموقع يمنع السحب الآلي من صفحاته. "
                    "استخدم رابط RSS الخاص به إن وُجد (نوع المصدر RSS)، أو اختر مصدرًا آخر. "
                    f"الرابط: {url}")
        if code == 404:
            return f"الصفحة غير موجودة (404): {url}"
        return f"الموقع أعاد خطأ {code}: {url}"
    if isinstance(exc, httpx.TimeoutException):
        return "انتهت مهلة الاتصال بالموقع — أعد المحاولة لاحقًا"
    return str(exc)[:500]
