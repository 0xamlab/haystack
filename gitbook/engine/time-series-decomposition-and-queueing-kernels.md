---
icon: hourglass-half
description: Closed-form M/M/1, M/M/c, and Erlang B/C queueing formulas, plus additive time-series decomposition (trend, seasonal, residual) and a lightweight STL-like iterator -- two unrelated formula libraries sharing this page.
---

# Time-series decomposition and queueing kernels

Two small, independent formula libraries closing out the engine's formula-kernel documentation.
`queueing` answers "how long will a queue make you wait": closed-form M/M/1, M/M/c, and Erlang
B/C formulas. `time_series_decompose` answers "what is the trend, the repeating seasonal
pattern, and the leftover noise in this series": a centered-moving-average trend, per-phase
seasonal averaging, and a small iterative (STL-like) refinement. Neither module imports the
other, and -- unlike most pairings on a bundled page -- both are quietly load-bearing elsewhere
in the tree: `discrete_event.queue_sim` calls five of `queueing`'s eleven functions as the exact
ground truth its seeded M/M/1/M/M/c simulator is checked against, and `forecasting.point` calls
three of `time_series_decompose`'s nine functions to build the seasonal indices behind
ETS(A,A,A) forecasting.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# M/M/1: arrival rate 4/unit, service rate 5/unit -- rho = 0.8
runtime.execute("queueing", "mm1_utilization", [4.0, 5.0])["result"]        # 0.8
runtime.execute("queueing", "mm1_avg_queue_length", [4.0, 5.0])["result"]   # 3.2  -- rho^2/(1-rho)
runtime.execute("queueing", "mm1_avg_wait_time", [4.0, 5.0])["result"]      # 0.8  -- rho/(mu-lambda)

# additive decomposition of a 20-point series with a linear trend and period-4 seasonality
data = [0.0, 1.5, 3.0, 4.5, 2.0, 3.5, 5.0, 6.5, 4.0, 5.5, 7.0, 8.5,
        6.0, 7.5, 9.0, 10.5, 8.0, 9.5, 11.0, 12.5]
trend, seasonal, resid = runtime.execute("time_series_decompose", "decompose_additive",
                                          [data, 4])["result"]
