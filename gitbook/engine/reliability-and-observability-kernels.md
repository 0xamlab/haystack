---
icon: shield-halved
description: Distributed-training checkpoint/recovery math, LLM-serving health metrics, a structured JSON logger, classical MTBF/Weibull reliability engineering, and perturbation-based sensitivity analysis -- five separate disciplines, not one system.
---

# Reliability and observability kernels

Five modules that get grouped under one "things fail, plan for it" umbrella but answer five
genuinely different questions: how does a distributed training job recover when a node dies
mid-step, how does a serving fleet measure its own health, how does a kernel emit a structured
log line, how likely is a system to survive a mission without failing, and how sensitive is a
model's output to perturbing its inputs. None of these five modules imports another, and two of
the names are misleading on first read, so the mapping from name to real content is worth stating
up front:

* **`fault_tolerance`** is not retry/backoff/circuit-breaker logic. It is the arithmetic behind
  resuming a distributed training job after a node failure -- checkpoint-interval sizing,
  recovery cost, deterministic replay seeds, and elastic worker rescaling.
* **`observability`** is not a tracing/span library. It is ten closed-form estimators for the
  numbers an inference-serving dashboard would show -- p99 latency, GPU memory pressure, token
  throughput, cache miss rate, and a composite health score.
* **`logging.logger`** is exactly what it sounds like: a small structured JSON logger.
* **`reliability`** is classical reliability engineering -- exponential and Weibull survival
  curves, MTBF, availability, series/parallel/k-of-n systems, the bathtub curve.
* **`robustness`**, despite sitting next to `reliability` in this family, means something
  unrelated to failure rates: it is perturbation and sensitivity analysis (one-at-a-time,
  Morris screening, Sobol indices, tornado charts) for a generic scalar function. A system's
  probability of not failing and a model's sensitivity to input noise are different questions
  answered with different math, and this corpus keeps them in separate modules.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# MTBF = 1000 hours, MTTR = 10 hours -> A = MTBF / (MTBF + MTTR)
runtime.execute("reliability", "availability", [1000.0, 10.0])["result"]
# 0.9900990099009901 -- about five hours of downtime a year at this MTBF/MTTR ratio

