"""Publisher registry."""
from .base import Publisher, PublishError
from .buffer import BufferPublisher
from .meta import MetaPublisher
from .uploadpost import UploadPostPublisher

REGISTRY: dict[str, type[Publisher]] = {
    "buffer": BufferPublisher,
    "meta": MetaPublisher,
    "uploadpost": UploadPostPublisher,
}


def get_publisher(name: str) -> Publisher:
    if name not in REGISTRY:
        raise PublishError(f"مزوّد نشر غير معروف: {name}")
    return REGISTRY[name]()
