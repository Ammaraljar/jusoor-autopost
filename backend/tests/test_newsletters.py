"""Newsletters: sending account, contacts import, designs, sending and tracking."""
import io

from openpyxl import Workbook

from app.db import Contact, Delivery, Newsletter, session_scope
from app.services import mailer, newsletter


def test_sending_account_hides_secrets(client):
    r = client.put("/api/email/settings", json={"provider": "brevo", "from_email": "news@acme.test",
                                                "from_name": "Acme", "brevo_api_key": "xkeysib-secret-1234"})
    assert r.status_code == 200
    data = client.get("/api/email/settings").json()
    assert data["ready"] and data["brevo_api_key"] == {"set": True, "hint": "…1234"}
    assert "xkeysib" not in str(data)


def test_import_contacts_from_csv_excel_and_text(client):
    csv_data = "Name,Email,City\nSara,sara@x.test,KL\nbad,not-an-email,\nOmar,OMAR@x.test,Doha\n".encode()
    r = client.post("/api/contacts/import", data={"new_list": "Customers"},
                    files={"file": ("c.csv", csv_data, "text/csv")})
    assert r.json() == {"added": 2, "updated": 0, "invalid": 1}
    wb = Workbook()
    wb.active.append(["البريد الإلكتروني", "الاسم"])
    wb.active.append(["ali@x.test", "علي"])
    buf = io.BytesIO()
    wb.save(buf)
    lid = next(lst["id"] for lst in client.get("/api/contacts/lists").json() if lst["name"] == "Customers")
    r = client.post("/api/contacts/import", data={"list_id": str(lid)},
                    files={"file": ("c.xlsx", buf.getvalue(), "application/octet-stream")})
    assert r.json()["added"] == 1
    r = client.post("/api/contacts/import-text", json={"text": "Mona <mona@x.test>, sara@x.test", "list_id": lid})
    assert r.json() == {"added": 1, "updated": 1, "invalid": 0}
    members = client.get(f"/api/contacts?list_id={lid}").json()
    assert members["total"] == 4 and {c["email"] for c in members["items"]} >= {"omar@x.test", "ali@x.test"}


