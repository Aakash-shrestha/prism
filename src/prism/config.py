"""Central configuration for Prism.

Loads environment variables from .env and provides typed access to settings.
Importing this module is the canonical way to ensure env vars are loaded
before any other code runs.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings, populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # GitHub
    github_webhook_secret: str = Field(..., alias="GITHUB_WEBHOOK_SECRET")
    github_token: str = Field(..., alias="GITHUB_TOKEN")

    # Groq
    groq_api_key: SecretStr = Field(..., alias="GROQ_API_KEY")

    # App
    app_env: str = Field(default="development", alias="APP_ENV")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # database
    database_url: str = Field(default="postgresql+asyncpg://localhost/prism", alias="DATABASE_URL")


settings = Settings()
