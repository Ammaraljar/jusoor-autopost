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


def _rule(family: str) -> str:
    if family == "food":
        return ('<svg class="pf-rule squiggle" viewBox="0 0 200 20" preserveAspectRatio="none">'
                '<path d="M2 12 Q 22 2 42 12 T 82 12 T 122 12 T 162 12 T 198 12"/></svg>')
    if family == "auto":
        return '<div class="pf-rule stripes"><i></i><i></i><i></i></div>'
    return '<div class="pf-rule"></div>'


def build(spec, brand, lang: str, logo_html: str, logo_plate_html: str, bg: str,
          logo_start: bool = True) -> tuple[str, str]:
    """HTML body content and body classes for one slide."""
    pal = brand.palette or {}
    family = pal.get("family") or getattr(brand, "family", None) or "general"
    if family not in _P:
        family = "general"
    layout = pal.get("layout") if pal.get("layout") in ("lower", "edge", "numeral", "chip", "upper", "split") else "lower"
    cover = pal.get("cover") if pal.get("cover") in ("hero", "top", "center", "frame", "label", "poster") else "hero"
    cta = pal.get("cta") if pal.get("cta") in ("center", "bottom") else "center"
    lang = lang if lang in SWIPE else "en"
    classes = f"theme-photo fam-{family} lang-{lang}"
    content_total = max(spec.total - 2, 1)

    if spec.kind == "cta":
        site = f'<div class="pf-site">{_esc(brand.website)}</div>' if brand.website else ""
        acts = "".join(f'<span class="pf-act"><svg viewBox="0 0 24 24">{SAVE_ICONS[k]}</svg>{_esc(v)}</span>'
                       for k, v in zip(("save", "share", "msg"), ACTIONS[lang]))
        button = f'<div class="pf-button">{_esc(brand.handle or brand.name)}</div>'
        body = (f'{bg}<div class="scrim scrim-cta-{cta}"></div>'
                f'<div class="pf-cta pf-cta-{cta}"><div class="pf-cta-logo">{logo_html}</div>'
                f'<h1 data-fit="{"380" if cta == "center" else "300"},40">{_esc(spec.heading)}</h1>'
                f'<p>{_esc(spec.body)}</p>{button}{site}<div class="pf-acts">{acts}</div></div>')
        return body, f"{classes} kind-cta cta-{cta}"

    top = f'<div class="pf-top{"" if logo_start else " logo-end"}">{logo_plate_html}'
    if spec.kind == "content":
        top += f'<span class="pf-count">{spec.position:02d}<small>/{content_total:02d}</small></span>'
    top += "</div>"

    if spec.kind == "cover":
        badge = BADGES[lang].get(spec.badge or "", "") if spec.badge else ""
        kicker_text = badge or FAMILY_KICKER[lang][family]
        kicker = f'<div class="pf-kicker">{_icon(family)}<span>{_esc(kicker_text)}</span></div>'
        credit = f'<span class="pf-credit">{CREDIT[lang]}: {_esc(spec.credit)}</span>' if spec.credit else "<span></span>"
        arrow = "←" if lang == "ar" else "→"
        foot = f'<div class="pf-foot">{credit}<span class="pf-swipe">{SWIPE[lang]} <b>{arrow}</b></span></div>'
        frame = '<div class="pf-frame"><i></i><i></i><i></i><i></i></div>' if cover == "frame" else ""
        fit = {"hero": "560,44", "top": "520,44", "center": "620,44", "frame": "520,44", "label": "560,44",
               "poster": "640,48"}[cover]
        text = (f'<div class="pf-cover pf-cover-{cover}" data-fit="{fit}">{kicker}'
                f'<h1>{_highlight(spec.heading, spec.highlight)}</h1>{_rule(family)}'
                f'<p class="pf-sub">{_esc(spec.body)}</p></div>')
        ticker = '<div class="pf-ticker"></div>' if cover == "label" else ""
        scrim = {"top": "top", "center": "center"}.get(cover, "cover")
        return (f'{bg}<div class="scrim scrim-{scrim}"></div>{frame}{top}{text}{foot}{ticker}',
                f"{classes} kind-cover cover-{cover}")

    # content slide
    progress = min(100, int(100 * spec.position / content_total))
    foot = f'<div class="pf-progress"><i style="width:{progress}%"></i></div>'
    head = f'<h2>{_esc(spec.heading)}</h2>'
    para = f'<p>{_esc(spec.body)}</p>'
    if layout == "split":
        text = (f'<div class="pf-text pf-split-head" data-fit="260,34">{head}{_rule(family)}</div>'
                f'<div class="pf-text pf-split-body" data-fit="330,28">{para}</div>')
        scrim = "both"
    elif layout == "upper":
        text = f'<div class="pf-text pf-upper" data-fit="520,28">{head}{_rule(family)}{para}</div>'
        scrim = "top"
    elif layout == "numeral":
        text = (f'<div class="pf-text pf-numeral" data-fit="560,28"><div class="pf-num">{spec.position:02d}</div>'
                f'{head}{para}</div>')
        scrim = "bottom"
    elif layout == "chip":
        text = (f'<div class="pf-text pf-chip" data-fit="540,28"><div class="pf-chip-head">{head}</div>'
                f'{para}</div>')
        scrim = "bottom"
    elif layout == "edge":
        text = f'<div class="pf-text pf-edge" data-fit="540,28">{head}{para}</div>'
        scrim = "bottom"
    else:
        text = f'<div class="pf-text pf-lower" data-fit="540,28">{head}{_rule(family)}{para}</div>'
        scrim = "bottom"
    return (f'{bg}<div class="scrim scrim-{scrim}"></div>{top}{text}{foot}',
            f"{classes} kind-content layout-{layout}")
