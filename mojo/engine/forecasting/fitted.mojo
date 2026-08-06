"""
forecasting.fitted — drivers that FIT what the pointwise drivers take as inputs: the
Holt family's smoothing parameters AND initial state (closing the measured M4
fixed-init defect), and the Theta family's theta itself — static (`theta_fitted`,
golden section on the profile SSE) and dynamic (`dotm_fitted`, the reference DOTM
state-space fit). Zero Python imports.

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

The seasonal driver: the SAME defect, one component over — with the measurement
---------------------------------------------------------------------------------
The first shipped `ets_aaa_fitted` composed the frozen static seasonal indices with the
fitted AAN core, and it measured WORSE than statsforecast's ETS(A,A,A) on M4 Quarterly
by +0.397 sMAPE (10.873 vs 10.476, all 24,000 series). The controlled experiment that
isolated the cause (2026-08-01, this machine, 300-series M4 Quarterly sample, replica
recursion validated to ~1e-12 against statsforecast 2.1.1 on every component):

    statsforecast fit, statsforecast forecast            sMAPE 10.62   (the target)
    their fitted (alpha, beta, gamma), UNFITTED initial
      states from the decomposition heuristic            sMAPE 14.59   (+3.97)
    joint fit with gamma FROZEN at the 1e-4 floor        sMAPE 10.90   (+0.28)

Handing the reference its own smoothing parameters but a heuristic initial state
destroys the forecast; freezing the seasonal UPDATE barely moves it (median fitted
gamma sits at the floor). The failing component is therefore the same one the module
exists to fit — the initial state, which for a seasonal model includes the m - 1 free
initial seasonal indices (the m-th is the zero-sum closure). `ets_aaa_fitted` now fits
[alpha, beta, gamma, l0, b0, s_1..s_(m-1)] jointly through the same reference
Nelder-Mead, from the reference starting point (`initparam`'s m-dependent starts and
in-place beta/gamma ceilings; `initstate`'s centered-MA decomposition, de-meaned phase
averages, OLS over min(max(10, 2m), n) head observations). With the return-index
semantics documented at `_nm_run` reproduced as well, the end-to-end replica matches
statsforecast's fitted parameter vectors to rel < 1e-8 on 300 of 300 sampled Quarterly
series, and THIS DRIVER's forecasts match a statsforecast 2.1.1 run on the same
machine on every seasonal M4 series there is — 24,000 Quarterly, 48,000 Monthly, 414
Hourly, all within 1e-6 scaled, row sMAPE/MASE equal to four decimals. A caution
recorded from the same measurement: two statsforecast runs from DIFFERENT
numpy/statsmodels builds disagree with each other on 3,280 of 24,000 Quarterly series
(0.10 sMAPE between them, equal in-sample objectives) — at simplex dimension m + 4 the
optimizer has equal-likelihood basins that last-bit arithmetic selects between, so
cross-checks of this row are only meaningful against a same-environment run. One
deviation from the reference is deliberate: for 2m <= n < 3m it switches its starting
decomposition to a Fourier regression; this module keeps the centered-MA decomposition
wherever `fc_period_defect` admits the period (the bound is exactly the
full-phase-coverage bound of the MA), because the start only seeds the joint fit. No M4
series is short enough to hit that branch.

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

from series import _ols_fit

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_ERR_WORK_BUDGET,
    FC_METHOD_ETS_AAA,
    FC_METHOD_ETS_AAN,
    FC_OK,
    fc_damping_defect,
    fc_finite,
    fc_horizon_defect,
    fc_period_defect,
    fc_series_defect,
    fc_smoothing_defect,
    fc_status_name,
    fc_work_fits,
)
from forecasting.point import FC_MAX_THETA, theta_forecast

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
comptime FIT_GAMMA_LO: Float64 = 1.0e-4
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
# one O(n) pass, and dim <= 5 for the non-seasonal drivers. The honest worst-case charge
# per call is therefore FIT_NM_MAX_ITER * 8 = 8000 passes. Bounding memory is not
# bounding work: without this charge a structurally valid 4-million-observation series
# is a ~2.6e11-operation request — a hang, which from the caller's side is the same
# outcome as the uncatchable abort. 2^32 / 8000 admits n up to ~536,000, several times
# the longest series in any forecasting corpus this package has been pointed at, and
# caps the worst case at a few seconds of CPU. The SEASONAL driver's dim is m + 4, so
# its charge cannot be a comptime constant: `ets_aaa_fitted` charges
# FIT_NM_MAX_ITER * (m + 7) with the same arithmetic, against the same budget.
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
    authority — no padded zeros, no repeated last value). `alpha`, `beta`, `gamma`,
    `phi` are the fitted smoothing parameters — `gamma` is 0.0 for the non-seasonal
    drivers, the value the reference recursion itself uses for a seasonless model, and
    reported so a seasonal fit is auditable; `l0`, `b0` the fitted initial state;
    `level`, `trend` the terminal state the forecast extrapolates from. `sse` is the
    exact in-sample one-step SSE at the reported fit; `insample_mae` is the mean
    absolute one-step error over t = 1..n-1 — t = 0 is EXCLUDED so the number is
    comparable across methods whose first forecast consumes a different amount of state
    (SES's first error is at t = 1; this model's is at t = 0). `forecasting.select`
    selects on exactly that field.

    `init_status`/`init_solved` report the initial-state provenance separately from
    `status`: a fit whose final vertex sat on a singular 2x2 system still forecasts, but
    a caller auditing the state must be able to see the fallback. For the SEASONAL
    driver there is no closed-form 2x2 audit — the whole initial state is a jointly
    fitted quantity — so `ets_aaa_fitted` reports `init_status = FC_OK` with
    `init_solved = False`, a combination the non-seasonal drivers never produce (their
    fallback is always accompanied by FC_ERR_INSUFFICIENT_HISTORY). `n_params` counts
    fitted quantities carrying information: 4 for Holt (alpha, beta, l0, b0), 5 damped,
    m + 4 seasonal (alpha, beta, gamma, l0, b0, m - 1 free initial seasonal states).
    """

    var status: Int
    var method_id: Int
    var horizon: Int
    var n_train: Int
    var values: List[Float64]
    var has_forecast: Bool
    var alpha: Float64
    var beta: Float64
    var gamma: Float64
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


def _no_fitted(status: Int, method_id: Int, horizon: Int, n_train: Int) -> FittedForecast:
    """A refusal: no path, no parameter estimates, every presence flag cleared."""
    return FittedForecast(
        status, method_id, horizon, n_train, List[Float64](), False,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        status, False, 0, fc_status_name(status), fc_status_name(status),
    )


