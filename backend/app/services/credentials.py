"""AI engines, API keys and publishing keys — editable from the dashboard.

Values live in the database (so nobody has to touch the hosting environment) and fall back to
environment variables. Secrets are write-only: the API reports whether a key is set, never
its value.

Engines (all OpenAI-compatible)
-------------------------------
mistral     Mistral AI (La Plateforme)
openrouter  OpenRouter — one key for many models, including free ones (openrouter/free, ":free")
groq        Groq — fast, with a free tier

Mode ``single`` uses the primary engine (and falls back to the other ready engines if it fails).
Mode ``ensemble`` asks every engine that has a key at the same time and lets a judge (the primary
engine) pick the best post.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import AppSetting, session_scope

SETTINGS_KEY = "credentials"
VERSION = "3.4-upload-fix"

# Each engine carries what its own environment needs: suggested models, the key's format,
# where to get the key, and request tweaks applied in generator._tune_payload().
ENGINES: dict[str, dict[str, Any]] = {
    "mistral": {
        "label": "Mistral", "kind": "openai", "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
        "models": [
            {"id": "mistral-small-latest", "note": "سريع واقتصادي — مناسب للمنشورات"},
            {"id": "mistral-medium-latest", "note": "جودة أعلى"},
            {"id": "mistral-large-latest", "note": "الأقوى — أبطأ"},
        ],
        "key_url": "https://console.mistral.ai/api-keys", "key_prefix": "", "key_placeholder": "مفتاح من 32 حرفًا",
        "free": "خطة Experiment مجانية بحدود استخدام",
    },
    "openrouter": {
        "label": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openrouter/free",
        "models": [
            {"id": "openrouter/free", "note": "يختار نموذجًا مجانيًا يدعم JSON تلقائيًا"},
        ],
        "key_url": "https://openrouter.ai/keys", "key_prefix": "sk-or-", "key_placeholder": "sk-or-v1-…",
        "free": "مجاني بحد يومي للطلبات — أي نموذج ينتهي بـ :free",
    },
    "groq": {
        "label": "Groq", "kind": "openai", "base_url": "https://api.groq.com/openai/v1",
        "default_model": "openai/gpt-oss-120b",
        "models": [
            {"id": "openai/gpt-oss-120b", "note": "الأفضل للعربية على Groq"},
            {"id": "openai/gpt-oss-20b", "note": "أسرع وأخف"},
            {"id": "qwen/qwen3.8-27b", "note": "تجريبي (Preview)"},
        ],
        "key_url": "https://console.groq.com/keys", "key_prefix": "gsk_", "key_placeholder": "gsk_…",
        "free": "خطة مجانية بحدود في الدقيقة واليوم",
    },
}
ENGINE_ORDER = ("mistral", "groq", "openrouter")   # preference when no primary is chosen

# field -> (is_secret, env fallback attribute on Settings)
FIELDS: dict[str, tuple[bool, str]] = {
    "ai_mode": (False, "ai_mode"),
    "ai_primary": (False, "ai_primary"),
    "ai_ensemble": (False, "ai_ensemble"),
    "mistral_api_key": (True, "mistral_api_key"),
    "mistral_model": (False, "mistral_model"),
    "openrouter_api_key": (True, "openrouter_api_key"),
    "openrouter_model": (False, "openrouter_model"),
    "groq_api_key": (True, "groq_api_key"),
    "groq_model": (False, "groq_model"),
    "pexels_api_key": (True, "pexels_api_key"),
    "buffer_api_key": (True, "buffer_api_key"),
    "meta_access_token": (True, "meta_access_token"),
    "uploadpost_api_key": (True, "uploadpost_api_key"),
}

_cache: dict[str, str] | None = None


# --------------------------------------------------------------------- storage
def _raw_stored() -> dict[str, str]:
    global _cache
    if _cache is None:
        try:
            with session_scope() as db:
                row = db.get(AppSetting, SETTINGS_KEY)
                _cache = {k: str(v) for k, v in (row.value or {}).items()} if row else {}
        except Exception:  # noqa: BLE001 - never break a request because of the cache
            return {}
    return _cache


def _stored() -> dict[str, str]:
    """Stored values that still mean something (keys of removed engines are ignored)."""
    return {k: v for k, v in _raw_stored().items() if k in FIELDS and v}


def refresh() -> None:
    global _cache
    _cache = None


def _env_value(field: str) -> str:
    attr = FIELDS[field][1]
    return str(getattr(get_settings(), attr, "") or "") if attr else ""


def _names(value: str) -> list[str]:
    return [n.strip().lower() for n in (value or "").split(",") if n.strip().lower() in ENGINES]


def current() -> dict[str, str]:
    """Effective configuration: dashboard values win, environment variables are the fallback.

    Values that name removed engines (an old AI_PRIMARY=gemini, say) are ignored rather than
    breaking generation."""
    stored = _stored()
    out = {field: stored.get(field) or _env_value(field) for field in FIELDS}
    out["ai_mode"] = out["ai_mode"] if out["ai_mode"] in ("single", "ensemble") else "single"

    primary = (stored.get("ai_primary") or "").lower()
    if not _ready(primary, out):
        primary = (_env_value("ai_primary") or "").lower()
    out["ai_primary"] = primary if _ready(primary, out) else _default_primary(out)

    ensemble = _names(stored.get("ai_ensemble", "")) or _names(_env_value("ai_ensemble"))
    out["ai_ensemble"] = ",".join(ensemble or list(ENGINE_ORDER))
    return out


def _default_primary(values: dict[str, str]) -> str:
    for name in ENGINE_ORDER:
        if _ready(name, values):
            return name
    return ENGINE_ORDER[0]


def source_of(field: str) -> str:
    if field not in FIELDS:
        return "unset"
    if _stored().get(field):
        return "dashboard"
    return "environment" if _env_value(field) else "unset"


# --------------------------------------------------------------------- engines
def engine(name: str, values: dict[str, str] | None = None) -> dict[str, str]:
    v = values or current()
    meta = ENGINES[name]
    return {"name": name, "label": meta["label"], "kind": meta["kind"], "base_url": meta["base_url"],
            "api_key": v.get(f"{name}_api_key", ""),
            "model": v.get(f"{name}_model", "") or meta["default_model"]}


def _ready(name: str, values: dict[str, str]) -> bool:
    return name in ENGINES and bool(values.get(f"{name}_api_key"))


def ready_engines(values: dict[str, str] | None = None) -> list[str]:
    v = values or current()
    return [n for n in ENGINE_ORDER if _ready(n, v)]


def fallback_order(values: dict[str, str] | None = None) -> list[str]:
    """Primary first, then every other ready engine — used when an engine fails."""
    v = values or current()
    primary = v.get("ai_primary", "")
    rest = [n for n in ready_engines(v) if n != primary]
    return ([primary] if _ready(primary, v) else []) + rest


def ensemble_engines(values: dict[str, str] | None = None) -> list[str]:
    """Parallel generation uses every engine that has an API key — nothing else to configure."""
    return ready_engines(values)


def ai_warnings(values: dict[str, str] | None = None) -> list[str]:
    """Settings that cannot work — explained in plain Arabic."""
    v = values or current()
    out: list[str] = []
    if not ready_engines(v):
        out.append("لا يوجد محرّك ذكاء اصطناعي جاهز — أضف مفتاح Mistral أو OpenRouter أو Groq")
    if v.get("ai_mode") == "ensemble" and len(ensemble_engines(v)) == 1:
        out.append("وضع التوازي يحتاج مفتاحين على الأقل — يعمل حاليًا بمحرّك واحد")

    mistral_key = v.get("mistral_api_key", "")
    if mistral_key and re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                                    mistral_key):
        out.append("مفتاح Mistral يبدو كمعرّف المفتاح (UUID) لا المفتاح السري نفسه — انسخ المفتاح الذي يظهر "
                   "مرة واحدة عند إنشائه من console.mistral.ai")
    or_key = v.get("openrouter_api_key", "")
    if or_key and not or_key.startswith("sk-or-"):
        out.append("مفاتيح OpenRouter تبدأ عادةً بـ sk-or- — تأكد من نسخ المفتاح كاملًا")
    groq_key = v.get("groq_api_key", "")
    if groq_key and not groq_key.startswith("gsk_"):
        out.append("مفاتيح Groq تبدأ عادةً بـ gsk_ — تأكد من نسخ المفتاح كاملًا")
    return out


# --------------------------------------------------------------------- API views
def public_view() -> dict[str, Any]:
    """Safe representation for the dashboard: secrets become a status, never a value."""
    values = current()
    out: dict[str, Any] = {}
    for field, (secret, _env) in FIELDS.items():
        if secret:
            out[field] = {"set": bool(values[field]), "source": source_of(field),
                          "hint": f"…{values[field][-4:]}" if values[field] else ""}
        else:
            out[field] = values[field]
    out["engines"] = {name: {"label": ENGINES[name]["label"], "ready": _ready(name, values),
                             "model": engine(name, values)["model"],
                             "default_model": ENGINES[name]["default_model"],
                             "models": ENGINES[name]["models"], "key_url": ENGINES[name]["key_url"],
                             "key_prefix": ENGINES[name]["key_prefix"],
                             "key_placeholder": ENGINES[name]["key_placeholder"],
                             "free": ENGINES[name]["free"]}
                      for name in ENGINE_ORDER}
    out["ready"] = ready_engines(values)
    out["version"] = VERSION
    out["warnings"] = ai_warnings(values)
    return out


def save(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    """Update stored credentials. For secrets: "" keeps the current value, None clears it.

    Fields of removed engines are dropped from the database on every save."""
    row = db.get(AppSetting, SETTINGS_KEY)
    data = dict(_stored())
    for field, (secret, _env) in FIELDS.items():
        if field not in values:
            continue
        value = values[field]
        if value is None:
            data.pop(field, None)
            continue
        value = str(value).strip()
        if secret and value == "":
            continue                       # untouched password field
        if field == "ai_primary" and value not in ENGINES:
            continue
        if field == "ai_ensemble":
            value = ",".join(_names(value))
        if value == "":
            data.pop(field, None)
        else:
            data[field] = value
    if row:
        row.value = data
    else:
        db.add(AppSetting(key=SETTINGS_KEY, value=data))
    db.flush()
    global _cache
    _cache = dict(data)
    return public_view()
