---
sidebar_position: 99
slug: /self-hosting
---

# Setup & Configuration

Use this page after [Quickstart](/quickstart). It covers the supported self-hosted shape, the manual install path, and the production configuration contract.

## Supported deployment shape

Self-hosted v1 is the service product:

- API service
- worker service
- PostgreSQL
- Redis
- object storage
- Docker Compose on your infrastructure

Integrate with it over HTTP or the SDKs after the service is running.

## Requirements

- Linux VM with Docker Engine
- Docker Compose v2 plugin (`docker compose`) or standalone `docker-compose`
- 4+ vCPU recommended
- 8+ GB RAM recommended
- persistent disk for PostgreSQL and object storage
- outbound access to pull release images for the default install path

## Manual install

Use this path when you need to inspect or modify the Compose bundle directly.

### 1. Download the bundle

```bash
git clone https://github.com/algenta/decision-engine
cd decision-engine
cp .env.example .env
```

### 2. Set the required environment

```bash
API_ENV=production
DATABASE_URL=postgresql+asyncpg://algenta:algenta_secret@postgres:5432/algenta
DATABASE_URL_SYNC=postgresql://algenta:algenta_secret@postgres:5432/algenta
REDIS_URL=redis://redis:6379/0
JWT_SECRET=change-me-use-256-bit-random-value
RESULT_STORAGE_ENABLED=true
ALGENTA_IMAGE_REGISTRY=ghcr.io/algenta/decision-engine
ALGENTA_IMAGE_TAG=git-YOUR_RELEASE_TAG
ALGENTA_DEPLOYMENT_MODE=self_hosted
ALGENTA_DISABLE_CLOUD=1
ALGENTA_DISABLE_TELEMETRY=1
ALGENTA_TELEMETRY_MODE=local_audit
ALGENTA_METERING_MODE=local_audit
ALGENTA_ALLOW_OUTBOUND_NETWORK=0
ALGENTA_EGRESS_ALLOWLIST=minio:9000
ALGENTA_API_PUBLIC_BASE_URL=http://localhost:8000
ALGENTA_APP_BASE_URL=
```

### 3. Start the stack

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml up -d
```

### 4. Run migrations

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml exec -T api \
  python -m alembic -c apps/api_server/alembic.ini upgrade head
```

### 5. Create the bootstrap key

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml exec -T api \
  python scripts/bootstrap_self_host.py
```

Save the printed `BOOTSTRAP_API_KEY` value temporarily. It is a one-time
bootstrap credential. Rotate it to a bounded-lifetime replacement key before
recurring workloads:

```bash
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"label":"mission-runtime","expires_at":"2028-05-19T00:00:00Z","device_limit":3}'
```

The bootstrap output also includes `BOOTSTRAP_API_KEY_ID` and
`BOOTSTRAP_API_KEY_PREFIX` for audit and revocation. The replacement key
response returns `raw_key`, `id`, `key_prefix`, `device_limit`, and
`expires_at`; store the non-secret identity fields for ongoing audit and
revocation. Use the returned `raw_key` as `ALGENTA_API_KEY` for ongoing operator and service access, then revoke the bootstrap key by id:

```bash
curl -X DELETE http://localhost:8000/v1/api-keys/${BOOTSTRAP_API_KEY_ID} \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

After rotation, `GET /v1/api-keys` returns only non-secret metadata such as
`id`, `label`, `key_prefix`, `device_limit`, `created_at`, and `expires_at`; it
does not return `raw_key` again.

An explicit `device_limit` also binds ordinary hosted API traffic for that key,
not just the local runtime/device-register path. The SDKs send the stable
device headers automatically. Raw HTTP callers using capped keys must send
`X-Algenta-Device-Id`, `X-Algenta-Platform`, and
`X-Algenta-Hostname-Hash` on authenticated requests. The first successful
hosted request for a new capped device also returns
`X-Algenta-Device-Binding-Token`; store and replay that token on later
requests from the same device. The SDKs do this automatically.

## Enterprise privacy defaults

The generated self-hosted `.env` now defaults to the private enterprise profile:

- `ALGENTA_DEPLOYMENT_MODE=self_hosted`
- `ALGENTA_DISABLE_CLOUD=1`
- `ALGENTA_DISABLE_TELEMETRY=1`
- `ALGENTA_TELEMETRY_MODE=local_audit`
- `ALGENTA_METERING_MODE=local_audit`
- `ALGENTA_ALLOW_OUTBOUND_NETWORK=0`
- `ALGENTA_API_PUBLIC_BASE_URL=http://localhost:8000`

`ALGENTA_DISABLE_TELEMETRY=1` means no outbound or vendor telemetry. It does
not disable local audit events, local metering records, or local egress logs.

