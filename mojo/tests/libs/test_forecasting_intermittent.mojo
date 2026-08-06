"""test_forecasting_intermittent.mojo — known-value tests for the Croston family.

Hand-written. The worked example is small enough to compute entirely on paper and every step
of it is asserted.

    y = [0, 0, 5, 0, 0, 0, 10, 0, 3]
      demand sizes     = [5, 10, 3]        (positions 2, 6, 8)
      intervals        = [3, 4, 2]         (from position -1, so the first is 2-(-1) = 3)

At alpha = 1 the SES level is the last observation, so z = 3, p = 2 and the classic rate is
exactly 1.5. At alpha = 0.5:
      z: 5 -> 0.5*10+0.5*5   = 7.5  -> 0.5*3+0.5*7.5   = 5.25
      p: 3 -> 0.5*4 +0.5*3   = 3.5  -> 0.5*2+0.5*3.5   = 2.75
so the classic rate is 5.25/2.75 = 1.909090909..., the SBA factor is 1 - 0.5/2 = 0.75 and the
SBA rate is 1.431818181.... All three are asserted, together with `demand_level` and
`interval_level` themselves, so a wrong rate cannot hide behind a right ratio.

Two frozen kernels are called DIRECTLY to prove nothing was re-implemented: both smoothings
must equal `series.exponential_forecast` on the derived series, and the classification's moments
must equal `stats.compute_mean` and `stats.compute_variance` (the SAMPLE variance) on the demand
sizes.

The Rule-4 cases, which is what this module exists for:

  * an all-zero series has NO demand rate — there are no intervals to smooth, so `z/p` does not
    exist. FC_ERR_NO_DEMAND with an EMPTY path. A forecast of 0.0 would be indistinguishable
    from a rate that was estimated and came out zero, and a reorder policy branches on exactly
    that difference. The census (`n_zero = 6`, `zero_fraction = 1.0`) still comes back, because
    it is the whole explanation.
  * SBJ at `alpha_interval = 1` has a bias factor of EXACTLY ZERO, which would turn every
    forecast into 0.0 under a success status. Refused.
  * one demand observation gives an ADI and no CV — a sample variance of one point is undefined,
    not zero — so `has_cv2` is False and the class is FC_DEMAND_UNCLASSIFIED, which is a real
    category and not a fourth quadrant reached by treating a missing statistic as 0.0.
"""
from std.math import abs as fabs

from series import exponential_forecast
from stats import compute_mean, compute_variance

from forecasting.contract import (
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HORIZON,
    FC_ERR_METHOD,
    FC_ERR_NEGATIVE_VALUES,
    FC_ERR_NO_DEMAND,
    FC_ERR_PARAM_RANGE,
    FC_METHOD_CROSTON,
    FC_OK,
)
from forecasting.intermittent import (
    FC_ADI_CUT,
    FC_CROSTON_CLASSIC,
    FC_CROSTON_SBA,
    FC_CROSTON_SBJ,
    FC_CV2_CUT,
    FC_DEMAND_ERRATIC,
    FC_DEMAND_INTERMITTENT,
    FC_DEMAND_LUMPY,
    FC_DEMAND_SMOOTH,
    FC_DEMAND_UNCLASSIFIED,
    IntermittentForecast,
    croston_forecast,
    croston_variant_name,
    demand_class_name,
    demand_classify,
)


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _refused(f: IntermittentForecast) -> Bool:
    """A refusal carries no path and no levels — never a rate of 0.0."""
    return (
        f.status != FC_OK
        and not f.has_forecast
        and len(f.forecast) == 0
        and not f.has_levels
        and f.demand_level == 0.0
        and f.interval_level == 0.0
    )


