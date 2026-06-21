---
icon: chart-scatter
description: Build a full simulation request — auto vs expert mode, choose a simulation_model, declare distributions and params, pin a seed, and read the percentiles back.
---

# Simulate a scenario

This guide walks you through a complete simulation: you will send a `POST /v1/simulate` request in both auto and expert mode, choose a `simulation_model`, declare each input variable's distribution and parameters, pin a `seed` so the run is reproducible, and read the percentiles back from the decision envelope. You need a verified account and an API key (see [Authentication](../authentication.md)); the examples target the hosted API at `https://api.algenta.ai`, but a self-hosted engine at `http://localhost:8000` works the same way. If you have not run a simulation before, start with [Run your first query](first-query.md).

{% stepper %}
{% step %}
### Choose auto or expert mode

The `mode` field is the request discriminator. Use `mode: "auto"` when you only know an optimistic and pessimistic bound for each variable — the engine infers a distribution from each variable's `low`/`high`. Use `mode: "expert"` when you want to declare each variable's `distribution` and `params` and supply your own `objective_function`. Verify your choice by confirming the matching payload shape: auto requires a `scenario` object, expert requires a `simulation` object. Sending an `auto` payload with a `simulation` block (or the reverse) is rejected with HTTP 422.
{% endstep %}

{% step %}
### Select a simulation_model

Set `simulation_model` to the algorithm that fits your question. It defaults to `monte_carlo`; the other values are `qmc_sobol`, `lhs`, `bootstrap`, `scenario`, `sensitivity`, `mcmc`, `decision_tree`, `time_series`, `compare`, and `importance_sampling`. Pick `monte_carlo` for a standard expected-value-and-spread pass, `sensitivity` to learn which input drives the outcome, or `importance_sampling` for a rare tail estimate. Some models need a config block (for example `sensitivity_config` or `mcmc_config`), and `mcmc` and `importance_sampling` are expert-mode only. Verify the engine honored your choice: the response echoes the algorithm used in the top-level `simulation_model` field, which should match what you sent.
{% endstep %}

{% step %}
### Send an auto-mode request

In auto mode you give each variable a `low` and a `high` (the engine infers the shape) and name an `objective`. Valid `objective` values are `maximize_net_value`, `maximize_revenue`, `minimize_cost`, `minimize_risk`, and `maximize_score`. Add `seed` to make the run reproducible. `runs` ranges from 100 to 100,000 in auto mode and defaults to 10,000.

```bash title="simulate_auto.sh"
curl -sS -X POST "https://api.algenta.ai/v1/simulate" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "simulation_model": "monte_carlo",
    "scenario": {
      "name": "Product launch decision",
      "variables": {
        "revenue": {"low": 80000, "high": 200000},
        "cost": {"low": 40000, "high": 90000}
      },
      "objective": "maximize_net_value"
    },
    "runs": 10000,
    "seed": 42
  }'
```

Verify it succeeded: you get HTTP 200 and a JSON body whose `recommended_action` and `confidence` fields are populated. An `high` that is not strictly greater than `low` returns HTTP 422 before any computation runs.
{% endstep %}

{% step %}
### Declare distributions and params in expert mode

Expert mode replaces inferred bounds with an explicit `distribution` and `params` per variable, plus an `objective_function` expression over those variable names. The validator rejects a variable that omits the parameters its distribution requires. The common distributions and their required `params` are:

| `distribution` | Required `params` |
| --- | --- |
| `normal` | `mean`, `std` (`std` must be positive) |
| `lognormal` | `mean`, `std` |
| `triangular` | `low`, `mode`, `high` (with `low <= mode <= high`) |
| `uniform` | `low`, `high` (with `high > low`) |
| `beta` | `alpha`, `beta` |
| `poisson` | `lambda` |
| `pert` | `low`, `likely`, `high` |

The full enum also includes `fixed`, `discrete`, `categorical`, `exponential`, `weibull`, `gamma`, `bernoulli`, and additional heavy-tailed and circular families. Verify your spec before sending by confirming each variable's `params` covers every field its `distribution` requires; otherwise the engine returns HTTP 422 with a message naming the missing parameter (for example `Normal distribution requires 'mean' and 'std'`).
{% endstep %}

