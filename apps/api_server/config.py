"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.platform_contract_constants import API_KEY_PREFIX_LIVE, API_KEY_PREFIX_TEST
from apps.privacy_policy import PrivacyPolicy, build_privacy_policy


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
    login_rate_limit_per_minute: int = Field(default=10)  # per (email, client IP) — brute-force guard
    algenta_metering_mode: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_METERING_MODE"),
    )
    algenta_require_local_license: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_REQUIRE_LOCAL_LICENSE"),
    )
    # P5 enforcement opt-in (default None = OFF). When set, the runtime requires a valid local
    # license even on self-hosted (the fail-closed machinery; DARK until the flip). See P5.
    algenta_enforce_license_validation: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_ENFORCE_LICENSE_VALIDATION"),
    )
    algenta_control_plane_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_CONTROL_PLANE_URL"),
    )
    # Service role (P4): 'full' = the complete engine + control-plane API (default, today's
    # behavior); 'control_plane' = ONLY the hosted control-plane surfaces (auth/account/billing/
    # devices/team/credits/metering/license/meta) — no engine routers, no Mojo, no /mcp. The
    # control-plane Fly app sets ALGENTA_SERVICE_ROLE=control_plane. An unrecognized value
    # fails closed (refuse to start) rather than silently running the wrong surface set.
    algenta_service_role: str = Field(
        default="full",
        validation_alias=AliasChoices("ALGENTA_SERVICE_ROLE"),
    )

    @field_validator("algenta_service_role")
    @classmethod
    def _validate_service_role(cls, value: str) -> str:
        normalized = (value or "full").strip().lower()
        if normalized not in {"full", "control_plane"}:
            raise ValueError(
                f"ALGENTA_SERVICE_ROLE must be 'full' or 'control_plane', got {value!r}."
            )
        return normalized
    algenta_allow_outbound_network: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_ALLOW_OUTBOUND_NETWORK"),
    )
    algenta_egress_allowlist: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_EGRESS_ALLOWLIST"),
    )
    algenta_agent_core_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALGENTA_AGENT_CORE_URL"),
    )
    # ── Managed-LLM pass-through (D3) ─────────────────────────────────────────
    # Hosted multi-tenant deployments set this so orgs may use the platform's pooled provider key
    # (metered + capped) when managed_llm_enabled. OFF (default) preserves single-tenant/BYOK
    # behavior exactly. The synchronous key resolver reads ALGENTA_MANAGED_LLM directly
    # (llm_spend_service.managed_llm_mode_enabled); this field surfaces it for startup validation.
    algenta_managed_llm: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALGENTA_MANAGED_LLM"),
    )
    # Enforce the per-org free-tier storage_gb cap on the repository-intelligence object store
    # (hosted, opt-in). OFF (default) = footprint is surfaced in /v1/usage but never blocks a write.
    # The gate reads ALGENTA_ENFORCE_STORAGE_CAP directly (storage_accounting_service); this surfaces
    # it for visibility/validation.
    algenta_enforce_storage_cap: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALGENTA_ENFORCE_STORAGE_CAP"),
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
            enforce_license_validation=self.algenta_enforce_license_validation,
            control_plane_url=self.algenta_control_plane_url,
            allow_outbound_network=self.algenta_allow_outbound_network,
            egress_allowlist=self.algenta_egress_allowlist,
            agent_core_url=self.algenta_agent_core_url,
            supabase_url=self.supabase_url,
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
    # ─── License signer (P1) — keeps the private key out of the app/Fly ────────
    # backend: dev_hmac (default, legacy HS256) | pem (local RSA) | cf_worker (Cloudflare
    # Worker holds the key, app only calls it). See services/license_signer.py.
    license_signer_backend: str | None = Field(default=None)
    license_signing_private_key: str | None = Field(default=None)
    license_signing_private_key_file: str | None = Field(default=None)
    license_signer_kid: str | None = Field(default=None)
    license_signer_url: str | None = Field(default=None)
    license_signer_auth_token: str | None = Field(default=None)
    # cf_worker backend: the app never holds the Worker's private key, so to publish JWKS
    # it needs the Worker's PUBLIC key (PEM). Optional; if unset, JWKS is empty for cf_worker
    # (the Worker may expose its own JWKS in P4). See services/license_jwk.py.
    license_signer_worker_public_key: str | None = Field(default=None)
    license_signer_worker_public_key_file: str | None = Field(default=None)
    # When True, _issue_license_jwt emits the ver:2 entitlement claim shape (products/limits via
    # entitlement_service.to_license_claims) required by the cf_worker signer + the Telys verifier. Default
    # False preserves the legacy ver:1 license for existing Codna/Algenta consumers — flip ON only after
    # confirming every consumer accepts ver:2 (see docs in telys SHARED-PLATFORM-INTEGRATION.md).
    license_v2_issuance: bool = Field(default=False)
    # Per-product signer routing: comma-separated product names whose license is signed by the cf_worker
    # (RS256, license.algenta.ai) instead of the global default (dev_hmac/HS256) — because their on-device
    # runtime verifies the platform license OFFLINE. Default (None) = Telys only. **Algenta external users**
    # follow the same model: add "algenta" here (e.g. "telys,algenta") once its runtime verifies RS256 — no
    # code change, and Codna stays HS256. Only takes effect where license_signer_url is configured.
    rs256_license_products: str | None = Field(default=None)
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
    stripe_secret_key: str = Field(default="stripe_secret_key_replace_me")
    stripe_publishable_key: str = Field(default="stripe_publishable_key_replace_me")
    stripe_webhook_secret: str = Field(default="stripe_webhook_secret_replace_me")
    stripe_price_developer: str = Field(default="price_developer_replace_me")
    stripe_price_pro: str = Field(default="price_pro_replace_me")
    stripe_price_proplus: str = Field(default="price_proplus_replace_me")
    stripe_price_ultra: str = Field(default="price_ultra_replace_me")
    stripe_price_team: str = Field(default="price_team_replace_me")
    # Telys runtime paid tiers (telys_developer is free → no Stripe price). Create these in Stripe + set the env.
    stripe_price_telys_pro: str = Field(default="price_telys_pro_replace_me")
    stripe_price_telys_team: str = Field(default="price_telys_team_replace_me")
    # Algenta engine paid tiers (algenta_free is free → no Stripe price). Create these in Stripe (tagged
    # metadata.source=algenta) + set the env. Billing ships DARK — the checkout is gated on the product's
    # `billing` flag (product_registry) until the owner flips it after verifying in Stripe test-mode.
    stripe_price_algenta_pro: str = Field(default="price_algenta_pro_replace_me")
    stripe_price_algenta_team: str = Field(default="price_algenta_team_replace_me")
    # Self-hosted, billed PER ACTIVE NODE ($199/node). Self-serve checkout provisions a single-node license;
    # multi-node / air-gapped self-host is an offline per-node mint (scripts/issue_offline_license.py
    # --paid-selfhost) or an enterprise site license — never a self-serve unbounded quantity.
    stripe_price_algenta_selfhost: str = Field(default="price_algenta_selfhost_replace_me")

    # ─── GitHub App (codna "watch CI / open fix PRs") ─────────────────────────
    # Inert until configured: webhook route, token minter, and event handlers all
    # no-op when these are unset, so existing deployments are unaffected.
    github_app_id: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_ID")
    )
    github_app_private_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_PRIVATE_KEY")
    )
    github_app_webhook_secret: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_WEBHOOK_SECRET")
    )
    github_app_client_id: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_CLIENT_ID")
    )
    github_app_client_secret: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_CLIENT_SECRET")
    )
    # Public app slug (the `https://github.com/apps/<slug>` handle) — drives the
    # one-click install redirect. Optional; the dashboard can build the URL itself.
    github_app_slug: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_SLUG")
    )

    # ── Supabase identity (codna website BYOK bridge) ─────────────────────────
    # The codna marketing site signs users in with Supabase (GitHub OAuth) and forwards the
    # Supabase access_token (a JWT) to the top-level /byok endpoint. The engine verifies that JWT
    # OFFLINE against the project's JWKS (asymmetric ES256/RS256) — issuer + JWKS URL are derived
    # from this base URL — to read the caller's GitHub identity (user_metadata.provider_id) and map
    # them to their engine org. Inert until set (the /byok surface returns 503 while unconfigured).
    # NOTE: when set, this host is auto-added to the egress allowlist (build_privacy_policy), so the
    # JWKS fetch isn't blocked by the fail-closed/SSRF guard — no manual ALGENTA_EGRESS_ALLOWLIST
    # entry is needed for it.
    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    # Service/secret key for Supabase ADMIN operations (dormant-account sweep: list + delete users).
    # New sb_secret_… or legacy service_role JWT. Empty → the sweep can't list/delete (no-op).
    supabase_service_role_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY"),
    )
    # Legacy HS256 fallback — ONLY for projects still on the shared symmetric JWT secret (not the
    # asymmetric default). Leave unset for modern projects; the verifier prefers JWKS and branches
    # to HS256 only when the token header says alg=HS256.
    supabase_jwt_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_JWT_SECRET"),
    )
    # Expected `aud` claim. Supabase issues "authenticated" for signed-in users; override only if a
    # custom GoTrue audience is configured.
    supabase_jwt_aud: str = Field(
        default="authenticated",
        validation_alias=AliasChoices("SUPABASE_JWT_AUD"),
    )

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
        default="",
        description=(
            "Docker image to deploy on all cloud providers. MUST be a pinned tag or @sha256 digest "
            "(e.g. .../api:git-<sha>); never a floating :latest. Empty = unconfigured (provisioning "
            "supplies a pinned ref). Default no longer floats — enforced by test_image_pin_guard."
        ),
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
    # Resend (transactional email — team invites, dormant-account notices). Empty = disabled
    # (send_* helpers no-op + log a warning instead of raising).
    resend_api_key: str = Field(default="")
    resend_from_email: str = Field(default="Codna <noreply@codna.ai>")

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
    # Shared identity portal (accounts.thyn.ai) — the RFC-8628 device-login verification_uri points here
    # (…/device). Brand-aware via ?app=<slug>, resolved from the device grant's client_id.
    accounts_base_url: str = Field(
        default="https://accounts.thyn.ai",
        validation_alias=AliasChoices("ALGENTA_ACCOUNTS_BASE_URL", "ACCOUNTS_BASE_URL"),
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
