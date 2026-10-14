"""Flyer image for a product, service, course, programme or offer — like a printed travel/offer flyer.

One 1080×1350 image that carries everything a customer needs: the company logo at the top, a big
headline over the product's photo, feature chips with icons (flights, hotel, visa, certificate…),
price boxes (old price struck through), a requirements list, a call-to-action pill and, at the
bottom, the company's contact band: WhatsApp numbers, branch addresses, website and a QR code that
opens the product's page. The text comes from the AI (FLYER_TOOL) and the contact data from the
brand settings. Eight layouts rotate from one post to the next; all are light, with the brand's own
colours for the bands, chips and prices.
"""
from __future__ import annotations

import base64
import html
import io
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

LAYOUTS = ("poster", "side", "card", "price_hero", "arch", "diagonal", "ticket", "magazine")

# simple line icons (24×24, stroke) — the AI picks one per feature
ICONS = {
    "plane": '<path d="M2 16l20-8-3-2-7 3-5-5-2 1 3 6-4 2-2-1-1 1 3 3z"/>',
    "hotel": '<path d="M3 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16M3 21h18M17 9h2a2 2 0 0 1 2 2v10M7 7h2M11 7h2M7 11h2M11 11h2M8 21v-4h4v4"/>',
    "car": '<path d="M5 17h14M4 17v-5l2-5h12l2 5v5M4 12h16"/><circle cx="7.5" cy="17.5" r="1.8"/><circle cx="16.5" cy="17.5" r="1.8"/>',
    "bus": '<rect x="4" y="3" width="16" height="15" rx="3"/><path d="M4 11h16M8 21v-3M16 21v-3"/><circle cx="8" cy="14.5" r="1"/><circle cx="16" cy="14.5" r="1"/>',
    "ship": '<path d="M3 17l2 4h14l2-4-9-3zM6 14V8h12v6M12 3v5"/>',
    "meal": '<path d="M5 3v8a2 2 0 0 0 2 2v8M9 3v8a2 2 0 0 1-2 2M7 3v6M17 21V3c-2 0-4 3-4 7 0 2 1 3 4 3"/>',
    "guide": '<circle cx="12" cy="7" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-6 7-6s7 2.5 7 6M16 4.5a3.5 3.5 0 0 1 0 7M18 14c2.5.6 4 2.8 4 6"/>',
    "visa": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="11" r="2.5"/><path d="M5.5 17c.6-2 2-3 3.5-3s2.9 1 3.5 3M15 9h3M15 13h3"/>',
    "ticket": '<path d="M3 8a2 2 0 0 0 0 4v0a2 2 0 0 1 0 4v2h18v-2a2 2 0 0 1 0-4 2 2 0 0 0 0-4V6H3z"/><path d="M14 6v12" stroke-dasharray="2 2"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "location": '<path d="M12 22s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/>',
    "gift": '<rect x="3" y="8" width="18" height="5" rx="1"/><path d="M5 13v8h14v-8M12 8v13M12 8S10 3 7.5 4.5 9 8 12 8zM12 8s2-5 4.5-3.5S15 8 12 8z"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "wifi": '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1"/>',
    "certificate": '<rect x="3" y="3" width="18" height="13" rx="2"/><path d="M7 8h10M7 11h6"/><circle cx="16" cy="17" r="3"/><path d="M14.5 19.5L14 23l2-1 2 1-.5-3.5"/>',
    "book": '<path d="M12 6c-2-1.5-5-2-8-1.5v14c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5v-14c-3-.5-6 0-8 1.5zM12 6v14"/>',
    "laptop": '<rect x="4" y="4" width="16" height="11" rx="1.5"/><path d="M2 19h20l-2-4H4z"/>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
    "truck": '<path d="M2 6h12v10H2zM14 9h4l3 3v4h-7"/><circle cx="6" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>',
    "tag": '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="8" cy="8" r="1.5"/>',
    "percent": '<path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
    "heart": '<path d="M12 20s-8-5-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 9c0 6-8 11-8 11z"/>',
    "camera": '<path d="M4 7h3l2-3h6l2 3h3a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "medal": '<circle cx="12" cy="15" r="6"/><path d="M8 3h8l-2 6.5M8 3l2 6.5M12 12.5v5"/>',
    "support": '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="2.5" y="13" width="4" height="6" rx="1.5"/><rect x="17.5" y="13" width="4" height="6" rx="1.5"/><path d="M20 19c0 2-2 2.5-5 2.5"/>',
    "home": '<path d="M3 11l9-7 9 7M5 9.5V20h14V9.5M10 20v-5h4v5"/>',
    "tools": '<path d="M14 6a4 4 0 0 0 5 5l-9 9a2 2 0 0 1-3-3l9-9a4 4 0 0 0-2-2z"/>',
    "leaf": '<path d="M20 4C9 4 4 10 4 16c0 2 .5 3 1 4 1-5 4-8 9-10-4 2-6 5-7 10 9 1 13-7 13-16z"/>',
    "sparkle": '<path d="M12 3c.8 5 2 6.2 7 7-5 .8-6.2 2-7 7-.8-5-2-6.2-7-7 5-.8 6.2-2 7-7z"/>',
}
WHATSAPP = ('<svg viewBox="0 0 24 24" class="fl-wa"><path fill="#25D366" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2z"/>'
            '<path fill="#fff" d="M8.6 6.9c.2-.4.4-.4.7-.4h.6c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .6l-.4.6-.4.4c-.1.2-.2.3 0 .6.6 1 1.3 1.8 2.3 2.4.6.4 1 .5 1.2.5.2 0 .4-.2.6-.5l.6-.8c.2-.2.4-.2.6-.1l1.9.9c.3.1.4.2.5.3 0 .2 0 .9-.3 1.6-.3.7-1.6 1.3-2.2 1.3-.6.1-1.2.2-3.9-.9-3.2-1.3-5.2-4.6-5.4-4.8-.2-.2-1.3-1.7-1.3-3.2s.8-2.3 1.1-2.6z"/></svg>')
