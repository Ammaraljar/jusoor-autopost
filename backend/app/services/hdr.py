"""Ultra HDR slides: the post glows on HDR phone screens and looks normal everywhere else.

An Ultra HDR JPEG (Android 14+, Chrome, recent iPhones) is an ordinary JPEG plus a small grey
"gain map" JPEG appended to it. HDR screens brighten each pixel by the amount the gain map gives,
above the white of the rest of the screen, so the post looks lit from behind; other screens just
show the normal JPEG. Format: Adobe gain-map XMP (hdrgm 1.0) + GContainer XMP + MPF index, as in
https://developer.android.com/media/platform/hdr-image-format — written here in pure Python.
"""
from __future__ import annotations

import io
import math
import struct

from PIL import Image, ImageFilter

BASE_BOOST = 1.45      # the whole slide is lifted a little above the screen's white…
PEAK_BOOST = 2.6       # …and the highlights (light, gold, white) up to this
OFFSET = 1 / 64

_XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"


def _segment(marker: int, payload: bytes) -> bytes:
    return struct.pack(">BBH", 0xFF, marker, len(payload) + 2) + payload


def _primary_xmp(gain_map_length: int) -> bytes:
    xml = ('<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Jusoor AutoPost">'
           '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           '<rdf:Description rdf:about="" xmlns:Container="http://ns.google.com/photos/1.0/container/" '
           'xmlns:Item="http://ns.google.com/photos/1.0/container/item/" '
           'xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" hdrgm:Version="1.0">'
           '<Container:Directory><rdf:Seq>'
           '<rdf:li rdf:parseType="Resource"><Container:Item Item:Semantic="Primary" Item:Mime="image/jpeg"/></rdf:li>'
           f'<rdf:li rdf:parseType="Resource"><Container:Item Item:Semantic="GainMap" Item:Mime="image/jpeg" '
           f'Item:Length="{gain_map_length}"/></rdf:li>'
           '</rdf:Seq></Container:Directory></rdf:Description></rdf:RDF></x:xmpmeta>')
    return _XMP_NS + xml.encode()


def _gain_map_xmp(lo: float, hi: float) -> bytes:
    xml = ('<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Jusoor AutoPost">'
           '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           '<rdf:Description rdf:about="" xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" '
           f'hdrgm:Version="1.0" hdrgm:GainMapMin="{lo:.6f}" hdrgm:GainMapMax="{hi:.6f}" hdrgm:Gamma="1.0" '
           f'hdrgm:OffsetSDR="{OFFSET:.6f}" hdrgm:OffsetHDR="{OFFSET:.6f}" hdrgm:HDRCapacityMin="0.0" '
           f'hdrgm:HDRCapacityMax="{hi:.6f}" hdrgm:BaseRenditionIsHDR="False"/>'
           '</rdf:RDF></x:xmpmeta>')
    return _XMP_NS + xml.encode()


def _mpf(primary_size: int, gain_map_size: int, gain_map_offset: int) -> bytes:
    """Multi-Picture Format index (CIPA DC-007): where the gain map starts in the file."""
    entries_offset = 8 + 2 + 3 * 12 + 4                 # TIFF header + IFD (3 tags) + next-IFD
    ifd = struct.pack(">H", 3)
    ifd += struct.pack(">HHI4s", 0xB000, 7, 4, b"0100")                 # MPF version
    ifd += struct.pack(">HHII", 0xB001, 4, 1, 2)                        # number of images
    ifd += struct.pack(">HHII", 0xB002, 7, 32, entries_offset)          # MP entries
    ifd += struct.pack(">I", 0)
    entries = struct.pack(">IIIHH", 0x20030000, primary_size, 0, 0, 0)  # primary (representative)
    entries += struct.pack(">IIIHH", 0x00000000, gain_map_size, gain_map_offset, 0, 0)
    return b"MPF\x00" + b"MM\x00\x2A" + struct.pack(">I", 8) + ifd + entries


def _gain_map(img: Image.Image) -> tuple[bytes, float, float]:
    """A quarter-size grey map: 0 = base lift, 255 = full highlight lift."""
    small = img.convert("L").resize((max(1, img.width // 4), max(1, img.height // 4)), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(1.2))          # soft edges, no halos around text

    def level(v: int) -> int:
        x = v / 255
        t = min(1.0, max(0.0, (x - 0.45) / 0.5))                 # highlights from mid-light upwards
        return round(255 * t * t * (3 - 2 * t))
    gain = small.point([level(v) for v in range(256)])
    out = io.BytesIO()
    gain.save(out, "JPEG", quality=85)
    return out.getvalue(), math.log2(BASE_BOOST), math.log2(PEAK_BOOST)


def _strip_soi(jpeg: bytes) -> bytes:
    if jpeg[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    return jpeg[2:]


def to_ultra_hdr(jpeg: bytes) -> bytes:
    """Ultra HDR version of a slide JPEG (falls back to the original on any problem)."""
    try:
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        gm_raw, lo, hi = _gain_map(img)
        gain_map = b"\xff\xd8" + _segment(0xE1, _gain_map_xmp(lo, hi)) + _strip_soi(gm_raw)
        body = _strip_soi(jpeg)
        xmp = _segment(0xE1, _primary_xmp(len(gain_map)))
        mpf_len = len(_segment(0xE2, _mpf(0, 0, 0)))
        primary_size = 2 + len(xmp) + mpf_len + len(body)
        # MPF offsets count from the TIFF header inside the MPF segment (after FFE2, length, "MPF\0")
        tiff_start = 2 + len(xmp) + 4 + 4
        mpf = _segment(0xE2, _mpf(primary_size, len(gain_map), primary_size - tiff_start))
        return b"\xff\xd8" + xmp + mpf + body + gain_map
    except Exception:  # noqa: BLE001
        return jpeg


def is_ultra_hdr(data: bytes) -> bool:
    return b"hdrgm:Version" in data[:4096] and b"GainMap" in data[:4096]
