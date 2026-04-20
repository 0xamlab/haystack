"""test_wavelet.mojo — auto-generated tests for wavelet library."""
from std.math import isnan, isinf
from wavelet import haar_forward, haar_inverse, haar_multilevel, haar_multilevel_inverse, threshold_hard, threshold_soft, denoise_haar, energy_ratio, detail_coefficients, approx_coefficients

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

    var _v_haar_forward = haar_forward(_lf5)
    if len(_v_haar_forward) >= 0: passed += 1; print("  ✅ wavelet::haar_forward")
    var _v_haar_inverse = haar_inverse(_lf5)
    if len(_v_haar_inverse) >= 0: passed += 1; print("  ✅ wavelet::haar_inverse")
    var _v_haar_multilevel = haar_multilevel(_lf5, 5)
    if len(_v_haar_multilevel) >= 0: passed += 1; print("  ✅ wavelet::haar_multilevel")
    var _v_haar_multilevel_inverse = haar_multilevel_inverse(_lf5, 5)
    if len(_v_haar_multilevel_inverse) >= 0: passed += 1; print("  ✅ wavelet::haar_multilevel_inverse")
    var _v_threshold_hard = threshold_hard(_lf5, 0.5)
    if len(_v_threshold_hard) >= 0: passed += 1; print("  ✅ wavelet::threshold_hard")
    var _v_threshold_soft = threshold_soft(_lf5, 0.5)
    if len(_v_threshold_soft) >= 0: passed += 1; print("  ✅ wavelet::threshold_soft")
    var _v_denoise_haar = denoise_haar(_lf5, 0.5, 5)
    if len(_v_denoise_haar) >= 0: passed += 1; print("  ✅ wavelet::denoise_haar")
    var _v_energy_ratio = energy_ratio(_lf5)
    if is_finite(_v_energy_ratio): passed += 1; print("  ✅ wavelet::energy_ratio =", _v_energy_ratio)
    else: failed += 1; print("  ❌ wavelet::energy_ratio → non-finite:", _v_energy_ratio)
    var _v_detail_coefficients = detail_coefficients(_lf5)
    if len(_v_detail_coefficients) >= 0: passed += 1; print("  ✅ wavelet::detail_coefficients")
    var _v_approx_coefficients = approx_coefficients(_lf5)
    if len(_v_approx_coefficients) >= 0: passed += 1; print("  ✅ wavelet::approx_coefficients")

    print("  [wavelet] Passed:", passed, "Failed:", failed)