PIN = '<svg viewBox="0 0 24 24" class="fl-ic2"><path d="M12 22s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>'
GLOBE = ('<svg viewBox="0 0 24 24" class="fl-ic2"><circle cx="12" cy="12" r="9"/>'
         '<path d="M3 12h18M12 3c-3 3.5-3 14.5 0 18M12 3c3 3.5 3 14.5 0 18"/></svg>')
MAIL = '<svg viewBox="0 0 24 24" class="fl-ic2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>'
ARROW = {"rtl": '<svg viewBox="0 0 24 24"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>',
         "ltr": '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'}

LABELS = {
    "ar": {"req": "المتطلبات", "price": "السعر", "from": "يبدأ من", "scan": "امسح للتفاصيل", "contact": "للحجز والاستفسار",
           "branches": "فروعنا", "book": "احجز الآن"},
    "en": {"req": "Requirements", "price": "Price", "from": "From", "scan": "Scan for details", "contact": "Book & enquire",
           "branches": "Branches", "book": "Book now"},
    "ms": {"req": "Keperluan", "price": "Harga", "from": "Dari", "scan": "Imbas untuk butiran", "contact": "Tempah & tanya",
           "branches": "Cawangan", "book": "Tempah sekarang"},
    "fr": {"req": "Conditions", "price": "Prix", "from": "Dès", "scan": "Scannez pour les détails",
           "contact": "Réservation & infos", "branches": "Agences", "book": "Réservez"},
}

# sample flyer for the brand page preview
SAMPLE = {
    "ar": {"headline": "باقة العطلة المميزة", "highlight": "المميزة", "tagline": "كل ما تحتاجه في عرض واحد بسعر واضح",
           "badge": "عرض محدود", "features": [{"icon": "star", "text": "جودة مضمونة"}, {"icon": "gift", "text": "هدية ترحيبية"},
                                              {"icon": "support", "text": "دعم على مدار الساعة"}],
           "prices": [{"label": "للشخص", "amount": "1,999", "currency": "SAR", "old": "2,450"}],
           "requirements": ["حجز مسبق", "عربون 30%"], "cta": "احجز الآن"},
    "en": {"headline": "The Signature Package", "highlight": "Signature", "tagline": "Everything you need in one clear offer",
           "badge": "Limited offer", "features": [{"icon": "star", "text": "Guaranteed quality"}, {"icon": "gift", "text": "Welcome gift"},
                                                  {"icon": "support", "text": "24/7 support"}],
           "prices": [{"label": "Per person", "amount": "1,999", "currency": "USD", "old": "2,450"}],
           "requirements": ["Book in advance", "30% deposit"], "cta": "Book now"},
}


