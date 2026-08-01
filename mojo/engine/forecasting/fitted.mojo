"""
forecasting.fitted — Holt-family drivers that FIT the smoothing parameters AND the
initial state, closing the measured M4 defect in the fixed-init Holt path. Zero
Python imports.

The defect this module exists to close, with the measurement
------------------------------------------------------------
The frozen `timeseries_stats.holt_linear` initialises `l0 = y[0]`, `b0 = y[1] - y[0]`,
both unfitted, and every driver in `forecasting.point` inherits that by design (rule 3:
the frozen kernel is called, not reimplemented). At the SSE-optimal smoothing weights on
the M4 corpus the fitted beta is typically ~1e-4, so the trend state never forgets `b0`
— ONE noisy first difference is extrapolated across the entire horizon. Controlled
four-variant experiment on the same 95,000 series, same metric (2026-08-01, this
machine): the engine kernel with correct parameters scores WORSE (Monthly sMAPE 44.13)
than the engine kernel with a compensating parameter fit (18.05); restoring a FITTED
initial state recovers statsforecast exactly (13.97, state-space replica validated to
1e-10 against statsforecast 2.1.1 on all 100,000 series).

The frozen kernel is untouched. This module is the additive driver family with the
missing capability: the ETS(A,A,N) / ETS(A,Ad,N) STATE-SPACE recursion

    f_t = l + phi * b;   e_t = y_t - f_t;   l <- f_t + alpha * e_t;   b <- phi * b + beta * e_t

whose initial state is a fitted quantity, not a copy of the first two observations.
This recursion is NOT `holt_linear` re-implemented: the classical form cannot accept an
arbitrary initial state at all — its init IS the defect — and the gap is classified
`genuinely-missing` per the frozen-baseline rules. The two forms coincide only at
`phi = 1` with `beta_classical = beta_statespace / alpha` and the frozen init.

The closed-form initial state, and what it is FOR
-------------------------------------------------
Holt/Damped are linear state-space models: for FIXED (alpha, beta, phi) every in-sample
one-step forecast is a linear function of (l0, b0),

    yhat_t = p_t + q_t * l0 + r_t * b0,

where `p` comes from a zero-state pass driven by `y` and `q`, `r` from the two
homogeneous passes (unit level / unit trend, zero input). The SSE-optimal (l0, b0) is
therefore an EXACT 2x2 normal-equations solve — no iteration, no starting point.
`fitted_init_solve` is that solve, public, with the system accumulated in Float64 and a
determinant guard: a singular system is REPORTED (`solved = False`, status
FC_ERR_INSUFFICIENT_HISTORY) and the returned state falls back to `l0 = y[0], b0 = 0` —
a fallback carried in the result, never silently. On the corrupted-first-difference
known value in the suite the exact solve at fixed (0.5, 1e-4, 1.0) recovers the true
trend (+2.6 against a truth of +3) where the frozen init carries -4 — the one corrupted
difference — across the whole horizon.

Why the full drivers do NOT search over the profile objective, with the measurement
-----------------------------------------------------------------------------------
The obvious architecture — outer grid/pattern search on (alpha, beta), inner exact
solve — was built first and MEASURED against statsforecast 2.1.1 on the same M4 series,
same metric, before this module was written:

    Yearly holt, 1500-series sample:  grid+pattern outer  sMAPE +2.44 vs statsforecast
                                      local pattern outer sMAPE +1.35 vs statsforecast

The exact inner solve is not at fault — at statsforecast's own fitted (alpha, beta, phi)
it matches their initial state to forecast-equivalence (13.65 vs 13.58 sample sMAPE, and
slightly BETTER on damped). The outer search is: with (l0, b0) solved exactly per
candidate, in-sample SSE strictly improves toward the `beta -> alpha -> 1` corner on
short series, and the test-set forecast collapses (in-sample SSE 10% lower, sMAPE +18 to
+137 on the escaped series). R and statsforecast are protected from the same corner by
OPTIMIZER MYOPIA, not by their objective: their Nelder-Mead explores (alpha, beta, l0,
b0) JOINTLY, where the corner needs coordinated state moves the collapsing simplex never
finds. Removing the joint-space coupling removes the regularisation.

So the drivers reproduce the reference optimizer exactly (statsforecast 2.1.1
`nelder_mead.h` / `ets.cpp`, verified against source): Nelder-Mead on
[alpha, beta, (phi,) l0, b0] with box clamping, initial simplex perturbation
`x_i *= 1.05` (`1e-4` if zero), Gao-Han adaptive coefficients, convergence when the
population standard deviation of the simplex objective drops below 1e-4, at most 1000
iterations, objective `n * log(SSE)`, starting point per their `initparam`/`initstate`
(alpha 0.20006, beta 0.0201, phi 0.9782, OLS on the first min(10, n) observations for
the state), and — the detail that carries the regularisation — `initparam`'s in-place
beta ceiling, documented at `FIT_BETA_HI`. With all of those reproduced, this fit
matches the STORED statsforecast parameter vectors bit-exactly (rel < 1e-8) on 300 of
300 sampled M4 Yearly series, holt and damped both, through their own compiled
optimizer and through the replica of it below.

`fitted_init_solve` remains the closed-form fix it was designed to be — the exact
initial state for KNOWN parameters — and the suite proves both halves: the solve
recovers a hand-derived state exactly, and the drivers refuse to extrapolate a
corrupted first difference that the frozen init cannot help extrapolating.

Absence, per rule 4
-------------------
`FittedForecast.has_forecast` is the authority; on any refusal `values` is EMPTY. If no
Nelder-Mead vertex ever produced a finite objective (a series whose magnitudes overflow
the recursion), the status is FC_ERR_ALL_UNDEFINED and no parameter estimates are
reported at all — a fit that never evaluated is not a fit. `init_status` reports the
initial-state provenance separately from the fit status, because "the 2x2 system was
solved" and "the fallback state was used and reported" are different facts.

Status codes 300-319 via `forecasting.contract`; no table here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_fitted.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, log, sqrt

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_NON_FINITE,
    FC_ERR_PERIOD,
    FC_ERR_WORK_BUDGET,
    FC_METHOD_ETS_AAA,
    FC_METHOD_ETS_AAN,
    FC_OK,
    fc_all_finite,
    fc_damping_defect,
    fc_finite,
    fc_horizon_defect,
    fc_period_defect,
    fc_series_defect,
    fc_smoothing_defect,
    fc_status_name,
    fc_work_fits,
)
from forecasting.point import _seasonal_indices

# ── the reference optimizer's constants, verified against statsforecast 2.1.1 ────────
#
# `src/ets.cpp` hardcodes init_step = 0.05 and zero_pert = 1e-4 and calls
# `nm::NelderMead(..., tol_std = 1e-4, max_iter = 1000, adaptive = true)`; `ets.py`'s
# `initparam` produces the starting point below for a non-seasonal trend model (m = 1).
# These are REPRODUCED, not tuned: changing any of them moves the drivers off the
# reference implementation the module docstring's measurements were made against.

comptime FIT_NM_MAX_ITER: Int = 1000
comptime FIT_NM_TOL_STD: Float64 = 1.0e-4
comptime FIT_NM_INIT_STEP: Float64 = 0.05
comptime FIT_NM_ZERO_PERT: Float64 = 1.0e-4

comptime FIT_ALPHA_LO: Float64 = 1.0e-4
comptime FIT_ALPHA_HI: Float64 = 0.9999
comptime FIT_BETA_LO: Float64 = 1.0e-4
comptime FIT_PHI_LO: Float64 = 0.8
comptime FIT_PHI_HI: Float64 = 0.98

# initparam with m = 1: alpha = lo + 0.2*(hi - lo); beta = lo + 0.1*(beta_hi - lo);
# phi = lo + 0.99*(hi - lo). Spelled as arithmetic so the derivation is checkable.
comptime FIT_ALPHA_START: Float64 = FIT_ALPHA_LO + 0.2 * (FIT_ALPHA_HI - FIT_ALPHA_LO)

# THE BETA CEILING IS THE STARTING ALPHA, AND THAT IS NOT A TYPO. The reference
# `initparam` runs `upper[1] = min(upper[1], alpha)` on the SHARED bounds array before
# the optimizer ever sees it — an in-place mutation whose comment says "ensure
# beta < alpha" but whose effect is a hard box `beta <= 0.20006` for the entire fit,
# because `alpha` at that line is the STARTING alpha, not the fitted one. This is the
# regularisation that actually protects R-family Holt fits from the
# `beta -> alpha -> 1` in-sample corner (the module docstring's +18 to +137 sMAPE
# escapes): with the documented 0.9999 ceiling instead, the fit diverges from the
# stored statsforecast parameters on 99 of 300 M4 Yearly series; with THIS ceiling it
# matches all 300 of 300 bit-exactly, both models. Verified against statsforecast
# 2.1.1 `ets.py::initparam` source and its compiled optimizer on 2026-08-01.
comptime FIT_BETA_HI: Float64 = FIT_ALPHA_START
comptime FIT_BETA_START: Float64 = FIT_BETA_LO + 0.1 * (FIT_BETA_HI - FIT_BETA_LO)
comptime FIT_PHI_START: Float64 = FIT_PHI_LO + 0.99 * (FIT_PHI_HI - FIT_PHI_LO)

# How many observations the initial-state heuristic regresses over (initstate's
# `maxn = min(max(10, 2*m), n)` with m = 1).
comptime FIT_INIT_OBS: Int = 10

# ── the work budget, with the arithmetic ─────────────────────────────────────────────
#
# Every Nelder-Mead iteration evaluates the objective at most (dim + 3) times (reflect,
# expand or contract, plus a full shrink re-evaluation of dim vertices), each evaluation
# one O(n) pass, and dim <= 5. The honest worst-case charge per call is therefore
# FIT_NM_MAX_ITER * 8 = 8000 passes. Bounding memory is not bounding work: without this
# charge a structurally valid 4-million-observation series is a ~2.6e11-operation
# request — a hang, which from the caller's side is the same outcome as the uncatchable
# abort. 2^32 / 8000 admits n up to ~536,000, several times the longest series in any
# forecasting corpus this package has been pointed at, and caps the worst case at a few
# seconds of CPU.
comptime FIT_NM_MAX_EVALS: Int = FIT_NM_MAX_ITER * 8
comptime FIT_MAX_WORK: Int = 1 << 32

# The determinant guard for the 2x2 normal equations: the system is declared singular
# when `det <= FIT_SOLVE_SLACK * DBL_EPSILON * (Sqq * Srr)`. The judged quantity is the
# determinant and the scale is ITS OWN Gram bound (`det = Sqq*Srr - Sqr^2 <= Sqq*Srr` by
# Cauchy-Schwarz), not an aggregate over anything else — rule 4b's spelling for this
# comparison. 64 ulps of the bound covers the accumulation of the two sums it is formed
# from; a one-observation system hits it exactly (det = 0).
comptime FIT_SOLVE_SLACK: Float64 = 64.0
comptime FIT_DBL_EPSILON: Float64 = 2.220446049250313e-16


@fieldwise_init
struct InitSolve(Copyable, Movable):
    """The exact least-squares initial state for FIXED (alpha, beta, phi).

    `has_state` is the authority for `l0`/`b0`; `solved` says HOW they were produced:
    True means the 2x2 normal equations were solved, False with `has_state = True` means
    the system was singular and the REPORTED fallback `l0 = y[0], b0 = 0` is carried
    (status FC_ERR_INSUFFICIENT_HISTORY — the record cannot identify two initial-state
    parameters). `sse` is the exact in-sample one-step SSE at the returned state,
    recomputed by a clean forward pass, never the profile shortcut, so a caller can
    compare two solves without inheriting cancellation error. `det` is the normal-
    equations determinant, kept for the audit trail: a solve that barely cleared the
    guard is distinguishable from a comfortable one.
    """

    var status: Int
    var has_state: Bool
    var solved: Bool
    var l0: Float64
    var b0: Float64
    var sse: Float64
    var det: Float64
    var status_name: String


@fieldwise_init
struct FittedForecast(Copyable, Movable):
    """A forecast whose smoothing parameters AND initial state were fitted here.

    `values` holds steps 1..horizon; EMPTY on any refusal (`has_forecast` is the
    authority — no padded zeros, no repeated last value). `alpha`, `beta`, `phi` are the
    fitted smoothing parameters; `l0`, `b0` the fitted initial state; `level`, `trend`
    the terminal state the forecast extrapolates from. `sse` is the exact in-sample
    one-step SSE at the reported fit; `insample_mae` is the mean absolute one-step error
    over t = 1..n-1 — t = 0 is EXCLUDED so the number is comparable across methods whose
    first forecast consumes a different amount of state (SES's first error is at t = 1;
    this model's is at t = 0). `forecasting.select` selects on exactly that field.

    `init_status`/`init_solved` report the initial-state provenance separately from
    `status`: a fit whose final vertex sat on a singular 2x2 system still forecasts, but
    a caller auditing the state must be able to see the fallback. `n_params` counts
    fitted quantities carrying information: 4 for Holt (alpha, beta, l0, b0), 5 damped.
    """

    var status: Int
    var method_id: Int
    var horizon: Int
    var n_train: Int
    var values: List[Float64]
    var has_forecast: Bool
    var alpha: Float64
    var beta: Float64
    var phi: Float64
    var l0: Float64
    var b0: Float64
    var level: Float64
    var trend: Float64
    var sse: Float64
    var insample_mae: Float64
    var init_status: Int
    var init_solved: Bool
    var n_params: Int
    var status_name: String
    var init_status_name: String


fn _no_fitted(status: Int, method_id: Int, horizon: Int, n_train: Int) -> FittedForecast:
    """A refusal: no path, no parameter estimates, every presence flag cleared."""
    return FittedForecast(
        status, method_id, horizon, n_train, List[Float64](), False,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        status, False, 0, fc_status_name(status), fc_status_name(status),
    )


fn _clean_pass(
    y: List[Float64], alpha: Float64, beta: Float64, phi: Float64,
    l0: Float64, b0: Float64,
) -> List[Float64]:
    """`[sse, level, trend, sum_abs_err_from_t1]` by one forward recursion, or empty.

    THE one forward evaluation of the state-space recursion in this module: the solver,
    the objective and the drivers all reach the recursion through this function or its
    accumulating sibling `_profile_solve`, so there is no second copy to drift (rule 3
    inside a package). Empty on any non-finite intermediate, so a NaN level can never be
    read as a forecast.
    """
    var out = List[Float64]()
    var lev = l0
    var trd = b0
    var sse: Float64 = 0.0
    var sae: Float64 = 0.0
    for t in range(len(y)):
        var fb = phi * trd
        var f = lev + fb
        var e = y[t] - f
        sse += e * e
        if t >= 1:
            sae += fabs(e)
        lev = f + alpha * e
        trd = fb + beta * e
    if not fc_finite(sse) or not fc_finite(lev) or not fc_finite(trd):
        return out^
    out.append(sse)
    out.append(lev)
    out.append(trd)
    out.append(sae)
    return out^


fn _objective(
    y: List[Float64], alpha: Float64, beta: Float64, phi: Float64,
    l0: Float64, b0: Float64,
) -> Float64:
    """`n * log(SSE)` — the reference optimizer's likelihood for an additive-error model.

    Monotone in SSE, so the argmin is the SSE argmin; kept in log form because the
    convergence test (`std of simplex objectives < 1e-4`) is calibrated against THIS
    scale in the reference implementation, and changing the scale changes where the
    optimizer stops, which changes the fit. `SSE <= 0` (an exact fit) uses the reference
    guard `n * log(SSE + 1e-8)`. A non-finite pass is +inf: worse than every real
    vertex, so the simplex walks away from overflow instead of into it.
    """
    var pass_ = _clean_pass(y, alpha, beta, phi, l0, b0)
    if len(pass_) != 4:
        return 1.0 / 0.0
    var n = Float64(len(y))
    var sse = pass_[0]
    if sse > 0.0:
        return n * log(sse)
    return n * log(sse + 1.0e-8)


fn fitted_init_solve(
    y: List[Float64], alpha: Float64, beta: Float64, phi: Float64
) -> InitSolve:
    """The exact SSE-optimal initial state (l0, b0) for fixed (alpha, beta, phi).

    THE closed-form fix for the frozen init defect, usable whenever the smoothing
    parameters are already known: the model is linear in its initial state, so
    `yhat_t = p_t + q_t*l0 + r_t*b0` and one O(n) pass accumulates the 2x2 normal
    equations in Float64 — `p` driven by `y` from zero state, `q`/`r` the homogeneous
    unit-level/unit-trend responses. Solved by Cramer's rule under the determinant guard
    documented at `FIT_SOLVE_SLACK`; a singular system (one observation, or a degenerate
    accumulation) REPORTS the fallback `l0 = y[0], b0 = 0` with
    FC_ERR_INSUFFICIENT_HISTORY rather than inventing a state — the suite pins both the
    hand-derived solved values and the reported fallback.

    The returned `sse` is recomputed by a clean forward pass at the returned state, so
    it is exact rather than the profile identity `Syy - l0*Sqy - b0*Sry`, whose
    subtraction cancels catastrophically near an exact fit.

    @capability fitted_init_solve
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return InitSolve(defect, False, False, 0.0, 0.0, 0.0, 0.0, fc_status_name(defect))
    defect = fc_smoothing_defect(alpha)
    if defect != FC_OK:
        return InitSolve(defect, False, False, 0.0, 0.0, 0.0, 0.0, fc_status_name(defect))
    defect = fc_smoothing_defect(beta)
    if defect != FC_OK:
        return InitSolve(defect, False, False, 0.0, 0.0, 0.0, 0.0, fc_status_name(defect))
    defect = fc_damping_defect(phi)
    if defect != FC_OK:
        return InitSolve(defect, False, False, 0.0, 0.0, 0.0, 0.0, fc_status_name(defect))

    # One pass: particular solution (pl, pb) driven by y, homogeneous responses
    # (ql, qb) from state (1, 0) and (rl, rb) from state (0, 1), zero input.
    var pl: Float64 = 0.0
    var pb: Float64 = 0.0
    var ql: Float64 = 1.0
    var qb: Float64 = 0.0
    var rl: Float64 = 0.0
    var rb: Float64 = 1.0
    var sqq: Float64 = 0.0
    var sqr: Float64 = 0.0
    var srr: Float64 = 0.0
    var sqy: Float64 = 0.0
    var sry: Float64 = 0.0
    for t in range(n):
        var fpb = phi * pb
        var fp = pl + fpb
        var fqb = phi * qb
        var fq = ql + fqb
        var frb = phi * rb
        var fr = rl + frb
        var res = y[t] - fp
        sqq += fq * fq
        sqr += fq * fr
        srr += fr * fr
        sqy += fq * res
        sry += fr * res
        pl = fp + alpha * res
        pb = fpb + beta * res
        ql = fq - alpha * fq
        qb = fqb - beta * fq
        rl = fr - alpha * fr
        rb = frb - beta * fr
    if (
        not fc_finite(sqq) or not fc_finite(sqr) or not fc_finite(srr)
        or not fc_finite(sqy) or not fc_finite(sry)
    ):
        return InitSolve(
            FC_ERR_NON_FINITE, False, False, 0.0, 0.0, 0.0, 0.0,
            fc_status_name(FC_ERR_NON_FINITE),
        )
    var det = sqq * srr - sqr * sqr
    if det <= FIT_SOLVE_SLACK * FIT_DBL_EPSILON * (sqq * srr):
        # Singular: the record cannot identify two initial-state parameters. The
        # fallback is REPORTED, not silent, and its SSE is computed honestly.
        var fb_pass = _clean_pass(y, alpha, beta, phi, y[0], 0.0)
        var fb_sse = fb_pass[0] if len(fb_pass) == 4 else 0.0
        return InitSolve(
            FC_ERR_INSUFFICIENT_HISTORY, True, False, y[0], 0.0, fb_sse, det,
            fc_status_name(FC_ERR_INSUFFICIENT_HISTORY),
        )
    var l0 = (sqy * srr - sry * sqr) / det
    var b0 = (sqq * sry - sqr * sqy) / det
    if not fc_finite(l0) or not fc_finite(b0):
        return InitSolve(
            FC_ERR_NON_FINITE, False, False, 0.0, 0.0, 0.0, det,
            fc_status_name(FC_ERR_NON_FINITE),
        )
    var pass_ = _clean_pass(y, alpha, beta, phi, l0, b0)
    if len(pass_) != 4:
        return InitSolve(
            FC_ERR_NON_FINITE, False, False, 0.0, 0.0, 0.0, det,
            fc_status_name(FC_ERR_NON_FINITE),
        )
    return InitSolve(FC_OK, True, True, l0, b0, pass_[0], det, fc_status_name(FC_OK))


fn _heuristic_state(y: List[Float64]) -> List[Float64]:
    """`[l0, b0]` — OLS over the first min(10, n) observations against t = 1..maxn.

    The reference `initstate` for a non-seasonal additive-trend model, reproduced
    exactly including its regressor being 1-based. Requires n >= 2 (the caller enforces
    it); with maxn = 2 the line passes through both points. Empty when the closed-form
    denominator vanishes, which for distinct 1-based regressors cannot happen — the
    guard is against a future caller feeding maxn < 2.
    """
    var out = List[Float64]()
    var maxn = min(FIT_INIT_OBS, len(y))
    if maxn < 2:
        return out^
    var st: Float64 = 0.0
    var sy: Float64 = 0.0
    var stt: Float64 = 0.0
    var sty: Float64 = 0.0
    for i in range(maxn):
        var t = Float64(i + 1)
        st += t
        sy += y[i]
        stt += t * t
        sty += t * y[i]
    var nf = Float64(maxn)
    var den = nf * stt - st * st
    if den == 0.0:
        return out^
    var b = (nf * sty - st * sy) / den
    var l = (sy - b * st) / nf
    if not fc_finite(l) or not fc_finite(b):
        return out^
    out.append(l)
    out.append(b)
    return out^


fn _nm_objective_at(y: List[Float64], x: List[Float64], damped: Bool) -> Float64:
    """The joint objective at a Nelder-Mead vertex: unpack, then `n*log(SSE)`.

    Vertex layout is [alpha, beta, l0, b0] undamped and [alpha, beta, phi, l0, b0]
    damped — the reference parameter order (smoothing parameters first, then state).
    """
    if damped:
        return _objective(y, x[0], x[1], x[2], x[3], x[4])
    return _objective(y, x[0], x[1], 1.0, x[2], x[3])


fn _nm_clamp(mut x: List[Float64], lower: List[Float64], upper: List[Float64]):
    """Coordinate-wise clamp to the box, the reference bounds handling."""
    for i in range(len(x)):
        if x[i] < lower[i]:
            x[i] = lower[i]
        if x[i] > upper[i]:
            x[i] = upper[i]


fn _fit_nelder_mead(y: List[Float64], damped: Bool) -> List[Float64]:
    """`[alpha, beta, phi, l0, b0]` fitted by the reference Nelder-Mead, or empty.

    Reproduces statsforecast 2.1.1's `nm::NelderMead` exactly (verified against
    `nelder_mead.h` source, 2026-08-01): initial simplex perturbs coordinate i of vertex
    i by *1.05 (or to 1e-4 from zero) then clamps; Gao-Han adaptive coefficients
    gamma = 1 + 2/dim, rho = 0.75 - 1/(2*dim), sigma = 1 - 1/dim with reflection
    coefficient 1; every candidate clamped to the box; convergence when the POPULATION
    standard deviation of the vertex objectives drops below 1e-4, checked after
    ordering, before the centroid; at most 1000 iterations; ties in the vertex ordering
    broken stably (insertion sort), matching the replica this function was validated
    against series-by-series.

    Empty when no vertex of the initial simplex has a finite objective — the caller
    turns that into FC_ERR_ALL_UNDEFINED — and empty is also the answer when the
    heuristic starting state cannot be formed. A shrink step re-evaluates every
    non-best vertex, exactly as the reference does.
    """
    var out = List[Float64]()
    var start = _heuristic_state(y)
    if len(start) != 2:
        return out^
    var dim = 5 if damped else 4
    var x0 = List[Float64]()
    x0.append(FIT_ALPHA_START)
    x0.append(FIT_BETA_START)
    if damped:
        x0.append(FIT_PHI_START)
    x0.append(start[0])
    x0.append(start[1])
    var lower = List[Float64]()
    var upper = List[Float64]()
    var big: Float64 = 1.0 / 0.0
    lower.append(FIT_ALPHA_LO)
    upper.append(FIT_ALPHA_HI)
    lower.append(FIT_BETA_LO)
    upper.append(FIT_BETA_HI)
    if damped:
        lower.append(FIT_PHI_LO)
        upper.append(FIT_PHI_HI)
    lower.append(-big)
    upper.append(big)
    lower.append(-big)
    upper.append(big)
    _nm_clamp(x0, lower, upper)

    # dim+1 vertices; vertex i (i < dim) perturbs coordinate i, vertex dim is x0.
    var simplex = List[List[Float64]]()
    for i in range(dim + 1):
        var row = List[Float64]()
        for j in range(dim):
            row.append(x0[j])
        if i < dim:
            var val = row[i]
            if val == 0.0:
                val = FIT_NM_ZERO_PERT
            else:
                val *= 1.0 + FIT_NM_INIT_STEP
            if val < lower[i]:
                val = lower[i]
            if val > upper[i]:
                val = upper[i]
            row[i] = val
        simplex.append(row^)
    var fvals = List[Float64]()
    var any_finite = False
    for i in range(dim + 1):
        var fv = _nm_objective_at(y, simplex[i], damped)
        if fc_finite(fv):
            any_finite = True
        fvals.append(fv)
    if not any_finite:
        return out^

    # Gao-Han adaptive coefficients for this dimension.
    var nmd = Float64(dim)
    var coef_gamma = 1.0 + 2.0 / nmd
    var coef_rho = 0.75 - 1.0 / (2.0 * nmd)
    var coef_sigma = 1.0 - 1.0 / nmd

    var order = List[Int]()
    for i in range(dim + 1):
        order.append(i)
    for _ in range(FIT_NM_MAX_ITER):
        # Stable insertion sort of vertex indices by objective.
        for i in range(1, dim + 1):
            var key = order[i]
            var j = i - 1
            while j >= 0 and fvals[order[j]] > fvals[key]:
                order[j + 1] = order[j]
                j -= 1
            order[j + 1] = key
        var best = order[0]
        var second_worst = order[dim - 1]
        var worst = order[dim]
        # Population standard deviation of the objectives (the reference divides by
        # the count, not count-1). A non-finite objective in the simplex keeps the
        # test failing, which keeps the search running away from the overflow.
        var mean_f: Float64 = 0.0
        for i in range(dim + 1):
            mean_f += fvals[i]
        mean_f /= Float64(dim + 1)
        var var_f: Float64 = 0.0
        for i in range(dim + 1):
            var df = fvals[i] - mean_f
            var_f += df * df
        var_f /= Float64(dim + 1)
        if fc_finite(var_f) and sqrt(var_f) < FIT_NM_TOL_STD:
            break
        # Centroid of all vertices except the worst.
        var centroid = List[Float64]()
        for j in range(dim):
            var s: Float64 = 0.0
            for i in range(dim + 1):
                s += simplex[i][j]
            s -= simplex[worst][j]
            centroid.append(s / nmd)
        # Reflection.
        var xr = List[Float64]()
        for j in range(dim):
            xr.append(centroid[j] + (centroid[j] - simplex[worst][j]))
        _nm_clamp(xr, lower, upper)
        var fr = _nm_objective_at(y, xr, damped)
        if fvals[best] <= fr and fr < fvals[second_worst]:
            simplex[worst] = xr^
            fvals[worst] = fr
        elif fr < fvals[best]:
            # Expansion.
            var xe = List[Float64]()
            for j in range(dim):
                xe.append(centroid[j] + coef_gamma * (xr[j] - centroid[j]))
            _nm_clamp(xe, lower, upper)
            var fe = _nm_objective_at(y, xe, damped)
            if fe < fr:
                simplex[worst] = xe^
                fvals[worst] = fe
            else:
                simplex[worst] = xr^
                fvals[worst] = fr
        elif fvals[second_worst] <= fr and fr < fvals[worst]:
            # Outer contraction.
            var xoc = List[Float64]()
            for j in range(dim):
                xoc.append(centroid[j] + coef_rho * (xr[j] - centroid[j]))
            _nm_clamp(xoc, lower, upper)
            var foc = _nm_objective_at(y, xoc, damped)
            if foc <= fr:
                simplex[worst] = xoc^
                fvals[worst] = foc
            else:
                for i in range(dim + 1):
                    if i == best:
                        continue
                    for j in range(dim):
                        simplex[i][j] = (
                            simplex[best][j]
                            + coef_sigma * (simplex[i][j] - simplex[best][j])
                        )
                    _nm_clamp(simplex[i], lower, upper)
                    fvals[i] = _nm_objective_at(y, simplex[i], damped)
        else:
            # Inner contraction.
            var xic = List[Float64]()
            for j in range(dim):
                xic.append(centroid[j] - coef_rho * (xr[j] - centroid[j]))
            _nm_clamp(xic, lower, upper)
            var fic = _nm_objective_at(y, xic, damped)
            if fic < fvals[worst]:
                simplex[worst] = xic^
                fvals[worst] = fic
            else:
                for i in range(dim + 1):
                    if i == best:
                        continue
                    for j in range(dim):
                        simplex[i][j] = (
                            simplex[best][j]
                            + coef_sigma * (simplex[i][j] - simplex[best][j])
                        )
                    _nm_clamp(simplex[i], lower, upper)
                    fvals[i] = _nm_objective_at(y, simplex[i], damped)
    # Final stable ordering, then unpack the best vertex.
    for i in range(1, dim + 1):
        var key = order[i]
        var j = i - 1
        while j >= 0 and fvals[order[j]] > fvals[key]:
            order[j + 1] = order[j]
            j -= 1
        order[j + 1] = key
    var bidx = order[0]
    if not fc_finite(fvals[bidx]):
        return out^
    out.append(simplex[bidx][0])
    out.append(simplex[bidx][1])
    if damped:
        out.append(simplex[bidx][2])
        out.append(simplex[bidx][3])
        out.append(simplex[bidx][4])
    else:
        out.append(1.0)
        out.append(simplex[bidx][2])
        out.append(simplex[bidx][3])
    return out^


fn _fitted_driver(
    y: List[Float64], horizon: Int, damped: Bool, method_id: Int
) -> FittedForecast:
    """Shared body of `holt_fitted` / `damped_fitted`: validate, fit, extrapolate."""
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_fitted(defect, method_id, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_fitted(defect, method_id, horizon, n)
    if n < 2:
        return _no_fitted(FC_ERR_INSUFFICIENT_HISTORY, method_id, horizon, n)
    if not fc_work_fits(n, FIT_NM_MAX_EVALS, FIT_MAX_WORK):
        return _no_fitted(FC_ERR_WORK_BUDGET, method_id, horizon, n)
    var fit = _fit_nelder_mead(y, damped)
    if len(fit) != 5:
        return _no_fitted(FC_ERR_ALL_UNDEFINED, method_id, horizon, n)
    var alpha = fit[0]
    var beta = fit[1]
    var phi = fit[2]
    var l0 = fit[3]
    var b0 = fit[4]
    var pass_ = _clean_pass(y, alpha, beta, phi, l0, b0)
    if len(pass_) != 4:
        return _no_fitted(FC_ERR_NON_FINITE, method_id, horizon, n)
    var sse = pass_[0]
    var level = pass_[1]
    var trend = pass_[2]
    var mae = pass_[3] / Float64(n - 1)
    # The initial-state provenance, audited AT THE FITTED PARAMETERS: the drivers fit
    # the state jointly, and the exact solve is the independent cross-check a caller
    # can reproduce. Reported, never substituted — the forecast below uses the fit.
    var audit = fitted_init_solve(y, alpha, beta, phi)
    var values = List[Float64]()
    var damped_sum: Float64 = 0.0
    var power: Float64 = 1.0
    for _ in range(horizon):
        power *= phi
        damped_sum += power
        var v = level + trend * damped_sum
        if not fc_finite(v):
            return _no_fitted(FC_ERR_NON_FINITE, method_id, horizon, n)
        values.append(v)
    return FittedForecast(
        FC_OK, method_id, horizon, n, values^, True,
        alpha, beta, phi, l0, b0, level, trend, sse, mae,
        audit.status, audit.solved, 5 if damped else 4,
        fc_status_name(FC_OK), fc_status_name(audit.status),
    )


fn holt_fitted(y: List[Float64], horizon: Int) -> FittedForecast:
    """ETS(A,A,N) with FITTED (alpha, beta, l0, b0) — the M4 Holt defect, closed.

    Everything is estimated from the record: the smoothing parameters by the reference
    Nelder-Mead on `n*log(SSE)`, the initial state jointly with them from the OLS
    heuristic start. On the suite's corrupted-first-difference series the fitted trend
    recovers the true slope while the frozen-init driver at the same smoothing regime
    extrapolates the corruption across the whole horizon — that differential is the
    module's reason to exist, and it is asserted, not narrated.

    @capability holt_fitted
    complexity: O(n) -- at most FIT_NM_MAX_EVALS bounded O(n) passes, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    return _fitted_driver(y, horizon, False, FC_METHOD_ETS_AAN)


fn damped_fitted(y: List[Float64], horizon: Int) -> FittedForecast:
    """ETS(A,Ad,N) with FITTED (alpha, beta, phi, l0, b0); phi bounded [0.8, 0.98].

    The damped sibling of `holt_fitted`: phi is a fifth fitted coordinate with the
    reference bounds, entering both the recursion and the extrapolation
    `f_h = level + trend * (phi + ... + phi^h)`, accumulated once — no closed form with
    a `phi == 1` special case, and no O(horizon^2) re-derivation per step.

    @capability damped_fitted
    complexity: O(n) -- at most FIT_NM_MAX_EVALS bounded O(n) passes, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    return _fitted_driver(y, horizon, True, FC_METHOD_ETS_AAN)


fn ets_aaa_fitted(y: List[Float64], period: Int, horizon: Int) -> FittedForecast:
    """ETS(A,A,A) with fitted level/trend: frozen seasonal indices + `holt_fitted` core.

    The seasonal state is the frozen composition `forecasting.point._seasonal_indices`
    (moving-average trend -> detrend -> interior slice -> per-phase averages, all four
    steps frozen kernels); the level and trend are then fitted on the DESEASONALISED
    series exactly as `holt_fitted` fits them, and the index of the future phase
    `(n - 1 + h) mod period` is added back. `period == 1` reduces to `holt_fitted`
    (index 0.0) rather than being refused, matching `point.ets_aaa_forecast`.

    The seasonal indices are NOT refitted jointly with the state: they are the frozen
    estimate, deliberately, so the only new estimation surface this driver adds over
    `point.ets_aaa_forecast` is the one the M4 experiment isolated — the initial
    level/trend. A period the series cannot support one interior cycle of is
    FC_ERR_PERIOD, never a forecast built from edge padding.

    @capability ets_aaa_fitted
    complexity: O(n) -- the seasonal pass is O(n * period), charged by fc_period_defect
    counts:
    - dim period [kernel_validated]
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_fitted(defect, FC_METHOD_ETS_AAA, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_fitted(defect, FC_METHOD_ETS_AAA, horizon, n)
    defect = fc_period_defect(n, period)
    if defect != FC_OK:
        return _no_fitted(defect, FC_METHOD_ETS_AAA, horizon, n)
    if n < 2:
        return _no_fitted(FC_ERR_INSUFFICIENT_HISTORY, FC_METHOD_ETS_AAA, horizon, n)
    if not fc_work_fits(n, FIT_NM_MAX_EVALS, FIT_MAX_WORK):
        return _no_fitted(FC_ERR_WORK_BUDGET, FC_METHOD_ETS_AAA, horizon, n)
    var indices = _seasonal_indices(y, period)
    if len(indices) != period:
        return _no_fitted(FC_ERR_PERIOD, FC_METHOD_ETS_AAA, horizon, n)
    var adjusted = List[Float64]()
    for t in range(n):
        adjusted.append(y[t] - indices[t % period])
    if not fc_all_finite(adjusted):
        return _no_fitted(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAA, horizon, n)
    var core = _fitted_driver(adjusted, horizon, False, FC_METHOD_ETS_AAA)
    if not core.has_forecast:
        return _no_fitted(core.status, FC_METHOD_ETS_AAA, horizon, n)
    var values = List[Float64]()
    for h in range(1, horizon + 1):
        var v = core.values[h - 1] + indices[(n - 1 + h) % period]
        if not fc_finite(v):
            return _no_fitted(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAA, horizon, n)
        values.append(v)
    return FittedForecast(
        FC_OK, FC_METHOD_ETS_AAA, horizon, n, values^, True,
        core.alpha, core.beta, core.phi, core.l0, core.b0,
        core.level, core.trend, core.sse, core.insample_mae,
        core.init_status, core.init_solved, core.n_params + period,
        fc_status_name(FC_OK), fc_status_name(core.init_status),
    )
