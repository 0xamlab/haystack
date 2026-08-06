"""
transportation.mojo — Transportation Engineering Library. Zero Python imports.

Pure Mojo implementations of transportation engineering calculations including
level of service, highway capacity, signal delay, stopping distance,
fuel consumption, and crash rate analysis.

Public API:
  level_of_service_density  — Density = flow/speed
  highway_capacity          — C = lanes * capacity_per_lane
  travel_time               — t = d/s
  delay_at_signal           — Simplified Webster delay
  headway                   — Following headway
  stopping_distance         — Braking distance with grade
  fuel_consumption_rate     — Speed-dependent fuel rate
  passenger_car_equivalent  — PCE from truck percentage
  intersection_capacity     — Capacity from saturation flow
  queue_length_estimate     — Deterministic queue length
  vehicle_operating_cost    — Fuel-based VOC
  crash_rate                — Crashes per VMT
"""
from std.math import abs as fabs


# ── Constants ────────────────────────────────────────────────────────────────

comptime GRAVITY: Float64 = 9.81  # m/s²


# ── level_of_service_density ─────────────────────────────────────────────────


def level_of_service_density(flow: Float64, speed: Float64) -> Float64:
    """Traffic density: D = flow / speed (veh/km/lane).

    Args:
        flow: Flow rate (veh/hr/lane).
        speed: Speed (km/hr).

    Returns:
        Density (veh/km/lane).
    """
    if fabs(speed) < 1e-30:
        return 0.0
    return flow / speed


# ── highway_capacity ─────────────────────────────────────────────────────────


def highway_capacity(lanes: Float64, capacity_per_lane: Float64) -> Float64:
    """Highway capacity: C = lanes * capacity_per_lane.

    Args:
        lanes: Number of lanes.
        capacity_per_lane: Capacity per lane (veh/hr).

    Returns:
        Total capacity (veh/hr).
    """
    return lanes * capacity_per_lane


# ── travel_time ──────────────────────────────────────────────────────────────


def travel_time(distance: Float64, speed: Float64) -> Float64:
    """Travel time: t = d / s.

    Args:
        distance: Distance (km or mi).
        speed: Speed (km/hr or mi/hr).

    Returns:
        Travel time (hr).
    """
    if fabs(speed) < 1e-30:
        return 0.0
    return distance / speed


# ── delay_at_signal ──────────────────────────────────────────────────────────


def delay_at_signal(
    cycle_length: Float64,
    green_ratio: Float64,
    arrival_rate: Float64,
    service_rate: Float64,
) -> Float64:
    """Simplified Webster signal delay.

    d = 0.5 * C * (1 - g/C)² / (1 - min(1, λ/μ) * g/C)

    Args:
        cycle_length: Cycle length C (seconds).
        green_ratio: Green time ratio g/C.
        arrival_rate: Arrival rate λ (veh/s).
        service_rate: Service rate μ (veh/s).

    Returns:
        Average delay per vehicle (seconds).
    """
    var x = arrival_rate / service_rate if fabs(service_rate) > 1e-30 else 1.0
    if x > 1.0:
        x = 1.0
    var one_minus_g = 1.0 - green_ratio
    var denom = 1.0 - x * green_ratio
    if fabs(denom) < 1e-30:
        denom = 1e-30
    return 0.5 * cycle_length * one_minus_g * one_minus_g / denom


# ── headway ──────────────────────────────────────────────────────────────────


def headway(
    speed: Float64, reaction_time: Float64, deceleration: Float64
) -> Float64:
    """Safe following headway: h = reaction_time + speed / (2 * decel).

    Args:
        speed: Vehicle speed (m/s).
        reaction_time: Driver reaction time (s).
        deceleration: Deceleration rate (m/s²).

    Returns:
        Headway (seconds).
    """
    if fabs(deceleration) < 1e-30:
        return reaction_time
    return reaction_time + speed / (2.0 * deceleration)


# ── stopping_distance ────────────────────────────────────────────────────────


