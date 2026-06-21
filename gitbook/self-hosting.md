---
icon: server
---

# Self-hosting

This page walks you through running Algenta in production on your own infrastructure: the full engine (API, async worker, agent-core sidecar, PostgreSQL, Redis, and S3-compatible object storage) on a single Docker Compose stack, installed with one command. You will install the stack, understand the durable secrets that must survive restarts, bootstrap an owner and API key, and verify the deployment with the built-in health, privacy, and persistence proofs. Everything below is copy-pasteable and uses the exact commands, environment variables, and endpoint paths the engine ships with.

## What you get

A self-hosted install is the complete service product. The Compose stack runs six services:

| Service | Image | Role |
| --- | --- | --- |
| `api` | `…/api:${ALGENTA_IMAGE_TAG}` | FastAPI backend on port `8000` (`/v1/*`) |
| `worker` | `…/worker:${ALGENTA_IMAGE_TAG}` | Async job worker (simulate, persist, repository queues) |
| `sidecar` | `ghcr.io/thyn-ai/codna/sidecar` | Agent-core execution head on port `8787` (digest-pinned) |
| `postgres` | `postgres:16-alpine` | Primary datastore (durable volume) |
| `redis` | `redis:7-alpine` | Queue + cache (append-only, durable volume) |
| `minio` | `minio/minio` | S3-compatible object storage for results and artifacts |

Integrate over HTTP or the SDKs once the service is running. The agent-core sidecar powers the agentic repository / GitHub flow; the rest serve simulations, datasets, queries, and jobs.

### Requirements

- Linux host (or macOS for evaluation) with the Docker daemon running.
- Docker Compose v2 (`docker compose`) or the standalone `docker-compose` CLI.
- 4+ vCPU and 8+ GB RAM recommended.
- Persistent disk for PostgreSQL and object storage.
- Outbound access to pull the pinned release images (`ghcr.io/algenta/decision-engine`) and the sidecar image.

{% hint style="info" %}
The sidecar default is a private, digest-pinned GHCR image (`ghcr.io/thyn-ai/codna/sidecar@sha256:…`). The deploy host needs `read:packages` access to that package, or override it with `ALGENTA_SIDECAR_IMAGE`.
{% endhint %}

## Install in one command

```bash
curl -fsSL https://algenta.ai/install.sh | bash
```

The installer resolves a pinned image tag, downloads `infra/docker/docker-compose.selfhosted.yml` into `~/.algenta`, generates `~/.algenta/.env` with fresh secrets, starts the stack, runs migrations, and bootstraps an owner. It finishes by printing your API URL, the bootstrap API key, and the bootstrap user credentials.

You can steer the installer with environment variables:

```bash
# Pin a specific release and put the install somewhere other than ~/.algenta
ALGENTA_VERSION=git-1a2b3c4 ALGENTA_DIR=/opt/algenta \
  bash -c "$(curl -fsSL https://algenta.ai/install.sh)"
```

| Variable | Default | Effect |
| --- | --- | --- |
| `ALGENTA_DIR` | `$HOME/.algenta` | Install directory (holds `.env` and `docker-compose.yml`) |
| `ALGENTA_API_PORT` | `8000` | Host port the API binds to |
| `ALGENTA_VERSION` | latest `main` SHA | Release ref to pin (a git SHA or tag) |
| `ALGENTA_IMAGE_TAG` | derived from version | Pinned image tag (e.g. `git-1a2b3c4`) |
| `ALGENTA_IMAGE_REGISTRY` | `ghcr.io/algenta/decision-engine` | Image registry prefix |
| `ALGENTA_SKIP_IMAGE_PULL` | `0` | Set `1` to skip `compose pull` (use local images) |

### Manual install

Use the manual path when you want to inspect or modify the Compose bundle before starting it.

```bash
git clone https://github.com/algenta/decision-engine
cd decision-engine
docker compose -f infra/docker/docker-compose.selfhosted.yml up -d
```

Then run migrations and bootstrap (see below). The Compose file requires `ALGENTA_IMAGE_TAG` to be set to a pinned tag — it never ships a floating `:latest`. Provide it through an `.env` file in the same directory or `--env-file`.

## Durable secrets

Compose reads the `.env` file next to the Compose file — not your shell. Anything not written there is lost on the next `docker compose up`. The installer generates these once; keep them stable across restarts and back them up.

| Variable | What it is | Why it must stay stable |
| --- | --- | --- |
| `ALGENTA_CONFIG_ENCRYPTION_KEY` | 64-hex KEK that encrypts per-tenant provider keys at rest | Rotating or losing it makes every stored tenant provider key undecryptable (silent fail-closed) |
| `JWT_SECRET` | Auth token signing secret | Rotating invalidates existing sessions/tokens |
| `ALGENTA_API_KEY` | Operator/service API key the api+worker use | Used for engine-internal calls; keep aligned with a live key |
| `AGENT_CORE_AUTH_TOKEN` | Shared bearer for api/worker → sidecar | Without it the sidecar's inbound auth is open by default |
| `ALGENTA_AGENT_CORE_URL` | `http://sidecar:8787` | Docker-network address of the agent head |
| `ALGENTA_ENGINE_URL` | `http://api:8000` | Loopback URL the agent head dials to call back into `/v1` (must be the docker-network DNS name, not `localhost`) |
| `ALGENTA_ENGINE_API_KEY` | The dedicated **Engine Callback Key** | The agent head presents it (with `ALGENTA_ENGINE_URL`) to call back into `/v1` during a run |

