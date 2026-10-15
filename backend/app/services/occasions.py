"""Occasion posts: weekly (Friday), religious, national, world and shopping days.

The company picks the countries it speaks to; `compute()` builds that year's occasions for them
(dates, Hijri dates, anniversary numbers), `import_year()` stores them (keeping the company's own
edits), and `create_post()` writes a greeting post that fits the occasion, the country and the
company's field. A scheduler tick (`run_due`) creates the posts a few days ahead by itself.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import Draft, Occasion, Organization, Slide, session_scope
from . import app_settings, generator, industries, occasion_card
from . import occasions_data as data

log = logging.getLogger(__name__)
MAX_AUTO_PER_RUN = 3          # posts written per company per scheduler tick (spreads the AI cost)


# ------------------------------------------------------------------ dates
def _easter(year: int) -> date:
    from dateutil.easter import easter
    return easter(year)


def rule_date(year: int, rule: tuple) -> date | None:
    kind = rule[0]
    if kind == "fixed":
        return date(year, rule[1], rule[2])
    if kind == "easter":
        return _easter(year) + timedelta(days=rule[1])
    if kind == "dayofyear":
        return date(year, 1, 1) + timedelta(days=rule[1] - 1)
    if kind == "nth":
        month, weekday, n = rule[1], rule[2], rule[3]
        offset = rule[4] if len(rule) > 4 else 0
        if n > 0:
            first = date(year, month, 1)
            d = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
        else:
            last = (date(year, month % 12 + 1, 1) if month < 12 else date(year + 1, 1, 1)) - timedelta(days=1)
            d = last - timedelta(days=(last.weekday() - weekday) % 7)
        return d + timedelta(days=offset)
    return None


def hijri_of(d: date) -> tuple[int, int, int] | None:
    try:
        from hijridate import Gregorian
        h = Gregorian(d.year, d.month, d.day).to_hijri()
        return h.year, h.month, h.day
    except Exception:  # noqa: BLE001 - outside the Umm al-Qura range
        return None


def hijri_label(d: date | None, lang: str = "ar") -> str:
    h = hijri_of(d) if d else None
    if not h:
        return ""
    if lang == "ar":
        return f"{h[2]} {data.HIJRI_MONTHS_AR[h[1] - 1]} {h[0]}هـ"
    from hijridate import Hijri
    return f"{h[2]} {Hijri(*h).month_name()} {h[0]} AH"


def date_label(d: date | None, lang: str = "ar") -> str:
    if not d:
        return ""
    if lang == "ar":
        return f"{d.day} {data.MONTHS_AR[d.month - 1]} {d.year}"
    return d.strftime("%-d %B %Y")


def _islamic_dates(year: int) -> dict[str, date]:
    """Umm al-Qura dates of the Islamic occasions that fall in a Gregorian year."""
    from hijridate import Hijri
    out: dict[str, date] = {}
    for hy in (year - 580, year - 579, year - 578):
        for key, (hm, hd, *_rest) in data.ISLAMIC.items():
            try:
                g = Hijri(hy, hm, hd).to_gregorian()
            except Exception:  # noqa: BLE001
                continue
            d = date(g.year, g.month, g.day)
            if d.year == year and key not in out:
                out[key] = d
    return out


# ------------------------------------------------------------------ holiday lists
def _lang_for(cls, wanted: str) -> str | None:
    langs = getattr(cls, "supported_languages", ()) or ()
    for lang in langs:
        if lang == wanted or lang.startswith(wanted + "_"):
            return lang
    return None


def _holidays(country: str, year: int, lang: str) -> dict[date, list[str]]:
    import holidays
    try:
        base = holidays.country_holidays(country, years=year)
        use = _lang_for(base, lang) or (_lang_for(base, "en") if lang == "en" else None)
        if lang != "en" and not use:
            return {}
        kwargs = {"years": year, "observed": False, "language": use}
        if country in data.SUBDIVISION:
            kwargs["subdiv"] = data.SUBDIVISION[country]
        h = holidays.country_holidays(country, **kwargs)
    except Exception:  # noqa: BLE001 - unsupported country / language
        return {}
    return {d: [p.strip() for p in n.split(";") if p.strip()] for d, n in h.items()}


_CLEAN_EN = re.compile(r"\s*\((estimated|observed|tentative)[^)]*\)|\s+Holiday$", re.I)
_CLEAN_AR = re.compile(r"\s*\((تقديري|يوم تعويضي|يوم تعويضي تقديري)\)|^عطلة\s+")


def _clean_en(name: str) -> str:
    return _CLEAN_EN.sub("", _CLEAN_EN.sub("", name)).strip()


def _clean_ar(name: str) -> str:
    name = _CLEAN_AR.sub("", _CLEAN_AR.sub("", name)).strip()
    return data.AR_FIX.get(name, name)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50] or "day"


GENERIC_AR = ("اليوم الوطني", "عيد الاستقلال", "يوم الاستقلال", "عيد الجمهورية", "يوم الجمهورية", "يوم الدستور",
              "يوم القوات المسلحة", "عيد النصر", "يوم التأسيس", "يوم العلم")


def _with_country(name_ar: str, name_en: str, country: str) -> tuple[str, str]:
    """"National Day" alone is ambiguous when several countries are followed: name the country."""
    if name_ar not in GENERIC_AR or country not in data.COUNTRIES:
        return name_ar, name_en
    ar, en = data.COUNTRIES[country][0], data.COUNTRIES[country][1]
    return f"{name_ar} {'لل' + ar[2:] if ar.startswith('ال') else 'ل' + ar}", f"{name_en} ({en})"


def _national_motif(lname: str, festive: bool) -> str:
    if "chinese" in lname or "lunar" in lname:
        return "lantern"
    return "sparkle" if festive else "flag"


def _country_names(codes: list[str], lang: str = "ar") -> str:
    i = 0 if lang == "ar" else 1
    return "، ".join(data.COUNTRIES[c][i] for c in codes if c in data.COUNTRIES)


# ------------------------------------------------------------------ building a year
def compute(year: int, countries: list[str], industry: str | None = None) -> list[dict[str, Any]]:
    """Every occasion of the year for the given countries (not stored)."""
    countries = [c for c in dict.fromkeys(countries) if c in data.COUNTRIES]
    items: dict[str, dict[str, Any]] = {}
    muslim = [c for c in countries if c in data.MUSLIM]

    def add(key: str, **fields) -> None:
        if key in items:
            items[key]["countries"] = sorted(set(items[key]["countries"]) | set(fields.get("countries") or []))
            return
        fields.setdefault("number", None)
        fields.setdefault("relevant", True)
        fields.setdefault("enabled", True)
        items[key] = {"key": key, **fields}

    # holiday lists of each country
    islamic_seen: dict[str, dict[str, set[date]]] = defaultdict(lambda: defaultdict(set))
    world_dates: dict[tuple[str, str], date] = {}
    for c in countries:
        en = _holidays(c, year, "en")
        ar = _holidays(c, year, "ar")
        for d, names in sorted(en.items()):
            ar_names = ar.get(d) or []
            for i, raw in enumerate(names):
                low = raw.lower()
                isl = next((k for w, k in data.ISLAMIC_WORDS if w in low), None)
                if isl:
                    islamic_seen[isl][c].add(d)
                    continue
                if any(w in low for w in data.SKIP_WORDS):
                    continue
                name_en = _clean_en(raw)
                world = next((k for w, k in data.WORLD_WORDS if w in name_en.lower()), None)
                if world:
                    world_dates.setdefault((world, c), d)
                    continue
                name_ar = _clean_ar(ar_names[i]) if len(ar_names) == len(names) else ""
                name_ar = name_ar or data.AR_NAMES.get(name_en, name_en)
                lname = name_en.lower()
                mmdd = d.strftime("%m-%d")
                if any(w in lname for w in data.OTHER_FAITH_WORDS):
                    motif = "lamp" if ("diwali" in lname or "deepavali" in lname) else "star"
                    add(f"faith:{_slug(name_en)}:{mmdd}", kind="religious", tone="festive", motif=motif, date=d,
                        name_ar=name_ar, name_en=name_en, countries=[c])
                    continue
                memorial = any(w in lname for w in data.MEMORIAL_WORDS)
                festive = any(w in lname for w in ("new year", "festival", "songkran", "spring", "children",
                                                   "mid-autumn", "dragon boat"))
                base = data.NUMBERS.get((c, mmdd))
                key = f"nat:{c}:{_slug(name_en)}"          # several days off for one day: the first one counts
                name_ar, name_en = data.NAME_FIX.get((c, mmdd)) or _with_country(name_ar, name_en, c)
                add(key, kind="national",
                    tone="memorial" if memorial else ("festive" if festive else "pride"),
                    motif=_national_motif(lname, festive), date=d, name_ar=name_ar, name_en=name_en, countries=[c],
                    number=(year - base) if base else None)
        for mmdd, key, name_ar, name_en in data.NATIONAL_EXTRA.get(c, []):
            d = date(year, int(mmdd[:2]), int(mmdd[3:]))
            if any(it["kind"] == "national" and c in it["countries"] and it["date"] == d for it in items.values()):
                continue
            base = data.NUMBERS.get((c, mmdd))
            add(f"nat:{c}:{key}", kind="national", tone="memorial" if key == "commemoration" else "pride",
                motif="flag", date=d, name_ar=name_ar, name_en=name_en, countries=[c],
                number=(year - base) if base else None)

    # Islamic occasions: Umm al-Qura dates, or the date most target countries use
    if muslim:
        uq = _islamic_dates(year)
        for key, (_hm, _hd, name_ar, name_en, motif, tone, always, on) in data.ISLAMIC.items():
            if key not in uq:
                continue
            seen = islamic_seen.get(key, {})
            if not always and not seen:
                continue
            votes = Counter()
            for c in muslim:
                ds = seen.get(c)
                if not ds or uq[key] in ds:
                    votes[uq[key]] += 1
                    continue
                near = sorted(ds, key=lambda x: abs((x - uq[key]).days))[0]
                votes[near if abs((near - uq[key]).days) <= 2 else uq[key]] += 1
            best = max(votes.items(), key=lambda kv: (kv[1], kv[0] == uq[key]))[0]
            h = hijri_of(best)
            add(f"isl:{key}", kind="religious", tone=tone, motif=motif, date=best, name_ar=name_ar,
                name_en=name_en, countries=muslim if always else [c for c in muslim if c in seen], enabled=on,
                number=h[0] if key == "hijri_new_year" and h else None)

    # world and shopping days (each country may keep its own date)
    for key, w in data.WORLD.items():
        targets = [c for c in countries if not w.get("only") or c in w["only"]]
        if countries and not targets:
            continue
        groups: dict[tuple, list[str]] = defaultdict(list)
        for c in targets or [None]:
            rule, names = None, None
            for spec in w["rules"]:
                if spec[0] == "*" or (c and c in spec[0]):
                    rule, names = spec[1], (spec[2] if len(spec) > 2 else None)
                    break
            d = world_dates.get((key, c)) if c else None
            d = d or (rule_date(year, rule) if rule else None)
            if d:
                groups[(d, names)].append(c)
        relevant = w["industries"] is None or (industry or "general") in w["industries"]
        for (d, names), cs in groups.items():
            k = f"world:{key}" if len(groups) == 1 else f"world:{key}:{d.strftime('%m-%d')}" + (
                f":{_slug(names[1])}" if names else "")
            add(k, kind=w["kind"], tone=w["tone"], motif=w["motif"], date=d,
                name_ar=(names or (w["ar"], w["en"]))[0], name_en=(names or (w["ar"], w["en"]))[1],
                countries=[c for c in cs if c], relevant=relevant, enabled=bool(w["on"] and relevant),
                number=year if key == "new_year" else None)

    out = []
    for it in items.values():
        it.setdefault("weekday", None)
        it["year"] = year
        it["hijri"] = hijri_label(it.get("date"))
        out.append(it)
    # the weekly Friday greeting, for Muslim audiences
    for key, (weekday, name_ar, name_en, motif, tone, muslim_only) in data.WEEKLY.items():
        if muslim or not muslim_only:
            out.append({"key": f"weekly:{key}", "kind": "weekly", "tone": tone, "motif": motif, "date": None,
                        "weekday": weekday, "name_ar": name_ar, "name_en": name_en, "countries": muslim,
                        "number": None, "relevant": True, "enabled": True, "year": None, "hijri": ""})
    out.sort(key=lambda x: (x["date"] or date(year, 1, 1), x["key"]))
    return out


def settings(db: Session) -> dict[str, Any]:
    return app_settings.get_section(db, "occasions")


def _org(db: Session) -> Organization | None:
    from ..db import current_org
    oid = current_org.get()
    return db.get(Organization, oid) if oid else db.scalar(select(Organization).order_by(Organization.id))


def import_year(db: Session, year: int) -> dict[str, int]:
    """Store the year's occasions for the company's countries; the company's edits are kept."""
    cfg = settings(db)
    org = _org(db)
    industry = (org.industry if org else None) or app_settings.get_section(db, "generation").get("industry")
    kinds = cfg.get("kinds") or {}
    found = [it for it in compute(year, cfg.get("countries") or [], industry) if kinds.get(it["kind"], True)]
    existing = {o.key: o for o in db.scalars(select(Occasion).where(
        or_(Occasion.year == year, Occasion.year.is_(None)), Occasion.source == "auto"))}
    added = updated = removed = 0
    keys = set()
    for it in found:
        keys.add(it["key"])
        row = existing.get(it["key"])
        if row is None:
            db.add(Occasion(source="auto", recurrence="weekly" if it["kind"] == "weekly" else "yearly",
                            drafts={}, notes="", edited=False, **{k: it[k] for k in (
                                "year", "key", "kind", "tone", "motif", "date", "weekday", "name_ar", "name_en",
                                "countries", "number", "hijri", "enabled", "relevant")}))
            added += 1
            continue
        row.countries, row.relevant, row.kind, row.tone, row.motif = (it["countries"], it["relevant"], it["kind"],
                                                                      it["tone"], it["motif"])
        if not row.edited:
            row.date, row.weekday, row.name_ar, row.name_en = it["date"], it["weekday"], it["name_ar"], it["name_en"]
            row.number, row.hijri = it["number"], it["hijri"]
        updated += 1
    for key, row in existing.items():
        if key not in keys and not row.drafts and not row.edited:
            db.delete(row)
            removed += 1
    # the company's own yearly occasions come back every year
    have = {o.key for o in db.scalars(select(Occasion).where(Occasion.year == year, Occasion.source == "custom"))}
    for row in db.scalars(select(Occasion).where(Occasion.source == "custom", Occasion.recurrence == "yearly",
                                                 Occasion.year < year).order_by(Occasion.year.desc())):
        if row.key in have or not row.date:
            continue
        have.add(row.key)
        try:
            d = row.date.replace(year=year)
        except ValueError:           # 29 February
            d = row.date.replace(year=year, day=28)
        db.add(Occasion(source="custom", recurrence="yearly", year=year, key=row.key, kind=row.kind, tone=row.tone,
                        motif=row.motif, date=d, name_ar=row.name_ar, name_en=row.name_en, countries=row.countries,
                        number=(row.number + (year - row.year)) if row.number else None, hijri=hijri_label(d),
                        enabled=row.enabled, relevant=True, notes=row.notes, post_time=row.post_time, drafts={},
                        edited=True))
        added += 1
    db.flush()
    return {"added": added, "updated": updated, "removed": removed, "total": len(found)}


