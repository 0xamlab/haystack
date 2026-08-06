"""
adhesives.mojo — Adhesives Technology Library.

Provides bond-strength, curing, viscosity, and surface-energy calculations
for adhesive bonding applications.

Public API:
  lap_shear_strength              — τ = F / A (MPa)
  peel_strength                   — PS = F / W (N/mm)
  bond_line_thickness             — Returns gap directly (mm)
  coverage_rate                   — CR = volume / area (mL/m²)
  pot_life_temperature_adjusted   — PL = ref * factor^((ref_temp-temp)/10)
  cure_time_temperature           — CT = base / accel^((temp-ref)/10)
  joint_efficiency                — JE = bond / substrate * 100
  thermal_cycle_life              — Life ≈ n / (ΔT * Δα * t) simplified
  viscosity_temperature           — η = η_ref * exp(Ea/R*(1/T - 1/T_ref))
  surface_energy_contact_angle    — γ_s ≈ γ_l * (1+cos θ)² / 4
  open_time_estimate              — OT ≈ viscosity/100 * (1+(25-temp)*0.05)
  bond_area_from_load             — A = F * SF / τ
"""
from std.math import exp, cos, log
from std.math import abs as fabs

comptime PI: Float64 = 3.141592653589793


# ── lap_shear_strength ───────────────────────────────────────────────────────


def lap_shear_strength(force: Float64, bond_area: Float64) -> Float64:
    """Lap shear strength: τ = F / A (MPa).

    Args:
        force: Applied force (N).
        bond_area: Bond area (mm²).

    Returns:
        Shear strength (MPa = N/mm²).
    """
    return force / bond_area


# ── peel_strength ────────────────────────────────────────────────────────────


def peel_strength(force: Float64, width: Float64) -> Float64:
    """Peel strength: PS = F / W (N/mm).

    Args:
        force: Peel force (N).
        width: Bond width (mm).

    Returns:
        Peel strength (N/mm).
    """
    return force / width


# ── bond_line_thickness ──────────────────────────────────────────────────────


def bond_line_thickness(gap: Float64) -> Float64:
    """Bond line thickness — returns the gap value directly (mm).

    Optimal range is 0.05–0.25 mm for structural adhesives.

    Args:
        gap: Measured or designed gap (mm).

    Returns:
        Bond line thickness (mm).
    """
    return gap


# ── coverage_rate ────────────────────────────────────────────────────────────


def coverage_rate(volume_ml: Float64, area_m2: Float64) -> Float64:
    """Coverage rate: CR = volume / area (mL/m²).

    Args:
        volume_ml: Volume of adhesive used (mL).
        area_m2: Bonded area (m²).

    Returns:
        Coverage rate (mL/m²).
    """
    return volume_ml / area_m2


# ── pot_life_temperature_adjusted ────────────────────────────────────────────


def pot_life_temperature_adjusted(
    pot_life_ref: Float64,
    temp: Float64,
    ref_temp: Float64,
    factor: Float64,
) -> Float64:
    """Temperature-adjusted pot life: PL = ref * factor^((ref_temp - temp)/10).

    Args:
        pot_life_ref: Pot life at reference temperature (minutes).
        temp: Actual temperature (°C).
        ref_temp: Reference temperature (°C).
        factor: Temperature acceleration factor (typically ~2).

    Returns:
        Adjusted pot life (minutes).
    """
    comptime exponent_scale: Float64 = 10.0
    var exponent = (ref_temp - temp) / exponent_scale
    # factor^exponent = exp(exponent * ln(factor))
    return pot_life_ref * exp(exponent * log(factor))


# ── cure_time_temperature ────────────────────────────────────────────────────