{% hint style="warning" %}
Back up `ALGENTA_CONFIG_ENCRYPTION_KEY` immediately after install. If you reinstall over an existing database, restore your **previous** key into `.env` before starting, or stored per-tenant provider keys become unreadable.
{% endhint %}

The Engine Callback Key is minted by the bootstrap step as a least-privilege **service** key (no linked user, forced to `viewer`, scoped to repository-connector callbacks). It is separate from the rotatable bootstrap owner key, so rotating or revoking the owner key never breaks the agentic loop. The installer wires the minted value into `ALGENTA_ENGINE_API_KEY` and re-ups the stack so the api/worker pick it up.

## Deployment-mode flags

The generated `.env` defaults to the private enterprise profile. These are the flags that keep the deployment cloud-free and self-contained.

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALGENTA_DEPLOYMENT_MODE` | `self_hosted` | Private enterprise profile (use `air_gapped` for the strict profile) |
| `ALGENTA_DISABLE_CLOUD` | `1` | Blocks Algenta-owned cloud egress |
| `ALGENTA_DISABLE_TELEMETRY` | `1` | Disables outbound/vendor telemetry (local audit still runs) |
| `ALGENTA_TELEMETRY_MODE` | `local_audit` | Local-only audit; `control_plane_sync` only with an allowed control-plane URL |
| `ALGENTA_METERING_MODE` | `local_audit` | Local-only metering records |
| `ALGENTA_ALLOW_OUTBOUND_NETWORK` | `0` | Blocks Algenta-owned and undeclared public egress |
| `ALGENTA_EGRESS_ALLOWLIST` | `minio:9000` | Comma-separated allowlist for explicit connector/operator egress (e.g. `minio:9000,*.customer.internal`) |
| `ALGENTA_SOURCES_DIR` | `/home/app/.algenta/sources` | Local registry path for uploaded/queryable datasets |
| `ALGENTA_API_PUBLIC_BASE_URL` | `http://localhost:8000` | Public API origin used in quickstart links, billing redirects, and email content |
| `ALGENTA_APP_BASE_URL` | empty | Separate dashboard/account UI origin; leave blank to keep links on the API origin |

{% hint style="info" %}
`ALGENTA_DISABLE_TELEMETRY=1` means no outbound or vendor telemetry. It does not disable local audit events, local metering records, or local egress logs — those stay on your host for the proof endpoints below.
{% endhint %}

When you front the API with a public hostname, set `ALGENTA_API_PUBLIC_BASE_URL` to that origin (for example `https://algenta.acme.internal`) so generated links and email content point at your deployment. Set `ALGENTA_APP_BASE_URL` only when you run a separate dashboard; leaving it blank in a private profile keeps user-facing links on the API origin instead of pointing at Algenta cloud.

## Bootstrap an owner and key

If you used the one-line installer, this already ran and the credentials were printed. To run it manually (or re-run it idempotently):

```bash
cd ~/.algenta
docker compose exec -T api python scripts/bootstrap_self_host.py
```

The script prints machine-readable output. On the run that mints them, it includes the bootstrap key and the Engine Callback Key:

```
ALGENTA_BOOTSTRAP_READY=1
BOOTSTRAP_ORG_SLUG=self-hosted-org
BOOTSTRAP_USER_EMAIL=owner@selfhost.algenta.ai
BOOTSTRAP_USER_CREATED=1
BOOTSTRAP_API_KEY_ID=...
BOOTSTRAP_API_KEY_PREFIX=de_live_...
BOOTSTRAP_API_KEY=de_live_...
BOOTSTRAP_ENGINE_API_KEY=de_live_...
BOOTSTRAP_USER_PASSWORD=...
```

Override the bootstrap identity with environment variables if the defaults do not fit:

| Variable | Default |
| --- | --- |
| `ALGENTA_BOOTSTRAP_EMAIL` | `owner@selfhost.algenta.ai` |
| `ALGENTA_BOOTSTRAP_ORG_SLUG` | `self-hosted-org` |
| `ALGENTA_BOOTSTRAP_ORG_NAME` | `Self-Hosted Organization` |
| `ALGENTA_BOOTSTRAP_PASSWORD` | generated 32-char value |

### Rotate the bootstrap key

The bootstrap key is a one-time credential. Rotate it to a bounded-lifetime replacement, then revoke the original. The Engine Callback Key is separate and is not affected.

```bash
export ALGENTA_API_KEY='<paste the bootstrap key>'

# Mint a replacement
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"label":"mission-runtime","expires_at":"2028-05-19T00:00:00Z"}'
```

