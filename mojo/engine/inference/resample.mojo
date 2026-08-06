"""
inference.resample — bootstrap and permutation drivers that REPRODUCE. Zero Python imports.

Why this module exists
----------------------
`stats_bootstrap` has the primitives and cannot be quoted. All nine of its resampling entry
points — `bootstrap_replicate`, `bootstrap_mean_ci`, `bootstrap_std_ci`,
`bootstrap_median_ci`, `bootstrap_bias`, `bootstrap_se`, `bootstrap_test`, `bca_correction`
and everything built on them — draw from `std.random.random_float64`, which reads
process-global state. So the same call on the same data returns a different confidence
interval every time, and there is no seed parameter to pin it with.

A confidence interval that changes between runs cannot be used in a decision that has to be
explained, which is the premise of this entire tree. That is the whole gap this module
closes: the statistics are the frozen ones, the RANDOMNESS is addressed.

Determinism, and why counter-based
----------------------------------
Every draw comes from `determinism.sampling_keyed`, which is built on
`determinism.counter_rng` (Philox4x64-10). A draw is a pure function of its coordinates
`(seed, stream, draw_index)` rather than of what ran before it, so:

* replicate `r` of a bootstrap consumes exactly the coordinates `[r*n, (r+1)*n)` and is the
  same replicate no matter how many replicates were computed first, and no matter whether
  anything else in the process drew a number;
* two runs with the same `seed` and `stream` produce BIT-IDENTICAL intervals, which the
  suite asserts with `==` rather than a tolerance;
* two different `stream` values give independent answers on the same seed, so a caller can
  run an independent replication without changing the seed they published.

`random_float64` and `seed(` appear nowhere in this module. `stats_bootstrap.bootstrap_test`
is deliberately NOT called even as a cross-check: one call to it would make a driver here
non-deterministic, which is the defect being fixed.

What is reused rather than rebuilt
----------------------------------
* `determinism.sampling_keyed.bootstrap_keyed` — the resample-WITH-replacement draw itself.
* `determinism.sampling_keyed.permutation_keyed` — the Fisher-Yates permutation, keyed.
* `stats_bootstrap._mean`, `_median`, `_std` — the three statistics, called unchanged, so
  the numbers here are the frozen definitions with the draws made reproducible and nothing
  else changed. (`_median` insertion-sorts internally, which is why the WORK budget below
  charges `n^2` for the median statistic and `n` for the other two.)
* `sorting.mergesort` — the O(B log B) sort of the resample distribution. The frozen
  bootstrap CIs use an insertion sort for this, which is O(B^2) in the number of resamples
  and therefore the wrong shape for a driver whose whole point is a large B.
* `optimization.model._floor_f` — the percentile index, per rule 4c: never
  `Float64(Int(v))`, whose out-of-range `fptosi` is poison rather than truncation.
* `inference.core` — status vocabulary, finiteness, and the wrapping-safe budgets.

Rule 4 in this module
---------------------
* **A p-value of exactly zero does not exist for a finite permutation test.**
  `stats_bootstrap.bootstrap_test` returns `count / B`, which is `0.0` when no permutation
  beat the observed statistic — a number that claims impossibility from B trials. The
  estimator here is `(1 + count) / (1 + B)`, which is both the standard unbiased-under-the-
  null form and never zero, and `p_value_floor` reports `1 / (1 + B)` so a caller can see
  the smallest p-value their B could ever produce. Quoting `p < 0.001` off `B = 200` is the
  error this makes impossible.
* **An interval from B resamples has sampling error in the INTERVAL ITSELF.** Every result
  carries `n_resamples`, `seed` and `stream` so it is reproducible, and
  `lo_mc_halfwidth` / `hi_mc_halfwidth` so its precision is knowable: the endpoint of a
  percentile interval is the order statistic at rank `k = floor(a*B)`, whose rank has
  standard deviation `sqrt(B a (1-a))` across seeds, so the reported half-width is the
  spread of the resample distribution across one rank standard deviation either side of `k`.
  That is a measured quantity, not an asymptotic formula, and it goes to zero as B grows.
* A statistic of nothing does not exist: `n < 2` is `INF_ERR_TOO_FEW` for the standard
  deviation (which needs two points) and `n < 1` is `INF_ERR_EMPTY` for all three.
* An unrecognised statistic selector is `INF_ERR_TUNING` and no interval. The frozen
  `bootstrap_bias(data, B, stat_type)` treats every `stat_type` other than 1 as the mean,
  so a caller asking for the 99th percentile silently receives an interval for the mean.

Status codes 320-339 belong to the `inference` package; this module allocates none of its
own (rule 4e).

Work budgets, per "bounding memory is not bounding work"
-------------------------------------------------------
Memory is `2 * n_resamples` doubles for the resample distribution and its merge buffer, plus
`n` for the population prefix — bounded by `MAX_RESAMPLES` and `MAX_INFERENCE_OBS`. Neither
bounds the COST, which is a product:

    statistic 0 (mean) / 2 (std) : n_resamples * n            <= MAX_RESAMPLE_WORK
    statistic 1 (median)         : n_resamples * n * n        <= MAX_RESAMPLE_WORK
    permutation test             : n_permutations * (n1 + n2) <= MAX_RESAMPLE_WORK

each formed with `inference_product_fits` / `inference_product3_fits`, which decide by
division and never materialise the product — `n_resamples * n` is a wrapping 64-bit multiply
and therefore not a bound at all.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: required
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_inference_resample.mojo
benchmark: benchmarks/mojo_benchmarks/bench_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from determinism.sampling_keyed import bootstrap_keyed, permutation_keyed
from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EMPTY,
    INF_ERR_NON_FINITE,
    INF_ERR_RESAMPLE_COUNT,
    INF_ERR_SHAPE,
    INF_ERR_TOO_FEW,
    INF_ERR_TUNING,
    INF_OK,
    MAX_INFERENCE_OBS,
    MAX_RESAMPLES,
    MAX_RESAMPLE_WORK,
    inference_finite,
    inference_product3_fits,
    inference_product_fits,
)
from optimization.model import _floor_f
from sorting import mergesort
from stats_bootstrap import _mean, _median, _std

# Statistic selectors. 0 and 1 match `stats_bootstrap`'s own `stat_type` convention
# (0 = mean, 1 = median) so a caller moving off the frozen kernels does not have to relearn
# them; 2 names the standard deviation, which the frozen kernels select by calling a
# different function rather than by an id.
comptime STAT_MEAN: Int = 0
comptime STAT_MEDIAN: Int = 1
comptime STAT_STD: Int = 2


def resample_statistic_name(statistic: Int) -> String:
    """Name for a statistic selector, so a rejected id surfaces as a word.

    Deterministic. Returns "unknown" for anything this module does not implement, which is
    also the case `bootstrap_ci_flat` refuses rather than silently treating as the mean.
    """
    if statistic == STAT_MEAN:
        return "mean"
    if statistic == STAT_MEDIAN:
        return "median"
    if statistic == STAT_STD:
        return "standard_deviation"
    return "unknown"


def _statistic_of(values: List[Float64], statistic: Int) -> Float64:
    """The selected statistic, straight from the frozen `stats_bootstrap` kernels.

    Called for the point estimate and once per resample, so this is the ONLY place a
    statistic is chosen. Callers validate the selector first; an unrecognised id here would
    return the mean, which is exactly the frozen behaviour this module refuses.
    """
    if statistic == STAT_MEDIAN:
        return _median(values)
    if statistic == STAT_STD:
        return _std(values)
    return _mean(values)


def _percentile_index(fraction: Float64, b: Int) -> Int:
    """`floor(fraction * b)` clamped into `[0, b-1]`, with no `Float64(Int(v))` anywhere.

    Built on `optimization.model._floor_f` (i.e. `std.math.floor`), which is total over
    every finite Float64. `Int()` on a magnitude past the Float64 integer grid is an
    out-of-range `fptosi` — poison, not truncation — so the conversion is guarded by an
    explicit range test rather than by a finiteness check that `1e300` would pass.

    The index convention is the frozen one (`Int(alpha * n_bootstrap)` in
    `stats_bootstrap.bootstrap_mean_ci`), so an interval from this module and one from the
    frozen kernel differ only in their draws and not in how they read the percentile off the
    resample distribution.
    """
    if b <= 0:
        return 0
    var raw = _floor_f(fraction * Float64(b))
    if not inference_finite(raw) or raw < 0.0:
        return 0
    # b is at most MAX_RESAMPLES (2^20), so anything at or above b is clamped before the
    # conversion and the conversion itself can never see a value off the integer grid.
    if raw >= Float64(b):
        return b - 1
    return Int(raw)


@fieldwise_init
struct BootstrapCI(Copyable, Movable):
    """A percentile bootstrap confidence interval that can be quoted twice.

    `lo` and `hi` are meaningful only when `status == INF_OK`; on a refusal they are 0.0 and
    `interval_known` is False, so a caller cannot read a refusal as an interval around zero.

    `seed`, `stream` and `n_resamples` are carried so the interval is REPRODUCIBLE — rerun
    with the same three and the endpoints are bitwise identical.

    `lo_mc_halfwidth` / `hi_mc_halfwidth` are the Monte-Carlo uncertainty OF THE ENDPOINTS:
    the half-spread of the resample distribution across one rank standard deviation
    (`endpoint_rank_sd = sqrt(B a (1-a))`) either side of each endpoint's rank. They shrink
    as B grows and they answer "how much would this interval move under a different seed?",
    which `n_resamples` alone does not.

    `bias` is `mean(resample statistics) - point_estimate`, the frozen
    `stats_bootstrap.bootstrap_bias` quantity computed from the same reproducible draws.
    """

    var status: Int
    var statistic: Int
    var n_obs: Int
    var n_resamples: Int
    var seed: UInt64
    var stream: UInt64
    var confidence: Float64
    var interval_known: Bool
    var point_estimate: Float64
    var lo: Float64
    var hi: Float64
    var resample_se: Float64
    var bias: Float64
    var lo_rank: Int
    var hi_rank: Int
    var endpoint_rank_sd: Float64
    var lo_mc_halfwidth: Float64
    var hi_mc_halfwidth: Float64


def _ci_failure(
    code: Int, statistic: Int, n: Int, b: Int, seed: UInt64,
    stream: UInt64, confidence: Float64,
) -> BootstrapCI:
    return BootstrapCI(
        code, statistic, n, b, seed, stream, confidence, False,
        0.0, 0.0, 0.0, 0.0, 0.0, -1, -1, 0.0, 0.0, 0.0,
    )


def bootstrap_ci_flat(
    values: List[Float64], n: Int, statistic: Int,
    n_resamples: Int, confidence: Float64,
    seed: UInt64, stream: UInt64,
) -> BootstrapCI:
    """A percentile bootstrap CI for the mean, median or standard deviation, reproducibly.

    The statistic of each resample is the frozen `stats_bootstrap` kernel; the resample
    itself is `determinism.sampling_keyed.bootstrap_keyed` at coordinates
    `[r*n, (r+1)*n)`, so replicate `r` is a pure function of `(seed, stream, r)` and the
    interval reproduces bit for bit.

    Refuses rather than answering when: the payload does not contain `n` values, `n` is 0
    (`INF_ERR_EMPTY`) or 1 for the standard deviation (`INF_ERR_TOO_FEW`), any value is
    non-finite, `confidence` is not strictly inside `(0, 1)`, `n_resamples` is not positive
    or exceeds `MAX_RESAMPLES`, the statistic selector is unrecognised, or the WORK product
    exceeds `MAX_RESAMPLE_WORK` (see the module docstring — a median resample sorts, so its
    budget is charged `n^2`).

    @capability bootstrap_ci_flat
    complexity: O(n_resamples * n) for the mean and sd, O(n_resamples * n^2) for the median
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if statistic != STAT_MEAN and statistic != STAT_MEDIAN and statistic != STAT_STD:
        return _ci_failure(
            INF_ERR_TUNING, statistic, n, n_resamples, seed, stream, confidence
        )
    if n <= 0:
        return _ci_failure(
            INF_ERR_EMPTY, statistic, n, n_resamples, seed, stream, confidence
        )
    if n > len(values):
        return _ci_failure(
            INF_ERR_SHAPE, statistic, n, n_resamples, seed, stream, confidence
        )
    if n > MAX_INFERENCE_OBS:
        return _ci_failure(
            INF_ERR_DIMENSION_TOO_LARGE, statistic, n, n_resamples, seed, stream, confidence
        )
    if statistic == STAT_STD and n < 2:
        return _ci_failure(
            INF_ERR_TOO_FEW, statistic, n, n_resamples, seed, stream, confidence
        )
    for i in range(n):
        if not inference_finite(values[i]):
            return _ci_failure(
                INF_ERR_NON_FINITE, statistic, n, n_resamples, seed, stream, confidence
            )
    if not inference_finite(confidence) or confidence <= 0.0 or confidence >= 1.0:
        return _ci_failure(
            INF_ERR_ALPHA_RANGE, statistic, n, n_resamples, seed, stream, confidence
        )
    if n_resamples <= 0 or n_resamples > MAX_RESAMPLES:
        return _ci_failure(
            INF_ERR_RESAMPLE_COUNT, statistic, n, n_resamples, seed, stream, confidence
        )
    var work_ok = True
    if statistic == STAT_MEDIAN:
        work_ok = inference_product3_fits(n_resamples, n, n, MAX_RESAMPLE_WORK)
    else:
        work_ok = inference_product_fits(n_resamples, n, MAX_RESAMPLE_WORK)
    if not work_ok:
        return _ci_failure(
            INF_ERR_DIMENSION_TOO_LARGE, statistic, n, n_resamples, seed, stream, confidence
        )

    var population = List[Float64](capacity=n)
    for i in range(n):
        population.append(values[i])
    var point = _statistic_of(population, statistic)

    var stats = List[Float64](capacity=n_resamples)
    for r in range(n_resamples):
        # Replicate r owns the draw coordinates [r*n, (r+1)*n). The product is charged
        # against MAX_RESAMPLE_WORK above, so it cannot overflow the UInt64 counter.
        var replicate = bootstrap_keyed(
            population, n, seed, stream, UInt64(r * n)
        )
        stats.append(_statistic_of(replicate, statistic))
    var resample_se = _std(stats)
    var bias = _mean(stats) - point

    var sorted_stats = mergesort(stats)
    if len(sorted_stats) != n_resamples:
        return _ci_failure(
            INF_ERR_SHAPE, statistic, n, n_resamples, seed, stream, confidence
        )
    var alpha = (1.0 - confidence) / 2.0
    var lo_rank = _percentile_index(alpha, n_resamples)
    var hi_rank = _percentile_index(1.0 - alpha, n_resamples)
    var lo = sorted_stats[lo_rank]
    var hi = sorted_stats[hi_rank]

    # The rank of a percentile endpoint is Binomial(B, alpha), so its standard deviation is
    # sqrt(B a (1-a)). The value-scale uncertainty is how far the resample distribution
    # moves across that many ranks — measured on the distribution itself, not assumed.
    var rank_sd = sqrt(Float64(n_resamples) * alpha * (1.0 - alpha))
    var step = 0
    if rank_sd >= 1.0:
        var floored = _floor_f(rank_sd)
        if floored < Float64(n_resamples):
            step = Int(floored)
        else:
            step = n_resamples - 1
    var lo_hw = _halfwidth(sorted_stats, lo_rank, step)
    var hi_hw = _halfwidth(sorted_stats, hi_rank, step)

    return BootstrapCI(
        INF_OK, statistic, n, n_resamples, seed, stream, confidence, True,
        point, lo, hi, resample_se, bias, lo_rank, hi_rank, rank_sd, lo_hw, hi_hw,
    )