def next_dates(row: Occasion, start: date, days: int = 400) -> list[date]:
    """Upcoming dates of an occasion (a weekly one repeats)."""
    if row.recurrence == "weekly" and row.weekday is not None:
        first = start + timedelta(days=(row.weekday - start.weekday()) % 7)
        return [first + timedelta(days=7 * i) for i in range(days // 7 + 1)]
    return [row.date] if row.date and row.date >= start else []


# ------------------------------------------------------------------ the post
OCCASION_TOOL = {
    "name": "occasion_post",
    "description": "Return the occasion greeting post.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hook": {"type": "string", "description": "The greeting shown big on the image, max 6 words "
                                                      "(e.g. عيد فطر مبارك / كل عام وأنتم بخير / Happy Teachers' Day)."},
            "highlight": {"type": "string", "description": "1-2 words copied EXACTLY from the hook, shown in gold."},
            "subtitle": {"type": "string", "description": "One short line under the greeting, max 12 words."},
            "caption": {"type": "string", "description": "Caption, 45-110 words, fitting the occasion's identity."},
            "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 10},
            "image_keywords": {"type": "string",
                               "description": "3-6 English keywords for a background photo that matches the occasion "
                                              "and the country (no text in the photo), e.g. 'ramadan lantern night'."},
            "cta": {"type": "string", "description": "A short sign-off from the company, max 8 words."},
            "first_comment": {"type": "string", "description": "Usually an empty string."},
        },
        "required": ["hook", "subtitle", "caption", "hashtags", "image_keywords", "cta"],
    },
}


