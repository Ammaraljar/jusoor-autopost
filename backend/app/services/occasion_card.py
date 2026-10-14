"""The greeting image of an occasion post (one 1080×1350 slide): bright, clear and cheerful.

Every design is light — soft pastel or cream backgrounds, dark readable text, lively accents — and
is drawn here (lanterns, crescents, bunting, confetti, flowers, arches, fireworks…), so the most
sensitive occasions never depend on a stock photo. 24 layouts; each occasion only uses the ones
that suit its character (no confetti on a spiritual day, no party on a day of remembrance), and the
layout changes from one greeting to the next. Colours: the brand's main colour for the text, the
occasion's mood for the background (the flag's colours, softened, on national days).
"""
from __future__ import annotations

import base64
import colorsys
import html
import random
from datetime import date

from . import occasions_data as data

MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"),
    "ms": ("Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September", "Oktober", "November",
           "Disember"),
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"),
}
HIJRI_MONTHS = ("Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani", "Jumada al-Ula", "Jumada al-Akhirah", "Rajab",
                "Shaban", "Ramadan", "Shawwal", "Dhul Qadah", "Dhul Hijjah")

# layouts and the occasion characters they suit
LAYOUTS: dict[str, tuple[str, ...]] = {
    "lanterns": ("spiritual", "festive"),
    "crescent_sky": ("spiritual", "festive"),
    "arch": ("spiritual", "festive", "appreciation"),
    "geo": ("spiritual", "festive", "pride", "appreciation"),
    "floral": ("spiritual", "festive", "appreciation", "awareness"),
    "gold_frame": ("spiritual", "festive", "pride", "appreciation", "memorial", "awareness"),
    "medallion": ("spiritual", "festive", "pride", "appreciation", "awareness", "commercial"),
    "line_art": ("spiritual", "festive", "pride", "appreciation", "awareness", "memorial"),
    "hills": ("spiritual", "festive", "pride", "appreciation", "awareness"),
    "garland": ("spiritual", "festive", "appreciation"),
    "watercolor": ("spiritual", "festive", "pride", "appreciation", "awareness", "memorial", "commercial"),
    "stamp": ("festive", "pride", "appreciation", "spiritual"),
    "confetti": ("festive", "pride", "appreciation", "commercial"),
    "balloons": ("festive", "appreciation", "commercial"),
    "bunting": ("festive", "pride", "commercial"),
    "sunburst": ("festive", "pride", "commercial", "appreciation"),
    "fireworks": ("festive", "pride"),
    "ribbon": ("festive", "pride", "appreciation", "commercial", "awareness"),
    "card": ("festive", "appreciation", "awareness", "spiritual"),
    "big_number": ("pride", "festive"),
    "split": ("pride", "appreciation", "awareness", "commercial", "festive"),
    "ticket": ("commercial", "festive"),
    "speech": ("appreciation", "festive", "commercial", "awareness"),
    "photo_card": ("appreciation", "awareness", "commercial", "festive"),
}
# occasions whose pictures are sensitive: drawn designs only, never a stock photo
NO_PHOTO_KINDS = ("religious", "weekly", "national")
NO_PHOTO_TONES = ("spiritual", "pride", "memorial")
# safe photo searches (no people) by motif, for the days that may carry a photo
SAFE_KEYWORDS = {
    "book": "open books library desk", "heart": "pastel flowers bouquet", "ribbon": "pink ribbon flowers",
    "leaf": "green leaves nature light", "globe": "travel map globe suitcase", "cup": "coffee cup beans",
    "tag": "shopping bags gifts colorful", "camera": "vintage camera photography", "sparkle": "confetti celebration lights",
    "home": "modern house exterior", "star": "christmas lights decoration", "lamp": "diya oil lamps flowers",
    "lantern": "lanterns lights festival",
}

