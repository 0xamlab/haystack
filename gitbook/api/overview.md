---
icon: book-open
---

# API overview

This page orients you to the Algenta REST API: where it lives, how to authenticate, how to discover what an instance supports, and how the endpoints are organized. Everything here is a copy-pasteable starting point. The same HTTP contract backs the Python and TypeScript SDKs, the `algenta` CLI, and the MCP server, so anything you can do over HTTP you can also do through those clients without changing semantics.

## Base URL

Every request targets one base URL. There is no global default that points at someone else's data; you choose explicitly.

| Deployment | Base URL | When to use |
| --- | --- | --- |
| Hosted (Algenta cloud) | `https://api.algenta.ai` | The managed control plane. This is `DEFAULT_BASE_URL`. |
| Self-hosted | `http://localhost:8000` | The engine you run yourself (Docker, Fly, or local). |

All routes live under `/v1`. A few operational routes are unversioned (`/metrics`, `/v1/health/ready` for liveness/readiness, `/docs`, `/redoc`, `/openapi.json`).

```bash
export ALGENTA_BASE_URL="https://api.algenta.ai"   # or http://localhost:8000
export ALGENTA_API_KEY="de_live_..."
```

{% hint style="info" %}
The interactive OpenAPI explorer is served from the running instance at `/docs` (Swagger UI), `/redoc` (ReDoc), and the raw schema at `/openapi.json`. The schema is the source of truth for request and response shapes.
{% endhint %}

## Authentication

Authenticate with a bearer API key:

```
Authorization: Bearer ${ALGENTA_API_KEY}
```

Live keys are prefixed `de_live_` and test keys `de_test_`. A legacy `X-API-Key:` header is also accepted for older clients, but `Authorization: Bearer` is the canonical scheme.

```bash
curl -sS "${ALGENTA_BASE_URL}/v1/me" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

The SDKs read the key from the environment automatically. The variable is `ALGENTA_API_KEY` (the older `DE_API_KEY` still works):

```python
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])
me = client.get_contract()  # GET /v1/meta/contract
```

```typescript
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });
const contract = await client.getContract();
```

### Device headers for capped keys

Some keys are bound to a device (for example, an installed runtime or a capped seat). When a request is made with such a key, the engine requires device-identity headers and a binding token. Sending them yourself is only necessary if you are calling the API directly; the SDKs and CLI manage device binding for you.

| Header | Meaning |
| --- | --- |
| `X-Algenta-Device-Id` | Stable device identifier (minimum 16 characters). |
| `X-Algenta-Platform` | Platform string for the device. |
| `X-Algenta-Hostname-Hash` | Hash of the hostname (never the raw hostname). |
| `X-Algenta-Device-Binding-Token` | Token proving this device is bound to the key. |

```bash
curl -sS "${ALGENTA_BASE_URL}/v1/simulate" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "X-Algenta-Device-Id: ${ALGENTA_DEVICE_ID}" \
  -H "X-Algenta-Platform: ${ALGENTA_PLATFORM}" \
  -H "X-Algenta-Hostname-Hash: ${ALGENTA_HOSTNAME_HASH}" \
  -H "X-Algenta-Device-Binding-Token: ${ALGENTA_DEVICE_BINDING_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{ "mode": "auto", "scenario": { "name": "smoke", "variables": { "x": { "low": 1, "high": 2 } }, "objective": "maximize_net_value" }, "runs": 1000 }'
```

On the first bound request the engine issues a fresh `X-Algenta-Device-Binding-Token` in the response headers; store it and send it on subsequent calls. If a device header is missing, the error body names the exact `required_header`.

## Discovery endpoints

Before hardcoding anything, ask the instance what it is and what it supports. These four endpoints are how the SDKs, CLI, and MCP bootstrap themselves.

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/health` | Liveness. Returns `{ "status": "ok", "timestamp": ... }`. No auth. |
| `GET /v1/meta/contract` | Machine-readable platform contract: endpoint families, SDK and CLI and MCP method names, governed-filter rules. |
| `GET /v1/runtime/manifest` | Signed runtime manifest describing the engine build. |
| `GET /v1/models` | The LLM utility-model catalog this instance can actually execute. |

