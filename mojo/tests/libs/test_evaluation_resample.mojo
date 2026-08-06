"""test_evaluation_resample.mojo — hand-written tests for the bootstrap CI.

Hand-written, never machine-emitted.

A bootstrap is a place where "the function agrees with itself" is very easy to write and
worth nothing. So the WHOLE interval is rebuilt from frozen kernels this package does not own
and compared bit for bit:

  `independent_interval` draws every one of the `n_boot * n` indices from
  `determinism.sampling_keyed.uniform_int_keyed` at the coordinates the driver claims to use,
  forms each replicate's Brier score from `ml_metrics_extended.brier_score_term`, sorts the
  replicates with `sorting.heapsort`, and takes the two percentiles with `stats.quantile`.
  Asserting `lo` and `hi` against that checks the coordinate map `draw_index = b * n + i` for
  EVERY replicate, the stream derivation, the pairing of each prediction with its own label,
  and the percentile extraction — none of it against a number this module recorded earlier.
  `distinct_replicates` is asserted against the independently derived multiset too.

  This replaces an earlier `n_boot = 1` version of the same idea, which could only check
  replicate 0 and only worked because a one-replicate "95% interval" was accepted. It is not,
  any more: see the tail-resolution section below.

The tail-resolution bound, asserted at its boundary
---------------------------------------------------
A percentile interval reads the replicate distribution at `alpha/2`, and `n_boot` replicates
carry no information at any probability finer than `1/n_boot`. So `n_boot * alpha >= 2` is
required, which is 40 replicates at alpha = 0.05. Asserted AS a boundary — 39 refused, 40
accepted — because a bound tested only far from its edge does not pin where the edge is.
Measured before this was enforced, on non-degenerate data, all under status `ok`: `n_boot = 1`
gave `lo == hi` (a "95% CI" of width zero) with the point estimate OUTSIDE it, and
`n_boot = 2` gave a width of 0.0156 against 0.0933 at 2000 replicates.

Hand-computable known values:
  * All samples identical (p = 0.5, y = 1 six times): every replicate is the same multiset, so
    every replicate's Brier is (0.5 - 1)^2 = 0.25 and the interval collapses:
    point == lo == hi == 0.25 exactly, `distinct_replicates` == 1.
  * n = 1 (p = [0.2], y = [0]): the only index that can be drawn is 0, so again the interval
    collapses, onto 0.2^2 = 0.04.
  * base rate of [0,0,1,1,1] is 0.6 exactly, and the point estimate must be that, not a
    resampled approximation of it.
  * `bootstrap_min_replicates`: 40 at alpha = 0.05 (2/0.05), 20 at 0.10, 4 at 0.5, and 5 —
    not 6 — at alpha = 0.4, because `5 * 0.4 == 2.0` exactly while `fl(2/0.4)` is
    5.000000000000001 and a ceil-of-quotient implementation would demand 6.
"""
from std.math import abs as fabs

from determinism.sampling_keyed import uniform_int_keyed
from determinism.streams import stream_id
from ml_metrics_extended import brier_score_term
from sorting import heapsort
from stats import quantile

from evaluation.contract import (
    EVAL_BIN_EQUAL_COUNT,
    EVAL_BIN_EQUAL_WIDTH,
    EVAL_DBL_EPSILON,
    EVAL_ERR_ALPHA_RANGE,
    EVAL_ERR_BIN_COUNT,
    EVAL_ERR_COUNT,
    EVAL_ERR_EMPTY,
    EVAL_ERR_LABEL_NOT_BINARY,
    EVAL_ERR_RESAMPLE_COUNT,
    EVAL_ERR_SEED_NEGATIVE,
    EVAL_ERR_UNKNOWN_METRIC,
    EVAL_ERR_WORK_BUDGET,
    EVAL_MAX_RESAMPLES,
    EVAL_METRIC_BASE_RATE,
    EVAL_METRIC_BRIER,
    EVAL_METRIC_COUNT,
    EVAL_METRIC_ECE,
    EVAL_OK,
    eval_status_name,
)
from evaluation.resample import (
    EVAL_BOOTSTRAP_STREAM_NAME,
    bootstrap_draw_index,
    bootstrap_metric_ci_flat,
    bootstrap_min_replicates,
)
from evaluation.scores import metric_value_flat


