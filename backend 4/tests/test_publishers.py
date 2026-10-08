import asyncio
import json

import httpx
import pytest

from app.config import get_settings
from app.publishers import buffer as buffer_mod
from app.publishers import meta as meta_mod
from app.publishers import uploadpost as up_mod
from app.publishers.base import PublishRequest


def _req(**kw):
    base = dict(draft_id=1, caption="نص #سفر", image_urls=["https://x/1.jpg", "https://x/2.jpg"],
                image_keys=["k1", "k2"], platforms=["instagram", "facebook"], brand_config={}, first_comment="")
    base.update(kw)
    return PublishRequest(**base)


def _patch_async_client(monkeypatch, module, handler):
    real = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real(*a, **kw)
    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


def test_buffer_publishes_to_matching_channels(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "buffer_api_key", "tok")
    sent = []

    def handler(request):
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer tok"
        q = body["query"]
        if "organizations" in q:
            return httpx.Response(200, json={"data": {"account": {"organizations": [{"id": "o1", "name": "J"}]}}})
        if "channels" in q:
            return httpx.Response(200, json={"data": {"channels": [
                {"id": "c-ig", "name": "jusoortravel", "service": "instagram", "isDisconnected": False},
                {"id": "c-fb", "name": "Jusoor", "service": "facebook", "isDisconnected": False}]}})
        sent.append(body["variables"]["input"])
        return httpx.Response(200, json={"data": {"createPost": {"post": {"id": "p-" + body["variables"]["input"]["channelId"]}}}})

    _patch_async_client(monkeypatch, buffer_mod, handler)
    res = asyncio.run(buffer_mod.BufferPublisher().publish(_req()))
    assert [r.ok for r in res] == [True, True]
    assert sent[0]["channelId"] == "c-ig" and sent[0]["assets"][0] == {"image": {"url": "https://x/1.jpg"}}
    assert sent[0]["metadata"]["instagram"]["type"] == "post"


def test_buffer_retries_without_metadata(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "buffer_api_key", "tok")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        if "organizations" in body["query"]:
            return httpx.Response(200, json={"data": {"account": {"organizations": [{"id": "o1", "name": "J"}]}}})
        if "channels" in body["query"]:
            return httpx.Response(200, json={"data": {"channels": [
                {"id": "c-ig", "name": "ig", "service": "instagram", "isDisconnected": False}]}})
        calls.append(body["variables"]["input"])
        if "metadata" in body["variables"]["input"]:
            return httpx.Response(200, json={"errors": [{"message": "bad metadata"}]})
        return httpx.Response(200, json={"data": {"createPost": {"post": {"id": "p1"}}}})

    _patch_async_client(monkeypatch, buffer_mod, handler)
    res = asyncio.run(buffer_mod.BufferPublisher().publish(_req(platforms=["instagram", "linkedin"])))
    assert res[0].ok and len(calls) == 2
    assert not res[1].ok and "linkedin" in res[1].error


def test_meta_carousel_and_facebook(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "meta_access_token", "sys")
    log = []

    def handler(request):
        path = request.url.path.split("/", 2)[-1]
        form = dict(httpx.QueryParams(request.content.decode())) if request.method == "POST" else dict(request.url.params)
        log.append((request.method, path, form))
        if request.method == "GET" and path == "PAGE":
            return httpx.Response(200, json={"access_token": "page-tok"})
        if request.method == "GET":
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if path == "PAGE/photos":
            return httpx.Response(200, json={"id": f"ph{len(log)}"})
        if path == "PAGE/feed":
            return httpx.Response(200, json={"id": "PAGE_post"})
        if path == "IG/media":
            return httpx.Response(200, json={"id": f"cont{len(log)}"})
        if path == "IG/media_publish":
            return httpx.Response(200, json={"id": "igmedia"})
        return httpx.Response(400, json={"error": {"message": "unexpected " + path}})

    _patch_async_client(monkeypatch, meta_mod, handler)
    res = asyncio.run(meta_mod.MetaPublisher().publish(
        _req(brand_config={"meta": {"page_id": "PAGE", "ig_user_id": "IG"}})))
    assert all(r.ok for r in res), [r.error for r in res]
    carousel = [f for m, p, f in log if p == "IG/media" and f.get("media_type") == "CAROUSEL"][0]
    assert len(carousel["children"].split(",")) == 2 and carousel["access_token"] == "page-tok"
    feed = [f for m, p, f in log if p == "PAGE/feed"][0]
    assert "attached_media[1]" in feed


def test_meta_requires_ids(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "meta_access_token", "sys")
    _patch_async_client(monkeypatch, meta_mod, lambda r: httpx.Response(500))
    res = asyncio.run(meta_mod.MetaPublisher().publish(_req()))
    assert not any(r.ok for r in res)


def test_uploadpost_multipart(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploadpost_api_key", "up")
    monkeypatch.setattr(up_mod.storage, "read_bytes", lambda k: b"jpegdata")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["url"] = str(request.url)
        seen["body"] = request.content
        return httpx.Response(200, json={"success": True, "request_id": "r1"})

    _patch_async_client(monkeypatch, up_mod, handler)
    res = asyncio.run(up_mod.UploadPostPublisher().publish(
        _req(brand_config={"uploadpost": {"user": "jusoor", "facebook_page_id": "123"}}, first_comment="سؤال؟")))
    assert all(r.ok for r in res)
    assert seen["auth"] == "Apikey up" and seen["url"].endswith("/api/upload_photos")
    body = seen["body"]
    assert body.count(b'name="photos[]"') == 2 and b'name="facebook_page_id"' in body
    assert b'name="first_comment"' in body


def test_uploadpost_needs_user(client, monkeypatch):
    res = asyncio.run(up_mod.UploadPostPublisher().publish(_req()))
    assert not any(r.ok for r in res)
