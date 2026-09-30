"""Login endpoints for the internal (no-Supabase) mode."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
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


@router.post("/login")
def login(body: LoginBody):
    s = get_settings()
    if s.auth_mode != "internal":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "الدخول الداخلي غير مفعّل في الخادم")
    if body.email.strip().lower() != s.admin_email.strip().lower() or not password_matches(body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "البريد أو كلمة المرور غير صحيحة")
    return {"token": create_token(s.admin_email.strip().lower()), "email": s.admin_email.strip().lower()}
