"""Settings, provider status, jobs and statistics."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import RequireUser, check_supabase_key, current_user
from ..config import get_settings
from ..db import Article, Draft, PublishLog, Source, get_db, utcnow
from ..publishers import REGISTRY, get_publisher
from ..services import app_settings, credentials, generator, storage
from ..services.jobs import jobs

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health(check: bool = True):
    """Public setup diagnostics — booleans and host names only, never keys or secrets.

    Open https://<backend>/api/health after deploying: it names any misconfigured variable.
    """
    s = get_settings()
    auth_check = await check_supabase_key() if (check and not s.auth_disabled) else None
    problems: list[str] = []
    if auth_check and not auth_check.get("ok"):
        problems.append(auth_check.get("error", "إعداد Supabase غير صحيح"))
    if s.auth_mode == "unconfigured":
        problems.append("لا توجد طريقة دخول — أضف ADMIN_EMAIL و ADMIN_PASSWORD")
    if s.auth_mode == "internal" and len(s.admin_password) < 8:
        problems.append("ADMIN_PASSWORD قصيرة جدًا — استخدم 8 أحرف على الأقل")
    if s.auth_mode == "supabase" and not s.allowed_email_list:
        problems.append("ALLOWED_EMAILS فارغ — أي حساب في مشروع Supabase يستطيع الدخول")
    if not s.supabase_service_role_key and s.storage_backend == "supabase":
        problems.append("SUPABASE_SERVICE_ROLE_KEY غير مضبوط — رفع صور المنشورات سيفشل")
    if not storage.is_publicly_reachable():
        problems.append("روابط الصور غير عامة — النشر على Meta أو Buffer سيفشل")
    problems.extend(credentials.ai_warnings())
    return {
        "ok": not problems,
        "version": credentials.VERSION,
        "environment": s.environment,
        "auth": {
            "mode": s.auth_mode,
            "admin_email": "set" if s.admin_email else "missing",
            "supabase_url": s.supabase_base or None,
            "anon_key": s.anon_key_kind,
            "service_role_key": "set" if s.supabase_service_role_key else "missing",
            "allowed_emails": len(s.allowed_email_list),
            "auth_disabled": s.auth_disabled,
            "supabase_check": auth_check,
        },
        "storage": {"backend": s.storage_backend, "public": storage.is_publicly_reachable()},
        "ai": generator.ai_info(),
        "database": s.database_url.split("@")[-1].split("?")[0] if "@" in s.database_url else s.database_url,
        "problems": problems,
    }


@router.get("/me")
def me(user: dict = RequireUser):
    return user


@router.get("/status", dependencies=[RequireUser])
def status():
    s = get_settings()
    return {
        "ai": generator.ai_info(),
        "images": {"pexels": bool(credentials.current()["pexels_api_key"])},
        "storage": {"backend": s.storage_backend, "public": storage.is_publicly_reachable()},
        "providers": {name: {"configured": cls().configured(), "platforms": list(cls.platforms)}
                      for name, cls in REGISTRY.items()},
        "jobs": jobs.state(),
    }


@router.get("/providers/{name}/status", dependencies=[RequireUser])
async def provider_status(name: str):
    if name not in REGISTRY:
        raise HTTPException(404, "مزوّد غير معروف")
    return await get_publisher(name).status()


@router.get("/settings", dependencies=[RequireUser])
def all_settings(db: Session = Depends(get_db)):
    return {"values": {k: app_settings.get_section(db, k) for k in app_settings.DEFAULTS},
            "options": app_settings.options()}


@router.get("/settings/credentials", dependencies=[RequireUser])
def read_credentials():
    """Keys and AI provider settings. Secrets come back as a status, never as a value."""
    return {"values": credentials.public_view(), "providers": {"ai": list(credentials.ENGINES)}}


@router.post("/settings/credentials/test-ai", dependencies=[RequireUser])
async def test_ai():
    """Round-trip to the configured AI engine — powers the "test connection" button."""
    return await generator.test_connection()


@router.put("/settings/credentials", dependencies=[RequireUser])
def write_credentials(body: dict, db: Session = Depends(get_db)):
    """Save keys. An empty secret keeps the current one; null removes it."""
    # Fields of removed engines (sent by an older dashboard) are ignored instead of failing.
    body = {k: v for k, v in body.items() if k in credentials.FIELDS}
    return {"values": credentials.save(db, body)}


@router.put("/settings/{section}", dependencies=[RequireUser])
def save_settings(section: str, body: dict, db: Session = Depends(get_db)):
    try:
        return app_settings.update_section(db, section, body)
    except KeyError as exc:
        raise HTTPException(404, "قسم إعدادات غير معروف") from exc


@router.post("/scrape/run", dependencies=[RequireUser])
async def run_now(background: BackgroundTasks):
    if jobs.busy:
        raise HTTPException(409, "توجد عملية سحب قيد التنفيذ")
    background.add_task(jobs.run_collection, None)
    return {"ok": True, "started": True}


@router.post("/scrape/run-all", dependencies=[RequireUser])
async def run_all(background: BackgroundTasks, db: Session = Depends(get_db)):
    if jobs.busy:
        raise HTTPException(409, "توجد عملية سحب قيد التنفيذ")
    ids = list(db.scalars(select(Source.id).where(Source.enabled.is_(True))))
    background.add_task(jobs.run_collection, ids)
    return {"ok": True, "started": True, "sources": len(ids)}


@router.get("/jobs", dependencies=[RequireUser])
def job_state():
    return jobs.state()


@router.get("/stats", dependencies=[RequireUser])
def stats(days: int = 30, db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=days)
    by_status = dict(db.execute(select(Draft.status, func.count()).where(Draft.created_at >= since)
                                .group_by(Draft.status)).all())
    by_platform = [{"platform": p, "status": s, "count": c} for p, s, c in db.execute(
        select(PublishLog.platform, PublishLog.status, func.count()).where(PublishLog.created_at >= since)
        .group_by(PublishLog.platform, PublishLog.status)).all()]
    by_source = [{"source": n or "—", "drafts": c} for n, c in db.execute(
        select(Draft.source_name, func.count()).where(Draft.created_at >= since)
        .group_by(Draft.source_name).order_by(func.count().desc()).limit(10)).all()]
    articles = db.scalar(select(func.count()).select_from(Article).where(Article.fetched_at >= since)) or 0
    reviewed = sum(by_status.get(k, 0) for k in ("approved", "scheduled", "published", "rejected"))
    return {"days": days, "articles": articles, "by_status": by_status, "by_platform": by_platform,
            "by_source": by_source,
            "approval_rate": round(100 * (reviewed - by_status.get("rejected", 0)) / reviewed) if reviewed else None}
