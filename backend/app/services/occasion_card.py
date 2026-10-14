"""The greeting image of an occasion post (one 1080×1350 slide).

Three layouts rotate from post to post (the "redesign" button moves to the next one):
  frame   — the photo under a deep brand shade, an ornamental gold frame, everything centred;
  arch    — the photo on top, a brand-colour arch below carrying the greeting (heritage feel);
  pattern — no photo: brand colour with a pattern that fits the occasion (geometric stars for
            religious days, the flag's colours for national days, confetti for celebrations) and the
            anniversary number set huge behind the greeting.
The motif (crescent, lantern, mosque, flag burst, heart, book…) and the flag colours come from the
occasion, the colours and fonts from the brand.
"""
from __future__ import annotations

import base64
import html
from datetime import date

from . import occasions_data as data

LAYOUTS = ("frame", "arch", "pattern")
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

# simple line/solid icons on a 100×100 grid, drawn in the brand's accent colour
MOTIFS = {
    "crescent": '<path d="M62 12a40 40 0 1 0 26 66A34 34 0 1 1 62 12z" fill="currentColor"/>'
                '<path d="M74 30l3.2 9.6 10.1.1-8.1 6 3 9.7-8.2-5.9-8.2 5.9 3-9.7-8.1-6 10.1-.1z" fill="currentColor"/>',
    "lantern": '<path d="M50 4v8M38 14h24l6 10H32zM32 24h36l-4 50H36zM36 74h28l-6 10H42zM46 84h8v8h-8z" '
               'fill="none" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/>'
               '<path d="M50 34c6 8 6 22 0 30-6-8-6-22 0-30z" fill="currentColor"/>'
               '<path d="M40 30v40M60 30v40" stroke="currentColor" stroke-width="2.5" opacity=".7"/>',
    "mosque": '<path d="M50 14c-3 6-16 12-16 26h32c0-14-13-20-16-26z" fill="currentColor"/>'
              '<rect x="30" y="40" width="40" height="40" fill="currentColor"/>'
              '<path d="M44 80V64a6 6 0 0 1 12 0v16z" fill="#0003"/>'
              '<path d="M16 80V34l4-8 4 8v46zM76 80V34l4-8 4 8v46z" fill="currentColor"/>'
              '<path d="M10 82h80" stroke="currentColor" stroke-width="4"/><circle cx="50" cy="10" r="3" fill="currentColor"/>',
    "flag": '<g fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round">'
            '<path d="M50 50L50 8M50 50L80 20M50 50L92 50M50 50L80 80M50 50L50 92M50 50L20 80M50 50L8 50M50 50L20 20"/>'
            '</g><circle cx="50" cy="50" r="10" fill="currentColor"/>',
    "sparkle": '<path d="M42 10c3 20 8 25 28 28-20 3-25 8-28 28-3-20-8-25-28-28 20-3 25-8 28-28z" fill="currentColor"/>'
               '<path d="M76 56c2 10 4 12 14 14-10 2-12 4-14 14-2-10-4-12-14-14 10-2 12-4 14-14z" fill="currentColor"/>',
    "heart": '<path d="M50 86S12 62 12 36a19 19 0 0 1 38-6 19 19 0 0 1 38 6c0 26-38 50-38 50z" fill="currentColor"/>',
    "book": '<path d="M50 24c-10-8-26-10-38-8v60c12-2 28 0 38 8 10-8 26-10 38-8V16c-12-2-28 0-38 8z" fill="none" '
            'stroke="currentColor" stroke-width="4" stroke-linejoin="round"/><path d="M50 24v60" stroke="currentColor" '
            'stroke-width="4"/>',
    "ribbon": '<path d="M50 10c-12 0-18 10-14 24l26 52 10-6-24-46c-2-6 0-10 2-10s4 4 2 10L28 80l10 6 26-52c4-14-2-24-14-24z" '
              'fill="currentColor"/>',
    "leaf": '<path d="M82 14C36 14 18 40 18 64c0 8 2 14 6 20 4-22 18-38 40-46-20 10-30 26-32 46 46 4 56-38 50-70z" '
            'fill="currentColor"/>',
    "globe": '<circle cx="50" cy="50" r="38" fill="none" stroke="currentColor" stroke-width="4"/>'
             '<path d="M12 50h76M50 12c-14 16-14 60 0 76M50 12c14 16 14 60 0 76M20 30h60M20 70h60" fill="none" '
             'stroke="currentColor" stroke-width="3"/>',
    "cup": '<path d="M18 36h52v18a26 26 0 0 1-52 0zM70 42h6a10 10 0 0 1 0 20h-8" fill="none" stroke="currentColor" '
           'stroke-width="4"/><path d="M34 12c-4 6 4 10 0 16M48 12c-4 6 4 10 0 16" fill="none" stroke="currentColor" '
           'stroke-width="3" stroke-linecap="round"/><path d="M14 88h66" stroke="currentColor" stroke-width="4"/>',
    "tag": '<path d="M48 10h36a6 6 0 0 1 6 6v36L50 92 8 50z" fill="currentColor"/><circle cx="72" cy="28" r="7" fill="#0004"/>'
           '<path d="M38 58l20-20" stroke="#0005" stroke-width="5"/>',
    "camera": '<path d="M36 22l-6 10H16a6 6 0 0 0-6 6v38a6 6 0 0 0 6 6h68a6 6 0 0 0 6-6V38a6 6 0 0 0-6-6H70l-6-10z" '
              'fill="currentColor"/><circle cx="50" cy="56" r="15" fill="#0004"/>',
    "home": '<path d="M12 48L50 14l38 34M22 40v44h56V40" fill="none" stroke="currentColor" stroke-width="5" '
            'stroke-linejoin="round"/><rect x="42" y="58" width="16" height="26" fill="currentColor"/>',
    "star": '<path d="M50 6l12 30 32 2-25 20 8 32-27-18-27 18 8-32L6 38l32-2z" fill="currentColor"/>',
    "lamp": '<path d="M14 56h72c-4 18-18 28-36 28S18 74 14 56z" fill="currentColor"/>'
            '<path d="M50 50c-8-10-4-22 0-34 4 12 8 24 0 34z" fill="currentColor"/>',
}


