"""End-to-end pipeline: sources -> articles -> AI drafts -> rendered slides."""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Article, Brand, CalendarItem, Draft, Slide, Source, session_scope, utcnow
from . import app_settings, generator, images, scraper, storage
from .renderer import BrandStyle, SlideSpec, renderer

log = logging.getLogger(__name__)

JUSOOR_DEFAULT_BRAND = {
    "name": "JUSOOR Travel",
    "handle": "@jusoortravel",
    "website": "jusoortravel.com",
    "voice": "راقٍ، دافئ، موثوق وملهم — يخاطب المسافر العربي بلغة قريبة ومحترمة",
    "colors": {"navy": "#16244F", "gold": "#C6A23C", "goldLight": "#D9B96A",
               "cardBg": "rgba(247,245,240,0.94)", "cardTitle": "#16244F", "cardText": "#3A4058"},
    "cta_text": "راسلنا الآن لتصميم رحلتك",
    "is_default": True,
}


def ensure_default_brand(db: Session) -> Brand:
    brand = db.scalar(select(Brand).where(Brand.is_default.is_(True))) or db.scalar(select(Brand))
    if brand is None:
        brand = Brand(**JUSOOR_DEFAULT_BRAND)
        db.add(brand)
        db.flush()
    return brand


def _brand_for(db: Session, brand_id: int | None) -> Brand:
    return (db.get(Brand, brand_id) if brand_id else None) or ensure_default_brand(db)


def brand_context(brand: Brand) -> generator.BrandContext:
    return generator.BrandContext(name=brand.name, handle=brand.handle, website=brand.website,
                                  voice=brand.voice, cta_text=brand.cta_text)


def brand_style(brand: Brand, language: str) -> BrandStyle:
    logo = None
    if brand.logo_path:
        try:
            logo = storage.read_bytes(brand.logo_path)
        except Exception:  # noqa: BLE001
            logo = None
    return BrandStyle(name=brand.name, handle=brand.handle, website=brand.website, colors=brand.colors,
                      font_family=brand.font_family, logo=logo, logo_placement=brand.logo_placement,
                      card_style=brand.card_style, language=language)


# ---------------------------------------------------------------- collecting
def collect_source(source_id: int) -> dict:
    """Fetch new articles for one source and store them (status=new)."""
    with session_scope() as db:
        source = db.get(Source, source_id)
        if source is None:
            return {"ok": False, "error": "source not found"}
        sched = app_settings.get_section(db, "scheduler")
        max_age = timedelta(days=int(sched.get("max_article_age_days", 3)))
        source.last_checked_at = utcnow()
        created = 0
        try:
            if source.kind == "rss" and source.feed_url:
                items, status = scraper.fetch_feed(source.feed_url, limit=source.max_items_per_run * 3)
                candidates = items
            else:
                listing = scraper.discover_links(source, limit=source.max_items_per_run * 3)
                status = listing.http_status
                known = set(db.scalars(select(Article.url).where(Article.url.in_(listing.links))))
                candidates = [scraper.ScrapedArticle(url=u) for u in listing.links if u not in known]
            source.last_http_status = status
            for item in candidates:
                if created >= source.max_items_per_run:
                    break
                if db.scalar(select(Article.id).where(Article.url == item.url)):
                    continue
                art = item
                if source.kind != "rss" or len(item.body) < 400:
                    try:
                        art = scraper.fetch_article(item.url, source.body_selector)
                        art.title = art.title or item.title
                        art.image_url = art.image_url or item.image_url
                        art.published_at = art.published_at or item.published_at
                    except Exception as exc:  # noqa: BLE001
                        log.warning("article fetch failed %s: %s", item.url, exc)
                        continue
                status_value, note = "new", None
                if len(art.body) < 250:
                    status_value, note = "skipped", "نص المقال قصير جدًا"
                elif art.published_at and utcnow() - art.published_at > max_age:
                    status_value, note = "skipped", "المقال أقدم من الحد المسموح"
                elif db.scalar(select(Article.id).where(Article.fingerprint == art.fingerprint)):
                    status_value, note = "skipped", "مقال مكرر"
                db.add(Article(source_id=source.id, url=art.url, title=art.title, body=art.body,
                               image_url=art.image_url, published_at=art.published_at,
                               fingerprint=art.fingerprint, status=status_value, note=note))
                db.flush()
                if status_value == "new":
                    created += 1
            source.health = "healthy"
            source.last_success_at = utcnow()
            source.last_error = None
            return {"ok": True, "new_articles": created}
        except Exception as exc:  # noqa: BLE001
            source.health = "failing"
            source.last_error = str(exc)[:1000]
            log.exception("collect failed for source %s", source_id)
            return {"ok": False, "error": str(exc)[:300]}