def _halfwidth(sorted_stats: List[Float64], rank: Int, step: Int) -> Float64:
    """Half the spread of `sorted_stats` across `step` ranks either side of `rank`.

    Both indices are clamped into the array, so the value is a real half-spread even at the
    ends of the distribution; it is never an extrapolation. `step == 0` gives exactly 0.0,
    which is the honest answer when one rank standard deviation is below one rank: at that
    B the endpoint's rank does not move.
    """
    var b = len(sorted_stats)
    if b == 0:
        return 0.0
    var lo_i = rank - step
    var hi_i = rank + step
    if lo_i < 0:
        lo_i = 0
    if hi_i > b - 1:
        hi_i = b - 1
    return 0.5 * (sorted_stats[hi_i] - sorted_stats[lo_i])


@fieldwise_init
struct PermutationTest(Copyable, Movable):
    """A two-sample permutation test on the difference of means, reproducibly.

    `p_value` is `(1 + count) / (1 + n_permutations)` — never zero, because zero is not a
    p-value a finite permutation test can produce. `p_value_floor` is `1 / (1 + B)`, the
    smallest value this B could ever return, so a caller can tell "the effect is stronger
    than every permutation" from "p is 0.0005".

    `count_at_least_as_extreme` is the raw count, reported so the corrected estimator can be
    recomputed under a different convention without rerunning the test.

    `seed`, `stream` and `n_permutations` make the number reproducible; rerunning with the
    same three gives a bitwise identical p-value.
    """

    var status: Int
    var n1: Int
    var n2: Int
    var n_permutations: Int
    var seed: UInt64
    var stream: UInt64
    var mean1: Float64
    var mean2: Float64
    var observed_diff: Float64
    var count_at_least_as_extreme: Int
    var p_value: Float64
    var p_value_floor: Float64


