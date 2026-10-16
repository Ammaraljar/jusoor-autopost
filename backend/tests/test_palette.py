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
        assert pal and pal["variant"] in ("sand", "amber", "midnight")           # warm photo → warm brand set
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


def test_every_variant_stays_inside_the_brand_identity():
    """Only navy and gold families: no pink, no grey, readable text everywhere."""
    import colorsys

    from app.services.palette import brand_variants, contrast, hex_to_rgb

    def hue_sat(hx):
        r, g, b = (c / 255 for c in hex_to_rgb(hx))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        return h * 360, s

    variants = brand_variants()
    assert len({v["variant"] for v in variants}) == 6
    for v in variants:
        for key in ("navy", "cardTitle", "cardText"):
            h, s = hue_sat(v[key])
            assert 205 <= h <= 245 and s >= 0.25, (v["variant"], key, v[key])      # navy family, not grey
        for key in ("gold", "goldLight", "cardHeading"):
            h, s = hue_sat(v[key])
            assert 32 <= h <= 52 and s >= 0.3, (v["variant"], key, v[key])        # gold family
        assert contrast(v["gold"], v["navy"]) >= 4.5
        assert contrast(v["cardText"], v["cardBgHex"]) >= 7
        assert contrast(v["cardHeading"], v["cardBgHex"]) >= 4.5


def test_consecutive_posts_get_different_brand_sets():
    from app.services.palette import pick_variant
    recent: list[str] = []
    for i in range(6):
        v = pick_variant(None, recent, seed=i)
        assert v["variant"] not in recent[:2]
        recent.insert(0, v["variant"])
    assert len(set(recent)) >= 4


def test_magazine_cover_highlights_title_words_and_prompts_swipe():
    from app.services.renderer import BrandStyle, SlideSpec, build_html
    brand = BrandStyle(name="JUSOOR Travel", handle="@jusoortravel", theme="magazine", family="travel")
    html = build_html(SlideSpec(kind="cover", heading="٥ أسرار في لنكاوي", body="دليلك", position=0, total=6,
                                highlight=["٥ أسرار"]), brand)
    assert "<mark>٥ أسرار</mark>" in html and "اسحب" in html and "theme-photo" in html and "fam-travel" in html


def test_photo_first_cards_have_one_logo_and_no_boxes_over_the_photo():
    """Every field family, every design, every slide kind: a single logo and the photo uncovered."""
    from app.services import palette
    from app.services.renderer import BrandStyle, SlideSpec, build_html
    for family in palette.FAMILIES:
        for i in range(palette.DESIGN_COUNT):
            pal = palette.design(i, seed=3, family=family)
            for lang in ("ar", "en", "ms", "fr"):
                brand = BrandStyle(name="Acme Co", handle="@acme", theme="magazine", family=family,
                                   palette=pal, language=lang)
                for kind in ("cover", "content", "cta"):
                    html = build_html(SlideSpec(kind=kind, heading="h", body="b", position=1, total=6,
                                                badge="news"), brand)
                    body = html.split("<body", 1)[1]
                    assert body.count('class="logo') == 1, (family, i, kind)
                    for old in ("L2-", "C-stamp", "postmark", "m-panel", "card frosted"):
                        assert old not in body, (family, kind, old)


def test_brand_colour_roles_follow_main_colours_and_exact_mode():
    from app.services import palette as P
    c = P.complete_colors({"navy": "#0B3D2E", "gold": "#B8963E"})
    assert c["cardTitle"] == "#0b3d2e" and c["surface"] != "#fbf8f0" and c["goldLight"]
    assert P.contrast(c["cardText"], c["surface"]) >= 7
    # change the main colour: roles that followed it move; a role set by hand stays
    prev = {**c, "cardText": "#222222"}
    new = P.complete_colors({**prev, "navy": "#5A1E1E"}, prev)
    assert new["cardTitle"] == "#5a1e1e" and new["cardText"] == "#222222"
    # brand mode: the identity's colours exactly, and the template still rotates
    a = P.design(0, family="government", exact=new)
    b = P.design(1, family="government", exact=new)
    assert a["navy"] == "#5a1e1e" and a["cardBgHex"] == new["surface"]
    # the accent keeps its hue but is never dusty (posts must not look washed out)
    h0, _l0, _s0 = P._hls_of("#b8963e")
    h1, _l1, s1 = P._hls_of(a["gold"])
    assert abs(h0 - h1) < 0.02 and s1 >= 0.6
    assert a["template"] != b["template"]


