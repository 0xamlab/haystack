"""bench_elevator.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from elevator import round_trip_time, handling_capacity, interval_time, probable_stops, motor_power, counterweight_mass, shaft_area, annual_energy_consumption, waiting_time_average, traffic_intensity, rope_factor_of_safety, pit_depth_requirement
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_round_trip_time = round_trip_time(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_round_trip_time = _summary_float64(_result_round_trip_time)
    print("MOJO_RESULT elevator::round_trip_time", _summary_round_trip_time)
    var _acc_handling_capacity: Float64 = 0.0
    var _t0_handling_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_handling_capacity += handling_capacity(0.5, 0.5)
    var _t1_handling_capacity = perf_counter_ns()
    var _ns_handling_capacity = Float64(_t1_handling_capacity - _t0_handling_capacity) / Float64(N)
    print("MOJO_TIMING elevator::handling_capacity", _ns_handling_capacity, _acc_handling_capacity)
    var _result_handling_capacity = handling_capacity(0.5, 0.5)
    var _summary_handling_capacity = _summary_float64(_result_handling_capacity)
    print("MOJO_RESULT elevator::handling_capacity", _summary_handling_capacity)
    var _acc_interval_time: Float64 = 0.0
    var _t0_interval_time = perf_counter_ns()
    for _ in range(N):
        _acc_interval_time += interval_time(0.5, 0.5)
    var _t1_interval_time = perf_counter_ns()
    var _ns_interval_time = Float64(_t1_interval_time - _t0_interval_time) / Float64(N)
    print("MOJO_TIMING elevator::interval_time", _ns_interval_time, _acc_interval_time)
    var _result_interval_time = interval_time(0.5, 0.5)
    var _summary_interval_time = _summary_float64(_result_interval_time)
    print("MOJO_RESULT elevator::interval_time", _summary_interval_time)
    var _acc_probable_stops: Float64 = 0.0
    var _t0_probable_stops = perf_counter_ns()
    for _ in range(N):
        _acc_probable_stops += probable_stops(0.5, 0.5)
    var _t1_probable_stops = perf_counter_ns()
    var _ns_probable_stops = Float64(_t1_probable_stops - _t0_probable_stops) / Float64(N)
    print("MOJO_TIMING elevator::probable_stops", _ns_probable_stops, _acc_probable_stops)
    var _result_probable_stops = probable_stops(0.5, 0.5)
    var _summary_probable_stops = _summary_float64(_result_probable_stops)
    print("MOJO_RESULT elevator::probable_stops", _summary_probable_stops)
    var _acc_motor_power: Float64 = 0.0
    var _t0_motor_power = perf_counter_ns()
    for _ in range(N):
        _acc_motor_power += motor_power(0.5, 0.5, 0.5, 0.5)
    var _t1_motor_power = perf_counter_ns()
    var _ns_motor_power = Float64(_t1_motor_power - _t0_motor_power) / Float64(N)
    print("MOJO_TIMING elevator::motor_power", _ns_motor_power, _acc_motor_power)
    var _result_motor_power = motor_power(0.5, 0.5, 0.5, 0.5)
    var _summary_motor_power = _summary_float64(_result_motor_power)
    print("MOJO_RESULT elevator::motor_power", _summary_motor_power)
    var _acc_counterweight_mass: Float64 = 0.0
    var _t0_counterweight_mass = perf_counter_ns()
    for _ in range(N):
        _acc_counterweight_mass += counterweight_mass(0.5, 0.5, 0.5)
    var _t1_counterweight_mass = perf_counter_ns()
    var _ns_counterweight_mass = Float64(_t1_counterweight_mass - _t0_counterweight_mass) / Float64(N)
    print("MOJO_TIMING elevator::counterweight_mass", _ns_counterweight_mass, _acc_counterweight_mass)
    var _result_counterweight_mass = counterweight_mass(0.5, 0.5, 0.5)
    var _summary_counterweight_mass = _summary_float64(_result_counterweight_mass)
    print("MOJO_RESULT elevator::counterweight_mass", _summary_counterweight_mass)
    var _acc_shaft_area: Float64 = 0.0
    var _t0_shaft_area = perf_counter_ns()
    for _ in range(N):
        _acc_shaft_area += shaft_area(0.5, 0.5, 0.5)
    var _t1_shaft_area = perf_counter_ns()
    var _ns_shaft_area = Float64(_t1_shaft_area - _t0_shaft_area) / Float64(N)
    print("MOJO_TIMING elevator::shaft_area", _ns_shaft_area, _acc_shaft_area)
    var _result_shaft_area = shaft_area(0.5, 0.5, 0.5)
    var _summary_shaft_area = _summary_float64(_result_shaft_area)
    print("MOJO_RESULT elevator::shaft_area", _summary_shaft_area)
    var _acc_annual_energy_consumption: Float64 = 0.0
    var _t0_annual_energy_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_annual_energy_consumption += annual_energy_consumption(0.5, 0.5, 0.5, 0.5)
    var _t1_annual_energy_consumption = perf_counter_ns()
    var _ns_annual_energy_consumption = Float64(_t1_annual_energy_consumption - _t0_annual_energy_consumption) / Float64(N)
    print("MOJO_TIMING elevator::annual_energy_consumption", _ns_annual_energy_consumption, _acc_annual_energy_consumption)
    var _result_annual_energy_consumption = annual_energy_consumption(0.5, 0.5, 0.5, 0.5)
    var _summary_annual_energy_consumption = _summary_float64(_result_annual_energy_consumption)
    print("MOJO_RESULT elevator::annual_energy_consumption", _summary_annual_energy_consumption)
    var _acc_waiting_time_average: Float64 = 0.0
    var _t0_waiting_time_average = perf_counter_ns()
    for _ in range(N):
        _acc_waiting_time_average += waiting_time_average(0.5)
    var _t1_waiting_time_average = perf_counter_ns()
    var _ns_waiting_time_average = Float64(_t1_waiting_time_average - _t0_waiting_time_average) / Float64(N)
    print("MOJO_TIMING elevator::waiting_time_average", _ns_waiting_time_average, _acc_waiting_time_average)
    var _result_waiting_time_average = waiting_time_average(0.5)
    var _summary_waiting_time_average = _summary_float64(_result_waiting_time_average)
    print("MOJO_RESULT elevator::waiting_time_average", _summary_waiting_time_average)
    var _acc_traffic_intensity: Float64 = 0.0
    var _t0_traffic_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_traffic_intensity += traffic_intensity(0.5, 0.5)
    var _t1_traffic_intensity = perf_counter_ns()
    var _ns_traffic_intensity = Float64(_t1_traffic_intensity - _t0_traffic_intensity) / Float64(N)
    print("MOJO_TIMING elevator::traffic_intensity", _ns_traffic_intensity, _acc_traffic_intensity)
    var _result_traffic_intensity = traffic_intensity(0.5, 0.5)
    var _summary_traffic_intensity = _summary_float64(_result_traffic_intensity)
    print("MOJO_RESULT elevator::traffic_intensity", _summary_traffic_intensity)
    var _acc_rope_factor_of_safety: Float64 = 0.0
    var _t0_rope_factor_of_safety = perf_counter_ns()
    for _ in range(N):
        _acc_rope_factor_of_safety += rope_factor_of_safety(0.5, 0.5)
    var _t1_rope_factor_of_safety = perf_counter_ns()
    var _ns_rope_factor_of_safety = Float64(_t1_rope_factor_of_safety - _t0_rope_factor_of_safety) / Float64(N)
    print("MOJO_TIMING elevator::rope_factor_of_safety", _ns_rope_factor_of_safety, _acc_rope_factor_of_safety)
    var _result_rope_factor_of_safety = rope_factor_of_safety(0.5, 0.5)
    var _summary_rope_factor_of_safety = _summary_float64(_result_rope_factor_of_safety)
    print("MOJO_RESULT elevator::rope_factor_of_safety", _summary_rope_factor_of_safety)
    var _acc_pit_depth_requirement: Float64 = 0.0
    var _t0_pit_depth_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_pit_depth_requirement += pit_depth_requirement(0.5)
    var _t1_pit_depth_requirement = perf_counter_ns()
    var _ns_pit_depth_requirement = Float64(_t1_pit_depth_requirement - _t0_pit_depth_requirement) / Float64(N)
    print("MOJO_TIMING elevator::pit_depth_requirement", _ns_pit_depth_requirement, _acc_pit_depth_requirement)
    var _result_pit_depth_requirement = pit_depth_requirement(0.5)
    var _summary_pit_depth_requirement = _summary_float64(_result_pit_depth_requirement)
    print("MOJO_RESULT elevator::pit_depth_requirement", _summary_pit_depth_requirement)
