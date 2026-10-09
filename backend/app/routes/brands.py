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
from ..services import fonts as font_lib  # noqa: E402


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
    templates: list[str] | None = None
    font_latin: str | None = None


def _out(b: Brand) -> dict:
    data = b.to_dict()
    data["color_mode"] = b.color_mode or "auto"
    data["logo_backdrop"] = b.logo_backdrop or "auto"
    data["card_theme"] = b.card_theme or "magazine"
    data["font_latin"] = b.font_latin or "Cairo"
    data["font_options"] = font_lib.options()
    data["has_default_colors"] = bool(b.default_colors or b.logo_path)
    data["colors"] = colours.complete_colors(b.colors)
    data["logos"] = [{**x, "url": storage.public_url(x["key"]), "primary": x["key"] == b.logo_path}
                     for x in pipeline.brand_logos(b)]
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
    data = body.model_dump(exclude_unset=True)
    if data.get("font_family") is not None:
        data["font_family"] = font_lib.valid_arabic(data["font_family"])
    if data.get("font_latin") is not None:
        data["font_latin"] = font_lib.valid_latin(data["font_latin"])
    if data.get("templates") is not None:
        data["templates"] = [t for t in data["templates"] if t in colours.TEMPLATES]
    if data.get("colors") is not None:
        # roles that still follow the old main colours move with the new ones (title, text, card…)
        data["colors"] = colours.complete_colors(data["colors"], colours.complete_colors(b.colors))
    for k, v in data.items():
        if v is not None:
            setattr(b, k, v)
    return _out(b)


@router.post("/{bid}/colors/reset")
def reset_colors(bid: int, db: Session = Depends(get_db)):
    """Back to the identity generated from the primary colour logo (or the field's colours)."""
    from ..db import Organization, current_org
    from ..services import industries
    b = _get(db, bid)
    base = b.default_colors
    if not base and b.logo_path:
        data = storage.read_bytes(b.logo_path)
        base = colours.colors_from_logo(data) if data and colours.logo_tone(data) == "color" else None
    if not base:
        org = db.get(Organization, current_org.get()) if current_org.get() else None
        base = dict(industries.get(org.industry if org else None).get("colors") or {})
    b.colors = colours.complete_colors(base)
    b.color_mode = "auto"
    return _out(b)


@router.get("/{bid}/templates")
def templates(bid: int, db: Session = Depends(get_db)):
    """The card templates of the company's field, and which ones it keeps."""
    from ..db import current_org
    from ..services import cards
    b = _get(db, bid)
    return cards.template_options(pipeline.family_of(db, current_org.get()), b.templates)


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


LOGO_TYPES = {"image/png": "png", "image/svg+xml": "svg", "image/webp": "webp"}


def _set_primary(b: Brand, key: str, data: bytes | None) -> None:
    """The primary logo drives the brand identity: its colours become the brand colours."""
    b.logo_path = key
    if data and not data.lstrip().startswith(b"<"):
        found = colours.colors_from_logo(data)
        if found and colours.logo_tone(data) == "color":
            b.colors = colours.complete_colors(found)
            b.default_colors = dict(b.colors)          # the identity "reset" returns to
            b.color_mode = "auto"


async def _store_logo(b: Brand, file: UploadFile) -> dict:
    if file.content_type not in LOGO_TYPES:
        raise HTTPException(400, "ارفع الشعار بصيغة PNG شفافة أو SVG أو WEBP")
    data = await file.read()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(400, "الحد الأقصى 3 ميغابايت للشعار")
    key = f"brand/logo-{b.id}-{uuid.uuid4().hex[:8]}.{LOGO_TYPES[file.content_type]}"
    storage.save_bytes(key, data, file.content_type)
    item = {"key": key, "tone": colours.logo_tone(data), "name": (file.filename or "")[:80]}
    logos = pipeline.brand_logos(b)
    logos.append(item)
    b.logos = logos
    if not b.logo_path:
        _set_primary(b, key, data)
    return item


@router.post("/{bid}/logos")
async def upload_logos(bid: int, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    """Add one or more versions of the logo (colour, white, dark…). The tone of each is detected,
    and the slide renderer picks the version that reads best on each photo."""
    b = _get(db, bid)
    if len(files) > 8:
        raise HTTPException(400, "حتى 8 نسخ من الشعار")
    for f in files:
        await _store_logo(b, f)
    return _out(b)


@router.post("/{bid}/logo")
async def upload_logo(bid: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Older single-logo upload: adds the file and makes it the primary logo."""
    b = _get(db, bid)
    item = await _store_logo(b, file)
    _set_primary(b, item["key"], storage.read_bytes(item["key"]))
    return _out(b)


class LogoPatch(BaseModel):
    key: str
    tone: str | None = Field(None, pattern="^(color|light|dark)$")
    primary: bool | None = None


@router.patch("/{bid}/logos")
def update_logo(bid: int, body: LogoPatch, db: Session = Depends(get_db)):
    b = _get(db, bid)
    logos = pipeline.brand_logos(b)
    item = next((x for x in logos if x["key"] == body.key), None)
    if item is None:
        raise HTTPException(404, "الشعار غير موجود")
    if body.tone:
        item["tone"] = body.tone
    b.logos = logos
    if body.primary:
        _set_primary(b, item["key"], storage.read_bytes(item["key"]))
    return _out(b)


@router.delete("/{bid}/logos")
def delete_logo(bid: int, key: str, db: Session = Depends(get_db)):
    b = _get(db, bid)
    logos = pipeline.brand_logos(b)
    if not any(x["key"] == key for x in logos):
        raise HTTPException(404, "الشعار غير موجود")
    storage.delete(key)
    logos = [x for x in logos if x["key"] != key]
    b.logos = logos
    if b.logo_path == key:
        b.logo_path = logos[0]["key"] if logos else None
    return _out(b)


@router.delete("/{bid}/logo")
def remove_logo(bid: int, db: Session = Depends(get_db)):
    """Remove every version of the logo."""
    b = _get(db, bid)
    for x in pipeline.brand_logos(b):
        storage.delete(x["key"])
    b.logo_path = None
    b.logos = []
    return _out(b)


class PreviewIn(BaseModel):
    kind: str = "cover"
    language: str = "ar"
    template: str | None = None
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
    style.palette = colours.design(body.variant or 0, navy, gold, b.design_seed or 0, family, b.templates,
                                   body.template,
                                   exact=None if (b.color_mode or "auto") == "auto" else (b.colors or {}))
    if body.template:
        style.theme = "magazine"          # a template preview always shows that template
    logo, plate = colours.choose_logo(style.logos, style.logo, background, b.logo_placement or "top-left",
                                      body.kind, (style.palette or {}).get("template"))
    jpeg = await renderer.render(SlideSpec(kind=body.kind, heading=heading, body=text, position=1, total=6,
                                           background=background, logo_plate=plate, logo=logo,
                                           badge=None, credit="Reuters" if body.kind == "cover" else ""), style)
    return {"image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}
