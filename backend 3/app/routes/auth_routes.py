"""Login endpoints for the internal (no-Supabase) mode."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from pydantic import Field
from sqlalchemy import select

from ..auth import Principal, current_user
from ..config import get_settings
from ..db import Organization, User, session_scope, utcnow
from ..security import create_user_token, hash_password, password_matches, verify_password
from fastapi import Depends

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str
    password: str


@router.get("/mode")
def mode():
    """Tells the dashboard which login form to show."""
    s = get_settings()
    return {"mode": s.auth_mode, "allow_signup": bool(s.allow_signup)}


@router.get("/industries")
def industry_list():
    """Public list for the sign-up form."""
    from ..services import industries
    return industries.options()


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
    email = body.email.strip().lower()
    with session_scope() as db:
        user = db.scalar(select(User).where(User.email == email))
        env_admin = email == (s.admin_email or "").strip().lower() and password_matches(body.password)
        if env_admin and user is None:          # the platform owner from the server variables
            org_id = db.scalar(select(Organization.id).order_by(Organization.id))
            user = User(org_id=org_id, email=email, name="Admin", role="owner", is_superadmin=True,
                        password_hash=hash_password(body.password))
            db.add(user)
            db.flush()
        ok = user is not None and user.active and (env_admin or verify_password(body.password, user.password_hash))
        if not ok:
            attempts.append(now)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "البريد أو كلمة المرور غير صحيحة")
        if user.org_id and not user.is_superadmin:
            org = db.get(Organization, user.org_id)
            if org is None or org.status != "active":
                raise HTTPException(status.HTTP_403_FORBIDDEN, "حساب الشركة موقوف — تواصل مع إدارة المنصة")
        user.last_login_at = utcnow()
        uid, uemail = user.id, user.email
    attempts.clear()
    return {"token": create_user_token(uid, uemail), "email": uemail}


class SignupBody(BaseModel):
    company: str = Field(min_length=2, max_length=160)
    industry: str = "general"
    language: str = "ar"
    dialect: str | None = None
    name: str = ""
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=200)


@router.post("/signup")
def signup(body: SignupBody, request: Request):
    """Self-service: a new company with its owner account (when the platform allows sign-ups)."""
    from ..services import tenancy
    s = get_settings()
    if not s.allow_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "التسجيل الذاتي متوقف — تواصل مع إدارة المنصة")
    ip, now = _client_ip(request), time.time()
    attempts = _FAILED[f"signup:{ip}"]
    while attempts and now - attempts[0] > WINDOW:
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "محاولات تسجيل كثيرة — حاول لاحقًا")
    attempts.append(now)
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "بريد إلكتروني غير صالح")
    with session_scope() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(409, "هذا البريد مسجّل مسبقًا — سجّل الدخول")
        org, owner = tenancy.create_org(db, body.company, body.industry, body.language, body.dialect,
                                        email, body.password, body.name)
        db.flush()
        uid = owner.id
    return {"token": create_user_token(uid, email), "email": email}


class PasswordBody(BaseModel):
    current: str
    new: str = Field(min_length=8, max_length=200)


@router.post("/password")
def change_password(body: PasswordBody, who: Principal = Depends(current_user)):
    with session_scope() as db:
        user = db.get(User, who["id"]) if who["id"] else None
        if user is None or not verify_password(body.current, user.password_hash):
            raise HTTPException(400, "كلمة المرور الحالية غير صحيحة")
        user.password_hash = hash_password(body.new)
    return {"ok": True}
