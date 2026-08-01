"""Common random numbers: is the published 174x variance reduction real, and is it honest?

WHY THIS FILE EXISTS
--------------------
`strategy/crn.mojo` publishes a measured variance-reduction factor of 174x for common random
numbers, from ONE configuration at 32 scenarios. A reviewer in the discrete-event-simulation
field will ask two questions about a number like that, and both of them are answerable by
measurement rather than by argument:

  1. Is 174 a property of the CRN MACHINERY, or of a test problem built to flatter pairing?
  2. Is 174 even a stable estimate of its own population quantity at 32 scenarios?

This benchmark answers both, and then re-measures the same claim on a problem a practitioner
actually faces — an M/M/1 capacity study — so the published factor can be stated with the effect
size it belongs to.

WHAT THE LITERATURE REPORTS, FOR CALIBRATION (sources, not paraphrase)
---------------------------------------------------------------------
* Murphy, Klein, Smolen, Klein, Roberts (2013), "Using Common Random Numbers in Health Care
  Cost-Effectiveness Simulation Modeling", Health Services Research 48(4):1508-1525 (PMC3725537).
  FULL CRN (identical patients, synchronised processing) 93.6% variance reduction = 15.6x; 1,000
  simulated patients gave what 16,000 gave without CRN. PARTIAL CRN (common initial
  characteristics only, unsynchronised) 5.6% = 1.06x. This is the best numeric anchor available.
* Klein, Abeysuriya, Stuart, Kerr (2024), arXiv:2409.02086: reductions in the number of
  simulations needed for a given standard error "exceeding 10-fold for some applications".
* Adewunmi & Aickelin (2013), arXiv:1305.7424: across manufacturing, call-centre and cross-docking
  models CRN was NOT the best variance-reduction technique in any of them, and the amount of
  reduction "can vary substantially from one output performance measure to the other, as well as
  one simulation model to the other". They quote Law & Kelton: "there is no way to evaluate the
  increase or decrease in variance resulting from the use of CRN, other than to repeat the
  simulation runs without the use of the technique" — which is precisely what
  `crn_pairing_audit` does mechanically, and is the correct framing for our claim.
* L'Ecuyer & Buist (2006), "Variance Reduction in the Simulation of Call Centers", WSC 2006,
  pp. 604-613: CRN improves the CONVERGENCE RATE of the variance of a difference between two
  systems — a rate result, not a fixed factor. Numeric tables not retrieved (paywalled); no
  number from that paper is quoted here.

THE EXACT ARITHMETIC OF THE SHIPPED TOY PROBLEM (derived, then verified below)
-----------------------------------------------------------------------------
The published configuration is one uniform factor `x ~ U[0,1)`, cost 0.5, gamma 1.0, horizon 64,
THRESHOLD policies with unit weight at 0.40 and 0.50. Per step the payoff of threshold `theta` is
`p(x) = (x - 0.5) * 1[x >= theta]`, so

    E[p_theta]    = 0.5*theta - theta^2/2
    E[p_theta^2]  = (0.125 - (theta - 0.5)^3) / 3

and the PAIRED per-step difference for `a < b` is `d(x) = -(x - 0.5) * 1[a <= x < b]`, supported
ONLY on the disagreement slice `[a, b)`:

    E[d]   = -((b^2 - a^2)/2 - 0.5*(b - a))
    E[d^2] = ((b - 0.5)^3 - (a - 0.5)^3) / 3

Steps are i.i.d., so the horizon multiplies every variance and CANCELS in the ratio. The exact
variance ratio is therefore `(Var p_a + Var p_b) / Var d`, computed by `_toy_analytic_ratio` with
no simulation and no quadrature. It is 173.973 at the published gap of 0.10 — the shipped
measurement of 174.1 is arithmetically right, and this file gates that agreement across a gap
sweep spanning 4.2 to 19,848.

THE TWO HONEST CRITICISMS, BOTH MEASURED HERE
---------------------------------------------
MAGNITUDE IS A KNOB, NOT AN ACHIEVEMENT. The ratio is a monotone function of how similar the two
compared designs are: 4.2x at a 0.50 threshold gap, 174x at 0.10, 19,849x at 0.02. Quoting 174x
without the gap says nothing about the implementation. Section 1 measures the whole curve against
the exact analytic value, which converts the single boast into a falsifiable claim.

PRECISION WAS OVERSTATED. Re-running the published configuration at twelve other master seeds,
32 scenarios each, gives ratios from 74 to 260 (section 2). A variance ratio from 32 replications
has a relative standard error near sqrt(2/31) = 25%, so "174.1" quotes three digits of noise. The
central value is right — at 2000 scenarios the same configuration returns 172.9 against the exact
173.973 — but the shipped docstring should carry the scenario count and the estimator's spread.

WHAT SURVIVES BOTH CRITICISMS, AND IS THE REAL RESULT
-----------------------------------------------------
Section 3 re-measures pairing on an M/M/1 capacity study through `discrete_event.qs_run_flat`:
lambda = 0.80, a baseline server at mu = 1.00, and a candidate 2% faster at mu = 1.02, which moves
exact Wq from 4.000000 to 3.565062 (-10.87%). The response is the per-replication mean wait in
queue over 2000 customers. Paired means both designs at the SAME replication coordinate; unpaired
means the candidate at coordinate `n_reps + r`, independent by coordinate — the construction
`crn_pairing_audit` uses, transplanted onto the queue.

MEASURED (2000 replications, seed 4242, 2000 customers, this machine, load average ~124):

    arm A (mu 1.00)          mean 3.959203  var 0.873773
    arm B paired (mu 1.02)   mean 3.537173  var 0.622105   corr(A,B) = 0.996852
    arm B independent        mean 3.540954  var 0.660310   corr(A,B) = -0.004169
    PAIRED   difference      mean -0.422030  var 0.025964  CI95 [-0.429096, -0.414964]
    UNPAIRED difference      mean -0.418248  var 1.540417  CI95 [-0.472675, -0.363821]
    variance ratio 59.33   -> the same 95% half-width needs 2,015 paired replications or
                              119,681 unpaired ones (both computed with the shipped
                              `inference_t_quantile`, not a normal approximation)

So the realistic problem does NOT collapse the factor to the literature's 15.6x. It lands at 59x,
because 59x is what a 2% design change is worth on this model, and 15.6x is what Murphy et al.'s
effect size was worth on theirs. Placed on a common scale — |E[difference]| divided by the
unpaired standard deviation — the toy problem at a 0.10 gap sits at 0.173 and the queue at a 2%
change sits at 0.337, and the queue's LARGER (easier) effect still returns a ratio within a factor
of three of the toy's. The two problems are the same curve, which is the point: publish the effect
size with the factor, always.

THE PART THAT IS ACTUALLY OURS
------------------------------
The factor above is available to any simulator that synchronises its streams correctly. What the
counter-addressed substrate contributes is that synchronisation is not the user's problem, and
section 4 measures what it costs when it IS. Every individual draw is compared as a 64-bit pattern
through `Float64.to_bits()` — not a digest, not a mean:

  * 6,144 tape cells across two independent generations, `crn_cell_draw`, and the raw
    `determinism.counter_rng` word underneath: one bit pattern, three code paths.
  * 2,560 words of scenario/policy stream separation: zero cross-stream collisions, zero
    environment words moved by a change of strategy index, 3,072 per-strategy coin pairs distinct.
  * 10,000 service draws at two different service rates: `s(mu)[i]` equals `-log(u_i)/mu`
    bit-exactly for BOTH rates, i.e. both designs are driven by the same underlying uniform, which
    is inversion-based CRN in L'Ecuyer's sense; 10,000 arrival gaps bit-identical across designs.
  * the negative control: a SEQUENTIAL consumer of the same generator, where one arm took one
    extra draw, agrees on 0 of 64 steps and diverges at step 0.

The external half of that measurement is in `benchmarks/crn_simpy_baseline.py` (SimPy 4.1.2, run
from a throwaway virtualenv — SimPy is not a repo dependency): on the identical M/M/1 comparison,
hand-built two-stream CRN reproduces the effect (48x at 400 replications), while the naive
same-seed single-stream attempt a practitioner reaches for first returns 1.35x, because changing
the service rate changes the interleaving of arrival and service draws — 55% of its arrival gaps
differ between the two designs, first divergence at customer 44 of 2000. That 1.35x sits on top of
Murphy et al.'s 1.06x for unsynchronised partial CRN, and it is the honest measure of what the
addressing buys.

WHAT IS NOT CLAIMED
-------------------
No timing number here is a gate, and none should be quoted as a speed result: this machine has run
at load average 400+ today, and the repo's own `bench_discrete_event.mojo` documents two runs five
minutes apart whose growth exponents disagreed 1.11 vs 1.99 with no code change. Everything gated
below is an arithmetic identity, an exact-bit equality, or an agreement with a closed form. Record
the load average beside any wall-clock line printed here.

The arm means below are for a 2000-customer run from an empty system with NO warm-up truncation,
so they carry the initialisation bias every DES text describes: arm A measures 3.9592 against an
exact Wq of 4.0, about -1%, and at 2000 replications the CI half-width (0.041) is the same size as
the bias, so steady-state coverage is marginal by construction. That is why the shipped
`replicate_mm1_flat` runs an MSER-5 pilot and truncates; it is not a defect of the estimator, and
this file gates the FINITE-HORIZON claims rather than pretending the two estimands are the same.
"""
from std.math import sqrt
from std.time import perf_counter_ns

