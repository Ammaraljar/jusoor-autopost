"""Companies (organisations), their staff, and the first-run migration to multi-company mode."""
from __future__ import annotations

import logging
import random
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import (AppSetting, Article, Brand, CalendarItem, Campaign, Draft, Organization, Source, User,
                  session_scope, use_org)
from ..security import hash_password
from . import app_settings, industries

log = logging.getLogger(__name__)
ROLES = ("owner", "editor", "reviewer")
TENANT_TABLES = (Brand, Source, Article, Campaign, CalendarItem, Draft)


def new_brand(org: Organization, name: str | None = None, logo_path: str | None = None) -> Brand:
    """A brand that already speaks the company's field: colours, CTA and a unique design seed."""
    profile = industries.get(org.industry)
    return Brand(org_id=org.id, name=name or org.name, handle="", website="",
                 voice="", colors=dict(profile.get("colors") or {}),
                 cta_text=industries.cta(profile, org.language),
                 card_theme="magazine", design_seed=random.randint(1, 10_000), is_default=True,
                 logo_path=logo_path)


def create_org(db: Session, name: str, industry: str = "general", language: str = "ar",
               dialect: str | None = None, owner_email: str | None = None, owner_password: str | None = None,
               owner_name: str = "") -> tuple[Organization, User | None]:
    if industry not in industries.INDUSTRIES:
        industry = "general"
    org = Organization(name=name.strip(), industry=industry, language=language if language in industries.LANGUAGES else "ar",
                       dialect=dialect)
    db.add(org)
    db.flush()
    with use_org(org.id):
        db.add(new_brand(org))
        app_settings.update_section(db, "generation",
                                    industries.generation_defaults(industry, org.language, dialect))
    owner = None
    if owner_email:
        owner = User(org_id=org.id, email=owner_email.strip().lower(), name=owner_name.strip(),
                     password_hash=hash_password(owner_password or ""), role="owner")
        db.add(owner)
    db.flush()
    return org, owner


def bootstrap() -> None:
    """First start in multi-company mode: everything that exists becomes company #1, and the
    ADMIN_EMAIL account becomes the platform's super-admin (and owner of company #1)."""
    s = get_settings()
    with session_scope() as db:
        org = db.scalar(select(Organization).order_by(Organization.id))
        if org is None:
            brand = db.scalar(select(Brand).order_by(Brand.is_default.desc(), Brand.id))
            gen = db.get(AppSetting, "generation")
            industry = (gen.value or {}).get("industry", "travel") if gen else "travel"
            org = Organization(name=brand.name if brand else "My company", industry=industry, language="ar",
                               dialect=(gen.value or {}).get("dialect") if gen else None)
            db.add(org)
            db.flush()
            for model in TENANT_TABLES:
                db.execute(update(model).where(model.org_id.is_(None)).values(org_id=org.id)
                           .execution_options(all_orgs=True))
            # settings and publishing accounts move to the company
            for section in ("generation", "scheduler", "publishing"):
                row = db.get(AppSetting, section)
                if row and not db.get(AppSetting, f"org{org.id}:{section}"):
                    db.add(AppSetting(key=f"org{org.id}:{section}", value=dict(row.value or {})))
            creds = db.get(AppSetting, "credentials")
            if creds and creds.value:
                own = {k: v for k, v in creds.value.items()
                       if k in ("buffer_api_key", "meta_access_token", "uploadpost_api_key")}
                if own and not db.get(AppSetting, f"credentials:org{org.id}"):
                    db.add(AppSetting(key=f"credentials:org{org.id}", value=own))
            log.info("multi-company mode: existing data moved to company #%s", org.id)
        # the Algerian dialect was retired: such settings move to Moroccan (Maghrebi)
        for row in db.scalars(select(AppSetting)):
            if isinstance(row.value, dict) and row.value.get("dialect") == "algeria":
                row.value = {**row.value, "dialect": "maghreb"}
        db.execute(update(Organization).where(Organization.dialect == "algeria").values(dialect="maghreb"))
        db.execute(update(Source).where(Source.dialect == "algeria").values(dialect="maghreb")
                   .execution_options(all_orgs=True))
        # brands without a design seed get one (unique look per company)
        for b in db.scalars(select(Brand).where(Brand.design_seed.is_(None)).execution_options(all_orgs=True)):
            b.design_seed = random.randint(1, 10_000)
        # the environment's admin account is the super-admin
        email = (s.admin_email or "").strip().lower()
        if email:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                db.add(User(org_id=org.id, email=email, name="Admin", role="owner", is_superadmin=True,
                            password_hash=hash_password(s.admin_password) if s.admin_password else ""))
            else:
                user.is_superadmin = True
                if s.admin_password and not user.password_hash:
                    user.password_hash = hash_password(s.admin_password)


def org_summary(db: Session, org: Organization) -> dict[str, Any]:
    users = db.scalar(select(func.count()).select_from(User).where(User.org_id == org.id)) or 0
    drafts = db.scalar(select(func.count()).select_from(Draft).where(Draft.org_id == org.id)
                       .execution_options(all_orgs=True)) or 0
    sources = db.scalar(select(func.count()).select_from(Source).where(Source.org_id == org.id)
                        .execution_options(all_orgs=True)) or 0
    return {**org.to_dict(), "industry_label": industries.get(org.industry)["ar"], "users": users,
            "drafts": drafts, "sources": sources}
