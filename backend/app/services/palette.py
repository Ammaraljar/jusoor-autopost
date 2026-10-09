"""Post colours — always inside the JUSOOR identity (navy + gold), varied from post to post.

* ``brand_variants``    — six colour sets derived from the brand's own navy and gold (deeper,
  brighter, warmer, cooler shades of the same two colours), with WCAG contrast guarantees.
* ``pick_variant``      — chooses one set per post: it suits the photo (warm/cool) and is never
  the same as the last posts, so the feed varies without leaving the identity.
* ``extract_palette``   — (legacy) colours taken from the photo's own hue; no longer used for posts.
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


# ------------------------------------------------------------------ brand variants
BRAND_NAVY = "#16244F"
BRAND_GOLD = "#C6A23C"

# (id, name, warmth, navy: (hue shift°, sat ×, lightness), gold: (hue shift°, sat, lightness), card)
# card = ("ivory" | "cool" | "gold", lightness)
_VARIANTS = [
    ("classic",  "كلاسيكي",        0.5, (0, 1.00, None), (0, None, None),  ("ivory", 0.965)),
    ("midnight", "كحلي ليلي",      0.6, (0, 1.10, 0.17), (3, 0.58, 0.62),  ("ivory", 0.970)),
    ("royal",    "أزرق ملكي",      0.2, (-3, 1.25, 0.28), (-4, 0.66, 0.50), ("cool", 0.970)),
    ("ocean",    "كحلي بحري",      0.1, (-10, 1.15, 0.24), (0, 0.50, 0.56), ("cool", 0.965)),
    ("sand",     "ذهبي رملي",      0.9, (0, 1.00, 0.21), (2, 0.60, 0.47),  ("gold", 0.935)),
    ("amber",    "ذهبي كهرماني",   0.8, (6, 1.05, 0.22), (-6, 0.72, 0.50), ("ivory", 0.960)),
]
VARIANT_IDS = [v[0] for v in _VARIANTS]
# Modern theme: a different creative layout for each colour set
LAYOUTS = {"classic": "panel", "midnight": "arch", "royal": "ticket", "ocean": "polaroid",
           "sand": "wave", "amber": "circle"}
COVERS = {"classic": "full", "midnight": "stamp", "royal": "diagonal", "ocean": "full",
          "sand": "stamp", "amber": "diagonal"}
# Card per colour set: light frosted cards and navy cards with a gold edge, alternating
CARD_SHAPES = {"classic": "frosted", "midnight": "solid", "royal": "frosted", "ocean": "solid",
               "sand": "frosted", "amber": "solid"}


def _hls_of(hex_colour: str) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in hex_to_rgb(hex_colour))
    return colorsys.rgb_to_hls(r, g, b)


def brand_variants(navy: str = BRAND_NAVY, gold: str = BRAND_GOLD) -> list[dict[str, Any]]:
    """Colour sets for posts, all derived from the brand's navy and gold — no foreign colours."""
    nh, nl, ns = _hls_of(navy)
    gh, gl, gs = _hls_of(gold)
    out = []
    for vid, name, warmth, (dh, dsm, dl), (gdh, gsat, gli), (card_kind, card_l) in _VARIANTS:
        dark_h = nh + dh / 360
        dark = navy if (dh == 0 and dsm == 1.0 and dl is None) else _hex(_hsl(dark_h, ns * dsm, dl if dl else nl))
        acc_h = gh + gdh / 360
        base_gold = gold if (gdh == 0 and gsat is None and gli is None) else _hex(_hsl(acc_h, gsat or gs, gli or gl))
        dh_, dl_, ds_ = _hls_of(dark)
        ah, al, as_ = _hls_of(base_gold)
        accent = _shift_until(ah, as_, al, dark, MIN_TEXT_CONTRAST, +0.02)      # gold readable on navy
        accent_light = _shift_until(ah, as_ * 0.85, max(al, 0.66), dark, 7.0, +0.02)
        if card_kind == "cool":
            card_bg_hex = _hex(_hsl(dh_, 0.40, card_l))                          # blue-white, from the navy
        elif card_kind == "gold":
            card_bg_hex = _hex(_hsl(ah, 0.55, card_l))                           # pale gold
        else:
            card_bg_hex = _hex(_hsl(ah, 0.45, card_l))                           # warm ivory, from the gold
        card_heading = _shift_until(ah, max(as_, 0.55), 0.38, card_bg_hex, MIN_TEXT_CONTRAST, -0.02)
        card_text = _shift_until(dh_, max(ds_, 0.35), 0.26, card_bg_hex, 7.0, -0.02)   # navy-tinted, never grey
        r, g, b = hex_to_rgb(card_bg_hex)
        out.append({
            "variant": vid, "variant_name": name, "warmth": warmth,
            "navy": dark, "gold": accent, "goldLight": accent_light,
            "cardBg": f"rgba({r},{g},{b},0.94)", "cardBgHex": card_bg_hex,
            "cardTitle": dark, "cardHeading": card_heading, "cardText": card_text,
            "cardStyle": CARD_SHAPES.get(vid, "frosted"),
            "layout": LAYOUTS.get(vid, "panel"), "cover": COVERS.get(vid, "full"),
        })
    return out


