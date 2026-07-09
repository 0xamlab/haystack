---
icon: sliders
description: Sweep one simulation variable across a range to see how outcomes move, and stream a long simulation live over Server-Sent Events.
---

# Run a what-if sweep

A what-if sweep varies one variable across a range while holding everything else fixed, then runs a full simulation at each step — in parallel — so you can see exactly how the outcome moves. `POST /v1/simulate/what-if` returns the sweep plus a computed sensitivity direction and elasticity, the numbers behind a tornado chart. For long simulations, `POST /v1/simulate/stream` streams progressive results over Server-Sent Events so you can show live progress instead of waiting for the final answer.

{% hint style="info" %}
What-if operates on **expert-mode** simulation requests (`"mode": "expert"`), because it needs named variables with explicit distribution parameters to sweep. See [Simulation models](../concepts/simulation-models.md) for the full expert schema.
{% endhint %}

## Before you start

You need:

- An API key sent as `Authorization: Bearer $ALGENTA_API_KEY` on a verified account.
- An expert simulation you want to probe: a `variable` name and the `param` of its distribution to sweep (`mean`, `std`, `low`, `high`, `mode`, or `value`).

## Sweep one variable

{% stepper %}
{% step %}
### Build the sweep request

The body wraps a base expert simulation in `request`, then names what to vary:

| Field | Default | Meaning |
| --- | --- | --- |
| `request` | — | The base expert `SimulateRequest`. |
| `variable` | — | Name of the variable to sweep. |
| `param` | `mean` | Which distribution parameter to move: `mean`, `std`, `low`, `high`, `mode`, `value`. |
| `range_pct` | `0.30` | Sweep width as a fraction of the base value (`0.30` = ±30%). |
| `n_steps` | `11` | Number of steps (3–51; odd is symmetric around the base). |
| `runs_per_step` | `5000` | Monte Carlo runs per step (100–100,000). |
{% endstep %}

{% step %}
### Send it to `/v1/simulate/what-if`

{% tabs %}
{% tab title="cURL" %}
```bash title="what-if.sh"
curl -sS -X POST "https://api.algenta.ai/v1/simulate/what-if" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "mode": "expert",
      "simulation": {
        "variables": [
          {"name": "revenue", "distribution": "normal", "params": {"mean": 120000, "std": 30000}},
          {"name": "cost",    "distribution": "fixed",  "params": {"value": 70000}}
        ],
        "objective_function": "revenue - cost"
      },
      "runs": 5000
    },
    "variable": "revenue",
    "param": "mean",
    "range_pct": 0.3,
    "n_steps": 9,
    "runs_per_step": 5000
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="what_if.py"
import os
import requests

BASE = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")

resp = requests.post(
    f"{BASE}/v1/simulate/what-if",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "request": {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {"name": "revenue", "distribution": "normal", "params": {"mean": 120000, "std": 30000}},
                    {"name": "cost",    "distribution": "fixed",  "params": {"value": 70000}},
                ],
                "objective_function": "revenue - cost",
            },
            "runs": 5000,
        },
        "variable": "revenue",
        "param": "mean",
        "range_pct": 0.3,
        "n_steps": 9,
        "runs_per_step": 5000,
    },
)
resp.raise_for_status()
sweep = resp.json()

print(sweep["sensitivity_label"], "elasticity=", sweep["elasticity"])
for step in sweep["steps"]:
    print(step["label"], "EV=", round(step["mean"]), "PoL=", step["probability_of_loss"])
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="whatIf.ts"
const base = process.env.ALGENTA_API_URL ?? "https://api.algenta.ai";

const res = await fetch(`${base}/v1/simulate/what-if`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    request: {
      mode: "expert",
      simulation: {
        variables: [
          { name: "revenue", distribution: "normal", params: { mean: 120000, std: 30000 } },
          { name: "cost",    distribution: "fixed",  params: { value: 70000 } },
        ],
        objective_function: "revenue - cost",
      },
      runs: 5000,
    },
    variable: "revenue",
    param: "mean",
    range_pct: 0.3,
    n_steps: 9,
    runs_per_step: 5000,
  }),
});
if (!res.ok) throw new Error(`what-if failed: ${res.status}`);
const sweep = await res.json();
console.log(sweep.sensitivity_label, sweep.elasticity);
```
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Read the sweep

The `200` `WhatIfResponse` gives one `step` per point, plus a summary of how much the outcome reacts:

