"""Uploading a photo from the user's computer onto a carousel slide."""
import io
import time

from PIL import Image

from app.db import Draft, Slide, session_scope


def _jpeg(w=900, h=1200, colour=(30, 120, 200)):
    out = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(out, "PNG")
    return out.getvalue()


def test_uploaded_photo_is_used_without_calling_our_own_server(client, monkeypatch):
    from app.services import images
    calls = []
    real_get = images.httpx.get
    monkeypatch.setattr(images.httpx, "get", lambda url, **kw: calls.append(url) or real_get(url, **kw))
    with session_scope() as db:
        d = Draft(hook="h", caption="c " * 30, status="pending_review", origin="manual", language="ar")
        for i, kind in enumerate(["cover", "content", "cta"]):
            d.slides.append(Slide(position=i, kind=kind, heading="ع", body="ن", background_url="https://x.example/p.jpg"))
        db.add(d)
        db.flush()
        did, sid = d.id, d.slides[1].id
    try:
        started = time.time()
        r = client.post(f"/api/drafts/{did}/slides/{sid}/background",
                        files={"file": ("phone.png", _jpeg(), "image/png")})
        assert r.status_code == 200, r.text
        assert time.time() - started < 20
        slide = [s for s in r.json()["slides"] if s["id"] == sid][0]
        assert "/media/uploads/bg-" in slide["background_url"] and slide["image_url"]
        assert not any("/media/uploads/" in c for c in calls)          # read from disk, not over HTTP
        bad = client.post(f"/api/drafts/{did}/slides/{sid}/background", files={"file": ("x.heic", b"notanimage", "image/heic")})
        assert bad.status_code == 400 and "JPG" in bad.json()["detail"]
    finally:
        client.delete(f"/api/drafts/{did}")


def test_several_photos_are_spread_over_the_slides(client):
    with session_scope() as db:
        d = Draft(hook="h", caption="c " * 30, status="pending_review", origin="manual", language="ar")
        for i, kind in enumerate(["cover", "content", "content", "content", "cta"]):
            d.slides.append(Slide(position=i, kind=kind, heading="ع", body="ن"))
        db.add(d)
        db.flush()
        did = d.id
    try:
        files = [("files", (f"p{i}.png", _jpeg(colour=(i * 60, 80, 120)), "image/png")) for i in range(2)]
        r = client.post(f"/api/drafts/{did}/backgrounds", files=files)
        assert r.status_code == 200, r.text
        bgs = [s["background_url"] for s in sorted(r.json()["slides"], key=lambda s: s["position"])]
        assert len(set(bgs)) == 2 and bgs[0] == bgs[2] == bgs[4] and bgs[1] == bgs[3]   # repeated in order
    finally:
        client.delete(f"/api/drafts/{did}")
