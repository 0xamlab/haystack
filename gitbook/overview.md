---
icon: house
---

# What Algenta is

This page explains what Algenta is, where it sits in your stack, and how you talk to it. By the end you will know the four ways to reach the engine — HTTP API, the `algenta-core` Runtime, the `algenta-sdk` clients, and the `algenta-mcp` server — and you will have copy-pasteable examples for each. When you are ready to run it, the Install and Quickstart pages take over.

## Algenta is the engine, not an app

Algenta is the **engine**. It is a local-first, deterministic **computational intelligence runtime**: a large library of mathematical and operational functions and high-performance libraries, plus simulation, decision planning, an agent runtime, decision memory, and governed execution. All of it sits behind one universal surface — **API / SDK / MCP** — with metering, auth, BYOK, and enterprise controls built in.

You do not adopt Algenta as a finished vertical product. You deploy the engine and integrate against it. Specialized products are surfaces on top of the one engine.

{% hint style="info" %}
**Official position.** Algenta is a self-hosted decision engine you deploy on your infrastructure. Integrate via API or SDK. Run locally for development if needed.
{% endhint %}

## What lives inside the engine

A single backend and runtime core powers every surface:

| Capability | What it does |
| --- | --- |
| Math / operational libraries | A large catalog of deterministic functions and high-performance libraries, addressable by name. |
| Simulation | Monte Carlo simulation returning a structured decision envelope (`POST /v1/simulate`). |
| Decision planning | Structured `DecisionPlan` and decision envelopes. |
| Agent runtime | Persisted agent runs with events, checkpoints, telemetry, and lifecycle control. |
| Decision memory | Log decisions, record outcomes, and review them later. |
| Governed execution | Discover, summarize, resolve, verify, and query data under a governed contract. |

Around that core sit the cross-cutting controls every deployment gets: **metering** (each `POST /v1/simulate` consumes one simulation from your quota), **auth** (API keys, optional device binding), **BYOK** (bring your own provider keys), and **enterprise controls** (air-gapped profile, telemetry disable, operator proof endpoints).

## The four surfaces

Pick the surface that fits your caller. They all reach the same engine and honor the same governance and metering.

### 1. HTTP API (`/v1`)

The default integration surface. Every route is versioned under `/v1`. No SDK or Python install required.

```bash
# Health check — confirm the engine is up
curl http://localhost:8000/v1/health
```

```bash
# Run your first decision
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

The governed data path follows the same versioned shape: `GET /v1/data?search=...&compact=1` then `GET /v1/data/{dataset_id}/summary` then `POST /v1/query`.

### 2. The `algenta-core` Runtime

A high-level Python runtime for governed data/query flows, local runtime control, and local Mojo libraries. The `Runtime` object selects how it reaches the engine via `mode`.

```bash
pip install algenta-core            # pure local runtime
pip install "algenta-core[cloud]"   # adds the API-backed transport
```

```python
import os
from algenta import QueryFilterCondition, QueryFilterSpec, Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(
    mode="self_hosted",
    api_key=api_key,
    base_url="http://localhost:8000",
)

datasets = rt.list_datasets(search="orders", compact=True)
summary = rt.get_dataset_summary(datasets.datasets[0].dataset_id)
```

| `mode` | Reaches the engine via | Use when |
| --- | --- | --- |
| `local` | In-process pure-Python runtime | Development, offline, embedded work. |
| `self_hosted` | HTTP to your own deployment | Production on your infrastructure. Never falls back to the hosted control plane. |
| `api` | HTTP to the Algenta cloud control plane | Cloud Managed path. |

{% hint style="info" %}
`Runtime(mode="api")` and `Runtime(mode="self_hosted")` fail closed if `algenta-sdk` is not installed. Private profiles (`self_hosted`, `air_gapped`) never silently fall back to Algenta cloud.
{% endhint %}

### 3. The `algenta-sdk` clients (Python + TypeScript)

Thin, typed clients over the HTTP API. Same name on both languages: `AlgentaClient`.

```bash
pip install algenta-sdk      # Python
npm install algenta-sdk      # TypeScript / JavaScript
```

```python
import os
from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
client = AlgentaClient(api_key=api_key, base_url="https://api.algenta.ai")

datasets = client.list_datasets(search="orders", compact=True)
```

```typescript
import { AlgentaClient } from 'algenta-sdk';

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error('Set ALGENTA_API_KEY or DE_API_KEY before running this example.');
}

const client = new AlgentaClient({ apiKey });
const result = await client.simulate({
  mode: 'auto',
  scenario: {
    variables: { revenue: { low: 80000, high: 200000 } },
    objective: 'maximize_net_value',
  },
});
console.log(result.recommended_action, result.confidence);
```

The Python SDK also ships the `de` CLI for the same surface:

```bash
de contract
de data list --search orders --compact --limit 5
de data summary orders_facts
de runtime execute rerank_eval hit_rate_at_k --args-json '[[1,0,1,1,0],5]' --format json
```

### 4. The `algenta-mcp` server

A Model Context Protocol bridge so AI agents can reach governed datasets, exact queries, simulations, decision memory, and agent runs as tools. Point it at any Algenta deployment.

```bash
pipx install algenta-mcp        # or: pip install algenta-mcp
```

`algenta-mcp` runs the **stdio** transport by default (Cursor, Claude Desktop). For HTTP/SSE clients use `algenta-mcp --mode http --port 8001`.

```json
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

## What Algenta is not

Knowing the boundaries keeps your architecture honest. Algenta is **not**:

- an LLM-to-SQL generator
- a semantic-model-first BI layer
- an agent framework
- a `pip install` product pretending to be a platform

It is a deterministic execution engine you deploy and integrate against.

## Products that consume the SDK

Specialized products are surfaces on top of the one engine. Each lives in its own repository and talks to Algenta over the API/SDK — they are not the engine itself.

| Product | Domain |
| --- | --- |
| **Codna** | Coding — repository intelligence: triage, fix / PR-repair, blast-radius, simulate. |
| **Mission** | API-first local integration (the `:8000` API + MCP stack). |
| **Cohenta** | Marketing intelligence. |
| **Decimas** | Trading / market simulation. |
| **Escrypto** | Crypto governance. |

One plugin platform, multiple editions — not multiple codebases.

## Deployment defaults

Self-hosted is the default. Cloud is optional.

| Setting | Effect |
| --- | --- |
| `api + worker + postgres + redis + object storage` | The self-hosted service stack, deployed with Docker Compose. |
| `ALGENTA_DEPLOYMENT_MODE=air_gapped` | Strict privacy profile. |
| `ALGENTA_DISABLE_TELEMETRY=1` | Disables outbound/vendor telemetry; keeps local audit. |
| `ALGENTA_API_PUBLIC_BASE_URL` / `ALGENTA_APP_BASE_URL` | Control user-facing self-hosted links without cloud fallback. |
| `GET /v1/admin/privacy-report` | The operator proof endpoint. |

{% hint style="info" %}
Self-hosted by default, cloud optional. The local `Runtime()` path is a development and embedded surface; the self-hosted service is the primary product contract.
{% endhint %}

## Next steps

- **Install** — deploy the engine on your infrastructure. The fastest start is `curl -sSL https://algenta.ai/install.sh | bash`, which prints the API URL, a bootstrap API key, and a ready-to-run `POST /v1/simulate` example.
- **Quickstart** — verify with `GET /v1/health`, then run your first decision through `POST /v1/simulate` or your first governed query through the `/v1/data` flow.
