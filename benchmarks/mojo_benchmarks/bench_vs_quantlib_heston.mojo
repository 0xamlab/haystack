"""bench_vs_quantlib_heston.mojo — Algenta's Heston-QE + Longstaff-Schwartz against QuantLib.

WHAT THIS IS
------------
`quantfin/heston.mojo` implements Andersen's (2008) Quadratic-Exponential scheme for Heston and
Longstaff-Schwartz (2001) least-squares Monte Carlo for early exercise. QuantLib
(github.com/lballabio/QuantLib) is the open-source pricing library real quant desks use, and it
is a real, installable opponent for exactly this workload: `ql.HestonProcess`'s OWN DEFAULT
discretisation is `QuadraticExponentialMartingale` — the same scheme this file's Mojo arm runs by
default. This is not a STAC-A2 result (see `STAC_A2_WORKLOAD.md`); it is a separate, narrower
comparison against a real, obtainable opponent, priced on THE SAME CONTRACT this file fixes below.

WHAT QUANTLIB'S PUBLIC BINDINGS DO NOT EXPOSE
----------------------------------------------
There is no single QuantLib call that does "Heston + Longstaff-Schwartz American" the way
`heston_basket_price` does. `ql.MCAmericanEngine` and `ql.BinomialVanillaEngine` are wired to a
`GeneralizedBlackScholesProcess`, not a `HestonProcess`. So the American comparison here runs on
the BLACK-SCHOLES-DEGENERATE corner of our own model (`xi = 0, rho = 0, v0 = theta = sigma^2`),
which collapses Heston to Black-Scholes exactly and lets QuantLib's BS-only American engines price
the identical contract. `ql.FdHestonVanillaEngine` (a PDE solver, not Monte Carlo, and genuinely
Heston-native) is measured separately in the Python arm and reported as a DIFFERENT METHOD, never
folded into the LSM-vs-LSM numbers.

THE CONTRACT, FIXED HERE SO BOTH ARMS PRICE THE SAME THING
------------------------------------------------------------
S0=100, K=100, r=3%, q=0 (no dividends — required for American-call-equals-European), T=1y.
European leg: v0=theta=0.04, kappa=2.0, xi=0.5, rho=-0.7 (Feller 0.64 — the same branch-coverage
configuration `STAC_A2_WORKLOAD.md` section 4b uses, so the QE exponential branch is genuinely
exercised here and not only on the degenerate quadratic branch). American leg: the BS-degenerate
corner of the same spot/rate/tenor, sigma = sqrt(0.04) = 0.2.

WHAT IS PRINTED
----------------
`QLHEURO` rows: our European MC price vs OUR OWN closed form (Fourier / Little Heston Trap),
at three path counts, wall time in ms. `QLHAMER` rows: our American LSM price vs OUR OWN
European-CRR-binomial reference (2048 steps; valid here only because q=0 makes American=European),
at the same three path counts. A companion Python arm (`bench_vs_quantlib_heston.py`) prices the
identical contract with QuantLib and a driver (`bench_vs_quantlib_heston_driver.py`) interleaves
the two, records load, and reports accuracy and speed honestly — including a loss, if that is what
the numbers say.

ZERO DISPATCH. Verify with the grep in `bench_stac_a2_workload.mojo`'s own docstring; the same
statement applies here.
"""

from std.time import perf_counter_ns
from std.math import sqrt, abs as fabs

from quantfin.heston import (
    HestonParams, heston_basket_price, heston_optionpv_error, heston_closed_form_call,
    heston_feller, HESTON_SCHEME_QE, HESTON_OK,
)
from option_pricing import binomial_tree_call

# ── The contract. Both arms price exactly this. ────────────────────────────────

comptime SPOT: Float64 = 100.0
comptime STRIKE: Float64 = 100.0
comptime RATE: Float64 = 0.03
comptime DIVY: Float64 = 0.0
comptime TENOR: Float64 = 1.0
comptime V0: Float64 = 0.04
comptime THETA: Float64 = 0.04
comptime KAPPA: Float64 = 2.0
comptime XI: Float64 = 0.5
comptime RHO: Float64 = -0.7
comptime SIGMA_BS: Float64 = 0.2  # sqrt(V0), the American-leg degenerate volatility
comptime N_STEPS: Int = 252
comptime AMER_STEPS: Int = 100  # matches ql.MCAmericanEngine's timeSteps used on the QuantLib arm
comptime MASTER_SEED: UInt64 = 0x5148_2E51
comptime SCENARIO_ID: UInt64 = 99
comptime BINOMIAL_STEPS: Int = 2048

