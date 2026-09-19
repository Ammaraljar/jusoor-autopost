"""Buffer GraphQL API publisher (https://developers.buffer.com)."""
from __future__ import annotations

from typing import Any

import httpx

from ..config import get_settings
from .base import PlatformResult, PublishError, Publisher, PublishRequest

ORGS_QUERY = "query { account { organizations { id name } } }"
CHANNELS_QUERY = """query Channels($input: ChannelsInput!) {
  channels(input: $input) { id name service isDisconnected }
}"""
CREATE_POST = """mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt } }
    ... on MutationError { message }
  }
}"""


class BufferPublisher(Publisher):
    name = "buffer"
    platforms = ("instagram", "facebook", "linkedin", "tiktok", "x", "threads", "pinterest")

    def configured(self) -> bool:
        return bool(get_settings().buffer_api_key)

    async def _gql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        s = get_settings()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(s.buffer_api_url, json={"query": query, "variables": variables or {}},
                                     headers={"Authorization": f"Bearer {s.buffer_api_key}"})
        if resp.status_code >= 400:
            raise PublishError(f"Buffer HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        if body.get("errors"):
            raise PublishError("Buffer: " + "; ".join(e.get("message", "") for e in body["errors"]))
        return body.get("data") or {}

    async def list_channels(self) -> list[dict[str, Any]]:
        data = await self._gql(ORGS_QUERY)
        channels: list[dict[str, Any]] = []
        for org in data.get("account", {}).get("organizations", []):
            res = await self._gql(CHANNELS_QUERY, {"input": {"organizationId": org["id"]}})
            for ch in res.get("channels", []):
                channels.append({**ch, "organization": org["name"]})
        return channels

    async def status(self) -> dict[str, Any]:
        if not self.configured():
            return {"configured": False}
        try:
            return {"configured": True, "connected": True, "channels": await self.list_channels()}
        except Exception as exc:  # noqa: BLE001
            return {"configured": True, "connected": False, "error": str(exc)[:300]}

    async def publish(self, req: PublishRequest) -> list[PlatformResult]:
        from ..db import session_scope
        from ..services import app_settings

        with session_scope() as db:
            mode = app_settings.get_section(db, "publishing").get("buffer_mode", "shareNow")
        wanted_ids = set(req.brand_config.get("buffer_channel_ids") or [])
        channels = [c for c in await self.list_channels() if not c.get("isDisconnected")]
        results: list[PlatformResult] = []
        for platform in req.platforms:
            targets = [c for c in channels if c["service"] == platform and (not wanted_ids or c["id"] in wanted_ids)]
            if not targets:
                results.append(PlatformResult(platform, False, error=f"لا توجد قناة {platform} مربوطة في Buffer"))
                continue
            for ch in targets:
                results.append(await self._create(ch, platform, req, mode))
        return results

    async def _create(self, channel: dict, platform: str, req: PublishRequest, mode: str) -> PlatformResult:
        base_input: dict[str, Any] = {
            "channelId": channel["id"],
            "text": req.caption,
            "schedulingType": "automatic",
            "mode": mode,
            "assets": [{"image": {"url": u}} for u in req.image_urls[:10]],
        }
        meta: dict[str, Any] = {}
        if platform == "instagram":
            meta = {"instagram": {"type": "post", "shouldShareToFeed": True,
                                  **({"firstComment": req.first_comment} if req.first_comment else {})}}
        elif platform == "facebook":
            meta = {"facebook": {"type": "post",
                                 **({"firstComment": req.first_comment} if req.first_comment else {})}}
        attempts = [{**base_input, "metadata": meta}, base_input] if meta else [base_input]
        last_error = ""
        for payload in attempts:
            try:
                data = (await self._gql(CREATE_POST, {"input": payload})).get("createPost") or {}
            except PublishError as exc:
                last_error = str(exc)
                continue
            if data.get("post"):
                return PlatformResult(platform, True, external_id=data["post"]["id"],
                                      response={"channel": channel["name"], **data})
            last_error = data.get("message", "Buffer رفض المنشور")
        return PlatformResult(platform, False, error=last_error, response={"channel": channel["name"]})
