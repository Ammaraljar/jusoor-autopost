"""Whole photo libraries (Dropbox / Drive folders, gallery pages) come into the company's library."""
import io
import zipfile

import httpx

from app.db import MediaAsset, session_scope
from app.services import images, media

from .conftest import jpeg_bytes


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("trip/beach.jpg", jpeg_bytes((10, 120, 200), (1200, 900)))
        zf.writestr("trip/city.png", jpeg_bytes((200, 120, 10), (1000, 1000)))
        zf.writestr("trip/notes.txt", "hello")
    return buf.getvalue()


FOLDER = ('<div class="flip-entry"><a href="https://drive.google.com/file/d/AAAAAAAAAAAAAAAAAAAAAAAA1/view">'
          '<div class="flip-entry-title">sea.jpg</div></a></div>'
          '<div class="flip-entry"><a href="https://drive.google.com/file/d/BBBBBBBBBBBBBBBBBBBBBBBB2/view">'
          '<div class="flip-entry-title">plan.pdf</div></a></div>')
GALLERY = ('<html><head><meta property="og:image" content="/g/cover.jpg"></head><body><header><img src="/logo.png">'
           '</header><img src="/g/one.jpg" alt="Langkawi"><img data-src="/g/two.jpg"><a href="/g/three-full.jpg">x</a>'
           '</body></html>')


def fake(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    img = {"content-type": "image/jpeg"}
    if "dropbox.com" in url:
        assert "dl=1" in url
        return httpx.Response(200, content=_zip(), headers={"content-type": "application/zip"})
    if "embeddedfolderview" in url:
        return httpx.Response(200, text=FOLDER, headers={"content-type": "text/html"})
    if "lh3.googleusercontent.com/d/AAAA" in url:
        return httpx.Response(200, content=jpeg_bytes((5, 80, 160)), headers=img)
    if url.startswith("https://gallery.test/g/"):
        return httpx.Response(200, content=jpeg_bytes((hash(url) % 255, 90, 40), (1400, 1000)), headers=img)
    if url == "https://gallery.test/photos":
        return httpx.Response(200, text=GALLERY, headers={"content-type": "text/html"})
    return httpx.Response(404)


def test_import_libraries_and_sync_again(client, monkeypatch):
    transport = httpx.MockTransport(fake)
    monkeypatch.setattr(media, "_client", lambda: httpx.Client(transport=transport, follow_redirects=True))
    r = client.post("/api/media/import", json={"url": "https://www.dropbox.com/scl/fo/abc/def?rlkey=k&dl=0",
                                               "tags": "رحلات"})
    job = client.get(f"/api/media/import/{r.json()['job']}").json()
    assert job["status"] == "done" and job["result"]["added"] == 2 and job["result"]["kind"] == "dropbox", job
    r = client.post("/api/media/import", json={"url": "https://drive.google.com/drive/folders/FOLDER1234567890"})
    job = client.get(f"/api/media/import/{r.json()['job']}").json()
    assert job["result"]["added"] == 1                                 # the PDF is not a photo
    r = client.post("/api/media/import", json={"url": "https://gallery.test/photos"})
    job = client.get(f"/api/media/import/{r.json()['job']}").json()
    assert job["result"]["added"] == 4                                 # cover, two photos, linked full size; no logo
    sources = client.get("/api/media/sources").json()
    assert {s["kind"] for s in sources} == {"dropbox", "gdrive", "page"}
    # syncing again adds only new photos
    r = client.post("/api/media/sources/sync", json={"url": "https://gallery.test/photos"})
    job = client.get(f"/api/media/import/{r.json()['job']}").json()
    assert job["result"]["added"] == 0 and job["result"]["skipped"] == 4
    client.post("/api/media/sources/remove", json={"url": "https://gallery.test/photos"})
    assert len(client.get("/api/media/sources").json()) == 2
    with session_scope() as db:
        assert db.query(MediaAsset).filter(MediaAsset.tags == "رحلات").count() == 2
        for a in db.query(MediaAsset).all():
            db.delete(a)
    with session_scope() as db:
        from app.services import app_settings
        app_settings.update_section(db, "media", {"sources": []})


def test_photo_sources_follow_the_settings(monkeypatch):
    calls = []
    for name in ("pexels", "pixabay", "unsplash", "openverse", "wikimedia"):
        monkeypatch.setitem(images.STOCK, name, lambda q, count=8, page=1, n=name: calls.append(n) or
                            [{"url": f"https://{n}.test/{i}.jpg", "credit": ""} for i in range(3)])
    monkeypatch.setattr(images, "download_image", lambda url: jpeg_bytes((hash(url) % 255, 1, 1)))
    out = images.collect_backgrounds("https://site.test/a.jpg", "kl", "auto", 3,
                                     library=[{"url": "https://lib.test/1.jpg", "credit": "", "match": True}],
                                     sources=["library", "unsplash"])
    urls = [o["url"] for o in out]
    # the company's own photo first; then the most eye-catching of the stock photos
    assert urls[0] == "https://lib.test/1.jpg" and len(urls) == 3 and all(u.startswith("https://unsplash.test/") for u in urls[1:])
    assert calls == ["unsplash"]                                       # the article photo and other libraries are off
    assert images.sources_of({"image_source": "source"}) == ["article", "library"]
    assert images.sources_of({"image_sources": ["wikimedia", "bogus"]}) == ["wikimedia"]


def test_photos_are_ranked_and_enhanced():
    """A colourful, sharp photo beats a grey, flat one; every photo is given livelier colour."""
    import io
    from PIL import Image, ImageDraw
    from app.services import images
    grey = Image.new("RGB", (800, 1000), (128, 128, 128))
    vivid = Image.new("RGB", (800, 1000), (20, 120, 220))
    d = ImageDraw.Draw(vivid)
    for i in range(0, 800, 40):
        d.rectangle([i, 0, i + 20, 1000], fill=(240, 80, 30))
    def jpg(im):
        b = io.BytesIO(); im.save(b, "JPEG"); return b.getvalue()
    assert images.quality(jpg(vivid)) > images.quality(jpg(grey))
    dull = Image.new("RGB", (400, 400), (150, 130, 110))
    out = Image.open(io.BytesIO(images.enhance(jpg(dull))))
    h, s, v = out.convert("HSV").getpixel((200, 200))
    h0, s0, v0 = dull.convert("HSV").getpixel((200, 200))
    assert s > s0                                                       # more colour after enhancing