FLYER_TOOL = {
    "name": "write_flyer",
    "description": "Write the text of a one-page promotional flyer (like a printed offer flyer) for one product, "
                   "service, course, programme or offer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string", "description": "The big headline: the product/destination/offer name, max 5 words."},
            "highlight": {"type": "string", "description": "1-2 words copied EXACTLY from the headline, shown in the accent colour."},
            "tagline": {"type": "string", "description": "One selling line under the headline, max 10 words."},
            "badge": {"type": "string", "description": "A short tag, max 4 words: duration (e.g. 5 أيام / 4 ليالٍ), "
                                                       "'عرض محدود', 'جديد', level of a course… Empty if nothing fits."},
            "features": {"type": "array", "maxItems": 6, "description": "What is included / key benefits, 3-6 items.",
                         "items": {"type": "object", "properties": {
                             "icon": {"type": "string", "enum": list(ICONS)},
                             "text": {"type": "string", "description": "max 4 words"}},
                             "required": ["icon", "text"]}},
            "prices": {"type": "array", "maxItems": 3,
                       "description": "Prices EXACTLY as given in the details (never invent a price). Several when there "
                                      "are options (per adult / child, single / double room…). Empty if no price is given.",
                       "items": {"type": "object", "properties": {
                           "label": {"type": "string", "description": "max 3 words, e.g. للشخص / غرفة مزدوجة / Adult"},
                           "amount": {"type": "string", "description": "digits only, e.g. 3,950"},
                           "currency": {"type": "string"},
                           "old": {"type": "string", "description": "old price before the offer, digits only, or empty"}},
                           "required": ["amount"]}},
            "requirements": {"type": "array", "maxItems": 4, "items": {"type": "string"},
                             "description": "Conditions / what the customer needs (passport valid 6 months, photo, "
                                            "prerequisites…), max 6 words each. Only when relevant; often empty."},
            "cta": {"type": "string", "description": "Call to action on the pill, max 4 words (احجز مقعدك الآن)."},
        },
        "required": ["headline", "tagline", "features", "prices", "cta"],
    },
}


def _e(text: Any) -> str:
    return html.escape(str(text or ""))


def _clip(text: Any, words: int) -> str:
    parts = str(text or "").split()
    return " ".join(parts[:words])


def clean(data: dict | None) -> dict:
    """Keep the flyer text inside the limits the design can hold."""
    data = dict(data or {})
    feats = []
    for f in data.get("features") or []:
        if isinstance(f, dict) and str(f.get("text") or "").strip():
            feats.append({"icon": f.get("icon") if f.get("icon") in ICONS else "check", "text": _clip(f["text"], 5)})
    prices = []
    for p in data.get("prices") or []:
        if isinstance(p, dict) and re.search(r"\d", str(p.get("amount") or "")):
            prices.append({"label": _clip(p.get("label"), 4), "amount": str(p["amount"]).strip()[:14],
                           "currency": str(p.get("currency") or "").strip()[:6],
                           "old": str(p.get("old") or "").strip()[:14] if re.search(r"\d", str(p.get("old") or "")) else ""})
    return {"headline": _clip(data.get("headline"), 7), "highlight": str(data.get("highlight") or "").strip(),
            "tagline": _clip(data.get("tagline"), 14), "badge": _clip(data.get("badge"), 5),
            "features": feats[:6], "prices": prices[:3],
            "requirements": [_clip(x, 8) for x in (data.get("requirements") or []) if str(x).strip()][:4],
            "cta": _clip(data.get("cta"), 5)}


ICON_WORDS = [("plane", r"طيران|تذكر|flight|air"), ("hotel", r"فندق|إقامة|سكن|hotel|stay|night|ليال"),
              ("car", r"سيار|تنقل|car|transfer"), ("meal", r"وجب|إفطار|فطور|طعام|meal|breakfast"),
              ("guide", r"مرشد|guide"), ("visa", r"تأشير|visa"), ("certificate", r"شهاد|certific"),
              ("ship", r"بحر|كروز|cruise|boat"), ("shield", r"تأمين|ضمان|insur|warrant"), ("truck", r"شحن|توصيل|deliver|ship")]


def demo(title: str, body: str, price: str = "", currency: str = "", lang: str = "ar") -> dict:
    """A flyer text without the AI: the name, the first lines of the details as features, the price as given."""
    lines = [x.strip(" -•·\t") for x in re.split(r"[\n؛;•]|\. ", body or "") if 3 < len(x.strip()) < 60]
    lines = [x for x in lines if not x.lower().startswith(("price", "type", "page"))]
    feats = []
    for x in lines[:5]:
        icon = next((i for i, rx in ICON_WORDS if re.search(rx, x, re.I)), "check")
        feats.append({"icon": icon, "text": x})
    words = LABELS.get(lang, LABELS["en"])
    return clean({"headline": title, "tagline": "", "features": feats,
                  "prices": [{"label": "", "amount": price, "currency": currency}] if price else [],
                  "cta": words["book"]})