def _e(text: str) -> str:
    return html.escape(text or "")


def _svg(motif: str, cls: str = "oc-motif") -> str:
    body = MOTIFS.get(motif) or MOTIFS["sparkle"]
    return f'<svg class="{cls}" viewBox="0 0 100 100" aria-hidden="true">{body}</svg>'


def _uri(data_bytes: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(data_bytes).decode()}"


def date_text(day: date, lang: str, hijri: bool) -> str:
    """The date line on the image: Hijri first on religious days."""
    from .occasions import date_label, hijri_of, hijri_label
    if lang == "ar":
        greg = date_label(day, "ar")
        h = hijri_label(day, "ar") if hijri else ""
    else:
        months = MONTHS.get(lang, MONTHS["en"])
        greg = f"{day.day} {months[day.month - 1]} {day.year}"
        hh = hijri_of(day) if hijri else None
        h = f"{hh[2]} {HIJRI_MONTHS[hh[1] - 1]} {hh[0]} AH" if hh else ""
    return " · ".join(x for x in (h, greg) if x)


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
    religious = occ.get("kind") in ("religious", "weekly") and str(occ.get("key", "")).startswith(("isl:", "weekly:"))
    name = occ.get("name_ar") if lang == "ar" else (occ.get("name_en") or occ.get("name_ar"))
    layout = LAYOUTS[design % len(LAYOUTS)]
    if occ.get("tone") == "memorial":
        layout = "frame"
    return {"layout": layout, "motif": occ.get("motif") or "sparkle", "tone": occ.get("tone") or "festive",
            "name": name or "", "number": occ.get("number"), "flag": list(flag), "religious": religious,
            "date": date_text(day, lang, religious) if day and occ.get("kind") != "weekly" else
            (date_text(day, lang, True) if day else "")}


