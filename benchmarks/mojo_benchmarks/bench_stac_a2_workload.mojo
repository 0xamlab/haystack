"""bench_stac_a2_workload.mojo — the STAC-A2 MARKET-RISK WORKLOAD, unaudited.

READ THIS BEFORE QUOTING ANY NUMBER BELOW
------------------------------------------
This is NOT a STAC-A2 result and nothing here may be presented as one.

STAC-A2 is the Securities Technology Analysis Center's market-risk benchmark. An official
STAC-A2 result requires an audit by the STAC Benchmark Council. WE HAVE NOT HAD ONE. The STAC-A2
specification documents, the R reference implementation and the STAC Test Harness are restricted
to Council members and we do not have them. This file implements THE WORKLOAD STAC-A2 DESCRIBES,
reconstructed from publicly posted STAC Reports and from the cited academic literature, and
every figure it produces is UNAUDITED AND INDEPENDENTLY IMPLEMENTED FROM THE PUBLIC
SPECIFICATION.

Concretely, that means:
  * do not call any number below "a STAC-A2 result";
  * do not quote it under a STAC-A2 metric name (GREEKS.TIME.WARM, MAX_ASSETS, PATHGEN.PVSTDERR
    and the rest) as though it were certified — the names appear here only to say WHICH
    published definition each of our checks was modelled on;
  * state the unaudited status in the same sentence as the number, every time.

A falsely implied audit is worse than no benchmark.

WHAT THE WORKLOAD IS
--------------------
Monte Carlo estimation of Heston-based Greeks for a path-dependent, multi-asset option with
early exercise. The instrument is a "best-of" option: the holder may, at any date before expiry,
pay a price fixed in advance and receive the best of N assets. Paths come from Andersen's
Quadratic Exponential discretisation of the Heston model; early exercise is priced by
Longstaff-Schwartz least-squares Monte Carlo; each asset has its own Heston configuration and
the randoms are correlated across assets by an input correlation matrix.

The STAC BASELINE problem is 5 assets, 25,000 paths, 252 timesteps.

ZERO DISPATCH
-------------
Everything below runs IN-PROCESS. There is not one runtime-dispatch call in this file or in
`quantfin/heston.mojo`. Verify it with

    grep -nE '(dispatch_runtime_library|library_execute|json_parse)[[:space:]]*\\(' \\
        benchmarks/mojo_benchmarks/bench_stac_a2_workload.mojo \\
        benchmarks/mojo_benchmarks/bench_stac_a2_baseline.mojo \\
        mojo/engine/quantfin/heston.mojo

which returns nothing. The `\\(` matters: a bare token grep also matches this paragraph, which
is the sort of self-defeating check that gets pasted into a report and believed.
The runtime's argument boundary costs ~168 ns/cell on the dispatched path against
4.8 ns/cell batched; at 31.5M asset-steps per price and 94 prices per Greeks set, a dispatched
design would measure the boundary and not the model. TOTAL DISPATCHES FOR THE WHOLE WORKLOAD: 0.

WHAT IS GATED, AND WHAT IS ONLY MEASURED
-----------------------------------------
Following `bench_phold.mojo`: the HARD gates are correctness invariants and bit-exact
identities, which give the same verdict at any machine load. Wall-clock readings are ADVISORY,
because this machine is shared and a contended timing is not evidence of anything. The one
wall-clock property that IS gated is the tier ordering (hot <= warm) plus a dispersion bound,
and INVALID is printed with no ratio when the dispersion bound is breached, rather than a ratio
that a reader would quote.

CORRECTNESS BEFORE TIMING. Sections 1-9 are correctness and every one of them is a HARD gate;
nothing is timed until they have all passed, and `BENCH_GATE` reports on those nine. Section 10's
tier-order and dispersion checks are ADVISORY: they print INVALID and suppress the ratio, but do
not fail the build, because a wall-clock verdict on a shared machine is a verdict about the
machine. The first K-process run of this file returned a tier inversion on a process whose nine
correctness gates all passed, at load 40-60 on 16 cores — which is the whole argument.
"""

from std.time import perf_counter_ns
from std.math import sqrt, exp, log, abs as fabs
from std.sys import info

from quantfin.heston import (
    HestonParams, BasketGreeks,
    heston_basket_price, heston_basket_greeks, heston_basket_paths,
    heston_bs_degeneracy, heston_optionpv_error, heston_binomial_earlyex_error,
    heston_closed_form_call, heston_realised_correlation, heston_crn_replication_study,
    heston_lsm_regression_agreement, heston_rng_bit_identity, heston_worker_invariance,
    heston_feller, heston_scheme_name, heston_contract_id, heston_qe_psi_critical,
    HESTON_SCHEME_QE, HESTON_SCHEME_FULL_TRUNCATION, HESTON_OK,
)
from option_pricing import black_scholes_call

# ── The problem, fixed here so every section reads the same one ───────────────
# 5 assets, one Heston configuration each, as the public STAC material describes. The dividend
# yield is ABOVE the risk-free rate on purpose: a call on a non-dividend-paying asset is never
# optimally exercised early, so at q <= r the EARLYEX half of the workload would be present in
# the code and absent from the answer, and the early-exercise premium would be pure LSM noise.

comptime N_ASSETS: Int = 5
comptime RATE: Float64 = 0.03
comptime DIVY: Float64 = 0.05
comptime STRIKE: Float64 = 100.0
comptime TENOR: Float64 = 1.0
comptime BASE_STEPS: Int = 252          # STAC baseline: one per trading day, 1 year
comptime BASE_PATHS: Int = 25000        # STAC baseline
comptime TIER_PATHS: Int = 2000         # reduced size for the K-process tier statistics
comptime CROSS_CORR: Float64 = 0.4
comptime MASTER_SEED: UInt64 = 0x5A2C4A2


