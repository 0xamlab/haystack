---
icon: server
description: Deploy and operate the Algenta engine on your own infrastructure — configure it, run it, and verify a self-hosted instance is healthy.
---

# Self-hosting

This page walks you through running Algenta in production on your own infrastructure: the API, bundled engine runtime, PostgreSQL, Redis, and S3-compatible object storage in one Docker Compose stack, installed with one command. The engine image already contains the async worker, compiled Mojo runtime, and agent runtime; users do not install or manage those components separately. You will install the stack, understand the durable secrets that must survive restarts, bootstrap an owner and API key, and verify the deployment with the built-in health, privacy, and persistence proofs.

## What you get

A self-hosted install is the complete service product. The Compose stack runs five services:

| Service | Image | Role |
| --- | --- | --- |
| `api` | `…/api:${ALGENTA_IMAGE_TAG}` | FastAPI backend on port `8000` (`/v1/*`) |
| `engine` | `…/engine:${ALGENTA_IMAGE_TAG}` | Async worker, compiled Mojo runtime, and agent runtime |
| `postgres` | `postgres:16-alpine` | Primary datastore (durable volume) |
| `redis` | `redis:7-alpine` | Queue + cache (append-only, durable volume) |
| `minio` | `minio/minio` | S3-compatible object storage for results and artifacts |

Integrate over HTTP or the SDKs once the service is running. The bundled engine powers simulations, datasets, queries, jobs, and the agentic repository / GitHub flow.

### Requirements

- Linux host (or macOS for evaluation) with the Docker daemon running.
- Docker Compose v2 (`docker compose`) or the standalone `docker-compose` CLI.
- 4+ vCPU and 8+ GB RAM recommended.
- Persistent disk for PostgreSQL and object storage.
- Outbound access to pull the pinned Algenta release images from `ghcr.io/thyn-ai/algenta`.

## Install in one command

{% stepper %}
{% step %}
### Run the installer

```bash title="install.sh"
curl -sSL https://algenta.ai/install.sh | bash
```

The installer resolves a pinned image tag, downloads `infra/docker/docker-compose.selfhosted.yml` into `~/.algenta`, generates `~/.algenta/.env` with fresh secrets, starts the stack, runs migrations, and bootstraps an owner. It finishes by printing your API URL, the bootstrap API key, and the bootstrap user credentials.
{% endstep %}

{% step %}
### Capture the printed credentials

The final output includes your API URL, the bootstrap API key, and the bootstrap user login. Store the bootstrap key in your secret manager now — the raw value is shown once.
{% endstep %}

{% step %}
### Back up the encryption key