def _system_prompt(brand: generator.BrandContext, gen: dict[str, Any], occ: dict[str, Any]) -> str:
    language = gen.get("language", "ar")
    profile = industries.get(gen.get("industry"))
    lang = generator.LANG_NAMES.get(language, "Arabic")
    countries = occ.get("countries") or []
    tones = [data.TONE.get(c, data.TONE_DEFAULT) for c in countries[:4]] or [data.TONE_DEFAULT]
    tone_lines = "\n".join(f"- {t}" for t in dict.fromkeys(tones))
    style = generator.dialect_rules(gen.get("dialect")) if language == "ar" else ""
    return f"""You write occasion greeting posts for {brand.name} ({brand.handle}), a {profile['brand_type']}.
Industry: {profile['en']}. Brand voice: {brand.voice or 'warm, trustworthy and respectful'}.
Write everything in {lang}.{(' ' + style) if style else ''}
Audience and country tone:
{tone_lines}
Occasion identity: {data.TONE_RULES.get(occ.get('tone'), data.TONE_RULES['festive'])}
Field tone: link the greeting to {brand.name}'s field ({profile['en']}) in one natural line — the way a respected
{profile['brand_type']} would, never a sales pitch on spiritual, national or memorial days.
Rules:
- The image shows only the greeting (hook), one short line (subtitle), the logo and the date: keep them short.
- Never invent facts, prices, discounts, official slogans or quotes. Use the anniversary number only if it is given.
- Hashtags: the ones people in the target country really use for this occasion (with the number when given),
  plus 1-2 for the brand's field. No spaces inside a hashtag.
- At most 2 emojis in the caption, none on the image, none at all on memorial days."""