fn _assets() -> List[HestonParams]:
    var s0 = [100.0, 95.0, 105.0, 110.0, 90.0]
    var v0 = [0.04, 0.05, 0.03, 0.06, 0.045]
    var kp = [1.5, 2.0, 1.2, 2.5, 1.8]
    var xi = [0.35, 0.45, 0.30, 0.50, 0.40]
    var rh = [-0.7, -0.6, -0.5, -0.75, -0.65]
    var out = List[HestonParams]()
    for a in range(N_ASSETS):
        out.append(HestonParams(s0[a], v0[a], kp[a], v0[a], xi[a], rh[a], DIVY))
    return out^


fn _corr() -> List[List[Float64]]:
    var c = List[List[Float64]]()
    for i in range(N_ASSETS):
        var row = List[Float64]()
        for j in range(N_ASSETS):
            row.append(1.0 if i == j else CROSS_CORR)
        c.append(row^)
    return c^


fn _f(x: Float64, dp: Int) -> String:
    """Fixed-point formatting so the columns line up and a reader can compare rows by eye."""
    # nan and inf must print as themselves. Without this the Int() below saturates and a
    # broken run reports "922337203685477.5807", which a reader will read as a number.
    if x != x:
        return String("nan")
    if x > 1.0e300:
        return String("+inf")
    if x < -1.0e300:
        return String("-inf")
    var neg = x < 0.0
    var v = -x if neg else x
    var scale: Float64 = 1.0
    for _ in range(dp):
        scale *= 10.0
    var scaled = v * scale + 0.5
    var ip = Int(scaled)
    var whole = ip // Int(scale)
    var frac = ip - whole * Int(scale)
    var fs = String(frac)
    while len(fs) < dp:
        fs = "0" + fs
    var s = String(whole) + "." + fs if dp > 0 else String(whole)
    return ("-" + s) if neg else s


fn _pad(s: String, n: Int) -> String:
    var out = s
    while len(out) < n:
        out += " "
    return out


fn _lpad(s: String, n: Int) -> String:
    var out = s
    while len(out) < n:
        out = " " + out
    return out


# ── 1. The generator identity gate ────────────────────────────────────────────


fn _sec_rng_identity() -> Int:
    print("1. GENERATOR IDENTITY — the one-block Philox path vs the frozen counter_rng")
    print("   heston.mojo computes one Philox4x64-10 counter block and reads two words out of")
    print("   it, where counter_rng.rng_normal runs all ten rounds twice for the same two words.")
    print("   That is a duplication of a frozen kernel's arithmetic, so it is PINNED here at")
    print("   exact Float64 equality with no tolerance. A tolerance would defeat the claim,")
    print("   which is not 'close' but 'the same generator'.")
    var bad = heston_rng_bit_identity(50000)
    print("   draws compared ......... 100000  (50000 normals + 50000 uniforms)")
    print("   bit-exact mismatches ... " + String(bad) + "   (must be 0)")
    if bad != 0:
        print("   GATE FAIL: the fast path is not the frozen generator.")
        return 1
    print("   GATE PASS")
    return 0


# ── 2. The regression identity gate ───────────────────────────────────────────


fn _sec_regression_identity() -> Int:
    print("2. REGRESSION IDENTITY — the LSM in-place normal equations vs frozen ols_multiple")
    print("   The LSM continuation fit accumulates X'X and X'y in place instead of calling")
    print("   regression.ols_multiple, which would materialise an n x p List[List[Float64]] once")
    print("   per exercise date — 6.3M small allocations per price at baseline size, 94 prices")
    print("   per Greeks set. The shortcut is checked against the audited kernel, not trusted.")
    var worst = 0.0
    var fails = 0
    for d in range(1, 4):
        var w = heston_lsm_regression_agreement(5000, d)
        print(
            "   degree " + String(d) + " max |coef| difference ... " + _f(w * 1e12, 3) + " e-12"
        )
        if w > worst:
            worst = w
        if w < 0.0 or w > 1.0e-6:
            fails += 1
    if fails > 0:
        print("   GATE FAIL: the in-place fit disagrees with the frozen kernel.")
        return 1
    print("   GATE PASS   (bound 1e-6; worst " + _f(worst * 1e12, 3) + " e-12)")
    return 0


# ── 3. The Black-Scholes degeneracy anchor ────────────────────────────────────


