"""test_robotics.mojo — auto-generated tests for robotics library."""
from std.math import isnan, isinf
from robotics import forward_kinematics_2dof, forward_kinematics_2dof_y, inverse_kinematics_2dof_theta2, jacobian_2dof_j11, pid_control, dead_reckoning_x, dead_reckoning_y, wheel_odometry_distance, differential_drive_omega, differential_drive_velocity, workspace_radius, manipulability_index

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

    var _v_forward_kinematics_2dof = forward_kinematics_2dof(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_forward_kinematics_2dof): passed += 1; print("  ✅ robotics::forward_kinematics_2dof =", _v_forward_kinematics_2dof)
    else: failed += 1; print("  ❌ robotics::forward_kinematics_2dof → non-finite:", _v_forward_kinematics_2dof)
    var _v_forward_kinematics_2dof_y = forward_kinematics_2dof_y(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_forward_kinematics_2dof_y): passed += 1; print("  ✅ robotics::forward_kinematics_2dof_y =", _v_forward_kinematics_2dof_y)
    else: failed += 1; print("  ❌ robotics::forward_kinematics_2dof_y → non-finite:", _v_forward_kinematics_2dof_y)
    var _v_inverse_kinematics_2dof_theta2 = inverse_kinematics_2dof_theta2(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_inverse_kinematics_2dof_theta2): passed += 1; print("  ✅ robotics::inverse_kinematics_2dof_theta2 =", _v_inverse_kinematics_2dof_theta2)
    else: failed += 1; print("  ❌ robotics::inverse_kinematics_2dof_theta2 → non-finite:", _v_inverse_kinematics_2dof_theta2)
    var _v_jacobian_2dof_j11 = jacobian_2dof_j11(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_jacobian_2dof_j11): passed += 1; print("  ✅ robotics::jacobian_2dof_j11 =", _v_jacobian_2dof_j11)
    else: failed += 1; print("  ❌ robotics::jacobian_2dof_j11 → non-finite:", _v_jacobian_2dof_j11)
    var _v_pid_control = pid_control(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_pid_control): passed += 1; print("  ✅ robotics::pid_control =", _v_pid_control)
    else: failed += 1; print("  ❌ robotics::pid_control → non-finite:", _v_pid_control)
    var _v_dead_reckoning_x = dead_reckoning_x(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_dead_reckoning_x): passed += 1; print("  ✅ robotics::dead_reckoning_x =", _v_dead_reckoning_x)
    else: failed += 1; print("  ❌ robotics::dead_reckoning_x → non-finite:", _v_dead_reckoning_x)
    var _v_dead_reckoning_y = dead_reckoning_y(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_dead_reckoning_y): passed += 1; print("  ✅ robotics::dead_reckoning_y =", _v_dead_reckoning_y)
    else: failed += 1; print("  ❌ robotics::dead_reckoning_y → non-finite:", _v_dead_reckoning_y)
    var _v_wheel_odometry_distance = wheel_odometry_distance(0.5, 0.5, 0.5)
    if is_finite(_v_wheel_odometry_distance): passed += 1; print("  ✅ robotics::wheel_odometry_distance =", _v_wheel_odometry_distance)
    else: failed += 1; print("  ❌ robotics::wheel_odometry_distance → non-finite:", _v_wheel_odometry_distance)
    var _v_differential_drive_omega = differential_drive_omega(0.5, 0.5, 0.5)
    if is_finite(_v_differential_drive_omega): passed += 1; print("  ✅ robotics::differential_drive_omega =", _v_differential_drive_omega)
    else: failed += 1; print("  ❌ robotics::differential_drive_omega → non-finite:", _v_differential_drive_omega)
    var _v_differential_drive_velocity = differential_drive_velocity(0.5, 0.5)
    if is_finite(_v_differential_drive_velocity): passed += 1; print("  ✅ robotics::differential_drive_velocity =", _v_differential_drive_velocity)
    else: failed += 1; print("  ❌ robotics::differential_drive_velocity → non-finite:", _v_differential_drive_velocity)
    var _v_workspace_radius = workspace_radius(0.5, 0.5)
    if is_finite(_v_workspace_radius): passed += 1; print("  ✅ robotics::workspace_radius =", _v_workspace_radius)
    else: failed += 1; print("  ❌ robotics::workspace_radius → non-finite:", _v_workspace_radius)
    var _v_manipulability_index = manipulability_index(0.5)
    if is_finite(_v_manipulability_index): passed += 1; print("  ✅ robotics::manipulability_index =", _v_manipulability_index)
    else: failed += 1; print("  ❌ robotics::manipulability_index → non-finite:", _v_manipulability_index)

    print("  [robotics] Passed:", passed, "Failed:", failed)
