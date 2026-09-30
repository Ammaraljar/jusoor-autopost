"""AI engines, API keys and publishing keys — editable from the dashboard.

Values live in the database (so nobody has to touch the hosting environment) and fall back to
environment variables. Secrets are write-only: the API reports whether a key is set, never
its value.

Engines
-------
claude    Anthropic API (structured output through tool use)
gemini    Google AI Studio, through its OpenAI-compatible endpoint
deepseek  DeepSeek, OpenAI-compatible
custom    Any OpenAI-compatible server (AnythingLLM, Ollama, LM Studio, vLLM…)

Mode ``single`` uses the primary engine. Mode ``ensemble`` asks every selected engine at the
same time and lets a judge (the primary engine) pick the best post.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import AppSetting, session_scope

SETTINGS_KEY = "credentials"

ENGINES: dict[str, dict[str, str]] = {
    "claude": {"label": "Claude", "kind": "anthropic", "base_url": "", "default_model": "claude-sonnet-5",
               "key_hint": "console.anthropic.com → sk-ant-…"},
    "gemini": {"label": "Gemini", "kind": "openai",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "default_model": "gemini-3.8-flash", "key_hint": "aistudio.google.com → Get API key"},
    "deepseek": {"label": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com",
                 "default_model": "deepseek-flash", "key_hint": "platform.deepseek.com → API keys"},
    "custom": {"label": "AnythingLLM / خادم مخصص", "kind": "openai", "base_url": "", "default_model": "",
               "key_hint": "AnythingLLM API key"},
}

# field -> (is_secret, env fallback attribute on Settings)
FIELDS: dict[str, tuple[bool, str]] = {
    "ai_mode": (False, "ai_mode"),
    "ai_primary": (False, ""),
    "ai_ensemble": (False, "ai_ensemble"),
    "claude_api_key": (True, "anthropic_api_key"),
    "claude_model": (False, "anthropic_model"),
    "gemini_api_key": (True, "gemini_api_key"),
    "gemini_model": (False, "gemini_model"),
    "deepseek_api_key": (True, "deepseek_api_key"),
    "deepseek_model": (False, "deepseek_model"),
    "custom_base_url": (False, "ai_base_url"),
    "custom_api_key": (True, "ai_api_key"),
    "custom_model": (False, "ai_model"),
    "pexels_api_key": (True, "pexels_api_key"),
    "buffer_api_key": (True, "buffer_api_key"),
    "meta_access_token": (True, "meta_access_token"),
    "uploadpost_api_key": (True, "uploadpost_api_key"),
}

# Names used by the first version of the dashboard (kept so old data and requests still work)
LEGACY_FIELDS = ("ai_provider", "ai_base_url", "ai_model", "ai_api_key")

_cache: dict[str, str] | None = None
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal")


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


def _is_local(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    return host in _LOCAL_HOSTS or host.startswith(("192.168.", "10.")) or host.endswith(".local")


def _stored() -> dict[str, str]:
    """Stored values in the current format, with the first version's names translated."""
    raw = dict(_raw_stored())
    provider = raw.get("ai_provider", "").lower()
    if provider:
        target = "claude" if provider == "anthropic" else "custom"
        # An old setting that points at the user's own computer can never work from the server,
        # and an AI_PRIMARY variable is a deliberate choice: neither is overridden by old data.
        unusable = target == "custom" and _is_local(raw.get("ai_base_url", ""))
        if not unusable and not get_settings().ai_primary:
            raw.setdefault("ai_primary", target)
        if raw.get("ai_api_key"):
            raw.setdefault(f"{target}_api_key", raw["ai_api_key"])
        if raw.get("ai_model"):
            raw.setdefault(f"{target}_model", raw["ai_model"])
        if raw.get("ai_base_url") and target == "custom":
            raw.setdefault("custom_base_url", raw["ai_base_url"])
    return {k: v for k, v in raw.items() if k in FIELDS and v}


def refresh() -> None:
    global _cache
    _cache = None


def _env_value(field: str) -> str:
    s = get_settings()
    if field == "claude_api_key":
        return s.anthropic_api_key or ("" if s.is_openai_compatible else s.ai_api_key)
    if field == "custom_api_key":
        return s.ai_api_key if s.is_openai_compatible else ""
    if field == "custom_model":
        return s.ai_model if s.is_openai_compatible else ""
    if field == "ai_primary":
        return s.ai_primary if s.ai_primary in ENGINES else ""
    attr = FIELDS[field][1]
    return str(getattr(s, attr, "") or "") if attr else ""


def current() -> dict[str, str]:
    """Effective configuration: dashboard values win, environment variables are the fallback."""
    stored = _stored()
    out = {field: stored.get(field) or _env_value(field) for field in FIELDS}
    if not out["ai_primary"]:
        out["ai_primary"] = _default_primary(out)
    out["ai_mode"] = out["ai_mode"] if out["ai_mode"] in ("single", "ensemble") else "single"
    return out