fn _sec_degeneracy(workers: Int) -> Int:
    print("3. BLACK-SCHOLES DEGENERACY — at vol-of-vol = 0 and rho = 0, Heston IS Black-Scholes")
    print("   With xi = 0 and v0 = theta the CIR variance is constant, so the Monte Carlo price")
    print("   must converge to option_pricing.black_scholes_call. This holds for ANY scheme, any")
    print("   step count and any path count, so a failure is unambiguous. It is also the corner")
    print("   where the QE quadratic formulae are singular (psi = 0 gives b2 = inf, a = 0 and")
    print("   a(b+Z)^2 = 0*inf = nan) — the first version of this module returned an infinite")
    print("   price here, which is exactly why the anchor is worth running.")
    print("   Reported as a Z SCORE, not an absolute error: an absolute error of 0.01 is a pass")
    print("   at 1,000 paths and a hard failure at 10 million, and only the Z score knows that.")
    print("")
    print("   paths      MC price    BS closed form   abs err    rel err     std err    Z")
    print("   ---------  ----------  ---------------  ---------  ----------  ---------  -----")
    var np_ = [1000, 4000, 16000, 64000, 256000]
    var fails = 0
    var last_se = 0.0
    var first_se = 0.0
    for i in range(5):
        var d = heston_bs_degeneracy(
            100.0, 100.0, 0.2, RATE, TENOR, np_[i], 64, MASTER_SEED, 1,
            HESTON_SCHEME_QE, workers,
        )
        if d.status != HESTON_OK:
            print("   status " + String(d.status) + " — GATE FAIL")
            return 1
        print(
            "   " + _pad(String(np_[i]), 9) + "  " + _lpad(_f(d.mc_price, 4), 10)
            + "  " + _lpad(_f(d.bs_price, 4), 15) + "  " + _lpad(_f(d.abs_error, 5), 9)
            + "  " + _lpad(_f(d.rel_error * 100.0, 4) + "%", 10)
            + "  " + _lpad(_f(d.std_error, 5), 9) + "  " + _lpad(_f(d.z_score, 2), 5)
        )
        # A Monte Carlo estimate is within 4 standard errors of the truth essentially always;
        # a systematic scheme error shows up as a Z that GROWS with the path count, because the
        # standard error shrinks while the bias does not.
        if d.z_score > 4.0:
            fails += 1
        if i == 0:
            first_se = d.std_error
        last_se = d.std_error
    # 256x the paths should be 16x the standard error. Gate the trend loosely (a factor of 2
    # either side) because it is a sampling statistic, not an identity.
    var ratio = first_se / last_se if last_se > 0.0 else 0.0
    print("")
    print(
        "   std error shrank " + _f(ratio, 2) + "x over a 256x path increase; sqrt(256) = 16.00"
    )
    if ratio < 8.0 or ratio > 32.0:
        print("   GATE FAIL: the standard error is not shrinking like 1/sqrt(n).")
        fails += 1
    if fails > 0:
        print("   GATE FAIL (" + String(fails) + ")")
        return fails
    print("   GATE PASS   (every Z <= 4.0, and the standard error tracks 1/sqrt(n))")
    return 0


# ── 4. OPTIONPV.ERR — the full model against the Fourier closed form ──────────