def _user_prompt(occ: dict[str, Any], notes: str, recent: list[str]) -> str:
    lines = [f"Occasion: {occ['name_ar']} / {occ['name_en']}",
             f"Date: {occ['date_label']}" + (f" (Hijri: {occ['hijri']})" if occ.get("hijri") else ""),
             f"Countries: {_country_names(occ.get('countries') or [], 'en') or 'international audience'}",
             f"Kind: {occ['kind']}"]
    if occ.get("number"):
        lines.append(f"Anniversary / year number to use: {occ['number']}")
    if notes:
        lines.append(f"Editor notes (follow them): {notes}")
    if recent:
        lines.append("Earlier greetings for the same occasion (write something clearly different): " + " | ".join(recent))
    return "\n".join(lines) + "\n\nWrite the post with the occasion_post tool."


def _demo(occ: dict[str, Any], language: str) -> dict[str, Any]:
    ar = language == "ar"
    name = occ["name_ar"] if ar else occ["name_en"]
    hook = name if len(name.split()) <= 6 else name.split("(")[0].strip()
    caption = (f"بمناسبة {name} نتقدّم إليكم بأطيب التهاني والتمنيات، ونسأل الله أن يعيده علينا وعليكم بالخير "
               f"والبركة. شكرًا لثقتكم الدائمة بنا، وكل عام وأنتم بخير."
               if ar else f"On {name}, we send you our warmest wishes. Thank you for your trust — may this day bring "
                          "you joy, peace and good things.")
    tag = re.sub(r"\s+", "_", re.sub(r"[()\.،,]", "", name)).strip("_")
    lines = {"spiritual": ("تقبّل الله منا ومنكم صالح الأعمال", "Warm wishes and blessings"),
             "pride": ("فخورون بوطنٍ يكبر بأهله", "Proud of a nation and its people"),
             "memorial": ("نستذكر بكل إجلال وتقدير", "We remember with respect"),
             "awareness": ("معًا من أجل حياة أفضل", "Together for a better life"),
             "commercial": ("ترقّبوا عروضنا", "Watch out for our offers")}
    sub = lines.get(occ.get("tone"), ("كل عام وأنتم بخير", "Best wishes from all of us"))[0 if ar else 1]
    return {"hook": hook, "highlight": "", "subtitle": sub, "caption": caption,
            "hashtags": [f"#{tag}", "#كل_عام_وأنتم_بخير" if ar else "#Greetings", "#تهنئة" if ar else "#Celebration",
                         "#مناسبات" if ar else "#Occasion"],
            "image_keywords": "celebration lights", "cta": "", "first_comment": ""}


