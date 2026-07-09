---
icon: robot
description: MCP reference for the Algenta agent-run lifecycle — create runs, read events, checkpoints, mission events and telemetry, and resume, cancel, or approve a run.
---

# Agent run MCP tools

These tools drive the deterministic Algenta **agent-run lifecycle**: create a persisted run, inspect its append-only history (events, checkpoints, mission events, runtime telemetry), and steer it (resume, cancel, approve). Every run is scoped to the authenticated organization, and every tool maps one-to-one to an authenticated Algenta API endpoint.

For a step-by-step walkthrough of launching and watching a run, see [Run an agent](../guides/agent-runs.md).

## Lifecycle tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `create_agent_run` | Create a persisted agent run. | `task` (required, min length 5), `context`, `tools`, `max_steps` (default `10`, 1–50), `output_format` (default `text`), `approval_mode` (`auto`/`manual`, default `auto`), `start_paused` (default `false`) |
| `list_agent_runs` | List persisted runs for the org. | `page` (default `1`), `limit` (default `25`, max 200), `status`, `request_hash`, `policy_snapshot_id`, `schema_snapshot_id` |
| `get_agent_run` | Fetch one run by id. | `run_id` (required) |
| `resume_agent_run` | Resume a paused run. | `run_id` (required) |
| `cancel_agent_run` | Cancel a run. | `run_id` (required) |
| `approve_agent_run` | Approve a run waiting on manual approval. | `run_id` (required) |

{% hint style="info" %}
`status` filters accept `running`, `paused`, `requires_approval`, `completed`, or `cancelled`. A run created with `approval_mode: manual` (or `start_paused: true`) pauses until you call `approve_agent_run` or `resume_agent_run`.
{% endhint %}

## History tools

Two shapes exist for each history stream: a per-run **get** tool (records for one `run_id`) and a cross-run **query** tool (paginated, filterable across runs).

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `get_agent_run_events` | Fetch the append-only event stream for one run. | `run_id` (required), `limit` (default `1000`) |
| `query_agent_run_checkpoints` | Query persisted checkpoints across runs. | `page`, `limit`, `status`, `request_hash`, `policy_snapshot_id`, `schema_snapshot_id`, `run_id`, `checkpoint_id` |
| `get_agent_run_checkpoints` | Fetch persisted checkpoints for one run. | `run_id` (required) |
| `get_agent_run_mission_events` | Fetch canonical mission-event records for one run. | `run_id` (required), `limit` (default `1000`) |
| `query_agent_run_mission_events` | Query mission-event records across runs. | `page`, `limit`, `status`, `request_hash`, `policy_snapshot_id`, `schema_snapshot_id`, `run_id`, `event_type` |
| `get_agent_run_telemetry` | Fetch runtime telemetry batches for one run. | `run_id` (required), `limit` (default `1000`) |
| `query_agent_run_telemetry` | Query runtime telemetry batches across runs. | `page`, `limit`, `status`, `request_hash`, `policy_snapshot_id`, `schema_snapshot_id`, `run_id`, `telemetry_kind`, `module_name` |

## HTTP mapping

| Tool | Method | Endpoint |
| --- | --- | --- |
| `create_agent_run` | `POST` | `/v1/agent/runs` |
| `list_agent_runs` | `GET` | `/v1/agent/runs` |
| `get_agent_run` | `GET` | `/v1/agent/runs/{run_id}` |
| `get_agent_run_events` | `GET` | `/v1/agent/runs/{run_id}/events` |
| `get_agent_run_checkpoints` | `GET` | `/v1/agent/runs/{run_id}/checkpoints` |
| `query_agent_run_checkpoints` | `GET` | `/v1/agent/runs/checkpoints` |
| `get_agent_run_mission_events` | `GET` | `/v1/agent/runs/{run_id}/mission-events` |
| `query_agent_run_mission_events` | `GET` | `/v1/agent/runs/mission-events` |
| `get_agent_run_telemetry` | `GET` | `/v1/agent/runs/{run_id}/telemetry` |
| `query_agent_run_telemetry` | `GET` | `/v1/agent/runs/telemetry` |
| `resume_agent_run` | `POST` | `/v1/agent/runs/{run_id}/resume` |
| `cancel_agent_run` | `POST` | `/v1/agent/runs/{run_id}/cancel` |
| `approve_agent_run` | `POST` | `/v1/agent/runs/{run_id}/approve` |

## Worked examples

### Create a run and read its events

{% tabs %}
{% tab title="MCP tool call" %}
Create a run with a bounded step budget. The result carries a `run_id` and the run's current `status`.

```json title="create_agent_run — arguments"
{
  "task": "Summarize last quarter's revenue drivers and flag the top three risks.",
  "max_steps": 12,
  "output_format": "text",
  "approval_mode": "auto"
}
```

```json title="create_agent_run — result"
{ "run_id": "$RUN_ID", "status": "running" }
```

Stream the run's history with `get_agent_run_events`. Events are append-only and returned oldest-first up to `limit`.

```json title="get_agent_run_events — arguments"
{ "run_id": "$RUN_ID", "limit": 200 }
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="create_and_read.sh"
curl -sS "$ALGENTA_BASE_URL/v1/agent/runs" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Summarize last quarter'\''s revenue drivers and flag the top three risks.",
    "max_steps": 12,
    "output_format": "text",
    "approval_mode": "auto"
  }'

curl -sS "$ALGENTA_BASE_URL/v1/agent/runs/$RUN_ID/events?limit=200" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

### Approve a run that is waiting

A run created with `approval_mode: manual` pauses in `requires_approval`. Approve it to let it continue.

{% tabs %}
{% tab title="MCP tool call" %}
```json title="approve_agent_run — arguments"
{ "run_id": "$RUN_ID" }
```

Use `resume_agent_run` with the same argument shape to continue a run that is merely `paused` (not awaiting approval), and `cancel_agent_run` to stop one for good.
{% endtab %}

{% tab title="HTTP" %}
```bash title="approve.sh"
curl -sS "$ALGENTA_BASE_URL/v1/agent/runs/$RUN_ID/approve" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```
{% endtab %}
{% endtabs %}

### Query telemetry across runs

Cross-run `query_*` tools filter by status, snapshot ids, and stream-specific fields. Here telemetry is narrowed to one runtime module.

{% tabs %}
{% tab title="MCP tool call" %}
```json title="query_agent_run_telemetry — arguments"
{ "status": "completed", "telemetry_kind": "latency", "module_name": "simulation", "limit": 50 }
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="query_telemetry.sh"
curl -sS "$ALGENTA_BASE_URL/v1/agent/runs/telemetry?status=completed&telemetry_kind=latency&module_name=simulation&limit=50" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

## Related references

{% content-ref url="../guides/agent-runs.md" %}
[agent-runs.md](../guides/agent-runs.md)
{% endcontent-ref %}

{% content-ref url="control-plane.md" %}
[control-plane.md](control-plane.md)
{% endcontent-ref %}

{% content-ref url="../concepts/execution-ownership.md" %}
[execution-ownership.md](../concepts/execution-ownership.md)
{% endcontent-ref %}
