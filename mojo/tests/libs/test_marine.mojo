"""test_marine.mojo — auto-generated tests for marine library."""
from std.math import isnan, isinf
from marine import seawater_density, wave_speed_deep, wave_speed_shallow, wave_period, significant_wave_height, tidal_range, mixed_layer_depth_estimate, ekman_depth, coriolis_parameter, buoyancy_frequency, salinity_from_conductivity, ocean_pressure_at_depth

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

    var _v_seawater_density = seawater_density(0.5, 0.5)
    if is_finite(_v_seawater_density): passed += 1; print("  ✅ marine::seawater_density =", _v_seawater_density)
    else: failed += 1; print("  ❌ marine::seawater_density → non-finite:", _v_seawater_density)
    var _v_wave_speed_deep = wave_speed_deep(0.5, 0.5)
    if is_finite(_v_wave_speed_deep): passed += 1; print("  ✅ marine::wave_speed_deep =", _v_wave_speed_deep)
    else: failed += 1; print("  ❌ marine::wave_speed_deep → non-finite:", _v_wave_speed_deep)
    var _v_wave_speed_shallow = wave_speed_shallow(0.5, 0.5)
    if is_finite(_v_wave_speed_shallow): passed += 1; print("  ✅ marine::wave_speed_shallow =", _v_wave_speed_shallow)
    else: failed += 1; print("  ❌ marine::wave_speed_shallow → non-finite:", _v_wave_speed_shallow)
    var _v_wave_period = wave_period(0.5, 0.5)
    if is_finite(_v_wave_period): passed += 1; print("  ✅ marine::wave_period =", _v_wave_period)
    else: failed += 1; print("  ❌ marine::wave_period → non-finite:", _v_wave_period)
    var _v_significant_wave_height = significant_wave_height(0.5)
    if is_finite(_v_significant_wave_height): passed += 1; print("  ✅ marine::significant_wave_height =", _v_significant_wave_height)
    else: failed += 1; print("  ❌ marine::significant_wave_height → non-finite:", _v_significant_wave_height)
    var _v_tidal_range = tidal_range(0.5, 0.5)
    if is_finite(_v_tidal_range): passed += 1; print("  ✅ marine::tidal_range =", _v_tidal_range)
    else: failed += 1; print("  ❌ marine::tidal_range → non-finite:", _v_tidal_range)
    var _v_mixed_layer_depth_estimate = mixed_layer_depth_estimate(0.5, 0.5)
    if is_finite(_v_mixed_layer_depth_estimate): passed += 1; print("  ✅ marine::mixed_layer_depth_estimate =", _v_mixed_layer_depth_estimate)
    else: failed += 1; print("  ❌ marine::mixed_layer_depth_estimate → non-finite:", _v_mixed_layer_depth_estimate)
    var _v_ekman_depth = ekman_depth(0.5, 0.5, 0.5)
    if is_finite(_v_ekman_depth): passed += 1; print("  ✅ marine::ekman_depth =", _v_ekman_depth)
    else: failed += 1; print("  ❌ marine::ekman_depth → non-finite:", _v_ekman_depth)
    var _v_coriolis_parameter = coriolis_parameter(0.5)
    if is_finite(_v_coriolis_parameter): passed += 1; print("  ✅ marine::coriolis_parameter =", _v_coriolis_parameter)
    else: failed += 1; print("  ❌ marine::coriolis_parameter → non-finite:", _v_coriolis_parameter)
    var _v_buoyancy_frequency = buoyancy_frequency(0.5, 0.5, 0.5)
    if is_finite(_v_buoyancy_frequency): passed += 1; print("  ✅ marine::buoyancy_frequency =", _v_buoyancy_frequency)
    else: failed += 1; print("  ❌ marine::buoyancy_frequency → non-finite:", _v_buoyancy_frequency)
    var _v_salinity_from_conductivity = salinity_from_conductivity(0.5, 0.5)
    if is_finite(_v_salinity_from_conductivity): passed += 1; print("  ✅ marine::salinity_from_conductivity =", _v_salinity_from_conductivity)
    else: failed += 1; print("  ❌ marine::salinity_from_conductivity → non-finite:", _v_salinity_from_conductivity)
    var _v_ocean_pressure_at_depth = ocean_pressure_at_depth(0.5, 0.5, 0.5)
    if is_finite(_v_ocean_pressure_at_depth): passed += 1; print("  ✅ marine::ocean_pressure_at_depth =", _v_ocean_pressure_at_depth)
    else: failed += 1; print("  ❌ marine::ocean_pressure_at_depth → non-finite:", _v_ocean_pressure_at_depth)

    print("  [marine] Passed:", passed, "Failed:", failed)
