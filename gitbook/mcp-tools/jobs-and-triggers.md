---
icon: hourglass-half
description: MCP reference for async simulation jobs and real-time triggers — submit and poll long-running jobs, test webhooks, and register conditions that auto-run simulations.
---

# Async jobs & triggers MCP tools

These tools cover two related lanes of the Algenta MCP surface: **async jobs** for long-running Monte Carlo work that outlives a single request, and **triggers** that watch a data source and auto-run a simulation when a threshold is crossed. Every tool listed here maps one-to-one to an authenticated Algenta API endpoint, so an MCP client (Claude Desktop, Cursor, an HTTP/SSE agent) and a raw `curl` call reach the same behavior.

For installing and connecting the MCP server itself, see [MCP server](../sdk/mcp.md).

## Async job tools

Use jobs when a simulation is too large to run inline (for example `n_simulations` in the millions) or when you want a webhook on completion. Submit once, then poll to a terminal state.

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `submit_job` | Submit a long-running async simulation job and return a `job_id`. | `variables` (required, array of `{name, low, high}`), `objective` (default `maximize`), `n_simulations` (default `1000000`), `callback_url` |
| `list_jobs` | List async simulation jobs with pagination and optional status filter. | `page` (default `1`), `limit` (default `25`), `status` |
| `get_job_status` | Fetch the latest status for one job by id. | `job_id` (required) |
| `poll_job` | Wait for a job to reach a terminal state, returning the result on completion or the terminal status on failure, cancellation, or timeout. | `job_id` (required), `timeout_seconds` (default `30`), `poll_interval_seconds` (default `2`) |
| `get_job_result` | Fetch the completed result payload for one job by id. | `job_id` (required) |
| `cancel_job` | Cancel a queued or running job by id. | `job_id` (required) |
| `test_webhook_delivery` | Send a test webhook payload to a callback URL and return the delivery result. | `callback_url` (required) |

## Trigger tools

Triggers watch a data source for a threshold condition. When the condition is met, the engine auto-runs the attached simulation template and optionally POSTs the result — and, with `auto_execute`, the decision plan — to a webhook.

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `register_trigger` | Register a real-time trigger with a threshold condition and a simulation template to run when it fires. | `name` (required), `condition` (required: `source_id`, `metric_hint`, `threshold`, `direction`; optional `aggregation`), `simulation_template` (required), `webhook_url`, `execution_webhook_url`, `auto_execute`, `description` |
| `list_triggers` | List registered triggers with status, last-checked time, and last-fired summary. | `status` (`active`/`paused`/`all`), `page`, `limit` |
| `fire_trigger` | Manually evaluate a trigger and run its template now. | `trigger_id` (required), `force` (default `false`) |
| `pause_trigger` | Pause or resume a trigger without deleting it. | `trigger_id` (required), `paused` (default `true`) |
| `delete_trigger` | Remove a trigger so it no longer fires automatically. | `trigger_id` (required) |

{% hint style="info" %}
`condition.direction` accepts `above` (fires when metric > threshold), `below` (fires when metric < threshold), or `change` (fires on any significant change). `condition.aggregation` accepts `sum`, `avg`, `max`, `min`, or `count` and defaults to `sum`.
{% endhint %}

## HTTP mapping

Because each tool wraps a single endpoint, you can reproduce any call against the raw API to verify behavior.

| Tool | Method | Endpoint |
| --- | --- | --- |
| `submit_job` | `POST` | `/v1/jobs` |
| `list_jobs` | `GET` | `/v1/jobs/list` |
| `get_job_status` | `GET` | `/v1/jobs/{job_id}` |
| `poll_job` | `GET` | `/v1/jobs/{job_id}` then `/v1/jobs/{job_id}/result` |
| `get_job_result` | `GET` | `/v1/jobs/{job_id}/result` |
| `cancel_job` | `POST` | `/v1/jobs/{job_id}/cancel` |
| `test_webhook_delivery` | `POST` | `/v1/webhooks/test` |
| `register_trigger` | `POST` | `/v1/triggers` |
| `list_triggers` | `GET` | `/v1/triggers` |
| `fire_trigger` | `POST` | `/v1/triggers/{trigger_id}/fire` |
| `pause_trigger` | `PATCH` | `/v1/triggers/{trigger_id}/pause` |
| `delete_trigger` | `DELETE` | `/v1/triggers/{trigger_id}` |

## Worked examples

### Submit a job, then poll it

{% tabs %}
{% tab title="MCP tool call" %}
First submit the job. The tool returns a `job_id` and a queued status.

