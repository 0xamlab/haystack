# Simulation Engine Expansion Plan
## Extended Simulation Models + Mojo Performance Overhaul

---

## Current State Analysis

### Critical Performance Bottlenecks in [`mojo/engine/main.mojo`](mojo/engine/main.mojo)

1. **`builtins.eval()` called in the hot loop** — The #1 bottleneck. Every iteration crosses the Mojo→Python boundary to call Python's `eval()` with a freshly-built dict. For 10K runs × N variables, that's 10K full Python interpreter calls inside what should be a pure-native loop.

2. **`py_to_f64()` via `struct.pack/unpack`** — Pre-loop conversion uses Python's `struct` module through `PythonObject`, adding unnecessary marshaling overhead.

3. **Recursive quicksort for post-sort stats** — Stack-based recursion on up to 1M float64 values; Mojo's introspection-based introsort or radix sort would be faster.

4. **Single-threaded hot loop** — No SIMD vectorization, no parallelism across CPU cores. Mojo supports both natively via `SIMD[DType.float64, 8]` and `parallelize()`.

5. **`Python.evaluate("{}")` per iteration** — Building a new empty dict in Python on every scenario run just to pass variable values.

6. **JSON output via string concatenation** — Brittle and slow; should use a dedicated output struct.

### Current Simulation Models: Only 1
- Monte Carlo with Normal, Uniform, Triangular, Lognormal, Fixed distributions

### Current Architecture
```
POST /v1/simulate
  └── simulation_service.py
        └── _build_*_mojo_payload()
              └── mojo_adapter.py → subprocess → mojo_build/simulate (binary)
                    └── stdout JSON → parse → DecisionEnvelope
```

---

## Target Architecture

```
POST /v1/simulate  (model: monte_carlo | qmc | lhs | mcmc | bootstrap | scenario | sensitivity)
  └── simulation_service.py
        ├── engine_dispatcher.py  ← NEW: routes to correct engine
        │     ├── mojo_engine/     ← ENHANCED: SIMD + parallel + no Python eval
        │     │     ├── main.mojo  (v0.3.0 — monte_carlo + qmc + lhs)
        │     │     └── mojo_adapter.py (unchanged interface)
        │     └── python_engine/   ← NEW: pure Python for MCMC, Bootstrap, Scenario, Sensitivity
        │           ├── mcmc.py
        │           ├── bootstrap.py
        │           ├── scenario.py
        │           └── sensitivity.py
        └── DecisionEnvelope (enhanced with model_type, convergence_stats, sensitivity_indices)
```

---

## Phase A: Mojo Engine Performance Overhaul

### A1 — Eliminate Python `eval()` from the Hot Loop

**Current code (bottleneck):**
```mojo
# Called 10,000 times — each call crosses Python/Mojo boundary
var locals_dict = Python.evaluate("{}")
locals_dict[var_names[i]] = sample[i]
var res = builtins.eval(objective_fn, globals_dict, locals_dict)
```

**Fix — Pre-compile to an expression tree in native Mojo:**

Parse the `objective_function` string *once* before the loop into an `ExprNode` tree. Each node is a `+`, `-`, `*`, `/` or a variable reference (index into the sample array). Then evaluate the tree with zero Python calls.

```mojo
struct ExprNode:
    var op: Int      # 0=literal, 1=var_ref, 2=add, 3=sub, 4=mul, 5=div
    var value: Float64   # for literals
    var var_idx: Int     # for var_ref
    var left: Int        # child node index
    var right: Int       # child node index

# Parse once:
var expr_tree = parse_objective(objective_fn, var_names)

# Hot loop — zero Python calls:
for _ in range(runs):
    outcome = eval_expr(expr_tree, sample)
```

This eliminates 100% of Python boundary crossings from the hot loop. **Expected speedup: 10–50× for complex objective functions.**

### A2 — SIMD Vectorization

Process 8 scenarios simultaneously using Mojo's native SIMD:

```mojo
from sys.intrinsics import strided_load
alias SIMD_WIDTH = 8

# Sample 8 scenarios at once for each variable
var v_mean = SIMD[DType.float64, SIMD_WIDTH](param0[i])
var v_rand = randn_float64_simd[SIMD_WIDTH]()
var v_sample = v_mean + v_std * v_rand

# Vectorized objective evaluation (for linear objectives)
var v_outcome = v_revenue - v_cost
```

**Expected speedup: ~8× on vectorizable workloads.**

### A3 — Parallelism with `parallelize()`

Split the N runs across all CPU cores:

```mojo
from algorithm import parallelize, vectorize
alias THREADS = 8

var partial_outcomes = List[List[Float64]](capacity=THREADS)

@parameter
fn worker(thread_id: Int):
    var chunk = runs // THREADS
    var start = thread_id * chunk
    var local_outcomes = List[Float64](capacity=chunk)
    for _ in range(start, start + chunk):
        local_outcomes.append(eval_scenario(...))
    partial_outcomes[thread_id] = local_outcomes

parallelize[worker](THREADS)
# Merge and sort partial_outcomes
```

**Expected speedup: ~N× (N = CPU core count, typically 4–16×).**

### A4 — Fast `py_to_f64` Replacement

Replace the `struct.pack/unpack` bridge with a direct cast:

```mojo
# Old (slow — uses Python struct module):
var f = builtins.float(obj)
var packed = struct_m.pack("d", f)

# New (fast — direct Mojo cast):
fn fast_f64(obj: PythonObject) raises -> Float64:
    return Float64(String(obj.__str__()))
```

Or better: pre-convert all parameters to native Mojo `List[Float64]` once before the loop (already done), remove `py_to_f64` from anywhere it's called per-iteration.

### A5 — Replace Recursive Quicksort with Introsort

```mojo
# Replace recursive quicksort with iterative pattern + heapsort fallback
# Mojo stdlib will eventually expose sort(); until then use iterative quicksort
# with median-of-3 pivot selection and insertion sort for small subarrays (< 16)
fn introsort(mut arr: List[Float64], n: Int):
    var depth_limit = 2 * ilog2(n)
    _introsort_loop(arr, 0, n, depth_limit)
```

### A6 — New Distributions in Mojo

Add to `main.mojo`:

| Distribution | Params | Mojo implementation |
|---|---|---|
| `beta` | α, β | `sample_beta(alpha, beta)` — via two gamma samples |
| `exponential` | λ (rate) | `-ln(U) / λ` |
| `weibull` | k (shape), λ (scale) | `λ * (-ln(U))^(1/k)` |
| `poisson` | λ | Knuth algorithm or Devroye for large λ |
| `bernoulli` | p | `U < p ? 1 : 0` |
| `discrete` | values[], probs[] | inverse CDF lookup |
| `pert` | low, mode, high, γ=4 | Maps to beta via location/scale |
| `gamma` | shape α, scale θ | Marsaglia-Tsang method |
| `beta_pert` | low, likely, high | Special case of beta useful for project risk |

---

## Phase B: New Simulation Models

### B1 — Quasi-Monte Carlo (QMC) — Sobol Sequences

**What:** Instead of pseudo-random numbers, use low-discrepancy Sobol sequences. Same accuracy as Monte Carlo but with fewer samples (convergence rate O(log(N)^d / N) vs O(1/√N)).

**When to use:** When users need high accuracy with fewer trials (faster, cheaper). Best for smooth, low-dimensional problems (< 20 variables).

**Implementation:**
- Sobol sequence generator in Mojo (direction numbers from Joe-Kuo tables)
- Add `engine_type: "qmc"` or `simulation_model: "qmc_sobol"` to request schema
- Same output schema as Monte Carlo

```mojo
struct SobolGenerator:
    var dim: Int
    var count: Int
    var direction_numbers: List[List[Int]]  # Joe-Kuo 2010 tables
    
    fn next_point(mut self) -> List[Float64]:
        # Van der Corput + Gray code scrambling
        ...
```

**New request field:**
```json
{
  "simulation_model": "qmc_sobol",
  "runs": 4096,  // Sobol works best with powers of 2
  "scramble": true
}
```

### B2 — Latin Hypercube Sampling (LHS)

**What:** Stratified sampling that guarantees coverage of the full probability space. Divides each variable's distribution into N equal-probability strata and samples once from each.

**When to use:** Better than pure Monte Carlo for the same N, faster convergence, especially for high-dimensional input spaces.

**Implementation:**
- Python engine (numpy-based) — uses `scipy.stats.qmc.LatinHypercube`
- Output identical to Monte Carlo format
- Add `simulation_model: "lhs"` to request

```python
# apps/api_server/compute/python_engine/lhs.py
from scipy.stats import qmc
sampler = qmc.LatinHypercube(d=n_vars, seed=seed)
sample = sampler.random(n=runs)
scaled = qmc.scale(sample, lower_bounds, upper_bounds)
```

### B3 — Markov Chain Monte Carlo (MCMC)