Copy `ALGENTA_CONFIG_ENCRYPTION_KEY` out of `~/.algenta/.env` into durable backup before you do anything else. See [Durable secrets](#durable-secrets) for why this matters.
{% endstep %}
{% endstepper %}

You can steer the installer with environment variables:

```bash title="pin-and-relocate.sh"
# Pin a specific release and put the install somewhere other than ~/.algenta
ALGENTA_VERSION=git-1a2b3c4 ALGENTA_DIR=/opt/algenta \
  bash -c "$(curl -sSL https://algenta.ai/install.sh)"
```

### Installer environment variables
| Variable | Default | Effect |
| --- | --- | --- |
| `ALGENTA_DIR` | `$HOME/.algenta` | Install directory (holds `.env` and `docker-compose.yml`) |
| `ALGENTA_API_PORT` | `8000` | Host port the API binds to |
| `ALGENTA_VERSION` | latest `main` SHA | Release ref to pin (a git SHA or tag) |
| `ALGENTA_IMAGE_TAG` | derived from version | Pinned image tag (e.g. `git-1a2b3c4`) |
| `ALGENTA_IMAGE_REGISTRY` | `ghcr.io/thyn-ai/algenta` | Image registry prefix |
| `ALGENTA_SKIP_IMAGE_PULL` | `0` | Set `1` to skip `compose pull` (use local images) |

### Manual install

Use the manual path when you want to inspect or modify the Compose bundle before starting it. The installer downloads the pinned bundle to `~/.algenta/docker-compose.selfhosted.yml` — review or edit it there, then bring the stack up yourself:

```bash title="manual-install.sh"
cd ~/.algenta
# review or edit docker-compose.selfhosted.yml, then (ALGENTA_IMAGE_TAG is read from ~/.algenta/.env):
docker compose -f docker-compose.selfhosted.yml up -d
```

Then run migrations and bootstrap (see below).

{% hint style="warning" %}
The Compose file requires `ALGENTA_IMAGE_TAG` to be set to a pinned tag — it never ships a floating `:latest`. Provide it through an `.env` file in the same directory or `--env-file`.
{% endhint %}

## Durable secrets

Compose reads the `.env` file next to the Compose file — not your shell. Anything not written there is lost on the next `docker compose up`. The installer generates these once; keep them stable across restarts and back them up.

| Variable | What it is | Why it must stay stable |
| --- | --- | --- |
| `ALGENTA_CONFIG_ENCRYPTION_KEY` | 64-hex KEK that encrypts per-tenant provider keys at rest | Rotating or losing it makes every stored tenant provider key undecryptable (silent fail-closed) |
| `JWT_SECRET` | Auth token signing secret | Rotating invalidates existing sessions/tokens |
| `ALGENTA_API_KEY` | Operator/service API key the API and engine use | Used for engine-internal calls; keep aligned with a live key |
| `AGENT_CORE_AUTH_TOKEN` | Shared bearer for API → bundled engine | Generated by the installer and required by default |
| `ALGENTA_AGENT_CORE_URL` | `http://engine:8787` | Docker-network address of the bundled agent runtime |
| `ALGENTA_ENGINE_URL` | `http://api:8000` | Loopback URL the agent head dials to call back into `/v1` (must be the docker-network DNS name, not `localhost`) |
| `ALGENTA_ENGINE_API_KEY` | The dedicated **Engine Callback Key** | The agent head presents it (with `ALGENTA_ENGINE_URL`) to call back into `/v1` during a run |

{% hint style="danger" %}
Back up `ALGENTA_CONFIG_ENCRYPTION_KEY` immediately after install. If you reinstall over an existing database, restore your **previous** key into `.env` before starting, or stored per-tenant provider keys become unreadable.
{% endhint %}

The Engine Callback Key is minted by the bootstrap step as a least-privilege **service** key (no linked user, forced to `viewer`, scoped to repository-connector callbacks). It is separate from the rotatable bootstrap owner key, so rotating or revoking the owner key never breaks the agentic loop. The installer wires the minted value into `ALGENTA_ENGINE_API_KEY` and re-ups the stack so the API and engine pick it up.

## Deployment-mode flags

The generated `.env` defaults to the private enterprise profile. These are the flags that keep the deployment cloud-free and self-contained.

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALGENTA_DEPLOYMENT_MODE` | `self_hosted` | Private enterprise profile (use `air_gapped` for the strict profile) |
| `ALGENTA_DISABLE_CLOUD` | `1` | Blocks Algenta-owned cloud egress |
| `ALGENTA_DISABLE_TELEMETRY` | `1` | Disables outbound/vendor telemetry (local audit still runs) |
| `ALGENTA_TELEMETRY_MODE` | `local_audit` | Local-only audit; `control_plane_sync` only with an allowed control-plane URL |
| `ALGENTA_METERING_MODE` | `local_audit` | Local-only execution audit records; not a billing meter |
| `ALGENTA_ALLOW_OUTBOUND_NETWORK` | `0` | Blocks Algenta-owned and undeclared public egress |
| `ALGENTA_EGRESS_ALLOWLIST` | `minio:9000` | Comma-separated allowlist for explicit connector/operator egress (e.g. `minio:9000,*.customer.internal`) |
| `ALGENTA_SOURCES_DIR` | `/home/app/.algenta/sources` | Local registry path for uploaded/queryable datasets |
| `ALGENTA_API_PUBLIC_BASE_URL` | `http://localhost:8000` | Public API origin used in quickstart links, billing redirects, and email content |
| `ALGENTA_APP_BASE_URL` | empty | Separate dashboard/account UI origin; leave blank to keep links on the API origin |

{% hint style="info" %}
`ALGENTA_DISABLE_TELEMETRY=1` means no outbound or vendor telemetry. Local audit events and egress logs remain on your host for the proof endpoints below; they are not sent to Algenta and are not a billing meter.
{% endhint %}

When you front the API with a public hostname, set `ALGENTA_API_PUBLIC_BASE_URL` to that origin (for example `https://algenta.acme.internal`) so generated links and email content point at your deployment. Set `ALGENTA_APP_BASE_URL` only when you run a separate dashboard; leaving it blank in a private profile keeps user-facing links on the API origin instead of pointing at Algenta cloud.

## Bootstrap an owner and key

If you used the one-line installer, this already ran and the credentials were printed. To run it manually (or re-run it idempotently):

```bash title="bootstrap.sh"
cd ~/.algenta
docker compose exec -T api python scripts/bootstrap_self_host.py
```

The script prints machine-readable output. On the run that mints them, it includes the bootstrap key and the Engine Callback Key:

```text title="bootstrap-output.txt"
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

### Override the bootstrap identity
Override the bootstrap identity with environment variables if the defaults do not fit:

| Variable | Default |
| --- | --- |
| `ALGENTA_BOOTSTRAP_EMAIL` | `owner@selfhost.algenta.ai` |
| `ALGENTA_BOOTSTRAP_ORG_SLUG` | `self-hosted-org` |
| `ALGENTA_BOOTSTRAP_ORG_NAME` | `Self-Hosted Organization` |
| `ALGENTA_BOOTSTRAP_PASSWORD` | generated 32-char value |

### Rotate the bootstrap key

The bootstrap key is a one-time credential. Rotate it to a bounded-lifetime replacement, then revoke the original. The Engine Callback Key is separate and is not affected.

{% stepper %}
{% step %}
### Mint a replacement

```bash title="mint-replacement.sh"
export ALGENTA_API_KEY='<paste the bootstrap key>'

# Mint a replacement
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"label":"mission-runtime","expires_at":"2028-05-19T00:00:00Z"}'
```

The response returns `raw_key`, `id`, `key_prefix`, and `expires_at`. The `raw_key` is shown once. Store the non-secret identity fields and switch your callers to the replacement.
{% endstep %}

{% step %}
### Revoke the original

```bash title="revoke-bootstrap.sh"
export ALGENTA_API_KEY='<paste the replacement raw_key>'

