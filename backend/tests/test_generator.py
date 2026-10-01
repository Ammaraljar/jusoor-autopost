"""AI engine layer: Mistral / OpenRouter / Groq through their OpenAI-compatible APIs."""
import asyncio
import json

import httpx
import pytest

from app.config import get_settings
from app.services import generator as gen_mod
from app.services.generator import BrandContext, extract_json

BRAND = BrandContext(name="JUSOOR Travel", handle="@jusoortravel")
GEN = {"language": "ar", "tone": "friendly", "content_type": "news", "platform": "instagram", "content_slides": 3}

GOOD = {
    "relevance": 9, "hook": "بينانغ تسرق القلب", "subtitle": "دليلك للجزيرة",
    "caption": "نص المنشور " * 12, "hashtags": ["سفر", "#ماليزيا"],
    "slides": [{"heading": "ما الجديد؟", "body": "جورج تاون تغيّرت"}, {"heading": "المذاق", "body": "أسواق ليلية"}],
    "cta": "احجز معنا", "first_comment": "", "image_keywords": "penang george town", "badge": "news",
}


def _mock(module, handler):
    real = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real(*a, **kw)
    return factory


@pytest.fixture
def anythingllm(monkeypatch):
    """Only Mistral configured (from environment variables)."""
    from app.services import credentials
    s = get_settings()
    for f in ("openrouter_api_key", "groq_api_key"):
        monkeypatch.setattr(s, f, "")
    monkeypatch.setattr(s, "mistral_api_key", "AK-123")
    monkeypatch.setattr(s, "mistral_model", "mistral-test")
    monkeypatch.setattr(s, "ai_mode", "single")
    monkeypatch.setattr(s, "ai_json_mode", True)
    credentials.refresh()
    return s


def reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```')["a"] == 1
    assert extract_json('Sure! here it is:\n{"a": {"b": "}"}}\nhope that helps')["a"]["b"] == "}"
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_anythingllm_generates_post(client, anythingllm, monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return reply("```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```")

    monkeypatch.setattr(gen_mod.httpx, "AsyncClient", _mock(gen_mod, handler))
    post = asyncio.run(gen_mod.generate_from_article(BRAND, GEN, "Penang", "body text", "The Star"))
    assert post.hook == "بينانغ تسرق القلب"
    assert post.hashtags == ["#سفر", "#ماليزيا"] and len(post.slides) == 2
    assert seen["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert seen["auth"] == "Bearer AK-123"
    assert seen["body"]["model"] == "mistral-test"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in seen["body"]["messages"][1]["content"]


def test_anythingllm_retries_without_json_mode_then_on_bad_json(client, anythingllm, monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "unknown field response_format"})
        if len(calls) == 2:
            return reply("I cannot do JSON, sorry.")
        return reply(json.dumps(GOOD, ensure_ascii=False))

    monkeypatch.setattr(gen_mod.httpx, "AsyncClient", _mock(gen_mod, handler))
    post = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "شلالات لنكاوي"))
    assert post.hook == "بينانغ تسرق القلب"
    assert len(calls) == 3
    assert "not a valid json object" in calls[2]["messages"][-1]["content"]


def test_anythingllm_surfaces_server_errors(client, anythingllm, monkeypatch):
    monkeypatch.setattr(anythingllm, "ai_json_mode", False)
    monkeypatch.setattr(gen_mod.httpx, "AsyncClient",
                        _mock(gen_mod, lambda r: httpx.Response(401, text="Invalid API key")))
    with pytest.raises(RuntimeError, match="رفض المفتاح"):
        asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))


def test_loose_shapes_are_normalised(client, anythingllm, monkeypatch):
    loose = {**GOOD, "hashtags": "#سفر, ماليزيا #سفر", "relevance": "7",
             "slides": ["نص شريحة بلا عنوان", {"title": "عنوان", "text": "نص"}], "cta": ""}
    monkeypatch.setattr(gen_mod.httpx, "AsyncClient", _mock(gen_mod, lambda r: reply(json.dumps(loose, ensure_ascii=False))))
    post = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert post.hashtags == ["#سفر", "#ماليزيا"] and post.relevance == 7
    assert post.slides[0] == {"heading": "", "body": "نص شريحة بلا عنوان"}
    assert post.slides[1] == {"heading": "عنوان", "body": "نص"}
    assert post.cta == post.hook


def test_missing_fields_raise(client, anythingllm, monkeypatch):
    monkeypatch.setattr(gen_mod.httpx, "AsyncClient",
                        _mock(gen_mod, lambda r: reply('{"hook": "عنوان فقط"}')))
    with pytest.raises(RuntimeError, match="الحقول المطلوبة"):
        asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))


def test_ai_info_for_mistral(client, anythingllm):
    info = gen_mod.ai_info()
    assert info["provider"] == "mistral" and info["configured"] is True and info["primary"] == "mistral"
    assert info["base_url"] == "https://api.mistral.ai/v1" and info["model"] == "mistral-test"


def test_health_reports_supabase_misconfiguration(client, monkeypatch):
    """The public /api/health must name the broken variable instead of staying silent."""
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "supabase_url", "https://proj.supabase.co/rest/v1/")
    monkeypatch.setattr(s, "supabase_anon_key", "sb_secret_abc")
    body = client.get("/api/health").json()
    assert body["ok"] is False
    assert body["auth"]["supabase_url"] == "https://proj.supabase.co"   # path stripped
    assert body["auth"]["anon_key"] == "secret_key_wrong"
    assert any("SUPABASE_ANON_KEY" in p for p in body["problems"])


def test_health_flags_missing_supabase_key(client, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "admin_email", "")
    monkeypatch.setattr(s, "admin_password", "")
    monkeypatch.setattr(s, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(s, "supabase_anon_key", "")
    body = client.get("/api/health").json()
    assert body["auth"]["mode"] == "supabase"
    assert any("SUPABASE_ANON_KEY" in p for p in body["problems"])


def test_protected_route_explains_server_misconfiguration(client, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(s, "supabase_anon_key", "")
    r = client.get("/api/drafts/counts")
    assert r.status_code == 500 and "SUPABASE_ANON_KEY" in r.json()["detail"]


def test_credentials_saved_from_the_dashboard_are_used(client, monkeypatch):
    """Keys entered in the dashboard override the environment and are never echoed back."""
    from app.config import get_settings
    from app.services import credentials
    s = get_settings()
    for f in ("mistral_api_key", "openrouter_api_key", "groq_api_key", "gemini_api_key", "cloudflare_api_key",
              "ai_primary"):
        monkeypatch.setattr(s, f, "")
    credentials.refresh()
    assert client.get("/api/status").json()["ai"]["configured"] is False

    saved = client.put("/api/settings/credentials", json={
        "ai_primary": "groq", "groq_model": "groq-model", "groq_api_key": "gsk_secret-value",
        "pexels_api_key": "PX-secret",
    }).json()["values"]
    assert saved["groq_api_key"] == {"set": True, "source": "dashboard", "hint": "…alue"}
    assert saved["engines"]["groq"]["ready"] is True
    assert set(saved["engines"]) == {"gemini", "mistral", "groq", "cloudflare", "openrouter"}
    assert "gsk_secret-value" not in str(saved)

    status = client.get("/api/status").json()
    assert status["ai"]["configured"] is True and status["ai"]["primary"] == "groq"
    assert status["ai"]["model"] == "groq-model"
    assert status["images"]["pexels"] is True

    # Empty string keeps the stored secret, null clears it
    client.put("/api/settings/credentials", json={"groq_api_key": "", "groq_model": "m2"})
    assert credentials.current()["groq_api_key"] == "gsk_secret-value"
    client.put("/api/settings/credentials", json={"groq_api_key": None})
    assert credentials.current()["groq_api_key"] == ""

    # Fields of removed engines (an old dashboard) are ignored, not an error
    r = client.put("/api/settings/credentials", json={"deepseek_api_key": "sk-x", "ai_primary": "claude"})
    assert r.status_code == 200 and "deepseek_api_key" not in r.json()["values"]
    client.put("/api/settings/credentials", json={f: None for f in credentials.FIELDS})
    credentials.refresh()


def test_publishers_read_keys_from_the_dashboard(client, monkeypatch):
    from app.config import get_settings
    from app.publishers import get_publisher
    from app.services import credentials
    s = get_settings()
    for env_field in ("buffer_api_key", "meta_access_token", "uploadpost_api_key"):
        monkeypatch.setattr(s, env_field, "")
    credentials.refresh()
    assert not any(get_publisher(n).configured() for n in ("buffer", "meta", "uploadpost"))
    client.put("/api/settings/credentials", json={"buffer_api_key": "B-1", "meta_access_token": "M-1",
                                                  "uploadpost_api_key": "U-1"})
    assert all(get_publisher(n).configured() for n in ("buffer", "meta", "uploadpost"))
    client.put("/api/settings/credentials", json={f: None for f in credentials.FIELDS})
    credentials.refresh()


def test_regenerate_failure_is_a_clean_error_with_cors(client, monkeypatch):
    """An AI failure must return JSON with CORS headers — not a crash the browser reports as CORS."""
    from app.db import Draft, Slide, session_scope
    with session_scope() as db:
        d = Draft(hook="h", caption="c " * 30, status="rejected", origin="manual")
        d.slides.append(Slide(position=0, kind="cover", heading="h", body="b"))
        db.add(d)
        db.flush()
        did = d.id

    async def boom(*a, **kw):
        raise gen_mod.AIError("تعذّر الوصول إلى خادم الذكاء الاصطناعي")
    monkeypatch.setattr(gen_mod, "regenerate_field", boom)
    r = client.post(f"/api/drafts/{did}/regenerate", json={"field": "hook"},
                    headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 502
    assert "تعذّر الوصول" in r.json()["detail"]
    client.delete(f"/api/drafts/{did}")


def test_unexpected_crash_still_returns_json(client, monkeypatch):
    from app.routes import system
    def explode():
        raise ValueError("kaboom")
    monkeypatch.setattr(system.jobs, "state", explode)
    r = client.get("/api/jobs", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 500 and "kaboom" in r.json()["detail"]
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
