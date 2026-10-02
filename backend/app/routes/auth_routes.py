"""Login endpoints for the internal (no-Supabase) mode."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from ..config import get_settings
from ..security import create_token, password_matches

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str
    password: str


@router.get("/mode")
def mode():
    """Tells the dashboard which login form to show."""
    s = get_settings()
    return {"mode": s.auth_mode}


# Brute-force protection: at most 8 failed attempts per address in 15 minutes
_FAILED: dict[str, deque] = defaultdict(deque)
MAX_FAILED, WINDOW = 8, 15 * 60


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


@router.post("/login")
def login(body: LoginBody, request: Request):
    s = get_settings()
    if s.auth_mode != "internal":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "الدخول الداخلي غير مفعّل في الخادم")
    ip, now = _client_ip(request), time.time()
    attempts = _FAILED[ip]
    while attempts and now - attempts[0] > WINDOW:
        attempts.popleft()
    if len(attempts) >= MAX_FAILED:
        wait = int((WINDOW - (now - attempts[0])) // 60) + 1
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"محاولات دخول كثيرة — حاول مرة أخرى بعد {wait} دقيقة")
    if body.email.strip().lower() != s.admin_email.strip().lower() or not password_matches(body.password):
        attempts.append(now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "البريد أو كلمة المرور غير صحيحة")
    attempts.clear()
    return {"token": create_token(s.admin_email.strip().lower()), "email": s.admin_email.strip().lower()}
