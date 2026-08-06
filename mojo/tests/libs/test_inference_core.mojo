"""test_inference_core.mojo — known-value tests for the inference substrate.

Hand-written. Every expected value below is either a CLOSED FORM stated in the comment beside
the assertion or a value produced by an independent frozen kernel, because agreement between
two independent computations is evidence and a single plausible number is not.

The four kinds of assertion that do the real work:

1. *Closed forms for the tail functions.* Student's t has an elementary CDF at `df = 1` (it is
   Cauchy: `1/2 + atan(t)/pi`) and an elementary QUANTILE at `df = 2`
   (`t = (2p-1) sqrt(2/(1 - (2p-1)^2))`), and `P(F_{1,6} >= 3)` is exactly `(2 - sqrt(3))/2`.
   All three are asserted against the closed form, not against a table.

2. *An exact identity between two of our own functions.* `P(F_{1,d} >= t^2)` and
   `P(|T_d| >= |t|)` are the same number by construction of the F distribution, and they are
   computed here through two different argument orders of the incomplete beta. They must agree
   to the series' own accuracy.

3. *The (fixed) frozen defect, now a live cross-check.* `stat_tests._t_cdf(2.0, 6.0)` used to
   return `1.0114861686851442` — a value greater than 1, not a probability — which is the
   reason `inference_beta_inc` was built. As of this session `stat_tests._regularized_incomplete_beta`
   is fixed (see `inference.core`'s module docstring for the history and the measured
   inter-implementation gap, largest observed `5.8e-11`), so this section now asserts the
   CORRECTED reality: `_t_cdf(2.0, 6.0)` is a valid probability close to the closed-form
   truth, and `t_cdf_agreement` reports `agree = True`. A future regression back toward the
   old defect (a CDF outside `[0, 1]`, or a gap back at the `1e-2` scale) still fails this
   assertion loudly.

4. *Refusals.* A tail function outside its domain, a tolerance built from a NaN, a wrapping
   product, and four separate reasons `wls_solve_flat` has no solution. Each refusal is
   asserted by STATUS and by the absence of numbers, not by a value.

The inverse-round-trip test is the strongest single check on the quantile: for a spread of
`(p, df)` pairs, `inference_t_cdf(inference_t_quantile(p, df), df)` must return `p` back to
1e-9. That composes the two functions in opposite directions, so an error in either one shows
up unless both are wrong in exactly compensating ways.
"""
from std.math import abs as fabs, atan, exp, sqrt

from inference.core import (
    INF_DBL_EPSILON,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_NON_FINITE,
    INF_ERR_NOT_SYMMETRIC,
    INF_ERR_RANK_DEFICIENT,
    INF_ERR_SHAPE,
    INF_ERR_TOO_FEW,
    INF_OK,
    INF_TOL_UNDEFINED,
    INF_ULP_BUDGET,
    MAX_ASSUME_OBS,
    MAX_INFERENCE_OBS,
    MAX_INFERENCE_PARAMS,
    MAX_IRLS_WORK,
    MAX_RESAMPLES,
    MAX_RESAMPLE_WORK,
    MAX_SAMPLE_SIZE,
    inference_absent,
    inference_beta_inc,
    inference_ceilings,
    inference_dims_fit,
    inference_f_sf,
    inference_finite,
    inference_norm_sf_two_sided,
    inference_product3_fits,
    inference_product_fits,
    inference_scaled_tol,
    inference_scaled_tol_ulps,
    inference_status_name,
    inference_t_cdf,
    inference_t_quantile,
    inference_t_sf_two_sided,
    inference_t_tail_region,
    T_REGION_ABSENT,
    T_REGION_BETA,
    T_REGION_CENTRAL,
    T_REGION_NORMAL,
    T_TAIL_COMPLEMENT_FLOOR,
    T_TAIL_SERIES_MAX_T,
    t_cdf_agreement,
    wls_solve_flat,
)
from sparse_numerics.csr import MAX_CSR_DIM
from special_functions import erfc
from stat_tests import _t_cdf

comptime PI: Float64 = 3.141592653589793


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    """Absolute closeness. Used only where the comment states the reference value."""
    if not inference_finite(a) or not inference_finite(b):
        return False
    return fabs(a - b) <= tol


