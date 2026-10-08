"""End-to-end pipeline: sources -> articles -> AI drafts -> rendered slides."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Article, Brand, CalendarItem, Draft, Organization, Slide, Source, session_scope, utcnow
from . import app_settings, generator, images, industries, media, scraper, storage, variants
from . import palette as colours
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


def family_of(db: Session, org_id: int | None) -> str:
    """Card design family of the company's field."""
    from . import cards
    org = db.get(Organization, org_id) if org_id else None
    return cards.FAMILY_OF_INDUSTRY.get(org.industry if org else "general", "general")


def _read(key: str | None) -> bytes | None:
    if not key:
        return None
    try:
        return storage.read_bytes(key)
    except Exception:  # noqa: BLE001
        return None


def brand_logos(brand: Brand) -> list[dict]:
    """All logo versions of a brand; a brand from before multi-logo support has just its one logo."""
    items = [dict(x) for x in (brand.logos or []) if isinstance(x, dict) and x.get("key")]
    if brand.logo_path and not any(x["key"] == brand.logo_path for x in items):
        items.insert(0, {"key": brand.logo_path, "tone": "color", "name": ""})
    return items


def brand_style(brand: Brand, language: str, family: str = "general") -> BrandStyle:
    logo = _read(brand.logo_path)
    versions = [(x.get("tone") or "color", _read(x["key"])) for x in brand_logos(brand)]
    return BrandStyle(name=brand.name, handle=brand.handle, website=brand.website, colors=brand.colors,
                      font_family=brand.font_family, font_latin=brand.font_latin or "Cairo", logo=logo, logo_placement=brand.logo_placement,
                      card_style=brand.card_style, language=language,
                      logo_backdrop=brand.logo_backdrop or "auto",
                      theme=getattr(brand, "card_theme", None) or "magazine", family=family,
                      logos=[v for v in versions if v[1]])


# ---------------------------------------------------------------- collecting
def _fetch_pages(items: list, source) -> dict:
    """Fetch the article pages that are needed, 6 at a time. url → ScrapedArticle | Exception."""
    from concurrent.futures import ThreadPoolExecutor

    need = [i for i in items if source.kind != "rss" or len(i.body) < 400 or not i.image_url]
    if not need:
        return {}

    def get(item):
        try:
            return item.url, scraper.fetch_article(item.url, source.body_selector)
        except Exception as exc:  # noqa: BLE001
            return item.url, exc

    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(get, need))


def _in_window(published: datetime | None, window: dict | None) -> bool:
    if not window or published is None:
        return True
    day = published.astimezone(timezone.utc).date()
    if window.get("date_from") and day < window["date_from"]:
        return False
    if window.get("date_to") and day > window["date_to"]:
        return False
    return True


def _feed_pages(source, limit: int, window: dict | None) -> tuple[list, int | None]:
    """RSS items; for a past period, also older feed pages (WordPress: ?paged=2, 3…)."""
    items, status = scraper.fetch_feed(source.feed_url, limit=limit)
    date_from = (window or {}).get("date_from")
    page = 2
    while date_from and items and page <= 8:
        dated = [i.published_at for i in items if i.published_at]
        if not dated or min(dated).date() <= date_from:
            break
        sep = "&" if "?" in source.feed_url else "?"
        try:
            more, _ = scraper.fetch_feed(f"{source.feed_url}{sep}paged={page}", limit=limit)
        except Exception:  # noqa: BLE001 - the feed has no older pages
            break
        known = {i.url for i in items}
        more = [m for m in more if m.url not in known]
        if not more:
            break
        items += more
        page += 1
    return items, status


