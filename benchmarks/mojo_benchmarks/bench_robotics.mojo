"""bench_robotics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from robotics import forward_kinematics_2dof, forward_kinematics_2dof_y, inverse_kinematics_2dof_theta2, jacobian_2dof_j11, pid_control, dead_reckoning_x, dead_reckoning_y, wheel_odometry_distance, differential_drive_omega, differential_drive_velocity, workspace_radius, manipulability_index
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

    var _acc_forward_kinematics_2dof: Float64 = 0.0
    var _t0_forward_kinematics_2dof = perf_counter_ns()
    for _ in range(N):
        _acc_forward_kinematics_2dof += forward_kinematics_2dof(0.5, 0.5, 0.5, 0.5)
    var _t1_forward_kinematics_2dof = perf_counter_ns()
    var _ns_forward_kinematics_2dof = Float64(_t1_forward_kinematics_2dof - _t0_forward_kinematics_2dof) / Float64(N)
    print("MOJO_TIMING robotics::forward_kinematics_2dof", _ns_forward_kinematics_2dof, _acc_forward_kinematics_2dof)
    var _result_forward_kinematics_2dof = forward_kinematics_2dof(0.5, 0.5, 0.5, 0.5)
    var _summary_forward_kinematics_2dof = _summary_float64(_result_forward_kinematics_2dof)
    print("MOJO_RESULT robotics::forward_kinematics_2dof", _summary_forward_kinematics_2dof)
    var _acc_forward_kinematics_2dof_y: Float64 = 0.0
    var _t0_forward_kinematics_2dof_y = perf_counter_ns()
    for _ in range(N):
        _acc_forward_kinematics_2dof_y += forward_kinematics_2dof_y(0.5, 0.5, 0.5, 0.5)
    var _t1_forward_kinematics_2dof_y = perf_counter_ns()
    var _ns_forward_kinematics_2dof_y = Float64(_t1_forward_kinematics_2dof_y - _t0_forward_kinematics_2dof_y) / Float64(N)
    print("MOJO_TIMING robotics::forward_kinematics_2dof_y", _ns_forward_kinematics_2dof_y, _acc_forward_kinematics_2dof_y)
    var _result_forward_kinematics_2dof_y = forward_kinematics_2dof_y(0.5, 0.5, 0.5, 0.5)
    var _summary_forward_kinematics_2dof_y = _summary_float64(_result_forward_kinematics_2dof_y)
    print("MOJO_RESULT robotics::forward_kinematics_2dof_y", _summary_forward_kinematics_2dof_y)
    var _acc_inverse_kinematics_2dof_theta2: Float64 = 0.0
    var _t0_inverse_kinematics_2dof_theta2 = perf_counter_ns()
    for _ in range(N):
        _acc_inverse_kinematics_2dof_theta2 += inverse_kinematics_2dof_theta2(0.5, 0.5, 0.5, 0.5)
    var _t1_inverse_kinematics_2dof_theta2 = perf_counter_ns()
    var _ns_inverse_kinematics_2dof_theta2 = Float64(_t1_inverse_kinematics_2dof_theta2 - _t0_inverse_kinematics_2dof_theta2) / Float64(N)
    print("MOJO_TIMING robotics::inverse_kinematics_2dof_theta2", _ns_inverse_kinematics_2dof_theta2, _acc_inverse_kinematics_2dof_theta2)
    var _result_inverse_kinematics_2dof_theta2 = inverse_kinematics_2dof_theta2(0.5, 0.5, 0.5, 0.5)
    var _summary_inverse_kinematics_2dof_theta2 = _summary_float64(_result_inverse_kinematics_2dof_theta2)
    print("MOJO_RESULT robotics::inverse_kinematics_2dof_theta2", _summary_inverse_kinematics_2dof_theta2)
    var _acc_jacobian_2dof_j11: Float64 = 0.0
    var _t0_jacobian_2dof_j11 = perf_counter_ns()
    for _ in range(N):
        _acc_jacobian_2dof_j11 += jacobian_2dof_j11(0.5, 0.5, 0.5, 0.5)
    var _t1_jacobian_2dof_j11 = perf_counter_ns()
    var _ns_jacobian_2dof_j11 = Float64(_t1_jacobian_2dof_j11 - _t0_jacobian_2dof_j11) / Float64(N)
    print("MOJO_TIMING robotics::jacobian_2dof_j11", _ns_jacobian_2dof_j11, _acc_jacobian_2dof_j11)
    var _result_jacobian_2dof_j11 = jacobian_2dof_j11(0.5, 0.5, 0.5, 0.5)
    var _summary_jacobian_2dof_j11 = _summary_float64(_result_jacobian_2dof_j11)
    print("MOJO_RESULT robotics::jacobian_2dof_j11", _summary_jacobian_2dof_j11)
    var _acc_pid_control: Float64 = 0.0
    var _t0_pid_control = perf_counter_ns()
    for _ in range(N):
        _acc_pid_control += pid_control(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pid_control = perf_counter_ns()
    var _ns_pid_control = Float64(_t1_pid_control - _t0_pid_control) / Float64(N)
    print("MOJO_TIMING robotics::pid_control", _ns_pid_control, _acc_pid_control)
    var _result_pid_control = pid_control(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_pid_control = _summary_float64(_result_pid_control)
    print("MOJO_RESULT robotics::pid_control", _summary_pid_control)
    var _acc_dead_reckoning_x: Float64 = 0.0
    var _t0_dead_reckoning_x = perf_counter_ns()
    for _ in range(N):
        _acc_dead_reckoning_x += dead_reckoning_x(0.5, 0.5, 0.5, 0.5)
    var _t1_dead_reckoning_x = perf_counter_ns()
    var _ns_dead_reckoning_x = Float64(_t1_dead_reckoning_x - _t0_dead_reckoning_x) / Float64(N)
    print("MOJO_TIMING robotics::dead_reckoning_x", _ns_dead_reckoning_x, _acc_dead_reckoning_x)
    var _result_dead_reckoning_x = dead_reckoning_x(0.5, 0.5, 0.5, 0.5)
    var _summary_dead_reckoning_x = _summary_float64(_result_dead_reckoning_x)
    print("MOJO_RESULT robotics::dead_reckoning_x", _summary_dead_reckoning_x)
    var _acc_dead_reckoning_y: Float64 = 0.0
    var _t0_dead_reckoning_y = perf_counter_ns()
    for _ in range(N):
        _acc_dead_reckoning_y += dead_reckoning_y(0.5, 0.5, 0.5, 0.5)
    var _t1_dead_reckoning_y = perf_counter_ns()
    var _ns_dead_reckoning_y = Float64(_t1_dead_reckoning_y - _t0_dead_reckoning_y) / Float64(N)
    print("MOJO_TIMING robotics::dead_reckoning_y", _ns_dead_reckoning_y, _acc_dead_reckoning_y)
    var _result_dead_reckoning_y = dead_reckoning_y(0.5, 0.5, 0.5, 0.5)
    var _summary_dead_reckoning_y = _summary_float64(_result_dead_reckoning_y)
    print("MOJO_RESULT robotics::dead_reckoning_y", _summary_dead_reckoning_y)
    var _acc_wheel_odometry_distance: Float64 = 0.0
    var _t0_wheel_odometry_distance = perf_counter_ns()
    for _ in range(N):
        _acc_wheel_odometry_distance += wheel_odometry_distance(0.5, 0.5, 0.5)
    var _t1_wheel_odometry_distance = perf_counter_ns()
    var _ns_wheel_odometry_distance = Float64(_t1_wheel_odometry_distance - _t0_wheel_odometry_distance) / Float64(N)
    print("MOJO_TIMING robotics::wheel_odometry_distance", _ns_wheel_odometry_distance, _acc_wheel_odometry_distance)
    var _result_wheel_odometry_distance = wheel_odometry_distance(0.5, 0.5, 0.5)
    var _summary_wheel_odometry_distance = _summary_float64(_result_wheel_odometry_distance)
    print("MOJO_RESULT robotics::wheel_odometry_distance", _summary_wheel_odometry_distance)
    var _acc_differential_drive_omega: Float64 = 0.0
    var _t0_differential_drive_omega = perf_counter_ns()
    for _ in range(N):
        _acc_differential_drive_omega += differential_drive_omega(0.5, 0.5, 0.5)
    var _t1_differential_drive_omega = perf_counter_ns()
    var _ns_differential_drive_omega = Float64(_t1_differential_drive_omega - _t0_differential_drive_omega) / Float64(N)
    print("MOJO_TIMING robotics::differential_drive_omega", _ns_differential_drive_omega, _acc_differential_drive_omega)
    var _result_differential_drive_omega = differential_drive_omega(0.5, 0.5, 0.5)
    var _summary_differential_drive_omega = _summary_float64(_result_differential_drive_omega)
    print("MOJO_RESULT robotics::differential_drive_omega", _summary_differential_drive_omega)
    var _acc_differential_drive_velocity: Float64 = 0.0
    var _t0_differential_drive_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_differential_drive_velocity += differential_drive_velocity(0.5, 0.5)
    var _t1_differential_drive_velocity = perf_counter_ns()
    var _ns_differential_drive_velocity = Float64(_t1_differential_drive_velocity - _t0_differential_drive_velocity) / Float64(N)
    print("MOJO_TIMING robotics::differential_drive_velocity", _ns_differential_drive_velocity, _acc_differential_drive_velocity)
    var _result_differential_drive_velocity = differential_drive_velocity(0.5, 0.5)
    var _summary_differential_drive_velocity = _summary_float64(_result_differential_drive_velocity)
    print("MOJO_RESULT robotics::differential_drive_velocity", _summary_differential_drive_velocity)
    var _acc_workspace_radius: Float64 = 0.0
    var _t0_workspace_radius = perf_counter_ns()
    for _ in range(N):
        _acc_workspace_radius += workspace_radius(0.5, 0.5)
    var _t1_workspace_radius = perf_counter_ns()
    var _ns_workspace_radius = Float64(_t1_workspace_radius - _t0_workspace_radius) / Float64(N)
    print("MOJO_TIMING robotics::workspace_radius", _ns_workspace_radius, _acc_workspace_radius)
    var _result_workspace_radius = workspace_radius(0.5, 0.5)
    var _summary_workspace_radius = _summary_float64(_result_workspace_radius)
    print("MOJO_RESULT robotics::workspace_radius", _summary_workspace_radius)
    var _acc_manipulability_index: Float64 = 0.0
    var _t0_manipulability_index = perf_counter_ns()
    for _ in range(N):
        _acc_manipulability_index += manipulability_index(0.5)
    var _t1_manipulability_index = perf_counter_ns()
    var _ns_manipulability_index = Float64(_t1_manipulability_index - _t0_manipulability_index) / Float64(N)
    print("MOJO_TIMING robotics::manipulability_index", _ns_manipulability_index, _acc_manipulability_index)
    var _result_manipulability_index = manipulability_index(0.5)
    var _summary_manipulability_index = _summary_float64(_result_manipulability_index)
    print("MOJO_RESULT robotics::manipulability_index", _summary_manipulability_index)