CSS = """
.oc { position: absolute; inset: 0; overflow: hidden; }
.oc-photo { position: absolute; inset: 0; background-size: cover; background-position: center; }
.oc.memorial .oc-photo { filter: grayscale(1) contrast(1.05); }
.oc-motif { display: block; color: var(--gold); filter: drop-shadow(0 6px 18px rgba(0,0,0,.25)); }
.oc-kicker { color: var(--gold-light); font-weight: 800; font-size: 34px; letter-spacing: .5px; line-height: 1.5; }
.lang-en .oc-kicker, .lang-fr .oc-kicker, .lang-ms .oc-kicker { text-transform: uppercase; letter-spacing: 4px; font-size: 28px; }
.oc-text { font-size: 112px; }
.oc-text h1 { font-size: 1em; line-height: 1.2; font-weight: 900; color: #fff; text-shadow: 0 4px 24px rgba(0,0,0,.28); }
.oc-text h1 em { font-style: normal; color: var(--gold-light); }
.oc-text p { font-size: .34em; line-height: 1.6; font-weight: 600; color: rgba(255,255,255,.92); margin-top: .7em; }
.oc-date { font-size: 30px; font-weight: 700; color: rgba(255,255,255,.88); display: inline-flex; gap: 14px; align-items: center; }
.oc-date::before, .oc-date::after { content: ""; width: 46px; height: 3px; border-radius: 3px; background: var(--gold); opacity: .8; }
.oc-num { font-weight: 900; color: var(--gold); line-height: 1; letter-spacing: -2px; direction: ltr; unicode-bidi: isolate; }
.oc-foot { font-size: 28px; font-weight: 700; color: var(--gold-light); direction: ltr; unicode-bidi: isolate; }
.oc-flag { position: absolute; left: 0; right: 0; bottom: 0; height: 16px; display: flex; }
.oc-flag i { flex: 1; display: block; }
.oc .logo img { height: 96px; }

/* frame */
.oc-frame .oc-shade { position: absolute; inset: 0;
  background: radial-gradient(ellipse 80% 70% at 50% 50%, rgba(var(--navy-rgb),.62), rgba(var(--navy-rgb),.80) 70%, rgba(var(--navy-rgb),.92)); }
.oc-frame .oc-border { position: absolute; inset: 44px; border: 3px solid var(--gold); border-radius: 26px; }
.oc-frame .oc-border::after { content: ""; position: absolute; inset: 14px; border: 1.5px solid rgba(255,255,255,.35); border-radius: 18px; }
.oc-frame .oc-corner { position: absolute; width: 34px; height: 34px; background: var(--gold); transform: rotate(45deg); }
.oc-frame .c1 { top: 27px; left: 27px; } .oc-frame .c2 { top: 27px; right: 27px; }
.oc-frame .c3 { bottom: 27px; left: 27px; } .oc-frame .c4 { bottom: 27px; right: 27px; }
.oc-frame .oc-body { position: absolute; inset: 220px 116px 150px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center; gap: 34px; }
.oc-frame .oc-motif { width: 150px; height: 150px; }
.oc-frame .oc-num { font-size: 150px; }
.oc-frame .oc-logo { position: absolute; top: 96px; left: 0; right: 0; display: flex; justify-content: center; }
.oc-frame .oc-foot { position: absolute; bottom: 92px; left: 0; right: 0; text-align: center; }

/* arch */
.oc-arch .oc-photo { bottom: 560px; }
.oc-arch .oc-top { position: absolute; top: 0; left: 0; right: 0; height: 260px;
  background: linear-gradient(180deg, rgba(0,0,0,.42), rgba(0,0,0,0)); }
.oc-arch .oc-logo { position: absolute; top: 56px; left: 64px; right: 64px; display: flex; flex-direction: var(--oc-dir); }
.oc-arch .oc-panel { position: absolute; left: 0; right: 0; bottom: 0; height: 800px; background: var(--navy);
  border-top-left-radius: 540px 230px; border-top-right-radius: 540px 230px;
  box-shadow: 0 -18px 50px rgba(0,0,0,.25); }
.oc-arch .oc-panel::before { content: ""; position: absolute; inset: 22px 22px auto; height: 400px;
  border-top: 3px solid var(--gold); border-top-left-radius: 520px 214px; border-top-right-radius: 520px 214px; opacity: .85; }
.oc-arch .oc-badge { position: absolute; left: 50%; top: 0; transform: translate(-50%, -50%); width: 190px; height: 190px;
  border-radius: 50%; background: var(--gold); display: grid; place-items: center; box-shadow: 0 14px 34px rgba(0,0,0,.3);
  border: 8px solid var(--navy); }
.oc-arch .oc-badge .oc-motif { width: 104px; height: 104px; color: var(--navy); filter: none; }
.oc-arch .oc-badge .oc-num { color: var(--navy); font-size: 78px; }
.oc-arch .oc-body { position: absolute; left: 90px; right: 90px; top: 150px; bottom: 120px; display: flex;
  flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 26px; }
.oc-arch .oc-text { font-size: 104px; }
.oc-arch .oc-foot { position: absolute; bottom: 56px; left: 0; right: 0; text-align: center; }

/* pattern */
.oc-pattern { background: var(--navy); }
.oc-pattern .oc-bgpat { position: absolute; inset: 0; opacity: .16; color: var(--gold); }
.oc-pattern .oc-glow { position: absolute; inset: 0;
  background: radial-gradient(circle at 50% 46%, rgba(255,255,255,.10), rgba(255,255,255,0) 55%); }
.oc-pattern .oc-water { position: absolute; left: 0; right: 0; top: 50%; transform: translateY(-54%); text-align: center;
  font-size: 560px; font-weight: 900; line-height: 1; color: transparent; -webkit-text-stroke: 5px var(--gold);
  opacity: .30; direction: ltr; letter-spacing: -10px; }
.oc-pattern .oc-water .oc-motif { width: 640px; height: 640px; margin: 0 auto; filter: none; opacity: .6; }
.oc-pattern .oc-logo { position: absolute; top: 80px; left: 0; right: 0; display: flex; justify-content: center; }
.oc-pattern .oc-body { position: absolute; inset: 250px 100px 170px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center; gap: 30px; }
.oc-pattern .oc-motif.small { width: 120px; height: 120px; }
.oc-pattern .oc-pill { background: var(--gold); color: var(--navy); font-weight: 900; font-size: 40px; padding: 8px 34px;
  border-radius: 999px; direction: ltr; }
.oc-pattern .oc-foot { position: absolute; bottom: 70px; left: 0; right: 0; text-align: center; }
"""


