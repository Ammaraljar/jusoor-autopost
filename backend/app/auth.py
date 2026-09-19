"""Authentication: validates Supabase access tokens and applies an e-mail allow-list."""
from __future__ import annotations

import time

import httpx
from fastapi import Depends, HTTPException, Request, status

from .config import get_settings

_cache: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 60


async def _verify_with_supabase(token: str) -> dict:
    now = time.time()
    hit = _cache.get(token)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    s = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{s.supabase_url}/auth/v1/user",
                                headers={"Authorization": f"Bearer {token}", "apikey": s.supabase_anon_key})
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "جلسة غير صالحة، سجّل الدخول من جديد")
    user = resp.json()
    if len(_cache) > 500:
        _cache.clear()
    _cache[token] = (now, user)
    return user


async def current_user(request: Request) -> dict:
    s = get_settings()
    if s.auth_disabled:
        return {"id": "local", "email": "local@dev"}
    if not s.supabase_url:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "SUPABASE_URL غير مُعدّ")
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "مطلوب تسجيل الدخول")
    user = await _verify_with_supabase(header.split(" ", 1)[1].strip())
    allowed = s.allowed_email_list
    if allowed and (user.get("email") or "").lower() not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "هذا الحساب غير مصرّح له باستخدام اللوحة")
    return {"id": user.get("id"), "email": user.get("email")}


RequireUser = Depends(current_user)