from determinism.counter_rng import philox_word, rng_uniform, rng_uniform_left_open
from discrete_event.contract import DE_OK, de_stream_arrival, de_stream_service
from discrete_event.queue_sim import qs_closed_form_flat, qs_interarrivals, qs_run_flat, qs_service_times
from discrete_event.replicate import replicate_ci_flat
from inference.core import inference_t_quantile
from math_ext import correlation
from stats import compute_mean, compute_variance
from strategy.contract import (
    STRAT_FACTOR_UNIFORM,
    STRAT_OK,
    STRAT_POLICY_THRESHOLD,
    strat_stream_policy,
    strat_stream_scenario,
)
from strategy.crn import crn_cell_draw, crn_pairing_audit, crn_scenario_tape
from std.math import log


# ── the exact analytic reference for the toy environment ──────────────────────


fn _toy_step_moments(theta: Float64) -> List[Float64]:
    """[E[p], Var p] for one step of threshold `theta`, in closed form."""
    var e1 = 0.5 * theta - 0.5 * theta * theta
    var c = theta - 0.5
    var e2 = (0.125 - c * c * c) / 3.0
    var out = List[Float64]()
    out.append(e1)
    out.append(e2 - e1 * e1)
    return out^


fn _toy_diff_moments(a: Float64, b: Float64) -> List[Float64]:
    """[E[d], Var d] for the paired per-step difference on the slice [a, b)."""
    var e1 = -((b * b - a * a) / 2.0 - 0.5 * (b - a))
    var ca = a - 0.5
    var cb = b - 0.5
    var e2 = (cb * cb * cb - ca * ca * ca) / 3.0
    var out = List[Float64]()
    out.append(e1)
    out.append(e2 - e1 * e1)
    return out^