runtime.execute("logging.logger", "get_logger", ["engine"])["result"]
# {"__algenta_struct": "Logger", "v": ["engine", 1]} -- level 1 == INFO
```

## The modules

| Module | What it does |
| --- | --- |
| `fault_tolerance` | Checkpoint-interval sizing, failure-recovery cost, deterministic replay seeding, node-failure probability, gradient staleness under async training, elastic worker rescaling, and checkpoint-replication storage overhead for distributed training jobs. |
| `observability` | Ten rolling/closed-form metrics for a serving fleet: p99 latency, GPU memory pressure, token-throughput EMA, cache miss rate, queue-wait percentile, GPU utilization, request success rate, model-drift alert score, cost-per-token, and a composite health score. |
| `logging.logger` | A structured JSON logger: one `{"level":...,"logger":...,"msg":...}` line per call, four levels (DEBUG/INFO/WARNING/ERROR), minimum-level filtering. |
| `reliability` | Classical reliability engineering: exponential and Weibull reliability/failure-rate, MTBF, availability, series/parallel/k-of-n system reliability, the bathtub curve, and mission reliability. |
| `robustness` | Perturbation and sensitivity analysis for a generic scalar function: one-at-a-time sensitivity, Morris elementary-effects screening, a simplified Monte Carlo Sobol first-order estimate, tornado-chart data, input-range sweeps, and a coefficient-of-variation robustness score. |

## `fault_tolerance`: distributed-training recovery arithmetic, not software retry patterns

| Function | What it does |
| --- | --- |
| `checkpoint_interval_optimal(checkpoint_cost_steps, failure_rate_per_step)` | `sqrt(2 * cost / rate)` -- the classic square-root form that trades checkpoint overhead against expected work lost to failure. `1e6` (a large sentinel, not infinity) if the failure rate is `<= 0`. |
| `recovery_cost_estimate(steps_since_checkpoint, step_compute_cost, checkpoint_load_cost)` | `checkpoint_load_cost + steps_since_checkpoint * step_compute_cost` -- total cost of replaying from the last checkpoint. |
| `deterministic_seed(base_seed, step, rank)` | `base_seed + step * 1000003 + rank` -- a reproducible per-step, per-worker seed for replaying training exactly after a restart. |
| `partial_batch_replay_loss(full_batch_loss, processed_samples, batch_size)` | `full_batch_loss * processed_samples / batch_size` -- the loss contribution already "banked" from a batch that failed partway through. `0.0` if `batch_size <= 0`. |
| `node_failure_probability(n_nodes, mtbf_hours, job_duration_hours)` | `1 - exp(-n_nodes * job_duration_hours / mtbf_hours)` -- probability at least one node fails somewhere in the job. `1.0` if `mtbf_hours <= 0`. |
| `mtbf_checkpoint_frequency(mtbf_hours, steps_per_hour)` | `sqrt(mtbf_hours * steps_per_hour)` -- checkpoint every this many steps, derived from per-node MTBF converted to steps. |
| `gradient_staleness_factor(staleness, decay_rate)` | `exp(-decay_rate * staleness)` -- down-weights a gradient computed `staleness` steps ago in asynchronous training; `1.0` when fresh. |
| `elastic_training_scale(current_workers, target_workers, lr)` | `lr * target_workers / current_workers` -- linear learning-rate rescaling when the worker count changes mid-job. `lr` unchanged if `current_workers <= 0`. |
| `failure_detection_latency(heartbeat_interval_ms, missed_heartbeats)` | `heartbeat_interval_ms * missed_heartbeats` -- time to declare a node dead from missed heartbeats. |
| `replication_overhead(checkpoint_bytes, replication_factor, total_storage_bytes)` | `(replication_factor - 1) * checkpoint_bytes / total_storage_bytes` -- storage fraction spent on replica copies beyond the primary. `0.0` if `total_storage_bytes <= 0`. |

**Why checkpoint often, traced against a real cluster size.** At 1,024 nodes, a per-node MTBF of
100,000 hours (about 11.4 years — a solid, not exceptional, hardware reliability figure), and a
72-hour (three-day) training run:

```python
runtime.execute("fault_tolerance", "node_failure_probability", [1024.0, 100000.0, 72.0])["result"]
# 0.5215865680876512
```

Better-than-average hardware still gives this job roughly a coin flip's chance of losing at least
one node before it finishes, purely from node count multiplying an individually-small failure
rate. That is the argument `checkpoint_interval_optimal` and `mtbf_checkpoint_frequency` are
built to answer: given `checkpoint_interval_optimal(50.0, 0.0002)` (50 steps lost per checkpoint,
a 1-in-5,000 per-step failure rate), the optimal spacing is `sqrt(2*50/0.0002) = 707.1067811865476`
steps between checkpoints -- frequent enough that `recovery_cost_estimate` after a failure stays
cheap: replaying 300 steps at `1.2` cost units each plus a `45`-unit checkpoint load is
`recovery_cost_estimate(300.0, 1.2, 45.0) = 45 + 300*1.2 = 405.0` units, a small fraction of a
707-step interval.

**Both this module and `reliability` return a large finite sentinel instead of infinity on a
degenerate input.** `checkpoint_interval_optimal` returns `1e6` when the failure rate is `<= 0`,
and `reliability.mtbf` (below) returns `1e30` when the failure rate is `<= 0` -- the same idiom,
two different scales, both chosen so a caller doing arithmetic on the result never has to
special-case `inf` or `NaN`.

## `observability`: closed-form serving-fleet metrics, not a tracing library

| Function | What it does |
| --- | --- |
| `p99_latency_estimate(mean_latency, std_latency)` | `mean + 2.326 * std` -- a normal-distribution approximation of the 99th percentile. |
| `memory_pressure_score(used_bytes, total_bytes, fragmentation)` | `min(1, used/total + fragmentation*0.2)`, with `used/total` itself capped at `1.0` first. `1.0` if `total_bytes <= 0`. |
| `token_throughput_ema(current_ema, new_tokens, elapsed_ms, alpha)` | EMA of tokens/sec: `alpha * (new_tokens/elapsed_ms*1000) + (1-alpha) * current_ema`. Unchanged if `elapsed_ms <= 0`. |
| `cache_miss_rate(total_accesses, cache_misses)` | `cache_misses / total_accesses`. `0.0` if `total_accesses <= 0`. |
| `batch_queue_wait_percentile(mean_wait, std_wait, percentile)` | An exponential-tail quantile shape, `mean + (-log(1-percentile) * 1.2816) * std` -- **not** the same normal-quantile shape `p99_latency_estimate` uses (see below). `mean + 4*std` at `percentile >= 1.0`; `0.0` at `percentile <= 0.0`. |
| `gpu_utilization_rolling(current_util, new_sample, alpha)` | Plain EMA: `alpha*new_sample + (1-alpha)*current_util`. |
| `request_success_rate(successes, total_requests)` | `successes / total_requests`. Defaults to `1.0` (not `0.0`) when `total_requests <= 0` -- "no data" reads as healthy, not failing. |
| `model_drift_alert_score(psi_score, accuracy_drop, calibration_ece)` | `0.4*PSI + 0.4*accuracy_drop + 0.2*calibration_ece`; per the docstring, `> 0.5` is an alert threshold and `> 1.0` is critical (the function itself only returns the raw score). |
| `cost_per_token_rolling(current_cpt, new_cost, new_tokens, alpha)` | EMA of \$/token: `alpha*(new_cost/new_tokens) + (1-alpha)*current_cpt`. Unchanged if `new_tokens <= 0`. |
| `health_check_score(memory_pressure, gpu_util, error_rate, queue_depth_ratio)` | `1 - (0.3*memory_pressure + 0.4*error_rate + 0.3*queue_depth_ratio)`, floored at `0.0`. |

**`health_check_score` takes `gpu_util` and never uses it.** Reading the body directly: `issues`
is computed from `memory_pressure`, `error_rate`, and `queue_depth_ratio` only; `gpu_util` is
accepted as the function's second parameter and then never appears again. Two calls that differ
only in `gpu_util` return the identical score --
`health_check_score(0.7, 0.99, 0.5, 0.2)` and `health_check_score(0.7, 0.0, 0.5, 0.2)` both return
`1 - (0.3*0.7 + 0.4*0.5 + 0.3*0.2) = 0.53`. A caller passing a live GPU-utilization reading here is
not wrong to do so (the signature invites it), but that reading has no effect on the composite
score this function actually returns.

**`batch_queue_wait_percentile` does not share `p99_latency_estimate`'s normal-quantile shape,
despite both living in the same module and both being called "percentile" estimators.**
`p99_latency_estimate` is symmetric around the mean (`mean + z*std` for a fixed normal `z`).
`batch_queue_wait_percentile` instead scales `-log(1-percentile)` by the constant `1.2816` --
an exponential-tail shape appropriate for right-skewed queueing-wait distributions, not a
symmetric Gaussian one. At `percentile=0.5` this returns `mean + 0.8883*std`, already above the
mean at the median, and at `percentile=0.95` it returns `mean + 3.8393*std`
(`batch_queue_wait_percentile(40.0, 10.0, 0.95)["result"] == 78.39330479223594` for a 40ms mean,
10ms std queue) -- far past where a normal-quantile formula would place the 95th percentile
(`mean + 1.645*std = 56.45`). Treating the two functions' outputs as comparable "percentile of a
latency distribution" numbers would silently compare two different distributional assumptions.

## `logging.logger`: a structured JSON logger

The dotted contract name is `logging.logger`. Its only function reachable through
`runtime.execute` is the factory:

```python
state = runtime.execute("logging.logger", "get_logger", ["engine"])["result"]
```

`get_logger(name)` returns a `Logger` struct (`name: String`, `level: Int`) initialized at
`level=1` (INFO). The runtime marshals that struct the same way it marshals any struct return
elsewhere in this corpus -- `{"__algenta_struct": "Logger", "v": [name, level]}`, field order
matching the struct's declaration. The struct's real work, though, is in its bound methods
(`debug`, `info`, `warning`, `error`, `log`), and those are Mojo-only: they are not standalone
contract functions, so a caller reaching this module only through `runtime.execute` gets the
logger's *state*, not its logging side effect. The actual logging happens inside compiled Mojo
code that holds a `Logger` value directly, for example:

```mojo
var log = Logger("engine", LOG_INFO)
log.info("simulation_started", "runs=10000")
# {"level":"info","logger":"engine","msg":"simulation_started","extra":"runs=10000"}
```

That traced line comes straight from `log()`'s own string-concatenation body (`json_escape_string`
around each field, `"extra"` omitted entirely when empty) -- it is not paraphrased, it is what the
four `line +=` statements in `logger.mojo` produce for exactly this call, and it matches the
module's own docstring example verbatim.

**Level filtering is a plain integer comparison, not four separate code paths.** `debug`, `info`,
`warning`, and `error` are all one-line wrappers around `log(level, msg, extra)`, which returns
immediately if `level < self.level`. A `Logger("test", LOG_INFO)` (level `1`) that receives
`.debug("should_not_print")` (level `0`) emits nothing, confirmed directly in
`tests/mojo/test_wave8.mojo`; the same call against a `Logger("debug_test", LOG_DEBUG)` (level
`0`) prints normally.

## `reliability`: classical reliability engineering

| Function | What it does |
| --- | --- |
| `exponential_reliability(t, lambda_rate)` | `exp(-lambda_rate * t)` -- constant-hazard survival probability past time `t`. |
| `exponential_failure_rate(lambda_rate)` | Returns `lambda_rate` unchanged -- the constant hazard rate itself. |
| `weibull_reliability(t, beta, eta)` | `exp(-(t/eta)^beta)`. `1.0` at `t <= 0`; `0.0` if `eta <= 0`. |
| `weibull_failure_rate(t, beta, eta)` | `(beta/eta) * (t/eta)^(beta-1)` -- the Weibull hazard function. `0.0` if `t <= 0` or `eta <= 0`. |
| `mtbf(failure_rate)` | `1 / failure_rate`. `1e30` sentinel if `failure_rate <= 0`. |
| `availability(mtbf_val, mttr)` | `mtbf / (mtbf + mttr)`. `0.0` if the denominator is `<= 0`. |
| `series_reliability(reliabilities)` | `Π(R_i)` -- a series system fails if any one component fails. |
| `parallel_reliability(reliabilities)` | `1 - Π(1-R_i)` -- a parallel system fails only if every component fails. |
| `k_of_n_reliability(k, n, r)` | `Σ_{i=k}^{n} C(n,i) r^i (1-r)^{n-i}` -- binomial k-out-of-n system reliability at identical per-unit reliability `r`. |
| `bathtub_rate(t, beta_infant, lambda_useful, beta_wearout, eta_wearout, t_wearout)` | Sum of a decreasing Weibull(`beta_infant < 1`) infant-mortality term, a constant `lambda_useful` term, and (past `t_wearout`) an increasing Weibull(`beta_wearout > 1`) wearout term. |
| `mission_reliability(duration, failure_rate)` | `exp(-failure_rate * duration)` -- literally `exponential_reliability` under a mission-planning name; per the module's own docstring, "same as exponential but semantically for mission planning." |

Every number below is pinned in `tests/mojo/test_wave30.mojo` (not the auto-generated smoke
suite -- these are hand-written assertions with tolerances):

```python
runtime.execute("reliability", "series_reliability", [[0.99, 0.99, 0.99]])["result"]
# 0.970299 -- three components at 99% each, all must survive