# ------------------------------------------------------------------ the brand's own colour roles
ROLES = ("navy", "gold", "goldLight", "surface", "cardTitle", "cardText")
LEGACY_ROLES = {"goldLight": "#d9b96a", "surface": "#fbf8f0", "cardTitle": "#16244f", "cardText": "#1f2b55"}


def _norm(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if len(v) == 7 and v.startswith("#") else ""


def role_defaults(navy: str, gold: str) -> dict[str, str]:
    """The secondary colour roles that follow from the main (navy) and secondary (gold) colours."""
    nh, nl, ns = _hls_of(navy)
    gh, gl, gs = _hls_of(gold)
    surface = _hex(_hsl(gh, 0.45, 0.965))                                   # warm ivory from the accent
    return {
        "goldLight": _shift_until(gh, gs * 0.85, max(gl, 0.66), navy, 7.0, +0.02),
        "surface": surface,
        "cardTitle": navy,
        "cardText": _shift_until(nh, max(ns, 0.35), min(nl, 0.26), surface, 7.0, -0.02),
    }


def complete_colors(colors: dict | None, previous: dict | None = None) -> dict[str, str]:
    """Fill the colour roles from the main and secondary colours.

    A role follows the main colours when it is empty, still the old default, or still what was
    derived from the previous main colours; a role the user set by hand is kept."""
    colors = {k: v for k, v in (colors or {}).items() if v}
    navy = _norm(colors.get("navy")) or BRAND_NAVY.lower()
    gold = _norm(colors.get("gold")) or BRAND_GOLD.lower()
    new = role_defaults(navy, gold)
    prev = previous or {}
    old_derived = role_defaults(_norm(prev.get("navy")) or BRAND_NAVY, _norm(prev.get("gold")) or BRAND_GOLD) \
        if prev else {}
    out = {**colors, "navy": navy, "gold": gold}
    for role, value in new.items():
        cur = _norm(colors.get(role))
        edited = prev and cur and cur != _norm(prev.get(role))        # changed by hand in this save
        stale = (not cur or cur == _norm(old_derived.get(role)) or cur == LEGACY_ROLES.get(role))
        if not edited and stale:
            out[role] = value
    return out


def exact_set(colors: dict | None) -> dict[str, Any]:
    """The brand's colours exactly as set in its identity (no shades), with readable text guaranteed."""
    c = complete_colors(colors)
    navy, gold, surface = c["navy"], c["gold"], c["surface"]
    title, text = c["cardTitle"], c["cardText"]
    sh, sl, ss = _hls_of(surface)
    if contrast(title, surface) < 3.0:             # only an unreadable choice is corrected
        h, l, s_ = _hls_of(title)
        title = _shift_until(h, s_, l, surface, MIN_TEXT_CONTRAST, -0.02 if sl > 0.5 else 0.02)
    if contrast(text, surface) < 4.5:
        h, l, s_ = _hls_of(text)
        text = _shift_until(h, s_, l, surface, 7.0, -0.02 if sl > 0.5 else 0.02)
    gh, gl, gs = _hls_of(gold)
    heading = gold if contrast(gold, surface) >= 3.0 else _shift_until(gh, max(gs, 0.55), gl, surface, 3.0, -0.02)
    r, g, b = hex_to_rgb(surface)
    return {"variant": "brand", "variant_name": "ألوان الهوية", "navy": navy, "gold": gold,
            "goldLight": c["goldLight"], "cardBg": f"rgba({r},{g},{b},0.94)", "cardBgHex": surface,
            "cardTitle": title, "cardHeading": heading, "cardText": text, "cardStyle": "frosted"}


def photo_warmth(image_bytes: bytes | None) -> float | None:
    """0 = cool photo (sea, sky), 1 = warm photo (sunset, desert, food); None when unclear."""
    if not image_bytes:
        return None
    try:
        found = dominant_hue(image_bytes)
    except Exception:  # noqa: BLE001
        return None
    if not found:
        return None
    deg = found[0] * 360
    if deg < 70 or deg > 320:
        return 1.0 - min(abs(((deg + 40) % 360) - 40) / 70, 1.0) * 0.4
    if 160 <= deg <= 260:
        return 0.0
    return 0.5


def pick_variant(image_bytes: bytes | None, recent: list[str] | None = None,
                 navy: str = BRAND_NAVY, gold: str = BRAND_GOLD, seed: int = 0) -> dict[str, Any]:
    """One brand colour set for a post: suits the photo, and differs from the last posts."""
    variants = brand_variants(navy, gold)
    recent = [r for r in (recent or []) if r]
    avoid = set(recent[:2])                          # never repeat the last two posts
    pool = [v for v in variants if v["variant"] not in avoid] or variants
    warmth = photo_warmth(image_bytes)
    if warmth is None:
        # No clear photo mood: rotate through the set, least recently used first
        order = sorted(pool, key=lambda v: (recent.index(v["variant"]) if v["variant"] in recent else -1,
                                            (VARIANT_IDS.index(v["variant"]) + seed) % len(VARIANT_IDS)),
                       reverse=False)
        unused = [v for v in pool if v["variant"] not in recent]
        return (unused or order)[seed % len(unused or order)]
    ranked = sorted(pool, key=lambda v: (abs(v["warmth"] - warmth), v["variant"] in recent))
    return ranked[0]


def _top_region(image_bytes: bytes | None, placement: str = "top-left") -> tuple[float, float] | None:
    """Mean brightness and busyness (0-1) of the photo where the logo sits."""
    if not image_bytes:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception:  # noqa: BLE001
        return None
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
    stat = ImageStat.Stat(img.crop((x0, 0, x1, int(h * 0.16))))
    return stat.mean[0] / 255, stat.stddev[0] / 255


def logo_needs_plate(image_bytes: bytes | None, placement: str = "top-left", rtl: bool = True) -> bool:
    """True when the area behind the logo is bright or busy, so a white logo would vanish."""
    region = _top_region(image_bytes, placement)
    if region is None:
        return False
    mean, spread = region
    # White text needs a dark surround: anything from mid-tones up gets the plate, and so do
    # busy areas (clouds, buildings) where the logo would compete with detail.
    return mean > PLATE_BRIGHTNESS or (mean > 0.36 and spread > 0.20)


def logo_tone(data: bytes) -> str:
    """light (white/pale version), dark (black/navy version) or color — read from the logo itself."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return "color"                          # SVG and unreadable files: treated as the colour version
    img.thumbnail((120, 120))
    px = [(r, g, b) for r, g, b, a in img.getdata() if a > 128]
    if not px:
        return "color"
    lum = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px) / (255 * len(px))
    sat = sum((max(p) - min(p)) / 255 for p in px) / len(px)
    if lum > 0.78 and sat < 0.18:
        return "light"
    if lum < 0.24 and sat < 0.35:
        return "dark"
    return "color"


def choose_logo(logos: list | None, primary: bytes | None, background: bytes | None,
                placement: str = "top-left", kind: str = "content", template: str | None = None
                ) -> tuple[bytes | None, bool]:
    """The best version of the logo for one slide, and whether it still needs a backdrop plate.

    Bright photo behind the logo → dark version; dark photo or a dark brand surface (last slide,
    top band) → white version; otherwise the colour version. With a single logo the old rule
    (plate on bright areas) applies."""
    by_tone: dict[str, bytes] = {}
    for tone, data in logos or []:
        if data and tone not in by_tone:
            by_tone[tone] = data
    on_dark_surface = kind == "cta" or template == "topbar"
    if len(by_tone) <= 1:
        plate = False if on_dark_surface else logo_needs_plate(background, placement)
        return primary, plate
    if on_dark_surface:
        return by_tone.get("light") or by_tone.get("color") or primary, False
    region = _top_region(background, placement)
    mean, spread = region if region else (0.3, 0.1)
    if mean > 0.55 or (mean > 0.45 and spread > 0.2):          # bright behind the logo
        if "dark" in by_tone:
            return by_tone["dark"], False
        if "color" in by_tone:
            return by_tone["color"], False
        return by_tone.get("light") or primary, True
    if mean < 0.4:                                              # dark behind the logo
        return by_tone.get("light") or by_tone.get("color") or primary, False
    if "color" in by_tone:                                      # mid-tones
        return by_tone["color"], False
    logo = by_tone.get("light") or primary
    return logo, logo_needs_plate(background, placement)


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



# ------------------------------------------------------------------ design rotation
# Card templates: complete looks (cover + content slides). Every field gets its own set of at
# least 20 that suit it; the company may switch any of them off. Every redesign moves to the next
# template of the company's own order, and all of them are used before any comes back.
SHARED_TEMPLATES = ["magazine", "glass", "navy", "diagonal", "editorial", "ribbon", "side", "band", "frame",
                    "postcard", "medallion", "topbar", "leaf", "stripe", "centered", "wave", "outline",
                    "polaroid", "lens", "sticker", "headline", "minimal", "split", "gradient"]
FIELD_TEMPLATES: dict[str, list[str]] = {
    "travel": ["ticket", "quote"], "news": ["breaking", "stat"], "tech": ["breaking", "stat", "blueprint"],
    "food": ["menu", "pricetag", "quote"], "education": ["certificate", "stat", "quote", "blueprint"],
    "training": ["certificate", "stat", "quote"], "nonprofit": ["quote", "stat", "certificate"],
    "retail": ["pricetag", "breaking", "stat"], "luxury": ["blueprint", "certificate", "pricetag", "stat"],
    "fashion": ["pricetag", "quote"], "health": ["stat", "quote", "certificate"], "beauty": ["menu", "quote", "pricetag"],
    "auto": ["breaking", "blueprint", "pricetag", "stat"], "events": ["ticket", "certificate", "breaking"],
    "government": ["certificate", "stat", "breaking", "blueprint"], "rental": ["pricetag", "ticket", "stat", "blueprint"],
    "general": ["stat", "quote", "breaking"],
}
# looks that do not suit a field's voice
FIELD_EXCLUDE: dict[str, set[str]] = {
    "news": {"leaf", "sticker", "polaroid"}, "luxury": {"sticker"}, "health": {"sticker"},
    "nonprofit": {"sticker"}, "education": set(), "tech": {"leaf"},
    "government": {"sticker", "polaroid", "leaf", "gradient"},
}
TEMPLATES = list(dict.fromkeys(SHARED_TEMPLATES + [t for v in FIELD_TEMPLATES.values() for t in v]))
FAMILIES = ["travel", "news", "tech", "food", "education", "training", "nonprofit", "retail", "luxury",
            "fashion", "health", "beauty", "auto", "events", "government", "rental", "general"]
DESIGN_COUNT = len(TEMPLATES)


def family_templates(family: str) -> list[str]:
    family = family if family in FAMILIES else "general"
    skip = FIELD_EXCLUDE.get(family, set())
    return [t for t in FIELD_TEMPLATES.get(family, []) + SHARED_TEMPLATES if t not in skip]


def design_count(family: str = "general", enabled: list[str] | None = None) -> int:
    return len(_active(family, enabled))


def _active(family: str, enabled: list[str] | None) -> list[str]:
    allowed = family_templates(family)
    chosen = [t for t in allowed if t in set(enabled or [])]
    return chosen or allowed


def design(index: int, navy: str = BRAND_NAVY, gold: str = BRAND_GOLD, seed: int = 0,
           family: str = "general", enabled: list[str] | None = None,
           template: str | None = None, exact: dict | None = None) -> dict[str, Any]:
    """Design #index of the company's own rotation (its seed shuffles the order, so every company
    gets its own sequence). Consecutive designs always change template and colour set.
    enabled: the templates the company kept (empty = all of its field's templates)."""
    import random
    family = family if family in FAMILIES else "general"
    rnd = random.Random(seed or 0)
    variants = brand_variants(navy, gold)
    v_order = list(range(len(variants)))
    t_order = _active(family, enabled)
    rnd.shuffle(v_order)
    rnd.shuffle(t_order)
    n = len(t_order)
    i = index % n
    # exact = "brand colours" mode: every post uses the identity's colours as they are
    out = exact_set(exact) if exact is not None else dict(variants[v_order[i % 6]])
    out["template"] = template if template in TEMPLATES else t_order[i]
    out["layout"] = out["template"]
    out["cover"] = out["template"]
    out["cta"] = ["center", "bottom"][(i // 3) % 2]
    out["family"] = family
    out["design"] = i
    out["count"] = n
    out["source"] = "design"
    return out


# ------------------------------------------------------------------ colours from a logo
def colors_from_logo(data: bytes) -> dict[str, str] | None:
    """Brand colours read from the logo: a deep main colour (cards, overlays) and an accent.

    Works with transparent PNGs; white, near-black and transparent pixels are ignored when a real
    colour exists. Returns None for images it cannot read (e.g. SVG)."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None
    img.thumbnail((160, 160))
    pixels = [(r, g, b) for r, g, b, a in img.getdata() if a > 128]
    if not pixels:
        return None
    flat = Image.new("RGB", (len(pixels), 1))
    flat.putdata(pixels)
    quant = flat.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal = quant.getpalette() or []
    found = []
    for count, idx in sorted(quant.getcolors() or [], reverse=True):
        r, g, b = (pal[idx * 3 + i] / 255 for i in range(3))
        h, l, sat = colorsys.rgb_to_hls(r, g, b)
        found.append((count, h, l, sat))
    total = sum(c for c, *_ in found) or 1
    colourful = [f for f in found if f[3] >= 0.25 and 0.12 <= f[2] <= 0.85 and f[0] / total > 0.03]
    if not colourful:                       # monochrome logo: keep it elegant (charcoal + warm gold)
        return {"navy": "#1C1C24", "gold": "#C6A23C"}
    main = max(colourful, key=lambda f: f[0] * (1.2 - f[2]))            # frequent and not too light
    _, mh, ml, ms = main
    navy = _hex(_hsl(mh, max(ms, 0.45), min(ml, 0.24)))                # deep version of the main colour
    others = [f for f in colourful if min(abs(f[1] - mh), 1 - abs(f[1] - mh)) > 0.07]
    if others:
        acc = max(others, key=lambda f: f[0] * f[3])
        gold = _hex(_hsl(acc[1], max(acc[3], 0.55), min(max(acc[2], 0.45), 0.6)))
    else:                                   # one-colour logo: a bright tint of the same hue
        gold = _hex(_hsl(mh, max(ms, 0.6), 0.55))
    return {"navy": navy, "gold": gold}
