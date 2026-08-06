"""bench_evaluation.mojo — the gate behind `evaluation`'s cost and refusal claims.

Hand-written, not generated. `benchmark_mojo_vs_python.py` writes `bench_<lib>.mojo` per
runtime-inventory library, and `evaluation` is a package of five modules rather than one
library, so no generated file claims this name.

WHAT IS GATED, AND WHY EACH ONE IS A CLAIM SOMETHING DEPENDS ON
===============================================================
Every gate below is on SHAPE — cost per unit of work as the problem grows — never on absolute
nanoseconds, which are machine- and JIT-dependent. The absolute numbers are printed so a
regression is visible, and nothing fails because a laptop was busy.

Every timed region is the MINIMUM of `BENCH_REPS` repetitions, not a single reading. Gating on
a shape ratio built from one timing per point is not a shape gate: measured here with single
readings, the same n = 16000 bootstrap gave 45.6 ns/draw on one run and 205.6 on the next, and
the n-sweep gate failed about one run in three on scheduler noise alone. See `BENCH_REPS`.

1. **`evaluate_flat` is linear in n.** Its declared complexity is `O(n log n + h)` and the
   equal-width path does no sorting, so cost per SAMPLE must be flat as n grows 64x. If it is
   not, some part of the driver is quadratic and a valid request will burn minutes at a size
   the length ceiling permits. Gate: per-sample cost varies by less than 3x across the sweep.

2. **The quantile path pays a sort, and only a sort.** Equal-count binning sorts and then binary
   searches, so cost per sample grows like `log n` — it must NOT grow like n. Gate: per-sample
   cost grows by less than 6x while n grows 64x. A linear-per-sample growth would show up here
   as ~64x.

3. **Bins are charged separately from samples.** Cost per BIN must be flat as h grows 64x at
   fixed n. This is the `O(n * h)` trap: a per-sample linear scan over the bin edges instead of
   a binary search would make the real cost `n * h` while every declared cost in the package
   says `n + h`. Measured elsewhere in this tree as 0.49s against 23.89s at an identical
   declared cost.

4. **The bootstrap costs `n_boot * n` and the budget charges `n_boot * n`.** Cost per DRAW must
   be flat as `n_boot` grows at fixed n AND as n grows at fixed `n_boot`. That is the
   measurement that makes `eval_resample_work_fits` an honest budget rather than a number
   somebody liked: if per-draw cost rose with either factor, the budget would be charging one
   factor of a product (rule 1c).

5. **The bootstrap ALSO costs `n_boot * h`, and the budget charges that too.** Gate 4 sweeps
   `n_boot` and `n` on a metric that never bins, so it is structurally blind to the bin factor.
   This gate holds `n_boot` and `n` fixed, sweeps `h` 4096x on `EVAL_METRIC_ECE` — which
   rebuilds the whole partition inside every replicate — and reads the DECLARED cost back out
   of `eval_resample_work_fits` itself by binary search over its own predicate, rather than
   restating the cost model here where it could agree with a wrong one. Nanoseconds per
   declared unit must not RISE as h grows. Measured against the version that charged `n_bins`
   only for its sign: 9.2 ms at h = 1 against 1231.9 ms at h = 4096 for one declared cost of
   4096 units — a 133x undercharge that gate 4 cannot see.

6. **The work budget refuses BEFORE doing the work.** A request of 2^13 samples by 2^20
   replicates is inside every individual ceiling and is 2^33 draws. It must be refused in
   validation time — measurably faster than a legal 40-replicate bootstrap on the same data.
   A budget that is checked after the loop is not a budget.

7. **The gates fail.** Both a Brier regression and a PSI drift case are run and asserted to
   produce a REJECTION, and the PSI incompleteness case is asserted to be UNDECIDED at a
   threshold its lower bound cannot reach. A gate never demonstrated failing is decoration,
   and a benchmark is the second place (after the test suite) where that has to be shown.

8. **No refusal costs the worker its life.** The last section fires every refusal the package
   has at the drivers, including counts far past the end of every list. Reading past a `List`
   end is an uncatchable abort, so this section reaching its own print IS the assertion.

A NOTE ON `alpha` IN THE COST SWEEPS. A percentile interval needs `n_boot * alpha >= 2` — 40
replicates at the usual alpha = 0.05 — and `bootstrap_metric_ci_flat` refuses below that
rather than returning an interval too narrow to mean anything. The sweeps below that need a
SMALL replicate count to keep a cost measurement quick therefore pass `alpha = 0.5`, the
widest interval whose tails 4 replicates can resolve. Nothing statistical is being claimed in
those sections; they measure the shape of the cost.

Running it, from `mojo_env/`:

    pixi run mojo run -I../mojo/engine ../benchmarks/mojo_benchmarks/bench_evaluation.mojo
"""
from std.math import abs as fabs
from std.time import perf_counter_ns