runtime.execute("reliability", "parallel_reliability", [[0.9, 0.9]])["result"]
# 0.99 -- two 90%-reliable components backing each other up

runtime.execute("reliability", "k_of_n_reliability", [2, 3, 0.9])["result"]
# 0.972 -- 2-of-3 needed, strictly between the series (0.9^3=0.729) and parallel
# (1-0.1^3=0.999) extremes, matching C(3,2)*0.9^2*0.1 + C(3,3)*0.9^3 = 0.243+0.729

runtime.execute("reliability", "mission_reliability", [100.0, 0.001])["result"]
# 0.9048374180359595 -- exp(-0.1)
```

**`bathtub_rate` traces the three-phase curve its name promises.** At
`bathtub_rate(t, 0.5, 0.001, 2.0, 100.0, 500.0)` (infant shape `0.5` decreasing, useful-life rate
`0.001`, wearout shape `2.0`/scale `100`, wearout starting at `t_wearout=500`):

| `t` | infant term | useful term | wearout term | total |
| --- | --- | --- | --- | --- |
| 1.0 | 0.0223607 | 0.001 | 0.0 (before `t_wearout`) | 0.0233607 |
| 250.0 | 0.0014142 | 0.001 | 0.0 (before `t_wearout`) | 0.0024142 |
| 600.0 | 0.0009129 | 0.001 | 0.02 (past `t_wearout`) | 0.0219129 |

The rate is highest early (infant mortality dominates), dips in the middle (only the constant
useful-life term is active), and rises again once `t` crosses `t_wearout` -- exactly the shape
`test_wave30.mojo` checks (`rate_early > rate_mid` and `rate_late > rate_mid`); the exact values
above were traced independently from the formula in `reliability.mojo`, not read off the test.

**`reliability.weibull_reliability` evaluates a Weibull curve at parameters you already have;
`survival_analysis.parametric.weibull_mle` fits those same parameters from censored data.** This
is a real, source-confirmed relationship, not an assumed one: `survival_analysis/parametric.mojo`
imports `weibull_reliability` directly from `reliability` (`from reliability import
weibull_reliability`) and its own module docstring states it plainly -- *"the frozen
`reliability.mojo` EVALUATES a Weibull: `weibull_reliability(t, beta, eta)` and
`weibull_failure_rate(t, beta, eta)` both take the parameters as arguments. Nothing anywhere
[in `reliability.mojo`] estimates `beta` or `eta` from data."* `weibull_mle`'s fitted `shape` and
`scale` are meant to be handed straight to `reliability.weibull_reliability(t, shape, scale)` to
get a fitted survival curve -- same `(beta, eta)` parameterization, one module estimates it, the
other evaluates it. See [Survival analysis](survival-analysis.md) for the estimation side.

## `robustness`: perturbation and sensitivity analysis, an unrelated meaning of "robust"

| Function | What it does |
| --- | --- |
| `eval_test_func(x, func_id)` | Built-in target function for every other function in this module: `func_id=0` sum, `1` product, anything else a weighted sum `Σ (i+1)*x_i`. |
| `perturbation_test(values, perturbation)` | Adds an independent `Uniform(-perturbation, +perturbation)` draw to each value. |
| `sensitivity_one_at_a_time(baseline, index, delta, func_id)` | `(f(baseline with index += delta) - f(baseline)) / delta` -- one-at-a-time (OAT) finite-difference sensitivity. `0.0` if `\|delta\| < 1e-15`. |
| `morris_screening(n_inputs, func_id, n_trajectories, delta)` | Mean absolute elementary effect per input, averaged over `n_trajectories` random base points -- Morris screening. |
| `sobol_first_order_estimate(n_inputs, func_id, n_samples)` | A simplified Monte Carlo estimate of each input's first-order Sobol index, clamped to `[0, 1]`. |
| `input_range_sweep(baseline, index, lo, hi, n_points, func_id)` | Sweeps one input linearly from `lo` to `hi` and records `[input_value, output]` for each of `n_points`. |
| `tornado_data(baseline, deltas, func_id)` | For each input, `[output at baseline - delta, output at baseline + delta]` -- the paired low/high values a tornado chart bars. |
| `robustness_score(results)` | Coefficient of variation, `std / \|mean\|`. `0.0` for an empty list or a near-zero mean. |

**This module answers "how much does the output move if the inputs wiggle," which has nothing to
do with `reliability`'s "how likely is the system to keep working over time."** The two modules
share a doc page here because both get filed under general systems-engineering rigor, not because
they compute related quantities -- `robustness_score`'s coefficient of variation and
`reliability.availability`'s MTBF/(MTBF+MTTR) ratio take no arguments in common and answer
unrelated questions. (The word "robustness" also shows up in a third, unrelated sense elsewhere in
this corpus -- `causal_inference.sensitivity`'s "robustness values," a Cinelli-and-Hazlett-style
bound on unmeasured confounding -- which is a third meaning again, not this module.)

All of the following are pinned in `tests/mojo/test_wave55.mojo`:

```python
runtime.execute("robustness", "eval_test_func", [[1.0, 2.0, 3.0], 2])["result"]
# 14.0 -- weighted sum: 1*1 + 2*2 + 3*3

