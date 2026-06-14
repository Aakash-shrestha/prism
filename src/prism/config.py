"""Central configuration for Prism.

Loads environment variables from .env and provides typed access to settings.
Importing this module is the canonical way to ensure env vars are loaded
before any other code runs.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
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


settings = Settings()