fn _toy_analytic_ratio(gap: Float64) -> Float64:
    """The EXACT unpaired/paired variance ratio. The horizon cancels, so none is needed."""
    var a = 0.5 - gap
    var ma = _toy_step_moments(a)
    var mb = _toy_step_moments(0.5)
    var md = _toy_diff_moments(a, 0.5)
    if md[1] <= 0.0:
        return -1.0
    return (ma[1] + mb[1]) / md[1]


fn _toy_analytic_effect_to_noise(gap: Float64, horizon: Int) -> Float64:
    """|E[difference]| / sd(unpaired difference) — the scale-free "how similar" axis."""
    var a = 0.5 - gap
    var ma = _toy_step_moments(a)
    var mb = _toy_step_moments(0.5)
    var md = _toy_diff_moments(a, 0.5)
    var h = Float64(horizon)
    var num = h * md[0]
    if num < 0.0:
        num = -num
    return num / sqrt(h * (ma[1] + mb[1]))


# ── one driver call per function (see bench_strategy.mojo: nesting them stalls the compiler) ──


fn _pair_block(theta_a: Float64, theta_b: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(1.0)
    out.append(theta_a)
    out.append(1.0)
    out.append(theta_b)
    return out^


fn _audit(seed: Int, n_scen: Int, horizon: Int, gap: Float64) -> List[Float64]:
    """ONE `crn_pairing_audit`. Returns
    [status, ratio, var_paired, var_unpaired, mean_paired, mean_unpaired, p_paired, p_unpaired,
     n_bit_identical, conclusions_differ, ms, paired_excludes_zero, unpaired_excludes_zero]."""
    var block = _pair_block(0.5 - gap, 0.5)
    var t0 = perf_counter_ns()
    var au = crn_pairing_audit(
        seed, 7, n_scen, horizon, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5,
        STRAT_POLICY_THRESHOLD, block, 2, 2, 0, 1, 1.0, 0.95,
    )
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(au.status))
    out.append(au.variance_ratio)
    out.append(au.paired_variance)
    out.append(au.unpaired_variance)
    out.append(au.paired_mean)
    out.append(au.unpaired_mean)
    out.append(au.paired_p_value)
    out.append(au.unpaired_p_value)
    out.append(Float64(au.n_scenarios_bit_identical))
    out.append(1.0 if au.conclusions_differ else 0.0)
    out.append(Float64(Int(dt)) / 1.0e6)
    out.append(1.0 if au.paired_excludes_zero else 0.0)
    out.append(1.0 if au.unpaired_excludes_zero else 0.0)
    return out^


fn _queue(
    lam: Float64, mu_a: Float64, mu_b: Float64, n_cust: Int, n_reps: Int, seed: Int,
    warmup: Int,
) -> List[Float64]:
    """The paired/unpaired M/M/1 design comparison. Returns
    [ok, mean_A, var_A, mean_Bp, var_Bp, mean_paired, var_paired, ci_lo_p, ci_hi_p,
     mean_unpaired, var_unpaired, ci_lo_u, ci_hi_u, ratio, corr_paired, corr_unpaired,
     cf_wait_A, cf_wait_B, n, ms, paired_excl, unpaired_excl, reps_needed_paired,
     reps_needed_unpaired, half_width]."""
    var t0 = perf_counter_ns()
    var wa = List[Float64]()
    var wb = List[Float64]()
    var wi = List[Float64]()
    var paired = List[Float64]()
    var unpaired = List[Float64]()
    var ok = True
    for r in range(1, n_reps + 1):
        var ra = qs_run_flat(lam, mu_a, n_cust, 1, seed, r, warmup)
        var rb = qs_run_flat(lam, mu_b, n_cust, 1, seed, r, warmup)
        var ri = qs_run_flat(lam, mu_b, n_cust, 1, seed, n_reps + r, warmup)
        var good = ra.status == DE_OK and rb.status == DE_OK and ri.status == DE_OK
        good = good and ra.has_mean_wait and rb.has_mean_wait and ri.has_mean_wait
        if not good:
            ok = False
            continue
        wa.append(ra.mean_wait)
        wb.append(rb.mean_wait)
        wi.append(ri.mean_wait)
        paired.append(rb.mean_wait - ra.mean_wait)
        unpaired.append(ri.mean_wait - ra.mean_wait)
    var dt = perf_counter_ns() - t0
    var n = len(paired)
    var out = List[Float64]()
    if n < 2:
        out.append(0.0)
        return out^
    var ma = compute_mean(wa, n)
    var mb = compute_mean(wb, n)
    var mp = compute_mean(paired, n)
    var mu_ = compute_mean(unpaired, n)
    var va = compute_variance(wa, n, ma)
    var vb = compute_variance(wb, n, mb)
    var vp = compute_variance(paired, n, mp)
    var vu = compute_variance(unpaired, n, mu_)
    var cip = replicate_ci_flat(paired, n, 0.95)
    var ciu = replicate_ci_flat(unpaired, n, 0.95)
    var cfa = qs_closed_form_flat(lam, mu_a, 1)
    var cfb = qs_closed_form_flat(lam, mu_b, 1)
    var h: Float64 = 0.0
    if cip.has_ci:
        h = 0.5 * (cip.ci_upper - cip.ci_lower)
    # Replications for the half-width the paired arm already reaches, on BOTH variances, with the
    # shipped t quantile rather than 1.96 — at 40 replications the difference is 3%.
    var need_p = -1
    var need_u = -1
    var k = 2
    while k <= 4000000 and h > 0.0:
        var tc = inference_t_quantile(0.975, Float64(k - 1))
        if need_p < 0 and tc * sqrt(vp / Float64(k)) <= h:
            need_p = k
        if need_u < 0 and tc * sqrt(vu / Float64(k)) <= h:
            need_u = k
        if need_p > 0 and need_u > 0:
            break
        k = k + 1 if k < 64 else k + k // 32
    out.append(1.0 if ok else 0.0)
    out.append(ma)
    out.append(va)
    out.append(mb)
    out.append(vb)
    out.append(mp)
    out.append(vp)
    out.append(cip.ci_lower if cip.has_ci else 0.0)
    out.append(cip.ci_upper if cip.has_ci else 0.0)
    out.append(mu_)
    out.append(vu)
    out.append(ciu.ci_lower if ciu.has_ci else 0.0)
    out.append(ciu.ci_upper if ciu.has_ci else 0.0)
    out.append(vu / vp if vp > 0.0 else -1.0)
    out.append(correlation(wa, wb))
    out.append(correlation(wa, wi))
    out.append(cfa.wait_in_queue)
    out.append(cfb.wait_in_queue)
    out.append(Float64(n))
    out.append(Float64(Int(dt)) / 1.0e6)
    out.append(1.0 if (cip.has_ci and (cip.ci_lower > 0.0 or cip.ci_upper < 0.0)) else 0.0)
    out.append(1.0 if (ciu.has_ci and (ciu.ci_lower > 0.0 or ciu.ci_upper < 0.0)) else 0.0)
    out.append(Float64(need_p))
    out.append(Float64(need_u))
    out.append(h)
    return out^