from determinism.counter_rng import rng_uniform

from evaluation.binning import eval_bins_build
from evaluation.contract import (
    EVAL_BIN_EQUAL_COUNT,
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_ERR_PSI_INCOMPLETE,
    EVAL_ERR_WORK_BUDGET,
    EVAL_MAX_RESAMPLES,
    EVAL_MAX_RESAMPLE_WORK,
    EVAL_METRIC_BRIER,
    EVAL_METRIC_ECE,
    EVAL_OK,
    eval_resample_work_fits,
    eval_status_name,
)
from evaluation.gates import (
    metric_gate,
    metric_regression_gate_flat,
    psi_drift_gate_flat,
)
from evaluation.resample import bootstrap_metric_ci_flat
from evaluation.scores import (
    calibration_error_flat,
    evaluate_flat,
    log_loss_flat,
    metric_value_flat,
    reliability_diagram_flat,
)

comptime BENCH_STREAM: UInt64 = 4242
"""A fixed Philox stream for the synthetic data, so every printed number below comes from the
same dataset on every machine. `random_float64` would make the benchmark unreproducible, which
is the property a benchmark exists to have."""


comptime BENCH_REPS: Int = 7
"""How many times each measured region is repeated; the MINIMUM is the reading.

A single timing is not a measurement on a shared machine. Measured here before this existed:
the same `bootstrap_metric_ci_flat` call at n = 16000 read 45.6 ns/draw on one run and 205.6
on the next, and the n-sweep shape gate — which is correct in what it gates — failed on
roughly one run in three purely from that. A shape gate that flips on scheduler noise is not a
gate, it is a coin flip, and a benchmark that reds a build at random gets disabled.

The minimum is the right estimator rather than the mean or the median: interference from
another process, a page fault or a migration can only ever ADD time to a region, never remove
it, so the smallest of several readings is the closest available estimate of the work the
kernel actually did. The mean would carry every outlier into the ratio the gate reads.
Repetitions do not weaken the gate: an O(n*h) defect is present in all seven."""


def per_unit_ns(elapsed: UInt, units: Int) -> Float64:
    """Nanoseconds per unit of work. `perf_counter_ns` yields UInt, so it converts here."""
    if units <= 0:
        return 0.0
    return Float64(Int(elapsed)) / Float64(units)


def min_ns(a: UInt, b: UInt) -> UInt:
    """The smaller of two elapsed spans. See `BENCH_REPS` for why the minimum."""
    return a if a < b else b


def ratio(a: Float64, b: Float64) -> Float64:
    """`max/min` of two positive costs; 0.0 when either is unmeasurable."""
    if a <= 0.0 or b <= 0.0:
        return 0.0
    return a / b if a > b else b / a


def declared_replicate_cost(n: Int, n_bins: Int) -> Int:
    """What `eval_resample_work_fits` charges for ONE equal-width ECE replicate.

    Recovered from the predicate rather than restated: the largest `n_boot` it accepts is
    `EVAL_MAX_RESAMPLE_WORK / per_replicate`, found here by binary search over the predicate
    itself, so `EVAL_MAX_RESAMPLE_WORK / that` is the charge. Writing the cost model into this
    benchmark instead would let a wrong model in the kernel be checked against a copy of
    itself — which is exactly how the missing `n_bins` factor survived a benchmark that swept
    `n_boot` and `n`.

    The search is over `[0, EVAL_MAX_RESAMPLE_WORK]` and halves every step, so it terminates
    in at most 33 iterations; the predicate is monotone decreasing in `n_boot`, which is what
    makes a binary search valid on it.
    """
    var lo = 0
    var hi = EVAL_MAX_RESAMPLE_WORK
    while lo < hi:
        var mid = lo + (hi - lo + 1) // 2
        if eval_resample_work_fits(
            mid, n, n_bins, EVAL_METRIC_ECE, EVAL_BIN_EQUAL_WIDTH
        ):
            lo = mid
        else:
            hi = mid - 1
    if lo <= 0:
        return 0
    return EVAL_MAX_RESAMPLE_WORK // lo