{% step %}
### Pin a seed for reproducibility

Add a `seed` (any integer `>= 0`) at the top level of the request. Determinism is a core guarantee: the same inputs plus the same `seed` always return the same decision envelope. Omit `seed` and each run draws a fresh random stream. This expert-mode request pins `seed: 42`, weights the score with `scoring` (whose `expected_value` and `downside_risk` weights must sum to `1.0`), and allows `runs` up to 1,000,000.

```python title="simulate_expert.py"
import os
import httpx

resp = httpx.post(
    "https://api.algenta.ai/v1/simulate",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "mode": "expert",
        "simulation_model": "qmc_sobol",
        "simulation": {
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "lognormal",
                    "params": {"mean": 11.5, "std": 0.4},
                },
                {
                    "name": "cost",
                    "distribution": "triangular",
                    "params": {"low": 40000, "mode": 60000, "high": 90000},
                },
            ],
            "objective_function": "revenue - cost",
            "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
        },
        "runs": 50000,
        "seed": 42,
    },
)
resp.raise_for_status()
envelope = resp.json()
```

Verify reproducibility by running the request twice and comparing `result_hash` (also returned as the `X-Decision-Hash` response header): the two values are identical when `seed` is pinned and differ when it is omitted.
{% endstep %}

{% step %}
### Read the percentiles

The response is a decision envelope. Read the spread of the objective from the `percentiles` object — it always carries `p5`, `p25`, `p50`, `p75`, and `p95`, and includes `p10`, `p90`, and `p99` when the model produces them. The `metrics` object adds `expected_value`, `median`, `std_deviation`, `probability_of_loss`, `var_95`, and `cvar_95`. The `metadata.seed` field echoes the seed that produced the run.

```python title="read_percentiles.py"
pct = envelope["percentiles"]
print("p5  (downside floor):", pct["p5"])
print("p50 (median)        :", pct["p50"])
print("p95 (upside ceiling):", pct["p95"])

m = envelope["metrics"]
print("expected_value      :", m["expected_value"])
print("probability_of_loss :", m["probability_of_loss"])
print("seed used           :", envelope["metadata"]["seed"])
```

Verify the values are coherent: `p5 <= p50 <= p95`, `metadata.seed` matches the seed you sent, and `simulation_model` matches the algorithm you requested.
{% endstep %}
{% endstepper %}

## Expected result

A successful call returns HTTP 200 with a decision envelope containing a populated `recommended_action`, a `confidence` between 0 and 1, a `metrics` summary, and a `percentiles` summary with at least `p5`, `p25`, `p50`, `p75`, and `p95`. The top-level `simulation_model` echoes the algorithm you selected, `metadata.seed` echoes your pinned seed, and a `result_hash` (mirrored in the `X-Decision-Hash` header) lets you confirm two seeded runs are byte-for-byte identical.

## Troubleshooting

{% hint style="warning" %}
**HTTP 422 on the request.** A validation error means the payload does not match the schema. Common causes: a `distribution` whose `params` omits a required field (the message names it), an auto variable whose `high` is not strictly greater than `low`, `runs` outside the allowed range (100–100,000 auto, 100–1,000,000 expert), `scoring` weights that do not sum to `1.0`, or a `mode` value that does not match the body block you sent. See [API errors](../api/errors.md).
{% endhint %}

{% hint style="info" %}
**HTTP 429.** Each successful call consumes one simulation from your monthly quota; a 429 means the quota or the per-plan rate limit is exhausted. See [Rate limits](../api/rate-limits.md) and [Plans, billing & credits](../billing.md).
{% endhint %}

## Next

{% content-ref url="../concepts/simulation-models.md" %}
[simulation-models.md](../concepts/simulation-models.md)
{% endcontent-ref %}

{% content-ref url="run-a-decision.md" %}
[run-a-decision.md](run-a-decision.md)
{% endcontent-ref %}
