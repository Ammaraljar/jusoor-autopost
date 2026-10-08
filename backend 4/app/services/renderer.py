"""Render branded carousel slides (1080x1350 JPEG) from HTML with headless Chromium.

Chromium gives correct Arabic shaping, RTL layout and web fonts, which Pillow cannot do reliably.
"""
from __future__ import annotations

import asyncio
import base64
import html
import logging
import os
from dataclasses import dataclass

from . import fonts
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)
RENDER_DIR = Path(__file__).resolve().parent.parent / "render"
WIDTH, HEIGHT = 1080, 1350

BADGE_LABELS = {
    "ar": {"news": "خبر", "tips": "نصائح", "guide": "دليل", "offer": "عرض", "event": "فعالية",
           "culture": "ثقافة", "food": "مذاق"},
    "en": {"news": "News", "tips": "Tips", "guide": "Guide", "offer": "Offer", "event": "Event",
           "culture": "Culture", "food": "Food"},
    "fr": {"news": "Actu", "tips": "Conseils", "guide": "Guide", "offer": "Offre", "event": "Événement",
           "culture": "Culture", "food": "Saveurs"},
    "ms": {"news": "Berita", "tips": "Tip", "guide": "Panduan", "offer": "Tawaran", "event": "Acara",
           "culture": "Budaya", "food": "Rasa"},
}
CREDIT_LABEL = {"ar": "المصدر", "en": "Source", "fr": "Source", "ms": "Sumber"}

DEFAULT_COLORS = {"navy": "#16244F", "gold": "#C6A23C", "goldLight": "#D9B96A",
                  "cardBg": "rgba(251,248,240,0.94)", "cardTitle": "#16244F", "cardText": "#1F2B55",
                  "cardHeading": "#8A6D16"}


def _rgb_triplet(hex_colour: str) -> str:
    value = (hex_colour or "#16244F").lstrip("#")
    try:
        return ",".join(str(int(value[i:i + 2], 16)) for i in (0, 2, 4))
    except ValueError:
        return "22,36,79"


@dataclass
class SlideSpec:
    kind: str                 # cover | content | cta
    heading: str
    body: str
    position: int
    total: int
    background: bytes | None = None
    badge: str | None = None
    credit: str = ""
    variant: int = 0          # used to vary crop when a background is reused
    logo_plate: bool = False  # navy backdrop behind the logo (bright photo behind it)
    highlight: list[str] | None = None   # words of the cover title shown in gold
    logo: bytes | None = None            # the logo version chosen for this slide (white/dark/colour)


@dataclass
class BrandStyle:
    name: str
    handle: str = ""
    website: str = ""
    colors: dict | None = None
    font_family: str = "Cairo"          # Arabic font
    font_latin: str = "Cairo"           # font for English / Malay / French
    logo: bytes | None = None
    logo_placement: str = "top-left"
    card_style: str = "frosted"
    language: str = "ar"
    palette: dict | None = None       # colours taken from the photo (overrides brand colours)
    logo_backdrop: str = "auto"       # auto | always | never
    theme: str = "magazine"           # magazine = photo-first field designs | classic (rounded cards)
    family: str = "general"           # card design family of the company's field
    logos: list | None = None         # [(tone, bytes)] all versions of the logo


@lru_cache
def _font_faces() -> str:
    faces = []
    ranges = {
        "arabic": "U+0600-06FF, U+0750-077F, U+0870-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200E",
        "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, "
                 "U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
        "latin-ext": "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+1E00-1EFF, "
                     "U+20A0-20C0, U+2C60-2C7F, U+A720-A7FF",
    }
    for file in sorted((RENDER_DIR / "fonts").glob("cairo-*-normal.woff2")):
        parts = file.stem.split("-")              # cairo-<subset>-<weight>-normal, subset may contain "-"
        subset, weight = "-".join(parts[1:-2]), parts[-2]
        b64 = base64.b64encode(file.read_bytes()).decode()
        faces.append(f"@font-face {{ font-family: 'Cairo'; font-weight: {weight}; font-style: normal; "
                     f"src: url(data:font/woff2;base64,{b64}) format('woff2'); unicode-range: {ranges[subset]}; }}")
    return "\n".join(faces)


