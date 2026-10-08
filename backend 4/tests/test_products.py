"""Products from the company's own site become posts with their link."""
import json

import httpx

from app.db import Draft, Product, session_scope
from app.services import products

SHOP_PAGE = """<html><head><script type="application/ld+json">%s</script>
<meta property="og:image" content="https://shop.test/img/kit.jpg"></head><body>Kit</body></html>""" % json.dumps({
    "@context": "https://schema.org", "@type": "Course", "name": "Leadership Masterclass",
    "description": "Three days of practical leadership training with an accredited certificate.",
    "offers": {"@type": "Offer", "price": "1200", "priceCurrency": "MYR"}})


def fake_shop(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.endswith("/products.json?limit=250") or "/wp-json/" in url:
        return httpx.Response(404)
    if url.endswith("/sitemap.xml"):
        return httpx.Response(200, text="<urlset><url><loc>https://shop.test/courses/leadership</loc></url>"
                                        "<url><loc>https://shop.test/about</loc></url></urlset>")
    if url.endswith("/courses/leadership"):
        return httpx.Response(200, text=SHOP_PAGE, headers={"content-type": "text/html"})
    return httpx.Response(200, text="<html><body></body></html>", headers={"content-type": "text/html"})


def test_discover_reads_schema_org_items(monkeypatch):
    transport = httpx.MockTransport(fake_shop)
    monkeypatch.setattr(products, "_client", lambda: httpx.Client(transport=transport, follow_redirects=True))
    found = products.discover("shop.test")
    assert found["method"] == "pages"
    item = found["items"][0]
    assert item["name"] == "Leadership Masterclass" and item["kind"] == "course"
    assert item["price"] == "1200" and item["currency"] == "MYR"


def test_sync_and_product_post_carries_the_link(client, monkeypatch):
    transport = httpx.MockTransport(fake_shop)
    monkeypatch.setattr(products, "_client", lambda: httpx.Client(transport=transport, follow_redirects=True))
    r = client.post("/api/products/sync", json={"url": "https://shop.test"})
    assert r.status_code == 200 and r.json()["added"] == 1
    pid = client.get("/api/products").json()[0]["id"]
    assert client.post(f"/api/products/{pid}/draft").status_code == 200
    with session_scope() as db:
        p = db.get(Product, pid)
        d = db.get(Draft, p.draft_id)
        assert p.status == "drafted" and d.link_url == "https://shop.test/courses/leadership"
        from app.services import pipeline
        assert "https://shop.test/courses/leadership" in pipeline.compose_caption(d)
        did = d.id
    client.delete(f"/api/drafts/{did}")
    client.post("/api/products/bulk", json={"ids": [pid], "action": "delete"})
