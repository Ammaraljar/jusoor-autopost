"""AI content generation.

Two providers are supported and chosen with AI_PROVIDER:

* ``anthropic``          — Claude API with tool use, which guarantees valid structured output.
* ``openai_compatible``  — any OpenAI-compatible server (AnythingLLM, Ollama, LM Studio, vLLM…).
  Those servers usually have no tool calling, so the JSON Schema is put in the prompt and the
  reply is parsed defensively (code fences, stray text and a retry round are all handled).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import get_settings
from . import credentials

log = logging.getLogger(__name__)

LANG_NAMES = {"ar": "Modern Standard Arabic (فصحى سهلة)", "en": "English", "fr": "French"}

POST_TOOL = {
    "name": "create_post",
    "description": "Return the complete social media carousel post.",
    "input_schema": {
        "type": "object",
        "properties": {
            "relevance": {"type": "integer", "minimum": 0, "maximum": 10,
                          "description": "How relevant/useful this is for the brand's travel audience (0-10)."},
            "relevance_reason": {"type": "string"},
            "hook": {"type": "string", "description": "Scroll-stopping title, max 10 words."},
            "subtitle": {"type": "string", "description": "One short supporting line, max 14 words."},
            "caption": {"type": "string", "description": "Post caption, 60-160 words, short paragraphs, ends with a soft CTA."},
            "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 14},
            "slides": {
                "type": "array",
                "description": "Content slides (not including cover and CTA).",
                "items": {"type": "object",
                          "properties": {"heading": {"type": "string", "description": "max 6 words"},
                                         "body": {"type": "string", "description": "max 35 words"}},
                          "required": ["heading", "body"]},
            },
            "cta": {"type": "string", "description": "Closing call-to-action slide text, max 16 words."},
            "first_comment": {"type": "string",
                              "description": "Optional first comment (extra tip or question). Empty string if none."},
            "image_keywords": {"type": "string", "description": "3-6 English keywords for a stock photo search."},
            "badge": {"type": "string", "enum": ["news", "tips", "guide", "offer", "event", "culture", "food"]},
        },
        "required": ["relevance", "hook", "subtitle", "caption", "hashtags", "slides", "cta",
                     "first_comment", "image_keywords", "badge"],
    },
}


@dataclass
class GeneratedPost:
    hook: str
    subtitle: str
    caption: str
    hashtags: list[str]
    slides: list[dict[str, str]]
    cta: str
    first_comment: str = ""
    image_keywords: str = ""
    badge: str = "news"
    relevance: int = 10
    relevance_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)   # which engine wrote it, ensemble verdict


@dataclass
class BrandContext:
    name: str
    handle: str = ""
    website: str = ""
    voice: str = ""
    cta_text: str = ""


def build_system_prompt(brand: BrandContext, gen: dict[str, Any]) -> str:
    lang = LANG_NAMES.get(gen.get("language", "ar"), "Arabic")
    return f"""You are the senior social media editor for {brand.name} ({brand.handle}), a premium travel brand.
Brand voice: {brand.voice or 'sophisticated, warm, trustworthy and inspiring'}.
Target audience: {gen.get('audience') or 'Arab travellers'}.
Marketing objective: {gen.get('objective') or 'engagement and trust'}.
Write everything in {lang}. Tone: {gen.get('tone', 'friendly')}. Content type: {gen.get('content_type', 'news')}.
Platform: {gen.get('platform', 'instagram')} carousel (1080x1350).

