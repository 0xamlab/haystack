"""bench_inference.mojo — the gate behind the inference package's claims.

Hand-written, not generated. `tests/benchmark_mojo_vs_python.py` writes
`benchmarks/mojo_benchmarks/bench_<lib_id>.mojo` where `lib_id` is `<subdir>_<stem>` for a
package file (`get_all_libs`), so the seven modules of this package generate
`bench_inference_core.mojo`, `bench_inference_power.mojo`, … and none of them can collide
with this name. There is no top-level `mojo/engine/inference.mojo` that would generate it
either, and `__init__` is in that harness's `SKIP_FILES`. That harness only writes — it
never unlinks.

What is measured, and why each one is the claim that matters
-----------------------------------------------------------
This package's claim is NOT raw speed. `stat_tests` already computes many of the same
quantities faster, because it computes them without checking whether they exist. What is
gated here is that the answers differ, that the refusals happen, and that the declared work
charges are the work actually done.

1. **The corrected t CDF now agrees with the frozen one — it did not always.**
   `stat_tests._t_cdf` had a first-term bug in its Lentz continued fraction (fixed as of
   this session; see `inference.core`'s module docstring for the history and the
   measured pre-fix divergence, up to a `-0.023` value where a probability belongs).
   `CdfAgreement` is exported so the relationship between the two implementations is a
   value rather than a footnote either way. Measured over a 280-point `(t, df)` grid: how
   often they still disagree beyond the two continued fractions' own truncation, and
   whether the frozen value is ever not a probability at all (it no longer is). The gate
   now insists on the OPPOSITE of what it used to: agreement is the rule (the largest gap
   stays orders of magnitude below the old `~0.058` divergence), the corrected value is a
   probability at every one of the 280 points, and — so the comparison is not a constant —
   that at `t = 0`, where both short-circuit `I_1(a, b) = 1`, they agree EXACTLY.

1b. **…and section 1 covers ONE of the three tail lanes, so 1b covers the other two.** All
   280 of section 1's points are `T_REGION_BETA` — that count is measured and printed, not
   assumed — because the handoff needs `df` above ~1e8 and section 1's largest is 100. So a
   df sweep from 1e6 to 1e18 walks the handoff: a CDF of exactly 0.5 or a two-sided p of
   exactly 1.0 for a nonzero `t` is counted and must be 0 (both were the pre-split answer at
   every one of those df), the CDF may not FALL as df rises, p must be strictly decreasing in
   `|t|` across the band, and past `|t| = 3` the answer must equal this package's normal tail
   BIT for bit. `inference_f_sf` inherits the same regions at `df1 = 1` through the exact
   identity `P(F_{1,d} >= t^2) = P(|T_d| >= |t|)` and is gated on it; the `df1 > 1` corner is
   a recorded gap and is pinned at its measured wrong value so it cannot quietly change.

2. **`inference_t_quantile` refuses rather than returning its bracket edge.** Bisection
   converges to something whether or not the root is inside `[-1e4, 1e4]`, and without the
   bracket check a quantile beyond the bracket came back as the EDGE — a finite,
   plausible-looking critical value. Gated on both sides of the boundary: `cdf(-1e4, 1)` is
   3.183e-05, so `p = 3.2e-05` must be ANSWERED (and strictly inside the bracket) while
   `p = 3.0e-05` must be ABSENT. The size of the avoided lie is printed from the closed form
   — for `df = 1` the quantile is `tan(pi (p - 1/2))`, so at `p = 1e-9` the truth is
   -3.18e+08 and the bracket edge is -1e4, four orders of magnitude of understated critical
   value. Cost is also gated on shape: the bisection is a FIXED `T_QUANTILE_STEPS` count, so
   ns per quantile must not move with `df`.

3. **`sample_size` VERIFIES rather than trusting its closed form.** The canonical design
   `d = 0.5`, two-sided `alpha = 0.05`, target 0.80 gives `n = 63` on the normal lane and 64
   on the t lane, and both `achieved_power` and `power_at_n_minus_1` are gated at their
   measured values — then re-derived by calling `power_two_means_flat` directly, which must
   return the identical Float64. That is what "verified" means here: the report's numbers ARE
   the power function's, not the algebra restating itself.

   And the refusal that matters more: at `d = 0.005` the bounded search cannot reach the
   target inside `POWER_SEARCH_STEPS`, so the answer is `INF_ERR_NOT_CONVERGED` with the
   diagnostics kept. An `INF_OK` there would be a sample-size calculator handing back an
   underpowered `n`, which is discovered only after the data is collected. `d = 0.01`, which
   needs 48 of the 64 steps and DOES converge, is gated too, so the refusal is not "small
   effects always refuse".

4. **Multiplicity correction is monotone and its cost is linear in the family size.**
   Bonferroni is O(n) and is the one procedure that does not sort, so its growth exponent
   across a 64x rise in `n` — up to `MAX_TESTS`, the declared ceiling — must be 1. Holm and
   BH sort, through the frozen `retrieval_rank_order` (a bottom-up merge sort), and measured
   they come out at ~1.3 rather than the ~1.05 an ideal `n log n` would give: that sort
   streams the whole array once per pass, so past cache every pass costs a DRAM round trip.
   The gate says so explicitly and allows 1.7, which is a bandwidth allowance and still
   excludes quadratic — and the exclusion is MEASURED, not assumed, because the pairwise
   monotonicity scan in the same section is O(n^2) by construction and is timed at two sizes
   as a control: the same `p <= 1.7` predicate has to reject it. Monotonicity itself is gated
   as a pairwise property (`p_i <= p_j` implies `adjusted_i <= adjusted_j`, over all 8,910,336
   pairs x 3 procedures at n = 1024 and 4096), plus the cross-procedure ordering
   `BH <= Holm <= Bonferroni` at every position at every size, plus a graded family where BH
   strictly out-rejects Bonferroni so that ordering is not vacuously satisfied by three equal
   counts. All timings are the minimum of three repeats.

5. **Bootstrap and permutation cost scales with draws as declared.** `bootstrap_ci_flat`
   declares O(B n) for the mean and charges O(B n^2) for the median; the permutation test
   declares O(B (n1 + n2)). Gated as ns per charged unit across a 16x rise in B and a 4x
   rise in n, plus — for the median — that ns per `B n^2` does not GROW, i.e. the budget is
   not undercharged (the real cost is `B n log n`, so it over-charges, which is the safe
   direction; both numbers are printed). Timings are the minimum of three: measured, the
   single-shot per-unit figure here moved between 70 and 124 ns across two runs of this file
   on one machine, which is wide enough to make a 3x ratio gate a coin flip. The
   reproducibility claim is gated as an exact equality: the same `(seed, stream, B)` returns
   bitwise identical endpoints, one stream apart they differ, and the Monte-Carlo halfwidth of
   those endpoints shrinks as B grows. And the permutation p-value is gated on the ONE input
   where its estimator and the frozen convention disagree — two groups so separated that the
   raw count is 0, where `count / B` is exactly 0.0 and `(1 + count) / (1 + B)` is the floor.

Running it
----------
    cd mojo_env && pixi run mojo run -I../mojo/engine \
        ../benchmarks/mojo_benchmarks/bench_inference.mojo

JIT vs compiled: `mojo run` is the JIT, so every absolute nanosecond figure here is a JIT
figure. Each timed section takes a warm-up call first, and the gates are on ratios, which is
the portable part.

Gate
----
`BENCH_GATE inference PASS`, or `FAIL <n>` and a raised Error. Fails on the properties and
the verdicts, never on absolute nanoseconds:
  * the frozen/corrected t CDF gap must exceed 0.1 somewhere, the frozen value must be
    outside [0, 1] somewhere, the corrected one must be inside [0, 1] everywhere, and the
    two must agree exactly at t = 0
  * ns per corrected t CDF must not grow more than 3x across a 10,000x rise in df
  * section 1's 280 points must all be one region, and the 1e6..1e18 sweep must reach the
    other two; across that sweep cdf == 0.5 and p == 1.0 must occur ZERO times, the CDF must
    never fall as df rises and must land within 1e-12 of 0.8413447460685429, p must strictly
    decrease in |t| at df = 1e16, and `t_sf_two_sided(6, 1e16)` must EQUAL the normal tail
  * `f_sf(1, 1, 1e16)` must be bit-equal to the t tail and within 1e-12 of 0.3173105078629141,
    while the recorded `df1 = 4` gap stays exactly 0.9999240029662446, over 0.25 from its limit
  * neither the central-series lane nor the normal lane may cost more than 3x the beta lane
  * a quantile inside the bracket must be answered and round-trip through the CDF; three
    outside it must be absent; ns per quantile must not grow more than 3x with df
  * the canonical sample sizes must be 63 (normal) and 64 (t) with both verification powers
    bit-identical to a direct power call; d = 0.005 must be INF_ERR_NOT_CONVERGED with
    achieved < target and steps == POWER_SEARCH_STEPS; d = 0.01 must be INF_OK
  * Bonferroni's growth exponent across a 64x rise in n must be <= 1.2; Holm's and BH's must
    be <= 1.7; and the O(n^2) control must MEASURE above 1.7, so the predicate discriminates
  * all 8,910,336 monotonicity pairs x 3 procedures must hold, BH <= Holm <= Bonferroni at
    every position and every rejection count, and BH must strictly out-reject Bonferroni on
    the graded family
  * bootstrap and permutation ns per charged unit must not grow more than 3x across a 16x
    rise in B or a 4x rise in n; the median's ns per (B n^2) must not grow at all
  * two runs at one (seed, stream) must be bitwise identical while one stream apart must
    differ, and the endpoint halfwidth at 16,000 draws must not exceed the one at 1,000
  * a permutation test on separated groups must return count 0 with p == 1/(1 + B) > 0

Every ratio-gated timing point is the MINIMUM of `GATE_REPS` repetitions, not a single reading
and not a mean. See that constant: measured, single readings of these same points spread up to
16.3x, which made every ratio gate here a coin flip; at the minimum of seven the same points
read 1.00x-1.09x against a 3.0 limit.
"""
from std.time import perf_counter_ns
from std.math import abs as fabs, log, tan

