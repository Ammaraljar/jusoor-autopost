"""Media storage: local disk (dev) or Supabase Storage public bucket (production).

Social platforms (Meta, Buffer) need a PUBLIC https URL for every image,
so production must use Supabase Storage or a public PUBLIC_BASE_URL.
"""
from __future__ import annotations

import os

import httpx

from ..config import get_settings


def _local_path(key: str) -> str:
    s = get_settings()
    path = os.path.abspath(os.path.join(s.media_dir, key))
    if not path.startswith(os.path.abspath(s.media_dir)):
        raise ValueError("invalid storage key")
    return path


def save_bytes(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    """Store bytes under key and return the public URL."""
    s = get_settings()
    if s.storage_backend == "supabase":
        url = f"{s.supabase_url}/storage/v1/object/{s.supabase_bucket}/{key}"
        headers = {
            "Authorization": f"Bearer {s.supabase_service_role_key}",
            "apikey": s.supabase_service_role_key,
            "Content-Type": content_type,
            "x-upsert": "true",
            "Cache-Control": "max-age=3600",
        }
        resp = httpx.post(url, content=data, headers=headers, timeout=60)
        resp.raise_for_status()
        return public_url(key)
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return public_url(key)


def read_bytes(key: str) -> bytes:
    s = get_settings()
    if s.storage_backend == "supabase":
        resp = httpx.get(public_url(key), timeout=60)
        resp.raise_for_status()
        return resp.content
    with open(_local_path(key), "rb") as fh:
        return fh.read()


def delete(key: str) -> None:
    s = get_settings()
    try:
        if s.storage_backend == "supabase":
            httpx.request("DELETE", f"{s.supabase_url}/storage/v1/object/{s.supabase_bucket}",
                          json={"prefixes": [key]},
                          headers={"Authorization": f"Bearer {s.supabase_service_role_key}",
                                   "apikey": s.supabase_service_role_key}, timeout=30)
        else:
            os.remove(_local_path(key))
    except Exception:
        pass


def public_url(key: str) -> str:
    s = get_settings()
    if s.storage_backend == "supabase":
        return f"{s.supabase_url}/storage/v1/object/public/{s.supabase_bucket}/{key}"
    return f"{s.public_base_url.rstrip('/')}/media/{key}"


def own_key(url: str | None) -> str | None:
    """The storage key when a URL points at our own media (so it can be read without HTTP)."""
    if not url:
        return None
    s = get_settings()
    prefixes = [f"{s.public_base_url.rstrip('/')}/media/", "/media/"]
    if s.supabase_url:
        prefixes.append(f"{s.supabase_url.rstrip('/')}/storage/v1/object/public/{s.supabase_bucket}/")
    for prefix in prefixes:
        if url.startswith(prefix):
            key = url[len(prefix):].split("?")[0]
            return key or None
    return None


def is_publicly_reachable() -> bool:
    """True when stored media URLs can be fetched by Meta/Buffer servers."""
    s = get_settings()
    if s.storage_backend == "supabase":
        return bool(s.supabase_url and s.supabase_service_role_key)
    base = s.public_base_url.lower()
    return base.startswith("https://") and "localhost" not in base and "127.0.0.1" not in base