def cure_time_temperature(
    base_time: Float64,
    temp: Float64,
    ref_temp: Float64,
    acceleration: Float64,
) -> Float64:
    """Temperature-adjusted cure time: CT = base / accel^((temp-ref)/10).

    Args:
        base_time: Cure time at reference temperature (minutes).
        temp: Actual temperature (°C).
        ref_temp: Reference temperature (°C).
        acceleration: Acceleration factor per 10°C (typically ~2).

    Returns:
        Adjusted cure time (minutes).
    """
    comptime exponent_scale: Float64 = 10.0
    var exponent = (temp - ref_temp) / exponent_scale
    return base_time / exp(exponent * log(acceleration))


# ── joint_efficiency ─────────────────────────────────────────────────────────


def joint_efficiency(bond_strength: Float64, substrate_strength: Float64) -> Float64:
    """Joint efficiency: JE = bond / substrate * 100 (%).

    Args:
        bond_strength: Bond failure strength (MPa).
        substrate_strength: Substrate failure strength (MPa).

    Returns:
        Joint efficiency (%).
    """
    return bond_strength / substrate_strength * 100.0


# ── thermal_cycle_life ───────────────────────────────────────────────────────


def thermal_cycle_life(
    n_cycles: Float64,
    delta_t: Float64,
    cte_mismatch: Float64,
    thickness: Float64,
) -> Float64:
    """Simplified thermal cycle life: Life ≈ n / (ΔT * Δα * t).

    Args:
        n_cycles: Reference cycle count.
        delta_t: Temperature range (°C).
        cte_mismatch: CTE mismatch between substrates (1/°C).
        thickness: Bond line thickness (mm).

    Returns:
        Estimated cycle life (cycles).
    """
    return n_cycles / (delta_t * cte_mismatch * thickness)


# ── viscosity_temperature ────────────────────────────────────────────────────


def viscosity_temperature(
    viscosity_ref: Float64,
    activation_energy: Float64,
    r: Float64,
    t: Float64,
    t_ref: Float64,
) -> Float64:
    """Arrhenius viscosity model: η = η_ref * exp(Ea/R*(1/T - 1/T_ref)).

    Args:
        viscosity_ref: Viscosity at reference temperature (Pa·s).
        activation_energy: Activation energy (J/mol).
        r: Gas constant (J/(mol·K)).
        t: Temperature (K).
        t_ref: Reference temperature (K).

    Returns:
        Viscosity at temperature T (Pa·s).
    """
    return viscosity_ref * exp(activation_energy / r * (1.0 / t - 1.0 / t_ref))


# ── surface_energy_contact_angle ─────────────────────────────────────────────


def surface_energy_contact_angle(gamma_l: Float64, contact_angle_deg: Float64) -> Float64:
    """Surface energy from contact angle (Young-Dupré):
    γ_s ≈ γ_l * (1 + cos θ)² / 4.

    Args:
        gamma_l: Liquid surface tension (mN/m).
        contact_angle_deg: Contact angle (degrees).

    Returns:
        Estimated solid surface energy (mN/m).
    """
    var theta_rad = contact_angle_deg * PI / 180.0
    var term = 1.0 + cos(theta_rad)
    return gamma_l * term * term / 4.0


# ── open_time_estimate ───────────────────────────────────────────────────────


def open_time_estimate(viscosity: Float64, temperature: Float64) -> Float64:
    """Empirical open time estimate: OT ≈ viscosity/100 * (1 + (25-temp)*0.05).

    Args:
        viscosity: Initial viscosity (Pa·s).
        temperature: Ambient temperature (°C).

    Returns:
        Estimated open time (minutes).
    """
    return viscosity / 100.0 * (1.0 + (25.0 - temperature) * 0.05)


# ── bond_area_from_load ──────────────────────────────────────────────────────


def bond_area_from_load(
    design_load: Float64,
    allowable_stress: Float64,
    safety_factor: Float64,
) -> Float64:
    """Required bond area: A = F * SF / τ (mm²).

    Args:
        design_load: Design load (N).
        allowable_stress: Allowable shear stress (MPa).
        safety_factor: Safety factor (≥1).

    Returns:
        Required bond area (mm²).
    """
    return design_load * safety_factor / allowable_stress
