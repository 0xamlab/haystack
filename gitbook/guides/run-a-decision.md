---
icon: scale-balanced
description: Turn a scenario into a recommended action — call simulate or recommend and read the decision envelope (recommended action, expected value, confidence, percentiles).
---

# Run a decision

This guide turns a business scenario into a single recommended action and shows you how to read the decision envelope it returns — the structured result carrying `recommended_action`, `expected_value`, `confidence`, and the outcome `percentiles`. You will run the same decision three ways (HTTP, the Python SDK, and the `de` CLI), using `POST /v1/simulate` in auto mode for a single scenario and `POST /v1/recommend` to rank competing actions. Prerequisites: a reachable engine (`https://api.algenta.ai` or a self-hosted `http://localhost:8000`) and an API key exported as `$ALGENTA_API_KEY`. See [Authentication](../authentication.md) if you do not have a key yet.

{% stepper %}
{% step %}
### Describe the scenario in auto mode

Auto mode is the minimal-setup path: you give each variable a `low` and a `high`, name an `objective`, and the engine infers the distributions and runs a Monte Carlo simulation. Save the request body so every surface sends the same payload. The `mode`, `scenario.variables`, and `scenario.objective` fields are required; `runs` and `seed` are optional (`seed` makes the run reproducible).

```json title="launch.json"
{
  "mode": "auto",
  "scenario": {
    "name": "Product launch decision",
    "variables": {
      "revenue": { "low": 80000, "high": 200000 },
      "cost": { "low": 40000, "high": 90000 }
    },
    "objective": "maximize_net_value"
  },
  "runs": 10000,
  "seed": 42
}
```

Verify the file is valid JSON before sending it:

```bash
python -m json.tool launch.json
```

A pretty-printed echo of the body confirms it parses; a traceback means fix the JSON first.
{% endstep %}

{% step %}
### Run the decision over HTTP

Post the body to `POST /v1/simulate`. Each successful call consumes one simulation from your monthly quota and returns HTTP 200 with a decision envelope. Server-side compute is fast (p50 under 15 ms via the Mojo worker pool); persistence happens asynchronously after the response is sent.

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/simulate" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  --data @launch.json
```

Verify you received `200` and that the JSON body has a top-level `recommended_action` and a `decision_plan` object. The response also carries an `X-Decision-Hash` header — the tamper-evident fingerprint of this decision.
{% endstep %}

{% step %}
### Run the same decision from the Python SDK

The SDK is a thin typed client over the HTTP API. `client.simulate(...)` posts to `/v1/simulate` and returns the parsed decision envelope. Pass the scenario as keyword arguments; the client supplies auto-mode defaults.

```python title="run_decision.py"
import os

from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="http://localhost:8000",
)

envelope = client.simulate(
    scenario={
        "name": "Product launch decision",
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 40000, "high": 90000},
        },
        "objective": "maximize_net_value",
    },
    runs=10000,
    seed=42,
)