def test_every_field_has_forty_distinct_designs_of_its_own():
    from app.services import cards, signature
    from app.services import palette as p
    for fam in p.FAMILIES:
        designs = p.family_templates(fam)
        assert len(designs) >= 40 and len(set(designs)) == len(designs), fam
        assert not any("~" in t for t in designs), fam               # no near-copies (template + finish)
        assert sum(1 for t in designs if t in signature.LAYOUTS) >= 22, fam
        assert designs[0] in signature.FIELD_FIRST[fam]                 # the field's own signature first
        for t in designs:
            assert t in cards.TEMPLATE_SPEC or t in signature.LAYOUTS, (fam, t)
            assert t in p.TEMPLATES
    assert p.family_templates("travel")[:4] != p.family_templates("food")[:4]        # field-specific
    assert "menu_board" in p.family_templates("food") and "menu_board" not in p.family_templates("tech")
    opts = cards.template_options("food", ["menu_board"])
    assert len(opts) >= 40 and {o["group"] for o in opts} == {"signature", "classic"}
    assert [o["id"] for o in opts if o["enabled"]] == ["menu_board"]
    # only the kept designs rotate
    assert {p.design(i, family="food", enabled=["menu_board", "menu"])["template"] for i in range(6)} == {"menu_board", "menu"}
    # an older choice of template~finish still renders (it is no longer offered)
    assert "glass~glow" in p.TEMPLATES or any("~" in t for t in p.TEMPLATES)


def test_signature_designs_render_every_kind_with_one_logo():
    from app.services import palette as p, signature
    from app.services.renderer import BrandStyle, SlideSpec, build_html
    for t in signature.LAYOUTS:
        brand = BrandStyle(name="J T", colors={"navy": "#252531", "gold": "#D6BE66"}, language="ar", family="travel")
        brand.palette = p.design(0, "#252531", "#D6BE66", 0, "travel", None, t)
        for kind in ("cover", "content", "cta"):
            html = build_html(SlideSpec(kind=kind, heading="عنوان", body="نص", position=1, total=5,
                                        background=p.sample_background("content"), badge="guide"), brand)
            body = html.split("<body", 1)[1]
            assert f"sg-L-{t}" in body and body.count('class="logo') == 1, (t, kind)
    # vivid colours: a dusty gold accent becomes a rich one
    c = signature.colours({"navy": "#252531", "gold": "#D6BE66", "source": "design"}, "travel", 0, False)
    import colorsys
    r, g, b = signature._rgb(c["acc"])
    assert colorsys.rgb_to_hls(r, g, b)[2] >= 0.66 and c["pop"] in signature.FIELD_POPS["travel"]


def test_a_finish_is_drawn_on_the_slide():
    from app.services import palette as p
    from app.services.renderer import BrandStyle, SlideSpec, build_html
    brand = BrandStyle(name="J T", colors={"navy": "#16244F", "gold": "#C6A23C"}, language="ar", family="travel")
    brand.palette = p.design(0, "#16244F", "#C6A23C", 0, "travel", None, "navy~pattern")
    html = build_html(SlideSpec(kind="cover", heading="عنوان", body="سطر", position=0, total=3,
                                background=p.sample_background("content")), brand)
    assert "tpl-navy" in html and "with-pattern" in html and 'class="fx-pattern"' in html
    assert p.choose_logo([("light", b"L"), ("dark", b"D")], b"L", None, "top-left", "cover", "topbar~mono") == (b"L", False)