MOTIFS = {
    "crescent": '<path d="M62 12a40 40 0 1 0 26 66A34 34 0 1 1 62 12z" fill="currentColor"/>'
                '<path d="M74 30l3.2 9.6 10.1.1-8.1 6 3 9.7-8.2-5.9-8.2 5.9 3-9.7-8.1-6 10.1-.1z" fill="currentColor"/>',
    "lantern": '<path d="M50 4v8M38 14h24l6 10H32zM32 24h36l-4 50H36zM36 74h28l-6 10H42zM46 84h8v8h-8z" '
               'fill="none" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/>'
               '<path d="M50 34c6 8 6 22 0 30-6-8-6-22 0-30z" fill="currentColor"/>',
    "mosque": '<path d="M50 14c-3 6-16 12-16 26h32c0-14-13-20-16-26z" fill="currentColor"/>'
              '<rect x="30" y="40" width="40" height="40" fill="currentColor"/>'
              '<path d="M44 80V64a6 6 0 0 1 12 0v16z" fill="#fff" opacity=".5"/>'
              '<path d="M16 80V34l4-8 4 8v46zM76 80V34l4-8 4 8v46z" fill="currentColor"/>'
              '<path d="M10 82h80" stroke="currentColor" stroke-width="4"/><circle cx="50" cy="10" r="3" fill="currentColor"/>',
    "flag": '<path d="M22 10v82" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>'
            '<path d="M24 14c16-8 30 8 46 0s20-2 20-2v40s-6-6-20 2-30-8-46 0z" fill="currentColor"/>',
    "sparkle": '<path d="M42 10c3 20 8 25 28 28-20 3-25 8-28 28-3-20-8-25-28-28 20-3 25-8 28-28z" fill="currentColor"/>'
               '<path d="M76 56c2 10 4 12 14 14-10 2-12 4-14 14-2-10-4-12-14-14 10-2 12-4 14-14z" fill="currentColor"/>',
    "heart": '<path d="M50 86S12 62 12 36a19 19 0 0 1 38-6 19 19 0 0 1 38 6c0 26-38 50-38 50z" fill="currentColor"/>',
    "book": '<path d="M50 24c-10-8-26-10-38-8v60c12-2 28 0 38 8 10-8 26-10 38-8V16c-12-2-28 0-38 8z" fill="none" '
            'stroke="currentColor" stroke-width="5" stroke-linejoin="round"/><path d="M50 24v60" stroke="currentColor" stroke-width="5"/>',
    "ribbon": '<path d="M50 10c-12 0-18 10-14 24l26 52 10-6-24-46c-2-6 0-10 2-10s4 4 2 10L28 80l10 6 26-52c4-14-2-24-14-24z" '
              'fill="currentColor"/>',
    "leaf": '<path d="M82 14C36 14 18 40 18 64c0 8 2 14 6 20 4-22 18-38 40-46-20 10-30 26-32 46 46 4 56-38 50-70z" '
            'fill="currentColor"/>',
    "globe": '<circle cx="50" cy="50" r="38" fill="none" stroke="currentColor" stroke-width="5"/>'
             '<path d="M12 50h76M50 12c-14 16-14 60 0 76M50 12c14 16 14 60 0 76" fill="none" stroke="currentColor" stroke-width="4"/>',
    "cup": '<path d="M18 36h52v18a26 26 0 0 1-52 0zM70 42h6a10 10 0 0 1 0 20h-8" fill="none" stroke="currentColor" '
           'stroke-width="5"/><path d="M34 12c-4 6 4 10 0 16M48 12c-4 6 4 10 0 16" fill="none" stroke="currentColor" '
           'stroke-width="4" stroke-linecap="round"/>',
    "tag": '<path d="M48 10h36a6 6 0 0 1 6 6v36L50 92 8 50z" fill="currentColor"/><circle cx="72" cy="28" r="7" fill="#fff"/>',
    "camera": '<path d="M36 22l-6 10H16a6 6 0 0 0-6 6v38a6 6 0 0 0 6 6h68a6 6 0 0 0 6-6V38a6 6 0 0 0-6-6H70l-6-10z" '
              'fill="currentColor"/><circle cx="50" cy="56" r="15" fill="#fff" opacity=".6"/>',
    "home": '<path d="M12 48L50 14l38 34M22 40v44h56V40" fill="none" stroke="currentColor" stroke-width="6" '
            'stroke-linejoin="round"/><rect x="42" y="58" width="16" height="26" fill="currentColor"/>',
    "star": '<path d="M50 6l12 30 32 2-25 20 8 32-27-18-27 18 8-32L6 38l32-2z" fill="currentColor"/>',
    "lamp": '<path d="M14 56h72c-4 18-18 28-36 28S18 74 14 56z" fill="currentColor"/>'
            '<path d="M50 50c-8-10-4-22 0-34 4 12 8 24 0 34z" fill="currentColor"/>',
}

# pastel moods: (background 1, background 2, accent 1, accent 2)
MOODS = {
    "spiritual": ("#FFF8EA", "#EAF6F2", "#D4A537", "#2A9D8F"),
    "festive": ("#FFF4F1", "#EAF7FF", "#F2A541", "#E76F9A"),
    "appreciation": ("#FFF6EE", "#F3EEFF", "#F08A5D", "#8E7CC3"),
    "awareness": ("#FFF2F6", "#EEF8F1", "#E86F9C", "#4CAF7A"),
    "commercial": ("#FFF7E0", "#FFECEF", "#FF8A3D", "#E8436A"),
    "memorial": ("#F6F7FA", "#EEF2F6", "#8A97AD", "#5D6B82"),
    "pride": ("#F2FAF5", "#FFFFFF", "#2E8B57", "#C9A227"),
}


def _e(text: str) -> str:
    return html.escape(text or "")


def _svg(motif: str, cls: str = "oc-motif", color: str | None = None) -> str:
    body = MOTIFS.get(motif) or MOTIFS["sparkle"]
    style = f' style="color:{color}"' if color else ""
    return f'<svg class="{cls}" viewBox="0 0 100 100" aria-hidden="true"{style}>{body}</svg>'


def _uri(data_bytes: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(data_bytes).decode()}"


def _rgb(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        return (0.5, 0.5, 0.5)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb) -> str:  # noqa: ANN001
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def tint(hex_colour: str, amount: float) -> str:
    """The colour mixed with white (amount 0 = colour, 1 = white)."""
    r, g, b = _rgb(hex_colour)
    return _hex((r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount))


