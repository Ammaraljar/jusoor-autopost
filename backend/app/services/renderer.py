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
}
CREDIT_LABEL = {"ar": "المصدر", "en": "Source", "fr": "Source"}

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


@dataclass
class BrandStyle:
    name: str
    handle: str = ""
    website: str = ""
    colors: dict | None = None
    font_family: str = "Cairo"
    logo: bytes | None = None
    logo_placement: str = "top-left"
    card_style: str = "frosted"
    language: str = "ar"
    palette: dict | None = None       # colours taken from the photo (overrides brand colours)
    logo_backdrop: str = "auto"       # auto | always | never


@lru_cache
def _font_faces() -> str:
    faces = []
    for file in sorted((RENDER_DIR / "fonts").glob("cairo-*-normal.woff2")):
        _, subset, weight, _ = file.stem.split("-")
        b64 = base64.b64encode(file.read_bytes()).decode()
        rng = "U+0600-06FF, U+0750-077F, U+0870-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200E" if subset == "arabic" \
            else "U+0000-00FF, U+2000-206F, U+20AC, U+2122"
        faces.append(f"@font-face {{ font-family: 'Cairo'; font-weight: {weight}; font-style: normal; "
                     f"src: url(data:font/woff2;base64,{b64}) format('woff2'); unicode-range: {rng}; }}")
    return "\n".join(faces)


@lru_cache
def _template() -> str:
    return (RENDER_DIR / "slide.html").read_text(encoding="utf-8")


def _data_uri(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")


def _logo_html(brand: BrandStyle, plate: bool = False) -> str:
    cls = "logo plate" if plate else "logo"
    if brand.logo:
        mime = "image/svg+xml" if brand.logo.lstrip().startswith(b"<") else "image/png"
        return f'<div class="{cls}"><img src="{_data_uri(brand.logo, mime)}" alt=""></div>'
    parts = brand.name.split(" ", 1)
    first = _esc(parts[0])
    rest = f" <span>{_esc(parts[1])}</span>" if len(parts) > 1 else ""
    return f'<div class="{cls}"><div class="wordmark">{first}{rest}</div></div>'


def build_html(spec: SlideSpec, brand: BrandStyle) -> str:
    lang = brand.language if brand.language in BADGE_LABELS else "ar"
    rtl = lang == "ar"
    brand_colors = {**DEFAULT_COLORS, **(brand.colors or {})}
    colors = {**brand_colors, **(brand.palette or {})}
    # The logo plate always uses the brand's own navy, so the logo keeps its identity.
    plate = brand.logo_backdrop == "always" or (brand.logo_backdrop != "never" and spec.logo_plate)
    bg_pos = ["center", "30% center", "70% center", "center 30%", "center 70%"][spec.variant % 5]
    bg_filter = "filter: blur(2px) saturate(1.05); transform: scale(1.04);" if spec.variant % 2 and spec.kind == "content" else ""
    bg = f'<div class="bg" style="background-image:url({_data_uri(spec.background)})"></div>' if spec.background else ""

    # Logo sits on the requested side; badge takes the other side.
    logo_left = brand.logo_placement.endswith("left")
    top_dir = "row" if (logo_left != rtl) else "row-reverse"   # in RTL, row starts from the right
    badge_text = BADGE_LABELS[lang].get(spec.badge or "", "") if spec.badge else ""
    badge = f'<div class="badge">{_esc(badge_text)}</div>' if badge_text else "<div></div>"
    top = f'<div class="top" >{_logo_html(brand, plate)}{badge}</div>'

    dots = "".join(f'<i class="{"on" if i == spec.position else ""}"></i>' for i in range(spec.total))
    credit = f'<span class="credit">{CREDIT_LABEL[lang]}: {_esc(spec.credit)}</span>' if spec.credit else ""
    handle = f'<span class="handle">{_esc(brand.handle)}</span>' if brand.handle else ""
    footer = f'<div class="footer">{handle}{credit}<div class="dots">{dots}</div></div>'
    card_style = brand.card_style if brand.card_style in ("frosted", "solid", "minimal") else "frosted"
    if card_style != "minimal" and (brand.palette or {}).get("cardStyle") in ("frosted", "solid"):
        card_style = brand.palette["cardStyle"]          # the post's brand colour set decides the card

    if spec.kind == "cover":
        content = (f'{bg}<div class="shade"></div>{top}'
                   f'<div class="card {card_style}" data-fit="760,40"><div class="accent"></div>'
                   f'<h1 style="font-size:76px">{_esc(spec.heading)}</h1>'
                   f'<p class="subtitle" style="font-size:36px">{_esc(spec.body)}</p></div>{footer}')
    elif spec.kind == "cta":
        site = f'<div class="site">{_esc(brand.website)}</div>' if brand.website else ""
        button = _esc(brand.handle or brand.name)
        # Last slide: the brand logo takes the centre (no plane icon, no small logo in the corner)
        content = (f'{bg}<div class="cta-overlay"></div>'
                   f'<div class="cta-wrap"><div class="cta-logo">{_logo_html(brand, False)}</div>'
                   f'<h1 style="font-size:70px" data-fit="520,40">{_esc(spec.heading)}</h1>'
                   f'<p style="font-size:36px;opacity:.9">{_esc(spec.body)}</p>'
                   f'<div class="button">{button}</div>{site}</div>'
                   f'<div class="footer"><span></span><div class="dots">{dots}</div></div>')
    else:
        content = (f'{bg}<div class="shade"></div>{top}'
                   f'<div class="card {card_style}" data-fit="820,30">'
                   f'<h2 style="font-size:54px">{_esc(spec.heading)}</h2>'
                   f'<p style="font-size:42px">{_esc(spec.body)}</p></div>{footer}')

    return _template().format(
        lang=lang, dir="rtl" if rtl else "ltr", font_faces=_font_faces(), font=brand.font_family or "Cairo",
        navy=colors["navy"], gold=colors["gold"], gold_light=colors.get("goldLight", colors["gold"]),
        card_bg=colors.get("cardBg"), card_title=colors.get("cardTitle"),
        card_text=colors.get("cardText", colors.get("cardSubtle", "#3A4058")),
        card_heading=colors.get("cardHeading") or colors["gold"],
        navy_rgb=_rgb_triplet(colors["navy"]), plate_rgb=_rgb_triplet(brand_colors["navy"]),
        bg_pos=bg_pos, bg_filter=bg_filter, top_dir=top_dir, content=content,
    )


class Renderer:
    """Keeps a single headless Chromium alive and renders slides sequentially."""

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
        async with self._lock:
            browser = await self._ensure()
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
