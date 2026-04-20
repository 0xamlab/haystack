"""test_transportation.mojo — auto-generated tests for transportation library."""
from std.math import isnan, isinf
from transportation import level_of_service_density, highway_capacity, travel_time, delay_at_signal, headway, stopping_distance, fuel_consumption_rate, passenger_car_equivalent, intersection_capacity, queue_length_estimate, vehicle_operating_cost, crash_rate

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

    var _v_level_of_service_density = level_of_service_density(0.5, 0.5)
    if is_finite(_v_level_of_service_density): passed += 1; print("  ✅ transportation::level_of_service_density =", _v_level_of_service_density)
    else: failed += 1; print("  ❌ transportation::level_of_service_density → non-finite:", _v_level_of_service_density)
    var _v_highway_capacity = highway_capacity(0.5, 0.5)
    if is_finite(_v_highway_capacity): passed += 1; print("  ✅ transportation::highway_capacity =", _v_highway_capacity)
    else: failed += 1; print("  ❌ transportation::highway_capacity → non-finite:", _v_highway_capacity)
    var _v_travel_time = travel_time(0.5, 0.5)
    if is_finite(_v_travel_time): passed += 1; print("  ✅ transportation::travel_time =", _v_travel_time)
    else: failed += 1; print("  ❌ transportation::travel_time → non-finite:", _v_travel_time)
    var _v_delay_at_signal = delay_at_signal(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_delay_at_signal): passed += 1; print("  ✅ transportation::delay_at_signal =", _v_delay_at_signal)
    else: failed += 1; print("  ❌ transportation::delay_at_signal → non-finite:", _v_delay_at_signal)
    var _v_headway = headway(0.5, 0.5, 0.5)
    if is_finite(_v_headway): passed += 1; print("  ✅ transportation::headway =", _v_headway)
    else: failed += 1; print("  ❌ transportation::headway → non-finite:", _v_headway)
    var _v_stopping_distance = stopping_distance(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_stopping_distance): passed += 1; print("  ✅ transportation::stopping_distance =", _v_stopping_distance)
    else: failed += 1; print("  ❌ transportation::stopping_distance → non-finite:", _v_stopping_distance)
    var _v_fuel_consumption_rate = fuel_consumption_rate(0.5, 0.5, 0.5)
    if is_finite(_v_fuel_consumption_rate): passed += 1; print("  ✅ transportation::fuel_consumption_rate =", _v_fuel_consumption_rate)
    else: failed += 1; print("  ❌ transportation::fuel_consumption_rate → non-finite:", _v_fuel_consumption_rate)
    var _v_passenger_car_equivalent = passenger_car_equivalent(0.5, 0.5)
    if is_finite(_v_passenger_car_equivalent): passed += 1; print("  ✅ transportation::passenger_car_equivalent =", _v_passenger_car_equivalent)
    else: failed += 1; print("  ❌ transportation::passenger_car_equivalent → non-finite:", _v_passenger_car_equivalent)
    var _v_intersection_capacity = intersection_capacity(0.5, 0.5)
    if is_finite(_v_intersection_capacity): passed += 1; print("  ✅ transportation::intersection_capacity =", _v_intersection_capacity)
    else: failed += 1; print("  ❌ transportation::intersection_capacity → non-finite:", _v_intersection_capacity)
    var _v_queue_length_estimate = queue_length_estimate(0.5, 0.5, 0.5)
    if is_finite(_v_queue_length_estimate): passed += 1; print("  ✅ transportation::queue_length_estimate =", _v_queue_length_estimate)
    else: failed += 1; print("  ❌ transportation::queue_length_estimate → non-finite:", _v_queue_length_estimate)
    var _v_vehicle_operating_cost = vehicle_operating_cost(0.5, 0.5, 0.5)
    if is_finite(_v_vehicle_operating_cost): passed += 1; print("  ✅ transportation::vehicle_operating_cost =", _v_vehicle_operating_cost)
    else: failed += 1; print("  ❌ transportation::vehicle_operating_cost → non-finite:", _v_vehicle_operating_cost)
    var _v_crash_rate = crash_rate(0.5, 0.5)
    if is_finite(_v_crash_rate): passed += 1; print("  ✅ transportation::crash_rate =", _v_crash_rate)
    else: failed += 1; print("  ❌ transportation::crash_rate → non-finite:", _v_crash_rate)

    print("  [transportation] Passed:", passed, "Failed:", failed)