`ALGENTA_API_PUBLIC_BASE_URL` is the public API origin used in quickstart links,
billing redirects, and email content. Set `ALGENTA_APP_BASE_URL` only when you
front a separate dashboard or account UI; when it is blank in a private
profile, Algenta keeps user-facing links on the API origin instead of silently
pointing at Algenta cloud.

Use `ALGENTA_DEPLOYMENT_MODE=air_gapped` for the strict privacy profile. That
profile inherits the self-hosted defaults, requires a local signed license, and
forbids control-plane sync.

The buyer-facing proof endpoints are:

- `GET /v1/admin/egress-policy`
- `GET /v1/admin/egress-log`
- `GET /v1/admin/privacy-report`

## Required environment variables

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | PostgreSQL async URL used by the API |
| `DATABASE_URL_SYNC` | PostgreSQL sync URL used for migrations |
| `REDIS_URL` | Redis connection URL |
| `JWT_SECRET` | 256-bit random secret for auth tokens |

## Common self-hosted settings

| Variable | Description |
| --- | --- |
| `API_ENV` | Set to `production` for self-hosted deployments |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `POSTGRES_HOST_PORT` | Optional localhost port binding for PostgreSQL |
| `REDIS_HOST_PORT` | Optional localhost port binding for Redis |
| `MINIO_API_HOST_PORT` | Optional localhost port binding for the MinIO S3 API |
| `MINIO_CONSOLE_HOST_PORT` | Optional localhost port binding for the MinIO console |
| `RUNTIME_FALLBACK_MODE` | Set to `allow` for the default self-hosted install so the API can start when the bundled Mojo binary cannot serve pool mode |
| `ALGENTA_SOURCES_DIR` | Local registry path for uploaded/queryable datasets |
| `ALGENTA_DEPLOYMENT_MODE` | `self_hosted` for the private enterprise default, `air_gapped` for the strict privacy profile |
| `ALGENTA_DISABLE_CLOUD` | Set to `1` to block Algenta-owned cloud egress |
| `ALGENTA_DISABLE_TELEMETRY` | Set to `1` to disable outbound/vendor telemetry while keeping local audit enabled |
| `ALGENTA_TELEMETRY_MODE` | `local_audit` for local-only audit, `control_plane_sync` only when an allowed control plane URL is configured |
| `ALGENTA_METERING_MODE` | `local_audit` for local-only metering, `control_plane_sync` only when explicitly permitted |
| `ALGENTA_REQUIRE_LOCAL_LICENSE` | Set to `1` for strict local signed license enforcement; required by the `air_gapped` profile |
| `ALGENTA_CONTROL_PLANE_URL` | Optional explicit control-plane URL; leave blank in the default private self-hosted profile |
| `ALGENTA_ALLOW_OUTBOUND_NETWORK` | Set to `0` to block Algenta-owned and undeclared public egress |
| `ALGENTA_EGRESS_ALLOWLIST` | Comma-separated allowlist for explicit connector/operator egress such as `minio:9000,*.customer.internal,postgres.internal:5432` |
| `ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE` | PEM public key file used to verify offline local licenses in strict private profiles |
| `ALGENTA_API_PUBLIC_BASE_URL` | Public API origin used in generated quickstart URLs, billing redirects, and user-facing email content |
| `ALGENTA_APP_BASE_URL` | Optional separate dashboard/account UI origin; leave blank to keep private-profile links on the API origin |
| `RESULT_STORAGE_ENABLED` | Set to `true` to persist full simulation results in MinIO/S3 |
| `S3_BUCKET_NAME` | Bucket for large result storage |
| `S3_ENDPOINT_URL` | MinIO/S3 endpoint |
| `S3_ACCESS_KEY_ID` | MinIO/S3 access key |
| `S3_SECRET_ACCESS_KEY` | MinIO/S3 secret key |
| `METRICS_SECRET` | Shared secret for remote `/metrics` scraping |
| `WEBHOOK_SIGNING_SECRET` | Signing secret for outbound webhooks |
| `SMTP_*` | Optional email delivery settings |
| `STRIPE_*` | Optional billing settings |

## Release artifact settings

| Variable | Description |
| --- | --- |
| `ALGENTA_IMAGE_REGISTRY` | Registry prefix for API and worker images |
| `ALGENTA_IMAGE_TAG` | Pinned API and worker image tag |

## Related pages

- [Operations](/operations)
- [TLS & Reverse Proxy](/operations/tls-and-reverse-proxy)
- [Logs & Metrics](/operations/logs-and-metrics)
- [Upgrade & Rollback](/operations/upgrade-and-rollback)
- [API Authentication](/api-reference/authentication)
