"""Photo-first carousel cards, one design family per field (industry).

Rules every design follows:
- the photo is the content: full-bleed and sharp on every slide, text sits on a soft shade only
  where it is written — never inside a box or panel that hides the photo;
- exactly one logo per slide: a small one at the top on cover/content slides, a large centred
  one on the last slide (no second logo, wordmark or stamp anywhere);
- colours come only from the brand (main colour + accent).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

RENDER_DIR = Path(__file__).resolve().parent.parent / "render"

FAMILY_OF_INDUSTRY = {
    "travel": "travel", "news": "news", "tech": "tech", "restaurants": "food", "education": "education",
    "training": "training", "nonprofit": "nonprofit", "ecommerce": "retail", "realestate": "luxury",
    "fashion": "fashion", "health": "health", "beauty": "beauty", "automotive": "auto", "events": "events",
    "general": "general",
}

SWIPE = {"ar": "اسحب", "en": "Swipe", "ms": "Leret", "fr": "Glissez"}
CREDIT = {"ar": "المصدر", "en": "Source", "ms": "Sumber", "fr": "Source"}
ACTIONS = {"ar": ("احفظ", "شارك", "راسلنا"), "en": ("Save", "Share", "Message us"),
           "ms": ("Simpan", "Kongsi", "Mesej kami"), "fr": ("Enregistrez", "Partagez", "Écrivez-nous")}
BADGES = {
    "ar": {"news": "خبر", "tips": "نصائح", "guide": "دليل", "offer": "عرض", "event": "فعالية",
           "culture": "ثقافة", "food": "مذاق"},
    "en": {"news": "News", "tips": "Tips", "guide": "Guide", "offer": "Offer", "event": "Event",
           "culture": "Culture", "food": "Food"},
    "ms": {"news": "Berita", "tips": "Tip", "guide": "Panduan", "offer": "Tawaran", "event": "Acara",
           "culture": "Budaya", "food": "Rasa"},
    "fr": {"news": "Actu", "tips": "Conseils", "guide": "Guide", "offer": "Offre", "event": "Événement",
           "culture": "Culture", "food": "Saveurs"},
}
# a word shown in the kicker when the post has no badge, in the family's voice
FAMILY_KICKER = {
    "ar": {"travel": "وجهة", "news": "خبر", "tech": "تقنية", "food": "من مطبخنا", "education": "تعليم",
           "training": "تطوير مهني", "nonprofit": "أثر", "retail": "جديد", "luxury": "عقار مميز",
           "fashion": "مجموعة جديدة", "health": "صحتك", "beauty": "إطلالتك", "auto": "قيادة",
           "events": "فعالية", "general": "جديد"},
    "en": {"travel": "Destination", "news": "News", "tech": "Tech", "food": "From our kitchen", "education": "Learning",
           "training": "Professional growth", "nonprofit": "Impact", "retail": "New in", "luxury": "Featured property",
           "fashion": "New collection", "health": "Your health", "beauty": "Your look", "auto": "Drive",
           "events": "Event", "general": "New"},
    "ms": {"travel": "Destinasi", "news": "Berita", "tech": "Teknologi", "food": "Dari dapur kami",
           "education": "Pembelajaran", "training": "Pembangunan profesional", "nonprofit": "Impak",
           "retail": "Baharu", "luxury": "Hartanah pilihan", "fashion": "Koleksi baharu", "health": "Kesihatan anda",
           "beauty": "Gaya anda", "auto": "Pemanduan", "events": "Acara", "general": "Baharu"},
    "fr": {"travel": "Destination", "news": "Actu", "tech": "Tech", "food": "De notre cuisine",
           "education": "Apprendre", "training": "Développement pro", "nonprofit": "Impact", "retail": "Nouveauté",
           "luxury": "Bien d’exception", "fashion": "Nouvelle collection", "health": "Votre santé",
           "beauty": "Votre beauté", "auto": "Conduite", "events": "Événement", "general": "Nouveau"},
}

_P = {
    "travel": '<path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/>',
    "news": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "tech": '<path d="M8.6 16.6 4 12l4.6-4.6L10 8.8 6.8 12l3.2 3.2zm6.8 0L14 15.2l3.2-3.2L14 8.8l1.4-1.4L20 12z"/>',
    "food": '<path d="M7 2v9a2 2 0 0 1-1 1.7V22H4v-9.3A2 2 0 0 1 3 11V2h1v6h1V2h1v6h1V2zm9 0c2.2 0 4 2.7 4 6 0 2.4-1 4.4-2.5 5.4V22h-2V2z"/>',
    "education": '<path d="M12 3 1 9l11 6 9-4.9V17h2V9zM5 13.2v4L12 21l7-3.8v-4L12 17z"/>',
    "training": '<path d="M12 2a6 6 0 0 0-3.6 10.8L7 22l5-3 5 3-1.4-9.2A6 6 0 0 0 12 2zm0 3a3 3 0 1 1 0 6 3 3 0 0 1 0-6z"/>',
    "nonprofit": '<path d="M12 21s-8-5.3-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.7-8 11-8 11z"/>',
    "retail": '<path d="M3 3h8l10 10-8 8L3 11zm4.5 2.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>',
    "luxury": '<path d="M12 3 2 11h3v10h5v-6h4v6h5V11h3z"/>',
    "fashion": '<path d="M12 2 9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z"/>',
    "health": '<path d="M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z"/>',
    "beauty": '<path d="M12 2 9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z"/>',
    "auto": '<path d="M12 4a10 10 0 0 0-10 10h3a7 7 0 0 1 14 0h3A10 10 0 0 0 12 4zm4.2 3.6L11 13a2 2 0 1 0 2.8 2.8l3.6-7z"/>',
    "events": '<path d="M7 2h2v2h6V2h2v2h3v18H4V4h3zm-1 7v11h12V9z"/>',
    "general": '<path d="M12 2l2.9 6.9L22 9.3l-5.5 4.8L18.2 22 12 18.3 5.8 22l1.7-7.9L2 9.3l7.1-.4z"/>',
}
SAVE_ICONS = {
    "save": '<path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z"/>',
    "share": '<path d="M18 8a3 3 0 1 0-2.8-4L8.9 7.6a3 3 0 1 0 0 4.8l6.3 3.6A3 3 0 1 0 16 14l-6.3-3.6a3 3 0 0 0 0-.8L16 6a3 3 0 0 0 2 2z"/>',
    "msg": '<path d="M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9l-5 4V5a1 1 0 0 1 1-1z"/>',
}


def css() -> str:
    # the file is written with doubled braces like the template; it is inserted as a value here
    return (RENDER_DIR / "photo.css").read_text(encoding="utf-8").replace("{{", "{").replace("}}", "}")


def _esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")


def _icon(family: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{_P.get(family, _P["general"])}</svg>'


def _highlight(text: str, words: list[str] | None) -> str:
    out = _esc(text)
    picks = [w.strip() for w in (words or []) if w and w.strip() and w.strip() in (text or "")]
    if not picks:
        picks = re.findall(r"[0-9٠-٩]+(?:[.,][0-9٠-٩]+)?%?", text or "")[:1]
    for w in sorted(set(picks), key=len, reverse=True)[:2]:
        esc = _esc(w)
        out = out.replace(esc, f"<mark>{esc}</mark>", 1)
    return out


SWIPE_LONG = {"ar": "اسحب للمزيد", "en": "Swipe for more", "ms": "Leret seterusnya", "fr": "Glissez pour voir"}

# template → (text sits on a light card?, footer sits on that card?, badge as a pill at the top?)
TEMPLATE_SPEC: dict[str, tuple[bool, bool, bool]] = {
    "magazine": (False, False, True), "glass": (True, False, True), "navy": (False, False, True),
    "diagonal": (True, True, True), "editorial": (False, False, False), "ribbon": (False, False, True),
    "side": (True, False, True), "band": (True, True, True), "frame": (False, False, False),
    "postcard": (True, True, True), "ticket": (True, False, False), "medallion": (False, False, False),
    "topbar": (False, False, True), "leaf": (True, False, True), "stripe": (False, False, False),
    "centered": (False, False, False), "wave": (False, False, True), "outline": (False, False, True),
    "breaking": (False, False, False), "quote": (False, False, False), "certificate": (False, False, False),
    "menu": (True, False, False), "pricetag": (False, False, False), "blueprint": (False, False, False),
    "polaroid": (False, False, True), "lens": (False, False, True), "sticker": (False, False, False),
    "headline": (False, False, True), "minimal": (False, False, False), "stat": (False, False, False),
    "split": (False, False, True), "gradient": (False, False, False),
}
DECOR = {
    "diagonal": '<div class="dz-diag"><i class="g"></i><i class="p"></i></div>',
    "frame": '<div class="dz-frame"></div>',
    "postcard": '<div class="dz-postcard"></div>',
    "topbar": '<div class="dz-topbar"></div>',
    "certificate": '<div class="dz-cert"><i></i><b class="c1"></b><b class="c2"></b><b class="c3"></b><b class="c4"></b></div>',
    "blueprint": '<div class="dz-grid"></div>',
    "breaking": '<div class="dz-ticker"></div>',
    "gradient": '<div class="dz-edge"></div>',
    "wave": ('<div class="dz-wave"><svg viewBox="0 0 1080 140" preserveAspectRatio="none">'
             '<path d="M0,80 C200,0 380,140 600,70 C800,10 930,100 1080,50 L1080,140 L0,140 Z"/></svg><i></i></div>'),
}


def _rule(family: str) -> str:
    if family == "food":
        return ('<svg class="pf-rule squiggle" viewBox="0 0 200 20" preserveAspectRatio="none">'
                '<path d="M2 12 Q 22 2 42 12 T 82 12 T 122 12 T 162 12 T 198 12"/></svg>')
    if family == "auto":
        return '<div class="pf-rule stripes"><i></i><i></i><i></i></div>'
    return '<div class="pf-rule"></div>'


def _template(pal: dict) -> str:
    t = pal.get("template") or pal.get("layout")
    return t if t in TEMPLATE_SPEC else "magazine"


def build(spec, brand, lang: str, logo_html: str, logo_plate_html: str, bg: str,
          logo_start: bool = True) -> tuple[str, str]:
    """HTML body content and body classes for one slide."""
    pal = brand.palette or {}
    family = pal.get("family") or getattr(brand, "family", None) or "general"
    if family not in _P:
        family = "general"
    tpl = _template(pal)
    light, foot_on_card, use_pill = TEMPLATE_SPEC[tpl]
    cta = pal.get("cta") if pal.get("cta") in ("center", "bottom") else "center"
    lang = lang if lang in SWIPE else "en"
    classes = f"theme-photo tpl-{tpl} fam-{family} lang-{lang}" + (" tx-light" if light else "") \
        + (" foot-card" if foot_on_card else "")
    content_total = max(spec.total - 2, 1)
    handle = f'<span class="pf-handle">{_esc(brand.handle)}</span>' if brand.handle else "<span></span>"

    if spec.kind == "cta":
        site = f'<div class="pf-site">{_esc(brand.website)}</div>' if brand.website else ""
        acts = "".join(f'<span class="pf-act"><svg viewBox="0 0 24 24">{SAVE_ICONS[k]}</svg>{_esc(v)}</span>'
                       for k, v in zip(("save", "share", "msg"), ACTIONS[lang]))
        button = f'<div class="pf-button">{_esc(brand.handle or brand.name)}</div>'
        body = (f'{bg}<div class="scrim scrim-cta-{cta}"></div>'
                f'<div class="pf-cta pf-cta-{cta}"><div class="pf-cta-logo">{logo_html}</div>'
                f'<h1 data-fit="{"380" if cta == "center" else "300"},40">{_esc(spec.heading)}</h1>'
                f'<p>{_esc(spec.body)}</p>{button}{site}<div class="pf-acts">{acts}</div></div>')
        return body, f"theme-photo fam-{family} lang-{lang} kind-cta cta-{cta}"

    badge = BADGES[lang].get(spec.badge or "", "") if spec.badge else ""
    top = f'<div class="pf-top{"" if logo_start else " logo-end"}">{logo_plate_html}'
    if spec.kind == "content":
        top += f'<span class="pf-count">{spec.position:02d}<small>/{content_total:02d}</small></span>'
    elif use_pill and badge:
        top += f'<span class="pf-pill">{_esc(badge)}</span>'
    top += "</div>"
    decor = DECOR.get(tpl, "")
    number = f"{spec.position:02d}"

    if spec.kind == "cover":
        kicker = "" if use_pill else (f'<div class="pf-kicker">{_icon(family)}'
                                      f'<span>{_esc(badge or FAMILY_KICKER[lang][family])}</span></div>')
        head = f'<h1>{_highlight(spec.heading, spec.highlight)}</h1>'
        sub = f'<p class="pf-sub">{_esc(spec.body)}</p>'
        credit = f'<span class="pf-credit">{CREDIT[lang]}: {_esc(spec.credit)}</span>' if spec.credit else ""
        arrow = "←" if lang == "ar" else "→"
        swipe = f'<span class="pf-swipe">{SWIPE_LONG[lang]} <b>{arrow}</b></span>'
        foot = f'<div class="pf-foot">{handle}{credit}{swipe}</div>'
        medal = f'<div class="pf-medal">{_icon(family)}</div>' if tpl == "medallion" else ""
        if tpl == "sticker":
            medal = (f'<div class="pf-sticker">{_icon(family)}'
                     f'<span>{_esc(badge or FAMILY_KICKER[lang][family])}</span></div>')
            kicker = ""
        if tpl == "stat":
            digits = re.findall(r"[0-9٠-٩]+(?:[.,][0-9٠-٩]+)?%?", spec.heading or "")
            if digits:
                medal = f'<div class="pf-stat">{_esc(digits[0])}</div>'
        if tpl == "quote":
            medal = '<div class="pf-quote">“</div>'
        tk = (f'<div class="tk-head">{_icon(family)}<span>{_esc(badge or FAMILY_KICKER[lang][family])}</span>'
              '<b>✈</b></div>') if tpl == "ticket" else ""
        if tpl == "ticket":
            kicker = ""
        text = (f'<div class="tx tx-cover" data-fit="{_fit(tpl, True)}">{tk}{medal}<div class="tx-in">{kicker}'
                f'{head}{_rule(family)}{sub}</div></div>')
        return (f'{bg}<div class="scrim scrim-{tpl}"></div>{decor}{top}{text}{foot}',
                f"{classes} kind-cover")

    # content slide
    dots = "".join(f'<i class="{"on" if i + 1 == spec.position else ""}"></i>' for i in range(content_total))
    foot = f'<div class="pf-foot">{handle}<div class="pf-dots">{dots}</div></div>'
    num = f'<div class="pf-num">{number}</div>'
    tk = (f'<div class="tk-head">{_icon(family)}<span>{_esc(FAMILY_KICKER[lang][family])}</span>'
          f'<b>{number}</b></div>') if tpl == "ticket" else ""
    medal = f'<div class="pf-medal">{number}</div>' if tpl in ("medallion", "sticker") else ""
    if tpl == "stat":
        medal = f'<div class="pf-stat">{number}</div>'
    elif tpl == "quote":
        medal = '<div class="pf-quote">“</div>'
    text = (f'<div class="tx tx-content" data-fit="{_fit(tpl, False)}">{tk}{medal}<div class="tx-in">'
            f'{"" if tpl in ("ticket", "medallion", "sticker", "stat") else num}<h2>{_esc(spec.heading)}</h2>{_rule(family)}'
            f'<p>{_esc(spec.body)}</p></div></div>')
    return (f'{bg}<div class="scrim scrim-{tpl}"></div>{decor}{top}{text}{foot}',
            f"{classes} kind-content")


def _fit(tpl: str, cover: bool) -> str:
    """Max text height (px) and min font size for the auto-fit script."""
    tall = {"topbar": 360, "side": 620, "centered": 640, "band": 600, "diagonal": 420, "postcard": 560,
            "wave": 420, "ticket": 460, "glass": 640, "navy": 640, "leaf": 640, "outline": 640,
            "polaroid": 330, "lens": 300, "split": 400, "menu": 560, "headline": 640, "minimal": 420,
            "stat": 480, "quote": 560, "certificate": 600, "pricetag": 460, "sticker": 520}
    h = tall.get(tpl, 560 if cover else 600)
    return f"{h},{40 if cover else 28}"


TEMPLATE_LABELS: dict[str, tuple[str, str, str, str]] = {
    "magazine": ("مجلة", "Magazine", "Majalah", "Magazine"),
    "glass": ("بطاقة زجاجية", "Glass card", "Kad kaca", "Carte vitrée"),
    "navy": ("بطاقة داكنة", "Dark card", "Kad gelap", "Carte sombre"),
    "diagonal": ("شريط مائل", "Diagonal", "Pepenjuru", "Diagonale"),
    "editorial": ("تحريري", "Editorial", "Editorial", "Éditorial"),
    "ribbon": ("شرائط", "Ribbons", "Reben", "Rubans"),
    "side": ("لوحة جانبية", "Side panel", "Panel sisi", "Panneau latéral"),
    "band": ("شريط عريض", "Wide band", "Jalur lebar", "Bandeau"),
    "frame": ("إطار رفيع", "Thin frame", "Bingkai nipis", "Cadre fin"),
    "postcard": ("بطاقة بريدية", "Postcard", "Poskad", "Carte postale"),
    "ticket": ("بطاقة صعود", "Boarding pass", "Pas masuk", "Carte d’embarquement"),
    "medallion": ("ميدالية", "Medallion", "Medalion", "Médaillon"),
    "topbar": ("شريط علوي", "Top band", "Jalur atas", "Bandeau haut"),
    "leaf": ("ورقة", "Leaf card", "Kad daun", "Carte feuille"),
    "stripe": ("خط جانبي", "Side stripe", "Jalur sisi", "Bande latérale"),
    "centered": ("في الوسط", "Centred", "Di tengah", "Centré"),
    "wave": ("موجة", "Wave", "Ombak", "Vague"),
    "outline": ("إطار مفتوح", "Outline", "Garis luar", "Contour"),
    "breaking": ("عاجل", "Breaking", "Terkini", "Flash info"),
    "quote": ("اقتباس", "Quote", "Petikan", "Citation"),
    "certificate": ("شهادة", "Certificate", "Sijil", "Certificat"),
    "menu": ("قائمة طعام", "Menu card", "Kad menu", "Carte menu"),
    "pricetag": ("بطاقة سعر", "Price tag", "Tanda harga", "Étiquette"),
    "blueprint": ("مخطط", "Blueprint", "Pelan", "Plan"),
    "polaroid": ("صورة فورية", "Polaroid", "Polaroid", "Polaroid"),
    "lens": ("دائرة", "Lens", "Lensa", "Objectif"),
    "sticker": ("ملصق", "Sticker", "Pelekat", "Sticker"),
    "headline": ("عنوان ضخم", "Big headline", "Tajuk besar", "Grand titre"),
    "minimal": ("بسيط", "Minimal", "Minimal", "Minimal"),
    "stat": ("رقم بارز", "Big number", "Nombor besar", "Grand chiffre"),
    "split": ("نصفان", "Split", "Belah", "Partagé"),
    "gradient": ("تدرّج", "Gradient", "Gradien", "Dégradé"),
}


def template_options(family: str, enabled: list[str] | None) -> list[dict]:
    from . import palette
    kept = set(enabled or [])
    return [{"id": t, "ar": TEMPLATE_LABELS[t][0], "en": TEMPLATE_LABELS[t][1], "ms": TEMPLATE_LABELS[t][2],
             "fr": TEMPLATE_LABELS[t][3], "enabled": not kept or t in kept}
            for t in palette.family_templates(family)]
