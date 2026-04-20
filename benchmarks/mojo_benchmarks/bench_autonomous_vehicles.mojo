"""bench_autonomous_vehicles.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from autonomous_vehicles import safe_following_distance, time_to_collision, braking_distance, sensor_range_required, lane_change_distance, perception_latency_distance, comfort_deceleration, emergency_deceleration, headway_time, fuel_efficiency_at_speed, v2x_communication_range, localization_error_gps
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

    var _acc_safe_following_distance: Float64 = 0.0
    var _t0_safe_following_distance = perf_counter_ns()
    for _ in range(N):
        _acc_safe_following_distance += safe_following_distance(0.5, 0.5, 0.5)
    var _t1_safe_following_distance = perf_counter_ns()
    var _ns_safe_following_distance = Float64(_t1_safe_following_distance - _t0_safe_following_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::safe_following_distance", _ns_safe_following_distance, _acc_safe_following_distance)
    var _acc_time_to_collision: Float64 = 0.0
    var _t0_time_to_collision = perf_counter_ns()
    for _ in range(N):
        _acc_time_to_collision += time_to_collision(0.5, 0.5)
    var _t1_time_to_collision = perf_counter_ns()
    var _ns_time_to_collision = Float64(_t1_time_to_collision - _t0_time_to_collision) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::time_to_collision", _ns_time_to_collision, _acc_time_to_collision)
    var _acc_braking_distance: Float64 = 0.0
    var _t0_braking_distance = perf_counter_ns()
    for _ in range(N):
        _acc_braking_distance += braking_distance(0.5, 0.5, 0.5)
    var _t1_braking_distance = perf_counter_ns()
    var _ns_braking_distance = Float64(_t1_braking_distance - _t0_braking_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::braking_distance", _ns_braking_distance, _acc_braking_distance)
    var _acc_sensor_range_required: Float64 = 0.0
    var _t0_sensor_range_required = perf_counter_ns()
    for _ in range(N):
        _acc_sensor_range_required += sensor_range_required(0.5, 0.5, 0.5)
    var _t1_sensor_range_required = perf_counter_ns()
    var _ns_sensor_range_required = Float64(_t1_sensor_range_required - _t0_sensor_range_required) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::sensor_range_required", _ns_sensor_range_required, _acc_sensor_range_required)
    var _acc_lane_change_distance: Float64 = 0.0
    var _t0_lane_change_distance = perf_counter_ns()
    for _ in range(N):
        _acc_lane_change_distance += lane_change_distance(0.5, 0.5, 0.5)
    var _t1_lane_change_distance = perf_counter_ns()
    var _ns_lane_change_distance = Float64(_t1_lane_change_distance - _t0_lane_change_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::lane_change_distance", _ns_lane_change_distance, _acc_lane_change_distance)
    var _acc_perception_latency_distance: Float64 = 0.0
    var _t0_perception_latency_distance = perf_counter_ns()
    for _ in range(N):
        _acc_perception_latency_distance += perception_latency_distance(0.5, 0.5)
    var _t1_perception_latency_distance = perf_counter_ns()
    var _ns_perception_latency_distance = Float64(_t1_perception_latency_distance - _t0_perception_latency_distance) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::perception_latency_distance", _ns_perception_latency_distance, _acc_perception_latency_distance)
    var _acc_comfort_deceleration: Float64 = 0.0
    var _t0_comfort_deceleration = perf_counter_ns()
    for _ in range(N):
        _acc_comfort_deceleration += comfort_deceleration()
    var _t1_comfort_deceleration = perf_counter_ns()
    var _ns_comfort_deceleration = Float64(_t1_comfort_deceleration - _t0_comfort_deceleration) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::comfort_deceleration", _ns_comfort_deceleration, _acc_comfort_deceleration)
    var _acc_emergency_deceleration: Float64 = 0.0
    var _t0_emergency_deceleration = perf_counter_ns()
    for _ in range(N):
        _acc_emergency_deceleration += emergency_deceleration()
    var _t1_emergency_deceleration = perf_counter_ns()
    var _ns_emergency_deceleration = Float64(_t1_emergency_deceleration - _t0_emergency_deceleration) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::emergency_deceleration", _ns_emergency_deceleration, _acc_emergency_deceleration)
    var _acc_headway_time: Float64 = 0.0
    var _t0_headway_time = perf_counter_ns()
    for _ in range(N):
        _acc_headway_time += headway_time(0.5, 0.5)
    var _t1_headway_time = perf_counter_ns()
    var _ns_headway_time = Float64(_t1_headway_time - _t0_headway_time) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::headway_time", _ns_headway_time, _acc_headway_time)
    var _acc_fuel_efficiency_at_speed: Float64 = 0.0
    var _t0_fuel_efficiency_at_speed = perf_counter_ns()
    for _ in range(N):
        _acc_fuel_efficiency_at_speed += fuel_efficiency_at_speed(0.5, 0.5, 0.5)
    var _t1_fuel_efficiency_at_speed = perf_counter_ns()
    var _ns_fuel_efficiency_at_speed = Float64(_t1_fuel_efficiency_at_speed - _t0_fuel_efficiency_at_speed) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::fuel_efficiency_at_speed", _ns_fuel_efficiency_at_speed, _acc_fuel_efficiency_at_speed)
    var _acc_v2x_communication_range: Float64 = 0.0
    var _t0_v2x_communication_range = perf_counter_ns()
    for _ in range(N):
        _acc_v2x_communication_range += v2x_communication_range(0.5, 0.5, 0.5)
    var _t1_v2x_communication_range = perf_counter_ns()
    var _ns_v2x_communication_range = Float64(_t1_v2x_communication_range - _t0_v2x_communication_range) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::v2x_communication_range", _ns_v2x_communication_range, _acc_v2x_communication_range)
    var _acc_localization_error_gps: Float64 = 0.0
    var _t0_localization_error_gps = perf_counter_ns()
    for _ in range(N):
        _acc_localization_error_gps += localization_error_gps(0.5, 0.5)
    var _t1_localization_error_gps = perf_counter_ns()
    var _ns_localization_error_gps = Float64(_t1_localization_error_gps - _t0_localization_error_gps) / Float64(N)
    print("MOJO_TIMING autonomous_vehicles::localization_error_gps", _ns_localization_error_gps, _acc_localization_error_gps)
