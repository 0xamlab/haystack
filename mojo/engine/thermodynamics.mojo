"""
thermodynamics.mojo — Thermodynamics equations. Zero Python imports.

Replaces custom thermo code with pure Mojo implementations of ideal gas law,
Carnot efficiency, entropy change, heat capacity, adiabatic processes,
isothermal work, Stefan-Boltzmann radiation, thermal conductivity,
Gibbs free energy, and Clausius-Clapeyron equation.

Public API:
  ideal_gas_pressure        — P = nRT/V
  ideal_gas_volume          — V = nRT/P
  carnot_efficiency         — η = 1 - T_cold/T_hot
  entropy_change            — ΔS = Q/T
  heat_capacity             — Q = mcΔT
  adiabatic_process         — P2 = P1*(V1/V2)^γ
  work_isothermal           — W = nRT*ln(V2/V1)
  stefan_boltzmann          — P = εσAT⁴
  thermal_conductivity_flux — Q/t = -kA(dT/dx)
  gibbs_free_energy         — G = H - TS
  clausius_clapeyron        — ln(P2/P1) = -(ΔH/R)*(1/T2 - 1/T1)
"""
from std.math import log, pow, exp, abs as fabs


# ── Constants ────────────────────────────────────────────────────────────────

comptime R_GAS: Float64 = 8.314  # J/(mol·K)
comptime STEFAN_BOLTZMANN: Float64 = 5.67e-8  # W/(m²·K⁴)


# ── ideal_gas_pressure ───────────────────────────────────────────────────────


fn ideal_gas_pressure(n: Float64, T: Float64, V: Float64) -> Float64:
    """Ideal gas law: P = nRT/V.

    Args:
        n: Amount of substance (mol).
        T: Temperature (K).
        V: Volume (m³).

    Returns:
        Pressure in Pa.
    """
    if fabs(V) < 1e-30:
        return 0.0
    return n * R_GAS * T / V


# ── ideal_gas_volume ─────────────────────────────────────────────────────────


fn ideal_gas_volume(n: Float64, T: Float64, P: Float64) -> Float64:
    """Ideal gas law: V = nRT/P.

    Args:
        n: Amount of substance (mol).
        T: Temperature (K).
        P: Pressure (Pa).

    Returns:
        Volume in m³.
    """
    if fabs(P) < 1e-30:
        return 0.0
    return n * R_GAS * T / P


# ── carnot_efficiency ────────────────────────────────────────────────────────


fn carnot_efficiency(T_hot: Float64, T_cold: Float64) -> Float64:
    """Carnot efficiency: η = 1 - T_cold/T_hot.

    Args:
        T_hot:  Hot reservoir temperature (K).
        T_cold: Cold reservoir temperature (K).

    Returns:
        Efficiency (dimensionless, 0 to 1).
    """
    if fabs(T_hot) < 1e-30:
        return 0.0
    return 1.0 - T_cold / T_hot


# ── entropy_change ───────────────────────────────────────────────────────────


fn entropy_change(Q: Float64, T: Float64) -> Float64:
    """Entropy change: ΔS = Q/T.

    Args:
        Q: Heat transferred (J).
        T: Temperature (K).

    Returns:
        Entropy change in J/K.
    """
    if fabs(T) < 1e-30:
        return 0.0
    return Q / T


# ── heat_capacity ────────────────────────────────────────────────────────────


fn heat_capacity(mass: Float64, specific_heat: Float64, delta_T: Float64) -> Float64:
    """Heat capacity: Q = mcΔT.

    Args:
        mass:          Mass (kg).
        specific_heat: Specific heat capacity (J/(kg·K)).
        delta_T:       Temperature change (K).

    Returns:
        Heat energy in J.
    """
    return mass * specific_heat * delta_T


# ── adiabatic_process ────────────────────────────────────────────────────────


fn adiabatic_process(P1: Float64, V1: Float64, V2: Float64, gamma: Float64) -> Float64:
    """Adiabatic process: P2 = P1*(V1/V2)^γ.

    Args:
        P1:    Initial pressure (Pa).
        V1:    Initial volume (m³).
        V2:    Final volume (m³).
        gamma: Heat capacity ratio.

    Returns:
        Final pressure P2 in Pa.
    """
    if fabs(V2) < 1e-30:
        return 0.0
    return P1 * pow(V1 / V2, gamma)


# ── work_isothermal ──────────────────────────────────────────────────────────


fn work_isothermal(n: Float64, T: Float64, V1: Float64, V2: Float64) -> Float64:
    """Isothermal work: W = nRT*ln(V2/V1).

    Args:
        n:  Amount of substance (mol).
        T:  Temperature (K).
        V1: Initial volume (m³).
        V2: Final volume (m³).

    Returns:
        Work done in J.
    """
    if fabs(V1) < 1e-30 or V2 / V1 <= 0.0:
        return 0.0
    return n * R_GAS * T * log(V2 / V1)


# ── stefan_boltzmann ─────────────────────────────────────────────────────────


fn stefan_boltzmann(T: Float64, A: Float64, emissivity: Float64 = 1.0) -> Float64:
    """Stefan-Boltzmann law: P = εσAT⁴.

    Args:
        T:          Temperature (K).
        A:          Surface area (m²).
        emissivity: Emissivity (0 to 1, default 1.0).

    Returns:
        Radiated power in W.
    """
    return emissivity * STEFAN_BOLTZMANN * A * pow(T, 4.0)


# ── thermal_conductivity_flux ────────────────────────────────────────────────


fn thermal_conductivity_flux(k: Float64, A: Float64, dT: Float64, dx: Float64) -> Float64:
    """Fourier's law: Q/t = -kA(dT/dx).

    Args:
        k:  Thermal conductivity (W/(m·K)).
        A:  Cross-sectional area (m²).
        dT: Temperature difference (K).
        dx: Thickness (m).

    Returns:
        Heat flux in W (magnitude, positive).
    """
    if fabs(dx) < 1e-30:
        return 0.0
    return -k * A * dT / dx


# ── gibbs_free_energy ────────────────────────────────────────────────────────


fn gibbs_free_energy(H: Float64, T: Float64, S: Float64) -> Float64:
    """Gibbs free energy: G = H - TS.

    Args:
        H: Enthalpy (J).
        T: Temperature (K).
        S: Entropy (J/K).

    Returns:
        Gibbs free energy in J.
    """
    return H - T * S


# ── clausius_clapeyron ───────────────────────────────────────────────────────


fn clausius_clapeyron(P1: Float64, T1: Float64, T2: Float64, dH_vap: Float64) -> Float64:
    """Clausius-Clapeyron equation: ln(P2/P1) = -(ΔH/R)*(1/T2 - 1/T1).

    Args:
        P1:     Initial pressure (Pa).
        T1:     Initial temperature (K).
        T2:     Final temperature (K).
        dH_vap: Enthalpy of vaporization (J/mol).

    Returns:
        Final pressure P2 in Pa.
    """
    if fabs(T1) < 1e-30 or fabs(T2) < 1e-30:
        return 0.0
    var exponent = -(dH_vap / R_GAS) * (1.0 / T2 - 1.0 / T1)
    return P1 * exp(exponent)