runtime.execute("robustness", "sensitivity_one_at_a_time", [[1.0, 2.0, 3.0], 0, 0.01, 0])["result"]
# 1.0 -- perturbing index 0 by 0.01 moves the sum (func_id=0) by exactly 0.01, so the
# finite-difference ratio is exactly 1.0 for this linear target function

runtime.execute("robustness", "tornado_data", [[1.0, 2.0, 3.0], [0.5, 0.5, 0.5], 0])["result"]
# [[5.5, 6.5], [5.5, 6.5], [5.5, 6.5]] -- input 0 low/high: sum(0.5,2,3)=5.5, sum(1.5,2,3)=6.5

runtime.execute("robustness", "robustness_score", [[10.0, 10.5, 9.5, 10.2, 9.8]])["result"]
# 0.03405877273185278 -- low coefficient of variation for a tightly clustered result set
runtime.execute("robustness", "robustness_score", [[5.0, 5.0, 5.0]])["result"]
# 0.0 -- zero variation for a constant result set
```

**`perturbation_test`, `morris_screening`, and `sobol_first_order_estimate` call
`random_float64()` directly, with no seed parameter anywhere in their signatures.** Every other
function in this entire five-module family -- every `fault_tolerance`, `observability`, `logger`,
and `reliability` function, plus `robustness`'s own `eval_test_func`, `sensitivity_one_at_a_time`,
`input_range_sweep`, `tornado_data`, and `robustness_score` -- is a pure function of its
arguments: same inputs, same output, always. These three are not. `tests/mojo/test_wave55.mojo`'s
own coverage for `morris_screening` and `sobol_first_order_estimate` only asserts bounds (effects
`> 0.0`, indices in `[0, 1]`), never a pinned value, because the value genuinely changes from run
to run. A caller wanting reproducible screening results needs to control for this outside the
function -- there is no seed argument to do it through the contract.

## Verification

`fault_tolerance`, `observability`, and `logging.logger` have only the auto-generated coverage
smoke tests (`mojo/tests/libs/test_fault_tolerance.mojo`, `test_observability.mojo`,
`test_logging_logger.mojo`): each calls every function once with literal `0.5` arguments (or
`get_logger("test")` for the logger) and checks only that a `Float64` result is finite, or that
the call didn't raise. None of that family's worked numbers above come from a pinned test --
they were hand-computed from the real formulas in `fault_tolerance.mojo` and `observability.mojo`
and independently verified (shown in this page's Python asides) before being presented as fact.
`reliability` and `robustness` additionally have real hand-verified numeric suites in
`tests/mojo/test_wave30.mojo` and `test_wave55.mojo` respectively, and every pinned number quoted
above for those two modules is copied directly from those tests' own assertions.

**Next:** see [Survival analysis](survival-analysis.md) for the censored-data estimation side of
the Weibull parameters `reliability.weibull_reliability` evaluates, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