def _pattern_svg(kind: str, flag: list[str]) -> str:
    if flag:                                  # the flag's colours as soft diagonal bands
        bands = "".join(f'<rect x="{i * 150}" y="-300" width="34" height="2000" fill="{c}"/>'
                        for i, c in enumerate((flag * 12)[:12]))
        return (f'<svg class="oc-bgpat" style="opacity:.12" viewBox="0 0 1080 1350" preserveAspectRatio="none">'
                f'<g transform="rotate(-20 540 675)">{bands}</g></svg>')
    if kind == "stars":                       # eight-point stars (Islamic geometry)
        star = ('<path d="M60 20l12 28 28 12-28 12-12 28-12-28-28-12 28-12z" fill="none" stroke="currentColor" '
                'stroke-width="3"/><rect x="38" y="38" width="44" height="44" transform="rotate(45 60 60)" fill="none" '
                'stroke="currentColor" stroke-width="3"/>')
        return ('<svg class="oc-bgpat" viewBox="0 0 1080 1350"><defs><pattern id="st" width="120" height="120" '
                f'patternUnits="userSpaceOnUse">{star}</pattern></defs><rect width="1080" height="1350" fill="url(#st)"/></svg>')
    dots = ('<circle cx="20" cy="20" r="6" fill="currentColor"/><rect x="80" y="60" width="16" height="6" rx="3" '
            'transform="rotate(30 88 63)" fill="currentColor"/><circle cx="110" cy="120" r="4" fill="currentColor"/>'
            '<rect x="30" y="110" width="14" height="6" rx="3" transform="rotate(-40 37 113)" fill="currentColor"/>')
    return ('<svg class="oc-bgpat" viewBox="0 0 1080 1350"><defs><pattern id="cf" width="150" height="150" '
            f'patternUnits="userSpaceOnUse">{dots}</pattern></defs><rect width="1080" height="1350" fill="url(#cf)"/></svg>')


