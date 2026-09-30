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
from .routes import auth_routes, brands, drafts, planning, sources, system
from .services.jobs import jobs
from .services.pipeline import ensure_default_brand
from .services.renderer import renderer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session_scope() as db:
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

for r in (system.router, auth_routes.router, drafts.router, sources.router, planning.router, brands.router):
    app.include_router(r)

if settings.storage_backend == "local":
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
