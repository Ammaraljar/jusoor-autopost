"""Server messages in the user's interface language.

Messages are written in Arabic in the code. When the dashboard asks for another language
(X-Lang header: en | ms | fr), every error and status text in the response is translated from
app/i18n/messages.json. "{}" in a template is a variable part (a number, a name, or another
message, which is translated in turn). Text that is not a known message — post content, names,
article titles — is never touched.
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

LANGS = ("ar", "en", "ms", "fr")
current_lang: ContextVar[str] = ContextVar("current_lang", default="ar")
_FILE = Path(__file__).resolve().parent.parent / "i18n" / "messages.json"
_ARABIC = re.compile("[؀-ۿ]")
# fields that hold content written by people or the AI — never translated
CONTENT_KEYS = {"hook", "caption", "heading", "body", "first_comment", "hashtags", "original_title", "original_body",
                "title", "topic", "notes", "name", "voice", "cta_text", "text", "variants", "caption_preview",
                "audience", "objective", "tags", "source_name", "handle", "website", "hook_highlight",
                "ar", "industry_label", "reply", "relevance_reason", "colors", "options"}


@lru_cache
def _catalog() -> list[tuple[re.Pattern, dict[str, str], int]]:
    data: dict[str, dict[str, str]] = json.loads(_FILE.read_text(encoding="utf-8"))
    out = []
    # longer templates first, so the most specific message wins
    for ar in sorted(data, key=len, reverse=True):
        parts = [re.escape(p) for p in ar.split("{}")]
        holes = len(parts) - 1
        pattern = "".join(p + ("(.*?)" if i < holes - 1 else "(.*)") for i, p in enumerate(parts[:-1])) + parts[-1]
        out.append((re.compile(f"^{pattern}$", re.S), data[ar], holes))
    return out


def translate(text: str, lang: str | None = None, _depth: int = 0) -> str:
    lang = lang or current_lang.get()
    if lang == "ar" or lang not in LANGS or not isinstance(text, str) or not _ARABIC.search(text) or _depth > 3:
        return text
    for sep in ("؛ ", "\n"):                          # several messages joined together
        if sep in text:
            pieces = text.split(sep)
            done = [translate(p, lang, _depth + 1) for p in pieces]
            if done != pieces:
                return ("; " if sep == "؛ " else sep).join(done)
    for pattern, tr, holes in _catalog():
        m = pattern.match(text)
        if not m:
            continue
        target = tr.get(lang) or text
        values = [translate(v, lang, _depth + 1) for v in m.groups()]
        for v in values:
            target = target.replace("{}", v.replace("{}", "{ }"), 1)
        return target
    return text


def translate_tree(value: Any, lang: str | None = None, key: str | None = None) -> Any:
    """Translate the messages inside a JSON-ready structure (dicts, lists, strings)."""
    lang = lang or current_lang.get()
    if lang == "ar":
        return value
    if isinstance(value, str):
        return value if key in CONTENT_KEYS else translate(value, lang)
    if isinstance(value, dict):
        return {k: (v if k in CONTENT_KEYS else translate_tree(v, lang, k)) for k, v in value.items()}
    if isinstance(value, list):
        return [translate_tree(v, lang, key) for v in value]
    return value


def lang_from_headers(headers: list[tuple[bytes, bytes]]) -> str:
    for k, v in headers:
        if k.lower() == b"x-lang":
            lang = v.decode("latin-1").strip().lower()[:2]
            return lang if lang in LANGS else "ar"
    return "ar"


# ------------------------------------------------------------------ web layer
from starlette.responses import JSONResponse  # noqa: E402


class LocalizedJSONResponse(JSONResponse):
    """JSON response whose messages follow the interface language of the request."""

    def render(self, content: Any) -> bytes:
        return super().render(translate_tree(content))


class LangMiddleware:
    """Reads X-Lang (the dashboard's interface language) for the whole request."""

    def __init__(self, app):  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = current_lang.set(lang_from_headers(scope.get("headers") or []))
        try:
            return await self.app(scope, receive, send)
        finally:
            current_lang.reset(token)
