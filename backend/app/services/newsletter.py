"""Email newsletters: field-specific designs (email-safe HTML), AI content, sending and tracking."""
from __future__ import annotations

import asyncio
import html as html_lib
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy import func, select

from ..config import get_settings
from ..db import Brand, Contact, Delivery, Draft, Newsletter, Organization, Product, session_scope, use_org, utcnow
from . import cards, generator, industries, mailer, pipeline, storage

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ designs
LAYOUTS = ["classic", "magazine", "minimal", "bold", "digest", "spotlight"]
LAYOUT_LABELS = {
    "classic": ("كلاسيكي", "Classic", "Klasik", "Classique"),
    "magazine": ("مجلة", "Magazine", "Majalah", "Magazine"),
    "minimal": ("بسيط أنيق", "Minimal", "Minimal", "Minimal"),
    "bold": ("جريء", "Bold", "Berani", "Audacieux"),
    "digest": ("ملخص", "Digest", "Ringkasan", "Condensé"),
    "spotlight": ("تسليط الضوء", "Spotlight", "Sorotan", "À la une"),
}
# every field gets its own combination (and its own skin below)
FIELD_LAYOUTS = {
    "travel": ["spotlight", "magazine", "classic", "bold", "digest"],
    "news": ["digest", "classic", "magazine", "minimal"],
    "tech": ["minimal", "digest", "bold", "classic"],
    "food": ["bold", "spotlight", "magazine", "classic"],
    "education": ["classic", "digest", "spotlight", "minimal"],
    "training": ["classic", "spotlight", "digest", "bold"],
    "nonprofit": ["spotlight", "minimal", "classic", "magazine"],
    "retail": ["bold", "magazine", "spotlight", "digest", "classic"],
    "luxury": ["minimal", "spotlight", "magazine", "classic"],
    "fashion": ["magazine", "minimal", "bold", "spotlight"],
    "health": ["classic", "minimal", "digest", "spotlight"],
    "beauty": ["spotlight", "minimal", "magazine", "bold"],
    "auto": ["bold", "spotlight", "digest", "classic"],
    "events": ["bold", "spotlight", "classic", "digest"],
    "general": ["classic", "magazine", "minimal", "bold", "digest", "spotlight"],
}
SKINS = {
    "serif": {"luxury", "fashion", "beauty", "nonprofit"},
    "round": {"food", "beauty", "health", "retail", "travel", "events", "nonprofit"},
    "square": {"news", "tech", "auto", "luxury"},
    "numbered": {"education", "training", "health"},
    "dotted": {"food"},
}
UNSUB = {"ar": "إلغاء الاشتراك", "en": "Unsubscribe", "ms": "Nyahlanggan", "fr": "Se désabonner"}
WHY = {"ar": "تصلك هذه الرسالة لأنك مشترك في نشرة", "en": "You receive this email because you subscribed to",
       "ms": "Anda menerima e-mel ini kerana melanggan", "fr": "Vous recevez cet e-mail car vous êtes abonné à"}
VIEW = {"ar": "اقرأ المزيد", "en": "Read more", "ms": "Baca lagi", "fr": "Lire la suite"}


def family_of_org(db, org_id) -> str:  # noqa: ANN001
    return pipeline.family_of(db, org_id)


def designs_for(family: str) -> list[dict[str, str]]:
    return [{"id": d, "ar": LAYOUT_LABELS[d][0], "en": LAYOUT_LABELS[d][1], "ms": LAYOUT_LABELS[d][2],
             "fr": LAYOUT_LABELS[d][3]} for d in FIELD_LAYOUTS.get(family, FIELD_LAYOUTS["general"])]


def _e(text: str | None) -> str:
    return html_lib.escape(text or "").replace("\n", "<br>")


def _abs(url: str | None) -> str:
    if not url:
        return ""
    if url.startswith(("http", "data:")):
        return url
    base = (get_settings().public_base_url or "").rstrip("/")
    return f"{base}/{url.lstrip('/')}" if base else url


def _logo_url(brand: Brand, dark_background: bool) -> str:
    logos = pipeline.brand_logos(brand)
    want = "light" if dark_background else "color"
    pick = next((x for x in logos if x.get("tone") == want), None) or \
        next((x for x in logos if x.get("tone") == ("dark" if not dark_background else "color")), None)
    key = (pick or {}).get("key") or brand.logo_path
    return _abs(storage.public_url(key)) if key else ""


