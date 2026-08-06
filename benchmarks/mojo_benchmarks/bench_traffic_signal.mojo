"""bench_traffic_signal.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from traffic_signal import cycle_length_webster, effective_green, green_ratio, capacity_lane, volume_to_capacity, delay_uniform, pedestrian_crossing_time, yellow_interval, all_red_interval, level_of_service_delay, intersection_capacity_utilization, peak_hour_factor
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

    var _acc_cycle_length_webster: Float64 = 0.0
    var _t0_cycle_length_webster = perf_counter_ns()
    for _ in range(N):
        _acc_cycle_length_webster += cycle_length_webster(0.5, 0.5)
    var _t1_cycle_length_webster = perf_counter_ns()
    var _ns_cycle_length_webster = Float64(_t1_cycle_length_webster - _t0_cycle_length_webster) / Float64(N)
    print("MOJO_TIMING traffic_signal::cycle_length_webster", _ns_cycle_length_webster, _acc_cycle_length_webster)
    var _result_cycle_length_webster = cycle_length_webster(0.5, 0.5)
    var _summary_cycle_length_webster = _summary_float64(_result_cycle_length_webster)
    print("MOJO_RESULT traffic_signal::cycle_length_webster", _summary_cycle_length_webster)
    var _acc_effective_green: Float64 = 0.0
    var _t0_effective_green = perf_counter_ns()
    for _ in range(N):
        _acc_effective_green += effective_green(0.5, 0.5, 0.5)
    var _t1_effective_green = perf_counter_ns()
    var _ns_effective_green = Float64(_t1_effective_green - _t0_effective_green) / Float64(N)
    print("MOJO_TIMING traffic_signal::effective_green", _ns_effective_green, _acc_effective_green)
    var _result_effective_green = effective_green(0.5, 0.5, 0.5)
    var _summary_effective_green = _summary_float64(_result_effective_green)
    print("MOJO_RESULT traffic_signal::effective_green", _summary_effective_green)
    var _acc_green_ratio: Float64 = 0.0
    var _t0_green_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_green_ratio += green_ratio(0.5, 0.5)
    var _t1_green_ratio = perf_counter_ns()
    var _ns_green_ratio = Float64(_t1_green_ratio - _t0_green_ratio) / Float64(N)
    print("MOJO_TIMING traffic_signal::green_ratio", _ns_green_ratio, _acc_green_ratio)
    var _result_green_ratio = green_ratio(0.5, 0.5)
    var _summary_green_ratio = _summary_float64(_result_green_ratio)
    print("MOJO_RESULT traffic_signal::green_ratio", _summary_green_ratio)
    var _acc_capacity_lane: Float64 = 0.0
    var _t0_capacity_lane = perf_counter_ns()
    for _ in range(N):
        _acc_capacity_lane += capacity_lane(0.5, 0.5)
    var _t1_capacity_lane = perf_counter_ns()
    var _ns_capacity_lane = Float64(_t1_capacity_lane - _t0_capacity_lane) / Float64(N)
    print("MOJO_TIMING traffic_signal::capacity_lane", _ns_capacity_lane, _acc_capacity_lane)
    var _result_capacity_lane = capacity_lane(0.5, 0.5)
    var _summary_capacity_lane = _summary_float64(_result_capacity_lane)
    print("MOJO_RESULT traffic_signal::capacity_lane", _summary_capacity_lane)
    var _acc_volume_to_capacity: Float64 = 0.0
    var _t0_volume_to_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_volume_to_capacity += volume_to_capacity(0.5, 0.5)
    var _t1_volume_to_capacity = perf_counter_ns()
    var _ns_volume_to_capacity = Float64(_t1_volume_to_capacity - _t0_volume_to_capacity) / Float64(N)
    print("MOJO_TIMING traffic_signal::volume_to_capacity", _ns_volume_to_capacity, _acc_volume_to_capacity)
    var _result_volume_to_capacity = volume_to_capacity(0.5, 0.5)
    var _summary_volume_to_capacity = _summary_float64(_result_volume_to_capacity)
    print("MOJO_RESULT traffic_signal::volume_to_capacity", _summary_volume_to_capacity)
    var _acc_delay_uniform: Float64 = 0.0
    var _t0_delay_uniform = perf_counter_ns()
    for _ in range(N):
        _acc_delay_uniform += delay_uniform(0.5, 0.5, 0.5)
    var _t1_delay_uniform = perf_counter_ns()
    var _ns_delay_uniform = Float64(_t1_delay_uniform - _t0_delay_uniform) / Float64(N)
    print("MOJO_TIMING traffic_signal::delay_uniform", _ns_delay_uniform, _acc_delay_uniform)
    var _result_delay_uniform = delay_uniform(0.5, 0.5, 0.5)
    var _summary_delay_uniform = _summary_float64(_result_delay_uniform)
    print("MOJO_RESULT traffic_signal::delay_uniform", _summary_delay_uniform)
    var _acc_pedestrian_crossing_time: Float64 = 0.0
    var _t0_pedestrian_crossing_time = perf_counter_ns()
    for _ in range(N):
        _acc_pedestrian_crossing_time += pedestrian_crossing_time(0.5, 0.5)
    var _t1_pedestrian_crossing_time = perf_counter_ns()
    var _ns_pedestrian_crossing_time = Float64(_t1_pedestrian_crossing_time - _t0_pedestrian_crossing_time) / Float64(N)
    print("MOJO_TIMING traffic_signal::pedestrian_crossing_time", _ns_pedestrian_crossing_time, _acc_pedestrian_crossing_time)
    var _result_pedestrian_crossing_time = pedestrian_crossing_time(0.5, 0.5)
    var _summary_pedestrian_crossing_time = _summary_float64(_result_pedestrian_crossing_time)
    print("MOJO_RESULT traffic_signal::pedestrian_crossing_time", _summary_pedestrian_crossing_time)
    var _acc_yellow_interval: Float64 = 0.0
    var _t0_yellow_interval = perf_counter_ns()
    for _ in range(N):
        _acc_yellow_interval += yellow_interval(0.5, 0.5, 0.5, 0.5)
    var _t1_yellow_interval = perf_counter_ns()
    var _ns_yellow_interval = Float64(_t1_yellow_interval - _t0_yellow_interval) / Float64(N)
    print("MOJO_TIMING traffic_signal::yellow_interval", _ns_yellow_interval, _acc_yellow_interval)
    var _result_yellow_interval = yellow_interval(0.5, 0.5, 0.5, 0.5)
    var _summary_yellow_interval = _summary_float64(_result_yellow_interval)
    print("MOJO_RESULT traffic_signal::yellow_interval", _summary_yellow_interval)
    var _acc_all_red_interval: Float64 = 0.0
    var _t0_all_red_interval = perf_counter_ns()
    for _ in range(N):
        _acc_all_red_interval += all_red_interval(0.5, 0.5, 0.5)
    var _t1_all_red_interval = perf_counter_ns()
    var _ns_all_red_interval = Float64(_t1_all_red_interval - _t0_all_red_interval) / Float64(N)
    print("MOJO_TIMING traffic_signal::all_red_interval", _ns_all_red_interval, _acc_all_red_interval)
    var _result_all_red_interval = all_red_interval(0.5, 0.5, 0.5)
    var _summary_all_red_interval = _summary_float64(_result_all_red_interval)
    print("MOJO_RESULT traffic_signal::all_red_interval", _summary_all_red_interval)
    var _acc_level_of_service_delay: Float64 = 0.0
    var _t0_level_of_service_delay = perf_counter_ns()
    for _ in range(N):
        _acc_level_of_service_delay += Float64(level_of_service_delay(0.5))
    var _t1_level_of_service_delay = perf_counter_ns()
    var _ns_level_of_service_delay = Float64(_t1_level_of_service_delay - _t0_level_of_service_delay) / Float64(N)
    print("MOJO_TIMING traffic_signal::level_of_service_delay", _ns_level_of_service_delay, _acc_level_of_service_delay)
    var _result_level_of_service_delay = level_of_service_delay(0.5)
    var _summary_level_of_service_delay = _summary_int(_result_level_of_service_delay)
    print("MOJO_RESULT traffic_signal::level_of_service_delay", _summary_level_of_service_delay)
    var _acc_intersection_capacity_utilization: Float64 = 0.0
    var _t0_intersection_capacity_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_intersection_capacity_utilization += intersection_capacity_utilization(0.5, 0.5, 0.5)
    var _t1_intersection_capacity_utilization = perf_counter_ns()
    var _ns_intersection_capacity_utilization = Float64(_t1_intersection_capacity_utilization - _t0_intersection_capacity_utilization) / Float64(N)
    print("MOJO_TIMING traffic_signal::intersection_capacity_utilization", _ns_intersection_capacity_utilization, _acc_intersection_capacity_utilization)
    var _result_intersection_capacity_utilization = intersection_capacity_utilization(0.5, 0.5, 0.5)
    var _summary_intersection_capacity_utilization = _summary_float64(_result_intersection_capacity_utilization)
    print("MOJO_RESULT traffic_signal::intersection_capacity_utilization", _summary_intersection_capacity_utilization)
    var _acc_peak_hour_factor: Float64 = 0.0
    var _t0_peak_hour_factor = perf_counter_ns()
    for _ in range(N):
        _acc_peak_hour_factor += peak_hour_factor(0.5, 0.5)
    var _t1_peak_hour_factor = perf_counter_ns()
    var _ns_peak_hour_factor = Float64(_t1_peak_hour_factor - _t0_peak_hour_factor) / Float64(N)
    print("MOJO_TIMING traffic_signal::peak_hour_factor", _ns_peak_hour_factor, _acc_peak_hour_factor)
    var _result_peak_hour_factor = peak_hour_factor(0.5, 0.5)
    var _summary_peak_hour_factor = _summary_float64(_result_peak_hour_factor)
    print("MOJO_RESULT traffic_signal::peak_hour_factor", _summary_peak_hour_factor)