def collect_source(source_id: int, window: dict | None = None) -> dict:
    """Fetch new articles for one source and store them (status=new).

    window = {"date_from", "date_to", "max_items"}: only articles published in that period."""
    with session_scope() as db:
        source = db.get(Source, source_id)
        if source is None:
            return {"ok": False, "error": "source not found"}
        sched = app_settings.get_section(db, "scheduler")
        max_age = timedelta(days=int(sched.get("max_article_age_days", 3)))
        programs = (source.purpose or "news") == "programs"
        evergreen = programs or source.purpose == "own_site"     # no "too old" limit for these
        per_run = int((window or {}).get("max_items") or source.max_items_per_run)
        source.last_checked_at = utcnow()
        created = 0
        try:
            if source.kind == "rss" and source.feed_url:
                items, status = _feed_pages(source, per_run * 3, window)
                candidates = [i for i in items if _in_window(i.published_at, window)]
            else:
                listing = scraper.discover_links(source, limit=per_run * 3)
                status = listing.http_status
                known = set(db.scalars(select(Article.url).where(Article.url.in_(listing.links))))
                candidates = [scraper.ScrapedArticle(url=u) for u in listing.links if u not in known]
            source.last_http_status = status
            # Download the article pages in parallel first (network), then store them (database)
            wanted = []
            for item in candidates:
                if len(wanted) >= per_run * 2:
                    break
                if not db.scalar(select(Article.id).where(Article.url == item.url)):
                    wanted.append(item)
            pages = _fetch_pages(wanted, source)
            candidates = wanted
            for item in candidates:
                if created >= per_run:
                    break
                if db.scalar(select(Article.id).where(Article.url == item.url)):
                    continue
                art = item
                page = pages.get(item.url)
                needs_page = source.kind != "rss" or len(item.body) < 400
                if isinstance(page, Exception) or (needs_page and page is None):
                    log.warning("article fetch failed %s: %s", item.url, page)
                    if len(item.body) < 250:     # RSS text is enough when the page itself is blocked
                        continue
                elif page is not None:
                    if needs_page:
                        art = page
                        art.title = art.title or item.title
                        art.image_url = art.image_url or item.image_url
                        art.published_at = art.published_at or item.published_at
                    elif not art.image_url:
                        art.image_url = page.image_url   # every article must come with its photo
                status_value, note = "new", None
                if not art.image_url and not programs:      # programs use stock photos, not the source's
                    status_value, note = "skipped", "المقال بلا صورة"
                elif len(art.body) < 250:
                    status_value, note = "skipped", "نص المقال قصير جدًا"
                elif window and not _in_window(art.published_at, window):
                    status_value, note = "skipped", "خارج الفترة المطلوبة"
                elif (not window and not evergreen and art.published_at
                      and utcnow() - art.published_at > max_age):
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
            source.last_error = scraper.friendly_error(exc)[:1000]
            log.exception("collect failed for source %s", source_id)
            return {"ok": False, "error": scraper.friendly_error(exc)[:300]}


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
        gen = dict(app_settings.get_section(db, "generation"))
        programs = bool(source and (source.purpose or "news") == "programs")
        own_site = bool(source and source.purpose == "own_site")
        if source and source.dialect:
            gen["dialect"] = source.dialect
        if programs:
            gen.update(purpose="programs", content_type="promotional")
        elif source and source.purpose:
            gen["purpose"] = source.purpose
        draft = Draft(brand_id=brand.id, source_id=art.source_id, article_id=art.id, origin="source",
                      # the company's own website is never credited as an outside source
                      source_name="" if own_site else (source.name if source else ""), source_url=art.url,
                      original_title=art.title, original_body=art.body,
                      # a programme from another company is re-designed with stock photos, never theirs
                      original_image_url=None if programs else art.image_url,
                      original_published_at=art.published_at, language=gen["language"], tone=gen["tone"],
                      content_type="program" if programs else gen["content_type"], platform=gen["platform"],
                      dialect=gen.get("dialect"), status="generating")
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
        if post.relevance < int(gen.get("min_relevance", 0)) and gen.get("purpose") != "own_site":
            draft.status = "rejected"
            draft.reject_reason = f"صلة منخفضة بجمهور الشركة ({post.relevance}/10): {post.relevance_reason}"
            return draft_id
    # Platform texts (AI) and slide images (photos + rendering) are independent: do both at once
    await asyncio.gather(make_variants(draft_id), render_draft(draft_id))
    return draft_id