@lru_cache
def _template() -> str:
    return (RENDER_DIR / "slide.html").read_text(encoding="utf-8")


def _data_uri(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")


def _logo_html(brand: BrandStyle, plate: bool = False, logo: bytes | None = None) -> str:
    cls = "logo plate" if plate else "logo"
    logo = logo or brand.logo
    if logo:
        mime = "image/svg+xml" if logo.lstrip().startswith(b"<") else "image/png"
        return f'<div class="{cls}"><img src="{_data_uri(logo, mime)}" alt=""></div>'
    parts = brand.name.split(" ", 1)
    first = _esc(parts[0])
    rest = f" <span>{_esc(parts[1])}</span>" if len(parts) > 1 else ""
    return f'<div class="{cls}"><div class="wordmark">{first}{rest}</div></div>'


CARD_STYLES = ("frosted", "solid", "band", "side", "ribbon", "outline", "minimal")


SWIPE = {"ar": "اسحب للمزيد", "en": "Swipe for more", "fr": "Glissez", "ms": "Leret"}
SAVE_SHARE = {"ar": ("احفظ", "شارك", "راسلنا"), "en": ("Save", "Share", "Message us"),
              "ms": ("Simpan", "Kongsi", "Mesej kami"),
              "fr": ("Enregistrez", "Partagez", "Écrivez-nous")}
_ICONS = {
    "save": '<svg viewBox="0 0 24 24"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg>',
    "share": '<svg viewBox="0 0 24 24"><path d="M18 8a3 3 0 1 0-2.8-4L8.9 7.6a3 3 0 1 0 0 4.8l6.3 3.6A3 3 0 1 0 16 14l-6.3-3.6a3 3 0 0 0 0-.8L16 6a3 3 0 0 0 2 2z"/></svg>',
    "msg": '<svg viewBox="0 0 24 24"><path d="M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9l-5 4V5a1 1 0 0 1 1-1z"/></svg>',
}


def _highlight(text: str, words: list[str] | None) -> str:
    """Escape the title and wrap the chosen words (or numbers) in <mark> so they show in gold."""
    out = _esc(text)
    picks = [w.strip() for w in (words or []) if w and w.strip() and w.strip() in (text or "")]
    if not picks:
        import re
        picks = re.findall(r"[0-9٠-٩]+(?:[.,][0-9٠-٩]+)?\s?\S*", text or "")[:1]
    for w in sorted(set(picks), key=len, reverse=True)[:2]:
        esc = _esc(w)
        out = out.replace(esc, f"<mark>{esc}</mark>", 1)
    return out


def _magazine(spec: SlideSpec, brand: BrandStyle, lang: str, bg: str, top: str, plate: bool) -> str:
    """Bold, modern carousel: big gold-accented titles, numbered tips, a clear swipe / save prompt."""
    handle = f'<span class="handle">{_esc(brand.handle)}</span>' if brand.handle else "<span></span>"
    content_total = max(spec.total - 2, 1)
    if spec.kind == "cover":
        alt = _cover_variant(spec, brand, lang, bg, top)
        if alt:
            return alt
        kicker = BADGE_LABELS[lang].get(spec.badge or "", "") if spec.badge else ""
        credit = f'<div class="m-credit">{CREDIT_LABEL[lang]}: {_esc(spec.credit)}</div>' if spec.credit else ""
        return (f'{bg}<div class="m-shade"></div>{top}'
                f'<div class="m-cover" data-fit="700,44">'
                + (f'<div class="m-kicker"><i></i>{_esc(kicker)}</div>' if kicker else "")
                + f'<h1>{_highlight(spec.heading, spec.highlight)}</h1>'
                f'<p class="m-sub">{_esc(spec.body)}</p></div>'
                f'<div class="m-bar">{handle}{credit}<span class="m-swipe">{SWIPE[lang]} <b>←</b></span></div>')
    if spec.kind == "cta":
        site = f'<div class="site">{_esc(brand.website)}</div>' if brand.website else ""
        labels = SAVE_SHARE[lang]
        actions = "".join(f'<span class="m-act">{_ICONS[k]}{_esc(v)}</span>'
                          for k, v in zip(("save", "share", "msg"), labels))
        return (f'{bg}<div class="cta-overlay"></div>'
                f'<div class="cta-wrap"><div class="cta-logo">{_logo_html(brand, False, spec.logo)}</div>'
                f'<h1 style="font-size:70px" data-fit="420,40">{_esc(spec.heading)}</h1>'
                f'<p style="font-size:36px;opacity:.92">{_esc(spec.body)}</p>'
                f'<div class="button">{_esc(brand.handle or brand.name)}</div>{site}'
                f'<div class="m-actions">{actions}</div></div>')
    number = f"{spec.position:02d}"
    progress = int(100 * spec.position / content_total) if content_total else 100
    text = (f'<div class="m-body" data-fit="{{fit}}"><h2>{_esc(spec.heading)}</h2><p>{_esc(spec.body)}</p></div>')
    foot = (f'<div class="m-foot">{handle}<span class="m-count">{spec.position}/{content_total}</span></div>'
            f'<div class="m-progress"><i style="width:{min(progress, 100)}%"></i></div>')
    layout = (brand.palette or {}).get("layout") or "panel"
    # Every layout keeps the photo as the hero (full-bleed); only a compact text shape sits on it.
    photo = f'{bg}<div class="ph-shade"></div>{top}'
    if layout == "arch":            # text inside a small travel-poster arch
        return (f'{photo}<div class="L2-arch"><div class="arch-num">{number}</div>'
                f'{text.format(fit="300,26")}</div>{foot}')
    if layout == "ticket":          # compact boarding pass at the bottom
        return (f'{photo}<div class="L2-ticket"><div class="tk-head"><span class="tk-plane">✈</span>'
                f'<span class="tk-label">{"بطاقة صعود" if lang == "ar" else "Boarding pass"}</span>'
                f'<span class="tk-seat">{number}</span></div><div class="tk-text">{text.format(fit="250,26")}</div></div>{foot}')
    if layout == "polaroid":        # a taped paper note
        return (f'{photo}<div class="L2-note"><i class="tape t1"></i><i class="tape t2"></i>'
                f'<div class="note-num">{number}</div>{text.format(fit="290,26")}</div>{foot}')
    if layout == "wave":            # wave rising from the bottom
        return (f'{photo}<div class="L2-wave"><svg viewBox="0 0 1080 120" preserveAspectRatio="none">'
                f'<path d="M0,70 C180,0 360,120 560,60 C760,0 900,90 1080,40 L1080,120 L0,120 Z"/></svg>'
                f'<div class="wave-num">{number}</div>{text.format(fit="300,26")}</div>{foot}')
    if layout == "circle":          # leaf-shaped card with a gold number medal
        return (f'{photo}<div class="L2-leaf"><div class="leaf-num">{number}</div>'
                f'{text.format(fit="300,26")}</div>{foot}')
    return (f'{photo}<div class="L2-panel"><div class="m-num">{number}</div>'
            f'{text.format(fit="320,26")}</div>{foot}')


def _cover_variant(spec: SlideSpec, brand: BrandStyle, lang: str, bg: str, top: str) -> str | None:
    """Alternative covers: a postage stamp on a postcard, or a diagonal gold band."""
    style = (brand.palette or {}).get("cover") or "full"
    handle = f'<span class="handle">{_esc(brand.handle)}</span>' if brand.handle else "<span></span>"
    kicker = BADGE_LABELS[lang].get(spec.badge or "", "") if spec.badge else ""
    credit = f'<div class="m-credit">{CREDIT_LABEL[lang]}: {_esc(spec.credit)}</div>' if spec.credit else ""
    swipe = f'<span class="m-swipe">{SWIPE[lang]} <b>←</b></span>'
    title = (f'{f"<div class=m-kicker><i></i>{_esc(kicker)}</div>" if kicker else ""}'
             f'<h1>{_highlight(spec.heading, spec.highlight)}</h1><p class="m-sub">{_esc(spec.body)}</p>')
    if style == "stamp":
        mark = _esc((brand.name or "").split(" ")[0].upper())
        return (f'<div class="C-stamp"><div class="stamp"><div class="stamp-photo">{bg}</div></div>'
                f'<div class="postmark"><span>{mark}</span><small>TRAVEL</small></div>{top}'
                f'<div class="stamp-title" data-fit="275,34">{title}</div>'
                f'<div class="m-bar dark">{handle}{credit}{swipe}</div></div>')
    if style == "diagonal":
        return (f'{bg}<div class="C-diag"><i class="diag-gold"></i><div class="diag-band"></div></div>{top}'
                f'<div class="diag-title" data-fit="300,36">{title}</div>'
                f'<div class="m-bar dark">{handle}{credit}{swipe}</div>')
    return None


def build_html(spec: SlideSpec, brand: BrandStyle) -> str:
    lang = brand.language if brand.language in BADGE_LABELS else "ar"
    rtl = lang == "ar"
    brand_colors = {**DEFAULT_COLORS, **(brand.colors or {})}
    surface = (brand.colors or {}).get("surface")
    if surface and surface.startswith("#") and len(surface) == 7:      # the brand's own card colour
        r, g, b = (int(surface[i:i + 2], 16) for i in (1, 3, 5))
        brand_colors.update(cardBgHex=surface, cardBg=f"rgba({r},{g},{b},0.94)")
    colors = {**brand_colors, **(brand.palette or {})}
    # The logo plate always uses the brand's own navy, so the logo keeps its identity.
    plate = brand.logo_backdrop == "always" or (brand.logo_backdrop != "never" and spec.logo_plate)
    bg_pos = ["center", "30% center", "70% center", "center 30%", "center 70%"][spec.variant % 5]
    bg_filter = ("filter: blur(2px) saturate(1.05); transform: scale(1.04);"
                 if spec.variant % 2 and spec.kind == "content" and brand.theme != "magazine" else "")
    bg = f'<div class="bg" style="background-image:url({_data_uri(spec.background)})"></div>' if spec.background else ""

    # Logo sits on the requested side; badge takes the other side.
    logo_left = brand.logo_placement.endswith("left")
    top_dir = "row" if (logo_left != rtl) else "row-reverse"   # in RTL, row starts from the right
    badge_text = BADGE_LABELS[lang].get(spec.badge or "", "") if spec.badge else ""
    badge = f'<div class="badge">{_esc(badge_text)}</div>' if badge_text else "<div></div>"
    top = f'<div class="top" >{_logo_html(brand, plate, spec.logo)}{badge}</div>'

    dots = "".join(f'<i class="{"on" if i == spec.position else ""}"></i>' for i in range(spec.total))
    credit = f'<span class="credit">{CREDIT_LABEL[lang]}: {_esc(spec.credit)}</span>' if spec.credit else ""
    handle = f'<span class="handle">{_esc(brand.handle)}</span>' if brand.handle else ""
    footer = f'<div class="footer">{handle}{credit}<div class="dots">{dots}</div></div>'
    card_style = brand.card_style if brand.card_style in CARD_STYLES else "frosted"
    # "frosted" (the default) means automatic: the post's colour set brings its own card shape
    if card_style == "frosted" and (brand.palette or {}).get("cardStyle") in CARD_STYLES:
        card_style = brand.palette["cardStyle"]          # the post's brand colour set decides the card

    extra_css = ""
    if brand.theme == "magazine":
        # photo-first cards of the company's field: one logo, no boxes over the photo
        from . import cards
        content, theme_class = cards.build(spec, brand, lang, _logo_html(brand, False, spec.logo),
                                          _logo_html(brand, plate, spec.logo), bg,
                                          logo_start=(logo_left != rtl))
        extra_css = cards.css()
    elif spec.kind == "cover":
        content = (f'{bg}<div class="shade"></div>{top}'
                   f'<div class="card {card_style}" data-fit="760,40"><div class="accent"></div>'
                   f'<h1 style="font-size:76px">{_esc(spec.heading)}</h1>'
                   f'<p class="subtitle" style="font-size:36px">{_esc(spec.body)}</p></div>{footer}')
    elif spec.kind == "cta":
        site = f'<div class="site">{_esc(brand.website)}</div>' if brand.website else ""
        button = _esc(brand.handle or brand.name)
        # Last slide: the brand logo takes the centre (no plane icon, no small logo in the corner)
        content = (f'{bg}<div class="cta-overlay"></div>'
                   f'<div class="cta-wrap"><div class="cta-logo">{_logo_html(brand, False, spec.logo)}</div>'
                   f'<h1 style="font-size:70px" data-fit="520,40">{_esc(spec.heading)}</h1>'
                   f'<p style="font-size:36px;opacity:.9">{_esc(spec.body)}</p>'
                   f'<div class="button">{button}</div>{site}</div>'
                   f'<div class="footer"><span></span><div class="dots">{dots}</div></div>')
    else:
        content = (f'{bg}<div class="shade"></div>{top}'
                   f'<div class="card {card_style}" data-fit="820,30">'
                   f'<h2 style="font-size:54px">{_esc(spec.heading)}</h2>'
                   f'<p style="font-size:42px">{_esc(spec.body)}</p></div>{footer}')

    if brand.theme != "magazine":
        theme_class = "theme-classic"
    return _template().format(
        theme=theme_class, extra_css=extra_css, lang=lang, dir="rtl" if rtl else "ltr", font_faces=_font_faces() + "\n" + fonts.faces(fonts.valid_arabic(brand.font_family), fonts.valid_latin(brand.font_latin)),
        font=fonts.stack(fonts.valid_arabic(brand.font_family), fonts.valid_latin(brand.font_latin), lang),
        navy=colors["navy"], gold=colors["gold"], gold_light=colors.get("goldLight", colors["gold"]),
        card_bg=colors.get("cardBg"), card_solid=colors.get("cardBgHex") or "#F8F4EA", card_title=colors.get("cardTitle"),
        card_text=colors.get("cardText", colors.get("cardSubtle", "#3A4058")),
        card_heading=colors.get("cardHeading") or colors["gold"],
        navy_rgb=_rgb_triplet(colors["navy"]), plate_rgb=_rgb_triplet(brand_colors["navy"]),
        bg_pos=bg_pos, bg_filter=bg_filter, top_dir=top_dir, content=content,
    )


class Renderer:
    """Keeps a single headless Chromium alive; renders up to three slides at once."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._loop = None
        self._lock: asyncio.Lock | None = None

    def _bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if loop is not self._loop:
            # A browser belongs to the event loop that started it (matters for tests / reloads).
            self._loop, self._lock, self._browser, self._pw = loop, asyncio.Lock(), None, None
            self._pages = asyncio.Semaphore(3)

    async def _ensure(self):
        if self._browser and self._browser.is_connected():
            return self._browser
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        exe = os.environ.get("CHROMIUM_PATH")
        self._browser = await self._pw.chromium.launch(
            executable_path=exe or None, args=["--no-sandbox", "--disable-dev-shm-usage"])
        return self._browser

    async def render(self, spec: SlideSpec, brand: BrandStyle) -> bytes:
        self._bind_loop()
        async with self._lock:                       # only one launch at a time
            browser = await self._ensure()
        async with self._pages:                      # several slides render side by side
            page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            try:
                await page.set_content(build_html(spec, brand), wait_until="load")
                await page.wait_for_function("document.body.dataset.ready === '1'", timeout=10000)
                await page.evaluate("document.fonts.ready")
                return await page.screenshot(type="jpeg", quality=90,
                                             clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT})
            finally:
                await page.close()

    async def close(self) -> None:
        if self._loop is not asyncio.get_running_loop():
            return
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = self._pw = None


renderer = Renderer()
