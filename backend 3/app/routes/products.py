"""Products, services, courses and offers from the company's own website → one post each."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import RequireUser, RequireWriter
from ..db import Brand, Product, get_db, utcnow
from ..services import pipeline, products

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[RequireUser, RequireWriter])


@router.get("")
def list_products(db: Session = Depends(get_db)):
    return [p.to_dict() for p in db.scalars(select(Product).order_by(Product.status, Product.id.desc()))]


class SyncIn(BaseModel):
    url: str | None = None


@router.post("/sync")
async def sync(body: SyncIn, db: Session = Depends(get_db)):
    """Read the site (Shopify, WooCommerce or product pages) and add what is new."""
    url = (body.url or "").strip()
    if not url:
        brand = db.scalar(select(Brand).order_by(Brand.is_default.desc(), Brand.id))
        url = (brand.website or "").strip() if brand else ""
    if not url:
        raise HTTPException(400, "أضف رابط موقعك الإلكتروني (أو احفظه في الهوية البصرية أولًا)")
    found = await asyncio.to_thread(products.discover, url)
    added = updated = 0
    for item in found["items"]:
        row = db.scalar(select(Product).where(Product.url == item["url"]))
        if row is None:
            db.add(Product(**item))
            added += 1
        else:
            for k in ("name", "description", "price", "currency", "image_url", "kind"):
                if item.get(k):
                    setattr(row, k, item[k])
            row.updated_at = utcnow()
            updated += 1
    return {"found": len(found["items"]), "added": added, "updated": updated, "method": found["method"]}


def _get(db: Session, pid: int) -> Product:
    p = db.get(Product, pid)
    if p is None:
        raise HTTPException(404, "المنتج غير موجود")
    return p


@router.post("/{pid}/draft")
def make_post(pid: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    p = _get(db, pid)
    p.status = "drafted"
    db.commit()
    background.add_task(pipeline.draft_from_product, pid)
    return {"ok": True}


class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    action: str = Field(pattern="^(draft|skip|restore|delete)$")


@router.post("/bulk")
async def bulk(body: BulkIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Product).where(Product.id.in_(body.ids))))
    for p in rows:
        if body.action == "delete":
            db.delete(p)
        elif body.action == "skip":
            p.status = "skipped"
        elif body.action == "restore":
            p.status = "new"
        else:
            p.status = "drafted"
    db.commit()
    if body.action == "draft":
        async def run_all(ids: list[int]) -> None:
            for i in ids:                      # one after another: AI limits stay happy
                await pipeline.draft_from_product(i)
        background.add_task(run_all, [p.id for p in rows])
    return {"done": len(rows)}


@router.delete("/{pid}")
def delete(pid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, pid))
    return {"ok": True}
