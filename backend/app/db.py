"""Database engine, session handling and ORM models.

Works with Supabase Postgres in production (DATABASE_URL=postgresql+psycopg://...)
and SQLite for local development / tests.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
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


# ------------------------------------------------------------------ multi-tenancy
# The organisation the current request / job works for. Every tenant table is filtered by it
# automatically (see _scope_to_org below), so a company only ever sees its own data.
current_org: ContextVar[int | None] = ContextVar("current_org", default=None)


@contextmanager
def use_org(org_id: int | None):
    token = current_org.set(org_id)
    try:
        yield
    finally:
        current_org.reset(token)


class TenantMixin:
    org_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    industry: Mapped[str] = mapped_column(String(40), default="travel")
    language: Mapped[str] = mapped_column(String(5), default="ar")       # main posting language
    dialect: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")   # active | suspended
    plan: Mapped[str] = mapped_column(String(30), default="standard")
    max_users: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    password_hash: Mapped[str] = mapped_column(String(300), default="")
    role: Mapped[str] = mapped_column(String(20), default="editor")      # owner | editor | reviewer
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role, "org_id": self.org_id,
                "is_superadmin": self.is_superadmin, "active": self.active,
                "last_login_at": self.to_dict()["last_login_at"], "created_at": self.to_dict()["created_at"]}


class Brand(TenantMixin, Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    handle: Mapped[str] = mapped_column(String(120), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    voice: Mapped[str] = mapped_column(Text, default="")
    colors: Mapped[dict[str, Any]] = mapped_column(default=dict)
    font_family: Mapped[str] = mapped_column(String(60), default="Cairo")
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)      # the primary logo
    # every version of the logo: [{"key", "tone": color|light|dark, "name"}] — the best one is picked per slide
    logos: Mapped[list[Any] | None] = mapped_column(nullable=True)
    templates: Mapped[list[Any] | None] = mapped_column(nullable=True)        # card templates kept (empty = all)
    default_colors: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)  # identity read from the logo
    font_latin: Mapped[str | None] = mapped_column(String(60), nullable=True)   # font for English/Malay/French
    logo_placement: Mapped[str] = mapped_column(String(20), default="top-left")
    card_style: Mapped[str] = mapped_column(String(20), default="frosted")
    card_theme: Mapped[str | None] = mapped_column(String(20), nullable=True, default="magazine")  # magazine | classic
    design_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)   # makes each company's design unique
    color_mode: Mapped[str | None] = mapped_column(String(20), nullable=True, default="auto")      # auto | brand
    logo_backdrop: Mapped[str | None] = mapped_column(String(20), nullable=True, default="auto")   # auto | always | never
    cta_text: Mapped[str] = mapped_column(Text, default="")
    publish_config: Mapped[dict[str, Any]] = mapped_column(default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Source(TenantMixin, Base):
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
    purpose: Mapped[str] = mapped_column(String(20), default="news")   # news | programs (tour packages)
    dialect: Mapped[str | None] = mapped_column(String(20), nullable=True)   # overrides the default dialect
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


class Article(TenantMixin, Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("org_id", "url", name="uq_articles_org_url"),)
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


class Campaign(TenantMixin, Base):
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


class CalendarItem(TenantMixin, Base):
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
    dialect: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned | generated | scheduled | published
    draft_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Draft(TenantMixin, Base):
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
    palette: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)   # brand colour set of this post
    variants: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # per-platform text + images
    cover_thumb_url: Mapped[str | None] = mapped_column(String(800), nullable=True)  # small cover for lists
    dialect: Mapped[str | None] = mapped_column(String(20), nullable=True)   # msa | gulf | maghreb | algeria
    hook_highlight: Mapped[str | None] = mapped_column(String(200), nullable=True)  # title words shown in gold
    link_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)   # product/service page added to the text
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


class MediaAsset(TenantMixin, Base):
    """The company's own photo library — used when the sources have no suitable photo."""
    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(800))
    key: Mapped[str | None] = mapped_column(String(500), nullable=True)      # storage key when uploaded/copied
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)   # original link (Drive, Unsplash…)
    title: Mapped[str] = mapped_column(String(200), default="")
    tags: Mapped[str] = mapped_column(Text, default="")                      # space/comma separated keywords
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Product(TenantMixin, Base):
    """A product, service, course, programme or event read from the company's own website."""
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("org_id", "url", name="uq_products_org_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1000))
    name: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[str] = mapped_column(String(60), default="")
    currency: Mapped[str] = mapped_column(String(10), default="")
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="product")       # product | service | course | event | offer
    origin: Mapped[str] = mapped_column(String(20), default="page")        # shopify | woocommerce | jsonld | page
    status: Mapped[str] = mapped_column(String(20), default="new")         # new | drafted | skipped
    draft_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ContactList(TenantMixin, Base):
    """A mailing list (e.g. "Customers", "Newsletter sign-ups")."""
    __tablename__ = "contact_lists"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Contact(TenantMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_contacts_org_email"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    list_ids: Mapped[list[Any]] = mapped_column(default=list)
    fields: Mapped[dict[str, Any]] = mapped_column(default=dict)                 # extra columns from the import
    status: Mapped[str] = mapped_column(String(20), default="subscribed")       # subscribed | unsubscribed | bounced
    source: Mapped[str] = mapped_column(String(20), default="manual")           # manual | import
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Newsletter(TenantMixin, Base):
    __tablename__ = "newsletters"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(300), default="")
    preheader: Mapped[str] = mapped_column(String(300), default="")
    design: Mapped[str] = mapped_column(String(40), default="classic")
    kind: Mapped[str] = mapped_column(String(30), default="hybrid")     # curated | educational | … (newsletter_types)
    language: Mapped[str] = mapped_column(String(5), default="ar")
    font: Mapped[str] = mapped_column(String(40), default="")          # "" = safe system font (newsletter.EMAIL_FONTS)
    content: Mapped[dict[str, Any]] = mapped_column(default=dict)     # headline, intro, sections[], cta, ps
    list_ids: Mapped[list[Any]] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft|scheduled|sending|sent|failed
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Delivery(TenantMixin, Base):
    """One newsletter sent to one person: opens, clicks and unsubscribes are counted here."""
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    newsletter_id: Mapped[int] = mapped_column(ForeignKey("newsletters.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(200), default="")
    token: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")      # queued | sent | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answer: Mapped[str | None] = mapped_column(String(200), nullable=True)   # poll answer (survey newsletters)


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
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
            # WAL lets the dashboard read while the collector writes; NORMAL sync is safe with WAL.
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()
    return eng


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _install_tenant_scope() -> None:
    from sqlalchemy import event
    from sqlalchemy.orm import Session, with_loader_criteria

    @event.listens_for(Session, "do_orm_execute")
    def _scope_to_org(state):  # noqa: ANN001
        org = current_org.get()
        if org is None or state.execution_options.get("all_orgs"):
            return
        if state.is_select or state.is_update or state.is_delete:
            state.statement = state.statement.options(
                with_loader_criteria(TenantMixin, lambda cls: cls.org_id == org, include_aliases=True))

    @event.listens_for(Session, "before_flush")
    def _stamp_org(session, _ctx, _instances):  # noqa: ANN001
        org = current_org.get()
        if org is None:
            return
        for obj in session.new:
            if isinstance(obj, TenantMixin) and getattr(obj, "org_id", None) is None:
                obj.org_id = org


_install_tenant_scope()


# Columns added after the first release: (table, column, SQL type). create_all() never alters
# existing tables, so these are added in place on start-up.
_ADDED_COLUMNS = [
    ("drafts", "ai_meta", "JSON"),
    ("drafts", "palette", "JSON"),
    ("drafts", "variants", "JSON"),
    ("drafts", "cover_thumb_url", "VARCHAR(800)"),
    ("drafts", "dialect", "VARCHAR(20)"),
    ("sources", "purpose", "VARCHAR(20) DEFAULT 'news'"),
    ("sources", "dialect", "VARCHAR(20)"),
    ("calendar_items", "dialect", "VARCHAR(20)"),
    ("brands", "card_theme", "VARCHAR(20)"),
    ("brands", "design_seed", "INTEGER"),
    ("brands", "logos", "JSON"),
    ("brands", "templates", "JSON"),
    ("drafts", "link_url", "VARCHAR(1000)"),
    ("newsletters", "kind", "VARCHAR(30) DEFAULT 'hybrid'"),
    ("newsletters", "font", "VARCHAR(40) DEFAULT ''"),
    ("deliveries", "answer", "VARCHAR(200)"),
    ("brands", "default_colors", "JSON"),
    ("brands", "font_latin", "VARCHAR(60)"),
    ("brands", "org_id", "INTEGER"),
    ("sources", "org_id", "INTEGER"),
    ("articles", "org_id", "INTEGER"),
    ("campaigns", "org_id", "INTEGER"),
    ("calendar_items", "org_id", "INTEGER"),
    ("drafts", "org_id", "INTEGER"),
    ("drafts", "hook_highlight", "VARCHAR(200)"),
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
    _migrate_article_uniqueness()


def _migrate_article_uniqueness() -> None:
    """Article URLs were unique across the whole app; with several companies they are unique per company."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "articles" not in inspector.get_table_names():
        return
    uniques = inspector.get_unique_constraints("articles")
    if not any(u.get("column_names") == ["url"] for u in uniques):
        return
    cols = [c["name"] for c in inspector.get_columns("articles")]
    keep = [c for c in cols if c in Article.__table__.columns]
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA legacy_alter_table=ON"))      # keep other tables' references intact
            conn.execute(text("ALTER TABLE articles RENAME TO articles_old"))
            for idx in inspect(conn).get_indexes("articles_old"):
                conn.execute(text(f'DROP INDEX IF EXISTS "{idx["name"]}"'))
            Article.__table__.create(conn)
            names = ", ".join(keep)
            conn.execute(text(f"INSERT INTO articles ({names}) SELECT {names} FROM articles_old"))
            conn.execute(text("DROP TABLE articles_old"))
            conn.execute(text("PRAGMA legacy_alter_table=OFF"))
        else:
            for u in uniques:
                if u.get("column_names") == ["url"]:
                    conn.execute(text(f'ALTER TABLE articles DROP CONSTRAINT "{u["name"]}"'))
            conn.execute(text("ALTER TABLE articles ADD CONSTRAINT uq_articles_org_url UNIQUE (org_id, url)"))


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
