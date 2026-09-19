"""Automatic quality checks before a draft can be published."""
from __future__ import annotations

import re

# Short fields that only say "nothing here" are generation leftovers (e.g. first comment "لا يوجد فيديو").
EMPTYISH = re.compile(r"^\W*(لا يوجد|لا توجد|غير متوفر|غير متاح|none|n/a|null|-)", re.I)
TEMPLATE_JUNK = re.compile(r"(\{\{|\}\}|\blorem ipsum\b|\bTODO\b|\[insert)", re.I)


def _placeholder(fields: list[str]) -> str | None:
    for text in fields:
        t = (text or "").strip()
        if not t:
            continue
        if len(t) <= 30 and EMPTYISH.search(t):
            return t
        m = TEMPLATE_JUNK.search(t)
        if m:
            return m.group(0)
    return None


def _item(key: str, label: str, status: str, message: str) -> dict:
    return {"key": key, "label": label, "status": status, "message": message}


def run_qa(draft, slides: list, credit_required: bool = True) -> dict:
    items: list[dict] = []
    words = len((draft.hook or "").split())
    if not draft.hook:
        items.append(_item("hook", "قوة العنوان", "fail", "لا يوجد عنوان."))
    elif words > 12:
        items.append(_item("hook", "قوة العنوان", "warn", f"العنوان طويل ({words} كلمة)، الأفضل 10 كلمات أو أقل."))
    else:
        items.append(_item("hook", "قوة العنوان", "pass", f"عنوان مناسب ({words} كلمات)."))

    cap_words = len((draft.caption or "").split())
    if cap_words < 20:
        items.append(_item("caption", "نص المنشور", "fail", "نص المنشور قصير جدًا أو فارغ."))
    elif len(draft.caption) > 2100:
        items.append(_item("caption", "نص المنشور", "fail", "النص يتجاوز حد إنستغرام (2200 حرف مع الهاشتاقات)."))
    else:
        items.append(_item("caption", "نص المنشور", "pass", f"نص المنشور جاهز ({cap_words} كلمة)."))

    tags = [t for t in (draft.hashtags or "").split() if t.startswith("#")]
    if len(tags) < 3:
        items.append(_item("hashtags", "الهاشتاقات", "warn", f"{len(tags)} هاشتاق فقط."))
    elif len(tags) > 30:
        items.append(_item("hashtags", "الهاشتاقات", "fail", "إنستغرام يسمح بـ 30 هاشتاق كحد أقصى."))
    else:
        items.append(_item("hashtags", "الهاشتاقات", "pass", f"{len(tags)} هاشتاق."))

    found = _placeholder([draft.hook, draft.subtitle, draft.caption, draft.first_comment, draft.cta] +
                         [s.heading for s in slides] + [s.body for s in slides])
    if found:
        items.append(_item("placeholder", "نصوص ناقصة", "fail", f"يوجد نص مؤقت أو ناقص: «{found}»."))
    else:
        items.append(_item("placeholder", "نصوص ناقصة", "pass", "لا توجد نصوص مؤقتة."))

    has_cta = any(s.kind == "cta" for s in slides)
    items.append(_item("cta", "دعوة للإجراء (CTA)", "pass" if has_cta else "warn",
                       "توجد شريحة دعوة للإجراء." if has_cta else "لا توجد شريحة دعوة للإجراء."))

    content = sum(1 for s in slides if s.kind == "content")
    if not slides:
        items.append(_item("structure", "بنية الكاروسيل", "fail", "لا توجد شرائح."))
    elif len(slides) > 10:
        items.append(_item("structure", "بنية الكاروسيل", "fail", "إنستغرام يسمح بـ 10 شرائح كحد أقصى."))
    else:
        items.append(_item("structure", "بنية الكاروسيل", "pass", f"{len(slides)} شرائح ({content} محتوى)."))

    missing = [s.position + 1 for s in slides if not s.image_url]
    bad_size = [s.position + 1 for s in slides if s.image_url and (s.width, s.height) != (1080, 1350)]
    if missing:
        items.append(_item("images", "جودة الصور", "fail", f"شرائح بدون صورة: {missing}."))
    elif bad_size:
        items.append(_item("images", "جودة الصور", "warn", f"مقاسات غير قياسية في الشرائح {bad_size}."))
    else:
        items.append(_item("images", "جودة الصور", "pass", "كل الصور بدقة 1080×1350."))

    bg_hashes = [s.image_hash for s in slides if s.kind == "content" and s.image_hash]
    dupes = len(bg_hashes) - len(set(bg_hashes))
    items.append(_item("repetition", "تكرار الصور", "warn" if dupes else "pass",
                       f"{dupes} شريحة تعيد استخدام نفس الخلفية." if dupes else "لا تكرار في الصور."))

    if draft.origin == "source" and credit_required:
        ok = bool(draft.source_name)
        items.append(_item("credit", "ذكر المصدر", "pass" if ok else "warn",
                           f"سيُذكر المصدر: {draft.source_name}." if ok else "اسم المصدر غير معروف."))

    fails = sum(1 for i in items if i["status"] == "fail")
    warns = sum(1 for i in items if i["status"] == "warn")
    return {"items": items, "passed": fails == 0, "fails": fails, "warns": warns}
