"""bench_transportation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from transportation import level_of_service_density, highway_capacity, travel_time, delay_at_signal, headway, stopping_distance, fuel_consumption_rate, passenger_car_equivalent, intersection_capacity, queue_length_estimate, vehicle_operating_cost, crash_rate
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_level_of_service_density: Float64 = 0.0
    var _t0_level_of_service_density = perf_counter_ns()
    for _ in range(N):
        _acc_level_of_service_density += level_of_service_density(0.5, 0.5)
    var _t1_level_of_service_density = perf_counter_ns()
    var _ns_level_of_service_density = Float64(_t1_level_of_service_density - _t0_level_of_service_density) / Float64(N)
    print("MOJO_TIMING transportation::level_of_service_density", _ns_level_of_service_density, _acc_level_of_service_density)
    var _acc_highway_capacity: Float64 = 0.0
    var _t0_highway_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_highway_capacity += highway_capacity(0.5, 0.5)
    var _t1_highway_capacity = perf_counter_ns()
    var _ns_highway_capacity = Float64(_t1_highway_capacity - _t0_highway_capacity) / Float64(N)
    print("MOJO_TIMING transportation::highway_capacity", _ns_highway_capacity, _acc_highway_capacity)
    var _acc_travel_time: Float64 = 0.0
    var _t0_travel_time = perf_counter_ns()
    for _ in range(N):
        _acc_travel_time += travel_time(0.5, 0.5)
    var _t1_travel_time = perf_counter_ns()
    var _ns_travel_time = Float64(_t1_travel_time - _t0_travel_time) / Float64(N)
    print("MOJO_TIMING transportation::travel_time", _ns_travel_time, _acc_travel_time)
    var _acc_delay_at_signal: Float64 = 0.0
    var _t0_delay_at_signal = perf_counter_ns()
    for _ in range(N):
        _acc_delay_at_signal += delay_at_signal(0.5, 0.5, 0.5, 0.5)
    var _t1_delay_at_signal = perf_counter_ns()
    var _ns_delay_at_signal = Float64(_t1_delay_at_signal - _t0_delay_at_signal) / Float64(N)
    print("MOJO_TIMING transportation::delay_at_signal", _ns_delay_at_signal, _acc_delay_at_signal)
    var _acc_headway: Float64 = 0.0
    var _t0_headway = perf_counter_ns()
    for _ in range(N):
        _acc_headway += headway(0.5, 0.5, 0.5)
    var _t1_headway = perf_counter_ns()
    var _ns_headway = Float64(_t1_headway - _t0_headway) / Float64(N)
    print("MOJO_TIMING transportation::headway", _ns_headway, _acc_headway)
    var _acc_stopping_distance: Float64 = 0.0
    var _t0_stopping_distance = perf_counter_ns()
    for _ in range(N):
        _acc_stopping_distance += stopping_distance(0.5, 0.5, 0.5, 0.5)
    var _t1_stopping_distance = perf_counter_ns()
    var _ns_stopping_distance = Float64(_t1_stopping_distance - _t0_stopping_distance) / Float64(N)
    print("MOJO_TIMING transportation::stopping_distance", _ns_stopping_distance, _acc_stopping_distance)
    var _acc_fuel_consumption_rate: Float64 = 0.0
    var _t0_fuel_consumption_rate = perf_counter_ns()
    for _ in range(N):
        _acc_fuel_consumption_rate += fuel_consumption_rate(0.5, 0.5, 0.5)
    var _t1_fuel_consumption_rate = perf_counter_ns()
    var _ns_fuel_consumption_rate = Float64(_t1_fuel_consumption_rate - _t0_fuel_consumption_rate) / Float64(N)
    print("MOJO_TIMING transportation::fuel_consumption_rate", _ns_fuel_consumption_rate, _acc_fuel_consumption_rate)
    var _acc_passenger_car_equivalent: Float64 = 0.0
    var _t0_passenger_car_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_passenger_car_equivalent += passenger_car_equivalent(0.5, 0.5)
    var _t1_passenger_car_equivalent = perf_counter_ns()
    var _ns_passenger_car_equivalent = Float64(_t1_passenger_car_equivalent - _t0_passenger_car_equivalent) / Float64(N)
    print("MOJO_TIMING transportation::passenger_car_equivalent", _ns_passenger_car_equivalent, _acc_passenger_car_equivalent)
    var _acc_intersection_capacity: Float64 = 0.0
    var _t0_intersection_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_intersection_capacity += intersection_capacity(0.5, 0.5)
    var _t1_intersection_capacity = perf_counter_ns()
    var _ns_intersection_capacity = Float64(_t1_intersection_capacity - _t0_intersection_capacity) / Float64(N)
    print("MOJO_TIMING transportation::intersection_capacity", _ns_intersection_capacity, _acc_intersection_capacity)
    var _acc_queue_length_estimate: Float64 = 0.0
    var _t0_queue_length_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_queue_length_estimate += queue_length_estimate(0.5, 0.5, 0.5)
    var _t1_queue_length_estimate = perf_counter_ns()
    var _ns_queue_length_estimate = Float64(_t1_queue_length_estimate - _t0_queue_length_estimate) / Float64(N)
    print("MOJO_TIMING transportation::queue_length_estimate", _ns_queue_length_estimate, _acc_queue_length_estimate)
    var _acc_vehicle_operating_cost: Float64 = 0.0
    var _t0_vehicle_operating_cost = perf_counter_ns()
    for _ in range(N):
        _acc_vehicle_operating_cost += vehicle_operating_cost(0.5, 0.5, 0.5)
    var _t1_vehicle_operating_cost = perf_counter_ns()
    var _ns_vehicle_operating_cost = Float64(_t1_vehicle_operating_cost - _t0_vehicle_operating_cost) / Float64(N)
    print("MOJO_TIMING transportation::vehicle_operating_cost", _ns_vehicle_operating_cost, _acc_vehicle_operating_cost)
    var _acc_crash_rate: Float64 = 0.0
    var _t0_crash_rate = perf_counter_ns()
    for _ in range(N):
        _acc_crash_rate += crash_rate(0.5, 0.5)
    var _t1_crash_rate = perf_counter_ns()
    var _ns_crash_rate = Float64(_t1_crash_rate - _t0_crash_rate) / Float64(N)
    print("MOJO_TIMING transportation::crash_rate", _ns_crash_rate, _acc_crash_rate)
