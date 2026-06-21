---
icon: robot
description: Start a deterministic, replayable agent run through the Algenta Agent Runtime, follow its lifecycle, stream its events, and retrieve its checkpoints and proof artifacts.
---

# Run an agent

By the end of this page you will have started a **persisted agent run** through the Algenta Agent Runtime, watched it move through its lifecycle, streamed its events, and retrieved the run's result, checkpoints, and proof artifacts. Unlike a one-shot product call, an agent run is a durable resource: every run carries a `request_hash` and `decision_hash`, is anchored to a policy and schema snapshot, and persists a checkpoint after each lifecycle transition, so the run can be listed, replayed, and forked later. This is the same [execution ownership](../concepts/execution-ownership.md) contract that backs the rest of the engine — the same inputs against the same snapshots produce the same answer.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)). Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment. All routes below are under `/v1` and authenticate with `Authorization: Bearer <key>`.

{% hint style="info" %}
The Agent Runtime is the persisted lifecycle surface at `/v1/agent/runs`. If you only need a single, stateless task call with an immediate structured result, use the simpler `POST /v1/agent/run` product endpoint instead. This page documents the persisted runtime, which adds checkpoints, replay, fork, approval gates, and durable proof artifacts.
{% endhint %}

## The run lifecycle

A run is created in one of three starting states, decided by the request body:

* **`running`** — the default (`approval_mode: "auto"`, `start_paused: false`). The runtime selects a tool and executes it synchronously, so the create call returns a run that is already `completed`.
* **`requires_approval`** — when `approval_mode: "manual"`. The run pauses with `pending_action: "approve"` before executing its selected tool. Call `/approve` to execute.
* **`paused`** — when `start_paused: true`. The run is persisted with `pending_action: "resume"` and does nothing until you call `/resume`.

The terminal states are **`completed`** and **`cancelled`**. The full set of statuses is `running`, `paused`, `requires_approval`, `completed`, `cancelled`.

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every tool below picks them up from the environment.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_API_URL="https://api.algenta.ai"
```

Confirm the variables are set before continuing:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_API_URL"
```
{% endstep %}

{% step %}
### Start an agent run

`POST /v1/agent/runs` creates the run. The only required field is `task` (at least 5 characters). The runtime inspects the task wording and routes it to one tool from `tools` — by default `search`, `simulate`, `optimize`, `calculate`, and `summarize` are all available.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `task` | string | — | Required. What the agent should do (min length 5). |
| `context` | object | `null` | Optional additional context or data. |
| `tools` | array of strings | all five | Subset of `search`, `simulate`, `optimize`, `calculate`, `summarize`. |
| `max_steps` | integer | `10` | Maximum execution steps (1–50). |
| `output_format` | string | `"text"` | One of `text`, `json`, `markdown`. |
| `approval_mode` | string | `"auto"` | `auto` executes immediately; `manual` waits for `/approve`. |
| `start_paused` | boolean | `false` | If `true`, the run is persisted `paused` until `/resume`. |

{% tabs %}
{% tab title="cURL" %}
```bash title="Create an agent run"
curl -s -X POST "$ALGENTA_API_URL/v1/agent/runs" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Estimate the downside risk of launching the new pricing tier",
    "tools": ["simulate", "calculate"],
    "max_steps": 8,
    "output_format": "json",
    "approval_mode": "auto"
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="Create an agent run with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

run = client.create_agent_run(
    task="Estimate the downside risk of launching the new pricing tier",
    tools=["simulate", "calculate"],
    max_steps=8,
    output_format="json",
    approval_mode="auto",
)
print(run.run_id, run.status, run.selected_tool)
```
{% endtab %}
{% endtabs %}

Capture the `run_id` from the response — the rest of the steps use it:

```bash title="Capture the run id"
export RUN_ID="$RUN_ID"  # paste the run_id returned by the create call
```
{% endstep %}

{% step %}
### Inspect the run

`GET /v1/agent/runs/{run_id}` returns the current run resource. Poll this to follow a run that is not yet terminal (a `manual` or `start_paused` run).

```bash title="Get one run"
curl -s "$ALGENTA_API_URL/v1/agent/runs/$RUN_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The run resource includes `status`, `selected_tool`, `tools_used`, `result`, the ordered `steps` (each with `step`, `action`, `tool`, `result`, `status`), `latency_ms`, the determinism anchors `request_hash`, `decision_hash`, `policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, and the proof anchors `artifact_refs`, `latest_checkpoint_id`, and `checkpoint_count`.
{% endstep %}

{% step %}
### Stream the events

`GET /v1/agent/runs/{run_id}/events` returns the ordered event log. By default it is a JSON list; add `stream=true` to receive a Server-Sent Events stream that follows the run until it reaches a terminal state.

```bash title="Stream run events (SSE)"
curl -sN "$ALGENTA_API_URL/v1/agent/runs/$RUN_ID/events?stream=true" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Each SSE frame is a `data:` line. Per-event frames carry `{"type": "agent.run.event", "run_id": "...", "event": {...}}`, where the embedded event has `event_id`, `event_type` (for example `run_created`, `tool_selected`, `tool_executed`, `run_completed`), `status`, `message`, `created_at`, and `details`. When the run finishes the stream emits `{"type": "agent.run.completed", "run_id": "...", "status": "completed", "total_events": N}` followed by `data: [DONE]`.

```python title="Stream run events with the Python SDK"
for event in client.stream_agent_run_events(run.run_id):
    print(event)
