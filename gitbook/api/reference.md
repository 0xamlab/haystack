---
icon: code
---

# API endpoint reference

This page is the working reference for the Algenta HTTP API. Every endpoint below is served under the `/v1` prefix by the API server (`apps/api_server`) and is reachable the same way whether you run the engine yourself or call the hosted control plane. You can drive everything here directly with `curl`, or through the `algenta-sdk` clients for Python and TypeScript. Each section lists the real method, path, and purpose; the high-traffic endpoints include copy-pasteable `curl` examples.

## Base URL and authentication

All requests go to your engine base URL plus the endpoint path. For a local engine that is `http://localhost:8000`; for the hosted plane, your provisioned URL.

Authenticate with your API key as a bearer token. `X-API-Key` is also accepted for legacy clients.

```bash
export ALGENTA_API_URL="http://localhost:8000"
export ALGENTA_API_KEY="sk_live_..."
```

```bash
# Preferred
curl -H "Authorization: Bearer ${ALGENTA_API_KEY}" "${ALGENTA_API_URL}/v1/me"

# Legacy header, same effect
curl -H "X-API-Key: ${ALGENTA_API_KEY}" "${ALGENTA_API_URL}/v1/me"
```

{% hint style="info" %}
The same key works across the API, the SDKs, and the CLI. The Python SDK reads `ALGENTA_API_KEY`; the TypeScript SDK reads `ALGENTA_API_KEY` plus `ALGENTA_API_URL` / `ALGENTA_BASE_URL` for the endpoint. The `algenta` CLI (from `algenta-core`) uses the same credentials.
{% endhint %}

### SDK clients

```python
# Python — pip install algenta-sdk
from decision_engine import CodnaClient   # AlgentaClient is a back-compat alias

client = CodnaClient(api_key="sk_live_...", base_url="http://localhost:8000")
```

```typescript
// TypeScript — npm install algenta-sdk
import { Runtime } from "algenta-sdk";

const rt = new Runtime({ apiKey: process.env.ALGENTA_API_KEY, baseUrl: process.env.ALGENTA_API_URL });
```

---

## Data and query

Onboard governed datasets, check their state, and resolve or query across them.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/datasets` | List onboarded datasets |
| `POST` | `/v1/datasets/onboard` | Onboard a dataset from a connector or URL |
| `POST` | `/v1/datasets/onboard/file` | Onboard a dataset from an uploaded file |
| `GET` | `/v1/datasets/{dataset_id}/status` | Poll onboarding / training status |
| `POST` | `/v1/datasets/{dataset_id}/retrain` | Trigger a retrain of the dataset model |
| `POST` | `/v1/resolve` | Resolve a natural-language ask to a concrete query plan |
| `POST` | `/v1/query` | Execute a governed query and return rows |
| `POST` | `/v1/query/batch` | Run multiple queries in one request |
| `POST` | `/v1/query/sql-report` | Produce a structured SQL report |

```bash
# List datasets
curl -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  "${ALGENTA_API_URL}/v1/datasets"
```

```bash
# Resolve a plain-language ask into a query plan
curl -X POST "${ALGENTA_API_URL}/v1/resolve" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query": "top 10 customers by revenue last quarter"}'
```

```bash
# Poll dataset status
curl -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  "${ALGENTA_API_URL}/v1/datasets/ds_123/status"
```

```python
# SDK equivalents
plan = client.resolve(query="top 10 customers by revenue last quarter")
rows = client.query(...)
```

{% hint style="info" %}
The query surface also exposes `GET /v1/sources/schema` (governed schema discovery) and `POST /v1/verify` (verify a resolved plan before execution).
{% endhint %}

---

## Decisions and simulation

The simulation engine runs Monte Carlo and related models natively. `POST /v1/simulate` is the hot path: p50 under 15ms server-side, with async persistence. Each successful call consumes one simulation from your monthly quota and returns `429` when quota or rate limit is exceeded.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/v1/simulate` | Run a simulation, return a decision envelope |
| `POST` | `/v1/decisions` | Create a decision record |
| `POST` | `/v1/decisions/plan` | Generate a decision plan |
| `GET` | `/v1/decisions/{decision_id}` | Fetch a decision |
| `POST` | `/v1/decisions/{decision_id}/execute` | Mark a decision as executed |
| `POST` | `/v1/decisions/{decision_id}/outcome` | Record the realized outcome |
| `POST` | `/v1/recommend` | Rank actions and recommend one |
| `POST` | `/v1/score` | Score a single action |
| `POST` | `/v1/batch` | Batch scoring (alias of the batch recommend path) |
| `POST` | `/v1/compare` | Compare N scenarios head to head |
| `POST` | `/v1/simulate/what-if` | What-if sensitivity on a base scenario |

### POST /v1/simulate

```bash
curl -X POST "${ALGENTA_API_URL}/v1/simulate" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "runs": 50000,
    "scenario": {
      "objective": "maximize_net_value",
      "variables": {
        "revenue":  { "low": 80000,  "high": 140000 },
        "cost":     { "low": 50000,  "high": 70000 }
      }
    }
  }'
```

