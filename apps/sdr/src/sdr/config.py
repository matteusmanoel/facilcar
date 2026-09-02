"""Application settings (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Env vars map automatically (e.g. database_url ← DATABASE_URL)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://postgres:postgres@localhost:5432/facilcar"
    redis_url: str = "redis://localhost:6379/0"

    sdr_webhook_secret: str = "change-me-local-secret"
    julia_enabled: bool = False
    sdr_transport_mode: Literal["vercel_relay", "direct"] = "vercel_relay"

    evolution_api_url: str = "http://localhost:8081"
    evolution_api_key: str = ""
    evolution_sdr_instance: str = "facilcar-sdr"

    openai_api_key: str = ""
    sdr_understanding_model: str = "gpt-4.1-mini"
    sdr_response_model: str = "gpt-4.1-mini"
    sdr_vision_model: str = "gpt-4o"
    # sandbox: may include failure_code in customer-facing recovery.
    # production: tool/media failures stay silent so a human can take over.
    sdr_environment: Literal["sandbox", "production"] = "sandbox"

    sdr_debounce_ms: int = Field(default=1500)
    sdr_lock_ttl_seconds: int = Field(default=60)
    sdr_max_turns_in_context: int = Field(default=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()
