"""Database engine, session handling and ORM models.

Works with Supabase Postgres in production (DATABASE_URL=postgresql+psycopg://...)
and SQLite for local development / tests.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for col in self.__table__.columns:
            val = getattr(self, col.key)
            if isinstance(val, datetime):
                if val.tzinfo is None:
                    val = val.replace(tzinfo=timezone.utc)
                val = val.isoformat()
            elif isinstance(val, date):
                val = val.isoformat()
            out[col.key] = val
        return out


class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    handle: Mapped[str] = mapped_column(String(120), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    voice: Mapped[str] = mapped_column(Text, default="")
    colors: Mapped[dict[str, Any]] = mapped_column(default=dict)
    font_family: Mapped[str] = mapped_column(String(60), default="Cairo")
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_placement: Mapped[str] = mapped_column(String(20), default="top-left")
    card_style: Mapped[str] = mapped_column(String(20), default="frosted")
    color_mode: Mapped[str | None] = mapped_column(String(20), nullable=True, default="auto")      # auto | brand
    logo_backdrop: Mapped[str | None] = mapped_column(String(20), nullable=True, default="auto")   # auto | always | never
    cta_text: Mapped[str] = mapped_column(Text, default="")
    publish_config: Mapped[dict[str, Any]] = mapped_column(default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(20), default="website")  # website | rss
    base_url: Mapped[str] = mapped_column(String(500), default="")
    feed_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_urls: Mapped[list[Any]] = mapped_column(default=list)
    link_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    link_pattern: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    category: Mapped[str] = mapped_column(String(60), default="travel")
    country: Mapped[str] = mapped_column(String(60), default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=120)
    max_items_per_run: Mapped[int] = mapped_column(Integer, default=5)
    health: Mapped[str] = mapped_column(String(20), default="unknown")  # healthy | failing | unknown
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url", name="uq_articles_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    url: Mapped[str] = mapped_column(String(800))
    title: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), default="", index=True)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | drafted | skipped | error
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    objective: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(20), default="#C6A23C")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CalendarItem(Base):
    __tablename__ = "calendar_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    date: Mapped[date] = mapped_column(Date)
    time: Mapped[str] = mapped_column(String(5), default="10:00")
    topic: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    content_type: Mapped[str] = mapped_column(String(30), default="travel")
    platform: Mapped[str] = mapped_column(String(30), default="instagram")
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned | generated | scheduled | published
    draft_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"), nullable=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    calendar_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="source")  # source | calendar | manual
    source_name: Mapped[str] = mapped_column(String(160), default="")
    source_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    original_title: Mapped[str] = mapped_column(Text, default="")
    original_body: Mapped[str] = mapped_column(Text, default="")
    original_image_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    original_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="ar")
    tone: Mapped[str] = mapped_column(String(30), default="friendly")
    content_type: Mapped[str] = mapped_column(String(30), default="news")
    platform: Mapped[str] = mapped_column(String(30), default="instagram")
    hook: Mapped[str] = mapped_column(Text, default="")
    subtitle: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(Text, default="")
    first_comment: Mapped[str] = mapped_column(Text, default="")
    cta: Mapped[str] = mapped_column(Text, default="")
    image_keywords: Mapped[str] = mapped_column(Text, default="")
    relevance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)   # engine / ensemble verdict
    palette: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)   # colours taken from the photo
    badge: Mapped[str] = mapped_column(String(30), default="news")
    status: Mapped[str] = mapped_column(String(20), default="generating", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_targets: Mapped[list[Any]] = mapped_column(default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    slides: Mapped[list["Slide"]] = relationship(back_populates="draft", cascade="all, delete-orphan",
                                                 order_by="Slide.position")


class Slide(Base):
    __tablename__ = "slides"
    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(20), default="content")  # cover | content | cta
    heading: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    background_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    draft: Mapped[Draft] = relationship(back_populates="slides")


class PublishLog(Base):
    __tablename__ = "publish_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    platform: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))  # success | error
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    response: Mapped[dict[str, Any]] = mapped_column(default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


def _make_engine():
    url = get_settings().database_url
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "")
        if path and path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Columns added after the first release: (table, column, SQL type). create_all() never alters
# existing tables, so these are added in place on start-up.
_ADDED_COLUMNS = [
    ("drafts", "ai_meta", "JSON"),
    ("drafts", "palette", "JSON"),
    ("brands", "color_mode", "VARCHAR(20)"),
    ("brands", "logo_backdrop", "VARCHAR(20)"),
]


def _migrate() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, sql_type in _ADDED_COLUMNS:
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate()


@contextmanager
def session_scope() -> Iterator:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI dependency."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
