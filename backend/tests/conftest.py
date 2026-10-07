import io
import os
import shutil
import tempfile

TMP = tempfile.mkdtemp(prefix="autopost-test-")
os.environ.update({
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{TMP}/test.db"),
    "MEDIA_DIR": f"{TMP}/media",
    "AUTH_DISABLED": "true",
    "SCHEDULER_ENABLED": "false",
    "STORAGE_BACKEND": "local",
    "PUBLIC_BASE_URL": "https://autopost.example.com",
    "ANTHROPIC_API_KEY": "",
    "PEXELS_API_KEY": "",
    "BUFFER_API_KEY": "",
    "META_ACCESS_TOKEN": "",
    "UPLOADPOST_API_KEY": "",
})
if os.path.exists("/opt/pw-browsers/chromium") and not os.environ.get("CHROMIUM_PATH"):
    os.environ["CHROMIUM_PATH"] = "/opt/pw-browsers/chromium"

import httpx  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

LISTING_HTML = """<html><body>
<a href="/lifestyle/travel/2099/01/02/penang-after-22-years-an-island-that-steals-the-heart">Penang</a>
<a href="/lifestyle/travel/2099/01/02/penang-after-22-years-an-island-that-steals-the-heart#comments">dup</a>
<a href="/tag/travel">tag</a>
<a href="https://other.com/lifestyle/travel/2099/01/02/x">external</a>
</body></html>"""

ARTICLE_HTML = """<html><head>
<meta property="og:title" content="Penang after 22 years: an island that steals the heart">
<meta property="og:image" content="https://cdn.example.com/penang.jpg">
<meta property="article:published_time" content="2099-01-02T08:00:00Z">
</head><body><article>
<p>George Town in Penang has transformed over the last two decades into one of Southeast Asia's most loved heritage cities.</p>
<p>Visitors can explore street art, heritage cafes and night markets that stay open late into the evening.</p>
<p>The island's food scene remains its biggest draw, with char kway teow and assam laksa served at hawker centres.</p>
<p>Families will find new museums and a revitalised waterfront that makes walking tours easy even in the heat.</p>
</article></body></html>"""


def jpeg_bytes(color=(40, 90, 160), size=(1200, 1500)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


def fake_site(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.endswith("/lifestyle/travel"):
        return httpx.Response(200, text=LISTING_HTML)
    if "penang-after-22-years" in url:
        return httpx.Response(200, text=ARTICLE_HTML)
    if url.endswith(".jpg"):
        return httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"})
    return httpx.Response(404)


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch):
    """Provider retries wait seconds in production; tests must not."""
    from app.services import generator
    monkeypatch.setattr(generator, "RETRY_DELAYS", (0, 0, 0))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
    shutil.rmtree(TMP, ignore_errors=True)


@pytest.fixture
def fake_network(monkeypatch):
    from app.services import images, scraper

    transport = httpx.MockTransport(fake_site)
    monkeypatch.setattr(scraper, "_client",
                        lambda: httpx.Client(transport=transport, headers=scraper.HEADERS, follow_redirects=True))
    monkeypatch.setattr(images, "download_image",
                        lambda url: jpeg_bytes((hash(url) % 255, 120, 180)))
    return transport


@pytest.fixture(autouse=True)
def home_org(client):
    """Code in tests runs as company #1 (the migrated, original company)."""
    from sqlalchemy import select

    from app.db import Organization, current_org, session_scope
    with session_scope() as db:
        org_id = db.scalar(select(Organization.id).order_by(Organization.id))
    token = current_org.set(org_id)
    yield org_id
    current_org.reset(token)