curl -X DELETE http://localhost:8000/v1/api-keys/${BOOTSTRAP_API_KEY_ID} \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```
{% endstep %}
{% endstepper %}

## Run your first decision

No SDK or Python install is required to use Algenta; the SDKs are a convenience over the same `/v1` surface. The response includes `status` and `recommended_action`.

{% tabs %}
{% tab title="cURL" %}
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
{% endtab %}

{% tab title="Python" %}
```python title="first_decision.py"
import os
import httpx

resp = httpx.post(
    "http://localhost:8000/v1/simulate",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "mode": "auto",
        "scenario": {
            "variables": {
                "revenue": {"low": 80000, "high": 200000},
                "cost": {"low": 30000, "high": 90000},
            },
            "objective": "maximize_net_value",
        },
        "runs": 10000,
        "seed": 42,
    },
)
result = resp.json()
print(result["status"], result["recommended_action"])
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="firstDecision.ts"
const resp = await fetch("http://localhost:8000/v1/simulate", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    mode: "auto",
    scenario: {
      variables: {
        revenue: { low: 80000, high: 200000 },
        cost: { low: 30000, high: 90000 },
      },
      objective: "maximize_net_value",
    },
    runs: 10000,
    seed: 42,
  }),
});

const result = await resp.json();
console.log(result.status, result.recommended_action);
```
{% endtab %}
{% endtabs %}

## Verify the deployment

### Health

```bash title="health.sh"
curl http://localhost:8000/v1/health
# {"status":"ok","timestamp":"..."}
```

{% hint style="success" %}
**Expected result** — `/v1/health` returns `{"status":"ok"}` with a current timestamp. A non-200 or connection error means the engine is not up yet.
{% endhint %}

### Privacy proof

The privacy report proves the deployment is cloud-free. It returns the active deployment mode and a 24-hour egress summary.

{% tabs %}
{% tab title="Request" %}
```bash
curl http://localhost:8000/v1/admin/privacy-report \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```
{% endtab %}

{% tab title="Response" %}
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
{% endtab %}
{% endtabs %}

Two companion endpoints give the full picture:

