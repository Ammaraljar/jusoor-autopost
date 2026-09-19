"""FastAPI entry point."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db, session_scope
from .routes import brands, drafts, planning, sources, system
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
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (system.router, drafts.router, sources.router, planning.router, brands.router):
    app.include_router(r)

if settings.storage_backend == "local":
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