trend[10]     # 6.25
seasonal[10]  # 2.8
resid[10]     # -2.05  -- trend[10] + seasonal[10] + resid[10] == data[10] == 7.0, exactly
```

## The modules

| Module | What it does |
| --- | --- |
| `queueing` | Closed-form M/M/1 (utilization, queue length, wait time, system time, system size), M/M/c (Erlang C wait probability, average wait), Erlang B blocking probability, a plain factorial helper, and Little's Law in both directions. |
| `time_series_decompose` | Centered moving-average trend extraction, detrending, per-phase seasonal averaging (tiled back to the series length), residual computation, a full additive decomposition, seasonal/trend "strength" scores, autocorrelation-based period detection, and a small iterative (STL-like) refinement. |

## `queueing`: M/M/1, M/M/c, and Erlang B/C, and nothing else

| Function | What it does |
| --- | --- |
| `mm1_utilization(arrival_rate, service_rate)` | rho = lambda/mu; `0.0` if `service_rate <= 0`. |
| `mm1_avg_queue_length(arrival_rate, service_rate)` | Lq = rho^2/(1-rho); `1e18` (sentinel) if `rho >= 1`. |
| `mm1_avg_system_size(arrival_rate, service_rate)` | L = rho/(1-rho); same `1e18` sentinel. |
| `mm1_avg_wait_time(arrival_rate, service_rate)` | Wq = rho/(mu-lambda); `1e18` if `mu <= lambda`. |
| `mm1_avg_system_time(arrival_rate, service_rate)` | W = 1/(mu-lambda); same sentinel. |
| `mmc_erlang_c(arrival_rate, service_rate, servers)` | Erlang C: P(an arrival waits) in an M/M/c queue; `1.0` if the offered traffic `>= servers` (unstable). |
| `mmc_avg_wait_time(arrival_rate, service_rate, servers)` | Wq = C(c,A) / (c\*mu - lambda); `1e18` if the denominator isn't positive. |
| `erlang_b(traffic_intensity, servers)` | Erlang B blocking probability for an M/M/c/c loss system, via the exact recursion B(A,n) = A\*B(A,n-1)/(n + A\*B(A,n-1)). |
| `factorial(n)` | `n!` as a `Float64` (used internally by the Erlang formulas); `1.0` for `n <= 0`. |
| `littles_law_L(arrival_rate, avg_time)` | L = lambda \* W. |
| `littles_law_W(arrival_rate, avg_number)` | W = L / lambda; `0.0` if `lambda <= 0`. |

Every "unstable" branch returns a literal `1e18` rather than infinity or a refusal code -- this
module carries no status-code vocabulary of its own (no struct, no `*_status_name` lookup), so a
finite-but-enormous sentinel is the only way an overloaded queue distinguishes itself from a real
answer. A caller comparing a result against `1e18` directly, rather than checking `rho >= 1`
first, gets it right by coincidence rather than by design.

### Worked M/M/1 and M/M/c chain

`tests/mojo/test_wave21.mojo` pins the M/M/1 example at `lambda=4.0`, `mu=5.0` (rho = 0.8) used
above: `mm1_utilization = 0.8`, `mm1_avg_system_size = 4.0`, `mm1_avg_system_time = 1.0`,
`mm1_avg_wait_time = 0.8`, `mm1_avg_queue_length = 3.2`, and the same test checks Little's Law
holds across those numbers: `littles_law_L(4.0, mm1_avg_system_time(4.0, 5.0)) ==
mm1_avg_system_size(4.0, 5.0)` to `1e-10`.

Adding servers to that same `lambda=4.0`, `mu=5.0` load (hand-recomputed from the Erlang C
formula above; the test checks only the direction of the effect, not these magnitudes):

| Servers | Offered traffic A = lambda/mu | Erlang C, P(wait) | M/M/c avg wait Wq |
| --- | --- | --- | --- |
| 2 | 0.8 | 0.2286 | 0.0381 |
| 3 | 0.8 | 0.0520 | 0.00473 |

Going from 2 to 3 servers at the same load drops the probability of waiting at all by a factor
of roughly 4.4, and the average wait itself by a factor of roughly 8 -- `test_wave21.mojo`
asserts only `mmc_avg_wait_time(4,5,3) < mmc_avg_wait_time(4,5,2)`, but the magnitude is what
makes adding one server to an already-adequate pool disproportionately effective.

`erlang_b(1.0, 1) = 1/(1+1) = 0.5` (one server, exactly one erlang offered, half of everything
offered is blocked) is the other pinned value in the same test file, and `erlang_b(0.0, n)` is
`0.0` for any `n` -- no traffic offered, nothing blocked.

### Verification: this module is the closed form the discrete-event simulator is graded against

`queueing` is not merely analogous to a simulator's math -- it is a dependency of one.
`mojo/engine/discrete_event/queue_sim.mojo` imports `mm1_avg_queue_length`,
`mm1_avg_system_size`, `mm1_avg_system_time`, `mm1_avg_wait_time`, and `mmc_avg_wait_time`
directly (alongside `operations_research.utilization_factor` for rho) and calls them unchanged
to build `qs_closed_form_flat`'s exact reference values -- the numbers `discrete_event.replicate`
checks its confidence intervals against in
[Discrete-event simulation & queueing](discrete-event-simulation.md). The one thing `queue_sim`
adds on top is exactly the sentinel problem described above: because `queueing`'s M/M/1
functions return the finite `1e18` rather than refusing when `rho >= 1`, `qs_closed_form_flat`
checks stability itself *before* calling into `queueing`, and reports `exists = False` with
zeroed fields in the unstable region rather than ever letting the sentinel leak through as if it
were a real wait time.

`benchmarks/mojo_benchmarks/bench_queueing_validation.mojo` goes further and runs the
discrete-event engine's own simulator against these same formulas as a hard, gated check, not a
timing benchmark: 20 replications each at three M/M/1 utilizations and two M/M/c
configurations, plus the loss-system Erlang B recursion and the delay-probability Erlang C, all
checked as 95%-confidence-interval coverage against this module's output, with a
6-of-29-interval-miss failure threshold. That file also documents and gates a **second,
independent** `erlang_b` living in `telecommunications.mojo`
(`telecommunications.erlang_b(n, a)`) -- same bare function name, arguments in the opposite
order (`n` before `a`, versus this module's `traffic_intensity` before `servers`), and a
different recursion (forward on `B` here; inverse on `1/B` there). Neither calls the other, and
neither is called by `discrete_event`; a caller who reaches for `telecommunications.erlang_b`
expecting this module's argument order gets a plausible-looking number for the wrong quantity.
See [Business operations and real-estate kernels](business-operations-and-real-estate-kernels.md)
for that module.

### A second, non-identical queueing library sits one page over

[Business operations and real-estate kernels](business-operations-and-real-estate-kernels.md)'s
`operations_research` module also has `little_law_l`, `little_law_w`, `utilization_factor`,
`mm1_expected_queue_length`, and `mm1_expected_wait_time` -- the same five quantities as five of
this module's eleven functions, computing the same underlying formulas. The two libraries are not
the same code path: `operations_research.mm1_expected_queue_length(rho)` and
`mm1_expected_wait_time(rho, mu)` take the utilization `rho` directly as an already-computed
argument (with an explicit `0.0` degenerate-input guard for `rho` outside `[0, 1)`), while this
module's `mm1_avg_queue_length(arrival_rate, service_rate)` and
`mm1_avg_wait_time(arrival_rate, service_rate)` take the raw rates and compute `rho` internally
(with the `1e18` sentinel instead of a `0.0` guard). `operations_research` also stops at M/M/1 --
it has no M/M/c, no Erlang B or C, and no `mm1_avg_system_size`/`mm1_avg_system_time`
counterparts. `discrete_event.queue_sim` (previous section) draws from *both* libraries in the
same file: `queueing` for the M/M/1/M/M/c wait-time formulas, `operations_research` for
`utilization_factor`. Neither module imports the other.

### Distinct from `queue_ds`: a struct, not a formula

`queue_ds` (documented in
[Data structures and algorithms kernels](data-structures-and-algorithms-kernels.md)) is a
binary-heap-backed `PriorityQueue` struct and a fixed-capacity `CircularBuffer` struct that a
caller pushes and pops by value -- a data structure with mutable state, no arrival rate, no
service rate, and no queueing-theory formula anywhere in it. Nothing in `queue_ds.mojo` computes
a wait time or a utilization; nothing in `queueing.mojo` holds a struct or exposes push/pop. The
shared "queue" in the module name is the only thing the two have in common.

## `time_series_decompose`: trend, seasonal, residual, and a lightweight STL

| Function | What it does |
| --- | --- |
| `moving_average_trend(data, window)` | Centered moving average over `window` points; the first and last `window // 2` positions are zero-padded, not extrapolated. |
| `detrend(data, trend)` | `data - trend`, index by index. |
| `seasonal_component(detrended, period)` | Averages `detrended` by phase (`i mod period`) across the whole series, then tiles that per-phase average back out to the original length. |
| `residual(data, trend, seasonal)` | `data - trend - seasonal`. |
| `decompose_additive(data, period)` | Runs the four functions above in sequence and returns `[trend, seasonal, residual]`. |
| `seasonal_strength(resid, seasonal_plus_residual)` | `1 - var(resid) / var(seasonal + residual)`, clamped to `[0, 1]`. |
| `trend_strength(resid, trend_plus_residual)` | `1 - var(resid) / var(trend + residual)`, clamped to `[0, 1]`. |
| `detect_period(data, max_period)` | The lag in `[2, max_period]` with the highest raw autocorrelation; `1` if the series is too short, `max_period < 2`, or the series has ~zero variance. |
| `stl_like(data, period, n_iter=2)` | Iterates `moving_average_trend` -> `detrend` -> `seasonal_component` `n_iter` times, deseasonalizing before each trend re-fit; returns `[trend, seasonal, residual]`. Refuses (returns an empty list) if `period <= 0` or `period > len(data)`. |

