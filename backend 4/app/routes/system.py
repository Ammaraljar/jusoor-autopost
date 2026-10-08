"""Settings, provider status, jobs and statistics."""
from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import RequireOwner, RequireUser, RequireWriter, check_supabase_key, current_user
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
    from ..db import Organization, session_scope
    out = dict(user)
    with session_scope() as db:
        org = db.get(Organization, user.get("org_id")) if user.get("org_id") else None
        if org:
            out["org"] = {"id": org.id, "name": org.name, "industry": org.industry, "language": org.language,
                          "dialect": org.dialect, "status": org.status}
    return out


@router.get("/status", dependencies=[RequireUser])
def status():
    s = get_settings()
    return {
        "ai": generator.ai_info(),
        "images": {"pexels": bool(credentials.current()["pexels_api_key"]),
                   "pixabay": bool(credentials.current().get("pixabay_api_key"))},
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


@router.post("/settings/credentials/test-ai", dependencies=[RequireOwner])
async def test_ai():
    """Round-trip to the configured AI engine — powers the "test connection" button."""
    return await generator.test_connection()


@router.get("/settings/credentials/models/{engine}", dependencies=[RequireUser])
async def engine_models(engine: str):
    """Models the saved key can really use — fetched live from the provider."""
    if engine not in credentials.ENGINES:
        raise HTTPException(404, "محرّك غير معروف")
    try:
        return {"engine": engine, "models": await generator.list_models(engine, fresh=True)}
    except generator.AIError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.put("/settings/credentials", dependencies=[RequireOwner])
def write_credentials(body: dict, db: Session = Depends(get_db)):
    """Save keys. An empty secret keeps the current one; null removes it."""
    # Fields of removed engines (sent by an older dashboard) are ignored instead of failing.
    body = {k: v for k, v in body.items() if k in credentials.FIELDS}
    return {"values": credentials.save(db, body)}


@router.put("/settings/{section}", dependencies=[RequireOwner])
def save_settings(section: str, body: dict, db: Session = Depends(get_db)):
    try:
        return app_settings.update_section(db, section, body)
    except KeyError as exc:
        raise HTTPException(404, "قسم إعدادات غير معروف") from exc


@router.post("/scrape/run", dependencies=[RequireWriter])
async def run_now(background: BackgroundTasks):
    if jobs.busy:
        raise HTTPException(409, "توجد عملية سحب قيد التنفيذ")
    background.add_task(jobs.run_collection, None)
    return {"ok": True, "started": True}


class ScrapeWindow(BaseModel):
    date_from: date | None = None       # only articles published in this period
    date_to: date | None = None
    max_items: int | None = Field(None, ge=1, le=50)     # per source
    source_ids: list[int] | None = None
    purpose: str | None = None          # news | programs


@router.post("/scrape/run-all", dependencies=[RequireWriter])
async def run_all(background: BackgroundTasks, body: ScrapeWindow | None = None, db: Session = Depends(get_db)):
    if jobs.busy:
        raise HTTPException(409, "توجد عملية سحب قيد التنفيذ")
    body = body or ScrapeWindow()
    if body.date_from and body.date_to and body.date_from > body.date_to:
        raise HTTPException(400, "تاريخ البداية بعد تاريخ النهاية")
    q = select(Source.id).where(Source.enabled.is_(True))
    if body.source_ids:
        q = select(Source.id).where(Source.id.in_(body.source_ids))
    if body.purpose:
        q = q.where(Source.purpose == body.purpose)
    ids = list(db.scalars(q))
    window = {"date_from": body.date_from, "date_to": body.date_to, "max_items": body.max_items} \
        if (body.date_from or body.date_to or body.max_items) else None
    background.add_task(jobs.run_collection, ids, window)
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


# ------------------------------------------------------------------ backup
_SOURCE_FIELDS = ("name", "kind", "base_url", "feed_url", "listing_urls", "link_selector", "link_pattern",
                  "body_selector", "purpose", "dialect", "category", "country", "language", "priority", "enabled",
                  "check_interval_minutes", "max_items_per_run")
_BRAND_FIELDS = ("name", "handle", "website", "voice", "colors", "font_family", "logo_placement", "card_style",
                 "color_mode", "logo_backdrop", "cta_text", "publish_config", "is_default")


@router.get("/backup", dependencies=[RequireUser])
def export_backup(db: Session = Depends(get_db)):
    """Everything needed to rebuild the setup elsewhere — never the API keys."""
    from ..db import Brand, Campaign
    return {
        "app": "jusoor-autopost", "version": credentials.VERSION, "exported_at": utcnow().isoformat(),
        "settings": {k: app_settings.get_section(db, k) for k in ("generation", "scheduler", "publishing")},
        "sources": [{f: getattr(s, f) for f in _SOURCE_FIELDS} for s in db.scalars(select(Source))],
        "brands": [{f: getattr(b, f) for f in _BRAND_FIELDS} for b in db.scalars(select(Brand))],
        "campaigns": [{k: v for k, v in c.to_dict().items() if k not in ("id", "created_at")}
                      for c in db.scalars(select(Campaign))],
    }


@router.post("/backup/restore", dependencies=[RequireOwner])
def restore_backup(body: dict, db: Session = Depends(get_db)):
    """Restore settings and add missing sources / campaigns from a backup file (nothing is deleted)."""
    from ..db import Campaign
    if body.get("app") != "jusoor-autopost":
        raise HTTPException(400, "هذا ليس ملف نسخة احتياطية من النظام")
    for section, values in (body.get("settings") or {}).items():
        if section in ("generation", "scheduler", "publishing") and isinstance(values, dict):
            app_settings.update_section(db, section, values)
    names = set(db.scalars(select(Source.name)))
    added = 0
    for item in body.get("sources") or []:
        if item.get("name") and item["name"] not in names:
            db.add(Source(**{f: item[f] for f in _SOURCE_FIELDS if f in item}))
            added += 1
    camp_names = set(db.scalars(select(Campaign.name)))
    camps = 0
    for item in body.get("campaigns") or []:
        if item.get("name") and item["name"] not in camp_names:
            allowed = {c.key for c in Campaign.__table__.columns} - {"id", "created_at"}
            values = {k: v for k, v in item.items() if k in allowed}
            for k in ("start_date", "end_date"):
                if isinstance(values.get(k), str):
                    values[k] = date.fromisoformat(values[k][:10])
            db.add(Campaign(**values))
            camps += 1
    return {"ok": True, "sources_added": added, "campaigns_added": camps}
