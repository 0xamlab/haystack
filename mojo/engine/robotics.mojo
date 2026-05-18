"""
robotics.mojo — Robotics & Kinematics Library. Zero Python imports.

Provides functions for forward/inverse kinematics, PID control,
dead reckoning, wheel odometry, and differential drive calculations.

Public API:
  forward_kinematics_2dof     — X end-effector for 2-DOF planar arm
  forward_kinematics_2dof_y   — Y end-effector for 2-DOF planar arm
  inverse_kinematics_2dof_theta2 — Elbow angle via inverse kinematics
  jacobian_2dof_j11           — J[0,0] of 2-DOF Jacobian
  pid_control                 — PID controller output
  dead_reckoning_x            — X position via dead reckoning
  dead_reckoning_y            — Y position via dead reckoning
  wheel_odometry_distance     — Distance from encoder ticks
  differential_drive_omega    — Angular velocity of diff drive
  differential_drive_velocity — Linear velocity of diff drive
  workspace_radius            — Max reach of 2-link arm
  manipulability_index        — Yoshikawa manipulability measure
"""

from std.math import sin, cos, sqrt, acos, abs as _abs


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793


# ── forward_kinematics_2dof ──────────────────────────────────────────────────


fn forward_kinematics_2dof(
    l1: Float64, l2: Float64, theta1: Float64, theta2: Float64
) -> Float64:
    """End-effector X for 2-DOF planar arm: x = l1*cos(θ1) + l2*cos(θ1+θ2)."""
    return l1 * cos(theta1) + l2 * cos(theta1 + theta2)


# ── forward_kinematics_2dof_y ────────────────────────────────────────────────


fn forward_kinematics_2dof_y(
    l1: Float64, l2: Float64, theta1: Float64, theta2: Float64
) -> Float64:
    """End-effector Y for 2-DOF planar arm: y = l1*sin(θ1) + l2*sin(θ1+θ2)."""
    return l1 * sin(theta1) + l2 * sin(theta1 + theta2)


# ── inverse_kinematics_2dof_theta2 ──────────────────────────────────────────


fn inverse_kinematics_2dof_theta2(
    l1: Float64, l2: Float64, x: Float64, y: Float64
) -> Float64:
    """Elbow angle: cos(θ2) = (x²+y²-l1²-l2²)/(2*l1*l2), return acos."""
    var cos_theta2 = (x * x + y * y - l1 * l1 - l2 * l2) / (2.0 * l1 * l2)
    # Clamp to [-1, 1] for numerical safety
    if cos_theta2 > 1.0:
        cos_theta2 = 1.0
    if cos_theta2 < -1.0:
        cos_theta2 = -1.0
    return acos(cos_theta2)


# ── jacobian_2dof_j11 ───────────────────────────────────────────────────────


fn jacobian_2dof_j11(
    l1: Float64, l2: Float64, theta1: Float64, theta2: Float64
) -> Float64:
    """Jacobian J[0,0] = -l1*sin(θ1) - l2*sin(θ1+θ2)."""
    return -l1 * sin(theta1) - l2 * sin(theta1 + theta2)


# ── pid_control ──────────────────────────────────────────────────────────────


fn pid_control(
    kp: Float64,
    ki: Float64,
    kd: Float64,
    error: Float64,
    integral: Float64,
    derivative: Float64,
) -> Float64:
    """PID output = kp*error + ki*integral + kd*derivative."""
    return kp * error + ki * integral + kd * derivative


# ── dead_reckoning_x ────────────────────────────────────────────────────────


fn dead_reckoning_x(
    x0: Float64, v: Float64, theta: Float64, dt: Float64
) -> Float64:
    """Dead reckoning X: x = x0 + v*cos(θ)*dt."""
    return x0 + v * cos(theta) * dt


# ── dead_reckoning_y ────────────────────────────────────────────────────────


fn dead_reckoning_y(
    y0: Float64, v: Float64, theta: Float64, dt: Float64
) -> Float64:
    """Dead reckoning Y: y = y0 + v*sin(θ)*dt."""
    return y0 + v * sin(theta) * dt


# ── wheel_odometry_distance ─────────────────────────────────────────────────


fn wheel_odometry_distance(
    wheel_radius: Float64, encoder_ticks: Float64, ticks_per_rev: Float64
) -> Float64:
    """Distance = 2π*r * ticks/tpr."""
    return 2.0 * PI * wheel_radius * encoder_ticks / ticks_per_rev


# ── differential_drive_omega ─────────────────────────────────────────────────


fn differential_drive_omega(
    v_left: Float64, v_right: Float64, wheel_base: Float64
) -> Float64:
    """Angular velocity ω = (v_right - v_left) / wheel_base."""
    return (v_right - v_left) / wheel_base


# ── differential_drive_velocity ──────────────────────────────────────────────


fn differential_drive_velocity(v_left: Float64, v_right: Float64) -> Float64:
    """Linear velocity v = (v_left + v_right) / 2."""
    return (v_left + v_right) / 2.0


# ── workspace_radius ────────────────────────────────────────────────────────


fn workspace_radius(l1: Float64, l2: Float64) -> Float64:
    """Maximum reach of 2-link arm = l1 + l2."""
    return l1 + l2


# ── manipulability_index ─────────────────────────────────────────────────────


fn manipulability_index(det_jacobian: Float64) -> Float64:
    """Yoshikawa manipulability = |det(J)|."""
    return _abs(det_jacobian)
