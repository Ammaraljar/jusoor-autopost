"""Colours follow the photo, text stays readable, and a white logo never disappears."""
import io

import pytest
from PIL import Image

from app.services import palette as colours


def photo(rgb, size=(1200, 1500), top=None):
    img = Image.new("RGB", size, rgb)
    if top:
        img.paste(Image.new("RGB", (size[0], size[1] // 5), top), (0, 0))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


@pytest.mark.parametrize("rgb", [(20, 140, 150), (220, 90, 40), (40, 150, 60), (140, 60, 170), (200, 170, 40)])
def test_palette_is_readable_for_any_hue(rgb):
    p = colours.extract_palette(photo(rgb))
    card = p["cardBgHex"]
    assert colours.contrast(p["cardHeading"], card) >= 4.5      # slide headings on the card
    assert colours.contrast(p["cardText"], card) >= 7            # body text on the card
    assert colours.contrast(p["cardTitle"], card) >= 7           # cover title on the card
    assert colours.contrast(p["gold"], p["navy"]) >= 4.5         # badge / button text


def test_different_photos_give_different_colours():
    sea = colours.extract_palette(photo((20, 140, 150)))
    sunset = colours.extract_palette(photo((220, 90, 40)))
    assert sea["gold"] != sunset["gold"] and abs(sea["hue"] - sunset["hue"]) > 90


def test_grey_photo_falls_back_to_brand_colours():
    assert colours.extract_palette(photo((128, 128, 128))) is None
    assert colours.extract_palette(None) is None


def test_logo_plate_only_where_the_photo_is_bright():
    assert colours.logo_needs_plate(photo((30, 40, 60), top=(245, 245, 250))) is True     # white sky
    assert colours.logo_needs_plate(photo((245, 245, 250), top=(15, 25, 45))) is False    # dark night top
    assert colours.logo_needs_plate(None) is False


def test_renderer_uses_palette_and_plate():
    from app.services.renderer import BrandStyle, SlideSpec, build_html
    p = colours.extract_palette(photo((220, 90, 40)))
    style = BrandStyle(name="JUSOOR Travel", colors={"navy": "#16244F"}, palette=p)
    html = build_html(SlideSpec("cover", "عنوان", "نص", 0, 3, logo_plate=True), style)
    assert p["gold"] in html and 'class="logo plate"' in html
    assert "--plate-rgb: 22,36,79" in html          # the plate keeps the brand navy

    html = build_html(SlideSpec("cover", "عنوان", "نص", 0, 3, logo_plate=True),
                      BrandStyle(name="J", logo_backdrop="never"))
    assert 'class="logo plate"' not in html
    html = build_html(SlideSpec("cover", "عنوان", "نص", 0, 3, logo_plate=False),
                      BrandStyle(name="J", logo_backdrop="always"))
    assert 'class="logo plate"' in html


def test_pipeline_stores_one_palette_per_post(client, fake_network, monkeypatch):
    """All slides of a post share the cover's colours; re-rendering one slide keeps them."""
    import asyncio

    from app.db import Draft, session_scope
    from app.services import images, pipeline

    sunset = photo((220, 90, 40))
    monkeypatch.setattr(images, "download_image", lambda url: sunset)
    monkeypatch.setattr(images, "collect_backgrounds", lambda *a, **kw: [
        {"url": "https://img.example/sunset.jpg", "bytes": sunset, "hash": "s1", "credit": ""}])
    created = client.post("/api/drafts/manual", json={"topic": "غروب لنكاوي"}).json()
    assert created["ok"]
    with session_scope() as db:
        d = db.query(Draft).order_by(Draft.id.desc()).first()
        did, pal = d.id, d.palette
    try:
        assert pal and pal.get("hue") is not None and 10 <= pal["hue"] <= 40     # orange
        asyncio.run(pipeline.render_draft(did, [1]))
        with session_scope() as db:
            assert db.get(Draft, did).palette == pal
    finally:
        client.delete(f"/api/drafts/{did}")


def test_brand_colour_mode_and_logo_backdrop_are_saved(client):
    brand = client.get("/api/brands").json()[0]
    assert brand["color_mode"] == "auto" and brand["logo_backdrop"] == "auto"
    r = client.patch(f"/api/brands/{brand['id']}", json={"color_mode": "brand", "logo_backdrop": "always"})
    assert r.json()["color_mode"] == "brand" and r.json()["logo_backdrop"] == "always"
    assert client.patch(f"/api/brands/{brand['id']}", json={"color_mode": "rainbow"}).status_code == 422
    client.patch(f"/api/brands/{brand['id']}", json={"color_mode": "auto", "logo_backdrop": "auto"})