The response returns `raw_key`, `id`, `key_prefix`, and `expires_at`. The `raw_key` is shown once. Store the non-secret identity fields, switch your callers to the replacement, then revoke the bootstrap key by id:

```bash
export ALGENTA_API_KEY='<paste the replacement raw_key>'

curl -X DELETE http://localhost:8000/v1/api-keys/${BOOTSTRAP_API_KEY_ID} \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

## Run your first decision

```bash
curl -X POST http://localhost:8000/v1/simulate \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "scenario": {
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost": { "low": 30000, "high": 90000 }
      },
      "objective": "maximize_net_value"
    },
    "runs": 10000,
    "seed": 42
  }'
```

The response includes `status` and `recommended_action`. No SDK or Python install is required to use Algenta; the SDKs are a convenience over the same `/v1` surface.

## Verify the deployment

### Health

```bash
curl http://localhost:8000/v1/health
# {"status":"ok","timestamp":"..."}
```

### Privacy proof

The privacy report is the buyer-facing proof that the deployment is cloud-free. It returns the active deployment mode and a 24-hour egress summary.

```bash
curl http://localhost:8000/v1/admin/privacy-report \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

```json
{
  "deployment_mode": "self_hosted",
  "algenta_cloud_enabled": false,
  "vendor_telemetry_enabled": false,
  "telemetry_mode": "local_audit",
  "metering_mode": "local_audit",
  "algenta_owned_egress_count_24h": 0,
  "blocked_egress_attempt_count_24h": 0,
  "last_outbound_request_at": null,
  "last_algenta_owned_egress_at": null
}
```

Two companion endpoints give the full picture:

- `GET /v1/admin/egress-policy` — the active egress policy.
- `GET /v1/admin/egress-log` — the recorded egress decisions (paginated).

### Smoke and persistence proofs

Two scripts exercise the full stack end to end against a local build. The smoke script builds the prod images, starts the stack, bootstraps, rotates and revokes the key, runs a synchronous decision, and runs an async job to completion:

```bash
bash scripts/self_host_smoke.sh
# or
make self-host-smoke
```

The persistence proof additionally seeds a dataset, query, and run, then restarts the stack, takes a PostgreSQL dump and volume backups, recreates the stack from those backups, and re-verifies that the dataset, query result, run, and object-storage artifacts all survive:

```bash
bash scripts/self_host_persistence_proof.sh
# or
make self-host-persistence-proof
```

Both scripts run on isolated ports and project names so they will not collide with a running install.

## Operations

Run these from the install directory (`~/.algenta` by default):

```bash
cd ~/.algenta

docker compose ps                 # service status
docker compose logs -f api        # follow API logs
docker compose logs -f worker     # follow worker logs
docker compose logs -f sidecar    # follow agent-core logs
docker compose pull && docker compose up -d   # upgrade to a new pinned tag
docker compose stop               # stop the stack
```

After changing `.env`, run `docker compose up -d` again — Compose recreates only the services whose environment changed.

### TLS and exposure

PostgreSQL, Redis, and MinIO bind to `127.0.0.1` only and must not be exposed publicly. Put nginx or Caddy in front of the API on port `8000` for TLS termination, and set `CORS_ORIGINS` and `ALGENTA_API_PUBLIC_BASE_URL` to your public origin.

### Agentic repository flow

To enable the agentic repository / GitHub flow, set an LLM provider key in `.env` and re-up:

```bash
# in ~/.algenta/.env
ANTHROPIC_API_KEY=sk-ant-...
```

```bash
cd ~/.algenta && docker compose up -d
```

Scale the agent head horizontally when needed — the api and worker reach it through the round-robin `sidecar` service DNS:

```bash
docker compose up -d --scale sidecar=3
```

## Managed-host deploy (Fly.io)

For a managed origin on Fly.io with Cloudflare at the edge, the engine splits into a public `api` app and a private `engine` app (worker + co-located sidecar sharing one volume). The full runbook lives in `DEPLOY.md`, with `fly.api.toml`, `fly.engine.toml`, and `fly.control-plane.toml` defining the apps.

```bash
export FLY_API_TOKEN=…
make bootstrap        # create apps, Postgres, Redis, object storage, request cert
make deploy-fly       # deploy engine first, then api (runs alembic upgrade head)
make status           # fly status + /v1/health + secrets check
```

On Fly, set the same durable secrets per app: both apps need `ALGENTA_CONFIG_ENCRYPTION_KEY`, `ALGENTA_AGENT_CORE_TOKEN`, and the `DATABASE_URL`/`REDIS_URL`/`S3_*` set; the api app additionally needs `ALGENTA_ENGINE_URL`, `ALGENTA_ENGINE_API_KEY`, and `JWT_SECRET`; the engine app needs the matching `AGENT_CORE_AUTH_TOKEN`, `AGENT_CORE_REQUIRE_AUTH=1`, and the LLM key. Do not scale the engine app past one Machine — it holds the single shared working-directory volume.
