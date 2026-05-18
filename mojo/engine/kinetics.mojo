"""
kinetics.mojo — Chemical kinetics calculations. Zero Python imports.

Public API:
  reaction_rate_first_order    — rate = k * [A]
  reaction_rate_second_order   — rate = k * [A] * [B]
  arrhenius_rate_constant      — k = A * exp(-Ea/RT)
  half_life_first_order        — t½ = ln(2)/k
  half_life_second_order       — t½ = 1/(k*[A]0)
  concentration_first_order    — [A](t) = [A]0 * exp(-k*t)
  activation_energy            — Ea from two k values at two temperatures
  collision_frequency          — Z from kinetic theory
  michaelis_menten_rate        — v = Vmax*[S] / (Km + [S])
  turnover_number              — kcat = Vmax / [E]T
"""
from std.math import exp, log, sqrt


fn reaction_rate_first_order(rate_constant: Float64, concentration: Float64) -> Float64:
    """First-order reaction rate: r = k·[A].

    Args:
        rate_constant: Rate constant (s⁻¹).
        concentration: Reactant concentration (mol/L).

    Returns:
        Reaction rate (mol/L/s).
    """
    if rate_constant < 0.0 or concentration < 0.0:
        return 0.0
    return rate_constant * concentration


fn reaction_rate_second_order(
    rate_constant: Float64, conc_a: Float64, conc_b: Float64
) -> Float64:
    """Second-order reaction rate: r = k·[A]·[B].

    Args:
        rate_constant: Rate constant (L/mol/s).
        conc_a: Concentration of A (mol/L).
        conc_b: Concentration of B (mol/L).

    Returns:
        Reaction rate (mol/L/s).
    """
    if rate_constant < 0.0 or conc_a < 0.0 or conc_b < 0.0:
        return 0.0
    return rate_constant * conc_a * conc_b


fn arrhenius_rate_constant(
    pre_exponential: Float64, activation_energy: Float64, temperature: Float64
) -> Float64:
    """Arrhenius equation: k = A·exp(-Ea/RT).

    Args:
        pre_exponential: Pre-exponential factor A (same units as k).
        activation_energy: Activation energy (J/mol).
        temperature: Temperature (K).

    Returns:
        Rate constant.
    """
    if temperature <= 0.0 or pre_exponential < 0.0:
        return 0.0
    var R = 8.314  # J/(mol·K)
    return pre_exponential * exp(-activation_energy / (R * temperature))


fn half_life_first_order(rate_constant: Float64) -> Float64:
    """Half-life for a first-order reaction: t½ = ln2/k.

    Args:
        rate_constant: Rate constant (s⁻¹).

    Returns:
        Half-life (s).
    """
    if rate_constant <= 0.0:
        return 0.0
    return log(2.0) / rate_constant


fn half_life_second_order(
    rate_constant: Float64, initial_concentration: Float64
) -> Float64:
    """Half-life for a second-order reaction: t½ = 1/(k·[A]₀).

    Args:
        rate_constant: Rate constant (L/mol/s).
        initial_concentration: Initial concentration (mol/L).

    Returns:
        Half-life (s).
    """
    if rate_constant <= 0.0 or initial_concentration <= 0.0:
        return 0.0
    return 1.0 / (rate_constant * initial_concentration)


fn concentration_first_order(
    c0: Float64, rate_constant: Float64, time: Float64
) -> Float64:
    """Concentration remaining for first-order reaction.

    [A](t) = [A]₀ · exp(−k·t)

    Args:
        c0: Initial concentration (mol/L).
        rate_constant: Rate constant (s⁻¹).
        time: Time elapsed (s).

    Returns:
        Remaining concentration (mol/L).
    """
    if c0 < 0.0 or rate_constant < 0.0 or time < 0.0:
        return c0
    return c0 * exp(-rate_constant * time)


fn activation_energy(
    k1: Float64, k2: Float64, t1_k: Float64, t2_k: Float64
) -> Float64:
    """Activation energy from two rate constants at two temperatures.

    Ea = R · ln(k2/k1) / (1/T1 - 1/T2)

    Args:
        k1: Rate constant at temperature T1.
        k2: Rate constant at temperature T2.
        t1_k: Temperature T1 (K).
        t2_k: Temperature T2 (K).

    Returns:
        Activation energy (J/mol).
    """
    if k1 <= 0.0 or k2 <= 0.0 or t1_k <= 0.0 or t2_k <= 0.0:
        return 0.0
    var R = 8.314
    var denom = 1.0 / t1_k - 1.0 / t2_k
    if denom == 0.0:
        return 0.0
    return R * log(k2 / k1) / denom


fn collision_frequency(
    n_density: Float64, diameter: Float64, temperature: Float64, mass: Float64
) -> Float64:
    """Bimolecular collision frequency from kinetic theory.

    Z = n²·π·σ²·√(8kT/πm)

    Args:
        n_density: Number density (m⁻³).
        diameter: Collision diameter (m).
        temperature: Temperature (K).
        mass: Molecular mass (kg).

    Returns:
        Collision frequency (m⁻³ s⁻¹).
    """
    if n_density <= 0.0 or diameter <= 0.0 or temperature <= 0.0 or mass <= 0.0:
        return 0.0
    var kB = 1.380649e-23
    var pi = 3.141592653589793
    var v_rel = sqrt(8.0 * kB * temperature / (pi * mass))
    return n_density * n_density * pi * diameter * diameter * v_rel


fn michaelis_menten_rate(
    vmax: Float64, substrate: Float64, km: Float64
) -> Float64:
    """Michaelis-Menten enzyme kinetics: v = Vmax·[S] / (Km + [S]).

    Args:
        vmax: Maximum reaction velocity (mol/L/s).
        substrate: Substrate concentration [S] (mol/L).
        km: Michaelis constant (mol/L).

    Returns:
        Reaction rate (mol/L/s).
    """
    var denom = km + substrate
    if denom <= 0.0:
        return 0.0
    return vmax * substrate / denom


fn turnover_number(vmax: Float64, enzyme_total: Float64) -> Float64:
    """Enzyme turnover number: kcat = Vmax / [E]T.

    Args:
        vmax: Maximum velocity (mol/L/s).
        enzyme_total: Total enzyme concentration (mol/L).

    Returns:
        Turnover number kcat (s⁻¹).
    """
    if enzyme_total <= 0.0:
        return 0.0
    return vmax / enzyme_total
