"""Colours derived from the photo, so every post matches its own image.

* ``extract_palette``   — builds card / heading / accent colours from the dominant hue of a
  photo, with WCAG contrast guarantees so text always stays readable.
* ``logo_needs_plate``  — measures how bright the photo is behind the logo; a white logo on
  a light sky gets a navy plate behind it.
"""
from __future__ import annotations

import colorsys
import io
from typing import Any

from PIL import Image, ImageStat

MIN_TEXT_CONTRAST = 4.5          # WCAG AA for normal text
PLATE_BRIGHTNESS = 0.44          # above this mean luminance a white logo needs a backdrop


# ------------------------------------------------------------------ colour maths
def _hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(c * 255))) for c in rgb))


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hsl(h: float, s: float, l: float) -> tuple[float, float, float]:
    return colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))


def _luminance(rgb: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la = _luminance(tuple(c / 255 for c in hex_to_rgb(a)))
    lb = _luminance(tuple(c / 255 for c in hex_to_rgb(b)))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _shift_until(h: float, s: float, l: float, against: str, target: float, step: float) -> str:
    """Move lightness (step < 0 darkens, > 0 lightens) until the contrast target is met."""
    colour = _hex(_hsl(h, s, l))
    for _ in range(60):
        if contrast(colour, against) >= target or not 0.02 <= l <= 0.98:
            break
        l += step
        colour = _hex(_hsl(h, s, l))
    return colour


# ------------------------------------------------------------------ photo analysis
def _open(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((200, 200))
    return img


def dominant_hue(image_bytes: bytes) -> tuple[float, float] | None:
    """(hue, saturation) of the most characteristic colour, or None for grey photos."""
    img = _open(image_bytes)
    quant = img.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    palette = quant.getpalette() or []
    counts = sorted(quant.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    best, best_score = None, 0.0
    for count, index in counts:
        r, g, b = (palette[index * 3 + i] / 255 for i in range(3))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if s < 0.22 or l < 0.12 or l > 0.92:
            continue                      # greys, near-black and near-white say nothing about mood
        share = count / total
        score = s * (0.35 + share) * (1 - abs(l - 0.5))
        if score > best_score:
            best, best_score = (h, s), score
    return best


def extract_palette(image_bytes: bytes | None, fallback: dict[str, str] | None = None) -> dict[str, str] | None:
    """Colour set for one post. Returns None (→ brand colours) when the photo has no clear hue."""
    if not image_bytes:
        return None
    try:
        found = dominant_hue(image_bytes)
    except Exception:  # noqa: BLE001 - an odd image must not break rendering
        return None
    if not found:
        return None
    h, s = found
    sat = max(0.45, min(s, 0.85))

    dark = _hex(_hsl(h, min(max(s, 0.35), 0.65), 0.16))            # overlays, card titles, logo-free areas
    card_bg_hex = _hex(_hsl(h, 0.30, 0.965))
    accent = _shift_until(h, sat, 0.50, dark, MIN_TEXT_CONTRAST, +0.02)   # readable on the dark tone
    accent_light = _shift_until(h, sat * 0.8, 0.72, dark, 7.0, +0.02)
    card_heading = _shift_until(h, sat, 0.40, card_bg_hex, MIN_TEXT_CONTRAST, -0.02)
    card_text = _shift_until(h, 0.18, 0.30, card_bg_hex, 7.0, -0.02)
    r, g, b = hex_to_rgb(card_bg_hex)
    return {
        "navy": dark, "gold": accent, "goldLight": accent_light,
        "cardBg": f"rgba({r},{g},{b},0.94)", "cardBgHex": card_bg_hex,
        "cardTitle": dark, "cardHeading": card_heading, "cardText": card_text,
        "hue": round(h * 360),
    }


def logo_needs_plate(image_bytes: bytes | None, placement: str = "top-left", rtl: bool = True) -> bool:
    """True when the area behind the logo is bright or busy, so a white logo would vanish."""
    if not image_bytes:
        return False
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception:  # noqa: BLE001
        return False
    # Match the 4:5 crop used on the slide (background-size: cover, centred)
    w, h = img.size
    target = 4 / 5
    if w / h > target:
        new_w = int(h * target)
        img = img.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
    else:
        new_h = int(w / target)
        img = img.crop((0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h))
    w, h = img.size
    on_left = placement.endswith("left")
    x0, x1 = (0, int(w * 0.45)) if on_left else (int(w * 0.55), w)
    region = img.crop((x0, 0, x1, int(h * 0.16)))
    stat = ImageStat.Stat(region)
    mean = stat.mean[0] / 255
    spread = stat.stddev[0] / 255
    # White text needs a dark surround: anything from mid-tones up gets the plate, and so do
    # busy areas (clouds, buildings) where the logo would compete with detail.
    return mean > PLATE_BRIGHTNESS or (mean > 0.36 and spread > 0.20)


# ------------------------------------------------------------------ previews
def sample_background(kind: str) -> bytes:
    """Synthetic photos for the brand preview: light sky, turquoise sea, warm sunset."""
    from PIL import ImageDraw, ImageFilter

    presets: dict[str, Any] = {
        "cover": ((222, 236, 246), (246, 236, 214), (250, 250, 245)),      # bright sky → tests the logo plate
        "content": ((18, 118, 132), (32, 170, 160), (220, 240, 232)),       # sea
        "cta": ((212, 88, 48), (246, 164, 72), (255, 220, 170)),            # sunset
    }
    top, bottom, sun = presets.get(kind, presets["content"])
    img = Image.new("RGB", (1080, 1350))
    draw = ImageDraw.Draw(img)
    for y in range(1350):
        k = y / 1350
        draw.line([(0, y), (1080, y)], fill=tuple(int(top[i] * (1 - k) + bottom[i] * k) for i in range(3)))
    draw.ellipse([700, 180, 930, 410], fill=sun)
    for i in range(9):
        x = 130 * i - 60
        draw.polygon([(x - 220, 1350), (x + 20, 980 - (i % 3) * 70), (x + 260, 1350)],
                     fill=tuple(max(0, int(c * 0.72)) for c in bottom))
    img = img.filter(ImageFilter.GaussianBlur(1.5))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()
