"""News source management."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import RequireUser
from ..db import Article, Draft, Source, get_db
from ..services import pipeline, scraper
from ..services.jobs import jobs

router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=[RequireUser])

PRESETS = [
    {"name": "The Star - Travel", "kind": "website", "base_url": "https://www.thestar.com.my",
     "listing_urls": ["https://www.thestar.com.my/lifestyle/travel"], "category": "travel", "country": "Malaysia",
     "language": "en", "link_pattern": r"/lifestyle/travel/\d{4}/\d{2}/\d{2}/"},
    {"name": "The Star - Culture", "kind": "website", "base_url": "https://www.thestar.com.my",
     "listing_urls": ["https://www.thestar.com.my/lifestyle/culture"], "category": "culture", "country": "Malaysia",
     "language": "en", "link_pattern": r"/lifestyle/culture/\d{4}/\d{2}/\d{2}/"},
    {"name": "Travel Daily Media - Malaysia", "kind": "website", "base_url": "https://www.traveldailymedia.com",
     "listing_urls": ["https://www.traveldailymedia.com/category/asia-news/malaysia/"],
     "category": "travel", "country": "Malaysia", "language": "en",
     "link_selector": "h3.entry-title a",
     "link_pattern": r"^https://www\.traveldailymedia\.com/[a-zA-Z0-9-]+/?$",
     "body_selector": ".entry-content, .td-post-content"},
    {"name": "TripAdvisor - Top Destinations", "kind": "website", "base_url": "https://www.tripadvisor.com.my",
     "listing_urls": ["https://www.tripadvisor.com.my/TravelersChoice-Destinations-cTop-g2"],
     "category": "destinations", "country": "", "language": "en",
     "link_selector": "div.ui_columns a.b_title, a[href*=\"/Tourism-g\"]",
     "link_pattern": r"/Tourism-g\d+-[A-Za-z0-9_]+",
     "body_selector": "div.body_text, .ui_column div.p13n_description"},
]


class SourceIn(BaseModel):
    name: str = Field(min_length=2)
    kind: str = "website"
    base_url: str = ""
    feed_url: str | None = None
    listing_urls: list[str] = []
    link_selector: str | None = None
    link_pattern: str | None = None
    body_selector: str | None = None
    category: str = "travel"
    country: str = ""
    language: str = "en"
    priority: int = 5
    enabled: bool = True
    check_interval_minutes: int = Field(120, ge=15, le=10080)
    max_items_per_run: int = Field(5, ge=1, le=30)
    brand_id: int | None = None


class SourcePatch(BaseModel):
    model_config = {"extra": "ignore"}
    name: str | None = None
    kind: str | None = None
    base_url: str | None = None
    feed_url: str | None = None
    listing_urls: list[str] | None = None
    link_selector: str | None = None
    link_pattern: str | None = None
    body_selector: str | None = None
    category: str | None = None
    country: str | None = None
    language: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    check_interval_minutes: int | None = None
    max_items_per_run: int | None = None
    brand_id: int | None = None


def _validate(data: dict[str, Any]) -> None:
    if data.get("kind") == "rss" and not data.get("feed_url"):
        raise HTTPException(400, "رابط RSS مطلوب لمصادر RSS")
    if data.get("kind") == "website" and not (data.get("listing_urls") or data.get("base_url")):
        raise HTTPException(400, "أضف رابط صفحة الأخبار على الأقل")
    for key in ("base_url", "feed_url"):
        if data.get(key) and not str(data[key]).startswith(("http://", "https://")):
            raise HTTPException(400, f"{key} يجب أن يبدأ بـ https://")


def _with_stats(db: Session, s: Source) -> dict[str, Any]:
    articles = db.scalar(select(func.count()).select_from(Article).where(Article.source_id == s.id)) or 0
    drafts = db.scalar(select(func.count()).select_from(Draft).where(Draft.source_id == s.id)) or 0
    published = db.scalar(select(func.count()).select_from(Draft)
                          .where(Draft.source_id == s.id, Draft.status == "published")) or 0
    return {**s.to_dict(), "stats": {"articles": articles, "drafts": drafts, "published": published}}


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    return [_with_stats(db, s) for s in db.scalars(select(Source).order_by(Source.priority.desc(), Source.id))]


@router.get("/presets")
def presets():
    return PRESETS


@router.post("")
def create_source(body: SourceIn, db: Session = Depends(get_db)):
    data = body.model_dump()
    _validate(data)
    s = Source(**data)
    db.add(s)
    db.flush()
    return _with_stats(db, s)


@router.post("/import")
def import_sources(items: list[SourceIn], db: Session = Depends(get_db)):
    created = 0
    for item in items:
        data = item.model_dump()
        _validate(data)
        exists = db.scalar(select(Source.id).where(Source.name == data["name"]))
        if not exists:
            db.add(Source(**data))
            created += 1
    return {"created": created}


@router.post("/test")
def test_unsaved(body: SourceIn):
    data = body.model_dump()
    _validate(data)
    return scraper.test_source(Source(**data))


@router.get("/{source_id}")
def get_source(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404, "المصدر غير موجود")
    return _with_stats(db, s)


@router.patch("/{source_id}")
def update_source(source_id: int, body: SourcePatch, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404, "المصدر غير موجود")
    changes = body.model_dump(exclude_unset=True)
    merged = {**s.to_dict(), **changes}
    _validate(merged)
    for k, v in changes.items():
        setattr(s, k, v)
    return _with_stats(db, s)


@router.delete("/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404, "المصدر غير موجود")
    db.delete(s)
    return {"ok": True}


@router.post("/{source_id}/test")
def test_source(source_id: int, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404, "المصدر غير موجود")
    return scraper.test_source(s)


@router.post("/{source_id}/scrape")
async def scrape_now(source_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    if not db.get(Source, source_id):
        raise HTTPException(404, "المصدر غير موجود")
    if jobs.busy:
        raise HTTPException(409, "توجد عملية سحب قيد التنفيذ")
    background.add_task(jobs.run_collection, [source_id])
    return {"ok": True, "started": True}


@router.get("/{source_id}/articles")
def source_articles(source_id: int, limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(select(Article).where(Article.source_id == source_id)
                      .order_by(Article.fetched_at.desc()).limit(min(limit, 200)))
    return [{k: v for k, v in a.to_dict().items() if k != "body"} for a in rows]


@router.post("/articles/{article_id}/draft")
async def draft_article(article_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    art = db.get(Article, article_id)
    if not art:
        raise HTTPException(404, "المقال غير موجود")
    art.status = "new"
    db.commit()
    background.add_task(pipeline.draft_from_article, article_id)
    return {"ok": True}
