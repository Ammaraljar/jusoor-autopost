"""Fonts a brand can choose for its slides: Arabic fonts and fonts for English, Malay and French.
Files live in app/render/fonts/<id>/<subset>-<weight>.woff2 (Cairo stays in app/render/fonts)."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "render" / "fonts"
ARABIC = {
    "Cairo": "Cairo", "Tajawal": "tajawal", "Almarai": "almarai", "IBM Plex Sans Arabic": "ibm-plex-sans-arabic",
    "Noto Kufi Arabic": "noto-kufi-arabic", "Readex Pro": "readex-pro", "El Messiri": "el-messiri",
}
LATIN = {
    "Cairo": "Cairo", "Poppins": "poppins", "Montserrat": "montserrat", "Playfair Display": "playfair-display",
    "DM Sans": "dm-sans", "Raleway": "raleway", "Inter": "inter",
}
RANGES = {
    "arabic": "U+0600-06FF, U+0750-077F, U+0870-08FF, U+FB50-FDFF, U+FE70-FEFF, U+200C-200E",
    "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, "
             "U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
    "latin-ext": "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+1E00-1EFF, "
                 "U+20A0-20C0, U+2C60-2C7F, U+A720-A7FF",
}


def options() -> dict[str, list[str]]:
    return {"arabic": list(ARABIC), "latin": list(LATIN)}


def valid_arabic(name: str | None) -> str:
    return name if name in ARABIC else "Cairo"


def valid_latin(name: str | None) -> str:
    return name if name in LATIN else "Cairo"


@lru_cache(maxsize=64)
def faces(*names: str) -> str:
    """@font-face rules for the chosen fonts (Cairo is always built in by the renderer)."""
    out = []
    for name in dict.fromkeys(names):
        slug = ARABIC.get(name) or LATIN.get(name)
        if not slug or slug == "Cairo":
            continue
        for file in sorted((DIR / slug).glob("*.woff2")):
            subset, weight = file.stem.rsplit("-", 1)
            b64 = base64.b64encode(file.read_bytes()).decode()
            out.append(f"@font-face {{ font-family: '{name}'; font-weight: {weight}; font-style: normal; "
                       f"src: url(data:font/woff2;base64,{b64}) format('woff2'); unicode-range: {RANGES[subset]}; }}")
    return "\n".join(out)


def stack(arabic: str, latin: str, lang: str) -> str:
    first, second = (arabic, latin) if lang == "ar" else (latin, arabic)
    return ", ".join(f"'{n}'" for n in dict.fromkeys([first, second, "Cairo"])) + ", sans-serif"
