"""Brand identity (visual + voice + publishing channels)."""
from __future__ import annotations

import base64
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import RequireUser
from ..db import Brand, get_db
from ..services import pipeline, storage
from ..services.renderer import SlideSpec, renderer

router = APIRouter(prefix="/api/brands", tags=["brands"], dependencies=[RequireUser])
FONTS = ["Cairo"]


class BrandIn(BaseModel):
    model_config = {"extra": "ignore"}
    name: str | None = Field(None, min_length=2)
    handle: str | None = None
    website: str | None = None
    voice: str | None = None
    colors: dict[str, str] | None = None
    font_family: str | None = None
    logo_placement: str | None = Field(None, pattern="^(top-left|top-right)$")
    card_style: str | None = Field(None, pattern="^(frosted|solid|minimal)$")
    cta_text: str | None = None
    publish_config: dict[str, Any] | None = None


def _out(b: Brand) -> dict:
    return {**b.to_dict(), "logo_url": storage.public_url(b.logo_path) if b.logo_path else None}


@router.get("")
def list_brands(db: Session = Depends(get_db)):
    pipeline.ensure_default_brand(db)
    return [_out(b) for b in db.scalars(select(Brand).order_by(Brand.is_default.desc(), Brand.id))]


@router.post("")
def create_brand(body: BrandIn, db: Session = Depends(get_db)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data.get("name"):
        raise HTTPException(400, "اسم العلامة مطلوب")
    base = dict(pipeline.JUSOOR_DEFAULT_BRAND)
    base.update(is_default=False, voice="", cta_text="")
    base.update(data)
    b = Brand(**base)
    db.add(b)
    db.flush()
    return _out(b)


def _get(db: Session, bid: int) -> Brand:
    b = db.get(Brand, bid)
    if not b:
        raise HTTPException(404, "العلامة غير موجودة")
    return b


@router.patch("/{bid}")
def update_brand(bid: int, body: BrandIn, db: Session = Depends(get_db)):
    b = _get(db, bid)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(b, k, v)
    return _out(b)


@router.post("/{bid}/default")
def make_default(bid: int, db: Session = Depends(get_db)):
    target = _get(db, bid)
    for b in db.scalars(select(Brand)):
        b.is_default = b.id == target.id
    return _out(target)


@router.delete("/{bid}")
def delete_brand(bid: int, db: Session = Depends(get_db)):
    b = _get(db, bid)
    if b.is_default:
        raise HTTPException(400, "لا يمكن حذف العلامة الافتراضية")
    db.delete(b)
    return {"ok": True}


@router.post("/{bid}/logo")
async def upload_logo(bid: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    b = _get(db, bid)
    if file.content_type not in ("image/png", "image/svg+xml"):
        raise HTTPException(400, "ارفع الشعار بصيغة PNG شفافة أو SVG")
    data = await file.read()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(400, "الحد الأقصى 3 ميغابايت")
    ext = "svg" if file.content_type == "image/svg+xml" else "png"
    key = f"brand/logo-{b.id}-{uuid.uuid4().hex[:8]}.{ext}"
    storage.save_bytes(key, data, file.content_type)
    if b.logo_path:
        storage.delete(b.logo_path)
    b.logo_path = key
    return _out(b)


@router.delete("/{bid}/logo")
def remove_logo(bid: int, db: Session = Depends(get_db)):
    b = _get(db, bid)
    if b.logo_path:
        storage.delete(b.logo_path)
    b.logo_path = None
    return _out(b)


class PreviewIn(BaseModel):
    kind: str = "cover"
    language: str = "ar"


@router.post("/{bid}/preview")
async def preview(bid: int, body: PreviewIn, db: Session = Depends(get_db)):
    b = _get(db, bid)
    style = pipeline.brand_style(b, body.language)
    samples = {
        "cover": ("بينانغ بعد ٢٢ عامًا... جزيرة تسرق القلب", "دليلك لأجمل ما تغيّر في الجزيرة"),
        "content": ("ما الجديد؟", "مقاهٍ تراثية، وشوارع فنية، وأسواق ليلية تجعل من جورج تاون وجهة مثالية للعائلات."),
        "cta": (b.cta_text or "خطّط رحلتك القادمة معنا", "فريقنا جاهز لمساعدتك"),
    }
    heading, text = samples.get(body.kind, samples["cover"])
    jpeg = await renderer.render(SlideSpec(kind=body.kind, heading=heading, body=text, position=0, total=6,
                                           badge="news" if body.kind == "cover" else None,
                                           credit="The Star" if body.kind != "cta" else ""), style)
    return {"image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}
