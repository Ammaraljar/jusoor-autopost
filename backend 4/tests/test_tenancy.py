"""Several companies on one platform: each sees only its own data, staff have roles."""
from app.db import Draft, Organization, Source, session_scope, use_org
from app.services import tenancy


def _org(name="Cafe Nour", industry="restaurants"):
    with session_scope() as db:
        org, _ = tenancy.create_org(db, name, industry, "en")
        return org.id


def test_companies_are_isolated(client):
    other = _org()
    with session_scope() as db:
        db.add(Draft(hook="private to company 1", caption="c", origin="manual", status="pending_review"))
    with use_org(other), session_scope() as db:
        db.add(Draft(hook="private to the cafe", caption="c", origin="manual", status="pending_review"))
        db.add(Source(name="Cafe source", kind="rss", feed_url="https://cafe.example/feed"))
    mine = client.get("/api/drafts?status=all").json()
    theirs = client.get("/api/drafts?status=all", headers={"X-Org-Id": str(other)}).json()
    assert any(d["hook"] == "private to company 1" for d in mine)
    assert not any(d["hook"] == "private to the cafe" for d in mine)
    assert [d["hook"] for d in theirs] == ["private to the cafe"]
    their_sources = client.get("/api/sources", headers={"X-Org-Id": str(other)}).json()
    assert [s["name"] for s in their_sources] == ["Cafe source"]
    # a draft of company 1 is not reachable from the cafe
    did = [d for d in mine if d["hook"] == "private to company 1"][0]["id"]
    assert client.get(f"/api/drafts/{did}", headers={"X-Org-Id": str(other)}).status_code == 404


def test_new_company_speaks_its_industry(client):
    other = _org("Al Noor School", "education")
    gen = client.get("/api/settings", headers={"X-Org-Id": str(other)}).json()["values"]["generation"]
    assert gen["industry"] == "education" and gen["language"] == "en"
    brand = client.get("/api/brands", headers={"X-Org-Id": str(other)}).json()[0]
    assert brand["name"] == "Al Noor School" and brand["design_seed"]


def test_signup_login_and_roles(client, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "admin_email", "root@platform.test")
    monkeypatch.setattr(s, "admin_password", "root-password-123")
    r = client.post("/api/auth/signup", json={"company": "Dar Realty", "industry": "realestate", "language": "ar",
                                              "dialect": "gulf", "name": "Sara", "email": "sara@dar.test",
                                              "password": "sara-password-1"})
    assert r.status_code == 200, r.text
    owner = {"Authorization": f"Bearer {r.json()['token']}"}
    me = client.get("/api/me", headers=owner).json()
    assert me["role"] == "owner" and me["email"] == "sara@dar.test"
    # the owner adds an editor and a reviewer
    for email, role in (("ed@dar.test", "editor"), ("rev@dar.test", "reviewer")):
        assert client.post("/api/team", headers=owner, json={"email": email, "name": role, "role": role,
                                                            "password": "temp-password-1"}).status_code == 200
    rev = client.post("/api/auth/login", json={"email": "rev@dar.test", "password": "temp-password-1"}).json()
    rev_h = {"Authorization": f"Bearer {rev['token']}"}
    assert client.get("/api/drafts/counts", headers=rev_h).status_code == 200      # can read
    assert client.post("/api/sources", headers=rev_h, json={"name": "x", "kind": "rss",
                                                            "feed_url": "https://x.test/f"}).status_code == 403
    assert client.get("/api/team", headers=rev_h).status_code == 403                # team is owner-only
    # a company owner is not a platform admin
    assert client.get("/api/admin/orgs", headers=owner).status_code == 403
    # the platform admin sees every company and can suspend one
    root = client.post("/api/auth/login", json={"email": "root@platform.test", "password": "root-password-123"}).json()
    root_h = {"Authorization": f"Bearer {root['token']}"}
    orgs = client.get("/api/admin/orgs", headers=root_h).json()
    dar = [o for o in orgs if o["name"] == "Dar Realty"][0]
    assert client.patch(f"/api/admin/orgs/{dar['id']}", headers=root_h, json={"status": "suspended"}).status_code == 200
    assert client.get("/api/drafts/counts", headers=owner).status_code == 403
