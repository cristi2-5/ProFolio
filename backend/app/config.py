"""
Auto-Apply Backend — Application Configuration.

Loads all settings from environment variables using Pydantic BaseSettings.
Supports .env files for local development.

Tech Decisions (for the team):
    - LLM Provider: OpenAI GPT-4 (structured output, mature API)
    - Job API: Adzuna (free tier, legal, structured JSON responses)
    - File Storage: Local filesystem (S3-ready abstraction planned)
    - Auth: JWT tokens (HS256), OAuth stubs for Phase 2
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        app_name: Display name of the application.
        environment: Current environment (development, staging, production).
        database_url: PostgreSQL async connection string.
        secret_key: Secret key for JWT token signing.
        access_token_expire_minutes: JWT token expiration in minutes.
        algorithm: JWT signing algorithm.
        openai_api_key: OpenAI API key for GPT-4 agent calls.
        adzuna_app_id: Adzuna API application ID.
        adzuna_app_key: Adzuna API application key.
        upload_dir: Local directory for uploaded CV files.
        cors_origins: Allowed CORS origins for frontend.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "Auto-Apply API"
    environment: str = "development"

    # --- Database ---
    database_url: str = (
        "postgresql+asyncpg://autoapply:changeme@localhost:5432/autoapply_db"
    )

    # --- Authentication ---
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    # --- LLM (OpenAI GPT-4) ---
    openai_api_key: str = ""

    # --- Job API (Adzuna) ---
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # --- File Storage ---
    upload_dir: str = "./uploads"

    # --- CORS ---
    cors_origins: List[str] = ["http://localhost:5173"]

    # --- Job Scanner Scheduler ---
    job_scan_interval_hours: int = 24  # How often the cron scans all users
    job_scan_rate_limit_hours: int = 1  # Max manual scans per user per N hours


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
