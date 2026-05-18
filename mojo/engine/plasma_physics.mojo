"""
plasma_physics.mojo — Plasma properties and fusion energy calculations. Zero Python imports.

Public API:
  debye_length                 — λD = sqrt(ε0*kT / n*e²)
  plasma_frequency             — ωp = sqrt(n*e²/(ε0*m))
  thermal_velocity             — vth = sqrt(kT/m)
  larmor_radius                — rL = m*v⊥/(|q|*B)
  coulomb_logarithm            — ln(Λ) from plasma parameters
  spitzer_resistivity          — η = Z * e² * m_e^0.5 / (12π^1.5 * ε0² * (kT)^1.5)
  alfven_speed                 — vA = B / sqrt(μ0*ρ)
  mhd_beta                     — β = 2μ0*nkT / B²
  fusion_lawson_criterion      — nτ product for ignition
  bremsstrahlung_power         — P_br ∝ n²*sqrt(T)
"""
from std.math import sqrt, log, exp, pow


fn debye_length(temperature_ev: Float64, electron_density: Float64) -> Float64:
    """Debye shielding length in a plasma.

    λD = sqrt(ε0·kT / n·e²)

    Args:
        temperature_ev: Electron temperature (eV).
        electron_density: Electron number density (m⁻³).

    Returns:
        Debye length (m).
    """
    if temperature_ev <= 0.0 or electron_density <= 0.0:
        return 0.0
    var epsilon0 = 8.854e-12
    var kT = temperature_ev * 1.602e-19  # eV → J
    var e = 1.602e-19
    return sqrt(epsilon0 * kT / (electron_density * e * e))


fn plasma_frequency(electron_density: Float64) -> Float64:
    """Electron plasma frequency ωp = sqrt(n·e²/(ε0·me)).

    Args:
        electron_density: Electron number density (m⁻³).

    Returns:
        Plasma (angular) frequency (rad/s).
    """
    if electron_density <= 0.0:
        return 0.0
    var e = 1.602e-19
    var me = 9.109e-31
    var epsilon0 = 8.854e-12
    return sqrt(electron_density * e * e / (epsilon0 * me))


fn thermal_velocity(temperature_ev: Float64, mass_kg: Float64) -> Float64:
    """Thermal velocity: vth = sqrt(kT/m).

    Args:
        temperature_ev: Temperature (eV).
        mass_kg: Particle mass (kg).

    Returns:
        Thermal velocity (m/s).
    """
    if temperature_ev <= 0.0 or mass_kg <= 0.0:
        return 0.0
    var kT = temperature_ev * 1.602e-19
    return sqrt(kT / mass_kg)


fn larmor_radius(
    mass_kg: Float64, velocity_perp: Float64, charge: Float64, b_field: Float64
) -> Float64:
    """Larmor (gyro) radius of a particle in a magnetic field.

    rL = m·v⊥ / (|q|·B)

    Args:
        mass_kg: Particle mass (kg).
        velocity_perp: Velocity perpendicular to B (m/s).
        charge: Charge magnitude (C).
        b_field: Magnetic field (T).

    Returns:
        Larmor radius (m).
    """
    if charge <= 0.0 or b_field <= 0.0:
        return 0.0
    return mass_kg * velocity_perp / (charge * b_field)


fn coulomb_logarithm(temperature_ev: Float64, electron_density: Float64) -> Float64:
    """Coulomb logarithm ln(Λ) for electron-ion collisions.

    Simplified: ln(Λ) ≈ 24 - ln(sqrt(n) / T) for T > 10 eV

    Args:
        temperature_ev: Temperature (eV).
        electron_density: Electron density (m⁻³).

    Returns:
        Coulomb logarithm (dimensionless, typically 10–20).
    """
    if temperature_ev <= 0.0 or electron_density <= 0.0:
        return 10.0
    return 24.0 - log(sqrt(electron_density / 1e6) / temperature_ev)


fn spitzer_resistivity(temperature_ev: Float64, z_eff: Float64) -> Float64:
    """Spitzer resistivity of a plasma.

    η ∝ Z_eff / T^1.5  (in Ω·m, simplified proportionality)

    Args:
        temperature_ev: Electron temperature (eV).
        z_eff: Effective charge number Z_eff.

    Returns:
        Resistivity (Ω·m, approximate).
    """
    if temperature_ev <= 0.0:
        return 0.0
    # η ≈ 5.2e-5 * Z_eff * ln(Λ) / T_eV^1.5  (Ω·m)
    var ln_lambda = 15.0  # typical value
    return 5.2e-5 * z_eff * ln_lambda / pow(temperature_ev, 1.5)


fn alfven_speed(b_field: Float64, mass_density: Float64) -> Float64:
    """Alfvén speed: vA = B / sqrt(μ0·ρ).

    Args:
        b_field: Magnetic field (T).
        mass_density: Plasma mass density (kg/m³).

    Returns:
        Alfvén speed (m/s).
    """
    if mass_density <= 0.0:
        return 0.0
    var mu0 = 1.2566e-6
    return b_field / sqrt(mu0 * mass_density)


fn mhd_beta(
    electron_density: Float64, temperature_ev: Float64, b_field: Float64
) -> Float64:
    """MHD β: ratio of plasma pressure to magnetic pressure.

    β = 2μ0·n·kT / B²

    Args:
        electron_density: Electron density (m⁻³).
        temperature_ev: Temperature (eV).
        b_field: Magnetic field (T).

    Returns:
        β (dimensionless). β << 1 = magnetically confined.
    """
    if b_field <= 0.0:
        return 0.0
    var mu0 = 1.2566e-6
    var kT = temperature_ev * 1.602e-19
    return 2.0 * mu0 * electron_density * kT / (b_field * b_field)


fn fusion_lawson_criterion(
    electron_density: Float64, confinement_time: Float64
) -> Float64:
    """Lawson parameter nτ for DT fusion ignition.

    Ignition requires n·τ > ~2e20 m⁻³·s.

    Args:
        electron_density: Electron density n (m⁻³).
        confinement_time: Energy confinement time τE (s).

    Returns:
        Lawson parameter nτ (m⁻³·s).
    """
    return electron_density * confinement_time


fn bremsstrahlung_power(
    electron_density: Float64, ion_density: Float64, temperature_ev: Float64, z: Float64
) -> Float64:
    """Bremsstrahlung radiation power density from thermal plasma.

    P_br ∝ Z²·ne·ni·√T   (W/m³, simplified)

    Args:
        electron_density: Electron density (m⁻³).
        ion_density: Ion density (m⁻³).
        temperature_ev: Electron temperature (eV).
        z: Average charge number Z.

    Returns:
        Bremsstrahlung power density (W/m³, approximate).
    """
    if temperature_ev <= 0.0:
        return 0.0
    # Simplified coefficient ~5.35e-37 in SI
    return 5.35e-37 * z * z * electron_density * ion_density * sqrt(temperature_ev)