```json title="submit_job — arguments"
{
  "variables": [
    { "name": "revenue", "low": 80000, "high": 200000 },
    { "name": "cost", "low": 40000, "high": 90000 }
  ],
  "objective": "maximize",
  "n_simulations": 2000000,
  "callback_url": "https://example.com/webhooks/algenta"
}
```

```json title="submit_job — result"
{
  "job_id": "$JOB_ID",
  "status": "queued",
  "message": "Job submitted. Poll with get_job_status(job_id=...) to check progress."
}
```

Then wait for it with `poll_job`. On completion it returns both the final job record and the result payload.

```json title="poll_job — arguments"
{ "job_id": "$JOB_ID", "timeout_seconds": 60, "poll_interval_seconds": 2 }
```

```json title="poll_job — result (completed)"
{
  "job": { "job_id": "$JOB_ID", "status": "completed" },
  "result": { "recommended_action": "proceed", "expected_value": 71500.0, "confidence": 0.86 }
}
```

If the job is still running when `timeout_seconds` elapses, `poll_job` returns `{ "terminal": false, "timed_out": true, ... }` — call it again to keep waiting.
{% endtab %}

{% tab title="HTTP" %}
```bash title="submit_and_poll.sh"
# Submit
curl -sS "$ALGENTA_BASE_URL/v1/jobs" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "n_simulations": 2000000,
    "scenario": {
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost":    { "low": 40000, "high": 90000 }
      },
      "objective": "maximize"
    }
  }'

# Poll status, then fetch the result
curl -sS "$ALGENTA_BASE_URL/v1/jobs/$JOB_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
curl -sS "$ALGENTA_BASE_URL/v1/jobs/$JOB_ID/result" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

### Register a trigger and fire it manually

{% tabs %}
{% tab title="MCP tool call" %}
Register a trigger that watches monthly revenue and runs a simulation template when it drops below a threshold.

```json title="register_trigger — arguments"
{
  "name": "Revenue floor alert",
  "condition": {
    "source_id": "$SOURCE_ID",
    "metric_hint": "net_sales",
    "threshold": 80000,
    "direction": "below",
    "aggregation": "sum"
  },
  "simulation_template": {
    "mode": "auto",
    "scenario": {
      "name": "Contingency plan",
      "variables": { "spend": { "low": 5000, "high": 20000 } },
      "objective": "minimize_downside"
    }
  },
  "webhook_url": "https://example.com/webhooks/algenta",
  "description": "Run the contingency plan when monthly net sales fall below the floor."
}
```

```json title="register_trigger — result"
{
  "trigger_id": "$TRIGGER_ID",
  "name": "Revenue floor alert",
  "status": "active",
  "note": "Trigger registered. It will auto-evaluate when source data updates. Use fire_trigger to test it immediately."
}
```

Test it immediately with `fire_trigger` and `force: true`, which runs the template even if the condition is not currently met.

```json title="fire_trigger — arguments"
{ "trigger_id": "$TRIGGER_ID", "force": true }
```

```json title="fire_trigger — result"
{
  "trigger_id": "$TRIGGER_ID",
  "condition_met": false,
  "fired": true,
  "simulation_run_id": "$RUN_ID",
  "recommended_action": "hold",
  "expected_value": 12400.0,
  "confidence": 0.79
}
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="trigger.sh"
# Register
curl -sS "$ALGENTA_BASE_URL/v1/triggers" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Revenue floor alert",
    "condition": {
      "source_id": "'"$SOURCE_ID"'",
      "metric_hint": "net_sales",
      "threshold": 80000,
      "direction": "below",
      "aggregation": "sum"
    },
    "simulation_template": {
      "mode": "auto",
      "scenario": { "variables": { "spend": { "low": 5000, "high": 20000 } }, "objective": "minimize_downside" }
    }
  }'

# Fire it now, ignoring the current condition
curl -sS "$ALGENTA_BASE_URL/v1/triggers/$TRIGGER_ID/fire" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "force": true }'
```
{% endtab %}
{% endtabs %}

## Related references

{% content-ref url="../guides/async-jobs.md" %}
[async-jobs.md](../guides/async-jobs.md)
{% endcontent-ref %}

{% content-ref url="agent-runs.md" %}
[agent-runs.md](agent-runs.md)
{% endcontent-ref %}

{% content-ref url="../sdk/mcp.md" %}
[mcp.md](../sdk/mcp.md)
{% endcontent-ref %}