def _occ_dict(row: Occasion, on: date) -> dict[str, Any]:
    return {"id": row.id, "key": row.key, "kind": row.kind, "tone": row.tone, "motif": row.motif,
            "name_ar": row.name_ar, "name_en": row.name_en, "countries": list(row.countries or []),
            "number": row.number, "date": on.isoformat(), "date_label": date_label(on),
            "hijri": hijri_label(on) if row.kind in ("religious", "weekly") or row.key.startswith("isl:") else "",
            "notes": row.notes or ""}


def _dialect_for(countries: list[str], gen: dict[str, Any], cfg: dict[str, Any]) -> str | None:
    if gen.get("language", "ar") != "ar" or not cfg.get("dialect_by_country", True):
        return None
    arab = [c for c in countries if c in data.ARAB]
    dialects = {data.COUNTRIES[c][3] for c in arab}
    return dialects.pop() if len(arab) >= 1 and len(dialects) == 1 and len(arab) == len(countries) else None


def _post_of(db: Session, row: Occasion, day: str, did: Any) -> Draft | None:
    """The occasion's own post for that day. A deleted post's number can be given to a new, unrelated
    post later, so the post must really be this occasion's greeting for this date."""
    try:
        d = db.get(Draft, int(did))
    except (TypeError, ValueError):
        return None
    if d is None or d.origin != "occasion":
        return None
    occ = (d.ai_meta or {}).get("occasion") or {}
    if occ.get("id") != row.id and occ.get("key") != row.key:
        return None
    return d if not occ.get("date") or occ.get("date") == day else None


