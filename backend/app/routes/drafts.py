"""Draft review, editing, regeneration and publishing endpoints."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import RequireUser
from ..db import Draft, PublishLog, Slide, get_db, utcnow
from ..publishers import REGISTRY
from ..services import app_settings, generator, pipeline, publishing, qa, scheduling, storage, variants

router = APIRouter(prefix="/api/drafts", tags=["drafts"], dependencies=[RequireUser])
STATUSES = ["generating", "pending_review", "approved", "scheduled", "publishing", "published", "failed", "rejected"]
EDITABLE = ["hook", "subtitle", "caption", "hashtags", "first_comment", "cta", "badge", "campaign_id", "brand_id"]


def _get(db: Session, draft_id: int) -> Draft:
    d = db.get(Draft, draft_id)
    if d is None:
        raise HTTPException(404, "المسودة غير موجودة")
    return d


def _iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _summary(d: Draft) -> dict[str, Any]:
    cover = d.cover_thumb_url or (d.slides[0].image_url if d.slides else None)
    return {"id": d.id, "status": d.status, "hook": d.hook or d.original_title, "source": d.source_name,
            "origin": d.origin, "cover_url": cover, "content_type": d.content_type, "dialect": d.dialect, "slides": len(d.slides), "brand_id": d.brand_id,
            "campaign_id": d.campaign_id, "relevance": d.relevance, "error": d.error,
            "scheduled_at": _iso(d.scheduled_at), "published_at": _iso(d.published_at),
            "original_published_at": _iso(d.original_published_at), "created_at": _iso(d.created_at)}


def _full(db: Session, d: Draft) -> dict[str, Any]:
    gen = app_settings.get_section(db, "generation")
    logs = db.scalars(select(PublishLog).where(PublishLog.draft_id == d.id).order_by(PublishLog.id.desc()))
    return {**d.to_dict(), "slides": [s.to_dict() for s in d.slides],
            "qa": qa.run_qa(d, d.slides, gen.get("credit_source", True)),
            "caption_preview": pipeline.compose_caption(d, gen.get("credit_source", True)),
            "variants": d.variants or (variants.finalize(d, variants.fallback_texts(d), gen.get("credit_source", True))
                                       if d.slides else {}),
            "variants_generated": bool(d.variants),
            "logs": [l.to_dict() for l in logs]}


@router.get("")
def list_drafts(status: str = "pending_review", brand_id: int | None = None, campaign_id: int | None = None,
                q: str | None = None, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    query = select(Draft)
    if status != "all":
        query = query.where(Draft.status.in_(status.split(",")))
    if brand_id:
        query = query.where(Draft.brand_id == brand_id)
    if campaign_id:
        query = query.where(Draft.campaign_id == campaign_id)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Draft.hook.ilike(like), Draft.original_title.ilike(like), Draft.caption.ilike(like)))
    from sqlalchemy.orm import selectinload
    query = query.options(selectinload(Draft.slides)).order_by(Draft.created_at.desc()).limit(min(limit, 300)).offset(offset)
    return [_summary(d) for d in db.scalars(query)]


@router.get("/counts")
def counts(db: Session = Depends(get_db)):
    rows = db.execute(select(Draft.status, func.count()).group_by(Draft.status)).all()
    data = {s: 0 for s in STATUSES}
    data.update({s: c for s, c in rows})
    data["all"] = sum(c for _, c in rows)
    return data


class ManualDraft(BaseModel):
    topic: str = Field(min_length=3)
    notes: str = ""
    dialect: str | None = None
    brand_id: int | None = None
    content_type: str = "travel"
    platform: str = "instagram"


@router.post("/manual")
async def create_manual(body: ManualDraft, background: BackgroundTasks, db: Session = Depends(get_db)):
    from ..db import CalendarItem
    item = CalendarItem(brand_id=body.brand_id, date=datetime.now(timezone.utc).date(), topic=body.topic,
                        notes=body.notes, content_type=body.content_type, platform=body.platform,
                        dialect=body.dialect or None)
    db.add(item)
    db.commit()
    background.add_task(pipeline.draft_from_calendar, item.id)
    return {"ok": True, "calendar_item_id": item.id}


class BulkBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    action: str                     # approve | reject | restore | unschedule | delete | auto_schedule


@router.post("/bulk")
def bulk(body: BulkBody, db: Session = Depends(get_db)):
    """Apply one decision to many posts at once — including permanent deletion."""
    if body.action not in ("approve", "reject", "restore", "unschedule", "delete", "auto_schedule"):
        raise HTTPException(400, "إجراء غير معروف")
    done, skipped = 0, 0
    reasons: list[str] = []
    rows = db.scalars(select(Draft).where(Draft.id.in_(body.ids)).order_by(Draft.created_at)).all()
    if body.action == "auto_schedule":
        for d in rows:
            try:
                scheduling.schedule(db, d)
                done += 1
            except ValueError as exc:
                skipped += 1
                reasons.append(f"#{d.id}: {exc}")
        return {"ok": True, "done": done, "skipped": skipped, "reasons": reasons[:10]}
    for d in rows:
        if body.action == "delete":
            if d.status == "publishing":          # never pull a post out from under the publisher
                skipped += 1
                continue
            for sl in d.slides:
                if sl.image_key:
                    storage.delete(sl.image_key)
            db.delete(d)
        elif body.action == "approve":
            if d.status in ("generating", "publishing", "published"):
                skipped += 1
                continue
            d.status, d.error = "approved", None
        elif body.action == "reject":
            if d.status in ("publishing", "published"):
                skipped += 1
                continue
            d.status = "rejected"
        elif body.action == "restore":
            if d.status in ("generating", "publishing"):
                skipped += 1
                continue
            d.status, d.error, d.scheduled_at = "pending_review", None, None
        elif body.action == "unschedule":
            if d.status != "scheduled":
                skipped += 1
                continue
            d.status, d.scheduled_at = "approved", None
        done += 1
    return {"ok": True, "done": done, "skipped": skipped}


class VariantPatch(BaseModel):
    text: str | None = None
    slides: list[int] | None = None       # single-image platforms: which slide to post


@router.patch("/{draft_id}/variants/{platform}")
def update_variant(draft_id: int, platform: str, body: VariantPatch, db: Session = Depends(get_db)):
    """Edit one platform's post (its text, or which image a single-image platform uses)."""
    d = _get(db, draft_id)
    if platform not in variants.PLATFORM_SPECS:
        raise HTTPException(404, "منصة غير معروفة")
    gen = app_settings.get_section(db, "generation")
    current = dict(d.variants or variants.finalize(d, variants.fallback_texts(d), gen.get("credit_source", True)))
    v = dict(current.get(platform) or {})
    spec = variants.PLATFORM_SPECS[platform]
    if body.text is not None:
        if len(body.text) > spec["limit"]:
            raise HTTPException(400, f"النص يتجاوز حد {spec['label']} ({spec['limit']} حرف)")
        v["text"] = body.text
    if body.slides is not None:
        chosen = variants.clean_slides(platform, body.slides, len(d.slides))
        if not chosen:
            raise HTTPException(400, "اختر صورة واحدة على الأقل")
        v["slides"], v["custom_slides"] = chosen, True
    slides = v.get("slides") or variants.default_slides(platform, variants._kinds(d))
    current[platform] = {**v, "slides": slides, "format": "carousel" if len(slides) > 1 else "single",
                         "limit": spec["limit"], "label": spec["label"], "images": spec["images"]}
    d.variants = current
    return _full(db, d)