# ── section 1: the toy curve against the exact analytic ratio ─────────────────


fn _bench_toy_curve() -> Int:
    print("  [1] the published 174x is one point on a curve, and the curve is exactly known")
    print("      gap   measured      exact         rel_err   effect/noise  var_paired    var_unpaired")
    var gaps = List[Float64]()
    gaps.append(0.50)
    gaps.append(0.40)
    gaps.append(0.30)
    gaps.append(0.20)
    gaps.append(0.10)
    gaps.append(0.05)
    gaps.append(0.02)
    var worst: Float64 = 0.0
    var monotone = True
    var prev: Float64 = -1.0
    var ok = True
    for i in range(len(gaps)):
        var g = gaps[i]
        var m = _audit(12345, 2000, 64, g)
        if Int(m[0]) != STRAT_OK:
            print("      REFUSED status", Int(m[0]), "at gap", g)
            ok = False
            continue
        var exact = _toy_analytic_ratio(g)
        var rel = m[1] / exact - 1.0
        var arel = rel if rel >= 0.0 else -rel
        if arel > worst:
            worst = arel
        # The sweep walks the gap DOWNWARD, so the ratio must rise at every step.
        if prev >= 0.0 and m[1] < prev:
            monotone = False
        prev = m[1]
        print("     ", g, m[1], exact, rel, _toy_analytic_effect_to_noise(g, 64), m[2], m[3])
    print("      worst relative error vs the closed form:", worst)
    if not ok:
        return 1
    if worst > 0.15:
        print("  FAIL a measured variance ratio is more than 15% from its exact analytic value")
        return 1
    if not monotone:
        print("  FAIL the ratio is not monotone in the threshold gap")
        return 1
    print(
        "  PASS measured ratios track the closed form across 4.2x to 19,849x, so the 174x is",
        "arithmetically correct AND is a statement about the threshold gap, not about CRN",
    )
    return 0


fn _bench_toy_horizon_invariance() -> Int:
    print("  [2] the exact ratio is horizon-free, so the measurement must be too")
    print("      horizon  measured      exact")
    var hs = List[Int]()
    hs.append(16)
    hs.append(64)
    hs.append(256)
    var exact = _toy_analytic_ratio(0.10)
    var lo: Float64 = 1.0e18
    var hi: Float64 = -1.0
    for i in range(len(hs)):
        var m = _audit(12345, 2000, hs[i], 0.10)
        if Int(m[0]) != STRAT_OK:
            print("      REFUSED status", Int(m[0]), "at horizon", hs[i])
            return 1
        print("     ", hs[i], m[1], exact)
        if m[1] < lo:
            lo = m[1]
        if m[1] > hi:
            hi = m[1]
    print("      spread across horizons:", hi / lo, "x")
    if hi / lo > 1.35:
        print("  FAIL the ratio moved with the horizon, which the closed form says it cannot")
        return 1
    print("  PASS the ratio is horizon-invariant, as the i.i.d.-step derivation requires")
    return 0


# ── section 2: how stable is a variance ratio at 32 scenarios? ────────────────


fn _bench_seed_spread() -> Int:
    print("  [3] the published number came from 32 scenarios — here it is at 12 other seeds")
    print("      seed        ratio        var_paired   var_unpaired  unpaired_excludes_zero")
    var seeds = List[Int]()
    seeds.append(12345)
    seeds.append(1)
    seeds.append(2)
    seeds.append(7)
    seeds.append(99)
    seeds.append(1234)
    seeds.append(4242)
    seeds.append(20260731)
    seeds.append(555555)
    seeds.append(31337)
    seeds.append(8675309)
    seeds.append(101)
    seeds.append(2718281)
    var lo: Float64 = 1.0e18
    var hi: Float64 = -1.0
    var n_paired_decided = 0
    var n_unpaired_decided = 0
    for i in range(len(seeds)):
        var m = _audit(seeds[i], 32, 64, 0.10)
        if Int(m[0]) != STRAT_OK:
            print("      REFUSED status", Int(m[0]), "at seed", seeds[i])
            return 1
        if Int(m[8]) != 32:
            print("      FAIL only", Int(m[8]), "of 32 scenarios were bit-identical")
            return 1
        if m[1] <= 1.0:
            print("      FAIL pairing did not reduce variance at seed", seeds[i])
            return 1
        if m[1] < lo:
            lo = m[1]
        if m[1] > hi:
            hi = m[1]
        n_paired_decided += Int(m[11])
        n_unpaired_decided += Int(m[12])
        print("     ", seeds[i], m[1], m[2], m[3], Int(m[12]))
    var exact = _toy_analytic_ratio(0.10)
    print("      min", lo, " max", hi, " spread", hi / lo, "x  exact", exact)
    print("      the 95% CI excluded zero in", n_paired_decided, "of", len(seeds),
          "paired comparisons and", n_unpaired_decided, "of", len(seeds), "unpaired ones")
    if lo > exact or hi < exact:
        print("  FAIL the exact ratio is outside the observed envelope, which points at a bug")
        return 1
    if hi / lo < 1.5:
        print("  NOTE the spread was small this run; the finding below is then weaker than stated")
    print(
        "  PASS the estimator brackets the exact value but swings by more than 3x across seeds at",
        "32 scenarios — quoting '174.1' to four digits quotes sampling noise, and the scenario",
        "count belongs beside the number",
    )
    return 0


