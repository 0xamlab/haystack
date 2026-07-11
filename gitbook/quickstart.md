---
icon: bolt
description: Run Algenta end to end in minutes — install the integrated service, mint an API key, and make your first decision call.
---

# Quickstart

This page takes you from nothing to a working Algenta engine in about two minutes. You will run the one-line installer, confirm the integrated service is healthy, mint a bounded API key to replace the bootstrap key, and make your first decision call.

There are two supported execution targets, and both use the same HTTP contract:

- **Self-hosted engine** — a real HTTP service on `localhost:8000` with Postgres, Redis, and object storage, driven over `/v1`. Use this when you want the full decision engine, API keys, and the agentic flows.
- **Algenta cloud** — use `https://api.algenta.ai` with an API key; Algenta operates the integrated runtime.

{% hint style="info" %}
The engine reads your key from `ALGENTA_API_KEY` (or the legacy `DE_API_KEY`). Export one of them once and every example below works unchanged.
{% endhint %}

## Self-host the engine in three steps

{% stepper %}
{% step %}
### Install the engine and check health

Run the installer. It checks for Docker and Docker Compose, pulls pinned images, writes a self-hosted `.env`, runs migrations, and bootstraps an owner plus a first API key.

```bash title="install.sh"
curl -sSL https://algenta.ai/install.sh | bash
```

When it finishes, it prints the API URL, a bootstrap API key, and a ready-to-run decision example. The output looks like this:

```text
 Algenta is running.

  API:          http://localhost:8000
  Health:       curl http://localhost:8000/v1/health
  API Docs:     http://localhost:8000/docs

  API Key:      de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  Bootstrap key id: 6f1c...­
  Bootstrap key prefix: de_live_xxxx
  Bootstrap user: owner@your-host.local
```

Confirm the engine is up:

{% tabs %}
{% tab title="cURL" %}
```bash
curl http://localhost:8000/v1/health
```
{% endtab %}
{% endtabs %}

A healthy engine returns:

```json title="health.json"
{ "status": "ok", "timestamp": "2026-06-20T12:00:00Z" }
```

{% hint style="success" %}
**Expected result** — the health endpoint returns `{"status":"ok"}`. The engine is running and ready for authenticated calls.
{% endhint %}

Export the bootstrap key the installer printed so the rest of the commands authenticate:

```bash
export ALGENTA_API_KEY='de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
```

Now run your first decision. The installer prints this exact `POST /v1/simulate` example:

```bash
curl -X POST http://localhost:8000/v1/simulate \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "scenario": {
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost":    { "low": 30000, "high": 90000 }
      },
      "objective": "maximize_net_value"
    },
    "runs": 10000,
    "seed": 42
  }'
```

{% hint style="info" %}
No SDK or Python install is required to use the engine. Everything in the first two steps is plain `curl` against `/v1`. Browse the full interactive API at `http://localhost:8000/docs`.
{% endhint %}
{% endstep %}

{% step %}
### Mint a bounded replacement key

The bootstrap key is for first contact. Replace it with a key you control: give it a label, an expiry, and a device limit for the local-runtime path. Create it with `POST /v1/api-keys`, authenticating with the bootstrap key you just exported.

```bash
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "mission-runtime",
    "expires_at": "2028-05-19T00:00:00Z",
    "device_limit": 3
  }'
```

The response is returned once and contains the raw key. Capture `raw_key`, `id`, and `key_prefix` before you move on — the raw key is never shown again.

```json title="api-key-response.json"
{
  "id": "f2a1c0de-1234-4abc-9def-0123456789ab",
  "label": "mission-runtime",
  "key_prefix": "de_live_a1b2",
  "device_limit": 3,
  "raw_key": "de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "created_at": "2026-06-20T12:01:00Z",
  "expires_at": "2028-05-19T00:00:00Z"
}
```

{% hint style="warning" %}
The `raw_key` is shown exactly once and is never recoverable. Capture it now. If you lose it, mint a new key and revoke the old one.
{% endhint %}

{% expandable title="Request body fields" %}
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `label` | string | yes | Human-readable name (1–255 chars), e.g. `mission-runtime`. |
| `expires_at` | RFC 3339 timestamp | no | Must be in the future. Omit for a non-expiring key. |
| `device_limit` | integer (`>= 0`) | no | Max registered devices on the local-runtime path. `0` keeps the plan default. |
{% endexpandable %}

Swap your shell over to the replacement key:

```bash
export ALGENTA_API_KEY='de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # the raw_key returned above
```

{% hint style="success" %}
Rotating the bootstrap key does not break the agentic repository flow. The engine-callback key is a separate, long-lived key the installer wires into `.env` as `ALGENTA_ENGINE_API_KEY`. Leave it alone.
{% endhint %}

You can store the `id` to revoke the key later with `DELETE /v1/api-keys/{id}`. The engine refuses to revoke your last active key, so you cannot lock yourself out.
{% endstep %}

{% step %}
### Your first call in code

For programmatic use today, install the published Python HTTP SDK and call the engine you just started.

{% tabs %}
{% tab title="Python" %}
```bash
pip install algenta-sdk
```

```python title="first_call.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="http://localhost:8000",
)

result = client.simulate(
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

print(result)
```
{% endtab %}
{% endtabs %}

For governed data queries, connect a dataset through the API and then call the query methods from the same client:

```python title="query.py"
datasets = client.list_datasets(search="orders", compact=True)
summary = client.get_dataset_summary(datasets.datasets[0].dataset_id)
query_result = client.query_with_metadata({
    "dataset_id": summary.dataset_id,
    "metric": {"hint": "revenue"},
    "aggregation": "sum",
})
```

{% endstep %}
{% endstepper %}

## Where to go next

- Run the engine in production: see the self-hosting guide for TLS, secrets, and the `.env` reference written by the installer.
- Call `/v1` directly without the SDK: the engine exposes the full surface at `http://localhost:8000/docs`.
- Manage keys: list with `GET /v1/api-keys`, revoke with `DELETE /v1/api-keys/{id}`.

{% content-ref url="self-hosting.md" %}
[self-hosting.md](self-hosting.md)
{% endcontent-ref %}

{% content-ref url="authentication.md" %}
[authentication.md](authentication.md)
{% endcontent-ref %}

{% content-ref url="sdk/python.md" %}
[sdk/python.md](sdk/python.md)
{% endcontent-ref %}

{% content-ref url="api/reference.md" %}
[api/reference.md](api/reference.md)
{% endcontent-ref %}