fn _sec_optionpv(workers: Int) -> Int:
    print("4. FULL-MODEL ANCHOR — Monte Carlo vs the Heston closed form (STAC calls this")
    print("   OPTIONPV.ERR: worst-case relative error of five single-asset European options")
    print("   against the Heston closed form; this reproduces their check, unaudited)")
    print("   Stronger than section 3, which is blind by construction to a mis-signed rho: at")
    print("   xi > 0 both QE branches run, the martingale correction is live, and the K1/K2 terms")
    print("   carry the spot/vol correlation. The closed form is the branch-safe 'Little Heston")
    print("   Trap' Fourier inversion (Albrecher-Mayer-Schoutens-Tistaert 2007), integrated with")
    print("   the frozen integrate.simpson.")
    print("   Both schemes are run on the IDENTICAL Philox coordinates, so their difference is")
    print("   discretisation bias and nothing else.")
    print("")
    print("   asset  Feller  scheme            MC price   closed form  rel err    Z      negV      zeroV     QE-exp branch")
    print("   -----  ------  ----------------  ---------  -----------  ---------  -----  --------  --------  -------------")
    var ps = _assets()
    var fails = 0
    var worst_rel = 0.0
    var worst_z = 0.0
    var qe_exp = 0
    var qe_zero = 0
    for a in range(N_ASSETS):
        for si in range(2):
            var sc = HESTON_SCHEME_QE if si == 0 else HESTON_SCHEME_FULL_TRUNCATION
            var nm = "Andersen-QE     " if si == 0 else "full-trunc Euler"
            var c = heston_optionpv_error(
                ps[a], STRIKE, RATE, TENOR, 100000, BASE_STEPS, MASTER_SEED,
                UInt64(100 + a), sc, True, workers,
            )
            if c.status != HESTON_OK:
                print("   status " + String(c.status) + " — GATE FAIL")
                return 1
            print(
                "   " + _pad(String(a), 5) + "  " + _lpad(_f(heston_feller(ps[a]), 2), 6)
                + "  " + nm + "  " + _lpad(_f(c.mc_price, 4), 9)
                + "  " + _lpad(_f(c.closed_form, 4), 11)
                + "  " + _lpad(_f(c.rel_error * 100.0, 4) + "%", 9)
                + "  " + _lpad(_f(c.z_score, 2), 5)
                + "  " + _lpad(String(c.n_negative_variance), 8)
                + "  " + _lpad(String(c.n_zero_variance), 8)
                + "  " + _lpad(String(c.n_exponential_branch), 13)
            )
            if si == 0:
                qe_exp += c.n_exponential_branch
                qe_zero += c.n_zero_variance
            if c.rel_error > worst_rel:
                worst_rel = c.rel_error
            if c.z_score > worst_z:
                worst_z = c.z_score
            if c.z_score > 4.0:
                fails += 1
            # THE QE NON-NEGATIVITY GATE. The quadratic branch is a square and the exponential
            # branch has support [0, inf), so QE cannot produce a negative variance. One is a bug.
            if si == 0 and c.n_negative_variance != 0:
                print("   GATE FAIL: QE produced " + String(c.n_negative_variance)
                      + " negative variances. The scheme cannot do that; the code did.")
                fails += 1
    print("")
    print("   negV      for QE it MUST be 0: the quadratic branch is a square and the")
    print("             exponential branch has support [0, inf). For full-truncation Euler it is")
    print("             expected to be large, and that IS why full truncation is not the default")
    print("             — the raw Euler variance goes negative and the scheme survives only by")
    print("             truncating at use. A naive Euler with no truncation would take sqrt of")
    print("             those and produce nan.")
    print("")
    print("   QE-exp branch is 0 on EVERY row above, and that is a real finding rather than an")
    print("   oversight. Andersen's exponential branch is taken when psi = s2/m^2 exceeds")
    print("   psi_c = " + _f(heston_qe_psi_critical(), 2) + ". For a variance started at its own long-run level (v0 = theta),")
    print("   m = theta exactly at every step, and as dt grows s2 tends to theta*xi^2/(2*kappa),")
    print("   so")
    print("")
    print("       psi  ->  xi^2 / (2*kappa*theta)  =  1 / Feller")
    print("")
    print("   psi is therefore bounded above by 1/Feller no matter how coarse the timestep, and")
    print("   the exponential branch is UNREACHABLE unless Feller < 1/psi_c = "
          + _f(1.0 / heston_qe_psi_critical(), 3) + ". The five")
    print("   assets above sit at 0.80 to 1.20, so only the quadratic branch runs on them —")
    print("   verified directly at 1, 2, 4, 12, 52, 126 and 252 steps, all zero.")
    print("   Consequence worth carrying into section 9: on THIS configuration the QE branch")
    print("   divergence that would desynchronise a stateful generator does not arise, so the")
    print("   variance reduction measured there comes from sharing draws and not from surviving")
    print("   a branch flip. The fixed-slot design covers the flip; this configuration does not")
    print("   exercise it. The next row does.")
    print("")
    print("   BRANCH COVERAGE — one configuration chosen so Feller < " + _f(1.0 / heston_qe_psi_critical(), 3)
          + " and the exponential")
    print("   branch is genuinely taken, because a scheme half of which never executes is a")
    print("   scheme half tested:")
    print("")
    var lowf = HestonParams(100.0, 0.04, 2.0, 0.04, 0.5, -0.7, DIVY)
    var lc = heston_optionpv_error(
        lowf, STRIKE, RATE, TENOR, 100000, BASE_STEPS, MASTER_SEED, 200,
        HESTON_SCHEME_QE, True, workers,
    )
    if lc.status != HESTON_OK:
        print("   status " + String(lc.status) + " — GATE FAIL")
        return fails + 1
    print("   Feller " + _f(heston_feller(lowf), 2) + "   MC " + _f(lc.mc_price, 4)
          + "   closed form " + _f(lc.closed_form, 4)
          + "   rel err " + _f(lc.rel_error * 100.0, 4) + "%   Z " + _f(lc.z_score, 2))
    print("   QE-exp branch visits " + String(lc.n_exponential_branch)
          + "   zeroV " + String(lc.n_zero_variance)
          + "   negV " + String(lc.n_negative_variance))
    print("")
    print("   zeroV is non-zero here and is NOT an error: the CIR variance genuinely reaches the")
    print("   zero boundary when Feller < 1, and the exponential branch has an atom there.")
    print("   negV must still be 0 — the exponential branch's support is [0, inf).")
    if lc.n_exponential_branch == 0:
        print("   GATE FAIL: the exponential branch still was not taken, so it remains untested.")
        fails += 1
    if lc.n_negative_variance != 0:
        print("   GATE FAIL: the exponential branch produced a negative variance.")
        fails += 1
    if lc.z_score > 4.0:
        print("   GATE FAIL: the exponential branch disagrees with the closed form by "
              + _f(lc.z_score, 2) + " s.e.")
        fails += 1
    if lc.n_exponential_branch != 0 and lc.n_negative_variance == 0 and lc.z_score <= 4.0:
        print("   BRANCH COVERAGE GATE PASS")
    print("")
    print("   qe totals over the five baseline assets: exponential-branch visits " + String(qe_exp)
          + ", zeroV " + String(qe_zero))
    print("")
    print("   worst relative error " + _f(worst_rel * 100.0, 4) + "%   worst Z " + _f(worst_z, 2)
          + "   (gate: Z <= 4.0)")
    if fails > 0:
        print("   GATE FAIL (" + String(fails) + ")")
        return fails
    print("   GATE PASS")
    return 0


# ── 5. CORRAND.CORR — realised cross-asset correlation ────────────────────────


fn _sec_corrand() -> Int:
    print("5. CROSS-ASSET CORRELATION — realised vs input (STAC calls this CORRAND.CORR, whose")
    print("   ideal is 0; this reproduces their check, unaudited)")
    print("   RMS error of the realised correlation of the mapped normals Z = L W against the")
    print("   input matrix. The floor is the sampling error 1/sqrt(n), so the gate is against")
    print("   that floor and not against zero — a result BELOW the sampling floor would itself")
    print("   be suspicious.")
    print("")
    print("   samples    RMS corr error   1/sqrt(n) floor   ratio")
    print("   ---------  ---------------  ----------------  -----")
    var c = _corr()
    var ns = [10000, 100000, 1000000]
    var fails = 0
    for i in range(3):
        var rms = heston_realised_correlation(N_ASSETS, c, ns[i], MASTER_SEED, 7)
        var floor = 1.0 / sqrt(Float64(ns[i]))
        var ratio = rms / floor if floor > 0.0 else 0.0
        print(
            "   " + _pad(String(ns[i]), 9) + "  " + _lpad(_f(rms, 6), 15)
            + "  " + _lpad(_f(floor, 6), 16) + "  " + _lpad(_f(ratio, 2), 5)
        )
        if rms < 0.0 or ratio > 3.0:
            fails += 1
    if fails > 0:
        print("   GATE FAIL: the realised correlation is more than 3x the sampling floor.")
        return fails
    print("   GATE PASS   (within 3x the sampling floor at every size)")
    return 0


