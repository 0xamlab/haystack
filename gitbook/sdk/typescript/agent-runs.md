---
icon: robot
description: TypeScript SDK reference for agent runs — launch, stream, approve, fork, and replay runs, and query their events, checkpoints, mission events, and telemetry.
---

# TypeScript agent runs

Agent runs drive a task through the engine's tool loop with deterministic, replayable checkpoints. This page is the complete `AlgentaClient` reference for the agent-run surface: every method, its HTTP route, and copy-pasteable examples. All bodies and query parameters stay snake_case even though the method names are camelCase, mirroring the [HTTP contract](../../api/overview.md) exactly. For the end-to-end walkthrough, see the [agent runs guide](../../guides/agent-runs.md).

Every method here lives on the client you construct once:

```ts title="client.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY,
  baseUrl: process.env.ALGENTA_BASE_URL ?? "https://api.algenta.ai",
});
```

## Launch and stream a run

`createAgentRun` accepts an `AgentRunCreateRequest` (`task`, and optional `context`, `tools`, `max_steps`, `output_format`, `approval_mode`, `start_paused`) and returns an `AgentRunResponse` carrying the `run_id`, `status`, `request_hash`, and `decision_hash`. `streamAgentRunEvents` is an async generator that yields `agent.run.event` messages until a final `agent.run.completed` message.

{% tabs %}
{% tab title="TypeScript" %}
```ts title="launch_and_stream.ts"
const run = await client.createAgentRun({
  task: "Summarize the latest incident report and propose a remediation",
  max_steps: 8,
  approval_mode: "auto", // "auto" | "manual"
  start_paused: false,
});

for await (const message of client.streamAgentRunEvents(run.run_id)) {
  if (message.type === "agent.run.completed") {
    console.log("done:", message.status);
    break;
  }
  console.log(message.event?.event_type, message.event?.summary);
}

const finished = await client.getAgentRun(run.run_id);
console.log(finished.status, finished.request_hash, finished.decision_hash);
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/agent/runs" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Summarize the latest incident report and propose a remediation",
    "max_steps": 8,
    "approval_mode": "auto",
    "start_paused": false
  }'
```
{% endtab %}
{% endtabs %}

{% hint style="info" %}
`AgentRunStatus` is one of `running`, `paused`, `requires_approval`, `completed`, or `cancelled`. When a run pauses, `pending_action` is `resume` or `approve`.
{% endhint %}

## Control a run

When a run pauses for a gated action, advance it with `approveAgentRun`; continue a plain paused run with `resumeAgentRun`; stop it early with `cancelAgentRun`. Branch a new run from a checkpoint with `forkAgentRun`, or re-execute deterministically from one with `replayAgentRun`. Both `forkAgentRun` and `replayAgentRun` take an optional `checkpoint_id` — omit it (or pass `null`) to use the latest checkpoint.

```ts title="control.ts"
await client.approveAgentRun(run.run_id); // approve the pending gated action
await client.resumeAgentRun(run.run_id);  // continue a paused run
await client.cancelAgentRun(run.run_id);  // stop the run

const branch = await client.forkAgentRun(run.run_id, { checkpoint_id: "ckpt_3" });
const replay = await client.replayAgentRun(run.run_id, { checkpoint_id: "ckpt_3" });
console.log(branch.run_id, replay.status);
```

## Read events, checkpoints, mission events, and telemetry

Per-run readers take the `runId` and an optional `{ limit }`; the `query*` variants scan across runs and accept pagination plus provenance filters such as `request_hash`, `policy_snapshot_id`, and `schema_snapshot_id`.

