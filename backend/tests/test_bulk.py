"""Selecting many items and deciding at once — including permanent deletion."""
from app.db import Article, Draft, Source, session_scope


def _drafts(n, status="pending_review"):
    ids = []
    with session_scope() as db:
        for i in range(n):
            d = Draft(hook=f"h{i}", caption="c", status=status, origin="manual")
            db.add(d)
            db.flush()
            ids.append(d.id)
    return ids


def test_bulk_draft_actions(client):
    ids = _drafts(3)
    r = client.post("/api/drafts/bulk", json={"ids": ids[:2], "action": "approve"}).json()
    assert r["done"] == 2
    with session_scope() as db:
        assert [db.get(Draft, i).status for i in ids] == ["approved", "approved", "pending_review"]
    assert client.post("/api/drafts/bulk", json={"ids": ids, "action": "reject"}).json()["done"] == 3
    assert client.post("/api/drafts/bulk", json={"ids": ids, "action": "delete"}).json()["done"] == 3
    with session_scope() as db:
        assert all(db.get(Draft, i) is None for i in ids)
    assert client.post("/api/drafts/bulk", json={"ids": ids, "action": "explode"}).status_code == 400


def test_bulk_source_and_article_delete(client):
    sid = client.post("/api/sources", json={"name": "Bulk src", "listing_urls": ["https://ex.com/n"]}).json()["id"]
    with session_scope() as db:
        a = Article(source_id=sid, url="https://ex.com/bulk-a", title="t", body="b", status="new", fingerprint="fb")
        db.add(a)
        db.flush()
        aid = a.id
        d = Draft(hook="h", caption="c", status="pending_review", origin="source", source_id=sid, article_id=aid)
        db.add(d)
        db.flush()
        did = d.id
    assert client.post("/api/sources/bulk", json={"ids": [sid], "action": "disable"}).json()["done"] == 1
    assert client.post("/api/sources/bulk", json={"ids": [sid], "action": "delete"}).json()["done"] == 1
    with session_scope() as db:
        assert db.get(Source, sid) is None and db.get(Article, aid) is None
        assert db.get(Draft, did).source_id is None          # the post itself is kept
    client.delete(f"/api/drafts/{did}")


def test_bulk_calendar_delete(client):
    ids = [client.post("/api/calendar", json={"date": "2026-11-01", "topic": f"موضوع {i}"}).json()["id"] for i in range(2)]
    assert client.post("/api/calendar/bulk-delete", json={"ids": ids}).json()["done"] == 2
