"""
elevator.mojo — Elevator / Vertical Transport Engineering Library.

Pure Mojo implementations of fundamental elevator engineering equations
including round-trip time, handling capacity, probable stops, motor power,
counterweight sizing, shaft area, energy consumption, and safety factors.

Public API:
  round_trip_time             — simplified RTT estimate
  handling_capacity           — persons per 5 minutes
  interval_time               — INT = RTT / n_cars
  probable_stops              — S = N * (1 - (1-1/N)^P)
  motor_power                 — P = m*g*v / η (watts)
  counterweight_mass          — CW = car + balance*load
  shaft_area                  — A = (w+cl) * (d+cl)
  annual_energy_consumption   — kWh per year
  waiting_time_average        — WT ≈ interval / 2
  traffic_intensity           — TI = arrivals / HC
  rope_factor_of_safety      — FOS = strength / load
  pit_depth_requirement       — simplified pit depth
"""
from std.math import sqrt, exp, log, abs as fabs


# ── round_trip_time ──────────────────────────────────────────────────────────


def round_trip_time(
    floors: Float64,
    floor_height: Float64,
    speed: Float64,
    accel: Float64,
    door_time: Float64,
    passengers: Float64,
) -> Float64:
    """Simplified round-trip time (seconds).

    RTT ≈ 2*H/v + floors*door_time + passengers*transfer_time
    where H = floors*floor_height and transfer_time ≈ 2 s.
    """
    var h = floors * floor_height
    var travel = 2.0 * h / speed
    var doors = floors * door_time
    var transfer = passengers * 2.0
    return travel + doors + transfer


# ── handling_capacity ────────────────────────────────────────────────────────


def handling_capacity(car_capacity: Float64, rtt_seconds: Float64) -> Float64:
    """Handling capacity: HC = cap * 300 / RTT (persons per 5 min)."""
    return car_capacity * 300.0 / rtt_seconds


# ── interval_time ────────────────────────────────────────────────────────────


def interval_time(rtt: Float64, n_cars: Float64) -> Float64:
    """Interval time: INT = RTT / n_cars (seconds)."""
    return rtt / n_cars


# ── probable_stops ───────────────────────────────────────────────────────────


def probable_stops(floors: Float64, passengers: Float64) -> Float64:
    """Probable number of stops: S = N * (1 - (1 - 1/N)^P).

    Uses exp/log for the exponentiation.
    """
    if floors <= 0.0:
        return 0.0
    var ratio = 1.0 - 1.0 / floors
    if ratio <= 0.0:
        return floors
    var power = exp(passengers * log(ratio))
    return floors * (1.0 - power)


# ── motor_power ──────────────────────────────────────────────────────────────


def motor_power(
    load_kg: Float64, speed_mps: Float64, gravity: Float64, efficiency: Float64
) -> Float64:
    """Motor power: P = m * g * v / η (watts)."""
    return load_kg * gravity * speed_mps / efficiency


# ── counterweight_mass ───────────────────────────────────────────────────────


def counterweight_mass(
    car_mass: Float64, rated_load: Float64, balance_factor: Float64
) -> Float64:
    """Counterweight: CW = car_mass + balance_factor * rated_load (kg)."""
    return car_mass + balance_factor * rated_load


# ── shaft_area ───────────────────────────────────────────────────────────────


def shaft_area(
    car_width: Float64, car_depth: Float64, clearance: Float64
) -> Float64:
    """Shaft area: A = (w + clearance) * (d + clearance) (m²)."""
    return (car_width + clearance) * (car_depth + clearance)


# ── annual_energy_consumption ────────────────────────────────────────────────


def annual_energy_consumption(
    power_kw: Float64,
    daily_trips: Float64,
    trip_time_s: Float64,
    days_per_year: Float64,
) -> Float64:
    """Annual energy: E = P * trips * t * days / 3600 (kWh)."""
    return power_kw * daily_trips * trip_time_s * days_per_year / 3600.0


# ── waiting_time_average ─────────────────────────────────────────────────────


def waiting_time_average(interval: Float64) -> Float64:
    """Average waiting time: WT ≈ interval / 2 (seconds)."""
    return interval / 2.0


# ── traffic_intensity ────────────────────────────────────────────────────────


def traffic_intensity(
    arrivals_per_5min: Float64, handling_cap: Float64
) -> Float64:
    """Traffic intensity: TI = arrivals / HC."""
    return arrivals_per_5min / handling_cap


# ── rope_factor_of_safety ────────────────────────────────────────────────────


def rope_factor_of_safety(
    breaking_strength: Float64, max_load: Float64
) -> Float64:
    """Rope factor of safety: FOS = breaking_strength / max_load."""
    return breaking_strength / max_load


# ── pit_depth_requirement ────────────────────────────────────────────────────


def pit_depth_requirement(speed_mps: Float64) -> Float64:
    """Simplified pit depth: depth ≈ 0.5*v² / (2*g) + 0.5 (metres).

    Includes buffer space of 0.5 m; g = 9.81 m/s².
    """
    return 0.5 * speed_mps * speed_mps / (2.0 * 9.81) + 0.5