@router.post("/{draft_id}/variants/regenerate")
async def regenerate_variants(draft_id: int, db: Session = Depends(get_db)):
    """Rewrite every platform's text from the current post (after editing the main text or slides)."""
    d = _get(db, draft_id)
    if not d.slides:
        raise HTTPException(409, "المنشور بلا شرائح بعد")
    db.commit()
    try:
        await pipeline.make_variants(draft_id)
    except generator.AIError as exc:
        raise HTTPException(502, str(exc)) from exc
    db.expire_all()
    return _full(db, _get(db, draft_id))


class ScheduleBody(BaseModel):
    scheduled_at: datetime | None = None     # exact time; or
    date: str | None = None                  # a day (YYYY-MM-DD): the first free slot that day
    targets: list[dict] | None = None


@router.post("/{draft_id}/schedule")
def schedule_draft(draft_id: int, body: ScheduleBody, db: Session = Depends(get_db)):
    """Put a post on the plan, or move it: next free slot, a given day, or an exact time."""
    from datetime import date as date_cls
    d = _get(db, draft_id)
    when = body.scheduled_at
    if when and when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if body.date and not when:
        try:
            day = date_cls.fromisoformat(body.date)
        except ValueError as exc:
            raise HTTPException(400, "تاريخ غير صالح") from exc
        when = scheduling.next_free_slot(db, draft_id=d.id, only_day=day)
        if when is None:
            raise HTTPException(409, f"لا يوجد موعد فارغ يوم {body.date} — اختر يومًا آخر أو ارفع عدد المنشورات اليومي")
    if when and when <= utcnow():
        raise HTTPException(400, "اختر وقتًا في المستقبل")
    try:
        scheduling.schedule(db, d, when, body.targets)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _full(db, d)


