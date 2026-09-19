"""Publishing orchestration and scheduled-post processing."""
from __future__ import annotations

import logging

from sqlalchemy import select

from ..db import CalendarItem, Draft, PublishLog, session_scope, utcnow
from ..publishers import get_publisher
from ..publishers.base import PlatformResult, PublishRequest
from . import app_settings, qa, storage
from .pipeline import _brand_for, compose_caption

log = logging.getLogger(__name__)


async def publish_draft(draft_id: int) -> dict:
    """Publish a draft to all of its publish_targets [{provider, platforms}]."""
    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        if draft is None:
            return {"ok": False, "error": "draft not found"}
        gen = app_settings.get_section(db, "generation")
        pub = app_settings.get_section(db, "publishing")
        report = qa.run_qa(draft, draft.slides, gen.get("credit_source", True))
        if not report["passed"]:
            draft.status, draft.error = "failed", "فشل فحص الجودة: " + "، ".join(
                i["message"] for i in report["items"] if i["status"] == "fail")
            return {"ok": False, "error": draft.error}
        if not storage.is_publicly_reachable():
            draft.status = "failed"
            draft.error = "الصور غير متاحة على رابط عام. فعّل STORAGE_BACKEND=supabase أو اضبط PUBLIC_BASE_URL."
            return {"ok": False, "error": draft.error}
        brand = _brand_for(db, draft.brand_id)
        targets = draft.publish_targets or []
        req_base = dict(draft_id=draft.id, caption=compose_caption(draft, gen.get("credit_source", True)),
                        image_urls=[s.image_url for s in draft.slides],
                        image_keys=[s.image_key for s in draft.slides],
                        brand_config=brand.publish_config or {},
                        first_comment=draft.first_comment if pub.get("first_comment_enabled") else "",
                        title=draft.hook)
        draft.status, draft.error = "publishing", None

    all_results = []
    for target in targets:
        provider = target.get("provider")
        platforms = target.get("platforms") or []
        try:
            publisher = get_publisher(provider)
            if not publisher.configured():
                raise RuntimeError(f"{provider} غير مُعدّ (مفتاح API مفقود)")
            results = await publisher.publish(PublishRequest(platforms=platforms, **req_base))
        except Exception as exc:  # noqa: BLE001
            log.exception("publish failed")
            results = [PlatformResult(p, False, error=str(exc)[:500]) for p in platforms]
        for r in results:
            all_results.append({"provider": provider, **r.__dict__})

    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        for r in all_results:
            db.add(PublishLog(draft_id=draft_id, provider=r["provider"], platform=r["platform"],
                              status="success" if r["ok"] else "error", external_id=r["external_id"],
                              response=r["response"] or {}, error=r["error"]))
        ok_count = sum(1 for r in all_results if r["ok"])
        if all_results and ok_count == len(all_results):
            draft.status, draft.published_at = "published", utcnow()
        elif ok_count:
            draft.status, draft.published_at = "published", utcnow()
            draft.error = "نُشر جزئيًا: " + "؛ ".join(f"{r['platform']}: {r['error']}" for r in all_results if not r["ok"])
        else:
            draft.status = "failed"
            draft.error = "؛ ".join(f"{r['provider']}/{r['platform']}: {r['error']}" for r in all_results) or "لا توجد وجهات نشر"
        if draft.calendar_item_id and draft.status == "published":
            item = db.get(CalendarItem, draft.calendar_item_id)
            if item:
                item.status = "published"
        return {"ok": ok_count > 0, "results": all_results, "status": draft.status, "error": draft.error}


async def publish_due() -> int:
    with session_scope() as db:
        ids = list(db.scalars(select(Draft.id).where(Draft.status == "scheduled", Draft.scheduled_at <= utcnow())))
    for did in ids:
        await publish_draft(did)
    return len(ids)