Rules:
- Use ONLY facts present in the source material. Never invent prices, dates, names, numbers or quotes.
- Rewrite in your own words; do not translate sentence by sentence and do not copy long passages.
- Keep brand and place names recognisable (you may add the English name in brackets once).
- Hashtags: mix of Arabic and English where useful, no spaces inside a hashtag, each starts with #.
- Never output placeholder text such as "لا يوجد" or "N/A". If there is no good first comment, return an empty string.
- Produce exactly {int(gen.get('content_slides', 4))} content slides that tell a clear story (what / why it matters / tips / how to go).
- The CTA should invite followers to contact or book with {brand.name}{(' — ' + brand.cta_text) if brand.cta_text else ''}.
- Score relevance honestly: general culture or politics with no travel angle should score low (0-4)."""


def _normalise_hashtags(tags: Any) -> list[str]:
    if isinstance(tags, str):
        tags = re.split(r"[\s,]+", tags)
    out: list[str] = []
    for t in tags or []:
        t = re.sub(r"\s+", "_", str(t).strip().lstrip("#"))
        if t and f"#{t}" not in out:
            out.append(f"#{t}")
    return out


def _normalise_slides(slides: Any) -> list[dict[str, str]]:
    """Weaker models sometimes return plain strings or different key names."""
    out: list[dict[str, str]] = []
    for item in slides or []:
        if isinstance(item, str):
            heading, body = "", item
        elif isinstance(item, dict):
            heading = str(item.get("heading") or item.get("title") or "").strip()
            body = str(item.get("body") or item.get("text") or item.get("content") or "").strip()
        else:
            continue
        if body or heading:
            out.append({"heading": heading, "body": body or heading})
    return out[:8]


def _as_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return str(value).strip() if value is not None and not isinstance(value, (list, dict)) else ""


def _parse(data: dict[str, Any]) -> GeneratedPost:
    post = GeneratedPost(
        hook=_text(data.get("hook")),
        subtitle=_text(data.get("subtitle")),
        caption=_text(data.get("caption")),
        hashtags=_normalise_hashtags(data.get("hashtags")),
        slides=_normalise_slides(data.get("slides")),
        cta=_text(data.get("cta")),
        first_comment=_text(data.get("first_comment")),
        image_keywords=_text(data.get("image_keywords")),
        badge=_text(data.get("badge")) or "news",
        relevance=max(0, min(10, _as_int(data.get("relevance"), 10))),
        relevance_reason=_text(data.get("relevance_reason")),
        raw=data,
    )
    missing = [k for k in ("hook", "caption") if not getattr(post, k)] + ([] if post.slides else ["slides"])
    if missing:
        raise RuntimeError("النموذج لم يُعد الحقول المطلوبة: " + "، ".join(missing))
    if not post.cta:
        post.cta = post.hook
    return post


class AIError(RuntimeError):
    """A readable, user-facing failure of an AI engine."""


# Provider-side overload or rate limit: retried after a short pause (seconds between attempts).
TRANSIENT_STATUSES = (429, 500, 502, 503, 504)
RETRY_DELAYS: tuple[float, ...] = (3, 8, 15)


# ============================================================ Claude (tool use)
async def _call_claude(cfg: dict[str, str], system: str, user: str, tool: dict[str, Any],
                       max_tokens: int = 3000) -> dict[str, Any]:
    """Anthropic tool use — the model can only answer with a valid tool input."""
    import anthropic
    from anthropic import AsyncAnthropic

    s = get_settings()
    if not cfg["api_key"]:
        raise AIError("مفتاح Claude غير مضبوط — أضفه من الإعدادات ← المفاتيح والاتصالات")
    client = AsyncAnthropic(api_key=cfg["api_key"], timeout=s.ai_timeout_seconds)
    try:
        msg = await client.messages.create(
            model=cfg["model"] or "claude-sonnet-5",
            max_tokens=max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as exc:
        raise AIError("مفتاح Claude مرفوض — تأكد من نسخه كاملًا من console.anthropic.com") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AIError("مفتاح Claude لا يملك صلاحية — تحقق من رصيد الحساب") from exc
    except anthropic.NotFoundError as exc:
        raise AIError(f"نموذج Claude «{cfg['model']}» غير موجود") from exc
    except anthropic.RateLimitError as exc:
        raise AIError("Claude: تجاوزت حد الاستخدام أو نفد الرصيد") from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("تعذّر الاتصال بخوادم Anthropic — أعد المحاولة بعد قليل") from exc
    except anthropic.APIStatusError as exc:
        raise AIError(f"رد غير متوقع من Claude ({exc.status_code}): {str(exc)[:200]}") from exc
    for block in msg.content:
        if block.type == "tool_use":
            return dict(block.input)
    raise AIError("Claude لم يُعد مخرجات منظّمة")


# ============================================================ OpenAI-compatible engines
def extract_json(text: str) -> dict[str, Any]:
    """Pull one JSON object out of a free-text reply (code fences, prefixes, trailing notes)."""
    if not text or not text.strip():
        raise ValueError("empty reply")
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object in reply")
    depth, in_string, escaped = 0, False, False
    for i, ch in enumerate(cleaned[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                data = json.loads(cleaned[start:i + 1])
                if not isinstance(data, dict):
                    raise ValueError("reply is not a JSON object")
                return data
    raise ValueError("unterminated JSON object")


def _schema_prompt(user: str, tool: dict[str, Any]) -> str:
    # The word "json" must appear literally — DeepSeek's JSON mode requires it.
    return (f"{user}\n\n"
            "Answer with ONE json object and nothing else: no explanation, no markdown, no code fences.\n"
            "It must follow this JSON Schema exactly (all required keys present, correct types):\n"
            f"{json.dumps(tool['input_schema'], ensure_ascii=False)}")


async def _call_openai_compatible(cfg: dict[str, str], system: str, user: str, tool: dict[str, Any],
                                  max_tokens: int = 3000) -> dict[str, Any]:
    """Gemini, DeepSeek, AnythingLLM…: ask for JSON in the prompt, then parse it defensively."""
    s = get_settings()
    label = cfg["label"]
    if not cfg["base_url"]:
        raise AIError(f"{label}: رابط الخادم غير مضبوط")
    if cfg["name"] != "custom" and not cfg["api_key"]:
        raise AIError(f"مفتاح {label} غير مضبوط")
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    if cfg["name"] == "openrouter":            # optional attribution headers OpenRouter recommends
        headers["HTTP-Referer"] = s.public_base_url or "https://jusoor-autopost.app"
        headers["X-Title"] = "JUSOOR AutoPost"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": _schema_prompt(user, tool)}]
    json_mode = s.ai_json_mode
    last_error = ""
    json_retries = 0
    transient = 0

    async with httpx.AsyncClient(timeout=s.ai_timeout_seconds) as client:
        while True:
            payload: dict[str, Any] = {"model": cfg["model"], "messages": messages,
                                       "max_tokens": max_tokens, "temperature": 0.6, "stream": False}
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.ConnectError as exc:
                warnings = [w for w in credentials.ai_warnings() if "جهازك المحلي" in w] if cfg["name"] == "custom" else []
                raise AIError(warnings[0] if warnings else f"{label}: تعذّر الوصول إلى {cfg['base_url']}") from exc
            except httpx.TimeoutException as exc:
                raise AIError(f"{label}: انتهت مهلة الاتصال ({s.ai_timeout_seconds} ثانية)") from exc
            except httpx.TransportError as exc:
                raise AIError(f"{label}: تعذّر الوصول إلى {cfg['base_url']} ({exc})") from exc

            # Overload / rate limit on the provider's side: wait and try again.
            if resp.status_code in TRANSIENT_STATUSES:
                if transient < len(RETRY_DELAYS):
                    log.warning("%s busy (%s), retrying in %ss", label, resp.status_code, RETRY_DELAYS[transient])
                    await asyncio.sleep(RETRY_DELAYS[transient])
                    transient += 1
                    continue
                if resp.status_code == 429:
                    raise AIError(f"{label}: تجاوزت حد الطلبات أو الحصة المجانية — انتظر قليلًا ثم أعد المحاولة")
                raise AIError(f"{label} مشغول حاليًا بسبب ضغط الطلبات عنده (خطأ {resp.status_code}) — "
                              "المفتاح صالح، والمشكلة مؤقتة من جهة المزوّد؛ أعد المحاولة بعد دقائق")
            if resp.status_code in (401, 403):
                raise AIError(f"{label} رفض المفتاح — تأكد من المفتاح أو أنشئ مفتاحًا جديدًا")
            if resp.status_code == 402:
                tip = " أو اختر نموذجًا مجانيًا مثل openrouter/free" if cfg["name"] == "openrouter" else ""
                raise AIError(f"{label}: الرصيد غير كافٍ — أضف رصيدًا في حسابك{tip}")
            if resp.status_code == 404:
                raise AIError(f"{label}: الرابط أو النموذج «{cfg['model']}» غير موجود")
            if resp.status_code >= 400:
                body = resp.text[:300]
                if json_mode:
                    # Some servers reject response_format — drop it and retry once.
                    log.warning("%s rejected json mode (%s), retrying without it", label, resp.status_code)
                    json_mode = False
                    continue
                raise AIError(f"{label} أعاد خطأ {resp.status_code}: {body}")
            try:
                data = resp.json()
            except ValueError as exc:
                raise AIError(f"{label}: رد غير مفهوم: {resp.text[:200]}") from exc
            choices = data.get("choices") or []
            if not choices:
                raise AIError(f"{label}: لم يُرجع أي رد")
            message = choices[0].get("message") or {}
            text = message.get("content") or choices[0].get("text") or ""
            if isinstance(text, list):   # some servers return content parts
                text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
            try:
                return extract_json(text)
            except ValueError as exc:
                last_error = str(exc)
                json_retries += 1
                if json_retries >= 3:
                    break
                log.warning("%s reply was not valid JSON (%s), asking again", label, last_error)
                messages = messages[:2] + [
                    {"role": "assistant", "content": text[:2000] or "(empty)"},
                    {"role": "user", "content": "Your previous reply was not a valid json object "
                                                f"({last_error}). Return ONLY the json object, nothing else."},
                ]
    raise AIError(f"{label}: لم يُرجع JSON صالحًا بعد 3 محاولات ({last_error})")


# ============================================================ engine routing
async def _call_engine(name: str, system: str, user: str, tool: dict[str, Any],
                       max_tokens: int = 3000) -> dict[str, Any]:
    cfg = credentials.engine(name)
    if cfg["kind"] == "anthropic":
        return await _call_claude(cfg, system, user, tool, max_tokens)
    return await _call_openai_compatible(cfg, system, user, tool, max_tokens)


def _primary() -> str:
    return credentials.current()["ai_primary"]


async def _call_model(system: str, user: str, tool: dict[str, Any], max_tokens: int = 3000) -> dict[str, Any]:
    """Quick tasks (rewrite one field or one slide) use the primary engine only."""
    return await _call_engine(_primary(), system, user, tool, max_tokens)


JUDGE_TOOL = {
    "name": "choose_best",
    "description": "Pick the best social media post among the candidates.",
    "input_schema": {
        "type": "object",
        "properties": {
            "winner": {"type": "string", "description": "Label of the best candidate (A, B, C…)."},
            "scores": {"type": "object", "description": "Score from 0 to 10 for every label.",
                       "additionalProperties": {"type": "integer"}},
            "reason": {"type": "string", "description": "One short sentence in Arabic explaining the choice."},
        },
        "required": ["winner", "scores", "reason"],
    },
}


def heuristic_score(post: GeneratedPost, expected_slides: int) -> float:
    """Rule-based quality score used when no judge is available."""
    score = 0.0
    score += 2 if 0 < len(post.hook.split()) <= 10 else 0
    score += 2 if 40 <= len(post.caption.split()) <= 220 else 0
    score += 2 if 5 <= len(post.hashtags) <= 14 else 0
    score += 2 if len(post.slides) == expected_slides else (1 if post.slides else 0)
    score += 1 if post.cta and post.cta != post.hook else 0
    score += 1 if not re.search(r"لا يوجد|N/A|TODO|\{\{", " ".join([post.hook, post.caption, post.cta])) else 0
    return score + post.relevance / 10


def _candidate_view(post: GeneratedPost) -> dict[str, Any]:
    return {"hook": post.hook, "subtitle": post.subtitle, "caption": post.caption, "hashtags": post.hashtags,
            "slides": post.slides, "cta": post.cta}


async def _judge(brand_system: str, candidates: list[tuple[str, GeneratedPost]], expected_slides: int,
                 judge_engine: str) -> tuple[int, dict[str, Any]]:
    """Return the index of the best candidate and the verdict details."""
    labels = [chr(ord("A") + i) for i in range(len(candidates))]
    listing = {labels[i]: _candidate_view(post) for i, (_name, post) in enumerate(candidates)}
    user = ("Several writers produced the same carousel post. Judge them as a senior editor for this brand: "
            "accuracy to the source, natural Arabic, hook strength, clarity of the slides, and a useful CTA. "
            "Do not favour length.\n\n"
            f"Candidates:\n{json.dumps(listing, ensure_ascii=False)}\n\nUse the choose_best tool.")
    try:
        verdict = await _call_engine(judge_engine, brand_system, user, JUDGE_TOOL, max_tokens=500)
        winner = str(verdict.get("winner", "")).strip().upper()[:1]
        if winner in labels:
            scores = {str(k).upper(): _as_int(v, 0) for k, v in (verdict.get("scores") or {}).items()}
            return labels.index(winner), {
                "method": "judge", "judge": credentials.ENGINES[judge_engine]["label"],
                "reason": _text(verdict.get("reason"))[:300],
                "scores": {candidates[i][0]: scores.get(labels[i]) for i in range(len(candidates))},
            }
        log.warning("judge returned an unknown winner: %s", verdict)
    except Exception as exc:  # noqa: BLE001 - a failed judge must not lose good posts
        log.warning("judge failed, falling back to rules: %s", exc)
    scores = [heuristic_score(post, expected_slides) for _name, post in candidates]
    best = max(range(len(candidates)), key=lambda i: scores[i])
    return best, {"method": "rules", "reason": "اختيار آلي حسب قواعد الجودة (تعذّر عمل الحَكَم)",
                  "scores": {candidates[i][0]: round(scores[i], 1) for i in range(len(candidates))}}


async def _generate_post(system: str, user: str, gen: dict[str, Any]) -> GeneratedPost:
    """Full post generation: one engine, or several in parallel with a judge."""
    cfg = credentials.current()
    engines = credentials.ensemble_engines(cfg) if cfg["ai_mode"] == "ensemble" else []
    label = lambda n: credentials.ENGINES[n]["label"]  # noqa: E731

    if len(engines) < 2:
        name = cfg["ai_primary"]
        post = _parse(await _call_engine(name, system, user, POST_TOOL))
        post.meta = {"mode": "single", "engine": name, "engine_label": label(name)}
        return post

    results = await asyncio.gather(*(_call_engine(n, system, user, POST_TOOL) for n in engines),
                                   return_exceptions=True)
    candidates: list[tuple[str, GeneratedPost]] = []
    errors: dict[str, str] = {}
    for name, res in zip(engines, results):
        if isinstance(res, BaseException):
            errors[name] = str(res)[:300]
            continue
        try:
            candidates.append((name, _parse(res)))
        except Exception as exc:  # noqa: BLE001
            errors[name] = str(exc)[:300]
    if not candidates:
        raise AIError("فشلت كل المحرّكات: " + " | ".join(f"{label(n)}: {e}" for n, e in errors.items()))

    expected = int(gen.get("content_slides", 4))
    if len(candidates) == 1:
        name, post = candidates[0]
        post.meta = {"mode": "ensemble", "engine": name, "engine_label": label(name),
                     "candidates": [name], "errors": {label(n): e for n, e in errors.items()},
                     "reason": "المحرّك الوحيد الذي نجح"}
        return post

    judge = cfg["ai_primary"] if cfg["ai_primary"] in credentials.ready_engines(cfg) else candidates[0][0]
    best, verdict = await _judge(system, candidates, expected, judge)
    name, post = candidates[best]
    post.meta = {"mode": "ensemble", "engine": name, "engine_label": label(name),
                 "candidates": [n for n, _p in candidates],
                 "scores": {label(n): v for n, v in verdict["scores"].items()},
                 "method": verdict["method"], "judge": verdict.get("judge"), "reason": verdict["reason"],
                 "errors": {label(n): e for n, e in errors.items()}}
    return post


# ============================================================ status & connection test
async def test_connection() -> dict[str, Any]:
    """Round-trip to every ready engine in parallel — powers the "test connection" button."""
    tool = {"name": "ping", "description": "Reply with a short greeting.",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}
    names = credentials.ready_engines() or [_primary()]

    async def one(name: str) -> dict[str, Any]:
        cfg = credentials.engine(name)
        try:
            data = await _call_engine(name, "You are a helpful assistant. Answer in Arabic.",
                                      "قل مرحبًا بكلمتين فقط.", tool, max_tokens=80)
            return {"engine": name, "label": cfg["label"], "model": cfg["model"], "ok": True,
                    "reply": _text(data.get("text"))[:120]}
        except Exception as exc:  # noqa: BLE001 - the message is what the user needs
            return {"engine": name, "label": cfg["label"], "model": cfg["model"], "ok": False,
                    "error": str(exc)[:400]}

    results = list(await asyncio.gather(*(one(n) for n in names)))
    return {"ok": any(r["ok"] for r in results), "engines": results, **ai_info()}


def ai_available() -> bool:
    return bool(credentials.ready_engines())


def ai_info() -> dict[str, Any]:
    cfg = credentials.current()
    primary = cfg["ai_primary"]
    engine = credentials.engine(primary, cfg)
    return {"configured": ai_available(), "mode": cfg["ai_mode"], "primary": primary,
            "provider": "anthropic" if engine["kind"] == "anthropic" else "openai_compatible",
            "model": engine["model"], "base_url": engine["base_url"] if primary == "custom" else "",
            "ready": credentials.ready_engines(cfg), "ensemble": credentials.ensemble_engines(cfg),
            "source": credentials.source_of(f"{primary}_api_key")}


async def generate_from_article(brand: BrandContext, gen: dict[str, Any], title: str, body: str,
                                source_name: str = "") -> GeneratedPost:
    user = (f"Source: {source_name}\nOriginal title: {title}\n\nArticle:\n{body[:12000]}\n\n"
            "Create the carousel post using the create_post tool.")
    if not ai_available():
        return demo_post(title, body, gen)
    return await _generate_post(build_system_prompt(brand, gen), user, gen)


async def generate_from_topic(brand: BrandContext, gen: dict[str, Any], topic: str, notes: str = "") -> GeneratedPost:
    user = (f"Planned content-calendar topic: {topic}\nEditor notes: {notes or '-'}\n\n"
            "There is no source article: write evergreen, factual content only (no specific prices or dates). "
            "Relevance should reflect the topic fit. Use the create_post tool.")
    if not ai_available():
        return demo_post(topic, notes, gen)
    return await _generate_post(build_system_prompt(brand, gen), user, gen)


async def regenerate_field(brand: BrandContext, gen: dict[str, Any], draft_context: str, field_name: str) -> str:
    """Regenerate a single text field (hook | caption | cta | first_comment)."""
    tool = {"name": "rewrite", "description": f"Return a fresh alternative for the {field_name}.",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}
    user = (f"Current post:\n{draft_context}\n\nWrite a new, clearly different and stronger {field_name}. "
            "Keep the same facts and language. Use the rewrite tool.")
    if not ai_available():
        return f"{field_name} — نسخة تجريبية جديدة"
    data = await _call_model(build_system_prompt(brand, gen), user, tool, max_tokens=800)
    return _text(data.get("text"))


async def regenerate_slide(brand: BrandContext, gen: dict[str, Any], draft_context: str,
                           heading: str, body: str) -> dict[str, str]:
    tool = {"name": "slide", "description": "Return the rewritten slide.",
            "input_schema": {"type": "object",
                             "properties": {"heading": {"type": "string"}, "body": {"type": "string"}},
                             "required": ["heading", "body"]}}
    user = (f"Post context:\n{draft_context}\n\nRewrite this slide to be clearer and more engaging "
            f"(heading max 6 words, body max 35 words):\nHeading: {heading}\nBody: {body}")
    if not ai_available():
        return {"heading": heading, "body": body}
    data = await _call_model(build_system_prompt(brand, gen), user, tool, max_tokens=600)
    return {"heading": _text(data.get("heading")) or heading, "body": _text(data.get("body")) or body}


def demo_post(title: str, body: str, gen: dict[str, Any]) -> GeneratedPost:
    """Deterministic placeholder used when no AI provider is configured (local demo / tests)."""
    n = int(gen.get("content_slides", 4))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?؟])\s+", body or "") if s.strip()] or [title]
    slides = [{"heading": f"النقطة {i + 1}", "body": sentences[i % len(sentences)][:180]} for i in range(n)]
    return GeneratedPost(
        hook=(title or "منشور تجريبي")[:80], subtitle="نسخة تجريبية — أضف مفتاح Claude لتوليد محتوى حقيقي",
        caption=f"{title}\n\n{sentences[0][:300]}\n\nتواصل معنا لتخطيط رحلتك.",
        hashtags=["#سفر", "#ماليزيا", "#سياحة", "#جسور_للسفر", "#travel"], slides=slides,
        cta="احجز رحلتك القادمة مع جسور للسفر", first_comment="", image_keywords="travel malaysia",
        badge="news", relevance=8, raw={"demo": True}, meta={"mode": "demo"},
    )


def draft_context(d) -> str:
    return json.dumps({"hook": d.hook, "subtitle": d.subtitle, "caption": d.caption[:1500],
                       "original_title": d.original_title}, ensure_ascii=False)
