from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from app.db import Draft, session_scope
from app.publishers import REGISTRY
from app.publishers.base import PlatformResult, Publisher
from app.services import app_settings, publishing, storage


@pytest.fixture
def source_id(client):
    r = client.post("/api/sources", json={
        "name": "The Star - Travel", "kind": "website", "base_url": "https://www.thestar.com.my",
        "listing_urls": ["https://www.thestar.com.my/lifestyle/travel"], "max_items_per_run": 3})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_full_pipeline_creates_reviewable_draft(client, fake_network, source_id):
    with session_scope() as db:
        app_settings.update_section(db, "scheduler", {"max_article_age_days": 400000})
    import asyncio

    from app.services.jobs import jobs
    summary = asyncio.run(jobs.run_collection([source_id]))
    assert summary["new_articles"] == 1, summary
    assert summary["drafts"] == 1, summary

    drafts = client.get("/api/drafts?status=pending_review").json()
    assert len(drafts) == 1
    d = client.get(f"/api/drafts/{drafts[0]['id']}").json()
    assert [s["kind"] for s in d["slides"]] == ["cover", "content", "content", "content", "content", "cta"]
    assert d["qa"]["passed"], [i["message"] for i in d["qa"]["items"] if i["status"] != "pass"]
    assert "The Star - Travel" in d["caption_preview"]

    key = d["slides"][0]["image_key"]
    img = Image.open(storage._local_path(key))
    assert img.size == (1080, 1350)

    # Running again must not duplicate the article
    summary2 = asyncio.run(jobs.run_collection([source_id]))
    assert summary2["new_articles"] == 0

    # Edit a slide -> re-rendered with a new image key
    slide = d["slides"][1]
    r = client.patch(f"/api/drafts/{d['id']}/slides/{slide['id']}", json={"heading": "عنوان جديد"})
    assert r.status_code == 200
    updated = r.json()["slides"][1]
    assert updated["heading"] == "عنوان جديد" and updated["image_key"] != slide["image_key"]

    # Placeholder text must fail QA and block publishing
    client.patch(f"/api/drafts/{d['id']}", json={"first_comment": "لا يوجد فيديو"})
    r = client.post(f"/api/drafts/{d['id']}/publish",
                    json={"targets": [{"provider": "buffer", "platforms": ["instagram"]}]})
    assert r.status_code == 422
    client.patch(f"/api/drafts/{d['id']}", json={"first_comment": ""})

    # Schedule for later
    when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    r = client.post(f"/api/drafts/{d['id']}/publish",
                    json={"targets": [{"provider": "buffer", "platforms": ["instagram"]}], "scheduled_at": when})
    assert r.status_code == 200 and r.json()["status"] == "scheduled"
    cal = client.get("/api/calendar").json()
    assert any(p["id"] == d["id"] for p in cal["posts"])


class FakePublisher(Publisher):
    name = "fake"
    platforms = ("instagram", "facebook")
    calls = []

    def configured(self):
        return True

    async def publish(self, req):
        FakePublisher.calls.append(req)
        return [PlatformResult(p, p == "instagram", external_id="x1" if p == "instagram" else None,
                               error=None if p == "instagram" else "boom") for p in req.platforms]


def test_publish_due_marks_partial_success(client, monkeypatch):
    import asyncio

    monkeypatch.setitem(REGISTRY, "fake", FakePublisher)
    with session_scope() as db:
        d = db.query(Draft).filter(Draft.status == "scheduled").first()
        d.scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        d.publish_targets = [{"provider": "fake", "platforms": ["instagram", "facebook"]}]
        did = d.id
    assert asyncio.run(publishing.publish_due()) == 1
    d = client.get(f"/api/drafts/{did}").json()
    assert d["status"] == "published"
    assert "facebook" in d["error"]
    assert {l["platform"] for l in d["logs"]} == {"instagram", "facebook"}
    by_platform = {r.platforms[0]: r for r in FakePublisher.calls[-2:]}
    ig, fb = by_platform["instagram"], by_platform["facebook"]
    assert len(ig.image_urls) == 6 and all(u.startswith("https://autopost.example.com/media/") for u in ig.image_urls)
    assert len(fb.image_urls) == 1                     # Facebook: one image, its own text
    assert "#" in ig.caption


def test_calendar_and_campaign_flow(client, fake_network):
    c = client.post("/api/campaigns", json={"name": "صيف ماليزيا", "start_date": "2026-10-01",
                                            "end_date": "2026-10-31"}).json()
    item = client.post("/api/calendar", json={"date": "2026-10-05", "time": "09:30",
                                              "topic": "أفضل 5 شلالات في لنكاوي", "campaign_id": c["id"]}).json()
    r = client.post(f"/api/calendar/{item['id']}/generate")
    assert r.status_code == 200
    cal = client.get("/api/calendar?start=2026-10-01&end=2026-10-31").json()
    got = [i for i in cal["items"] if i["id"] == item["id"]][0]
    assert got["status"] == "generated" and got["draft_id"]
    d = client.get(f"/api/drafts/{got['draft_id']}").json()
    assert d["campaign_id"] == c["id"] and d["origin"] == "calendar"
    camps = client.get("/api/campaigns").json()
    assert camps[0]["stats"]["drafts"] >= 1


def test_settings_and_status(client):
    r = client.put("/api/settings/generation", json={"tone": "luxury", "unknown": 1})
    assert r.json()["tone"] == "luxury" and "unknown" not in r.json()
    assert client.put("/api/settings/nope", json={}).status_code == 404
    st = client.get("/api/status").json()
    assert st["storage"]["public"] is True
    assert set(st["providers"]) >= {"buffer", "meta", "uploadpost"}


def test_brand_preview_renders(client):
    brands = client.get("/api/brands").json()
    assert brands[0]["name"] == "JUSOOR Travel"
    r = client.post(f"/api/brands/{brands[0]['id']}/preview", json={"kind": "cta"})
    assert r.json()["image"].startswith("data:image/jpeg;base64,")
