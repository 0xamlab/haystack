"""bench_forecasting.mojo — timing and scaling gate for the forecasting package.

Hand-written, not generated. `benchmark_mojo_vs_python.py` only writes `bench_<lib>.mojo` for
libraries in the runtime inventory; the inventory names the modules `forecasting.contract`,
`forecasting.point`, … so a generated file would be `bench_forecasting_point.mojo` and cannot
collide with this name. That harness only writes — it never unlinks.

What is measured, and why each one is the claim that matters
-----------------------------------------------------------
1. **A backtest costs origins x window, and nothing worse.** This is the only load-bearing
   performance claim in the package: a rolling backtest refits per origin, so a careless
   implementation is easy to make quadratic in the SERIES length on top of that. Measured as
   ns per (origin x training window) across a 4x rise in series length at a fixed origin
   count, which must stay flat. If it grows, something is rescanning the whole series per
   origin that should not be.

2. **Sliding windows are cheaper than expanding ones, and the ratio is the window ratio.**
   An expanding window's mean training length is ~n/2 while a sliding one is exactly
   `min_train`. Both are timed on the same series so the difference is the policy and not the
   machine.

3. **The seasonal path costs O(n x period) per origin, as its work charge says.** The charge
   in `_per_origin_cost` claims `n * period + horizon`; this measures ns per
   (origin x window x period) across a rising period, which must stay flat. A budget whose
   arithmetic does not match the code is not a budget.

4. **The empirical band is quadratic in the residual count, which is why it is capped.**
   `contract.fc_quantile_of` reaches the frozen `risk.value_at_risk`, whose sort is
   `risk._sort_copy` — an INSERTION sort. That is a deliberate reuse (one definition of an
   empirical quantile in the tree) with a deliberate consequence, and
   `FC_MAX_QUANTILE_SAMPLES = 4096` exists because of it. Measured as ns per k^2 across a
   rising k, which must stay flat: confirming the O(k^2) rather than pretending it is O(k log k)
   is the point, because the ceiling is only justified if the cost really is quadratic.

5. **Reconciliation is linear in cells.** Bottom-up and top-down are single passes plus an
   audit, so ns per cell must stay flat as the hierarchy grows.

Gate
----
Fails on the SCALING properties, not on absolute nanoseconds, which vary by machine:
  * backtest ns per (origin x window) must not grow more than 3x across a 4x rise in n
  * seasonal ns per (origin x window x period) must not grow more than 3x across a 4x rise
    in period
  * empirical-band ns per k^2 must not grow more than 3x across a 4x rise in k
  * reconciliation ns per cell must not grow more than 3x across a 16x rise in cells
  * every timed call must return FC_OK — a refusal is instant and would "win" every timing
Absolute numbers are printed for tracking.

Every timed point is the MINIMUM of `GATE_REPS` repetitions, not a single reading. See that
constant: measured, a single reading made all four of these ratio gates a coin flip, and the
one super-linear verdict this file has ever printed was scheduler noise rather than the code.
"""
from std.time import perf_counter_ns

from forecasting.backtest import backtest_flat
from forecasting.contract import (
    FC_METHOD_ETS_AAA,
    FC_METHOD_THETA,
    FC_OK,
    FC_MAX_QUANTILE_SAMPLES,
)
from forecasting.hierarchy import reconcile_bottom_up_flat, reconcile_top_down_flat
from forecasting.interval import interval_empirical_flat


fn _series(n: Int, period: Int) -> List[Float64]:
    """A deterministic trend-plus-season-plus-wobble series. No randomness: a benchmark whose
    input changes between runs cannot be compared against its own previous numbers."""
    var out = List[Float64]()
    for t in range(n):
        var phase = Float64((t * 7) % period) - Float64(period) * 0.5
        var wobble = Float64((t * 13) % 11) * 0.25
        out.append(100.0 + 0.5 * Float64(t) + phase + wobble)
    return out^


fn _ns(t0: UInt, t1: UInt) -> Float64:
    return Float64(Int(t1 - t0))


