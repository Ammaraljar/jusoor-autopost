"""API keys and AI provider settings, editable from the dashboard.

Values live in the database (so the user never touches the hosting environment again) and
fall back to environment variables. Secrets are write-only: the API reports whether a key is
set, never its value.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import AppSetting, session_scope

SETTINGS_KEY = "credentials"

# field -> (is_secret, env fallback attribute on Settings)
FIELDS: dict[str, tuple[bool, str]] = {
    "ai_provider": (False, "ai_provider"),
    "ai_base_url": (False, "ai_base_url"),
    "ai_model": (False, "ai_model_name"),
    "ai_api_key": (True, "ai_key"),
    "pexels_api_key": (True, "pexels_api_key"),
    "buffer_api_key": (True, "buffer_api_key"),
    "meta_access_token": (True, "meta_access_token"),
    "uploadpost_api_key": (True, "uploadpost_api_key"),
}

_cache: dict[str, str] | None = None


def _stored() -> dict[str, str]:
    """Values saved from the dashboard (cached; the cache is refreshed on save)."""
    global _cache
    if _cache is None:
        try:
            with session_scope() as db:
                row = db.get(AppSetting, SETTINGS_KEY)
                _cache = {k: str(v) for k, v in (row.value or {}).items() if k in FIELDS} if row else {}
        except Exception:  # noqa: BLE001 - never break a request because of the cache
            return {}
    return _cache


def refresh() -> None:
    global _cache
    _cache = None


def current() -> dict[str, str]:
    """Effective configuration: dashboard values win, environment variables are the fallback."""
    s = get_settings()
    stored = _stored()
    out: dict[str, str] = {}
    for field, (_secret, env_attr) in FIELDS.items():
        out[field] = stored.get(field) or (getattr(s, env_attr, "") or "")
    return out


def source_of(field: str) -> str:
    if _stored().get(field):
        return "dashboard"
    s = get_settings()
    return "environment" if getattr(s, FIELDS[field][1], "") else "unset"


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
    return out


def save(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    """Update stored credentials.

    For secrets: "" keeps the current value, None clears the dashboard override.
    """
    row = db.get(AppSetting, SETTINGS_KEY)
    data = dict(row.value) if row and isinstance(row.value, dict) else {}
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
    _cache = {k: v for k, v in data.items() if k in FIELDS}
    return public_view()