def render(nl: Newsletter, brand: Brand, family: str, token: str | None = None) -> tuple[str, str]:
    """(html, plain text) of a newsletter. With a token, links and the open pixel are tracked."""
    s = get_settings()
    base = (s.public_base_url or "").rstrip("/")
    lang = nl.language if nl.language in UNSUB else "ar"
    rtl = lang == "ar"
    c = {"navy": "#16244F", "gold": "#C6A23C", "goldLight": "#D9B96A", "surface": "#FBF8F0",
         "cardTitle": "#16244F", "cardText": "#1F2B55", **(brand.colors or {})}
    navy, gold, surface, title_c, text_c = c["navy"], c["gold"], c.get("surface") or "#FBF8F0", \
        c.get("cardTitle") or c["navy"], c.get("cardText") or "#333"
    layout = nl.design if nl.design in LAYOUTS else FIELD_LAYOUTS.get(family, ["classic"])[0]
    serif = family in SKINS["serif"]
    radius = 18 if family in SKINS["round"] else (2 if family in SKINS["square"] else 10)
    btn_radius = 999 if family in SKINS["round"] else (2 if family in SKINS["square"] else 8)
    body_font = "Tahoma, 'Segoe UI', Arial, sans-serif" if rtl else "'Segoe UI', Helvetica, Arial, sans-serif"
    head_font = ("Georgia, 'Times New Roman', serif" if serif and not rtl else body_font)
    align = "right" if rtl else "left"
    dir_ = "rtl" if rtl else "ltr"
    content = nl.content or {}

    def link(url: str) -> str:
        url = _abs(url)
        if token and url and base:
            return f"{base}/api/t/c/{token}?u={quote(url, safe='')}"
        return url or "#"

    def button(text: str, url: str, light: bool = False) -> str:
        if not text:
            return ""
        bg, fg = (gold, navy) if not light else ("#ffffff", navy)
        return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0 6px"><tr>'
                f'<td style="background:{bg};border-radius:{btn_radius}px">'
                f'<a href="{_e(link(url))}" style="display:inline-block;padding:13px 30px;font:bold 16px {body_font};'
                f'color:{fg};text-decoration:none;border-radius:{btn_radius}px">{_e(text)}</a></td></tr></table>')

    def img(url: str, h: int | None = None, r: int = radius) -> str:
        if not url:
            return ""
        style = f"display:block;width:100%;max-width:600px;border-radius:{r}px;border:0"
        if h:
            style += f";height:{h}px;object-fit:cover"
        return f'<img src="{_e(_abs(url))}" alt="" width="600" style="{style}">'

    headline = content.get("headline") or nl.subject
    intro = content.get("intro") or ""
    hero = content.get("hero_image") or ""
    sections = [x for x in (content.get("sections") or []) if isinstance(x, dict)]
    cta_text, cta_url = content.get("cta_text") or "", content.get("cta_url") or brand.website or ""
    ps = content.get("ps") or ""
    h1 = f"font:bold 30px/1.3 {head_font};color:{title_c};margin:0 0 12px"
    p = f"font:16px/1.75 {body_font};color:{text_c};margin:0"

    # header
    if layout in ("bold", "spotlight") and hero:
        logo = _logo_url(brand, True)
        header = (f'<tr><td style="background:{navy};padding:22px 32px;text-align:center">'
                  + (f'<img src="{_e(logo)}" alt="{_e(brand.name)}" height="42" style="height:42px;border:0">' if logo
                     else f'<span style="font:bold 22px {head_font};color:#fff">{_e(brand.name)}</span>')
                  + '</td></tr>')
        if layout == "spotlight":
            header += (f'<tr><td style="padding:0">{img(hero, 340, 0)}</td></tr>'
                       f'<tr><td style="background:{navy};padding:30px 36px 34px;text-align:{align}">'
                       f'<div style="font:bold 32px/1.3 {head_font};color:#ffffff">{_e(headline)}</div>'
                       f'<div style="width:70px;height:5px;background:{gold};margin:16px 0"></div>'
                       f'<div style="font:16px/1.7 {body_font};color:#e9ecf5">{_e(intro)}</div>'
                       f'{button(cta_text, cta_url)}</td></tr>')
        else:
            header += (f'<tr><td style="background:{gold};padding:34px 36px;text-align:{align}">'
                       f'<div style="font:900 34px/1.25 {head_font};color:{navy}">{_e(headline)}</div>'
                       f'<div style="font:16px/1.7 {body_font};color:{navy};margin-top:12px">{_e(intro)}</div></td></tr>'
                       f'<tr><td style="padding:0">{img(hero, 300, 0)}</td></tr>')
        intro_block = ""
    else:
        dark = layout in ("classic", "digest")
        logo = _logo_url(brand, dark)
        bg = navy if dark else "#ffffff"
        name_color = "#ffffff" if dark else navy
        header = (f'<tr><td style="background:{bg};padding:24px 32px;text-align:{"center" if layout != "digest" else align};'
                  f'{"border-bottom:4px solid " + gold if dark else "border-bottom:1px solid #eee"}">'
                  + (f'<img src="{_e(logo)}" alt="{_e(brand.name)}" height="44" style="height:44px;border:0">' if logo
                     else f'<span style="font:bold 22px {head_font};color:{name_color}">{_e(brand.name)}</span>')
                  + '</td></tr>')
        intro_block = (f'<tr><td style="padding:32px 36px 8px;text-align:{align}">'
                       + (f'<div style="margin-bottom:22px">{img(hero, 280)}</div>' if hero and layout != "minimal" else "")
                       + f'<h1 style="{h1}">{_e(headline)}</h1>'
                       + (f'<div style="width:60px;height:4px;background:{gold};margin:0 0 16px"></div>' if layout != "minimal"
                          else f'<div style="width:40px;height:1px;background:{gold};margin:0 0 16px"></div>')
                       + f'<p style="{p}">{_e(intro)}</p>' + (button(cta_text, cta_url) if layout == "minimal" else "")
                       + '</td></tr>')

    # sections
    rows = []
    for i, sec in enumerate(sections, 1):
        t, txt, im = sec.get("title") or "", sec.get("text") or "", sec.get("image") or ""
        more = button(sec.get("button") or (VIEW[lang] if sec.get("link") else ""), sec.get("link") or "", light=False) \
            if sec.get("link") else ""
        num = (f'<span style="display:inline-block;width:30px;height:30px;line-height:30px;border-radius:50%;'
               f'background:{gold};color:{navy};font:bold 14px {body_font};text-align:center;margin-{"left" if rtl else "right"}:8px">'
               f'{i}</span>') if family in SKINS["numbered"] else ""
        h2 = f'<h2 style="font:bold 21px/1.35 {head_font};color:{title_c};margin:0 0 8px">{num}{_e(t)}</h2>'
        divider = (f'<div style="border-top:2px dotted {gold};margin:6px 0 0"></div>' if family in SKINS["dotted"]
                   else f'<div style="border-top:1px solid #ececec;margin:6px 0 0"></div>')
        if layout == "magazine" and im:
            first, second = (f'<td width="46%" valign="top" style="padding:0 0 0 0">{img(im, 190)}</td>',
                             f'<td valign="top" style="padding:0 18px;text-align:{align}">{h2}<p style="{p}">{_e(txt)}</p>{more}</td>')
            cells = second + first if (i % 2 == 0) != rtl else first + second
            rows.append(f'<tr><td style="padding:18px 36px"><table role="presentation" width="100%" cellpadding="0" '
                        f'cellspacing="0"><tr>{cells}</tr></table>{divider}</td></tr>')
        elif layout == "digest":
            thumb = (f'<td width="110" valign="top">{img(im, 90, 8)}</td>' if im else "")
            text_td = f'<td valign="top" style="padding:0 14px;text-align:{align}">{h2}<p style="{p};font-size:15px">{_e(txt)}</p>{more}</td>'
            cells = text_td + thumb if rtl else thumb + text_td
            rows.append(f'<tr><td style="padding:14px 36px"><table role="presentation" width="100%" cellpadding="0" '
                        f'cellspacing="0"><tr>{cells}</tr></table>{divider}</td></tr>')
        elif layout == "bold":
            rows.append(f'<tr><td style="padding:22px 36px;text-align:{align}">'
                        f'<div style="background:{surface};border-radius:{radius}px;padding:22px 24px;border-{"right" if rtl else "left"}:6px solid {gold}">'
                        + (f'<div style="margin-bottom:14px">{img(im, 220)}</div>' if im else "")
                        + f'{h2}<p style="{p}">{_e(txt)}</p>{more}</div></td></tr>')
        else:   # classic, minimal, spotlight
            rows.append(f'<tr><td style="padding:20px 36px;text-align:{align}">'
                        + (f'<div style="margin-bottom:14px">{img(im, 240)}</div>' if im and layout != "minimal" else "")
                        + f'{h2}<p style="{p}">{_e(txt)}</p>{more}{divider}</td></tr>')

    cta_block = ""
    if cta_text and layout not in ("spotlight", "minimal"):
        cta_block = (f'<tr><td style="padding:24px 36px 30px;text-align:center">'
                     f'<div style="background:{navy};border-radius:{radius}px;padding:28px 24px">'
                     f'<div style="font:bold 22px {head_font};color:#ffffff">{_e(content.get("cta_title") or cta_text)}</div>'
                     f'<table role="presentation" align="center" cellpadding="0" cellspacing="0"><tr><td>{button(cta_text, cta_url)}'
                     f'</td></tr></table></div></td></tr>')
    ps_block = f'<tr><td style="padding:0 36px 24px;text-align:{align}"><p style="{p};font-style:italic">{_e(ps)}</p></td></tr>' if ps else ""

    unsub_url = f"{base}/api/t/u/{token}" if token and base else "#"
    footer = (f'<tr><td style="background:{navy};padding:24px 32px;text-align:center;font:13px/1.7 {body_font};color:#c9cfe0">'
              f'{_e(WHY[lang])} {_e(brand.name)}.<br>'
              + (f'{_e(get_address(brand))}<br>' if get_address(brand) else "")
              + (f'<a href="{_e(link(brand.website))}" style="color:{c.get("goldLight", gold)}">{_e(brand.website)}</a> · ' if brand.website else "")
              + f'<a href="{_e(unsub_url)}" style="color:{c.get("goldLight", gold)}">{UNSUB[lang]}</a></td></tr>')
    pixel = f'<img src="{base}/api/t/o/{token}.gif" width="1" height="1" alt="" style="display:block;border:0">' \
        if token and base else ""
    pre = _e(nl.preheader)
    page_bg = "#f2f2f2" if layout != "minimal" else "#ffffff"
    html = (f'<!doctype html><html lang="{lang}" dir="{dir_}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{_e(nl.subject)}</title></head>'
            f'<body style="margin:0;padding:0;background:{page_bg}">'
            f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{pre}</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{page_bg}"><tr>'
            f'<td align="center" style="padding:24px 10px">'
            f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" dir="{dir_}" '
            f'style="width:100%;max-width:600px;background:#ffffff;border-radius:{min(radius, 14)}px;overflow:hidden">'
            f'{header}{intro_block}{"".join(rows)}{cta_block}{ps_block}{footer}</table>{pixel}</td></tr></table></body></html>')
    text_parts = [headline, intro] + [f"{x.get('title', '')}\n{x.get('text', '')}\n{x.get('link', '')}".strip()
                                      for x in sections] + [f"{cta_text}: {cta_url}" if cta_text else "", ps,
                                                            f"{UNSUB[lang]}: {unsub_url}"]
    return html, "\n\n".join(x for x in text_parts if x)


