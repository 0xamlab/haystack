"""
traffic_signal.mojo — Traffic Signal Engineering Library.

Provides signal timing, capacity, delay, and level-of-service calculations
for intersection design and analysis.

Public API:
  cycle_length_webster               — C = (1.5*L + 5) / (1 - Y)
  effective_green                    — g = G - start_loss + end_gain
  green_ratio                        — g/C ratio
  capacity_lane                      — c = s * g/C
  volume_to_capacity                 — v/c ratio
  delay_uniform                      — d1 = 0.5*C*(1-g/C)² / (1-min(1,X)*g/C)
  pedestrian_crossing_time           — t = d / v
  yellow_interval                    — Y = t + v/(2*(a + g*G))
  all_red_interval                   — AR = (W + L) / v
  level_of_service_delay             — LOS A–F from delay
  intersection_capacity_utilization  — ICU = Σ(v/s)_crit + L/C
  peak_hour_factor                   — PHF = V / (4 * V15)
"""
from std.math import abs as fabs


# ── cycle_length_webster ─────────────────────────────────────────────────────


fn cycle_length_webster(total_lost_time: Float64, critical_vc_ratio: Float64) -> Float64:
    """Webster optimal cycle length: C = (1.5*L + 5) / (1 - Y).

    Args:
        total_lost_time: Total lost time per cycle L (seconds).
        critical_vc_ratio: Sum of critical phase flow ratios Y.

    Returns:
        Optimal cycle length (seconds).
    """
    # Y = 1.0 saturates the intersection and zeros the denominator.
    if critical_vc_ratio == 1.0:
        return 0.0
    return (1.5 * total_lost_time + 5.0) / (1.0 - critical_vc_ratio)


# ── effective_green ──────────────────────────────────────────────────────────


fn effective_green(actual_green: Float64, start_loss: Float64, end_gain: Float64) -> Float64:
    """Effective green time: g = G - start_loss + end_gain.

    Args:
        actual_green: Displayed green time (seconds).
        start_loss: Start-up lost time (seconds).
        end_gain: End gain / extension into yellow (seconds).

    Returns:
        Effective green time (seconds).
    """
    return actual_green - start_loss + end_gain


# ── green_ratio ──────────────────────────────────────────────────────────────


fn green_ratio(effective_green_val: Float64, cycle_length: Float64) -> Float64:
    """Green ratio: g/C.

    Args:
        effective_green_val: Effective green time (seconds).
        cycle_length: Cycle length (seconds).

    Returns:
        Green ratio (dimensionless, 0–1).
    """
    return effective_green_val / cycle_length


# ── capacity_lane ────────────────────────────────────────────────────────────


fn capacity_lane(saturation_flow: Float64, green_ratio_val: Float64) -> Float64:
    """Lane capacity: c = s * (g/C).

    Args:
        saturation_flow: Saturation flow rate s (veh/hr/lane).
        green_ratio_val: Green ratio g/C.

    Returns:
        Lane capacity (veh/hr).
    """
    return saturation_flow * green_ratio_val


# ── volume_to_capacity ───────────────────────────────────────────────────────


fn volume_to_capacity(volume: Float64, capacity: Float64) -> Float64:
    """Volume-to-capacity ratio: v/c.

    Args:
        volume: Traffic volume (veh/hr).
        capacity: Lane or approach capacity (veh/hr).

    Returns:
        v/c ratio (dimensionless).
    """
    return volume / capacity


# ── delay_uniform ────────────────────────────────────────────────────────────


fn delay_uniform(cycle: Float64, green_ratio_val: Float64, vc_ratio: Float64) -> Float64:
    """Uniform delay (Webster/HCM d1 component):
    d1 = 0.5 * C * (1 - g/C)² / (1 - min(1, X) * g/C).

    Args:
        cycle: Cycle length C (seconds).
        green_ratio_val: Green ratio g/C.
        vc_ratio: Volume-to-capacity ratio X.

    Returns:
        Uniform delay (seconds/vehicle).
    """
    var x_capped = vc_ratio
    if x_capped > 1.0:
        x_capped = 1.0
    var numerator = (1.0 - green_ratio_val) * (1.0 - green_ratio_val)
    var denominator = 1.0 - x_capped * green_ratio_val
    # X = 1 with g/C = 1 zeros the denominator (saturated approach, full green).
    if denominator == 0.0:
        return 0.0
    return 0.5 * cycle * numerator / denominator


# ── pedestrian_crossing_time ─────────────────────────────────────────────────


fn pedestrian_crossing_time(distance: Float64, walk_speed: Float64) -> Float64:
    """Pedestrian crossing time: t = d / v.

    Args:
        distance: Crossing distance (m).
        walk_speed: Walking speed (m/s, typically 1.2).

    Returns:
        Crossing time (seconds).
    """
    return distance / walk_speed


# ── yellow_interval ──────────────────────────────────────────────────────────


fn yellow_interval(
    perception_time: Float64,
    velocity: Float64,
    deceleration: Float64,
    grade: Float64,
) -> Float64:
    """Yellow interval: Y = t + v / (2*(a + g*G)).

    Args:
        perception_time: Perception-reaction time t (seconds).
        velocity: Approach speed (m/s).
        deceleration: Comfortable deceleration a (m/s²).
        grade: Grade fraction G (+ for uphill).

    Returns:
        Yellow interval (seconds).
    """
    comptime g_accel: Float64 = 9.81
    return perception_time + velocity / (2.0 * (deceleration + g_accel * grade))


# ── all_red_interval ─────────────────────────────────────────────────────────


fn all_red_interval(width: Float64, length: Float64, velocity: Float64) -> Float64:
    """All-red clearance interval: AR = (W + L) / v.

    Args:
        width: Intersection width (m).
        length: Vehicle length (m).
        velocity: Approach speed (m/s).

    Returns:
        All-red interval (seconds).
    """
    return (width + length) / velocity


# ── level_of_service_delay ───────────────────────────────────────────────────


fn level_of_service_delay(delay_sec: Float64) -> Int:
    """Level of service from control delay (HCM signalized):
    A=1 (≤10), B=2 (10-20), C=3 (20-35), D=4 (35-55), E=5 (55-80), F=6 (>80).

    Args:
        delay_sec: Average control delay (sec/veh).

    Returns:
        LOS as integer 1(A)–6(F).
    """
    if delay_sec <= 10.0:
        return 1
    if delay_sec <= 20.0:
        return 2
    if delay_sec <= 35.0:
        return 3
    if delay_sec <= 55.0:
        return 4
    if delay_sec <= 80.0:
        return 5
    return 6


# ── intersection_capacity_utilization ────────────────────────────────────────


fn intersection_capacity_utilization(
    sum_critical_vc: Float64,
    total_lost: Float64,
    cycle_length: Float64,
) -> Float64:
    """Intersection Capacity Utilization: ICU = Σ(v/s)_crit + L/C.

    Args:
        sum_critical_vc: Sum of critical v/s ratios.
        total_lost: Total lost time (seconds).
        cycle_length: Cycle length (seconds).

    Returns:
        ICU value (dimensionless).
    """
    return sum_critical_vc + total_lost / cycle_length


# ── peak_hour_factor ─────────────────────────────────────────────────────────


fn peak_hour_factor(peak_volume: Float64, peak_15min_volume: Float64) -> Float64:
    """Peak hour factor: PHF = V / (4 * V15).

    Args:
        peak_volume: Peak hour volume (veh).
        peak_15min_volume: Peak 15-minute volume within the hour (veh).

    Returns:
        PHF (0–1, typically 0.85–0.95).
    """
    return peak_volume / (4.0 * peak_15min_volume)
