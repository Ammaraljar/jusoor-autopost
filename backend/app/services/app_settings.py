"""Editable application settings stored in the database (non-secret)."""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from ..db import AppSetting

LANGUAGES = ["ar", "en", "fr"]
TONES = ["friendly", "professional", "luxury", "emotional", "bold", "educational", "corporate", "storytelling"]
CONTENT_TYPES = ["news", "travel", "tips", "educational", "promotional", "storytelling",
                 "announcement", "corporate", "comparison", "event", "product"]
PLATFORMS = ["instagram", "facebook", "linkedin", "tiktok", "x", "threads"]
PROVIDERS = ["buffer", "meta", "uploadpost"]

DEFAULTS: dict[str, dict[str, Any]] = {
    "generation": {
        "language": "ar",
        "tone": "friendly",
        "content_type": "news",
        "platform": "instagram",
        "audience": "مسافرون عرب من الخليج والشرق الأوسط مهتمون بماليزيا وجنوب شرق آسيا",
        "objective": "بناء الثقة وزيادة التفاعل وتوجيه المتابعين لحجز رحلاتهم مع جسور",
        "min_relevance": 6,
        "content_slides": 4,
        "image_source": "auto",     # auto | source | pexels
        "credit_source": True,
    },
    "scheduler": {
        "scrape_enabled": True,
        "max_article_age_days": 3,
        "max_drafts_per_run": 10,
    },
    "publishing": {
        "default_provider": "buffer",
        "default_platforms": ["instagram", "facebook"],
        "first_comment_enabled": False,
        "buffer_mode": "shareNow",
    },
}


def get_section(db: Session, key: str) -> dict[str, Any]:
    row = db.get(AppSetting, key)
    merged = copy.deepcopy(DEFAULTS.get(key, {}))
    if row and isinstance(row.value, dict):
        merged.update(row.value)
    return merged


def update_section(db: Session, key: str, values: dict[str, Any]) -> dict[str, Any]:
    if key not in DEFAULTS:
        raise KeyError(key)
    allowed = {k: v for k, v in values.items() if k in DEFAULTS[key]}
    row = db.get(AppSetting, key)
    current = dict(row.value) if row and isinstance(row.value, dict) else {}
    current.update(allowed)
    if row:
        row.value = current
    else:
        db.add(AppSetting(key=key, value=current))
    db.flush()
    return get_section(db, key)


def options() -> dict[str, list[str]]:
    return {"languages": LANGUAGES, "tones": TONES, "content_types": CONTENT_TYPES,
            "platforms": PLATFORMS, "providers": PROVIDERS}