**What:** Bayesian inference engine. Given observed data and prior beliefs, computes the posterior distribution of parameters. Unlike standard Monte Carlo which samples from known distributions, MCMC infers the distribution itself.

**When to use:**
- "Given our historical revenue data, what's the posterior distribution of growth rate?"
- Bayesian A/B testing
- Parameter estimation from data

**Algorithm:** Metropolis-Hastings (simple to implement, widely understood)

```python
# apps/api_server/compute/python_engine/mcmc.py
class MCMCSimulation:
    def run(self, likelihood_fn, prior_fn, initial_params, n_samples, burn_in):
        samples = []
        current = initial_params
        for i in range(n_samples + burn_in):
            proposal = propose(current)
            ratio = exp(likelihood_fn(proposal) + prior_fn(proposal)
                      - likelihood_fn(current) - prior_fn(current))
            if random() < min(1, ratio):
                current = proposal
            if i >= burn_in:
                samples.append(current)
        return samples
```

**New request schema:**
```json
{
  "simulation_model": "mcmc",
  "observed_data": [150000, 180000, 165000, 200000],
  "parameter_priors": {
    "mean": {"distribution": "normal", "params": {"mean": 170000, "std": 30000}},
    "std": {"distribution": "uniform", "params": {"low": 5000, "high": 50000}}
  },
  "n_samples": 10000,
  "burn_in": 1000,
  "chains": 4
}
```

### B4 — Bootstrap Simulation

**What:** Non-parametric resampling from actual historical data. No assumption about distribution shape. Resample with replacement N times, compute statistic each time.

**When to use:**
- "I have 3 years of monthly revenue — what's my distribution of annual revenue?"
- Confidence intervals on empirical data
- When you can't assume any distribution

**Implementation:**
```python
# apps/api_server/compute/python_engine/bootstrap.py
def run_bootstrap(historical_data: list[float], statistic: str, n_resamples: int):
    results = []
    n = len(historical_data)
    for _ in range(n_resamples):
        resample = random.choices(historical_data, k=n)
        results.append(compute_statistic(resample, statistic))
    return results
```

**New request schema:**
```json
{
  "simulation_model": "bootstrap",
  "historical_data": [120000, 145000, 138000, 160000, 175000],
  "statistic": "mean",  // mean | median | std | sharpe | percentile_5
  "n_resamples": 10000,
  "confidence_level": 0.95
}
```

### B5 — Scenario Analysis

**What:** Discrete weighted scenarios (bear/base/bull or custom). Not stochastic — deterministic outcomes per scenario with assigned probabilities.

**When to use:**
- "In a recession scenario (30% probability), revenue drops 40%..."
- Board presentations requiring named scenario outputs
- Strategic planning with clear scenario labels

**Implementation:** Pure Python, very fast.

```python
# apps/api_server/compute/python_engine/scenario.py
class ScenarioAnalysis:
    def run(self, scenarios: list[Scenario]) -> ScenarioResult:
        # Each scenario: name, probability, variable_values
        # Output: expected value = Σ(prob_i × value_i), scenario comparison table
```

**New request schema:**
```json
{
  "simulation_model": "scenario",
  "scenarios": [
    {"name": "Bear", "probability": 0.25, "variables": {"revenue": 400000, "cost": 350000}},
    {"name": "Base", "probability": 0.50, "variables": {"revenue": 600000, "cost": 400000}},
    {"name": "Bull", "probability": 0.25, "variables": {"revenue": 900000, "cost": 420000}}
  ]
}
```

### B6 — Sensitivity Analysis (Tornado Charts)

**What:** Determines which input variables have the most impact on the output. Runs Monte Carlo while varying one variable at a time (Pearson correlations, Spearman rank correlations, Sobol sensitivity indices).

**When to use:**
- "Which of our 15 variables actually matters?"
- Pre-simulation exploration to reduce model complexity
- Communicating key risk drivers to stakeholders

**Implementation:**
```python
# apps/api_server/compute/python_engine/sensitivity.py
class SensitivityAnalysis:
    def run_tornado(self, variables, objective_fn, base_values, n_samples):
        # For each variable: fix all others at base, vary this one ±1σ
        # Compute swing in objective output
        # Return sorted by impact magnitude (tornado chart data)
        
    def run_sobol(self, variables, objective_fn, n_samples):
        # First-order Sobol indices (individual effect)
        # Total-order Sobol indices (including interactions)
```

