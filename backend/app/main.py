"""FastAPI entry point."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db, session_scope
from .routes import auth_routes, brands, drafts, media, planning, sources, system, team
from .services.jobs import jobs
from .services.pipeline import ensure_default_brand
from .services.renderer import renderer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .db import Organization, use_org
    from .services import tenancy
    tenancy.bootstrap()
    with session_scope() as db:
        org_ids = [o.id for o in db.query(Organization).all()]
    for oid in org_ids:
        with use_org(oid), session_scope() as db:
            ensure_default_brand(db)
    jobs.start()
    yield
    jobs.stop()
    await renderer.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan,
              docs_url="/api/docs" if settings.environment != "production" else None, redoc_url=None)


@app.middleware("http")
async def json_errors(request: Request, call_next):
    """Turn crashes into JSON *inside* the CORS layer, so the browser shows the real message
    instead of a misleading CORS error."""
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("app").exception("unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": f"خطأ داخلي في الخادم: {str(exc)[:300]}"})


# Added after the error middleware so CORS wraps it (the last middleware added is the outermost).
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_origin_regex=settings.cors_origin_regex or None, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# Compress JSON (draft lists, articles) — much faster on mobile connections
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
app.add_middleware(GZipMiddleware, minimum_size=1024)


class CachedStatic(StaticFiles):
    """Media keys are unique (a new name on every render), so browsers may cache them for good."""

    async def get_response(self, path, scope):  # noqa: ANN001
        resp = await super().get_response(path, scope)
        if resp.status_code == 200:
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


for r in (system.router, auth_routes.router, drafts.router, sources.router, planning.router, brands.router,
          team.router, team.admin, media.router):
    app.include_router(r)

if settings.storage_backend == "local":
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount("/media", CachedStatic(directory=settings.media_dir), name="media")