def _perm_failure(
    code: Int, n1: Int, n2: Int, b: Int, seed: UInt64, stream: UInt64
) -> PermutationTest:
    return PermutationTest(
        code, n1, n2, b, seed, stream, 0.0, 0.0, 0.0, 0, -1.0, -1.0
    )


def permutation_test_flat(
    values: List[Float64], n1: Int, n2: Int,
    n_permutations: Int, seed: UInt64, stream: UInt64,
) -> PermutationTest:
    """Two-sided permutation test that two groups share a mean, with a reproducible p-value.

    `values` is the two groups concatenated: the first `n1` entries are group one, the next
    `n2` are group two, and `len(values)` must be exactly `n1 + n2` — a longer payload is
    `INF_ERR_SHAPE` rather than a silently ignored tail, because a group boundary the caller
    got wrong is not something to guess at.

    Permutation `r` is `determinism.sampling_keyed.permutation_keyed` at draw coordinate
    `r * (n1 + n2 - 1)`, which is exactly the number of draws one Fisher-Yates pass over
    `n1 + n2` items consumes, so no two permutations share a coordinate and the whole test
    is a pure function of `(seed, stream, n_permutations)`.

    `stats_bootstrap.bootstrap_test` computes the same quantity and is NOT called: it draws
    from process-global randomness, so one call would make this result irreproducible, and
    it returns `count / B`, which can be `0.0`.

    @capability permutation_test_flat
    complexity: O(n_permutations * (n1 + n2))
    counts:
    - n1 + n2 == len(values) [kernel_validated]
    @endcapability
    """
    if n1 <= 0 or n2 <= 0:
        return _perm_failure(INF_ERR_EMPTY, n1, n2, n_permutations, seed, stream)
    if n1 > MAX_INFERENCE_OBS or n2 > MAX_INFERENCE_OBS:
        return _perm_failure(
            INF_ERR_DIMENSION_TOO_LARGE, n1, n2, n_permutations, seed, stream
        )
    var total = n1 + n2
    if len(values) != total:
        return _perm_failure(INF_ERR_SHAPE, n1, n2, n_permutations, seed, stream)
    for i in range(total):
        if not inference_finite(values[i]):
            return _perm_failure(
                INF_ERR_NON_FINITE, n1, n2, n_permutations, seed, stream
            )
    if n_permutations <= 0 or n_permutations > MAX_RESAMPLES:
        return _perm_failure(
            INF_ERR_RESAMPLE_COUNT, n1, n2, n_permutations, seed, stream
        )
    if not inference_product_fits(n_permutations, total, MAX_RESAMPLE_WORK):
        return _perm_failure(
            INF_ERR_DIMENSION_TOO_LARGE, n1, n2, n_permutations, seed, stream
        )

    var sum1: Float64 = 0.0
    for i in range(n1):
        sum1 += values[i]
    var sum2: Float64 = 0.0
    for i in range(n1, total):
        sum2 += values[i]
    var mean1 = sum1 / Float64(n1)
    var mean2 = sum2 / Float64(n2)
    var observed = fabs(mean1 - mean2)

    var stride = total - 1
    var count = 0
    for r in range(n_permutations):
        var order = permutation_keyed(total, seed, stream, UInt64(r * stride))
        if len(order) != total:
            return _perm_failure(
                INF_ERR_SHAPE, n1, n2, n_permutations, seed, stream
            )
        var a: Float64 = 0.0
        for i in range(n1):
            a += values[order[i]]
        var b: Float64 = 0.0
        for i in range(n1, total):
            b += values[order[i]]
        var diff = fabs(a / Float64(n1) - b / Float64(n2))
        # `>=` and not `>`: a permutation exactly as extreme as the observed split is
        # evidence for the null, and the observed split is itself one of the permutations.
        if diff >= observed:
            count += 1

    var bf = Float64(n_permutations)
    return PermutationTest(
        INF_OK, n1, n2, n_permutations, seed, stream, mean1, mean2,
        mean1 - mean2, count,
        (1.0 + Float64(count)) / (1.0 + bf), 1.0 / (1.0 + bf),
    )