**New response fields:**
```json
{
  "sensitivity_indices": {
    "first_order": {"revenue": 0.62, "cost": 0.31, "churn": 0.07},
    "total_order": {"revenue": 0.68, "cost": 0.35, "churn": 0.12},
    "tornado_chart": [
      {"variable": "revenue", "low_swing": -250000, "high_swing": 180000},
      {"variable": "cost", "low_swing": -120000, "high_swing": 90000}
    ]
  }
}
```

---

## Phase C: Engine Dispatcher

New `apps/api_server/compute/engine_dispatcher.py`:

```
simulation_model    →  engine         →  why
─────────────────────────────────────────────────────────
monte_carlo         →  Mojo v0.3      →  SIMD + parallel native Mojo
qmc_sobol           →  Mojo v0.3      →  Sobol generator in native Mojo
lhs                 →  Python/scipy   →  scipy.stats.qmc already optimal
mcmc                →  Python         →  Bayesian: complex, Python/numpy fine
bootstrap           →  Python/numpy   →  Resampling: numpy choice() is fast
scenario            →  Python         →  Trivial arithmetic, no sampling needed
sensitivity         →  Python/numpy   →  Correlation/Sobol needs numpy anyway
```

```python
# engine_dispatcher.py
async def dispatch(model: SimulationModel, payload: dict) -> dict:
    if model in (SimulationModel.MONTE_CARLO, SimulationModel.QMC_SOBOL):
        return await invoke_engine(payload)       # Mojo binary
    elif model == SimulationModel.LHS:
        return await lhs_engine.run(payload)
    elif model == SimulationModel.MCMC:
        return await mcmc_engine.run(payload)
    elif model == SimulationModel.BOOTSTRAP:
        return await bootstrap_engine.run(payload)
    elif model == SimulationModel.SCENARIO:
        return await scenario_engine.run(payload)
    elif model == SimulationModel.SENSITIVITY:
        return await sensitivity_engine.run(payload)
```

---

## Phase D: Schema Changes

### New fields in `SimulateRequest`:

```python
class SimulationModel(str, enum.Enum):
    MONTE_CARLO = "monte_carlo"   # default — current behavior
    QMC_SOBOL   = "qmc_sobol"    # quasi-Monte Carlo
    LHS         = "lhs"           # Latin hypercube
    MCMC        = "mcmc"          # Bayesian MCMC
    BOOTSTRAP   = "bootstrap"     # non-parametric resampling
    SCENARIO    = "scenario"      # discrete scenarios
    SENSITIVITY = "sensitivity"   # sensitivity analysis

class SimulateRequestV2(SimulateRequestExpert):
    simulation_model: SimulationModel = SimulationModel.MONTE_CARLO
    # model-specific extensions via discriminated union
    mcmc_config: MCMCConfig | None = None
    bootstrap_config: BootstrapConfig | None = None
    scenario_config: ScenarioConfig | None = None
    sensitivity_config: SensitivityConfig | None = None
```

### New fields in `DecisionEnvelope` response:

```python
class DecisionEnvelope(BaseModel):
    # ... existing fields ...
    simulation_model: str          # which model was used
    engine_type: str               # "mojo-native" | "python-numpy"
    convergence_rate: float | None # for QMC: convergence estimate
    sensitivity_indices: SensitivityResult | None  # for sensitivity model
    scenarios: list[ScenarioResult] | None         # for scenario model
    bootstrap_ci: BootstrapCI | None               # for bootstrap model
```

### New `SimulationModel` DB column (migration 0011):

```sql
ALTER TABLE simulation_runs ADD COLUMN simulation_model VARCHAR(30) DEFAULT 'monte_carlo';
```

---

## Phase E: API Changes

### Updated `POST /v1/simulate`:

The `mode` field stays (`auto` | `expert`) but a new `simulation_model` field is added:

```bash
# Monte Carlo (existing)
curl -X POST /v1/simulate -d '{"mode": "auto", "simulation_model": "monte_carlo", ...}'

# Quasi-Monte Carlo (new, faster convergence)
curl -X POST /v1/simulate -d '{"mode": "expert", "simulation_model": "qmc_sobol", "runs": 4096, ...}'

# Bootstrap from historical data (new)
curl -X POST /v1/simulate -d '{
  "simulation_model": "bootstrap",
  "bootstrap_config": {"historical_data": [120000, 145000, ...], "statistic": "mean"},
  "runs": 10000
}'

# Scenario analysis (new)
curl -X POST /v1/simulate -d '{
  "simulation_model": "scenario",
  "scenario_config": {"scenarios": [{"name": "Bear", "probability": 0.3, ...}]}
}'

# Sensitivity tornado chart (new)
curl -X POST /v1/simulate -d '{
  "simulation_model": "sensitivity",
  "mode": "expert",
  "simulation": {"variables": [...], "objective_function": "revenue - cost"}
}'
```

