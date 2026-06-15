# Canonical Decision Schema v1.0

> Phase 2 — Codna Decision Engine
> Schema version: `"1.0"`
> Last updated: 2026-04-01

---

## 1. Top-Level Request Contract

```json
{
  "schema_version": "1.0",
  "engine_type": "monte_carlo",
  "runs": 10000,
  "seed": null,
  "workers": 0,
  "stream": false,
  "checkpoint_every": 1000,

  "variables": [ /* VarSpec[] */ ],
  "correlations": [ /* CorrSpec[] */ ],
  "objective_function": "revenue - cost",
  "scoring": {
    "expected_value": 0.6,
    "downside_risk": 0.4
  },

  "objectives": [ /* ObjectiveSpec[] — multi-output via | separator */ ],

  "engine_config": { /* EngineConfig — engine-specific blob */ }
}
```

### Field Definitions

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `schema_version` | `"1.0"` | No | `"1.0"` | Bump on breaking changes |
| `engine_type` | enum (11 values) | No | `"monte_carlo"` | See §2 |
| `runs` | int ≥ 1 | No | `10000` | Total MC iterations |
| `seed` | int \| null | No | `null` | null = non-deterministic |
| `workers` | int ≥ 0 | No | `0` | 0 = auto-detect cores |
| `stream` | bool | No | `false` | NDJSON progress frames |
| `checkpoint_every` | int ≥ 100 | No | `1000` | Streaming checkpoint interval |
| `variables` | `VarSpec[]` | No | `[]` | Simulation variables |
| `correlations` | `CorrSpec[]` | No | `[]` | Pearson correlation pairs |
| `objective_function` | string \| null | No | `null` | null = first variable |
| `scoring.expected_value` | float [0,1] | No | `0.6` | Weight for EV in score |
| `scoring.downside_risk` | float [0,1] | No | `0.4` | Weight for downside risk |

---

## 2. Engine Type Enumeration

| `engine_type` | Description | Required `engine_config` key |
|---------------|-------------|------------------------------|
| `monte_carlo` | Standard MC + Cholesky correlations | None |
| `qmc_sobol` | Quasi-MC with Sobol sequences | None |
| `lhs` | Latin Hypercube Sampling | None |
| `bootstrap` | Non-parametric bootstrap resampling | `bootstrap_config` |
| `scenario` | Discrete weighted scenario analysis | `scenario_config` |
| `sensitivity` | Tornado + first-order Sobol indices | None |
| `mcmc` | Metropolis-Hastings Bayesian MCMC | `mcmc_config` |
| `decision_tree` | Probability-weighted decision paths | `decision_tree_config` |
| `time_series` | Multi-horizon GBM/OU/ABM simulation | `time_series_config` |
| `compare` | N scenarios × M runs comparison | `scenarios` array |
| `importance_sampling` | Exponential tilting for tail events | `importance_sampling_config` |

---

## 3. VarSpec — Variable Specification

```json
{
  "name": "revenue",
  "distribution": "normal",
  "params": {
    "mean": 100000,
    "std": 20000
  }
}
```

### Supported Distributions

| `distribution` | `params` keys | Notes |
|----------------|--------------|-------|
| `normal` | `mean`, `std` | Standard normal |
| `uniform` | `low`, `high` | Inclusive bounds |
| `triangular` | `low`, `mode`, `high` | — |
| `lognormal` | `mean`, `std` | Log-space params |
| `beta` | `alpha`, `beta` | Shape params |
| `exponential` | `rate` | Rate = 1/mean |
| `weibull` | `shape`, `scale` | — |
| `gamma` | `shape`, `scale` | Marsaglia-Tsang |
| `pert` | `low`, `likely`, `high`, `gamma` | gamma default=4 |
| `bernoulli` | `p` | Returns 0 or 1 |
| `poisson` | `lambda` | Count distribution |
| `discrete` | `values[]`, `probabilities[]` | Cumulative CDF |
| `categorical` | `probabilities[]` | Returns index 0..N-1 |
| `student_t` | `df`, `loc`, `scale` | Heavy-tailed |
| `cauchy` | `location`, `scale` | No mean/variance |
| `laplace` | `mu`, `b` | Double exponential |
| `pareto` | `alpha`, `x_min` | Power-law |
| `gumbel` | `mu`, `beta` | Extreme value |
| `rayleigh` | `sigma` | — |
| `arcsine` | `low`, `high` | U-shaped |
| `logistic` | `mu`, `scale` | — |
| `halfnormal` | `sigma` | Positive only |
| `vonmises` | `mu`, `kappa` | Circular/angular |
| `neg_binomial` | `r`, `p` | Number of failures |
| `hypergeometric` | `N`, `K`, `n` | Sampling w/o replacement |
| `fixed` | `value` | Constant deterministic |

---

## 4. CorrSpec — Correlation Specification

```json
{
  "variables": ["revenue", "cost"],
  "coefficient": 0.65
}
```

Only normal-distributed variable pairs support Cholesky correlation.
Coefficient range: `[-1.0, 1.0]`.

---

## 5. Engine-Specific Config Blobs

### 5.1 `bootstrap_config`
```json
{
  "historical_data": [/* float array */],
  "statistic": "mean"
}
```
`statistic` values: `mean`, `median`, `std`, `sum`, `min`, `max`, `sharpe`, `range`

### 5.2 `scenario_config`
```json
{
  "scenarios": [
    {
      "name": "Optimistic",
      "probability": 0.3,
      "variables": { "revenue": 150000, "cost": 80000 },
      "objective_function": "revenue - cost"
    }
  ]
}
```

