"""RSS full content and clear messages for sites that block automated access."""
import httpx

from app.services import scraper

FEED = """<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>t</title><item><title>Langkawi news</title><link>https://ex.com/a/</link>
<description>short</description><content:encoded><![CDATA[<p>""" + ("Full article text. " * 40) + """</p>]]></content:encoded>
</item></channel></rss>"""


def test_feed_uses_full_content(monkeypatch):
    real = httpx.Client
    monkeypatch.setattr(scraper.httpx, "Client",
                        lambda *a, **kw: real(*a, **{**kw, "transport": httpx.MockTransport(lambda r: httpx.Response(200, text=FEED))}))
    items, status = scraper.fetch_feed("https://ex.com/feed/")
    assert status == 200 and len(items[0].body) > 400


def test_403_is_explained():
    req = httpx.Request("GET", "https://blocked.example/")
    exc = httpx.HTTPStatusError("403", request=req, response=httpx.Response(403, request=req))
    msg = scraper.friendly_error(exc)
    assert "RSS" in msg and "403" in msg