def test_designs_per_field_render_and_track(client, monkeypatch):
    for family, layouts in newsletter.FIELD_LAYOUTS.items():
        assert len(layouts) >= 4, family
    sent = []
    monkeypatch.setattr(mailer, "send", lambda cfg, to, name, subject, html, text, headers=None: sent.append((to, html, headers)) or "id")
    monkeypatch.setattr(newsletter.time, "sleep", lambda s: None)
    lid = client.post("/api/contacts/lists", json={"name": "VIP"}).json()["id"]
    for e in ("a@vip.test", "b@vip.test"):
        client.post("/api/contacts", json={"email": e, "list_ids": [lid]})
    client.put("/api/email/settings", json={"provider": "brevo", "from_email": "news@acme.test",
                                            "brevo_api_key": "xkeysib-secret-1234"})
    nid = client.post("/api/newsletters", json={"topic": "Summer offers", "list_ids": [lid]}).json()["id"]
    nl = client.get(f"/api/newsletters/{nid}").json()
    assert nl["subject"] and nl["audience"] == 2
    for d in client.get("/api/newsletters/designs").json():
        html = client.get(f"/api/newsletters/{nid}/preview?design={d['id']}").json()["html"]
        assert "<table" in html and "Summer offers" in html or nl["subject"] in html
    client.patch(f"/api/newsletters/{nid}", json={"content": {"headline": "Hello", "intro": "Hi",
                 "sections": [{"title": "Deal", "text": "Text", "link": "https://acme.test/deal", "button": "See"}],
                 "cta_text": "Shop", "cta_url": "https://acme.test"}})
    assert client.post(f"/api/newsletters/{nid}/send", json={}).status_code == 200
    assert len(sent) == 2 and "/api/t/o/" in sent[0][1] and "List-Unsubscribe" in sent[0][2]
    with session_scope() as db:
        token = db.query(Delivery).filter(Delivery.newsletter_id == nid).first().token
    assert client.get(f"/api/t/o/{token}.gif").headers["content-type"] == "image/gif"
    r = client.get(f"/api/t/c/{token}?u=https%3A%2F%2Facme.test%2Fdeal", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://acme.test/deal"
    assert "unsubscribed" in client.get(f"/api/t/u/{token}").text.lower() or client.get(f"/api/t/u/{token}").status_code == 200
    stats = client.get(f"/api/newsletters/{nid}").json()["stats"]
    assert stats["sent"] == 2 and stats["opened"] == 1 and stats["clicked"] == 1 and stats["unsubscribed"] == 1
    with session_scope() as db:
        assert db.get(Newsletter, nid).status == "sent"
        assert db.query(Contact).filter(Contact.status == "unsubscribed").count() >= 1
    # scheduling
    nid2 = client.post(f"/api/newsletters/{nid}/duplicate").json()["id"]
    r = client.post(f"/api/newsletters/{nid2}/send", json={"when": "2099-01-01T09:00:00Z"})
    assert r.json()["status"] == "scheduled"
    assert client.post(f"/api/newsletters/{nid2}/cancel").json()["status"] == "draft"


def test_newsletter_types_event_and_poll(client, monkeypatch):
    kinds = {t["id"] for t in client.get("/api/newsletters/types").json()}
    assert kinds == {"curated", "educational", "reporting", "roundup", "story", "analysis", "promotional",
                     "update", "internal", "survey", "event", "hybrid"}
    nid = client.post("/api/newsletters", json={
        "kind": "event", "topic": "Leadership webinar",
        "event": {"date": "2026-11-20", "time": "10:00", "place": "Zoom", "url": "https://acme.test/register"}}).json()["id"]
    nl = client.get(f"/api/newsletters/{nid}").json()
    assert nl["kind"] == "event" and nl["content"]["event"]["place"] == "Zoom"
    html = client.get(f"/api/newsletters/{nid}/preview").json()["html"]
    assert "Zoom" in html and "2026-11-20" in html
    # survey with the company's own question
    sent = []
    monkeypatch.setattr(mailer, "send", lambda *a, **k: sent.append(a) or "id")
    monkeypatch.setattr(newsletter.time, "sleep", lambda s: None)
    lid = client.post("/api/contacts/lists", json={"name": "Poll"}).json()["id"]
    client.post("/api/contacts", json={"email": "voter@x.test", "list_ids": [lid]})
    client.put("/api/email/settings", json={"provider": "brevo", "from_email": "news@acme.test",
                                            "brevo_api_key": "xkeysib-secret-1234"})
    sid = client.post("/api/newsletters", json={"kind": "survey", "topic": "Your opinion", "list_ids": [lid],
                                                "poll": {"question": "Best day?", "options": ["Mon", "Fri"]}}).json()["id"]
    client.patch(f"/api/newsletters/{sid}", json={"subject": "Quick question"})
    assert client.post(f"/api/newsletters/{sid}/send", json={}).status_code == 200
    assert "/api/t/p/" in sent[0][4]
    with session_scope() as db:
        token = db.query(Delivery).filter(Delivery.newsletter_id == sid).first().token
    assert client.get(f"/api/t/p/{token}?a=1").status_code == 200
    poll = client.get(f"/api/newsletters/{sid}").json()["stats"]["poll"]
    assert poll[1] == {"option": "Fri", "votes": 1, "percent": 100.0}


def test_newsletter_font_and_translate(client, monkeypatch):
    fonts = client.get("/api/newsletters/fonts?language=en").json()
    assert fonts[0]["id"] == "" and any(f["id"] == "Poppins" for f in fonts)
    assert not any(f["id"] == "Poppins" for f in client.get("/api/newsletters/fonts?language=ar").json())
    nid = client.post("/api/newsletters", json={"topic": "Offers", "language": "en", "font": "Poppins"}).json()["id"]
    client.patch(f"/api/newsletters/{nid}", json={"content": {"headline": "Hello", "intro": "Hi",
                 "sections": [{"title": "Deal", "text": "Text", "link": "https://acme.test/d", "button": "See"}],
                 "cta_text": "Shop"}})
    html = client.get(f"/api/newsletters/{nid}/preview").json()["html"]
    assert "family=Poppins" in html and "'Poppins'" in html
    assert "Hybrid" not in html and "@@KICKER@@" not in html      # readers never see the newsletter type

    async def fake(system, user, tool, max_tokens=0):
        import json
        return {"texts": ["ع:" + t for t in json.loads(user.split("\n", 1)[1])]}
    monkeypatch.setattr(newsletter.generator, "ai_available", lambda: True)
    monkeypatch.setattr(newsletter.generator, "_call_model", fake)
    assert client.post(f"/api/newsletters/{nid}/translate", json={"language": "ar"}).status_code == 200
    nl = client.get(f"/api/newsletters/{nid}").json()
    assert nl["language"] == "ar" and nl["status"] == "draft" and nl["font"] == ""
    assert nl["content"]["headline"] == "ع:Hello" and nl["content"]["sections"][0]["button"] == "ع:See"
    assert nl["content"]["sections"][0]["link"] == "https://acme.test/d"


def test_brevo_payload_has_no_empty_headers(monkeypatch):
    calls = []

    class R:
        status_code = 201
        def json(self):
            return {"messageId": "m1"}
    monkeypatch.setattr(mailer.httpx, "post", lambda url, json=None, **kw: calls.append(json) or R())
    cfg = {"provider": "brevo", "from_email": "news@acme.test", "brevo_api_key": "k"}
    assert mailer.send(cfg, "a@x.test", "", "Hi", "<p>x</p>", "x") == "m1"
    assert "headers" not in calls[0]
    mailer.send(cfg, "a@x.test", "", "Hi", "<p>x</p>", "x", headers={"List-Unsubscribe": "<https://u>"})
    assert calls[1]["headers"]["List-Unsubscribe"] == "<https://u>"


def test_links_without_scheme_and_live_preview(client):
    assert newsletter.href("jusoortravel.com") == "https://jusoortravel.com"
    assert newsletter.href("www.x.com/a?b=1") == "https://www.x.com/a?b=1"
    assert newsletter.href("info@x.com") == "mailto:info@x.com"
    assert newsletter.href("https://x.com") == "https://x.com"
    nid = client.post("/api/newsletters", json={"topic": "Offers"}).json()["id"]
    html = client.post(f"/api/newsletters/{nid}/preview", json={"content": {
        "headline": "Live", "cta_text": "Book", "cta_url": "jusoortravel.com",
        "sections": [{"title": "S", "text": "T", "link": "jusoortravel.com/offer", "button": "See"}]}}).json()["html"]
    assert 'href="https://jusoortravel.com"' in html and "https://jusoortravel.com/offer" in html and "Live" in html
    assert client.get(f"/api/newsletters/{nid}").json()["content"].get("headline") != "Live"   # not saved


def test_post_newsletter_has_no_source_link_and_uses_own_photos(client, monkeypatch):
    from app.db import Brand, Draft, MediaAsset
    with session_scope() as db:
        b = db.query(Brand).first()
        b.website = "https://jusoortravel.com"
        d = Draft(hook="Langkawi", caption="Great island.\n\nالمصدر: The Star\n🔗 https://thestar.com/x",
                  source_url="https://thestar.com/x", source_name="The Star", status="approved")
        db.add(d)
        db.add(MediaAsset(url="https://cdn.test/lib/langkawi-beach.jpg", title="Langkawi beach", tags="langkawi island"))
        db.add(MediaAsset(url="https://cdn.test/lib/office.jpg", title="Office", tags="team"))
        db.flush()
        did = d.id
    seen = {}

    async def fake(system, user, tool, max_tokens=0):
        seen["user"] = user
        n = next(int(line.split(":")[0][1:]) for line in user.splitlines() if line.startswith("P") and "Langkawi beach" in line)
        return {"subject": "S", "preheader": "", "headline": "H", "intro": "I", "cta_text": "Go", "hero_image": n,
                "sections": [{"title": "Langkawi", "text": "T", "ref": 1, "image": n}]}
    monkeypatch.setattr(newsletter.generator, "ai_available", lambda: True)
    monkeypatch.setattr(newsletter.generator, "_call_model", fake)
    nid = client.post("/api/newsletters", json={"kind": "roundup", "draft_ids": [did]}).json()["id"]
    c = client.get(f"/api/newsletters/{nid}").json()["content"]
    assert "thestar" not in seen["user"] and "The Star" not in seen["user"]
    assert c["sections"][0]["link"] == "" and c["hero_image"] == "https://cdn.test/lib/langkawi-beach.jpg"
    assert c["sections"][0]["image"] == ""            # same photo is not reused
    with session_scope() as db:                       # leave the shared library as it was
        for a in db.query(MediaAsset).filter(MediaAsset.url.like("https://cdn.test/lib/%")):
            db.delete(a)
