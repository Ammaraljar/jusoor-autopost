"""Daily posting plan: N posts a day, spread across the day, never two within the minimum gap.

Times are planned in the brand's local time zone (Malaysia by default) and stored in UTC.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Draft
from . import app_settings, qa

BUSY_STATUSES = ("scheduled", "publishing", "published")
LOOKAHEAD_DAYS = 60


def config(db: Session) -> dict[str, Any]:
    pub = app_settings.get_section(db, "publishing")
    return {
        "per_day": max(1, min(int(pub.get("posts_per_day", 5)), 24)),
        "start": str(pub.get("day_start", "09:00")),
        "end": str(pub.get("day_end", "22:00")),
        "gap": max(0.0, float(pub.get("min_gap_hours", 2))),
        "tz": ZoneInfo(str(pub.get("timezone", "Asia/Kuala_Lumpur"))),
    }


def _hm(value: str) -> time:
    h, m = (value.split(":") + ["0"])[:2]
    return time(int(h) % 24, int(m) % 60)


def day_slots(cfg: dict[str, Any], day: date) -> list[datetime]:
    """The planned posting times for one local day (UTC datetimes), evenly spread."""
    tz = cfg["tz"]
    start = datetime.combine(day, _hm(cfg["start"]), tzinfo=tz)
    end = datetime.combine(day, _hm(cfg["end"]), tzinfo=tz)
    if end <= start:
        end = start + timedelta(hours=12)
    n = cfg["per_day"]
    step = (end - start) / (n - 1) if n > 1 else timedelta(0)
    step = max(step, timedelta(hours=cfg["gap"])) if n > 1 else step
    slots = []
    for i in range(n):
        at = start + step * i
        if at > end + timedelta(minutes=1):
            break
        slots.append(at.astimezone(timezone.utc))
    return slots


def _busy_times(db: Session, start: datetime, end: datetime, exclude_id: int | None = None) -> list[datetime]:
    # occasion greetings live outside the plan: they never take a regular post's place
    q = select(Draft.id, Draft.scheduled_at, Draft.published_at).where(Draft.status.in_(BUSY_STATUSES),
                                                                       Draft.origin != "occasion")
    out = []
    for did, sched, pub in db.execute(q):
        if did == exclude_id:
            continue
        at = sched or pub
        if at is None:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if start - timedelta(days=1) <= at <= end + timedelta(days=1):
            out.append(at)
    return out


def _local_day(cfg: dict[str, Any], at: datetime) -> date:
    return at.astimezone(cfg["tz"]).date()


def check(db: Session, when: datetime, draft_id: int | None = None, cfg: dict | None = None) -> str | None:
    """Why this time breaks the plan (gap or daily limit) — None when it is fine."""
    cfg = cfg or config(db)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    busy = _busy_times(db, when, when, draft_id)
    gap = timedelta(hours=cfg["gap"])
    for at in busy:
        if abs(at - when) < gap:
            local = at.astimezone(cfg["tz"]).strftime("%H:%M")
            return f"يوجد منشور آخر الساعة {local} — يجب أن يفصل {cfg['gap']:g} ساعة على الأقل بين منشورين"
    day = _local_day(cfg, when)
    same_day = [a for a in busy if _local_day(cfg, a) == day]
    if len(same_day) >= cfg["per_day"]:
        return f"اكتمل عدد منشورات يوم {day.isoformat()} ({cfg['per_day']} منشورات) — اختر يومًا آخر أو ارفع العدد من الإعدادات"
    return None


def next_free_slot(db: Session, after: datetime | None = None, draft_id: int | None = None,
                   only_day: date | None = None, cfg: dict | None = None) -> datetime | None:
    """The earliest planned slot that respects the gap and the daily limit."""
    cfg = cfg or config(db)
    now = datetime.now(timezone.utc)
    after = max(after or now, now + timedelta(minutes=10))
    first_day = only_day or _local_day(cfg, after)
    days = [only_day] if only_day else [first_day + timedelta(days=i) for i in range(LOOKAHEAD_DAYS)]
    busy = _busy_times(db, after, after + timedelta(days=LOOKAHEAD_DAYS), draft_id)
    gap = timedelta(hours=cfg["gap"])
    for day in days:
        taken = [a for a in busy if _local_day(cfg, a) == day]
        if len(taken) >= cfg["per_day"]:
            continue
        for slot in day_slots(cfg, day):
            if slot < after:
                continue
            if all(abs(slot - a) >= gap for a in busy):
                return slot
    return None


# ------------------------------------------------------------------ channels: provider + quota per platform
PERIODS = ("day", "week", "month")
PERIOD_AR = {"day": "اليوم", "week": "هذا الأسبوع", "month": "هذا الشهر"}


def channels(db: Session) -> dict[str, dict[str, Any]]:
    """{platform: {provider, limit, period}} — which service publishes each platform, and how often.
    limit 0 = no limit. Older settings (one provider for everything) are read the same way."""
    pub = app_settings.get_section(db, "publishing")
    raw = pub.get("channels") or {}
    if not raw:
        raw = {p: {"provider": pub.get("default_provider", "buffer")} for p in pub.get("default_platforms") or []}
    out = {}
    for platform, c in raw.items():
        if not isinstance(c, dict) or not c.get("provider"):
            continue
        period = c.get("period") if c.get("period") in PERIODS else "week"
        out[platform] = {"provider": str(c["provider"]), "limit": max(0, int(c.get("limit") or 0)), "period": period}
    return out


def default_targets(db: Session) -> list[dict[str, Any]]:
    """Every enabled platform with its own service — several services can publish one post together."""
    groups: dict[str, list[str]] = {}
    for platform, c in channels(db).items():
        groups.setdefault(c["provider"], []).append(platform)
    return [{"provider": p, "platforms": pl} for p, pl in groups.items()]


def _window(cfg: dict[str, Any], when: datetime, period: str) -> tuple[datetime, datetime]:
    local = when.astimezone(cfg["tz"])
    day = datetime.combine(local.date(), time(0), tzinfo=cfg["tz"])
    if period == "day":
        start, end = day, day + timedelta(days=1)
    elif period == "week":                      # Monday to Sunday
        start = day - timedelta(days=local.weekday())
        end = start + timedelta(days=7)
    else:
        start = day.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def usage(db: Session, platform: str, when: datetime, period: str, exclude_id: int | None = None,
          cfg: dict | None = None) -> int:
    """Posts already published or planned on this platform in the period that contains `when`."""
    cfg = cfg or config(db)
    start, end = _window(cfg, when, period)
    n = 0
    for d in db.scalars(select(Draft).where(Draft.status.in_(BUSY_STATUSES), Draft.origin != "occasion")):
        if d.id == exclude_id:
            continue
        at = d.scheduled_at or d.published_at
        if at is None:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if start <= at < end and any(platform in (t.get("platforms") or []) for t in d.publish_targets or []):
            n += 1
    return n


def within_quota(db: Session, targets: list[dict], when: datetime, exclude_id: int | None = None
                 ) -> tuple[list[dict], dict[str, str]]:
    """The targets whose platform still has room at that time, and why the others were held back."""
    ch, cfg = channels(db), config(db)
    kept, blocked = [], {}
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    for t in targets or []:
        ok = []
        for p in t.get("platforms") or []:
            c = ch.get(p)
            if c and c["limit"] and usage(db, p, when, c["period"], exclude_id, cfg) >= c["limit"]:
                blocked[p] = f"اكتمل حد {p}: {c['limit']} منشور {PERIOD_AR[c['period']]}"
            else:
                ok.append(p)
        if ok:
            kept.append({**t, "platforms": ok})
    return kept, blocked


def schedule(db: Session, draft: Draft, when: datetime | None = None, targets: list | None = None) -> datetime:
    """Put a draft on the plan (the next free slot unless a time is given)."""
    gen = app_settings.get_section(db, "generation")
    report = qa.run_qa(draft, draft.slides, gen.get("credit_source", True))
    if not report["passed"]:
        raise ValueError("لا يمكن جدولة منشور لم يجتز فحص الجودة")
    if draft.status in ("generating", "publishing", "published"):
        raise ValueError("لا يمكن جدولة هذا المنشور في حالته الحالية")
    wanted = targets or draft.publish_targets or default_targets(db)
    if not any(t.get("platforms") for t in wanted):
        raise ValueError("لا توجد منصات نشر افتراضية — حدّدها من الإعدادات ← النشر")
    if when is None:
        # the next free slot where at least one of the post's platforms still has room in its quota
        after, kept = None, []
        for _ in range(120):
            when = next_free_slot(db, after=after, draft_id=draft.id)
            if when is None:
                raise ValueError("لا توجد مواعيد فارغة في الأيام القادمة — ارفع عدد المنشورات اليومي من الإعدادات")
            kept, _blocked = within_quota(db, wanted, when, draft.id)
            if kept:
                break
            after = when + timedelta(minutes=1)
        if not kept:
            raise ValueError("اكتملت حدود النشر لكل منصات هذا المنشور في الأيام القادمة")
    else:
        problem = check(db, when, draft.id)
        if problem:
            raise ValueError(problem)
        kept, blocked = within_quota(db, wanted, when, draft.id)
        if not kept:
            raise ValueError("؛ ".join(blocked.values()))
    draft.publish_targets = kept
    draft.status, draft.scheduled_at, draft.error = "scheduled", when, None
    db.flush()
    return when


def plan_view(db: Session) -> dict[str, Any]:
    """Settings + today's slots, for the calendar."""
    cfg = config(db)
    today = datetime.now(cfg["tz"]).date()
    return {"posts_per_day": cfg["per_day"], "day_start": cfg["start"], "day_end": cfg["end"],
            "min_gap_hours": cfg["gap"], "timezone": str(cfg["tz"]),
            "today_slots": [s.astimezone(cfg["tz"]).strftime("%H:%M") for s in day_slots(cfg, today)]}