print(envelope["recommended_action"])
print(envelope["confidence"])
print(envelope["metrics"]["expected_value"])
print(envelope["percentiles"]["p5"], envelope["percentiles"]["p95"])
```

Verify the script prints a non-empty `recommended_action`, a `confidence` between 0 and 1, and a numeric expected value with its p5/p95 bounds.
{% endstep %}

{% step %}
### Run the same decision from the de CLI

The `de` CLI reads the request file and posts it to the same endpoint. Use `de simulate <file>` for one scenario; add `--format json` to print the full envelope instead of the summary table.

```bash
de simulate launch.json --format json
```

Verify the command exits `0` and the JSON output contains `recommended_action`, `decision_plan`, and `percentiles`. A non-zero exit prints `Error <status>` with the API message — check [API errors](../api/errors.md).
{% endstep %}

{% step %}
### Read the decision envelope

The envelope is the same shape across `/v1/simulate`, `/v1/recommend`, and `/v1/score`. These are the decision-critical fields:

- `recommended_action` — the action the engine recommends.
- `confidence` — calibrated confidence in the recommendation, in the range 0 to 1.
- `metrics.expected_value` — the mean simulated outcome for the objective.
- `percentiles` — the outcome distribution: `p5`, `p25`, `p50`, `p75`, `p95` (with optional `p10`, `p90`, `p99`).
- `decision_plan` — the compact, LLM-readable headline: `recommended_action`, `confidence`, `expected_value`, a `risk` block (`p5`, `p95`, `probability_of_loss`, `var_95`), the ranked `options`, and a `rationale`.
- `result_hash` — the 64-character SHA-256 fingerprint of this output, also returned as the `X-Decision-Hash` header.

Verify your reader pulls `recommended_action` and `confidence` from the top level and the downside/upside from `percentiles.p5` and `percentiles.p95`.
{% endstep %}

{% step %}
### Rank competing actions with recommend

When you have two or more named alternatives, `POST /v1/recommend` runs a simulation for each and returns them ranked by expected value. The top-ranked action becomes `recommended_action`, and every alternative appears in `decision_plan.options` with its own rank, expected value, score, and risk. Send 2 to 10 actions, each with a `name` and a `request` (any auto- or expert-mode body).

```python title="rank_actions.py"
import os

from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="http://localhost:8000",
)

result = client.recommend(
    actions=[
        {
            "name": "launch_now",
            "request": {
                "mode": "auto",
                "scenario": {
                    "variables": {
                        "revenue": {"low": 80000, "high": 200000},
                        "cost": {"low": 40000, "high": 90000},
                    },
                    "objective": "maximize_net_value",
                },
            },
        },
        {
            "name": "wait_one_quarter",
            "request": {
                "mode": "auto",
                "scenario": {
                    "variables": {
                        "revenue": {"low": 100000, "high": 180000},
                        "cost": {"low": 55000, "high": 80000},
                    },
                    "objective": "maximize_net_value",
                },
            },
        },
    ],
)

print(result["recommended_action"])
for option in result["decision_plan"]["options"]:
    print(option["rank"], option["name"], option["expected_value"], option["score"])
```

Verify the printed `recommended_action` matches the rank-1 entry in `decision_plan.options`, and that options are ordered by descending expected value.
{% endstep %}
{% endstepper %}

## Expected result

You have a decision envelope from `POST /v1/simulate` whose top-level `recommended_action` names the action to take, with `confidence` in the range 0 to 1, `metrics.expected_value` giving the mean outcome, and `percentiles.p5`/`percentiles.p95` bounding the downside and upside. The `decision_plan` block carries the same headline plus the ranked `options` and a `rationale`, and `result_hash` (mirrored in the `X-Decision-Hash` header) lets you prove the decision was not altered. With `POST /v1/recommend` you get the same envelope where `recommended_action` is the highest-expected-value alternative and every option is ranked in `decision_plan.options`.

## Troubleshooting

{% hint style="warning" %}
**HTTP 429 (quota or rate limit).** Each successful simulation consumes one unit of your monthly quota, and a per-plan rate limit applies. A 429 means you hit one of them. See [Rate limits](../api/rate-limits.md) and [Plans, billing & credits](../billing.md).
{% endhint %}

{% hint style="info" %}
**422 on the request body.** Auto-mode requires each variable's `high` to exceed its `low`, and `objective` must be one of the supported values (for example `maximize_net_value`, `minimize_cost`, `minimize_risk`). The error body names the failing field — fix it and resend. See [API errors](../api/errors.md).
{% endhint %}

{% hint style="info" %}
**`confidence` looks flat across runs.** Confidence is calibrated from your organization's recorded outcomes and only adjusts once enough outcomes exist. Until then it reflects the raw engine value. Record outcomes to improve it — see [Build decision memory](decision-memory.md).
{% endhint %}

## Next

{% content-ref url="../concepts/simulation-models.md" %}
[simulation-models.md](../concepts/simulation-models.md)
{% endcontent-ref %}

{% content-ref url="../concepts/decision-memory.md" %}
[decision-memory.md](../concepts/decision-memory.md)
{% endcontent-ref %}
