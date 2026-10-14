from datetime import date, timedelta, timezone

from sqlalchemy import select

from app.db import Draft, Occasion, session_scope
from app.services import app_settings, occasions

from .conftest import jpeg_bytes


def _by_key(items):
    return {i["key"]: i for i in items}


def test_year_of_occasions_for_countries():
    items = _by_key(occasions.compute(2026, ["SA", "AE", "MY", "EG"], "travel"))
    # national days with their anniversary numbers and the names people use
    assert items["nat:SA:national_day"]["number"] == 96 and items["nat:SA:national_day"]["date"] == date(2026, 9, 23)
    assert items["nat:SA:national_day"]["name_ar"] == "اليوم الوطني السعودي"
    assert items["nat:MY:national_day"]["number"] == 69
    uae = next(i for k, i in items.items() if k.startswith("nat:AE:national_day"))
    assert uae["name_ar"] == "عيد الاتحاد" and uae["number"] == 55 and uae["date"] == date(2026, 12, 2)
    # Islamic occasions once, for all Muslim countries, with the Hijri date
    eid = items["isl:eid_fitr"]
    assert eid["date"] == date(2026, 3, 20) and eid["hijri"].startswith("1 شوال 1447")
    assert set(eid["countries"]) == {"SA", "AE", "MY", "EG"}
    assert items["isl:hijri_new_year"]["number"] == 1448
    assert "SA" not in items["isl:mawlid"]["countries"]              # only where it is observed
    # the weekly Friday greeting
    assert items["weekly:friday"]["weekday"] == 4 and items["weekly:friday"]["date"] is None
    # world days keep each country's own date
    mothers = [i for k, i in items.items() if k.startswith("world:mothers_day")]
    assert {(i["date"], tuple(i["countries"])) for i in mothers} == {(date(2026, 3, 21), ("SA", "AE", "EG")),
                                                                      (date(2026, 5, 10), ("MY",))}
    friday = [i for k, i in items.items() if k.startswith("world:black_friday")]
    assert {i["name_ar"] for i in friday} == {"الجمعة البيضاء", "الجمعة السوداء (بلاك فرايدي)"}
    # what fits the field is on, the rest is listed but off
    assert items["world:tourism_day"]["enabled"] and not items["world:heart_day"]["enabled"]
    # no days off / duplicates of multi-day holidays
    assert not any("observed" in i["name_en"].lower() or "second day" in i["name_en"].lower() for i in items.values())
    assert len([k for k in items if k.startswith("nat:AE:national_day")]) == 1


def test_import_keeps_edits_and_custom_occasions(client):
    client.put("/api/occasions/settings", json={"countries": ["SA", "MY", "XX"], "lead_days": 3})
    with session_scope() as db:
        assert occasions.settings(db)["countries"] == ["SA", "MY"]
    r = client.post("/api/occasions/import", json={"year": 2030})
    assert r.status_code == 200 and r.json()["added"] > 20
    data = client.get("/api/occasions", params={"year": 2030}).json()
    nat = next(i for i in data["items"] if i["key"] == "nat:SA:national_day")
    assert nat["number"] == 100 and nat["flags"] == "🇸🇦"
    # the company edits a date and a name, and turns a day off
    r = client.patch(f"/api/occasions/{nat['id']}", json={"date": "2030-09-24", "name_ar": "يومنا الوطني",
                                                         "notes": "اذكر فرعنا في الرياض"})
    assert r.json()["edited"] and r.json()["date"] == "2030-09-24"
    ramadan = next(i for i in data["items"] if i["key"] == "isl:ramadan_start")
    client.patch(f"/api/occasions/{ramadan['id']}", json={"enabled": False})
    # its own yearly occasion
    r = client.post("/api/occasions", json={"name": "ذكرى تأسيس جسور", "date": "2030-04-10", "recurrence": "yearly",
                                            "number": 12, "countries": ["MY"]})
    assert r.status_code == 200, r.text
    # importing again keeps all of it
    client.post("/api/occasions/import", json={"year": 2030})
    data = client.get("/api/occasions", params={"year": 2030}).json()
    nat = next(i for i in data["items"] if i["key"] == "nat:SA:national_day")
    assert nat["date"] == "2030-09-24" and nat["name_ar"] == "يومنا الوطني" and nat["notes"] == "اذكر فرعنا في الرياض"
    assert not next(i for i in data["items"] if i["key"] == "isl:ramadan_start")["enabled"]
    # next year the company's yearly occasion comes back with the next number
    client.post("/api/occasions/import", json={"year": 2031})
    mine = [i for i in client.get("/api/occasions", params={"year": 2031}).json()["items"] if i["source"] == "custom"]
    assert mine and mine[0]["date"] == "2031-04-10" and mine[0]["number"] == 13
    # a country occasion is turned off, not deleted; one's own can be deleted
    assert client.delete(f"/api/occasions/{nat['id']}").status_code == 400
    assert client.delete(f"/api/occasions/{mine[0]['id']}").status_code == 200
    with session_scope() as db:
        for o in db.scalars(select(Occasion)).all():
            db.delete(o)