def own_posts(db: Session, row: Occasion) -> dict[str, Draft]:
    """{date: draft} of the occasion; links to deleted or foreign posts are dropped from the row."""
    out = {}
    for day, did in (row.drafts or {}).items():
        d = _post_of(db, row, day, did)
        if d is not None:
            out[day] = d
    if len(out) != len(row.drafts or {}):
        row.drafts = {day: d.id for day, d in out.items()}
    return out


def create_post_draft(occasion_id: int, on: date | None = None) -> int:
    """A draft for one occasion date (the text and design are made by finish_post)."""
    from .pipeline import _brand_for
    with session_scope() as db:
        row = db.get(Occasion, occasion_id)
        if row is None:
            raise ValueError("المناسبة غير موجودة")
        on = on or (next_dates(row, date.today()) or [row.date or date.today()])[0]
        drafts = {day: d.id for day, d in own_posts(db, row).items()}
        if on.isoformat() in drafts:
            raise ValueError("يوجد منشور لهذه المناسبة في هذا التاريخ")
        brand = _brand_for(db, None)
        gen = app_settings.get_section(db, "generation")
        cfg = settings(db)
        occ = _occ_dict(row, on)
        dialect = _dialect_for(occ["countries"], gen, cfg) or gen.get("dialect")
        draft = Draft(brand_id=brand.id, origin="occasion", original_title=row.name_ar or row.name_en,
                      original_body=_user_prompt(occ, row.notes or "", []), language=gen["language"],
                      tone=gen["tone"], content_type="occasion", platform=gen.get("platform", "instagram"),
                      dialect=dialect, badge="", status="generating", ai_meta={"occasion": occ})
        db.add(draft)
        db.flush()
        drafts[on.isoformat()] = draft.id
        row.drafts = drafts
        return draft.id


def _recent(db: Session, key: str, exclude: int) -> list[str]:
    rows = db.scalars(select(Draft).where(Draft.origin == "occasion", Draft.id != exclude)
                      .order_by(Draft.id.desc()).limit(40)).all()
    return [d.hook for d in rows if ((d.ai_meta or {}).get("occasion") or {}).get("key") == key and d.hook][:4]