```bash
# Is it up?
curl -sS "${ALGENTA_BASE_URL}/v1/health"

# What does it support? (drives the SDKs)
curl -sS "${ALGENTA_BASE_URL}/v1/meta/contract" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"

# Which runtime build is running?
curl -sS "${ALGENTA_BASE_URL}/v1/runtime/manifest" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"

# Which models can I call here?
curl -sS "${ALGENTA_BASE_URL}/v1/models" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

{% hint style="info" %}
`GET /v1/models` advertises only models that are truly executable on the instance: runtime-backed or explicitly configured provider-backed. If a model is not listed, calling it will not work. Read the catalog, then route to it.
{% endhint %}

## Endpoint families

The router areas map cleanly to where you look for a given capability. All paths are under `/v1`.

| Area | Representative paths | What it does |
| --- | --- | --- |
| Data and query | `/v1/data`, `/v1/data/{dataset_id}/summary`, `/v1/resolve`, `/v1/verify`, `/v1/query`, `/v1/query/batch`, `/v1/query/sql-report`, `/v1/sources` | Discover datasets, resolve hints, run governed exact queries and read-only SQL reports. |
| Decisions | `/v1/decisions`, `/v1/decisions/plan`, `/v1/decisions/{id}/outcome`, `/v1/decisions/{id}/execute` | Decision memory: record decisions, plan, log outcomes, replay. |
| Simulate and recommend | `/v1/simulate`, `/v1/simulate/templates`, `/v1/templates/{id}/run`, `/v1/recommend`, `/v1/score`, `/v1/compare` | Monte Carlo simulation, templates, scoring and recommendation. |
| Agent runs | `/v1/agent/runs`, `/v1/agent/runs/{run_id}`, `/v1/agent/runs/{run_id}/events` | Launch and inspect agentic runs and their event streams. |
| Repositories | `/v1/repositories/capabilities`, `/v1/repositories/{id}/snapshots`, `/v1/repositories/{id}/triage`, `/v1/repositories/{id}/graph-query` | Repository intelligence: snapshot, triage, graph queries, security analyses. |
| LLM | `/v1/models`, plus the chat/embedding/utility routes under `/v1` | The governed LLM surface; models routed per the catalog. |
| Capabilities and connectors | `/v1/capability-providers`, `/v1/capability-bindings`, `/v1/capabilities`, `/v1/capabilities/route`, `/v1/capabilities/execute` | The capability plane: providers, bindings, routing and execution. |
| Account, keys, devices | `/v1/me`, `/v1/usage`, `/v1/limits`, `/v1/api-keys`, `/v1/device/register`, `/v1/device/heartbeat`, `/v1/device/list` | Identity, usage, key management, device lifecycle. |
| Billing, credits, metering | `/v1/billing/info`, `/v1/billing/checkout`, `/v1/billing/portal`, `/v1/credits/refresh`, `/v1/metering` | Plan and billing, credit buckets, local-runtime metering flush. |
| License | `/v1/license/challenge`, `/v1/license/renew`, `/v1/license/revocations` | License verification and renewal for self-hosted and bound deployments. |

The full, current set is always available at `/openapi.json` and described machine-readably at `/v1/meta/contract`.

## Request and response shape

Requests and responses are JSON. Send `Content-Type: application/json` on bodies. A typical write — an auto-mode simulation:

```bash
curl -sS "${ALGENTA_BASE_URL}/v1/simulate" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "simulation_model": "monte_carlo",
    "scenario": {
      "name": "Product launch decision",
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost":    { "low": 40000, "high": 90000 }
      },
      "objective": "maximize_net_value"
    },
    "runs": 10000
  }'
```

The same call through the SDK:

```python
envelope = client.simulate({
    "mode": "auto",
    "simulation_model": "monte_carlo",
    "scenario": {
        "name": "Product launch decision",
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 40000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    "runs": 10000,
})
```

Successful responses carry the resource shape documented for each endpoint (for `/v1/simulate`, a decision envelope with `expected_value`, `percentiles`, `recommended_action`, `confidence`, `execution_ms`, and a structured `decision_plan`). Every response includes a `request_id` you can quote in support requests.

### Error envelope

Every error — auth, validation, not found, rate limit, server — is returned in one envelope:

```json
{
  "error": {
    "code": "invalid_api_key",
    "message": "The API key provided is invalid, expired, or has been revoked.",
    "request_id": "req_...",
    "docs_url": "https://docs.algenta.ai/errors/invalid_api_key"
  }
}
```

| Status | Typical `code` | Meaning |
| --- | --- | --- |
| 401 | `authentication_required`, `invalid_api_key` | No key, or the key is invalid/expired/revoked. |
| 403 | `organization_suspended`, `account_suspended`, `email_verification_required` | Authenticated but not permitted. |
| 422 | `validation_error` | Request body or query params failed validation. `details` lists each `field` and `issue`. |
| 429 | rate limit / quota exceeded | Slow down or upgrade your plan. |
| 500 | `internal_error` | Unexpected server error; quote the `request_id`. |

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": [
      { "field": "body.runs", "issue": "Input should be less than or equal to 100000" }
    ],
    "request_id": "req_...",
    "docs_url": "https://docs.algenta.ai/errors/validation_error"
  }
}
```

{% hint style="info" %}
Branch on `error.code`, not on the human-readable `message`. Codes are stable; messages are not.
{% endhint %}

## One contract, many clients

The HTTP API is the contract. The SDKs, the CLI, and MCP are thin, faithful surfaces over it — the method and tool names are themselves published in `/v1/meta/contract`.

```python
# Python SDK — direct client over HTTP
from decision_engine import AlgentaClient
client = AlgentaClient(api_key="de_live_...")
datasets = client.list_datasets(search="orders", compact=True)
```

```typescript
// TypeScript SDK
import { AlgentaClient } from "algenta-sdk";
const client = new AlgentaClient({ apiKey: "de_live_..." });
const datasets = await client.listDatasets({ search: "orders", compact: true });
```

```bash
# CLI — same operations
de contract
de data list --search orders --compact --limit 10
de data summary <dataset_id>
```

MCP clients (Claude Desktop, Codex, and other MCP hosts) connect to the same instance at `/mcp/sse` with the matching tools at `/mcp/tools`, exposing tools such as `get_contract`, `list_data`, `query_data`, `route_capabilities`, and `execute_capability`. Whichever surface you choose, you are speaking the same `/v1` contract — pick the one that fits your stack and start from the discovery endpoints above.