def _clean_pass(
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


def _objective(
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


def _aaa_pass(
    y: List[Float64], m: Int, alpha: Float64, beta: Float64, gamma: Float64,
    l0: Float64, b0: Float64, s_init: List[Float64],
) -> List[Float64]:
    """`[sse, level, trend, sum_abs_err_from_t1, s_0..s_(m-1)]` for ETS(A,A,A), or empty.

    THE one forward evaluation of the seasonal state-space recursion — the seasonal
    sibling of `_clean_pass`, reproducing the reference `ets.cpp::Calc` operation
    order exactly (phi = 1): the likelihood error is `y_t - ((l + b) + s_head)` while
    the state update recomputes its own differently-rounded residuals
    (`p - q`, `t - s_head`) and applies `phi_b + (beta/alpha)*(r - phi_b)` to the
    trend — algebraically `b + beta*e` but not the same floats, and the fit was
    validated against the reference through THIS rounding. `s_init` carries the full
    m seasonal states, `s_init[m-1]` applying to the first observation; the terminal
    states come back in the same layout (index 0 newest). The buffer is circular —
    the reference's per-step shift, without the copy. Empty on any non-finite
    accumulation, so a NaN state can never be read as a forecast.
    """
    var out = List[Float64]()
    if len(s_init) != m or m < 2:
        return out^
    var lev = l0
    var trd = b0
    var buf = List[Float64](capacity=m)
    for j in range(m):
        buf.append(s_init[j])
    var top = 0
    var bpa = beta / alpha
    var sse: Float64 = 0.0
    var sae: Float64 = 0.0
    for t in range(len(y)):
        var head = buf[(top + m - 1) % m]
        var f0 = lev + trd
        f0 = f0 + head
        var e = y[t] - f0
        sse += e * e
        if t >= 1:
            sae += fabs(e)
        var phi_b = trd
        var q = lev + phi_b
        var p = y[t] - head
        var lnew = q + alpha * (p - q)
        var r = lnew - lev
        var bnew = phi_b + bpa * (r - phi_b)
        var tres = y[t] - q
        var snew = head + gamma * (tres - head)
        top = (top + m - 1) % m
        buf[top] = snew
        lev = lnew
        trd = bnew
    if not fc_finite(sse) or not fc_finite(lev) or not fc_finite(trd):
        return out^
    for j in range(m):
        if not fc_finite(buf[(top + j) % m]):
            return out^
    out.append(sse)
    out.append(lev)
    out.append(trd)
    out.append(sae)
    for j in range(m):
        out.append(buf[(top + j) % m])
    return out^


def _seasonal_decompose_state(y: List[Float64], m: Int) -> List[Float64]:
    """`[l0, b0, s_1..s_(m-1)]` — the reference `initstate` for a seasonal additive
    model, from the record itself.

    Centered moving-average trend (the 2xm filter for an even m), detrend, per-phase
    means over the interior where the trend exists, DE-MEANED so the phase indices sum
    to zero (the closure the optimizer's derived m-th state relies on), then OLS of the
    seasonally adjusted head — min(max(10, 2m), n) observations against t = 1.. — for
    (l0, b0). The m - 1 free states are the phase indices at phases m-1 down to 1, the
    reference's ordering; the m-th is NOT returned because it is not a free coordinate.
    `fc_period_defect`'s admission bound is exactly the bound at which every phase has
    at least one interior detrended observation, so a caller that validated the period
    cannot reach the empty return through phase coverage — the guard remains for
    non-finite accumulation only.
    """
    var out = List[Float64]()
    var n = len(y)
    var half = m // 2
    if n < m + 2 * half:
        return out^
    # Valid centered-MA positions: [half, half + n_valid), one trend value each.
    var n_valid = n - m + 1 if m % 2 == 1 else n - m
    var sums = List[Float64](capacity=m)
    var counts = List[Int](capacity=m)
    for _ in range(m):
        sums.append(0.0)
        counts.append(0)
    for k in range(n_valid):
        var t = half + k
        var acc: Float64 = 0.0
        if m % 2 == 0:
            acc = 0.5 * y[t - half]
            for j in range(t - half + 1, t + half):
                acc += y[j]
            acc += 0.5 * y[t + half]
        else:
            for j in range(t - half, t + half + 1):
                acc += y[j]
        var trend_t = acc / Float64(m)
        sums[t % m] += y[t] - trend_t
        counts[t % m] += 1
    var pa = List[Float64](capacity=m)
    var pa_sum: Float64 = 0.0
    for ph in range(m):
        if counts[ph] == 0:
            return out^
        var v = sums[ph] / Float64(counts[ph])
        pa.append(v)
        pa_sum += v
    var pa_mean = pa_sum / Float64(m)
    for ph in range(m):
        pa[ph] -= pa_mean
    # OLS of the seasonally adjusted head against t = 1..maxn (the reference regressor).
    var maxn = min(max(10, 2 * m), n)
    var st: Float64 = 0.0
    var sy: Float64 = 0.0
    var stt: Float64 = 0.0
    var sty: Float64 = 0.0
    for i in range(maxn):
        var t = Float64(i + 1)
        var v = y[i] - pa[i % m]
        st += t
        sy += v
        stt += t * t
        sty += t * v
    var nf = Float64(maxn)
    var den = nf * stt - st * st
    if den == 0.0:
        return out^
    var b0 = (nf * sty - st * sy) / den
    var l0 = (sy - b0 * st) / nf
    if not fc_finite(l0) or not fc_finite(b0):
        return out^
    out.append(l0)
    out.append(b0)
    for j in range(m - 1):
        var v = pa[m - 1 - j]
        if not fc_finite(v):
            return List[Float64]()
        out.append(v)
    return out^


def fitted_init_solve(
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


def _heuristic_state(y: List[Float64]) -> List[Float64]:
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


def _nm_objective_at(
    y: List[Float64], x: List[Float64], damped: Bool, m: Int, dotm: Bool = False
) -> Float64:
    """The joint objective at a Nelder-Mead vertex: unpack, then `n*log(SSE)`.

    Vertex layout is [alpha, beta, l0, b0] undamped and [alpha, beta, phi, l0, b0]
    damped — the reference parameter order (smoothing parameters first, then state).
    `m > 1` selects the seasonal layout [alpha, beta, gamma, l0, b0, s_1..s_(m-1)]:
    the m-th seasonal state is DERIVED, `0 - sum(free states)` in coordinate order,
    exactly the reference's zero-sum closure — the optimizer moves m - 1 seasonal
    coordinates and the closure absorbs them, so the simplex geometry matches the
    implementation the fit was validated against.

    `dotm` selects the dynamic-theta layout [l0, alpha, theta] and ITS reference
    objective (tail SSE over the mean absolute observation — see `_dotm_pass`); the
    default keeps every existing caller on the exact code path the ETS fits were
    validated on.
    """
    if dotm:
        var pass_ = _dotm_pass(y, x[0], x[1], x[2])
        if len(pass_) != 7:
            return 1.0 / 0.0
        return pass_[0]
    if m > 1:
        var s_full = List[Float64](capacity=m)
        var s_sum: Float64 = 0.0
        for j in range(m - 1):
            s_full.append(x[5 + j])
            s_sum += x[5 + j]
        s_full.append(0.0 - s_sum)
        var pass_ = _aaa_pass(y, m, x[0], x[1], x[2], x[3], x[4], s_full)
        if len(pass_) != 4 + m:
            return 1.0 / 0.0
        var n = Float64(len(y))
        var sse = pass_[0]
        if sse > 0.0:
            return n * log(sse)
        return n * log(sse + 1.0e-8)
    if damped:
        return _objective(y, x[0], x[1], x[2], x[3], x[4])
    return _objective(y, x[0], x[1], 1.0, x[2], x[3])


def _nm_clamp(mut x: List[Float64], lower: List[Float64], upper: List[Float64]):
    """Coordinate-wise clamp to the box, the reference bounds handling."""
    for i in range(len(x)):
        if x[i] < lower[i]:
            x[i] = lower[i]
        if x[i] > upper[i]:
            x[i] = upper[i]


def _nm_run(
    y: List[Float64], x0: List[Float64], lower: List[Float64],
    upper: List[Float64], damped: Bool, m: Int, dotm: Bool = False,
) -> List[Float64]:
    """The best vertex of the reference Nelder-Mead over the given box, or empty.

    Reproduces statsforecast 2.1.1's `nm::NelderMead` exactly (verified against
    `nelder_mead.h` source, 2026-08-01): initial simplex perturbs coordinate i of vertex
    i by *1.05 (or to 1e-4 from zero) then clamps; Gao-Han adaptive coefficients
    gamma = 1 + 2/dim, rho = 0.75 - 1/(2*dim), sigma = 1 - 1/dim with reflection
    coefficient 1; every candidate clamped to the box; convergence when the POPULATION
    standard deviation of the vertex objectives drops below 1e-4, checked after
    ordering, before the centroid; at most 1000 iterations; ties in the vertex ordering
    broken stably (insertion sort), matching the replica this function was validated
    against series-by-series. The dimension is `len(x0)` — the same loop drives the
    4/5-coordinate trend fits and the (m + 4)-coordinate seasonal fit, so there is no
    second optimizer to drift from the validated one.

    THE RETURN INDEX IS THE REFERENCE'S, AND IT IS SUBTLE: `nm::NelderMead` returns
    `simplex.row(best_idx)` where `best_idx` came from the ordering at the START of the
    final iteration — when the 1000-iteration cap ends the search, an improvement
    accepted DURING that final iteration is discarded, because the reference never
    re-sorts after the loop. A first draft of the seasonal fit returned the post-update
    best instead, and the measured consequence on the divergent M4 Quarterly series was
    one-sided: 122 of 600 sampled fits strictly BETTER in-sample, zero worse — a
    different estimator from the reference, not a faithful replica, and unauditable
    against it. With the reference index reproduced, the same probe finds 600 of 600
    exact objective ties. The trend fits converge long before the cap (dim 4/5), which
    is why they matched the stored parameter vectors either way; the seasonal simplex
    (dim m + 4) hits the cap routinely.

    Empty when no vertex of the initial simplex has a finite objective — the caller
    turns that into FC_ERR_ALL_UNDEFINED. A shrink step re-evaluates every non-best
    vertex, exactly as the reference does. The returned list is the RAW winning vertex
    in the caller's coordinate layout.
    """
    var out = List[Float64]()
    var dim = len(x0)
    var x0c = List[Float64](capacity=dim)
    for j in range(dim):
        x0c.append(x0[j])
    _nm_clamp(x0c, lower, upper)

    # dim+1 vertices; vertex i (i < dim) perturbs coordinate i, vertex dim is x0.
    var simplex = List[List[Float64]]()
    for i in range(dim + 1):
        var row = List[Float64]()
        for j in range(dim):
            row.append(x0c[j])
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
        var fv = _nm_objective_at(y, simplex[i], damped, m, dotm)
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
    # The reference's return index: the best vertex as of the LAST ordering performed,
    # never re-sorted after the loop (see the docstring for the measured consequence).
    var ret_idx = 0
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
        ret_idx = best
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
        var fr = _nm_objective_at(y, xr, damped, m, dotm)
        if fvals[best] <= fr and fr < fvals[second_worst]:
            simplex[worst] = xr^
            fvals[worst] = fr
        elif fr < fvals[best]:
            # Expansion.
            var xe = List[Float64]()
            for j in range(dim):
                xe.append(centroid[j] + coef_gamma * (xr[j] - centroid[j]))
            _nm_clamp(xe, lower, upper)
            var fe = _nm_objective_at(y, xe, damped, m, dotm)
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
            var foc = _nm_objective_at(y, xoc, damped, m, dotm)
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
                    fvals[i] = _nm_objective_at(y, simplex[i], damped, m, dotm)
        else:
            # Inner contraction.
            var xic = List[Float64]()
            for j in range(dim):
                xic.append(centroid[j] - coef_rho * (xr[j] - centroid[j]))
            _nm_clamp(xic, lower, upper)
            var fic = _nm_objective_at(y, xic, damped, m, dotm)
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
                    fvals[i] = _nm_objective_at(y, simplex[i], damped, m, dotm)
    if not fc_finite(fvals[ret_idx]):
        return out^
    for j in range(dim):
        out.append(simplex[ret_idx][j])
    return out^


def _fit_nelder_mead(y: List[Float64], damped: Bool) -> List[Float64]:
    """`[alpha, beta, phi, l0, b0]` fitted by the reference Nelder-Mead, or empty.

    The non-seasonal builder over `_nm_run`: reference starting point (`initparam`'s
    m = 1 starts, `initstate`'s OLS head regression), reference box (the FIT_BETA_HI
    ceiling included), then the validated optimizer. Empty when no vertex of the
    initial simplex has a finite objective — the caller turns that into
    FC_ERR_ALL_UNDEFINED — and empty is also the answer when the heuristic starting
    state cannot be formed. The undamped return carries phi = 1.0 so both layouts
    unpack identically downstream.
    """
    var out = List[Float64]()
    var start = _heuristic_state(y)
    if len(start) != 2:
        return out^
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
    var best = _nm_run(y, x0, lower, upper, damped, 1)
    if len(best) == 0:
        return out^
    out.append(best[0])
    out.append(best[1])
    if damped:
        out.append(best[2])
        out.append(best[3])
        out.append(best[4])
    else:
        out.append(1.0)
        out.append(best[2])
        out.append(best[3])
    return out^


def _fit_nelder_mead_aaa(y: List[Float64], m: Int) -> List[Float64]:
    """`[alpha, beta, gamma, l0, b0, s_0..s_(m-1)]` jointly fitted, or empty.

    The seasonal builder over `_nm_run`, reproducing the reference exactly:

      * `initparam` with the season length in it — `alpha = lo + 0.2*(hi - lo)/m`,
        then the SAME in-place ceiling trap as FIT_BETA_HI, twice: the beta box is
        `min(hi, alpha_start)` and the gamma box `min(hi, 1 - alpha_start)`, both
        against the STARTING alpha, and `beta = lo + 0.1*(box)`,
        `gamma = lo + 0.05*(box)` from the mutated boxes.
      * `initstate` via `_seasonal_decompose_state` — the m - 1 free seasonal
        coordinates ride the simplex; the m-th is derived by the zero-sum closure
        inside the objective.

    The RETURNED seasonal state is the full m-vector with the closure applied to the
    winning vertex (index 0 newest, s[m-1] applying to the first observation), so the
    caller never re-derives the closure. Empty when the decomposition cannot be formed
    or no vertex is finite.
    """
    var out = List[Float64]()
    var state = _seasonal_decompose_state(y, m)
    if len(state) != m + 1:
        return out^
    var alpha0 = FIT_ALPHA_LO + 0.2 * (FIT_ALPHA_HI - FIT_ALPHA_LO) / Float64(m)
    var beta_hi = min(FIT_ALPHA_HI, alpha0)
    var beta0 = FIT_BETA_LO + 0.1 * (beta_hi - FIT_BETA_LO)
    var gamma_hi = min(FIT_ALPHA_HI, 1.0 - alpha0)
    var gamma0 = FIT_GAMMA_LO + 0.05 * (gamma_hi - FIT_GAMMA_LO)
    var x0 = List[Float64]()
    x0.append(alpha0)
    x0.append(beta0)
    x0.append(gamma0)
    for j in range(m + 1):
        x0.append(state[j])
    var lower = List[Float64]()
    var upper = List[Float64]()
    var big: Float64 = 1.0 / 0.0
    lower.append(FIT_ALPHA_LO)
    upper.append(FIT_ALPHA_HI)
    lower.append(FIT_BETA_LO)
    upper.append(beta_hi)
    lower.append(FIT_GAMMA_LO)
    upper.append(gamma_hi)
    for _ in range(m + 1):
        lower.append(-big)
        upper.append(big)
    var best = _nm_run(y, x0, lower, upper, False, m)
    if len(best) != m + 4:
        return out^
    for j in range(5):
        out.append(best[j])
    var s_sum: Float64 = 0.0
    for j in range(m - 1):
        out.append(best[5 + j])
        s_sum += best[5 + j]
    out.append(0.0 - s_sum)
    return out^


def _fitted_driver(
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
        alpha, beta, 0.0, phi, l0, b0, level, trend, sse, mae,
        audit.status, audit.solved, 5 if damped else 4,
        fc_status_name(FC_OK), fc_status_name(audit.status),
    )


def holt_fitted(y: List[Float64], horizon: Int) -> FittedForecast:
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


def damped_fitted(y: List[Float64], horizon: Int) -> FittedForecast:
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


def ets_aaa_fitted(y: List[Float64], period: Int, horizon: Int) -> FittedForecast:
    """ETS(A,A,A) with the WHOLE state fitted: level, trend AND the seasonal indices.

    The joint fit the module docstring's controlled experiment demands:
    [alpha, beta, gamma, l0, b0, s_1..s_(m-1)] on one Nelder-Mead simplex (the m-th
    initial seasonal state is the zero-sum closure), objective `n*log(SSE)` through the
    reference recursion `_aaa_pass`, starting point `_seasonal_decompose_state` /
    `initparam`-with-m. Its predecessor held the decomposition indices STATIC and fitted
    only the deseasonalised level/trend; the controlled attribution showed the static
    initial state — not the missing seasonal update — carries the loss (+3.97 sample
    sMAPE at the reference's own smoothing parameters), and the replica of THIS fit
    matches statsforecast 2.1.1 to rel < 1e-8 on 287/300 sampled Quarterly series.

    Forecast step h adds the seasonal state of phase `(m - 1 - (h-1)) mod m` (newest
    first, the reference's indexing) to `level + h*trend`. On the full M4 corpus this
    driver's forecasts match a same-machine statsforecast 2.1.1 run on ALL seasonal
    series (24,000 + 48,000 + 414, within 1e-6 scaled; row sMAPE/MASE equal to four
    decimals), and the M4 AAA row moves from OWA 0.928/0.961/0.755 (static indices) to
    0.903/0.952/0.703 on Quarterly/Monthly/Hourly. `period == 1` reduces to
    `holt_fitted` (gamma unused, reported 0.0) rather than being refused, matching
    `point.ets_aaa_forecast`. A period the series cannot support one interior
    moving-average cycle of is FC_ERR_PERIOD, never a forecast built from edge padding.
    The work budget is charged at the seasonal dimension: FIT_NM_MAX_ITER * (m + 7)
    bounded O(n) passes, the (dim + 3) arithmetic documented at FIT_NM_MAX_EVALS.

    `init_status` is FC_OK with `init_solved = False`: the initial state is a jointly
    fitted quantity here, and there is no closed-form 2x2 audit to report — see the
    struct docstring for why that combination is reserved to this driver.

    @capability ets_aaa_fitted
    complexity: O(n) -- at most FIT_NM_MAX_ITER * (period + 7) bounded O(n) passes
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
    if period <= 1:
        return _fitted_driver(y, horizon, False, FC_METHOD_ETS_AAA)
    var seasonal_evals = FIT_NM_MAX_ITER * (period + 7)
    if not fc_work_fits(n, seasonal_evals, FIT_MAX_WORK):
        return _no_fitted(FC_ERR_WORK_BUDGET, FC_METHOD_ETS_AAA, horizon, n)
    var fit = _fit_nelder_mead_aaa(y, period)
    if len(fit) != period + 5:
        return _no_fitted(FC_ERR_ALL_UNDEFINED, FC_METHOD_ETS_AAA, horizon, n)
    var alpha = fit[0]
    var beta = fit[1]
    var gamma = fit[2]
    var l0 = fit[3]
    var b0 = fit[4]
    var s_init = List[Float64](capacity=period)
    for j in range(period):
        s_init.append(fit[5 + j])
    var pass_ = _aaa_pass(y, period, alpha, beta, gamma, l0, b0, s_init)
    if len(pass_) != 4 + period:
        return _no_fitted(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAA, horizon, n)
    var sse = pass_[0]
    var level = pass_[1]
    var trend = pass_[2]
    var mae = pass_[3] / Float64(n - 1)
    var values = List[Float64]()
    for h in range(1, horizon + 1):
        var j = period - h
        while j < 0:
            j += period
        var v = level + Float64(h) * trend + pass_[4 + j]
        if not fc_finite(v):
            return _no_fitted(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAA, horizon, n)
        values.append(v)
    return FittedForecast(
        FC_OK, FC_METHOD_ETS_AAA, horizon, n, values^, True,
        alpha, beta, gamma, 1.0, l0, b0,
        level, trend, sse, mae,
        FC_OK, False, period + 4,
        fc_status_name(FC_OK), fc_status_name(FC_OK),
    )


# ═══ Optimized Theta: theta fitted per series, not frozen at 2 ══════════════════════
#
# `point.theta_forecast` takes theta as an INPUT and the shipped pipelines freeze it at
# the classical 2.0. But theta is a per-series quantity: `1 - 1/theta` is the weight on
# the extrapolated OLS line, and how much a series' future rewards its full-sample trend
# is exactly the kind of thing an in-sample fit can estimate (Fiorucci et al. 2016 fit
# it by in-sample SSE and call the family "optimised theta"). The fit here is the same
# machinery the package already trusts for alpha — golden section on the one-step
# in-sample SSE — nested: for each theta probe, alpha is fitted on the theta line by
# the EXACT golden section `forecasting.select` ships for the classical theta-2 line
# (same bounds, same 28 iterations, same bracket updates), then the profile objective
#
#     SSE(theta) = (1/theta)^2 * SSE_SES(Z_theta, alpha*(theta))
#
# is compared across theta probes. The (1/theta)^2 scaling is NOT decoration: by the
# decomposition identity `y = (1/theta)*Z(theta) + (1 - 1/theta)*L` the one-step
# in-sample error of the theta METHOD is `(1/theta) * (z_t - s_{t-1})` — the SES error
# on the theta line, rescaled — so without the scaling the objective would be the error
# of the LINE, not of the method, and it would grow ~theta^2 instead of measuring
# anything. `theta = 1` is plain SES; the profile at 1 equals the SES SSE exactly.
#
# Why golden section and not the Nelder-Mead above: the alpha fit this must reduce to
# at theta = 2 (the shipped Theta row's `a_th`) IS a golden section, and the anchor
# requirement — theta forced to 2.0 reproduces that row bit-for-bit — is only checkable
# if the inner fit is op-identical to it. The helpers below therefore mirror
# `select._ses_sse_mae` / `select._golden_ses_alpha` operation for operation; the suite
# pins the two fits to bit-equality on probe series so the copies cannot drift.
#
# The theta box [1, 10]: the lower bound is `theta_forecast`'s own admission bound
# (theta < 1 leans AGAINST the fitted trend — a sign error, refused there). The upper
# bound is fixed a priori, not tuned: at theta = 10 the line weight `1 - 1/theta` is
# already 0.9, past which the family is numerically the OLS-line extrapolation that
# `series.linear_extrapolation` serves honestly (the same reasoning as FC_MAX_THETA,
# one order of magnitude earlier). The reference implementation (statsforecast 2.1.1
# `optimize_theta_target_fn`) bounds theta in [1, 1e10] but starts its Nelder-Mead at
# 2.0, so ITS effective range is local myopia; a golden section needs the honest box
# stated, and it is stated here once, before any measurement.

comptime FIT_THETA_LO: Float64 = 1.0
comptime FIT_THETA_HI: Float64 = 10.0
comptime FIT_THETA_GOLDEN_ITERS: Int = 28
comptime FIT_THETA_GOLDEN_RATIO: Float64 = 0.6180339887498949  # (sqrt(5) - 1) / 2
# The reference SES bounds, the same values `forecasting.select` uses for a_theta.
comptime FIT_THETA_ALPHA_LO: Float64 = 0.01
comptime FIT_THETA_ALPHA_HI: Float64 = 0.99

# The work budget, with the arithmetic: one theta PROBE costs one theta-line build,
# one inner golden section (2 SSE passes per iteration) and one SSE pass at the fitted
# alpha = 2 * FIT_THETA_GOLDEN_ITERS + 2 bounded O(n) passes. The outer golden section
# runs 2 probes per iteration plus the final refit probe, and the OLS line is one more
# pass: (2 * 28 + 1) * (2 * 28 + 2) + 1 = 3307. Same FIT_MAX_WORK budget as the
# Nelder-Mead drivers; 2^32 / 3307 admits n up to ~1.3 million.
comptime FIT_THETA_PROBE_PASSES: Int = 2 * FIT_THETA_GOLDEN_ITERS + 2
comptime FIT_THETA_MAX_EVALS: Int = (
    (2 * FIT_THETA_GOLDEN_ITERS + 1) * FIT_THETA_PROBE_PASSES + 1
)


@fieldwise_init
struct ThetaFit(Copyable, Movable):
    """A Theta forecast whose theta (and theta-line alpha) were fitted here.

    `values` holds steps 1..horizon, EMPTY on any refusal (`has_forecast` is the
    authority — no padded zeros, no repeated last value). `theta` and `alpha` are the
    fitted parameters; the path itself comes out of `point.theta_forecast`, so the
    method family stays FC_METHOD_THETA — a theta with a fitted theta is the same
    method family, not a new method, and no id is minted.

    `sse` is the one-step in-sample SSE of the METHOD — `(1/theta)^2` times the SES SSE
    on the theta line, by the decomposition identity — and `insample_mae` the matching
    mean absolute one-step error over t = 1..n-1, the SAME statistic
    `forecasting.select` computes for classical theta (its `0.5 * z_mae` is this
    quantity at theta = 2), so a selector can rank this driver against the existing
    candidates without a conversion.
    """

    var status: Int
    var horizon: Int
    var n_train: Int
    var values: List[Float64]
    var has_forecast: Bool
    var theta: Float64
    var alpha: Float64
    var sse: Float64
    var insample_mae: Float64
    var status_name: String


def _no_theta_fit(status: Int, horizon: Int, n_train: Int) -> ThetaFit:
    """A refusal: no path, no parameter estimates."""
    return ThetaFit(
        status, horizon, n_train, List[Float64](), False,
        0.0, 0.0, 0.0, 0.0, fc_status_name(status),
    )


def _theta_ses_sse_mae(z: List[Float64], alpha: Float64) -> List[Float64]:
    """`[sse, mae]` of one-step errors under the engine SES recursion, `s_0 = z[0]`.

    OP-IDENTICAL to `select._ses_sse_mae` — same recursion, same accumulation order —
    because the theta = 2 special case of the drivers below must reproduce the shipped
    Theta pipeline bit-for-bit, and that pipeline's alpha came out of exactly this
    pass. The suite pins the equality; a change here that survives compilation will
    fail it. Errors run t = 1..n-1; the caller guarantees n >= 2. Empty on a
    non-finite accumulation.
    """
    var out = List[Float64]()
    var s = z[0]
    var sse: Float64 = 0.0
    var sae: Float64 = 0.0
    for t in range(1, len(z)):
        var e = z[t] - s
        sse += e * e
        sae += fabs(e)
        s = alpha * z[t] + (1.0 - alpha) * s
    if not fc_finite(sse) or not fc_finite(sae):
        return out^
    out.append(sse)
    out.append(sae / Float64(len(z) - 1))
    return out^


def _theta_golden_alpha(z: List[Float64]) -> Float64:
    """Golden-section argmin of the SES one-step SSE over [0.01, 0.99].

    OP-IDENTICAL to `select._golden_ses_alpha` (same bracket updates, same 28
    iterations, same midpoint return), for the same bit-parity reason as
    `_theta_ses_sse_mae`. A non-finite SSE at a probe is +inf so the bracket walks
    away from overflow; if every probe is non-finite the midpoint is still returned
    and the CALLER's subsequent pass reports the non-finite fit.
    """
    var lo = FIT_THETA_ALPHA_LO
    var hi = FIT_THETA_ALPHA_HI
    for _ in range(FIT_THETA_GOLDEN_ITERS):
        var x1 = hi - FIT_THETA_GOLDEN_RATIO * (hi - lo)
        var x2 = lo + FIT_THETA_GOLDEN_RATIO * (hi - lo)
        var p1 = _theta_ses_sse_mae(z, x1)
        var p2 = _theta_ses_sse_mae(z, x2)
        var f1 = p1[0] if len(p1) == 2 else 1.0 / 0.0
        var f2 = p2[0] if len(p2) == 2 else 1.0 / 0.0
        if f1 < f2:
            hi = x2
        else:
            lo = x1
    return 0.5 * (lo + hi)


def _theta_line_at(
    y: List[Float64], intercept: Float64, slope: Float64, theta: Float64
) -> List[Float64]:
    """`Z_t = theta*y_t + (1-theta)*(a + b*t)`, or empty on a non-finite value.

    The EXPRESSION is `point.theta_forecast`'s own theta-line construction, kept
    op-identical so the SSE minimised here is the SSE of the line the forecast will
    actually smooth. (At theta = 2 it is also bit-equal to `select._theta_line`'s
    `2*y - L`: `(1-2) * L` is an exact sign flip and `x + (-L)` is the same IEEE
    operation as `x - L`.)
    """
    var out = List[Float64]()
    for t in range(len(y)):
        var z = theta * y[t] + (1.0 - theta) * (intercept + slope * Float64(t))
        if not fc_finite(z):
            return List[Float64]()
        out.append(z)
    return out^


def _theta_profile(
    y: List[Float64], intercept: Float64, slope: Float64, theta: Float64
) -> List[Float64]:
    """`[alpha, method_sse, method_mae]` at one theta, or empty on a non-finite fit.

    One probe of the profile objective: build the theta line, fit alpha on it by the
    inner golden section, then rescale the line's SSE/MAE by `1/theta` per the
    decomposition identity so the numbers are the METHOD's one-step errors, comparable
    across theta values (and across methods — see `ThetaFit.insample_mae`).
    """
    var out = List[Float64]()
    var z = _theta_line_at(y, intercept, slope, theta)
    if len(z) != len(y):
        return out^
    var alpha = _theta_golden_alpha(z)
    var p = _theta_ses_sse_mae(z, alpha)
    if len(p) != 2:
        return out^
    var w = 1.0 / theta
    out.append(alpha)
    out.append(w * w * p[0])
    out.append(w * p[1])
    return out^


def theta_fitted_at(y: List[Float64], theta: Float64, horizon: Int) -> ThetaFit:
    """Classical Theta at a CALLER-CHOSEN theta, with alpha fitted on the theta line.

    The building block `theta_fitted` optimises over, public because it is the anchor:
    at theta = 2.0 this IS the shipped M4 Theta pipeline — the same golden-section
    alpha on the same theta-2 line feeding `point.theta_forecast` — reproduced
    bit-for-bit (the suite asserts it against `forecasting.select`'s own fit, and the
    M4 artifact row was verified equal to the last bit on all 100,000 series).

    Requires n >= 3: the fit ranks alphas by an SSE over n - 1 one-step errors, and a
    single error is an anecdote, not an objective (the same bound `forecasting.select`
    uses, for the same reason).

    @capability theta_fitted_at
    complexity: O(n) -- at most 2*FIT_THETA_GOLDEN_ITERS + 3 bounded O(n) passes
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_theta_fit(defect, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_theta_fit(defect, horizon, n)
    if n < 3:
        return _no_theta_fit(FC_ERR_INSUFFICIENT_HISTORY, horizon, n)
    if not fc_finite(theta):
        return _no_theta_fit(FC_ERR_NON_FINITE, horizon, n)
    if theta < 1.0 or theta > FC_MAX_THETA:
        return _no_theta_fit(FC_ERR_PARAM_RANGE, horizon, n)
    if not fc_work_fits(n, FIT_THETA_PROBE_PASSES + 1, FIT_MAX_WORK):
        return _no_theta_fit(FC_ERR_WORK_BUDGET, horizon, n)
    var fit = _ols_fit(y)
    if len(fit) != 2 or not fc_finite(fit[0]) or not fc_finite(fit[1]):
        return _no_theta_fit(FC_ERR_NON_FINITE, horizon, n)
    var prof = _theta_profile(y, fit[0], fit[1], theta)
    if len(prof) != 3:
        return _no_theta_fit(FC_ERR_NON_FINITE, horizon, n)
    var fc = theta_forecast(y, theta, prof[0], horizon)
    if not fc.has_forecast:
        return _no_theta_fit(fc.status, horizon, n)
    return ThetaFit(
        FC_OK, horizon, n, fc.values.copy(), True,
        theta, prof[0], prof[1], prof[2], fc_status_name(FC_OK),
    )


def theta_fitted(y: List[Float64], horizon: Int) -> ThetaFit:
    """Optimized Theta: theta fitted per series by golden section on the profile SSE.

    Outer golden section on theta over [FIT_THETA_LO, FIT_THETA_HI]; each probe fits
    alpha on that probe's theta line by the inner golden section and reports the
    method's one-step SSE via the decomposition identity (module comment above). The
    returned forecast is `theta_fitted_at(y, theta*, horizon)` — the SAME public
    building block, so the optimum and its forecast cannot drift apart.

    Everything the fit reads is the training series: the OLS line, the theta lines,
    the SES recursions and both golden sections consume `y` alone. Nothing here sees
    a test window; a caller holding one out never hands it to this function.

    A non-finite probe (magnitudes that overflow the theta-line recursion) is +inf, so
    the bracket walks away from overflow exactly as the alpha fit does; if EVERY probe
    is non-finite the final refit reports the non-finite fit and the driver refuses —
    a fit that never evaluated is not a fit.

    @capability theta_fitted
    complexity: O(n) -- at most FIT_THETA_MAX_EVALS bounded O(n) passes, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_theta_fit(defect, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_theta_fit(defect, horizon, n)
    if n < 3:
        return _no_theta_fit(FC_ERR_INSUFFICIENT_HISTORY, horizon, n)
    if not fc_work_fits(n, FIT_THETA_MAX_EVALS, FIT_MAX_WORK):
        return _no_theta_fit(FC_ERR_WORK_BUDGET, horizon, n)
    var fit = _ols_fit(y)
    if len(fit) != 2 or not fc_finite(fit[0]) or not fc_finite(fit[1]):
        return _no_theta_fit(FC_ERR_NON_FINITE, horizon, n)
    var lo = FIT_THETA_LO
    var hi = FIT_THETA_HI
    for _ in range(FIT_THETA_GOLDEN_ITERS):
        var x1 = hi - FIT_THETA_GOLDEN_RATIO * (hi - lo)
        var x2 = lo + FIT_THETA_GOLDEN_RATIO * (hi - lo)
        var p1 = _theta_profile(y, fit[0], fit[1], x1)
        var p2 = _theta_profile(y, fit[0], fit[1], x2)
        var f1 = p1[1] if len(p1) == 3 else 1.0 / 0.0
        var f2 = p2[1] if len(p2) == 3 else 1.0 / 0.0
        if f1 < f2:
            hi = x2
        else:
            lo = x1
    return theta_fitted_at(y, 0.5 * (lo + hi), horizon)


# ═══ Dynamic Optimized Theta (DOTM): the trend line re-estimated at every step ══════
#
# `theta_fitted` extrapolates the OLS line of the WHOLE record; DOTM (Fiorucci et al.
# 2016, the strongest pure-Theta M4 entry class) re-estimates the line RECURSIVELY —
# at step t the model only trusts the line fitted to y_1..y_t — and couples it to the
# smoothed level through the state-space mean
#
#     mu_t = l_{t-1} + (1 - 1/theta) * (A_{t-1}*(1-alpha)^t + B_{t-1}*(1-(1-alpha)^(t+1))/alpha)
#
# where (A_t, B_t) are the running OLS intercept/slope against the 1-based clock,
# maintained by exact recurrences, and l_t is the SES level. The implementation
# reproduces statsforecast 2.1.1's compiled `theta::calc` / `theta::forecast` /
# `theta::optimize` (verified against the C++ source AND numerically against the
# compiled library on randomized trials to 1e-12 before this section was written):
#
#   * t = 0 is charged NO error (mu_0 = y_0 by the reference's dynamic init
#     A_0 = y_0, B_0 = 0) and the level update at t = 0 consumes the FITTED initial
#     level parameter.
#   * B updates from the PRE-update running mean, then the mean updates, then
#     A = meany - B*(t+2)/2 — this exact order; the sampler-style order (mean first)
#     is a DIFFERENT estimator and fails the suite's reference-pinned path.
#   * the fit objective is `sum(e_t^2 for t >= 3) / max(mean|y|, 1e-10)` — the first
#     three errors are excluded (two of them are dominated by the unidentified
#     initial states) and the normalisation makes the 1e-4 simplex-spread stopping
#     rule scale-free. Reproduced EXACTLY, because the Nelder-Mead stopping test is
#     calibrated on this objective's scale, and a rescaled objective is a different
#     stopping point, which is a different fit.
#   * the optimizer is the SAME `_nm_run` the ETS fits were validated on (the
#     reference calls one nm::NelderMead template for both), over the layout
#     [l0, alpha, theta], start [y_0/2, 0.5, 2.0], box [-1e10, 1e10] x [0.1, 0.99]
#     x [1, 1e10] — `initparamtheta` / `optimize_theta_target_fn` verbatim. Theta's
#     alpha floor is 0.1 (not the SES fit's 0.01) and theta's ceiling is the
#     reference's own 1e10: unlike the static golden section, Nelder-Mead needs no
#     finite bracket, so the reference box is reproduced rather than re-derived.
#
# The forecast recursion continues the SAME state updates with each mu taking the
# place of the unobserved y (the reference `theta::forecast`), so a caller cannot
# get a path whose dynamics differ from the fit that produced it.

comptime FIT_DOTM_ALPHA_LO: Float64 = 0.1
comptime FIT_DOTM_ALPHA_HI: Float64 = 0.99
comptime FIT_DOTM_THETA_LO: Float64 = 1.0
comptime FIT_DOTM_THETA_HI: Float64 = 1.0e10
comptime FIT_DOTM_LEVEL_BOUND: Float64 = 1.0e10
comptime FIT_DOTM_MEAN_FLOOR: Float64 = 1.0e-10


@fieldwise_init
struct DotmFit(Copyable, Movable):
    """A dynamic-optimized-theta forecast: (l0, alpha, theta) fitted jointly here.

    `values` holds steps 1..horizon, EMPTY on any refusal (`has_forecast` is the
    authority). `l0` is the fitted initial level (a parameter of this model, unlike
    the static driver where the SES start is pinned to the first theta-line value);
    `theta` and `alpha` the fitted dynamics. The method family is still Theta — no
    new id is minted.

    `sse` is the sum of squared one-step errors over t = 1..n-1 (t = 0 is
    structurally error-free in this model and charging it would flatter nothing);
    NOTE it is the plain SSE, not the reference's normalised OBJECTIVE — the
    objective's tail truncation and scale floor belong to the optimizer, not to an
    audit field. `insample_mae` is the mean absolute one-step error over the same
    t = 1..n-1, the statistic `forecasting.select` ranks candidates by.
    """

    var status: Int
    var horizon: Int
    var n_train: Int
    var values: List[Float64]
    var has_forecast: Bool
    var l0: Float64
    var alpha: Float64
    var theta: Float64
    var sse: Float64
    var insample_mae: Float64
    var status_name: String


def _no_dotm(status: Int, horizon: Int, n_train: Int) -> DotmFit:
    """A refusal: no path, no parameter estimates."""
    return DotmFit(
        status, horizon, n_train, List[Float64](), False,
        0.0, 0.0, 0.0, 0.0, 0.0, fc_status_name(status),
    )


def _dotm_pass(
    y: List[Float64], l0: Float64, alpha: Float64, theta: Float64
) -> List[Float64]:
    """`[objective, level, meany, A, B, sse_from_t1, sae_from_t1]`, or empty.

    THE one forward evaluation of the DOTM recursion — the optimizer's objective,
    the driver's audit numbers and the forecast's starting states all come from this
    pass, so there is no second copy to drift. Reproduces the reference `calc` for
    ModelType::DOTM exactly: dynamic init (A = y_0, B = 0, no t = 0 error), B before
    mean before A, powers taken by `pow` per step as the reference does (a running
    product rounds differently and this fit was validated against the reference
    through this rounding). Objective = tail SSE (t >= 3) over the floored mean
    absolute observation. Empty on any non-finite accumulation.
    """
    var out = List[Float64]()
    var n = len(y)
    if n < 1:
        return out^
    var one_m_a = 1.0 - alpha
    var w = 1.0 - 1.0 / theta
    var lev = alpha * y[0] + one_m_a * l0
    var meany = y[0]
    var a_n = y[0]
    var b_n: Float64 = 0.0
    var abs_sum = fabs(y[0])
    var sse: Float64 = 0.0
    var sae: Float64 = 0.0
    var tail_sse: Float64 = 0.0
    for i in range(1, n):
        var fi = Float64(i)
        var pw = one_m_a ** fi
        var pw1 = one_m_a ** (fi + 1.0)
        var mu = lev + w * (a_n * pw + b_n * (1.0 - pw1) / alpha)
        var e = y[i] - mu
        sse += e * e
        sae += fabs(e)
        if i >= 3:
            tail_sse += e * e
        abs_sum += fabs(y[i])
        lev = alpha * y[i] + one_m_a * lev
        b_n = ((fi - 1.0) * b_n + 6.0 * (y[i] - meany) / (fi + 1.0)) / (fi + 2.0)
        meany = (fi * meany + y[i]) / (fi + 1.0)
        a_n = meany - b_n * (fi + 2.0) / 2.0
    if (
        not fc_finite(lev) or not fc_finite(meany) or not fc_finite(a_n)
        or not fc_finite(b_n) or not fc_finite(sse) or not fc_finite(sae)
    ):
        return out^
    var mean_abs = abs_sum / Float64(n)
    if mean_abs < FIT_DOTM_MEAN_FLOOR:
        mean_abs = FIT_DOTM_MEAN_FLOOR
    out.append(tail_sse / mean_abs)
    out.append(lev)
    out.append(meany)
    out.append(a_n)
    out.append(b_n)
    out.append(sse)
    out.append(sae)
    return out^


def _dotm_forecast_path(
    n: Int, horizon: Int, alpha: Float64, theta: Float64,
    lev0: Float64, meany0: Float64, a0: Float64, b0: Float64,
) -> List[Float64]:
    """Steps 1..horizon of the reference DOTM forecast recursion, or empty.

    Continues the state updates from the terminal in-sample states with each mu
    standing in for the unobserved observation — `theta::forecast` verbatim,
    validated numerically against the compiled reference. Empty on any non-finite
    value, so a diverging extrapolation is a refusal, not a path of infinities.
    """
    var out = List[Float64]()
    var one_m_a = 1.0 - alpha
    var w = 1.0 - 1.0 / theta
    var lev = lev0
    var meany = meany0
    var a_n = a0
    var b_n = b0
    for i in range(n, n + horizon):
        var fi = Float64(i)
        var pw = one_m_a ** fi
        var pw1 = one_m_a ** (fi + 1.0)
        var mu = lev + w * (a_n * pw + b_n * (1.0 - pw1) / alpha)
        if not fc_finite(mu):
            return List[Float64]()
        out.append(mu)
        lev = alpha * mu + one_m_a * lev
        b_n = ((fi - 1.0) * b_n + 6.0 * (mu - meany) / (fi + 1.0)) / (fi + 2.0)
        meany = (fi * meany + mu) / (fi + 1.0)
        a_n = meany - b_n * (fi + 2.0) / 2.0
    return out^


def dotm_fitted(y: List[Float64], horizon: Int) -> DotmFit:
    """DOTM: (l0, alpha, theta) fitted by the reference Nelder-Mead, then extrapolated.

    The dynamic sibling of `theta_fitted` — see the section comment for the model,
    the reference-faithful details, and why the objective is reproduced to the
    letter. Everything the fit reads is the training series; nothing here sees a
    test window.

    Requires n >= 4: the reference objective scores errors from t = 3 on, and a fit
    whose objective saw NO error would converge instantly at its starting point and
    hand back an arbitrary forecast wearing a fitted label — the reference does
    exactly that silently; here it is a refusal.

    @capability dotm_fitted
    complexity: O(n) -- at most FIT_NM_MAX_EVALS bounded O(n) passes, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_dotm(defect, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_dotm(defect, horizon, n)
    if n < 4:
        return _no_dotm(FC_ERR_INSUFFICIENT_HISTORY, horizon, n)
    if not fc_work_fits(n, FIT_NM_MAX_EVALS, FIT_MAX_WORK):
        return _no_dotm(FC_ERR_WORK_BUDGET, horizon, n)
    var x0 = List[Float64]()
    x0.append(y[0] / 2.0)
    x0.append(0.5)
    x0.append(2.0)
    var lower = List[Float64]()
    var upper = List[Float64]()
    lower.append(-FIT_DOTM_LEVEL_BOUND)
    upper.append(FIT_DOTM_LEVEL_BOUND)
    lower.append(FIT_DOTM_ALPHA_LO)
    upper.append(FIT_DOTM_ALPHA_HI)
    lower.append(FIT_DOTM_THETA_LO)
    upper.append(FIT_DOTM_THETA_HI)
    var best = _nm_run(y, x0, lower, upper, False, 1, True)
    if len(best) != 3:
        return _no_dotm(FC_ERR_ALL_UNDEFINED, horizon, n)
    var l0 = best[0]
    var alpha = best[1]
    var theta = best[2]
    var pass_ = _dotm_pass(y, l0, alpha, theta)
    if len(pass_) != 7:
        return _no_dotm(FC_ERR_NON_FINITE, horizon, n)
    var values = _dotm_forecast_path(
        n, horizon, alpha, theta, pass_[1], pass_[2], pass_[3], pass_[4]
    )
    if len(values) != horizon:
        return _no_dotm(FC_ERR_NON_FINITE, horizon, n)
    var mae = pass_[6] / Float64(n - 1)
    return DotmFit(
        FC_OK, horizon, n, values^, True,
        l0, alpha, theta, pass_[5], mae, fc_status_name(FC_OK),
    )
