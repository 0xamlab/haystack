"""bench_autonomous_vehicles.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from autonomous_vehicles import safe_following_distance, time_to_collision, braking_distance, sensor_range_required, lane_change_distance, perception_latency_distance, comfort_deceleration, emergency_deceleration, headway_time, fuel_efficiency_at_speed, v2x_communication_range, localization_error_gps
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_safe_following_distance: Float64 = 0.0
    var _t0_safe_following_distance = perf_counter_ns()
    for _ in range(N):
        _acc_safe_following_distance += safe_following_distance(0.5, 0.5, 0.5)
    var _t1_safe_following_distance = perf_counter_ns()
    var _ns_safe_following_distance = Float64(_t1_safe_following_distance - _t0_safe_following_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::safe_following_distance", _ns_safe_following_distance, _acc_safe_following_distance)
    var _result_safe_following_distance = safe_following_distance(0.5, 0.5, 0.5)
    var _summary_safe_following_distance = _summary_float64(_result_safe_following_distance)
    print("MOJO_RESULT autonomous_vehicles::safe_following_distance", _summary_safe_following_distance)
    var _acc_time_to_collision: Float64 = 0.0
    var _t0_time_to_collision = perf_counter_ns()
    for _ in range(N):
        _acc_time_to_collision += time_to_collision(0.5, 0.5)
    var _t1_time_to_collision = perf_counter_ns()
    var _ns_time_to_collision = Float64(_t1_time_to_collision - _t0_time_to_collision) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::time_to_collision", _ns_time_to_collision, _acc_time_to_collision)
    var _result_time_to_collision = time_to_collision(0.5, 0.5)
    var _summary_time_to_collision = _summary_float64(_result_time_to_collision)
    print("MOJO_RESULT autonomous_vehicles::time_to_collision", _summary_time_to_collision)
    var _acc_braking_distance: Float64 = 0.0
    var _t0_braking_distance = perf_counter_ns()
    for _ in range(N):
        _acc_braking_distance += braking_distance(0.5, 0.5, 0.5)
    var _t1_braking_distance = perf_counter_ns()
    var _ns_braking_distance = Float64(_t1_braking_distance - _t0_braking_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::braking_distance", _ns_braking_distance, _acc_braking_distance)
    var _result_braking_distance = braking_distance(0.5, 0.5, 0.5)
    var _summary_braking_distance = _summary_float64(_result_braking_distance)
    print("MOJO_RESULT autonomous_vehicles::braking_distance", _summary_braking_distance)
    var _acc_sensor_range_required: Float64 = 0.0
    var _t0_sensor_range_required = perf_counter_ns()
    for _ in range(N):
        _acc_sensor_range_required += sensor_range_required(0.5, 0.5, 0.5)
    var _t1_sensor_range_required = perf_counter_ns()
    var _ns_sensor_range_required = Float64(_t1_sensor_range_required - _t0_sensor_range_required) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::sensor_range_required", _ns_sensor_range_required, _acc_sensor_range_required)
    var _result_sensor_range_required = sensor_range_required(0.5, 0.5, 0.5)
    var _summary_sensor_range_required = _summary_float64(_result_sensor_range_required)
    print("MOJO_RESULT autonomous_vehicles::sensor_range_required", _summary_sensor_range_required)
    var _acc_lane_change_distance: Float64 = 0.0
    var _t0_lane_change_distance = perf_counter_ns()
    for _ in range(N):
        _acc_lane_change_distance += lane_change_distance(0.5, 0.5, 0.5)
    var _t1_lane_change_distance = perf_counter_ns()
    var _ns_lane_change_distance = Float64(_t1_lane_change_distance - _t0_lane_change_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::lane_change_distance", _ns_lane_change_distance, _acc_lane_change_distance)
    var _result_lane_change_distance = lane_change_distance(0.5, 0.5, 0.5)
    var _summary_lane_change_distance = _summary_float64(_result_lane_change_distance)
    print("MOJO_RESULT autonomous_vehicles::lane_change_distance", _summary_lane_change_distance)
    var _acc_perception_latency_distance: Float64 = 0.0
    var _t0_perception_latency_distance = perf_counter_ns()
    for _ in range(N):
        _acc_perception_latency_distance += perception_latency_distance(0.5, 0.5)
    var _t1_perception_latency_distance = perf_counter_ns()
    var _ns_perception_latency_distance = Float64(_t1_perception_latency_distance - _t0_perception_latency_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::perception_latency_distance", _ns_perception_latency_distance, _acc_perception_latency_distance)
    var _result_perception_latency_distance = perception_latency_distance(0.5, 0.5)
    var _summary_perception_latency_distance = _summary_float64(_result_perception_latency_distance)
    print("MOJO_RESULT autonomous_vehicles::perception_latency_distance", _summary_perception_latency_distance)
    var _acc_comfort_deceleration: Float64 = 0.0
    var _t0_comfort_deceleration = perf_counter_ns()
    for _ in range(N):
        _acc_comfort_deceleration += comfort_deceleration()
    var _t1_comfort_deceleration = perf_counter_ns()
    var _ns_comfort_deceleration = Float64(_t1_comfort_deceleration - _t0_comfort_deceleration) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::comfort_deceleration", _ns_comfort_deceleration, _acc_comfort_deceleration)
    var _result_comfort_deceleration = comfort_deceleration()
    var _summary_comfort_deceleration = _summary_float64(_result_comfort_deceleration)
    print("MOJO_RESULT autonomous_vehicles::comfort_deceleration", _summary_comfort_deceleration)
    var _acc_emergency_deceleration: Float64 = 0.0
    var _t0_emergency_deceleration = perf_counter_ns()
    for _ in range(N):
        _acc_emergency_deceleration += emergency_deceleration()
    var _t1_emergency_deceleration = perf_counter_ns()
    var _ns_emergency_deceleration = Float64(_t1_emergency_deceleration - _t0_emergency_deceleration) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::emergency_deceleration", _ns_emergency_deceleration, _acc_emergency_deceleration)
    var _result_emergency_deceleration = emergency_deceleration()
    var _summary_emergency_deceleration = _summary_float64(_result_emergency_deceleration)
    print("MOJO_RESULT autonomous_vehicles::emergency_deceleration", _summary_emergency_deceleration)
    var _acc_headway_time: Float64 = 0.0
    var _t0_headway_time = perf_counter_ns()
    for _ in range(N):
        _acc_headway_time += headway_time(0.5, 0.5)
    var _t1_headway_time = perf_counter_ns()
    var _ns_headway_time = Float64(_t1_headway_time - _t0_headway_time) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::headway_time", _ns_headway_time, _acc_headway_time)
    var _result_headway_time = headway_time(0.5, 0.5)
    var _summary_headway_time = _summary_float64(_result_headway_time)
    print("MOJO_RESULT autonomous_vehicles::headway_time", _summary_headway_time)
    var _acc_fuel_efficiency_at_speed: Float64 = 0.0
    var _t0_fuel_efficiency_at_speed = perf_counter_ns()
    for _ in range(N):
        _acc_fuel_efficiency_at_speed += fuel_efficiency_at_speed(0.5, 0.5, 0.5)
    var _t1_fuel_efficiency_at_speed = perf_counter_ns()
    var _ns_fuel_efficiency_at_speed = Float64(_t1_fuel_efficiency_at_speed - _t0_fuel_efficiency_at_speed) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::fuel_efficiency_at_speed", _ns_fuel_efficiency_at_speed, _acc_fuel_efficiency_at_speed)
    var _result_fuel_efficiency_at_speed = fuel_efficiency_at_speed(0.5, 0.5, 0.5)
    var _summary_fuel_efficiency_at_speed = _summary_float64(_result_fuel_efficiency_at_speed)
    print("MOJO_RESULT autonomous_vehicles::fuel_efficiency_at_speed", _summary_fuel_efficiency_at_speed)
    var _acc_v2x_communication_range: Float64 = 0.0
    var _t0_v2x_communication_range = perf_counter_ns()
    for _ in range(N):
        _acc_v2x_communication_range += v2x_communication_range(0.5, 0.5, 0.5)
    var _t1_v2x_communication_range = perf_counter_ns()
    var _ns_v2x_communication_range = Float64(_t1_v2x_communication_range - _t0_v2x_communication_range) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::v2x_communication_range", _ns_v2x_communication_range, _acc_v2x_communication_range)
    var _result_v2x_communication_range = v2x_communication_range(0.5, 0.5, 0.5)
    var _summary_v2x_communication_range = _summary_float64(_result_v2x_communication_range)
    print("MOJO_RESULT autonomous_vehicles::v2x_communication_range", _summary_v2x_communication_range)
    var _acc_localization_error_gps: Float64 = 0.0
    var _t0_localization_error_gps = perf_counter_ns()
    for _ in range(N):
        _acc_localization_error_gps += localization_error_gps(0.5, 0.5)
    var _t1_localization_error_gps = perf_counter_ns()
    var _ns_localization_error_gps = Float64(_t1_localization_error_gps - _t0_localization_error_gps) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::localization_error_gps", _ns_localization_error_gps, _acc_localization_error_gps)
    var _result_localization_error_gps = localization_error_gps(0.5, 0.5)
    var _summary_localization_error_gps = _summary_float64(_result_localization_error_gps)
    print("MOJO_RESULT autonomous_vehicles::localization_error_gps", _summary_localization_error_gps)