def due_sources() -> list[int]:
    with session_scope() as db:
        now = utcnow()
        out = []
        for s in db.scalars(select(Source).where(Source.enabled.is_(True)).order_by(Source.priority.desc())):
            last = s.last_checked_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last is None or now - last >= timedelta(minutes=s.check_interval_minutes or 120):
                out.append(s.id)
        return out


# ---------------------------------------------------------------- drafting
async def draft_from_article(article_id: int) -> int | None:
    with session_scope() as db:
        art = db.get(Article, article_id)
        if art is None or art.status != "new":
            return None
        source = db.get(Source, art.source_id) if art.source_id else None
        brand = _brand_for(db, source.brand_id if source else None)
        gen = app_settings.get_section(db, "generation")
        draft = Draft(brand_id=brand.id, source_id=art.source_id, article_id=art.id, origin="source",
                      source_name=source.name if source else "", source_url=art.url,
                      original_title=art.title, original_body=art.body, original_image_url=art.image_url,
                      original_published_at=art.published_at, language=gen["language"], tone=gen["tone"],
                      content_type=gen["content_type"], platform=gen["platform"], status="generating")
        db.add(draft)
        art.status = "drafted"
        db.flush()
        draft_id = draft.id
        ctx, title, body, src_name = brand_context(brand), art.title, art.body, draft.source_name

    try:
        post = await generator.generate_from_article(ctx, gen, title, body, src_name)
    except Exception as exc:  # noqa: BLE001
        _fail(draft_id, f"فشل توليد النص: {exc}")
        return draft_id

    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        _apply_post(draft, post)
        if post.relevance < int(gen.get("min_relevance", 0)):
            draft.status = "rejected"
            draft.reject_reason = f"صلة منخفضة بجمهور السفر ({post.relevance}/10): {post.relevance_reason}"
            return draft_id
    await render_draft(draft_id)
    return draft_id


async def draft_from_calendar(item_id: int) -> int | None:
    with session_scope() as db:
        item = db.get(CalendarItem, item_id)
        if item is None:
            return None
        brand = _brand_for(db, item.brand_id)
        gen = {**app_settings.get_section(db, "generation"), "content_type": item.content_type,
               "platform": item.platform}
        draft = Draft(brand_id=brand.id, campaign_id=item.campaign_id, calendar_item_id=item.id, origin="calendar",
                      original_title=item.topic, original_body=item.notes, language=gen["language"],
                      tone=gen["tone"], content_type=item.content_type, platform=item.platform, status="generating")
        db.add(draft)
        db.flush()
        item.draft_id = draft.id
        item.status = "generated"
        draft_id, ctx, topic, notes = draft.id, brand_context(brand), item.topic, item.notes
    try:
        post = await generator.generate_from_topic(ctx, gen, topic, notes)
    except Exception as exc:  # noqa: BLE001
        _fail(draft_id, f"فشل توليد النص: {exc}")
        return draft_id
    with session_scope() as db:
        _apply_post(db.get(Draft, draft_id), post)
    await render_draft(draft_id)
    return draft_id


def _apply_post(draft: Draft, post: generator.GeneratedPost) -> None:
    draft.hook, draft.subtitle, draft.caption = post.hook, post.subtitle, post.caption
    draft.hashtags = " ".join(post.hashtags)
    draft.first_comment, draft.cta = post.first_comment, post.cta
    draft.image_keywords, draft.badge, draft.relevance = post.image_keywords, post.badge, post.relevance
    draft.ai_meta = post.meta or None
    draft.slides.clear()
    items = [("cover", post.hook, post.subtitle)] + [("content", s["heading"], s["body"]) for s in post.slides] \
        + [("cta", post.cta, "")]
    for pos, (kind, heading, body) in enumerate(items):
        draft.slides.append(Slide(position=pos, kind=kind, heading=heading, body=body))


def _fail(draft_id: int, message: str) -> None:
    with session_scope() as db:
        d = db.get(Draft, draft_id)
        if d:
            d.status, d.error = "failed", message[:2000]


