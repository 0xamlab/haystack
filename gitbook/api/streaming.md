---
icon: signal-stream
description: The Algenta Server-Sent Events surfaces — streaming simulation, agent-run event streams, and structured logs — with the exact events, frames, and how to consume them with curl and the SDKs.
---

# Streaming (Server-Sent Events)

Some Algenta responses are long-running, and you want results as they happen rather than one blob at the end. Those endpoints stream over **Server-Sent Events (SSE)**: a single HTTP connection stays open and the engine pushes `text/event-stream` frames until the work is done. This page is the reference for every SSE surface — the frames each one emits and how to read them from curl and the SDKs.

All three surfaces set `Content-Type: text/event-stream` and disable proxy buffering so frames arrive promptly. Base URL is `https://api.algenta.ai` or your own origin such as `http://localhost:8000`.

## The SSE surfaces

| Surface | Method + path | What it streams |
| --- | --- | --- |
| Streaming simulation | `POST /v1/simulate/stream` | Live `progress` events, then a `final` DecisionEnvelope. |
| Agent-run events | `GET /v1/agent/runs/{run_id}/events?stream=true` | Each run event as it is recorded, then completion. |
| Structured logs | `GET /v1/logs` | A `connected` frame, then structured log entries as they occur. |

{% hint style="info" %}
SSE frames are line-based. A data frame is `data: <payload>\n\n`. A named-event frame prefixes it with `event: <name>\n`. A line starting with `:` is a comment (used here for heartbeats and keepalives) and carries no data. Read frames until the stream closes.
{% endhint %}

## Streaming simulation

`POST /v1/simulate/stream` runs the same computation as [`/v1/simulate`](../guides/simulate.md) but emits progress as the engine computes. It uses the same auth and quota checks, and the same request body (`mode: "auto"` or `mode: "expert"`).

This surface uses **named** SSE events.

| Event | When | Payload |
| --- | --- | --- |
| `progress` | Every `checkpoint_every` runs. | `type`, `runs_completed`, `runs_total`, `progress` (0–1), plus online stats `mean`, `std`, `min`, `max`, `probability_of_loss`. |
| `final` | On completion. | `type` and `result`: the full `DecisionEnvelope`, identical to `/v1/simulate`. |
| `error` | On failure. | `type` and an `error` object with `code` and `message`. |

| Query param | Default | Meaning |
| --- | --- | --- |
| `checkpoint_every` | `1000` | Emit a `progress` event every N runs. Values below `100` are raised to `100`. |

{% code title="Consume the simulation stream with curl" %}
```bash
curl -N -X POST "$ALGENTA_BASE_URL/v1/simulate/stream?checkpoint_every=5000" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "runs": 100000,
    "scenario": {
      "name": "Product launch decision",
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost":    { "low": 40000, "high": 90000 }
      },
      "objective": "maximize_net_value"
    }
  }'
```
{% endcode %}

The `-N` flag disables curl's output buffering so you see each frame as it arrives:

```http title="Stream (abridged)"
: stream-started

event: progress
data: {"type":"progress","runs_completed":5000,"runs_total":100000,"progress":0.05,"mean":61240.5,"std":18220.1,"probability_of_loss":0.07}

event: progress
data: {"type":"progress","runs_completed":100000,"runs_total":100000,"progress":1.0,"mean":60980.2,"std":18110.7,"probability_of_loss":0.06}

event: final
data: {"type":"final","result":{"expected_value":60980.2,"recommended_action":"...","confidence":0.94,"decision_plan":{"...":"..."}}}

: stream-end
```

In a browser, subscribe to the named events:

```javascript title="Consume with EventSource (browser)"
const es = new EventSource(`${ALGENTA_BASE_URL}/v1/simulate/stream`);
es.addEventListener("progress", (e) => console.log(JSON.parse(e.data)));
es.addEventListener("final", (e) => {
  console.log("result", JSON.parse(e.data).result);
  es.close();
});
```

{% hint style="warning" %}
The native browser `EventSource` cannot set request headers or issue a `POST`. For header-authenticated or `POST` streams, consume the body with `fetch` and a `ReadableStream` reader, or use the SDKs, which handle SSE for you.
{% endhint %}

## Agent-run events

