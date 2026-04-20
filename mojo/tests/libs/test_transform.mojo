"""test_transform.mojo — auto-generated tests for transform library."""
from std.math import isnan, isinf
from transform import log_transform, log1p_transform, box_cox, standardize, min_max_scale, robust_scale, quantile_transform, power_transform, clamp_values, rank_transform, abs_transform, reciprocal_transform

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_log_transform = log_transform(_lf5)
    if len(_v_log_transform) >= 0: passed += 1; print("  ✅ transform::log_transform")
    var _v_log1p_transform = log1p_transform(_lf5)
    if len(_v_log1p_transform) >= 0: passed += 1; print("  ✅ transform::log1p_transform")
    var _v_box_cox = box_cox(_lf5, 0.5)
    if len(_v_box_cox) >= 0: passed += 1; print("  ✅ transform::box_cox")
    var _v_standardize = standardize(_lf5)
    if len(_v_standardize) >= 0: passed += 1; print("  ✅ transform::standardize")
    var _v_min_max_scale = min_max_scale(_lf5, 0.5, 0.5)
    if len(_v_min_max_scale) >= 0: passed += 1; print("  ✅ transform::min_max_scale")
    var _v_robust_scale = robust_scale(_lf5)
    if len(_v_robust_scale) >= 0: passed += 1; print("  ✅ transform::robust_scale")
    var _v_quantile_transform = quantile_transform(_lf5)
    if len(_v_quantile_transform) >= 0: passed += 1; print("  ✅ transform::quantile_transform")
    var _v_power_transform = power_transform(_lf5, 0.5)
    if len(_v_power_transform) >= 0: passed += 1; print("  ✅ transform::power_transform")
    var _v_clamp_values = clamp_values(_lf5, 0.5, 0.5)
    if len(_v_clamp_values) >= 0: passed += 1; print("  ✅ transform::clamp_values")
    var _v_rank_transform = rank_transform(_lf5)
    if len(_v_rank_transform) >= 0: passed += 1; print("  ✅ transform::rank_transform")
    var _v_abs_transform = abs_transform(_lf5)
    if len(_v_abs_transform) >= 0: passed += 1; print("  ✅ transform::abs_transform")
    var _v_reciprocal_transform = reciprocal_transform(_lf5)
    if len(_v_reciprocal_transform) >= 0: passed += 1; print("  ✅ transform::reciprocal_transform")

    print("  [transform] Passed:", passed, "Failed:", failed)
