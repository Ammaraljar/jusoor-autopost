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
            anchors = soup.select(source.link_selector) if source.link_selector else soup.find_all("a", href=True)
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
    image = meta("og:image", "twitter:image")
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
    return ScrapedArticle(url=url, title=title, body=body.strip(), image_url=urljoin(url, image) if image else None,
                          published_at=published)


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
        summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)
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
        return {"ok": False, "error": str(exc)[:500]}