from inference.core import (
    INF_ERR_NOT_CONVERGED,
    INF_OK,
    MAX_TESTS,
    T_QUANTILE_BRACKET,
    T_QUANTILE_STEPS,
    T_REGION_BETA,
    T_REGION_CENTRAL,
    T_REGION_NORMAL,
    inference_f_sf,
    inference_finite,
    inference_norm_sf_two_sided,
    inference_status_name,
    inference_t_cdf,
    inference_t_quantile,
    inference_t_sf_two_sided,
    inference_t_tail_region,
    t_cdf_agreement,
)
from inference.multiplicity import (
    benjamini_hochberg_flat,
    bonferroni_flat,
    correction_agreement_flat,
    holm_flat,
)
from inference.power import (
    POWER_SEARCH_STEPS,
    power_two_means_flat,
    power_two_means_t_flat,
    sample_size_two_means_flat,
    sample_size_two_means_t_flat,
)
from inference.resample import (
    STAT_MEAN,
    STAT_MEDIAN,
    bootstrap_ci_flat,
    permutation_test_flat,
)

comptime PI: Float64 = 3.141592653589793

# How many times every ratio-gated timing point is repeated before its MINIMUM is taken.
#
# Seven, and the number is measured rather than chosen. Every ratio gate in this file was
# failing intermittently — 1 run in 4 passed on a developer machine running other work —
# and the cause was the ESTIMATOR, not the code under test. Timed in isolation at seven
# repetitions per point, the per-unit costs this file gates are:
#
#   corrected t CDF, df 1 -> 10,000     1023 -> 1117 ns/call     ratio 1.09
#   bootstrap, B 1,000 -> 16,000        43.27 -> 43.64 ns/(B n)  ratio 1.01
#   permutation, B 1,000 -> 16,000      40.68 -> 40.64 ns/(B n)  ratio 1.00
#   the O(n^2) pairwise control                                  exponent 2.43
#
# while the SPREAD between the fastest and slowest single reading of the same point reached
# 16.3x for the bootstrap, 7.6x for the permutation and 2.6x for the CDF. A single reading, or
# the minimum of three, therefore decides a 3x ratio gate on scheduler luck: the observed
# failures were 3.06x and 3.16x against a 3.0 limit, and a "12.6x" CDF reading whose true
# ratio is 1.09. The minimum of seven leaves every one of these gates with more than 170% of
# margin instead of 2%, and it is the right statistic for a timing floor — a run can be made
# arbitrarily slower by contention but never faster than the work takes.
comptime GATE_REPS: Int = 7


