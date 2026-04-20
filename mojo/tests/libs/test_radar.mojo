"""test_radar.mojo — auto-generated tests for radar library."""
from std.math import isnan, isinf
from radar import radar_range_equation, doppler_frequency, doppler_velocity, range_from_time, pulse_repetition_interval, max_unambiguous_range, max_unambiguous_velocity, range_resolution, antenna_gain_from_area, radar_cross_section_sphere, noise_power, signal_to_clutter

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

    var _v_radar_range_equation = radar_range_equation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_radar_range_equation): passed += 1; print("  ✅ radar::radar_range_equation =", _v_radar_range_equation)
    else: failed += 1; print("  ❌ radar::radar_range_equation → non-finite:", _v_radar_range_equation)
    var _v_doppler_frequency = doppler_frequency(0.5, 0.5)
    if is_finite(_v_doppler_frequency): passed += 1; print("  ✅ radar::doppler_frequency =", _v_doppler_frequency)
    else: failed += 1; print("  ❌ radar::doppler_frequency → non-finite:", _v_doppler_frequency)
    var _v_doppler_velocity = doppler_velocity(0.5, 0.5)
    if is_finite(_v_doppler_velocity): passed += 1; print("  ✅ radar::doppler_velocity =", _v_doppler_velocity)
    else: failed += 1; print("  ❌ radar::doppler_velocity → non-finite:", _v_doppler_velocity)
    var _v_range_from_time = range_from_time(0.5, 0.5)
    if is_finite(_v_range_from_time): passed += 1; print("  ✅ radar::range_from_time =", _v_range_from_time)
    else: failed += 1; print("  ❌ radar::range_from_time → non-finite:", _v_range_from_time)
    var _v_pulse_repetition_interval = pulse_repetition_interval(0.5)
    if is_finite(_v_pulse_repetition_interval): passed += 1; print("  ✅ radar::pulse_repetition_interval =", _v_pulse_repetition_interval)
    else: failed += 1; print("  ❌ radar::pulse_repetition_interval → non-finite:", _v_pulse_repetition_interval)
    var _v_max_unambiguous_range = max_unambiguous_range(0.5, 0.5)
    if is_finite(_v_max_unambiguous_range): passed += 1; print("  ✅ radar::max_unambiguous_range =", _v_max_unambiguous_range)
    else: failed += 1; print("  ❌ radar::max_unambiguous_range → non-finite:", _v_max_unambiguous_range)
    var _v_max_unambiguous_velocity = max_unambiguous_velocity(0.5, 0.5)
    if is_finite(_v_max_unambiguous_velocity): passed += 1; print("  ✅ radar::max_unambiguous_velocity =", _v_max_unambiguous_velocity)
    else: failed += 1; print("  ❌ radar::max_unambiguous_velocity → non-finite:", _v_max_unambiguous_velocity)
    var _v_range_resolution = range_resolution(0.5)
    if is_finite(_v_range_resolution): passed += 1; print("  ✅ radar::range_resolution =", _v_range_resolution)
    else: failed += 1; print("  ❌ radar::range_resolution → non-finite:", _v_range_resolution)
    var _v_antenna_gain_from_area = antenna_gain_from_area(0.5, 0.5)
    if is_finite(_v_antenna_gain_from_area): passed += 1; print("  ✅ radar::antenna_gain_from_area =", _v_antenna_gain_from_area)
    else: failed += 1; print("  ❌ radar::antenna_gain_from_area → non-finite:", _v_antenna_gain_from_area)
    var _v_radar_cross_section_sphere = radar_cross_section_sphere(0.5)
    if is_finite(_v_radar_cross_section_sphere): passed += 1; print("  ✅ radar::radar_cross_section_sphere =", _v_radar_cross_section_sphere)
    else: failed += 1; print("  ❌ radar::radar_cross_section_sphere → non-finite:", _v_radar_cross_section_sphere)
    var _v_noise_power = noise_power(0.5, 0.5, 0.5)
    if is_finite(_v_noise_power): passed += 1; print("  ✅ radar::noise_power =", _v_noise_power)
    else: failed += 1; print("  ❌ radar::noise_power → non-finite:", _v_noise_power)
    var _v_signal_to_clutter = signal_to_clutter(0.5, 0.5)
    if is_finite(_v_signal_to_clutter): passed += 1; print("  ✅ radar::signal_to_clutter =", _v_signal_to_clutter)
    else: failed += 1; print("  ❌ radar::signal_to_clutter → non-finite:", _v_signal_to_clutter)

    print("  [radar] Passed:", passed, "Failed:", failed)