async def finish_post(draft_id: int) -> None:
    """Write the greeting, then design the image (and schedule it when the company wants that)."""
    from . import pipeline
    with session_scope() as db:
        d = db.get(Draft, draft_id)
        if d is None:
            return
        brand = pipeline._brand_for(db, d.brand_id)
        gen = {**app_settings.get_section(db, "generation"), "language": d.language}
        if d.dialect:
            gen["dialect"] = d.dialect
        org = _org(db)
        if org and org.industry:
            gen["industry"] = org.industry
        occ = dict((d.ai_meta or {}).get("occasion") or {})
        row = db.get(Occasion, occ.get("id")) if occ.get("id") else None
        notes = (row.notes if row else occ.get("notes")) or ""
        recent = _recent(db, occ.get("key", ""), draft_id)
        ctx = pipeline.brand_context(brand)
    try:
        if generator.ai_available():
            result = await generator._call_model(_system_prompt(ctx, gen, occ), _user_prompt(occ, notes, recent),
                                                 OCCASION_TOOL, max_tokens=1500)
        else:
            result = _demo(occ, gen.get("language", "ar"))
    except Exception as exc:  # noqa: BLE001
        pipeline._fail(draft_id, f"فشل توليد النص: {exc}")
        return
    hook = generator._text(result.get("hook")) or occ.get("name_ar", "")
    highlight = generator._text(result.get("highlight"))
    with session_scope() as db:
        d = db.get(Draft, draft_id)
        d.hook, d.subtitle = hook, generator._text(result.get("subtitle"))
        d.caption = generator._text(result.get("caption"))
        d.hashtags = " ".join(generator._normalise_hashtags(result.get("hashtags")))
        d.cta, d.first_comment = generator._text(result.get("cta")), generator._text(result.get("first_comment"))
        # the photo search is never left to the AI: a curated, people-free one (most greetings use none)
        d.image_keywords = occasion_card.safe_keywords(occ)
        d.hook_highlight = highlight if highlight and highlight in hook else None
        d.badge, d.relevance = "", 10
        d.ai_meta = {"occasion": occ}
        d.slides.clear()
        d.slides.append(Slide(position=0, kind="cover", heading=d.hook, body=d.subtitle))
    await asyncio.gather(pipeline.make_variants(draft_id), pipeline.render_draft(draft_id))
    with session_scope() as db:
        if settings(db).get("auto_schedule", True):
            schedule_post(db, draft_id)


def _local_dt(db: Session, on: date, hm: str) -> datetime:
    from .scheduling import _hm, config
    tz: ZoneInfo = config(db)["tz"]
    return datetime.combine(on, _hm(hm), tzinfo=tz).astimezone(timezone.utc)


def schedule_post(db: Session, draft_id: int) -> datetime | None:
    """Put an occasion post on its own day, in the morning, on every platform the company publishes on.

    Occasion greetings are outside the regular plan: no daily slots, no gap between posts and no
    platform limits — a greeting that arrives late is worse than none."""
    from . import pipeline, qa, scheduling
    d = db.get(Draft, draft_id)
    occ = (d.ai_meta or {}).get("occasion") if d else None
    if not d or not occ or d.status not in ("pending_review", "approved"):
        return None
    row = db.get(Occasion, occ.get("id")) if occ.get("id") else None
    on = date.fromisoformat(occ["date"])
    hm = (row.post_time if row and row.post_time else None) or settings(db).get("post_time") or "08:00"
    at = _local_dt(db, on, hm)
    now = datetime.now(timezone.utc)
    if at < now:
        if _local_dt(db, on, "23:00") < now:
            return None                                   # the day is over
        at = now + timedelta(minutes=5)                   # made on the day itself: as soon as possible
    report = qa.run_qa(d, d.slides, app_settings.get_section(db, "generation").get("credit_source", True))
    if not report["passed"]:
        pipeline._fail_soft(draft_id, "لم تُجدول التهنئة: فشل فحص الجودة")
        return None
    targets = scheduling.default_targets(db)
    if not any(t.get("platforms") for t in targets):
        pipeline._fail_soft(draft_id, "لم تُجدول التهنئة: لا توجد منصات نشر — حدّدها من الإعدادات ← النشر")
        return None
    d.publish_targets = targets
    d.status, d.scheduled_at, d.error = "scheduled", at, None
    db.flush()
    return at


