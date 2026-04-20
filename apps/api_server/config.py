"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.platform_contract_constants import API_KEY_PREFIX_LIVE, API_KEY_PREFIX_TEST


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
    runtime_fallback_mode: str = Field(
        default="auto",
        description=(
            "Runtime fallback policy: auto uses development defaults, "
            "allow always permits degraded runtime paths, deny fail-closes instead."
        ),
    )
    mojo_profiling_policy: str = Field(
        default="optional",
        description=(
            "Mojo profiling policy: optional disables profiling explicitly on errors, "
            "disabled never invokes profiling, required fail-closes profiling errors."
        ),
    )

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def is_development(self) -> bool:
        return self.api_env == "development"

    @computed_field  # type: ignore[misc]
    @property
    def allow_runtime_fallbacks(self) -> bool:
        mode = self.runtime_fallback_mode.strip().lower()
        if mode == "allow":
            return True
        if mode == "deny":
            return False
        return self.is_development

    @computed_field  # type: ignore[misc]
    @property
    def normalized_mojo_profiling_policy(self) -> str:
        policy = self.mojo_profiling_policy.strip().lower()
        if policy in {"disabled", "required"}:
            return policy
        return "optional"

    @computed_field  # type: ignore[misc]
    @property
    def mojo_profiling_enabled(self) -> bool:
        return self.normalized_mojo_profiling_policy != "disabled"

    @computed_field  # type: ignore[misc]
    @property
    def mojo_profiling_required(self) -> bool:
        return self.normalized_mojo_profiling_policy == "required"

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
    result_storage_enabled: bool = Field(default=False)

    # ─── Auth ─────────────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="change-me-in-production-use-256-bit-random-value")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=10080)
    license_signing_secret: str | None = Field(default=None)
    api_key_prefix: str = Field(default=API_KEY_PREFIX_LIVE)
    api_key_test_prefix: str = Field(default=API_KEY_PREFIX_TEST)

    # ─── Mojo Engine ──────────────────────────────────────────────────────────
    mojo_binary_path: str = Field(default="./mojo_build/simulate")
    mojo_timeout_seconds: int = Field(default=30)
    mojo_max_concurrent: int = Field(default=4)

    # ─── Request Limits ───────────────────────────────────────────────────────
    max_payload_size_bytes: int = Field(default=1_048_576)
    max_sync_runs: int = Field(default=100_000)
    max_batch_items_free: int = Field(default=10)
    max_batch_items_pro: int = Field(default=100)

    # ─── Billing ──────────────────────────────────────────────────────────────
    stripe_secret_key: str = Field(default="sk_test_replace_me")
    stripe_publishable_key: str = Field(default="pk_test_replace_me")
    stripe_webhook_secret: str = Field(default="whsec_replace_me")
    stripe_price_developer: str = Field(default="price_developer_replace_me")
    stripe_price_pro: str = Field(default="price_pro_replace_me")

    # ─── Cloud Provider Credentials (for per-org deployment provisioning) ──────
    # AWS
    aws_access_key_id: str | None = Field(
        default=None,
        description="AWS access key for ECS/RDS provisioning",
    )
    aws_secret_access_key: str | None = Field(default=None, description="AWS secret key")
    aws_default_region: str = Field(default="us-east-1")
    aws_ecr_image_uri: str | None = Field(
        default=None,
        description="ECR image URI for Algenta engine",
    )

    # Azure
    azure_subscription_id: str | None = Field(default=None, description="Azure subscription ID")
    azure_tenant_id: str | None = Field(default=None, description="Azure tenant ID")
    azure_client_id: str | None = Field(
        default=None,
        description="Azure service principal client ID",
    )
    azure_client_secret: str | None = Field(
        default=None,
        description="Azure service principal secret",
    )
    azure_resource_group_prefix: str = Field(
        default="algenta",
        description="Prefix for Azure resource groups",
    )
    azure_acr_registry: str | None = Field(default=None, description="Azure Container Registry URL")

    # GCP
    gcp_project_id: str | None = Field(default=None, description="GCP project ID")
    gcp_service_account_json: str | None = Field(
        default=None,
        description="GCP service account JSON (base64-encoded)",
    )
    gcp_region: str = Field(default="us-central1")
    gcp_artifact_registry: str | None = Field(
        default=None,
        description="GCP Artifact Registry image URL",
    )

    # Provisioning
    algenta_engine_image: str = Field(
        default="ghcr.io/algenta/decision-engine-api:latest",
        description="Docker image to deploy on all cloud providers",
    )
    deployment_base_domain: str = Field(
        default="deploy.algenta.ai",
        description="Base domain for per-org deployment endpoints",
    )
    deployment_billing_markup_pct: float = Field(
        default=20.0,
        description="Default pass-through billing markup percentage",
    )

    # ─── Observability ────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str | None = Field(default=None)
    sentry_dsn: str | None = Field(default=None)
    # Metrics endpoint protection — set to a random secret for production
    # Prometheus scraper must send: X-Metrics-Secret: <this value>
    # Leave empty to allow loopback-only access (no public access)
    metrics_secret: str | None = Field(default=None)

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