def get_address(brand: Brand) -> str:
    try:
        with session_scope() as db:
            return mailer.load(db).get("company_address", "")
    except Exception:  # noqa: BLE001
        return ""


# ------------------------------------------------------------------ AI content
NEWSLETTER_TOOL = {
    "name": "newsletter",
    "description": "Write an email newsletter.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Subject line: specific and enticing, max 60 characters, "
                                                         "no spammy words, no ALL CAPS."},
            "preheader": {"type": "string", "description": "Preview text after the subject, max 90 characters."},
            "headline": {"type": "string", "description": "Main headline of the email."},
            "intro": {"type": "string", "description": "2-3 warm sentences that open the email."},
            "sections": {"type": "array", "items": {"type": "object", "properties": {
                "title": {"type": "string"}, "text": {"type": "string", "description": "2-4 sentences."},
                "button": {"type": "string", "description": "Short button label if the item has a link."},
                "ref": {"type": "integer", "description": "Number of the material item this section is about, or 0."}},
                "required": ["title", "text"]}},
            "cta_title": {"type": "string", "description": "A short line above the main button."},
            "cta_text": {"type": "string", "description": "Main button label (2-4 words)."},
            "ps": {"type": "string", "description": "Optional P.S. line, or empty."},
        },
        "required": ["subject", "preheader", "headline", "intro", "sections", "cta_text"],
    },
}