Auto mode takes `low`/`high` ranges per variable and picks distributions for you. Expert mode (`"mode": "expert"`) accepts an explicit `distribution` and `params` per variable across the full distribution set (normal, lognormal, triangular, beta, poisson, pareto, and more) and a `simulation_model` such as `monte_carlo`, `qmc_sobol`, `lhs`, `bootstrap`, `mcmc`, or `sensitivity`.

The response is a decision envelope: `recommended_action`, `confidence`, `rationale`, `metrics` (e.g. `expected_value`, `probability_of_loss`), `percentiles`, `scenarios_run`, a structured `decision_plan`, and `request_id`.

```python
# Python SDK
result = client.simulate(
    mode="auto",
    runs=50000,
    scenario={
        "objective": "maximize_net_value",
        "variables": {
            "revenue": {"low": 80000, "high": 140000},
            "cost":    {"low": 50000, "high": 70000},
        },
    },
)
print(result.recommended_action, result.confidence)
```

```typescript
// TypeScript SDK
const result = await rt.simulate({
  mode: "auto",
  runs: 50000,
  scenario: {
    objective: "maximize_net_value",
    variables: {
      revenue: { low: 80000, high: 140000 },
      cost:    { low: 50000, high: 70000 },
    },
  },
});
```

### POST /v1/recommend

```bash
curl -X POST "${ALGENTA_API_URL}/v1/recommend" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "runs": 10000,
    "scenario": { "objective": "maximize_net_value", "variables": { } }
  }'
```

---

## LLM utility

A provider-neutral surface for chat, structured responses, embeddings, reranking, and token accounting. Requests are governed and metered like the rest of the API.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/models` | List available models |
| `POST` | `/v1/chat/completions` | Chat completion (OpenAI-compatible shape) |
| `POST` | `/v1/responses` | Structured response generation |
| `POST` | `/v1/embeddings` | Compute embeddings |
| `POST` | `/v1/embeddings/similarity` | Similarity between embedding inputs |
| `POST` | `/v1/rerank` | Rerank documents against a query |
| `POST` | `/v1/tokenize` | Tokenize text |
| `POST` | `/v1/count_tokens` | Count tokens without generating |
| `POST` | `/v1/artifacts/resolve` | Resolve an artifact reference |

```bash
# Chat completion
curl -X POST "${ALGENTA_API_URL}/v1/chat/completions" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Summarize the decision envelope."}]
  }'
```

```bash
# Count tokens
curl -X POST "${ALGENTA_API_URL}/v1/count_tokens" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"text": "how many tokens is this"}'
```

```python
client.count_tokens(text="how many tokens is this")
client.rerank(...)
```

---

## Agent runs

Create, observe, and control agent runs. Read endpoints (events, telemetry, checkpoints, mission-events) are the ones you poll; the action endpoints drive run lifecycle.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/v1/agent/runs` | Create an agent run |
| `GET` | `/v1/agent/runs` | List agent runs |
| `GET` | `/v1/agent/runs/{run_id}` | Fetch a run |
| `GET` | `/v1/agent/runs/{run_id}/events` | Run event stream |
| `GET` | `/v1/agent/runs/{run_id}/checkpoints` | Run checkpoints |
| `GET` | `/v1/agent/runs/{run_id}/telemetry` | Run telemetry |
| `GET` | `/v1/agent/runs/{run_id}/mission-events` | Mission-level events |
| `POST` | `/v1/agent/runs/{run_id}/resume` | Resume a paused run |
| `POST` | `/v1/agent/runs/{run_id}/cancel` | Cancel a run |
| `POST` | `/v1/agent/runs/{run_id}/approve` | Approve a gated step |
| `POST` | `/v1/agent/runs/{run_id}/fork` | Fork a run |
| `POST` | `/v1/agent/runs/{run_id}/replay` | Replay a run |

There are also collection-level read endpoints — `GET /v1/agent/runs/events`, `/checkpoints`, `/telemetry`, `/mission-events` — that aggregate across runs, useful for dashboards and webhook-style polling.

```bash
# Create a run
curl -X POST "${ALGENTA_API_URL}/v1/agent/runs" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{ "...": "AgentRunCreateRequest fields" }'

# Poll its events
curl -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  "${ALGENTA_API_URL}/v1/agent/runs/run_123/events"

# Approve a gated step
curl -X POST "${ALGENTA_API_URL}/v1/agent/runs/run_123/approve" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

---

## Repositories (Codna)

Repository intelligence: snapshot a repo, query its graph, triage, plan and simulate patches, then apply. `GET /v1/repositories/capabilities` advertises what the engine supports.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/repositories/capabilities` | List repository capabilities |
| `POST` | `/v1/repositories/{repository_id}/snapshots` | Create a snapshot |
| `GET` | `/v1/repositories/{repository_id}/snapshots/{snapshot_id}` | Fetch a snapshot |
| `POST` | `/v1/repositories/{repository_id}/triage` | Triage the repository |
| `POST` | `/v1/repositories/{repository_id}/graph-query` | Query the code graph |
| `POST` | `/v1/repositories/{repository_id}/decision-plans` | Generate decision plans |
| `POST` | `/v1/repositories/{repository_id}/pipeline` | Run the analysis pipeline |
| `POST` | `/v1/repositories/{repository_id}/simulate` | Simulate over the repo |
| `POST` | `/v1/repositories/{repository_id}/simulate-patch` | Simulate a candidate patch |
| `POST` | `/v1/repositories/{repository_id}/apply` | Apply a patch |
| `POST` | `/v1/repositories/{repository_id}/security-analyses` | Run a security analysis |
| `POST` | `/v1/repositories/{repository_id}/security-analyses/closure` | Compute analysis closure |

