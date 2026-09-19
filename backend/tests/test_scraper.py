from app.db import Source
from app.services import scraper
from tests.conftest import ARTICLE_HTML


def test_parse_article_extracts_metadata():
    art = scraper.parse_article("https://www.thestar.com.my/a", ARTICLE_HTML)
    assert art.title.startswith("Penang after 22 years")
    assert art.image_url == "https://cdn.example.com/penang.jpg"
    assert art.published_at.year == 2099
    assert "George Town" in art.body and len(art.body) > 250


def test_discover_links_filters_noise(fake_network):
    src = Source(name="t", kind="website", base_url="https://www.thestar.com.my",
                 listing_urls=["https://www.thestar.com.my/lifestyle/travel"])
    result = scraper.discover_links(src)
    assert result.links == ["https://www.thestar.com.my/lifestyle/travel/2099/01/02/"
                            "penang-after-22-years-an-island-that-steals-the-heart"]
    assert result.http_status == 200


def test_title_fingerprint_ignores_order_and_punctuation():
    assert scraper.title_fingerprint("Penang, the island!") == scraper.title_fingerprint("the island penang")