def _material(db, draft_ids: list[int], product_ids: list[int]) -> list[dict]:  # noqa: ANN001
    items = []
    for d in db.scalars(select(Draft).where(Draft.id.in_(draft_ids or [0]))):
        cover = next((s.image_url for s in sorted(d.slides, key=lambda s: s.position) if s.image_url), None)
        items.append({"title": d.hook, "text": d.caption[:900], "image": cover,
                      "link": d.link_url or d.source_url or ""})
    for p in db.scalars(select(Product).where(Product.id.in_(product_ids or [0]))):
        items.append({"title": p.name, "text": (p.description or "")[:700] + (f" — {p.price} {p.currency}" if p.price else ""),
                      "image": p.image_url, "link": p.url})
    return items


async def generate(newsletter_id: int, topic: str = "", draft_ids: list[int] | None = None,
                   product_ids: list[int] | None = None, sections: int = 4) -> None:
    """Fill a newsletter with AI-written content from posts, products and/or a topic."""
    with session_scope() as db:
        nl = db.get(Newsletter, newsletter_id)
        brand = db.scalar(select(Brand).order_by(Brand.is_default.desc(), Brand.id))
        gen = dict(pipeline.app_settings.get_section(db, "generation"))
        gen["language"] = nl.language
        material = _material(db, draft_ids or [], product_ids or [])
        ctx = pipeline.brand_context(brand)
        website = brand.website or ""
    listing = "\n".join(f"[{i}] {m['title']}\n{m['text']}" for i, m in enumerate(material, 1))
    user = (f"Write an email newsletter for {ctx.name}'s subscribers.\n"
            + (f"Topic / angle: {topic}\n" if topic else "")
            + (f"Material to feature (one section per item, set ref to its number):\n{listing}\n" if material
               else f"Write {sections} useful sections for the audience.\n")
            + "Email style: personal, scannable, useful; short paragraphs; one clear main call to action. "
              "Use only facts from the material. Use the newsletter tool.")
    system = generator.build_system_prompt(ctx, gen).split("Writing playbook")[0] + \
        "You write email newsletters. Write everything in the language and dialect above."
    if generator.ai_available():
        data = await generator._call_model(system, user, NEWSLETTER_TOOL, max_tokens=3000)
    else:
        data = {"subject": topic or (material[0]["title"] if material else ctx.name), "preheader": "",
                "headline": topic or ctx.name, "intro": "", "cta_text": "",
                "sections": [{"title": m["title"], "text": m["text"][:300], "ref": i} for i, m in enumerate(material, 1)]}
    secs = []
    for s in (data.get("sections") or [])[:8]:
        if not isinstance(s, dict):
            continue
        ref = s.get("ref") or 0
        m = material[ref - 1] if isinstance(ref, int) and 0 < ref <= len(material) else {}
        secs.append({"title": generator._text(s.get("title")), "text": generator._text(s.get("text")),
                     "button": generator._text(s.get("button")) if m.get("link") else "",
                     "image": m.get("image") or "", "link": m.get("link") or ""})
    hero = next((m["image"] for m in material if m.get("image")), "")
    with session_scope() as db:
        nl = db.get(Newsletter, newsletter_id)
        nl.subject = generator._text(data.get("subject"))[:300] or nl.subject
        nl.preheader = generator._text(data.get("preheader"))[:300]
        nl.content = {"headline": generator._text(data.get("headline")), "intro": generator._text(data.get("intro")),
                      "hero_image": hero, "sections": secs, "cta_title": generator._text(data.get("cta_title")),
                      "cta_text": generator._text(data.get("cta_text")), "cta_url": website,
                      "ps": generator._text(data.get("ps"))}
        nl.status = "draft" if nl.status == "generating" else nl.status
        nl.error = None


