import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    APP_NAME: str = "DOGFOOD Hackathon Portal API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # API configuration
    API_PREFIX: str = "/api"
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # Database configuration
    # By default, use SQLite for zero-setup, self-contained offline execution.
    # Can be overridden by DATABASE_URL in .env to point to Postgres / Supabase.
    DATABASE_URL: str = "sqlite:///./portal.db"

    # Supabase credentials (from existing auth system)
    SUPABASE_PUBLIC_URL: Optional[str] = "http://localhost:8000"
    ANON_KEY: Optional[str] = None

    # Security & Auth
    SECRET_KEY: str = "dogfood-hackathon-portal-secret-key-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