def run_autoplan() -> dict[str, int]:
    """Automation: put approved (and, if enabled, high-scoring) posts on the plan by themselves."""
    from ..db import session_scope
    import logging
    log = logging.getLogger(__name__)
    done = 0
    with session_scope() as db:
        pub = app_settings.get_section(db, "publishing")
        threshold = int(pub.get("auto_approve_min_relevance") or 0)
        candidates: list[Draft] = []
        if pub.get("auto_schedule_approved"):
            candidates += list(db.scalars(select(Draft).where(Draft.status == "approved", Draft.scheduled_at.is_(None))
                                          .order_by(Draft.created_at)))
        if threshold > 0:
            candidates += list(db.scalars(select(Draft).where(Draft.status == "pending_review",
                                                              Draft.relevance >= threshold)
                                          .order_by(Draft.relevance.desc(), Draft.created_at)))
        # the best posts take the limited places first (e.g. one post a week on LinkedIn)
        candidates.sort(key=lambda d: (-(d.relevance or 0), d.created_at))
        # an approved occasion greeting goes on its own day, never on the next free slot
        from . import occasions
        for d in db.scalars(select(Draft).where(Draft.status == "approved", Draft.scheduled_at.is_(None),
                                                Draft.origin == "occasion")).all():
            if occasions.schedule_post(db, d.id):
                done += 1
        for d in [c for c in candidates if c.origin != "occasion"][:20]:
            try:
                schedule(db, d)
                done += 1
            except ValueError as exc:
                log.info("autoplan skipped draft %s: %s", d.id, exc)
    return {"scheduled": done}