# ------------------------------------------------------------------ sending
def recipients(db, list_ids: list[int]) -> list[Contact]:  # noqa: ANN001
    rows = db.scalars(select(Contact).where(Contact.status == "subscribed")).all()
    wanted = set(int(i) for i in list_ids or [])
    return [c for c in rows if not wanted or wanted & set(int(x) for x in (c.list_ids or []))]


def send_newsletter(newsletter_id: int, org_id: int) -> None:
    """Send to every subscribed contact of the chosen lists (runs in a worker thread)."""
    with use_org(org_id):
        with session_scope() as db:
            nl = db.get(Newsletter, newsletter_id)
            if nl is None or nl.status == "sent":
                return
            cfg = mailer.load(db)
            if not mailer.ready(cfg):
                nl.status, nl.error = "failed", "حساب الإرسال غير مضبوط — أكمل إعدادات البريد أولًا"
                return
            nl.status, nl.error = "sending", None
            done = {d.contact_id for d in db.scalars(select(Delivery).where(Delivery.newsletter_id == nl.id))}
            for c in recipients(db, nl.list_ids):
                if c.id not in done:
                    db.add(Delivery(newsletter_id=nl.id, contact_id=c.id, email=c.email, name=c.name,
                                    token=secrets.token_urlsafe(18)))
        with session_scope() as db:
            nl = db.get(Newsletter, newsletter_id)
            brand = db.scalar(select(Brand).order_by(Brand.is_default.desc(), Brand.id))
            family = pipeline.family_of(db, org_id)
            queue = [(d.id, d.email, d.name, d.token) for d in
                     db.scalars(select(Delivery).where(Delivery.newsletter_id == nl.id, Delivery.status == "queued"))]
            subject = nl.subject
            pace = 60 / max(1, int(cfg.get("batch_per_minute") or 120))
            base = (get_settings().public_base_url or "").rstrip("/")
            db.expunge(brand)
            db.expunge(nl)
        failures = 0
        for did, email, name, token in queue:
            html, text = render(nl, brand, family, token)
            headers = {"List-Unsubscribe": f"<{base}/api/t/u/{token}>" if base else "",
                       "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
            headers = {k: v for k, v in headers.items() if v}
            try:
                mailer.send(cfg, email, name, subject, html, text, headers)
                status, error = "sent", None
            except Exception as exc:  # noqa: BLE001
                status, error, failures = "failed", str(exc)[:500], failures + 1
            with session_scope() as db:
                d = db.get(Delivery, did)
                d.status, d.error = status, error
                d.sent_at = utcnow() if status == "sent" else None
            time.sleep(pace)
        with session_scope() as db:
            nl = db.get(Newsletter, newsletter_id)
            sent = db.scalar(select(func.count()).select_from(Delivery).where(
                Delivery.newsletter_id == nl.id, Delivery.status == "sent")) or 0
            nl.status = "sent" if sent else "failed"
            nl.sent_at = utcnow()
            if failures:
                first = db.scalar(select(Delivery.error).where(Delivery.newsletter_id == nl.id,
                                                               Delivery.status == "failed").limit(1))
                nl.error = first


async def send_due() -> None:
    """Scheduled newsletters whose time has come (called by the scheduler for each company)."""
    from ..db import current_org
    now = datetime.now(timezone.utc)
    with session_scope() as db:
        due = [n.id for n in db.scalars(select(Newsletter).where(Newsletter.status == "scheduled"))
               if n.scheduled_at and (n.scheduled_at if n.scheduled_at.tzinfo else
                                      n.scheduled_at.replace(tzinfo=timezone.utc)) <= now]
        for nid in due:
            db.get(Newsletter, nid).status = "sending"
    for nid in due:                      # sending runs in the background; the scheduler moves on
        task = asyncio.create_task(asyncio.to_thread(send_newsletter, nid, current_org.get()))
        _RUNNING.add(task)
        task.add_done_callback(_RUNNING.discard)


_RUNNING: set = set()


def stats(db, nl: Newsletter) -> dict[str, Any]:  # noqa: ANN001
    q = select(Delivery).where(Delivery.newsletter_id == nl.id)
    rows = list(db.scalars(q))
    sent = [d for d in rows if d.status == "sent"]
    opened = [d for d in sent if d.opened_at]
    clicked = [d for d in sent if d.clicked_at]
    unsub = [d for d in rows if d.unsubscribed_at]
    pct = lambda a, b: round(100 * a / b, 1) if b else 0  # noqa: E731
    return {"recipients": len(rows), "sent": len(sent), "failed": sum(1 for d in rows if d.status == "failed"),
            "queued": sum(1 for d in rows if d.status == "queued"), "opened": len(opened),
            "open_rate": pct(len(opened), len(sent)), "opens_total": sum(d.open_count for d in rows),
            "clicked": len(clicked), "click_rate": pct(len(clicked), len(sent)),
            "clicks_total": sum(d.click_count for d in rows), "unsubscribed": len(unsub)}


def org_language(db, org_id) -> str:  # noqa: ANN001
    org = db.get(Organization, org_id) if org_id else None
    return org.language if org and org.language in UNSUB else "ar"


__all__ = ["render", "generate", "send_newsletter", "send_due", "stats", "designs_for", "industries", "cards"]
