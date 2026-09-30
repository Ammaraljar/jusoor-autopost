"""Parallel generation: Gemini + DeepSeek write at the same time, a judge picks the best post."""
import asyncio
import json

import httpx
import pytest

from app.services import credentials
from app.services import generator as gen_mod
from app.services.generator import BrandContext

BRAND = BrandContext(name="JUSOOR Travel", handle="@jusoortravel")
GEN = {"language": "ar", "tone": "friendly", "content_type": "news", "platform": "instagram", "content_slides": 2}


def post(hook, slides=2):
    return {"relevance": 9, "hook": hook, "subtitle": "سطر", "caption": "نص المنشور " * 30,
            "hashtags": ["سفر", "ماليزيا", "لنكاوي", "عائلة", "travel"],
            "slides": [{"heading": f"عنوان {i}", "body": "نص"} for i in range(slides)],
            "cta": "احجز معنا", "first_comment": "", "image_keywords": "langkawi", "badge": "news"}


def chat(content):
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


@pytest.fixture
def two_engines(client, monkeypatch):
    client.put("/api/settings/credentials", json={
        "ai_mode": "ensemble", "ai_primary": "gemini", "ai_ensemble": "gemini,deepseek",
        "gemini_api_key": "AIza-test-gemini", "deepseek_api_key": "sk-test-deepseek",
    })
    yield
    client.put("/api/settings/credentials", json={f: None for f in credentials.FIELDS})
    credentials.refresh()


def install(monkeypatch, handler):
    real = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real(*a, **kw)
    monkeypatch.setattr(gen_mod.httpx, "AsyncClient", factory)


def test_both_engines_write_and_the_judge_picks(client, two_engines, monkeypatch):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        host = request.url.host
        seen.append((host, body["model"], request.headers["Authorization"]))
        prompt = body["messages"][-1]["content"]
        assert "json" in prompt                       # DeepSeek JSON mode requirement
        if "choose_best" in prompt or "Candidates" in prompt:
            return chat(json.dumps({"winner": "B", "scores": {"A": 6, "B": 9},
                                    "reason": "عنوان أقوى ولغة أوضح"}, ensure_ascii=False))
        hook = "نسخة Gemini" if host == "generativelanguage.googleapis.com" else "نسخة DeepSeek"
        return chat(json.dumps(post(hook), ensure_ascii=False))

    install(monkeypatch, handler)
    result = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "شلالات لنكاوي"))

    assert result.hook == "نسخة DeepSeek"                     # B = deepseek won
    assert result.meta["mode"] == "ensemble" and result.meta["engine"] == "deepseek"
    assert result.meta["method"] == "judge" and result.meta["judge"] == "Gemini"
    assert result.meta["scores"] == {"Gemini": 6, "DeepSeek": 9}
    assert result.meta["reason"] == "عنوان أقوى ولغة أوضح"

    hosts = [h for h, _m, _a in seen]
    assert hosts.count("generativelanguage.googleapis.com") == 2   # writer + judge
    assert hosts.count("api.deepseek.com") == 1
    auth = {h: a for h, _m, a in seen}
    assert auth["api.deepseek.com"] == "Bearer sk-test-deepseek"
    models = {h: m for h, m, _a in seen}
    assert models["api.deepseek.com"] == "deepseek-flash"
    assert models["generativelanguage.googleapis.com"] == "gemini-3.8-flash"


def test_one_engine_failing_does_not_stop_the_post(client, two_engines, monkeypatch):
    def handler(request):
        if request.url.host == "api.deepseek.com":
            return httpx.Response(402, json={"error": "Insufficient Balance"})
        return chat(json.dumps(post("نسخة Gemini"), ensure_ascii=False))

    install(monkeypatch, handler)
    result = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert result.hook == "نسخة Gemini"
    assert result.meta["engine"] == "gemini" and "DeepSeek" in result.meta["errors"]
    assert "الرصيد" in result.meta["errors"]["DeepSeek"]


def test_judge_failure_falls_back_to_quality_rules(client, two_engines, monkeypatch):
    def handler(request):
        prompt = json.loads(request.content)["messages"][-1]["content"]
        if "Candidates" in prompt:
            return httpx.Response(500, text="judge down")
        if request.url.host == "api.deepseek.com":
            weak = post("عنوان طويل جدا جدا جدا جدا جدا جدا جدا جدا جدا جدا جدا جدا", slides=1)
            weak["hashtags"] = ["سفر"]
            return chat(json.dumps(weak, ensure_ascii=False))
        return chat(json.dumps(post("عنوان قصير وقوي"), ensure_ascii=False))

    install(monkeypatch, handler)
    result = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert result.hook == "عنوان قصير وقوي"
    assert result.meta["method"] == "rules"


def test_all_engines_failing_gives_one_clear_error(client, two_engines, monkeypatch):
    install(monkeypatch, lambda r: httpx.Response(401, text="bad key"))
    with pytest.raises(gen_mod.AIError) as err:
        asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert "Gemini" in str(err.value) and "DeepSeek" in str(err.value)