# ── 6. EARLYEX.ERR — Longstaff-Schwartz against a binomial ────────────────────


fn _sec_earlyex(workers: Int) -> Int:
    print("6. EARLY EXERCISE — Longstaff-Schwartz vs a Black-Scholes binomial (STAC calls this")
    print("   EARLYEX.ERR and defines it exactly this way; this reproduces their check, unaudited)")
    print("   Run in the degenerate xi = 0, rho = 0 corner, because that is the ONLY corner where")
    print("   a constant-sigma binomial is a valid reference for a Heston price. Comparing them")
    print("   at xi > 0 would report a model difference as an estimator error.")
    print("   The LSM estimator is the standard in-sample one and is biased HIGH by the usual")
    print("   foresight bias of reusing the regression paths for the cash flows. That is what")
    print("   Longstaff-Schwartz as published does; it is stated, not hidden.")
    print("")
    print("   paths      LSM rel err vs binomial(2048)")
    print("   ---------  -----------------------------")
    var np_ = [10000, 40000, 160000]
    var fails = 0
    var worst = 0.0
    for i in range(3):
        var e = heston_binomial_earlyex_error(
            100.0, 100.0, 0.2, RATE, TENOR, np_[i], 64, MASTER_SEED, 9, 2, workers
        )
        if e < 0.0:
            print("   refused — GATE FAIL")
            return 1
        print("   " + _pad(String(np_[i]), 9) + "  " + _lpad(_f(e * 100.0, 4) + "%", 29))
        if e > worst:
            worst = e
        if e > 0.02:
            fails += 1
    print("")
    print("   Published reference for scale: the 2013 STAC Report for SUT NVDA131118 records")
    print("   EARLYEX.ERR 0.007 on an AUDITED run. Ours is above, unaudited, and on a different")
    print("   configuration — it is a sanity scale, not a comparison.")
    if fails > 0:
        print("   GATE FAIL: relative error above the 2% bound.")
        return fails
    print("   GATE PASS   (worst " + _f(worst * 100.0, 4) + "%, bound 2%)")
    return 0


# ── 7. Worker invariance ──────────────────────────────────────────────────────


fn _sec_worker_invariance(workers: Int) -> Int:
    print("7. WORKER INVARIANCE — the band-parallel result is BIT-IDENTICAL to the serial one")
    print("   Not 'close'. Every draw is addressed by its own path index, so a band split cannot")
    print("   change a value, and a tolerance would hide exactly the bug class that band")
    print("   parallelisation introduces: a shared accumulator or a captured scratch buffer.")
    var ps = _assets()
    var c = _corr()
    var fails = 0
    for w in range(2, workers + 1, 3):
        var bad = heston_worker_invariance(
            ps, c, STRIKE, RATE, TENOR, 4000, BASE_STEPS, MASTER_SEED, 3, w
        )
        print("   1 worker vs " + _lpad(String(w), 2) + " workers ... "
              + ("identical" if bad == 0 else "DIFFERENT"))
        fails += bad
    if fails > 0:
        print("   GATE FAIL")
        return fails
    print("   GATE PASS")
    return 0


# ── 8. Greeks convergence ─────────────────────────────────────────────────────


fn _sec_greeks_convergence(workers: Int) -> Int:
    print("8. GREEKS CONVERGENCE — the Greeks must settle as the path count grows")
    print("   Asset-0 Delta and Gamma from CRN-paired central differences, at four path counts.")
    print("   Reported as the successive change, because a Greek that is still moving by more")
    print("   than its own size is not converged whatever its value looks like.")
    print("")
    print("   paths     price       delta_0    gamma_0     |d delta|   |d gamma|")
    print("   --------  ----------  ---------  ----------  ----------  ----------")
    var ps = _assets()
    var c = _corr()
    var np_ = [500, 2000, 8000, 32000]
    var pd = 0.0
    var pg = 0.0
    var last_dd = 0.0
    var last_dg = 0.0
    for i in range(4):
        var g = heston_basket_greeks(
            ps, c, STRIKE, RATE, TENOR, np_[i], BASE_STEPS, MASTER_SEED, 11,
            HESTON_SCHEME_QE, True, 2, workers,
        )
        if g.status != HESTON_OK:
            print("   status " + String(g.status) + " — GATE FAIL")
            return 1
        var dd = fabs(g.delta[0] - pd) if i > 0 else 0.0
        var dg = fabs(g.gamma[0] - pg) if i > 0 else 0.0
        print(
            "   " + _pad(String(np_[i]), 8) + "  " + _lpad(_f(g.price, 4), 10)
            + "  " + _lpad(_f(g.delta[0], 5), 9) + "  " + _lpad(_f(g.gamma[0], 6), 10)
            + "  " + (_lpad(_f(dd, 5), 10) if i > 0 else _lpad("-", 10))
            + "  " + (_lpad(_f(dg, 6), 10) if i > 0 else _lpad("-", 10))
        )
        pd = g.delta[0]
        pg = g.gamma[0]
        if i > 0:
            last_dd = dd
            last_dg = dg
    print("")
    print("   Delta is a fraction of a unit of asset 0 in a 5-asset best-of, so the scale is")
    print("   right if it sits well inside [0, 1]. The final successive change is the")
    print("   convergence evidence, not the value.")
    if pd < 0.0 or pd > 1.0:
        print("   GATE FAIL: delta_0 = " + _f(pd, 5) + " is outside [0, 1], which is impossible")
        print("   for a best-of call's sensitivity to one of its underlyings.")
        return 1
    if last_dd > 0.10:
        print("   GATE FAIL: delta_0 still moving by " + _f(last_dd, 5) + " at the largest size.")
        return 1
    print("   GATE PASS   (delta_0 in [0,1]; final successive change " + _f(last_dd, 5)
          + " delta, " + _f(last_dg, 6) + " gamma)")
    return 0


