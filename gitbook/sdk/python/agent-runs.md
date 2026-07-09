---
icon: robot
description: Python SDK reference for agent runs — launch, inspect, stream, pause/approve/resume, replay and fork agentic runs, with every AlgentaClient method and its endpoint.
---

# Agent runs (Python SDK)

Every method here lives on the `AlgentaClient` (and its async twin `AsyncAlgentaClient`) and is a thin, faithful client over the `/v1/agent/runs` HTTP surface. Construct the client once, then call any method below. The async client exposes the identical names — call them with `await`.

```python title="client.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",   # or http://localhost:8000 self-hosted
)
```

For a task-first walkthrough see [Run an agent](../../guides/agent-runs.md); for the raw contract see the [API overview](../../api/overview.md).

## Launch and lifecycle

| Method | HTTP | Returns |
| --- | --- | --- |
| `create_agent_run(*, task, context=None, tools=None, max_steps=10, output_format="text", approval_mode="auto", start_paused=False)` | `POST /v1/agent/runs` | `AgentRunResult` |
| `get_agent_run(run_id)` | `GET /v1/agent/runs/{run_id}` | `AgentRunResult` |
| `list_agent_runs(*, page=1, limit=25, status=None, request_hash=None, policy_snapshot_id=None, schema_snapshot_id=None)` | `GET /v1/agent/runs` | `AgentRunListResult` |
| `resume_agent_run(run_id)` | `POST /v1/agent/runs/{run_id}/resume` | `AgentRunResult` |
| `cancel_agent_run(run_id)` | `POST /v1/agent/runs/{run_id}/cancel` | `AgentRunResult` |
| `approve_agent_run(run_id)` | `POST /v1/agent/runs/{run_id}/approve` | `AgentRunResult` |

- `create_agent_run` — start a new agentic run. `task` is the natural-language objective; `tools` scopes which capability tools the run may call; `max_steps` caps the loop; `output_format` is the shape you want back (for example `text`); `approval_mode` and `start_paused` control human-in-the-loop gating.
- `approve_agent_run` / `resume_agent_run` — advance a run that paused for approval or was started with `start_paused=True`.
- `cancel_agent_run` — stop a run that is still in flight.

## Events and telemetry

| Method | HTTP | Returns |
| --- | --- | --- |
| `get_agent_run_events(run_id, *, limit=1000)` | `GET /v1/agent/runs/{run_id}/events` | `AgentRunEventsResult` |
| `stream_agent_run_events(run_id, *, limit=1000)` | `GET /v1/agent/runs/{run_id}/events?stream=true` | `Iterator[AgentRunStreamEventResult]` |
| `list_agent_run_mission_events(run_id, *, limit=1000)` | `GET /v1/agent/runs/{run_id}/mission-events` | `AgentRunMissionEventsResult` |
| `query_agent_run_mission_events(*, page=1, limit=25, status=None, request_hash=None, policy_snapshot_id=None, schema_snapshot_id=None, run_id=None, event_type=None)` | `GET /v1/agent/runs/mission-events` | `AgentRunMissionEventListResponseResult` |
| `list_agent_run_telemetry(run_id, *, limit=1000)` | `GET /v1/agent/runs/{run_id}/telemetry` | `AgentRunTelemetryResult` |
| `query_agent_run_telemetry(*, page=1, limit=25, status=None, request_hash=None, policy_snapshot_id=None, schema_snapshot_id=None, run_id=None, telemetry_kind=None, module_name=None)` | `GET /v1/agent/runs/telemetry` | `AgentRunTelemetryListResult` |

- `get_agent_run_events` returns the recorded event log for one run; `stream_agent_run_events` yields the same events live as the run executes, each chunk carrying a `type` of `agent.run.event` or `agent.run.completed`.
- The `list_*` variants scope to one `run_id`; the `query_*` variants page across runs and filter by provenance (`request_hash`, `policy_snapshot_id`, `schema_snapshot_id`) and kind.

## Checkpoints, replay and fork

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_agent_run_checkpoints(run_id)` | `GET /v1/agent/runs/{run_id}/checkpoints` | `AgentRunCheckpointsResult` |
| `query_agent_run_checkpoints(*, page=1, limit=25, status=None, request_hash=None, policy_snapshot_id=None, schema_snapshot_id=None, run_id=None, checkpoint_id=None)` | `GET /v1/agent/runs/checkpoints` | `AgentRunCheckpointListResponseResult` |
| `replay_agent_run(run_id, *, checkpoint_id=None)` | `POST /v1/agent/runs/{run_id}/replay` | `AgentRunReplayResult` |
| `fork_agent_run(run_id, *, checkpoint_id=None)` | `POST /v1/agent/runs/{run_id}/fork` | `AgentRunResult` |

- `replay_agent_run` deterministically re-runs an existing run (optionally from a specific `checkpoint_id`) and reports whether the replay matched.
- `fork_agent_run` branches a new run from an existing run or checkpoint, so you can explore an alternative continuation without losing the original.

{% hint style="info" %}
Every list result carries pagination fields (`total`, `page`, `limit`, `pages`); page until you have what you need. Provenance filters like `request_hash`, `policy_snapshot_id`, and `schema_snapshot_id` let you tie any event, checkpoint, or telemetry row back to the exact request and governance snapshots that produced it.
{% endhint %}

## Example: launch a run and stream its events

```python title="stream_agent_run.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"], base_url="https://api.algenta.ai")

run = client.create_agent_run(
    task="Summarize open incidents and propose a remediation order",
    tools=["query_data", "route_capabilities"],
    max_steps=12,
    output_format="text",
)
print(run.run_id, run.status)

for chunk in client.stream_agent_run_events(run.run_id):
    if chunk.event is not None:
        print(chunk.event.event_type, "-", chunk.event.message)
    if chunk.type == "agent.run.completed":
        print("finished:", chunk.status)

final = client.get_agent_run(run.run_id)
print(final.status, final.result)
```

Expected output resembles:

```json title="run.json"
{
  "run_id": "run_...",
  "status": "completed",
  "output_format": "text",
  "checkpoint_count": 4,
  "latest_checkpoint_id": "ckpt_..."
}
```

## Example: pause for approval, then replay from a checkpoint

```python title="approve_and_replay.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"], base_url="https://api.algenta.ai")

# Start paused so a human can review before any tool executes.
run = client.create_agent_run(
    task="Draft and apply the config change",
    approval_mode="manual",
    start_paused=True,
)

# A reviewer approves, then the run resumes.
client.approve_agent_run(run.run_id)
client.resume_agent_run(run.run_id)

# Inspect checkpoints and deterministically replay from the last one.
checkpoints = client.list_agent_run_checkpoints(run.run_id)
last = client.get_agent_run(run.run_id).latest_checkpoint_id
replay = client.replay_agent_run(run.run_id, checkpoint_id=last)
print(replay.replay_status)
```

## Related references

{% content-ref url="jobs-triggers-capabilities.md" %}
[jobs-triggers-capabilities.md](jobs-triggers-capabilities.md)
{% endcontent-ref %}

{% content-ref url="../../guides/agent-runs.md" %}
[agent-runs.md](../../guides/agent-runs.md)
{% endcontent-ref %}

{% content-ref url="../../api/reference.md" %}
[reference.md](../../api/reference.md)
{% endcontent-ref %}