def system_prompt(brand_name: str, lang: str, dialect_rules: str = "") -> str:
    language = {"ar": "Arabic", "en": "English", "ms": "Malay", "fr": "French"}.get(lang, "Arabic")
    return (f"You write the text of promotional flyers for {brand_name}. Write in {language}. "
            "A flyer is read in three seconds: short, concrete, attractive words. Use only facts from the details; "
            "never invent prices, dates, inclusions or conditions. " + (dialect_rules or ""))


async def write(brand_name: str, lang: str, dialect_rules: str, title: str, body: str,
                price: str = "", currency: str = "") -> dict:
    """The flyer text from the AI (or a plain one without it)."""
    from . import generator
    if not generator.ai_available():
        return demo(title, body, price, currency, lang)
    try:
        data = await generator._call_model(system_prompt(brand_name, lang, dialect_rules),
                                           f"Name: {title}\nDetails:\n{body}"[:6000], FLYER_TOOL, max_tokens=1200)
        out = clean(data)
        if not out["headline"]:
            out["headline"] = _clip(title, 7)
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("flyer text failed: %s", exc)
        return demo(title, body, price, currency, lang)


# ------------------------------------------------------------------ contact data of the company
def clean_contact(data: dict | None) -> dict:
    data = dict(data or {})
    phones = []
    for p in data.get("phones") or []:
        if isinstance(p, dict) and re.search(r"\d{5}", re.sub(r"\D", "", str(p.get("number") or ""))):
            phones.append({"number": str(p["number"]).strip()[:24], "label": str(p.get("label") or "").strip()[:24],
                           "whatsapp": p.get("whatsapp") is not False})
    branches = []
    for b in data.get("branches") or []:
        if isinstance(b, dict) and (str(b.get("name") or "").strip() or str(b.get("address") or "").strip()):
            branches.append({"name": str(b.get("name") or "").strip()[:40], "address": str(b.get("address") or "").strip()[:120]})
    return {"phones": phones[:4], "branches": branches[:4], "email": str(data.get("email") or "").strip()[:80],
            "qr_url": str(data.get("qr_url") or "").strip()[:500], "show": data.get("show") is not False}


def qr_svg(url: str, dark: str) -> str:
    """A QR code (data URI) that opens the page."""
    if not url:
        return ""
    try:
        import segno
        return segno.make(url, error="m").svg_data_uri(dark=dark, light="#ffffff", border=1, scale=8)
    except Exception as exc:  # noqa: BLE001
        log.warning("qr failed: %s", exc)
        return ""


# ------------------------------------------------------------------ colours and photo
def _rgb(hex_colour: str) -> tuple[float, float, float]:
    h = (hex_colour or "").lstrip("#")
    if len(h) != 6:
        return (0.1, 0.15, 0.3)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lum(hex_colour: str) -> float:
    r, g, b = _rgb(hex_colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _mix(hex_colour: str, amount: float, to=(1, 1, 1)) -> str:
    r, g, b = _rgb(hex_colour)
    return "#" + "".join(f"{round((c + (t - c) * amount) * 255):02X}" for c, t in zip((r, g, b), to))


def photo_fit(data: bytes | None) -> str:
    """'contain' for a product shot on a plain white background (shown whole), 'cover' for a scene."""
    if not data:
        return "cover"
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((200, 200))
        w, h = img.size
        corners = [img.getpixel((x, y)) for x, y in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2))]
        return "contain" if all(min(c) > 238 for c in corners) else "cover"
    except Exception:  # noqa: BLE001
        return "cover"