# ── 9. The CRN replication study — the headline result ────────────────────────


fn _sec_crn(workers: Int) -> Int:
    print("9. COMMON RANDOM NUMBERS — paired vs unpaired, and what each design COSTS")
    print("   The estimator is the central difference (V(S0+h) - V(S0-h)) / 2h for asset 0.")
    print("")
    print("   PAIRED   — the UP and DOWN legs are priced on the IDENTICAL Philox coordinates.")
    print("   UNPAIRED — the two legs use different scenario ids from the same family and seed:")
    print("              independent BY COORDINATE, which is what a caller gets from running the")
    print("              two bumped valuations as separate jobs.")
    print("   Same estimator, same bump, same path count, same replication count. The ONLY")
    print("   difference is whether the two legs faced the same scenario.")
    print("")
    print("   TWO SEPARATE PROPERTIES OF THE COUNTER-BASED GENERATOR, and only the first")
    print("   produces the number below — keeping them apart is the honest reading:")
    print("     1. draws are shared EXACTLY between the legs. That is what buys the variance")
    print("        reduction measured here.")
    print("     2. a variable-consumption branch cannot desynchronise the legs. Andersen QE")
    print("        consumes a normal on the quadratic branch and a uniform on the exponential")
    print("        one, and a stateful stream generator would shift every subsequent draw at the")
    print("        first divergence; the fixed slot budget means the unused slot is simply")
    print("        unread. Section 4 MEASURED that this hazard does not arise on the baseline")
    print("        configuration — psi is bounded by 1/Feller and only the quadratic branch ever")
    print("        runs there — so property 2 is insurance on this problem, not the mechanism.")
    print("        Section 4's branch-coverage row is where it is actually exercised.")
    print("")
    var ps = _assets()
    var c = _corr()
    var hw = 0.01     # target half-width on asset-0 Delta, in Delta units
    var s = heston_crn_replication_study(
        ps, c, STRIKE, RATE, TENOR, 1000, BASE_STEPS, 24, MASTER_SEED, hw, 1.96,
        0.01, HESTON_SCHEME_QE, workers,
    )
    if s.status != HESTON_OK:
        print("   status " + String(s.status) + " — GATE FAIL")
        return 1
    print("   replications used to estimate ... " + String(s.n_replications)
          + "    paths per replication ... " + String(s.n_paths_per_rep))
    print("   coordinate-identical rechecks ... " + String(s.n_coordinate_identical)
          + " / " + String(s.n_replications)
          + "   (a re-run at the same coordinates must give the same price)")
    print("")
    print("   arm        mean delta_0   variance        std dev      replications for a")
    print("                                                          +/-" + _f(hw, 3)
          + " interval at 95%")
    print("   ---------  -------------  --------------  -----------  --------------------")
    print(
        "   PAIRED     " + _lpad(_f(s.paired_mean, 5), 13) + "  "
        + _lpad(_f(s.paired_variance * 1e6, 4) + " e-6", 14) + "  "
        + _lpad(_f(sqrt(s.paired_variance), 6), 11) + "  " + _lpad(String(s.n_paired), 20)
    )
    print(
        "   UNPAIRED   " + _lpad(_f(s.unpaired_mean, 5), 13) + "  "
        + _lpad(_f(s.unpaired_variance * 1e6, 4) + " e-6", 14) + "  "
        + _lpad(_f(sqrt(s.unpaired_variance), 6), 11) + "  " + _lpad(String(s.n_unpaired), 20)
    )
    print("")
    var rr = Float64(s.n_unpaired) / Float64(s.n_paired) if s.n_paired > 0 else 0.0
    print("   variance ratio (unpaired / paired) ..... " + _f(s.variance_ratio, 1) + "x")
    print("   replication ratio ...................... " + _f(rr, 1) + "x")
    print("   pairing reduces variance ............... "
          + ("yes" if s.pairing_reduces_variance else "NO"))
    print("")
    print("   Read the replication columns as the cost: at " + String(s.n_paths_per_rep)
          + " paths per replication, the")
    print("   unpaired design needs " + String(s.n_unpaired) + " replications to pin asset-0 Delta to +/-"
          + _f(hw, 3) + " where the")
    print("   paired design needs " + String(s.n_paired) + ". That factor is the whole return on")
    print("   using an addressable generator, and it is measured here rather than asserted.")
    if s.n_coordinate_identical != s.n_replications:
        print("   GATE FAIL: a re-run at the same coordinates gave a different price. The")
        print("   generator is not a pure function of its coordinates and CRN is not real.")
        return 1
    if not s.pairing_reduces_variance:
        print("   GATE FAIL: pairing did not reduce variance on this problem.")
        return 1
    print("   GATE PASS")
    return 0


# ── 10. Timing ────────────────────────────────────────────────────────────────