async def dialect_copy(src_id: int, dialect: str) -> int | None:
    """Same post for another market: rewritten in another Arabic dialect, same photos."""
    with session_scope() as db:
        src = db.get(Draft, src_id)
        if src is None:
            return None
        brand = _brand_for(db, src.brand_id)
        gen = {**app_settings.get_section(db, "generation"), "language": "ar", "tone": src.tone,
               "content_type": src.content_type if src.content_type != "program" else "promotional",
               "platform": src.platform, "dialect": dialect,
               **({"purpose": "programs"} if src.content_type == "program" else {})}
        copy = Draft(brand_id=src.brand_id, source_id=src.source_id, campaign_id=src.campaign_id, origin=src.origin,
                     source_name=src.source_name, source_url=src.source_url, original_title=src.original_title,
                     original_body=src.original_body, original_image_url=src.original_image_url,
                     original_published_at=src.original_published_at, language="ar", tone=src.tone,
                     content_type=src.content_type, platform=src.platform, dialect=dialect, status="generating")
        db.add(copy)
        db.flush()
        new_id = copy.id
        photos = {s.position: s.background_url for s in src.slides}
        ctx, origin = brand_context(brand), src.origin
        title, body, source_name = src.original_title, src.original_body, src.source_name
    try:
        if origin == "source":
            post = await generator.generate_from_article(ctx, gen, title, body, source_name)
        else:
            post = await generator.generate_from_topic(ctx, gen, title, body)
    except Exception as exc:  # noqa: BLE001
        _fail(new_id, f"فشل توليد النص: {exc}")
        return new_id
    with session_scope() as db:
        draft = db.get(Draft, new_id)
        _apply_post(draft, post)
        db.flush()
        for s in draft.slides:
            s.background_url = photos.get(s.position)
    await asyncio.gather(make_variants(new_id), render_draft(new_id))
    return new_id


async def draft_from_product(product_id: int) -> int | None:
    """One post for one product / service / course from the company's own site, with its link."""
    from ..db import Product
    from . import products as product_lib
    with session_scope() as db:
        prod = db.get(Product, product_id)
        if prod is None:
            return None
        brand = _brand_for(db, None)
        gen = {**app_settings.get_section(db, "generation"), "purpose": "product", "content_type": "promotional"}
        title, body = product_lib.as_article(prod)
        draft = Draft(brand_id=brand.id, origin="product", source_name="", source_url=prod.url,
                      original_title=title, original_body=body, original_image_url=prod.image_url,
                      language=gen["language"], tone=gen["tone"], content_type="promotional",
                      platform=gen["platform"], dialect=gen.get("dialect"), link_url=prod.url, status="generating")
        db.add(draft)
        db.flush()
        prod.status, prod.draft_id = "drafted", draft.id
        draft_id = draft.id
        ctx = brand_context(brand)
    try:
        post = await generator.generate_from_article(ctx, gen, title, body, "")
    except Exception as exc:  # noqa: BLE001
        _fail(draft_id, f"فشل توليد النص: {exc}")
        return draft_id
    with session_scope() as db:
        _apply_post(db.get(Draft, draft_id), post)
    await asyncio.gather(make_variants(draft_id), render_draft(draft_id))
    return draft_id


async def draft_from_calendar(item_id: int) -> int | None:
    with session_scope() as db:
        item = db.get(CalendarItem, item_id)
        if item is None:
            return None
        brand = _brand_for(db, item.brand_id)
        base = app_settings.get_section(db, "generation")
        if not item.content_type:
            item.content_type = base.get("content_type") or "news"
        gen = {**base, "content_type": item.content_type, "platform": item.platform}
        if getattr(item, "dialect", None):
            gen["dialect"] = item.dialect
        draft = Draft(brand_id=brand.id, campaign_id=item.campaign_id, calendar_item_id=item.id, origin="calendar",
                      original_title=item.topic, original_body=item.notes, language=gen["language"],
                      tone=gen["tone"], content_type=item.content_type, platform=item.platform,
                      dialect=gen.get("dialect"), status="generating")
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
    # Platform texts (AI) and slide images (photos + rendering) are independent: do both at once
    await asyncio.gather(make_variants(draft_id), render_draft(draft_id))
    return draft_id


def _apply_post(draft: Draft, post: generator.GeneratedPost) -> None:
    draft.hook, draft.subtitle, draft.caption = post.hook, post.subtitle, post.caption
    draft.hook_highlight = post.highlight if post.highlight and post.highlight in post.hook else None
    draft.hashtags = " ".join(post.hashtags)
    draft.first_comment, draft.cta = post.first_comment, post.cta
    draft.image_keywords, draft.badge, draft.relevance = post.image_keywords, post.badge, post.relevance
    draft.ai_meta = post.meta or None
    draft.slides.clear()
    items = [("cover", post.hook, post.subtitle)] + [("content", s["heading"], s["body"]) for s in post.slides] \
        + [("cta", post.cta, "")]
    for pos, (kind, heading, body) in enumerate(items):
        draft.slides.append(Slide(position=pos, kind=kind, heading=heading, body=body))