def _lum(hex_colour: str) -> float:
    r, g, b = _rgb(hex_colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _vivid(hex_colour: str) -> bool:
    r, g, b = _rgb(hex_colour)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return s > 0.25 and 0.15 < l < 0.85


def mood_colours(occ: dict, ink: str) -> dict[str, str]:
    """Background and accent colours of the greeting: light, and the flag's colours on national days."""
    tone = occ.get("tone") or "festive"
    bg1, bg2, a1, a2 = MOODS.get(tone, MOODS["festive"])
    flag = [c for c in occ.get("flag") or [] if _vivid(c)]
    if flag:
        a1 = flag[0]
        a2 = flag[1] if len(flag) > 1 else a2
        bg1, bg2 = tint(a1, 0.92), tint(a2, 0.9)
    if occ.get("motif") == "ribbon":
        a1, bg1 = "#E86F9C", "#FFF0F5"
    return {"bg1": bg1, "bg2": bg2, "a1": a1, "a2": a2, "ink": ink if _lum(ink) < 0.45 else "#1F2A44",
            "soft": tint(a1, 0.75), "soft2": tint(a2, 0.78)}


def date_text(day: date, lang: str, hijri: bool) -> str:
    """The date line on the image: Hijri first on religious days."""
    from .occasions import date_label, hijri_label, hijri_of
    if lang == "ar":
        greg = date_label(day, "ar")
        h = hijri_label(day, "ar") if hijri else ""
    else:
        months = MONTHS.get(lang, MONTHS["en"])
        greg = f"{day.day} {months[day.month - 1]} {day.year}"
        hh = hijri_of(day) if hijri else None
        h = f"{hh[2]} {HIJRI_MONTHS[hh[1] - 1]} {hh[0]} AH" if hh else ""
    return " · ".join(x for x in (h, greg) if x)


def uses_photo(occ: dict) -> bool:
    """Only days whose pictures are not sensitive may carry a (safe, people-free) photo."""
    return occ.get("kind") not in NO_PHOTO_KINDS and occ.get("tone") not in NO_PHOTO_TONES


def safe_keywords(occ: dict) -> str:
    return SAFE_KEYWORDS.get(occ.get("motif") or "", "flowers light pastel")


def layouts_for(occ: dict) -> list[str]:
    tone = occ.get("tone") or "festive"
    motif = occ.get("motif") or ""
    out = [name for name, tones in LAYOUTS.items() if tone in tones]
    if motif not in ("lantern", "crescent"):                 # lanterns and night sky belong to Ramadan/Eid
        out = [x for x in out if x not in ("lanterns", "crescent_sky")]
    if occ.get("number") is None:
        out = [x for x in out if x != "big_number"]
    if not uses_photo(occ):
        out = [x for x in out if x != "photo_card"]
    return out or ["watercolor"]


def spec_for(occ: dict, lang: str, design: int) -> dict:
    """What the slide needs to know about the occasion."""
    countries = occ.get("countries") or []
    flag = ()
    if occ.get("kind") == "national" and len(countries) == 1 and countries[0] in data.COUNTRIES:
        flag = data.COUNTRIES[countries[0]][4]
    try:
        day = date.fromisoformat(occ.get("date") or "")
    except ValueError:
        day = None
    religious = str(occ.get("key", "")).startswith(("isl:", "weekly:"))
    name = occ.get("name_ar") if lang == "ar" else (occ.get("name_en") or occ.get("name_ar"))
    options = layouts_for({**occ, "flag": list(flag)})
    rnd = random.Random(f"{occ.get('key')}")
    rnd.shuffle(options)                                     # each occasion has its own order of layouts
    return {"layout": options[design % len(options)], "layouts": len(options), "motif": occ.get("motif") or "sparkle",
            "tone": occ.get("tone") or "festive", "kind": occ.get("kind"), "name": name or "",
            "number": occ.get("number"), "flag": list(flag), "religious": religious, "key": occ.get("key") or "",
            "photo": uses_photo(occ), "date": date_text(day, lang, religious) if day else ""}


# ------------------------------------------------------------------ drawn decorations
def _lantern(x: float, string: float, size: float, color: str, glow: str) -> str:
    s = size
    return (f'<g transform="translate({x},0)"><line x1="0" y1="0" x2="0" y2="{string}" stroke="{color}" stroke-width="3"/>'
            f'<g transform="translate({-s / 2},{string})">'
            f'<path d="M{s * .35} 0h{s * .3}l{s * .12} {s * .18}H{s * .23}z" fill="{color}"/>'
            f'<path d="M{s * .15} {s * .18}h{s * .7}l-{s * .08} {s * .9}H{s * .23}z" fill="{glow}" stroke="{color}" stroke-width="5"/>'
            f'<path d="M{s * .5} {s * .35}c{s * .12} {s * .15} {s * .12} {s * .4} 0 {s * .55}c-{s * .12}-{s * .15}-{s * .12}-{s * .4} 0-{s * .55}z" fill="{color}" opacity=".85"/>'
            f'<path d="M{s * .23} {s * 1.08}h{s * .54}l-{s * .1} {s * .14}H{s * .33}z" fill="{color}"/></g></g>')


def _stars(rnd: random.Random, n: int, color: str, area=(0, 0, 1080, 520)) -> str:
    out = []
    for _ in range(n):
        x, y = rnd.uniform(area[0], area[2]), rnd.uniform(area[1], area[3])
        r = rnd.uniform(6, 16)
        out.append(f'<path transform="translate({x:.0f},{y:.0f}) scale({r / 10:.2f})" '
                   f'd="M0-10l2.4 7.6H10L3.8 2l2.4 8L0 5.2-6.2 10l2.4-8L-10-2.4h7.6z" fill="{color}" opacity="{rnd.uniform(.5, 1):.2f}"/>')
    return "".join(out)


def _confetti(rnd: random.Random, colours: list[str], n: int = 70, area=(0, 0, 1080, 1350),
              hole=(170, 200, 910, 1190)) -> str:
    """Confetti pieces around the edges: none falls on the text area (hole)."""
    out = []
    i = -1
    for _ in range(n * 6):
        if len(out) >= n:
            break
        x, y = rnd.uniform(area[0], area[2]), rnd.uniform(area[1], area[3])
        if hole and hole[0] - 20 < x < hole[2] and hole[1] - 20 < y < hole[3]:
            continue
        if 230 < x < 850 and (y > 1180 or y < 180):             # the footer line and the logo stay clear
            continue
        i += 1
        c = colours[i % len(colours)]
        rot = rnd.uniform(0, 180)
        if i % 3 == 0:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(5, 10):.0f}" fill="{c}"/>')
        elif i % 3 == 1:
            out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{rnd.uniform(14, 26):.0f}" height="9" rx="3" fill="{c}" '
                       f'transform="rotate({rot:.0f} {x:.0f} {y:.0f})"/>')
        else:
            out.append(f'<path d="M{x:.0f} {y:.0f} q12 -14 24 0 t24 0" stroke="{c}" stroke-width="6" fill="none" '
                       f'stroke-linecap="round" transform="rotate({rot:.0f} {x:.0f} {y:.0f})"/>')
    return "".join(out)


