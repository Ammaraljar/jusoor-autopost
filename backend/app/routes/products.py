"""Products, services, courses and offers from the company's own website → one post each."""
from __future__ import annotations


from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import RequireUser, RequireWriter
from ..db import Brand, Product, get_db, session_scope, utcnow
from ..services import app_settings, pipeline, products, tasks

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[RequireUser, RequireWriter])


@router.get("")
def list_products(db: Session = Depends(get_db)):
    return [p.to_dict() for p in db.scalars(select(Product).order_by(Product.status, Product.id.desc()))]


class SyncIn(BaseModel):
    url: str | None = None


def _save(found: dict) -> dict:
    added = updated = 0
    with session_scope() as db:
        for item in found["items"]:
            row = db.scalar(select(Product).where(Product.url == item["url"]))
            if row is None:
                db.add(Product(**{k: item.get(k) for k in ("url", "name", "description", "price", "currency",
                                                           "image_url", "kind", "origin")}))
                added += 1
            else:
                for k in ("name", "description", "price", "currency", "image_url", "kind"):
                    if item.get(k):
                        setattr(row, k, item[k])
                row.updated_at = utcnow()
                updated += 1
    return {"found": len(found["items"]), "added": added, "updated": updated, "method": found.get("method"),
            "blocked": bool(found.get("blocked")) and not found["items"]}


@router.post("/sync")
async def sync(body: SyncIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Read any link (a site, a listing page or one product page) and add what is new — as a job
    (a JavaScript site is opened in a headless browser, which can take a minute)."""
    url = (body.url or "").strip()
    if not url:
        brand = db.scalar(select(Brand).order_by(Brand.is_default.desc(), Brand.id))
        url = (brand.website or "").strip() if brand else ""
    if not url:
        raise HTTPException(400, "أضف رابط موقعك الإلكتروني (أو احفظه في الهوية البصرية أولًا)")
    lang = app_settings.get_section(db, "generation").get("language", "ar")
    job_id = tasks.new()

    async def work() -> dict:
        return _save(await products.discover_full(url, lang))
    background.add_task(tasks.run, job_id, work, "انتهت المهلة: الموقع بطيء جدًا أو يمنع القراءة الآلية")
    return {"job": job_id, "status": "running"}


@router.get("/sync/{job_id}")
def sync_status(job_id: str):
    job = tasks.get(job_id)
    if job is None:
        raise HTTPException(404, "انتهت صلاحية العملية — أعد المحاولة")
    return job


def _get(db: Session, pid: int) -> Product:
    p = db.get(Product, pid)
    if p is None:
        raise HTTPException(404, "المنتج غير موجود")
    return p


class PostIn(BaseModel):
    schedule: bool = False          # put the post on the plan (next free time) once it is ready


async def _post(pid: int, schedule: bool) -> None:
    draft_id = await pipeline.draft_from_product(pid)
    if draft_id and schedule:
        from ..services import scheduling
        with session_scope() as db:
            from ..db import Draft
            d = db.get(Draft, draft_id)
            if d is not None and d.status == "pending_review":
                try:
                    scheduling.schedule(db, d)
                except ValueError as exc:
                    pipeline._fail_soft(draft_id, f"لم يُجدول تلقائيًا: {exc}")


@router.post("/{pid}/draft")
def make_post(pid: int, background: BackgroundTasks, body: PostIn | None = None, db: Session = Depends(get_db)):
    p = _get(db, pid)
    p.status = "drafted"
    db.commit()
    background.add_task(_post, pid, bool(body and body.schedule))
    return {"ok": True}


class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    action: str = Field(pattern="^(draft|schedule|skip|restore|delete)$")


@router.post("/bulk")
async def bulk(body: BulkIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Product).where(Product.id.in_(body.ids))))
    for p in rows:
        if body.action == "delete":
            db.delete(p)
        elif body.action == "skip":
            p.status = "skipped"
        elif body.action == "restore":
            p.status = "new"
        else:
            p.status = "drafted"
    db.commit()
    if body.action in ("draft", "schedule"):
        async def run_all(ids: list[int]) -> None:
            for i in ids:                      # one after another: AI limits stay happy
                await _post(i, body.action == "schedule")
        background.add_task(run_all, [p.id for p in rows])
    return {"done": len(rows)}


@router.delete("/{pid}")
def delete(pid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, pid))
    return {"ok": True}
