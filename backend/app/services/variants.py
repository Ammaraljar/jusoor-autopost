"""One article → one post per platform.

Each platform gets its own text (length, tone, hashtags) and its own image set, sized to what
performs best there (the user can pick other slides):

* instagram 2-5 · facebook 2-4 · linkedin 3-5 · x 1 · threads 1-3 · tiktok 3-10

The texts come from the AI in a single call; if that fails, they are derived from the main
caption so publishing never blocks.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from . import generator

log = logging.getLogger(__name__)

PLATFORM_SPECS: dict[str, dict[str, Any]] = {
    "instagram": {"label": "Instagram", "format": "carousel", "limit": 2200, "tags": (5, 10),
                  "images": {"best": (2, 5), "max": 10, "default": 5},
                  "guide": "Carousel caption: strong first line, short paragraphs with line breaks, 1-3 emojis, "
                           "a clear call to action, then 5-10 relevant hashtags at the end."},
    "facebook": {"label": "Facebook", "format": "carousel", "limit": 1500, "tags": (0, 3),
                 "images": {"best": (2, 4), "max": 20, "default": 4},
                 "guide": "Photo post: conversational, 3-5 short paragraphs telling the story, a question "
                          "to invite comments, a call to action, at most 3 hashtags."},
    "linkedin": {"label": "LinkedIn", "format": "carousel", "limit": 2500, "tags": (3, 5),
                 "images": {"best": (3, 5), "max": 9, "default": 5},
                 "guide": "Multi-image post for professionals: an insight-led opening line, the business or "
                          "industry angle of the brand's field (market, trends, what it means for customers), 3-5 short paragraphs, no slang, "
                          "at most 1 emoji, 3-5 professional hashtags at the end."},
    "x": {"label": "X", "format": "single", "limit": 270, "tags": (1, 2),
          "images": {"best": (1, 1), "max": 4, "default": 1},
          "guide": "One-image post: ONE punchy sentence with the key fact plus 1-2 hashtags. "
                   "The WHOLE text must be under 270 characters."},
    "threads": {"label": "Threads", "format": "single", "limit": 480, "tags": (0, 2),
                "images": {"best": (1, 3), "max": 10, "default": 1},
                "guide": "Short post: casual and warm, 2-3 short lines, under 480 characters, 0-2 hashtags."},
    "tiktok": {"label": "TikTok", "format": "carousel", "limit": 2000, "tags": (3, 6),
               "images": {"best": (3, 10), "max": 35, "default": 10},
               "guide": "Photo-carousel caption: a catchy hook, 1-2 short lines, 3-6 trending hashtags of the brand's field."},
}
PLATFORMS = list(PLATFORM_SPECS)

VARIANTS_TOOL = {
    "name": "platform_posts",
    "description": "Write the post text for each social platform.",
    "input_schema": {
        "type": "object",
        "properties": {p: {"type": "string", "description": spec["guide"]} for p, spec in PLATFORM_SPECS.items()},
        "required": PLATFORMS,
    },
}


def _tags(hashtags: str, n: int) -> str:
    return " ".join([t for t in (hashtags or "").split() if t.startswith("#")][:n])


def _trim(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    cut = cut[: max(cut.rfind(" "), limit // 2)]
    return cut.rstrip(" ,.،:") + "…"


def _credit_line(draft, credit: bool) -> str:
    if not (credit and draft.origin == "source" and draft.source_name):
        return ""
    label = {"ar": "المصدر", "en": "Source", "fr": "Source"}.get(draft.language, "Source")
    return f"{label}: {draft.source_name}"


def fallback_texts(draft) -> dict[str, str]:
    """Platform texts derived from the main caption (no AI)."""
    caption = (draft.caption or "").strip()
    first_para = caption.split("\n\n")[0] if caption else draft.hook
    return {
        "instagram": "\n\n".join(p for p in [caption, _tags(draft.hashtags, 10)] if p),
        "facebook": "\n\n".join(p for p in [caption, _tags(draft.hashtags, 3)] if p),
        "linkedin": "\n\n".join(p for p in [draft.hook, caption, _tags(draft.hashtags, 4)] if p),
        "x": f"{draft.hook} {_tags(draft.hashtags, 2)}".strip(),
        "threads": "\n\n".join(p for p in [draft.hook, first_para] if p),
        "tiktok": "\n\n".join(p for p in [draft.hook, _tags(draft.hashtags, 6)] if p),
    }


def _kinds(draft) -> list[str]:
    return [s.kind for s in sorted(draft.slides, key=lambda s: s.position)] if getattr(draft, "slides", None) else []


def default_slides(platform: str, kinds: list[str]) -> list[int]:
    """The best-performing number of images for the platform: cover first, the CTA slide last."""
    total = len(kinds)
    if not total:
        return []
    n = min(PLATFORM_SPECS[platform]["images"]["default"], total)
    if n >= total:
        return list(range(total))
    cover = [i for i, k in enumerate(kinds) if k == "cover"][:1] or [0]
    content = [i for i, k in enumerate(kinds) if k == "content"]
    cta = [i for i, k in enumerate(kinds) if k == "cta"][:1]
    if n == 1:
        return cover
    if n == 2:
        return cover + (content[:1] or cta)
    return sorted(set(cover + content[: n - 1 - len(cta)] + cta))


def clean_slides(platform: str, wanted: list[int] | None, total: int) -> list[int]:
    """Valid positions within the platform's maximum, in slide order."""
    cap = PLATFORM_SPECS[platform]["images"]["max"]
    return sorted({i for i in (wanted or []) if 0 <= i < total})[:cap]


