---
icon: list-check
description: Submit a long-running simulation as an async job, poll its status by id, fetch the result when it completes, and cancel a queued or running job.
---

# Run a long simulation as an async job

This guide shows you how to offload a large or slow simulation to an asynchronous [job](../help/glossary.md). Instead of holding an HTTP connection open while the engine works, you submit the simulation to `POST /v1/jobs`, get a `job_id` back immediately, then poll `GET /v1/jobs/{job_id}` until the job reaches a terminal state and read the result from `GET /v1/jobs/{job_id}/result`. You need a verified account and an API key (see [Authentication](../authentication.md)). The examples target the hosted API at `https://api.algenta.ai`; a self-hosted engine at `http://localhost:8000` behaves the same way.

{% hint style="info" %}
A synchronous `POST /v1/simulate` (see [Simulate a scenario](simulate.md)) returns the decision envelope in one round trip and is the right choice for interactive, fast runs. Reach for an async job when a single request would otherwise run long enough to risk a client or gateway timeout.
{% endhint %}

## When to use an async job

Use an async job when the work does not comfortably fit in one request/response cycle. The clearest case is a very large [simulation](../concepts/simulation-models.md) — an expert-mode run can request up to **1,000,000** runs (`runs` is bounded `100 <= runs <= 1_000_000` in expert mode, and `100 <= runs <= 100_000` in auto mode). A 1,000,000-run scenario, a heavy `sensitivity` or `mcmc` model, or any operation you expect to take many seconds is a good candidate. The async path also lets you fire many jobs without blocking, and optionally receive a webhook when each finishes via the `callback_url`.

Submitting a job creates an underlying [simulation run](../guides/simulate.md) in the `queued` state with `execution_type = async`, then enqueues the work. If no background worker is available (common in local and self-hosted setups), the API executes the job in-process instead — the contract you poll is identical either way.

{% hint style="warning" %}
Async jobs are available on every Algenta edition and have no separate plan concurrency quota. Work still runs within the licensed workers/device capacity and the resources of your deployment. See [Execution policy & safety limits](../api/rate-limits.md).
{% endhint %}

## Submit a job

Send the same simulation body you would send to `POST /v1/simulate`, wrapped under a `request` key. The `mode` field on the request (`auto` or `expert`) is the discriminator. Optionally add a top-level `callback_url` — when set, the engine POSTs a `job.completed` webhook to that URL when the job finishes (it must be HTTPS in production).

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/jobs" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "mode": "expert",
      "simulation_model": "monte_carlo",
      "simulation": {
        "variables": [
          {"name": "revenue", "distribution": "lognormal", "params": {"mean": 11.5, "std": 0.4}},
          {"name": "cost", "distribution": "triangular", "params": {"low": 40000, "mode": 60000, "high": 90000}}
        ],
        "objective_function": "revenue - cost",
        "scoring": {"expected_value": 0.6, "downside_risk": 0.4}
      },
      "runs": 1000000,
      "seed": 42
    },
    "callback_url": "https://example.com/hooks/algenta"
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
import os
import httpx

base = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}

body = {
    "request": {
        "mode": "expert",
        "simulation_model": "monte_carlo",
        "simulation": {
            "variables": [
                {"name": "revenue", "distribution": "lognormal", "params": {"mean": 11.5, "std": 0.4}},
                {"name": "cost", "distribution": "triangular", "params": {"low": 40000, "mode": 60000, "high": 90000}},
            ],
            "objective_function": "revenue - cost",
            "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
        },
        "runs": 1_000_000,
        "seed": 42,
    },
    "callback_url": "https://example.com/hooks/algenta",
}

resp = httpx.post(f"{base}/v1/jobs", headers=headers, json=body, timeout=30)
resp.raise_for_status()
submitted = resp.json()
job_id = submitted["job_id"]
print(submitted["status"], job_id)
```
{% endtab %}
{% endtabs %}

**Expected result.** The endpoint returns HTTP **202 Accepted** with a `SubmitJobResponse` body — the work is acknowledged, not yet finished:

```json
{
  "job_id": "3f9c2b1a-7e44-4a0e-9c2b-1a7e444a0e9c",
  "run_id": "b2d7e9a1-0c33-4f6a-8b1e-9a10c334f6a8",
  "status": "queued",
  "poll_url": "https://api.algenta.ai/v1/jobs/3f9c2b1a-7e44-4a0e-9c2b-1a7e444a0e9c",
  "message": "Job queued. Poll the poll_url for status updates."
}
```

Capture the `job_id` (and the convenience `poll_url`) — you will use the id for every subsequent call.

## Job status values

A job moves through a small state machine. The `status` field on the job object is always one of:

| Status | Meaning | Terminal |
| --- | --- | --- |
| `queued` | Accepted and waiting to start. | No |
| `validating` | Request payload is being validated. | No |
| `running` | The engine is executing the simulation. | No |
| `completed` | Finished successfully; result is available. | Yes |
| `failed` | Execution errored; see `error_message`. | Yes |
| `cancelled` | Cancelled before completion. | Yes |
| `expired` | Completed result aged out past its TTL. | Yes |

Valid transitions are `queued -> validating -> running -> completed`, with `failed` and `cancelled` reachable from the non-terminal states, and `completed -> expired` once a result passes its time-to-live. A submitted job's result has a default TTL of 24 hours, surfaced as `ttl_expires_at` on the job object.

## Poll a job's status

Poll `GET /v1/jobs/{job_id}` on an interval until `status` is terminal. Each poll returns the full `JobStatusResponse`.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_API_URL/v1/jobs/$JOB_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python
import os
import time
import httpx

base = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}
job_id = os.environ["JOB_ID"]

terminal = {"completed", "failed", "cancelled", "expired"}
while True:
    job = httpx.get(f"{base}/v1/jobs/{job_id}", headers=headers, timeout=30).json()
    print(job["status"])
    if job["status"] in terminal:
        break
    time.sleep(2)
```
{% endtab %}
{% endtabs %}

