"""Background job runner + APScheduler wiring."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..db import session_scope
from . import app_settings, pipeline, publishing, scheduling

log = logging.getLogger(__name__)


class Jobs:
    def __init__(self) -> None:
        self._running = False
        self.last_run: dict[str, Any] | None = None
        self.scheduler = None

    @property
    def busy(self) -> bool:
        return self._running

    async def run_collection(self, source_ids: list[int] | None = None,
                             window: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._running:
            return {"skipped": True}
        self._running = True
        try:
            started = datetime.now(timezone.utc)
            try:
                summary = await pipeline.run_collection_cycle(source_ids, window)
            except Exception as exc:  # noqa: BLE001
                log.exception("collection cycle failed")
                summary = {"error": str(exc)[:500]}
            self.last_run = {"started_at": started.isoformat(),
                             "finished_at": datetime.now(timezone.utc).isoformat(), **summary}
            return self.last_run
        finally:
            self._running = False

    async def scheduled_collection(self) -> None:
        with session_scope() as db:
            enabled = app_settings.get_section(db, "scheduler").get("scrape_enabled", True)
        if enabled:
            await self.run_collection(None)

    async def scheduled_autoplan(self) -> None:
        try:
            await asyncio.to_thread(scheduling.run_autoplan)
        except Exception:  # noqa: BLE001
            log.exception("autoplan failed")

    async def scheduled_publish(self) -> None:
        try:
            await publishing.publish_due()
        except Exception:  # noqa: BLE001
            log.exception("scheduled publish failed")

    def start(self) -> None:
        if not get_settings().scheduler_enabled:
            return
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self.scheduler = AsyncIOScheduler(timezone="UTC")
        # Sources decide their own interval; this tick only checks which ones are due.
        self.scheduler.add_job(self.scheduled_collection, "interval", minutes=10, id="collect",
                               max_instances=1, coalesce=True)
        self.scheduler.add_job(self.scheduled_publish, "interval", minutes=1, id="publish",
                               max_instances=1, coalesce=True)
        self.scheduler.add_job(self.scheduled_autoplan, "interval", minutes=5, id="autoplan",
                               max_instances=1, coalesce=True)
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler:
            self.scheduler.shutdown(wait=False)

    def state(self) -> dict[str, Any]:
        next_runs = {}
        if self.scheduler:
            for job in self.scheduler.get_jobs():
                next_runs[job.id] = job.next_run_time.isoformat() if job.next_run_time else None
        return {"running": self.busy, "scheduler": bool(self.scheduler), "next_runs": next_runs,
                "last_run": self.last_run}


jobs = Jobs()