# ── section 3: the same claim on a queue a practitioner would actually study ──


fn _print_queue(tag: String, label: Float64, m: List[Float64]):
    if len(m) < 25:
        print("     ", tag, label, "REFUSED")
        return
    print(
        "     ", tag, label,
        " ratio=", m[13], " corr=", m[14],
        " d_paired=", m[5], "[", m[7], ",", m[8], "] excl=", Int(m[20]),
        " d_unpaired=", m[9], "[", m[11], ",", m[12], "] excl=", Int(m[21]),
        " exact_delta=", m[17] - m[16],
        " reps_needed p/u=", Int(m[22]), "/", Int(m[23]),
        " ms=", m[19],
    )


fn _bench_queue_curve() -> Int:
    print("  [4] M/M/1 capacity study, lambda 0.80, baseline mu 1.00, 2000 customers, 40 reps")
    var mus = List[Float64]()
    mus.append(1.005)
    mus.append(1.01)
    mus.append(1.02)
    mus.append(1.05)
    mus.append(1.10)
    var prev: Float64 = -1.0
    var monotone = True
    var all_paired_decided = True
    for i in range(len(mus)):
        var m = _queue(0.80, 1.00, mus[i], 2000, 40, 4242, 0)
        if len(m) < 25 or m[0] < 1.0:
            print("      REFUSED at mu_B", mus[i])
            return 1
        if m[6] >= m[10]:
            print("  FAIL pairing did not reduce the variance at mu_B", mus[i])
            return 1
        if Int(m[20]) != 1:
            all_paired_decided = False
        if prev >= 0.0 and m[13] > prev:
            monotone = False
        prev = m[13]
        _print_queue("mu_B=", mus[i], m)
    if not monotone:
        print("  FAIL the ratio is not monotone in the size of the design change")
        return 1
    if not all_paired_decided:
        print("  FAIL a paired comparison failed to decide a real difference")
        return 1
    print(
        "  PASS the same curve appears on a real queue: 1000x for a 0.5% design change down to",
        "4.6x for a 10% one, so a CRN factor is meaningless without the effect size beside it",
    )
    return 0


fn _bench_queue_headline() -> Int:
    print("  [5] the number to publish: a 2% faster server, 2000 replications")
    var m = _queue(0.80, 1.00, 1.02, 2000, 2000, 4242, 0)
    if len(m) < 25 or m[0] < 1.0:
        print("      REFUSED")
        return 1
    print("      arm_A        mean=", m[1], " var=", m[2], " exact_Wq=", m[16])
    print("      arm_B paired mean=", m[3], " var=", m[4], " exact_Wq=", m[17])
    print("      PAIRED   diff mean=", m[5], " var=", m[6], " CI=[", m[7], ",", m[8], "]")
    print("      UNPAIRED diff mean=", m[9], " var=", m[10], " CI=[", m[11], ",", m[12], "]")
    print("      exact delta=", m[17] - m[16], "  corr(A,B)=", m[14],
          "  corr(A,B_indep)=", m[15])
    print("      variance ratio=", m[13], "  half-width=", m[24],
          "  replications needed paired=", Int(m[22]), " unpaired=", Int(m[23]))
    print("      wall_ms=", m[19], "(informational only — record the load average beside it)")
    var ratio = m[13]
    var need_ratio = Float64(Int(m[23])) / Float64(Int(m[22]))
    var rel = need_ratio / ratio - 1.0
    if rel < 0.0:
        rel = -rel
    print("      replication-count ratio", need_ratio, "vs variance ratio", ratio,
          " relative gap", rel)
    var exact_delta = m[17] - m[16]
    var covers = m[7] <= exact_delta and exact_delta <= m[8]
    print("      NOTE paired CI contains the exact steady-state delta:", covers,
          " — at 2000 replications with no warm-up truncation the half-width has shrunk below",
          "the initialisation bias; section [6] measures that bias and removes it")
    if ratio < 10.0 or ratio > 400.0:
        print("  FAIL the variance ratio left the plausible band for this design change")
        return 1
    if rel > 0.10:
        print("  FAIL 'n times fewer replications' does not agree with the variance ratio")
        return 1
    if Int(m[20]) != 1:
        print("  FAIL the paired comparison did not decide a 10.87% difference in mean wait")
        return 1
    var d = m[5]
    if d >= 0.0:
        print("  FAIL the paired difference has the wrong sign")
        return 1
    print(
        "  PASS a 2% faster server is decided by pairing with 2,015 replications where the",
        "unpaired workflow needs ~120,000 — that is the claim, and 59x is its size at THIS",
        "effect. The literature's 15.6x (Murphy 2013, full CRN) is the same statement at a",
        "different effect size, not a contradiction",
    )
    return 0


