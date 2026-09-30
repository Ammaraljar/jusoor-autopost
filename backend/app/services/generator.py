"""AI content generation.

Two providers are supported and chosen with AI_PROVIDER:

* ``anthropic``          — Claude API with tool use, which guarantees valid structured output.
* ``openai_compatible``  — any OpenAI-compatible server (AnythingLLM, Ollama, LM Studio, vLLM…).
  Those servers usually have no tool calling, so the JSON Schema is put in the prompt and the
  reply is parsed defensively (code fences, stray text and a retry round are all handled).
"""
from __future__ import annotations

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


async def _call_claude(system: str, user: str, tool: dict[str, Any], max_tokens: int = 3000) -> dict[str, Any]:
    """Anthropic tool use — the model can only answer with a valid tool input."""
    from anthropic import AsyncAnthropic

    s = get_settings()
    cfg = credentials.current()
    client = AsyncAnthropic(api_key=cfg["ai_api_key"], timeout=s.ai_timeout_seconds)
    msg = await client.messages.create(
        model=cfg["ai_model"] or "claude-sonnet-5",
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user}],
    )
    for block in msg.content:
        if block.type == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude did not return structured output")


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
    return (f"{user}\n\n"
            "Answer with ONE JSON object and nothing else: no explanation, no markdown, no code fences.\n"
            "It must follow this JSON Schema exactly (all required keys present, correct types):\n"
            f"{json.dumps(tool['input_schema'], ensure_ascii=False)}")


async def _call_openai_compatible(system: str, user: str, tool: dict[str, Any],
                                  max_tokens: int = 3000) -> dict[str, Any]:
    """AnythingLLM and friends: ask for JSON in the prompt, then parse it defensively."""
    s = get_settings()
    cfg = credentials.current()
    if not cfg["ai_base_url"]:
        raise RuntimeError("رابط خادم الذكاء الاصطناعي غير مضبوط")
    url = cfg["ai_base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['ai_api_key']}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": _schema_prompt(user, tool)}]
    json_mode = s.ai_json_mode
    last_error = ""

    async with httpx.AsyncClient(timeout=s.ai_timeout_seconds) as client:
        for attempt in range(3):
            payload: dict[str, Any] = {"model": cfg["ai_model"], "messages": messages,
                                       "max_tokens": max_tokens, "temperature": 0.6, "stream": False}
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                body = resp.text[:300]
                if json_mode:
                    # Some servers reject the unknown response_format field — drop it and retry once.
                    log.warning("AI server rejected json mode (%s), retrying without it", resp.status_code)
                    json_mode = False
                    continue
                raise RuntimeError(f"AI HTTP {resp.status_code}: {body}")
            try:
                data = resp.json()
            except ValueError as exc:
                raise RuntimeError(f"AI returned non-JSON response: {resp.text[:200]}") from exc
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"AI returned no choices: {str(data)[:200]}")
            message = choices[0].get("message") or {}
            text = message.get("content") or choices[0].get("text") or ""
            if isinstance(text, list):   # some servers return content parts
                text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
            try:
                return extract_json(text)
            except ValueError as exc:
                last_error = str(exc)
                log.warning("AI reply was not valid JSON (%s), asking again", last_error)
                messages = messages[:2] + [
                    {"role": "assistant", "content": text[:2000]},
                    {"role": "user", "content": "Your previous reply was not a valid JSON object "
                                                f"({last_error}). Return ONLY the JSON object, nothing else."},
                ]
    raise RuntimeError(f"AI did not return valid JSON after 3 attempts: {last_error}")


def _openai_compatible() -> bool:
    return credentials.current()["ai_provider"].lower() in ("openai_compatible", "openai", "anythingllm")


async def _call_model(system: str, user: str, tool: dict[str, Any], max_tokens: int = 3000) -> dict[str, Any]:
    if _openai_compatible():
        return await _call_openai_compatible(system, user, tool, max_tokens)
    return await _call_claude(system, user, tool, max_tokens)


def ai_available() -> bool:
    cfg = credentials.current()
    if _openai_compatible():
        return bool(cfg["ai_base_url"] and cfg["ai_model"])
    return bool(cfg["ai_api_key"])


def ai_info() -> dict[str, Any]:
    cfg = credentials.current()
    openai_compatible = _openai_compatible()
    return {"configured": ai_available(), "provider": "openai_compatible" if openai_compatible else "anthropic",
            "model": cfg["ai_model"] or ("" if openai_compatible else "claude-sonnet-5"),
            "base_url": cfg["ai_base_url"] if openai_compatible else "",
            "source": credentials.source_of("ai_api_key")}


async def generate_from_article(brand: BrandContext, gen: dict[str, Any], title: str, body: str,
                                source_name: str = "") -> GeneratedPost:
    user = (f"Source: {source_name}\nOriginal title: {title}\n\nArticle:\n{body[:12000]}\n\n"
            "Create the carousel post using the create_post tool.")
    if not ai_available():
        return demo_post(title, body, gen)
    return _parse(await _call_model(build_system_prompt(brand, gen), user, POST_TOOL))


async def generate_from_topic(brand: BrandContext, gen: dict[str, Any], topic: str, notes: str = "") -> GeneratedPost:
    user = (f"Planned content-calendar topic: {topic}\nEditor notes: {notes or '-'}\n\n"
            "There is no source article: write evergreen, factual content only (no specific prices or dates). "
            "Relevance should reflect the topic fit. Use the create_post tool.")
    if not ai_available():
        return demo_post(topic, notes, gen)
    return _parse(await _call_model(build_system_prompt(brand, gen), user, POST_TOOL))


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
        badge="news", relevance=8, raw={"demo": True},
    )


def draft_context(d) -> str:
    return json.dumps({"hook": d.hook, "subtitle": d.subtitle, "caption": d.caption[:1500],
                       "original_title": d.original_title}, ensure_ascii=False)