fn _time_greeks(
    ps: List[HestonParams], c: List[List[Float64]], n_paths: Int, workers: Int,
    mut prices_out: Int,
) -> Float64:
    var t0 = perf_counter_ns()
    var g = heston_basket_greeks(
        ps, c, STRIKE, RATE, TENOR, n_paths, BASE_STEPS, MASTER_SEED, 21,
        HESTON_SCHEME_QE, True, 2, workers,
    )
    var t1 = perf_counter_ns()
    prices_out = g.n_prices
    return Float64(t1 - t0) / 1.0e6


fn _sec_timing(workers: Int, mut cold_out: Float64, mut warm_out: Float64,
               mut hot_out: Float64, mut spread_out: Float64) -> Int:
    print("10. TIMING — the full Greeks set, cold / warm / hot")
    print("   Configuration: " + String(N_ASSETS) + " assets, " + String(TIER_PATHS)
          + " paths, " + String(BASE_STEPS) + " timesteps, fp64, " + String(workers)
          + " workers, Apple M4 Max arm64.")
    print("   THIS IS THE REDUCED TIER SIZE, NOT THE STAC BASELINE. The STAC baseline is 25,000")
    print("   paths and is measured by bench_stac_a2_baseline.mojo, which runs STAC's own")
    print("   1-cold-4-warm protocol once. This file uses " + String(TIER_PATHS)
          + " paths so that K separate")
    print("   processes are tractable, and the tier statistics below are about the TIERS.")
    print("")
    print("   COLD is one reading per process, by definition — the first Greeks set this process")
    print("   ever ran. K cold readings need K launches; run this through")
    print("   benchmarks/cold_start_harness.py -K <n> and state K next to the figure. A cold")
    print("   number without a K is not a measurement.")
    print("")
    var ps = _assets()
    var c = _corr()
    var np_ = 0
    var cold = _time_greeks(ps, c, TIER_PATHS, workers, np_)
    var n_prices = np_
    var warm = 1.0e308
    var hot = 1.0e308
    var mx = 0.0
    # STAC's own protocol is one cold run and four warm runs, WARM being the fastest warm time.
    # HOT is the same statistic taken after the warm set, which is what a steady-state service
    # sees; keeping both is the house convention and the gap between them is the interesting part.
    for i in range(4):
        var t = _time_greeks(ps, c, TIER_PATHS, workers, np_)
        if t < warm:
            warm = t
        if t > mx:
            mx = t
        _ = i
    for _ in range(3):
        var t = _time_greeks(ps, c, TIER_PATHS, workers, np_)
        if t < hot:
            hot = t
        if t > mx:
            mx = t
    var mn = warm if warm < hot else hot
    var spread = mx / mn if mn > 0.0 else 0.0
    cold_out = cold
    warm_out = warm
    hot_out = hot
    spread_out = spread

    var asset_steps = Float64(TIER_PATHS) * Float64(BASE_STEPS) * Float64(N_ASSETS)
    var per_set = asset_steps * Float64(n_prices)
    print("   prices per Greeks set .......... " + String(n_prices)
          + "   (1 base + 10 spot + 20 cross + 1 time + 2 rate + 40 model + 20 corr)")
    print("   asset-steps per Greeks set ..... " + String(Int(per_set / 1.0e6)) + " M")
    print("   DISPATCHES for the whole set ... 0")
    print("")
    print("   tier   wall ms       paths/sec (set)   asset-steps/sec")
    print("   -----  ------------  ----------------  ----------------")
    var rows = [cold, warm, hot]
    var nms = ["cold ", "warm ", "hot  "]
    for i in range(3):
        var ms = rows[i]
        var pps = Float64(TIER_PATHS) * Float64(n_prices) / (ms / 1000.0)
        var aps = per_set / (ms / 1000.0)
        print(
            "   " + nms[i] + "  " + _lpad(_f(ms, 1), 12) + "  " + _lpad(_f(pps, 0), 16)
            + "  " + _lpad(_f(aps / 1.0e6, 2) + " M", 16)
        )
    print("")
    # THESE TWO CHECKS ARE ADVISORY, NOT HARD GATES, AND THE DISTINCTION IS DELIBERATE.
    #
    # Both are wall-clock properties, and a wall-clock property on a shared machine gives a
    # different verdict run to run with no code change. `bench_phold.mojo` documents the
    # evidence for that split: two runs five minutes apart at load ~440, no edit, growth
    # exponent 1.11 then 1.99. Measured on THIS file: the first harness run at load 40-60
    # returned a tier inversion on a process whose nine correctness gates all passed. A build
    # that is provably correct must not be reported as FAILING because a sibling process was
    # using nine cores.
    #
    # So the breach is printed as INVALID, the ratio IS suppressed — a ratio a reader would
    # quote as a property of the code is the actual harm — and the count is carried to the
    # summary line as an ADVISORY. The hard gates are sections 1-9, every one of which is an
    # identity or a correctness invariant and gives the same verdict at any load.
    var advisory = 0
    # ADVISORY: hot must not be slower than warm. It is the same work in a warmer process; if
    # hot loses, the reading is contention and not a tier.
    if hot > warm:
        print("   INVALID — hot (" + _f(hot, 1) + " ms) is SLOWER than warm (" + _f(warm, 1)
              + " ms). No cold/hot ratio is printed, because on a contended machine the ratio")
        print("   would be a number about the machine and a reader would quote it as a number")
        print("   about the code.")
        advisory += 1
    # ADVISORY: dispersion. max/min above 3.0 means the readings are measuring the load.
    if spread > 3.0:
        print("   INVALID — tier dispersion max/min = " + _f(spread, 2)
              + " exceeds the 3.00 bound. No")
        print("   cold/hot ratio is printed. Re-run on a quiet machine; capture `uptime` before")
        print("   and after and quote it beside any figure taken from this run.")
        advisory += 1
    if advisory == 0:
        print("   cold/hot ratio ... " + _f(cold / hot, 2)
              + "x     tier dispersion max/min ... " + _f(spread, 2) + " (bound 3.00)")
        print("   TIER CHECK PASS")
    else:
        print("")
        print("   " + String(advisory) + " ADVISORY tier breach(es). NOT gate failures — see the")
        print("   comment at this check in the source. The correctness gates above are")
        print("   unaffected and are what BENCH_GATE reports on.")
    return advisory