fn _bias_row(m: List[Float64], n_cust: Int, warmup: Int) -> List[Float64]:
    """[contains_exact, abs_rel_bias, ratio] for one bias-ladder rung, printed as it goes."""
    var out = List[Float64]()
    if len(m) < 25 or m[0] < 1.0:
        print("      REFUSED at", n_cust, "customers, warmup", warmup)
        return out^
    var exact = m[17] - m[16]
    var inside = m[7] <= exact and exact <= m[8]
    var rel = m[5] / exact - 1.0
    var arel = rel if rel >= 0.0 else -rel
    print("     ", n_cust, warmup, Int(m[18]), m[5], "[", m[7], ",", m[8], "]", exact,
          " contains_exact=", inside, " rel_bias=", rel, " ratio=", m[13])
    out.append(1.0 if inside else 0.0)
    out.append(arel)
    out.append(m[13])
    return out^


fn _bench_queue_bias() -> Int:
    """Where the 2000-replication CI of section 5 misses the exact delta, and why.

    Section 5 reports a paired CI of [-0.429096, -0.414964] against an exact steady-state delta of
    -0.434938 — the CI EXCLUDES the exact value. That is not a variance failure and widening the
    interval would be the wrong response: at 2000 customers from an empty system with no warm-up
    truncation the estimand is the finite-horizon difference, which sits about 2% short of the
    steady-state one, and at 2000 replications the half-width (0.7%) has shrunk below that bias.
    This section measures the bias directly and shows both textbook remedies removing it.
    """
    print("  [6] initialisation bias in the paired difference, and the two remedies")
    print("      customers warmup reps  d_paired      CI                        exact")
    var rows = List[Float64]()
    var inside_count = 0
    var n_rungs = 0
    var lo_ratio: Float64 = 1.0e18
    var hi_ratio: Float64 = -1.0
    var bias_untruncated: Float64
    var bias_truncated: Float64
    var bias_long: Float64

    # Flattened as [contains, |rel_bias|, ratio] triples: a `List[Float64]` is not implicitly
    # copyable in this toolchain, so the rungs are folded as they are produced.
    var cust = List[Int]()
    var warm = List[Int]()
    var reps = List[Int]()
    cust.append(2000)
    warm.append(0)
    reps.append(400)
    cust.append(2000)
    warm.append(200)
    reps.append(400)
    cust.append(2000)
    warm.append(500)
    reps.append(400)
    cust.append(20000)
    warm.append(0)
    reps.append(400)
    cust.append(2000)
    warm.append(500)
    reps.append(2000)
    for i in range(len(cust)):
        var r = _bias_row(
            _queue(0.80, 1.00, 1.02, cust[i], reps[i], 4242, warm[i]), cust[i], warm[i]
        )
        if len(r) < 3:
            return 1
        n_rungs += 1
        inside_count += Int(r[0])
        if r[2] < lo_ratio:
            lo_ratio = r[2]
        if r[2] > hi_ratio:
            hi_ratio = r[2]
        rows.append(r[1])
    bias_untruncated = rows[0]
    bias_truncated = rows[2]
    bias_long = rows[3]
    print("      |relative bias|: no truncation", bias_untruncated, " -> 500 discarded",
          bias_truncated, " -> 10x longer run", bias_long)
    print("      variance ratio across all five rungs:", lo_ratio, "to", hi_ratio)
    print("      CIs containing the exact delta:", inside_count, "of", n_rungs)
    if inside_count != n_rungs:
        print("  FAIL a paired CI missed the exact M/M/1 delta even after truncation")
        return 1
    if bias_untruncated < bias_truncated or bias_untruncated < bias_long:
        print("  FAIL truncation and a longer run did not both reduce the bias")
        return 1
    if lo_ratio < 20.0 or hi_ratio > 200.0:
        print("  FAIL the variance reduction is sensitive to the warm-up choice")
        return 1
    print(
        "  PASS the section-5 CI miss is initialisation bias, not a broken estimator: discarding",
        "500 of 2000 customers or lengthening the run 10x each cuts it from ~2% to ~0.1% and the",
        "CI then covers the exact delta at 2000 replications, while the variance ratio stays in",
        "the same band throughout — the pairing result does not depend on the warm-up choice",
    )
    return 0


# ── section 4: the property that makes any of this valid, checked on bits ─────


fn _c_tape(seed: Int, family: Int, n_scen: Int, horizon: Int, n_factors: Int) -> List[Int]:
    """[cells, tape_bit_equal, celldraw_bit_equal, raw_bit_equal, in_unit_interval]."""
    var cells = 0
    var eq_tape = 0
    var eq_cell = 0
    var eq_raw = 0
    var in_unit = 0
    var stream = UInt64(strat_stream_scenario())
    for r in range(n_scen):
        var tape_a = crn_scenario_tape(
            seed, family, r, horizon, n_factors, STRAT_FACTOR_UNIFORM, 0.0
        )
        var tape_b = crn_scenario_tape(
            seed, family, r, horizon, n_factors, STRAT_FACTOR_UNIFORM, 0.0
        )
        if len(tape_a) != horizon * n_factors or len(tape_b) != horizon * n_factors:
            return List[Int]()
        for t in range(horizon):
            for j in range(n_factors):
                var idx = t * n_factors + j
                cells += 1
                var ba = tape_a[idx].to_bits()
                if ba == tape_b[idx].to_bits():
                    eq_tape += 1
                var cd = crn_cell_draw(
                    seed, family, r, t, j, n_factors, STRAT_FACTOR_UNIFORM, 0.0
                )
                if cd.status == STRAT_OK and cd.has_value and cd.value.to_bits() == ba:
                    eq_cell += 1
                var raw = rng_uniform(
                    UInt64(seed), UInt64(family), UInt64(r), UInt64(t), UInt64(j), stream, 0
                )
                if raw.to_bits() == ba:
                    eq_raw += 1
                if tape_a[idx] >= 0.0 and tape_a[idx] < 1.0:
                    in_unit += 1
    var out = List[Int]()
    out.append(cells)
    out.append(eq_tape)
    out.append(eq_cell)
    out.append(eq_raw)
    out.append(in_unit)
    return out^