def test_ensemble_verdict_is_stored_on_the_draft(client, two_engines, monkeypatch, fake_network):
    def handler(request):
        prompt = json.loads(request.content)["messages"][-1]["content"]
        if "Candidates" in prompt:
            return chat('{"winner": "A", "scores": {"A": 8, "B": 7}, "reason": "أدق"}')
        return chat(json.dumps(post("منشور"), ensure_ascii=False))

    install(monkeypatch, handler)
    created = client.post("/api/drafts/manual", json={"topic": "أفضل وقت لزيارة بينانغ"}).json()
    assert created["ok"]
    drafts = client.get("/api/drafts?status=all").json()
    d = client.get(f"/api/drafts/{drafts[0]['id']}").json()
    assert d["ai_meta"]["mode"] == "ensemble" and d["ai_meta"]["engine"] == "gemini"
    assert d["ai_meta"]["reason"] == "أدق"
    client.delete(f"/api/drafts/{d['id']}")


def test_single_mode_uses_only_the_primary(client, monkeypatch):
    client.put("/api/settings/credentials", json={"ai_mode": "single", "ai_primary": "deepseek",
                                                  "deepseek_api_key": "sk-x", "gemini_api_key": "AIza-y"})
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        return chat(json.dumps(post("واحد"), ensure_ascii=False))

    install(monkeypatch, handler)
    result = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert hosts == ["api.deepseek.com"] and result.meta == {"mode": "single", "engine": "deepseek",
                                                              "engine_label": "DeepSeek"}
    client.put("/api/settings/credentials", json={f: None for f in credentials.FIELDS})
    credentials.refresh()


def test_ensemble_warnings(client):
    client.put("/api/settings/credentials", json={"ai_mode": "ensemble", "ai_ensemble": "gemini,deepseek",
                                                  "gemini_api_key": "AQ.not-a-gemini-key"})
    warnings = client.get("/api/settings/credentials").json()["values"]["warnings"]
    assert any("محرّكين" in w for w in warnings)          # only one engine ready
    assert any("AIza" in w for w in warnings)             # key format hint
    client.put("/api/settings/credentials", json={f: None for f in credentials.FIELDS})
    credentials.refresh()


def test_migration_adds_new_column_to_an_old_database(tmp_path, monkeypatch):
    """A database created by the previous release gets the new column on start-up."""
    from sqlalchemy import create_engine, inspect, text

    from app import db as db_mod
    old = create_engine(f"sqlite:///{tmp_path}/old.db")
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE drafts (id INTEGER PRIMARY KEY, hook TEXT)"))
    monkeypatch.setattr(db_mod, "engine", old)
    db_mod._migrate()
    assert {"ai_meta", "palette"} <= {c["name"] for c in inspect(old).get_columns("drafts")}
    db_mod._migrate()   # idempotent


def test_railway_variables_alone_enable_gemini_and_deepseek(client, monkeypatch):
    """The production situation: an old localhost AnythingLLM setting is stored in the database,
    and the two keys arrive as Railway variables. The variables must be enough on their own."""
    from app.config import get_settings
    from app.db import AppSetting, session_scope

    with session_scope() as db:                    # what the first dashboard version saved
        row = db.get(AppSetting, credentials.SETTINGS_KEY)
        legacy = {"ai_provider": "openai_compatible", "ai_base_url": "http://localhost:3001/api/v1",
                  "ai_model": "claude-sonnet-5", "ai_api_key": "AK-old"}
        if row:
            row.value = legacy
        else:
            db.add(AppSetting(key=credentials.SETTINGS_KEY, value=legacy))
    credentials.refresh()

    s = get_settings()
    for attr, value in {"gemini_api_key": "AIza-env", "deepseek_api_key": "sk-env", "ai_mode": "ensemble",
                        "ai_ensemble": "gemini,deepseek", "ai_primary": "deepseek",
                        "anthropic_api_key": ""}.items():
        monkeypatch.setattr(s, attr, value)

    info = client.get("/api/status").json()["ai"]
    assert info["mode"] == "ensemble" and info["primary"] == "deepseek"
    assert info["ensemble"] == ["gemini", "deepseek"]

    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        prompt = json.loads(request.content)["messages"][-1]["content"]
        if "Candidates" in prompt:
            return chat('{"winner": "A", "scores": {"A": 8, "B": 7}, "reason": "أوضح"}')
        return chat(json.dumps(post("منشور"), ensure_ascii=False))

    install(monkeypatch, handler)
    result = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert result.meta["mode"] == "ensemble" and result.meta["judge"] == "DeepSeek"
    assert "localhost" not in hosts and hosts.count("api.deepseek.com") == 2   # writer + judge

    # Quick edits go to the primary (DeepSeek), never to the dead localhost server
    hosts.clear()
    data = asyncio.run(gen_mod._call_model("s", "u", {"name": "t", "input_schema": {"type": "object"}}))
    assert hosts == ["api.deepseek.com"] and isinstance(data, dict)

    with session_scope() as db:
        db.get(AppSetting, credentials.SETTINGS_KEY).value = {}
    credentials.refresh()


