# app/config.py
#
# DocLoop — centralised settings
# All config is read from environment variables (/.env.local in dev).
# Pydantic-settings validates and coerces types at startup so the app
# fails loudly if a required value is missing — never silently.

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # silently drop unknown env vars
    )

    # ------------------------------------------------------------------
    # App identity
    # ------------------------------------------------------------------
    APP_NAME: str = "DocLoop API"
    APP_VERSION: str = "0.1.0"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ------------------------------------------------------------------
    # PostgreSQL / Supabase DB
    # Supply either DATABASE_URL or the individual SUPABASE_* vars.
    # ------------------------------------------------------------------
    DATABASE_URL: PostgresDsn | None = None          # postgresql+asyncpg://...
    SUPABASE_DB_HOST: str | None = None
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_DB_USER: str = "postgres"
    SUPABASE_DB_PASSWORD: str | None = None

    # SQLAlchemy pool tuning
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30        # seconds
    DB_POOL_RECYCLE: int = 1800      # seconds — recycle before Supabase's 1h timeout

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        if self.DATABASE_URL is None:
            if not (self.SUPABASE_DB_HOST and self.SUPABASE_DB_PASSWORD):
                raise ValueError(
                    "Supply DATABASE_URL or both SUPABASE_DB_HOST and "
                    "SUPABASE_DB_PASSWORD in your .env.local"
                )
            self.DATABASE_URL = PostgresDsn(
                f"postgresql+asyncpg://{self.SUPABASE_DB_USER}:"
                f"{self.SUPABASE_DB_PASSWORD}@{self.SUPABASE_DB_HOST}:"
                f"{self.SUPABASE_DB_PORT}/{self.SUPABASE_DB_NAME}"
            )
        return self

    # ------------------------------------------------------------------
    # Supabase Auth + Storage
    # ------------------------------------------------------------------
    SUPABASE_URL: AnyHttpUrl                         # https://xxxx.supabase.co
    SUPABASE_ANON_KEY: str                           # public anon key
    SUPABASE_SERVICE_ROLE_KEY: str                   # secret — server-side only
    SUPABASE_JWT_SECRET: str                         # used to verify JWT locally
    SUPABASE_STORAGE_BUCKET: str = "docloop-documents"

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379/0")
    REDIS_ARQ_DB: int = 1            # separate DB index for ARQ queues

    @property
    def redis_arq_url(self) -> str:
        """ARQ expects a plain string URL on its own Redis DB."""
        base = str(self.REDIS_URL).rsplit("/", 1)[0]
        return f"{base}/{self.REDIS_ARQ_DB}"

    # ------------------------------------------------------------------
    # CORS — origins the Next.js frontend is served from
    # ------------------------------------------------------------------
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Allow CORS_ORIGINS to be a comma-separated string in .env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ------------------------------------------------------------------
    # External services
    # ------------------------------------------------------------------
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str = "noreply@docloop.app"

    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_FROM_NUMBER: str | None = None

    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRICE_ID_PRO: str | None = None

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ------------------------------------------------------------------
    # Security / misc
    # ------------------------------------------------------------------
    SECRET_KEY: str = "change-me-in-production"   # used for HMAC signing
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24    # 24 h (Supabase issues its own)
    MAX_UPLOAD_SIZE_MB: int = 50

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # ------------------------------------------------------------------
    # APScheduler
    # ------------------------------------------------------------------
    SCHEDULER_TIMEZONE: str = "UTC"
    SCHEDULER_JOB_DEFAULTS: dict = {
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 60,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.
    Use as a FastAPI dependency: Depends(get_settings).
    The lru_cache means .env is only parsed once per process.
    """
    return Settings()


# Module-level convenience — most internal modules import this directly.
settings = get_settings()
