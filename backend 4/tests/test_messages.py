"""Server messages follow the interface language; post content is never touched."""
from app.db import Draft, Slide, session_scope
from app.services import messages


def test_errors_come_back_in_the_interface_language(client):
    assert client.get("/api/sources/999999").json()["detail"] == "المصدر غير موجود"
    assert client.get("/api/sources/999999", headers={"X-Lang": "en"}).json()["detail"] == "Source not found"
    assert client.get("/api/sources/999999", headers={"X-Lang": "fr"}).json()["detail"] == "Source introuvable"
    ms = client.get("/api/drafts/999999", headers={"X-Lang": "ms"}).json()["detail"]
    assert ms and "مسودة" not in ms


def test_nested_and_variable_messages():
    t = messages.translate("فشل توليد النص: Groq: تجاوزت حد الطلبات أو الحصة المجانية — انتظر قليلًا ثم أعد المحاولة", "en")
    assert t.startswith("Text generation failed") and "Groq" in t and "rate limit" in t.lower()
    assert "14" in messages.translate("العنوان طويل (14 كلمة)، الأفضل 10 كلمات أو أقل.", "fr")


def test_post_content_is_not_translated(client):
    with session_scope() as db:
        d = Draft(hook="المصدر غير موجود", caption="نص عربي", status="pending_review", origin="manual",
                  error="فشل توليد النص: خطأ ما")
        d.slides.append(Slide(position=0, kind="cover", heading="عنوان", body="نص"))
        db.add(d)
        db.flush()
        did = d.id
    data = client.get(f"/api/drafts/{did}", headers={"X-Lang": "en"}).json()
    assert data["hook"] == "المصدر غير موجود"                 # content stays as written
    assert data["error"].startswith("Text generation failed")
    import re
    assert data["qa"]["items"] and not any(re.search("[\u0600-\u06FF]", i["label"] + i["message"])
                                           for i in data["qa"]["items"])
    client.delete(f"/api/drafts/{did}")
