"""bench_robotics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from robotics import forward_kinematics_2dof, forward_kinematics_2dof_y, inverse_kinematics_2dof_theta2, jacobian_2dof_j11, pid_control, dead_reckoning_x, dead_reckoning_y, wheel_odometry_distance, differential_drive_omega, differential_drive_velocity, workspace_radius, manipulability_index
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

    var _acc_forward_kinematics_2dof: Float64 = 0.0
    var _t0_forward_kinematics_2dof = perf_counter_ns()
    for _ in range(N):
        _acc_forward_kinematics_2dof += forward_kinematics_2dof(0.5, 0.5, 0.5, 0.5)
    var _t1_forward_kinematics_2dof = perf_counter_ns()
    var _ns_forward_kinematics_2dof = Float64(_t1_forward_kinematics_2dof - _t0_forward_kinematics_2dof) / Float64(N)
    print("MOJO_TIMING robotics::forward_kinematics_2dof", _ns_forward_kinematics_2dof, _acc_forward_kinematics_2dof)
    var _acc_forward_kinematics_2dof_y: Float64 = 0.0
    var _t0_forward_kinematics_2dof_y = perf_counter_ns()
    for _ in range(N):
        _acc_forward_kinematics_2dof_y += forward_kinematics_2dof_y(0.5, 0.5, 0.5, 0.5)
    var _t1_forward_kinematics_2dof_y = perf_counter_ns()
    var _ns_forward_kinematics_2dof_y = Float64(_t1_forward_kinematics_2dof_y - _t0_forward_kinematics_2dof_y) / Float64(N)
    print("MOJO_TIMING robotics::forward_kinematics_2dof_y", _ns_forward_kinematics_2dof_y, _acc_forward_kinematics_2dof_y)
    var _acc_inverse_kinematics_2dof_theta2: Float64 = 0.0
    var _t0_inverse_kinematics_2dof_theta2 = perf_counter_ns()
    for _ in range(N):
        _acc_inverse_kinematics_2dof_theta2 += inverse_kinematics_2dof_theta2(0.5, 0.5, 0.5, 0.5)
    var _t1_inverse_kinematics_2dof_theta2 = perf_counter_ns()
    var _ns_inverse_kinematics_2dof_theta2 = Float64(_t1_inverse_kinematics_2dof_theta2 - _t0_inverse_kinematics_2dof_theta2) / Float64(N)
    print("MOJO_TIMING robotics::inverse_kinematics_2dof_theta2", _ns_inverse_kinematics_2dof_theta2, _acc_inverse_kinematics_2dof_theta2)
    var _acc_jacobian_2dof_j11: Float64 = 0.0
    var _t0_jacobian_2dof_j11 = perf_counter_ns()
    for _ in range(N):
        _acc_jacobian_2dof_j11 += jacobian_2dof_j11(0.5, 0.5, 0.5, 0.5)
    var _t1_jacobian_2dof_j11 = perf_counter_ns()
    var _ns_jacobian_2dof_j11 = Float64(_t1_jacobian_2dof_j11 - _t0_jacobian_2dof_j11) / Float64(N)
    print("MOJO_TIMING robotics::jacobian_2dof_j11", _ns_jacobian_2dof_j11, _acc_jacobian_2dof_j11)
    var _acc_pid_control: Float64 = 0.0
    var _t0_pid_control = perf_counter_ns()
    for _ in range(N):
        _acc_pid_control += pid_control(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pid_control = perf_counter_ns()
    var _ns_pid_control = Float64(_t1_pid_control - _t0_pid_control) / Float64(N)
    print("MOJO_TIMING robotics::pid_control", _ns_pid_control, _acc_pid_control)
    var _acc_dead_reckoning_x: Float64 = 0.0
    var _t0_dead_reckoning_x = perf_counter_ns()
    for _ in range(N):
        _acc_dead_reckoning_x += dead_reckoning_x(0.5, 0.5, 0.5, 0.5)
    var _t1_dead_reckoning_x = perf_counter_ns()
    var _ns_dead_reckoning_x = Float64(_t1_dead_reckoning_x - _t0_dead_reckoning_x) / Float64(N)
    print("MOJO_TIMING robotics::dead_reckoning_x", _ns_dead_reckoning_x, _acc_dead_reckoning_x)
    var _acc_dead_reckoning_y: Float64 = 0.0
    var _t0_dead_reckoning_y = perf_counter_ns()
    for _ in range(N):
        _acc_dead_reckoning_y += dead_reckoning_y(0.5, 0.5, 0.5, 0.5)
    var _t1_dead_reckoning_y = perf_counter_ns()
    var _ns_dead_reckoning_y = Float64(_t1_dead_reckoning_y - _t0_dead_reckoning_y) / Float64(N)
    print("MOJO_TIMING robotics::dead_reckoning_y", _ns_dead_reckoning_y, _acc_dead_reckoning_y)
    var _acc_wheel_odometry_distance: Float64 = 0.0
    var _t0_wheel_odometry_distance = perf_counter_ns()
    for _ in range(N):
        _acc_wheel_odometry_distance += wheel_odometry_distance(0.5, 0.5, 0.5)
    var _t1_wheel_odometry_distance = perf_counter_ns()
    var _ns_wheel_odometry_distance = Float64(_t1_wheel_odometry_distance - _t0_wheel_odometry_distance) / Float64(N)
    print("MOJO_TIMING robotics::wheel_odometry_distance", _ns_wheel_odometry_distance, _acc_wheel_odometry_distance)
    var _acc_differential_drive_omega: Float64 = 0.0
    var _t0_differential_drive_omega = perf_counter_ns()
    for _ in range(N):
        _acc_differential_drive_omega += differential_drive_omega(0.5, 0.5, 0.5)
    var _t1_differential_drive_omega = perf_counter_ns()
    var _ns_differential_drive_omega = Float64(_t1_differential_drive_omega - _t0_differential_drive_omega) / Float64(N)
    print("MOJO_TIMING robotics::differential_drive_omega", _ns_differential_drive_omega, _acc_differential_drive_omega)
    var _acc_differential_drive_velocity: Float64 = 0.0
    var _t0_differential_drive_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_differential_drive_velocity += differential_drive_velocity(0.5, 0.5)
    var _t1_differential_drive_velocity = perf_counter_ns()
    var _ns_differential_drive_velocity = Float64(_t1_differential_drive_velocity - _t0_differential_drive_velocity) / Float64(N)
    print("MOJO_TIMING robotics::differential_drive_velocity", _ns_differential_drive_velocity, _acc_differential_drive_velocity)
    var _acc_workspace_radius: Float64 = 0.0
    var _t0_workspace_radius = perf_counter_ns()
    for _ in range(N):
        _acc_workspace_radius += workspace_radius(0.5, 0.5)
    var _t1_workspace_radius = perf_counter_ns()
    var _ns_workspace_radius = Float64(_t1_workspace_radius - _t0_workspace_radius) / Float64(N)
    print("MOJO_TIMING robotics::workspace_radius", _ns_workspace_radius, _acc_workspace_radius)
    var _acc_manipulability_index: Float64 = 0.0
    var _t0_manipulability_index = perf_counter_ns()
    for _ in range(N):
        _acc_manipulability_index += manipulability_index(0.5)
    var _t1_manipulability_index = perf_counter_ns()
    var _ns_manipulability_index = Float64(_t1_manipulability_index - _t0_manipulability_index) / Float64(N)
    print("MOJO_TIMING robotics::manipulability_index", _ns_manipulability_index, _acc_manipulability_index)
