"""Common publisher interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublishRequest:
    draft_id: int
    caption: str
    image_urls: list[str]           # public URLs, in slide order
    image_keys: list[str]           # storage keys (for providers that want file uploads)
    platforms: list[str]
    brand_config: dict[str, Any]
    first_comment: str = ""
    title: str = ""


@dataclass
class PlatformResult:
    platform: str
    ok: bool
    external_id: str | None = None
    error: str | None = None
    response: dict[str, Any] = field(default_factory=dict)


class PublishError(Exception):
    pass


class Publisher:
    name = "base"
    platforms: tuple[str, ...] = ()

    def configured(self) -> bool:
        raise NotImplementedError

    async def status(self) -> dict[str, Any]:
        return {"configured": self.configured()}

    async def publish(self, req: PublishRequest) -> list[PlatformResult]:
        raise NotImplementedError