def finalize(draft, texts: dict[str, str], credit: bool = True,
             previous: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Build the stored variants: text within the platform limit (credit included), and images."""
    total = len(draft.slides) if getattr(draft, "slides", None) else 0
    fallback = fallback_texts(draft)
    credit_line = _credit_line(draft, credit)
    out: dict[str, dict[str, Any]] = {}
    for platform, spec in PLATFORM_SPECS.items():
        text = (texts.get(platform) or "").strip() or fallback[platform]
        text = re.sub(r"\n{3,}", "\n\n", text)
        if credit_line and credit_line not in text:
            room = spec["limit"] - len(credit_line) - 2
            text = f"{_trim(text, room)}\n{credit_line}" if platform == "x" else f"{_trim(text, room)}\n\n{credit_line}"
        text = _trim(text, spec["limit"])
        prev = (previous or {}).get(platform) or {}
        slides = clean_slides(platform, prev.get("slides"), total) if prev.get("custom_slides") else []
        custom = bool(slides)
        slides = slides or default_slides(platform, _kinds(draft))
        out[platform] = {"text": text, "format": "carousel" if len(slides) > 1 else "single", "slides": slides,
                         "custom_slides": custom, "limit": spec["limit"], "label": spec["label"],
                         "images": spec["images"]}
    return out


async def generate_texts(brand: generator.BrandContext, gen: dict[str, Any], draft) -> dict[str, str]:
    """One AI call → a text per platform. Falls back to derived texts on any failure."""
    if not generator.ai_available():
        return fallback_texts(draft)
    slides = "\n".join(f"- {s.heading}: {s.body}" for s in sorted(draft.slides, key=lambda s: s.position)
                       if s.kind == "content")
    user = (f"The same news must be published on several platforms. Base post:\n"
            f"Headline: {draft.hook}\nSubtitle: {draft.subtitle}\nKey points:\n{slides}\n"
            f"Main caption:\n{draft.caption}\nHashtags: {draft.hashtags}\nCall to action: {draft.cta}\n\n"
            "Write a separate text for each platform, adapted to how people read there (length, tone, "
            "hashtags) — not copies of each other. Same language as the base post, same facts, no new claims. "
            "Do not add a source line (it is added automatically). Use the platform_posts tool.")
    try:
        data = await generator._call_model(generator.build_system_prompt(brand, gen), user, VARIANTS_TOOL,
                                           max_tokens=3500)
        texts = {p: generator._text(data.get(p)) for p in PLATFORMS}
        if sum(1 for t in texts.values() if t) < 3:
            raise ValueError("too few platform texts")
        return texts
    except Exception as exc:  # noqa: BLE001 - never block a post over this
        log.warning("platform texts failed, using derived texts: %s", exc)
        return fallback_texts(draft)


def for_publish(draft, platform: str, credit: bool = True) -> tuple[str, list[int]]:
    """(text, slide positions) to publish on one platform."""
    variants = draft.variants or finalize(draft, fallback_texts(draft), credit)
    v = variants.get(platform)
    if not v:
        fb = finalize(draft, fallback_texts(draft), credit)
        v = fb.get(platform) or {"text": fb["instagram"]["text"], "slides": list(range(len(draft.slides)))}
    total = len(draft.slides)
    key = platform if platform in PLATFORM_SPECS else "instagram"
    chosen = clean_slides(key, v.get("slides"), total) if v.get("custom_slides") else []
    return v["text"], chosen or default_slides(key, _kinds(draft)) or [0]