def synth_probs(n: Int, seed: UInt64) -> List[Float64]:
    """`n` reproducible predictions in [0, 1] from the frozen keyed Philox kernel."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(rng_uniform(seed, 0, 0, 0, 0, BENCH_STREAM, UInt64(i)))
    return out^


def synth_labels(probs: List[Float64], n: Int, seed: UInt64) -> List[Float64]:
    """Labels drawn at each prediction's own rate, so the data is genuinely calibrated-ish.

    A label that is a deterministic function of the prediction would make every bin perfectly
    calibrated and the ECE identically zero, which would exercise the arithmetic without
    exercising the branches that only occupied, imperfect bins reach.
    """
    var out = List[Float64](capacity=n)
    for i in range(n):
        var u = rng_uniform(seed, 0, 0, 0, 0, BENCH_STREAM + 1, UInt64(i))
        out.append(1.0 if u < probs[i] else 0.0)
    return out^


def main() raises:
    var failures = 0
    print("bench_evaluation — shape gates over the evaluation drivers")
    print("")

    # ── 1. evaluate_flat is linear in n (equal width) ─────────────────────────
    print("[1] evaluate_flat, equal-width h=20: ns per sample as n grows 64x")
    var sizes = List[Int]()
    sizes.append(2000)
    sizes.append(8000)
    sizes.append(32000)
    sizes.append(128000)
    var ew_cost = List[Float64]()
    var checksum = 0.0
    for s in range(len(sizes)):
        var n = sizes[s]
        var p = synth_probs(n, 20260731)
        var y = synth_labels(p, n, 20260731)
        # One warm-up call, so the first size does not pay the JIT for the whole sweep.
        var warm = evaluate_flat(p, y, n, 20, EVAL_BIN_EQUAL_WIDTH)
        checksum += warm.brier
        var rep = warm.copy()
        var best: UInt = 0
        for r in range(BENCH_REPS):
            var t0 = perf_counter_ns()
            rep = evaluate_flat(p, y, n, 20, EVAL_BIN_EQUAL_WIDTH)
            var t1 = perf_counter_ns()
            checksum += rep.brier
            best = (t1 - t0) if r == 0 else min_ns(best, t1 - t0)
        var cost = per_unit_ns(best, n)
        ew_cost.append(cost)
        print("    n =", n, " ns/sample", cost, " brier", rep.brier, " ece", rep.ece,
              " occupied", rep.bins_occupied, "/20")
        if rep.status != EVAL_OK:
            failures += 1
            print("      ❌ refused:", eval_status_name(rep.status))
    var ew_lo = ew_cost[0]
    var ew_hi = ew_cost[0]
    for s in range(len(ew_cost)):
        if ew_cost[s] < ew_lo:
            ew_lo = ew_cost[s]
        if ew_cost[s] > ew_hi:
            ew_hi = ew_cost[s]
    var ew_spread = ratio(ew_hi, ew_lo)
    print("    per-sample spread over a 64x size range:", ew_spread, "x  (gate: < 3.0)")
    if ew_spread >= 3.0 or ew_spread <= 0.0:
        failures += 1
        print("    ❌ per-sample cost is not flat — something in the driver is superlinear")
    else:
        print("    ✅ per-sample cost is flat, so O(n) is the real cost and not just the claim")
    print("")

    # ── 2. the quantile path pays log n, not n ───────────────────────────────
    print("[2] evaluate_flat, equal-COUNT h=20: ns per sample (a sort per call)")
    var ec_cost = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s]
        var p = synth_probs(n, 20260731)
        var y = synth_labels(p, n, 20260731)
        var warm = evaluate_flat(p, y, n, 20, EVAL_BIN_EQUAL_COUNT)
        checksum += warm.brier
        var rep = warm.copy()
        var best: UInt = 0
        for r in range(BENCH_REPS):
            var t0 = perf_counter_ns()
            rep = evaluate_flat(p, y, n, 20, EVAL_BIN_EQUAL_COUNT)
            var t1 = perf_counter_ns()
            checksum += rep.brier
            best = (t1 - t0) if r == 0 else min_ns(best, t1 - t0)
        var cost = per_unit_ns(best, n)
        ec_cost.append(cost)
        print("    n =", n, " ns/sample", cost, " ece", rep.ece, " occupied",
              rep.bins_occupied, "/20")
        if rep.status != EVAL_OK:
            failures += 1
            print("      ❌ refused:", eval_status_name(rep.status))
    var ec_growth = ratio(ec_cost[len(ec_cost) - 1], ec_cost[0])
    print("    per-sample growth over a 64x size range:", ec_growth, "x  (gate: < 6.0)")
    print("    for reference, a linear-per-sample defect would show ~64x here")
    if ec_growth >= 6.0 or ec_growth <= 0.0:
        failures += 1
        print("    ❌ the quantile path grows faster than its declared O(n log n)")
    else:
        print("    ✅ the quantile path grows like log n; the sort is the only extra cost")
    # Equal-count is expected to be SLOWER than equal-width. Printed rather than hidden.
    print("    equal-count / equal-width at n =", sizes[len(sizes) - 1], ":",
          ratio(ec_cost[len(ec_cost) - 1], ew_cost[len(ew_cost) - 1]), "x")
    print("")

    # ── 3. bins are charged per bin, not per sample x bin ────────────────────
    print("[3] calibration_error_flat at n = 20000: ns per BIN as h grows 64x")
    var bin_counts = List[Int]()
    bin_counts.append(8)
    bin_counts.append(32)
    bin_counts.append(128)
    bin_counts.append(512)
    var bin_n = 20000
    var bp = synth_probs(bin_n, 20260731)
    var by = synth_labels(bp, bin_n, 20260731)
    var bin_total = List[Float64]()
    for t in range(len(bin_counts)):
        var h = bin_counts[t]
        var warm = calibration_error_flat(bp, by, bin_n, h, EVAL_BIN_EQUAL_WIDTH)
        checksum += warm.ece
        var ce = warm.copy()
        var best: UInt = 0
        for r in range(BENCH_REPS):
            var t0 = perf_counter_ns()
            ce = calibration_error_flat(bp, by, bin_n, h, EVAL_BIN_EQUAL_WIDTH)
            var t1 = perf_counter_ns()
            checksum += ce.ece
            best = (t1 - t0) if r == 0 else min_ns(best, t1 - t0)
        var total = Float64(Int(best))
        bin_total.append(total)
        print("    h =", h, " total ns", total, " ns/sample", total / Float64(bin_n),
              " ece", ce.ece, " occupied", ce.bins_occupied, "/", h)
        if ce.status != EVAL_OK:
            failures += 1
            print("      ❌ refused:", eval_status_name(ce.status))
    # If the driver were O(n * h), 64x the bins would be ~64x the total time. The gate is a
    # loose 8x, which is far below 64x and far above the noise of a nearly-constant cost.
    var bin_growth = ratio(bin_total[len(bin_total) - 1], bin_total[0])
    print("    total-time growth for 64x the bins:", bin_growth, "x  (gate: < 8.0)")
    print("    an O(n*h) per-sample scan over the edges would show ~64x here")
    if bin_growth >= 8.0 or bin_growth <= 0.0:
        failures += 1
        print("    ❌ bins are being charged per sample — the binary search is not being used")
    else:
        print("    ✅ h is charged additively, so O(n + h) is the real cost")
    print("")

    # ── 4. the bootstrap costs n_boot * n, in both directions ────────────────
    print("[4] bootstrap_metric_ci_flat: ns per DRAW, sweeping each factor separately")
    var boot_n = 4000
    var sp = synth_probs(boot_n, 20260731)
    var sy = synth_labels(sp, boot_n, 20260731)
    var boot_counts = List[Int]()
    boot_counts.append(8)
    boot_counts.append(16)
    boot_counts.append(32)
    boot_counts.append(64)
    var draw_cost_b = List[Float64]()
    for t in range(len(boot_counts)):
        var nb = boot_counts[t]
        var ci = bootstrap_metric_ci_flat(
            sp, sy, boot_n, EVAL_METRIC_BRIER, 20, EVAL_BIN_EQUAL_WIDTH, nb, 0.5, 7
        )
        checksum += ci.point
        var best: UInt = 0
        for r in range(BENCH_REPS):
            var t0 = perf_counter_ns()
            ci = bootstrap_metric_ci_flat(
                sp, sy, boot_n, EVAL_METRIC_BRIER, 20, EVAL_BIN_EQUAL_WIDTH, nb, 0.5, 7
            )
            var t1 = perf_counter_ns()
            checksum += ci.point
            best = (t1 - t0) if r == 0 else min_ns(best, t1 - t0)
        var cost = per_unit_ns(best, nb * boot_n)
        draw_cost_b.append(cost)
        print("    n_boot =", nb, " ns/draw", cost, " point", ci.point,
              " [", ci.lo, ",", ci.hi, "]  distinct", ci.distinct_replicates, "/", nb)
        if ci.status != EVAL_OK:
            failures += 1
            print("      ❌ refused:", eval_status_name(ci.status))
        if ci.distinct_replicates <= 1 and nb > 1:
            failures += 1
            print("      ❌ the replicate distribution collapsed — the seed is not reaching")
            print("         every draw, which is the property the whole module rests on")
    var boot_b_spread = ratio(draw_cost_b[len(draw_cost_b) - 1], draw_cost_b[0])
    print("    per-draw spread over an 8x replicate range:", boot_b_spread,
          "x  (gate: < 3.0)")
    if boot_b_spread >= 3.0 or boot_b_spread <= 0.0:
        failures += 1
        print("    ❌ per-draw cost depends on n_boot, so charging n_boot * n is wrong")
    else:
        print("    ✅ per-draw cost is flat in n_boot")

    var boot_sizes = List[Int]()
    boot_sizes.append(1000)
    boot_sizes.append(4000)
    boot_sizes.append(16000)
    var draw_cost_n = List[Float64]()
    for s in range(len(boot_sizes)):
        var n = boot_sizes[s]
        var p = synth_probs(n, 20260731)
        var y = synth_labels(p, n, 20260731)
        var ci = bootstrap_metric_ci_flat(
            p, y, n, EVAL_METRIC_BRIER, 20, EVAL_BIN_EQUAL_WIDTH, 16, 0.5, 7
        )
        checksum += ci.point
        var best: UInt = 0
        for r in range(BENCH_REPS):
            var t0 = perf_counter_ns()
            ci = bootstrap_metric_ci_flat(
                p, y, n, EVAL_METRIC_BRIER, 20, EVAL_BIN_EQUAL_WIDTH, 16, 0.5, 7
            )
            var t1 = perf_counter_ns()
            checksum += ci.point
            best = (t1 - t0) if r == 0 else min_ns(best, t1 - t0)
        var cost = per_unit_ns(best, 16 * n)
        draw_cost_n.append(cost)
        print("    n =", n, " ns/draw", cost, " point", ci.point)
        if ci.status != EVAL_OK:
            failures += 1
            print("      ❌ refused:", eval_status_name(ci.status))
    var boot_n_spread = ratio(draw_cost_n[len(draw_cost_n) - 1], draw_cost_n[0])
    print("    per-draw spread over a 16x sample range:", boot_n_spread, "x  (gate: < 3.0)")
    if boot_n_spread >= 3.0 or boot_n_spread <= 0.0:
        failures += 1
        print("    ❌ per-draw cost depends on n, so charging n_boot * n is wrong")
    else:
        print("    ✅ per-draw cost is flat in n; n_boot * n is the honest charge")
    print("")

    # ── 5. the declared cost tracks the work as the BIN COUNT grows ──────────
    print("[5] bootstrap ECE at n=1, n_boot=256: ns per DECLARED unit as h grows 4096x")
    var decl_p = List[Float64]()
    decl_p.append(0.5)
    var decl_y = List[Float64]()
    decl_y.append(1.0)
    var decl_hs = List[Int]()
    decl_hs.append(1)
    decl_hs.append(64)
    decl_hs.append(1024)
    decl_hs.append(4096)
    var decl_nboot = 256
    var decl_cost = List[Float64]()
    for t in range(len(decl_hs)):
        var h = decl_hs[t]
        # The declared cost is read OUT of the budget, not restated here: the largest
        # `n_boot` the predicate accepts is `ceiling / per_replicate`, so
        # `ceiling / that` recovers what the budget thinks one replicate costs. A cost
        # model written into this benchmark could agree with a wrong one in the kernel.
        var charged = declared_replicate_cost(1, h)
        var declared = decl_nboot * charged
        var warm = bootstrap_metric_ci_flat(
            decl_p, decl_y, 1, EVAL_METRIC_ECE, h, EVAL_BIN_EQUAL_WIDTH,
            decl_nboot, 0.5, 7,
        )
        checksum += warm.point
        var ci = warm.copy()
        var best: UInt = 0
        for r in range(BENCH_REPS):
            var t0 = perf_counter_ns()
            ci = bootstrap_metric_ci_flat(
                decl_p, decl_y, 1, EVAL_METRIC_ECE, h, EVAL_BIN_EQUAL_WIDTH,
                decl_nboot, 0.5, 7,
            )
            var t1 = perf_counter_ns()
            checksum += ci.point
            best = (t1 - t0) if r == 0 else min_ns(best, t1 - t0)
        var cost = per_unit_ns(best, declared)
        decl_cost.append(cost)
        print("    h =", h, " budget charges", charged, "per replicate, declared", declared,
              " total ms", Float64(Int(best)) / 1.0e6, " ns/declared unit", cost)
        if ci.status != EVAL_OK:
            failures += 1
            print("      ❌ refused:", eval_status_name(ci.status))
        if charged <= 1:
            failures += 1
            print("      ❌ the budget charges", charged, "for a replicate that rebuilds an")
            print("         h-bin partition; h is not being charged at all")
    # ONE-SIDED on purpose. Charging a bin the same as a sample-draw over-charges binning
    # (measured slopes: ~400 ns per extra sample against ~140 ns per extra bin), so the cost
    # per declared unit FALLING as h grows is the safe direction and is expected. What must
    # never happen is the reverse: real work growing faster than the number charged for it.
    var decl_undercharge = 0.0
    if decl_cost[0] > 0.0:
        decl_undercharge = decl_cost[len(decl_cost) - 1] / decl_cost[0]
    print("    ns/declared-unit at h=4096 divided by h=1:", decl_undercharge,
          " (gate: < 4.0)")
    print("    the version that charged n_bins only for its sign read ~133x here")
    if decl_undercharge >= 4.0 or decl_undercharge <= 0.0:
        failures += 1
        print("    ❌ the declared cost understates the work as h grows: a request the budget")
        print("       rates cheap is minutes of real work, which from the caller's side is")
        print("       the hang that rule 1 is about")
    else:
        print("    ✅ h is charged, so one declared unit means the same work at any h")
    print("")

    # ── 6. the work budget refuses before doing the work ─────────────────────
    print("[6] the work budget refuses in validation time, not after the loop")
    var refuse_n = 8192
    var rp = synth_probs(refuse_n, 20260731)
    var ry = synth_labels(rp, refuse_n, 20260731)
    # Deliberately asymmetric: the legal run is timed at its FASTEST and the refusal at its
    # SLOWEST, so the comparison below is the hardest version of the claim. If even the worst
    # refusal beats the best legal run of the same shape, the budget is certainly being
    # checked before the loop and not after it.
    var legal = bootstrap_metric_ci_flat(
        rp, ry, refuse_n, EVAL_METRIC_BRIER, 20, EVAL_BIN_EQUAL_WIDTH, 40, 0.05, 1
    )
    checksum += legal.point
    var legal_best: UInt = 0
    for r in range(BENCH_REPS):
        var t_legal_0 = perf_counter_ns()
        legal = bootstrap_metric_ci_flat(
            rp, ry, refuse_n, EVAL_METRIC_BRIER, 20, EVAL_BIN_EQUAL_WIDTH, 40, 0.05, 1
        )
        var t_legal_1 = perf_counter_ns()
        checksum += legal.point
        legal_best = (
            (t_legal_1 - t_legal_0) if r == 0
            else min_ns(legal_best, t_legal_1 - t_legal_0)
        )
    var refused = legal.copy()
    var refuse_worst: UInt = 0
    for r in range(BENCH_REPS):
        var t_ref_0 = perf_counter_ns()
        refused = bootstrap_metric_ci_flat(
            rp, ry, refuse_n, EVAL_METRIC_BRIER, 20, EVAL_BIN_EQUAL_WIDTH,
            EVAL_MAX_RESAMPLES, 0.05, 1
        )
        var t_ref_1 = perf_counter_ns()
        var span = t_ref_1 - t_ref_0
        if r == 0 or span > refuse_worst:
            refuse_worst = span
    var legal_ns = Float64(Int(legal_best))
    var refuse_ns = Float64(Int(refuse_worst))
    print("    legal   n=8192 x  40 replicates, FASTEST of", BENCH_REPS, ":", legal_ns,
          "ns ->", eval_status_name(legal.status))
    print("    refused n=8192 x 2^20 replicates (2^33 draws), SLOWEST of", BENCH_REPS, ":",
          refuse_ns, "ns ->", eval_status_name(refused.status))
    if refused.status != EVAL_ERR_WORK_BUDGET:
        failures += 1
        print("    ❌ a 2^33-draw request was not refused by the work budget")
    elif refuse_ns >= legal_ns:
        failures += 1
        print("    ❌ the refusal cost as much as doing 40 replicates, so the budget is")
        print("       being checked after the loop rather than before it")
    else:
        print("    ✅ the refusal is cheaper than the smallest legal run of the same shape")
    if legal.status != EVAL_OK:
        failures += 1
        print("    ❌ the legal shape was refused")
    print("")

    # ── 7. the gates FAIL ────────────────────────────────────────────────────
    print("[7] the gates reject. A gate never shown failing is decoration.")
    var base_p = List[Float64]()
    var base_y = List[Float64]()
    base_p.append(0.1); base_y.append(0.0)
    base_p.append(0.9); base_y.append(1.0)
    var cand_p = List[Float64]()
    var cand_y = List[Float64]()
    cand_p.append(0.6); cand_y.append(0.0)
    cand_p.append(0.4); cand_y.append(1.0)
    var reg = metric_regression_gate_flat(
        base_p, base_y, 2, cand_p, cand_y, 2, EVAL_METRIC_BRIER, 4,
        EVAL_BIN_EQUAL_WIDTH, 0.01
    )
    print("    Brier 0.01 -> 0.36, tolerance 0.01: decided", reg.decided,
          " passed", reg.passed, " margin", reg.margin)
    if not reg.decided or reg.passed:
        failures += 1
        print("    ❌ a 35x Brier regression was not rejected")
    var reg_ok = metric_regression_gate_flat(
        base_p, base_y, 2, base_p, base_y, 2, EVAL_METRIC_BRIER, 4,
        EVAL_BIN_EQUAL_WIDTH, 0.0
    )
    print("    the same dataset against itself, tolerance 0.0: passed", reg_ok.passed)
    if not reg_ok.passed:
        failures += 1
        print("    ❌ an identical candidate was rejected, so the gate rejects everything")
    var tie = metric_gate(0.25, 0.5, 0.25, False)
    if not tie.passed or tie.margin != 0.0:
        failures += 1
        print("    ❌ the documented inclusive boundary (an exact binary tie) did not pass")
    var near = metric_gate(0.09, 0.10, 0.01, False)
    print("    the decimal near-tie 0.09 -> 0.10 at tolerance 0.01: passed", near.passed,
          " margin", near.margin)
    if near.passed:
        failures += 1
        print("    ❌ fl(0.10) - fl(0.09) exceeds fl(0.01) and must be rejected exactly")

    var refs = List[Float64]()
    refs.append(0.1); refs.append(0.2); refs.append(0.6); refs.append(0.7)
    var drifted = List[Float64]()
    drifted.append(0.1); drifted.append(0.6); drifted.append(0.7); drifted.append(0.8)
    var psi = psi_drift_gate_flat(refs, 4, drifted, 4, 2, 0.25)
    print("    PSI", psi.psi, "against a 0.25 threshold: decided", psi.decided,
          " drifted", psi.drifted)
    if not psi.decided or not psi.drifted:
        failures += 1
        print("    ❌ a PSI of 0.2747 did not fire a 0.25 drift threshold")
    var abandoned = List[Float64]()
    abandoned.append(0.6); abandoned.append(0.7); abandoned.append(0.8); abandoned.append(0.9)
    var inc = psi_drift_gate_flat(refs, 4, abandoned, 4, 2, 0.40)
    print("    a bin the candidate abandoned, threshold 0.40: status",
          eval_status_name(inc.status), " present", inc.present, " decided", inc.decided,
          " lower bound", inc.psi_lower_bound)
    if inc.status != EVAL_ERR_PSI_INCOMPLETE or inc.present:
        failures += 1
        print("    ❌ an infinite PSI term was reported as a complete index")
    elif inc.decided or inc.drifted:
        failures += 1
        print("    ❌ a lower bound of 0.3466 decides nothing about a 0.40 threshold; this is")
        print("       exactly where a naive sum over the frozen term concludes 'no drift'")
    else:
        print("    ✅ the incomplete index is absent and the verdict is withheld")
    var inc_decisive = psi_drift_gate_flat(refs, 4, abandoned, 4, 2, 0.25)
    if not inc_decisive.decided or not inc_decisive.drifted:
        failures += 1
        print("    ❌ the same lower bound DOES decide a 0.25 threshold and must fire")
    print("")

    # ── 8. no refusal takes the process with it ──────────────────────────────
    print("[8] every refusal returns a status. Reaching the end of this section is the test.")
    var small = List[Float64]()
    var small_y = List[Float64]()
    small.append(0.25); small_y.append(0.0)
    small.append(0.75); small_y.append(1.0)
    var refusals = 0
    var typed = 0
    # Counts far past the end of a two-element list, on every driver that takes one.
    if evaluate_flat(small, small_y, 1000000, 8, EVAL_BIN_EQUAL_WIDTH).status != EVAL_OK:
        typed += 1
    refusals += 1
    if log_loss_flat(small, small_y, 1000000).status != EVAL_OK:
        typed += 1
    refusals += 1
    if calibration_error_flat(small, small_y, 1000000, 8, EVAL_BIN_EQUAL_WIDTH).status != EVAL_OK:
        typed += 1
    refusals += 1
    if len(reliability_diagram_flat(small, small_y, 1000000, 8, 0).bin_lo) == 0:
        typed += 1
    refusals += 1
    if eval_bins_build(small, small_y, 1000000, 8, EVAL_BIN_EQUAL_WIDTH).status != EVAL_OK:
        typed += 1
    refusals += 1
    if metric_value_flat(small, small_y, 1000000, EVAL_METRIC_ECE, 8, 0).status != EVAL_OK:
        typed += 1
    refusals += 1
    if bootstrap_metric_ci_flat(small, small_y, 1000000, 0, 8, 0, 4, 0.05, 1).status != EVAL_OK:
        typed += 1
    refusals += 1
    if psi_drift_gate_flat(small, 1000000, small, 2, 8, 0.25).status != EVAL_OK:
        typed += 1
    refusals += 1
    if metric_regression_gate_flat(
        small, small_y, 1000000, small, small_y, 2, EVAL_METRIC_BRIER, 8, 0, 0.01
    ).status != EVAL_OK:
        typed += 1
    refusals += 1
    # A negative count is not a subscript, but it must not be trusted either.
    if evaluate_flat(small, small_y, -1000, 8, EVAL_BIN_EQUAL_WIDTH).status != EVAL_OK:
        typed += 1
    refusals += 1
    # A negative bin count would index a negative slot if it reached the allocation.
    if evaluate_flat(small, small_y, 2, -8, EVAL_BIN_EQUAL_WIDTH).status != EVAL_OK:
        typed += 1
    refusals += 1
    # A non-finite prediction, which would otherwise reach a metric field.
    var nan_p = List[Float64]()
    nan_p.append(0.0 / 0.0)
    nan_p.append(0.5)
    if evaluate_flat(nan_p, small_y, 2, 8, EVAL_BIN_EQUAL_WIDTH).status != EVAL_OK:
        typed += 1
    refusals += 1
    # A replicate count too small to resolve the requested tails: valid in every other
    # respect, and the interval it would produce is narrower than the data supports.
    var narrow = bootstrap_metric_ci_flat(
        small, small_y, 2, EVAL_METRIC_BRIER, 8, EVAL_BIN_EQUAL_WIDTH, 1, 0.05, 1
    )
    if narrow.status != EVAL_OK and not narrow.present and narrow.n_boot_min == 40:
        typed += 1
    refusals += 1
    print("    refusals fired:", typed, "of", refusals, "attempted")
    if typed != refusals:
        failures += 1
        print("    ❌ a malformed request was ACCEPTED, which is worse than a crash")
    else:
        print("    ✅ every malformed request returned a typed refusal and the process lived")
    print("")

    print("    (checksum, so no measured call is optimized away:", checksum, ")")
    if failures == 0:
        print("BENCH_GATE evaluation PASS")
    else:
        print("BENCH_GATE evaluation FAIL " + String(failures))
        raise Error(
            "bench_evaluation: " + String(failures) + " gate failure(s)"
        )
