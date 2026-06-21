---
icon: rocket-launch
---

# Quickstart

This page takes you from nothing to a working Algenta engine in about two minutes. You will run the one-line installer, confirm the engine is healthy, mint a bounded API key to replace the bootstrap key, and make your first decision call. If you would rather not run a server at all, the last section shows the zero-friction local demo: `pip install algenta-core` and `algenta demo`.

There are two ways to start, and they are complementary:

- **Self-hosted engine** — a real HTTP service on `localhost:8000` with Postgres, Redis, and object storage, driven over `/v1`. Use this when you want the full decision engine, API keys, and the agentic flows.
- **Local runtime (`algenta-core`)** — a pip-installable, in-process library and CLI for register, resolve, and query against your own files. No server, no key, no network.

{% hint style="info" %}
The engine reads your key from `ALGENTA_API_KEY` (or the legacy `DE_API_KEY`). Export one of them once and every example below works unchanged.
{% endhint %}

## Step 1 — Install the engine and check health

Run the installer. It checks for Docker and Docker Compose, pulls pinned images, writes a self-hosted `.env`, runs migrations, and bootstraps an owner plus a first API key.

```bash
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

```bash
curl http://localhost:8000/v1/health
```

A healthy engine returns:

```json
{ "status": "ok", "timestamp": "2026-06-20T12:00:00Z" }
```

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
No SDK or Python install is required to use the engine. Everything in Steps 1 through 2 is plain `curl` against `/v1`. Browse the full interactive API at `http://localhost:8000/docs`.
{% endhint %}

## Step 2 — Mint a bounded replacement key

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

```json
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

Request body fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `label` | string | yes | Human-readable name (1–255 chars), e.g. `mission-runtime`. |
| `expires_at` | RFC 3339 timestamp | no | Must be in the future. Omit for a non-expiring key. |
| `device_limit` | integer (`>= 0`) | no | Max registered devices on the local-runtime path. `0` keeps the plan default. |

Swap your shell over to the replacement key:

```bash
export ALGENTA_API_KEY='de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # the raw_key returned above
```

{% hint style="info" %}
Rotating the bootstrap key does not break the agentic repository flow. The engine-callback key is a separate, long-lived key the installer wires into `.env` as `ALGENTA_ENGINE_API_KEY`. Leave it alone.
{% endhint %}

You can store the `id` to revoke the key later with `DELETE /v1/api-keys/{id}`. The engine refuses to revoke your last active key, so you cannot lock yourself out.

## Step 3 — Your first call in code

For programmatic use, install `algenta-core` and drive the `Runtime`. The default `Runtime()` runs locally and in-process — register a source, resolve a plan, and run the query. No server or key required.

```bash
pip install algenta-core
```

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")

plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)

print(result)
```

The flow is always the same three calls: `connect` registers a source under a name, `resolve` turns an intent into a typed plan, and `query` executes it. Adding `group_by` is one more key:

```python
plan = rt.resolve({
    "source_name": "orders",
    "metric": "revenue",
    "group_by": "product_line",
})
result = rt.query(plan)
```

{% hint style="info" %}
When you are ready to point the same code at your self-hosted engine instead of the in-process runtime, construct it in API mode and pass your key:

```python
import os
from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
rt = Runtime(mode="api", api_key=api_key)
plan = rt.resolve({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})
result = rt.query(plan)
```
{% endhint %}

## Zero-friction demo (no server, no key)

If you want to see Algenta work before installing the engine, the `algenta` CLI ships with `algenta-core` and runs a fully local, deterministic demo against a bundled dataset.

```bash
pip install algenta-core
algenta demo
```

`algenta demo` walks the local path: register, resolve, verify, query. In a terminal it is interactive; pass flags to script it.

| Command | What it does |
| --- | --- |
| `algenta demo` | Interactive local runtime demo (picker in a TTY). |
| `algenta demo --list` | List the selectable demo scenarios and exit. |
| `algenta demo --scenario region` | Run one named scenario and exit. |
| `algenta demo --all --no-interactive` | Run every scenario in sequence, no prompts. |

The built-in scenario keys are `product_line`, `region`, `canada_filter`, and `guardrail`. Run a non-interactive single scenario like this:

```bash
algenta demo --scenario region --no-interactive
```

To preview your own data, import a CSV. This validates local registration and schema discovery, then prints the exact `Runtime` snippet to continue in Python.

```bash
algenta import orders.csv --name orders
```

The import preview ends with copy-pasteable code that mirrors Step 3:

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
```

You can import several sources at once to discover cross-table relationships:

```bash
algenta import orders.csv financial.csv ratings.csv
```

{% hint style="info" %}
The demo and `import` run entirely on your machine. Private profiles fail closed: Algenta does not silently fall back to the cloud. To connect the CLI or SDK to your engine later, run `algenta upgrade` for the exact `ALGENTA_BASE_URL` and key steps.
{% endhint %}

## Where to go next

- Run the engine in production: see the self-hosting guide for TLS, secrets, and the `.env` reference written by the installer.
- Call `/v1` directly without the SDK: the engine exposes the full surface at `http://localhost:8000/docs`.
- Manage keys: list with `GET /v1/api-keys`, revoke with `DELETE /v1/api-keys/{id}`.
