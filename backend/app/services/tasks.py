"""Long jobs started from the dashboard (reading a site, importing a photo library…).

The request returns at once with a job id and the page asks for the result, so a slow site never
holds a request open long enough to time out (which the browser then reports as a CORS error).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Awaitable, Callable

from ..db import current_org

_JOBS: dict[str, dict[str, Any]] = {}
MAX_SECONDS = 240


def new() -> str:
    if len(_JOBS) > 300:
        for k in list(_JOBS)[:150]:
            _JOBS.pop(k, None)
    job_id = uuid.uuid4().hex[:12]
    _JOBS[job_id] = {"status": "running", "org": current_org.get()}
    return job_id


async def run(job_id: str, work: Callable[[], Awaitable[Any]], timeout_message: str) -> None:
    org = _JOBS.get(job_id, {}).get("org")
    try:
        result = await asyncio.wait_for(work(), timeout=MAX_SECONDS)
        _JOBS[job_id] = {"status": "done", "result": result, "org": org}
    except asyncio.TimeoutError:
        _JOBS[job_id] = {"status": "failed", "error": timeout_message, "org": org}
    except ValueError as exc:
        _JOBS[job_id] = {"status": "failed", "error": str(exc), "org": org}
    except Exception as exc:  # noqa: BLE001
        _JOBS[job_id] = {"status": "failed", "error": str(exc)[:300], "org": org}


def get(job_id: str) -> dict[str, Any] | None:
    job = _JOBS.get(job_id)
    if job is None or job.get("org") not in (None, current_org.get()):
        return None
    return {k: v for k, v in job.items() if k != "org"}
