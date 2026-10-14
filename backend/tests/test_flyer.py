"""Product / service / offer flyers: logo, headline, feature chips, prices, requirements, contact band, QR."""
import asyncio

from app.services import flyer
from app.services.renderer import BrandStyle, SlideSpec, build_html, renderer


def test_flyer_text_is_kept_within_the_design():
    data = flyer.clean({"headline": "رحلة إسطنبول وبورصة الرائعة جدا جدا جدا جدا", "features": [
        {"icon": "plane", "text": "طيران"}, {"icon": "nope", "text": "فندق"}, {"icon": "meal", "text": ""}] * 4,
        "prices": [{"amount": "3,950", "currency": "SAR", "old": "4,600"}, {"amount": "اتصل بنا"}],
        "requirements": ["جواز", "صورة", "عربون", "تأمين", "خامس"], "cta": "احجز"})
    assert len(data["headline"].split()) <= 7
    assert len(data["features"]) == 6 and data["features"][1]["icon"] == "check"     # unknown icon → check
    assert data["prices"] == [{"label": "", "amount": "3,950", "currency": "SAR", "old": "4,600"}]  # no invented price
    assert len(data["requirements"]) == 4
    demo = flyer.demo("دورة التصميم", "شهادة معتمدة\nمدة 6 أسابيع\nPrice: 900 RM", "900", "RM", "ar")
    assert demo["prices"][0]["amount"] == "900" and demo["features"][0]["icon"] == "certificate"


def test_contact_data_is_cleaned():
    c = flyer.clean_contact({"phones": [{"number": "+966 55 123 4567"}, {"number": "abc"}, {"number": "12"}],
                             "branches": [{"name": "الرياض", "address": "العليا"}, {"name": " "}], "show": True})
    assert [p["number"] for p in c["phones"]] == ["+966 55 123 4567"] and c["phones"][0]["whatsapp"]
    assert c["branches"] == [{"name": "الرياض", "address": "العليا"}] and c["show"]


def test_every_flyer_layout_renders_with_logo_contact_and_qr():
    brand = BrandStyle(name="Jusoor Travel", handle="@jusoortravel", website="jusoortravel.com",
                       colors={"navy": "#16244F", "gold": "#C6A23C"}, language="ar")
    base = flyer.clean({"headline": "رحلة إسطنبول", "highlight": "إسطنبول", "tagline": "6 أيام", "badge": "عرض محدود",
                        "features": [{"icon": "plane", "text": "طيران"}, {"icon": "hotel", "text": "فندق"}],
                        "prices": [{"label": "للشخص", "amount": "3,950", "currency": "SAR", "old": "4,600"}],
                        "requirements": ["جواز ساري"], "cta": "احجز الآن"})
    contact = flyer.clean_contact({"phones": [{"number": "+966 55 123 4567"}], "branches": [{"name": "الرياض"}]})
    assert len(flyer.LAYOUTS) >= 8
    for layout in flyer.LAYOUTS:
        spec = SlideSpec(kind="cover", heading="رحلة إسطنبول", body="6 أيام", position=0, total=3,
                         flyer={**base, "layout": layout, "contact": contact, "qr_url": "https://jusoortravel.com/x"})
        page = build_html(spec, brand)
        assert f"fl-{layout}" in page and "+966 55 123 4567" in page and "data:image/svg+xml" in page
        assert "3,950" in page and "<em>إسطنبول</em>" in page and "جواز ساري" in page

    async def one():
        spec = SlideSpec(kind="cover", heading="رحلة", body="", position=0, total=1,
                         flyer={**base, "layout": "poster", "contact": {}, "qr_url": ""})
        out = await renderer.render(spec, brand)
        await renderer.close()
        return out
    assert asyncio.run(one())[:2] == b"\xff\xd8"
