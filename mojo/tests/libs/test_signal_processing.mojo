"""test_signal_processing.mojo — auto-generated tests for signal_processing library."""
from std.math import isnan, isinf
from signal_processing import hamming_window, hann_window, blackman_window, apply_window, peak_detect, zero_crossings, spectral_energy, spectral_centroid, spectral_flatness, signal_power

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

    var _v_hamming_window = hamming_window(5)
    if len(_v_hamming_window) >= 0: passed += 1; print("  ✅ signal_processing::hamming_window")
    var _v_hann_window = hann_window(5)
    if len(_v_hann_window) >= 0: passed += 1; print("  ✅ signal_processing::hann_window")
    var _v_blackman_window = blackman_window(5)
    if len(_v_blackman_window) >= 0: passed += 1; print("  ✅ signal_processing::blackman_window")
    var _v_apply_window = apply_window(_lf5, _lf5)
    if len(_v_apply_window) >= 0: passed += 1; print("  ✅ signal_processing::apply_window")
    var _v_peak_detect = peak_detect(_lf5, 0.5)
    if len(_v_peak_detect) >= 0: passed += 1; print("  ✅ signal_processing::peak_detect")
    var _v_zero_crossings = zero_crossings(_lf5)
    if len(_v_zero_crossings) >= 0: passed += 1; print("  ✅ signal_processing::zero_crossings")
    var _v_spectral_energy = spectral_energy(_lf5)
    if is_finite(_v_spectral_energy): passed += 1; print("  ✅ signal_processing::spectral_energy =", _v_spectral_energy)
    else: failed += 1; print("  ❌ signal_processing::spectral_energy → non-finite:", _v_spectral_energy)
    var _v_spectral_centroid = spectral_centroid(_lf5, 0.5)
    if is_finite(_v_spectral_centroid): passed += 1; print("  ✅ signal_processing::spectral_centroid =", _v_spectral_centroid)
    else: failed += 1; print("  ❌ signal_processing::spectral_centroid → non-finite:", _v_spectral_centroid)
    var _v_spectral_flatness = spectral_flatness(_lf5)
    if is_finite(_v_spectral_flatness): passed += 1; print("  ✅ signal_processing::spectral_flatness =", _v_spectral_flatness)
    else: failed += 1; print("  ❌ signal_processing::spectral_flatness → non-finite:", _v_spectral_flatness)
    var _v_signal_power = signal_power(_lf5)
    if is_finite(_v_signal_power): passed += 1; print("  ✅ signal_processing::signal_power =", _v_signal_power)
    else: failed += 1; print("  ❌ signal_processing::signal_power → non-finite:", _v_signal_power)

    print("  [signal_processing] Passed:", passed, "Failed:", failed)