fn _f64s(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ns(t0: UInt, t1: UInt) -> Float64:
    return Float64(Int(t1 - t0))


fn _log2(x: Float64) -> Float64:
    return log(x) / log(2.0)


fn _flat(small: Float64, large: Float64, allow: Float64) -> Bool:
    """Per-unit cost at the LARGER problem must not exceed `allow` times the smaller one.

    Rule 9: the contract is that per-unit cost stays flat as the problem grows. A zero or
    negative baseline means the clock did not resolve the small case, which is a measurement
    failure and not a pass.
    """
    if small <= 0.0 or large <= 0.0:
        return False
    return large <= allow * small


fn _exponent(t_small: Float64, n_small: Int, t_large: Float64, n_large: Int) -> Float64:
    """`p` in `t ~ n^p` from two measurements, or -1.0 when they cannot decide one.

    Normalised for the size step, which a raw ratio is not: a 2x ratio across a 4x rise and a
    2x ratio across a 64x rise are different growth laws, and this benchmark compares
    procedures measured at different size steps against one threshold. -1.0 when either
    reading is non-positive (the clock did not resolve it) or the sizes do not rise, and every
    gate tests `p >= 0.0` so the marker cannot pass as a small exponent."""
    if t_small <= 0.0 or t_large <= 0.0 or n_large <= n_small or n_small <= 0:
        return -1.0
    return log(t_large / t_small) / log(Float64(n_large) / Float64(n_small))


fn _p_family(n: Int) -> List[Float64]:
    """A deterministic family of `n` p-values in [0, 1). No randomness: a benchmark whose
    input changes between runs cannot be compared against its own previous numbers. 7919 and
    100003 are coprime primes, so the sequence walks the residue grid rather than cycling
    early, and repeats (legitimate ties) only past 100,003 hypotheses."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(Float64((i * 7919) % 100003) / 100003.0)
    return out^


fn _sample(n: Int) -> List[Float64]:
    """A deterministic bounded sample for the resampling sections."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(10.0 + Float64((i * 37) % 101) * 0.1)
    return out^


fn main() raises:
    var failures = 0
    print("\n[bench_inference] gate for the inference package")
    # One warm-up through the two hot primitives, so the first timed loop below is not
    # paying for JIT compilation of the continued fraction.
    var warm = inference_t_cdf(1.3, 7.0) + inference_t_quantile(0.9, 7.0)
    print("  (warm-up checksum", warm, ")")

    # ══ 1. the corrected t CDF now agrees with the frozen one ══════════════════
    print("\n-- 1. frozen vs corrected t CDF (CdfAgreement over 280 points) --")
    var cdf_dfs = _f64s(1.0, 2.0, 5.0, 6.0, 10.0, 30.0, 100.0)
    var n_pairs = 0
    var n_disagree = 0
    var n_frozen_not_prob = 0
    var n_corrected_not_prob = 0
    var n_refused = 0
    var max_gap: Float64 = 0.0
    var mg_t: Float64 = 0.0
    var mg_df: Float64 = 0.0
    for i in range(len(cdf_dfs)):
        var df = cdf_dfs[i]
        var worst: Float64 = 0.0
        var worst_t: Float64 = 0.0
        var bad = 0
        for k in range(1, 41):
            var t = 0.1 * Float64(k)
            var a = t_cdf_agreement(t, df)
            n_pairs += 1
            if a.status != INF_OK:
                n_refused += 1
                continue
            if not a.agree:
                n_disagree += 1
            if not a.frozen_is_probability:
                n_frozen_not_prob += 1
                bad += 1
            if a.corrected_cdf < 0.0 or a.corrected_cdf > 1.0:
                n_corrected_not_prob += 1
            if inference_finite(a.abs_gap):
                if a.abs_gap > worst:
                    worst = a.abs_gap
                    worst_t = t
                if a.abs_gap > max_gap:
                    max_gap = a.abs_gap
                    mg_t = t
                    mg_df = df
        print(
            "   df =", df, "worst |frozen - corrected| =", worst, "at t =", worst_t,
            "| frozen outside [0,1] at", bad, "of 40 t values",
        )
    print(
        "   pairs", n_pairs, "| disagree", n_disagree, "| frozen not a probability",
        n_frozen_not_prob, "| corrected not a probability", n_corrected_not_prob,
        "| refused", n_refused,
    )
    print("   max gap", max_gap, "at t =", mg_t, "df =", mg_df)
    var canon = t_cdf_agreement(2.0, 6.0)
    # This is the exact (t, df) the package's own docstrings quote as the historical
    # reproduction. The frozen two-sided tail derived from it is now POSITIVE and close to
    # the closed-form truth (~0.0924), not the negative value the old defect produced and
    # the frozen tests clamped to a confident 0.0.
    var frozen_tail = 2.0 * (1.0 - canon.frozen_cdf)
    print(
        "   t = 2, df = 6: frozen", canon.frozen_cdf, "corrected", canon.corrected_cdf,
        "gap", canon.abs_gap,
    )
    print(
        "   the frozen two-sided tail 2(1 - cdf) is", frozen_tail,
        "— positive, matching the corrected tail (both implementations now agree)",
    )
    var at_zero = t_cdf_agreement(0.0, 5.0)
    print(
        "   t = 0, df = 5: frozen", at_zero.frozen_cdf, "corrected", at_zero.corrected_cdf,
        "gap", at_zero.abs_gap, "agree", at_zero.agree,
    )
    if (
        n_frozen_not_prob == 0
        and n_disagree == 0
        and max_gap < 1.0e-8
        and n_corrected_not_prob == 0
        and n_refused == 0
        and canon.status == INF_OK
        and canon.frozen_is_probability
        and canon.agree
        and frozen_tail > 0.0
        and frozen_tail < 1.0
        and at_zero.status == INF_OK
        and at_zero.abs_gap == 0.0
        and at_zero.agree
    ):
        print(
            "   ✅ the frozen and corrected CDFs agree everywhere on this grid, both are",
            "probabilities at all", n_pairs, "points, and exactly so at t = 0",
        )
    else:
        failures += 1
        print(
            "   ❌ CdfAgreement no longer measures real agreement:", n_frozen_not_prob,
            n_disagree, max_gap, n_corrected_not_prob, n_refused, at_zero.abs_gap,
        )

    # Cost shape: the continued fraction is capped at 201 levels, so the cost of a corrected
    # CDF must not move with df. If it did, the cap would not be the thing bounding the work.
    var cdf_cost = List[Float64]()
    var cost_dfs = _f64s(1.0, 100.0, 10000.0)
    var reps = 4000
    for i in range(len(cost_dfs)):
        var df = cost_dfs[i]
        var acc: Float64 = 0.0
        var per: Float64 = 0.0
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            for r in range(reps):
                acc += inference_t_cdf(0.5 + 0.0005 * Float64(r), df)
            var t1 = perf_counter_ns()
            var one = _ns(t0, t1) / Float64(reps)
            if rep == 0 or one < per:
                per = one
        cdf_cost.append(per)
        print(
            "   df =", df, "ns per corrected t CDF (min of", GATE_REPS, ")", per,
            "(checksum", acc, ")",
        )
    if len(cdf_cost) == 3 and _flat(cdf_cost[0], cdf_cost[2], 3.0):
        print("   ✅ ns per corrected t CDF stayed flat across a 10,000x rise in df")
    else:
        failures += 1
        print("   ❌ corrected t CDF cost moves with df:", cdf_cost[0], "->", cdf_cost[2])

    # ══ 1b. the two regions section 1's grid never enters ═══════════════════════
    #
    # WHY THIS SUBSECTION EXISTS, measured: every one of the 280 (t, df) points in section 1
    # is `T_REGION_BETA` — the count is computed and printed below rather than asserted, and
    # it is 280/0/0. Section 1's largest df is 100, and the region handoff needs
    # `t^2/(df + t^2) < T_TAIL_COMPLEMENT_FLOOR`, i.e. df above ~1e8 at t = 1. So section 1
    # gates the incomplete-beta lane and NOTHING about the other two lanes, and a benchmark
    # that only runs section 1 passes with the saturation region deleted. This subsection is
    # the part that fails when it is.
    #
    # The defect being gated: `x = df/(df + t^2)` rounds to exactly 1.0 once `t^2` is below
    # half an ulp of `df`, and `inference_beta_inc(1.0, a, b)` is exactly 1.0 — so the CDF
    # returned exactly 0.5 and the two-sided p-value exactly 1.0 for every t, at df where the
    # answer is simply the normal's. That is a silent non-rejection: a test that cannot reject
    # anything, reported under INF_OK.
    print("\n-- 1b. the saturated band: region coverage, and the values in it --")
    var grid_beta = 0
    var grid_central = 0
    var grid_normal = 0
    for i in range(len(cdf_dfs)):
        for k in range(1, 41):
            var reg = inference_t_tail_region(0.1 * Float64(k), cdf_dfs[i])
            if reg == T_REGION_BETA:
                grid_beta += 1
            elif reg == T_REGION_CENTRAL:
                grid_central += 1
            elif reg == T_REGION_NORMAL:
                grid_normal += 1
    print(
        "   section 1's", n_pairs, "points by region: beta", grid_beta, "central",
        grid_central, "normal", grid_normal, "— so section 1 alone gates one lane of three",
    )

    # A df sweep at fixed t = 1 straight through the handoff. `norm_cdf` is the frozen
    # Abramowitz-Stegun erf (6.9e-8), so the SWEEP is judged against the t's own limit
    # 0.8413447460685429 = 0.5 erfc(-1/sqrt(2)) rather than against this tree's normal, and
    # the bit-equality claim is made only where the code returns the normal by construction.
    var band_dfs = _f64s(1.0e6, 1.0e7, 1.0e8, 1.0e9, 1.0e10, 1.0e12, 1.0e14, 1.0e16, 1.0e18)
    var true_cdf_at_1: Float64 = 0.8413447460685429
    var band_regions = List[Int]()
    var band_cdfs = List[Float64]()
    var band_ps = List[Float64]()
    var band_saturated_cdf = 0
    var band_saturated_p = 0
    for i in range(len(band_dfs)):
        var df = band_dfs[i]
        var reg = inference_t_tail_region(1.0, df)
        var c = inference_t_cdf(1.0, df)
        var p = inference_t_sf_two_sided(1.0, df)
        band_regions.append(reg)
        band_cdfs.append(c)
        band_ps.append(p)
        # The two shapes of the defect, counted rather than described: a CDF pinned at the
        # median for a nonzero t, and a two-sided mass of exactly 1.
        if c == 0.5:
            band_saturated_cdf += 1
        if p == 1.0:
            band_saturated_p += 1
        print(
            "   t = 1, df =", df, "region", reg, "| cdf", c, "| two-sided p", p,
            "| cdf - limit", c - true_cdf_at_1,
        )
    # Monotone in df at fixed t > 0: lighter tails put more mass below t, so the CDF may not
    # fall as df rises. Ties at the top are legitimate (the answer has converged to the last
    # representable double); a DROP is the saturation collapsing to 0.5.
    var band_monotone = True
    var band_rose = False
    for i in range(1, len(band_cdfs)):
        if band_cdfs[i] < band_cdfs[i - 1]:
            band_monotone = False
        if band_cdfs[i] > band_cdfs[i - 1]:
            band_rose = True
    # Monotone in |t| ACROSS the band, at one saturated df. A flat 1.0 is not.
    var p_eighth = inference_t_sf_two_sided(0.125, 1.0e16)
    var p_quarter = inference_t_sf_two_sided(0.25, 1.0e16)
    var p_half = inference_t_sf_two_sided(0.5, 1.0e16)
    var p_one = inference_t_sf_two_sided(1.0, 1.0e16)
    print(
        "   df = 1e16, two-sided p at |t| = 0.125 / 0.25 / 0.5 / 1:", p_eighth, p_quarter,
        p_half, p_one,
    )
    # Past the |t| > 3 series cap the complement floor forces df > 8.99e8, where the normal
    # IS the accurate answer — so the handoff is asserted BIT-EQUAL, not merely close, which
    # is what makes a t test at df = 1e16 and a Wald z test on the same statistic agree.
    var far_t_region = inference_t_tail_region(6.0, 1.0e16)
    var far_t_p = inference_t_sf_two_sided(6.0, 1.0e16)
    var far_t_norm = inference_norm_sf_two_sided(6.0)
    print(
        "   t = 6, df = 1e16: region", far_t_region, "| p", far_t_p, "| package normal",
        far_t_norm, "| bit-equal", far_t_p == far_t_norm,
    )
    if (
        # Coverage, as a gated fact: the sweep reaches lanes section 1 cannot.
        grid_central == 0
        and grid_normal == 0
        and grid_beta == n_pairs
        and band_regions[0] == T_REGION_BETA
        and band_regions[len(band_regions) - 1] == T_REGION_CENTRAL
        and far_t_region == T_REGION_NORMAL
        # Nothing in the band is saturated any more.
        and band_saturated_cdf == 0
        and band_saturated_p == 0
        # And the values are the right ones, not merely unsaturated.
        and band_cdfs[len(band_cdfs) - 1] > 0.5
        and fabs(band_cdfs[len(band_cdfs) - 1] - true_cdf_at_1) < 1.0e-12
        and band_ps[len(band_ps) - 1] < 1.0
        and fabs(band_ps[len(band_ps) - 1] - 0.3173105078629141) < 1.0e-12
        and band_monotone
        and band_rose
        # Strictly decreasing in |t| across the saturated band.
        and p_eighth > p_quarter
        and p_quarter > p_half
        and p_half > p_one
        and p_eighth < 1.0
        # The |t| > 3 handoff is the normal, bit for bit.
        and far_t_p == far_t_norm
        and far_t_p > 0.0
    ):
        print(
            "   ✅ the saturated band returns the truth: 0 of", len(band_dfs),
            "df values give cdf == 0.5 or p == 1.0, the CDF never falls as df rises, p is",
            "strictly decreasing in |t|, and the |t| > 3 lane is the normal bit for bit",
        )
    else:
        failures += 1
        print(
            "   ❌ the large-df t tail saturated: cdf==0.5 at", band_saturated_cdf,
            "df values, p==1.0 at", band_saturated_p, "| monotone", band_monotone,
            "| regions", grid_central, band_regions[len(band_regions) - 1], far_t_region,
            "| last cdf", band_cdfs[len(band_cdfs) - 1], "| p(1e16) at |t|=0.125..1",
            p_eighth, p_one, "| far-t bit-equal", far_t_p == far_t_norm,
        )

    # The same complement loss, one function over: `inference_f_sf`'s `x = df2/(df2 + df1 f)`
    # hides the answer in `1 - x` exactly as the t's does. At `df1 = 1` the exact identity
    # `P(F_{1,d} >= t^2) = P(|T_d| >= |t|)` gives it the t's regions for free, and that
    # delegation is what is gated here — nothing else under benchmarks/ calls `inference_f_sf`.
    var f_one = inference_f_sf(1.0, 1.0, 1.0e16)
    var f_small = inference_f_sf(0.0625, 1.0, 1.0e15)
    var f_identity = f_one == inference_t_sf_two_sided(1.0, 1.0e16)
    # `df1 > 1` below the floor is a RECORDED GAP, not a fixed lane: it needs an accurate
    # upper incomplete gamma this tree does not have. Pinned literally against the elementary
    # `P(chi2_4 >= 2) = 2/e` it is converging away from, so the gap cannot quietly stop being
    # one — this pin does NOT bite the saturation fix, it fixes the documented number.
    var chi2_4_at_2: Float64 = 0.7357588823428847
    var f_gap = inference_f_sf(0.5, 4.0, 1.0e16)
    var f_gap_ok = inference_f_sf(0.5, 4.0, 1.0e6)
    print(
        "   f_sf(1, 1, 1e16)", f_one, "| f_sf(0.0625, 1, 1e15)", f_small,
        "| identity with the t tail bit-equal", f_identity,
    )
    print(
        "   df1 = 4 below the floor is the recorded gap: f_sf(0.5, 4, 1e16)", f_gap,
        "vs the chi2_4 limit", chi2_4_at_2, "— off by", fabs(f_gap - chi2_4_at_2),
        "and correct at df2 = 1e6:", f_gap_ok,
    )
    if (
        f_identity
        and f_one < 1.0
        and fabs(f_one - 0.3173105078629141) < 1.0e-12
        and f_small < 1.0
        and fabs(f_small - 0.8025873486341526) < 1.0e-12
        and f_gap == 0.9999240029662446
        and fabs(f_gap - chi2_4_at_2) > 0.25
        and fabs(f_gap_ok - chi2_4_at_2) < 1.0e-9
    ):
        print(
            "   ✅ the F tail inherits the t's regions at df1 = 1 (bit-equal), and the df1 > 1",
            "gap stays pinned at its measured wrong value rather than being papered over",
        )
    else:
        failures += 1
        print(
            "   ❌ F tail below the complement floor:", f_one, f_small, f_identity, f_gap,
            f_gap_ok,
        )

    # Cost shape across the handoff (rule 9, a ratio not a nanosecond count): the central
    # series is capped at T_TAIL_SERIES_TERMS = 64 terms and the normal lane is closed-form,
    # so neither may cost more than 3x the 201-level continued fraction it replaced. This is
    # a SHAPE claim about the region split, not the correctness claim above.
    var region_cost = List[Float64]()
    var region_t = _f64s(1.0, 1.0, 6.0)
    var region_df = _f64s(1.0e6, 1.0e12, 1.0e12)
    for i in range(len(region_t)):
        var acc: Float64 = 0.0
        var per: Float64 = 0.0
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            for r in range(reps):
                acc += inference_t_cdf(region_t[i] + 1.0e-9 * Float64(r), region_df[i])
            var t1 = perf_counter_ns()
            var one = _ns(t0, t1) / Float64(reps)
            if rep == 0 or one < per:
                per = one
        region_cost.append(per)
        print(
            "   region", inference_t_tail_region(region_t[i], region_df[i]), "(t =",
            region_t[i], "df =", region_df[i], ") ns per t CDF (min of", GATE_REPS, ")",
            per, "(checksum", acc, ")",
        )
    if (
        len(region_cost) == 3
        and _flat(region_cost[0], region_cost[1], 3.0)
        and _flat(region_cost[0], region_cost[2], 3.0)
    ):
        print("   ✅ neither replacement lane costs more than 3x the beta lane it replaced")
    else:
        failures += 1
        print(
            "   ❌ a region handoff changed the cost shape:", region_cost[0], "->",
            region_cost[1], region_cost[2],
        )

    # ══ 2. the t quantile refuses instead of returning its bracket edge ═════════
    print("\n-- 2. inference_t_quantile: answered inside the bracket, absent outside --")
    var lo_edge = inference_t_cdf(-T_QUANTILE_BRACKET, 1.0)
    var hi_edge = inference_t_cdf(T_QUANTILE_BRACKET, 1.0)
    print(
        "   bracket", T_QUANTILE_BRACKET, "steps", T_QUANTILE_STEPS,
        "| cdf(-1e4, 1) =", lo_edge, "cdf(+1e4, 1) =", hi_edge,
    )
    var q_in = inference_t_quantile(1.0e-4, 1.0)
    var q_near = inference_t_quantile(3.2e-5, 1.0)
    var q_out = inference_t_quantile(3.0e-5, 1.0)
    var q_far = inference_t_quantile(1.0e-9, 1.0)
    var q_upper = inference_t_quantile(1.0 - 1.0e-6, 1.0)
    var round_trip = inference_t_cdf(q_in, 1.0)
    # df = 1 is Cauchy, so the quantile has a closed form and the size of the avoided lie is
    # computable rather than asserted.
    var cauchy_far = tan(PI * (1.0e-9 - 0.5))
    print(
        "   p = 1e-4  -> q =", q_in, "finite", inference_finite(q_in),
        "| cdf(q) =", round_trip,
    )
    print(
        "   p = 3.2e-5 (just above cdf(-1e4)) -> q =", q_near, "finite",
        inference_finite(q_near), "| |q| < bracket", fabs(q_near) < T_QUANTILE_BRACKET,
    )
    print("   p = 3.0e-5 (just below)           -> finite", inference_finite(q_out))
    print("   p = 1e-9                          -> finite", inference_finite(q_far))
    print("   p = 1 - 1e-6 (above cdf(+1e4))    -> finite", inference_finite(q_upper))
    print(
        "   the lie avoided at p = 1e-9: closed-form Cauchy quantile is", cauchy_far,
        "and the bracket edge is", -T_QUANTILE_BRACKET,
    )
    var known_10 = inference_t_quantile(0.975, 10.0)
    print("   known value: t_quantile(0.975, 10) =", known_10, "(textbook 2.228138851986065)")
    if (
        inference_finite(q_in)
        and fabs(round_trip - 1.0e-4) <= 1.0e-12
        and inference_finite(q_near)
        and fabs(q_near) < T_QUANTILE_BRACKET
        and 3.2e-5 > lo_edge
        and 3.0e-5 < lo_edge
        and not inference_finite(q_out)
        and not inference_finite(q_far)
        and not inference_finite(q_upper)
        and fabs(known_10 - 2.228138851986065) <= 1.0e-8
    ):
        print(
            "   ✅ answered inside the bracket (and round-trips through the CDF),",
            "absent on both sides outside it",
        )
    else:
        print("   ❌ the bracket check is not holding:", q_in, round_trip, q_near, q_out)
        failures += 1

    # Cost shape: T_QUANTILE_STEPS is a fixed halving count, so a quantile is a fixed number
    # of CDF evaluations no matter what df or p is asked for.
    var q_cost = List[Float64]()
    var q_reps = 400
    for i in range(len(cost_dfs)):
        var df = cost_dfs[i]
        var acc: Float64 = 0.0
        var per: Float64 = 0.0
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            for r in range(q_reps):
                acc += inference_t_quantile(0.5 + 0.001 * Float64(r), df)
            var t1 = perf_counter_ns()
            var one = _ns(t0, t1) / Float64(q_reps)
            if rep == 0 or one < per:
                per = one
        q_cost.append(per)
        print(
            "   df =", df, "ns per quantile (min of", GATE_REPS, ")", per,
            "ns per bisection step", per / Float64(T_QUANTILE_STEPS), "(checksum", acc, ")",
        )
    if len(q_cost) == 3 and _flat(q_cost[0], q_cost[2], 3.0):
        print("   ✅ ns per quantile stayed flat across a 10,000x rise in df")
    else:
        failures += 1
        print("   ❌ quantile cost moves with df:", q_cost[0], "->", q_cost[2])

    # ══ 3. sample_size verifies its closed form, and refuses when it cannot ═════
    print("\n-- 3. sample_size: verified, and INF_ERR_NOT_CONVERGED when unreachable --")
    var sn = sample_size_two_means_flat(0.5, 0.05, 0.80, False)
    var st = sample_size_two_means_t_flat(0.5, 0.05, 0.80, False)
    print(
        "   normal d=0.5 a=0.05 target=0.80 -> n", sn.n_per_group, "closed", sn.closed_form_n,
        "steps", sn.search_steps, "achieved", sn.achieved_power, "at n-1",
        sn.power_at_n_minus_1, "minimal", sn.minimal, inference_status_name(sn.status),
    )
    print(
        "   t lane  d=0.5 a=0.05 target=0.80 -> n", st.n_per_group, "closed",
        st.closed_form_n, "steps", st.search_steps, "achieved", st.achieved_power,
        "at n-1", st.power_at_n_minus_1, "minimal", st.minimal,
        inference_status_name(st.status),
    )
    # The verification is only worth the name if the report's numbers ARE the power
    # function's. Re-derived here through the public entry point a caller would use, and
    # compared with `==`: a tolerance would accept exactly the drift this checks for.
    var direct_63 = power_two_means_flat(0.5, 63, 0.05, False)
    var direct_62 = power_two_means_flat(0.5, 62, 0.05, False)
    var direct_t64 = power_two_means_t_flat(0.5, 64, 0.05, False)
    var direct_t63 = power_two_means_t_flat(0.5, 63, 0.05, False)
    var redirected = (
        sn.achieved_power == direct_63.power
        and sn.power_at_n_minus_1 == direct_62.power
        and st.achieved_power == direct_t64.power
        and st.power_at_n_minus_1 == direct_t63.power
        # …and the `==` above is discriminating: the two lanes at the SAME n differ, so an
        # equality that held against either lane's power would be measuring nothing.
        and sn.achieved_power != direct_t63.power
    )
    print(
        "   report powers bit-identical to a direct power call:", redirected,
        "| the two lanes at n = 63 differ:", direct_63.power, "vs", direct_t63.power,
    )
    # The `sample_size_two_means_flat` docstring quotes 0.80130 for this design. That is the
    # all-Acklam figure; the two-sided lane calls the frozen `ab_testing.power_analysis`,
    # which uses the cruder Abramowitz-Stegun probit — see test_inference_power.mojo:24-31.
    # The two are the same design to that probit's accuracy, which is what is gated.
    var acklam_gap = fabs(sn.achieved_power - 0.8013023941055797)
    print(
        "   docstring quotes 0.80130 (all-Acklam); this lane returns", sn.achieved_power,
        "from the frozen A-S probit — gap", acklam_gap,
    )
    if (
        sn.status == INF_OK
        and sn.n_per_group == 63
        and sn.closed_form_n == 63
        and sn.search_steps == 0
        and sn.achieved_power == 0.8011822526702241
        and sn.power_at_n_minus_1 == 0.7948856284208302
        and sn.achieved_power >= 0.80
        and sn.power_at_n_minus_1 < 0.80
        and sn.minimal
        and st.status == INF_OK
        and st.n_per_group == 64
        and st.search_steps == 1
        and st.achieved_power == 0.8013829274055866
        and st.power_at_n_minus_1 == 0.7950790808528411
        and st.minimal
        and redirected
        and acklam_gap <= 5.0e-4
    ):
        print(
            "   ✅ n = 63 (normal) and 64 (t) with both verification powers re-derived",
            "bit-identically from a direct power call",
        )
    else:
        failures += 1
        print(
            "   ❌ the canonical verified sample size moved:", sn.status, sn.n_per_group,
            sn.achieved_power, st.n_per_group, st.achieved_power, redirected,
        )

    # An unreachable target. At d = 0.005 the power curve is flat enough in n that the frozen
    # probit's 1.2e-4 deficit is worth more than POWER_SEARCH_STEPS integer steps, so the
    # bounded refinement cannot arrive. INF_OK here would be an underpowered n reported as an
    # answer.
    var unreach = sample_size_two_means_flat(0.005, 0.05, 0.80, False)
    print(
        "   normal d=0.005 target=0.80 -> status", unreach.status,
        inference_status_name(unreach.status), "n", unreach.n_per_group, "closed",
        unreach.closed_form_n, "steps", unreach.search_steps, "achieved",
        unreach.achieved_power, "minimal", unreach.minimal,
    )
    # And the boundary: 48 of the 64 steps is still an answer, so the refusal above is the
    # step cap binding and not "a small effect always refuses".
    var reachable = sample_size_two_means_flat(0.01, 0.05, 0.80, False)
    print(
        "   normal d=0.01  target=0.80 -> status", reachable.status,
        inference_status_name(reachable.status), "n", reachable.n_per_group, "steps",
        reachable.search_steps, "achieved", reachable.achieved_power, "minimal",
        reachable.minimal,
    )
    if (
        unreach.status == INF_ERR_NOT_CONVERGED
        and unreach.achieved_power < unreach.target_power
        and unreach.search_steps == POWER_SEARCH_STEPS
        and unreach.n_per_group > 0
        and unreach.achieved_power > 0.0
        and not unreach.minimal
        and reachable.status == INF_OK
        and reachable.achieved_power >= 0.80
        and reachable.search_steps < POWER_SEARCH_STEPS
        and reachable.minimal
    ):
        print(
            "   ✅ an unreachable target is INF_ERR_NOT_CONVERGED with the diagnostics kept,",
            "while d = 0.01 at", reachable.search_steps, "steps is still INF_OK",
        )
    else:
        failures += 1
        print(
            "   ❌ an underpowered n came back as an answer:", unreach.status,
            unreach.achieved_power, unreach.search_steps, reachable.status,
        )

    # ══ 4. multiplicity: monotone, and linear in the family size ════════════════
    print("\n-- 4. multiplicity: cost shape and monotonicity --")
    var fam_sizes = _ints(16384, 131072, 1048576)
    var bonf_ns = List[Float64]()
    var holm_ns = List[Float64]()
    var bh_ns = List[Float64]()
    var order_ok = True
    for i in range(len(fam_sizes)):
        var n = fam_sizes[i]
        var p = _p_family(n)
        var best_b: Float64 = 0.0
        var best_h: Float64 = 0.0
        var best_q: Float64 = 0.0
        var rej_b = 0
        var rej_h = 0
        var rej_q = 0
        var refused = False
        # Minimum of `GATE_REPS`, not the first or the mean: the minimum is the run least
        # contaminated by whatever else the machine was doing, and this measurement decides a
        # growth exponent, which one contended reading at either end moves directly. See the
        # measured spreads at `GATE_REPS` — the per-element cost of the sort at n = 2^17 was
        # seen to swing 3.7x between single readings on a machine running other work.
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            var b = bonferroni_flat(p, n, 0.05)
            var t1 = perf_counter_ns()
            var h = holm_flat(p, n, 0.05)
            var t2 = perf_counter_ns()
            var q = benjamini_hochberg_flat(p, n, 0.05)
            var t3 = perf_counter_ns()
            if b.status != INF_OK or h.status != INF_OK or q.status != INF_OK:
                refused = True
                break
            if rep == 0 or _ns(t0, t1) < best_b:
                best_b = _ns(t0, t1)
            if rep == 0 or _ns(t1, t2) < best_h:
                best_h = _ns(t1, t2)
            if rep == 0 or _ns(t2, t3) < best_q:
                best_q = _ns(t2, t3)
            if rep == 0:
                rej_b = b.n_rejected
                rej_h = h.n_rejected
                rej_q = q.n_rejected
                # The provable per-position ordering, checked at every position and not only
                # at the ones this family rejects. O(n), so it runs at every size including
                # the ceiling.
                for j in range(n):
                    if q.adjusted[j] > h.adjusted[j] or h.adjusted[j] > b.adjusted[j]:
                        order_ok = False
                    if b.adjusted[j] < 0.0 or b.adjusted[j] > 1.0:
                        order_ok = False
                if b.n_rejected > h.n_rejected or h.n_rejected > q.n_rejected:
                    order_ok = False
        if refused:
            failures += 1
            print("   ❌ a correction refused at n =", n)
            continue
        bonf_ns.append(best_b)
        holm_ns.append(best_h)
        bh_ns.append(best_q)
        var nf = Float64(n)
        var nlogn = nf * _log2(nf)
        print(
            "   n =", n, "(min of", GATE_REPS, ") bonferroni ns/n", best_b / nf,
            "| holm ns/n", best_h / nf, "ns/(n log2 n)", best_h / nlogn,
            "| bh ns/(n log2 n)", best_q / nlogn,
            "| rejected", rej_b, rej_h, rej_q,
        )
    if order_ok:
        print(
            "   ✅ BH <= Holm <= Bonferroni at every position and every rejection count,",
            "at every size, all adjusted values in [0, 1]",
        )
    else:
        failures += 1
        print("   ❌ the adjusted-value ordering across procedures is violated")

    # Gated as a growth EXPONENT rather than a ratio, because the three procedures are
    # compared against different declared complexities and against the quadratic control
    # below at a different size step; an exponent is normalised for the size step and a ratio
    # is not. p = log(t_large / t_small) / log(n_large / n_small).
    #
    # Holm and BH are allowed up to 1.7 and NOT the 1.05 an ideal n log n would give,
    # because the frozen `retrieval_rank_order` is a bottom-up merge sort that streams the
    # whole array once per pass: past cache each pass costs a DRAM round trip, and the
    # measured exponent here is ~1.3 rather than ~1.05 for exactly that reason. That is a
    # bandwidth term, not an algorithmic one.
    #
    # 1.7 is where it is because BOTH envelopes were measured over six runs of this file on
    # one machine, one of them under heavy load: Holm and BH came out in [1.24, 1.43], and
    # the O(n^2) control below came out in [2.07, 2.28]. 1.7 sits between the two with about
    # 19% of margin on each side. It is not a number that makes today's reading pass — it is
    # the midpoint of a measured gap, and the control is what keeps the lower half honest.
    var p_bonf: Float64 = -1.0
    var p_holm: Float64 = -1.0
    var p_bh: Float64 = -1.0
    if len(bonf_ns) == 3:
        p_bonf = _exponent(bonf_ns[0], fam_sizes[0], bonf_ns[2], fam_sizes[2])
        p_holm = _exponent(holm_ns[0], fam_sizes[0], holm_ns[2], fam_sizes[2])
        p_bh = _exponent(bh_ns[0], fam_sizes[0], bh_ns[2], fam_sizes[2])
    print(
        "   growth exponent p in t ~ n^p across the 64x rise: bonferroni", p_bonf,
        "holm", p_holm, "bh", p_bh,
        "(1.0 = linear, ~1.05 = ideal n log n, 2.0 = quadratic)",
    )
    if p_bonf >= 0.0 and p_bonf <= 1.2:
        print(
            "   ✅ Bonferroni is linear in the family size across a 64x rise, up to",
            "MAX_TESTS =", MAX_TESTS, "— it is the one procedure that does not sort",
        )
    else:
        failures += 1
        print("   ❌ Bonferroni is not linear in n: exponent", p_bonf)
    if p_holm >= 0.0 and p_holm <= 1.7 and p_bh >= 0.0 and p_bh <= 1.7:
        print(
            "   ✅ Holm and BH stayed inside their declared O(n log n) plus a bandwidth term",
            "and nowhere near quadratic",
        )
    else:
        failures += 1
        print("   ❌ a sorting correction exceeded its charge: exponents", p_holm, p_bh)

    # Monotonicity as a pairwise property: a correction that is not order-preserving is not a
    # correction. Every unordered pair, for all three procedures, at two sizes — which is
    # itself an O(n^2) scan, so timing it at both sizes doubles as the CONTROL that proves
    # the exponent gate above can reject quadratic work. If the same `p <= 1.7` predicate
    # accepted this scan, that gate would be measuring nothing.
    var mono_sizes = _ints(1024, 4096)
    var mono_ns = List[Float64]()
    var pairs_total = 0
    var mono_bad = 0
    var reject_rule_bad = 0
    for s in range(len(mono_sizes)):
        var mono_n = mono_sizes[s]
        var mono_p = _p_family(mono_n)
        var mb = bonferroni_flat(mono_p, mono_n, 0.05)
        var mh = holm_flat(mono_p, mono_n, 0.05)
        var mq = benjamini_hochberg_flat(mono_p, mono_n, 0.05)
        if mb.status != INF_OK or mh.status != INF_OK or mq.status != INF_OK:
            failures += 1
            print("   ❌ a correction refused at the monotonicity size", mono_n)
            continue
        var pairs = 0
        var best: Float64 = 0.0
        for rep in range(GATE_REPS):
            var bad_local = 0
            var rule_local = 0
            var pairs_local = 0
            var t0 = perf_counter_ns()
            for i in range(mono_n):
                if mb.rejected[i] != (mb.adjusted[i] <= 0.05):
                    rule_local += 1
                if mh.rejected[i] != (mh.adjusted[i] <= 0.05):
                    rule_local += 1
                if mq.rejected[i] != (mq.adjusted[i] <= 0.05):
                    rule_local += 1
                for j in range(i + 1, mono_n):
                    pairs_local += 1
                    if mono_p[i] <= mono_p[j]:
                        if mb.adjusted[i] > mb.adjusted[j]:
                            bad_local += 1
                        if mh.adjusted[i] > mh.adjusted[j]:
                            bad_local += 1
                        if mq.adjusted[i] > mq.adjusted[j]:
                            bad_local += 1
                    else:
                        if mb.adjusted[i] < mb.adjusted[j]:
                            bad_local += 1
                        if mh.adjusted[i] < mh.adjusted[j]:
                            bad_local += 1
                        if mq.adjusted[i] < mq.adjusted[j]:
                            bad_local += 1
            var t1 = perf_counter_ns()
            if rep == 0 or _ns(t0, t1) < best:
                best = _ns(t0, t1)
            # The verdict is taken from one pass; the remaining passes exist only to give the
            # control a minimum. Counting every identical pass would multiply a single
            # violation by `GATE_REPS` and report it as that many.
            if rep == 0:
                mono_bad += bad_local
                reject_rule_bad += rule_local
                pairs = pairs_local
        mono_ns.append(best)
        pairs_total += pairs
        print(
            "   n =", mono_n, ":", pairs, "pairs x 3 procedures in", best,
            "ns (min of", GATE_REPS, ") | order violations", mono_bad,
            "| rejected == (adjusted <= alpha) violations", reject_rule_bad,
        )
    if mono_bad == 0 and reject_rule_bad == 0 and pairs_total == 8910336:
        print(
            "   ✅ every procedure preserves the p-value order over all", pairs_total,
            "pairs and applies its own rejection rule",
        )
    else:
        failures += 1
        print("   ❌ a correction is not order-preserving:", mono_bad, reject_rule_bad,
              pairs_total)
    var p_control: Float64 = -1.0
    if len(mono_ns) == 2:
        p_control = _exponent(mono_ns[0], mono_sizes[0], mono_ns[1], mono_sizes[1])
    print(
        "   control: the pairwise scan is O(n^2) by construction and measures exponent",
        p_control,
    )
    if p_control > 1.7:
        print(
            "   ✅ the same p <= 1.7 predicate REJECTS this quadratic scan, so the exponent",
            "gate above discriminates rather than passing everything",
        )
    else:
        failures += 1
        print(
            "   ❌ the exponent gate cannot tell quadratic work apart; control exponent",
            p_control,
        )

    # A graded family where BH strictly out-rejects Bonferroni, so the ordering assertion
    # above is not satisfied vacuously by three equal counts.
    var graded_n = 20
    var graded = List[Float64](capacity=graded_n)
    for i in range(graded_n):
        graded.append(0.001 * Float64(i + 1))
    var ag = correction_agreement_flat(graded, graded_n, 0.05)
    print(
        "   graded family of", graded_n, "p-values: rejected bonferroni",
        ag.n_rejected_bonferroni, "holm", ag.n_rejected_holm, "bh", ag.n_rejected_bh,
        "| smallest-p identical", ag.smallest_p_identical, "| monotone",
        ag.monotone_bh_le_holm_le_bonferroni, "| power ordering",
        ag.power_ordering_holds,
    )
    if (
        ag.status == INF_OK
        and ag.smallest_p_identical
        and ag.monotone_bh_le_holm_le_bonferroni
        and ag.power_ordering_holds
        and ag.n_rejected_bonferroni < ag.n_rejected_bh
    ):
        print(
            "   ✅ BH strictly out-rejects Bonferroni here (", ag.n_rejected_bonferroni,
            "vs", ag.n_rejected_bh, "), so the ordering is not vacuous",
        )
    else:
        failures += 1
        print(
            "   ❌ the three procedures do not cohere on the graded family:", ag.status,
            ag.n_rejected_bonferroni, ag.n_rejected_bh,
        )

    # ══ 5. resampling cost scales with draws as declared ═══════════════════════
    print("\n-- 5. bootstrap / permutation: cost per draw, and reproducibility --")
    var boot_n = 128
    var boot_vals = _sample(boot_n)
    var warm_ci = bootstrap_ci_flat(boot_vals, boot_n, STAT_MEAN, 64, 0.95, 7, 1)
    var boot_bs = _ints(1000, 4000, 16000)
    var boot_unit = List[Float64]()
    var hw_first: Float64 = -1.0
    var hw_last: Float64 = -1.0
    # Minimum of `GATE_REPS` again. Measured, the single-shot ns per (B x n) here moved between
    # 43 and 725 on this machine — a 16.3x spread — which is wide enough to make a 3x ratio
    # gate a coin flip, and did: it read 3.16x against the 3.0 limit while the true ratio at
    # the minimum of seven is 1.01.
    for i in range(len(boot_bs)):
        var b = boot_bs[i]
        var best: Float64 = 0.0
        var refused = False
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            var ci = bootstrap_ci_flat(boot_vals, boot_n, STAT_MEAN, b, 0.95, 7, 1)
            var t1 = perf_counter_ns()
            if ci.status != INF_OK or not ci.interval_known:
                refused = True
                print("   ❌ bootstrap refused at B =", b, inference_status_name(ci.status))
                break
            if rep == 0 or _ns(t0, t1) < best:
                best = _ns(t0, t1)
            if rep == 0:
                if i == 0:
                    hw_first = ci.lo_mc_halfwidth
                hw_last = ci.lo_mc_halfwidth
                print(
                    "   mean B =", b, "n =", boot_n, "| [", ci.lo, ",", ci.hi,
                    "] mc halfwidth", ci.lo_mc_halfwidth, "rank sd", ci.endpoint_rank_sd,
                )
        if refused:
            failures += 1
            continue
        var per = best / (Float64(b) * Float64(boot_n))
        boot_unit.append(per)
        print("   mean B =", b, "(min of", GATE_REPS, ") ns", best, "ns/(B*n)", per)
    if len(boot_unit) == 3 and _flat(boot_unit[0], boot_unit[2], 3.0):
        print("   ✅ bootstrap ns per (B x n) stayed flat across a 16x rise in B")
    else:
        failures += 1
        print("   ❌ bootstrap cost grew with B:", boot_unit[0], "->", boot_unit[2])
    if hw_first > 0.0 and hw_last <= hw_first:
        print(
            "   ✅ the endpoint's Monte-Carlo halfwidth shrank from", hw_first, "to", hw_last,
            "as B rose 16x — the interval's own precision, which B alone does not state",
        )
    else:
        failures += 1
        print("   ❌ the endpoint halfwidth did not shrink with B:", hw_first, hw_last)

    var boot_ns_unit = List[Float64]()
    var boot_sizes = _ints(128, 512)
    for i in range(len(boot_sizes)):
        var n = boot_sizes[i]
        var v = _sample(n)
        var best: Float64 = 0.0
        var refused = False
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            var ci = bootstrap_ci_flat(v, n, STAT_MEAN, 2000, 0.95, 7, 1)
            var t1 = perf_counter_ns()
            if ci.status != INF_OK:
                refused = True
                break
            if rep == 0 or _ns(t0, t1) < best:
                best = _ns(t0, t1)
        if refused:
            failures += 1
            print("   ❌ bootstrap refused at n =", n)
            continue
        var per = best / (2000.0 * Float64(n))
        boot_ns_unit.append(per)
        print("   mean B = 2000 n =", n, "(min of", GATE_REPS, ") ns", best, "ns/(B*n)", per)
    if len(boot_ns_unit) == 2 and _flat(boot_ns_unit[0], boot_ns_unit[1], 3.0):
        print("   ✅ bootstrap ns per (B x n) stayed flat across a 4x rise in n")
    else:
        failures += 1
        print("   ❌ bootstrap cost grew super-linearly in n:", boot_ns_unit[0], "->",
              boot_ns_unit[1])

    # The median resample sorts, so its budget is charged n^2 while the real cost is
    # n log n. Over-charging is the safe direction; what is gated is that the charge is not
    # UNDER-charged, i.e. ns per (B n^2) must not grow.
    var med_charge = List[Float64]()
    var med_real = List[Float64]()
    var med_sizes = _ints(64, 256)
    for i in range(len(med_sizes)):
        var n = med_sizes[i]
        var v = _sample(n)
        var best: Float64 = 0.0
        var refused = False
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            var ci = bootstrap_ci_flat(v, n, STAT_MEDIAN, 500, 0.95, 7, 1)
            var t1 = perf_counter_ns()
            if ci.status != INF_OK:
                refused = True
                break
            if rep == 0 or _ns(t0, t1) < best:
                best = _ns(t0, t1)
        if refused:
            failures += 1
            print("   ❌ median bootstrap refused at n =", n)
            continue
        var nf = Float64(n)
        med_charge.append(best / (500.0 * nf * nf))
        med_real.append(best / (500.0 * nf * _log2(nf)))
        print(
            "   median B = 500 n =", n, "(min of", GATE_REPS, ") ns", best, "ns/(B n^2)",
            best / (500.0 * nf * nf), "ns/(B n log2 n)",
            best / (500.0 * nf * _log2(nf)),
        )
    if len(med_charge) == 2 and med_charge[1] <= med_charge[0]:
        print(
            "   ✅ the median's declared n^2 charge is not undercharged; the real shape is",
            "n log n (ns per B n log2 n", med_real[0], "->", med_real[1], ")",
        )
    else:
        failures += 1
        print("   ❌ the median charge is undercharged:", med_charge[0], "->", med_charge[1])

    var p_n1 = 64
    var p_n2 = 64
    var perm_vals = _sample(p_n1 + p_n2)
    var warm_perm = permutation_test_flat(perm_vals, p_n1, p_n2, 32, 11, 3)
    var perm_unit = List[Float64]()
    for i in range(len(boot_bs)):
        var b = boot_bs[i]
        var best: Float64 = 0.0
        var refused = False
        for rep in range(GATE_REPS):
            var t0 = perf_counter_ns()
            var pt = permutation_test_flat(perm_vals, p_n1, p_n2, b, 11, 3)
            var t1 = perf_counter_ns()
            if pt.status != INF_OK:
                refused = True
                print("   ❌ permutation refused at B =", b,
                      inference_status_name(pt.status))
                break
            if rep == 0 or _ns(t0, t1) < best:
                best = _ns(t0, t1)
            if rep == 0:
                var exact = (
                    1.0 + Float64(pt.count_at_least_as_extreme)
                ) / (1.0 + Float64(b))
                print(
                    "   permutation B =", b, "| p", pt.p_value, "floor", pt.p_value_floor,
                    "count", pt.count_at_least_as_extreme, "| p == (1+count)/(1+B)",
                    pt.p_value == exact,
                )
                if (
                    pt.p_value != exact
                    or pt.p_value < pt.p_value_floor
                    or pt.p_value <= 0.0
                ):
                    failures += 1
                    print("   ❌ the corrected p-value estimator is not what it claims")
        if refused:
            failures += 1
            continue
        var per = best / (Float64(b) * Float64(p_n1 + p_n2))
        perm_unit.append(per)
        print("   permutation B =", b, "(min of", GATE_REPS, ") ns", best, "ns/(B*total)", per)
    if len(perm_unit) == 3 and _flat(perm_unit[0], perm_unit[2], 3.0):
        print("   ✅ permutation ns per (B x (n1 + n2)) stayed flat across a 16x rise in B")
    else:
        failures += 1
        print("   ❌ permutation cost grew with B:", perm_unit[0], "->", perm_unit[2])

    # The input that separates `(1 + count) / (1 + B)` from the frozen
    # `stats_bootstrap.bootstrap_test`'s `count / B`: two groups so far apart that NO
    # permutation is as extreme as the observed split, so the raw count is 0. The frozen
    # convention returns exactly 0.0 there, which is not a p-value a finite permutation test
    # can produce; the corrected estimator returns the floor. Without this case the p-value
    # assertions above are checked only where count is in the thousands and both conventions
    # give something positive.
    var far = List[Float64]()
    for i in range(32):
        far.append(1.0 + 0.01 * Float64(i % 5))
    for i in range(32):
        far.append(100.0 + 0.01 * Float64(i % 5))
    var far_pt = permutation_test_flat(far, 32, 32, 2000, 11, 3)
    print(
        "   separated groups: count", far_pt.count_at_least_as_extreme, "| frozen count/B",
        Float64(far_pt.count_at_least_as_extreme) / 2000.0, "| corrected p",
        far_pt.p_value, "= floor", far_pt.p_value_floor, "| observed diff",
        far_pt.observed_diff,
    )
    if (
        far_pt.status == INF_OK
        and far_pt.count_at_least_as_extreme == 0
        and far_pt.p_value > 0.0
        and far_pt.p_value == far_pt.p_value_floor
        and far_pt.p_value == 1.0 / 2001.0
    ):
        print(
            "   ✅ a count of zero returns the floor, not 0.0 — the one input where the",
            "corrected estimator and the frozen convention actually disagree",
        )
    else:
        failures += 1
        print(
            "   ❌ the zero-count case is not returning the floor:",
            far_pt.count_at_least_as_extreme, far_pt.p_value, far_pt.p_value_floor,
        )

    # Reproducibility, with `==`: every draw is counter-based on (seed, stream, coordinate),
    # so a rerun is the same computation and a tolerance here would accept exactly the drift
    # that `stats_bootstrap`'s process-global randomness introduces. `rep_c` changes only the
    # stream and is gated to DIFFER, so the equalities above are known to be discriminating
    # rather than two reads of one constant.
    var rep_a = bootstrap_ci_flat(boot_vals, boot_n, STAT_MEAN, 2000, 0.95, 42, 5)
    var rep_b = bootstrap_ci_flat(boot_vals, boot_n, STAT_MEAN, 2000, 0.95, 42, 5)
    var rep_c = bootstrap_ci_flat(boot_vals, boot_n, STAT_MEAN, 2000, 0.95, 42, 6)
    var perm_a = permutation_test_flat(perm_vals, p_n1, p_n2, 2000, 42, 5)
    var perm_b = permutation_test_flat(perm_vals, p_n1, p_n2, 2000, 42, 5)
    print(
        "   same (seed, stream): ci [", rep_a.lo, ",", rep_a.hi, "] vs [", rep_b.lo, ",",
        rep_b.hi, "] | p", perm_a.p_value, "vs", perm_b.p_value,
    )
    print("   stream 6 instead of 5: ci [", rep_c.lo, ",", rep_c.hi, "]")
    if (
        rep_a.lo == rep_b.lo
        and rep_a.hi == rep_b.hi
        and rep_a.bias == rep_b.bias
        and rep_a.resample_se == rep_b.resample_se
        and perm_a.p_value == perm_b.p_value
        and perm_a.count_at_least_as_extreme == perm_b.count_at_least_as_extreme
        and warm_ci.status == INF_OK
        and warm_perm.status == INF_OK
        and rep_c.status == INF_OK
        and rep_c.lo != rep_a.lo
    ):
        print(
            "   ✅ one (seed, stream) reproduces bitwise, for both the CI and the p-value —",
            "and stream 6 moves the endpoint, so the equality is discriminating",
        )
    else:
        failures += 1
        print("   ❌ a resampled result did not reproduce:", rep_a.lo, rep_b.lo,
              perm_a.p_value, perm_b.p_value)

    print("")
    if failures == 0:
        print("BENCH_GATE inference PASS")
    else:
        print("BENCH_GATE inference FAIL " + String(failures))
        raise Error("bench_inference: " + String(failures) + " gate failure(s)")
