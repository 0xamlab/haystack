"""
welding.mojo — Welding Engineering Library. Zero Python imports.

Pure Mojo implementations of fundamental welding engineering equations
including heat input, carbon equivalent, cooling rate, dilution,
electrode consumption, joint efficiency, fillet weld sizing, and
hydrogen cracking risk assessment.

Public API:
  heat_input                  — HI = V*I/speed (J/mm)
  heat_input_kj               — HI in kJ/mm
  preheat_carbon_equivalent   — CE (IIW formula)
  cooling_rate_2d             — simplified 2D cooling rate
  weld_dilution               — dilution percentage
  electrode_consumption       — mass from length * rate
  welding_speed_from_deposition — speed from deposition params
  joint_efficiency            — weld/base strength ratio
  throat_thickness_fillet     — a = leg * 0.707
  allowable_shear_fillet      — F = throat * length * stress
  interpass_temperature_max   — Tmax from CE
  hydrogen_cracking_risk      — risk index from CE, H2, restraint
"""
from std.math import sqrt, abs as fabs


# ── heat_input ───────────────────────────────────────────────────────────────


def heat_input(voltage: Float64, current: Float64, travel_speed: Float64) -> Float64:
    """Heat input HI = V * I / speed (J/mm). travel_speed in mm/s."""
    return voltage * current / travel_speed


# ── heat_input_kj ────────────────────────────────────────────────────────────


def heat_input_kj(voltage: Float64, current: Float64, travel_speed_mm_min: Float64) -> Float64:
    """Heat input HI = V * I * 60 / (speed * 1000) (kJ/mm). Speed in mm/min."""
    return voltage * current * 60.0 / (travel_speed_mm_min * 1000.0)


# ── preheat_carbon_equivalent ────────────────────────────────────────────────


def preheat_carbon_equivalent(
    c: Float64, mn: Float64, cr: Float64, mo: Float64,
    v: Float64, ni: Float64, cu: Float64,
) -> Float64:
    """IIW carbon equivalent: CE = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15."""
    return c + mn / 6.0 + (cr + mo + v) / 5.0 + (ni + cu) / 15.0


# ── cooling_rate_2d ──────────────────────────────────────────────────────────


def cooling_rate_2d(hi: Float64, t0: Float64, tp: Float64) -> Float64:
    """Simplified 2D cooling rate ∝ (Tp - T0)² / HI."""
    return (tp - t0) * (tp - t0) / hi


# ── weld_dilution ────────────────────────────────────────────────────────────


def weld_dilution(base_area: Float64, weld_area: Float64) -> Float64:
    """Dilution D = base_area / (base_area + weld_area) * 100 (%)."""
    return base_area / (base_area + weld_area) * 100.0


# ── electrode_consumption ────────────────────────────────────────────────────


def electrode_consumption(length: Float64, deposition_rate: Float64) -> Float64:
    """Mass = length * deposition_rate (kg)."""
    return length * deposition_rate


# ── welding_speed_from_deposition ────────────────────────────────────────────


def welding_speed_from_deposition(
    deposition_rate: Float64, cross_section: Float64, density: Float64,
) -> Float64:
    """Speed = deposition_rate / (cross_section * density)."""
    return deposition_rate / (cross_section * density)


# ── joint_efficiency ─────────────────────────────────────────────────────────


def joint_efficiency(weld_strength: Float64, base_strength: Float64) -> Float64:
    """JE = weld_strength / base_strength * 100 (%)."""
    return weld_strength / base_strength * 100.0


# ── throat_thickness_fillet ──────────────────────────────────────────────────


def throat_thickness_fillet(leg_size: Float64) -> Float64:
    """Throat thickness a = leg * 0.707 ≈ leg / sqrt(2)."""
    return leg_size * 0.707


# ── allowable_shear_fillet ───────────────────────────────────────────────────


def allowable_shear_fillet(
    throat: Float64, length: Float64, allowable_stress: Float64,
) -> Float64:
    """Allowable shear force F = throat * length * allowable_stress."""
    return throat * length * allowable_stress


# ── interpass_temperature_max ────────────────────────────────────────────────


def interpass_temperature_max(carbon_equivalent: Float64) -> Float64:
    """Tmax ≈ 350 - 200 * CE (simplified, °C)."""
    return 350.0 - 200.0 * carbon_equivalent


# ── hydrogen_cracking_risk ───────────────────────────────────────────────────


def hydrogen_cracking_risk(
    ce: Float64, hydrogen_ml: Float64, restraint_level: Float64,
) -> Float64:
    """Risk index = CE*10 + hydrogen*0.5 + restraint."""
    return ce * 10.0 + hydrogen_ml * 0.5 + restraint_level
