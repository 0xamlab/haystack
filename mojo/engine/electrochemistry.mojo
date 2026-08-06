"""
electrochemistry.mojo — Electrochemical cell and corrosion calculations. Zero Python imports.

Public API:
  nernst_cell_potential        — E = E0 - (RT/nF)*ln(Q)
  faraday_mass_deposited       — m = M*I*t / (n*F)
  battery_capacity             — C = I * t (Ah)
  energy_density               — Wh/kg from V and capacity
  corrosion_rate               — mils per year from current density
  tafel_slope                  — b = 2.303*RT/(alpha*F)
  exchange_current_density     — i0 from rate constants
  charge_transfer_resistance   — Rct = RT / (n*F*i0)
  diffusion_limiting_current   — iL = n*F*D*c / delta
  coulombic_efficiency         — CE = charge_out / charge_in
"""
from std.math import log, exp, sqrt


def nernst_cell_potential(
    e0: Float64, n_electrons: Float64, temperature: Float64, reaction_quotient: Float64
) -> Float64:
    """Nernst equation for cell potential.

    E = E⁰ - (RT/nF)·ln(Q)

    Args:
        e0: Standard cell potential (V).
        n_electrons: Number of electrons transferred.
        temperature: Temperature (K).
        reaction_quotient: Reaction quotient Q.

    Returns:
        Cell potential (V).
    """
    if n_electrons <= 0.0 or reaction_quotient <= 0.0 or temperature <= 0.0:
        return e0
    var R = 8.314
    var F = 96485.0
    return e0 - (R * temperature / (n_electrons * F)) * log(reaction_quotient)


def faraday_mass_deposited(
    molar_mass: Float64, current: Float64, time_s: Float64, n_electrons: Float64
) -> Float64:
    """Mass deposited by electrolysis: m = M·I·t / (n·F).

    Args:
        molar_mass: Molar mass of depositing species (g/mol).
        current: Current (A).
        time_s: Time (s).
        n_electrons: Electrons per formula unit.

    Returns:
        Mass deposited (g).
    """
    if n_electrons <= 0.0:
        return 0.0
    var F = 96485.0
    return molar_mass * current * time_s / (n_electrons * F)


def battery_capacity(current: Float64, time_hours: Float64) -> Float64:
    """Battery capacity: C = I·t.

    Args:
        current: Discharge/charge current (A).
        time_hours: Time (hours).

    Returns:
        Capacity (Ah).
    """
    return current * time_hours


def energy_density(
    voltage: Float64, capacity_ah: Float64, mass_kg: Float64
) -> Float64:
    """Gravimetric energy density of a battery.

    Ed = V · C / mass  (Wh/kg)

    Args:
        voltage: Nominal voltage (V).
        capacity_ah: Capacity (Ah).
        mass_kg: Total battery mass (kg).

    Returns:
        Specific energy (Wh/kg).
    """
    if mass_kg <= 0.0:
        return 0.0
    return voltage * capacity_ah / mass_kg


def corrosion_rate(
    current_density: Float64, molar_mass: Float64,
    density: Float64, n_electrons: Float64
) -> Float64:
    """Corrosion rate in mils per year (mpy) from current density.

    CR = (i · M) / (n · F · ρ) × 1.288e5

    Args:
        current_density: Corrosion current density (A/m²).
        molar_mass: Molar mass of corroding metal (g/mol).
        density: Metal density (g/cm³).
        n_electrons: Valence electrons.

    Returns:
        Corrosion rate (mpy — mils per year).
    """
    if n_electrons <= 0.0 or density <= 0.0:
        return 0.0
    var F = 96485.0
    # CR in m/s, converted to mpy (1 m/s = 1.26e9 mpy; scaling for g/cm³)
    return (current_density * molar_mass / (n_electrons * F * density)) * 1.288e5


def tafel_slope(
    alpha: Float64, n_electrons: Float64, temperature: Float64
) -> Float64:
    """Tafel slope: b = 2.303·RT/(α·F).

    Args:
        alpha: Transfer coefficient (typically 0.5).
        n_electrons: Number of electrons.
        temperature: Temperature (K).

    Returns:
        Tafel slope (V/decade).
    """
    if alpha <= 0.0 or n_electrons <= 0.0 or temperature <= 0.0:
        return 0.0
    var R = 8.314
    var F = 96485.0
    return 2.303 * R * temperature / (alpha * n_electrons * F)


def exchange_current_density(
    k0: Float64, c_ox: Float64, c_red: Float64, alpha: Float64
) -> Float64:
    """Exchange current density from Butler-Volmer.

    i0 = F·k0·c_ox^α·c_red^(1-α)

    Args:
        k0: Standard rate constant (m/s).
        c_ox: Oxidised species concentration (mol/m³).
        c_red: Reduced species concentration (mol/m³).
        alpha: Transfer coefficient.

    Returns:
        Exchange current density (A/m²).
    """
    if k0 <= 0.0 or c_ox <= 0.0 or c_red <= 0.0:
        return 0.0
    var F = 96485.0
    from std.math import pow
    return F * k0 * pow(c_ox, alpha) * pow(c_red, 1.0 - alpha)


def charge_transfer_resistance(
    exchange_current: Float64, n_electrons: Float64, temperature: Float64
) -> Float64:
    """Charge transfer resistance: Rct = RT/(n·F·i0).

    Args:
        exchange_current: Exchange current density (A/m²).
        n_electrons: Number of electrons.
        temperature: Temperature (K).

    Returns:
        Charge transfer resistance (Ω·m²).
    """
    if exchange_current <= 0.0 or n_electrons <= 0.0 or temperature <= 0.0:
        return 0.0
    var R = 8.314
    var F = 96485.0
    return R * temperature / (n_electrons * F * exchange_current)


def diffusion_limiting_current(
    n_electrons: Float64, diffusivity: Float64,
    concentration: Float64, layer_thickness: Float64
) -> Float64:
    """Limiting diffusion current: iL = n·F·D·c/δ.

    Args:
        n_electrons: Number of electrons.
        diffusivity: Diffusion coefficient (m²/s).
        concentration: Bulk concentration (mol/m³).
        layer_thickness: Nernst diffusion layer thickness (m).

    Returns:
        Limiting current density (A/m²).
    """
    if layer_thickness <= 0.0:
        return 0.0
    var F = 96485.0
    return n_electrons * F * diffusivity * concentration / layer_thickness


def coulombic_efficiency(
    charge_out: Float64, charge_in: Float64
) -> Float64:
    """Coulombic efficiency of a charge/discharge cycle.

    CE = Q_out / Q_in

    Args:
        charge_out: Charge extracted during discharge (C or Ah).
        charge_in: Charge stored during charge (C or Ah).

    Returns:
        Coulombic efficiency (0–1).
    """
    if charge_in <= 0.0:
        return 0.0
    return charge_out / charge_in