**Expected result.** While the job is in flight you will see `status` values of `queued`, then `validating`, then `running`. Once the engine finishes, a poll returns the terminal `completed` state with `started_at` and `completed_at` populated:

```json
{
  "job_id": "3f9c2b1a-7e44-4a0e-9c2b-1a7e444a0e9c",
  "run_id": "b2d7e9a1-0c33-4f6a-8b1e-9a10c334f6a8",
  "org_id": "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
  "status": "completed",
  "queue_name": "default",
  "retry_count": 0,
  "callback_url": "https://example.com/hooks/algenta",
  "callback_status": "delivered",
  "error_message": null,
  "created_at": "2026-06-19T12:00:00Z",
  "started_at": "2026-06-19T12:00:01Z",
  "completed_at": "2026-06-19T12:00:09Z",
  "ttl_expires_at": "2026-06-20T12:00:00Z",
  "poll_url": "https://api.algenta.ai/v1/jobs/3f9c2b1a-7e44-4a0e-9c2b-1a7e444a0e9c"
}
```

The `callback_status` field tracks webhook delivery: `not_configured` when no `callback_url` was given, `pending` before delivery, then `delivered` or `failed`. If the job ends in `failed`, `error_message` carries the reason.

## Fetch the result

Once a job is `completed`, fetch its result from `GET /v1/jobs/{job_id}/result`. This endpoint is safe to call at any time — if the job is not yet done it reports the current status rather than erroring.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_API_URL/v1/jobs/$JOB_ID/result" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python
import os
import httpx

base = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}
job_id = os.environ["JOB_ID"]

payload = httpx.get(f"{base}/v1/jobs/{job_id}/result", headers=headers, timeout=30).json()
if payload["status"] == "completed":
    envelope = payload["result"]
    print(envelope)
else:
    print("not ready:", payload["status"])
```
{% endtab %}
{% endtabs %}

**Expected result.** For a `completed` job, the response wraps the simulation's decision envelope under a `result` key:

```json
{
  "status": "completed",
  "result": {
    "recommended_action": "proceed",
    "confidence": 0.82,
    "scenarios_run": 1000000,
    "engine_version": "0.7.0-mojo-parallel"
  }
}
```

The shapes for the other terminal and in-flight states are:

```json
{"status": "failed", "error": "<error_message>"}
```

```json
{"status": "cancelled"}
```

```json
{"status": "running", "message": "Job is still processing. Poll again later."}
```

## List your jobs

To see all jobs for your organization, call `GET /v1/jobs/list`. It is paginated with `page` (default `1`) and `limit` (default `25`, max `200`), and accepts an optional `status` filter (any of the status values above).

```bash
curl -sS "$ALGENTA_API_URL/v1/jobs/list?status=running&page=1&limit=25" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result.** A paginated envelope: `jobs` is an array of `JobStatusResponse` objects (ordered newest first), alongside `total`, `page`, `limit`, and `pages`.

## Cancel a job

If a job is still in a non-terminal state, cancel it with `POST /v1/jobs/{job_id}/cancel`.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/jobs/$JOB_ID/cancel" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result.** The cancelled job is returned as a `JobStatusResponse` with `status` set to `cancelled` and `completed_at` populated. The underlying simulation run is also moved to `cancelled`.

{% hint style="warning" %}
Cancellation only applies to in-flight jobs. Cancelling a job that has already reached a terminal state returns HTTP 409 — `job_already_terminal` if it is `completed`, `failed`, `cancelled`, or `expired`, or `job_cannot_be_cancelled` for any other non-cancellable state. Requesting a job that does not belong to your org returns 403 (`job_access_denied`); an unknown id returns 404 (`job_not_found`).
{% endhint %}

{% hint style="success" %}
You can verify your webhook endpoint before relying on it: `POST /v1/webhooks/test` with `{"callback_url": "https://example.com/hooks/algenta"}` sends a one-off `webhook.test` payload and returns `{"success": ..., "status_code": ..., "message": ...}`.
{% endhint %}

## Next steps

- [Simulate a scenario](../guides/simulate.md) — build the synchronous `POST /v1/simulate` body that async jobs wrap.
- [Run an agent](../guides/agent-runs.md) — kick off and track long-running agent work the same way you track jobs.
- [Execution policy & safety limits](../api/rate-limits.md) — distinguish unlimited execution from request-shape and worker-capacity controls.
- [API reference](../api/reference.md) — the full schema for every job endpoint, field, and status value.