```ts title="inspect.ts"
// Per-run event log (non-streaming).
const events = await client.getAgentRunEvents(run.run_id, { limit: 500 });
console.log(events.total_events, events.data.length);

// Checkpoints you can fork or replay from.
const checkpoints = await client.listAgentRunCheckpoints(run.run_id);
console.log(checkpoints.total_checkpoints);

// Mission events and telemetry for one run.
const mission = await client.listAgentRunMissionEvents(run.run_id, { limit: 200 });
const telemetry = await client.listAgentRunTelemetry(run.run_id, { limit: 200 });
console.log(mission.data.length, telemetry.total_batches);

// Cross-run history, paginated and filtered.
const page = await client.listAgentRuns({ page: 1, limit: 25, status: "completed" });
const ckptScan = await client.queryAgentRunCheckpoints({ run_id: run.run_id, limit: 50 });
const missionScan = await client.queryAgentRunMissionEvents({ event_type: "tool_call", limit: 50 });
const telemetryScan = await client.queryAgentRunTelemetry({ telemetry_kind: "token_usage", limit: 50 });
console.log(page.total, ckptScan.data.length, missionScan.data.length, telemetryScan.data.length);
```

## Method reference

| Method | HTTP | Notes |
| --- | --- | --- |
| `createAgentRun(request)` | `POST /v1/agent/runs` | `request` is an `AgentRunCreateRequest` (`task`, `context`, `tools`, `max_steps`, `output_format`, `approval_mode`, `start_paused`). |
| `getAgentRun(runId)` | `GET /v1/agent/runs/{run_id}` | Current `AgentRunResponse`, including `request_hash` and `decision_hash`. |
| `listAgentRuns(options?)` | `GET /v1/agent/runs` | Paginated. Options: `page`, `limit`, `status`, `request_hash`, `policy_snapshot_id`, `schema_snapshot_id`. Defaults `page=1`, `limit=25`. |
| `getAgentRunEvents(runId, { limit })` | `GET /v1/agent/runs/{run_id}/events` | Event log; `limit` defaults to 1000. |
| `streamAgentRunEvents(runId, { limit })` | `GET /v1/agent/runs/{run_id}/events?stream=true` | Async generator of `AgentRunStreamEventResponse` (`agent.run.event` / `agent.run.completed`). |
| `listAgentRunCheckpoints(runId)` | `GET /v1/agent/runs/{run_id}/checkpoints` | Checkpoints available to fork or replay from. |
| `queryAgentRunCheckpoints(options?)` | `GET /v1/agent/runs/checkpoints` | Cross-run checkpoint scan. Options include `run_id`, `checkpoint_id`, `status`, `request_hash`, plus pagination. |
| `listAgentRunMissionEvents(runId, { limit })` | `GET /v1/agent/runs/{run_id}/mission-events` | Mission-level events for one run; `limit` defaults to 1000. |
| `queryAgentRunMissionEvents(options?)` | `GET /v1/agent/runs/mission-events` | Cross-run mission-event scan. Options include `run_id`, `event_type`, plus pagination. |
| `replayAgentRun(runId, { checkpoint_id })` | `POST /v1/agent/runs/{run_id}/replay` | Deterministic re-execution from a checkpoint; omit `checkpoint_id` for the latest. |
| `forkAgentRun(runId, { checkpoint_id })` | `POST /v1/agent/runs/{run_id}/fork` | New run branched from a checkpoint. |
| `resumeAgentRun(runId)` | `POST /v1/agent/runs/{run_id}/resume` | Continue a paused run. |
| `cancelAgentRun(runId)` | `POST /v1/agent/runs/{run_id}/cancel` | Stop the run. |
| `approveAgentRun(runId)` | `POST /v1/agent/runs/{run_id}/approve` | Approve a pending gated action. |
| `listAgentRunTelemetry(runId, { limit })` | `GET /v1/agent/runs/{run_id}/telemetry` | Telemetry batches for one run; `limit` defaults to 1000. |
| `queryAgentRunTelemetry(options?)` | `GET /v1/agent/runs/telemetry` | Cross-run telemetry scan. Options include `run_id`, `telemetry_kind`, `module_name`, plus pagination. |

## Related pages

{% content-ref url="../../guides/agent-runs.md" %}
[agent-runs.md](../../guides/agent-runs.md)
{% endcontent-ref %}

{% content-ref url="jobs-triggers-capabilities.md" %}
[jobs-triggers-capabilities.md](jobs-triggers-capabilities.md)
{% endcontent-ref %}

{% content-ref url="../typescript.md" %}
[typescript.md](../typescript.md)
{% endcontent-ref %}
