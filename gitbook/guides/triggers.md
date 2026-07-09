---
icon: bell
description: Register a threshold condition on a data source, fire it to run an attached simulation, pause or resume it, and delete it — with optional webhook and auto-execution dispatch.
---

# Register a trigger

A trigger watches one metric on a data source and, when that metric crosses a threshold you set, runs an attached simulation template. The result is logged to decision memory and — if you attached webhook URLs — pushed to your endpoints. Triggers turn "re-run this analysis whenever the number moves" into a single registered object you fire on demand.

This guide covers the full lifecycle: register a trigger, fire it, pause and resume it, and delete it. All routes live under `/v1/triggers` and require `Authorization: Bearer $ALGENTA_API_KEY`.

## Before you start

You need:

- A registered data source id (`source_id`) and the metric you want to watch. See [Connect a data source](connect-data.md).
- A `simulation_template` — any payload accepted by [`/v1/simulate`](simulate.md). The engine runs it verbatim each time the trigger fires.

## Create the trigger

The `condition` names the source, the metric hint, an aggregation, a threshold, and a direction (`above`, `below`, or `change`). Attach a `webhook_url` for a result summary, and set `auto_execute` with an `execution_webhook_url` to dispatch the full decision plan for action.

`POST /v1/triggers`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/triggers" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "revenue-drop",
    "condition": {
      "source_id": "'"$SOURCE_ID"'",
      "metric_hint": "revenue",
      "threshold": 100000,
      "direction": "below",
      "aggregation": "sum"
    },
    "simulation_template": {
      "mode": "auto",
      "scenario": {
        "variables": { "revenue": { "low": 80000, "high": 200000 } },
        "objective": "maximize_net_value"
      },
      "runs": 10000,
      "seed": 42
    },
    "webhook_url": "https://example.com/algenta/webhook",
    "description": "Re-simulate the quarter when revenue falls below target."
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="register_trigger.py"
import os
import httpx

resp = httpx.post(
    "https://api.algenta.ai/v1/triggers",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "name": "revenue-drop",
        "condition": {
            "source_id": os.environ["SOURCE_ID"],
            "metric_hint": "revenue",
            "threshold": 100000,
            "direction": "below",
            "aggregation": "sum",
        },
        "simulation_template": {
            "mode": "auto",
            "scenario": {
                "variables": {"revenue": {"low": 80000, "high": 200000}},
                "objective": "maximize_net_value",
            },
            "runs": 10000,
            "seed": 42,
        },
        "webhook_url": "https://example.com/algenta/webhook",
    },
    timeout=30.0,
)
trigger = resp.json()
print(trigger["trigger_id"], trigger["status"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="register_trigger.ts"
const resp = await fetch("https://api.algenta.ai/v1/triggers", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    name: "revenue-drop",
    condition: {
      source_id: process.env.SOURCE_ID,
      metric_hint: "revenue",
      threshold: 100000,
      direction: "below",
      aggregation: "sum",
    },
    simulation_template: {
      mode: "auto",
      scenario: {
        variables: { revenue: { low: 80000, high: 200000 } },
        objective: "maximize_net_value",
      },
      runs: 10000,
      seed: 42,
    },
    webhook_url: "https://example.com/algenta/webhook",
  }),
});
const trigger = await resp.json();
console.log(trigger.trigger_id, trigger.status);
```
{% endtab %}
{% endtabs %}

{% hint style="success" %}
**Expected result** — a `201` `TriggerSummary` with a `trigger_id`, `status: "active"`, and the `condition` you registered. Save the id as `$TRIGGER_ID`.
{% endhint %}

{% expandable title="Condition fields" %}
| Field | Type | Notes |
| --- | --- | --- |
| `source_id` | string | The registered source to watch. |
| `metric_hint` | string | The metric to aggregate and compare. |
| `threshold` | number | The value the metric is compared against. |
| `direction` | `above` \| `below` \| `change` | `above`/`below` compare to the threshold; `change` fires on every evaluation. |
| `aggregation` | `sum` \| `avg` \| `max` \| `min` \| `count` | How the metric is aggregated. Defaults to `sum`. |
{% endexpandable %}

## List triggers

`GET /v1/triggers` returns your org's triggers, newest fields included. Filter by `status` (`active`, `paused`, or `all`) and page with `page` and `limit`.

```bash title="list_triggers.sh"
curl -sS "https://api.algenta.ai/v1/triggers?status=active&page=1&limit=50" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The `200` `TriggerListResponse` carries `triggers`, plus `count`, `total`, `page`, `limit`, and `pages` for pagination.

## Fire a trigger

Firing evaluates the condition against the source's current value. If the condition is met (or you pass `force: true`), the engine runs the simulation template, records the outcome on the trigger, and dispatches any attached webhooks.

`POST /v1/triggers/{trigger_id}/fire`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/triggers/$TRIGGER_ID/fire" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "force": false }'
```
{% endtab %}

{% tab title="Python" %}
```python title="fire_trigger.py"
import os
import httpx

trigger_id = os.environ["TRIGGER_ID"]
resp = httpx.post(
    f"https://api.algenta.ai/v1/triggers/{trigger_id}/fire",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={"force": False},
    timeout=60.0,
)
fired = resp.json()
print(fired["fired"], fired["recommended_action"], fired["message"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="fire_trigger.ts"
const triggerId = process.env.TRIGGER_ID!;
const resp = await fetch(
  `https://api.algenta.ai/v1/triggers/${triggerId}/fire`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ force: false }),
  },
);
const fired = await resp.json();
console.log(fired.fired, fired.recommended_action, fired.message);
```
{% endtab %}
{% endtabs %}

The `200` `FireTriggerResponse` reports `condition_met`, `fired`, the `simulation_run_id`, and the simulation's `recommended_action`, `expected_value`, and `confidence`. When the trigger has `auto_execute` set, `execution_status` is `dispatched` (the decision plan was sent to the execution webhook) or `skipped_uncalibrated` (execution policy blocked it).

{% hint style="success" %}
**Expected result** — when the condition holds, `fired` is `true`, `simulation_run_id` is populated, and `message` reads `Fired: <action>`. If the condition is not met and you did not force it, `fired` is `false` with `message: "Condition not met."`.
{% endhint %}

## Pause, resume, and delete

Pause a trigger to stop it firing without deleting it, then resume it later. Deleting removes it permanently.

{% tabs %}
{% tab title="Pause" %}
`PATCH /v1/triggers/{trigger_id}/pause` sets the status. Pass `paused=false` to resume.

```bash
curl -sS -X PATCH "https://api.algenta.ai/v1/triggers/$TRIGGER_ID/pause?paused=true" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Resume" %}
```bash
curl -sS -X PATCH "https://api.algenta.ai/v1/triggers/$TRIGGER_ID/pause?paused=false" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Delete" %}
`DELETE /v1/triggers/{trigger_id}` returns `204 No Content`.

```bash
curl -sS -X DELETE "https://api.algenta.ai/v1/triggers/$TRIGGER_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

{% hint style="info" %}
A paused trigger still fires if you pass `force: true` to the fire endpoint — handy for testing a paused trigger's template without reactivating it.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Receive trigger events</strong></td><td>Wire up the notification and decision-execution webhooks.</td><td><a href="webhooks.md">webhooks.md</a></td></tr>
<tr><td><strong>Build the template</strong></td><td>Design the simulation a trigger runs when it fires.</td><td><a href="simulate.md">simulate.md</a></td></tr>
<tr><td><strong>Connect the source</strong></td><td>Register the data source the condition watches.</td><td><a href="connect-data.md">connect-data.md</a></td></tr>
</tbody></table>
