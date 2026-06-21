---
icon: download
---

# Install

This page gets Algenta onto your machine. It covers every install path: the self-hosted service (one command, Docker), the local runtime package, the HTTP SDKs for Python and TypeScript, and the MCP server for agent tools. Each section ends with a verification step so you know the install worked. Pick the path that matches what you are building; you do not need all of them.

{% hint style="info" %}
To make a first call against the self-hosted service, you do not need to install any SDK or Python package. The installer prints a ready-to-run `curl` command. Reach for an SDK only when you want typed responses and retries inside your application code.
{% endhint %}

## Choose an install path

| You want to... | Install | Section |
| --- | --- | --- |
| Run the full Algenta service (API, worker, database, storage) locally or on a server | `curl ... install.sh \| bash` | [Self-hosted service](#self-hosted-service) |
| Embed the deterministic runtime in a Python process | `pip install algenta-core` | [Local runtime package](#local-runtime-package) |
| Call a running Algenta API from Python | `pip install algenta-sdk` | [Python SDK](#python-sdk) |
| Call a running Algenta API from TypeScript or JavaScript | `npm install algenta-sdk` | [TypeScript SDK](#typescript-sdk) |
| Expose Algenta as MCP tools to Cursor or Claude Desktop | `pipx install algenta-mcp` | [MCP server](#mcp-server) |

## Self-hosted service

The self-hosted service is the complete Algenta deployment: the API, the worker, Postgres, Redis, and MinIO object storage, wired together with Docker Compose. One command installs and starts everything.

{% hint style="info" %}
**Prerequisites.** Docker, with the daemon running, plus Docker Compose. Either the Compose v2 plugin (`docker compose`) or the standalone `docker-compose` binary works; the installer detects whichever is present.
{% endhint %}

{% stepper %}
{% step %}
### Run the installer

```bash
curl -sSL https://algenta.ai/install.sh | bash
```

The installer:

1. Checks for Docker and Docker Compose and confirms the daemon is reachable.
2. Resolves a pinned release and writes the Compose bundle to `$HOME/.algenta`.
3. Generates a `.env` with stable secrets (kept owner-only at mode `600`).
4. Pulls the `ghcr.io/algenta/decision-engine` image and starts the stack.
5. Waits for the API, runs database migrations, and bootstraps an owner plus an API key.
{% endstep %}

{% step %}
### Save the bootstrap key

When it finishes, the installer prints your API endpoint, your bootstrap API key, and a ready-to-run `curl` command. Save the API key.

{% hint style="warning" %}
The bootstrap API key is shown once. Copy it before you close the terminal. To recover from a lost key, rotate it (see [Next steps](#next-steps)).
{% endhint %}
{% endstep %}

{% step %}
### Verify the install

The liveness endpoint returns `{"status":"ok"}`:

```bash
curl http://localhost:8000/v1/health
```

```json title="health response"
{ "status": "ok", "timestamp": "2026-06-20T00:00:00Z" }
```

Then run your first decision with the bootstrap key the installer printed.

```bash title="first-simulation.sh"
export ALGENTA_API_KEY='<paste the bootstrap key>'

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
{% endstep %}
{% endstepper %}

### Configure the install with environment variables

Set these before running the installer to control where it installs, which port it binds, and which image it pins.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ALGENTA_DIR` | `$HOME/.algenta` | Install directory. Holds `docker-compose.yml` and `.env`. |
| `ALGENTA_API_PORT` | `8000` | Host port the API binds to. |
| `ALGENTA_VERSION` | latest `main` | Release ref to pin. A git SHA or a release tag. |
| `ALGENTA_IMAGE_TAG` | derived from the ref | Exact image tag to pull. |
| `ALGENTA_IMAGE_REGISTRY` | `ghcr.io/algenta/decision-engine` | Image registry and repository. |
| `ALGENTA_SKIP_IMAGE_PULL` | `0` | Set to `1` to skip `compose pull` (use an already-pulled image). |

{% expandable title="Pin a specific build and bind a non-default port" %}
```bash
ALGENTA_VERSION=v1.0.0 \
ALGENTA_IMAGE_TAG=v1.0.0 \
ALGENTA_API_PORT=8080 \
  bash -c "curl -sSL https://algenta.ai/install.sh | bash"
```
{% endexpandable %}

{% hint style="danger" %}
The generated `.env` contains `ALGENTA_CONFIG_ENCRYPTION_KEY`, which encrypts every stored per-tenant provider key at rest. Back it up. If you reinstall over an existing database with a different key, the previously stored keys become undecryptable. Restore your prior key into `.env` before starting.
{% endhint %}

### Manage the stack

The installer prints these too. Run them from your install directory.

```bash title="manage-stack.sh"
cd ~/.algenta && docker compose ps
cd ~/.algenta && docker compose logs -f api
cd ~/.algenta && docker compose pull && docker compose up -d   # upgrade
cd ~/.algenta && docker compose stop
```

{% hint style="info" %}
If you are on the standalone binary, substitute `docker-compose` for `docker compose`.
{% endhint %}

## Local runtime package

`algenta-core` is the Algenta runtime as a Python package. Use it to run deterministic resolve and query flows in-process, or to drive a remote API through one `Runtime` object.

{% tabs %}
{% tab title="Local only" %}
```bash
pip install algenta-core
```

This installs `algenta-core` with no external dependencies. It is enough for `Runtime(mode="local")` and the local Mojo libraries.
{% endtab %}

{% tab title="API-backed" %}
`Runtime(mode="api")` and `Runtime(mode="self_hosted")` fail closed unless `algenta-sdk` is installed. Add it with the `cloud` extra:

```bash
pip install "algenta-core[cloud]"
```

Or install the SDK directly:

```bash
pip install algenta-sdk
```
{% endtab %}
{% endtabs %}

### Verify

`algenta-core` ships an `algenta` CLI. Confirm the install and inspect capabilities:

```bash
algenta version
```

Run the built-in demo:

```bash
algenta demo
```

Drive a remote engine from Python:

```python title="remote_runtime.py"
import os
from algenta import Runtime

rt = Runtime(mode="api", api_key=os.environ["ALGENTA_API_KEY"])
plan = rt.resolve({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})
result = rt.query(plan)
```

{% hint style="info" %}
Use Cloud Managed base URLs only with `Runtime(mode="api")`. For self-hosted deployments use `Runtime(mode="self_hosted")` with an explicit `base_url` and the API key your operator provisioned.
{% endhint %}

## Python SDK

`algenta-sdk` is the HTTP client for a running Algenta API. The installed import package is `decision_engine`.

```bash
pip install algenta-sdk
```

### Verify

The client reads `ALGENTA_API_KEY` from the environment and accepts a `base_url` for self-hosted deployments. `AlgentaClient` is the preferred name; `DecisionEngineClient` remains as a compatibility alias.

```python title="verify_python_sdk.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="http://localhost:8000",
)

print(client.health())   # {'status': 'ok', 'timestamp': '...'}
print(client.version())  # {'api_version': '1.0.0', 'engine_version': '...', 'environment': '...'}

envelope = client.simulate(
    scenario={
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 30000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    runs=10000,
    seed=42,
)
```

{% hint style="warning" %}
If you call `AlgentaClient()` with no `api_key` and no `ALGENTA_API_KEY` set, construction raises immediately with a message telling you which environment variable to set. The legacy `DE_API_KEY` is also accepted.
{% endhint %}

## TypeScript SDK

The TypeScript SDK is published under the same name on npm.

```bash
npm install algenta-sdk
```

### Verify

The client reads `ALGENTA_API_KEY` in Node, and takes `apiKey` and `baseUrl` in its config. `AlgentaClient` and `DecisionEngineClient` are both exported.

```typescript title="verify-ts-sdk.ts"
import { AlgentaClient } from 'algenta-sdk';

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: 'http://localhost:8000',
});

console.log(await client.health());   // { status: 'ok', timestamp: '...' }
console.log(await client.version());  // { api_version: '1.0.0', engine_version: '...', environment: '...' }

const envelope = await client.simulate({
  mode: 'auto',
  scenario: {
    variables: {
      revenue: { low: 80000, high: 200000 },
      cost: { low: 30000, high: 90000 },
    },
    objective: 'maximize_net_value',
  },
  runs: 10000,
  seed: 42,
});
```

{% hint style="info" %}
The package requires Node 18 or newer.
{% endhint %}

## MCP server

`algenta-mcp` exposes the Algenta API as Model Context Protocol tools for Cursor, Claude Desktop, and other MCP clients.

{% stepper %}
{% step %}
### Install the server

Install it as an isolated CLI with `pipx`:

```bash
pipx install algenta-mcp
```

{% expandable title="Alternative: install with pip into the current environment" %}
```bash
pip install algenta-mcp
```
{% endexpandable %}
{% endstep %}

{% step %}
### Choose a transport

Point it at your deployment with `ALGENTA_BASE_URL` and `ALGENTA_API_KEY`. It runs the stdio transport by default. For HTTP/SSE clients, run it as a server:

```bash
algenta-mcp --mode http --port 8001
```
{% endstep %}

{% step %}
### Wire it into Cursor or Claude Desktop

Add this to your MCP config (Cursor `~/.cursor/mcp.json`, or Claude Desktop `claude_desktop_config.json`):

```json title="mcp.json"
{
  "mcpServers": {
    "algenta": {
      "command": "algenta-mcp",
      "env": {
        "ALGENTA_BASE_URL": "http://localhost:8000",
        "ALGENTA_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

The server connects your agent to governed dataset discovery, exact queries, deterministic utility-model routes, product helpers, simulations, and persisted agent runs.
{% endstep %}
{% endstepper %}

## Next steps

{% hint style="success" %}
The install is done. Before production, walk through the operator checklist below, then continue to the quickstart for a first end-to-end decision.
{% endhint %}

- Self-hosted operators: review `~/.algenta/.env` before production, set `ANTHROPIC_API_KEY` for the agentic repository flow, and put TLS in front of the API port.
- Rotate the bootstrap key with `POST /v1/api-keys` and a bounded `expires_at`, then store the returned `raw_key` (shown once) before revoking the bootstrap key.

{% content-ref url="quickstart.md" %}
[quickstart.md](quickstart.md)
{% endcontent-ref %}

{% content-ref url="self-hosting.md" %}
[self-hosting.md](self-hosting.md)
{% endcontent-ref %}

{% content-ref url="authentication.md" %}
[authentication.md](authentication.md)
{% endcontent-ref %}

{% content-ref url="sdk/python.md" %}
[sdk/python.md](sdk/python.md)
{% endcontent-ref %}
