"""
autonomous_vehicles.mojo — Autonomous Vehicles Library. Zero Python imports.

Pure Mojo implementations of autonomous driving computations including
safe following distance, time-to-collision, braking distance, sensor range,
lane change dynamics, perception latency, and V2X communication.

Public API:
  safe_following_distance       — d = v*t + v²/(2*a)
  time_to_collision             — TTC = d / v_rel
  braking_distance              — d = v²/(2*g*(μ+G))
  sensor_range_required         — R = v*t + v²/(2*a)
  lane_change_distance          — d ≈ v*sqrt(2*w/a_lat)
  perception_latency_distance   — d = v * latency/1000
  comfort_deceleration          — Returns 3.0 m/s²
  emergency_deceleration        — Returns 8.0 m/s²
  headway_time                  — THW = d/v
  fuel_efficiency_at_speed      — eff = base*(1 - 0.01*(speed-opt)²/opt)
  v2x_communication_range       — Simplified range model
  localization_error_gps        — error = HDOP * UERE
"""
from std.math import sqrt, exp, log, pow


# ── safe_following_distance ──────────────────────────────────────────────────


fn safe_following_distance(
    speed_mps: Float64, reaction_time: Float64, deceleration: Float64
) -> Float64:
    """d = v*t + v²/(2*a) — reaction distance + braking distance."""
    return speed_mps * reaction_time + speed_mps * speed_mps / (2.0 * deceleration)


# ── time_to_collision ────────────────────────────────────────────────────────


fn time_to_collision(distance: Float64, relative_speed: Float64) -> Float64:
    """TTC = d / v_rel (seconds). Returns -1 if relative_speed <= 0."""
    if relative_speed <= 0.0:
        return -1.0
    return distance / relative_speed


# ── braking_distance ─────────────────────────────────────────────────────────


fn braking_distance(speed: Float64, friction: Float64, grade: Float64) -> Float64:
    """d = v²/(2*g*(μ+G)) where g=9.81 m/s²."""
    var g = 9.81
    return speed * speed / (2.0 * g * (friction + grade))


# ── sensor_range_required ────────────────────────────────────────────────────


fn sensor_range_required(
    speed: Float64, reaction_time: Float64, max_decel: Float64
) -> Float64:
    """R = v*t + v²/(2*a) — minimum sensor detection range needed."""
    return speed * reaction_time + speed * speed / (2.0 * max_decel)


# ── lane_change_distance ────────────────────────────────────────────────────


fn lane_change_distance(
    speed: Float64, lateral_accel: Float64, lane_width: Float64
) -> Float64:
    """d ≈ v * sqrt(2*w / a_lat) — longitudinal distance during lane change."""
    return speed * sqrt(2.0 * lane_width / lateral_accel)


# ── perception_latency_distance ──────────────────────────────────────────────


fn perception_latency_distance(speed: Float64, latency_ms: Float64) -> Float64:
    """d = v * latency/1000 — distance traveled during perception latency."""
    return speed * latency_ms / 1000.0


# ── comfort_deceleration ────────────────────────────────────────────────────


fn comfort_deceleration() -> Float64:
    """Returns 3.0 m/s² — standard comfortable braking deceleration."""
    return 3.0


# ── emergency_deceleration ──────────────────────────────────────────────────


fn emergency_deceleration() -> Float64:
    """Returns 8.0 m/s² — maximum emergency braking deceleration."""
    return 8.0


# ── headway_time ─────────────────────────────────────────────────────────────


fn headway_time(distance: Float64, speed: Float64) -> Float64:
    """THW = d / v (seconds) — time headway between vehicles."""
    return distance / speed


# ── fuel_efficiency_at_speed ─────────────────────────────────────────────────


fn fuel_efficiency_at_speed(
    base_eff: Float64, speed: Float64, optimal_speed: Float64
) -> Float64:
    """eff = base_eff * (1 - 0.01*(speed - optimal_speed)²/optimal_speed).

    Quadratic penalty for deviation from optimal cruising speed.
    """
    var diff = speed - optimal_speed
    return base_eff * (1.0 - 0.01 * diff * diff / optimal_speed)


# ── v2x_communication_range ─────────────────────────────────────────────────


fn v2x_communication_range(
    tx_power: Float64, frequency: Float64, path_loss_exp: Float64
) -> Float64:
    """Simplified V2X range: R = (tx_power / frequency)^(1/n).

    tx_power in Watts, frequency in Hz, path_loss_exp = n.
    Returns relative range metric (unitless simplified model).
    """
    var ratio = tx_power / frequency
    return exp(log(ratio) / path_loss_exp)


# ── localization_error_gps ───────────────────────────────────────────────────


fn localization_error_gps(hdop: Float64, uere: Float64) -> Float64:
    """GPS localization error = HDOP * UERE (meters).

    HDOP = Horizontal Dilution of Precision.
    UERE = User Equivalent Range Error (meters).
    """
    return hdop * uere
