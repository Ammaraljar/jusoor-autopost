"""Products / services / courses / travel programmes from any link become posts with their link."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import httpx

from app.db import Draft, Product, session_scope
from app.services import products

SHOP_PAGE = """<html><head><script type="application/ld+json">%s</script>
<meta property="og:image" content="https://shop.test/img/kit.jpg"></head><body>Kit</body></html>""" % json.dumps({
    "@context": "https://schema.org", "@type": "Course", "name": "Leadership Masterclass",
    "description": "Three days of practical leadership training with an accredited certificate.",
    "offers": {"@type": "Offer", "price": "1200", "priceCurrency": "MYR"}})

# a travel agency's offers page that lists its packages in schema.org (ItemList of Products)
ITEMLIST_PAGE = """<html><head><title>عروض سياحية ماليزيا</title><script type="application/ld+json">%s</script></head>
<body><h1>عروض سياحية ماليزيا</h1></body></html>""" % json.dumps({"@context": "https://schema.org", "@graph": [
    {"@type": "WebPage", "name": "عروض"},
    {"@type": "ItemList", "itemListElement": [
        {"@type": "Product", "name": "باقة ماليزيا لشهر العسل 8 ليالي", "url": "https://agency.test/package-honeymoon",
         "description": "سيلانجور ولنكاوي وكوالالمبور مع الفنادق والجولات.", "image": "https://agency.test/img/h.jpg",
         "offers": {"@type": "Offer", "price": "2268", "priceCurrency": "SAR"}},
        {"@type": "Product", "name": "باقة ماليزيا العائلية 10 ليالي", "url": "https://agency.test/package-family",
         "description": "برنامج عائلي متكامل.", "image": "https://agency.test/img/f.jpg",
         "offers": {"@type": "Offer", "price": "3100", "priceCurrency": "SAR"}}]}]}, ensure_ascii=False)

# a listing whose cards link to item pages (plus menus and booking buttons that must be ignored)
CARDS_PAGE = """<html><body><header><a href="/الدولة/1/ماليزيا">ماليزيا</a><a href="/اتصل-بنا">اتصل</a></header>
<main>""" + "".join(f"""<div class="card"><a href="/عروض/{i}/عرض-رقم-{i}"><img src="/storage/offer{i}.jpg"></a>
<a href="/عروض/{i}/عرض-رقم-{i}"><h3>عرض ماليزيا رقم {i}</h3></a><a href="/طلب-الحجز/عروض/{i}">احجز</a></div>"""
                     for i in (440, 439, 438)) + """</main><footer><a href="/الصفحة/الدفع">الدفع</a></footer></body></html>"""
OFFER_PAGE = """<html><head><meta property="og:image" content="https://trips.test/storage/logo_1.png">
<meta property="og:title" content="عرض ماليزيا رقم {i} | سرب">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"TouristTrip","name":"عرض ماليزيا رقم {i}",
"description":"12 ليلة بين سيلانجور ولنكاوي","offers":{{"@type":"Offer","price":"1140","priceCurrency":"USD"}}}}</script>
</head><body>عرض</body></html>"""

# a site built in JavaScript whose programmes live in a data file
DATA_PAGE = """<html><head><title>البرامج</title><script src="assets/js/data.js"></script>
<script src="assets/js/main.js"></script></head><body><div id="app"></div></body></html>"""
DATA_JS = "// data\nwindow.SITE_DATA = " + json.dumps({"company": {"name_ar": "جسور"}, "countries": [
    {"id": "malaysia", "name_ar": "ماليزيا", "flag": "🇲🇾", "programs": [
        {"id": "malaysia-premium-12n", "title_ar": "ماليزيا الفاخرة الكاملة", "title_en": "The Complete Premium Malaysia",
         "subtitle_ar": "سيلانجور، لنكاوي، كاميرون هايلاند، وكوالالمبور", "days_count": 13, "nights_count": 12,
         "card_img": "https://images.test/photo-1.jpg", "desc_ar": "برنامج فاخر بفنادق 5 نجوم.",
         "prices": {"adult": {"USD": 1350}},
         "itinerary": [{"title_ar": "اليوم الأول", "img": "https://images.test/d1.jpg"}]},
        {"id": "langkawi-5n", "title_ar": "لنكاوي الساحرة", "title_en": "Magical Langkawi", "days_count": 6,
         "nights_count": 5, "card_img": "https://images.test/photo-2.jpg", "desc_ar": "جزيرة لنكاوي.",
         "prices": {"adult": {"USD": 690}}}]},
    {"id": "thailand", "name_ar": "تايلاند", "flag": "🇹🇭", "programs": []}]}, ensure_ascii=False) + ";\n"

SHOPEE_PAGE = """<html><head><title>Sunway Lagoon Tickets | Shopee Malaysia</title>
<meta property="og:title" content="Sunway Lagoon Theme Park Admission Tickets | Shopee Malaysia">
<meta property="og:image" content="https://down-my.img.test/file/abc">
<meta property="og:description" content="All 6 parks at one price."></head><body></body></html>"""


def fake_web(request: httpx.Request) -> httpx.Response:
    url = unquote(str(request.url))
    html = {"content-type": "text/html; charset=utf-8"}
    if url.endswith("/products.json?limit=250") or "/wp-json/" in url:
        return httpx.Response(404)
    if url.endswith("/sitemap.xml"):
        return httpx.Response(200, text="<urlset><url><loc>https://shop.test/courses/leadership</loc></url>"
                                        "<url><loc>https://shop.test/about</loc></url></urlset>")
    if url.endswith("/courses/leadership"):
        return httpx.Response(200, text=SHOP_PAGE, headers=html)
    if url.startswith("https://agency.test/offers"):
        return httpx.Response(200, text=ITEMLIST_PAGE, headers=html)
    if url.startswith("https://trips.test/الدولة"):
        return httpx.Response(200, text=CARDS_PAGE, headers=html)
    if url.startswith("https://trips.test/عروض/"):
        i = url.split("/عروض/")[1].split("/")[0]
        return httpx.Response(200, text=OFFER_PAGE.format(i=i), headers=html)
    if url == "https://travel.test/programs.html":
        return httpx.Response(200, text=DATA_PAGE, headers=html)
    if url == "https://travel.test/assets/js/data.js":
        return httpx.Response(200, text=DATA_JS, headers={"content-type": "application/javascript"})
    if url.startswith("https://shopee.test/product/"):
        return httpx.Response(200, text=SHOPEE_PAGE, headers=html)
    return httpx.Response(200, text="<html><body></body></html>", headers=html)


def _fake(monkeypatch):
    transport = httpx.MockTransport(fake_web)
    monkeypatch.setattr(products, "_client", lambda: httpx.Client(transport=transport, follow_redirects=True))


def test_whole_site_reads_schema_org_items(monkeypatch):
    _fake(monkeypatch)
    found = products.discover("shop.test")
    item = found["items"][0]
    assert found["method"] == "sitemap"
    assert item["name"] == "Leadership Masterclass" and item["kind"] == "course"
    assert item["price"] == "1200" and item["currency"] == "MYR"


def test_listing_page_with_item_list(monkeypatch):
    _fake(monkeypatch)
    found = products.discover("https://agency.test/offers-malaysia.html")
    assert found["method"] == "jsonld-list" and len(found["items"]) == 2
    first = found["items"][0]
    assert first["url"] == "https://agency.test/package-honeymoon" and first["price"] == "2268"
    assert first["currency"] == "SAR" and first["image_url"] == "https://agency.test/img/h.jpg"


def test_listing_page_with_cards_reads_each_offer(monkeypatch):
    _fake(monkeypatch)
    found = products.discover("https://trips.test/الدولة/1/ماليزيا/عروض")
    assert found["method"] == "links" and len(found["items"]) == 3            # no menus, no booking links
    item = next(i for i in found["items"] if "440" in i["url"])
    assert item["name"] == "عرض ماليزيا رقم 440" and item["kind"] == "offer" and item["price"] == "1140"
    assert item["image_url"].endswith("/storage/offer440.jpg")                # the card photo, not the logo


def test_javascript_site_with_data_file(monkeypatch):
    _fake(monkeypatch)
    found = products.discover("https://travel.test/programs.html", "ar")
    assert found["method"] == "data"
    names = [i["name"] for i in found["items"]]
    assert names == ["ماليزيا الفاخرة الكاملة", "لنكاوي الساحرة"]               # not the days of the itinerary
    first = found["items"][0]
    assert first["price"] == "1350" and first["currency"] == "USD" and first["kind"] == "offer"
    assert "13 days / 12 nights" in first["description"]
    assert first["url"].startswith("https://travel.test/programs.html#item-malaysia-premium-12n")
    assert products.discover("https://travel.test/programs.html", "en")["items"][0]["name"] == "The Complete Premium Malaysia"


def test_single_product_page(monkeypatch):
    _fake(monkeypatch)
    found = products.discover("https://shopee.test/product/57248752/933234629?sig=x")
    assert found["method"] == "page" and len(found["items"]) == 1
    item = found["items"][0]
    assert item["name"] == "Sunway Lagoon Theme Park Admission Tickets" and item["image_url"].endswith("/file/abc")


class _Site(BaseHTTPRequestHandler):
    """A course site built in the browser: the page loads its courses from /api/courses."""
    def log_message(self, *args):  # noqa: ANN002
        pass

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/courses"):
            body = json.dumps({"data": [{"id": 7, "slug": "pmp-course", "title_ar": "الدورة الاحترافية للتحضير لشهادة PMP",
                                         "title_en": "PMP Exam Preparation", "description_ar": "برنامج تدريبي متكامل لاختبار PMP.",
                                         "price": 599, "currency": "USD", "cover_image": "/img/pmp.jpg",
                                         "duration_hours": 60, "instructor_name": "Dr. T"}]}).encode()
            ctype = "application/json"
        else:
            body = ("<html><head><title>Courses</title></head><body><div id=app></div><script>"
                    "fetch('/api/courses').then(r=>r.json()).then(j=>{document.getElementById('app').innerHTML="
                    "j.data.map(c=>`<a href=\"/ar/courses/${c.slug}\"><h3>${c.title_ar}</h3></a>`).join('')})"
                    "</script></body></html>").encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_site_built_in_the_browser():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/ar/courses"
        found = asyncio.run(products.discover_full(url, "ar"))
    finally:
        server.shutdown()
    assert found["method"].startswith("browser") and len(found["items"]) == 1
    item = found["items"][0]
    assert item["name"] == "الدورة الاحترافية للتحضير لشهادة PMP" and item["kind"] == "course"
    assert item["price"] == "599" and item["url"].endswith("/ar/courses/pmp-course")
    assert item["image_url"].endswith("/img/pmp.jpg")


def test_sync_job_then_post_with_link_and_schedule(client, monkeypatch):
    _fake(monkeypatch)
    r = client.post("/api/products/sync", json={"url": "https://agency.test/offers-malaysia.html"})
    assert r.status_code == 200
    job = client.get(f"/api/products/sync/{r.json()['job']}").json()
    assert job["status"] == "done" and job["result"]["added"] == 2, job
    rows = client.get("/api/products").json()
    pid = next(p["id"] for p in rows if p["url"] == "https://agency.test/package-honeymoon")
    assert client.post(f"/api/products/{pid}/draft", json={"schedule": False}).status_code == 200
    with session_scope() as db:
        p = db.get(Product, pid)
        d = db.get(Draft, p.draft_id)
        assert p.status == "drafted" and d.link_url == "https://agency.test/package-honeymoon"
        from app.services import pipeline
        assert "https://agency.test/package-honeymoon" in pipeline.compose_caption(d)
        did = d.id
    client.delete(f"/api/drafts/{did}")
    client.post("/api/products/bulk", json={"ids": [x["id"] for x in rows], "action": "delete"})
