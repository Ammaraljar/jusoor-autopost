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
    assert "not a valid JSON object" in calls[2]["messages"][-1]["content"]


def test_anythingllm_surfaces_server_errors(client, anythingllm, monkeypatch):
    monkeypatch.setattr(anythingllm, "ai_json_mode", False)
    monkeypatch.setattr(gen_mod.httpx, "AsyncClient",
                        _mock(gen_mod, lambda r: httpx.Response(401, text="Invalid API key")))
    with pytest.raises(RuntimeError, match="401"):
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
    assert gen_mod.ai_info() == {"configured": True, "provider": "anthropic", "model": "claude-sonnet-5", "base_url": ""}


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


def test_health_flags_missing_url(client, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "supabase_url", "")
    body = client.get("/api/health").json()
    assert any("SUPABASE_URL" in p for p in body["problems"])


def test_protected_route_explains_server_misconfiguration(client, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(s, "supabase_anon_key", "")
    r = client.get("/api/drafts/counts")
    assert r.status_code == 500 and "SUPABASE_ANON_KEY" in r.json()["detail"]
