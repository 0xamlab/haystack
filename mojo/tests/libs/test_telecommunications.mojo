"""test_telecommunications.mojo — auto-generated tests for telecommunications library."""
from std.math import isnan, isinf
from telecommunications import shannon_capacity, erlang_b, bit_error_rate_bpsk, spectral_efficiency, link_margin, thermal_noise_power, signal_to_noise_ratio, snr_db, data_rate_nyquist, propagation_delay, throughput, availability_percentage

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

    var _v_shannon_capacity = shannon_capacity(0.5, 0.5)
    if is_finite(_v_shannon_capacity): passed += 1; print("  ✅ telecommunications::shannon_capacity =", _v_shannon_capacity)
    else: failed += 1; print("  ❌ telecommunications::shannon_capacity → non-finite:", _v_shannon_capacity)
    var _v_erlang_b = erlang_b(5, 0.5)
    if is_finite(_v_erlang_b): passed += 1; print("  ✅ telecommunications::erlang_b =", _v_erlang_b)
    else: failed += 1; print("  ❌ telecommunications::erlang_b → non-finite:", _v_erlang_b)
    var _v_bit_error_rate_bpsk = bit_error_rate_bpsk(0.5)
    if is_finite(_v_bit_error_rate_bpsk): passed += 1; print("  ✅ telecommunications::bit_error_rate_bpsk =", _v_bit_error_rate_bpsk)
    else: failed += 1; print("  ❌ telecommunications::bit_error_rate_bpsk → non-finite:", _v_bit_error_rate_bpsk)
    var _v_spectral_efficiency = spectral_efficiency(0.5, 0.5)
    if is_finite(_v_spectral_efficiency): passed += 1; print("  ✅ telecommunications::spectral_efficiency =", _v_spectral_efficiency)
    else: failed += 1; print("  ❌ telecommunications::spectral_efficiency → non-finite:", _v_spectral_efficiency)
    var _v_link_margin = link_margin(0.5, 0.5)
    if is_finite(_v_link_margin): passed += 1; print("  ✅ telecommunications::link_margin =", _v_link_margin)
    else: failed += 1; print("  ❌ telecommunications::link_margin → non-finite:", _v_link_margin)
    var _v_thermal_noise_power = thermal_noise_power(0.5, 0.5)
    if is_finite(_v_thermal_noise_power): passed += 1; print("  ✅ telecommunications::thermal_noise_power =", _v_thermal_noise_power)
    else: failed += 1; print("  ❌ telecommunications::thermal_noise_power → non-finite:", _v_thermal_noise_power)
    var _v_signal_to_noise_ratio = signal_to_noise_ratio(0.5, 0.5)
    if is_finite(_v_signal_to_noise_ratio): passed += 1; print("  ✅ telecommunications::signal_to_noise_ratio =", _v_signal_to_noise_ratio)
    else: failed += 1; print("  ❌ telecommunications::signal_to_noise_ratio → non-finite:", _v_signal_to_noise_ratio)
    var _v_snr_db = snr_db(0.5)
    if is_finite(_v_snr_db): passed += 1; print("  ✅ telecommunications::snr_db =", _v_snr_db)
    else: failed += 1; print("  ❌ telecommunications::snr_db → non-finite:", _v_snr_db)
    var _v_data_rate_nyquist = data_rate_nyquist(0.5, 0.5)
    if is_finite(_v_data_rate_nyquist): passed += 1; print("  ✅ telecommunications::data_rate_nyquist =", _v_data_rate_nyquist)
    else: failed += 1; print("  ❌ telecommunications::data_rate_nyquist → non-finite:", _v_data_rate_nyquist)
    var _v_propagation_delay = propagation_delay(0.5, 0.5)
    if is_finite(_v_propagation_delay): passed += 1; print("  ✅ telecommunications::propagation_delay =", _v_propagation_delay)
    else: failed += 1; print("  ❌ telecommunications::propagation_delay → non-finite:", _v_propagation_delay)
    var _v_throughput = throughput(0.5, 0.5)
    if is_finite(_v_throughput): passed += 1; print("  ✅ telecommunications::throughput =", _v_throughput)
    else: failed += 1; print("  ❌ telecommunications::throughput → non-finite:", _v_throughput)
    var _v_availability_percentage = availability_percentage(0.5, 0.5)
    if is_finite(_v_availability_percentage): passed += 1; print("  ✅ telecommunications::availability_percentage =", _v_availability_percentage)
    else: failed += 1; print("  ❌ telecommunications::availability_percentage → non-finite:", _v_availability_percentage)

    print("  [telecommunications] Passed:", passed, "Failed:", failed)
