"""One article → a post per platform, published with its own text and images."""
import asyncio
import json

import httpx

from app.db import Draft, PublishLog, Slide, session_scope
from app.publishers.base import PlatformResult
from app.services import generator as gen_mod
from app.services import pipeline, publishing, variants


def _draft(n_slides=6, origin="source"):
    with session_scope() as db:
        d = Draft(hook="ماليزيا تستقبل رقمًا قياسيًا من السياح", subtitle="أرقام 2026", caption="نص المنشور " * 30,
                  hashtags="#ماليزيا #سفر #سياحة #جسور_للسفر #travel #malaysia", origin=origin,
                  source_name="TTG Asia", language="ar", status="approved", cta="احجز معنا")
        for i in range(n_slides):
            kind = "cover" if i == 0 else ("cta" if i == n_slides - 1 else "content")
            d.slides.append(Slide(position=i, kind=kind, heading=f"ع{i}", body="نص",
                                  image_url=f"https://cdn.example/s{i}.jpg", image_key=f"k{i}"))
        db.add(d)
        db.flush()
        return d.id


def test_fallback_variants_respect_each_platform():
    did = _draft()
    with session_scope() as db:
        d = db.get(Draft, did)
        v = variants.finalize(d, variants.fallback_texts(d))
        assert v["instagram"]["slides"] == [0, 1, 2, 3, 4, 5] and v["instagram"]["format"] == "carousel"
        for p in ("facebook", "linkedin", "x", "threads"):
            assert v[p]["slides"] == [0] and v[p]["format"] == "single"
        assert len(v["x"]["text"]) <= 270 and "TTG Asia" in v["x"]["text"]
        assert all(len(v[p]["text"]) <= variants.PLATFORM_SPECS[p]["limit"] for p in v)
        db.delete(d)


def test_ai_writes_one_text_per_platform(client, monkeypatch):
    did = _draft()
    texts = {p: f"نص خاص بـ {p}" for p in variants.PLATFORMS}
    texts["x"] = "خبر قصير جدًا #ماليزيا"

    async def fake_call(system, user, tool, max_tokens=3000):
        assert tool["name"] == "platform_posts"
        return texts
    monkeypatch.setattr(gen_mod, "_call_model", fake_call)
    monkeypatch.setattr(gen_mod, "ai_available", lambda: True)
    asyncio.run(pipeline.make_variants(did))
    d = client.get(f"/api/drafts/{did}").json()
    assert d["variants_generated"] and d["variants"]["linkedin"]["text"].startswith("نص خاص بـ linkedin")
    assert "المصدر: TTG Asia" in d["variants"]["facebook"]["text"]

    # Edit one platform: its text, and which image LinkedIn uses
    r = client.patch(f"/api/drafts/{did}/variants/linkedin", json={"text": "نص لينكدإن المعدّل", "slides": [2]}).json()
    assert r["variants"]["linkedin"]["text"] == "نص لينكدإن المعدّل" and r["variants"]["linkedin"]["slides"] == [2]
    assert client.patch(f"/api/drafts/{did}/variants/x", json={"text": "x" * 400}).status_code == 400
    client.delete(f"/api/drafts/{did}")


def test_publish_sends_each_platform_its_own_post(client, monkeypatch):
    did = _draft()
    with session_scope() as db:
        d = db.get(Draft, did)
        d.variants = variants.finalize(d, {"instagram": "IG text", "linkedin": "LI text", "x": "X text"}, credit=False)
        d.publish_targets = [{"provider": "buffer", "platforms": ["instagram", "linkedin", "x"]}]
    sent = []

    class FakePublisher:
        def configured(self):
            return True

        async def publish(self, req):
            sent.append((req.platforms, req.caption, req.image_urls))
            return [PlatformResult(p, True, external_id="id") for p in req.platforms]

    monkeypatch.setattr(publishing, "get_publisher", lambda name: FakePublisher())
    monkeypatch.setattr(publishing.storage, "is_publicly_reachable", lambda: True)
    monkeypatch.setattr(publishing.qa, "run_qa", lambda *a, **k: {"passed": True, "items": []})
    result = asyncio.run(publishing.publish_draft(did))
    assert result["ok"] and result["status"] == "published"
    by = {p[0]: (cap, urls) for p, cap, urls in sent}
    assert by["instagram"][0] == "IG text" and len(by["instagram"][1]) == 6       # carousel
    assert by["linkedin"][0] == "LI text" and by["linkedin"][1] == ["https://cdn.example/s0.jpg"]   # one image
    assert by["x"][0] == "X text" and len(by["x"][1]) == 1
    client.delete(f"/api/drafts/{did}")
