"""test_esrnn_bias_correction.mojo — known-value tests for the bias-only residual
corrector (`esrnn.bias_correction`).

Hand-written. The cases that carry the module's reason to exist:

  * KNOWN-VALUE MEAN, INCLUDING THE DEGENERATE CASES. `esrnn_bias_mean` on a plain
    residual list is asserted against the arithmetic mean computed by hand; empty input
    and a single non-finite element both collapse to `0.0` (a no-op bias), never a NaN
    that would otherwise poison every forecast it touches.
  * ROUND-TRIP EXACTNESS WHEN THE RESIDUAL REALLY IS CONSTANT. If every training-holdout
    residual is the SAME number, the bias-only corrector must reproduce the actual values
    exactly — `esrnn_apply_bias(forecast, esrnn_bias_mean(esrnn_residual(actual,
    forecast))) == actual`. This is the one shape a bias-only corrector is GUARANTEED to
    fix; failing it would mean the arithmetic itself, not just the M4 residual's lack of
    a constant structure, is broken.
  * A NON-CONSTANT RESIDUAL IS *NOT* FULLY FIXED, ON PURPOSE. The same composition on a
    residual that varies leaves a nonzero leftover error — proving this module does not
    somehow smuggle in per-element correction; it is genuinely a single scalar.
  * REFUSAL OVER SILENT ZERO. `esrnn_apply_bias` on a non-finite bias, or any non-finite
    backbone element, returns EMPTY — never a `+0.0` no-op that would look identical to
    "no defect happened."
"""
from esrnn.bias_correction import esrnn_apply_bias, esrnn_bias_mean
from esrnn.global_residual import esrnn_residual


fn _same_values(a: List[Float64], b: List[Float64]) -> Bool:
    """Elementwise `==` over two value lists — `List[Float64]` has no `__eq__` here, so
    every bit-exact comparison in this suite goes through this helper, never `a == b`."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn main():
    var passed = 0
    var failed = 0
    print("\n[esrnn.bias_correction] hand-written known-value suite")

    # ══ 1. esrnn_bias_mean: known value, empty, single non-finite element ═════════════
    var r1 = List[Float64]()
    r1.append(1.0)
    r1.append(2.0)
    r1.append(3.0)
    r1.append(6.0)
    var r_empty = List[Float64]()
    var r_bad = List[Float64]()
    r_bad.append(1.0)
    r_bad.append(1.0 / 0.0)
    r_bad.append(3.0)
    if (
        esrnn_bias_mean(r1) == 3.0
        and esrnn_bias_mean(r_empty) == 0.0
        and esrnn_bias_mean(r_bad) == 0.0
    ):
        passed += 1
        print("  ✅ bias_mean: mean(1,2,3,6)==3.0 exactly; empty and non-finite-poisoned -> 0.0")
    else:
        failed += 1
        print("  ❌ bias_mean arithmetic wrong:", esrnn_bias_mean(r1), esrnn_bias_mean(r_bad))

    # A single-element list: the mean of one number is that number, not 0.0.
    var r_one = List[Float64]()
    r_one.append(-7.5)
    if esrnn_bias_mean(r_one) == -7.5:
        passed += 1
        print("  ✅ bias_mean: single-element list returns that element, not the empty case's 0.0")
    else:
        failed += 1
        print("  ❌ single-element bias_mean wrong:", esrnn_bias_mean(r_one))

    # ══ 2. esrnn_apply_bias: known values, zero bias is identity, sign is additive ═════
    var bb = List[Float64]()
    bb.append(1.0)
    bb.append(2.0)
    bb.append(3.0)
    var applied_pos = esrnn_apply_bias(bb, 0.5)
    var applied_zero = esrnn_apply_bias(bb, 0.0)
    var applied_neg = esrnn_apply_bias(bb, -3.0)
    if (
        len(applied_pos) == 3 and applied_pos[0] == 1.5 and applied_pos[1] == 2.5 and applied_pos[2] == 3.5
        and _same_values(applied_zero, bb)
        and len(applied_neg) == 3 and applied_neg[0] == -2.0 and applied_neg[1] == -1.0
    ):
        passed += 1
        print("  ✅ apply_bias: +0.5 shifts every element up, 0.0 is identity, -3.0 shifts down")
    else:
        failed += 1
        print("  ❌ apply_bias arithmetic wrong:", applied_pos[0], applied_neg[0])

    # ══ 3. Refusal, not a silent zero, on a non-finite bias or backbone element ═══════
    var bb_bad = List[Float64]()
    bb_bad.append(1.0)
    bb_bad.append(1.0 / 0.0)
    var refuse_bad_bias = esrnn_apply_bias(bb, 0.0 / 0.0)
    var refuse_bad_backbone = esrnn_apply_bias(bb_bad, 1.0)
    if len(refuse_bad_bias) == 0 and len(refuse_bad_backbone) == 0:
        passed += 1
        print("  ✅ apply_bias: non-finite bias or backbone element refuses (empty), never a silent no-op")
    else:
        failed += 1
        print("  ❌ apply_bias failed to refuse on a non-finite input:", len(refuse_bad_bias), len(refuse_bad_backbone))

    # ══ 4. Round-trip EXACT when the residual really is constant ═════════════════════
    var actual_const = List[Float64]()
    actual_const.append(5.0)
    actual_const.append(6.0)
    actual_const.append(7.0)
    var forecast_const = List[Float64]()
    forecast_const.append(4.0)
    forecast_const.append(5.0)
    forecast_const.append(6.0)
    var resid_const = esrnn_residual(actual_const, forecast_const)
    var bias_const = esrnn_bias_mean(resid_const)
    var corrected_const = esrnn_apply_bias(forecast_const, bias_const)
    if (
        len(resid_const) == 3 and resid_const[0] == 1.0 and resid_const[1] == 1.0 and resid_const[2] == 1.0
        and bias_const == 1.0
        and _same_values(corrected_const, actual_const)
    ):
        passed += 1
        print("  ✅ round-trip: a genuinely constant residual is fixed EXACTLY by its own mean")
    else:
        failed += 1
        print("  ❌ constant-residual round-trip wrong:", bias_const, corrected_const[0])

    # ══ 5. A non-constant residual is left with a real, nonzero leftover error ═══════
    # This proves the module is genuinely a SINGLE scalar, not smuggled per-element fix.
    var actual_var = List[Float64]()
    actual_var.append(5.0)
    actual_var.append(6.0)
    actual_var.append(10.0)
    var forecast_var = List[Float64]()
    forecast_var.append(4.0)
    forecast_var.append(5.0)
    forecast_var.append(5.0)
    var resid_var = esrnn_residual(actual_var, forecast_var)  # [1.0, 1.0, 5.0]
    var bias_var = esrnn_bias_mean(resid_var)  # 7.0 / 3.0
    var corrected_var = esrnn_apply_bias(forecast_var, bias_var)
    var leftover0 = actual_var[0] - corrected_var[0]
    var leftover2 = actual_var[2] - corrected_var[2]
    if (
        bias_var > 2.0 and bias_var < 2.5
        and leftover0 != 0.0 and leftover2 != 0.0
        and leftover0 != leftover2  # different elements, different leftover -> not a per-element fix
    ):
        passed += 1
        print("  ✅ a non-constant residual keeps a real, per-element-varying leftover error")
    else:
        failed += 1
        print("  ❌ non-constant-residual case wrong:", bias_var, leftover0, leftover2)

    print("  [esrnn.bias_correction] Passed:", passed, "Failed:", failed)
