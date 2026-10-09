"""Photo-album posts: the company's own photos (an event, a visit, a place) are the content.

Slides follow the common international carousel pattern:
  1. a designed opening slide (the best photo, the album title, a small film strip of what is inside),
  2. photo slides that show only the photo — no text, no logo, nothing on top of it,
  3. a designed closing slide (a collage of the album, the logo and a closing line).
A photo whose shape differs from the 4:5 post is never cut badly: it is shown whole on a blurred,
darkened copy of itself (the "fit with blurred backdrop" layout used by Instagram editors).
"""
from __future__ import annotations

import base64
import html
import io

from PIL import Image

MAX_PHOTOS = 10            # Instagram: 10 slides per carousel → opening + 8 photos + closing
LABEL = {"ar": "ألبوم صور", "en": "Photo album", "ms": "Album foto", "fr": "Album photo"}
PHOTOS = {"ar": "صور", "en": "photos", "ms": "foto", "fr": "photos"}
SWIPE = {"ar": "اسحب لمشاهدة الصور", "en": "Swipe to see more", "ms": "Leret untuk lihat lagi", "fr": "Glissez pour voir"}
CAMERA = ('<svg viewBox="0 0 24 24" width="30" height="30" fill="currentColor"><path d="M9 3 7.2 5H4a2 2 0 0 0-2 2v11a2 2 0 0 0 '
          '2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3.2L15 3zm3 5a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"/></svg>')


def count_label(n: int, lang: str) -> str:
    if lang == "ar":     # Arabic number agreement
        return "صورتان" if n == 2 else (f"{n} صور" if 3 <= n <= 10 else f"{n} صورة")
    return f"{n} {PHOTOS.get(lang, PHOTOS['en'])}"


