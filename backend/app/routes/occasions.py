"""Occasions: the year's calendar of greetings for the company's countries, and their posts."""
from __future__ import annotations

from datetime import date
from datetime import date as Day

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import RequireUser, RequireWriter
from ..db import Occasion, get_db
from ..services import app_settings, occasions
from ..services import occasions_data as data

router = APIRouter(prefix="/api/occasions", tags=["occasions"], dependencies=[RequireUser, RequireWriter])


def _year(year: int | None) -> int:
    year = year or date.today().year
    if not 2000 <= year <= 2100:
        raise HTTPException(400, "سنة غير صحيحة")
    return year


@router.get("")
def list_occasions(year: int | None = None, db: Session = Depends(get_db)):
    year = _year(year)
    rows = db.scalars(select(Occasion).where(or_(Occasion.year == year, Occasion.year.is_(None)))
                      .order_by(Occasion.date.is_(None).desc(), Occasion.date, Occasion.id)).all()
    today = date.today()
    return {"year": year, "settings": occasions.settings(db), "countries": occasions.countries_catalog(),
            "kinds": list(data.KINDS), "tones": list(data.TONES),
            "items": [occasions.item_view(db, r, today) for r in rows]}


class SettingsIn(BaseModel):
    countries: list[str] | None = None
    kinds: dict[str, bool] | None = None
    auto_create: bool | None = None
    lead_days: int | None = Field(default=None, ge=0, le=30)
    auto_schedule: bool | None = None
    post_time: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    dialect_by_country: bool | None = None


@router.put("/settings")
def save_settings(body: SettingsIn, db: Session = Depends(get_db)):
    values = body.model_dump(exclude_none=True)
    if "countries" in values:
        values["countries"] = [c for c in dict.fromkeys(values["countries"]) if c in data.COUNTRIES][:30]
    if "kinds" in values:
        values["kinds"] = {k: bool(values["kinds"].get(k, True)) for k in data.KINDS if k != "custom"}
    return app_settings.update_section(db, "occasions", values)


class ImportIn(BaseModel):
    year: int | None = None


@router.post("/import")
def import_occasions(body: ImportIn, db: Session = Depends(get_db)):
    year = _year(body.year)
    if not occasions.settings(db).get("countries"):
        raise HTTPException(400, "اختر الدول التي تستهدفها أولًا")
    return occasions.import_year(db, year)


class OccasionIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    name_en: str = Field(default="", max_length=200)
    date: Day | None = None
    recurrence: str = "once"
    weekday: int | None = Field(default=None, ge=0, le=6)
    kind: str = "custom"
    tone: str = "festive"
    motif: str = "sparkle"
    countries: list[str] = []
    number: int | None = Field(default=None, ge=0, le=5000)
    notes: str = Field(default="", max_length=2000)
    post_time: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")


@router.post("")
def create_occasion(body: OccasionIn, db: Session = Depends(get_db)):
    values = body.model_dump()
    if values["kind"] not in data.KINDS:
        values["kind"] = "custom"
    try:
        row = occasions.new_custom(db, values)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return occasions.item_view(db, row)


class OccasionPatch(BaseModel):
    enabled: bool | None = None
    name_ar: str | None = Field(default=None, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    date: Day | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    number: int | None = Field(default=None, ge=0, le=5000)
    clear_number: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    post_time: str | None = Field(default=None, pattern=r"^(\d{1,2}:\d{2})?$")
    countries: list[str] | None = None
    tone: str | None = None


def _get(db: Session, oid: int) -> Occasion:
    row = db.get(Occasion, oid)
    if row is None:
        raise HTTPException(404, "المناسبة غير موجودة")
    return row


@router.patch("/{oid}")
def update_occasion(oid: int, body: OccasionPatch, db: Session = Depends(get_db)):
    row = _get(db, oid)
    values = body.model_dump(exclude_none=True)
    for key in ("name_ar", "name_en", "date", "weekday", "number"):
        if key in values and values[key] != getattr(row, key):
            setattr(row, key, values[key])
            row.edited = True
    if values.get("clear_number"):
        row.number, row.edited = None, True
    if "date" in values:
        row.year = values["date"].year if row.recurrence != "weekly" else None
        row.hijri = occasions.hijri_label(values["date"])
    for key in ("enabled", "notes"):
        if key in values:
            setattr(row, key, values[key])
    if "post_time" in values:
        row.post_time = values["post_time"] or None
    if "countries" in values:
        row.countries = [c for c in values["countries"] if c in data.COUNTRIES]
    if values.get("tone") in data.TONES:
        row.tone = values["tone"]
    db.flush()
    return occasions.item_view(db, row)


class BulkIn(BaseModel):
    ids: list[int]
    enabled: bool


@router.post("/bulk")
def bulk(body: BulkIn, db: Session = Depends(get_db)):
    rows = db.scalars(select(Occasion).where(Occasion.id.in_(body.ids))).all()
    for r in rows:
        r.enabled = body.enabled
    return {"ok": True, "done": len(rows)}


@router.delete("/{oid}")
def delete_occasion(oid: int, db: Session = Depends(get_db)):
    row = _get(db, oid)
    if row.source != "custom":
        raise HTTPException(400, "مناسبات الدول لا تُحذف — أوقفها بدلًا من ذلك")
    db.delete(row)
    return {"ok": True}


class PostIn(BaseModel):
    date: Day | None = None


@router.post("/{oid}/post")
def create_post(oid: int, body: PostIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    row = _get(db, oid)
    on = body.date or (occasions.next_dates(row, date.today()) or [row.date])[0]
    if on is None:
        raise HTTPException(400, "حدّد تاريخ المنشور")
    db.commit()
    try:
        draft_id = occasions.create_post_draft(row.id, on)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    background.add_task(occasions.finish_post, draft_id)
    return {"ok": True, "draft_id": draft_id}


@router.get("/preview")
def preview(year: int | None = None, countries: str = "", db: Session = Depends(get_db)):
    """What an import would bring for these countries (nothing is stored)."""
    from ..db import Organization, current_org
    org = db.get(Organization, current_org.get()) if current_org.get() else None
    items = occasions.compute(_year(year), [c for c in countries.split(",") if c], org.industry if org else None)
    return {"count": len(items), "items": [{**i, "date": i["date"].isoformat() if i["date"] else None}
                                           for i in items[:400]]}
