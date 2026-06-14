"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.privacy_policy import PrivacyPolicy, build_privacy_policy
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
    simulation_persist_transport: str = Field(
        default="auto",
        validation_alias=AliasChoices(
            "ALGENTA_SIMULATION_PERSIST_TRANSPORT",
            "SIMULATION_PERSIST_TRANSPORT",
        ),
        description=(
            "Simulation persistence transport: auto prefers Celery, "
            "celery requires Celery, and in_process forces FastAPI BackgroundTasks."
        ),
    )
    mojo_profiling_policy: str = Field(
        default="optional",
        description=(
            "Mojo profiling policy: optional disables profiling explicitly on errors, "
            "disabled never invokes profiling, required fail-closes profiling errors."
        ),
    )
    runtime_library_http_api_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED",
            "RUNTIME_LIBRARY_HTTP_API_ENABLED",
        ),
        description=(
            "Expose /v1/libraries, /v1/libraries/health, and /v1/libraries/execute "
            "on the hosted/public HTTP API surface. Disabled by default."
        ),
    )
    algenta_deployment_mode: str = Field(
        default="saas",
        validation_alias=AliasChoices("ALGENTA_DEPLOYMENT_MODE"),
    )
    algenta_disable_cloud: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_DISABLE_CLOUD"),
    )
    algenta_disable_telemetry: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_DISABLE_TELEMETRY"),
    )
    algenta_telemetry_mode: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_TELEMETRY_MODE"),
    )
    # ── Signup abuse protection (Wave 2) ──────────────────────────────────────
    # Cloudflare Turnstile: captcha is enforced on signup IFF a secret is set (feature flag).
    turnstile_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("TURNSTILE_SECRET_KEY", "ALGENTA_TURNSTILE_SECRET_KEY"),
    )
    signup_rate_limit_per_minute: int = Field(default=3)  # per client IP (burst)
    signup_max_per_day_per_email: int = Field(default=2)  # org-creation cap per email per day
    api_key_create_rate_limit_per_minute: int = Field(default=10)  # per org
    algenta_metering_mode: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_METERING_MODE"),
    )
    algenta_require_local_license: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_REQUIRE_LOCAL_LICENSE"),
    )
    algenta_control_plane_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_CONTROL_PLANE_URL"),
    )
    algenta_allow_outbound_network: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_ALLOW_OUTBOUND_NETWORK"),
    )
    algenta_egress_allowlist: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_EGRESS_ALLOWLIST"),
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
    def normalized_simulation_persist_transport(self) -> str:
        transport = self.simulation_persist_transport.strip().lower()
        if transport in {"in_process", "background", "background_tasks"}:
            return "in_process"
        if transport == "celery":
            return "celery"
        return "auto"

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

    @property
    def privacy_policy(self) -> PrivacyPolicy:
        return build_privacy_policy(
            deployment_mode=self.algenta_deployment_mode,
            disable_cloud=self.algenta_disable_cloud,
            disable_telemetry=self.algenta_disable_telemetry,
            telemetry_mode=self.algenta_telemetry_mode,
            metering_mode=self.algenta_metering_mode,
            require_local_license=self.algenta_require_local_license,
            control_plane_url=self.algenta_control_plane_url,
            allow_outbound_network=self.algenta_allow_outbound_network,
            egress_allowlist=self.algenta_egress_allowlist,
        )

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
        default="ghcr.io/algenta/decision-engine/api:latest",
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

    # ─── Public URL Resolution ───────────────────────────────────────────────
    app_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_APP_BASE_URL", "APP_BASE_URL", "DE_APP_BASE_URL"),
    )
    api_public_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_API_PUBLIC_BASE_URL", "API_PUBLIC_BASE_URL"),
    )
    api_transport_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL"),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Use as FastAPI dependency."""
    return Settings()


class SettingsProxy:
    """Live proxy that forwards access to the current cached settings object.

    This keeps module-level `settings` handles compatible with existing imports
    and tests while still honoring `get_settings.cache_clear()` and any updated
    environment-derived configuration.
    """

    __slots__ = ()

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(get_settings(), name)

    def __setattr__(self, name: str, value):  # type: ignore[no-untyped-def]
        setattr(get_settings(), name, value)

    def __delattr__(self, name: str) -> None:
        delattr(get_settings(), name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(get_settings())))

    def __repr__(self) -> str:
        return f"SettingsProxy({get_settings()!r})"
