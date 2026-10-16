"""Signature designs: bold, colourful post layouts in the spirit of the big brands of each field.

Travel takes its cue from the great airlines' campaigns (a sweeping tail-fin of colour, a cabin
window framing the destination, a premium boarding pass, a route arc); food from the big food
chains (a plate on a dark board, a painted brush stroke); tech from device launches (a phone
frame, neon); fashion and beauty from magazines (a cover masthead, a lookbook column); and so on.
Every layout is built for one 1080×1350 slide in three kinds — cover, content and last (CTA) —
with the brand's own colours made vivid and a strong "pop" colour from the field's mood, so the
posts never look washed out.
"""
from __future__ import annotations

import base64
import colorsys
import html
import re

# ------------------------------------------------------------------ the layouts
# id → (ar, en, ms, fr) labels shown in Settings → Designs
LAYOUTS: dict[str, tuple[str, str, str, str]] = {
    "hero_band": ("شريط البطل", "Hero band", "Jalur wira", "Bandeau héros"),
    "tailfin": ("ذيل الطائرة", "Tail fin", "Sirip ekor", "Dérive"),
    "window": ("نافذة الطائرة", "Cabin window", "Tingkap kabin", "Hublot"),
    "split_color": ("نصف ملوّن", "Colour split", "Belah warna", "Coupe couleur"),
    "cover_mag": ("غلاف مجلة", "Magazine cover", "Kulit majalah", "Couverture magazine"),
    "frame_bold": ("إطار عريض", "Bold frame", "Bingkai tebal", "Cadre épais"),
    "circle_orbit": ("مدار", "Orbit", "Orbit", "Orbite"),
    "mosaic": ("فسيفساء", "Mosaic", "Mozek", "Mosaïque"),
    "cutout_type": ("صورة داخل الحروف", "Photo in the letters", "Foto dalam huruf", "Photo dans les lettres"),
    "type_poster": ("ملصق العنوان", "Type poster", "Poster tipografi", "Affiche typo"),
    "sticker_price": ("ملصق دائري", "Round sticker", "Pelekat bulat", "Pastille"),
    "panorama": ("بانوراما", "Panorama", "Panorama", "Panorama"),
    "arch_window": ("قوس", "Arch", "Gerbang", "Arche"),
    "neon_night": ("نيون", "Neon night", "Malam neon", "Néon"),
    "brush_stroke": ("ضربة فرشاة", "Brush stroke", "Calitan berus", "Coup de pinceau"),
    "duo_panel": ("صورتان", "Duo", "Duo", "Duo"),
    "stripes_speed": ("خطوط السرعة", "Speed stripes", "Jalur laju", "Bandes vitesse"),
    "ribbon_corner": ("شريط الزاوية", "Corner ribbon", "Reben penjuru", "Ruban d’angle"),
    "minimal_luxe": ("فخامة هادئة", "Quiet luxury", "Mewah ringkas", "Luxe discret"),
    "card_stack": ("بطاقات متراكبة", "Card stack", "Timbunan kad", "Cartes empilées"),
    "map_route": ("خط الرحلة", "Flight route", "Laluan", "Itinéraire"),
    "boarding_lux": ("بطاقة صعود فاخرة", "Premium boarding pass", "Pas masuk premium", "Carte d’embarquement premium"),
    "menu_board": ("طبق على لوح", "Plate on a board", "Pinggan di papan", "Assiette sur ardoise"),
    "device": ("شاشة الجوال", "Phone screen", "Skrin telefon", "Écran mobile"),
    "lookbook": ("كتالوج", "Lookbook", "Lookbook", "Lookbook"),
    "pulse": ("نبض", "Pulse", "Nadi", "Pouls"),
    "notebook": ("دفتر", "Notebook", "Buku nota", "Carnet"),
    "stage": ("أضواء المسرح", "Stage lights", "Lampu pentas", "Projecteurs"),
    "seal": ("ختم رسمي", "Official seal", "Meterai rasmi", "Sceau officiel"),
}