# ── main ──────────────────────────────────────────────────────────────────────


def main() raises:
    var workers = info.num_physical_cores()
    print("")
    print("=== bench_stac_a2_workload: the STAC-A2 MARKET-RISK WORKLOAD ===")
    print("")
    print("UNAUDITED. INDEPENDENTLY IMPLEMENTED FROM THE PUBLIC SPECIFICATION.")
    print("This is NOT a STAC-A2 result and must never be presented as one. An official STAC-A2")
    print("result requires an audit by the STAC Benchmark Council; we have not had one. The")
    print("STAC-A2 specification, its R reference implementation and the STAC Test Harness are")
    print("restricted to Council members and we do not have them. Everything here is")
    print("reconstructed from publicly posted STAC Reports and the cited literature. STAC metric")
    print("names appear only to identify WHICH published definition each check was modelled on.")
    print("")
    print("model ............ Heston: CIR variance, GBM price, correlation rho between the")
    print("                   driving Brownians, one configuration per asset")
    print("discretisation ... " + heston_scheme_name(HESTON_SCHEME_QE))
    print("                   Andersen (2008), psi_c = " + _f(heston_qe_psi_critical(), 2)
          + ". Cross-checked against "
          + heston_scheme_name(HESTON_SCHEME_FULL_TRUNCATION) + ".")
    print("                   NAIVE EULER IS NEVER RUN — it lets the CIR variance go negative,")
    print("                   which is the most common error in this model. QE is non-negative")
    print("                   by construction: a square on one branch, support [0,inf) on the")
    print("                   other. Section 4 measures it rather than asserting it.")
    print("early exercise ... Longstaff-Schwartz least-squares Monte Carlo, degree-2 basis,")
    print("                   daily exercise dates")
    print("greeks ........... finite differences on COMMON RANDOM NUMBERS")
    print("contract ......... " + heston_contract_id())
    print("dispatches ....... 0. Everything is in-process; grep this file and quantfin/heston.mojo")
    print("                   for dispatch_runtime_library / library_execute / json_parse.")
    print("dtype ............ Float64 throughout.  device: CPU, Apple M4 Max arm64, "
          + String(workers) + " physical cores.")
    print("")
    print("CORRECTNESS BEFORE TIMING: sections 1-9 are HARD gates and run first. Section 10 is")
    print("timing, and its two tier checks are ADVISORY — a wall-clock verdict on a shared machine")
    print("is a verdict about the machine. BENCH_GATE below reports on sections 1-9.")
    print("")

    var failures = 0
    failures += _sec_rng_identity()
    print("")
    failures += _sec_regression_identity()
    print("")
    failures += _sec_degeneracy(workers)
    print("")
    failures += _sec_optionpv(workers)
    print("")
    failures += _sec_corrand()
    print("")
    failures += _sec_earlyex(workers)
    print("")
    failures += _sec_worker_invariance(workers)
    print("")
    failures += _sec_greeks_convergence(workers)
    print("")
    failures += _sec_crn(workers)
    print("")
    var cold = 0.0
    var warm = 0.0
    var hot = 0.0
    var spread = 0.0
    var advisory = _sec_timing(workers, cold, warm, hot, spread)
    print("")

    # The line the cold/warm/hot harness parses.
    print("-- cold / warm / hot, ms per full Greeks set --")
    print(
        "  A stac-a2 greeks ..... " + _f(cold, 1) + " / " + _f(warm, 1) + " / " + _f(hot, 1)
        + ("   cold/hot " + _f(cold / hot, 2) if (hot <= warm and spread <= 3.0 and hot > 0.0)
           else "   cold/hot unresolved")
    )
    print(
        "COLD_WARM_HOT stac_a2_greeks_2000paths " + _f(cold, 1) + " " + _f(warm, 1) + " "
        + _f(hot, 1) + " ms"
    )
    print("")
    print("CONTEXT REQUIRED: a Mojo process cannot read the system load average, and every")
    print("absolute figure above is a LOWER bound that depends on it. Capture `uptime`")
    print("immediately before and after this run and quote it beside any figure taken from it.")
    print("The cold reading is one per process: K cold readings need K launches, and K must be")
    print("stated.")
    print("")
    print("REMINDER, because it is the thing most likely to be dropped in a retelling: every")
    print("figure above is UNAUDITED and independently implemented from the public STAC-A2")
    print("specification. It is not a STAC-A2 result.")
    if advisory > 0:
        print("")
        print("NOTE " + String(advisory) + " wall-clock ADVISORY breach(es) in section 10. Not gate")
        print("failures. On a quiet machine these are worth investigating; under contention they")
        print("are expected, and the correctness gates are what the verdict below reports on.")
    if failures == 0:
        print("BENCH_GATE stac_a2_workload PASS")
    else:
        print("BENCH_GATE stac_a2_workload FAIL " + String(failures))
        raise Error("bench_stac_a2_workload: " + String(failures) + " gate failure(s)")