# QuantLib's Python MC engines (`MCEuropeanHestonEngine`, `MCAmericanEngine`) run ONE thread per
# call here — confirmed by CPU-percentage sampling during a call (~97%, one core), and there is
# no thread-count argument on either engine in the public SWIG/Python bindings. So `workers=1` is
# the LIKE-FOR-LIKE row and is what any speed claim must be based on. `workers=8` is measured too
# and printed in its own clearly separate section, exactly as bench_vs_torch_attention_driver.py
# keeps a matched-thread row and a default-thread row apart — never averaged together, never
# substituted for the like-for-like number.
comptime WORKERS_LIKE_FOR_LIKE: Int = 1
comptime WORKERS_PARALLEL: Int = 8

comptime PATH_COUNTS_0: Int = 10000
comptime PATH_COUNTS_1: Int = 40000
comptime PATH_COUNTS_2: Int = 160000


def _f(x: Float64, dp: Int) -> String:
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


def _europ(n_paths: Int, closed_form: Float64, workers: Int) raises -> Int:
    """Returns 1 on a gate failure (refused status or a negative-variance step), else 0."""
    var p = HestonParams(SPOT, V0, KAPPA, THETA, XI, RHO, DIVY)
    var t0 = perf_counter_ns()
    var chk = heston_optionpv_error(
        p, STRIKE, RATE, TENOR, n_paths, N_STEPS, MASTER_SEED, SCENARIO_ID,
        HESTON_SCHEME_QE, True, workers,
    )
    var t1 = perf_counter_ns()
    var wall_ms = Float64(t1 - t0) / 1.0e6
    if chk.status != HESTON_OK or chk.n_negative_variance != 0:
        print("QLHEURO REFUSED n_paths=" + String(n_paths) + " workers=" + String(workers)
              + " status=" + String(chk.status) + " negV=" + String(chk.n_negative_variance))
        return 1
    print(
        "QLHEURO n_paths=" + String(n_paths) + " n_steps=" + String(N_STEPS)
        + " workers=" + String(workers)
        + " price=" + _f(chk.mc_price, 5) + " closed_form=" + _f(closed_form, 5)
        + " rel_err_pct=" + _f(chk.rel_error * 100.0, 4)
        + " std_err=" + _f(chk.std_error, 5) + " z=" + _f(chk.z_score, 3)
        + " negV=" + String(chk.n_negative_variance) + " wall_ms=" + _f(wall_ms, 2)
    )
    return 0


def _amer(n_paths: Int, binomial_ref: Float64, workers: Int) raises -> Int:
    """Returns 1 on a gate failure (refused status or a negative variance — a real correctness
    invariant). A NEGATIVE early-exercise premium here is NOT gated: this contract is the
    no-dividend degenerate corner where the true American value equals the European value
    exactly (never-optimal-to-exercise-a-non-dividend-call is a model-free theorem, not a
    Heston-specific result), so any measured premium is pure finite-sample LSM regression bias,
    and that bias is known to run negative for the standard degree-2 in-sample estimator. This
    was independently reproduced on QuantLib's OWN `MCAmericanEngine` on the identical contract
    (seeds 42/7/123, 10k/40k/160k samples): every one of those 9 runs ALSO underpriced the
    European closed form, by -0.076 to -0.251. Both implementations show the same known
    property; it is reported, not hidden, and not treated as a defect in either."""
    var p = HestonParams(SPOT, V0, KAPPA, THETA, 0.0, 0.0, DIVY)
    var ps = List[HestonParams]()
    ps.append(p)
    var corr = List[List[Float64]]()
    var row = List[Float64]()
    row.append(1.0)
    corr.append(row^)
    var t0 = perf_counter_ns()
    var bp = heston_basket_price(
        ps, corr, STRIKE, RATE, TENOR, n_paths, AMER_STEPS, MASTER_SEED, SCENARIO_ID,
        HESTON_SCHEME_QE, True, 2, workers,
    )
    var t1 = perf_counter_ns()
    var wall_ms = Float64(t1 - t0) / 1.0e6
    if bp.status != HESTON_OK or bp.n_negative_variance != 0:
        print("QLHAMER REFUSED n_paths=" + String(n_paths) + " workers=" + String(workers)
              + " status=" + String(bp.status) + " negV=" + String(bp.n_negative_variance))
        return 1
    var rel_err = fabs(bp.price - binomial_ref) / binomial_ref if binomial_ref > 0.0 else -1.0
    print(
        "QLHAMER n_paths=" + String(n_paths) + " n_steps=" + String(AMER_STEPS)
        + " workers=" + String(workers)
        + " price=" + _f(bp.price, 5) + " european=" + _f(bp.european_value, 5)
        + " premium=" + _f(bp.early_exercise_premium, 5)
        + " binomial_ref=" + _f(binomial_ref, 5)
        + " rel_err_pct=" + _f(rel_err * 100.0, 4)
        + " n_exercised=" + String(bp.n_exercised) + " wall_ms=" + _f(wall_ms, 2)
    )
    return 0