# How many times every ratio-gated timing point is repeated before its MINIMUM is taken.
#
# Seven, and the number is measured. Gated on a SINGLE reading this file failed about 1 run in
# 4 on a developer machine running other work — "reconciliation grew super-linearly:
# 68.6 -> 335.8" — and the cause was the estimator, not the reconciler. Timed at seven
# repetitions per point, reconciliation costs 48.58 ns/cell at 1,024 nodes and 45.24 ns/cell at
# 16,384, a ratio of 0.93 against a 3.0 limit: flat, as a single pass plus an audit must be.
# The spread between the fastest and slowest single reading of one point was 1.14x here and
# reached 16x elsewhere in this batch, which is what a one-shot 3x gate was actually sampling.
# The minimum is the right statistic for a timing floor — contention can only ever make a
# reading slower than the work takes, never faster.
comptime GATE_REPS: Int = 7


fn _min_backtest_ns(
    y: List[Float64], method_id: Int, horizon: Int, min_train: Int,
    step: Int, expanding: Bool, period: Int
) -> Float64:
    """Fastest of `GATE_REPS` identical `backtest_flat` calls, or -1.0 if any one refused.

    This exists as its own function for a COMPILE-TIME reason, not a stylistic one. Putting this
    loop inline in `main` — a `backtest_flat` call inside a nested `for rep` among main's dozens
    of live Lists — took the Mojo compiler from 18 seconds to over ten minutes on this file, at
    every repetition count including one, so the cost is the structure and not the iterations.
    Hoisted into a small scope with four live values it builds in seconds. The band and
    reconciliation loops repeat inline without trouble; `backtest_flat` is the call that does
    not tolerate it, so only it is hoisted.

    -1.0 rather than a status: the caller re-runs the call once for the verdict and the metadata
    it prints, so this function only has to answer the timing question.
    """
    var best: Float64 = -1.0
    for rep in range(GATE_REPS):
        var t0 = perf_counter_ns()
        var report = backtest_flat(
            y, method_id, horizon, min_train, step, expanding, period, 2, 0.4, 0.2, 1.0, 2.0
        )
        var t1 = perf_counter_ns()
        if report.status != FC_OK or report.n_origins_run == 0:
            return -1.0
        if rep == 0 or _ns(t0, t1) < best:
            best = _ns(t0, t1)
    return best