```bash
# Capabilities
curl -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  "${ALGENTA_API_URL}/v1/repositories/capabilities"

# Triage a repository
curl -X POST "${ALGENTA_API_URL}/v1/repositories/repo_42/triage" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{ "...": "triage request" }'
```

```python
# Python SDK — the repository capability plane
client.triage_repository(...)
```

{% hint style="info" %}
Trigger repository work through the SDK (`triage_repository`) or the HTTP endpoints above. The engine runs the analysis server-side. Do not call the internal repository core directly in a cold process — that is the wrong plane and forces a cold reparse.
{% endhint %}

---

## Control plane

Identity, keys, devices, billing, credits, licensing, and bring-your-own-key provider credentials.

### Identity and usage

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/me` | Current org / identity |
| `PATCH` | `/v1/me` | Update profile fields |
| `GET` | `/v1/usage` | Usage to date |
| `GET` | `/v1/limits` | Plan limits |

```bash
curl -H "Authorization: Bearer ${ALGENTA_API_KEY}" "${ALGENTA_API_URL}/v1/me"
curl -H "Authorization: Bearer ${ALGENTA_API_KEY}" "${ALGENTA_API_URL}/v1/usage"
```

### API keys

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/api-keys` | List API keys |
| `POST` | `/v1/api-keys` | Create an API key |
| `DELETE` | `/v1/api-keys/{key_id}` | Revoke an API key |

```bash
curl -X POST "${ALGENTA_API_URL}/v1/api-keys" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"label":"mission-runtime","expires_at":"2028-05-19T00:00:00Z","device_limit":3}'
```

### Devices

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/v1/device/register` | Register a device |
| `POST` | `/v1/device/heartbeat` | Device heartbeat |
| `GET` | `/v1/device/list` | List devices |
| `DELETE` | `/v1/device/{registration_id}` | Deregister a device |

### Billing and credits

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/billing/info` | Billing summary |
| `POST` | `/v1/billing/checkout` | Start a checkout session |
| `POST` | `/v1/billing/portal` | Open the billing portal |
| `POST` | `/v1/billing/webhook` | Stripe webhook receiver |
| `POST` | `/v1/credits/refresh` | Refresh credit balance |

### License

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/license/revocations` | Revocation list |
| `POST` | `/v1/license/challenge` | License challenge |
| `POST` | `/v1/license/renew` | Renew the license |

### BYOK provider keys

Store your own LLM provider credentials per backend so calls route through your keys.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/provider-keys` | List configured provider keys |
| `POST` | `/v1/provider-keys` | Add a provider key |
| `DELETE` | `/v1/provider-keys/{backend}` | Remove a provider key for a backend |

```bash
curl -X POST "${ALGENTA_API_URL}/v1/provider-keys" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"backend":"...","api_key":"..."}'
```

---

## Admin

Operator-only endpoints for privacy reporting, runtime introspection, and egress policy. These require an admin-scoped key.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/admin/privacy-report` | Tenant privacy report |
| `GET` | `/v1/admin/runtime/modules` | Loaded runtime modules |
| `GET` | `/v1/admin/runtime/benchmarks` | Runtime benchmark results |
| `GET` | `/v1/admin/runtime/validation` | Runtime validation status |
| `GET` | `/v1/admin/egress-policy` | Active egress allowlist policy |
| `GET` | `/v1/admin/egress-log` | Recent egress decisions |

```bash
curl -H "Authorization: Bearer ${ALGENTA_ADMIN_KEY}" \
  "${ALGENTA_API_URL}/v1/admin/egress-policy"
```

---

## Meta and health

Unauthenticated or low-privilege endpoints for service discovery and health checks.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/health` | Liveness check |
| `GET` | `/v1/version` | Server version |
| `GET` | `/v1/meta/contract` | Platform contract metadata |
| `GET` | `/v1/runtime/manifest` | Runtime manifest |
| `GET` | `/v1/control-plane/meta` | Control-plane metadata |

```bash
curl "${ALGENTA_API_URL}/v1/health"
curl "${ALGENTA_API_URL}/v1/version"
```

{% hint style="info" %}
The complete, always-current schema for every endpoint, including request and response models, is published by the running server. Point your tooling at the engine's generated OpenAPI document to stay in sync with the deployed version.
{% endhint %}