async def create_post(occasion_id: int, on: date | None = None) -> int:
    draft_id = create_post_draft(occasion_id, on)
    await finish_post(draft_id)
    return draft_id


# ------------------------------------------------------------------ automation
def due(db: Session, today: date | None = None) -> list[tuple[int, date]]:
    """Occasions whose post should be written now (lead days before the date, no post yet)."""
    cfg = settings(db)
    if not cfg.get("auto_create", True):
        return []
    today = today or date.today()
    lead = max(0, min(int(cfg.get("lead_days", 3)), 30))
    out = []
    for row in db.scalars(select(Occasion).where(Occasion.enabled.is_(True))):
        days = 1 if row.recurrence == "weekly" else lead
        for on in next_dates(row, today, days + 1):
            if on - timedelta(days=days) <= today <= on and on.isoformat() not in own_posts(db, row):
                out.append((row.id, on))
    out.sort(key=lambda x: x[1])
    return out


async def run_due() -> int:
    with session_scope() as db:
        todo = due(db)[:MAX_AUTO_PER_RUN]
    done = 0
    for occ_id, on in todo:
        try:
            await create_post(occ_id, on)
            done += 1
        except Exception:  # noqa: BLE001
            log.exception("occasion post failed for %s on %s", occ_id, on)
    return done


def ensure_year(db: Session, year: int) -> None:
    """The coming year is prepared by itself once the company has chosen its countries."""
    cfg = settings(db)
    if not cfg.get("countries"):
        return
    if db.scalar(select(Occasion.id).where(Occasion.year == year, Occasion.source == "auto").limit(1)) is None:
        import_year(db, year)


# ------------------------------------------------------------------ views
def item_view(db: Session, row: Occasion, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    out = row.to_dict()
    nxt = next_dates(row, today, 14)
    out["next_date"] = nxt[0].isoformat() if nxt else None
    out["date_label"] = date_label(row.date) if row.date else ""
    posts = []
    for day, d in sorted(own_posts(db, row).items()):
        if d is not None:
            posts.append({"date": day, "draft_id": d.id, "status": d.status, "thumb": d.cover_thumb_url,
                          "scheduled_at": d.scheduled_at.isoformat() if d.scheduled_at else None})
    out["posts"] = posts
    out["flags"] = "".join(data.COUNTRIES[c][2] for c in (row.countries or []) if c in data.COUNTRIES)
    return out


def countries_catalog() -> list[dict[str, Any]]:
    return [{"code": c, "ar": v[0], "en": v[1], "flag": v[2], "muslim": c in data.MUSLIM, "arab": c in data.ARAB}
            for c, v in data.COUNTRIES.items()]


def new_custom(db: Session, body: dict[str, Any]) -> Occasion:
    rec = body.get("recurrence") if body.get("recurrence") in ("once", "yearly", "weekly") else "once"
    d = body.get("date")
    if rec != "weekly" and not d:
        raise ValueError("حدّد تاريخ المناسبة")
    row = Occasion(source="custom", recurrence=rec, key=f"custom:{uuid.uuid4().hex[:10]}",
                   kind="weekly" if rec == "weekly" else (body.get("kind") or "custom"),
                   tone=body.get("tone") if body.get("tone") in data.TONES else "festive",
                   motif=body.get("motif") or "sparkle", date=None if rec == "weekly" else d,
                   weekday=int(body.get("weekday") or 4) if rec == "weekly" else None,
                   year=None if rec == "weekly" else d.year, name_ar=body.get("name", "").strip(),
                   name_en=(body.get("name_en") or body.get("name", "")).strip(),
                   countries=[c for c in body.get("countries") or [] if c in data.COUNTRIES],
                   number=body.get("number"), hijri=hijri_label(d) if d and rec != "weekly" else "",
                   enabled=True, relevant=True, notes=body.get("notes") or "", post_time=body.get("post_time") or None,
                   drafts={}, edited=True)
    db.add(row)
    db.flush()
    return row
