"""
electrical.mojo — Electrical Engineering equations. Zero Python imports.

Replaces custom EE code with pure Mojo implementations of Ohm's law,
power, series/parallel resistance, RC/RLC circuits, impedance, and
reactance.

Public API:
  ohms_law_v            — V = IR
  ohms_law_i            — I = V/R
  ohms_law_r            — R = V/I
  power_dc              — P = VI
  series_resistance     — R_total = ΣR
  parallel_resistance   — 1/R_total = Σ(1/Ri)
  rc_time_constant      — τ = RC
  rc_voltage            — V(t) = V0·(1 - e^(-t/RC))
  rlc_resonance         — f₀ = 1/(2π√(LC))
  impedance_magnitude   — |Z| = √(R² + X²)
  power_factor          — PF = P/S
  capacitive_reactance  — Xc = 1/(2πfC)
  inductive_reactance   — Xl = 2πfL
  voltage_divider       — V_out = V_in·R2/(R1+R2)
"""
from std.math import sqrt, exp


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793


# ── ohms_law_v ───────────────────────────────────────────────────────────────


def ohms_law_v(I: Float64, R: Float64) -> Float64:
    """Voltage: V = I·R."""
    return I * R


# ── ohms_law_i ───────────────────────────────────────────────────────────────


def ohms_law_i(V: Float64, R: Float64) -> Float64:
    """Current: I = V/R."""
    return V / R


# ── ohms_law_r ───────────────────────────────────────────────────────────────


def ohms_law_r(V: Float64, I: Float64) -> Float64:
    """Resistance: R = V/I."""
    return V / I


# ── power_dc ─────────────────────────────────────────────────────────────────


def power_dc(V: Float64, I: Float64) -> Float64:
    """DC power: P = V·I."""
    return V * I


# ── series_resistance ────────────────────────────────────────────────────────


def series_resistance(resistors: List[Float64]) -> Float64:
    """Total series resistance: R_total = ΣR."""
    var total: Float64 = 0.0
    for i in range(len(resistors)):
        total += resistors[i]
    return total


# ── parallel_resistance ──────────────────────────────────────────────────────


def parallel_resistance(resistors: List[Float64]) -> Float64:
    """Total parallel resistance: 1/R_total = Σ(1/Ri)."""
    var inv_total: Float64 = 0.0
    for i in range(len(resistors)):
        inv_total += 1.0 / resistors[i]
    if inv_total == 0.0:
        return 0.0
    return 1.0 / inv_total


# ── rc_time_constant ────────────────────────────────────────────────────────


def rc_time_constant(R: Float64, C: Float64) -> Float64:
    """RC time constant: τ = R·C."""
    return R * C


# ── rc_voltage ───────────────────────────────────────────────────────────────


def rc_voltage(V0: Float64, R: Float64, C: Float64, t: Float64) -> Float64:
    """Charging voltage: V(t) = V0·(1 - e^(-t/(RC)))."""
    var tau = R * C
    return V0 * (1.0 - exp(-t / tau))


# ── rlc_resonance ────────────────────────────────────────────────────────────


def rlc_resonance(L: Float64, C: Float64) -> Float64:
    """Resonant frequency: f₀ = 1/(2π√(LC))."""
    return 1.0 / (2.0 * PI * sqrt(L * C))


# ── impedance_magnitude ──────────────────────────────────────────────────────


def impedance_magnitude(R: Float64, X: Float64) -> Float64:
    """Impedance magnitude: |Z| = √(R² + X²)."""
    return sqrt(R * R + X * X)


# ── power_factor ─────────────────────────────────────────────────────────────


def power_factor(real_power: Float64, apparent_power: Float64) -> Float64:
    """Power factor: PF = P/S."""
    return real_power / apparent_power


# ── capacitive_reactance ─────────────────────────────────────────────────────


def capacitive_reactance(C: Float64, f: Float64) -> Float64:
    """Capacitive reactance: Xc = 1/(2πfC)."""
    return 1.0 / (2.0 * PI * f * C)


# ── inductive_reactance ──────────────────────────────────────────────────────


def inductive_reactance(L: Float64, f: Float64) -> Float64:
    """Inductive reactance: Xl = 2πfL."""
    return 2.0 * PI * f * L


# ── voltage_divider ──────────────────────────────────────────────────────────


def voltage_divider(V_in: Float64, R1: Float64, R2: Float64) -> Float64:
    """Voltage divider: V_out = V_in·R2/(R1+R2)."""
    return V_in * R2 / (R1 + R2)
