"""Market dialects, tour-programme sources and date-window collection."""
import asyncio
from datetime import date, datetime, timezone

from app.db import Article, Draft, Slide, Source, session_scope
from app.services import generator as gen_mod
from app.services import pipeline


def test_prompt_carries_dialect_and_programme_rules():
    p = gen_mod.build_system_prompt(gen_mod.BrandContext(name="JUSOOR Travel"),
                                    {"language": "ar", "dialect": "gulf", "purpose": "programs"})
    assert "Gulf" in p and "وايد" in p and "TOUR PROGRAMME" in p and "price is available on request" in p
    p2 = gen_mod.build_system_prompt(gen_mod.BrandContext(name="J"), {"language": "ar", "dialect": "algeria"})
    assert "Algerian" in p2 and "TOUR PROGRAMME" not in p2


def test_programme_source_uses_stock_photos_and_dialect(client, monkeypatch):
    seen = {}

    async def fake_generate(ctx, gen, title, body, src):
        seen.update(gen)
        return gen_mod.demo_post(title, body, gen)

    async def no_render(did, *a, **k):
        return None
    monkeypatch.setattr(gen_mod, "generate_from_article", fake_generate)
    monkeypatch.setattr(pipeline, "render_draft", no_render)
    sid = client.post("/api/sources", json={"name": "Programs X", "kind": "rss", "feed_url": "https://ex.com/feed",
                                            "purpose": "programs", "dialect": "maghreb"}).json()["id"]
    with session_scope() as db:
        a = Article(source_id=sid, url="https://ex.com/p1", title="Malaysia 7 days", body="Day 1 KL. " * 40,
                    image_url="https://competitor.example/photo.jpg", status="new", fingerprint="prog1")
        db.add(a)
        db.flush()
        aid = a.id
    did = asyncio.run(pipeline.draft_from_article(aid))
    try:
        assert seen["purpose"] == "programs" and seen["dialect"] == "maghreb"
        with session_scope() as db:
            d = db.get(Draft, did)
            assert d.content_type == "program" and d.dialect == "maghreb" and d.original_image_url is None
    finally:
        client.delete(f"/api/drafts/{did}")
        client.delete(f"/api/sources/{sid}")


def test_window_filter():
    w = {"date_from": date(2026, 9, 1), "date_to": date(2026, 9, 30)}
    assert pipeline._in_window(datetime(2026, 9, 15, tzinfo=timezone.utc), w)
    assert not pipeline._in_window(datetime(2026, 8, 31, tzinfo=timezone.utc), w)
    assert not pipeline._in_window(datetime(2026, 10, 1, tzinfo=timezone.utc), w)
    assert pipeline._in_window(None, w)


def test_scrape_with_window_is_accepted(client, monkeypatch):
    from app.services.jobs import jobs
    calls = []

    async def fake_run(ids, window=None):
        calls.append((ids, window))
    monkeypatch.setattr(jobs, "run_collection", fake_run)
    r = client.post("/api/scrape/run-all", json={"date_from": "2026-09-01", "date_to": "2026-09-30", "max_items": 20})
    assert r.status_code == 200 and calls and calls[0][1]["date_from"] == date(2026, 9, 1)
    assert client.post("/api/scrape/run-all", json={"date_from": "2026-10-01", "date_to": "2026-09-01"}).status_code == 400


def test_dialect_copy_keeps_photos(client, monkeypatch):
    async def fake_topic(ctx, gen, topic, notes=""):
        assert gen["dialect"] == "algeria"
        return gen_mod.demo_post(topic, notes, gen)

    async def no_render(did, *a, **k):
        return None

    async def no_variants(did):
        return None
    monkeypatch.setattr(gen_mod, "generate_from_topic", fake_topic)
    monkeypatch.setattr(pipeline, "render_draft", no_render)
    monkeypatch.setattr(pipeline, "make_variants", no_variants)
    with session_scope() as db:
        d = Draft(hook="h", caption="c", origin="manual", language="ar", status="pending_review",
                  original_title="لنكاوي", original_body="جزيرة")
        for i in range(6):
            d.slides.append(Slide(position=i, kind="content", heading="ع", body="ن", background_url=f"https://p/{i}.jpg"))
        db.add(d)
        db.flush()
        src = d.id
    new_id = asyncio.run(pipeline.dialect_copy(src, "algeria"))
    with session_scope() as db:
        copy = db.get(Draft, new_id)
        assert copy.dialect == "algeria" and copy.slides[0].background_url == "https://p/0.jpg"
    client.post("/api/drafts/bulk", json={"ids": [src, new_id], "action": "delete"})


def test_backup_roundtrip_without_secrets(client):
    client.put("/api/settings/credentials", json={"groq_api_key": "gsk_secret_value"})
    client.post("/api/sources", json={"name": "Backup src", "kind": "rss", "feed_url": "https://ex.com/f"})
    data = client.get("/api/backup").json()
    assert "gsk_secret_value" not in str(data) and any(s["name"] == "Backup src" for s in data["sources"])
    sid = [s for s in client.get("/api/sources").json() if s["name"] == "Backup src"][0]["id"]
    client.delete(f"/api/sources/{sid}")
    r = client.post("/api/backup/restore", json=data).json()
    assert r["sources_added"] >= 1
    sid = [s for s in client.get("/api/sources").json() if s["name"] == "Backup src"][0]["id"]
    client.delete(f"/api/sources/{sid}")
    client.put("/api/settings/credentials", json={"groq_api_key": None})


def test_login_is_throttled(client, monkeypatch):
    from app.config import get_settings
    from app.routes import auth_routes
    s = get_settings()
    monkeypatch.setattr(s, "admin_email", "a@b.c")
    monkeypatch.setattr(s, "admin_password", "correct-horse")
    monkeypatch.setattr(s, "auth_disabled", False)
    auth_routes._FAILED.clear()
    if s.auth_mode != "internal":
        return
    for _ in range(8):
        assert client.post("/api/auth/login", json={"email": "a@b.c", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@b.c", "password": "correct-horse"}).status_code == 429
    auth_routes._FAILED.clear()
