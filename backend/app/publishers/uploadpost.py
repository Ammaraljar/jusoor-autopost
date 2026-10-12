"""upload-post.com publisher (https://docs.upload-post.com).

Photo posts go to /api/upload_photos. Discord and Telegram are tried there too; if upload-post
refuses photos for them, the post is sent through /api/upload_text with the caption and the links
of the images. YouTube takes videos only, so it is not offered for image posts.
"""
from __future__ import annotations

from typing import Any

import httpx

from ..config import get_settings
from ..services import credentials, storage
from .base import PlatformResult, Publisher, PublishRequest

# upload-post platform ids, in the order shown in the dashboard
PLATFORMS = ("instagram", "facebook", "linkedin", "tiktok", "x", "threads", "pinterest", "bluesky",
             "reddit", "google_business", "telegram", "discord")
MAX_IMAGES = {"bluesky": 4, "google_business": 1, "pinterest": 5, "x": 4}
TEXT_FALLBACK = {"telegram", "discord"}


class UploadPostPublisher(Publisher):
    name = "uploadpost"
    platforms = PLATFORMS

    def configured(self) -> bool:
        return bool(credentials.current()["uploadpost_api_key"])

    def _headers(self) -> dict[str, str]:
        key = credentials.current()["uploadpost_api_key"]
        return {"Authorization": f"Apikey {key}"}

    async def status(self) -> dict[str, Any]:
        return {"configured": self.configured()}

    def _missing(self, platform: str, cfg: dict) -> str | None:
        """A setting the platform needs that the brand has not filled in."""
        if platform == "facebook" and not cfg.get("facebook_page_id"):
            return "facebook_page_id مطلوب لـ upload-post"
        if platform == "pinterest" and not cfg.get("pinterest_board_id"):
            return "أضف رقم لوحة Pinterest (Board ID) في الهوية البصرية ← upload-post"
        if platform == "reddit" and not cfg.get("subreddit"):
            return "أضف اسم مجتمع Reddit (Subreddit) في الهوية البصرية ← upload-post"
        return None

    def _fields(self, platform: str, req: PublishRequest, cfg: dict) -> dict[str, Any]:
        title = (req.title or req.caption.split("\n")[0])[:300]
        data: dict[str, Any] = {"user": cfg["user"], "platform[]": [platform],
                                "title": req.caption, "description": req.caption}
        if platform == "facebook":
            data["facebook_page_id"] = str(cfg["facebook_page_id"])
        elif platform == "linkedin" and cfg.get("linkedin_page_id"):
            data["target_linkedin_page_id"] = str(cfg["linkedin_page_id"])
        elif platform == "pinterest":
            data.update(pinterest_board_id=str(cfg["pinterest_board_id"]), title=title[:100],
                        pinterest_description=req.caption[:500])
        elif platform == "reddit":
            data.update(subreddit=str(cfg["subreddit"]).removeprefix("r/").strip("/"), title=title)
        elif platform == "google_business" and cfg.get("gbp_location_id"):
            data["gbp_location_id"] = str(cfg["gbp_location_id"])
        if req.first_comment and platform not in ("pinterest", "google_business", "telegram", "discord"):
            data["first_comment"] = req.first_comment
        return data

    async def _post(self, path: str, data: dict, files: list | None = None) -> tuple[int, dict]:
        url = f"{get_settings().uploadpost_api_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, data=data, files=files or None, headers=self._headers())
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:500]}
        return resp.status_code, body if isinstance(body, dict) else {"raw": body}

    @staticmethod
    def _failed(status: int, body: dict) -> str | None:
        if status >= 400 or body.get("success") is False:
            return str(body.get("message") or body.get("error") or f"HTTP {status}")
        return None

    @staticmethod
    def _result(platform: str, body: dict) -> PlatformResult:
        per = body.get("results") if isinstance(body.get("results"), dict) else {}
        r = per.get(platform, {}) if per else {}
        ok = r.get("success", True) if isinstance(r, dict) else True
        ext = (r.get("post_id") or r.get("url")) if isinstance(r, dict) else None
        return PlatformResult(platform, bool(ok), external_id=ext or body.get("request_id"),
                              error=None if ok else str(r.get("error", "failed")), response=body)

    async def publish(self, req: PublishRequest) -> list[PlatformResult]:
        cfg = req.brand_config.get("uploadpost") or {}
        if not cfg.get("user"):
            return [PlatformResult(p, False, error="لم يُحدَّد اسم مستخدم upload-post للعلامة") for p in req.platforms]
        results: list[PlatformResult] = []
        for platform in req.platforms:
            if platform not in PLATFORMS:
                msg = ("يوتيوب يقبل الفيديو فقط، والمنشور صور" if platform == "youtube"
                       else "منصة غير مدعومة في upload-post")
                results.append(PlatformResult(platform, False, error=msg))
                continue
            missing = self._missing(platform, cfg)
            if missing:
                results.append(PlatformResult(platform, False, error=missing))
                continue
            data = self._fields(platform, req, cfg)
            keys = req.image_keys[:MAX_IMAGES.get(platform, 10)]
            files = [("photos[]", (f"slide-{i + 1}.jpg", storage.read_bytes(k), "image/jpeg"))
                     for i, k in enumerate(keys)]
            status, body = await self._post("/api/upload_photos", data, files)
            err = self._failed(status, body)
            if err and platform in TEXT_FALLBACK:
                # photos not accepted for this channel: send the text with the image links instead
                links = "\n".join(u for u in req.image_urls[:MAX_IMAGES.get(platform, 10)] if u)
                text = f"{req.caption}\n\n{links}".strip()
                status, body = await self._post("/api/upload_text", {**data, "title": text, "description": text})
                err = self._failed(status, body)
            if err:
                results.append(PlatformResult(platform, False, error=f"upload-post: {err}", response=body))
            else:
                results.append(self._result(platform, body))
        return results
