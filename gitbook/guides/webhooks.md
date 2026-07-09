---
icon: satellite-dish
description: Receive Algenta events by webhook — async job callbacks, trigger notifications, and decision-execution dispatch — verify delivery with a test POST, and receive inbound GitHub App events.
---

# Webhooks

Webhooks let Algenta push events to your endpoints instead of you polling for them. The engine sends outbound webhooks in three situations — when an async job finishes, when a trigger fires, and when a trigger dispatches a decision for execution — and it exposes a test endpoint so you can confirm your receiver works before you rely on it. In the other direction, the GitHub App delivers inbound events to the engine to start automated fixes.

Every outbound call is guarded by the engine's egress policy: a destination your deployment has not allowed is logged and skipped rather than sent. Use HTTPS endpoints in production. All API routes below require `Authorization: Bearer $ALGENTA_API_KEY`.

## Outbound: async job callbacks

Submit a long-running simulation as an async job with a `callback_url`, and the engine POSTs the completed result to that URL when the job finishes — no polling required.

`POST /v1/jobs`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/jobs" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "callback_url": "https://example.com/algenta/webhook",
    "request": {
      "mode": "auto",
      "scenario": {
        "variables": { "revenue": { "low": 80000, "high": 200000 } },
        "objective": "maximize_net_value"
      },
      "runs": 50000,
      "seed": 42
    }
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="job_callback.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

job = client.submit_job(
    {
        "mode": "auto",
        "scenario": {
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
        "runs": 50000,
        "seed": 42,
    },
    callback_url="https://example.com/algenta/webhook",
)
print(job["job_id"], job["poll_url"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="job_callback.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: "https://api.algenta.ai",
});

const job = await client.submitJob(
  {
    mode: "auto",
    scenario: {
      variables: { revenue: { low: 80000, high: 200000 } },
      objective: "maximize_net_value",
    },
    runs: 50000,
    seed: 42,
  },
  "https://example.com/algenta/webhook", // callback_url
);
console.log(job.job_id, job.poll_url);
```
{% endtab %}
{% endtabs %}

When the job completes, your endpoint receives a signed POST. The body carries the event and result; the headers carry the HMAC signature you verify against your signing secret:

```json title="job-callback-body.json"
{
  "event": "job.completed",
  "job_id": "b2c3...",
  "run_id": "a1b2...",
  "org_id": "d4e5...",
  "timestamp": "2026-07-05T12:00:00Z",
  "result": { "recommended_action": "invest", "confidence": 0.9 }
}
```

| Header | Value |
| --- | --- |
| `X-Webhook-Signature` | `sha256=...` HMAC of the raw body — verify this before trusting the payload. |
| `X-Webhook-Event` | The event name (for example `job.completed`). |
| `X-Job-Id` | The job id, for correlation. |

{% hint style="warning" %}
Job callbacks retry with exponential backoff if your endpoint returns a non-2xx status. Make your receiver idempotent: key on `job_id` so a retried delivery is processed once.
{% endhint %}

## Outbound: trigger notifications and decision execution

A [trigger](triggers.md) can attach two webhook URLs. When it fires, the engine POSTs a lightweight notification to `webhook_url`, and — when `auto_execute` is on — the full decision plan to `execution_webhook_url` for an automated actuator to run.

The **notification** payload summarizes the fire:

```json title="trigger-fired-body.json"
{
  "event": "trigger.fired",
  "trigger_id": "8f1c...",
  "trigger_name": "revenue-drop",
  "condition_met": true,
  "current_value": 74000.0,
  "run_id": "a1b2...",
  "recommended_action": "hold",
  "expected_value": 152000.0,
  "confidence": 0.88
}
```

The **execution** payload carries the actionable decision plan as a `decision.execute` event, so a downstream service can act on it:

```json title="decision-execute-body.json"
{
  "event": "decision.execute",
  "trigger_id": "8f1c...",
  "trigger_name": "revenue-drop",
  "fired_at": "2026-07-05T12:00:00Z",
  "policy_snapshot_id": "policy_...",
  "decision_plan": { "recommended_action": "hold", "steps": [] }
}
```

{% hint style="info" %}
Execution dispatch is gated by your execution policy. If auto-execution is not yet allowed for the org — for example while the decision model is still calibrating — the engine skips the execution webhook and the fire response reports `execution_status: "skipped_uncalibrated"`. See [Register a trigger](triggers.md) for the full lifecycle.
{% endhint %}

## Verify delivery with a test POST

Before you wire a real callback, confirm your endpoint accepts the engine's requests. The test endpoint sends a single `webhook.test` payload to any URL and returns the delivery outcome — no retries.

`POST /v1/webhooks/test`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/webhooks/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "callback_url": "https://example.com/algenta/webhook" }'
```
{% endtab %}

{% tab title="Python" %}
```python title="webhook_test.py"
import os
import httpx

resp = httpx.post(
    "https://api.algenta.ai/v1/webhooks/test",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={"callback_url": "https://example.com/algenta/webhook"},
    timeout=30.0,
)
print(resp.json())  # {"success": true, "status_code": 200, "message": "delivered"}
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="webhook_test.ts"
const resp = await fetch("https://api.algenta.ai/v1/webhooks/test", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ callback_url: "https://example.com/algenta/webhook" }),
});
console.log(await resp.json());
```
{% endtab %}
{% endtabs %}

{% hint style="success" %}
**Expected result** — a `200` `WebhookTestResponse`: `{ "success": true, "status_code": 200, "message": "delivered" }`. A blocked destination returns `success: false` with an egress-policy reason; a non-2xx endpoint returns `success: false` with the status your server sent.
{% endhint %}

## Inbound: the GitHub App

Webhooks also flow the other way. When you install the Algenta GitHub App, GitHub delivers repository events to the engine's inbound receiver, `POST /webhooks/github`. That route is the one public, unauthenticated endpoint: it verifies GitHub's HMAC signature (`X-Hub-Signature-256`), dedupes the delivery by its id, and returns `202` within seconds, then runs the fix pipeline asynchronously. You do not call it yourself — GitHub does. To connect it and see which events start a fix, follow the install stepper in [Fix a repository](repository-fix.md).

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Register a trigger</strong></td><td>Fire simulations on thresholds and dispatch the result.</td><td><a href="triggers.md">triggers.md</a></td></tr>
<tr><td><strong>Run async jobs</strong></td><td>Submit long simulations and poll or receive a callback.</td><td><a href="async-jobs.md">async-jobs.md</a></td></tr>
<tr><td><strong>Automate repository fixes</strong></td><td>Install the GitHub App that drives inbound events.</td><td><a href="repository-fix.md">repository-fix.md</a></td></tr>
</tbody></table>
