"""Photo-album posts: designed opening and closing, photo-only slides in between."""
import io

from PIL import Image

from app.db import Draft, MediaAsset, session_scope
from app.services import album, industries, palette
from app.services.renderer import BrandStyle, SlideSpec, build_html


def _jpeg(w, h, colour):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, "JPEG")
    return buf.getvalue()


def test_new_fields_have_profiles_designs_and_sources():
    for key, family in (("government", "government"), ("car_rental", "rental")):
        p = industries.get(key)
        assert p["ar"] and p["en"] and p["ms"] and p["fr"] and p["design"] == family
        assert len(palette.family_templates(family)) >= 20
        assert any(t["id"] == "own_site" for t in industries.source_types(key))
    assert industries.get("health")["ar"] == "المستشفيات والعيادات"
    assert "تصفيف الشعر" in industries.get("beauty")["ar"]


def test_album_slides_html():
    brand = BrandStyle(name="Jusoor", language="ar", theme="magazine", family="travel")
    wide = _jpeg(1600, 900, (200, 50, 50))
    photo = build_html(SlideSpec(kind="photo", heading="", body="", position=1, total=4, background=wide, album={}), brand)
    assert 'class="al-blur"' in photo and 'class="al-fit wide"' in photo and "<h1" not in photo and 'class="logo' not in photo
    tall = build_html(SlideSpec(kind="photo", heading="", body="", position=1, total=4,
                                background=_jpeg(1080, 1350, (0, 90, 0)), album={}), brand)
    assert 'class="al-bg"' in tall and 'class="al-blur"' not in tall
    cover = build_html(SlideSpec(kind="cover", heading="زيارة لنكاوي", body="أكتوبر", position=0, total=4,
                                 background=wide, album={"count": 12, "gallery": [album.thumb(wide)] * 3}), brand)
    assert "12 صورة" in cover and "ألبوم صور" in cover and "+8" in cover
    end = build_html(SlideSpec(kind="cta", heading="شكرًا", body="", position=3, total=4, background=wide,
                               album={"count": 3, "gallery": [album.thumb(wide)] * 3}), brand)
    assert 'class="al-collage n3"' in end and "شكرًا" in end


def test_album_post_from_uploads_and_library(client):
    with session_scope() as db:
        assert db.query(MediaAsset).count() == 0
        a = MediaAsset(url="https://cdn.test/album/one.jpg", title="Visit")
        db.add(a)
        db.flush()
        mid = a.id
    files = [("files", (f"p{i}.jpg", _jpeg(1200, 900, (i * 40, 80, 120)), "image/jpeg")) for i in range(3)]
    r = client.post("/api/drafts/album", data={"title": "زيارة فريقنا", "text": "زرنا شركاءنا في لنكاوي.",
                                               "media_ids": str(mid)}, files=files)
    assert r.status_code == 200, r.text
    with session_scope() as db:
        d = db.get(Draft, r.json()["draft_id"])
        kinds = [s.kind for s in sorted(d.slides, key=lambda s: s.position)]
        assert d.content_type == "album" and kinds == ["cover", "photo", "photo", "photo", "cta"]
        assert sorted(d.slides, key=lambda s: s.position)[0].background_url == "https://cdn.test/album/one.jpg"
        assert d.hook and d.caption
        assert db.query(MediaAsset).count() >= 4            # uploads were added to the library
        db.delete(d)                                        # leave the shared test database as it was
        for x in db.query(MediaAsset).all():
            db.delete(x)
    assert client.post("/api/drafts/album", data={"title": "x"}).status_code == 400
    too_many = [("files", (f"p{i}.jpg", _jpeg(10, 10, (0, 0, 0)), "image/jpeg")) for i in range(11)]
    assert client.post("/api/drafts/album", data={"title": "x"}, files=too_many).status_code == 400


def test_ultra_hdr_slide_is_a_valid_jpeg_with_gain_map():
    from app.services import hdr
    base = _jpeg(1080, 1350, (200, 180, 120))
    out = hdr.to_ultra_hdr(base)
    assert hdr.is_ultra_hdr(out) and out[:2] == b"\xff\xd8" and b"MPF\x00" in out[:4096]
    assert out.count(b"\xff\xd8") >= 2                      # primary + gain-map images
    assert Image.open(io.BytesIO(out)).size == (1080, 1350)  # ordinary viewers still read it
    assert hdr.to_ultra_hdr(b"not a jpeg") == b"not a jpeg"