```
{% endstep %}

{% step %}
### Approve or resume a paused run

If you created the run with `approval_mode: "manual"` or `start_paused: true`, advance it explicitly. `POST /v1/agent/runs/{run_id}/approve` executes a run in `requires_approval`; `POST /v1/agent/runs/{run_id}/resume` releases a `paused` run. Both return the updated run resource. `POST /v1/agent/runs/{run_id}/cancel` moves a `paused` or `requires_approval` run to `cancelled`.

```bash title="Approve a waiting run"
curl -s -X POST "$ALGENTA_API_URL/v1/agent/runs/$RUN_ID/approve" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

{% hint style="warning" %}
These transitions are state-guarded. Approving a run that is not `requires_approval`, resuming one that is not `paused`, or cancelling a run that is already terminal returns `409` with `error.code: "agent_run_invalid_state"`. A `manual` run that is also `start_paused` first resumes into `requires_approval`, then needs an `/approve`.
{% endhint %}
{% endstep %}

{% step %}
### Retrieve checkpoints and proof artifacts

Every lifecycle transition persists a checkpoint. `GET /v1/agent/runs/{run_id}/checkpoints` lists them.

```bash title="List a run's checkpoints"
curl -s "$ALGENTA_API_URL/v1/agent/runs/$RUN_ID/checkpoints" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Each checkpoint carries `checkpoint_id`, `checkpoint_index`, `parent_checkpoint_id`, the event window (`event_start_index`, `event_end_index`), and the verifiable hashes `request_hash`, `decision_hash`, and `content_hash`, alongside the same snapshot ids as the run. The proof artifacts a checkpoint produced are listed in its `artifact_refs` (also surfaced on the run resource). The runtime writes each checkpoint a JSON state snapshot plus a Parquet sidecar, so the run's evidence is durable and content-addressed.

{% hint style="info" %}
On a hosted, multi-replica deployment with the durable object store enabled, the engine mirrors a run's proof bundle and any generated patch `.diff` to a tenant-scoped object store under the run id, so a run's evidence and applied patch survive the loss of the node that produced it and are recoverable from any replica. In local mode the artifacts already live on the node's disk and the mirror is a no-op. Proof mirroring is best-effort and never fails an otherwise-successful run.
{% endhint %}

You can also inspect the canonical [mission events](../help/glossary.md) at `GET /v1/agent/runs/{run_id}/mission-events` and the runtime telemetry batches at `GET /v1/agent/runs/{run_id}/telemetry`.
{% endstep %}
{% endstepper %}

## Expected result

A run created with `approval_mode: "auto"` and `start_paused: false` comes back from `POST /v1/agent/runs` already `completed`: the response is an agent run resource with a `run_id`, `status: "completed"`, the `selected_tool` the runtime routed to, a populated `result`, a `tools_used` list, an ordered `steps` array, a `latency_ms`, a non-null `decision_hash`, a `latest_checkpoint_id`, and a `checkpoint_count` of at least one. A `manual` run returns `status: "requires_approval"` with `pending_action: "approve"`; a `start_paused` run returns `status: "paused"` with `pending_action: "resume"`. Re-fetching with `GET /v1/agent/runs/{run_id}` returns the same resource, and `GET /v1/agent/runs/{run_id}/checkpoints` returns the persisted, hash-anchored proof checkpoints for the run.

## Replay and fork

Because every checkpoint is content-addressed, a completed run can be re-verified or branched.

* `POST /v1/agent/runs/{run_id}/replay` deterministically recomputes a checkpoint (defaulting to the latest) and returns a `replay_status` of `matched` or `mismatch`, with the compared hashes. A `mismatch` carries `failure_code: "replay_mismatch"`.
* `POST /v1/agent/runs/{run_id}/fork` creates a new `paused` run seeded from a checkpoint (defaulting to the latest), with `source_run_id` and `source_checkpoint_id` set. Resume the fork to execute its own branch.

You can also browse across runs with `GET /v1/agent/runs` (filter by `status`, `request_hash`, `policy_snapshot_id`, `schema_snapshot_id`) and the cross-run query endpoints `/v1/agent/runs/checkpoints`, `/v1/agent/runs/mission-events`, and `/v1/agent/runs/telemetry`.

## Other ways to run an agent

The same `/v1/agent/runs` endpoints back the `de` CLI and the SDKs.

### de CLI

```bash title="Agent runs with the de CLI"
de agent-runs create request.json        # POST /v1/agent/runs from a JSON body
de agent-runs list                        # list persisted agent runs
de agent-runs get $RUN_ID                 # fetch one persisted run
de agent-runs events $RUN_ID --stream     # follow the SSE event stream
de agent-runs checkpoints $RUN_ID         # list a run's checkpoints
de agent-runs mission-events $RUN_ID      # canonical mission-event records
de agent-runs telemetry $RUN_ID           # runtime telemetry batches
de agent-runs resume $RUN_ID              # resume a paused run
de agent-runs approve $RUN_ID             # approve a waiting run
de agent-runs cancel $RUN_ID              # cancel a paused/waiting run
```

## Next steps

{% content-ref url="repository-intelligence.md" %}
[repository-intelligence.md](repository-intelligence.md)
{% endcontent-ref %}

{% content-ref url="async-jobs.md" %}
[async-jobs.md](async-jobs.md)
{% endcontent-ref %}

{% content-ref url="../concepts/execution-ownership.md" %}
[execution-ownership.md](../concepts/execution-ownership.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