def close(got: Float64, want: Float64) -> Bool:
    return fabs(got - want) <= 8.0 * EVAL_DBL_EPSILON * fabs(want)


def probs_a() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.1)
    out.append(0.3)
    out.append(0.5)
    out.append(0.7)
    out.append(0.9)
    return out^


def labels_a() -> List[Float64]:
    var out = List[Float64]()
    out.append(0.0)
    out.append(0.0)
    out.append(1.0)
    out.append(1.0)
    out.append(1.0)
    return out^


def replicate_brier(
    probs: List[Float64], labels: List[Float64], n: Int, replicate: Int, seed: Int
) -> Float64:
    """Rebuild replicate `replicate`'s Brier score from the FROZEN kernels alone.

    Calls `determinism.sampling_keyed.uniform_int_keyed` at the coordinates the driver claims
    to use and `ml_metrics_extended.brier_score_term` for each drawn pair, so this is an
    independent derivation and not a restatement of the driver.
    """
    var stream = stream_id(EVAL_BOOTSTRAP_STREAM_NAME)
    var total = 0.0
    for i in range(n):
        var draw = UInt64(replicate * n + i)
        var k = uniform_int_keyed(0, n - 1, UInt64(seed), stream, draw)
        total += brier_score_term(probs[k], labels[k])
    return total / Float64(n)


def independent_interval(
    probs: List[Float64], labels: List[Float64], n: Int, n_boot: Int,
    alpha: Float64, seed: Int
) -> List[Float64]:
    """The whole percentile interval, rebuilt from frozen kernels only.

    Returns `[lo, hi, distinct]`. Every replicate is derived by `replicate_brier`, which goes
    to the frozen keyed RNG at the driver's declared coordinates; the sort is the frozen
    `sorting.heapsort` and the two percentiles are the frozen `stats.quantile`. Nothing here
    reads a value this package produced, so an equality against the driver's own `lo`/`hi`
    checks the driver rather than checking it against itself.
    """
    var reps = List[Float64](capacity=n_boot)
    for b in range(n_boot):
        reps.append(replicate_brier(probs, labels, n, b, seed))
    var sorted_reps = heapsort(reps)
    var distinct = 1
    for i in range(1, len(sorted_reps)):
        if sorted_reps[i] != sorted_reps[i - 1]:
            distinct += 1
    var out = List[Float64]()
    out.append(quantile(sorted_reps, n_boot, alpha / 2.0))
    out.append(quantile(sorted_reps, n_boot, 1.0 - alpha / 2.0))
    out.append(Float64(distinct))
    return out^