def main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.intermittent] known-value suite")

    var y = _floats(0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 10.0, 0.0, 3.0)
    var sizes = _floats(5.0, 10.0, 3.0)
    var intervals = _floats(3.0, 4.0, 2.0)

    # ══ alpha = 1: the levels are the last observations, the rate is exactly 1.5 ════
    var classic1 = croston_forecast(y, 1.0, 1.0, FC_CROSTON_CLASSIC, 3)
    if (
        classic1.status == FC_OK
        and classic1.has_forecast
        and len(classic1.forecast) == 3
        and classic1.forecast[0] == 1.5
        and classic1.forecast[2] == 1.5
        and classic1.demand_level == 3.0
        and classic1.interval_level == 2.0
        and classic1.bias_factor == 1.0
        and classic1.has_levels
        and classic1.n_periods == 9
        and classic1.n_nonzero == 3
        and classic1.n_zero == 6
        and classic1.zero_fraction == 6.0 / 9.0
        and classic1.method_id == FC_METHOD_CROSTON
    ):
        passed += 1
        print("  ✅ alpha=1 gives z=3, p=2, rate exactly 1.5, and the full 9/3/6 census")
    else:
        failed += 1
        print("  ❌ classic alpha=1 wrong:", classic1.forecast[0], classic1.demand_level,
              classic1.interval_level)

    # ══ alpha = 0.5: 5.25 / 2.75, hand-computed above ══════════════════════════════
    var classic5 = croston_forecast(y, 0.5, 0.5, FC_CROSTON_CLASSIC, 2)
    if (
        classic5.status == FC_OK
        and classic5.demand_level == 5.25
        and classic5.interval_level == 2.75
        and classic5.forecast[0] == 5.25 / 2.75
    ):
        passed += 1
        print("  ✅ alpha=0.5 gives z=5.25, p=2.75, rate 5.25/2.75 = 1.9090909...")
    else:
        failed += 1
        print("  ❌ classic alpha=0.5 wrong:", classic5.demand_level, classic5.interval_level)

    # Both levels ARE the frozen kernel applied to the derived series. Bit-equality is what
    # proves this module contains no second smoother.
    var frozen_z = exponential_forecast(sizes, 0.5, 1)
    var frozen_p = exponential_forecast(intervals, 0.5, 1)
    if (
        len(frozen_z) == 1 and len(frozen_p) == 1
        and classic5.demand_level == frozen_z[0]
        and classic5.interval_level == frozen_p[0]
    ):
        passed += 1
        print("  ✅ both levels are BIT-EQUAL to the frozen series.exponential_forecast")
    else:
        failed += 1
        print("  ❌ the levels are not the frozen kernel")

    # ══ the two bias corrections ═══════════════════════════════════════════════════
    var sba = croston_forecast(y, 0.5, 0.5, FC_CROSTON_SBA, 2)
    var sbj = croston_forecast(y, 0.5, 0.5, FC_CROSTON_SBJ, 2)
    # SBA: 1 - 0.5/2 = 0.75.   SBJ: 1 - 0.5/(2-0.5) = 1 - 1/3 = 2/3.
    # The expected values are built from `var`s, not from literal expressions: Mojo folds a
    # constant expression at higher-than-double precision, so `1.0 - 0.5/1.5` written inline is
    # the exactly-rounded 2/3 while the kernel's runtime `1.0 - alpha/(2.0-alpha)` is one ulp
    # away. Using variables makes both sides do the same double arithmetic.
    var alpha_i = 0.5
    var sba_factor = 1.0 - 0.5 * alpha_i
    var sbj_factor = 1.0 - alpha_i / (2.0 - alpha_i)
    var base_rate = classic5.demand_level / classic5.interval_level
    if (
        sba.status == FC_OK
        and sba.bias_factor == sba_factor
        and sba_factor == 0.75
        and sba.forecast[0] == sba_factor * base_rate
        and sbj.status == FC_OK
        and sbj.bias_factor == sbj_factor
        and sbj.forecast[0] == sbj_factor * base_rate
        and sba.forecast[0] < classic5.forecast[0]
        and sbj.forecast[0] < sba.forecast[0]
    ):
        passed += 1
        print("  ✅ SBA factor 0.75 and SBJ factor 2/3, both applied and both reported")
    else:
        failed += 1
        print("  ❌ bias factors wrong:", sba.bias_factor, sbj.bias_factor)

    # SBJ at alpha_interval = 1 has a factor of EXACTLY zero: every forecast would be 0.0 under
    # a success status, for a series that plainly has demand.
    var annihilated = croston_forecast(y, 0.5, 1.0, FC_CROSTON_SBJ, 2)
    if (
        annihilated.status == FC_ERR_PARAM_RANGE
        and _refused(annihilated)
        and annihilated.n_nonzero == 3
        and croston_forecast(y, 0.5, 0.5, 7, 2).status == FC_ERR_METHOD
        and _refused(croston_forecast(y, 0.5, 0.5, 7, 2))
        and croston_variant_name(FC_CROSTON_SBA) == "syntetos_boylan_approximation"
        and croston_variant_name(7) == "unknown"
    ):
        passed += 1
        print("  ✅ a zero bias factor is refused, and an unknown variant is a SEPARATE status")
    else:
        failed += 1
        print("  ❌ SBJ annihilation or variant handling wrong:", annihilated.status)

    # ══ Rule 4: no positive demand means no rate, and 0.0 is not the answer ════════
    var zeros = List[Float64]()
    for _ in range(6):
        zeros.append(0.0)
    var no_demand = croston_forecast(zeros, 0.5, 0.5, FC_CROSTON_CLASSIC, 3)
    if (
        no_demand.status == FC_ERR_NO_DEMAND
        and _refused(no_demand)
        and no_demand.n_periods == 6
        and no_demand.n_nonzero == 0
        and no_demand.n_zero == 6
        and no_demand.zero_fraction == 1.0
    ):
        passed += 1
        print("  ✅ an all-zero series has NO rate — absent, with the census as the explanation")
    else:
        failed += 1
        print("  ❌ all-zero handling wrong:", no_demand.status, no_demand.zero_fraction)

    if (
        croston_forecast(_floats(1.0, -1.0, 2.0), 0.5, 0.5, FC_CROSTON_CLASSIC, 2).status
            == FC_ERR_NEGATIVE_VALUES
        and croston_forecast(List[Float64](), 0.5, 0.5, FC_CROSTON_CLASSIC, 2).status
            == FC_ERR_EMPTY_SERIES
        and croston_forecast(y, 0.5, 0.5, FC_CROSTON_CLASSIC, 20).status == FC_ERR_HORIZON
        and croston_forecast(y, 0.0, 0.5, FC_CROSTON_CLASSIC, 2).status == FC_ERR_PARAM_RANGE
    ):
        passed += 1
        print("  ✅ negative demand, empty, horizon > n and alpha = 0 are all refusals")
    else:
        failed += 1
        print("  ❌ a Croston guard is missing")

    # ══ the classification, both statistics computed by the frozen kernels ═════════
    # ADI = mean(3,4,2) = 3.  sizes = 5,10,3: mean 6, SAMPLE variance (1+16+9)/2 = 13,
    # so CV^2 = 13/36 = 0.361111...  ADI 3 >= 1.32 and CV^2 < 0.49 -> INTERMITTENT.
    var profile = demand_classify(y)
    var mean_size = compute_mean(sizes, 3)
    var var_size = compute_variance(sizes, 3, mean_size)
    if (
        profile.status == FC_OK
        and profile.adi == 3.0
        and profile.has_adi
        and profile.adi == compute_mean(intervals, 3)
        and profile.mean_demand == 6.0
        and profile.has_mean_demand
        and profile.mean_demand == mean_size
        and var_size == 13.0
        and profile.cv2 == 13.0 / 36.0
        and profile.has_cv2
        and profile.cv2 == var_size / (mean_size * mean_size)
        and profile.demand_class == FC_DEMAND_INTERMITTENT
        and profile.class_name == "intermittent"
        and profile.n_nonzero == 3
    ):
        passed += 1
        print("  ✅ ADI 3.0 and CV^2 13/36 from the frozen moments -> INTERMITTENT")
    else:
        failed += 1
        print("  ❌ classification wrong:", profile.adi, profile.cv2, profile.class_name)

    # All four quadrants are reachable, and the cuts are the named constants.
    # ADI 1: demand every period. sizes 5,5,5,5 -> CV^2 = 0 -> SMOOTH.
    var smooth = demand_classify(_floats(5.0, 5.0, 5.0, 5.0))
    # ADI 1, sizes 1,20,1,20 -> mean 10.5, sample var = 3*(9.5^2)*2/3 ... computed below.
    var erratic = demand_classify(_floats(1.0, 20.0, 1.0, 20.0))
    # ADI 2 with equal sizes -> INTERMITTENT (already covered), ADI 2 with wild sizes -> LUMPY.
    var lumpy = demand_classify(_floats(1.0, 0.0, 40.0, 0.0, 1.0, 0.0, 40.0, 0.0))
    if (
        smooth.adi == 1.0 and smooth.cv2 == 0.0
        and smooth.demand_class == FC_DEMAND_SMOOTH
        and erratic.adi == 1.0 and erratic.cv2 >= FC_CV2_CUT
        and erratic.demand_class == FC_DEMAND_ERRATIC
        and lumpy.adi >= FC_ADI_CUT and lumpy.cv2 >= FC_CV2_CUT
        and lumpy.demand_class == FC_DEMAND_LUMPY
        and FC_ADI_CUT == 1.32 and FC_CV2_CUT == 0.49
    ):
        passed += 1
        print("  ✅ all four quadrants reachable at the named 1.32 / 0.49 cuts")
    else:
        failed += 1
        print("  ❌ quadrants wrong:", smooth.class_name, erratic.class_name, lumpy.class_name)

    # ══ one demand observation: an ADI but no CV, so no quadrant ═══════════════════
    var single = demand_classify(_floats(0.0, 4.0, 0.0))
    var empty_profile = demand_classify(List[Float64]())
    var zero_profile = demand_classify(zeros)
    if (
        single.status == FC_OK
        and single.has_adi and single.adi == 2.0
        and not single.has_cv2 and single.cv2 == 0.0
        and single.demand_class == FC_DEMAND_UNCLASSIFIED
        and single.class_name == "unclassified"
        and empty_profile.status == FC_ERR_EMPTY_SERIES
        and not empty_profile.has_adi
        and zero_profile.status == FC_ERR_NO_DEMAND
        and not zero_profile.has_adi and not zero_profile.has_cv2
        and zero_profile.demand_class == FC_DEMAND_UNCLASSIFIED
        and demand_class_name(FC_DEMAND_UNCLASSIFIED) == "unclassified"
        and demand_class_name(99) == "unknown"
    ):
        passed += 1
        print("  ✅ one demand -> ADI present, CV absent, class UNCLASSIFIED (not SMOOTH)")
    else:
        failed += 1
        print("  ❌ single-demand classification wrong:", single.has_cv2, single.class_name)

    # A negative value is refused by the classifier too, at the same strength as by the
    # forecaster — one invariant, one status, not two strengths in one package.
    if (
        demand_classify(_floats(1.0, -1.0)).status == FC_ERR_NEGATIVE_VALUES
        and demand_classify(_floats(1.0, -1.0)).demand_class == FC_DEMAND_UNCLASSIFIED
    ):
        passed += 1
        print("  ✅ negative demand is the SAME refusal in the classifier as in the forecaster")
    else:
        failed += 1
        print("  ❌ the negativity invariant is enforced at two strengths")

    print("  [forecasting.intermittent] Passed:", passed, "Failed:", failed)