def test_gemini_failing_still_produces_posts_with_deepseek(client, monkeypatch):
    """If the Google key turns out to be invalid, DeepSeek alone keeps the pipeline running."""
    from app.config import get_settings
    s = get_settings()
    for attr, value in {"gemini_api_key": "AQ.not-a-real-gemini-key", "deepseek_api_key": "sk-env",
                        "ai_mode": "ensemble", "ai_ensemble": "gemini,deepseek", "ai_primary": "deepseek",
                        "anthropic_api_key": ""}.items():
        monkeypatch.setattr(s, attr, value)
    credentials.refresh()

    def handler(request):
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(401, json={"error": {"message": "API key not valid"}})
        return chat(json.dumps(post("من DeepSeek"), ensure_ascii=False))

    install(monkeypatch, handler)
    result = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert result.hook == "من DeepSeek" and "Gemini" in result.meta["errors"]


def test_busy_provider_is_retried_until_it_answers(client, monkeypatch):
    """Gemini's 503 "high demand" is temporary: wait and try again instead of failing."""
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "AIza-ok")
    monkeypatch.setattr(s, "ai_primary", "gemini")
    monkeypatch.setattr(s, "ai_mode", "single")
    monkeypatch.setattr(s, "anthropic_api_key", "")
    credentials.refresh()
    calls = []
    busy = {"error": {"code": 503, "message": "This model is currently experiencing high demand.",
                      "status": "UNAVAILABLE"}}

    def handler(request):
        calls.append(1)
        if len(calls) <= 2:
            return httpx.Response(503, json=[busy])
        return chat(json.dumps(post("بعد الانتظار"), ensure_ascii=False))

    install(monkeypatch, handler)
    result = asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert result.hook == "بعد الانتظار" and len(calls) == 3


def test_busy_provider_gives_a_clear_message_when_it_stays_busy(client, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "AIza-ok")
    monkeypatch.setattr(s, "ai_primary", "gemini")
    monkeypatch.setattr(s, "ai_mode", "single")
    monkeypatch.setattr(s, "anthropic_api_key", "")
    credentials.refresh()
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, text="overloaded")

    install(monkeypatch, handler)
    with pytest.raises(gen_mod.AIError) as err:
        asyncio.run(gen_mod.generate_from_topic(BRAND, GEN, "موضوع"))
    assert "المفتاح صالح" in str(err.value) and "مؤقتة" in str(err.value)
    assert len(calls) == 1 + len(gen_mod.RETRY_DELAYS)
    # json mode must be kept during retries (a 503 is not a rejection of response_format)


def test_new_engines_route_to_their_hosts(client, monkeypatch):
    """Mistral, OpenRouter and Groq are first-class engines with their own hosts, models and headers."""
    generator = gen_mod
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.append((request.url.host, request.url.path, body["model"], dict(request.headers)))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(post("x"))}}]})

    install(monkeypatch, handler)
    client.put("/api/settings/credentials", json={
        "ai_mode": "single", "mistral_api_key": "mk-test", "openrouter_api_key": "sk-or-test",
        "groq_api_key": "gsk_test"})
    try:
        for name in ("mistral", "openrouter", "groq"):
            cfg = credentials.engine(name)
            asyncio.run(generator._call_openai_compatible(cfg, "sys", "user", generator.POST_TOOL))
        hosts = {h: (p, m, hd) for h, p, m, hd in seen}
        assert hosts["api.mistral.ai"][:2] == ("/v1/chat/completions", "mistral-small-4-0-26-03")
        assert hosts["openrouter.ai"][:2] == ("/api/v1/chat/completions", "openrouter/free")
        assert hosts["openrouter.ai"][2]["x-title"] == "JUSOOR AutoPost"
        assert hosts["api.groq.com"][:2] == ("/openai/v1/chat/completions", "openai/gpt-oss-120b")
        assert hosts["api.groq.com"][2]["authorization"] == "Bearer gsk_test"
        view = client.get("/api/settings/credentials").json()["values"]
        assert all(view["engines"][n]["ready"] for n in ("mistral", "openrouter", "groq"))
    finally:
        client.put("/api/settings/credentials", json={
            "mistral_api_key": None, "openrouter_api_key": None, "groq_api_key": None})


def test_mistral_key_id_warning(client):
    client.put("/api/settings/credentials", json={"mistral_api_key": "123e4567-e89b-12d3-a456-426614174000"})
    try:
        warnings = client.get("/api/settings/credentials").json()["values"]["warnings"]
        assert any("Mistral" in w for w in warnings)
    finally:
        client.put("/api/settings/credentials", json={"mistral_api_key": None})
