"""test_esrnn_global_residual.mojo — known-value tests for the ES-RNN-class backbone
selection and residual-correction arithmetic.

Hand-written. The cases that carry the module's reason to exist:

  * THREE-WAY SELECTION, ALL THREE OUTCOMES REACHABLE. `esrnn_select_backbone` is not a
    disguised constant: a pure trend line picks Holt, a fast-rise-then-plateau shape
    picks Damped, and an early-outlier series picks Theta — the SAME three frozen
    drivers, three different real winners, each confirmed against the raw
    `holt_fitted`/`damped_fitted`/`theta_fitted` `insample_mae` fields it ranks.
  * THE EXACT TIE. At the M4-minimum shape `n=2, h=1`, Holt and Damped both reach
    `insample_mae == 0.0` exactly (Theta refuses at `n=2 < 3`) — a genuine floating-point
    tie, not a near-miss — and the selector picks Holt, proving the declared tie-break
    (declaration order, strict `<`) structurally rather than by assertion alone.
  * CALL-ONLY, PROVEN BIT-EXACT. `esrnn_backbone_forecast` reapplying a named method is
    asserted `==` (not a tolerance) against a fresh direct call to that same frozen
    driver — the "never reimplement" rule checked at the value level, not just narrated.
  * REFUSAL OVER SILENT TRUNCATION. `esrnn_residual`/`esrnn_apply_correction` on
    mismatched lengths or a non-finite input return EMPTY, never a `min(len, len)`
    partial answer — and the round-trip identity
    `apply_correction(backbone, residual(actual, backbone)) == actual` pins the sign
    convention of both functions against each other in one assertion.
"""
from std.math import abs as fabs

from esrnn.global_residual import (
    ESRNN_METHOD_DAMPED,
    ESRNN_METHOD_HOLT,
    ESRNN_METHOD_THETA,
    ESRNN_N_METHODS,
    esrnn_apply_correction,
    esrnn_backbone_forecast,
    esrnn_method_name,
    esrnn_residual,
    esrnn_scaled_window,
    esrnn_select_backbone,
    esrnn_window_scale,
)
from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_METHOD,
    FC_OK,
)
from forecasting.fitted import damped_fitted, holt_fitted, theta_fitted


