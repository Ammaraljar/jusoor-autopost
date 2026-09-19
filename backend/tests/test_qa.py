from types import SimpleNamespace

from app.services.qa import run_qa


def _draft(**kw):
    base = dict(hook="براغ مدينة السينما", subtitle="", caption=" ".join(["كلمة"] * 40),
                hashtags="#a #b #c #d", first_comment="", cta="احجز الآن", origin="source", source_name="The Star")
    base.update(kw)
    return SimpleNamespace(**base)


def _slides():
    kinds = ["cover", "content", "content", "cta"]
    return [SimpleNamespace(kind=k, heading="عنوان", body="لا يوجد مكان أجمل من بينانغ في الشتاء", position=i,
                            image_url=f"u{i}", width=1080, height=1350, image_hash=f"h{i}")
            for i, k in enumerate(kinds)]


def test_real_arabic_phrase_is_not_a_placeholder():
    assert run_qa(_draft(), _slides())["passed"]


def test_placeholder_first_comment_fails():
    report = run_qa(_draft(first_comment="لا يوجد فيديو"), _slides())
    assert not report["passed"]


def test_too_many_hashtags_fails():
    report = run_qa(_draft(hashtags=" ".join(f"#t{i}" for i in range(31))), _slides())
    assert not report["passed"]


def test_missing_images_fail():
    slides = _slides()
    slides[1].image_url = None
    assert not run_qa(_draft(), slides)["passed"]
