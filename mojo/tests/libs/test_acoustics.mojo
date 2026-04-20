"""test_acoustics.mojo — auto-generated tests for acoustics library."""
from std.math import isnan, isinf
from acoustics import sound_pressure_level, sound_intensity_level, sound_power_level, inverse_square_law_pressure, wavelength, resonant_frequency_pipe_open, resonant_frequency_pipe_closed, doppler_frequency, reverberation_time_sabine, noise_reduction_coefficient, decibel_sum_2, distance_doubling_attenuation

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

    var _v_sound_pressure_level = sound_pressure_level(0.5, 0.5)
    if is_finite(_v_sound_pressure_level): passed += 1; print("  ✅ acoustics::sound_pressure_level =", _v_sound_pressure_level)
    else: failed += 1; print("  ❌ acoustics::sound_pressure_level → non-finite:", _v_sound_pressure_level)
    var _v_sound_intensity_level = sound_intensity_level(0.5, 0.5)
    if is_finite(_v_sound_intensity_level): passed += 1; print("  ✅ acoustics::sound_intensity_level =", _v_sound_intensity_level)
    else: failed += 1; print("  ❌ acoustics::sound_intensity_level → non-finite:", _v_sound_intensity_level)
    var _v_sound_power_level = sound_power_level(0.5, 0.5)
    if is_finite(_v_sound_power_level): passed += 1; print("  ✅ acoustics::sound_power_level =", _v_sound_power_level)
    else: failed += 1; print("  ❌ acoustics::sound_power_level → non-finite:", _v_sound_power_level)
    var _v_inverse_square_law_pressure = inverse_square_law_pressure(0.5, 0.5, 0.5)
    if is_finite(_v_inverse_square_law_pressure): passed += 1; print("  ✅ acoustics::inverse_square_law_pressure =", _v_inverse_square_law_pressure)
    else: failed += 1; print("  ❌ acoustics::inverse_square_law_pressure → non-finite:", _v_inverse_square_law_pressure)
    var _v_wavelength = wavelength(0.5, 0.5)
    if is_finite(_v_wavelength): passed += 1; print("  ✅ acoustics::wavelength =", _v_wavelength)
    else: failed += 1; print("  ❌ acoustics::wavelength → non-finite:", _v_wavelength)
    var _v_resonant_frequency_pipe_open = resonant_frequency_pipe_open(0.5, 0.5)
    if is_finite(_v_resonant_frequency_pipe_open): passed += 1; print("  ✅ acoustics::resonant_frequency_pipe_open =", _v_resonant_frequency_pipe_open)
    else: failed += 1; print("  ❌ acoustics::resonant_frequency_pipe_open → non-finite:", _v_resonant_frequency_pipe_open)
    var _v_resonant_frequency_pipe_closed = resonant_frequency_pipe_closed(0.5, 0.5)
    if is_finite(_v_resonant_frequency_pipe_closed): passed += 1; print("  ✅ acoustics::resonant_frequency_pipe_closed =", _v_resonant_frequency_pipe_closed)
    else: failed += 1; print("  ❌ acoustics::resonant_frequency_pipe_closed → non-finite:", _v_resonant_frequency_pipe_closed)
    var _v_doppler_frequency = doppler_frequency(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_doppler_frequency): passed += 1; print("  ✅ acoustics::doppler_frequency =", _v_doppler_frequency)
    else: failed += 1; print("  ❌ acoustics::doppler_frequency → non-finite:", _v_doppler_frequency)
    var _v_reverberation_time_sabine = reverberation_time_sabine(0.5, 0.5)
    if is_finite(_v_reverberation_time_sabine): passed += 1; print("  ✅ acoustics::reverberation_time_sabine =", _v_reverberation_time_sabine)
    else: failed += 1; print("  ❌ acoustics::reverberation_time_sabine → non-finite:", _v_reverberation_time_sabine)
    var _v_noise_reduction_coefficient = noise_reduction_coefficient(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_noise_reduction_coefficient): passed += 1; print("  ✅ acoustics::noise_reduction_coefficient =", _v_noise_reduction_coefficient)
    else: failed += 1; print("  ❌ acoustics::noise_reduction_coefficient → non-finite:", _v_noise_reduction_coefficient)
    var _v_decibel_sum_2 = decibel_sum_2(0.5, 0.5)
    if is_finite(_v_decibel_sum_2): passed += 1; print("  ✅ acoustics::decibel_sum_2 =", _v_decibel_sum_2)
    else: failed += 1; print("  ❌ acoustics::decibel_sum_2 → non-finite:", _v_decibel_sum_2)
    var _v_distance_doubling_attenuation = distance_doubling_attenuation()
    if is_finite(_v_distance_doubling_attenuation): passed += 1; print("  ✅ acoustics::distance_doubling_attenuation =", _v_distance_doubling_attenuation)
    else: failed += 1; print("  ❌ acoustics::distance_doubling_attenuation → non-finite:", _v_distance_doubling_attenuation)

    print("  [acoustics] Passed:", passed, "Failed:", failed)
