"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ─────────────────────────────────────────────────────────
    api_env: str = Field(default="development")
    log_level: str = Field(default="info")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000")

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def is_development(self) -> bool:
        return self.api_env == "development"

    # ─── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/decision_engine"
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/decision_engine"
    )

    # ─── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ─── Object Storage ───────────────────────────────────────────────────────
    s3_bucket_name: str = Field(default="decision-engine-results")
    s3_endpoint_url: str | None = Field(default=None)
    s3_access_key_id: str = Field(default="minioadmin")
    s3_secret_access_key: str = Field(default="minioadmin")
    s3_region: str = Field(default="us-east-1")

    # ─── Auth ─────────────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="change-me-in-production-use-256-bit-random-value")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=10080)  # 7 days
    api_key_prefix: str = Field(default="de_live_")
    api_key_test_prefix: str = Field(default="de_test_")

    # ─── Mojo Engine ──────────────────────────────────────────────────────────
    mojo_binary_path: str = Field(default="./mojo_build/simulate")
    mojo_timeout_seconds: int = Field(default=30)
    mojo_max_concurrent: int = Field(default=4)

    # ─── Request Limits ───────────────────────────────────────────────────────
    max_payload_size_bytes: int = Field(default=1_048_576)  # 1 MB
    max_sync_runs: int = Field(default=100_000)
    max_batch_items_free: int = Field(default=10)
    max_batch_items_pro: int = Field(default=100)

    # ─── Billing ──────────────────────────────────────────────────────────────
    stripe_secret_key: str = Field(default="sk_test_replace_me")
    stripe_publishable_key: str = Field(default="pk_test_replace_me")
    stripe_webhook_secret: str = Field(default="whsec_replace_me")

    # ─── Observability ────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str | None = Field(default=None)
    sentry_dsn: str | None = Field(default=None)

    # ─── Email ────────────────────────────────────────────────────────────────
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    email_from: str = Field(default="noreply@algenta.ai")

    # ─── Webhooks ─────────────────────────────────────────────────────────────
    webhook_signing_secret: str = Field(default="change-me-in-production")
    webhook_max_retries: int = Field(default=3)

    # ─── Quotas ───────────────────────────────────────────────────────────────
    quota_free_simulations_month: int = Field(default=500)
    quota_developer_simulations_month: int = Field(default=10_000)
    quota_pro_simulations_month: int = Field(default=100_000)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Use as FastAPI dependency."""
    return Settings()