fn _c_streams(seed: Int, family: Int, n_scen: Int, horizon: Int, n_strategies: Int) -> List[Int]:
    """[words, cross_stream_collisions, env_words_moved, coin_pairs, coin_pairs_equal]."""
    var s_env = UInt64(strat_stream_scenario())
    var s_pol = UInt64(strat_stream_policy())
    var words = 0
    var collisions = 0
    var env_moved = 0
    var coin_pairs = 0
    var coin_equal = 0
    for r in range(n_scen):
        for t in range(horizon):
            var env = philox_word(UInt64(seed), UInt64(family), UInt64(r), UInt64(t), 0, s_env, 0)
            words += 1
            for s in range(n_strategies):
                var again = philox_word(
                    UInt64(seed), UInt64(family), UInt64(r), UInt64(t), 0, s_env, 0
                )
                if again != env:
                    env_moved += 1
                var coin = philox_word(
                    UInt64(seed), UInt64(family), UInt64(r), UInt64(t), UInt64(s), s_pol, 0
                )
                words += 1
                if coin == env:
                    collisions += 1
            for a in range(n_strategies):
                for b in range(a + 1, n_strategies):
                    var ca = philox_word(
                        UInt64(seed), UInt64(family), UInt64(r), UInt64(t), UInt64(a), s_pol, 0
                    )
                    var cb = philox_word(
                        UInt64(seed), UInt64(family), UInt64(r), UInt64(t), UInt64(b), s_pol, 0
                    )
                    coin_pairs += 1
                    if ca == cb:
                        coin_equal += 1
    var out = List[Int]()
    out.append(words)
    out.append(collisions)
    out.append(env_moved)
    out.append(coin_pairs)
    out.append(coin_equal)
    return out^


fn _c_queue_draws(
    lam: Float64, mu_a: Float64, mu_b: Float64, n: Int, seed: Int, n_reps: Int
) -> List[Float64]:
    """[draws, sA_matches_raw, sB_matches_raw, gaps, gaps_equal, max_rel_dev, cross_collisions]."""
    var draws = 0
    var sa_exact = 0
    var sb_exact = 0
    var gaps = 0
    var gaps_equal = 0
    var cross = 0
    var max_rel: Float64 = 0.0
    var s_serv = UInt64(de_stream_service())
    for r in range(1, n_reps + 1):
        var ga = qs_interarrivals(lam, n, seed, r)
        var gb = qs_interarrivals(lam, n, seed, r)
        var sa = qs_service_times(mu_a, n, seed, r)
        var sb = qs_service_times(mu_b, n, seed, r)
        if len(ga) != n or len(gb) != n or len(sa) != n or len(sb) != n:
            return List[Float64]()
        for i in range(n):
            gaps += 1
            if ga[i].to_bits() == gb[i].to_bits():
                gaps_equal += 1
            if ga[i].to_bits() == sa[i].to_bits():
                cross += 1
            var u = rng_uniform_left_open(UInt64(seed), 0, UInt64(r), UInt64(i), 0, s_serv, 0)
            draws += 1
            if (-log(u) / mu_a).to_bits() == sa[i].to_bits():
                sa_exact += 1
            if (-log(u) / mu_b).to_bits() == sb[i].to_bits():
                sb_exact += 1
            var la = sa[i] * mu_a
            var lb = sb[i] * mu_b
            var d = la - lb
            if d < 0.0:
                d = -d
            var rel = d / (la if la > 0.0 else 1.0)
            if rel > max_rel:
                max_rel = rel
    var out = List[Float64]()
    out.append(Float64(draws))
    out.append(Float64(sa_exact))
    out.append(Float64(sb_exact))
    out.append(Float64(gaps))
    out.append(Float64(gaps_equal))
    out.append(max_rel)
    out.append(Float64(cross))
    return out^


fn _c_sequential(seed: Int, family: Int, horizon: Int) -> List[Int]:
    """The negative control: what a STATEFUL consumer does when one arm takes an extra draw.

    [steps, addressed_bit_equal, sequential_bit_equal, first_divergence_step].
    """
    var stream = UInt64(strat_stream_scenario())
    var eq_addr = 0
    var eq_seq = 0
    var first_div = -1
    var cursor_a = 0
    var cursor_b = 1
    for t in range(horizon):
        var addr_a = rng_uniform(UInt64(seed), UInt64(family), 0, UInt64(t), 0, stream, 0)
        var addr_b = rng_uniform(UInt64(seed), UInt64(family), 0, UInt64(t), 0, stream, 0)
        if addr_a.to_bits() == addr_b.to_bits():
            eq_addr += 1
        var seq_a = rng_uniform(UInt64(seed), UInt64(family), 0, UInt64(cursor_a), 0, stream, 0)
        var seq_b = rng_uniform(UInt64(seed), UInt64(family), 0, UInt64(cursor_b), 0, stream, 0)
        if seq_a.to_bits() == seq_b.to_bits():
            eq_seq += 1
        elif first_div < 0:
            first_div = t
        cursor_a += 1
        cursor_b += 1
    var out = List[Int]()
    out.append(horizon)
    out.append(eq_addr)
    out.append(eq_seq)
    out.append(first_div)
    return out^


