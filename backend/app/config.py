"""
Configuration module for SealTrail.
Loads settings via pydantic-settings and fails fast if any required setting is empty.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL Configuration
    POSTGRES_DB: str = Field(..., min_length=1)
    POSTGRES_SUPERUSER: str = Field(..., min_length=1)
    POSTGRES_SUPERUSER_PASSWORD: str = Field(..., min_length=1)
    DB_OWNER_USER: str = Field(..., min_length=1)
    DB_OWNER_PASSWORD: str = Field(..., min_length=1)
    DB_APP_USER: str = Field(..., min_length=1)
    DB_APP_PASSWORD: str = Field(..., min_length=1)
    DB_HOST: str = Field(default="postgres")
    DB_PORT: int = Field(default=5432)
    DATABASE_URL_APP: str = Field(..., min_length=1)
    DATABASE_URL_OWNER: str = Field(..., min_length=1)
    DATABASE_URL_SUPERUSER_HOST: str = Field(default="")

    # S3 / MinIO Configuration
    MINIO_ROOT_USER: str = Field(..., min_length=1)
    MINIO_ROOT_PASSWORD: str = Field(..., min_length=1)
    S3_ENDPOINT_URL: str = Field(..., min_length=1)
    S3_ENDPOINT_URL_HOST: str = Field(default="http://127.0.0.1:9000")
    S3_REGION: str = Field(default="us-east-1")
    S3_BUCKET_EVIDENCE: str = Field(default="sealtrail-evidence")
    S3_BUCKET_EXPORTS: str = Field(default="sealtrail-exports")
    S3_APP_ACCESS_KEY: str = Field(..., min_length=1)
    S3_APP_SECRET_KEY: str = Field(..., min_length=1)
    S3_DISPOSER_ACCESS_KEY: str = Field(..., min_length=1)
    S3_DISPOSER_SECRET_KEY: str = Field(..., min_length=1)

    # Application & Security
    APP_ENV: str = Field(default="development")
    APP_BASE_URL: str = Field(default="http://localhost:8080")
    CORS_ORIGINS: str = Field(default="http://localhost:8080,http://localhost:5173")
    JWT_SECRET: str = Field(..., min_length=16)
    JWT_ACCESS_MINUTES: int = Field(default=30)
    JWT_REFRESH_DAYS: int = Field(default=7)
    COOKIE_SECURE: bool = Field(default=False)
    MAX_UPLOAD_MB: int = Field(default=200)
    LOGIN_MAX_FAILURES: int = Field(default=5)
    LOGIN_LOCKOUT_MINUTES: int = Field(default=10)
    PASSWORD_MIN_LENGTH: int = Field(default=10)

    # Audit chain / Checkpoints
    CHECKPOINT_SIGNING_KEY_B64: str = Field(..., min_length=1)
    CHECKPOINT_PUBLIC_KEY_B64: str = Field(..., min_length=1)
    CHECKPOINT_INTERVAL_MINUTES: int = Field(default=5)
    CHAIN_VERIFY_INTERVAL_MINUTES: int = Field(default=5)

    # Custody & Anomaly Rules
    ACK_SLA_MINUTES: int = Field(default=60)
    BUSINESS_TZ: str = Field(default="Asia/Kolkata")
    BUSINESS_HOURS_START: str = Field(default="08:00")
    BUSINESS_HOURS_END: str = Field(default="20:00")
    BURST_VIEW_THRESHOLD: int = Field(default=15)
    BURST_WINDOW_MINUTES: int = Field(default=5)
    DENIED_ATTEMPTS_THRESHOLD: int = Field(default=3)
    DENIED_WINDOW_MINUTES: int = Field(default=10)
    APPROVAL_EXPIRY_HOURS: int = Field(default=48)
    DEFAULT_RETENTION_DAYS: int = Field(default=1825)

    # Seed data
    SEED_ON_START: bool = Field(default=False)
    SEED_PASSWORD: str = Field(default="Demo#Seal2026!")
    SEED_EMAIL_DOMAIN: str = Field(default="sealtrail.local")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
