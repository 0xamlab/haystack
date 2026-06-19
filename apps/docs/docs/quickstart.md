---
sidebar_position: 2
slug: /quickstart
---

# Quickstart

In this guide you will:

1. Start Algenta locally
2. Verify the API is running
3. Run your first decision or first governed dataset query

## Install

```bash
curl -sSL https://codna.ai/install.sh | bash
```

The installer:

- validates Docker and Compose
- downloads the self-hosted Compose bundle
- generates `.env`
- pulls pinned API and worker images
- starts the stack
- runs migrations
- creates a bootstrap owner and API key

## Health check

The installer prints:

```text
Algenta is running.

API: http://localhost:8000
Health: curl http://localhost:8000/v1/health
API Key: <SELF_HOST_BOOTSTRAP_KEY>
```

Verify the API:

```bash
curl http://localhost:8000/v1/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## Bootstrap API key

Temporarily export the bootstrap key printed by the installer so you can rotate it:

```bash
export ALGENTA_API_KEY='<SELF_HOST_BOOTSTRAP_KEY>'
```

> **Critical**
> The installer prints the bootstrap API key only once. Store it before closing the terminal.

## Rotate the bootstrap key

Create a bounded-lifetime replacement key before using the service for recurring
workloads:

```bash
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"label":"mission-runtime","expires_at":"2028-05-19T00:00:00Z","device_limit":3}'
```

The returned `raw_key` value is shown only once. Record the returned `id`,
`key_prefix`, `device_limit`, and `expires_at`, then replace `ALGENTA_API_KEY`
with that replacement key before recurring service access:

```bash
export ALGENTA_API_KEY='<paste the replacement key returned above>'
```

An explicit `device_limit` also binds ordinary hosted API traffic for that key,
not just the device-registration path. The SDKs send the stable device headers
automatically. If you are calling the API directly with `curl` or a raw HTTP
client, send `X-Algenta-Device-Id`, `X-Algenta-Platform`, and
`X-Algenta-Hostname-Hash` on authenticated requests that use a capped key. The
first successful hosted request for a new capped device returns
`X-Algenta-Device-Binding-Token`; store that value and replay it on later
requests from the same device. The SDKs do this automatically.

## First request

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

Expected response:

```json
{
  "status": "completed",
  "recommended_action": "proceed",
  "confidence": 0.82,
  "rationale": "Expected value is positive in 82% of scenarios.",
  "metrics": {
    "expected_value": 105000.0,
    "probability_of_loss": 0.18
  },
  "scenarios_run": 10000
}
```

No SDK or Python install is required to use Algenta.

## First governed dataset query

If you are using Algenta for governed data/query rather than simulation, start
with the live machine-readable contract:

```bash
curl "http://localhost:8000/v1/meta/contract" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

If an older self-hosted node still returns `404` for `/v1/meta/contract`,
fetch `http://localhost:8000/openapi.json` and read
`x-primary-data-query-contract` instead. The official SDKs, CLI, and MCP
tooling already do that fallback automatically.

Then continue with the low-token discovery path:

```bash
curl "http://localhost:8000/v1/data?search=orders&compact=1&limit=5" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

Then fetch a low-token summary for the dataset you want:

```bash
curl "http://localhost:8000/v1/data/orders_summary/summary" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

Run a governed exact query only after you have the right dataset:

```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "orders_summary",
    "metric": { "role": "base_measure", "hint": "revenue" },
    "aggregation": "sum"
  }'
```

Widen to `POST /v1/query/batch` when one question needs several governed exact
metrics, or to `POST /v1/query/sql-report` only when you need a wide read-only
rowset over an already authorized dataset.

Next: Configure production setup -> [Operations](/operations)
