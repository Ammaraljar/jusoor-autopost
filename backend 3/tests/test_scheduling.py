"""Daily plan: 5 posts a day, spread out, never two within 2 hours; posts can be moved."""
from datetime import date, datetime, timedelta, timezone

from app.db import Draft, Slide, session_scope
from app.services import scheduling


def _ready_draft():
    with session_scope() as db:
        d = Draft(hook="عنوان جيد للمنشور", caption="نص المنشور الكامل " * 10, hashtags="#سفر #ماليزيا #سياحة #جسور #travel",
                  status="approved", origin="manual", language="ar", cta="احجز معنا")
        for i, kind in enumerate(["cover", "content", "content", "content", "content", "cta"]):
            d.slides.append(Slide(position=i, kind=kind, heading="عنوان", body="نص الشريحة",
                                  image_url=f"https://cdn.example/{i}.jpg", image_key=f"k{i}", width=1080, height=1350,
                                  image_hash=f"h{i}"))
        db.add(d)
        db.flush()
        return d.id


def test_day_slots_are_spread_and_respect_the_gap():
    cfg = {"per_day": 5, "start": "09:00", "end": "21:00", "gap": 2.0, "tz": scheduling.ZoneInfo("Asia/Kuala_Lumpur")}
    slots = scheduling.day_slots(cfg, date(2026, 11, 2))
    local = [s.astimezone(cfg["tz"]).strftime("%H:%M") for s in slots]
    assert local == ["09:00", "12:00", "15:00", "18:00", "21:00"]
    cfg["per_day"] = 10                       # 10 in 12 hours would break the 2-hour rule → spaced 2h apart
    local = [s.astimezone(cfg["tz"]).strftime("%H:%M") for s in scheduling.day_slots(cfg, date(2026, 11, 2))]
    assert local == ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00"]


def test_auto_schedule_fills_slots_and_moves(client):
    client.put("/api/settings/publishing", json={"posts_per_day": 3, "day_start": "09:00", "day_end": "21:00",
                                                 "min_gap_hours": 2, "default_platforms": ["instagram"]})
    ids = [_ready_draft() for _ in range(4)]
    try:
        r = client.post("/api/drafts/bulk", json={"ids": ids, "action": "auto_schedule"}).json()
        assert r["done"] == 4, r
        with session_scope() as db:
            times = sorted(db.get(Draft, i).scheduled_at.replace(tzinfo=timezone.utc) for i in ids)
        assert all(b - a >= timedelta(hours=2) for a, b in zip(times, times[1:]))
        tz = scheduling.ZoneInfo("Asia/Kuala_Lumpur")
        days = [t.astimezone(tz).date() for t in times]
        assert max(days.count(d) for d in set(days)) <= 3            # never more than the daily limit

        # Too close to another post → refused with a clear reason
        clash = (times[0] + timedelta(minutes=30)).isoformat()
        bad = client.post(f"/api/drafts/{ids[1]}/schedule", json={"scheduled_at": clash})
        assert bad.status_code == 409 and "ساعة" in bad.json()["detail"]

        # Move a post to another day: it takes that day's first free slot
        target = (days[-1] + timedelta(days=3)).isoformat()
        moved = client.post(f"/api/drafts/{ids[0]}/schedule", json={"date": target}).json()
        assert moved["status"] == "scheduled"
        at = datetime.fromisoformat(moved["scheduled_at"]).astimezone(tz)
        assert at.date().isoformat() == target and at.strftime("%H:%M") == "09:00"

        plan = client.get("/api/calendar").json()["plan"]
        assert plan["posts_per_day"] == 3 and plan["today_slots"][0] == "09:00"
    finally:
        client.post("/api/drafts/bulk", json={"ids": ids, "action": "delete"})
        client.put("/api/settings/publishing", json={"posts_per_day": 5, "day_end": "22:00"})


def test_autoplan_schedules_high_scoring_posts(client):
    did = _ready_draft()
    with session_scope() as db:
        d = db.get(Draft, did)
        d.status, d.relevance = "pending_review", 9
    client.put("/api/settings/publishing", json={"auto_approve_min_relevance": 8, "default_platforms": ["instagram"]})
    try:
        assert scheduling.run_autoplan()["scheduled"] >= 1
        with session_scope() as db:
            assert db.get(Draft, did).status == "scheduled"
    finally:
        client.put("/api/settings/publishing", json={"auto_approve_min_relevance": 0})
        client.delete(f"/api/drafts/{did}")
