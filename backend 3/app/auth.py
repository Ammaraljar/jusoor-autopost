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
from .security import read_token

log = logging.getLogger(__name__)
_cache: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 60


def _config_error() -> str | None:
    """Server-side misconfiguration that makes any login impossible."""
    s = get_settings()
    if s.auth_mode == "internal":
        return None
    if s.auth_mode == "unconfigured":
        return ("لا توجد طريقة دخول مضبوطة — أضف ADMIN_EMAIL و ADMIN_PASSWORD في الخادم")
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
    if s.auth_mode != "supabase":
        return {"ok": True, "mode": s.auth_mode}
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


class Principal(dict):
    """The signed-in person: {id, email, name, role, org_id, is_superadmin}. A dict, so old code keeps working."""

    @property
    def role(self) -> str:
        return self.get("role", "reviewer")

    @property
    def org_id(self) -> int | None:
        return self.get("org_id")


ROLE_RANK = {"reviewer": 1, "editor": 2, "owner": 3}


def _acting_org(request: Request, user_org: int | None, superadmin: bool) -> int | None:
    """A super-admin can open any company with the X-Org-Id header; everyone else stays in their own."""
    wanted = request.headers.get("x-org-id")
    if superadmin and wanted and wanted.isdigit():
        return int(wanted)
    return user_org


def _principal_from_user(request: Request, user) -> Principal:  # noqa: ANN001
    from .db import Organization, session_scope
    org_id = _acting_org(request, user.org_id, user.is_superadmin)
    if org_id is not None and not user.is_superadmin:
        with session_scope() as db:
            org = db.get(Organization, org_id)
            if org is None or org.status != "active":
                raise HTTPException(status.HTTP_403_FORBIDDEN, "حساب الشركة موقوف — تواصل مع إدارة المنصة")
    return Principal(id=user.id, email=user.email, name=user.name,
                     role="owner" if user.is_superadmin else user.role,
                     org_id=org_id, is_superadmin=user.is_superadmin, home_org_id=user.org_id)


def _default_org() -> int | None:
    from sqlalchemy import select

    from .db import Organization, session_scope
    with session_scope() as db:
        return db.scalar(select(Organization.id).order_by(Organization.id))


async def current_user(request: Request) -> Principal:
    from sqlalchemy import select

    from .db import User, current_org, session_scope
    s = get_settings()
    if s.auth_disabled:
        org_id = _acting_org(request, _default_org(), True)
        current_org.set(org_id)
        return Principal(id=0, email="local@dev", name="Local", role="owner", org_id=org_id, is_superadmin=True)
    problem = _config_error()
    if problem:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, problem)
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "مطلوب تسجيل الدخول")
    token = header.split(" ", 1)[1].strip()

    if s.auth_mode == "internal":
        payload = read_token(token)
        if not payload:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "انتهت صلاحية الجلسة، سجّل الدخول من جديد")
        with session_scope() as db:
            q = select(User).where(User.id == payload["uid"]) if payload.get("uid") else \
                select(User).where(User.email == (payload.get("email") or "").lower())
            user = db.scalar(q)
            if user is None or not user.active:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "الحساب غير موجود أو موقوف")
            db.expunge(user)
        who = _principal_from_user(request, user)
        current_org.set(who.org_id)
        return who

    supa = await _verify_with_supabase(token)
    email = (supa.get("email") or "").lower()
    with session_scope() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            db.expunge(user)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"الحساب {email} غير مسجّل في أي شركة")
    who = _principal_from_user(request, user)
    current_org.set(who.org_id)
    return who


RequireUser = Depends(current_user)


def require_role(minimum: str):
    """Dependency: the signed-in person needs at least this role in the company."""
    async def check(who: Principal = Depends(current_user)) -> Principal:
        if not who.get("is_superadmin") and ROLE_RANK.get(who.role, 0) < ROLE_RANK[minimum]:
            labels = {"owner": "مالك الشركة", "editor": "محرر", "reviewer": "مراجع"}
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"هذا الإجراء يحتاج صلاحية {labels[minimum]}")
        return who
    return check


async def require_superadmin(who: Principal = Depends(current_user)) -> Principal:
    if not who.get("is_superadmin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "هذه الصفحة لإدارة المنصة فقط")
    return who


RequireEditor = Depends(require_role("editor"))
RequireOwner = Depends(require_role("owner"))
RequireSuperadmin = Depends(require_superadmin)


_REVIEWER_WRITES = ("/approve", "/reject", "/restore")


async def write_guard(request: Request, who: Principal = Depends(current_user)) -> Principal:
    """Reviewers read everything and decide (approve / reject), but cannot change content."""
    if request.method in ("GET", "HEAD", "OPTIONS") or who.get("is_superadmin"):
        return who
    if who.role == "reviewer":
        path = request.url.path
        allowed = path.endswith(_REVIEWER_WRITES)
        if path == "/api/drafts/bulk":
            try:
                allowed = (await request.json()).get("action") in ("approve", "reject", "restore")
            except Exception:  # noqa: BLE001
                allowed = False
        if not allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "صلاحية المراجع: الاعتماد والرفض فقط")
    return who


RequireWriter = Depends(write_guard)
