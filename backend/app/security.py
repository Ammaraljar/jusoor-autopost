"""Session tokens for the internal (no-Supabase) login — signed with HMAC, no dependencies."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from .config import get_settings


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    key = get_settings().token_secret.encode()
    return _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())


def create_token(email: str, hours: int | None = None) -> str:
    s = get_settings()
    body = {"email": email, "exp": int(time.time()) + (hours or s.session_hours) * 3600}
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def read_token(token: str) -> dict[str, Any] | None:
    """Returns the payload when the token is valid and unexpired, otherwise None."""
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        body = json.loads(_unb64(payload))
    except Exception:  # noqa: BLE001
        return None
    if int(body.get("exp", 0)) < time.time():
        return None
    return body


def password_matches(given: str) -> bool:
    expected = get_settings().admin_password
    return bool(expected) and secrets.compare_digest(given.encode(), expected.encode())