def _snapshot(draft: Draft):
    """Detached copy of what the platform-text prompt needs."""
    from types import SimpleNamespace
    slides = [SimpleNamespace(position=s.position, kind=s.kind, heading=s.heading, body=s.body) for s in draft.slides]
    return SimpleNamespace(hook=draft.hook, subtitle=draft.subtitle, caption=draft.caption, hashtags=draft.hashtags,
                           cta=draft.cta, origin=draft.origin, source_name=draft.source_name,
                           language=draft.language, slides=slides)


async def make_variants(draft_id: int) -> None:
    """Write one post per platform (text + image set) for a draft."""
    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        if draft is None or not draft.slides:
            return
        brand = _brand_for(db, draft.brand_id)
        gen = app_settings.get_section(db, "generation")
        ctx, snap = brand_context(brand), _snapshot(draft)
        dialect = draft.dialect or gen.get("dialect")
    texts = await variants.generate_texts(ctx, {**gen, "language": snap.language, "dialect": dialect}, snap)
    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        if draft is not None:
            draft.variants = variants.finalize(draft, texts, gen.get("credit_source", True), draft.variants)


def _fail_soft(draft_id: int, message: str) -> None:
    """Report a problem on the draft without failing it."""
    with session_scope() as db:
        d = db.get(Draft, draft_id)
        if d:
            d.error = message[:2000]


def _fail(draft_id: int, message: str) -> None:
    with session_scope() as db:
        d = db.get(Draft, draft_id)
        if d:
            d.status, d.error = "failed", message[:2000]


def _recent_variants(draft_id: int, limit: int = 3) -> list[str]:
    """Colour sets of the latest other posts, newest first — so the next post looks different."""
    with session_scope() as db:
        rows = db.scalars(select(Draft.palette).where(Draft.id != draft_id, Draft.palette.is_not(None))
                          .order_by(Draft.id.desc()).limit(limit * 3)).all()
    return [p.get("variant") for p in rows if isinstance(p, dict) and p.get("variant")][:limit]


def _save_thumb(key: str, jpeg: bytes) -> str | None:
    """Small cover for the review grid (≈25 KB instead of ≈300 KB)."""
    try:
        from io import BytesIO

        from PIL import Image
        img = Image.open(BytesIO(jpeg))
        img.thumbnail((400, 500))
        out = BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=78, optimize=True)
        return storage.save_bytes(key.replace(".jpg", "-thumb.jpg"), out.getvalue())
    except Exception as exc:  # noqa: BLE001
        log.warning("thumbnail failed: %s", exc)
        return None


def _next_design_index(draft_id: int) -> int:
    """The design after the one used by the company's most recent post."""
    with session_scope() as db:
        rows = db.scalars(select(Draft.palette).where(Draft.id != draft_id, Draft.palette.is_not(None))
                          .order_by(Draft.id.desc()).limit(5)).all()
    for p in rows:
        if isinstance(p, dict) and p.get("design") is not None:
            return int(p["design"]) + 1
    return 0


