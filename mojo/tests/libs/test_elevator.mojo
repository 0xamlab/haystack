"""test_elevator.mojo — auto-generated tests for elevator library."""
from std.math import isnan, isinf
from elevator import round_trip_time, handling_capacity, interval_time, probable_stops, motor_power, counterweight_mass, shaft_area, annual_energy_consumption, waiting_time_average, traffic_intensity, rope_factor_of_safety, pit_depth_requirement

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

    var _v_round_trip_time = round_trip_time(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_round_trip_time): passed += 1; print("  ✅ elevator::round_trip_time =", _v_round_trip_time)
    else: failed += 1; print("  ❌ elevator::round_trip_time → non-finite:", _v_round_trip_time)
    var _v_handling_capacity = handling_capacity(0.5, 0.5)
    if is_finite(_v_handling_capacity): passed += 1; print("  ✅ elevator::handling_capacity =", _v_handling_capacity)
    else: failed += 1; print("  ❌ elevator::handling_capacity → non-finite:", _v_handling_capacity)
    var _v_interval_time = interval_time(0.5, 0.5)
    if is_finite(_v_interval_time): passed += 1; print("  ✅ elevator::interval_time =", _v_interval_time)
    else: failed += 1; print("  ❌ elevator::interval_time → non-finite:", _v_interval_time)
    var _v_probable_stops = probable_stops(0.5, 0.5)
    if is_finite(_v_probable_stops): passed += 1; print("  ✅ elevator::probable_stops =", _v_probable_stops)
    else: failed += 1; print("  ❌ elevator::probable_stops → non-finite:", _v_probable_stops)
    var _v_motor_power = motor_power(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_motor_power): passed += 1; print("  ✅ elevator::motor_power =", _v_motor_power)
    else: failed += 1; print("  ❌ elevator::motor_power → non-finite:", _v_motor_power)
    var _v_counterweight_mass = counterweight_mass(0.5, 0.5, 0.5)
    if is_finite(_v_counterweight_mass): passed += 1; print("  ✅ elevator::counterweight_mass =", _v_counterweight_mass)
    else: failed += 1; print("  ❌ elevator::counterweight_mass → non-finite:", _v_counterweight_mass)
    var _v_shaft_area = shaft_area(0.5, 0.5, 0.5)
    if is_finite(_v_shaft_area): passed += 1; print("  ✅ elevator::shaft_area =", _v_shaft_area)
    else: failed += 1; print("  ❌ elevator::shaft_area → non-finite:", _v_shaft_area)
    var _v_annual_energy_consumption = annual_energy_consumption(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_annual_energy_consumption): passed += 1; print("  ✅ elevator::annual_energy_consumption =", _v_annual_energy_consumption)
    else: failed += 1; print("  ❌ elevator::annual_energy_consumption → non-finite:", _v_annual_energy_consumption)
    var _v_waiting_time_average = waiting_time_average(0.5)
    if is_finite(_v_waiting_time_average): passed += 1; print("  ✅ elevator::waiting_time_average =", _v_waiting_time_average)
    else: failed += 1; print("  ❌ elevator::waiting_time_average → non-finite:", _v_waiting_time_average)
    var _v_traffic_intensity = traffic_intensity(0.5, 0.5)
    if is_finite(_v_traffic_intensity): passed += 1; print("  ✅ elevator::traffic_intensity =", _v_traffic_intensity)
    else: failed += 1; print("  ❌ elevator::traffic_intensity → non-finite:", _v_traffic_intensity)
    var _v_rope_factor_of_safety = rope_factor_of_safety(0.5, 0.5)
    if is_finite(_v_rope_factor_of_safety): passed += 1; print("  ✅ elevator::rope_factor_of_safety =", _v_rope_factor_of_safety)
    else: failed += 1; print("  ❌ elevator::rope_factor_of_safety → non-finite:", _v_rope_factor_of_safety)
    var _v_pit_depth_requirement = pit_depth_requirement(0.5)
    if is_finite(_v_pit_depth_requirement): passed += 1; print("  ✅ elevator::pit_depth_requirement =", _v_pit_depth_requirement)
    else: failed += 1; print("  ❌ elevator::pit_depth_requirement → non-finite:", _v_pit_depth_requirement)

    print("  [elevator] Passed:", passed, "Failed:", failed)
