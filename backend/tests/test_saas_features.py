"""Multi-company features: design rotation, logo identity, photo library, layered keys."""
import asyncio
import io

from PIL import Image

from app.db import Draft, MediaAsset, Slide, session_scope, use_org
from app.services import credentials, images, media, palette, pipeline, tenancy


def _png(color, size=(200, 120)):
    out = io.BytesIO()
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(30, 170):
        for y in range(20, 100):
            img.putpixel((x, y), color + (255,))
    img.save(out, "PNG")
    return out.getvalue()


def _jpg(c=(90, 120, 160)):
    out = io.BytesIO()
    Image.new("RGB", (900, 1100), c).save(out, "JPEG")
    return out.getvalue()


# ---------------------------------------------------------------- designs
def test_redesign_cycles_all_designs_before_repeating():
    seen = [palette.design(i, seed=4242) for i in range(palette.DESIGN_COUNT)]
    keys = {(d["variant"], d["layout"], d["cover"]) for d in seen}
    assert len(keys) == palette.DESIGN_COUNT                       # 18 different looks
    for a, b in zip(seen, seen[1:] + seen[:1]):                    # neighbours always differ visibly
        assert a["layout"] != b["layout"] and a["variant"] != b["variant"]
    # after the full cycle it starts again
    assert palette.design(palette.DESIGN_COUNT, seed=4242)["layout"] == seen[0]["layout"]


def test_each_company_gets_its_own_design_order():
    a = [palette.design(i, seed=11)["layout"] for i in range(6)]
    b = [palette.design(i, seed=9876)["layout"] for i in range(6)]
    assert a != b


def test_logo_sets_brand_colours():
    found = palette.colors_from_logo(_png((200, 30, 40)))
    assert found and found["navy"].startswith("#")
    r, g, b = (int(found["navy"][i:i + 2], 16) for i in (1, 3, 5))
    assert r > g and r > b                                          # deep red brand, not the default navy
    assert palette.colors_from_logo(b"not an image") is None


def test_logo_upload_changes_identity(client):
    brand = client.get("/api/brands").json()[0]
    r = client.post(f"/api/brands/{brand['id']}/logo",
                    files={"file": ("logo.png", _png((20, 140, 60)), "image/png")})
    assert r.status_code == 200
    navy = r.json()["colors"]["navy"]
    g = int(navy[3:5], 16)
    assert g >= int(navy[1:3], 16)                                  # green logo → green-led identity
    client.delete(f"/api/brands/{brand['id']}/logo")


# ---------------------------------------------------------------- library
def test_drive_and_dropbox_links_become_downloads():
    assert media.direct_link("https://drive.google.com/file/d/1AbCdEfGhIjKlMn/view?usp=sharing") == \
        "https://drive.google.com/uc?export=download&id=1AbCdEfGhIjKlMn"
    assert media.direct_link("https://drive.google.com/open?id=1AbCdEfGhIjKlMn").endswith("id=1AbCdEfGhIjKlMn")
    assert media.direct_link("https://www.dropbox.com/s/x/p.jpg?dl=0").endswith("dl=1")
    assert media.direct_link("https://example.com/a.jpg") == "https://example.com/a.jpg"


def test_library_upload_tag_pick_and_delete(client):
    r = client.post("/api/media/upload", data={"tags": "coffee, latte #breakfast"},
                    files=[("files", ("a.jpg", _jpg(), "image/jpeg")), ("files", ("b.jpg", _jpg((10, 10, 10)), "image/jpeg"))])
    assert r.status_code == 200, r.text
    added = r.json()["added"]
    assert len(added) == 2 and added[0]["tags"] == "coffee latte breakfast"
    aid = added[0]["id"]
    assert client.patch(f"/api/media/{aid}", json={"tags": "beach sunset"}).json()["tags"] == "beach sunset"
    assert [a["id"] for a in client.get("/api/media?q=sunset").json()] == [aid]
    with session_scope() as db:
        picked = media.pick(db, "a sunset on the beach", 1)
    assert picked[0]["match"] and picked[0]["url"].endswith(".jpg")
    # other companies never see this library
    other = tenancy.create_org
    with session_scope() as db:
        org, _ = other(db, "Other Co", "tech", "en")
        oid = org.id
    assert client.get("/api/media", headers={"X-Org-Id": str(oid)}).json() == []
    assert client.post("/api/media/bulk-delete", json={"ids": [a["id"] for a in added]}).json()["deleted"] == 2
    assert client.get("/api/media").json() == []


def test_library_photo_used_when_sources_have_none(client, monkeypatch):
    monkeypatch.setattr(images, "stock_photos", lambda kw, count, page=1: [])
    lib = client.post("/api/media/upload", data={"tags": "langkawi island"},
                      files=[("files", (f"{i}.jpg", _jpg((i * 40, 80, 120)), "image/jpeg")) for i in range(4)]).json()["added"]
    with session_scope() as db:
        d = Draft(hook="h", caption="c " * 30, status="pending_review", origin="manual", language="ar",
                  image_keywords="langkawi")
        for i, kind in enumerate(["cover", "content", "cta"]):
            d.slides.append(Slide(position=i, kind=kind, heading="ع", body="ن"))
        db.add(d)
        db.flush()
        did = d.id
    try:
        asyncio.run(pipeline.render_draft(did))
        lib_urls = {a["url"] for a in lib}
        with session_scope() as db:
            used = {s.background_url for s in db.get(Draft, did).slides}
        assert used and used <= lib_urls
    finally:
        client.delete(f"/api/drafts/{did}")
        client.post("/api/media/bulk-delete", json={"ids": [a["id"] for a in lib]})


def test_redesign_moves_to_a_new_design(client, monkeypatch):
    monkeypatch.setattr(images, "stock_photos", lambda kw, count, page=1: [])
    with session_scope() as db:
        d = Draft(hook="h", caption="c " * 30, status="pending_review", origin="manual", language="ar")
        for i, kind in enumerate(["cover", "content", "cta"]):
            d.slides.append(Slide(position=i, kind=kind, heading="ع", body="ن"))
        db.add(d)
        db.flush()
        did = d.id
    try:
        asyncio.run(pipeline.render_draft(did))
        designs = []
        for _ in range(3):
            asyncio.run(pipeline.render_draft(did, next_design=True))
            with session_scope() as db:
                designs.append(db.get(Draft, did).palette["design"])
        assert len(set(designs)) == 3
        assert designs[1] == (designs[0] + 1) % palette.DESIGN_COUNT
    finally:
        client.delete(f"/api/drafts/{did}")


# ---------------------------------------------------------------- keys
def test_company_keys_override_platform_and_publish_keys_stay_private():
    with session_scope() as db:
        org, _ = tenancy.create_org(db, "Keys Co", "ecommerce", "en")
        oid = org.id
    with use_org(None), session_scope() as db:
        credentials.save(db, {"mistral_api_key": "platform-mistral", "buffer_api_key": "platform-buffer"},
                         scope="platform")
    try:
        with use_org(oid):
            assert credentials.current()["mistral_api_key"] == "platform-mistral"
            assert credentials.source_of("mistral_api_key") == "platform"
            assert credentials.current()["buffer_api_key"] == ""          # publishing keys are never shared
            with session_scope() as db:
                credentials.save(db, {"mistral_api_key": "own-mistral"})
            assert credentials.current()["mistral_api_key"] == "own-mistral"
            assert credentials.source_of("mistral_api_key") == "dashboard"
    finally:
        with use_org(None), session_scope() as db:
            credentials.save(db, {"mistral_api_key": None, "buffer_api_key": None}, scope="platform")