def _uri(data: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"


def _e(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")


def thumb(data: bytes, size: int = 640) -> bytes:
    """A small copy for film strips and collages (keeps the page light)."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((size, size))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=82)
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return data


def aspect(data: bytes | None) -> float:
    try:
        w, h = Image.open(io.BytesIO(data)).size
        return w / h if h else 0.8
    except Exception:  # noqa: BLE001
        return 0.8


def _highlight(text: str, words: list[str] | None) -> str:
    out = _e(text)
    for w in words or []:
        if w and _e(w) in out:
            out = out.replace(_e(w), f"<em>{_e(w)}</em>", 1)
    return out


CSS = """
.al-bg { position: absolute; inset: 0; background-size: cover; background-position: center; }
.al-blur { position: absolute; inset: -60px; background-size: cover; background-position: center;
  filter: blur(46px) brightness(.55) saturate(1.15); }
.al-fit { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
.al-fit img { max-width: 100%; max-height: 100%; display: block; box-shadow: 0 30px 80px rgba(0,0,0,.45); }
.al-fit.wide img { width: 100%; height: auto; }
.al-fit.tall img { height: 100%; width: auto; }

/* opening slide */
.al-top { position: absolute; top: 0; left: 0; right: 0; height: 300px;
  background: linear-gradient(180deg, rgba(0,0,0,.45), rgba(0,0,0,0)); }
.al-shade { position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0) 38%, rgba(var(--navy-rgb),.35) 55%, rgba(var(--navy-rgb),.94) 100%); }
.al-head { position: absolute; top: 56px; left: 64px; right: 64px; display: flex; align-items: center;
  justify-content: space-between; flex-direction: var(--al-dir); }
.al-count { display: inline-flex; align-items: center; gap: 12px; background: rgba(255,255,255,.16);
  border: 2px solid rgba(255,255,255,.45); backdrop-filter: blur(10px); color: #fff; font-weight: 800;
  font-size: 30px; padding: 10px 26px; border-radius: 999px; }
.al-body { position: absolute; left: 72px; right: 72px; bottom: 84px; display: flex; flex-direction: column; gap: 26px; }
.al-kicker { display: flex; align-items: center; gap: 18px; color: var(--gold); font-weight: 900; font-size: 32px;
  letter-spacing: 1px; }
.al-kicker i { display: block; width: 70px; height: 6px; border-radius: 6px; background: var(--gold); }
.lang-en .al-kicker, .lang-fr .al-kicker, .lang-ms .al-kicker { text-transform: uppercase; letter-spacing: 5px; font-size: 28px; }
.al-title h1 { font-size: 84px; line-height: 1.18; font-weight: 900; color: #fff; text-shadow: 0 4px 22px rgba(0,0,0,.35); }
.al-title h1 em { font-style: normal; color: var(--gold); }
.al-title p { margin-top: 16px; font-size: 36px; line-height: 1.5; color: rgba(255,255,255,.92); font-weight: 500; }
.al-strip { display: flex; align-items: center; gap: 16px; margin-top: 8px; }
.al-strip .t { width: 128px; height: 128px; border-radius: 20px; background-size: cover; background-position: center;
  border: 4px solid rgba(255,255,255,.9); box-shadow: 0 10px 26px rgba(0,0,0,.35); flex: none; }
.al-strip .more { width: 128px; height: 128px; border-radius: 20px; display: grid; place-items: center; flex: none;
  background: var(--gold); color: var(--navy); font-weight: 900; font-size: 40px; }
.al-swipe { margin-inline-start: auto; color: rgba(255,255,255,.85); font-size: 26px; font-weight: 700;
  display: inline-flex; align-items: center; gap: 10px; }
.al-swipe b { font-size: 34px; color: var(--gold); }

/* closing slide */
.al-collage { position: absolute; inset: 0; display: grid; gap: 8px; background: var(--navy); }
.al-collage.n1 { grid-template: 1fr / 1fr; }
.al-collage.n2 { grid-template: 1fr 1fr / 1fr; }
.al-collage.n3 { grid-template: 1fr 1fr / 1.4fr 1fr; }
.al-collage.n3 div:first-child { grid-row: span 2; }
.al-collage.n4 { grid-template: 1fr 1fr / 1fr 1fr; }
.al-collage div { background-size: cover; background-position: center; }
.al-veil { position: absolute; inset: 0;
  background: radial-gradient(ellipse at center, rgba(var(--navy-rgb),.86) 0%, rgba(var(--navy-rgb),.72) 55%, rgba(var(--navy-rgb),.55) 100%); }
.al-end { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 0 110px; gap: 34px; }
.al-end .logo img { height: 170px; max-width: 640px; object-fit: contain; }
.al-end .rule { width: 120px; height: 6px; border-radius: 6px; background: var(--gold); }
.al-end h1 { font-size: 72px; line-height: 1.25; font-weight: 900; color: #fff; }
.al-end p { font-size: 36px; line-height: 1.55; color: rgba(255,255,255,.9); }
.al-links { display: flex; flex-wrap: wrap; justify-content: center; gap: 18px; margin-top: 6px; }
.al-links span { border: 2px solid var(--gold); color: #fff; border-radius: 999px; padding: 12px 34px; font-size: 30px;
  font-weight: 700; direction: ltr; }
.al-links span.solid { background: var(--gold); color: var(--navy); }
"""


def build(spec, brand, lang: str, logo_html: str, logo_start: bool) -> tuple[str, str]:  # noqa: ANN001
    """(html, css) of an album slide."""
    album = spec.album or {}
    photo = spec.background
    if spec.kind == "photo":
        if not photo:
            return "", CSS
        ratio = aspect(photo)
        if 0.72 <= ratio <= 0.9:                       # already a 4:5-ish portrait: fill the slide
            return f'<div class="al-bg" style="background-image:url({_uri(photo)})"></div>', CSS
        cls = "wide" if ratio > 0.8 else "tall"
        return (f'<div class="al-blur" style="background-image:url({_uri(thumb(photo, 480))})"></div>'
                f'<div class="al-fit {cls}"><img src="{_uri(photo)}" alt=""></div>', CSS)

    gallery = [g for g in album.get("gallery") or [] if g]
    count = int(album.get("count") or 0)
    direction = "row" if logo_start else "row-reverse"
    css = CSS + f"\n:root {{ --al-dir: {direction}; }}"

    if spec.kind == "cover":
        bg = f'<div class="al-bg" style="background-image:url({_uri(photo)})"></div>' if photo else ""
        pill = (f'<div class="al-count">{CAMERA}<span>{count_label(count, lang)}</span></div>'
                if count > 1 else "<div></div>")
        strip = ""
        if gallery:
            tiles = "".join(f'<div class="t" style="background-image:url({_uri(g)})"></div>' for g in gallery[:3])
            extra = count - 1 - min(3, len(gallery))
            more = f'<div class="more">+{extra}</div>' if extra > 0 else ""
            arrow = "←" if lang == "ar" else "→"
            strip = (f'<div class="al-strip">{tiles}{more}'
                     f'<span class="al-swipe">{SWIPE.get(lang, SWIPE["en"])} <b>{arrow}</b></span></div>')
        sub = f"<p>{_e(spec.body)}</p>" if spec.body else ""
        return (f'{bg}<div class="al-top"></div><div class="al-shade"></div>'
                f'<div class="al-head">{logo_html}{pill}</div>'
                f'<div class="al-body"><div class="al-kicker"><i></i>{_e(LABEL.get(lang, LABEL["en"]))}</div>'
                f'<div class="al-title" data-fit="470,44"><h1>{_highlight(spec.heading, spec.highlight)}</h1>{sub}</div>'
                f'{strip}</div>', css)

    # closing slide
    tiles = gallery[:4] or ([thumb(photo)] if photo else [])
    collage = (f'<div class="al-collage n{len(tiles)}">'
               + "".join(f'<div style="background-image:url({_uri(t)})"></div>' for t in tiles) + "</div>") if tiles else ""
    links = "".join(f'<span class="{"solid" if i == 0 else ""}">{_e(x)}</span>'
                    for i, x in enumerate([brand.handle, brand.website]) if x)
    body = f"<p>{_e(spec.body)}</p>" if spec.body else ""
    return (f'{collage}<div class="al-veil"></div><div class="al-end">{logo_html}<div class="rule"></div>'
            f'<div data-fit="520,40"><h1>{_e(spec.heading)}</h1>{body}</div>'
            f'{f"<div class=al-links>{links}</div>" if links else ""}</div>', css)
