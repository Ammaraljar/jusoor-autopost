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

    # Auth (Supabase)
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
    def allowed_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
