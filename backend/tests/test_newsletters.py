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