# What each field leaves out (the rest is offered), and its own layouts first.
FIELD_FIRST: dict[str, tuple[str, ...]] = {
    "travel": ("tailfin", "window", "boarding_lux", "map_route", "hero_band", "arch_window"),
    "news": ("hero_band", "split_color", "ribbon_corner", "type_poster"),
    "tech": ("device", "neon_night", "circle_orbit", "cutout_type"),
    "food": ("menu_board", "brush_stroke", "sticker_price", "duo_panel"),
    "education": ("notebook", "panorama", "split_color", "seal"),
    "training": ("notebook", "stage", "circle_orbit", "type_poster"),
    "nonprofit": ("seal", "brush_stroke", "duo_panel", "hero_band"),
    "retail": ("sticker_price", "ribbon_corner", "card_stack", "cutout_type"),
    "luxury": ("minimal_luxe", "arch_window", "frame_bold", "panorama"),
    "fashion": ("cover_mag", "lookbook", "cutout_type", "minimal_luxe"),
    "health": ("pulse", "circle_orbit", "split_color", "duo_panel"),
    "beauty": ("lookbook", "brush_stroke", "cover_mag", "circle_orbit"),
    "auto": ("stripes_speed", "neon_night", "hero_band", "cutout_type"),
    "events": ("stage", "neon_night", "sticker_price", "card_stack"),
    "government": ("seal", "panorama", "hero_band", "split_color"),
    "rental": ("stripes_speed", "map_route", "device", "sticker_price"),
    "general": ("hero_band", "circle_orbit", "card_stack", "split_color"),
}
FIELD_SKIP: dict[str, tuple[str, ...]] = {
    "travel": ("device", "pulse", "seal", "menu_board", "stage"),
    "news": ("menu_board", "lookbook", "brush_stroke"),
    "tech": ("menu_board", "pulse", "seal", "brush_stroke", "lookbook"),
    "food": ("device", "pulse", "seal", "map_route", "stripes_speed"),
    "education": ("menu_board", "neon_night", "stripes_speed", "lookbook"),
    "training": ("menu_board", "pulse", "lookbook", "brush_stroke"),
    "nonprofit": ("menu_board", "neon_night", "device", "stripes_speed", "minimal_luxe"),
    "retail": ("pulse", "seal", "notebook", "map_route"),
    "luxury": ("menu_board", "neon_night", "stripes_speed", "pulse", "sticker_price"),
    "fashion": ("menu_board", "pulse", "seal", "map_route", "stripes_speed"),
    "health": ("menu_board", "neon_night", "stripes_speed", "stage", "sticker_price"),
    "beauty": ("menu_board", "pulse", "seal", "stripes_speed", "map_route"),
    "auto": ("menu_board", "pulse", "lookbook", "notebook", "brush_stroke"),
    "events": ("menu_board", "pulse", "seal", "notebook"),
    "government": ("menu_board", "neon_night", "sticker_price", "stage", "lookbook"),
    "rental": ("menu_board", "pulse", "seal", "lookbook", "notebook"),
    "general": ("menu_board", "pulse", "seal"),
}


def for_family(family: str) -> list[str]:
    first = [x for x in FIELD_FIRST.get(family, ()) if x in LAYOUTS]
    skip = set(FIELD_SKIP.get(family, ()))
    return first + [x for x in LAYOUTS if x not in first and x not in skip]


