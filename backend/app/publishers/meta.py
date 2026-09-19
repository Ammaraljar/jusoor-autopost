"""Direct publishing through the Meta Graph API (Facebook Page + Instagram professional account)."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ..config import get_settings
from .base import PlatformResult, PublishError, Publisher, PublishRequest


class MetaPublisher(Publisher):
    name = "meta"
    platforms = ("facebook", "instagram")

    def configured(self) -> bool:
        return bool(get_settings().meta_access_token)

    @property
    def base(self) -> str:
        return f"https://graph.facebook.com/{get_settings().meta_graph_version}"

    async def _call(self, client: httpx.AsyncClient, method: str, path: str, **params: Any) -> dict[str, Any]:
        resp = await client.request(method, f"{self.base}/{path}", data=params if method == "POST" else None,
                                    params=params if method == "GET" else None)
        body = resp.json() if resp.content else {}
        if resp.status_code >= 400 or "error" in body:
            err = body.get("error", {})
            raise PublishError(f"Meta: {err.get('message', resp.text[:300])}")
        return body

    async def _page_token(self, client: httpx.AsyncClient, page_id: str) -> str:
        token = get_settings().meta_access_token
        try:
            data = await self._call(client, "GET", page_id, fields="access_token", access_token=token)
            return data.get("access_token") or token
        except PublishError:
            return token   # the configured token may already be a page token

    async def status(self) -> dict[str, Any]:
        if not self.configured():
            return {"configured": False}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                me = await self._call(client, "GET", "me", fields="id,name",
                                      access_token=get_settings().meta_access_token)
            return {"configured": True, "connected": True, "account": me.get("name")}
        except Exception as exc:  # noqa: BLE001
            return {"configured": True, "connected": False, "error": str(exc)[:300]}

    async def publish(self, req: PublishRequest) -> list[PlatformResult]:
        cfg = req.brand_config.get("meta") or {}
        results: list[PlatformResult] = []
        async with httpx.AsyncClient(timeout=120) as client:
            for platform in req.platforms:
                try:
                    if platform == "facebook":
                        if not cfg.get("page_id"):
                            raise PublishError("لم يُحدَّد Facebook Page ID للعلامة")
                        results.append(await self._facebook(client, cfg["page_id"], req))
                    elif platform == "instagram":
                        if not cfg.get("ig_user_id"):
                            raise PublishError("لم يُحدَّد Instagram User ID للعلامة")
                        results.append(await self._instagram(client, cfg, req))
                    else:
                        results.append(PlatformResult(platform, False, error="Meta يدعم فيسبوك وإنستغرام فقط"))
                except PublishError as exc:
                    results.append(PlatformResult(platform, False, error=str(exc)))
        return results

    async def _facebook(self, client: httpx.AsyncClient, page_id: str, req: PublishRequest) -> PlatformResult:
        token = await self._page_token(client, page_id)
        media_ids = []
        for url in req.image_urls[:10]:
            photo = await self._call(client, "POST", f"{page_id}/photos", url=url, published="false",
                                     access_token=token)
            media_ids.append(photo["id"])
        params: dict[str, Any] = {"message": req.caption, "access_token": token}
        for i, mid in enumerate(media_ids):
            params[f"attached_media[{i}]"] = f'{{"media_fbid":"{mid}"}}'
        post = await self._call(client, "POST", f"{page_id}/feed", **params)
        if req.first_comment:
            try:
                await self._call(client, "POST", f"{post['id']}/comments", message=req.first_comment,
                                 access_token=token)
            except PublishError:
                pass
        return PlatformResult("facebook", True, external_id=post["id"], response=post)

    async def _wait_ready(self, client: httpx.AsyncClient, container_id: str, token: str) -> None:
        for _ in range(30):
            data = await self._call(client, "GET", container_id, fields="status_code", access_token=token)
            code = data.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise PublishError(f"Instagram container {code}")
            await asyncio.sleep(2)
        raise PublishError("Instagram container timeout")

    async def _instagram(self, client: httpx.AsyncClient, cfg: dict, req: PublishRequest) -> PlatformResult:
        ig = cfg["ig_user_id"]
        token = await self._page_token(client, cfg["page_id"]) if cfg.get("page_id") else get_settings().meta_access_token
        urls = req.image_urls[:10]
        if len(urls) == 1:
            container = await self._call(client, "POST", f"{ig}/media", image_url=urls[0], caption=req.caption,
                                         access_token=token)
        else:
            children = []
            for url in urls:
                item = await self._call(client, "POST", f"{ig}/media", image_url=url, is_carousel_item="true",
                                        access_token=token)
                children.append(item["id"])
            for cid in children:
                await self._wait_ready(client, cid, token)
            container = await self._call(client, "POST", f"{ig}/media", media_type="CAROUSEL",
                                         children=",".join(children), caption=req.caption, access_token=token)
        await self._wait_ready(client, container["id"], token)
        published = await self._call(client, "POST", f"{ig}/media_publish", creation_id=container["id"],
                                     access_token=token)
        if req.first_comment:
            try:
                await self._call(client, "POST", f"{published['id']}/comments", message=req.first_comment,
                                 access_token=token)
            except PublishError:
                pass
        return PlatformResult("instagram", True, external_id=published["id"], response=published)
