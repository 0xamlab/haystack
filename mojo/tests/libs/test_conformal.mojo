"""test_conformal.mojo — known-value tests for conformal."""
from std.math import abs as fabs, isinf

from conformal import (
    ConformalInterval,
    ConformalBand,
    conformal_quantile,
    conformal_quantile_normalized,
    conformal_interval,
    conformal_interval_normalized,
    conformal_band,
    conformal_coverage,
)


fn _close(a: Float64, b: Float64) -> Bool:
    return fabs(a - b) <= 1e-12


fn _is_inf_sentinel(x: Float64) -> Bool:
    # Must be the effectively-infinite sentinel, and finite per the module
    # convention (never IEEE inf).
    return x >= 1e307 and not isinf(x)


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ conformal::" + name)
    else:
        failed += 1
        print("  ❌ conformal::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── conformal_quantile: spec case n=9, alpha=0.1 ─────────────────────────
    # Signed residuals; scores = |r| sorted:
    #   [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.2, 1.5, 2.0]
    # k = ceil(0.9 * 10) = 9 -> 9th smallest = 2.0
    var res9 = List[Float64]()
    res9.append(0.5); res9.append(-1.2); res9.append(0.3)
    res9.append(2.0); res9.append(-0.7); res9.append(1.5)
    res9.append(0.1); res9.append(-0.9); res9.append(1.1)
    check(
        _close(conformal_quantile(res9, 0.1), 2.0),
        "quantile n=9 alpha=0.1 -> 9th of sorted = 2.0",
        passed,
        failed,
    )
    # Same data, alpha=0.2: k = ceil(0.8 * 10) = 8 -> 8th = 1.5
    check(
        _close(conformal_quantile(res9, 0.2), 1.5),
        "quantile n=9 alpha=0.2 -> 8th of sorted = 1.5",
        passed,
        failed,
    )

    # ── conformal_quantile: fractional ceil, n=4, alpha=0.5 ──────────────────
    # scores [1,2,3,4]; k = ceil(0.5 * 5) = ceil(2.5) = 3 -> 3.0
    var res4 = List[Float64]()
    res4.append(1.0); res4.append(2.0); res4.append(3.0); res4.append(4.0)
    check(
        _close(conformal_quantile(res4, 0.5), 3.0),
        "quantile n=4 alpha=0.5 ceil(2.5)=3 -> 3.0",
        passed,
        failed,
    )

    # ── conformal_quantile: all-equal (ties) ─────────────────────────────────
    # Five copies of 0.5; alpha=0.25: k = ceil(0.75 * 6) = ceil(4.5) = 5 -> 0.5
    var res_eq = List[Float64]()
    for _ in range(5):
        res_eq.append(0.5)
    check(
        _close(conformal_quantile(res_eq, 0.25), 0.5),
        "quantile all-equal ties -> 0.5",
        passed,
        failed,
    )

    # ── conformal_quantile: n=1 ──────────────────────────────────────────────
    # alpha=0.5: k = ceil(0.5 * 2) = 1 -> |−3| = 3.0
    # alpha=0.1: k = ceil(0.9 * 2) = 2 > n -> infinite sentinel
    var res1 = List[Float64]()
    res1.append(-3.0)
    check(
        _close(conformal_quantile(res1, 0.5), 3.0),
        "quantile n=1 alpha=0.5 -> |residual| = 3.0",
        passed,
        failed,
    )
    check(
        _is_inf_sentinel(conformal_quantile(res1, 0.1)),
        "quantile n=1 alpha=0.1 rank>n -> infinite sentinel",
        passed,
        failed,
    )

    # ── conformal_quantile: empty + alpha extremes ───────────────────────────
    var res_empty = List[Float64]()
    check(
        _is_inf_sentinel(conformal_quantile(res_empty, 0.1)),
        "quantile empty calibration -> infinite sentinel",
        passed,
        failed,
    )
    check(
        _is_inf_sentinel(conformal_quantile(res4, 0.0)),
        "quantile alpha=0 -> infinite sentinel",
        passed,
        failed,
    )
    # alpha >= 1 clamps to the smallest score: |[3,-1,2]| -> min 1.0
    var res3 = List[Float64]()
    res3.append(3.0); res3.append(-1.0); res3.append(2.0)
    check(
        _close(conformal_quantile(res3, 1.0), 1.0),
        "quantile alpha=1 clamps to smallest score",
        passed,
        failed,
    )

    # ── conformal_quantile: NaN residual scores as infinite ──────────────────
    # scores sorted: [1, 2, INF]
    #   alpha=0.5:  k = ceil(0.5 * 4) = 2 -> 2.0 (NaN not selected)
    #   alpha=0.25: k = ceil(0.75 * 4) = 3 -> sentinel (NaN slot selected)
    var nanv = Float64(0.0) / Float64(0.0)
    var res_nan = List[Float64]()
    res_nan.append(nanv); res_nan.append(1.0); res_nan.append(2.0)
    check(
        _close(conformal_quantile(res_nan, 0.5), 2.0),
        "quantile NaN sorts last, k=2 -> 2.0",
        passed,
        failed,
    )
    check(
        _is_inf_sentinel(conformal_quantile(res_nan, 0.25)),
        "quantile NaN selected at k=3 -> infinite sentinel",
        passed,
        failed,
    )

    # ── conformal_quantile: non-finite alpha -> sentinel (never rank 1) ──────
    var posinf = Float64(1.0) / Float64(0.0)
    check(
        _is_inf_sentinel(conformal_quantile(res3, posinf))
        and _is_inf_sentinel(conformal_quantile(res3, -posinf))
        and _is_inf_sentinel(conformal_quantile(res3, -1e300)),
        "quantile non-finite / huge-negative alpha -> infinite sentinel",
        passed,
        failed,
    )

    # ── conformal_quantile: inf residual scores as finite sentinel ───────────
    # scores [1, inf->1e308]; n=2, alpha=0.5: k = ceil(0.5*3) = 2 -> sentinel,
    # and q must stay finite (module convention: never leak IEEE inf).
    var res_inf = List[Float64]()
    res_inf.append(1.0); res_inf.append(posinf)
    check(
        _is_inf_sentinel(conformal_quantile(res_inf, 0.5)),
        "quantile inf residual selected -> finite 1e308 sentinel",
        passed,
        failed,
    )

    # ── conformal_interval ───────────────────────────────────────────────────
    var iv = conformal_interval(10.0, 2.0)
    check(
        _close(iv.lo, 8.0) and _close(iv.hi, 12.0),
        "interval (10, 2) -> [8, 12]",
        passed,
        failed,
    )
    var iv_neg = conformal_interval(5.0, -1.0)
    check(
        _close(iv_neg.lo, 5.0) and _close(iv_neg.hi, 5.0),
        "interval negative q clamps to point [5, 5]",
        passed,
        failed,
    )

    # ── conformal_band ───────────────────────────────────────────────────────
    var preds = List[Float64]()
    preds.append(1.0); preds.append(2.0); preds.append(3.0)
    var band = conformal_band(preds, 0.5)
    check(
        len(band.lo) == 3
        and _close(band.lo[0], 0.5) and _close(band.hi[0], 1.5)
        and _close(band.lo[1], 1.5) and _close(band.hi[1], 2.5)
        and _close(band.lo[2], 2.5) and _close(band.hi[2], 3.5),
        "band preds±0.5 exact",
        passed,
        failed,
    )

    # ── conformal_coverage: hand-checked 3/5, bounds inclusive ───────────────
    #   y=1 in [0,2]   yes    y=2 in [2.5,3] no     y=3 in [2,4] yes
    #   y=4 in [5,6]   no     y=5 in [4,5]   yes (hi inclusive)
    var y5 = List[Float64]()
    y5.append(1.0); y5.append(2.0); y5.append(3.0); y5.append(4.0); y5.append(5.0)
    var lo5 = List[Float64]()
    lo5.append(0.0); lo5.append(2.5); lo5.append(2.0); lo5.append(5.0); lo5.append(4.0)
    var hi5 = List[Float64]()
    hi5.append(2.0); hi5.append(3.0); hi5.append(4.0); hi5.append(6.0); hi5.append(5.0)
    check(
        _close(conformal_coverage(y5, lo5, hi5), 0.6),
        "coverage 3/5 = 0.6 exact (boundary inclusive)",
        passed,
        failed,
    )

    # ── conformal_coverage: empty + length mismatch -> 0 ─────────────────────
    var empty_f = List[Float64]()
    check(
        _close(conformal_coverage(empty_f, empty_f, empty_f), 0.0)
        and _close(conformal_coverage(y5, lo5, empty_f), 0.0),
        "coverage empty / mismatched lengths -> 0.0",
        passed,
        failed,
    )

    # ── end-to-end: constructed exact 90% coverage ───────────────────────────
    # Calibration scores 1..99, alpha=0.1: k = ceil(0.9 * 100) = 90 -> q = 90.
    # Test: preds all 0, y_j = j for j=1..100 -> |y| <= 90 for exactly 90.
    var cal = List[Float64]()
    for j in range(1, 100):
        cal.append(Float64(j))
    var q90 = conformal_quantile(cal, 0.1)
    check(_close(q90, 90.0), "quantile 1..99 alpha=0.1 -> 90.0", passed, failed)
    var preds100 = List[Float64]()
    var y100 = List[Float64]()
    for j in range(1, 101):
        preds100.append(0.0)
        y100.append(Float64(j))
    var band100 = conformal_band(preds100, q90)
    check(
        _close(conformal_coverage(y100, band100.lo, band100.hi), 0.9),
        "end-to-end constructed coverage = 0.90 exact",
        passed,
        failed,
    )
    # Same calibration, alpha=0.05: k = ceil(0.95 * 100) = 95 -> q = 95.
    check(
        _close(conformal_quantile(cal, 0.05), 95.0),
        "quantile 1..99 alpha=0.05 -> 95.0",
        passed,
        failed,
    )

    # ── conformal_quantile_normalized ────────────────────────────────────────
    # residuals [1,-4,9] / scales [1,2,3] -> scores [1,2,3]
    # alpha=0.5: k = ceil(0.5 * 4) = 2 -> 2.0
    var rn = List[Float64]()
    rn.append(1.0); rn.append(-4.0); rn.append(9.0)
    var sn = List[Float64]()
    sn.append(1.0); sn.append(2.0); sn.append(3.0)
    check(
        _close(conformal_quantile_normalized(rn, sn, 0.5), 2.0),
        "normalized quantile scores [1,2,3] k=2 -> 2.0",
        passed,
        failed,
    )

    # zero scale -> that score is infinite; k=2 of sorted [2, INF] -> sentinel
    var rz = List[Float64]()
    rz.append(1.0); rz.append(2.0)
    var sz = List[Float64]()
    sz.append(0.0); sz.append(1.0)
    check(
        _is_inf_sentinel(conformal_quantile_normalized(rz, sz, 0.5)),
        "normalized zero scale selected -> infinite sentinel",
        passed,
        failed,
    )

    # length mismatch -> sentinel
    check(
        _is_inf_sentinel(conformal_quantile_normalized(rn, sz, 0.5)),
        "normalized length mismatch -> infinite sentinel",
        passed,
        failed,
    )

    # denormal scale: |1|/1e-320 overflows to inf -> clamps to finite
    # sentinel; k = ceil(0.5*3) = 2 of sorted [1, 1e308] selects it.
    var rd = List[Float64]()
    rd.append(1.0); rd.append(1.0)
    var sd = List[Float64]()
    sd.append(1e-320); sd.append(1.0)
    check(
        _is_inf_sentinel(conformal_quantile_normalized(rd, sd, 0.5)),
        "normalized denormal scale overflow -> finite 1e308 sentinel",
        passed,
        failed,
    )

    # ── conformal_interval_normalized ────────────────────────────────────────
    var ivn = conformal_interval_normalized(5.0, 2.0, 1.5)
    check(
        _close(ivn.lo, 2.0) and _close(ivn.hi, 8.0),
        "normalized interval (5, 2, 1.5) -> [2, 8]",
        passed,
        failed,
    )
    var ivn0 = conformal_interval_normalized(5.0, 2.0, -1.0)
    check(
        _close(ivn0.lo, 5.0) and _close(ivn0.hi, 5.0),
        "normalized interval negative scale clamps to point",
        passed,
        failed,
    )

    print("  [conformal] Passed:", passed, "Failed:", failed)
