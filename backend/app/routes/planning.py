"""Campaigns and content calendar."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import RequireUser
from ..db import CalendarItem, Campaign, Draft, get_db
from ..services import pipeline

router = APIRouter(prefix="/api", tags=["planning"], dependencies=[RequireUser])


class CampaignIn(BaseModel):
    name: str = Field(min_length=2)
    objective: str = ""
    color: str = "#C6A23C"
    start_date: date | None = None
    end_date: date | None = None
    notes: str = ""
    brand_id: int | None = None


def _campaign(db: Session, c: Campaign) -> dict:
    rows = dict(db.execute(select(Draft.status, func.count()).where(Draft.campaign_id == c.id)
                           .group_by(Draft.status)).all())
    planned = db.scalar(select(func.count()).select_from(CalendarItem).where(CalendarItem.campaign_id == c.id)) or 0
    return {**c.to_dict(), "stats": {"drafts": sum(rows.values()), "published": rows.get("published", 0),
                                     "scheduled": rows.get("scheduled", 0), "planned": planned}}


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return [_campaign(db, c) for c in db.scalars(select(Campaign).order_by(Campaign.id.desc()))]


@router.post("/campaigns")
def create_campaign(body: CampaignIn, db: Session = Depends(get_db)):
    if body.start_date and body.end_date and body.end_date < body.start_date:
        raise HTTPException(400, "تاريخ النهاية قبل تاريخ البداية")
    c = Campaign(**body.model_dump())
    db.add(c)
    db.flush()
    return _campaign(db, c)


@router.patch("/campaigns/{cid}")
def update_campaign(cid: int, body: CampaignIn, db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "الحملة غير موجودة")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    return _campaign(db, c)


@router.delete("/campaigns/{cid}")
def delete_campaign(cid: int, db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "الحملة غير موجودة")
    db.delete(c)
    return {"ok": True}


class AssignBody(BaseModel):
    campaign_id: int | None
    draft_ids: list[int]


@router.post("/campaigns/assign")
def assign(body: AssignBody, db: Session = Depends(get_db)):
    for did in body.draft_ids:
        d = db.get(Draft, did)
        if d:
            d.campaign_id = body.campaign_id
    return {"ok": True}


class CalendarIn(BaseModel):
    date: date
    time: str = Field("10:00", pattern=r"^\d{2}:\d{2}$")
    topic: str = Field(min_length=3)
    notes: str = ""
    content_type: str = "travel"
    platform: str = "instagram"
    campaign_id: int | None = None
    brand_id: int | None = None


@router.get("/calendar")
def calendar(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    start = start or today.replace(day=1)
    end = end or (start + timedelta(days=42))
    items = db.scalars(select(CalendarItem).where(CalendarItem.date >= start, CalendarItem.date <= end)
                       .order_by(CalendarItem.date, CalendarItem.time))
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
    scheduled = db.scalars(select(Draft).where(Draft.scheduled_at >= start_dt, Draft.scheduled_at <= end_dt,
                                               Draft.status.in_(["scheduled", "published", "failed"])))
    published = db.scalars(select(Draft).where(Draft.published_at >= start_dt, Draft.published_at <= end_dt,
                                               Draft.scheduled_at.is_(None)))
    posts = {}
    for d in list(scheduled) + list(published):
        posts[d.id] = {"id": d.id, "hook": d.hook, "status": d.status, "campaign_id": d.campaign_id,
                       "at": d.to_dict()["scheduled_at"] or d.to_dict()["published_at"],
                       "cover_url": d.slides[0].image_url if d.slides else None}
    return {"start": start.isoformat(), "end": end.isoformat(),
            "items": [i.to_dict() for i in items], "posts": list(posts.values())}


@router.post("/calendar")
def create_item(body: CalendarIn, db: Session = Depends(get_db)):
    item = CalendarItem(**body.model_dump())
    db.add(item)
    db.flush()
    return item.to_dict()


@router.patch("/calendar/{item_id}")
def update_item(item_id: int, body: CalendarIn, db: Session = Depends(get_db)):
    item = db.get(CalendarItem, item_id)
    if not item:
        raise HTTPException(404, "العنصر غير موجود")
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    return item.to_dict()


@router.delete("/calendar/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(CalendarItem, item_id)
    if not item:
        raise HTTPException(404, "العنصر غير موجود")
    db.delete(item)
    return {"ok": True}


@router.post("/calendar/{item_id}/generate")
async def generate_item(item_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    item = db.get(CalendarItem, item_id)
    if not item:
        raise HTTPException(404, "العنصر غير موجود")
    if item.draft_id and db.get(Draft, item.draft_id):
        raise HTTPException(409, "تم توليد مسودة لهذا الموضوع مسبقًا")
    background.add_task(pipeline.draft_from_calendar, item.id)
    return {"ok": True}
