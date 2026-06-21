---
icon: chart-scatter
description: The simulation algorithms and input distributions Algenta runs — auto vs expert mode, when to pick each engine, and how a seed makes every run reproducible.
---

# Simulation models and distributions

A simulation model is the algorithm the engine uses to turn uncertain inputs into a [decision envelope](../help/glossary.md), and a distribution is the probabilistic shape of a single input variable. A `POST /v1/simulate` request selects one `simulation_model` (default `monte_carlo`), supplies its variables either through `mode: "auto"` (the engine infers distributions from `low`/`high` bounds) or `mode: "expert"` (you declare each `distribution` and its `params`), and optionally pins a `seed` so the run is reproducible.

## Why it matters

Different decision questions need different sampling strategies. A standard Monte Carlo pass answers "what is the expected value and spread of this objective"; a sensitivity run answers "which input drives the outcome"; an importance-sampling run answers "how likely is a rare tail loss" without burning millions of trials. Exposing the model as one field keeps the request shape stable while letting you trade convergence, coverage, and the kind of statistic you get back. Auto mode keeps the common case to a few lines, expert mode gives you full control over each input's distribution and the objective expression, and the `seed` makes results deterministic — the same inputs plus the same seed always return the same envelope, which is what makes runs auditable and testable.

## The simulation models

All models run natively in the [Mojo engine](engine.md). The `simulation_model` field accepts the values below (the response echoes the one used in `simulation_model`).

| Model | Value | Pick it when |
| --- | --- | --- |
| Monte Carlo | `monte_carlo` | Default. You want the expected value, percentiles, and confidence of an objective over independently sampled inputs. |
| Quasi-Monte Carlo (Sobol) | `qmc_sobol` | You want better convergence at a low run count using low-discrepancy Sobol sequences instead of pseudo-random draws. |
| Latin Hypercube Sampling | `lhs` | You want stratified coverage of the input space so every region is sampled, again for tighter estimates at fewer runs. |
| Bootstrap | `bootstrap` | You have a list of historical observations and want a non-parametric confidence interval on a statistic (mean, median, std, percentiles, Sharpe, and others) by resampling. Configured with `bootstrap_config`. |
| Scenario | `scenario` | You have a small set of discrete, named, probability-weighted scenarios rather than continuous distributions. Configured with `scenario_config`. |
| Sensitivity | `sensitivity` | You want to know which inputs move the outcome — a tornado chart and first-order Sobol indices. Configured with `sensitivity_config` (`tornado`, `sobol`, or `both`). |
| MCMC | `mcmc` | You want Bayesian posterior estimates from observed data via Metropolis-Hastings. Configured with `mcmc_config` (priors, likelihood, chains, burn-in). Expert mode only. |
| Importance sampling | `importance_sampling` | You need an accurate estimate of a rare tail event (for example a 1-in-10,000 loss) without millions of trials. Uses exponential tilting and reports tail probability and CVaR. Configured with `importance_sampling_config`. Expert mode only. |

{% hint style="info" %}
The engine also supports `decision_tree`, `time_series`, and `compare` models. They follow the same request shape with their own config blocks (`decision_tree_config`, `time_series_config`). This page covers the eight models above; see the [API reference](../api/reference.md) for the full set.
{% endhint %}

## Input distributions

In expert mode each variable carries a `distribution` and a `params` object. The validator rejects a request that omits the parameters a distribution requires.

| Distribution | `distribution` | Required `params` |
| --- | --- | --- |
| Normal | `normal` | `mean`, `std` (`std` must be positive) |
| Lognormal | `lognormal` | `mean`, `std` |
| Triangular | `triangular` | `low`, `mode`, `high` (with `low <= mode <= high`) |
| Uniform | `uniform` | `low`, `high` (with `high > low`) |
| Beta | `beta` | `alpha`, `beta` |
| Poisson | `poisson` | `lambda` |
| Pareto | `pareto` | shape parameters (heavy-tailed: failures, wealth, city sizes) |

The full enum also includes `fixed`, `discrete`, `categorical`, `exponential`, `weibull`, `gamma`, `pert`, `bernoulli`, and additional heavy-tailed and circular families. Auto mode does not take a `distribution` — you give each variable a `low` and a `high` and the engine infers the shape.

## Example

Expert mode, an explicit Sobol pass over a lognormal revenue and a triangular cost, with a fixed seed for reproducibility:

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
envelope = resp.json()
print(envelope["recommended_action"], envelope["confidence"])
```

Auto mode is shorter — the engine infers distributions from each variable's bounds:

```json title="simulate_auto.json"
{
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
}
```

Because both requests pin `seed: 42`, re-running either returns an identical envelope. Omit `seed` and each run draws a fresh random stream. Auto mode allows `runs` from 100 to 100,000; expert mode allows up to 1,000,000.

## Use this when

- You are choosing between sampling strategies and need to know which `simulation_model` fits the question (expected value, coverage, rare-tail, which-input-matters, or Bayesian posterior).
- You are writing an expert-mode request and need the exact `params` each distribution requires.
- You want reproducible runs in tests or audits and need to know how `seed` controls determinism.
- You are deciding between auto mode (infer distributions from bounds) and expert mode (declare distributions, correlations, and the objective expression).

## Next

{% content-ref url="engine.md" %}
[engine.md](engine.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