def main() raises:
    print("== Algenta quantfin.heston vs QuantLib ==")
    print("   (this arm's own numbers; the Python arm asserts ql.__version__ at run time)")
    print("contract: S0=" + _f(SPOT, 1) + " K=" + _f(STRIKE, 1) + " r=" + _f(RATE, 3)
          + " q=" + _f(DIVY, 3) + " T=" + _f(TENOR, 2) + "y")
    print("Heston (European leg): v0=theta=" + _f(V0, 3) + " kappa=" + _f(KAPPA, 2)
          + " xi=" + _f(XI, 2) + " rho=" + _f(RHO, 2))
    var feller_p = HestonParams(SPOT, V0, KAPPA, THETA, XI, RHO, DIVY)
    print("Feller ratio " + _f(heston_feller(feller_p), 3) + " (< 0.667 -> QE exponential branch"
          + " is genuinely exercised, not only the quadratic branch)")
    print("American leg (BS-degenerate, xi=0, rho=0): sigma=" + _f(SIGMA_BS, 3))
    print("")

    var cf = heston_closed_form_call(feller_p, STRIKE, RATE, TENOR)
    print("QLHEURO_CLOSED_FORM price=" + _f(cf, 5)
          + "  (our Fourier / Little Heston Trap, independent of QuantLib)")

    var bref = binomial_tree_call(SPOT, STRIKE, TENOR, RATE, SIGMA_BS, BINOMIAL_STEPS)
    print("QLHAMER_BINOMIAL_REF price=" + _f(bref, 5)
          + "  (our European CRR, " + String(BINOMIAL_STEPS) + " steps; valid as the American"
          + " reference here ONLY because q=0)")
    print("")

    var fails = 0
    print("-- workers=" + String(WORKERS_LIKE_FOR_LIKE) + ", LIKE-FOR-LIKE against QuantLib's"
          + " single-threaded MC engines --")
    fails += _europ(PATH_COUNTS_0, cf, WORKERS_LIKE_FOR_LIKE)
    fails += _europ(PATH_COUNTS_1, cf, WORKERS_LIKE_FOR_LIKE)
    fails += _europ(PATH_COUNTS_2, cf, WORKERS_LIKE_FOR_LIKE)
    print("")
    fails += _amer(PATH_COUNTS_0, bref, WORKERS_LIKE_FOR_LIKE)
    fails += _amer(PATH_COUNTS_1, bref, WORKERS_LIKE_FOR_LIKE)
    fails += _amer(PATH_COUNTS_2, bref, WORKERS_LIKE_FOR_LIKE)

    print("")
    print("-- workers=" + String(WORKERS_PARALLEL) + ", NOT LIKE-FOR-LIKE (QuantLib has no"
          + " thread-count argument on these engines; reported separately, never averaged"
          + " into the row above) --")
    fails += _europ(PATH_COUNTS_0, cf, WORKERS_PARALLEL)
    fails += _europ(PATH_COUNTS_1, cf, WORKERS_PARALLEL)
    fails += _europ(PATH_COUNTS_2, cf, WORKERS_PARALLEL)
    print("")
    fails += _amer(PATH_COUNTS_0, bref, WORKERS_PARALLEL)
    fails += _amer(PATH_COUNTS_1, bref, WORKERS_PARALLEL)
    fails += _amer(PATH_COUNTS_2, bref, WORKERS_PARALLEL)

    print("")
    if fails == 0:
        print("BENCH_GATE vs_quantlib_heston_mojo_arm PASS")
    else:
        print("BENCH_GATE vs_quantlib_heston_mojo_arm FAIL " + String(fails))
