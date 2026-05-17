"""Application configuration."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> str | None:
    """Find .env file in current or parent directories."""
    # Check current directory first
    if Path(".env").exists():
        return ".env"
    # Check parent directory (for backend/ subdirectory)
    if Path("../.env").exists():
        return "../.env"
    # Check from this file's location (backend/src/agent_platform/)
    file_dir = Path(__file__).parent.parent.parent.parent
    env_path = file_dir / ".env"
    if env_path.exists():
        return str(env_path)
    return None


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Agent Runtime Platform"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: RedisDsn

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW: int = 60

    # Feishu (Lark) Bot Configuration
    FEISHU_APP_ID: Optional[str] = None
    FEISHU_APP_SECRET: Optional[str] = None
    FEISHU_BOT_WEBHOOK: Optional[str] = None
    FEISHU_WEBHOOK_SECRET: Optional[str] = None
    FEISHU_ENCRYPT_KEY: Optional[str] = None

    # App Base URL (for webhooks)
    APP_BASE_URL: str = "http://localhost:8000"

    @property
    def is_development(self) -> bool:
        return self.ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def feishu_enabled(self) -> bool:
        """Check if Feishu integration is enabled."""
        return bool(self.FEISHU_APP_ID and self.FEISHU_APP_SECRET)


@lru_cache
def get_settings() -> Settings:
    return Settings()