### 5.3 `mcmc_config`
```json
{
  "observed_data": [/* float array */],
  "burn_in": 1000,
  "chains": 4,
  "likelihood": "normal"
}
```
`likelihood` values: `normal`, `lognormal`

### 5.4 `decision_tree_config`
```json
{
  "paths": [
    {
      "label": "Launch → Accepts",
      "probability": 0.42,
      "variables": [/* VarSpec[] */],
      "objective_function": "revenue - cost"
    }
  ]
}
```

### 5.5 `time_series_config`
```json
{
  "model": "gbm",
  "initial_value": 100.0,
  "horizons": [1, 3, 6, 12, 24],
  "dt": 0.0833,
  "drift": 0.07,
  "volatility": 0.20,
  "ou_theta": 0.5,
  "ou_mu": 100.0,
  "autocorrelation": 0.0,
  "granularity": "month",
  "pct_levels": [5, 10, 25, 50, 75, 90, 95]
}
```
`model` values: `gbm`, `ou`, `arithmetic`, `compound`

### 5.6 `importance_sampling_config`
```json
{
  "target_threshold": -500000,
  "tail_direction": "lower",
  "tilt_variable": "revenue",
  "tilt_sigma": 0
}
```
`tail_direction` values: `lower`, `upper`

---

## 6. Objective Function Syntax

The `objective_function` field uses the Codna expression language:

```
revenue - cost
(revenue - cost) * probability
max(0, revenue - fixed_cost - variable_cost * units)
```

Multi-output (pipe-separated): `"revenue - cost | profit_margin * 100"`

Supported operators: `+`, `-`, `*`, `/`, `^` (pow), `-` (unary neg)  
Supported functions: `ln`, `log10`, `log2`, `exp`, `sqrt`, `abs`, `floor`, `ceil`, `round`, `min`, `max`, `clip`, `ifgt0`, `mod`

Variable names must exactly match the `name` fields in `variables[]`.

---

## 7. Response Envelope

```json
{
  "_proto": 1,
  "engine_version": "0.7.0-mojo-parallel",
  "engine_type": "monte_carlo",
  "simulation_model": "monte_carlo",
  "scenarios_run": 10000,
  "summary": {
    "mean": 42500.0,
    "median": 41200.0,
    "std": 15300.0,
    "variance": 234090000.0
  },
  "percentiles": {
    "p5": 18000.0, "p10": 22000.0, "p25": 31000.0,
    "p50": 41200.0, "p75": 53000.0, "p90": 63000.0,
    "p95": 70000.0, "p99": 84000.0
  },
  "risk": {
    "probability_of_loss": 0.082,
    "var_95": 18000.0,
    "cvar_95": 9500.0
  },
  "score": 0.72,
  "histogram_data": { /* Mojo-precomputed 50-bin histogram */ },
  "cdf_data": { /* Mojo-precomputed 100-point CDF */ },
  "result_hash": "a3f4b2c1..." /* SHA-256 hex, 64 chars */
}
```

`_proto: 1` = current JSON framing. `_proto: 2` = future binary framing.

---

## 8. Schema Versioning Policy

### `schema_version` bump rules

| Change Type | Action | Example |
|-------------|--------|---------|
| Add optional field | No bump | Add `objective_weights` |
| Add new engine_type | No bump | Add `vine_copula` |
| Remove field | MAJOR bump → `"2.0"` | Remove `correlations` |
| Change field semantics | MAJOR bump → `"2.0"` | `runs` → `iterations` |
| Add required field | MINOR bump → `"1.1"` | Add required `tenant_id` |

### Forward-compatibility rules

1. **Unknown fields MUST be ignored** by all parsers (both Python and Mojo)
2. **Missing optional fields use defaults** as specified in §1 Field Definitions
3. **`schema_version` is advisory** — engines process all requests regardless
4. Clients SHOULD send `schema_version: "1.0"` for explicit contract binding

---

## 9. Variable Usage by Engine

| Engine | `variables` | `correlations` | `objective_function` | `engine_config` |
|--------|-------------|----------------|----------------------|-----------------|
| `monte_carlo` | ✓ | ✓ | ✓ | — |
| `qmc_sobol` | ✓ | — | ✓ | — |
| `lhs` | ✓ | — | ✓ | — |
| `bootstrap` | — | — | — | `bootstrap_config` (historical_data) |
| `scenario` | ✓ (base vars) | — | ✓ | `scenario_config` (overrides) |
| `sensitivity` | ✓ | — | ✓ | — |
| `mcmc` | — | — | — | `mcmc_config` (observed_data) |
| `decision_tree` | — | — | — | `decision_tree_config` (paths.variables) |
| `time_series` | — | — | — | `time_series_config` |
| `compare` | — | — | — | `scenarios[].variables` |
| `importance_sampling` | ✓ | — | ✓ | `importance_sampling_config` |

---

## 10. Mandatory vs Optional Fields

### Mandatory (request MUST have)
- None — all fields have defaults. A `{}` payload runs 10k standard MC with no variables.

### Optional with explicit defaults
- `engine_type`: `"monte_carlo"`
- `runs`: `10000`
- `seed`: `null` (non-deterministic)
- `workers`: `0` (auto-detect cores)
- `stream`: `false`
- `checkpoint_every`: `1000`
- `scoring.expected_value`: `0.6`
- `scoring.downside_risk`: `0.4`

### Conditionally required (based on engine_type)
| Engine | Required field |
|--------|---------------|
| `bootstrap` | `bootstrap_config.historical_data` (non-empty array) |
| `scenario` | `scenario_config.scenarios` (non-empty array) |
| `mcmc` | `mcmc_config.observed_data` (non-empty array) |
| `decision_tree` | `decision_tree_config.paths` (non-empty array) |
| `time_series` | `time_series_config` (uses defaults if absent) |
