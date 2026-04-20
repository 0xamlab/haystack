"""test_seismology.mojo — auto-generated tests for seismology library."""
from std.math import isnan, isinf
from seismology import richter_magnitude, moment_magnitude, seismic_moment, energy_from_magnitude, peak_ground_acceleration, travel_time_p_wave, travel_time_s_wave, ts_tp_difference, epicenter_distance_from_ts_tp, intensity_mmi_from_pga, gutenberg_richter_rate, recurrence_interval

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

    var _v_richter_magnitude = richter_magnitude(0.5, 0.5)
    if is_finite(_v_richter_magnitude): passed += 1; print("  ✅ seismology::richter_magnitude =", _v_richter_magnitude)
    else: failed += 1; print("  ❌ seismology::richter_magnitude → non-finite:", _v_richter_magnitude)
    var _v_moment_magnitude = moment_magnitude(0.5)
    if is_finite(_v_moment_magnitude): passed += 1; print("  ✅ seismology::moment_magnitude =", _v_moment_magnitude)
    else: failed += 1; print("  ❌ seismology::moment_magnitude → non-finite:", _v_moment_magnitude)
    var _v_seismic_moment = seismic_moment(0.5)
    if is_finite(_v_seismic_moment): passed += 1; print("  ✅ seismology::seismic_moment =", _v_seismic_moment)
    else: failed += 1; print("  ❌ seismology::seismic_moment → non-finite:", _v_seismic_moment)
    var _v_energy_from_magnitude = energy_from_magnitude(0.5)
    if is_finite(_v_energy_from_magnitude): passed += 1; print("  ✅ seismology::energy_from_magnitude =", _v_energy_from_magnitude)
    else: failed += 1; print("  ❌ seismology::energy_from_magnitude → non-finite:", _v_energy_from_magnitude)
    var _v_peak_ground_acceleration = peak_ground_acceleration(0.5, 0.5, 0.5)
    if is_finite(_v_peak_ground_acceleration): passed += 1; print("  ✅ seismology::peak_ground_acceleration =", _v_peak_ground_acceleration)
    else: failed += 1; print("  ❌ seismology::peak_ground_acceleration → non-finite:", _v_peak_ground_acceleration)
    var _v_travel_time_p_wave = travel_time_p_wave(0.5, 0.5)
    if is_finite(_v_travel_time_p_wave): passed += 1; print("  ✅ seismology::travel_time_p_wave =", _v_travel_time_p_wave)
    else: failed += 1; print("  ❌ seismology::travel_time_p_wave → non-finite:", _v_travel_time_p_wave)
    var _v_travel_time_s_wave = travel_time_s_wave(0.5, 0.5)
    if is_finite(_v_travel_time_s_wave): passed += 1; print("  ✅ seismology::travel_time_s_wave =", _v_travel_time_s_wave)
    else: failed += 1; print("  ❌ seismology::travel_time_s_wave → non-finite:", _v_travel_time_s_wave)
    var _v_ts_tp_difference = ts_tp_difference(0.5, 0.5, 0.5)
    if is_finite(_v_ts_tp_difference): passed += 1; print("  ✅ seismology::ts_tp_difference =", _v_ts_tp_difference)
    else: failed += 1; print("  ❌ seismology::ts_tp_difference → non-finite:", _v_ts_tp_difference)
    var _v_epicenter_distance_from_ts_tp = epicenter_distance_from_ts_tp(2.0, 3.5, 6.0)
    if is_finite(_v_epicenter_distance_from_ts_tp): passed += 1; print("  ✅ seismology::epicenter_distance_from_ts_tp =", _v_epicenter_distance_from_ts_tp)
    else: failed += 1; print("  ❌ seismology::epicenter_distance_from_ts_tp → non-finite:", _v_epicenter_distance_from_ts_tp)
    var _v_intensity_mmi_from_pga = intensity_mmi_from_pga(0.5)
    if is_finite(_v_intensity_mmi_from_pga): passed += 1; print("  ✅ seismology::intensity_mmi_from_pga =", _v_intensity_mmi_from_pga)
    else: failed += 1; print("  ❌ seismology::intensity_mmi_from_pga → non-finite:", _v_intensity_mmi_from_pga)
    var _v_gutenberg_richter_rate = gutenberg_richter_rate(0.5, 0.5, 0.5)
    if is_finite(_v_gutenberg_richter_rate): passed += 1; print("  ✅ seismology::gutenberg_richter_rate =", _v_gutenberg_richter_rate)
    else: failed += 1; print("  ❌ seismology::gutenberg_richter_rate → non-finite:", _v_gutenberg_richter_rate)
    var _v_recurrence_interval = recurrence_interval(0.5)
    if is_finite(_v_recurrence_interval): passed += 1; print("  ✅ seismology::recurrence_interval =", _v_recurrence_interval)
    else: failed += 1; print("  ❌ seismology::recurrence_interval → non-finite:", _v_recurrence_interval)

    print("  [seismology] Passed:", passed, "Failed:", failed)