# ------------------------------------------------------------------ colours
# Strong colours of each field (moods from the leaders of the sector, never their logos)
FIELD_POPS: dict[str, tuple[str, ...]] = {
    "travel": ("#8A1538", "#0072CE", "#D7192D", "#00897B", "#B8860B", "#1B3A6B"),
    "news": ("#C8102E", "#0057B8", "#1A1A1A"),
    "tech": ("#2F6BFF", "#7B2CFF", "#00B3A4", "#111827"),
    "food": ("#E4002B", "#FF9F00", "#2E7D32", "#8B1E1E"),
    "education": ("#1A56DB", "#F59E0B", "#0F766E", "#7C3AED"),
    "training": ("#5B21B6", "#0EA5E9", "#F97316", "#0F172A"),
    "nonprofit": ("#0EA5E9", "#16A34A", "#F97316", "#E11D48"),
    "retail": ("#FF3D00", "#E91E63", "#FFB300", "#6A1B9A"),
    "luxury": ("#B08D57", "#0F3D3E", "#7A1F2B", "#111111"),
    "fashion": ("#111111", "#C2185B", "#B5835A", "#5E35B1"),
    "health": ("#0EA5A4", "#2563EB", "#16A34A", "#0369A1"),
    "beauty": ("#D63384", "#B76E79", "#8B5CF6", "#C2410C"),
    "auto": ("#D50000", "#1565C0", "#212121", "#FF6D00"),
    "events": ("#FF2E63", "#7C3AED", "#FFC300", "#00B8D9"),
    "government": ("#006C35", "#0B4F8A", "#8A6D1F", "#7F1D1D"),
    "rental": ("#0066FF", "#FF6B00", "#00A86B", "#1E293B"),
    "general": ("#2563EB", "#E11D48", "#0D9488", "#F59E0B"),
}


def _rgb(c: str) -> tuple[float, float, float]:
    c = (c or "").lstrip("#")
    if len(c) != 6:
        return (0.1, 0.1, 0.2)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb) -> str:  # noqa: ANN001
    return "#" + "".join(f"{max(0, min(255, round(v * 255))):02X}" for v in rgb)