async def render_draft(draft_id: int, positions: list[int] | None = None, refresh_backgrounds: bool = False,
                       next_design: bool = False) -> None:
    """(Re)render slide images. positions=None renders all slides."""
    with session_scope() as db:
        draft = db.get(Draft, draft_id)
        if draft is None:
            return
        brand = _brand_for(db, draft.brand_id)
        gen = app_settings.get_section(db, "generation")
        family = family_of(db, draft.org_id)
        style = brand_style(brand, draft.language, family)
        slides = [(s.id, s.kind, s.heading, s.body, s.position, s.background_url, s.image_key) for s in draft.slides]
        needs_bg = refresh_backgrounds or any(s[5] is None for s in slides if s[1] != "cta")
        keywords, article_image = draft.image_keywords, draft.original_image_url
        hook_text = draft.hook or ""
        org = db.get(Organization, draft.org_id) if draft.org_id else None
        fallback_keywords = industries.get(org.industry if org else None)["image_keywords"]
        credit = draft.source_name if (draft.origin == "source" and gen.get("credit_source", True)) else ""
        badge = draft.badge
        highlight = [draft.hook_highlight] if draft.hook_highlight else None
        mode = "pexels" if draft.content_type == "program" else gen.get("image_source", "auto")
        prev_status = draft.status
        color_mode = brand.color_mode or "auto"
        stored_palette = draft.palette
        brand_navy = (brand.colors or {}).get("navy") or colours.BRAND_NAVY
        brand_gold = (brand.colors or {}).get("gold") or colours.BRAND_GOLD
        design_seed = brand.design_seed or 0
        enabled_templates = list(brand.templates or [])
        logo_placement = brand.logo_placement or "top-left"
        rtl = draft.language == "ar"

    backgrounds = []
    if needs_bg:
        needed = max(1, sum(1 for s in slides if s[1] != "cta")) + 1        # +1: the last slide gets its own photo
        used = {s[5] for s in slides if s[5]} if refresh_backgrounds else set()
        with session_scope() as db:
            library = media.pick(db, f"{keywords} {hook_text}", needed + 4, used)
        # Network calls run in a worker thread so the server keeps answering while photos download
        backgrounds = await asyncio.to_thread(images.collect_backgrounds, article_image, keywords, mode, needed,
                                              used, refresh_backgrounds, library, fallback_keywords)
        if not backgrounds and mode != "source" and article_image and not refresh_backgrounds:
            backgrounds = await asyncio.to_thread(images.collect_backgrounds, article_image, keywords, "source", 1)
        if refresh_backgrounds and len(backgrounds) < 2:
            # Not enough new photos anywhere: at least reshuffle the post's own photos so it changes,
            # and tell the user how to get fresh ones.
            own = [s[5] for s in slides if s[5]]
            if len(set(own)) > 1:
                rotated = own[1:] + own[:1]
                backgrounds = backgrounds + [b for b in await asyncio.to_thread(
                    images.collect_backgrounds, None, "", "source", needed, set(), False,
                    [{"url": u, "credit": "", "match": True} for u in dict.fromkeys(rotated)])]
            _fail_soft(draft_id, "لم تتوفر صور جديدة كافية — أضف صورًا إلى مكتبة الصور أو مفتاح Pixabay/Pexels "
                                 "في الإعدادات لمزيد من التنوع")
            if not backgrounds:
                return

    # Design (colour set + card layout + cover style) from the company's own rotation: a new post
    # takes the next design after the previous post; "redesign" moves this post to its next one.
    # All designs are used before any of them comes back.
    palette_to_store = stored_palette
    if color_mode == "auto":
        stored_index = (stored_palette or {}).get("design")
        if next_design and stored_index is not None:
            index = int(stored_index) + 1
        elif stored_index is not None:
            index = int(stored_index)
        else:
            index = _next_design_index(draft_id)
        palette_to_store = colours.design(index, brand_navy, brand_gold, design_seed, family, enabled_templates)
        style.palette = palette_to_store
    else:
        style.palette = None
        palette_to_store = None

    total = len(slides)
    results: dict[int, dict] = {}
    thumb_url = None

    # 1) decide each slide's photo (cheap), 2) download + render all slides in parallel
    plan = []
    bg_index = 1 if len(backgrounds) > 1 else 0          # backgrounds[0] is the cover
    for slide_id, kind, heading, body, pos, bg_url, old_key in slides:
        if positions is not None and pos not in positions and not needs_bg:
            continue
        chosen = None
        if not (bg_url and not refresh_backgrounds) and backgrounds:
            if kind == "cover":
                chosen = backgrounds[0]
            elif kind == "cta":
                chosen = backgrounds[-1]                     # a different photo from the cover when possible
            else:
                chosen = backgrounds[bg_index % len(backgrounds)]
                bg_index += 1
        plan.append((slide_id, kind, heading, body, pos, bg_url, old_key, chosen))

    gate = asyncio.Semaphore(3)

    async def one(slide_id, kind, heading, body, pos, bg_url, old_key, chosen):
        async with gate:
            bg = chosen
            if bg is None and bg_url:
                # keep the slide's own photo (e.g. one the user uploaded)
                data = await asyncio.to_thread(images.download_image, bg_url)
                bg = {"url": bg_url, "bytes": data, "hash": hashlib.sha1(data).hexdigest()} if data else None
            # the logo version that reads best on this photo (white / dark / colour)
            chosen_logo, plate = colours.choose_logo(style.logos, style.logo, bg["bytes"] if bg else None,
                                                     logo_placement, kind, (style.palette or {}).get("template"))
            spec = SlideSpec(kind=kind, heading=heading, body=body, position=pos, total=total,
                             background=bg["bytes"] if bg else None,
                             badge=badge if kind == "cover" else None,
                             credit=credit if kind != "cta" else "", variant=pos,
                             highlight=highlight if kind == "cover" else None,
                             logo=chosen_logo, logo_plate=plate)
            jpeg = await renderer.render(spec, style)
            key = f"generated/draft-{draft_id}-s{pos}-{uuid.uuid4().hex[:8]}.jpg"
            url = await asyncio.to_thread(storage.save_bytes, key, jpeg)
            thumb = await asyncio.to_thread(_save_thumb, key, jpeg) if pos == 0 else None
            if old_key:
                await asyncio.to_thread(storage.delete, old_key)
            return slide_id, thumb, {"image_key": key, "image_url": url, "width": 1080, "height": 1350,
                                     "background_url": bg["url"] if bg else bg_url,
                                     "image_hash": bg["hash"] if bg else None}

    try:
        for slide_id, thumb, data in await asyncio.gather(*(one(*p) for p in plan)):
            results[slide_id] = data
            thumb_url = thumb_url or thumb
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
        draft.palette = palette_to_store
        if thumb_url:
            draft.cover_thumb_url = thumb_url
        draft.updated_at = utcnow()


