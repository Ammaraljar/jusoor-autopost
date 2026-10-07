"""Brand identity (visual + voice + publishing channels)."""
from __future__ import annotations

import base64
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import RequireUser, RequireWriter
from ..db import Brand, get_db
from ..services import palette as colours
from ..services import pipeline, storage
from ..services.renderer import SlideSpec, renderer

router = APIRouter(prefix="/api/brands", tags=["brands"], dependencies=[RequireUser, RequireWriter])
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
    card_style: str | None = Field(None, pattern="^(frosted|solid|band|side|ribbon|outline|minimal)$")
    card_theme: str | None = Field(None, pattern="^(magazine|classic)$")
    color_mode: str | None = Field(None, pattern="^(auto|brand)$")
    logo_backdrop: str | None = Field(None, pattern="^(auto|always|never)$")
    cta_text: str | None = None
    publish_config: dict[str, Any] | None = None


def _out(b: Brand) -> dict:
    data = b.to_dict()
    data["color_mode"] = b.color_mode or "auto"
    data["logo_backdrop"] = b.logo_backdrop or "auto"
    data["card_theme"] = b.card_theme or "magazine"
    return {**data, "logo_url": storage.public_url(b.logo_path) if b.logo_path else None}


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
    # The identity follows the logo at once: colours read from it drive every card and overlay
    from ..services import palette as colours
    if ext == "png":
        found = colours.colors_from_logo(data)
        if found:
            b.colors = {**(b.colors or {}), **found}
            b.color_mode = "auto"
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
    variant: int | None = None      # 0-5: one of the six JUSOOR colour sets / card shapes


SAMPLES = {
    "ar": {"cover": ("عنوان منشورك يظهر هنا بوضوح", "سطر قصير يشد المتابع للتمرير"),
           "content": ("فكرة واحدة واضحة", "كل شريحة تحمل فكرة واحدة بكلمات قليلة، والصورة تبقى هي البطل."),
           "cta": ("تواصل معنا اليوم", "فريقنا جاهز لمساعدتك")},
    "en": {"cover": ("Your headline shines here", "A short line that makes people swipe"),
           "content": ("One clear idea", "Each slide carries one idea in a few words — the photo stays the hero."),
           "cta": ("Get in touch today", "Our team is ready to help")},
    "ms": {"cover": ("Tajuk anda menyerlah di sini", "Satu baris ringkas yang buat orang terus leret"),
           "content": ("Satu idea yang jelas", "Setiap slaid membawa satu idea ringkas — foto kekal sebagai tumpuan."),
           "cta": ("Hubungi kami hari ini", "Pasukan kami sedia membantu")},
    "fr": {"cover": ("Votre titre brille ici", "Une phrase courte qui donne envie de glisser"),
           "content": ("Une idée claire", "Chaque slide porte une seule idée en quelques mots — la photo reste la star."),
           "cta": ("Contactez-nous aujourd’hui", "Notre équipe est prête à vous aider")},
}


@router.post("/{bid}/preview")
async def preview(bid: int, body: PreviewIn, db: Session = Depends(get_db)):
    """A sample slide in the company's own designs (variant = design number of its rotation)."""
    from ..db import current_org
    b = _get(db, bid)
    lang = body.language if body.language in SAMPLES else "ar"
    family = pipeline.family_of(db, current_org.get())
    style = pipeline.brand_style(b, lang, family)
    heading, text = SAMPLES[lang].get(body.kind, SAMPLES[lang]["cover"])
    if body.kind == "cta" and b.cta_text:
        heading = b.cta_text
    background = colours.sample_background(["cover", "content", "cta"][(body.variant or 0) % 3]
                                           if body.variant is not None else body.kind)
    navy = (b.colors or {}).get("navy") or colours.BRAND_NAVY
    gold = (b.colors or {}).get("gold") or colours.BRAND_GOLD
    style.palette = colours.design(body.variant or 0, navy, gold, b.design_seed or 0, family) \
        if (b.color_mode or "auto") == "auto" else {"family": family}
    plate = body.kind != "cta" and colours.logo_needs_plate(background, b.logo_placement or "top-left", lang == "ar")
    jpeg = await renderer.render(SlideSpec(kind=body.kind, heading=heading, body=text, position=1, total=6,
                                           background=background, logo_plate=plate,
                                           badge=None, credit="Reuters" if body.kind == "cover" else ""), style)
    return {"image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}