def _uri(data: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"


def _old(price: dict) -> str:
    return f"<s>{_e(price.get('old'))}</s>" if price.get("old") else ""


def _icon(name: str) -> str:
    return f'<svg viewBox="0 0 24 24" class="fl-ic">{ICONS.get(name) or ICONS["check"]}</svg>'


CSS = """
.fl { position: absolute; inset: 0; overflow: hidden; background: var(--fl-surface); color: var(--fl-ink); }
.fl-photo { position: absolute; background-size: cover; background-position: center; background-color: var(--fl-soft); }
.fl-photo.contain { background-size: contain; background-repeat: no-repeat; background-color: #fff; }
.fl-photo.empty { background: linear-gradient(135deg, var(--fl-soft) 0%, var(--fl-soft2) 100%); display: grid; place-items: center; }
.fl-photo.empty .fl-ic { width: 220px; height: 220px; stroke: var(--fl-accent); opacity: .55; }
.fl-head { position: absolute; top: 40px; left: 56px; right: 56px; display: flex; align-items: center;
  justify-content: space-between; z-index: 6; gap: 20px; }
.fl-head .logo { background: #fff; padding: 14px 26px; border-radius: 22px; box-shadow: 0 8px 26px rgba(20,30,60,.14); }
.fl-head .logo.plate { background: var(--fl-ink); }
.fl-head .logo img { height: 78px; filter: none; }
.fl-head .logo .wordmark { color: var(--fl-ink); text-shadow: none; font-size: 40px; }
.fl-head .logo.plate .wordmark { color: #fff; }
.fl-head .logo .wordmark span { color: var(--fl-accent); }
.fl-badge { background: var(--fl-accent); color: var(--fl-on-accent); font-weight: 900; font-size: 30px; padding: 12px 30px;
  border-radius: 999px; box-shadow: 0 8px 20px rgba(20,30,60,.18); white-space: nowrap; }
.fl-main { position: absolute; z-index: 5; font-size: 30px; display: flex; flex-direction: column; gap: .62em; }
.fl-title h1 { font-size: 2.75em; line-height: 1.12; font-weight: 900; color: var(--fl-ink); }
.fl-title h1 em { font-style: normal; color: var(--fl-accent-text); }
.fl-title p { font-size: 1.02em; font-weight: 700; line-height: 1.45; color: var(--fl-ink); opacity: .78; margin-top: .3em; }
.fl-chips { display: grid; grid-template-columns: repeat(3, 1fr); gap: .45em; }
.fl-chip { display: flex; align-items: center; gap: .4em; background: var(--fl-chip); border-radius: .7em; padding: .42em .5em;
  font-weight: 800; font-size: .86em; line-height: 1.25; color: var(--fl-ink); }
.fl-chip .fl-dot { flex: none; width: 1.9em; height: 1.9em; border-radius: 50%; background: var(--fl-ink); display: grid; place-items: center; }
.fl-ic { width: 1.1em; height: 1.1em; fill: none; stroke: #fff; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.fl-row { display: flex; gap: .6em; align-items: stretch; }
.fl-prices { display: flex; gap: .45em; flex: 1.2; }
.fl-price { flex: 1; border: .12em solid var(--fl-accent); background: #fff; border-radius: .7em; padding: .35em .5em .4em;
  text-align: center; display: flex; flex-direction: column; justify-content: center; }
.fl-price small { display: block; font-size: .7em; font-weight: 800; color: var(--fl-ink); opacity: .7; }
.fl-price b { display: block; font-size: 1.75em; font-weight: 900; color: var(--fl-ink); line-height: 1.1; direction: ltr; unicode-bidi: isolate; }
.fl-price b i { font-style: normal; font-size: .45em; margin-inline-start: .2em; color: var(--fl-accent-text); }
.fl-price s { font-size: .72em; font-weight: 700; opacity: .55; direction: ltr; unicode-bidi: isolate; }
.fl-reqs { flex: 1; background: var(--fl-chip); border-radius: .7em; padding: .45em .65em; }
.fl-reqs h4 { font-size: .8em; font-weight: 900; color: var(--fl-accent-text); margin-bottom: .2em; }
.fl-reqs li { list-style: none; font-size: .76em; font-weight: 700; line-height: 1.45; display: flex; gap: .35em; align-items: baseline; }
.fl-reqs li::before { content: "✓"; color: var(--fl-accent-text); font-weight: 900; }
.fl-cta { align-self: center; display: inline-flex; align-items: center; gap: .5em; background: var(--fl-accent);
  color: var(--fl-on-accent); font-weight: 900; font-size: 1.05em; padding: .38em 1.3em; border-radius: 999px;
  box-shadow: 0 .3em .8em rgba(20,30,60,.18); }
.fl-cta b { display: inline-grid; place-items: center; width: 1.5em; height: 1.5em; border-radius: 50%; background: var(--fl-ink); }
.fl-cta b svg { width: .95em; height: .95em; fill: none; stroke: #fff; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
.fl-band { position: absolute; left: 0; right: 0; bottom: 0; height: 214px; background: var(--fl-ink); color: #fff; z-index: 7;
  display: flex; align-items: center; gap: 28px; padding: 0 44px; }
.fl-band::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 8px; background: var(--fl-accent); }
.fl-qr { flex: none; display: flex; flex-direction: column; align-items: center; gap: 6px; }
.fl-qr img { width: 146px; height: 146px; border-radius: 12px; background: #fff; display: block; }
.fl-qr span { font-size: 17px; font-weight: 800; opacity: .85; }
.fl-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.fl-info .fl-k { font-size: 21px; font-weight: 800; color: var(--fl-accent-band); }
.fl-phones { display: flex; flex-wrap: wrap; gap: 8px 26px; }
.fl-phone { display: inline-flex; align-items: center; gap: 8px; font-size: 31px; font-weight: 900; direction: ltr; unicode-bidi: isolate; }
.fl-wa { width: 34px; height: 34px; flex: none; }
.fl-branches { display: flex; flex-wrap: wrap; gap: 4px 22px; font-size: 20px; font-weight: 700; opacity: .92; }
.fl-branch { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fl-ic2 { width: 22px; height: 22px; flex: none; fill: none; stroke: var(--fl-accent-band); stroke-width: 2; }
.fl-web { display: flex; flex-wrap: wrap; gap: 4px 22px; font-size: 21px; font-weight: 800; }
.fl-web span { display: inline-flex; align-items: center; gap: 6px; direction: ltr; unicode-bidi: isolate; }
.fl-band.simple .fl-info { align-items: center; text-align: center; }
.fl-band.simple .fl-web { font-size: 34px; justify-content: center; }

/* 1 poster: photo on top with a rounded edge, a white sheet over it */
.fl-poster .fl-photo { left: 0; right: 0; top: 0; height: 610px; border-radius: 0 0 64px 64px; }
.fl-poster .fl-main { left: 48px; right: 48px; top: 500px; background: #fff; border-radius: 40px; padding: 30px 36px 30px;
  box-shadow: 0 20px 50px rgba(20,30,60,.12); }
/* 2 side: photo column + text column */
.fl-side .fl-photo { top: 170px; bottom: 244px; width: 410px; inset-inline-end: 44px; border-radius: 36px;
  box-shadow: 0 18px 40px rgba(20,30,60,.16); }
.fl-side .fl-main { top: 176px; inset-inline-start: 50px; width: 548px; }
.fl-side .fl-chips, .fl-arch .fl-chips { grid-template-columns: 1fr 1fr; }
.fl-side .fl-row, .fl-arch .fl-row { flex-direction: column; }
.fl-side .fl-head, .fl-arch .fl-head { top: 36px; }
.fl-side::before { content: ""; position: absolute; top: 0; bottom: 0; inset-inline-end: 0; width: 300px; background: var(--fl-soft); }
/* 3 card: the photo fills the image, a white card at the bottom */
.fl-card .fl-photo { inset: 0 0 160px 0; }
.fl-card::after { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 260px; z-index: 2;
  background: linear-gradient(180deg, rgba(10,20,40,.35), rgba(10,20,40,0)); }
.fl-card .fl-main { left: 54px; right: 54px; bottom: 246px; background: rgba(255,255,255,.97); border-radius: 40px;
  padding: 30px 36px; box-shadow: 0 24px 60px rgba(10,20,40,.25); }
/* 4 price hero: big price medal on the photo */
.fl-price_hero .fl-photo { left: 0; right: 0; top: 0; height: 560px; }
.fl-price_hero .fl-main { left: 54px; right: 54px; top: 590px; }
.fl-price_hero .fl-medal { position: absolute; z-index: 6; top: 380px; inset-inline-end: 60px; width: 250px; height: 250px;
  border-radius: 50%; background: var(--fl-accent); color: var(--fl-on-accent); border: 10px solid #fff;
  box-shadow: 0 18px 40px rgba(20,30,60,.25); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.fl-medal small { font-size: 22px; font-weight: 800; max-width: 180px; line-height: 1.25; max-height: 56px; overflow: hidden; }
.fl-medal b { font-size: 64px; font-weight: 900; line-height: 1; direction: ltr; unicode-bidi: isolate; }
.fl-medal i { font-style: normal; font-size: 26px; font-weight: 900; }
.fl-medal s { font-size: 24px; opacity: .75; direction: ltr; unicode-bidi: isolate; }
.fl-price_hero .fl-title { padding-inline-end: 260px; }
/* 5 arch: photo in an arch, cream page */
.fl-arch .fl-photo { top: 176px; height: 760px; width: 400px; inset-inline-end: 50px; border-radius: 200px 200px 28px 28px;
  border: 10px solid #fff; box-shadow: 0 18px 44px rgba(20,30,60,.16); }
.fl-arch .fl-main { top: 182px; inset-inline-start: 50px; width: 548px; }
.fl-arch::before { content: ""; position: absolute; width: 520px; height: 520px; border-radius: 50%; background: var(--fl-soft2);
  bottom: 120px; inset-inline-end: -160px; }
/* 6 diagonal: photo with a slanted edge, title on a brand band */
.fl-diagonal .fl-photo { left: 0; right: 0; top: 0; height: 640px; clip-path: polygon(0 0, 100% 0, 100% 78%, 0 100%); }
.fl-diagonal .fl-main { left: 54px; right: 54px; top: 470px; }
.fl-diagonal .fl-title { background: var(--fl-ink); border-radius: 30px; padding: .55em .8em .6em; box-shadow: 0 18px 40px rgba(20,30,60,.22);
  border-inline-start: 14px solid var(--fl-accent); }
.fl-diagonal .fl-title h1, .fl-diagonal .fl-title p { color: #fff; opacity: 1; }
.fl-diagonal .fl-title h1 em { color: var(--fl-accent-band); }
/* 7 ticket: a boarding-pass card */
.fl-ticket { background: var(--fl-soft); }
.fl-ticket .fl-photo { left: 54px; right: 54px; top: 170px; height: 400px; border-radius: 36px 36px 0 0; }
.fl-ticket .fl-main { left: 54px; right: 54px; top: 570px; background: #fff; border-radius: 0 0 36px 36px; padding: 34px 38px 30px;
  box-shadow: 0 20px 50px rgba(20,30,60,.12); }
.fl-ticket .fl-main::before { content: ""; position: absolute; left: 30px; right: 30px; top: 0; border-top: 4px dashed var(--fl-soft2); }
.fl-ticket .fl-notch { position: absolute; z-index: 6; top: 548px; width: 44px; height: 44px; border-radius: 50%; background: var(--fl-soft); }
.fl-ticket .n1 { left: 32px; } .fl-ticket .n2 { right: 32px; }
/* 8 magazine: headline first, the photo as a wide strip */
.fl-magazine .fl-main { left: 54px; right: 54px; top: 172px; }
.fl-magazine .fl-strip { height: 10.5em; border-radius: .9em; background-size: cover; background-position: center;
  background-color: var(--fl-soft); box-shadow: 0 .5em 1.2em rgba(20,30,60,.14); }
.fl-magazine .fl-strip.contain { background-size: contain; background-repeat: no-repeat; background-color: #fff; }
.fl-magazine .fl-title h1 { font-size: 3em; }
.fl-magazine::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 12px; background: var(--fl-accent); }
"""

FIT = {"poster": 610, "side": 920, "card": 700, "price_hero": 515, "arch": 920, "diagonal": 650, "ticket": 520,
       "magazine": 950}


def contact_band(contact: dict, brand, lang: str, qr_url: str, ink: str) -> str:  # noqa: ANN001
    words = LABELS.get(lang, LABELS["en"])
    qr = qr_svg(qr_url, ink)
    qr_html = f'<div class="fl-qr"><img src="{qr}" alt=""><span>{_e(words["scan"])}</span></div>' if qr else ""
    phones = "".join(f'<span class="fl-phone">{WHATSAPP if p["whatsapp"] else ""}{_e(p["number"])}</span>'
                     for p in contact.get("phones", [])[:3])
    branches = "".join(f'<span class="fl-branch">{PIN}{_e(" — ".join(x for x in (b["name"], b["address"]) if x))}</span>'
                       for b in contact.get("branches", [])[:3])
    web = "".join(f"<span>{icon}{_e(v)}</span>" for icon, v in
                  ((GLOBE, brand.website), (MAIL, contact.get("email")), ("", brand.handle)) if v)
    if not phones and not branches:
        return f'<div class="fl-band simple"><div class="fl-info"><div class="fl-web">{web}</div></div>{qr_html}</div>'
    info = (f'<div class="fl-info">' + (f'<div class="fl-k">{_e(words["contact"])}</div><div class="fl-phones">{phones}</div>' if phones else "")
            + (f'<div class="fl-branches">{branches}</div>' if branches else "")
            + (f'<div class="fl-web">{web}</div>' if web and (not branches or len(contact.get("phones", [])) < 2) else "")
            + "</div>")
    return f'<div class="fl-band">{qr_html}{info}</div>'


def build(spec, brand, lang: str, logo_html: str) -> tuple[str, str]:  # noqa: ANN001
    """(html, css) of a flyer slide."""
    fl = spec.flyer or {}
    layout = fl.get("layout") if fl.get("layout") in LAYOUTS else "poster"
    colors = brand.colors or {}
    ink = colors.get("navy") or "#16244F"
    if _lum(ink) > 0.45:                                   # a light main colour cannot carry white text
        ink = _mix(ink, 0.55, (0, 0, 0))
    accent = colors.get("gold") or "#C6A23C"
    on_accent = ink if _lum(accent) > 0.5 else "#FFFFFF"
    accent_text = accent if _lum(accent) < 0.55 else _mix(accent, 0.35, (0, 0, 0))   # accent words on white
    accent_band = accent if _lum(accent) > 0.35 else _mix(accent, 0.5)                  # accent on the dark band
    surface = {"arch": _mix(accent, 0.9), "magazine": "#FFFFFF", "side": "#FFFFFF"}.get(layout, _mix(ink, 0.95))
    style = (f"--fl-ink:{ink};--fl-accent:{accent};--fl-on-accent:{on_accent};--fl-accent-text:{accent_text};"
             f"--fl-accent-band:{accent_band};--fl-surface:{surface};--fl-soft:{_mix(ink, 0.9)};"
             f"--fl-soft2:{_mix(accent, 0.75)};--fl-chip:{_mix(ink, 0.93)}")
    words = LABELS.get(lang, LABELS["en"])
    rtl = lang == "ar"

    title = _e(fl.get("headline") or spec.heading)
    hl = fl.get("highlight") or ""
    if hl and _e(hl) in title:
        title = title.replace(_e(hl), f"<em>{_e(hl)}</em>", 1)
    tagline = f'<p>{_e(fl.get("tagline"))}</p>' if fl.get("tagline") else ""
    title_html = f'<div class="fl-title"><h1>{title}</h1>{tagline}</div>'

    feats = fl.get("features") or []
    prices = fl.get("prices") or []
    reqs = fl.get("requirements") or []
    medal = ""
    if layout == "price_hero" and prices:
        p = prices[0]
        medal = (f'<div class="fl-medal"><small>{_e(p.get("label") or words["from"])}</small><b>{_e(p["amount"])}</b>'
                 f'<i>{_e(p.get("currency"))}</i>{_old(p)}</div>')
        prices = prices[1:]
    max_feats = 6 if layout in ("side", "arch", "magazine") else (6 if not (prices and reqs) else 3)
    chips = "".join(f'<div class="fl-chip"><span class="fl-dot">{_icon(f["icon"])}</span><span>{_e(f["text"])}</span></div>'
                    for f in feats[:max_feats])
    chips_html = f'<div class="fl-chips">{chips}</div>' if chips else ""
    price_html = "".join(
        f'<div class="fl-price"><small>{_e(p.get("label") or words["price"])}</small>'
        f'<b>{_e(p["amount"])}<i>{_e(p.get("currency"))}</i></b>'
        f'{_old(p)}</div>' for p in prices)
    req_html = (f'<div class="fl-reqs"><h4>{_e(words["req"])}</h4><ul>' + "".join(f"<li>{_e(r)}</li>" for r in reqs)
                + "</ul></div>") if reqs else ""
    row = (f'<div class="fl-row">' + (f'<div class="fl-prices">{price_html}</div>' if price_html else "") + req_html
           + "</div>") if (price_html or req_html) else ""
    cta = (f'<div class="fl-cta">{_e(fl.get("cta") or words["book"])}<b>{ARROW["rtl" if rtl else "ltr"]}</b></div>')

    fit_mode = fl.get("fit") or photo_fit(spec.background)
    if spec.background:
        photo = f'<div class="fl-photo {fit_mode}" style="background-image:url({_uri(spec.background)})"></div>'
        strip = f'<div class="fl-strip {fit_mode}" style="background-image:url({_uri(spec.background)})"></div>'
    else:
        icon = (feats[0]["icon"] if feats else "sparkle")
        photo = f'<div class="fl-photo empty">{_icon(icon)}</div>'
        strip = ""
    parts = [title_html, chips_html, row, cta]
    if layout == "magazine":
        parts = [title_html, strip, chips_html, row, cta]
        photo = ""
    main = f'<div class="fl-main" data-fit="{FIT[layout]},14">{"".join(x for x in parts if x)}</div>'
    badge = f'<div class="fl-badge">{_e(fl.get("badge"))}</div>' if fl.get("badge") else "<div></div>"
    head = f'<div class="fl-head">{logo_html}{badge}</div>'
    contact = fl.get("contact") or {}
    band = contact_band(contact, brand, lang, fl.get("qr_url") or "", ink)
    extra = '<i class="fl-notch n1"></i><i class="fl-notch n2"></i>' if layout == "ticket" else ""
    content = f'<div class="fl fl-{layout}" style="{style}">{photo}{extra}{head}{medal}{main}{band}</div>'
    return content, CSS