class DialectBody(BaseModel):
    dialect: str = Field(pattern="^(msa|gulf|maghreb|algeria)$")


@router.post("/{draft_id}/dialect-copy")
async def make_dialect_copy(draft_id: int, body: DialectBody, background: BackgroundTasks,
                            db: Session = Depends(get_db)):
    """A copy of the post for another market (Gulf, Maghreb, Algeria…), with the same photos."""
    d = _get(db, draft_id)
    if d.language != "ar":
        raise HTTPException(400, "اللهجات متاحة للمنشورات العربية فقط")
    background.add_task(pipeline.dialect_copy, d.id, body.dialect)
    return {"ok": True, "started": True}


@router.get("/{draft_id}")
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    return _full(db, _get(db, draft_id))


class DraftPatch(BaseModel):
    hook: str | None = None
    subtitle: str | None = None
    caption: str | None = None
    hashtags: str | None = None
    first_comment: str | None = None
    cta: str | None = None
    badge: str | None = None
    campaign_id: int | None = None
    brand_id: int | None = None


@router.patch("/{draft_id}")
async def update_draft(draft_id: int, body: DraftPatch, background: BackgroundTasks, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    changes = body.model_dump(exclude_unset=True)
    rerender: set[int] = set()
    for key, value in changes.items():
        if key in EDITABLE:
            setattr(d, key, value if value is not None or key in ("campaign_id",) else getattr(d, key))
    for s in d.slides:
        if s.kind == "cover" and ({"hook", "subtitle", "badge"} & changes.keys()):
            s.heading, s.body = d.hook, d.subtitle
            rerender.add(s.position)
        if s.kind == "cta" and "cta" in changes:
            s.heading = d.cta
            rerender.add(s.position)
    if "brand_id" in changes:
        rerender = {s.position for s in d.slides}
    db.commit()
    if rerender:
        background.add_task(pipeline.render_draft, d.id, sorted(rerender))
    return _full(db, d)


class SlidePatch(BaseModel):
    heading: str | None = None
    body: str | None = None


def _slide(d: Draft, slide_id: int) -> Slide:
    for s in d.slides:
        if s.id == slide_id:
            return s
    raise HTTPException(404, "الشريحة غير موجودة")


@router.patch("/{draft_id}/slides/{slide_id}")
async def update_slide(draft_id: int, slide_id: int, body: SlidePatch, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    s = _slide(d, slide_id)
    if body.heading is not None:
        s.heading = body.heading
    if body.body is not None:
        s.body = body.body
    if s.kind == "cover":
        d.hook, d.subtitle = s.heading, s.body
    elif s.kind == "cta":
        d.cta = s.heading
    db.commit()
    await pipeline.render_draft(d.id, [s.position])
    db.expire_all()
    return _full(db, _get(db, draft_id))


@router.post("/{draft_id}/slides/{slide_id}/regenerate")
async def regenerate_slide(draft_id: int, slide_id: int, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    s = _slide(d, slide_id)
    brand = pipeline._brand_for(db, d.brand_id)
    gen = {**app_settings.get_section(db, "generation"), "language": d.language, "tone": d.tone,
           **({"dialect": d.dialect} if d.dialect else {})}
    try:
        new = await generator.regenerate_slide(pipeline.brand_context(brand), gen, generator.draft_context(d),
                                               s.heading, s.body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"فشل توليد النص: {exc}") from exc
    s.heading, s.body = new["heading"], new["body"]
    db.commit()
    await pipeline.render_draft(d.id, [s.position])
    db.expire_all()
    return _full(db, _get(db, draft_id))


@router.post("/{draft_id}/slides/{slide_id}/background")
async def upload_background(draft_id: int, slide_id: int, file: UploadFile = File(...),
                            db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    s = _slide(d, slide_id)
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(400, "الحد الأقصى 15 ميغابايت")
    from ..services import images
    try:
        jpeg = images.normalise(data, min_width=1)         # any phone photo → upright JPEG
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "تعذّر قراءة الصورة — استخدم JPG أو PNG أو WEBP "
                                 "(صور HEIC من الآيفون: صدّرها كـ JPG أولًا)") from exc
    key = f"uploads/bg-{d.id}-{uuid.uuid4().hex[:8]}.jpg"
    s.background_url = storage.save_bytes(key, jpeg, "image/jpeg")
    db.commit()
    await pipeline.render_draft(d.id, [s.position])
    db.expire_all()
    return _full(db, _get(db, draft_id))


@router.post("/{draft_id}/backgrounds")
async def upload_backgrounds(draft_id: int, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    """Several photos from the user's computer, spread over all slides in order (repeated if fewer)."""
    d = _get(db, draft_id)
    if not d.slides:
        raise HTTPException(409, "المنشور بلا شرائح بعد")
    if len(files) > 20:
        raise HTTPException(400, "الحد الأقصى 20 صورة في المرة الواحدة")
    from ..services import images
    urls = []
    for f in files:
        data = await f.read()
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(400, f"{f.filename}: الحد الأقصى 15 ميغابايت للصورة")
        try:
            jpeg = images.normalise(data, min_width=1)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"{f.filename}: تعذّر قراءة الصورة — استخدم JPG أو PNG أو WEBP") from exc
        key = f"uploads/bg-{d.id}-{uuid.uuid4().hex[:8]}.jpg"
        urls.append(storage.save_bytes(key, jpeg, "image/jpeg"))
    for i, s in enumerate(sorted(d.slides, key=lambda x: x.position)):
        s.background_url = urls[i % len(urls)]
    db.commit()
    await pipeline.render_draft(d.id)
    db.expire_all()
    return _full(db, _get(db, draft_id))


class RegenField(BaseModel):
    field: str


@router.post("/{draft_id}/regenerate")
async def regenerate_text(draft_id: int, body: RegenField, background: BackgroundTasks,
                          db: Session = Depends(get_db)):
    if body.field not in ("hook", "caption", "cta", "first_comment", "subtitle"):
        raise HTTPException(400, "حقل غير مدعوم")
    d = _get(db, draft_id)
    brand = pipeline._brand_for(db, d.brand_id)
    gen = {**app_settings.get_section(db, "generation"), "language": d.language, "tone": d.tone,
           **({"dialect": d.dialect} if d.dialect else {})}
    try:
        text = await generator.regenerate_field(pipeline.brand_context(brand), gen, generator.draft_context(d),
                                                body.field)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"فشل توليد النص: {exc}") from exc
    setattr(d, body.field, text)
    positions = []
    for s in d.slides:
        if s.kind == "cover" and body.field in ("hook", "subtitle"):
            s.heading, s.body = d.hook, d.subtitle
            positions.append(s.position)
        if s.kind == "cta" and body.field == "cta":
            s.heading = d.cta
            positions.append(s.position)
    db.commit()
    if positions:
        await pipeline.render_draft(d.id, positions)
        db.expire_all()
    return _full(db, _get(db, draft_id))


@router.post("/{draft_id}/regenerate-all")
async def regenerate_all(draft_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    brand = pipeline._brand_for(db, d.brand_id)
    gen = {**app_settings.get_section(db, "generation"), "language": d.language, "tone": d.tone,
           **({"dialect": d.dialect} if d.dialect else {}),
           "content_type": d.content_type, "platform": d.platform,
           **({"purpose": "programs", "content_type": "promotional"} if d.content_type == "program" else {})}
    ctx = pipeline.brand_context(brand)
    origin, title, text, source_name = d.origin, d.original_title, d.original_body, d.source_name
    d.status = "generating"
    db.commit()

    async def job():
        try:
            if origin == "source":
                post = await generator.generate_from_article(ctx, gen, title, text, source_name)
            else:
                post = await generator.generate_from_topic(ctx, gen, title, text)
        except Exception as exc:  # noqa: BLE001
            pipeline._fail(draft_id, f"فشل توليد النص: {exc}")
            return
        from ..db import session_scope
        with session_scope() as s:
            pipeline._apply_post(s.get(Draft, draft_id), post)
        await pipeline.render_draft(draft_id)

    background.add_task(job)
    return {"ok": True}


class RenderBody(BaseModel):
    refresh_backgrounds: bool = False


@router.post("/{draft_id}/render")
async def rerender(draft_id: int, body: RenderBody, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    if body.refresh_backgrounds and d.error and d.error.startswith("لم تُعثر"):
        d.error = None
    db.commit()
    await pipeline.render_draft(d.id, None, refresh_backgrounds=body.refresh_backgrounds)
    db.expire_all()
    d = _get(db, draft_id)
    if body.refresh_backgrounds and d.error and d.error.startswith("لم تُعثر"):
        raise HTTPException(409, d.error)
    return _full(db, d)


@router.get("/{draft_id}/qa")
def draft_qa(draft_id: int, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    return qa.run_qa(d, d.slides, app_settings.get_section(db, "generation").get("credit_source", True))


@router.post("/{draft_id}/approve")
def approve(draft_id: int, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    d.status, d.error = "approved", None
    return _full(db, d)


class RejectBody(BaseModel):
    reason: str = ""


@router.post("/{draft_id}/reject")
def reject(draft_id: int, body: RejectBody, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    d.status, d.reject_reason = "rejected", body.reason
    return _full(db, d)


@router.post("/{draft_id}/restore")
def restore(draft_id: int, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    d.status, d.error, d.scheduled_at = "pending_review", None, None
    return _full(db, d)


class Target(BaseModel):
    provider: str
    platforms: list[str]


class PublishBody(BaseModel):
    targets: list[Target]
    scheduled_at: datetime | None = None


@router.post("/{draft_id}/publish")
async def publish(draft_id: int, body: PublishBody, background: BackgroundTasks, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    if d.status in ("publishing", "published", "generating"):
        raise HTTPException(409, "لا يمكن نشر هذه المسودة في حالتها الحالية")
    targets = [t.model_dump() for t in body.targets if t.platforms]
    if not targets:
        raise HTTPException(400, "اختر منصة واحدة على الأقل")
    for t in targets:
        if t["provider"] not in REGISTRY:
            raise HTTPException(400, f"مزوّد غير معروف: {t['provider']}")
    report = qa.run_qa(d, d.slides, app_settings.get_section(db, "generation").get("credit_source", True))
    if not report["passed"]:
        raise HTTPException(422, "لا يمكن النشر قبل إصلاح أخطاء فحص الجودة")
    d.publish_targets = targets
    when = body.scheduled_at
    if when and when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when and when > utcnow():
        problem = scheduling.check(db, when, d.id)
        if problem:
            raise HTTPException(409, problem)
        d.status, d.scheduled_at = "scheduled", when
        if d.calendar_item_id:
            from ..db import CalendarItem
            item = db.get(CalendarItem, d.calendar_item_id)
            if item:
                item.status = "scheduled"
        db.commit()
        return _full(db, d)
    d.status = "publishing"
    db.commit()
    background.add_task(publishing.publish_draft, d.id)
    return _full(db, d)


@router.post("/{draft_id}/unschedule")
def unschedule(draft_id: int, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    if d.status == "scheduled":
        d.status, d.scheduled_at = "approved", None
    return _full(db, d)


@router.delete("/{draft_id}")
def delete_draft(draft_id: int, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    for s in d.slides:
        if s.image_key:
            storage.delete(s.image_key)
    db.delete(d)
    return {"ok": True}


@router.get("/{draft_id}/download")
def download(draft_id: int, db: Session = Depends(get_db)):
    d = _get(db, draft_id)
    gen = app_settings.get_section(db, "generation")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in d.slides:
            if s.image_key:
                zf.writestr(f"slide-{s.position + 1}.jpg", storage.read_bytes(s.image_key))
        zf.writestr("caption.txt", pipeline.compose_caption(d, gen.get("credit_source", True)))
        if d.first_comment:
            zf.writestr("first-comment.txt", d.first_comment)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="post-{d.id}.zip"'})
