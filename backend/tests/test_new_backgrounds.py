"""“New backgrounds” must really change the photos."""
import asyncio
import io

from PIL import Image

from app.db import Draft, Slide, session_scope
from app.services import images, pipeline


def _img(c):
    out = io.BytesIO()
    Image.new("RGB", (800, 1000), c).save(out, "JPEG")
    return out.getvalue()


def test_refresh_uses_photos_not_used_before(client, monkeypatch):
    pool = [{"url": f"https://stock.example/{i}.jpg", "credit": ""} for i in range(12)]
    monkeypatch.setattr(images, "stock_photos", lambda kw, count, page=1: list(pool))
    monkeypatch.setattr(images, "download_image", lambda url: _img((int(url.split("/")[-1].split(".")[0]) * 20, 90, 120)))
    with session_scope() as db:
        d = Draft(hook="h", caption="c " * 30, status="pending_review", origin="manual", language="ar",
                  image_keywords="langkawi")
        for i, kind in enumerate(["cover", "content", "content", "cta"]):
            d.slides.append(Slide(position=i, kind=kind, heading="ع", body="ن"))
        db.add(d)
        db.flush()
        did = d.id
    try:
        asyncio.run(pipeline.render_draft(did))
        with session_scope() as db:
            first = {s.background_url for s in db.get(Draft, did).slides}
            cta = [s for s in db.get(Draft, did).slides if s.kind == "cta"][0].background_url
            cover = [s for s in db.get(Draft, did).slides if s.kind == "cover"][0].background_url
        assert cta != cover                                   # the last slide has its own photo
        asyncio.run(pipeline.render_draft(did, refresh_backgrounds=True))
        with session_scope() as db:
            second = {s.background_url for s in db.get(Draft, did).slides}
        assert first.isdisjoint(second)                       # every photo changed
    finally:
        client.delete(f"/api/drafts/{did}")
