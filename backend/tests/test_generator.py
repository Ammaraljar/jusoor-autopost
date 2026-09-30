"""AI provider layer: Claude tool use and OpenAI-compatible servers (AnythingLLM)."""
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
    s = get_settings()
    monkeypatch.setattr(s, "ai_provider", "openai_compatible")
    monkeypatch.setattr(s, "ai_base_url", "https://llm.example.com/api/v1/openai")
    monkeypatch.setattr(s, "ai_api_key", "AK-123")
    monkeypatch.setattr(s, "ai_model", "jusoor-workspace")
    monkeypatch.setattr(s, "ai_json_mode", True)
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
    assert seen["url"] == "https://llm.example.com/api/v1/openai/chat/completions"
    assert seen["auth"] == "Bearer AK-123"
    assert seen["body"]["model"] == "jusoor-workspace"
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


def test_claude_provider_uses_tool_use(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ai_provider", "anthropic")
    monkeypatch.setattr(s, "ai_api_key", "")
    monkeypatch.setattr(s, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(s, "anthropic_model", "claude-sonnet-5")
    captured = {}

    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            block = type("B", (), {"type": "tool_use", "input": GOOD})()
            return type("M", (), {"content": [block]})()

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)
    post = asyncio.run(gen_mod.generate_from_article(BRAND, GEN, "Penang", "body", "The Star"))
    assert post.hook == "بينانغ تسرق القلب"
    assert captured["tool_choice"] == {"type": "tool", "name": "create_post"}
    assert captured["model"] == "claude-sonnet-5"
    info = gen_mod.ai_info()
    assert info["configured"] and info["provider"] == "anthropic" and info["model"] == "claude-sonnet-5"
    assert info["primary"] == "claude" and info["mode"] == "single"


def test_ai_info_for_anythingllm(client, anythingllm):
    info = gen_mod.ai_info()
    assert info["provider"] == "openai_compatible" and info["configured"] is True
    assert info["base_url"].endswith("/api/v1/openai") and info["model"] == "jusoor-workspace"


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
    monkeypatch.setattr(s, "ai_provider", "anthropic")
    monkeypatch.setattr(s, "ai_api_key", "")
    monkeypatch.setattr(s, "anthropic_api_key", "")
    credentials.refresh()
    assert client.get("/api/status").json()["ai"]["configured"] is False

    saved = client.put("/api/settings/credentials", json={
        "ai_primary": "custom",
        "custom_base_url": "https://llm.example.com/api/v1/openai",
        "custom_model": "jusoor",
        "custom_api_key": "AK-secret-value",
        "pexels_api_key": "PX-secret",
    }).json()["values"]
    assert saved["custom_api_key"] == {"set": True, "source": "dashboard", "hint": "…alue"}
    assert saved["custom_base_url"] == "https://llm.example.com/api/v1/openai"
    assert saved["engines"]["custom"]["ready"] is True
    assert "AK-secret-value" not in str(saved)

    status = client.get("/api/status").json()
    assert status["ai"]["configured"] is True and status["ai"]["primary"] == "custom"
    assert status["ai"]["provider"] == "openai_compatible" and status["ai"]["model"] == "jusoor"
    assert status["images"]["pexels"] is True
    assert credentials.current()["custom_api_key"] == "AK-secret-value"

    # Empty string keeps the stored secret, null clears it
    client.put("/api/settings/credentials", json={"custom_api_key": "", "custom_model": "jusoor-2"})
    assert credentials.current()["custom_api_key"] == "AK-secret-value"
    client.put("/api/settings/credentials", json={"custom_api_key": None})
    assert credentials.current()["custom_api_key"] == ""

    # The first version's field names are still accepted
    client.put("/api/settings/credentials", json={"ai_provider": "anthropic", "ai_api_key": "sk-ant-legacy"})
    assert credentials.current()["claude_api_key"] == "sk-ant-legacy"
    assert credentials.current()["ai_primary"] == "claude"

    assert client.put("/api/settings/credentials", json={"nope": "x"}).status_code == 400
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


def test_localhost_ai_url_is_explained(client, monkeypatch):
    """The exact mistake from production: AnythingLLM on the user's laptop, server on the internet."""
    from app.services import credentials
    client.put("/api/settings/credentials", json={
        "ai_provider": "openai_compatible", "ai_base_url": "http://localhost:3001/api/v1",
        "ai_model": "claude-sonnet-5", "ai_api_key": "AK"})
    warnings = client.get("/api/settings/credentials").json()["values"]["warnings"]
    assert any("جهازك المحلي" in w for w in warnings)
    assert any("مساحة العمل" in w for w in warnings)
    problems = client.get("/api/health").json()["problems"]
    assert any("جهازك المحلي" in p for p in problems)

    def refuse(request):
        raise httpx.ConnectError("All connection attempts failed", request=request)
    monkeypatch.setattr(gen_mod.httpx, "AsyncClient", _mock(gen_mod, refuse))
    result = client.post("/api/settings/credentials/test-ai").json()
    assert result["ok"] is False
    custom = [e for e in result["engines"] if e["engine"] == "custom"][0]
    assert "جهازك المحلي" in custom["error"]
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