### The reconstruction identity is algebra, not a correctness proof

`decompose_additive`'s three outputs always satisfy `trend[i] + seasonal[i] + residual[i] ==
data[i]` exactly, at every index -- not because the decomposition is a good fit, but because
`residual` is *defined* as `data - trend - seasonal`. `tests/mojo/test_wave55.mojo` checks this
identity on a synthetic 20-point series (linear trend + period-4 seasonality, `data[i] = 0.5*i +
(i mod 4)`) at interior indices `4..15`; the hand-recomputed values above (`trend[10] = 6.25`,
`seasonal[10] = 2.8`, `resid[10] = -2.05`, summing to `data[10] = 7.0`) confirm it, and the
identity in fact holds at *every* index of that series, not only the interior ones -- what
breaks at the edges is not the sum, but what `seasonal` actually estimates there, next.

### Edge-padding contaminates the seasonal estimate on a trending series -- a real, documented gap

`moving_average_trend` zero-pads the first and last `window // 2` positions rather than
extrapolating, so at those positions `detrend` returns the **raw observation**, not a detrended
one (`trend = 0` there). `seasonal_component` then averages that raw, non-detrended value into
whichever phase owns that position -- and on a series with a real trend, the raw observation is
large precisely because time has advanced, not because that phase is seasonally high. This is
not hypothetical: in the worked 20-point example above, position 18 (phase 2, since `18 mod 4 =
2`) is a zero-padded edge, so `detrended[18] = data[18] = 11.0` flows straight into phase 2's
average alongside three genuinely detrended values near `0.75` from positions 2, 6, 10, 14 --
`season_avg = [-1.0, 0.1, 2.8, 3.9]`, a spread of `4.9`, when the underlying seasonal pattern
(recoverable from the four interior-only phase values `-1.25, -0.25, 0.75, 1.75`) has a spread of
exactly `3.0`.