`GET /v1/agent/runs/{run_id}/events` returns a JSON list by default. Add `stream=true` to receive the events as an SSE stream that stays open until the run finishes. Create a run first (`POST /v1/agent/runs`) to get a `$RUN_ID` — see [Run an agent](../guides/agent-runs.md).

This surface uses plain `data:` frames; the frame kind is the `type` field inside the JSON.

| Frame `type` | Meaning |
| --- | --- |
| `agent.run.event` | One recorded run event; carries `run_id` and the `event` object. |
| `agent.run.completed` | Terminal marker; carries `run_id`, final `status`, and `total_events`. |
| `[DONE]` | The literal `data: [DONE]` line closing the stream. |

| Query param | Default | Meaning |
| --- | --- | --- |
| `limit` | `1000` | Maximum events per poll (max `1000`). |
| `stream` | `false` | Set `true` for the SSE stream. |

{% code title="Stream agent-run events with curl" %}
```bash
curl -N "$ALGENTA_BASE_URL/v1/agent/runs/$RUN_ID/events?stream=true" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

```http title="Stream (abridged)"
data: {"type":"agent.run.event","run_id":"...","event":{"event_id":"...","kind":"tool_selected","...":"..."}}

data: {"type":"agent.run.event","run_id":"...","event":{"event_id":"...","kind":"tool_result","...":"..."}}

data: {"type":"agent.run.completed","run_id":"...","status":"completed","total_events":7}

data: [DONE]
```

The SDKs expose this as a generator, so you iterate events without parsing frames yourself:

{% tabs %}
{% tab title="Python" %}
```python title="stream_agent.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])
run = client.create_agent_run(task="Summarize the latest incident report")

for event in client.stream_agent_run_events(run.run_id):
    print(event)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="streamAgent.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });
const run = await client.createAgentRun({ task: "Summarize the latest incident report" });

for await (const event of client.streamAgentRunEvents(run.run_id)) {
  console.log(event);
}
```
{% endtab %}
{% endtabs %}

{% hint style="info" %}
The SDK stream methods send `Accept: text/event-stream` and stop when the run reaches `completed` or `cancelled`. The non-streaming `GET /v1/agent/runs/{run_id}/events` returns the same events as a single list when you do not need live updates.
{% endhint %}

## Structured logs

`GET /v1/logs` streams structured log events from the running instance as they occur — useful for tailing activity during a live session. It opens with a `connected` frame and sends keepalive comments during idle periods.

This surface uses plain `data:` frames.

| Query param | Meaning |
| --- | --- |
| `node_id` | Filter to a single compute node id. |
| `level` | Filter by log level (`info`, `warning`, `error`). |

{% code title="Tail structured logs with curl" %}
```bash
curl -N "$ALGENTA_BASE_URL/v1/logs?level=error" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

```http title="Stream (abridged)"
data: {"type":"connected","ts":"2026-07-09T12:00:00Z","message":"Log stream connected"}

data: {"level":"info","event":"simulate_completed","org_id":"...","ts":"2026-07-09T12:00:01Z"}

: keepalive 2026-07-09T12:00:06Z
```

The stream closes when your client disconnects. For long-lived monitoring, prefer a durable pipeline over an ad-hoc SSE tail — see [Monitoring & observability](../operate/monitoring.md).

## Consuming SSE reliably

A few rules apply to all three surfaces:

- **Disable buffering.** Use `curl -N`, and if you proxy the stream, do not buffer `text/event-stream` responses.
- **Read to the end.** Simulation ends on the `final` event; agent runs end on `data: [DONE]`; the log stream ends only when you disconnect.
- **Ignore comments.** Lines starting with `:` are heartbeats/keepalives — parse only `data:` payloads.
- **Reconnect with care.** If a connection drops mid-run, re-request the agent-run events (they are persisted and replayed from the start of the stream); re-run a simulation from scratch.

## Related references

- [API overview](overview.md) — base URL, authentication, and the error envelope.
- [Simulate a scenario](../guides/simulate.md) — the non-streaming simulation call.
- [Run an agent](../guides/agent-runs.md) — create the runs this stream reports on.
- [Python SDK](../sdk/python.md) and [TypeScript SDK](../sdk/typescript.md) — the streaming client methods.
