"""
nuclear.mojo — Nuclear Physics & Engineering Library. Zero Python imports.

Pure Mojo implementations of nuclear physics calculations including
radioactive decay, half-life, activity, binding energy, mass defect,
Q-value, neutron multiplication, dose rate, and shielding attenuation.

Public API:
  radioactive_decay            — N(t) = N0 * exp(-λ*t)
  half_life_from_lambda        — t½ = ln(2)/λ
  lambda_from_half_life        — λ = ln(2)/t½
  activity                     — A = λ*N
  decay_constant_from_activity — λ = A/N
  binding_energy_per_nucleon   — BE/A
  mass_defect                  — Δm = Z*mp + N*mn - M
  q_value                      — Q = (m_r - m_p)*c²
  neutron_multiplication       — N = k^generation
  dose_rate_inverse_square     — D = D_ref*(d_ref/d)²
  shielding_attenuation        — I = I0*exp(-μ*x)
  critical_mass_estimate       — Proportionality: ρ*σ_f*ν
"""
from std.math import log, exp, pow, abs as fabs


# ── Constants ────────────────────────────────────────────────────────────────

comptime LN2: Float64 = 0.6931471805599453


# ── radioactive_decay ────────────────────────────────────────────────────────


fn radioactive_decay(n0: Float64, lambda_val: Float64, t: Float64) -> Float64:
    """Radioactive decay: N(t) = N0 * exp(-λ*t).

    Args:
        n0: Initial number of atoms.
        lambda_val: Decay constant (1/s or 1/yr).
        t: Time elapsed.

    Returns:
        Remaining atoms N(t).
    """
    return n0 * exp(-lambda_val * t)


# ── half_life_from_lambda ────────────────────────────────────────────────────


fn half_life_from_lambda(lambda_val: Float64) -> Float64:
    """Half-life from decay constant: t½ = ln(2)/λ.

    Args:
        lambda_val: Decay constant.

    Returns:
        Half-life.
    """
    if fabs(lambda_val) < 1e-30:
        return 0.0
    return LN2 / lambda_val


# ── lambda_from_half_life ────────────────────────────────────────────────────


fn lambda_from_half_life(half_life: Float64) -> Float64:
    """Decay constant from half-life: λ = ln(2)/t½.

    Args:
        half_life: Half-life.

    Returns:
        Decay constant.
    """
    if fabs(half_life) < 1e-30:
        return 0.0
    return LN2 / half_life


# ── activity ─────────────────────────────────────────────────────────────────


fn activity(lambda_val: Float64, n: Float64) -> Float64:
    """Activity: A = λ*N (disintegrations per second).

    Args:
        lambda_val: Decay constant.
        n: Number of atoms.

    Returns:
        Activity (Bq).
    """
    return lambda_val * n


# ── decay_constant_from_activity ─────────────────────────────────────────────


fn decay_constant_from_activity(activity_val: Float64, n: Float64) -> Float64:
    """Decay constant from activity: λ = A/N.

    Args:
        activity_val: Measured activity.
        n: Number of atoms.

    Returns:
        Decay constant.
    """
    if fabs(n) < 1e-30:
        return 0.0
    return activity_val / n


# ── binding_energy_per_nucleon ───────────────────────────────────────────────


fn binding_energy_per_nucleon(total_be: Float64, a: Float64) -> Float64:
    """Binding energy per nucleon: BE/A.

    Args:
        total_be: Total binding energy (MeV).
        a: Mass number (nucleons).

    Returns:
        Binding energy per nucleon (MeV).
    """
    if fabs(a) < 1e-30:
        return 0.0
    return total_be / a


# ── mass_defect ──────────────────────────────────────────────────────────────


fn mass_defect(
    z: Float64,
    n: Float64,
    atomic_mass: Float64,
    mp: Float64,
    mn: Float64,
) -> Float64:
    """Mass defect: Δm = Z*mp + N*mn - M.

    Args:
        z: Number of protons.
        n: Number of neutrons.
        atomic_mass: Measured atomic mass (u).
        mp: Proton mass (u).
        mn: Neutron mass (u).

    Returns:
        Mass defect (u).
    """
    return z * mp + n * mn - atomic_mass


# ── q_value ──────────────────────────────────────────────────────────────────


fn q_value(
    mass_reactants: Float64, mass_products: Float64, c2: Float64
) -> Float64:
    """Q-value of a nuclear reaction: Q = (m_r - m_p) * c².

    Args:
        mass_reactants: Total mass of reactants (u).
        mass_products: Total mass of products (u).
        c2: Conversion factor c² (MeV/u), typically 931.5.

    Returns:
        Q-value (MeV).
    """
    return (mass_reactants - mass_products) * c2


# ── neutron_multiplication ───────────────────────────────────────────────────


fn neutron_multiplication(k_eff: Float64, generation: Float64) -> Float64:
    """Neutron multiplication: N = k^generation.

    Args:
        k_eff: Effective multiplication factor.
        generation: Number of generations.

    Returns:
        Neutron population multiplier.
    """
    return pow(k_eff, generation)


# ── dose_rate_inverse_square ─────────────────────────────────────────────────


fn dose_rate_inverse_square(
    dose_ref: Float64, d_ref: Float64, d: Float64
) -> Float64:
    """Inverse square law for dose: D = D_ref * (d_ref/d)².

    Args:
        dose_ref: Reference dose rate.
        d_ref: Reference distance.
        d: New distance.

    Returns:
        Dose rate at distance d.
    """
    if fabs(d) < 1e-30:
        return 0.0
    var ratio = d_ref / d
    return dose_ref * ratio * ratio


# ── shielding_attenuation ───────────────────────────────────────────────────


fn shielding_attenuation(
    intensity0: Float64, mu: Float64, thickness: Float64
) -> Float64:
    """Shielding attenuation: I = I0 * exp(-μ*x).

    Args:
        intensity0: Initial intensity.
        mu: Linear attenuation coefficient (1/cm).
        thickness: Shield thickness (cm).

    Returns:
        Attenuated intensity.
    """
    return intensity0 * exp(-mu * thickness)


# ── critical_mass_estimate ───────────────────────────────────────────────────


fn critical_mass_estimate(
    density: Float64, sigma_f: Float64, nu: Float64
) -> Float64:
    """Simplified critical mass proportionality: m_c ∝ ρ*σ_f*ν.

    Returns density * sigma_f * nu as a proportionality factor.

    Args:
        density: Material density (kg/m³).
        sigma_f: Fission cross-section (barns).
        nu: Average neutrons per fission.

    Returns:
        Proportionality factor (not actual mass).
    """
    return density * sigma_f * nu