def test_occasion_post_is_written_designed_and_scheduled(client, monkeypatch):
    from app.services import images
    monkeypatch.setattr(images, "collect_backgrounds",
                        lambda *a, **k: [{"url": "https://img.example.com/eid.jpg", "bytes": jpeg_bytes((30, 60, 90)),
                                          "hash": "eid", "credit": ""}])
    monkeypatch.setattr(images, "download_image", lambda url: jpeg_bytes((30, 60, 90)))
    on = date.today() + timedelta(days=2)
    with session_scope() as db:
        app_settings.update_section(db, "occasions", {"countries": ["SA"], "auto_schedule": True,
                                                      "post_time": "10:00", "lead_days": 3})
        app_settings.update_section(db, "publishing", {"channels": {"instagram": {"provider": "buffer", "limit": 0,
                                                                                 "period": "day"}}})
        row = Occasion(key="nat:SA:test_day", kind="national", tone="pride", motif="flag", name_ar="اليوم الوطني السعودي",
                       name_en="Saudi National Day", date=on, year=on.year, countries=["SA"], number=96,
                       recurrence="yearly", enabled=True, drafts={}, source="auto")
        db.add(row)
        db.flush()
        oid = row.id
        # it is due (within the lead days) and has no post yet
        assert (oid, on) in occasions.due(db)
    r = client.post(f"/api/occasions/{oid}/post", json={"date": on.isoformat()})
    assert r.status_code == 200, r.text
    draft_id = r.json()["draft_id"]
    with session_scope() as db:
        d = db.get(Draft, draft_id)
        assert d.origin == "occasion" and d.content_type == "occasion" and len(d.slides) == 1
        assert d.dialect == "gulf"                                  # a post for Saudi Arabia speaks Gulf Arabic
        assert d.slides[0].image_url and d.palette.get("occasion")
        assert d.status == "scheduled" and d.scheduled_at is not None
        at = d.scheduled_at if d.scheduled_at.tzinfo else d.scheduled_at.replace(tzinfo=timezone.utc)
        local = at.astimezone(occasions.ZoneInfo("Asia/Kuala_Lumpur"))
        assert local.date() == on and local.hour >= 10
        assert (oid, on) not in occasions.due(db)                   # no second post for the same day
        view = occasions.item_view(db, db.get(Occasion, oid))
        assert view["posts"][0]["draft_id"] == draft_id
    # a second post for the same date is refused
    assert client.post(f"/api/occasions/{oid}/post", json={"date": on.isoformat()}).status_code == 409
    with session_scope() as db:
        db.delete(db.get(Draft, draft_id))
        db.delete(db.get(Occasion, oid))
        app_settings.update_section(db, "publishing", {"channels": {}})
        app_settings.update_section(db, "occasions", {"countries": []})


def test_weekly_friday_repeats():
    row = Occasion(recurrence="weekly", weekday=4, drafts={})
    days = occasions.next_dates(row, date(2026, 10, 14), 20)
    assert days[0] == date(2026, 10, 16) and days[1] == date(2026, 10, 23)


def test_rule_dates():
    assert occasions.rule_date(2026, ("nth", 11, 3, 4, 1)) == date(2026, 11, 27)      # Black Friday
    assert occasions.rule_date(2026, ("nth", 5, 6, 2)) == date(2026, 5, 10)           # 2nd Sunday of May
    assert occasions.rule_date(2026, ("nth", 5, 6, -1)) == date(2026, 5, 31)          # last Sunday of May
    assert occasions.rule_date(2026, ("easter", -21)) == date(2026, 3, 15)            # Mothering Sunday (UK)
    assert occasions.rule_date(2026, ("dayofyear", 256)) == date(2026, 9, 13)         # Programmers' Day


def test_occasion_designs_are_many_bright_and_photo_safe():
    from app.services import occasion_card as oc
    assert len(oc.LAYOUTS) >= 20
    for tone, (bg1, bg2, *_rest) in oc.MOODS.items():
        assert oc._lum(bg1) > 0.85 and oc._lum(bg2) > 0.85, tone            # light backgrounds only
    eid = {"key": "isl:eid_fitr", "kind": "religious", "tone": "festive", "motif": "crescent"}
    sa = {"key": "nat:SA:national_day", "kind": "national", "tone": "pride", "motif": "flag", "number": 96}
    teachers = {"key": "world:teachers_day", "kind": "international", "tone": "appreciation", "motif": "book"}
    assert not oc.uses_photo(eid) and not oc.uses_photo(sa) and oc.uses_photo(teachers)
    assert "photo_card" not in oc.layouts_for(eid) and "photo_card" not in oc.layouts_for(sa)
    assert "confetti" not in oc.layouts_for({**eid, "tone": "spiritual"})
    assert "big_number" in oc.layouts_for(sa) and "big_number" not in oc.layouts_for(teachers)
    assert "lanterns" not in oc.layouts_for(teachers)
    assert len(oc.layouts_for(eid)) >= 10
    # every design index maps to a suitable layout, and consecutive greetings differ
    seen = {oc.spec_for(eid, "ar", i)["layout"] for i in range(5)}
    assert len(seen) == 5 and not (seen - set(oc.layouts_for(eid)))
    assert "people" not in oc.safe_keywords(teachers)


def test_logo_for_light_prefers_dark_then_colour_then_plate():
    from app.services.palette import logo_for_light
    assert logo_for_light([("light", b"L"), ("dark", b"D"), ("color", b"C")], b"L") == (b"D", False)
    assert logo_for_light([("light", b"L"), ("color", b"C")], b"L") == (b"C", False)
    assert logo_for_light([], None) == (None, False)
