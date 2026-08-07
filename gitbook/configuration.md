---
icon: gear
description: Every Algenta configuration environment variable in one place, with its default and any aliases — complete and current.
---

# Configuration reference

Every environment variable Algenta reads, with its default and any accepted aliases. Set these in your shell, your `.env`, or your orchestrator. Names are case-insensitive.

{% hint style="info" %}
Where a variable has accepted aliases (for example a legacy `DE_` name), they appear in the Aliases column.
{% endhint %}

| Variable | Default | Aliases | Description |
| --- | --- | --- | --- |
| `ALGENTA_ACCOUNTS_BASE_URL` | `https://accounts.thyn.ai` | `ACCOUNTS_BASE_URL` | — |
| `ALGENTA_AGENT_CORE_URL` | — | — | Optional bundled agent-runtime endpoint. |
| `ALGENTA_ALLOW_OUTBOUND_NETWORK` | — | — | Permit egress (default false in air-gapped). |
| `ALGENTA_API_PUBLIC_BASE_URL` | — | `API_PUBLIC_BASE_URL` | Public-facing API base URL (cloud). |
| `ALGENTA_APP_BASE_URL` | — | `APP_BASE_URL`, `DE_APP_BASE_URL` | Dashboard / console base URL for self-hosted links. |
| `ALGENTA_BASE_URL` | — | `DE_BASE_URL`, `ALGENTA_API_URL` | Engine URL for self-hosted clients (absolute, e.g. http://localhost:8000). |
| `ALGENTA_CONTROL_PLANE_URL` | — | — | Control-plane endpoint for satellite deployments. |
| `ALGENTA_DEPLOYMENT_MODE` | `saas` | — | Privacy/egress profile: saas \| vpc \| self_hosted \| air_gapped \| hybrid_provider. |
| `ALGENTA_DISABLE_CLOUD` | — | — | Opt out of any cloud integration (self-hosted). |
| `ALGENTA_DISABLE_TELEMETRY` | — | — | Disable all outbound/vendor telemetry; keep local audit. |
| `ALGENTA_EGRESS_ALLOWLIST` | — | — | Comma-separated allowlist of permitted egress destinations. |
| `ALGENTA_ENABLE_METERING` | `False` | — | — |
| `ALGENTA_ENFORCE_LICENSE_VALIDATION` | — | — | Enable fail-closed license validation on self-hosted deployments. |
| `ALGENTA_ENFORCE_STORAGE_CAP` | `False` | — | Enforce a configured organization storage policy (off by default; Algenta editions are uncapped). |
| `ALGENTA_ENGINE_IMAGE` | — | — | Docker image to deploy on all cloud providers. MUST be a pinned tag or @sha256 digest (e.g. .../api:git-<sha>); never a floating :latest. Empty = unconfigured (provisioning supplies a pinned ref). |
| `ALGENTA_ENTRA_ALLOWED_CLIENT_APPS` | — | — | — |
| `ALGENTA_ENTRA_ALLOWED_TENANTS` | — | — | — |
| `ALGENTA_ENTRA_AUDIENCE` | — | — | — |
| `ALGENTA_ENTRA_AUTO_PROVISION` | `False` | — | — |
| `ALGENTA_ENTRA_TENANT_ID` | — | — | — |
| `ALGENTA_MANAGED_LLM` | `False` | — | Enable the pooled managed-LLM provider key (multi-tenant SaaS). |
| `ALGENTA_METERING_MODE` | — | — | Execution-record destination. Self-hosted Algenta defaults to local_audit; control_plane_sync is for explicitly configured managed deployments. |
| `ALGENTA_PRODUCT` | — | — | Edition this deployment presents (e.g. algenta): scopes the MCP tool set and which product /billing/plans prices. |
| `ALGENTA_REGISTRY_READ_TOKEN` | — | — | — |
| `ALGENTA_REGISTRY_URL` | `ghcr.io` | — | — |
| `ALGENTA_REGISTRY_USERNAME` | — | — | — |
| `ALGENTA_REQUIRE_LOCAL_LICENSE` | — | — | Require a valid local signed license; disable hosted/dev fallback. |
| `ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED` | `True` | `RUNTIME_LIBRARY_HTTP_API_ENABLED` | Expose the /v1/libraries* runtime-library routes (on by default). |
| `ALGENTA_SERVICE_ROLE` | `full` | — | Deployment role: full (default, with engine) \| control_plane (engine-free). |
| `ALGENTA_SIMULATION_PERSIST_TRANSPORT` | `auto` | `SIMULATION_PERSIST_TRANSPORT` | Result persistence backend: auto \| celery \| in_process. |
| `ALGENTA_TELEMETRY_MODE` | — | — | Telemetry destination. Self-hosted Algenta defaults to local_audit with no outbound sync. |
| `API_ENV` | `development` | — | — |
| `API_KEY_CREATE_RATE_LIMIT_PER_MINUTE` | `10` | — | — |
| `API_KEY_PREFIX` | `de_live_` | — | — |
| `API_KEY_TEST_PREFIX` | `de_test_` | — | — |
| `AWS_ACCESS_KEY_ID` | — | — | AWS access key for ECS/RDS provisioning |
| `AWS_DEFAULT_REGION` | `us-east-1` | — | — |
| `AWS_ECR_IMAGE_URI` | — | — | ECR image URI for Algenta engine |
| `AWS_SECRET_ACCESS_KEY` | — | — | AWS secret key |
| `AZURE_ACR_REGISTRY` | — | — | Azure Container Registry URL |
| `AZURE_CLIENT_ID` | — | — | Azure service principal client ID |
| `AZURE_CLIENT_SECRET` | — | — | Azure service principal secret |
| `AZURE_RESOURCE_GROUP_PREFIX` | `algenta` | — | Prefix for Azure resource groups |
| `AZURE_SUBSCRIPTION_ID` | — | — | Azure subscription ID |
| `AZURE_TENANT_ID` | — | — | Azure tenant ID |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhos...` | — | — |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgre...` | — | Async PostgreSQL connection string. |
| `DATABASE_URL_SYNC` | `postgresql://postgres:postgres@localh...` | — | Sync PostgreSQL connection string (migrations). |
| `DEPLOYMENT_BASE_DOMAIN` | `deploy.algenta.ai` | — | Base domain for per-org deployment endpoints |
| `DEPLOYMENT_BILLING_MARKUP_PCT` | `20.0` | — | Default pass-through billing markup percentage |
| `EMAIL_FROM` | `noreply@algenta.ai` | — | — |
| `GCP_ARTIFACT_REGISTRY` | — | — | GCP Artifact Registry image URL |
| `GCP_PROJECT_ID` | — | — | GCP project ID |
| `GCP_REGION` | `us-central1` | — | — |
| `GCP_SERVICE_ACCOUNT_JSON` | — | — | GCP service account JSON (base64-encoded) |
| `JWT_ALGORITHM` | `HS256` | — | — |
| `JWT_EXPIRE_MINUTES` | `10080` | — | — |
| `JWT_SECRET` | `change-me-in-production-use-256-bit-r...` | — | Signing secret for session JWTs. |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | — | — |
| `LOG_LEVEL` | `info` | — | — |
| `MAX_BATCH_ITEMS_FREE` | `10` | — | — |
| `MAX_BATCH_ITEMS_PRO` | `100` | — | — |
| `MAX_PAYLOAD_SIZE_BYTES` | `1048576` | — | — |
| `MAX_SYNC_RUNS` | `100000` | — | — |
| `METRICS_SECRET` | — | — | Bearer secret guarding the /metrics endpoint. |
| `ORIGIN_GUARD_MODE` | `off` | — | — |
| `ORIGIN_SHARED_SECRET` | — | — | — |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | — | — |
| `QUOTA_DEVELOPER_SIMULATIONS_MONTH` | `10000` | — | — |
| `QUOTA_FREE_SIMULATIONS_MONTH` | `500` | — | — |
| `QUOTA_PRO_SIMULATIONS_MONTH` | `100000` | — | — |
| `REDIS_URL` | `redis://localhost:6379/0` | — | Redis connection (cache / queue / coordination). |
| `RESEND_API_KEY` | — | — | — |
| `RESEND_FROM_EMAIL` | `Algenta <noreply@algenta.ai>` | — | — |
| `RESULT_STORAGE_ENABLED` | `False` | — | — |
| `S3_ACCESS_KEY_ID` | `minioadmin` | — | — |
| `S3_BUCKET_NAME` | `algenta-results` | — | — |
| `S3_ENDPOINT_URL` | — | — | — |
| `S3_REGION` | `us-east-1` | — | — |
| `S3_SECRET_ACCESS_KEY` | `minioadmin` | — | — |
| `SENTRY_DSN` | — | — | — |
| `SIGNUP_MAX_PER_DAY_PER_EMAIL` | `2` | — | — |
| `SIGNUP_RATE_LIMIT_PER_MINUTE` | `3` | — | — |
| `SMTP_HOST` | `localhost` | — | — |
| `SMTP_PASSWORD` | — | — | — |
| `SMTP_PORT` | `1025` | — | — |
| `SMTP_USERNAME` | — | — | — |
| `STRIPE_PUBLISHABLE_KEY` | `stripe_publishable_key_replace_me` | — | — |
| `STRIPE_SECRET_KEY` | `stripe_secret_key_replace_me` | — | Stripe API secret key (billing). |
| `STRIPE_WEBHOOK_SECRET` | `stripe_webhook_secret_replace_me` | — | Stripe webhook signing secret. |
| `SUPABASE_JWT_AUD` | `authenticated` | — | — |
| `SUPABASE_JWT_SECRET` | — | — | — |
| `SUPABASE_SERVICE_ROLE_KEY` | — | — | — |
| `SUPABASE_URL` | — | `NEXT_PUBLIC_SUPABASE_URL` | — |
| `TURNSTILE_SECRET_KEY` | — | `ALGENTA_TURNSTILE_SECRET_KEY` | — |
| `WEBHOOK_MAX_RETRIES` | `3` | — | — |
| `WEBHOOK_SIGNING_SECRET` | `change-me-in-production` | — | — |

## Related

{% content-ref url="self-hosting.md" %}
[self-hosting.md](self-hosting.md)
{% endcontent-ref %}