```json title="what-if-response.json"
{
  "variable": "revenue",
  "n_steps": 9,
  "range_low": 84000,
  "range_high": 156000,
  "param_changed": "mean",
  "steps": [
    {
      "step": 0,
      "value": 84000,
      "label": "revenue=8.4e+04 (-30.0%)",
      "mean": 14000, "std": 29900,
      "p5": -35000, "p25": -6000, "p50": 14000, "p75": 34000, "p95": 63000,
      "probability_of_loss": 0.32,
      "score": 0.51
    }
  ],
  "increasing_direction": "better",
  "sensitivity_label": "High sensitivity",
  "elasticity": 1.02
}
```

- `steps` — mean, standard deviation, five percentiles, and probability of loss at each swept value.
- `increasing_direction` — whether increasing the variable helps (`better`), hurts (`worse`), barely moves the outcome (`insensitive`), or is non-monotonic (`mixed`).
- `sensitivity_label` — a plain-English band from `Insensitive` through `Very high sensitivity`.
- `elasticity` — percent change in expected value per percent change in the variable.
{% endstep %}
{% endstepper %}

## Stream a long simulation live

`POST /v1/simulate/stream` runs a normal simulation but emits results as they compute, over `text/event-stream`. You get named `progress` events with online statistics, then a single `final` event carrying the same `DecisionEnvelope` a normal `/v1/simulate` call returns. Set `checkpoint_every` (query parameter, default `1000`, minimum `100`) to control how often progress fires. The request body is a plain `SimulateRequest` — auto or expert.

{% tabs %}
{% tab title="cURL" %}
```bash title="stream.sh"
curl -N -X POST "https://api.algenta.ai/v1/simulate/stream?checkpoint_every=1000" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "expert",
    "simulation": {
      "variables": [
        {"name": "revenue", "distribution": "lognormal", "params": {"mean": 11.5, "std": 0.4}}
      ],
      "objective_function": "revenue"
    },
    "runs": 200000
  }'
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="stream.ts"
const base = process.env.ALGENTA_API_URL ?? "https://api.algenta.ai";

const res = await fetch(`${base}/v1/simulate/stream?checkpoint_every=1000`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    mode: "expert",
    simulation: {
      variables: [{ name: "revenue", distribution: "lognormal", params: { mean: 11.5, std: 0.4 } }],
      objective_function: "revenue",
    },
    runs: 200000,
  }),
});

const reader = res.body!.getReader();
const decoder = new TextDecoder();
for (;;) {
  const { value, done } = await reader.read();
  if (done) break;
  process.stdout.write(decoder.decode(value)); // raw SSE frames
}
```
{% endtab %}
{% endtabs %}

The wire is standard SSE: a heartbeat comment, repeated `progress` events, then one `final` event.

```text title="stream.sse"
: stream-started

event: progress
data: {"type":"progress","runs_completed":1000,"runs_total":200000,"progress":0.005,"mean":98123.4,"std":40211.2,"probability_of_loss":0.07}

event: progress
data: {"type":"progress","runs_completed":2000,"runs_total":200000,"progress":0.01,"mean":98410.2,"std":40088.1,"probability_of_loss":0.068}

event: final
data: {"type":"final","result":{ /* full DecisionEnvelope */ }}

: stream-end
```

Each `progress` event carries online (Welford) statistics — `mean`, `std`, `probability_of_loss`, `runs_completed`, and `progress` (0–1). The `final` event's `result` is the complete decision envelope; close the connection once you receive it.

{% hint style="success" %}
**Expected result** — `/v1/simulate/what-if` returns a `WhatIfResponse` whose `steps` length equals `n_steps` and whose `sensitivity_label` and `elasticity` summarize the reaction. `/v1/simulate/stream` streams one or more `progress` events followed by exactly one `final` event containing the full `DecisionEnvelope`.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Recommend an action</strong></td><td>Rank named actions and get a single recommendation.</td><td><a href="recommend-and-score.md">recommend-and-score.md</a></td></tr>
<tr><td><strong>Simulate a scenario</strong></td><td>Run a single decision simulation end to end.</td><td><a href="simulate.md">simulate.md</a></td></tr>
<tr><td><strong>Simulation models</strong></td><td>Distributions, objectives, and expert-mode options.</td><td><a href="../concepts/simulation-models.md">simulation-models.md</a></td></tr>
</tbody></table>
