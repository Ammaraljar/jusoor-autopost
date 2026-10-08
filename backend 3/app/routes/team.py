"""Company profile and staff (owner only), and the platform admin area (super-admin only)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import Principal, RequireOwner, RequireSuperadmin, RequireUser, current_user
from ..db import Organization, User, current_org, get_db, use_org
from ..security import hash_password
from ..services import app_settings, credentials, industries, tenancy

router = APIRouter(prefix="/api", tags=["team"])


# ------------------------------------------------------------------ company profile
@router.get("/org", dependencies=[RequireUser])
def my_org(db: Session = Depends(get_db)):
    org = db.get(Organization, current_org.get())
    if org is None:
        raise HTTPException(404, "لا توجد شركة")
    return {**tenancy.org_summary(db, org), "industries": industries.options()}


class OrgPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=160)
    industry: str | None = None
    language: str | None = Field(None, pattern="^(ar|en|ms|fr)$")
    dialect: str | None = None
    apply_industry_defaults: bool = False


@router.patch("/org", dependencies=[RequireOwner])
def update_org(body: OrgPatch, db: Session = Depends(get_db)):
    org = db.get(Organization, current_org.get())
    if org is None:
        raise HTTPException(404, "لا توجد شركة")
    if body.industry and body.industry not in industries.INDUSTRIES:
        raise HTTPException(400, "مجال غير معروف")
    for k in ("name", "industry", "language", "dialect"):
        v = getattr(body, k)
        if v is not None:
            setattr(org, k, v or None if k == "dialect" else v)
    gen_patch: dict[str, Any] = {"industry": org.industry, "language": org.language}
    if org.dialect:
        gen_patch["dialect"] = org.dialect
    if body.apply_industry_defaults:      # tone, audience, objective of the new field
        gen_patch = industries.generation_defaults(org.industry, org.language, org.dialect)
    app_settings.update_section(db, "generation", gen_patch)
    return tenancy.org_summary(db, org)


# ------------------------------------------------------------------ staff
class MemberIn(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    name: str = ""
    role: str = Field("editor", pattern="^(owner|editor|reviewer)$")
    password: str = Field(min_length=8, max_length=200)


class MemberPatch(BaseModel):
    name: str | None = None
    role: str | None = Field(None, pattern="^(owner|editor|reviewer)$")
    active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=200)


@router.get("/team", dependencies=[RequireOwner])
def team(db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.org_id == current_org.get()).order_by(User.created_at))
    return [u.public() for u in users]


@router.post("/team")
def add_member(body: MemberIn, who: Principal = RequireOwner, db: Session = Depends(get_db)):
    org = db.get(Organization, current_org.get())
    count = db.scalar(select(func.count()).select_from(User).where(User.org_id == org.id)) or 0
    if count >= (org.max_users or 10):
        raise HTTPException(409, f"وصلت الشركة للحد الأقصى من المستخدمين ({org.max_users})")
    email = body.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "هذا البريد مستخدم في حساب آخر")
    user = User(org_id=org.id, email=email, name=body.name.strip(), role=body.role,
                password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    return user.public()


def _member(db: Session, uid: int) -> User:
    user = db.get(User, uid)
    if user is None or user.org_id != current_org.get():
        raise HTTPException(404, "المستخدم غير موجود")
    return user


def _owners_left(db: Session, excluding: int) -> int:
    return db.scalar(select(func.count()).select_from(User).where(
        User.org_id == current_org.get(), User.role == "owner", User.active.is_(True), User.id != excluding)) or 0


@router.patch("/team/{uid}")
def update_member(uid: int, body: MemberPatch, who: Principal = RequireOwner, db: Session = Depends(get_db)):
    user = _member(db, uid)
    demoting = (body.role and body.role != "owner") or body.active is False
    if user.role == "owner" and demoting and _owners_left(db, user.id) == 0:
        raise HTTPException(409, "يجب أن يبقى مالك واحد على الأقل للشركة")
    if body.name is not None:
        user.name = body.name.strip()
    if body.role:
        user.role = body.role
    if body.active is not None:
        user.active = body.active
    if body.password:
        user.password_hash = hash_password(body.password)
    return user.public()


@router.delete("/team/{uid}")
def remove_member(uid: int, who: Principal = RequireOwner, db: Session = Depends(get_db)):
    user = _member(db, uid)
    if user.id == who["id"]:
        raise HTTPException(409, "لا يمكنك حذف حسابك")
    if user.role == "owner" and _owners_left(db, user.id) == 0:
        raise HTTPException(409, "يجب أن يبقى مالك واحد على الأقل للشركة")
    db.delete(user)
    return {"ok": True}


# ------------------------------------------------------------------ platform admin
admin = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[RequireSuperadmin])


@admin.get("/orgs")
def all_orgs(db: Session = Depends(get_db)):
    return [tenancy.org_summary(db, o) for o in db.scalars(select(Organization).order_by(Organization.id))]


class NewOrg(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    industry: str = "general"
    language: str = Field("ar", pattern="^(ar|en|ms|fr)$")
    dialect: str | None = None
    owner_email: str = Field(min_length=5)
    owner_name: str = ""
    owner_password: str = Field(min_length=8)
    max_users: int = Field(10, ge=1, le=500)


@admin.post("/orgs")
def create_org(body: NewOrg, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == body.owner_email.strip().lower())):
        raise HTTPException(409, "بريد المالك مستخدم في حساب آخر")
    org, _owner = tenancy.create_org(db, body.name, body.industry, body.language, body.dialect,
                                     body.owner_email, body.owner_password, body.owner_name)
    org.max_users = body.max_users
    return tenancy.org_summary(db, org)


class OrgAdminPatch(BaseModel):
    status: str | None = Field(None, pattern="^(active|suspended)$")
    max_users: int | None = Field(None, ge=1, le=500)
    plan: str | None = None
    name: str | None = None


@admin.patch("/orgs/{oid}")
def admin_update_org(oid: int, body: OrgAdminPatch, db: Session = Depends(get_db)):
    org = db.get(Organization, oid)
    if org is None:
        raise HTTPException(404, "الشركة غير موجودة")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(org, k, v)
    return tenancy.org_summary(db, org)


@admin.get("/credentials")
def platform_credentials():
    """The platform's shared AI / photo keys (used by every company without its own)."""
    with use_org(None):
        return {"values": credentials.public_view()}


@admin.put("/credentials")
def save_platform_credentials(body: dict, db: Session = Depends(get_db)):
    body = {k: v for k, v in body.items() if k in credentials.FIELDS and k not in credentials.COMPANY_ONLY}
    with use_org(None):
        return {"values": credentials.save(db, body, scope="platform")}