def lum(c: str) -> float:
    def lin(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in _rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def vivid(c: str, min_s: float = 0.68, lo: float = 0.46, hi: float = 0.6) -> str:
    """The same hue, saturated and at a lively lightness (a pale gold becomes a rich gold)."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(c))
    if s < 0.08:                       # grey/black/white: nothing to brighten
        return c
    return _hex(colorsys.hls_to_rgb(h, min(max(l, lo), hi), max(s, min_s)))


def deepen(c: str) -> str:
    """A deep version of the colour, rich enough to carry white text."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(c))
    return _hex(colorsys.hls_to_rgb(h, min(l, 0.24), s if s < 0.12 else max(s, 0.55)))


def mix(c: str, other: str, t: float) -> str:
    a, b = _rgb(c), _rgb(other)
    return _hex(tuple(x + (y - x) * t for x, y in zip(a, b)))


def colours(pal: dict, family: str, index: int, exact: bool) -> dict[str, str]:
    navy = pal.get("navy") or "#16244F"
    gold = pal.get("gold") or "#C6A23C"
    acc = vivid(gold)
    deep = deepen(navy)
    if exact:
        pop = acc if lum(acc) < 0.45 else vivid(navy, 0.55, 0.32, 0.45)
    else:
        pops = FIELD_POPS.get(family, FIELD_POPS["general"])
        pop = pops[index % len(pops)]
    on_pop = "#FFFFFF" if lum(pop) < 0.42 else "#14161F"
    on_acc = "#FFFFFF" if lum(acc) < 0.42 else "#14161F"
    ink = deep if lum(deep) < 0.08 else "#14161F"
    return {"deep": deep, "acc": acc, "pop": pop, "on_pop": on_pop, "on_acc": on_acc, "ink": ink,
            "paper": mix(acc, "#FFFFFF", 0.93), "pop_soft": mix(pop, "#FFFFFF", 0.85),
            "acc_text": acc if lum(acc) < 0.35 else mix(acc, "#000000", 0.35)}


# ------------------------------------------------------------------ pieces
def _esc(t: str) -> str:
    return html.escape(t or "").replace("\n", "<br>")


def _uri(data: bytes | None) -> str:
    if not data:
        return ""
    return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"


PLANE = '<path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>'


def build(spec, brand, lang: str, logo_html: str, family: str, tpl: str, highlight_fn, icon_html: str,
          kicker: str, swipe: str, actions: tuple[str, ...], save_icons: dict, logo_tone: str) -> tuple[str, str]:
    """(body html, body classes) of one slide in a signature layout."""
    pal = brand.palette or {}
    exact = pal.get("source") != "design" or pal.get("variant") == "brand"
    c = colours(pal, family, int(pal.get("design") or 0), exact)
    style = ";".join(f"--sg-{k.replace('_', '-')}:{v}" for k, v in c.items())
    photo = _uri(spec.background)
    ph = f"background-image:url({photo})" if photo else "background-image:linear-gradient(135deg,var(--sg-deep),var(--sg-pop))"
    kind = spec.kind if spec.kind in ("cover", "content", "cta") else "content"
    content_total = max(spec.total - 2, 1)
    pill_cls = "dark" if logo_tone == "light" else "light"
    logo = f'<div class="sg-logo {pill_cls}">{logo_html}</div>'
    handle = f'<span class="sg-handle">{_esc(brand.handle)}</span>' if brand.handle else "<span></span>"
    badge = f'<span class="sg-badge">{_esc(kicker)}</span>' if kicker else ""
    arrow = "←" if lang == "ar" else "→"
    num = f"{spec.position:02d}"

    if kind == "cta":
        acts = "".join(f'<span class="sg-act"><svg viewBox="0 0 24 24">{save_icons[k]}</svg>{_esc(v)}</span>'
                       for k, v in zip(("save", "share", "msg"), actions))
        site = f'<div class="sg-site">{_esc(brand.website)}</div>' if brand.website else ""
        body = (f'<div class="sg sg-cta-wrap" style="{style}"><div class="sg-photo" style="{ph}"></div>'
                f'<div class="sg-cta-wash"></div><div class="sg-cta-deco"></div>'
                f'<div class="sg-cta"><div class="sg-logo big {pill_cls}">{logo_html}</div>'
                f'<h1 data-fit="330,44">{_esc(spec.heading)}</h1><p>{_esc(spec.body)}</p>'
                f'<div class="sg-button">{_esc(brand.handle or brand.name)} <b>{arrow}</b></div>{site}'
                f'<div class="sg-acts">{acts}</div></div></div>')
        return body, f"theme-sig sg-L-{tpl} fam-{family} lang-{lang} kind-cta"

    if kind == "cover":
        text = (f'<div class="sg-text" data-fit="{FIT.get(tpl, (430, 44))[0]},{FIT.get(tpl, (430, 44))[1]}">'
                f'<div class="sg-kick"><i>{icon_html}</i><span>{_esc(kicker)}</span></div>'
                f'<h1>{highlight_fn(spec.heading, spec.highlight)}</h1>'
                f'<p class="sg-sub">{_esc(spec.body)}</p></div>')
        foot = f'<div class="sg-foot">{handle}<span class="sg-swipe">{_esc(swipe)} <b>{arrow}</b></span></div>'
    else:
        h, m = FIT_CONTENT.get(tpl, (470, 30))
        text = (f'<div class="sg-text sg-content" data-fit="{h},{m}"><div class="sg-num">{num}</div>'
                f'<h2>{_esc(spec.heading)}</h2><p>{_esc(spec.body)}</p></div>')
        dots = "".join(f'<i class="{"on" if i + 1 == spec.position else ""}"></i>' for i in range(content_total))
        foot = f'<div class="sg-foot">{handle}<div class="sg-dots">{dots}</div></div>'

    deco = _decor(tpl, ph, c, lang, icon_html, kicker, num if kind == "content" else "", spec)
    if tpl == "cutout_type" and kind == "cover":
        text = text.replace("<h1>", f'<h1 class="sg-clip" style="{ph}">', 1)
    # the kicker is written above the title; only the seal design (no kicker line) shows it as a pill
    top = f'<div class="sg-top">{logo}{badge if kind == "cover" and tpl == "seal" else ""}</div>'
    body = f'<div class="sg sg-{tpl}" style="{style}">{deco}{top}{text}{foot}</div>'
    return body, f"theme-sig sg-L-{tpl} fam-{family} lang-{lang} kind-{kind}"


def _decor(tpl: str, ph: str, c: dict, lang: str, icon_html: str, kicker: str, num: str, spec) -> str:  # noqa: ANN001
    """The photo and drawn shapes of each layout (behind the text)."""
    p = f'<div class="sg-photo" style="{ph}"></div>'
    rtl = lang == "ar"
    if tpl == "hero_band":
        return p + '<div class="sg-band"></div>'
    if tpl == "tailfin":
        flip = ' style="transform:scaleX(-1)"' if rtl else ""
        return (p + f'<svg class="sg-fin" viewBox="0 0 1080 1350" preserveAspectRatio="none"{flip}>'
                '<path d="M0 520 C 520 540 960 760 1080 1350 L0 1350Z" fill="var(--sg-deep)"/>'
                '<path d="M0 470 C 540 490 990 720 1080 1240" fill="none" stroke="var(--sg-acc)" stroke-width="16"/>'
                '<path d="M0 432 C 550 452 1010 690 1080 1150" fill="none" stroke="var(--sg-pop)" stroke-width="10"/></svg>')
    if tpl == "window":
        return '<div class="sg-glow"></div><div class="sg-win-ring"></div><div class="sg-win">' + p + '</div>'
    if tpl == "split_color":
        return p + '<div class="sg-block"></div>'
    if tpl == "cover_mag":
        word = _esc(kicker or "")
        return p + '<div class="sg-shade"></div>' + (f'<div class="sg-mast">{word}</div>' if word and not num else "")
    if tpl == "frame_bold":
        return '<div class="sg-frame">' + p + '</div>'
    if tpl == "circle_orbit":
        return ('<div class="sg-orbit o1"></div><div class="sg-orbit o2"><i></i></div>'
                '<div class="sg-circle">' + p + '</div>')
    if tpl == "mosaic":
        return "".join(f'<div class="sg-tile t{i}" style="{ph}"></div>' for i in range(3))
    if tpl == "cutout_type":
        return '<div class="sg-strip">' + p + '</div>'
    if tpl == "type_poster":
        return '<div class="sg-poster-photo">' + p + '</div>'
    if tpl == "sticker_price":
        label = num or _esc(kicker)
        return (p + '<svg class="sg-tear" viewBox="0 0 1080 60" preserveAspectRatio="none"><path d="M0 60 L0 30 ' +
                " ".join(f"L{x} {0 if (x // 40) % 2 else 30}" for x in range(40, 1121, 40)) +
                ' L1080 60Z" fill="var(--sg-paper)"/></svg><div class="sg-paper-strip"></div>'
                f'<div class="sg-sticker"><span>{label}</span></div>')
    if tpl == "panorama":
        return '<div class="sg-pano">' + p + '</div><i class="sg-pano-bar"></i>'
    if tpl == "arch_window":
        return '<div class="sg-pattern"></div><div class="sg-arch">' + p + '</div>'
    if tpl == "neon_night":
        return '<div class="sg-neon">' + p + '</div>'
    if tpl == "brush_stroke":
        return (p + '<svg class="sg-brush" viewBox="0 0 1080 600" preserveAspectRatio="none">'
                '<path d="M30 140 C 160 60 420 110 600 70 S 960 40 1060 120 L1050 210 C 1000 300 1070 380 1040 470 '
                'C 860 560 560 520 360 560 S 90 560 30 480 C 0 380 50 300 20 220Z" fill="var(--sg-acc)"/>'
                '<path d="M60 520 C 300 590 700 560 1000 540" stroke="var(--sg-pop)" stroke-width="18" fill="none" '
                'stroke-linecap="round"/></svg>')
    if tpl == "duo_panel":
        return ('<div class="sg-duo-big">' + p + '</div>'
                f'<div class="sg-duo-small" style="{ph}"></div>')
    if tpl == "stripes_speed":
        return p + '<div class="sg-topshade"></div><div class="sg-speed"><i></i><i></i><i></i></div>'
    if tpl == "ribbon_corner":
        return p + '<div class="sg-shade"></div>' + (f'<div class="sg-corner"><span>{_esc(kicker)}</span></div>'
                                                      if kicker and not num else "")
    if tpl == "minimal_luxe":
        return '<div class="sg-luxe-frame"></div><div class="sg-luxe">' + p + '</div>'
    if tpl == "card_stack":
        return '<div class="sg-card-back"></div><div class="sg-card-front">' + p + '</div>'
    if tpl == "map_route":
        return ('<svg class="sg-route" viewBox="0 0 1080 420"><path d="M130 330 Q 540 40 950 330" fill="none" '
                'stroke="var(--sg-acc)" stroke-width="6" stroke-dasharray="4 18" stroke-linecap="round"/>'
                '<circle cx="130" cy="330" r="16" fill="var(--sg-acc)"/><circle cx="950" cy="330" r="16" '
                'fill="none" stroke="var(--sg-acc)" stroke-width="6"/>'
                f'<g transform="translate(510 150) rotate({-90 if rtl else 90} 30 30) scale(2.5)" fill="#fff">{PLANE}</g></svg>'
                '<div class="sg-route-photo">' + p + '</div>')
    if tpl == "boarding_lux":
        return (p + '<div class="sg-pass"><div class="sg-stub"><svg viewBox="0 0 24 24">' + PLANE +
                '</svg><span>' + _esc(kicker or "") + '</span><div class="sg-barcode"></div></div></div>')
    if tpl == "menu_board":
        return '<div class="sg-board"></div><div class="sg-plate">' + p + '</div>'
    if tpl == "device":
        return '<div class="sg-glow"></div><div class="sg-phone"><div class="sg-screen">' + p + '</div><i></i></div>'
    if tpl == "lookbook":
        return '<div class="sg-look">' + p + '</div><div class="sg-look-side"></div>' + \
            (f'<div class="sg-vert">{_esc(kicker)}</div>' if kicker else "")
    if tpl == "pulse":
        return ('<div class="sg-pulse-photo">' + p + '</div><svg class="sg-ecg" viewBox="0 0 1080 120" '
                'preserveAspectRatio="none"><path d="M0 70 H360 L400 70 L430 20 L470 110 L505 40 L530 70 H1080" '
                'fill="none" stroke="var(--sg-pop)" stroke-width="8" stroke-linejoin="round"/></svg>')
    if tpl == "notebook":
        return '<div class="sg-ruled"></div><div class="sg-print">' + p + '<i class="sg-tape"></i></div>'
    if tpl == "stage":
        return '<div class="sg-beams"></div><div class="sg-stage-photo">' + p + '</div><div class="sg-dotsbg"></div>'
    if tpl == "seal":
        return (p + f'<div class="sg-seal-band"></div><div class="sg-emblem"><i>{icon_html}</i></div>')
    return p


# max text height and min font per layout (cover, content)
FIT = {"hero_band": (440, 44), "tailfin": (480, 44), "window": (330, 40), "split_color": (380, 44),
       "cover_mag": (380, 44), "frame_bold": (300, 40), "circle_orbit": (320, 40), "mosaic": (300, 40),
       "cutout_type": (560, 50), "type_poster": (500, 50), "sticker_price": (330, 40), "panorama": (340, 44),
       "arch_window": (700, 40), "neon_night": (330, 40), "brush_stroke": (360, 40), "duo_panel": (320, 40),
       "stripes_speed": (430, 44), "ribbon_corner": (430, 44), "minimal_luxe": (300, 38), "card_stack": (300, 40),
       "map_route": (330, 40), "boarding_lux": (330, 38), "menu_board": (300, 40), "device": (720, 40),
       "lookbook": (700, 40), "pulse": (300, 40), "notebook": (300, 40), "stage": (300, 40), "seal": (360, 40)}
FIT_CONTENT = {"hero_band": (450, 30), "tailfin": (470, 30), "window": (340, 28), "split_color": (390, 30),
               "cover_mag": (460, 30), "frame_bold": (310, 28), "circle_orbit": (330, 28), "mosaic": (310, 28),
               "cutout_type": (300, 28), "type_poster": (560, 30), "sticker_price": (340, 28), "panorama": (340, 28),
               "arch_window": (720, 28), "neon_night": (340, 28), "brush_stroke": (370, 28), "duo_panel": (330, 28),
               "stripes_speed": (440, 30), "ribbon_corner": (440, 30), "minimal_luxe": (310, 28),
               "card_stack": (310, 28), "map_route": (340, 28), "boarding_lux": (340, 28), "menu_board": (310, 28),
               "device": (720, 28), "lookbook": (720, 28), "pulse": (310, 28), "notebook": (310, 28),
               "stage": (310, 28), "seal": (370, 28)}