def _flower(x: float, y: float, r: float, petal: str, centre: str) -> str:
    petals = "".join(f'<ellipse cx="{x}" cy="{y - r * .55}" rx="{r * .32}" ry="{r * .55}" fill="{petal}" '
                     f'transform="rotate({a} {x} {y})"/>' for a in range(0, 360, 72))
    return petals + f'<circle cx="{x}" cy="{y}" r="{r * .26}" fill="{centre}"/>'


def _leafy(x: float, y: float, angle: float, color: str, size: float = 1) -> str:
    return (f'<g transform="translate({x},{y}) rotate({angle}) scale({size})">'
            f'<path d="M0 0c20-30 60-34 90-20-30 6-60 20-90 20z" fill="{color}"/>'
            f'<path d="M0 0c26 16 64 14 88 -6-30 2-60 10-88 6z" fill="{color}" opacity=".7"/></g>')


def _burst(cx: float, cy: float, r: float, color: str, n: int = 16) -> str:
    import math
    lines = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x1, y1 = cx + math.cos(a) * r * .35, cy + math.sin(a) * r * .35
        x2, y2 = cx + math.cos(a) * r, cy + math.sin(a) * r
        lines.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" stroke-width="6" '
                     f'stroke-linecap="round"/><circle cx="{x2:.0f}" cy="{y2:.0f}" r="6" fill="{color}"/>')
    return "".join(lines)


def _bunting(colours: list[str], y: float = 0, sag: float = 70) -> str:
    out = [f'<path d="M-20 {y + 10} Q540 {y + 10 + sag * 2} 1100 {y + 10}" stroke="#9AA3B5" stroke-width="3" fill="none"/>']
    n = 12
    for i in range(n):
        t = (i + .5) / n
        x = -20 + 1120 * t
        yy = y + 10 + 2 * sag * 2 * t * (1 - t)
        c = colours[i % len(colours)]
        out.append(f'<path d="M{x - 34:.0f} {yy:.0f} L{x + 34:.0f} {yy:.0f} L{x:.0f} {yy + 78:.0f}z" fill="{c}"/>')
    return "".join(out)


def _pattern(color: str) -> str:
    star = ('<path d="M60 20l12 28 28 12-28 12-12 28-12-28-28-12 28-12z" fill="none" stroke="currentColor" stroke-width="3"/>'
            '<rect x="38" y="38" width="44" height="44" transform="rotate(45 60 60)" fill="none" stroke="currentColor" '
            'stroke-width="3"/>')
    return (f'<svg class="oc-layer" viewBox="0 0 1080 1350" style="color:{color}"><defs><pattern id="ocp" width="120" '
            f'height="120" patternUnits="userSpaceOnUse">{star}</pattern></defs><rect width="1080" height="1350" fill="url(#ocp)"/></svg>')