async def run_collection_cycle(source_ids: list[int] | None = None, window: dict | None = None) -> dict:
    """Collect from due sources, then draft new articles."""
    with session_scope() as db:
        sched = app_settings.get_section(db, "scheduler")
    ids = source_ids if source_ids is not None else due_sources()
    summary = {"sources": 0, "new_articles": 0, "drafts": 0, "errors": []}
    # Sources are fetched in worker threads, several at a time: the dashboard stays responsive
    # and a slow site no longer holds up the others.
    gate = asyncio.Semaphore(4)

    async def one_source(sid: int) -> tuple[int, dict]:
        async with gate:
            return sid, await asyncio.to_thread(collect_source, sid, window)

    for sid, res in await asyncio.gather(*(one_source(i) for i in ids)):
        summary["sources"] += 1
        summary["new_articles"] += res.get("new_articles", 0)
        if not res.get("ok"):
            summary["errors"].append({"source_id": sid, "error": res.get("error")})
    with session_scope() as db:
        q = select(Article.id).where(Article.status == "new").order_by(Article.published_at.desc().nullslast())
        if source_ids is not None:
            q = q.where(Article.source_id.in_(source_ids))
        limit = int(sched.get("max_drafts_per_run", 10))
        if window and window.get("max_items"):
            limit = min(max(limit, int(window["max_items"]) * max(len(ids), 1)), 60)
        pending = list(db.scalars(q.limit(limit)))
    # Write up to 3 posts at the same time (AI calls and image downloads overlap)
    draft_gate = asyncio.Semaphore(3)

    async def one_draft(aid: int) -> bool:
        async with draft_gate:
            try:
                return bool(await draft_from_article(aid))
            except Exception:  # noqa: BLE001
                log.exception("drafting failed for article %s", aid)
                return False

    summary["drafts"] = sum(await asyncio.gather(*(one_draft(a) for a in pending)))
    return summary


def compose_caption(draft: Draft, credit: bool = True) -> str:
    parts = [draft.caption.strip()]
    if credit and draft.origin == "source" and draft.source_name:
        label = {"ar": "المصدر", "en": "Source", "fr": "Source", "ms": "Sumber"}.get(draft.language, "Source")
        parts.append(f"{label}: {draft.source_name}")
    if getattr(draft, "link_url", None) and draft.link_url not in parts[0]:
        parts.append(f"🔗 {draft.link_url}")
    if draft.hashtags:
        parts.append(draft.hashtags.strip())
    return "\n\n".join(p for p in parts if p)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