fn _bench_raw_draws() -> Int:
    print("  [7] the CRN precondition, on RAW DRAWS compared as 64-bit patterns")
    var a = _c_tape(12345, 7, 32, 64, 2)
    if len(a) < 5:
        print("  FAIL a tape was refused")
        return 1
    print("      tape: cells=", a[0], " two_generations_bit_equal=", a[1],
          " crn_cell_draw_bit_equal=", a[2], " raw_counter_rng_bit_equal=", a[3],
          " in_[0,1)=", a[4])
    var b = _c_tape(4242, 3, 16, 128, 1)
    if len(b) < 5:
        print("  FAIL a tape was refused")
        return 1
    print("      tape: cells=", b[0], " two_generations_bit_equal=", b[1],
          " crn_cell_draw_bit_equal=", b[2], " raw_counter_rng_bit_equal=", b[3],
          " in_[0,1)=", b[4])
    var s = _c_streams(12345, 7, 8, 64, 4)
    print("      streams: words=", s[0], " cross_stream_collisions=", s[1],
          " env_words_moved_by_strategy=", s[2], " coin_pairs=", s[3],
          " coin_pairs_equal=", s[4])
    print("      stream ids: scenario=", strat_stream_scenario(), " policy=",
          strat_stream_policy(), " de_arrival=", de_stream_arrival(), " de_service=",
          de_stream_service())
    var q = _c_queue_draws(0.80, 1.00, 1.02, 2000, 4242, 5)
    if len(q) < 7:
        print("  FAIL a queue draw vector was refused")
        return 1
    print("      queue: service_draws=", Int(q[0]), " sA_equals_-log(u)/muA=", Int(q[1]),
          " sB_equals_-log(u)/muB=", Int(q[2]), " arrival_gaps=", Int(q[3]),
          " gaps_bit_equal_across_designs=", Int(q[4]), " max_rel_dev(s*mu)=", q[5],
          " arrival/service_collisions=", Int(q[6]))
    var neg = _c_sequential(12345, 7, 64)
    print("      negative control: steps=", neg[0], " addressed_bit_equal=", neg[1],
          " sequential_bit_equal=", neg[2], " first_divergence_step=", neg[3])
    var fail = 0
    if a[1] != a[0] or a[2] != a[0] or a[3] != a[0] or a[4] != a[0]:
        fail += 1
    if b[1] != b[0] or b[2] != b[0] or b[3] != b[0] or b[4] != b[0]:
        fail += 1
    if s[1] != 0 or s[2] != 0 or s[4] != 0:
        fail += 1
    if Int(q[1]) != Int(q[0]) or Int(q[2]) != Int(q[0]) or Int(q[4]) != Int(q[3]):
        fail += 1
    if Int(q[6]) != 0:
        fail += 1
    if q[5] > 4.0e-16:
        print("      s*mu disagreed by more than 2 ulp:", q[5])
        fail += 1
    if neg[1] != neg[0]:
        fail += 1
    if neg[2] != 0 or neg[3] != 0:
        print("      the sequential control did NOT diverge, so it is not a control")
        fail += 1
    if fail > 0:
        print("  FAIL", fail, "bit-level CRN preconditions did not hold")
        return 1
    print(
        "  PASS every draw both designs see is the same 64-bit pattern, across three code paths",
        "and on the queue's inverse-CDF service times, while a sequential consumer of the same",
        "generator diverges at the first step after an extra draw",
    )
    return 0


fn _bench_t_table() -> Int:
    """scipy is not importable in this environment, so the t quantile is checked against tables."""
    print("  [8] inference_t_quantile(0.975, df) vs published Student-t table values")
    var dfs = List[Float64]()
    var tab = List[Float64]()
    dfs.append(1.0)
    tab.append(12.70620)
    dfs.append(2.0)
    tab.append(4.302653)
    dfs.append(5.0)
    tab.append(2.570582)
    dfs.append(10.0)
    tab.append(2.228139)
    dfs.append(30.0)
    tab.append(2.042272)
    dfs.append(39.0)
    tab.append(2.022691)
    dfs.append(399.0)
    tab.append(1.965927)
    dfs.append(1999.0)
    tab.append(1.961151)
    var worst: Float64 = 0.0
    for i in range(len(dfs)):
        var ours = inference_t_quantile(0.975, dfs[i])
        var d = ours - tab[i]
        if d < 0.0:
            d = -d
        if d > worst:
            worst = d
        print("      df=", dfs[i], " ours=", ours, " table=", tab[i], " abs_err=", d)
    print("      worst absolute error:", worst)
    if worst > 1.0e-5:
        print("  FAIL a t quantile is off the published table by more than 1e-5")
        return 1
    print(
        "  PASS every CI in this file rests on a t quantile that matches the published table to",
        "1e-5, checked against tables because scipy is not importable here",
    )
    return 0


fn main():
    print("\n=== bench_crn_variance_reduction: what the 174x is, and what it is not ===")
    print("Gates are on closed forms, exact bit equality and arithmetic identities.")
    print("No wall-clock number here is gated or comparable across sizes; print the load average")
    print("of the host beside any timing line you quote.\n")
    var failures = 0
    failures += _bench_toy_curve()
    print("")
    failures += _bench_toy_horizon_invariance()
    print("")
    failures += _bench_seed_spread()
    print("")
    failures += _bench_queue_curve()
    print("")
    failures += _bench_queue_headline()
    print("")
    failures += _bench_queue_bias()
    print("")
    failures += _bench_raw_draws()
    print("")
    failures += _bench_t_table()
    print("")
    if failures == 0:
        print("BENCH_GATE crn_variance_reduction PASS")
    else:
        print("BENCH_GATE crn_variance_reduction FAIL " + String(failures))