def _default_primary(values: dict[str, str]) -> str:
    if get_settings().is_openai_compatible and values.get("custom_base_url"):
        return "custom"
    for name in ("claude", "gemini", "deepseek", "custom"):
        if _ready(name, values):
            return name
    return "claude"


def source_of(field: str) -> str:
    if _stored().get(field):
        return "dashboard"
    return "environment" if _env_value(field) else "unset"


# --------------------------------------------------------------------- engines
def engine(name: str, values: dict[str, str] | None = None) -> dict[str, str]:
    v = values or current()
    meta = ENGINES[name]
    base_url = v.get("custom_base_url", "") if name == "custom" else meta["base_url"]
    return {"name": name, "label": meta["label"], "kind": meta["kind"], "base_url": base_url,
            "api_key": v.get(f"{name}_api_key", ""),
            "model": v.get(f"{name}_model", "") or meta["default_model"]}


def _ready(name: str, values: dict[str, str]) -> bool:
    if name == "custom":
        return bool(values.get("custom_base_url") and (values.get("custom_model") or ""))
    return bool(values.get(f"{name}_api_key"))


def ready_engines(values: dict[str, str] | None = None) -> list[str]:
    v = values or current()
    return [n for n in ENGINES if _ready(n, v)]


def ensemble_engines(values: dict[str, str] | None = None) -> list[str]:
    """Engines that take part in parallel generation (only the ready ones)."""
    v = values or current()
    wanted = [n.strip() for n in (v.get("ai_ensemble") or "").split(",") if n.strip() in ENGINES]
    return [n for n in wanted if _ready(n, v)]


def ai_warnings(values: dict[str, str] | None = None) -> list[str]:
    """Settings that cannot work — explained in plain Arabic."""
    v = values or current()
    out: list[str] = []
    primary = v.get("ai_primary") or "claude"
    if not ready_engines(v):
        out.append("لا يوجد محرّك ذكاء اصطناعي جاهز — أضف مفتاحًا واحدًا على الأقل")
    elif not _ready(primary, v):
        out.append(f"المحرّك الأساسي {ENGINES[primary]['label']} بلا مفتاح — اختر محرّكًا أساسيًا له مفتاح")
    if v.get("ai_mode") == "ensemble" and len(ensemble_engines(v)) < 2:
        out.append("وضع التوازي يحتاج محرّكين جاهزين على الأقل — سيعمل حاليًا بمحرّك واحد")

    url = (v.get("custom_base_url") or "").strip()
    custom_used = primary == "custom" or "custom" in (v.get("ai_ensemble") or "")
    if url and custom_used:
        host = (urlparse(url).hostname or "").lower()
        if host in _LOCAL_HOSTS or host.startswith(("192.168.", "10.")) or host.endswith(".local"):
            out.append(f"الرابط {url} يشير إلى جهازك المحلي، والخادم على الإنترنت لا يستطيع الوصول إليه. "
                       "استخدم رابطًا عامًا يبدأ بـ https:// أو محرّكًا آخر")
        elif url.rstrip("/").endswith("/api/v1"):
            out.append("رابط AnythingLLM المتوافق مع OpenAI ينتهي عادةً بـ /api/v1/openai")
        model = (v.get("custom_model") or "").lower()
        if not model:
            out.append("اسم نموذج الخادم المخصص فارغ — في AnythingLLM يكون اسم مساحة العمل")
        elif model.startswith("claude-"):
            out.append(f"النموذج «{v.get('custom_model')}» اسم نموذج Claude، أما AnythingLLM فيحتاج اسم مساحة العمل")

    gemini_key = v.get("gemini_api_key", "")
    if gemini_key and not gemini_key.startswith("AIza"):
        out.append("مفاتيح Google AI Studio تبدأ عادةً بـ AIza — إن فشل الاختبار فأنشئ مفتاحًا جديدًا من "
                   "aistudio.google.com")
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
    out["engines"] = {name: {"label": meta["label"], "ready": _ready(name, values),
                             "default_model": meta["default_model"], "key_hint": meta["key_hint"]}
                      for name, meta in ENGINES.items()}
    out["warnings"] = ai_warnings(values)
    return out


def _translate_legacy(values: dict[str, Any]) -> dict[str, Any]:
    """Accept the first version's field names in requests."""
    if not any(k in values for k in LEGACY_FIELDS):
        return values
    values = dict(values)
    provider = str(values.pop("ai_provider", "") or "").lower()
    target = "claude" if provider == "anthropic" else ("custom" if provider else current()["ai_primary"])
    if provider:
        values.setdefault("ai_primary", target)
    if "ai_base_url" in values:
        values.setdefault("custom_base_url", values.pop("ai_base_url"))
    if "ai_model" in values:
        values.setdefault(f"{target}_model", values.pop("ai_model"))
    if "ai_api_key" in values:
        values.setdefault(f"{target}_api_key", values.pop("ai_api_key"))
    return values


def save(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    """Update stored credentials. For secrets: "" keeps the current value, None clears it."""
    values = _translate_legacy(values)
    row = db.get(AppSetting, SETTINGS_KEY)
    data = {k: v for k, v in _stored().items()}          # also migrates old names on first save
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
