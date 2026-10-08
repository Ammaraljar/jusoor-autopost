"""upload-post.com publisher (https://docs.upload-post.com)."""
from __future__ import annotations

from typing import Any

import httpx

from ..config import get_settings
from ..services import credentials
from ..services import storage
from .base import PlatformResult, PublishError, Publisher, PublishRequest


class UploadPostPublisher(Publisher):
    name = "uploadpost"
    platforms = ("instagram", "facebook", "linkedin", "tiktok", "x", "threads", "pinterest", "bluesky")

    def configured(self) -> bool:
        return bool(credentials.current()["uploadpost_api_key"])

    def _headers(self) -> dict[str, str]:
        key = credentials.current()["uploadpost_api_key"]
        return {"Authorization": f"Apikey {key}"}

    async def status(self) -> dict[str, Any]:
        return {"configured": self.configured()}

    async def publish(self, req: PublishRequest) -> list[PlatformResult]:
        cfg = req.brand_config.get("uploadpost") or {}
        user = cfg.get("user")
        if not user:
            return [PlatformResult(p, False, error="لم يُحدَّد اسم مستخدم upload-post للعلامة") for p in req.platforms]
        unsupported = [p for p in req.platforms if p not in self.platforms]
        platforms = [p for p in req.platforms if p in self.platforms]
        results = [PlatformResult(p, False, error="منصة غير مدعومة في upload-post") for p in unsupported]
        if "facebook" in platforms and not cfg.get("facebook_page_id"):
            platforms.remove("facebook")
            results.append(PlatformResult("facebook", False, error="facebook_page_id مطلوب لـ upload-post"))
        if not platforms:
            return results

        data: dict[str, Any] = {"user": user, "title": req.caption, "description": req.caption,
                                "platform[]": platforms}
        if cfg.get("facebook_page_id") and "facebook" in platforms:
            data["facebook_page_id"] = str(cfg["facebook_page_id"])
        if req.first_comment:
            data["first_comment"] = req.first_comment
        files = [("photos[]", (f"slide-{i + 1}.jpg", storage.read_bytes(k), "image/jpeg"))
                 for i, k in enumerate(req.image_keys[:10])]
        url = f"{get_settings().uploadpost_api_url.rstrip('/')}/api/upload_photos"
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, data=data, files=files, headers=self._headers())
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:500]}
        if resp.status_code >= 400 or body.get("success") is False:
            err = body.get("message") or body.get("error") or f"HTTP {resp.status_code}"
            return results + [PlatformResult(p, False, error=f"upload-post: {err}", response=body) for p in platforms]

        per_platform = body.get("results") if isinstance(body.get("results"), dict) else {}
        for p in platforms:
            r = per_platform.get(p, {}) if per_platform else {}
            ok = r.get("success", True) if isinstance(r, dict) else True
            ext = (r.get("post_id") or r.get("url")) if isinstance(r, dict) else None
            results.append(PlatformResult(p, bool(ok), external_id=ext or body.get("request_id"),
                                          error=None if ok else str(r.get("error", "failed")), response=body))
        return results