def main():
    var passed: Int = 0
    var failed: Int = 0

    # ── 1. the frozen defect, FIXED, now a live cross-check ─────────────────────
    # These are the values this toolchain actually produces post-fix. `_t_cdf(2,6)` is a
    # valid probability (not 1.0114861686851442, the pre-fix value) and close to the
    # closed-form truth 0.9537868442341706 — both implementations converge to that truth
    # independently, to within their own continued-fraction truncation.
    var frozen_2_6 = _t_cdf(2.0, 6.0)
    if (
        frozen_2_6 > 0.0
        and frozen_2_6 < 1.0
        and _close(frozen_2_6, 0.9537868442341706, 1.0e-9)
        and _close(inference_t_cdf(2.0, 6.0), 0.9537868442341706, 1.0e-9)
        and _close(inference_t_cdf(1.0, 5.0), 0.8183912661754367, 1.0e-9)
    ):
        passed += 1
        print("  ✅ frozen and corrected _t_cdf(2,6) both agree with the closed-form truth")
    else:
        failed += 1
        print("  ❌ frozen/corrected t CDF changed:", frozen_2_6, inference_t_cdf(2.0, 6.0))

    var agreement = t_cdf_agreement(2.0, 6.0)
    # t = 0 is the one place the two cannot disagree: x = df/(df+0) = 1, and both
    # implementations short-circuit I_1(a,b) = 1 before the continued fraction runs.
    var agree_at_zero = t_cdf_agreement(0.0, 5.0)
    if (
        agreement.status == INF_OK
        and agreement.frozen_is_probability
        and agreement.agree
        and agreement.abs_gap < 1.0e-9
        and agree_at_zero.status == INF_OK
        and agree_at_zero.frozen_is_probability
        and agree_at_zero.agree
        and agree_at_zero.corrected_cdf == 0.5
    ):
        passed += 1
        print("  ✅ the two independent implementations agree, and exactly so at t=0")
    else:
        failed += 1
        print("  ❌ agreement report wrong:", agreement.abs_gap, agreement.frozen_is_probability)

    # ── 2. closed forms ────────────────────────────────────────────────────────
    # df = 1 is Cauchy: P(T <= t) = 1/2 + atan(t)/pi, exactly.
    var t1 = 6.313751514675043
    if (
        _close(inference_t_cdf(t1, 1.0), 0.5 + atan(t1) / PI, 1.0e-9)
        and _close(inference_t_cdf(-t1, 1.0), 0.5 + atan(-t1) / PI, 1.0e-9)
        and _close(inference_t_cdf(0.3, 1.0), 0.5 + atan(0.3) / PI, 1.0e-9)
    ):
        passed += 1
        print("  ✅ the df=1 t CDF matches the Cauchy closed form on both tails")
    else:
        failed += 1
        print("  ❌ Cauchy closed form:", inference_t_cdf(t1, 1.0), 0.5 + atan(t1) / PI)

    # df = 2 inverts in closed form: t = (2p-1) sqrt(2 / (1 - (2p-1)^2)).
    var u = 2.0 * 0.975 - 1.0
    var t2_closed = u * sqrt(2.0 / (1.0 - u * u))
    # df = 1 inverts to the Cauchy quantile: t = tan(pi (p - 1/2)); at p = 0.95 that is
    # 6.313751514675043, which is also the classical 5% one-tail critical value.
    if (
        _close(inference_t_quantile(0.975, 2.0), t2_closed, 1.0e-8)
        and _close(t2_closed, 4.302652729749463, 1.0e-12)
        and _close(inference_t_quantile(0.95, 1.0), 6.313751514675043, 1.0e-8)
        and _close(inference_t_quantile(0.975, 10.0), 2.228138851986065, 1.0e-8)
        and inference_t_quantile(0.5, 7.0) == 0.0
    ):
        passed += 1
        print("  ✅ the t quantile matches two closed forms and is exactly 0 at p=0.5")
    else:
        failed += 1
        print("  ❌ t quantile:", inference_t_quantile(0.975, 2.0), t2_closed)

    # P(F_{1,6} >= 3) = (2 - sqrt(3))/2, an elementary closed form.
    var f_closed = (2.0 - sqrt(3.0)) / 2.0
    if (
        _close(inference_f_sf(3.0, 1.0, 6.0), f_closed, 1.0e-8)
        and _close(f_closed, 0.1339745962155614, 1.0e-15)
        and inference_f_sf(0.0, 2.0, 3.0) == 1.0
        and _close(inference_f_sf(1.0, 1.0, 1.0), 0.5, 1.0e-9)
    ):
        passed += 1
        print("  ✅ P(F_1,6 >= 3) is (2-sqrt3)/2 and P(F_1,1 >= 1) is 1/2")
    else:
        failed += 1
        print("  ❌ F tail:", inference_f_sf(3.0, 1.0, 6.0), f_closed)

    # ── 3. an exact identity between two of our own functions ──────────────────
    # P(F_{1,d} >= t^2) == P(|T_d| >= |t|) by construction. Computed through two different
    # argument orders of the incomplete beta, so agreement is not tautological.
    var identity_ok = True
    var dfs = _floats(1.0, 2.0, 4.0, 6.0, 20.0, 100.0)
    var ts = _floats(0.25, 1.0, 1.7320508075688772, 2.5, 4.0)
    for i in range(len(dfs)):
        for j in range(len(ts)):
            var a = inference_f_sf(ts[j] * ts[j], 1.0, dfs[i])
            var b = inference_t_sf_two_sided(ts[j], dfs[i])
            if not _close(a, b, 1.0e-10):
                identity_ok = False
    if (
        identity_ok
        and inference_t_sf_two_sided(0.0, 5.0) == 1.0
        and _close(inference_t_sf_two_sided(3.6742346141747673, 4.0), 0.02131164112875572, 1.0e-9)
    ):
        passed += 1
        print("  ✅ P(F_1,d >= t^2) == P(|T_d| >= |t|) over 30 pairs, and the two-tail mass at 0 is 1")
    else:
        failed += 1
        print("  ❌ F/t identity broken")

    # ── 3b. the SAME identity where the incomplete beta has no digits left ─────
    # The 30 pairs above all sit above `T_TAIL_COMPLEMENT_FLOOR`, so they never exercised
    # the region `inference_t_tail_region` exists for. There the identity was BROKEN in one
    # direction only: `inference_t_sf_two_sided` was taught the central series, while
    # `inference_f_sf` still formed `df2/(df2 + df1 f)` and saturated, so the two halves of
    # one documented equality disagreed by 0.68 (1.0 against 0.31731050786291404). `df1 = 1`
    # now delegates to the t, and these assert BIT-EQUALITY rather than closeness, because
    # an exact mathematical identity routed through one implementation has no reason to
    # differ in a last bit. None of these `t` is a power of two, so `sqrt(t*t)` is not
    # trivially recovering the input.
    var big_identity_ok = True
    var big_ts = _floats(0.3, 0.7, 1.3, 2.9)
    var big_dfs = _floats(1.0e9, 1.0e16)
    for i in range(len(big_dfs)):
        for j in range(len(big_ts)):
            var bt = big_ts[j]
            if (
                inference_f_sf(bt * bt, 1.0, big_dfs[i])
                != inference_t_sf_two_sided(bt, big_dfs[i])
            ):
                big_identity_ok = False
    # Two elementary chi-square oracles for the `df2 -> inf` limit `P(F_{k,inf} >= f) =
    # P(chi2_k >= k f)`. `P(chi2_4 >= x) = e^(-x/2)(1 + x/2)`, so at x = 2 it is exactly
    # 2/e. `P(chi2_3 >= x) = erfc(sqrt(x/2)) + sqrt(2x/pi) e^(-x/2)`, from the frozen
    # `special_functions.erfc` — an independent kernel, and one whose own A&S error is
    # ~1e-7, which is why the tolerance against it below is 1e-6 and not tighter.
    var chi2_4_at_2 = 2.0 * exp(-1.0)
    var chi3_x = 3.0e-3
    var chi2_3_at_3e_3 = (
        erfc(sqrt(0.5 * chi3_x)) + sqrt(2.0 * chi3_x / PI) * exp(-0.5 * chi3_x)
    )
    if (
        big_identity_ok
        # The two values the collapse used to produce, now the truth. 0.3173105078629141
        # is the normal two-sided tail at 1.0, which `df2 = 1e16` IS to 2e-10.
        and _close(inference_f_sf(1.0, 1.0, 1.0e16), 0.3173105078629141, 1.0e-15)
        and inference_f_sf(1.0, 1.0, 1.0e16) < 1.0
        and _close(inference_f_sf(0.0625, 1.0, 1.0e15), 0.8025873486341526, 1.0e-15)
        and inference_f_sf(0.0625, 1.0, 1.0e15) < 1.0
        # `df1 > 1` below the floor is a RECORDED GAP, not a fixed region: it needs an
        # accurate upper incomplete gamma this tree does not have. These two lines PIN it
        # rather than endorse it — the first is the answer being right while the complement
        # still has digits, the second is the measured wrong value asserted LITERALLY, the
        # same way this suite pins `stat_tests._t_cdf(2.0, 6.0) = 1.0114861686851442`. If a
        # future change makes the corner right, THIS LINE MUST FAIL, loudly, rather than let
        # the gap quietly stop being a gap.
        and _close(inference_f_sf(0.5, 4.0, 1.0e6), chi2_4_at_2, 1.0e-9)
        and inference_f_sf(0.5, 4.0, 1.0e16) == 0.9999240029662446
        and fabs(inference_f_sf(0.5, 4.0, 1.0e16) - chi2_4_at_2) > 0.25
        # ...and the gap is NOT blanket-refused, because below the floor with `df1 f` small
        # the truth is pinned near 1 and the beta path returns it. This is the only corner
        # `assume.levene_flat` can reach (`MAX_ASSUME_OBS` is 4096), so refusing here would
        # have discarded a measured-correct p-value.
        and _close(inference_f_sf(1.0e-3, 3.0, 1.0e6), chi2_3_at_3e_3, 1.0e-6)
        # The delegation is gated on df1 being EXACTLY 1.0, because that is what the
        # identity requires; a df1 one part in 1e7 away is a different distribution and
        # takes the beta path, saturation and all.
        and _close(inference_f_sf(1.0, 1.0000001, 1.0e16), 1.0, 1.0e-7)
        and inference_f_sf(1.0, 1.0000001, 1.0e16) != inference_f_sf(1.0, 1.0, 1.0e16)
        # An overflowing `df1 * f` must not be read as "the complement is below the floor":
        # it is the opposite, an F so large the complement is 1 to every digit, and the
        # beta at x = 0 is exactly 0.
        and inference_f_sf(1.0e308, 1.0, 1.0e16) == 0.0
        and inference_f_sf(1.0e308, 4.0, 1.0e16) == 0.0
    ):
        passed += 1
        print("  ✅ the F tail keeps the t identity BIT-EQUAL below the floor; df1>1 gap pinned")
    else:
        failed += 1
        print(
            "  ❌ large-df F tail:",
            big_identity_ok,
            inference_f_sf(1.0, 1.0, 1.0e16),
            inference_f_sf(0.5, 4.0, 1.0e16),
            inference_f_sf(1.0e-3, 3.0, 1.0e6),
        )

    # ── 4. the quantile round-trip, in both directions ─────────────────────────
    var roundtrip_ok = True
    var ps = _floats(0.001, 0.025, 0.1, 0.4, 0.6, 0.9, 0.975, 0.999)
    for i in range(len(dfs)):
        for j in range(len(ps)):
            var q = inference_t_quantile(ps[j], dfs[i])
            if not inference_finite(q):
                roundtrip_ok = False
            elif not _close(inference_t_cdf(q, dfs[i]), ps[j], 1.0e-9):
                roundtrip_ok = False
    if roundtrip_ok:
        passed += 1
        print("  ✅ t_cdf(t_quantile(p, df), df) returns p over 48 (p, df) pairs")
    else:
        failed += 1
        print("  ❌ quantile round-trip failed")

    # ── 5. absence, never a plausible number ───────────────────────────────────
    # A quantile at p=0 or p=1 is -inf/+inf, which is not an answer. `math_ext.norm_ppf`
    # returns the FINITE sentinel +-1e300 there; this refuses instead.
    if (
        not inference_finite(inference_t_quantile(0.0, 5.0))
        and not inference_finite(inference_t_quantile(1.0, 5.0))
        and not inference_finite(inference_t_quantile(0.5, 0.0))
        and not inference_finite(inference_t_quantile(0.5, inference_absent()))
        and not inference_finite(inference_beta_inc(0.5, 0.0, 1.0))
        and not inference_finite(inference_beta_inc(0.5, 1.0, -1.0))
        and not inference_finite(inference_t_cdf(1.0, -1.0))
        and not inference_finite(inference_f_sf(1.0, 0.0, 1.0))
        and inference_beta_inc(0.0, 2.0, 3.0) == 0.0
        and inference_beta_inc(1.0, 2.0, 3.0) == 1.0
    ):
        passed += 1
        print("  ✅ every out-of-domain tail is ABSENT, and I_0 / I_1 are exactly 0 and 1")
    else:
        failed += 1
        print("  ❌ a domain violation returned a number")

    # ── 6. the tolerance builder (rule 4b) ─────────────────────────────────────
    # 256 ulps at magnitude 1 is 5.684341886080802e-14, and nothing about the tolerance may
    # come from a caller-supplied relative slop.
    var t_one = inference_scaled_tol(1.0, 0.0)
    if (
        t_one == INF_ULP_BUDGET * INF_DBL_EPSILON
        and _close(t_one, 5.684341886080802e-14, 1.0e-28)
        and inference_scaled_tol(0.0, 0.0) == 0.0
        and inference_scaled_tol(-4.0, 0.0) == inference_scaled_tol(4.0, 0.0)
        and inference_scaled_tol(1.0, 1.0e-9) > 1.0e-9
        # A non-finite magnitude yields a tolerance every comparison FAILS against, which is
        # the opposite of rule 4d's nan trap (there, every comparison passed).
        and inference_scaled_tol(inference_absent(), 0.0) == INF_TOL_UNDEFINED
        and inference_scaled_tol(1.0, inference_absent()) == INF_TOL_UNDEFINED
        and inference_scaled_tol(1.0, -1.0) == INF_TOL_UNDEFINED
        and 1.0e-300 > INF_TOL_UNDEFINED
        and inference_scaled_tol_ulps(1.0, 0.0, 0.0) == t_one
        and inference_scaled_tol_ulps(1.0, 0.0, 256.0) == 2.0 * t_one
        and inference_scaled_tol_ulps(1.0, 0.0, -1.0) == INF_TOL_UNDEFINED
    ):
        passed += 1
        print("  ✅ the tolerance scales with the judged quantity alone, and refuses safely")
    else:
        failed += 1
        print("  ❌ tolerance builder wrong:", t_one)

    # ── 7. wrapping-safe budgets ───────────────────────────────────────────────
    # 3 * 6148914691236517206 == 2 as a wrapping multiply, which is why the product is never
    # formed. `inference_dims_fit` inherits the same division from the frozen csr kernel.
    if (
        not inference_product_fits(3, 6148914691236517206, 100)
        and inference_product_fits(0, 6148914691236517206, 0)
        and inference_product_fits(10, 10, 100)
        and not inference_product_fits(10, 11, 100)
        and inference_product3_fits(10, 10, 10, 1000)
        and not inference_product3_fits(10, 10, 11, 1000)
        and not inference_product3_fits(3, 6148914691236517206, 2, 100)
        and inference_dims_fit(2, 3, 6)
        and not inference_dims_fit(3, 6148914691236517206, 2)
        and inference_dims_fit(4, 0, 0)
        and not inference_dims_fit(MAX_INFERENCE_OBS + 1, 1, MAX_INFERENCE_OBS + 1)
        and not inference_dims_fit(1, MAX_INFERENCE_PARAMS + 1, MAX_INFERENCE_PARAMS + 1)
    ):
        passed += 1
        print("  ✅ every budget is decided by division, and the wrapping product is caught")
    else:
        failed += 1
        print("  ❌ a budget formed a wrapping product")

    # ── 8. ceilings scaled below the shared outer limit (rule 1c) ──────────────
    var ceilings = inference_ceilings()
    if (
        len(ceilings) == 9
        and ceilings[0] == MAX_INFERENCE_OBS
        and ceilings[1] == MAX_INFERENCE_PARAMS
        and ceilings[2] == MAX_RESAMPLES
        and ceilings[3] == MAX_ASSUME_OBS
        and ceilings[5] == MAX_SAMPLE_SIZE
        and ceilings[6] == MAX_IRLS_WORK
        and ceilings[7] == MAX_RESAMPLE_WORK
        and ceilings[8] == MAX_CSR_DIM
        and MAX_CSR_DIM == 67108864
        # Every per-object dimension is strictly below the shared 2^26 ceiling, which is
        # justified for ONE array; an IRLS pass allocates eight per observation.
        and MAX_INFERENCE_OBS < MAX_CSR_DIM
        and MAX_INFERENCE_PARAMS < MAX_CSR_DIM
        and MAX_RESAMPLES < MAX_CSR_DIM
        and MAX_ASSUME_OBS < MAX_INFERENCE_OBS
    ):
        passed += 1
        print("  ✅ the ceilings are reported and every one is scaled below MAX_CSR_DIM")
    else:
        failed += 1
        print("  ❌ ceiling report wrong:", len(ceilings))

    # ── 9. wls_solve_flat: one known solve and four distinct refusals ──────────
    # 4x + y = 1, x + 3y = 2  ->  x = 1/11, y = 7/11 (determinant 11, positive definite).
    var a_pd = _floats(4.0, 1.0, 1.0, 3.0)
    var b_pd = _floats(1.0, 2.0)
    var solved = wls_solve_flat(a_pd, b_pd, 2)
    var shape_bad = wls_solve_flat(_floats(1.0, 2.0, 3.0), b_pd, 2)
    var asym = wls_solve_flat(_floats(1.0, 2.0, 3.0, 1.0), b_pd, 2)
    # Symmetric but INDEFINITE: eigenvalues 3 and -1. Cholesky fails, so there is no
    # weighted-least-squares solution and none is returned.
    var indefinite = wls_solve_flat(_floats(1.0, 2.0, 2.0, 1.0), b_pd, 2)
    # Singular: rank 1. `linalg.mat_solve` would return an all-zeros vector here and
    # `linear_models._solve_linear_system` would skip the pivot and leave y at 0.0.
    var singular = wls_solve_flat(_floats(1.0, 1.0, 1.0, 1.0), b_pd, 2)
    var nonfinite = wls_solve_flat(_floats(1.0, 0.0, 0.0, inference_absent()), b_pd, 2)
    if (
        solved.status == INF_OK
        and solved.positive_definite
        and solved.verified
        and _close(solved.beta[0], 1.0 / 11.0, 1.0e-14)
        and _close(solved.beta[1], 7.0 / 11.0, 1.0e-14)
        and solved.max_row_residual <= inference_scaled_tol(2.0, 0.0)
        and shape_bad.status == INF_ERR_SHAPE
        and len(shape_bad.beta) == 0
        and asym.status == INF_ERR_NOT_SYMMETRIC
        and len(asym.beta) == 0
        and indefinite.status == INF_ERR_RANK_DEFICIENT
        and len(indefinite.beta) == 0
        and singular.status == INF_ERR_RANK_DEFICIENT
        and len(singular.beta) == 0
        and nonfinite.status == INF_ERR_NON_FINITE
        and wls_solve_flat(a_pd, b_pd, 0).status == INF_ERR_TOO_FEW
        and wls_solve_flat(a_pd, b_pd, MAX_INFERENCE_PARAMS + 1).status
        == INF_ERR_DIMENSION_TOO_LARGE
        and solved.max_row_residual >= 0.0
    ):
        passed += 1
        print("  ✅ the known solve is exact and five refusals each carry NO beta")
    else:
        failed += 1
        print("  ❌ wls_solve_flat:", solved.status, len(solved.beta), indefinite.status)

    # ── 10. the A-Z harness shapes, which must all refuse rather than abort ────
    # The generated suite calls every contract function with a FIVE-element list and 5 for
    # every Int, so `wls_solve_flat(_lf5, _lf5, 5)` declares a 5x5 matrix backed by 5 cells.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    if (
        wls_solve_flat(lf5, lf5, 5).status == INF_ERR_SHAPE
        and len(wls_solve_flat(lf5, lf5, 5).beta) == 0
    ):
        passed += 1
        print("  ✅ the harness's 5x5-from-5-cells call is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the harness shape was not refused")

    # ── 11. the normal two-sided tail, from the frozen CDF ────────────────────
    # math_ext.norm_cdf is an Abramowitz-Stegun erf, measured 6.9e-8 at z = 1.9599639845, so
    # the two-sided tail at the 5% critical value is 0.05 to about 1.4e-7 and no better. The
    # tolerance here states that accuracy rather than pretending to more — and the same
    # approximation makes the frozen `erf(0)` about 2.05e-9 rather than exactly 0, so the
    # two-sided tail at z = 0 is 0.999999998 and not 1.0. Both are the frozen kernel's
    # accuracy, stated, and neither is corrected here: a Wald p-value does not need more.
    if (
        _close(inference_norm_sf_two_sided(1.959963984540054), 0.05, 2.0e-7)
        and _close(inference_norm_sf_two_sided(0.0), 1.0, 1.0e-8)
        and inference_norm_sf_two_sided(-1.959963984540054)
        == inference_norm_sf_two_sided(1.959963984540054)
        and not inference_finite(inference_norm_sf_two_sided(inference_absent()))
        and inference_norm_sf_two_sided(50.0) >= 0.0
    ):
        passed += 1
        print("  ✅ the normal two-sided tail is symmetric, 0.05 at 1.96, and refuses a NaN")
    else:
        failed += 1
        print("  ❌ normal tail:", inference_norm_sf_two_sided(1.959963984540054))

    # ── 12. the saturated region: a p-value of 1.0 where the truth is 0.32 ─────
    # `x = df/(df + t*t)` rounds to exactly 1.0 once `t*t` is below half an ulp of `df`, and
    # `inference_beta_inc(1.0, a, b)` returns exactly 1.0, so BEFORE the region split every
    # one of these was the same wrong number. Measured on this toolchain with the
    # incomplete-beta path forced everywhere:
    #
    #     inference_t_sf_two_sided(1.0, 1e16)   1.0   (a silent non-rejection)
    #     inference_t_cdf(1.0, 1e16)            0.5
    #     inference_t_sf_two_sided(0.25, 1e15)  1.0
    #     inference_t_cdf(0.25, 1e15)           0.5
    #
    # The references below are the NORMAL values, which is legitimate here and only here: at
    # `df = 1e15` the Edgeworth term `phi(t)(t^3+t)/(4 df)` is 2e-16, i.e. below the last bit
    # of the answer, so the t and the normal are the same number to double precision.
    # `erfc(1/sqrt(2)) = 0.31731050786291415` and `0.5 erfc(-1/sqrt(2)) = 0.8413447460685429`.
    if (
        _close(inference_t_sf_two_sided(1.0, 1.0e16), 0.31731050786291415, 1.0e-12)
        and _close(inference_t_cdf(1.0, 1.0e16), 0.8413447460685429, 1.0e-12)
        and _close(inference_t_sf_two_sided(0.25, 1.0e15), 0.8025873486341526, 1.0e-12)
        and _close(inference_t_cdf(0.25, 1.0e15), 0.5987063256829237, 1.0e-12)
        # Not merely close to the truth: no longer the saturated value at all, and still a
        # probability. A tail mass of exactly 1.0 for a nonzero `t` cannot be right for a
        # continuous distribution, so the strict inequality is the assertion that bites.
        and inference_t_sf_two_sided(1.0, 1.0e16) < 1.0
        and inference_t_cdf(1.0, 1.0e16) > 0.5
        and inference_t_sf_two_sided(0.25, 1.0e15) < 1.0
        # Monotone in |t| across the whole saturated band, which a flat 1.0 is not.
        and inference_t_sf_two_sided(0.5, 1.0e16)
        < inference_t_sf_two_sided(0.25, 1.0e16)
        and inference_t_sf_two_sided(0.25, 1.0e16)
        < inference_t_sf_two_sided(0.125, 1.0e16)
    ):
        passed += 1
        print("  ✅ the saturated large-df band returns the truth, not a flat p-value of 1.0")
    else:
        failed += 1
        print(
            "  ❌ large-df t tail:",
            inference_t_sf_two_sided(1.0, 1.0e16),
            inference_t_cdf(1.0, 1.0e16),
        )

    # ── 13. the central region against elementary closed forms ────────────────
    # Every point here has `1 - x` below 1e-8, so the incomplete-beta path had lost at least
    # half of the only digits that carry the answer; at `t = 1e-9, df = 1` it had lost all of
    # them and returned exactly 0.5 for a CDF whose offset from 0.5 is 3.18e-10.
    var c_tiny = 1.0e-9
    var c_small = 3.0e-8
    var d2_t = 1.0e-6
    var d3_t = 1.0e-4
    var d3_u = d3_t / sqrt(3.0)
    # df = 3 in closed form: F(t) = 1/2 + (1/pi)[ u/(1 + t^2/3) + atan(u) ], u = t/sqrt(3).
    var d3_closed = 0.5 + (d3_u / (1.0 + d3_t * d3_t / 3.0) + atan(d3_u)) / PI
    if (
        # Cauchy, exact: 1/2 + atan(t)/pi. Asserted to 1e-18, far below the 3.18e-10 offset
        # from 0.5 that the beta path threw away entirely.
        _close(inference_t_cdf(c_tiny, 1.0), 0.5 + atan(c_tiny) / PI, 1.0e-18)
        and _close(inference_t_cdf(c_small, 1.0), 0.5 + atan(c_small) / PI, 1.0e-18)
        and _close(inference_t_cdf(-c_tiny, 1.0), 0.5 + atan(-c_tiny) / PI, 1.0e-18)
        # df = 2 inverts elementarily: F(t) = (1 + t/sqrt(2 + t^2))/2.
        and _close(
            inference_t_cdf(d2_t, 2.0), 0.5 * (1.0 + d2_t / sqrt(2.0 + d2_t * d2_t)), 1.0e-18
        )
        # df = 3 is where the frozen `special_functions.log_gamma` shows through: the density
        # at zero carries ~2.4e-10 relative error, which on an offset of 3.68e-5 is 9e-15
        # absolute. Stated, not hidden — and still six orders below the defect being fixed.
        and _close(inference_t_cdf(d3_t, 3.0), d3_closed, 1.0e-13)
        # The tail and the CDF are the same computation seen twice, so they must close.
        and _close(
            inference_t_sf_two_sided(c_small, 1.0),
            2.0 * (1.0 - inference_t_cdf(c_small, 1.0)),
            1.0e-17,
        )
        # t = 0 is the one point where the mass is exactly 1 and the CDF exactly 1/2, and the
        # series must not perturb it: `_close` would accept 1e-18 of drift, `==` does not.
        and inference_t_cdf(0.0, 5.0) == 0.5
        and inference_t_sf_two_sided(0.0, 5.0) == 1.0
        # A t quantile just above the median. The pre-fix CDF was exactly 0.5 across this
        # whole neighbourhood, so bisection could only return the far edge of the flat band:
        # the true quantile is 2.67e-9 and the flat band ran out past 1e-4.
        and _close(inference_t_quantile(0.5 + 1.0e-9, 4.0), 2.666666442674494e-09, 1.0e-16)
        and _close(
            inference_t_cdf(inference_t_quantile(0.5 + 1.0e-9, 4.0), 4.0),
            0.5 + 1.0e-9,
            1.0e-15,
        )
    ):
        passed += 1
        print("  ✅ the central region matches the df=1/2/3 closed forms and keeps t=0 exact")
    else:
        failed += 1
        print(
            "  ❌ central region:",
            inference_t_cdf(c_tiny, 1.0),
            0.5 + atan(c_tiny) / PI,
            inference_t_quantile(0.5 + 1.0e-9, 4.0),
        )

    # ── 14. the region geometry is a value, not a hidden branch ────────────────
    # The three regions are exported so a caller can see which formula produced a number,
    # and so this suite can assert the handoffs rather than infer them.
    if (
        inference_t_tail_region(2.0, 6.0) == T_REGION_BETA
        and inference_t_tail_region(1.0, 1.0e16) == T_REGION_CENTRAL
        and inference_t_tail_region(0.0, 5.0) == T_REGION_CENTRAL
        and inference_t_tail_region(6.0, 1.0e16) == T_REGION_NORMAL
        and inference_t_tail_region(1.0, -1.0) == T_REGION_ABSENT
        and inference_t_tail_region(inference_absent(), 5.0) == T_REGION_ABSENT
        # Past the series cap the complement floor forces df > 8.99e8, so the answer IS the
        # package's normal tail — bit-identical, not merely close, which is what makes a t
        # test on 1e16 df and a Wald z test on the same statistic agree.
        and inference_t_sf_two_sided(6.0, 1.0e16) == inference_norm_sf_two_sided(6.0)
        and T_TAIL_COMPLEMENT_FLOOR == 1.0e-8
        and T_TAIL_SERIES_MAX_T == 3.0
        # The floor is where the complement still has half its digits: 2.0 at df=6 keeps
        # 1 - x = 0.4, eight orders above the floor, so the frozen-defect assertions in
        # section 1 are untouched by the split. The incomplete-beta path's own accuracy shows
        # here: it returns 0.9537868442803318 against a true 0.9537868442341706 (4.6e-11),
        # which is why section 1 judges it at 1e-9 and why this is not an `==`.
        and _close(inference_t_cdf(2.0, 6.0), 0.9537868442341706, 1.0e-9)
        and inference_t_cdf(2.0, 6.0) != 0.9537868442341706
    ):
        passed += 1
        print("  ✅ the three tail regions are exported, and the |t|>3 handoff IS the normal")
    else:
        failed += 1
        print(
            "  ❌ region geometry:",
            inference_t_tail_region(1.0, 1.0e16),
            inference_t_tail_region(6.0, 1.0e16),
        )

    # ── 15. one status vocabulary, 320-339, with names ────────────────────────
    if (
        inference_status_name(INF_OK) == "ok"
        and INF_OK == 320
        and inference_status_name(INF_ERR_NOT_SYMMETRIC)
        == "normal_equations_matrix_is_not_symmetric"
        and INF_ERR_NOT_SYMMETRIC == 338
        and inference_status_name(319) == "unknown"
        and inference_status_name(340) == "unknown"
        and inference_status_name(81) == "unknown"
        and inference_finite(1.0)
        and not inference_finite(1.0 / 0.0)
        and not inference_finite(inference_absent())
    ):
        passed += 1
        print("  ✅ the package owns 320-339 exactly, names them, and claims nothing outside")
    else:
        failed += 1
        print("  ❌ status vocabulary wrong:", inference_status_name(INF_OK))

    print("  [inference.core] Passed:", passed, "Failed:", failed)