def main() raises:
    var failures = 0
    var checks = 0
    var pa = probs_a()
    var ya = labels_a()

    # ── the coordinate map is injective, which is what "every draw" means ─────
    var seen = List[Bool]()
    for _ in range(20):
        seen.append(False)
    var collisions = 0
    var wrong = 0
    for b in range(4):
        for i in range(5):
            var idx = bootstrap_draw_index(b, i, 5)
            if idx != b * 5 + i:
                wrong += 1
            elif seen[idx]:
                collisions += 1
            else:
                seen[idx] = True
    checks += 1
    if wrong != 0 or collisions != 0:
        print("  ❌ the draw coordinate map is not injective:", wrong, "wrong,",
              collisions, "collision(s) — a collision means one draw's value is reused")
        failures += 1
    var unseen = 0
    for t in range(20):
        if not seen[t]:
            unseen += 1
    checks += 1
    if unseen != 0:
        print("  ❌", unseen, "of 20 coordinates never produced — the seed does not reach")
        print("     every draw")
        failures += 1
    checks += 1
    if bootstrap_draw_index(-1, 0, 5) != -1 or bootstrap_draw_index(0, -1, 5) != -1:
        print("  ❌ a negative coordinate is not a coordinate")
        failures += 1
    checks += 1
    if bootstrap_draw_index(0, 5, 5) != -1 or bootstrap_draw_index(0, 0, 0) != -1:
        print("  ❌ a sample index at or past n is not a coordinate")
        failures += 1

    # ── the tail-resolution bound, asserted AT its boundary ──────────────────
    # alpha = 0.05 needs 2/0.05 = 40 replicates. 39 must refuse and 40 must be accepted:
    # a bound tested only far from its edge does not pin where the edge is.
    var seed = 20260731
    checks += 1
    if bootstrap_min_replicates(0.05) != 40 or bootstrap_min_replicates(0.10) != 20:
        print("  ❌ bootstrap_min_replicates:", bootstrap_min_replicates(0.05),
              bootstrap_min_replicates(0.10), "want 40 and 20")
        failures += 1
    checks += 1
    if bootstrap_min_replicates(0.5) != 4 or bootstrap_min_replicates(0.4) != 5:
        print("  ❌ bootstrap_min_replicates(0.5) =", bootstrap_min_replicates(0.5),
              "want 4; (0.4) =", bootstrap_min_replicates(0.4), "want 5 — 5*0.4 == 2.0")
        print("     exactly, so a ceil(fl(2/0.4)) = 6 implementation is off by one")
        failures += 1
    checks += 1
    if (
        bootstrap_min_replicates(0.0) != 0
        or bootstrap_min_replicates(1.0) != 0
        or bootstrap_min_replicates(0.0 / 0.0) != 0
    ):
        print("  ❌ an alpha that is not a tail probability has no minimum, and 0 is the")
        print("     only value that cannot be mistaken for one")
        failures += 1
    checks += 1
    if bootstrap_min_replicates(1.0 / Float64(EVAL_MAX_RESAMPLES)) != 0:
        print("  ❌ an alpha whose tails no legal replicate count can reach must report 0,",
              bootstrap_min_replicates(1.0 / Float64(EVAL_MAX_RESAMPLES)))
        failures += 1

    var one = bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 1, 0.05, seed
    )
    checks += 1
    if one.status != EVAL_ERR_RESAMPLE_COUNT or one.present:
        print("  ❌ one replicate cannot carry a 95% interval —", eval_status_name(one.status),
              "present", one.present, ". Measured before this was checked: lo == hi, a width")
        print("     of exactly 0.0, with the point estimate outside its own interval")
        failures += 1
    checks += 1
    if one.lo != 0.0 or one.hi != 0.0 or one.n_boot_min != 40:
        print("  ❌ the refusal must carry no interval and must say what to ask for:",
              one.lo, one.hi, "n_boot_min", one.n_boot_min, "want 0.0, 0.0, 40")
        failures += 1
    var edge_lo = bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 39, 0.05, seed
    )
    var edge_ok = bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 40, 0.05, seed
    )
    checks += 1
    if edge_lo.status != EVAL_ERR_RESAMPLE_COUNT or edge_lo.n_boot_min != 40:
        print("  ❌ 39 replicates at alpha=0.05 must refuse:",
              eval_status_name(edge_lo.status), edge_lo.n_boot_min)
        failures += 1
    checks += 1
    if edge_ok.status != EVAL_OK or not edge_ok.present or edge_ok.n_boot_min != 40:
        print("  ❌ 40 replicates at alpha=0.05 is exactly the bound and must be accepted:",
              eval_status_name(edge_ok.status), edge_ok.present, edge_ok.n_boot_min)
        failures += 1
    # A wider alpha needs fewer replicates, so the bound is a function of alpha and not a
    # constant somebody liked.
    checks += 1
    if bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 4, 0.5, seed
    ).status != EVAL_OK:
        print("  ❌ 4 replicates DO resolve a 50% interval and must be accepted")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 3, 0.5, seed
    ).status != EVAL_ERR_RESAMPLE_COUNT:
        print("  ❌ 3 replicates do not resolve a 50% interval")
        failures += 1

    # ── the whole interval, rebuilt from frozen kernels, bit for bit ──────────
    # 40 replicates x 5 samples = 200 draws, every one re-derived from
    # uniform_int_keyed at draw_index = b*5 + i, so this checks the coordinate map for
    # every replicate and not only for replicate 0.
    var want = independent_interval(pa, ya, 5, 40, 0.05, seed)
    checks += 1
    if edge_ok.lo != want[0] or edge_ok.hi != want[1]:
        print("  ❌ the interval is [", edge_ok.lo, ",", edge_ok.hi, "] but the frozen keyed")
        print("     RNG + brier_score_term + heapsort + quantile give [", want[0], ",",
              want[1], "]")
        failures += 1
    checks += 1
    if Float64(edge_ok.distinct_replicates) != want[2]:
        print("  ❌ distinct replicates", edge_ok.distinct_replicates, "but the independent",
              "derivation has", want[2])
        failures += 1
    checks += 1
    if edge_ok.n_draws != 200:
        print("  ❌ n_draws", edge_ok.n_draws, "want 40 * 5 = 200")
        failures += 1
    # The derivation has to be non-degenerate or the equality above proves nothing.
    checks += 1
    if want[0] >= want[1] or want[2] < 3.0:
        print("  ❌ the independently derived interval is degenerate ([", want[0], ",",
              want[1], "], distinct", want[2], "), so matching it is not evidence")
        failures += 1

    # ── the point estimate is the FULL-SAMPLE metric, bit for bit ─────────────
    var full = metric_value_flat(pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH)
    var ci = bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 400, 0.05, 42
    )
    checks += 1
    if ci.point != full.value:
        print("  ❌ the point estimate", ci.point, "is not the full-sample metric", full.value)
        failures += 1
    checks += 1
    if ci.point != 0.09:
        print("  ❌ the point estimate must be the hand-computed Brier 0.09:", ci.point)
        failures += 1
    checks += 1
    if ci.lo > ci.hi:
        print("  ❌ the interval is inverted:", ci.lo, ci.hi)
        failures += 1
    checks += 1
    if not ci.point_inside:
        print("  ❌ the percentile interval excludes the point estimate on this data;")
        print("     that is possible for a skewed statistic but not expected here")
        failures += 1
    checks += 1
    if ci.n_draws != 2000:
        print("  ❌ n_draws", ci.n_draws, "want 400 * 5 = 2000")
        failures += 1
    checks += 1
    if ci.seed != 42 or ci.n_boot != 400 or ci.alpha != 0.05:
        print("  ❌ the result must carry enough provenance to reproduce itself")
        failures += 1

    # ── reproducibility, and a different seed gives a different answer ────────
    var again = bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 400, 0.05, 42
    )
    checks += 1
    if again.lo != ci.lo or again.hi != ci.hi or again.point != ci.point:
        print("  ❌ the same seed did not reproduce the interval bit for bit")
        failures += 1
    checks += 1
    if again.distinct_replicates != ci.distinct_replicates:
        print("  ❌ the same seed produced a different replicate distribution")
        failures += 1
    var other = bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 400, 0.05, 43
    )
    checks += 1
    if other.hi == ci.hi and other.lo == ci.lo:
        print("  ❌ seeds 42 and 43 gave an identical interval — the seed is not reaching")
        print("     the draws, or is being collapsed before it does")
        failures += 1
    # More than one distinct replicate value is the observable that a per-coordinate draw
    # scheme is actually working: a collapsed distribution is what a seed reaching only the
    # first draw would produce.
    checks += 1
    if ci.distinct_replicates <= 1:
        print("  ❌ 400 replicates of non-degenerate data collapsed to",
              ci.distinct_replicates, "distinct value(s)")
        failures += 1

    # ── degenerate data: the interval collapses onto a hand-computed value ────
    var flat_p = List[Float64]()
    var flat_y = List[Float64]()
    for _ in range(6):
        flat_p.append(0.5)
        flat_y.append(1.0)
    var deg = bootstrap_metric_ci_flat(
        flat_p, flat_y, 6, EVAL_METRIC_BRIER, 4, EVAL_BIN_EQUAL_WIDTH, 50, 0.05, 7
    )
    checks += 1
    if deg.point != 0.25 or deg.lo != 0.25 or deg.hi != 0.25:
        print("  ❌ identical samples must give (0.5-1)^2 = 0.25 for every replicate:",
              deg.point, deg.lo, deg.hi)
        failures += 1
    checks += 1
    if deg.distinct_replicates != 1:
        print("  ❌ identical samples cannot produce", deg.distinct_replicates,
              "distinct replicate values")
        failures += 1

    # ── n = 1: only one index can be drawn ───────────────────────────────────
    var single_p = List[Float64]()
    var single_y = List[Float64]()
    single_p.append(0.2)
    single_y.append(0.0)
    var single = bootstrap_metric_ci_flat(
        single_p, single_y, 1, EVAL_METRIC_BRIER, 2, EVAL_BIN_EQUAL_WIDTH, 40, 0.05, 3
    )
    checks += 1
    if not close(single.point, 0.04) or single.lo != single.point or single.hi != single.point:
        print("  ❌ n=1 must collapse onto 0.2^2 = 0.04:", single.point, single.lo, single.hi)
        failures += 1

    # ── the base rate is exact, not a resampled approximation ────────────────
    var base = bootstrap_metric_ci_flat(
        pa, ya, 5, EVAL_METRIC_BASE_RATE, 5, EVAL_BIN_EQUAL_WIDTH, 100, 0.10, 11
    )
    checks += 1
    if base.point != 0.6:
        print("  ❌ the base-rate point estimate", base.point, "want exactly 0.6")
        failures += 1
    checks += 1
    if base.bins_used != 0 or base.bin_policy != -1:
        print("  ❌ a non-binning metric must not imply a binning provenance:",
              base.bins_used, base.bin_policy)
        failures += 1

    # ── an ECE bootstrap carries its binning, under both policies ────────────
    for policy in range(2):
        var ece_ci = bootstrap_metric_ci_flat(
            pa, ya, 5, EVAL_METRIC_ECE, 5, policy, 60, 0.05, 5
        )
        checks += 1
        if ece_ci.status != EVAL_OK or not ece_ci.present:
            print("  ❌ ECE bootstrap policy", policy, eval_status_name(ece_ci.status))
            failures += 1
            continue
        checks += 1
        if ece_ci.bins_used != 5 or ece_ci.bin_policy != policy:
            print("  ❌ ECE bootstrap policy", policy, "provenance", ece_ci.bins_used,
                  ece_ci.bin_policy)
            failures += 1
        checks += 1
        if ece_ci.lo > ece_ci.hi or ece_ci.lo < 0.0 or ece_ci.hi > 1.0:
            print("  ❌ an ECE interval must lie in [0, 1] and not be inverted:",
                  ece_ci.lo, ece_ci.hi)
            failures += 1

    # ── every refusal is typed, and none of them can index past a list ────────
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 25, 0, 5, 0, 10, 0.05, 1).status != EVAL_ERR_COUNT:
        print("  ❌ n past the list end must refuse")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 0, 0, 5, 0, 10, 0.05, 1).status != EVAL_ERR_EMPTY:
        print("  ❌ an empty evaluation set has no interval")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, pa, 5, 0, 5, 0, 10, 0.05, 1).status != EVAL_ERR_LABEL_NOT_BINARY:
        print("  ❌ soft labels must refuse")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, 0, 0, 0, 10, 0.05, 1).status != EVAL_ERR_BIN_COUNT:
        print("  ❌ h=0 must refuse")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, EVAL_METRIC_COUNT, 5, 0, 10, 0.05, 1).status \
            != EVAL_ERR_UNKNOWN_METRIC:
        print("  ❌ an unknown metric must refuse, never default")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, 0, 5, 0, 0, 0.05, 1).status != EVAL_ERR_RESAMPLE_COUNT:
        print("  ❌ n_boot=0 must refuse")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, 0, 5, 0, -5, 0.05, 1).status != EVAL_ERR_RESAMPLE_COUNT:
        print("  ❌ a negative n_boot must refuse")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(
        pa, ya, 5, 0, 5, 0, EVAL_MAX_RESAMPLES + 1, 0.05, 1
    ).status != EVAL_ERR_RESAMPLE_COUNT:
        print("  ❌ the replicate ceiling must be enforced")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, 0, 5, 0, 10, 0.0, 1).status != EVAL_ERR_ALPHA_RANGE:
        print("  ❌ alpha=0 has no percentile interval")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, 0, 5, 0, 10, 1.0, 1).status != EVAL_ERR_ALPHA_RANGE:
        print("  ❌ alpha=1 must refuse")
        failures += 1
    var nan_v = 0.0 / 0.0
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, 0, 5, 0, 10, nan_v, 1).status != EVAL_ERR_ALPHA_RANGE:
        print("  ❌ a NaN alpha must refuse — an unvalidated NaN threshold makes every")
        print("     comparison False and the check passes having found nothing")
        failures += 1
    checks += 1
    if bootstrap_metric_ci_flat(pa, ya, 5, 0, 5, 0, 10, 0.05, -1).status \
            != EVAL_ERR_SEED_NEGATIVE:
        print("  ❌ a negative seed must refuse rather than be reinterpreted as a huge")
        print("     unsigned value the caller's record cannot reproduce")
        failures += 1
    # A refused request must leave nothing that looks like an interval.
    var refused = bootstrap_metric_ci_flat(pa, ya, 5, 0, 5, 0, 10, 0.05, -1)
    checks += 1
    if refused.present or refused.lo != 0.0 or refused.hi != 0.0 or refused.point != 0.0:
        print("  ❌ a refused CI must not carry values")
        failures += 1

    # ── the work budget refuses a shape that is memory-legal and unbounded ────
    # 2^13 samples and 2^20 replicates is 2^33 draws: every argument is inside its own
    # ceiling and the product is not. It must be refused BEFORE any draw is made.
    var big_p = List[Float64]()
    var big_y = List[Float64]()
    for i in range(8192):
        big_p.append(0.5)
        big_y.append(1.0 if i % 2 == 0 else 0.0)
    checks += 1
    if bootstrap_metric_ci_flat(
        big_p, big_y, 8192, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH,
        EVAL_MAX_RESAMPLES, 0.05, 1
    ).status != EVAL_ERR_WORK_BUDGET:
        print("  ❌ 2^13 * 2^20 = 2^33 draws must exceed the work budget; a budget that")
        print("     charges one factor of a product is not a budget")
        failures += 1
    # The same shape with a hundred replicates is legal and must still work.
    var ok_big = bootstrap_metric_ci_flat(
        big_p, big_y, 8192, EVAL_METRIC_BRIER, 5, EVAL_BIN_EQUAL_WIDTH, 40, 0.05, 1
    )
    checks += 1
    if ok_big.status != EVAL_OK or not ok_big.present:
        print("  ❌ a legal large shape was refused:", eval_status_name(ok_big.status))
        failures += 1
    checks += 1
    if not close(ok_big.point, 0.25):
        print("  ❌ every prediction is 0.5, so the Brier score is 0.25:", ok_big.point)
        failures += 1

    for _ in range(checks - failures):
        print("  ✅ evaluation.resample check")
    print("  [evaluation.resample] Passed:", checks - failures, "Failed:", failures)
    if failures != 0:
        raise Error("test_evaluation_resample failed")