def stopping_distance(
    speed: Float64,
    reaction_time: Float64,
    friction: Float64,
    grade: Float64,
) -> Float64:
    """Stopping distance: d = v*t_r + v² / (2*g*(f+G)).

    Args:
        speed: Speed (m/s).
        reaction_time: Reaction time (s).
        friction: Friction coefficient.
        grade: Road grade (+ for uphill).

    Returns:
        Total stopping distance (m).
    """
    var denom = 2.0 * GRAVITY * (friction + grade)
    if fabs(denom) < 1e-30:
        return speed * reaction_time
    return speed * reaction_time + speed * speed / denom


# ── fuel_consumption_rate ────────────────────────────────────────────────────


def fuel_consumption_rate(
    base_rate: Float64, speed: Float64, optimal_speed: Float64
) -> Float64:
    """Speed-dependent fuel consumption rate.

    rate = base * (1 + 0.01 * (speed - optimal)²)

    Args:
        base_rate: Base fuel rate (L/100km).
        speed: Current speed (km/hr).
        optimal_speed: Optimal speed for fuel efficiency (km/hr).

    Returns:
        Fuel rate (L/100km).
    """
    var diff = speed - optimal_speed
    return base_rate * (1.0 + 0.01 * diff * diff)


# ── passenger_car_equivalent ─────────────────────────────────────────────────


def passenger_car_equivalent(
    trucks_pct: Float64, terrain_factor: Float64
) -> Float64:
    """Passenger car equivalent: PCE = 1 + trucks_pct * (terrain_factor - 1).

    Args:
        trucks_pct: Truck percentage (as fraction, e.g. 0.10).
        terrain_factor: Terrain equivalency factor (e.g. 2.0 for rolling).

    Returns:
        PCE adjustment factor.
    """
    return 1.0 + trucks_pct * (terrain_factor - 1.0)


# ── intersection_capacity ────────────────────────────────────────────────────


def intersection_capacity(
    saturation_flow: Float64, green_ratio: Float64
) -> Float64:
    """Intersection capacity: c = s * g/C.

    Args:
        saturation_flow: Saturation flow rate (veh/hr).
        green_ratio: Green time ratio g/C.

    Returns:
        Capacity (veh/hr).
    """
    return saturation_flow * green_ratio


# ── queue_length_estimate ────────────────────────────────────────────────────


def queue_length_estimate(
    arrival_rate: Float64, service_rate: Float64, time_period: Float64
) -> Float64:
    """Deterministic queue length: Q = max(0, (λ - μ) * T).

    Args:
        arrival_rate: Arrival rate λ (veh/hr).
        service_rate: Service rate μ (veh/hr).
        time_period: Time period T (hr).

    Returns:
        Queue length (vehicles).
    """
    var q = (arrival_rate - service_rate) * time_period
    if q < 0.0:
        return 0.0
    return q


# ── vehicle_operating_cost ───────────────────────────────────────────────────


def vehicle_operating_cost(
    fuel_cost: Float64, distance: Float64, fuel_efficiency: Float64
) -> Float64:
    """Vehicle operating cost: VOC = fuel_cost * distance / efficiency.

    Args:
        fuel_cost: Fuel cost per unit ($/L or $/gal).
        distance: Distance travelled.
        fuel_efficiency: Fuel efficiency (km/L or mi/gal).

    Returns:
        Operating cost ($).
    """
    if fabs(fuel_efficiency) < 1e-30:
        return 0.0
    return fuel_cost * distance / fuel_efficiency


# ── crash_rate ───────────────────────────────────────────────────────────────


def crash_rate(crashes: Float64, vmt_millions: Float64) -> Float64:
    """Crash rate: Rate = crashes / VMT (millions).

    Args:
        crashes: Number of crashes.
        vmt_millions: Vehicle miles travelled (millions).

    Returns:
        Crash rate per million VMT.
    """
    if fabs(vmt_millions) < 1e-30:
        return 0.0
    return crashes / vmt_millions