`mojo/engine/forecasting/point.mojo`'s own docstring names this defect directly and reports the
numbers it produced on its own 12-point trending test case (seasonal indices `[5/3, 1/3, 28/3,
6]` against a true `s + 1`, and a resulting one-step forecast of `17` against a true `25`) --
which is exactly why `forecasting.point` does not call `decompose_additive`, and does not feed
the full-length `moving_average_trend`/`detrend` output straight into `seasonal_component`: it
slices to the interior `[period // 2, n - period // 2)` first, where the trend is real, and
rotates the phase indices to compensate afterward. **A caller using `decompose_additive` or
`stl_like` directly on a trending series should expect the same contamination** unless it
performs that same interior-slice-and-rotate step itself; nothing in `time_series_decompose`
does this internally.

### This module is the frozen kernel underneath `forecasting.point`'s seasonal adjustment

This is not an analogy -- `mojo/engine/forecasting/point.mojo` imports `detrend`,
`moving_average_trend`, and `seasonal_component` from this module by name and calls them
unchanged (per its own frozen-kernel table) to build `_seasonal_indices`, which backs both
`ets_aaa_forecast` and the standalone `deseasonalise_flat`. See
[Forecasting and backtesting](forecasting.md) for the forecasting-side interface; this page is
where those three functions themselves live.

### Distinct from `arima`/`timeseries_stats`: decomposition, not model fitting

[AR/MA estimation (ARIMA building blocks)](ml-arima.md)'s `arima` module fits AR(p)/MA(q)
*coefficients* (Yule-Walker, innovations algorithm, CSS log-likelihood), and its sibling
`timeseries_stats` computes ACF/PACF diagnostics and exponential/Holt smoothing -- neither one
extracts a trend-plus-seasonal-plus-residual split, and `time_series_decompose` fits no
coefficients and computes no likelihood. The two families are complementary rather than
overlapping: a pipeline might run `seasonal_strength` here to decide whether a series needs a
seasonal difference before handing it to `arima`, but neither module calls the other, and
grepping either's source for the other's function names turns up nothing.

### `detect_period`: real behavior, real test

`tests/mojo/test_wave55.mojo` builds 50 points of `sin(2*pi*i/5)` (a pure period-5 sine, no
noise) and checks `detect_period(data, 20) == 5` exactly -- the function scans lags 2 through
`max_period` (clamped to `len(data) - 1` if `max_period` would run off the end) and returns
whichever lag has the highest raw autocorrelation, with no normalization and no
multiple-comparison correction. A single sharp period on a low-noise series is the case it is
built and tested for; periods below 2 or a `max_period` below 2 fall back to `1` (no
periodicity) unconditionally.

### `stl_like` guards a real crash, not just a style choice

The `period > len(data)` refusal at the top of `stl_like` carries an explicit source comment:
without it, the second iteration would subscript an empty seasonal list and abort the whole
worker process -- not raise a catchable error -- rather than return cleanly.
`tests/mojo/test_wave55.mojo`'s 24-point/period-6/`n_iter=3` case exercises the normal path,
confirming all three outputs are 24 long and reconstruct the input exactly at interior indices
`6..17` -- the same tautological identity `decompose_additive` has.

## Verification

Both modules have real, hand-written test coverage beyond the auto-generated smoke tests
(`mojo/tests/libs/test_queueing.mojo` and `test_time_series_decompose.mojo`, which only check
finiteness/non-crash on one arbitrary input per function): `tests/mojo/test_wave21.mojo`
(`queueing`, the M/M/1 chain and Little's-Law cross-check above) and `tests/mojo/test_wave55.mojo`
(`time_series_decompose`, covering every function's shape, values, and the reconstruction
identity). `queueing` additionally has the closed-form-vs-simulator gate in
`bench_queueing_validation.mojo` described above, which is a harder check than either test file
alone: it has been deliberately broken twice against mutated copies of the discrete-event engine
(a stream-collision bug and a missing Lindley-recursion clamp) and confirmed to catch both.
Every worked number on this page not directly quoted from a pinned test (the M/M/c wait-time
table, the contaminated seasonal-index numbers) was independently recomputed here from the
formulas in `mojo/engine/queueing.mojo` and `mojo/engine/time_series_decompose.mojo`.

**Next:** see [Discrete-event simulation & queueing](discrete-event-simulation.md) for the
simulator these formulas validate, [Forecasting and backtesting](forecasting.md) for how
`time_series_decompose`'s seasonal machinery feeds ETS(A,A,A), or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
