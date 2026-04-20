"""bench_elevator.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from elevator import round_trip_time, handling_capacity, interval_time, probable_stops, motor_power, counterweight_mass, shaft_area, annual_energy_consumption, waiting_time_average, traffic_intensity, rope_factor_of_safety, pit_depth_requirement
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

    var _acc_round_trip_time: Float64 = 0.0
    var _t0_round_trip_time = perf_counter_ns()
    for _ in range(N):
        _acc_round_trip_time += round_trip_time(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_round_trip_time = perf_counter_ns()
    var _ns_round_trip_time = Float64(_t1_round_trip_time - _t0_round_trip_time) / Float64(N)
    print("MOJO_TIMING elevator::round_trip_time", _ns_round_trip_time, _acc_round_trip_time)
    var _acc_handling_capacity: Float64 = 0.0
    var _t0_handling_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_handling_capacity += handling_capacity(0.5, 0.5)
    var _t1_handling_capacity = perf_counter_ns()
    var _ns_handling_capacity = Float64(_t1_handling_capacity - _t0_handling_capacity) / Float64(N)
    print("MOJO_TIMING elevator::handling_capacity", _ns_handling_capacity, _acc_handling_capacity)
    var _acc_interval_time: Float64 = 0.0
    var _t0_interval_time = perf_counter_ns()
    for _ in range(N):
        _acc_interval_time += interval_time(0.5, 0.5)
    var _t1_interval_time = perf_counter_ns()
    var _ns_interval_time = Float64(_t1_interval_time - _t0_interval_time) / Float64(N)
    print("MOJO_TIMING elevator::interval_time", _ns_interval_time, _acc_interval_time)
    var _acc_probable_stops: Float64 = 0.0
    var _t0_probable_stops = perf_counter_ns()
    for _ in range(N):
        _acc_probable_stops += probable_stops(0.5, 0.5)
    var _t1_probable_stops = perf_counter_ns()
    var _ns_probable_stops = Float64(_t1_probable_stops - _t0_probable_stops) / Float64(N)
    print("MOJO_TIMING elevator::probable_stops", _ns_probable_stops, _acc_probable_stops)
    var _acc_motor_power: Float64 = 0.0
    var _t0_motor_power = perf_counter_ns()
    for _ in range(N):
        _acc_motor_power += motor_power(0.5, 0.5, 0.5, 0.5)
    var _t1_motor_power = perf_counter_ns()
    var _ns_motor_power = Float64(_t1_motor_power - _t0_motor_power) / Float64(N)
    print("MOJO_TIMING elevator::motor_power", _ns_motor_power, _acc_motor_power)
    var _acc_counterweight_mass: Float64 = 0.0
    var _t0_counterweight_mass = perf_counter_ns()
    for _ in range(N):
        _acc_counterweight_mass += counterweight_mass(0.5, 0.5, 0.5)
    var _t1_counterweight_mass = perf_counter_ns()
    var _ns_counterweight_mass = Float64(_t1_counterweight_mass - _t0_counterweight_mass) / Float64(N)
    print("MOJO_TIMING elevator::counterweight_mass", _ns_counterweight_mass, _acc_counterweight_mass)
    var _acc_shaft_area: Float64 = 0.0
    var _t0_shaft_area = perf_counter_ns()
    for _ in range(N):
        _acc_shaft_area += shaft_area(0.5, 0.5, 0.5)
    var _t1_shaft_area = perf_counter_ns()
    var _ns_shaft_area = Float64(_t1_shaft_area - _t0_shaft_area) / Float64(N)
    print("MOJO_TIMING elevator::shaft_area", _ns_shaft_area, _acc_shaft_area)
    var _acc_annual_energy_consumption: Float64 = 0.0
    var _t0_annual_energy_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_annual_energy_consumption += annual_energy_consumption(0.5, 0.5, 0.5, 0.5)
    var _t1_annual_energy_consumption = perf_counter_ns()
    var _ns_annual_energy_consumption = Float64(_t1_annual_energy_consumption - _t0_annual_energy_consumption) / Float64(N)
    print("MOJO_TIMING elevator::annual_energy_consumption", _ns_annual_energy_consumption, _acc_annual_energy_consumption)
    var _acc_waiting_time_average: Float64 = 0.0
    var _t0_waiting_time_average = perf_counter_ns()
    for _ in range(N):
        _acc_waiting_time_average += waiting_time_average(0.5)
    var _t1_waiting_time_average = perf_counter_ns()
    var _ns_waiting_time_average = Float64(_t1_waiting_time_average - _t0_waiting_time_average) / Float64(N)
    print("MOJO_TIMING elevator::waiting_time_average", _ns_waiting_time_average, _acc_waiting_time_average)
    var _acc_traffic_intensity: Float64 = 0.0
    var _t0_traffic_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_traffic_intensity += traffic_intensity(0.5, 0.5)
    var _t1_traffic_intensity = perf_counter_ns()
    var _ns_traffic_intensity = Float64(_t1_traffic_intensity - _t0_traffic_intensity) / Float64(N)
    print("MOJO_TIMING elevator::traffic_intensity", _ns_traffic_intensity, _acc_traffic_intensity)
    var _acc_rope_factor_of_safety: Float64 = 0.0
    var _t0_rope_factor_of_safety = perf_counter_ns()
    for _ in range(N):
        _acc_rope_factor_of_safety += rope_factor_of_safety(0.5, 0.5)
    var _t1_rope_factor_of_safety = perf_counter_ns()
    var _ns_rope_factor_of_safety = Float64(_t1_rope_factor_of_safety - _t0_rope_factor_of_safety) / Float64(N)
    print("MOJO_TIMING elevator::rope_factor_of_safety", _ns_rope_factor_of_safety, _acc_rope_factor_of_safety)
    var _acc_pit_depth_requirement: Float64 = 0.0
    var _t0_pit_depth_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_pit_depth_requirement += pit_depth_requirement(0.5)
    var _t1_pit_depth_requirement = perf_counter_ns()
    var _ns_pit_depth_requirement = Float64(_t1_pit_depth_requirement - _t0_pit_depth_requirement) / Float64(N)
    print("MOJO_TIMING elevator::pit_depth_requirement", _ns_pit_depth_requirement, _acc_pit_depth_requirement)