async def render_draft(draft_id: int, positions: list[int] | None = None, refresh_backgrounds: bool = False) -> None:
    """(Re)render slide images. positions=None renders all slides."""
    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        if draft is None:
            return
        brand = _brand_for(db, draft.brand_id)
        gen = app_settings.get_section(db, "generation")
        style = brand_style(brand, draft.language)
        slides = [(s.id, s.kind, s.heading, s.body, s.position, s.background_url, s.image_key) for s in draft.slides]
        needs_bg = refresh_backgrounds or any(s[5] is None for s in slides if s[1] != "cta")
        keywords, article_image = draft.image_keywords, draft.original_image_url
        credit = draft.source_name if (draft.origin == "source" and gen.get("credit_source", True)) else ""
        badge = draft.badge
        mode = gen.get("image_source", "auto")
        prev_status = draft.status

    backgrounds = []
    if needs_bg:
        needed = max(1, sum(1 for s in slides if s[1] != "cta"))
        backgrounds = images.collect_backgrounds(article_image, keywords, mode, needed)
        if not backgrounds and mode != "source" and article_image:
            backgrounds = images.collect_backgrounds(article_image, keywords, "source", 1)

    total = len(slides)
    results: dict[int, dict] = {}
    try:
        bg_index = 0
        for slide_id, kind, heading, body, pos, bg_url, old_key in slides:
            if positions is not None and pos not in positions and not needs_bg:
                continue
            bg = None
            if backgrounds:
                bg = backgrounds[0] if kind in ("cover", "cta") else backgrounds[bg_index % len(backgrounds)]
                if kind == "content":
                    bg_index += 1
            elif bg_url:
                data = images.download_image(bg_url)
                bg = {"url": bg_url, "bytes": data, "hash": hashlib.sha1(data).hexdigest()} if data else None
            spec = SlideSpec(kind=kind, heading=heading, body=body, position=pos, total=total,
                             background=bg["bytes"] if bg else None,
                             badge=badge if kind == "cover" else None,
                             credit=credit if kind != "cta" else "", variant=pos)
            jpeg = await renderer.render(spec, style)
            key = f"generated/draft-{draft_id}-s{pos}-{uuid.uuid4().hex[:8]}.jpg"
            url = storage.save_bytes(key, jpeg)
            if old_key:
                storage.delete(old_key)
            results[slide_id] = {"image_key": key, "image_url": url, "width": 1080, "height": 1350,
                                 "background_url": bg["url"] if bg else bg_url,
                                 "image_hash": bg["hash"] if bg else None}
    except Exception as exc:  # noqa: BLE001
        log.exception("render failed")
        _fail(draft_id, f"فشل تصميم الصور: {exc}")
        return

    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        for s in draft.slides:
            if s.id in results:
                for k, v in results[s.id].items():
                    setattr(s, k, v)
        if prev_status in ("generating", "failed"):
            draft.status, draft.error = "pending_review", None
        draft.updated_at = utcnow()


async def run_collection_cycle(source_ids: list[int] | None = None) -> dict:
    """Collect from due sources, then draft new articles."""
    with session_scope() as db:
        sched = app_settings.get_section(db, "scheduler")
    ids = source_ids if source_ids is not None else due_sources()
    summary = {"sources": 0, "new_articles": 0, "drafts": 0, "errors": []}
    for sid in ids:
        res = collect_source(sid)
        summary["sources"] += 1
        summary["new_articles"] += res.get("new_articles", 0)
        if not res.get("ok"):
            summary["errors"].append({"source_id": sid, "error": res.get("error")})
    with session_scope() as db:
        q = select(Article.id).where(Article.status == "new").order_by(Article.published_at.desc().nullslast())
        if source_ids is not None:
            q = q.where(Article.source_id.in_(source_ids))
        pending = list(db.scalars(q.limit(int(sched.get("max_drafts_per_run", 10)))))
    for aid in pending:
        if await draft_from_article(aid):
            summary["drafts"] += 1
    return summary


def compose_caption(draft: Draft, credit: bool = True) -> str:
    parts = [draft.caption.strip()]
    if credit and draft.origin == "source" and draft.source_name:
        label = {"ar": "المصدر", "en": "Source", "fr": "Source"}.get(draft.language, "Source")
        parts.append(f"{label}: {draft.source_name}")
    if draft.hashtags:
        parts.append(draft.hashtags.strip())
    return "\n\n".join(p for p in parts if p)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
