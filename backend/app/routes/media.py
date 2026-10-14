"""The company's photo library: upload, add by link (Google Drive, Dropbox, photo sites), tag, delete."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import RequireUser, RequireWriter
from ..db import MediaAsset, get_db, session_scope, utcnow
from ..services import app_settings, media, storage, tasks

router = APIRouter(prefix="/api/media", tags=["media"], dependencies=[RequireUser, RequireWriter])
MAX_FILES = 30
MAX_LINKS = 30


def _out(a: MediaAsset) -> dict:
    return a.to_dict()


@router.get("")
def list_media(q: str = "", db: Session = Depends(get_db)):
    stmt = select(MediaAsset).order_by(MediaAsset.created_at.desc())
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(MediaAsset.tags.ilike(like), MediaAsset.title.ilike(like)))
    return [_out(a) for a in db.scalars(stmt.limit(1000))]


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...), tags: str = Form(""), title: str = Form(""),
                 db: Session = Depends(get_db)):
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"الحد الأقصى {MAX_FILES} صورة في المرة الواحدة")
    added, errors = [], []
    for f in files:
        data = await f.read()
        try:
            name = title or (f.filename or "").rsplit(".", 1)[0]
            asset = await asyncio.to_thread(media.add_image, db, data, name, tags)
            added.append(_out(asset))
        except ValueError as exc:
            errors.append({"name": f.filename, "error": str(exc)})
    if not added and errors:
        raise HTTPException(400, errors[0]["error"])
    return {"added": added, "errors": errors}


class LinksIn(BaseModel):
    urls: list[str] = Field(min_length=1)
    tags: str = ""
    title: str = ""


@router.post("/links")
async def add_links(body: LinksIn, db: Session = Depends(get_db)):
    urls = [u.strip() for u in body.urls if u.strip().startswith(("http://", "https://"))][:MAX_LINKS]
    if not urls:
        raise HTTPException(400, "أضف روابط تبدأ بـ https://")
    added, errors = [], []
    for url in urls:
        try:
            data, _final = await asyncio.to_thread(media.fetch_link, url)
            asset = await asyncio.to_thread(media.add_image, db, data, body.title, body.tags, url)
            added.append(_out(asset))
        except Exception as exc:  # noqa: BLE001
            msg = str(exc) if isinstance(exc, ValueError) else "تعذّر تحميل الصورة — تأكد أن الرابط عام (أي شخص لديه الرابط)"
            errors.append({"url": url, "error": msg})
    if not added and errors:
        raise HTTPException(400, errors[0]["error"])
    return {"added": added, "errors": errors}


class AssetPatch(BaseModel):
    title: str | None = None
    tags: str | None = None


def _get(db: Session, aid: int) -> MediaAsset:
    a = db.get(MediaAsset, aid)
    if a is None:
        raise HTTPException(404, "الصورة غير موجودة")
    return a


@router.patch("/{aid}")
def update_asset(aid: int, body: AssetPatch, db: Session = Depends(get_db)):
    a = _get(db, aid)
    if body.title is not None:
        a.title = body.title.strip()[:200]
    if body.tags is not None:
        a.tags = media.normalise_tags(body.tags)
    return _out(a)


def _remove(db: Session, a: MediaAsset) -> None:
    if a.key:
        try:
            storage.delete(a.key)
        except Exception:  # noqa: BLE001
            pass
    db.delete(a)


@router.delete("/{aid}")
def delete_asset(aid: int, db: Session = Depends(get_db)):
    _remove(db, _get(db, aid))
    return {"ok": True}


class BulkDelete(BaseModel):
    ids: list[int] = Field(min_length=1)


@router.post("/bulk-delete")
def bulk_delete(body: BulkDelete, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(MediaAsset).where(MediaAsset.id.in_(body.ids))))
    for a in rows:
        _remove(db, a)
    return {"deleted": len(rows)}


# ---------------------------------------------------------------- connected libraries
class ImportIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    tags: str = ""
    title: str = ""
    keep: bool = True            # remember the library so it can be synced again


def _sources(db: Session) -> list[dict]:
    return list(app_settings.get_section(db, "media").get("sources") or [])


def _remember(url: str, kind: str, tags: str, title: str, result: dict) -> None:
    with session_scope() as db:
        sources = [s for s in _sources(db) if s.get("url") != url]
        old = next((s for s in _sources(db) if s.get("url") == url), {})
        sources.append({"url": url, "kind": kind, "tags": tags, "title": title, "last_sync": utcnow().isoformat(),
                        "count": int(old.get("count") or 0) + result["added"]})
        app_settings.update_section(db, "media", {"sources": sources[-30:]})


def _start_import(background: BackgroundTasks, url: str, tags: str, title: str, keep: bool) -> dict:
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "أضف رابطًا يبدأ بـ https://")
    job_id = tasks.new()

    async def work() -> dict:
        def run() -> dict:
            with session_scope() as db:
                return media.import_library(db, url, tags, title)
        result = await asyncio.to_thread(run)
        if keep and result["kind"] != "image":
            _remember(url, result["kind"], tags, title, result)
        return result
    background.add_task(tasks.run, job_id, work, "انتهت المهلة — المكتبة كبيرة أو بطيئة، جرّب مجلدًا أصغر")
    return {"job": job_id, "status": "running"}


@router.post("/import")
def import_library(body: ImportIn, background: BackgroundTasks):
    """Import a whole library: Dropbox / Google Drive folder, OneDrive, Google Photos album, gallery page."""
    return _start_import(background, body.url.strip(), body.tags, body.title, body.keep)


@router.get("/import/{job_id}")
def import_status(job_id: str):
    job = tasks.get(job_id)
    if job is None:
        raise HTTPException(404, "انتهت صلاحية العملية — أعد المحاولة")
    return job


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    return _sources(db)


class SourceRef(BaseModel):
    url: str


@router.post("/sources/sync")
def sync_source(body: SourceRef, background: BackgroundTasks, db: Session = Depends(get_db)):
    src = next((s for s in _sources(db) if s.get("url") == body.url), None)
    if src is None:
        raise HTTPException(404, "المكتبة غير موجودة")
    return _start_import(background, src["url"], src.get("tags", ""), src.get("title", ""), True)


@router.post("/sources/remove")
def remove_source(body: SourceRef, db: Session = Depends(get_db)):
    app_settings.update_section(db, "media", {"sources": [s for s in _sources(db) if s.get("url") != body.url]})
    return {"ok": True}