CSS = """
.oc { position: absolute; inset: 0; overflow: hidden; color: var(--oc-ink);
  background: linear-gradient(165deg, var(--oc-bg1) 0%, var(--oc-bg2) 100%); }
.oc-layer { position: absolute; inset: 0; width: 1080px; height: 1350px; }
.oc-logo { position: absolute; top: 64px; left: 0; right: 0; display: flex; justify-content: center; z-index: 5; }
.oc .logo img { height: 92px; filter: none; }
.oc .logo .wordmark { color: var(--oc-ink); text-shadow: none; }
.oc .logo .wordmark span { color: var(--oc-a1); }
.oc .logo.plate { background: var(--oc-ink); }
.oc-body { position: absolute; inset: 230px 110px 200px; display: flex; flex-direction: column; align-items: center;
  justify-content: center; text-align: center; gap: 26px; z-index: 4; }
.oc-motif { display: block; width: 140px; height: 140px; color: var(--oc-a1); }
.oc-kicker { font-weight: 800; font-size: 34px; color: var(--oc-a2); line-height: 1.4; }
.lang-en .oc-kicker, .lang-fr .oc-kicker, .lang-ms .oc-kicker { text-transform: uppercase; letter-spacing: 3px; font-size: 28px; }
.oc-text { font-size: 116px; }
.oc-text h1 { font-size: 1em; line-height: 1.18; font-weight: 900; color: var(--oc-ink); }
.oc-text h1 em { font-style: normal; color: var(--oc-a1); }
.oc-text p { font-size: .33em; line-height: 1.6; font-weight: 700; color: var(--oc-ink); opacity: .78; margin-top: .65em; }
.oc-date { font-size: 29px; font-weight: 800; color: var(--oc-ink); background: rgba(255,255,255,.75);
  border: 2px solid var(--oc-soft); padding: 10px 28px; border-radius: 999px; }
.oc-num { font-weight: 900; color: var(--oc-a1); line-height: 1; font-size: 150px; direction: ltr; unicode-bidi: isolate; }
.oc-foot { position: absolute; bottom: 60px; left: 0; right: 0; text-align: center; font-size: 28px; font-weight: 800;
  color: var(--oc-ink); opacity: .8; direction: ltr; unicode-bidi: isolate; z-index: 5; }
.oc-flagbar { position: absolute; left: 0; right: 0; bottom: 0; height: 18px; display: flex; z-index: 6; }
.oc-flagbar i { flex: 1; }

/* night-free Ramadan sky: soft dawn, lanterns, crescent */
.oc-crescent_sky { background: linear-gradient(180deg, #DDEBFF 0%, #FFF3E2 70%, #FFE9D6 100%); }
.oc-crescent_sky .oc-body { inset: 360px 110px 220px; }
.oc-lanterns .oc-body { inset: 420px 110px 190px; }
/* Islamic arch window */
.oc-arch .oc-body { inset: 330px 190px 250px; }
.oc-arch .oc-text { font-size: 100px; }
/* geometric pattern + white medallion */
.oc-geo .oc-panel, .oc-medallion .oc-panel { position: absolute; left: 150px; right: 150px; top: 290px; bottom: 230px;
  background: #fff; border-radius: 48px; box-shadow: 0 24px 60px rgba(31,42,68,.12); border: 3px solid var(--oc-soft); }
.oc-geo .oc-body { inset: 320px 190px 260px; }
.oc-geo .oc-text, .oc-medallion .oc-text { font-size: 96px; }
.oc-medallion .oc-panel { left: 120px; right: 120px; top: 270px; bottom: 210px; border-radius: 50%; }
.oc-medallion .oc-body { inset: 330px 200px 270px; }
/* flowers in the corners */
.oc-floral .oc-body { inset: 260px 150px 230px; }
/* thin golden double frame */
.oc-gold_frame .oc-frame { position: absolute; inset: 44px; border: 4px solid var(--oc-a1); border-radius: 30px; }
.oc-gold_frame .oc-frame::after { content: ""; position: absolute; inset: 16px; border: 2px solid var(--oc-soft); border-radius: 22px; }
.oc-gold_frame .oc-corner { position: absolute; width: 30px; height: 30px; background: var(--oc-a1); transform: rotate(45deg); }
.oc-gold_frame .c1 { top: 29px; left: 29px; } .oc-gold_frame .c2 { top: 29px; right: 29px; }
.oc-gold_frame .c3 { bottom: 29px; left: 29px; } .oc-gold_frame .c4 { bottom: 29px; right: 29px; }
/* big line drawing */
.oc-line_art .oc-big { position: absolute; width: 760px; height: 760px; left: 160px; top: 300px; color: var(--oc-soft); opacity: .7; }
/* hills / dunes */
.oc-hills .oc-body { inset: 230px 110px 380px; }
.oc-hills .oc-foot { color: #fff; opacity: 1; }
/* garland */
.oc-garland .oc-body { inset: 330px 120px 200px; }
/* watercolour wash */
.oc-watercolor { background:
  radial-gradient(circle at 18% 22%, var(--oc-soft) 0, transparent 34%),
  radial-gradient(circle at 85% 30%, var(--oc-soft2) 0, transparent 36%),
  radial-gradient(circle at 70% 85%, var(--oc-soft) 0, transparent 38%),
  radial-gradient(circle at 15% 80%, var(--oc-soft2) 0, transparent 30%), #FFFDF9; }
/* postage stamp */
.oc-stamp .oc-panel { position: absolute; left: 110px; right: 110px; top: 250px; bottom: 210px; background: #fff;
  border-radius: 10px; box-shadow: 0 18px 50px rgba(31,42,68,.12);
  -webkit-mask: radial-gradient(circle 14px at 14px 14px, transparent 98%, #000) -14px -14px / 40px 40px; }
.oc-stamp .oc-panel::after { content: ""; position: absolute; inset: 34px; border: 3px dashed var(--oc-a1); border-radius: 6px; }
.oc-stamp .oc-body { inset: 300px 170px 260px; }
.oc-stamp .oc-text { font-size: 98px; }
/* confetti, balloons, bunting, fireworks */
.oc-confetti, .oc-balloons, .oc-bunting { background: linear-gradient(180deg, #FFFFFF 0%, var(--oc-bg1) 100%); }
.oc-bunting .oc-body { inset: 300px 110px 200px; }
.oc-balloons .oc-body { inset: 260px 260px 260px 110px; align-items: flex-start; text-align: start; }
[dir="rtl"] .oc-balloons .oc-body { inset: 260px 110px 260px 260px; }
.oc-fireworks { background: linear-gradient(180deg, #FFE7EC 0%, #FFF4DE 60%, #FFFFFF 100%); }
/* sunburst */
.oc-sunburst { background: repeating-conic-gradient(from 0deg at 50% 52%, var(--oc-bg1) 0deg 9deg, #FFFFFF 9deg 18deg); }
.oc-sunburst .oc-panel { position: absolute; width: 760px; height: 760px; left: 160px; top: 330px; border-radius: 50%;
  background: radial-gradient(circle, #fff 60%, rgba(255,255,255,0) 71%); }
/* ribbon banner */
.oc-ribbon .oc-text { font-size: 100px; width: 100%; }
.oc-ribbon .oc-text h1 { color: #fff; background: var(--oc-a1); margin: .25em -150px 0; padding: .28em 150px .36em;
  transform: rotate(-4deg); text-shadow: 0 3px 0 rgba(0,0,0,.12); box-shadow: 0 16px 36px rgba(31,42,68,.16); }
.oc-ribbon .oc-text h1 em { color: var(--oc-ink); text-shadow: none; }
.oc-ribbon .oc-text p { color: var(--oc-ink); margin-top: 1.3em; }
/* greeting card */
.oc-card .oc-panel { position: absolute; left: 120px; right: 120px; top: 250px; bottom: 210px; background: #fff;
  border-radius: 36px; transform: rotate(-3deg); box-shadow: 0 30px 70px rgba(31,42,68,.16); border-top: 18px solid var(--oc-a1); }
.oc-card .oc-panel2 { position: absolute; left: 150px; right: 90px; top: 270px; bottom: 190px; background: var(--oc-soft2);
  border-radius: 36px; transform: rotate(4deg); }
.oc-card .oc-body { inset: 300px 180px 260px; }
.oc-card .oc-text { font-size: 98px; }
/* giant number */
.oc-big_number .oc-giant { position: absolute; left: 0; right: 0; top: 330px; text-align: center; font-size: 560px; font-weight: 900;
  line-height: 1; color: var(--oc-soft); direction: ltr; letter-spacing: -12px; }
.oc-big_number .oc-body { inset: 330px 110px 200px; }
/* two colours */
.oc-split { background: linear-gradient(180deg, var(--oc-a1) 0 38%, #FFFFFF 38% 100%); }
.oc-split .oc-logo .logo img { filter: brightness(0) invert(1); }
.oc-split .oc-logo .logo .wordmark, .oc-split .oc-logo .logo .wordmark span { color: #fff; }
.oc-split .oc-badge { position: absolute; left: 50%; top: 513px; transform: translate(-50%, -50%); width: 200px; height: 200px;
  border-radius: 50%; background: #fff; display: grid; place-items: center; box-shadow: 0 16px 40px rgba(31,42,68,.18); z-index: 5; }
.oc-split .oc-badge .oc-motif { width: 116px; height: 116px; }
.oc-split .oc-body { inset: 640px 110px 180px; }
.oc-split .oc-text { font-size: 100px; }
/* ticket */
.oc-ticket .oc-panel { position: absolute; left: 90px; right: 90px; top: 300px; bottom: 260px; background: #fff; border-radius: 36px;
  box-shadow: 0 24px 60px rgba(31,42,68,.14);
  -webkit-mask: radial-gradient(circle 40px at 0 50%, transparent 98%, #000) left / 51% 100% no-repeat,
                radial-gradient(circle 40px at 100% 50%, transparent 98%, #000) right / 51% 100% no-repeat; }
.oc-ticket .oc-panel::after { content: ""; position: absolute; top: 40px; bottom: 40px; left: 50%; border-left: 4px dashed var(--oc-soft); }
.oc-ticket .oc-strip { position: absolute; left: 90px; right: 90px; top: 300px; height: 120px; background: var(--oc-a1);
  border-radius: 36px 36px 0 0; }
.oc-ticket .oc-body { inset: 440px 150px 300px; }
.oc-ticket .oc-text { font-size: 96px; }
/* speech bubble */
.oc-speech .oc-panel { position: absolute; left: 100px; right: 100px; top: 270px; bottom: 330px; background: #fff;
  border-radius: 60px; border: 6px solid var(--oc-a1); }
.oc-speech .oc-tail { position: absolute; left: 260px; bottom: 270px; width: 90px; height: 90px; background: #fff;
  border-right: 6px solid var(--oc-a1); border-bottom: 6px solid var(--oc-a1); transform: skewX(-20deg) rotate(35deg); }
.oc-speech .oc-body { inset: 310px 150px 370px; }
.oc-speech .oc-text { font-size: 100px; }
/* photo card (only on days whose photos are not sensitive) */
.oc-photo_card .oc-photo { position: absolute; left: 90px; right: 90px; top: 220px; height: 560px; border-radius: 40px;
  background-size: cover; background-position: center; box-shadow: 0 24px 50px rgba(31,42,68,.18); border: 10px solid #fff; }
.oc-photo_card .oc-body { inset: 800px 110px 150px; gap: 16px; }
.oc-photo_card .oc-text { font-size: 84px; }
.oc-photo_card .oc-logo { top: 70px; }
/* remembrance: calm */
.memorial .oc-text h1 em { color: var(--oc-ink); }
"""