def _highlight(text: str, words: list[str] | None) -> str:
    out = _e(text)
    for w in words or []:
        if w and _e(w) in out:
            out = out.replace(_e(w), f"<em>{_e(w)}</em>", 1)
    return out


def build(spec, brand, lang: str, logo_html: str, logo_start: bool) -> tuple[str, str]:  # noqa: ANN001
    """(html, css) of an occasion greeting slide."""
    occ = spec.occasion or {}
    layout = occ.get("layout") or "frame"
    tone = occ.get("tone") or "festive"
    number = occ.get("number")
    flag = [c for c in occ.get("flag") or [] if isinstance(c, str) and c.startswith("#")]
    title = _highlight(spec.heading, spec.highlight)
    sub = f"<p>{_e(spec.body)}</p>" if spec.body else ""
    kicker = f'<div class="oc-kicker">{_e(occ.get("name"))}</div>' if occ.get("name") and occ.get("name") != spec.heading else ""
    when = f'<div class="oc-date">{_e(occ.get("date"))}</div>' if occ.get("date") else ""
    foot_text = brand.handle or brand.website or ""
    foot = f'<div class="oc-foot">{_e(foot_text)}</div>' if foot_text else ""
    # the flag's colours as a decorative band along the bottom edge
    stripes = ('<div class="oc-flag">' + "".join(f'<i style="background:{c}"></i>' for c in (flag * 12)[:12]) + "</div>"
               ) if flag else ""
    photo = f'<div class="oc-photo" style="background-image:url({_uri(spec.background)})"></div>' if spec.background else ""
    css = CSS + f"\n:root {{ --oc-dir: {'row' if logo_start else 'row-reverse'}; }}"
    text = f'<div class="oc-text" data-fit="{{fit}}"><h1>{title}</h1>{sub}</div>'
    cls = f"oc oc-{layout} {tone}"

    if layout == "arch":
        badge = (f'<div class="oc-badge"><span class="oc-num">{number}</span></div>' if number
                 else f'<div class="oc-badge">{_svg(occ.get("motif", "sparkle"))}</div>')
        return (f'<div class="{cls}">{photo}<div class="oc-top"></div><div class="oc-logo">{logo_html}</div>'
                f'<div class="oc-panel">{badge}<div class="oc-body">{kicker}{text.replace("{fit}", "440,52")}'
                f'{when}</div>{foot}</div>{stripes}</div>', css)

    if layout == "pattern":
        pat = _pattern_svg("stars" if occ.get("religious") or tone == "spiritual" else "confetti", flag)
        water = (f'<div class="oc-water">{number}</div>' if number
                 else f'<div class="oc-water">{_svg(occ.get("motif", "sparkle"))}</div>')
        top = f'<div class="oc-pill">{number}</div>' if number else _svg(occ.get("motif", "sparkle"), "oc-motif small")
        return (f'<div class="{cls}">{pat}<div class="oc-glow"></div>{water}<div class="oc-logo">{logo_html}</div>'
                f'<div class="oc-body">{top}{kicker}{text.replace("{fit}", "560,52")}{when}</div>{foot}{stripes}</div>',
                css)

    # frame
    top = (f'<div class="oc-num">{number}</div>' if number else _svg(occ.get("motif", "sparkle")))
    return (f'<div class="{cls}">{photo}<div class="oc-shade"></div><div class="oc-border"></div>'
            '<i class="oc-corner c1"></i><i class="oc-corner c2"></i><i class="oc-corner c3"></i><i class="oc-corner c4"></i>'
            f'<div class="oc-logo">{logo_html}</div>'
            f'<div class="oc-body">{top}{kicker}{text.replace("{fit}", "520,52")}{when}</div>{foot}{stripes}</div>', css)