---

## Phase F: Portal UI Changes

### Simulation page additions:

1. **Model selector tabs** at the top of the simulation form:
   ```
   [Monte Carlo] [QMC Sobol] [LHS] [MCMC] [Bootstrap] [Scenario] [Sensitivity]
   ```

2. **Monte Carlo**: existing form (no change)

3. **QMC Sobol**: same as Monte Carlo + "trials must be power of 2" hint + scramble toggle

4. **Bootstrap**: replaces variable form with "Paste historical data" text area + statistic selector

5. **Scenario**: table editor with rows (name, probability, variable values)

6. **Sensitivity**: existing variable form + output shows tornado chart (horizontal bar chart)

7. **MCMC**: priors editor + observed data input + chain config

### New distribution cards in variable editor:

Current: Normal, Uniform, Triangular, Lognormal, Fixed  
Add: **Beta**, **Exponential**, **Weibull**, **Poisson**, **Bernoulli**, **PERT**, **Gamma**

---

## Performance Targets

| Model | Current (10K runs) | Target |
|-------|-------------------|--------|
| Monte Carlo | ~200ms | ~15ms (SIMD + parallel) |
| QMC Sobol | — | ~8ms (deterministic, no RNG overhead) |
| LHS | — | ~50ms (scipy, Python) |
| Bootstrap | — | ~30ms (numpy resample) |
| Scenario | — | <5ms (pure arithmetic) |
| Sensitivity | — | ~200ms (runs MC multiple times) |
| MCMC | — | ~2s (10K samples, Python) |

---

## Implementation Order (Execution Sequence)

```
Week 1:
  A1 — Mojo: eliminate Python eval → ExprNode tree evaluator
  A2 — Mojo: SIMD vectorization for sampling
  A4 — Mojo: fast f64 conversion
  B5 — Python: Scenario engine (trivial, high value for users)

Week 2:
  A3 — Mojo: parallelize() across cores
  A5 — Mojo: introsort
  A6 — Mojo: new distributions (beta, exponential, weibull, poisson, pert)
  B4 — Python: Bootstrap engine

Week 3:
  B1 — Mojo: Sobol QMC generator
  B2 — Python: LHS engine (scipy)
  D  — Schema changes (SimulationModel enum, new request/response fields)
  migration 0011

Week 4:
  B6 — Python: Sensitivity analysis + tornado chart
  B3 — Python: MCMC (Metropolis-Hastings)
  C  — Engine dispatcher
  E  — API wiring
  F  — Portal UI (model selector, new forms, tornado chart)
```

---

## Files to Create/Modify

### New files:
- [`mojo/engine/main.mojo`](mojo/engine/main.mojo) — v0.3.0 (complete rewrite for perf)
- `apps/api_server/compute/python_engine/__init__.py`
- `apps/api_server/compute/python_engine/lhs.py`
- `apps/api_server/compute/python_engine/mcmc.py`
- `apps/api_server/compute/python_engine/bootstrap.py`
- `apps/api_server/compute/python_engine/scenario.py`
- `apps/api_server/compute/python_engine/sensitivity.py`
- `apps/api_server/compute/engine_dispatcher.py`
- `apps/api_server/alembic/versions/0011_add_simulation_model.py`

### Modified files:
- [`apps/api_server/schemas/simulate.py`](apps/api_server/schemas/simulate.py) — add `SimulationModel` enum + model-specific configs
- [`apps/api_server/schemas/response.py`](apps/api_server/schemas/response.py) — add `simulation_model`, `sensitivity_indices`, `scenarios`, `bootstrap_ci`
- [`apps/api_server/services/simulation_service.py`](apps/api_server/services/simulation_service.py) — route through dispatcher
- [`apps/api_server/models/simulation_run.py`](apps/api_server/models/simulation_run.py) — add `simulation_model` column
- [`apps/portal/src/app/dashboard/simulations/page.tsx`](apps/portal/src/app/dashboard/simulations/page.tsx) — model selector UI
- [`apps/portal/src/lib/api.ts`](apps/portal/src/lib/api.ts) — new request/response types

---

## Dependencies to Add

```
# requirements-dev.txt additions:
scipy>=1.13.0          # LHS, Sobol QMC, Sensitivity analysis
numpy>=1.26.0          # Bootstrap, MCMC, numerical ops
numba>=0.59.0          # Optional: JIT for Python engines if needed
```
