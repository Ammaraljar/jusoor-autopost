"""Fill a local database with demo sources and drafts (no network or API keys needed).

    cd backend && python -m scripts.seed_demo
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import random
from datetime import timedelta

from PIL import Image, ImageDraw, ImageFilter

from app.db import Article, Source, init_db, session_scope, utcnow
from app.services import images, pipeline

ARTICLES = [
    ("Penang after 22 years: an island that steals the heart", "The Star - Travel", 0),
    ("Borneo flavours await in Sabah and Sarawak", "The Star - Travel", 1),
    ("Famous filming locations in Prague to check out", "The Star - Travel", 0),
    ("Malaysia revives its visual memory with a new photo archive", "The Star - Culture", 2),
    ("Surfing cats and mountain-climbing kittens charm Malaysia", "The Star - Culture", 3),
    ("A 37-metre manuscript that changed literature goes on show", "The Star - Culture", 5),
]
BODY = ("George Town has transformed over the last two decades into one of Southeast Asia's most loved heritage "
        "cities. Visitors can explore street art, heritage cafes and night markets that stay open late. "
        "The food scene remains the biggest draw, with char kway teow and assam laksa at hawker centres. "
        "Families will find new museums and a revitalised waterfront that makes walking tours easy. ") * 2


def fake_photo(seed: int) -> bytes:
    rnd = random.Random(seed)
    top = (rnd.randint(20, 80), rnd.randint(90, 160), rnd.randint(150, 220))
    bottom = (rnd.randint(10, 60), rnd.randint(60, 120), rnd.randint(40, 90))
    img = Image.new("RGB", (1200, 1500))
    d = ImageDraw.Draw(img)
    for y in range(1500):
        k = y / 1500
        d.line([(0, y), (1200, y)], fill=tuple(int(top[i] * (1 - k) + bottom[i] * k) for i in range(3)))
    d.ellipse([rnd.randint(600, 900), 150, rnd.randint(950, 1100), 400], fill=(255, 220, 150))
    for i in range(14):
        x = rnd.randint(-100, 1200)
        h = rnd.randint(250, 700)
        d.polygon([(x - 260, 1500), (x, 1500 - h), (x + 260, 1500)], fill=tuple(max(0, c - 25) for c in bottom))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def fake_backgrounds(article_image, keywords, mode, needed):
    base = int(hashlib.md5((keywords or "x").encode() + (article_image or "").encode()).hexdigest(), 16) % 1000
    out = []
    for i in range(needed):
        data = fake_photo(base + i)
        out.append({"url": f"demo://{base + i}", "bytes": data, "hash": hashlib.sha1(data).hexdigest(), "credit": ""})
    return out


async def main() -> None:
    init_db()
    images.collect_backgrounds = fake_backgrounds
    with session_scope() as db:
        pipeline.ensure_default_brand(db)
        ids = {}
        for name, path in (("The Star - Travel", "travel"), ("The Star - Culture", "culture")):
            src = Source(name=name, kind="website", base_url="https://www.thestar.com.my",
                         listing_urls=[f"https://www.thestar.com.my/lifestyle/{path}"],
                         link_pattern=rf"/lifestyle/{path}/\d{{4}}/\d{{2}}/\d{{2}}/", health="healthy",
                         last_checked_at=utcnow() - timedelta(minutes=18), last_success_at=utcnow(),
                         last_http_status=200)
            db.add(src)
            db.flush()
            ids[name] = src.id
        art_ids = []
        for i, (title, source, age) in enumerate(ARTICLES):
            art = Article(source_id=ids[source], url=f"https://www.thestar.com.my/demo/{i}", title=title, body=BODY,
                          published_at=utcnow() - timedelta(days=age), fingerprint=f"demo{i}", status="new",
                          image_url=f"https://example.com/{i}.jpg")
            db.add(art)
            db.flush()
            art_ids.append(art.id)
    for aid in art_ids:
        await pipeline.draft_from_article(aid)
    from app.db import Draft
    from sqlalchemy import select
    with session_scope() as db:
        drafts = list(db.scalars(select(Draft).order_by(Draft.id)))
        for d, age in zip(drafts, [a[2] for a in ARTICLES]):
            d.created_at = utcnow() - timedelta(days=age, hours=1)
        drafts[-1].status = "published"
        drafts[-1].published_at = utcnow() - timedelta(days=1)
        drafts[-2].status = "scheduled"
        drafts[-2].scheduled_at = utcnow() + timedelta(days=2)
        drafts[-2].publish_targets = [{"provider": "buffer", "platforms": ["instagram", "facebook"]}]
    await pipeline.renderer.close()
    print(f"seeded {len(art_ids)} drafts")


if __name__ == "__main__":
    asyncio.run(main())
