"""Authentication: validates Supabase access tokens and applies an e-mail allow-list.

Every failure says exactly what is misconfigured, so a wrong environment variable
does not turn into a silent login loop.
"""
from __future__ import annotations

import logging
import time

import httpx
from fastapi import Depends, HTTPException, Request, status

from .config import get_settings

log = logging.getLogger(__name__)
_cache: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 60


def _config_error() -> str | None:
    """Server-side misconfiguration that makes any login impossible."""
    s = get_settings()
    if not s.supabase_base:
        return "SUPABASE_URL غير مضبوط في الخادم"
    kind = s.anon_key_kind
    if kind == "missing":
        return "SUPABASE_ANON_KEY غير مضبوط في الخادم"
    if kind == "secret_key_wrong":
        return ("SUPABASE_ANON_KEY يحتوي المفتاح السري (service_role / sb_secret) "
                "بدل مفتاح anon / publishable")
    return None


async def check_supabase_key() -> dict:
    """Live check of the SUPABASE_URL + SUPABASE_ANON_KEY pair (no user session needed)."""
    s = get_settings()
    problem = _config_error()
    if problem:
        return {"ok": False, "error": problem, "key_kind": s.anon_key_kind, "url": s.supabase_base}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{s.supabase_base}/auth/v1/settings",
                                    headers={"apikey": s.supabase_anon_key})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"تعذّر الوصول إلى Supabase: {exc}", "url": s.supabase_base}
    if resp.status_code == 200:
        return {"ok": True, "url": s.supabase_base, "key_kind": s.anon_key_kind}
    if resp.status_code in (401, 403):
        return {"ok": False, "status": resp.status_code, "url": s.supabase_base, "key_kind": s.anon_key_kind,
                "error": "المفتاح مرفوض من Supabase — SUPABASE_ANON_KEY خاطئ أو يخص مشروعًا آخر"}
    if resp.status_code == 404:
        return {"ok": False, "status": 404, "url": s.supabase_base,
                "error": "SUPABASE_URL لا يشير إلى مشروع Supabase صحيح"}
    return {"ok": False, "status": resp.status_code, "url": s.supabase_base,
            "error": f"رد غير متوقع من Supabase: {resp.text[:120]}"}


async def _verify_with_supabase(token: str) -> dict:
    now = time.time()
    hit = _cache.get(token)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{s.supabase_base}/auth/v1/user",
                                    headers={"Authorization": f"Bearer {token}", "apikey": s.supabase_anon_key})
    except Exception as exc:  # noqa: BLE001
        log.warning("supabase verification failed: %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"تعذّر الوصول إلى Supabase من الخادم: {exc}") from exc
    if resp.status_code == 200:
        user = resp.json()
        if len(_cache) > 500:
            _cache.clear()
        _cache[token] = (now, user)
        return user

    body = resp.text[:200]
    log.warning("supabase rejected the session: HTTP %s %s", resp.status_code, body)
    if resp.status_code == 404:
        detail = ("SUPABASE_URL في الخادم غير صحيح — يجب أن ينتهي عند .supabase.co "
                  "بدون /rest/v1 أو أي مسار آخر")
    elif "api key" in body.lower():
        detail = "SUPABASE_ANON_KEY في الخادم خاطئ أو يخص مشروعًا آخر"
    else:
        detail = "انتهت صلاحية الجلسة أو أنها تخص مشروع Supabase آخر — افحص /api/health في الخادم"
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail)


async def current_user(request: Request) -> dict:
    s = get_settings()
    if s.auth_disabled:
        return {"id": "local", "email": "local@dev"}
    problem = _config_error()
    if problem:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, problem)
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "مطلوب تسجيل الدخول")
    user = await _verify_with_supabase(header.split(" ", 1)[1].strip())
    allowed = s.allowed_email_list
    email = (user.get("email") or "").lower()
    if allowed and email not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"الحساب {email} غير مصرّح له — أضفه إلى ALLOWED_EMAILS في الخادم")
    return {"id": user.get("id"), "email": user.get("email")}


RequireUser = Depends(current_user)
