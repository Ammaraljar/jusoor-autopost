"""Application configuration loaded from environment variables (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "Jusoor AutoPost"
    environment: str = "development"
    database_url: str = "sqlite:///./data/autopost.db"
    public_base_url: str = "http://localhost:8000"   # used for locally stored media URLs
    cors_origins: str = "http://localhost:5173"
    timezone: str = "Asia/Kuala_Lumpur"

    # Auth — internal (email + password from the environment) or Supabase
    admin_email: str = ""
    admin_password: str = ""
    secret_key: str = ""                # signs the dashboard session token
    session_hours: int = 720            # 30 days

    # Auth (Supabase — only when internal credentials are not set)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    allowed_emails: str = ""          # comma separated allow-list; empty = any Supabase user
    auth_disabled: bool = False       # local development only

    # Storage
    storage_backend: str = "local"    # local | supabase
    media_dir: str = "./data/media"
    supabase_bucket: str = "autopost-media"

    # AI — provider can be Claude directly, or any OpenAI-compatible server (AnythingLLM, Ollama, LM Studio, …)
    ai_provider: str = "anthropic"          # anthropic | openai_compatible
    ai_base_url: str = ""                   # e.g. https://llm.jusoor.example/api/v1/openai
    ai_api_key: str = ""
    ai_model: str = ""                      # AnythingLLM: the workspace slug
    ai_json_mode: bool = True               # send response_format=json_object on the first try
    ai_timeout_seconds: int = 180
    # Legacy / Claude-specific names (still supported)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    @property
    def is_openai_compatible(self) -> bool:
        return self.ai_provider.lower() in ("openai_compatible", "openai", "anythingllm")

    @property
    def ai_key(self) -> str:
        """The API key of the active provider."""
        return self.ai_api_key or ("" if self.is_openai_compatible else self.anthropic_api_key)

    @property
    def ai_model_name(self) -> str:
        return self.ai_model or (self.anthropic_model if not self.is_openai_compatible else "")

    # Images
    pexels_api_key: str = ""

    # Publishers
    buffer_api_key: str = ""
    buffer_api_url: str = "https://api.buffer.com"
    meta_access_token: str = ""
    meta_graph_version: str = "v25.0"
    uploadpost_api_key: str = ""
    uploadpost_api_url: str = "https://api.upload-post.com"

    # Scheduler
    scheduler_enabled: bool = True

    @property
    def auth_mode(self) -> str:
        """internal = e-mail/password kept in the environment, supabase = Supabase Auth."""
        if self.auth_disabled:
            return "disabled"
        if self.admin_email and self.admin_password:
            return "internal"
        if self.supabase_url:
            return "supabase"
        return "unconfigured"

    @property
    def token_secret(self) -> str:
        """Key that signs session tokens; derived from the password when SECRET_KEY is unset."""
        if self.secret_key:
            return self.secret_key
        import hashlib
        return hashlib.sha256(f"jusoor-autopost::{self.admin_password}".encode()).hexdigest()

    @property
    def supabase_base(self) -> str:
        """Project URL without any path or trailing slash (people often paste .../rest/v1/)."""
        raw = (self.supabase_url or "").strip().rstrip("/")
        if not raw:
            return ""
        if not raw.startswith(("http://", "https://")):
            raw = "https://" + raw
        from urllib.parse import urlparse
        parts = urlparse(raw)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def anon_key_kind(self) -> str:
        """What kind of Supabase key SUPABASE_ANON_KEY holds — used by the health check."""
        key = (self.supabase_anon_key or "").strip()
        if not key:
            return "missing"
        if key.startswith("sb_publishable_"):
            return "publishable"
        if key.startswith("sb_secret_") or key.startswith("service_role"):
            return "secret_key_wrong"
        if key.startswith("eyJ"):
            import base64
            import json as _json
            try:
                payload = key.split(".")[1]
                data = _json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
                role = data.get("role", "")
            except Exception:  # noqa: BLE001
                return "jwt_unreadable"
            if role == "anon":
                return "anon"
            if role == "service_role":
                return "secret_key_wrong"
            return f"jwt_role_{role or 'unknown'}"
        return "unknown"

    @property
    def allowed_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
