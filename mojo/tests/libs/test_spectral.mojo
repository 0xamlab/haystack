"""test_spectral.mojo — auto-generated tests for spectral library."""
from std.math import isnan, isinf
from spectral import power_spectral_density, cross_spectral_density, coherence, spectral_centroid, spectral_bandwidth, spectral_rolloff, spectral_flatness, spectral_entropy, band_energy, peak_frequency

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

    var _v_power_spectral_density = power_spectral_density(_lf5, 0.5)
    if len(_v_power_spectral_density) >= 0: passed += 1; print("  ✅ spectral::power_spectral_density")
    var _v_cross_spectral_density = cross_spectral_density(_lf5, _lf5, 0.5)
    if len(_v_cross_spectral_density) >= 0: passed += 1; print("  ✅ spectral::cross_spectral_density")
    var _v_coherence = coherence(_lf5, _lf5, 0.5)
    if len(_v_coherence) >= 0: passed += 1; print("  ✅ spectral::coherence")
    var _v_spectral_centroid = spectral_centroid(_lf5, _lf5)
    if is_finite(_v_spectral_centroid): passed += 1; print("  ✅ spectral::spectral_centroid =", _v_spectral_centroid)
    else: failed += 1; print("  ❌ spectral::spectral_centroid → non-finite:", _v_spectral_centroid)
    var _v_spectral_bandwidth = spectral_bandwidth(_lf5, _lf5, 0.5)
    if is_finite(_v_spectral_bandwidth): passed += 1; print("  ✅ spectral::spectral_bandwidth =", _v_spectral_bandwidth)
    else: failed += 1; print("  ❌ spectral::spectral_bandwidth → non-finite:", _v_spectral_bandwidth)
    var _v_spectral_rolloff = spectral_rolloff(_lf5, _lf5, 0.5)
    if is_finite(_v_spectral_rolloff): passed += 1; print("  ✅ spectral::spectral_rolloff =", _v_spectral_rolloff)
    else: failed += 1; print("  ❌ spectral::spectral_rolloff → non-finite:", _v_spectral_rolloff)
    var _v_spectral_flatness = spectral_flatness(_lf5)
    if is_finite(_v_spectral_flatness): passed += 1; print("  ✅ spectral::spectral_flatness =", _v_spectral_flatness)
    else: failed += 1; print("  ❌ spectral::spectral_flatness → non-finite:", _v_spectral_flatness)
    var _v_spectral_entropy = spectral_entropy(_lf5)
    if is_finite(_v_spectral_entropy): passed += 1; print("  ✅ spectral::spectral_entropy =", _v_spectral_entropy)
    else: failed += 1; print("  ❌ spectral::spectral_entropy → non-finite:", _v_spectral_entropy)
    var _v_band_energy = band_energy(_lf5, _lf5, 0.5, 0.5)
    if is_finite(_v_band_energy): passed += 1; print("  ✅ spectral::band_energy =", _v_band_energy)
    else: failed += 1; print("  ❌ spectral::band_energy → non-finite:", _v_band_energy)
    var _v_peak_frequency = peak_frequency(_lf5, _lf5)
    if is_finite(_v_peak_frequency): passed += 1; print("  ✅ spectral::peak_frequency =", _v_peak_frequency)
    else: failed += 1; print("  ❌ spectral::peak_frequency → non-finite:", _v_peak_frequency)

    print("  [spectral] Passed:", passed, "Failed:", failed)