- `GET /v1/admin/egress-policy` — the active egress policy.
- `GET /v1/admin/egress-log` — the recorded egress decisions (paginated).

### Smoke and persistence proofs

Two scripts exercise the full stack end to end against a local build.

### Smoke proof: full lifecycle in one run
The smoke script builds the prod images, starts the stack, bootstraps, rotates and revokes the key, runs a synchronous decision, and runs an async job to completion:

```bash title="self_host_smoke.sh"
bash scripts/self_host_smoke.sh
# or
make self-host-smoke
```

### Persistence proof: survive a backup-and-restore cycle
The persistence proof additionally seeds a dataset, query, and run, then restarts the stack, takes a PostgreSQL dump and volume backups, recreates the stack from those backups, and re-verifies that the dataset, query result, run, and object-storage artifacts all survive:

```bash title="self_host_persistence_proof.sh"
bash scripts/self_host_persistence_proof.sh
# or
make self-host-persistence-proof
```

{% hint style="success" %}
Both scripts run on isolated ports and project names, so they will not collide with a running install.
{% endhint %}

## Operations

Run these from the install directory (`~/.algenta` by default):

```bash title="operations.sh"
cd ~/.algenta

docker compose ps                 # service status
docker compose logs -f api        # follow API logs
docker compose logs -f engine     # follow worker, Mojo, and agent-runtime logs
docker compose pull && docker compose up -d   # upgrade to a new pinned tag
docker compose stop               # stop the stack
```

{% hint style="info" %}
After changing `.env`, run `docker compose up -d` again — Compose recreates only the services whose environment changed.
{% endhint %}

### TLS and exposure

{% hint style="warning" %}
PostgreSQL, Redis, and MinIO bind to `127.0.0.1` only and must not be exposed publicly. Put nginx or Caddy in front of the API on port `8000` for TLS termination, and set `CORS_ORIGINS` and `ALGENTA_API_PUBLIC_BASE_URL` to your public origin.
{% endhint %}

### Agentic repository flow

To enable the agentic repository / GitHub flow, set an LLM provider key in `.env` and re-up:

```bash title=".env"
# in ~/.algenta/.env
ANTHROPIC_API_KEY="replace-with-your-anthropic-api-key"
```

```bash title="reup.sh"
cd ~/.algenta && docker compose up -d
```

The bundled engine uses one shared working-directory volume. Keep it at one replica in the supported Compose deployment; scale the stateless API separately on an orchestrator that provides an external load balancer and shared storage.

## Split-app deploy (optional reference pattern)

The single Compose stack above is the supported deployment. If your platform (a managed container host, your own Kubernetes cluster, or similar) needs a public/private split, an optional pattern is to run the FastAPI backend as a public-facing app and the bundled engine as a private app behind it, with a TLS-terminating edge (nginx, Caddy, or your platform's load balancer) in front. Adapt this to your own infrastructure and your platform's own deployment tooling.

{% hint style="danger" %}
Do not run more than one instance of the private engine app when it holds a single shared working-directory volume; that volume cannot be mounted by multiple instances at once. Scale the public API app freely.
{% endhint %}

Set the same durable secrets on each app: both need `ALGENTA_CONFIG_ENCRYPTION_KEY`, the shared agent-runtime auth token, and the `DATABASE_URL`/`REDIS_URL`/`S3_*` connection settings; the public API app additionally needs `ALGENTA_ENGINE_URL`, `ALGENTA_ENGINE_API_KEY`, and `JWT_SECRET`; the private engine app needs `AGENT_CORE_REQUIRE_AUTH=1` and the LLM provider key.

## Related pages

{% content-ref url="install.md" %}
[install.md](install.md)
{% endcontent-ref %}

{% content-ref url="authentication.md" %}
[authentication.md](authentication.md)
{% endcontent-ref %}

{% content-ref url="licensing.md" %}
[licensing.md](licensing.md)
{% endcontent-ref %}

{% content-ref url="operate/monitoring.md" %}
[monitoring.md](operate/monitoring.md)
{% endcontent-ref %}

{% content-ref url="operate/byok-kms.md" %}
[byok-kms.md](operate/byok-kms.md)
{% endcontent-ref %}

{% content-ref url="troubleshooting.md" %}
[troubleshooting.md](troubleshooting.md)
{% endcontent-ref %}