def _logo_block(logo_html: str) -> str:
    return f'<div class="oc-logo">{logo_html}</div>'


def build(spec, brand, lang: str, logo_html: str, logo_start: bool) -> tuple[str, str]:  # noqa: ANN001
    """(html, css) of an occasion greeting slide."""
    occ = spec.occasion or {}
    layout = occ.get("layout") if occ.get("layout") in LAYOUTS else "watercolor"
    tone = occ.get("tone") or "festive"
    motif = occ.get("motif") or "sparkle"
    number = occ.get("number")
    ink = ((brand.colors or {}).get("navy") or "#16244F")
    c = mood_colours(occ, ink)
    rnd = random.Random(f"{occ.get('key')}{layout}")
    flag = [x for x in occ.get("flag") or [] if isinstance(x, str) and x.startswith("#")]
    title = _e(spec.heading)
    for w in spec.highlight or []:
        if w and _e(w) in title:
            title = title.replace(_e(w), f"<em>{_e(w)}</em>", 1)
    sub = f"<p>{_e(spec.body)}</p>" if spec.body else ""
    kicker = (f'<div class="oc-kicker">{_e(occ.get("name"))}</div>'
              if occ.get("name") and occ.get("name") != spec.heading else "")
    when = f'<div class="oc-date">{_e(occ.get("date"))}</div>' if occ.get("date") else ""
    foot_text = " · ".join(x for x in (brand.handle, brand.website) if x)
    foot = f'<div class="oc-foot">{_e(foot_text)}</div>' if foot_text else ""
    flagbar = ('<div class="oc-flagbar">' + "".join(f'<i style="background:{x}"></i>' for x in (flag * 8)[:8]) + "</div>"
               ) if flag else ""
    fit = {"arch": "460,50", "geo": "420,48", "medallion": "380,46", "stamp": "430,48", "card": "430,48",
           "split": "330,46", "ticket": "290,44", "speech": "340,46", "photo_card": "220,40", "ribbon": "420,46",
           "balloons": "560,50", "hills": "430,50"}.get(layout, "520,52")
    text = f'<div class="oc-text" data-fit="{fit}"><h1>{title}</h1>{sub}</div>'
    head = f'<div class="oc-num">{number}</div>' if number else _svg(motif)
    style = (f"--oc-bg1:{c['bg1']};--oc-bg2:{c['bg2']};--oc-a1:{c['a1']};--oc-a2:{c['a2']};--oc-ink:{c['ink']};"
             f"--oc-soft:{c['soft']};--oc-soft2:{c['soft2']}")
    accents = [c["a1"], c["a2"], c["soft"], tint(c["a1"], .35), tint(c["a2"], .35)]
    deco, body_parts = "", [head, kicker, text, when]

    if layout == "lanterns":
        glow = tint(c["a1"], .6)
        lanterns = "".join(_lantern(x, s, z, c["a1"], glow) for x, s, z in
                           ((140, 120, 110), (300, 60, 80), (780, 80, 90), (940, 150, 120), (540, 20, 70)))
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350">{lanterns}'
                f'{_stars(rnd, 14, c["a1"], (60, 320, 1020, 420))}</svg>')
        body_parts = [kicker, text, when]
    elif layout == "crescent_sky":
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350"><g transform="translate(400,120) scale(2.8)" '
                f'style="color:{c["a1"]}">{MOTIFS["crescent"]}</g>{_stars(rnd, 22, c["a1"], (40, 60, 1040, 330))}'
                f'<path d="M0 1180 q140-60 280 0 t280 0 t280 0 t280 0V1350H0z" fill="#fff" opacity=".9"/>'
                f'<path d="M0 1230 q140-50 280 0 t280 0 t280 0 t280 0V1350H0z" fill="{c["soft"]}"/></svg>')
        body_parts = [kicker, text, when]
    elif layout == "arch":
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350"><path d="M150 1180V560Q150 250 540 230Q930 250 930 560V1180Z" '
                f'fill="#fff" stroke="{c["a1"]}" stroke-width="8"/><path d="M180 1150V570Q180 285 540 265Q900 285 900 570V1150Z" '
                f'fill="none" stroke="{c["soft"]}" stroke-width="3"/>'
                f'<g transform="translate(470,150) scale(1.4)" style="color:{c["a1"]}">{MOTIFS["mosque" if motif in ("mosque", "crescent", "lantern") else motif]}</g></svg>')
        body_parts = [kicker, text, when]
    elif layout in ("geo", "medallion"):
        deco = _pattern(c["soft"]) + '<div class="oc-panel"></div>'
    elif layout == "floral":
        flowers = "".join(_flower(x, y, r, p, q) for x, y, r, p, q in (
            (90, 260, 90, c["soft"], c["a1"]), (190, 170, 60, c["soft2"], c["a2"]), (990, 1090, 95, c["soft"], c["a1"]),
            (880, 1190, 60, c["soft2"], c["a2"]), (980, 230, 50, c["soft2"], c["a1"]), (110, 1150, 55, c["soft2"], c["a2"])))
        leaves = "".join(_leafy(x, y, a, tint(c["a2"], .3), 1.2) for x, y, a in
                         ((40, 330, -20), (250, 120, 30), (1040, 1000, 160), (820, 1240, 200)))
        deco = f'<svg class="oc-layer" viewBox="0 0 1080 1350">{leaves}{flowers}</svg>'
    elif layout == "gold_frame":
        deco = ('<div class="oc-frame"></div><i class="oc-corner c1"></i><i class="oc-corner c2"></i>'
                '<i class="oc-corner c3"></i><i class="oc-corner c4"></i>')
    elif layout == "line_art":
        deco = _svg(motif, "oc-big")
        body_parts = [kicker, text, when]
    elif layout == "hills":
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350"><circle cx="820" cy="250" r="90" fill="{tint(c["a1"], .45)}"/>'
                f'<path d="M0 1010 C240 900 420 1000 620 950 S960 880 1080 960 V1350 H0z" fill="{c["soft2"]}"/>'
                f'<path d="M0 1090 C200 1020 420 1110 640 1060 S940 1000 1080 1060 V1350 H0z" fill="{tint(c["a2"], .35)}"/>'
                f'<path d="M0 1180 C260 1130 480 1210 700 1160 S960 1120 1080 1150 V1350 H0z" fill="{c["a2"]}"/></svg>')
    elif layout == "garland":
        bulbs = []
        for i in range(13):
            t = i / 12
            x, y = 40 + 1000 * t, 140 + 300 * t * (1 - t) * 1.6
            bulbs.append(_leafy(x, y, rnd.uniform(-40, 40), tint(c["a2"], .25), .8))
            bulbs.append(f'<circle cx="{x:.0f}" cy="{y + 30:.0f}" r="13" fill="{accents[i % 2]}"/>')
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350"><path d="M40 140 Q540 420 1040 140" stroke="{c["a2"]}" '
                f'stroke-width="5" fill="none"/>{"".join(bulbs)}</svg>')
    elif layout == "watercolor":
        pass
    elif layout == "stamp":
        deco = '<div class="oc-panel"></div>'
    elif layout == "confetti":
        deco = f'<svg class="oc-layer" viewBox="0 0 1080 1350">{_confetti(rnd, accents)}</svg>'
    elif layout == "balloons":
        balloons = []
        for i, (x, y, r) in enumerate(((880, 300, 95), (760, 440, 80), (960, 520, 75), (840, 650, 70))):
            col = accents[i % 3]
            balloons.append(f'<path d="M{x} {y + r * 1.15} q-20 120 10 240 t-10 200" stroke="#9AA3B5" stroke-width="3" fill="none"/>'
                            f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r * 1.18}" fill="{col}"/>'
                            f'<ellipse cx="{x - r * .35}" cy="{y - r * .45}" rx="{r * .2}" ry="{r * .32}" fill="#fff" opacity=".45"/>'
                            f'<path d="M{x - 12} {y + r * 1.15}h24l-12 18z" fill="{col}"/>')
        mirror = ' transform="translate(1080,0) scale(-1,1)"' if lang == "ar" else ""
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350"><g{mirror}>{"".join(balloons)}</g>'
                f'{_confetti(rnd, accents, 26, (40, 1060, 1040, 1320))}</svg>')
    elif layout == "bunting":
        colours = flag or accents[:3]
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350">{_bunting(colours, 150, 40)}'
                f'{_confetti(rnd, accents, 22, (40, 1060, 1040, 1320))}</svg>')
    elif layout == "sunburst":
        deco = '<div class="oc-panel"></div>'
    elif layout == "fireworks":
        cols = flag or accents
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350">{_burst(200, 300, 150, cols[0 % len(cols)])}'
                f'{_burst(880, 230, 120, cols[1 % len(cols)], 14)}{_burst(900, 1110, 130, cols[2 % len(cols)], 12)}'
                f'{_burst(160, 1130, 100, cols[0], 12)}{_stars(rnd, 16, c["a1"], (40, 40, 1040, 1300))}</svg>')
    elif layout == "ribbon":
        deco = f'<svg class="oc-layer" viewBox="0 0 1080 1350">{_confetti(rnd, accents, 34)}</svg>'
        body_parts = [head, kicker, text, when]
    elif layout == "card":
        deco = '<div class="oc-panel2"></div><div class="oc-panel"></div>'
    elif layout == "big_number":
        deco = f'<div class="oc-giant">{number}</div>'
        body_parts = [kicker, text, when]
    elif layout == "split":
        deco = f'<div class="oc-badge">{_svg(motif)}</div>'
        body_parts = ([f'<div class="oc-num">{number}</div>'] if number else []) + [kicker, text, when]
    elif layout == "ticket":
        deco = '<div class="oc-panel"></div><div class="oc-strip"></div>'
    elif layout == "speech":
        deco = (f'<svg class="oc-layer" viewBox="0 0 1080 1350">{_confetti(rnd, accents, 18, (40, 1060, 1040, 1320))}</svg>'
                '<div class="oc-panel"></div><div class="oc-tail"></div>')
    elif layout == "photo_card":
        if spec.background:
            deco = f'<div class="oc-photo" style="background-image:url({_uri(spec.background)})"></div>'
            body_parts = [kicker, text, when]
        else:
            layout = "watercolor"

    body = "".join(x for x in body_parts if x)
    content = (f'<div class="oc oc-{layout} {tone}" style="{style}">{deco}{_logo_block(logo_html)}'
               f'<div class="oc-body">{body}</div>{foot}{flagbar}</div>')
    return content, CSS