def _same_values(a: List[Float64], b: List[Float64]) -> Bool:
    """Elementwise `==` over two value lists — `List[Float64]` has no `__eq__` here, so
    every bit-exact comparison in this suite goes through this helper, never `a == b`."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _pure_trend() -> List[Float64]:
    """30 points of y = 10 + 2t: a clean line every method can fit well, Holt best."""
    var y = List[Float64]()
    for t in range(30):
        y.append(10.0 + 2.0 * Float64(t))
    return y^


def _damped_shape() -> List[Float64]:
    """A fast rise that decelerates toward a plateau — the textbook damped-trend shape."""
    var y = List[Float64]()
    for t in range(20):
        y.append(100.0 - 80.0 / (1.0 + Float64(t)))
    return y^


def _early_spike() -> List[Float64]:
    """A sharp early outlier then a near-flat tail: the adaptive level/trend methods
    carry the spike's disturbance forward; Theta's global OLS line does not."""
    var y = List[Float64]()
    y.append(10.0)
    y.append(90.0)
    y.append(12.0)
    y.append(11.0)
    for t in range(20):
        y.append(10.0 + 0.05 * Float64(t))
    return y^


def main():
    var passed = 0
    var failed = 0
    print("\n[esrnn.global_residual] hand-written known-value suite")

    # ══ 1. Three-way selection: all three real outcomes, each cross-checked ═══════════
    var yt = _pure_trend()
    var ht = holt_fitted(yt, 6)
    var dt = damped_fitted(yt, 6)
    var tt = theta_fitted(yt, 6)
    var st = esrnn_select_backbone(yt, 6)
    if (
        ht.insample_mae < dt.insample_mae and ht.insample_mae < tt.insample_mae
        and st.status == FC_OK and st.method_id == ESRNN_METHOD_HOLT
        and st.insample_mae == ht.insample_mae and _same_values(st.values, ht.values)
    ):
        passed += 1
        print("  ✅ pure trend: Holt has the lowest insample_mae and is the one selected")
    else:
        failed += 1
        print("  ❌ pure-trend selection wrong:", esrnn_method_name(st.method_id))

    var yd = _damped_shape()
    var hd = holt_fitted(yd, 6)
    var dd = damped_fitted(yd, 6)
    var td = theta_fitted(yd, 6)
    var sd = esrnn_select_backbone(yd, 6)
    if (
        dd.insample_mae < hd.insample_mae and dd.insample_mae < td.insample_mae
        and sd.status == FC_OK and sd.method_id == ESRNN_METHOD_DAMPED
        and sd.insample_mae == dd.insample_mae
    ):
        passed += 1
        print("  ✅ damped shape: Damped has the lowest insample_mae and is selected")
    else:
        failed += 1
        print("  ❌ damped-shape selection wrong:", esrnn_method_name(sd.method_id))

    var ys = _early_spike()
    var hs = holt_fitted(ys, 6)
    var ds = damped_fitted(ys, 6)
    var ts = theta_fitted(ys, 6)
    var ss = esrnn_select_backbone(ys, 6)
    if (
        ts.insample_mae < hs.insample_mae and ts.insample_mae < ds.insample_mae
        and ss.status == FC_OK and ss.method_id == ESRNN_METHOD_THETA
        and ss.insample_mae == ts.insample_mae
    ):
        passed += 1
        print("  ✅ early-spike series: Theta has the lowest insample_mae and is selected")
    else:
        failed += 1
        print("  ❌ early-spike selection wrong:", esrnn_method_name(ss.method_id))

    # ══ 2. The exact tie at the M4-minimum shape (n=2, h=1) ═══════════════════════════
    # Holt and Damped both reach insample_mae == 0.0 EXACTLY; Theta refuses (n=2 < 3).
    # Holt must win: declaration order, strict `<` (damped never overrides an equal mae).
    var y2 = List[Float64]()
    y2.append(1.0)
    y2.append(3.0)
    var h2 = holt_fitted(y2, 1)
    var d2 = damped_fitted(y2, 1)
    var t2 = theta_fitted(y2, 1)
    var s2 = esrnn_select_backbone(y2, 1)
    if (
        h2.has_forecast and d2.has_forecast and not t2.has_forecast
        and h2.insample_mae == 0.0 and d2.insample_mae == 0.0
        and s2.status == FC_OK and s2.method_id == ESRNN_METHOD_HOLT
    ):
        passed += 1
        print("  ✅ exact Holt/Damped tie at n=2,h=1: Holt wins by declaration order")
    else:
        failed += 1
        print("  ❌ tie-break wrong:", esrnn_method_name(s2.method_id), h2.insample_mae, d2.insample_mae)

    # ══ 3. Total refusal: too short for anything (n=2, h=6) ═══════════════════════════
    var yshort = List[Float64]()
    yshort.append(1.0)
    yshort.append(2.0)
    var sshort = esrnn_select_backbone(yshort, 6)
    if (
        sshort.status == FC_ERR_ALL_UNDEFINED and sshort.method_id == -1
        and not sshort.has_forecast and len(sshort.values) == 0
        and sshort.insample_mae == -1.0
    ):
        passed += 1
        print("  ✅ n=2,h=6: all three refuse, selection reports FC_ERR_ALL_UNDEFINED, id -1")
    else:
        failed += 1
        print("  ❌ total-refusal case mistyped:", sshort.status, sshort.method_id)

    # ══ 4. esrnn_backbone_forecast: call-only, bit-exact against the direct driver ════
    var fh = esrnn_backbone_forecast(yt, ESRNN_METHOD_HOLT, 6)
    var fd = esrnn_backbone_forecast(yt, ESRNN_METHOD_DAMPED, 6)
    var fth = esrnn_backbone_forecast(yt, ESRNN_METHOD_THETA, 6)
    var direct_h = holt_fitted(yt, 6)
    var direct_d = damped_fitted(yt, 6)
    var direct_t = theta_fitted(yt, 6)
    if (
        fh.status == direct_h.status and _same_values(fh.values, direct_h.values)
        and fh.insample_mae == direct_h.insample_mae
        and fd.status == direct_d.status and _same_values(fd.values, direct_d.values)
        and fth.status == direct_t.status and _same_values(fth.values, direct_t.values)
    ):
        passed += 1
        print("  ✅ backbone_forecast reproduces holt/damped/theta_fitted bit-for-bit")
    else:
        failed += 1
        print("  ❌ backbone_forecast diverged from a direct fitted-driver call")

    # An unknown method id refuses BEFORE any fit runs — no partial work, no fiction.
    var fbad = esrnn_backbone_forecast(yt, 99, 6)
    if (
        fbad.status == FC_ERR_METHOD and fbad.method_id == 99
        and not fbad.has_forecast and len(fbad.values) == 0
        and ESRNN_N_METHODS == 3
    ):
        passed += 1
        print("  ✅ an unknown method id refuses with FC_ERR_METHOD, no fit attempted")
    else:
        failed += 1
        print("  ❌ unknown method id mishandled:", fbad.status)

    # ══ 5. The vocabulary is total and loud on unknowns ═══════════════════════════════
    if (
        esrnn_method_name(ESRNN_METHOD_HOLT) == "holt"
        and esrnn_method_name(ESRNN_METHOD_DAMPED) == "damped"
        and esrnn_method_name(ESRNN_METHOD_THETA) == "theta"
        and esrnn_method_name(-1) == "unknown_method"
        and esrnn_method_name(99) == "unknown_method"
    ):
        passed += 1
        print("  ✅ method-name vocabulary: total, loud on unknowns")
    else:
        failed += 1
        print("  ❌ a vocabulary hole")

    # ══ 6. esrnn_window_scale: known values, empty, all-zero ══════════════════════════
    var w1 = List[Float64]()
    w1.append(1.0)
    w1.append(-2.0)
    w1.append(3.0)
    var w1_empty = List[Float64]()
    var w1_zero = List[Float64]()
    w1_zero.append(0.0)
    w1_zero.append(0.0)
    if (
        esrnn_window_scale(w1) == 2.0
        and esrnn_window_scale(w1_empty) == 0.0
        and esrnn_window_scale(w1_zero) == 0.0
    ):
        passed += 1
        print("  ✅ window_scale: mean(|1,-2,3|) == 2.0 exactly; empty and all-zero -> 0.0")
    else:
        failed += 1
        print("  ❌ window_scale arithmetic wrong:", esrnn_window_scale(w1))

    # ══ 7. esrnn_scaled_window: the multi-horizon pseudo-timestep encoding ════════════
    var w2 = List[Float64]()
    w2.append(2.0)
    w2.append(4.0)
    var sw = esrnn_scaled_window(w2, 2.0, 0.5)
    var sw_bad_scale = esrnn_scaled_window(w2, 0.0, 0.5)
    var sw_neg_scale = esrnn_scaled_window(w2, -1.0, 0.5)
    var sw_nan_step = esrnn_scaled_window(w2, 2.0, 0.0 / 0.0)
    if (
        len(sw) == 3 and sw[0] == 1.0 and sw[1] == 2.0 and sw[2] == 0.5
        and len(sw_bad_scale) == 0 and len(sw_neg_scale) == 0 and len(sw_nan_step) == 0
    ):
        passed += 1
        print("  ✅ scaled_window: [w/scale...]+[step_frac]; refuses on scale<=0 or non-finite step")
    else:
        failed += 1
        print("  ❌ scaled_window wrong:", len(sw), len(sw_bad_scale), len(sw_neg_scale))

    # ══ 8. esrnn_residual / esrnn_apply_correction: sign, refusal, round-trip ═════════
    var actual = List[Float64]()
    actual.append(5.0)
    actual.append(6.0)
    var backbone = List[Float64]()
    backbone.append(4.0)
    backbone.append(6.0)
    var resid = esrnn_residual(actual, backbone)
    var corrected = esrnn_apply_correction(backbone, resid)
    var mismatched = List[Float64]()
    mismatched.append(1.0)
    var nonfinite = List[Float64]()
    nonfinite.append(1.0 / 0.0)
    nonfinite.append(2.0)
    if (
        len(resid) == 2 and resid[0] == 1.0 and resid[1] == 0.0
        and len(corrected) == 2 and corrected[0] == actual[0] and corrected[1] == actual[1]
        and len(esrnn_residual(actual, mismatched)) == 0
        and len(esrnn_apply_correction(backbone, mismatched)) == 0
        and len(esrnn_residual(nonfinite, backbone)) == 0
        and len(esrnn_apply_correction(backbone, nonfinite)) == 0
    ):
        passed += 1
        print("  ✅ residual/apply_correction: correct sign, round-trips to `actual`, refuses on defect")
    else:
        failed += 1
        print("  ❌ residual/apply_correction wrong:", resid[0], resid[1], corrected[0], corrected[1])

    print("  [esrnn.global_residual] Passed:", passed, "Failed:", failed)