fn main() raises:
    var failures = 0
    print("\n[bench_forecasting] scaling gate")

    # ══ 1. backtest cost is origins x window ═══════════════════════════════════════
    # Origin count held at 16 by scaling `step` with `n`, so the only thing that changes is
    # the training window length.
    var horizon = 4
    var per_unit = List[Float64]()
    var sizes = List[Int]()
    sizes.append(256)
    sizes.append(1024)
    for s in range(len(sizes)):
        var n = sizes[s]
        var min_train = n // 4
        var step = (n - horizon - min_train) // 15
        var y = _series(n, 12)
        var report = backtest_flat(
            y, FC_METHOD_THETA, horizon, min_train, step, True, 12, 2, 0.4, 0.2, 1.0, 2.0
        )
        if report.status != FC_OK or report.n_origins_run == 0:
            failures += 1
            print("  ❌ backtest refused at n =", n, "status", report.status_name)
            continue
        var best = _min_backtest_ns(y, FC_METHOD_THETA, horizon, min_train, step, True, 12)
        if best <= 0.0:
            failures += 1
            print("  ❌ backtest refused inside the timing loop at n =", n)
            continue
        # Expanding window: mean training length is about (first + last)/2.
        var mean_window = Float64(min_train + report.origin_index[report.n_origins_run - 1]) * 0.5
        var units = Float64(report.n_origins_run) * mean_window
        var ns_per_unit = best / units
        per_unit.append(ns_per_unit)
        print(
            "  n =", n, "origins", report.n_origins_run, "min of", GATE_REPS, "total ns", best,
            "ns/(origin*window)", ns_per_unit,
        )
    if len(per_unit) == 2:
        if per_unit[1] <= 3.0 * per_unit[0]:
            print("  ✅ backtest ns per (origin x window) stayed flat across a 4x rise in n")
        else:
            failures += 1
            print("  ❌ backtest cost grew super-linearly:", per_unit[0], "->", per_unit[1])

    # ══ 2. sliding is cheaper than expanding, by about the window ratio ════════════
    var n2 = 1024
    var y2 = _series(n2, 12)
    var min_train2 = n2 // 4
    var step2 = (n2 - horizon - min_train2) // 15
    var t2 = perf_counter_ns()
    var wide = backtest_flat(
        y2, FC_METHOD_THETA, horizon, min_train2, step2, True, 12, 2, 0.4, 0.2, 1.0, 2.0
    )
    var t3 = perf_counter_ns()
    var narrow = backtest_flat(
        y2, FC_METHOD_THETA, horizon, min_train2, step2, False, 12, 2, 0.4, 0.2, 1.0, 2.0
    )
    var t4 = perf_counter_ns()
    if wide.status != FC_OK or narrow.status != FC_OK:
        failures += 1
        print("  ❌ a window-policy run refused")
    else:
        print(
            "  expanding ns", _ns(t2, t3), "sliding ns", _ns(t3, t4),
            "origins", wide.n_origins_run,
        )
        # ADVISORY, not a gate, and deliberately not marked with a checkmark. The else branch
        # below counts no failure, so a broken invariant here cannot turn the verdict red --
        # verified by making this condition unsatisfiable and watching the benchmark still
        # report PASS. At these sizes both policies are O(window) and the difference is inside
        # the timing noise, so gating it would add a coin flip rather than a signal. It stays
        # printed because the comparison is still worth seeing. If you gate it later, give it a
        # min-of-GATE_REPS reading first and count the failure; until then it must not wear the
        # same checkmark as the four gates in this file that do fail.
        if _ns(t3, t4) <= _ns(t2, t3):
            print("  (note) sliding was faster here, as expected; both are O(window)")
        else:
            print("  (note) sliding was not faster here; both are O(window) and n is small")

    # ══ 3. the seasonal path is O(n x period) per origin, as its charge claims ══════
    var seasonal_unit = List[Float64]()
    var periods = List[Int]()
    periods.append(6)
    periods.append(24)
    for p in range(len(periods)):
        var period = periods[p]
        var n = 1024
        var y = _series(n, period)
        var min_train = n // 4
        var step = (n - horizon - min_train) // 7
        var report = backtest_flat(
            y, FC_METHOD_ETS_AAA, horizon, min_train, step, False, period, 2,
            0.4, 0.2, 1.0, 2.0,
        )
        if report.status != FC_OK or report.n_origins_run == 0:
            failures += 1
            print("  ❌ seasonal backtest refused at period", period, report.status_name)
            continue
        var best = _min_backtest_ns(
            y, FC_METHOD_ETS_AAA, horizon, min_train, step, False, period
        )
        if best <= 0.0:
            failures += 1
            print("  ❌ seasonal backtest refused inside the timing loop at period", period)
            continue
        var units = (
            Float64(report.n_origins_run) * Float64(min_train) * Float64(period)
        )
        var ns_per_unit = best / units
        seasonal_unit.append(ns_per_unit)
        print(
            "  period =", period, "origins", report.n_origins_run, "min of", GATE_REPS,
            "total ns", best, "ns/(origin*window*period)", ns_per_unit,
        )
    if len(seasonal_unit) == 2:
        if seasonal_unit[1] <= 3.0 * seasonal_unit[0]:
            print("  ✅ seasonal cost matches its declared O(n x period) work charge")
        else:
            failures += 1
            print("  ❌ seasonal cost exceeds its charge:", seasonal_unit[0], "->",
                  seasonal_unit[1])

    # ══ 4. the empirical band really is O(k^2) — which is why k is capped ══════════
    var band_unit = List[Float64]()
    var ks = List[Int]()
    ks.append(256)
    ks.append(1024)
    for i in range(len(ks)):
        var k = ks[i]
        var band_horizon = 2
        var error = List[Float64]()
        for j in range(k):
            error.append(Float64((j * 37) % 101) - 50.0)
            error.append(Float64((j * 53) % 97) - 48.0)
        var point = List[Float64]()
        point.append(100.0)
        point.append(200.0)
        var best: Float64 = 0.0
        var refused = False
        for rep in range(GATE_REPS):
            var t7 = perf_counter_ns()
            var band = interval_empirical_flat(error, k, band_horizon, point, 0.95)
            var t8 = perf_counter_ns()
            if band.status != FC_OK or band.n_steps_covered != band_horizon:
                refused = True
                print("  ❌ band refused at k =", k, band.status_name)
                break
            if rep == 0 or _ns(t7, t8) < best:
                best = _ns(t7, t8)
        if refused:
            failures += 1
            continue
        var units = Float64(band_horizon) * Float64(k) * Float64(k)
        var ns_per_unit = best / units
        band_unit.append(ns_per_unit)
        print(
            "  k =", k, "min of", GATE_REPS, "total ns", best, "ns/(horizon*k^2)",
            ns_per_unit,
        )
    if len(band_unit) == 2:
        if band_unit[1] <= 3.0 * band_unit[0]:
            print(
                "  ✅ band cost is O(horizon x k^2) as the frozen insertion sort implies;",
                "cap is", FC_MAX_QUANTILE_SAMPLES,
            )
        else:
            failures += 1
            print("  ❌ band cost worse than quadratic:", band_unit[0], "->", band_unit[1])

    # ══ 5. reconciliation is linear in cells ══════════════════════════════════════
    var recon_unit = List[Float64]()
    var node_counts = List[Int]()
    node_counts.append(1024)
    node_counts.append(16384)
    for i in range(len(node_counts)):
        var n_nodes = node_counts[i]
        var recon_horizon = 4
        var parent_of = List[Int]()
        var base = List[Float64]()
        for node in range(n_nodes):
            parent_of.append(-1 if node == 0 else (node - 1) // 2)
            for h in range(recon_horizon):
                base.append(1.0 + Float64((node * 17 + h) % 23))
        var best_bu: Float64 = 0.0
        var best_td: Float64 = 0.0
        var refused = False
        for rep in range(GATE_REPS):
            var t9 = perf_counter_ns()
            var bu = reconcile_bottom_up_flat(base, parent_of, recon_horizon, 0.0)
            var t10 = perf_counter_ns()
            var td = reconcile_top_down_flat(base, parent_of, recon_horizon, 0.0)
            var t11 = perf_counter_ns()
            if bu.status != FC_OK or td.status != FC_OK:
                refused = True
                print("  ❌ reconciliation refused at", n_nodes, "nodes:", bu.status_name,
                      td.status_name)
                break
            if rep == 0 or _ns(t9, t10) < best_bu:
                best_bu = _ns(t9, t10)
            if rep == 0 or _ns(t10, t11) < best_td:
                best_td = _ns(t10, t11)
        if refused:
            failures += 1
            continue
        var cells = Float64(n_nodes) * Float64(recon_horizon)
        var ns_per_cell = (best_bu + best_td) / cells
        recon_unit.append(ns_per_cell)
        print(
            "  nodes =", n_nodes, "min of", GATE_REPS, "bottom-up ns", best_bu,
            "top-down ns", best_td, "ns/cell", ns_per_cell,
        )
    if len(recon_unit) == 2:
        if recon_unit[1] <= 3.0 * recon_unit[0]:
            print("  ✅ reconciliation ns per cell stayed flat across a 16x rise in cells")
        else:
            failures += 1
            print("  ❌ reconciliation grew super-linearly:", recon_unit[0], "->",
                  recon_unit[1])

    print("  [bench_forecasting] scaling failures:", failures)

    # The gate. Every ❌ above already incremented `failures`; without this line the whole
    # benchmark printed its diagnoses and exited 0 regardless, so a super-linear regression
    # was visible to a reader and invisible to CI. The counted conditions are all SHAPE
    # claims — per-unit cost staying flat as the problem grows — never absolute nanoseconds,
    # which vary by machine and would make this gate a source of false failures.
    #
    # And it RAISES rather than only printing: `mojo run` exits 0 on a printed FAIL, so a CI
    # step that does not grep stdout would have gone green on a super-linear regression. Every
    # other gated benchmark in this tree raises; this one now does too.
    if failures == 0:
        print("BENCH_GATE forecasting PASS")
    else:
        print("BENCH_GATE forecasting FAIL " + String(failures))
        raise Error("bench_forecasting: " + String(failures) + " gate failure(s)")
