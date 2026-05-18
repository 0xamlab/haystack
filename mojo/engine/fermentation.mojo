"""
fermentation.mojo — Fermentation science and bioprocess calculations. Zero Python imports.

Public API:
  ethanol_yield                — yield from glucose (Gay-Lussac)
  alcohol_by_volume            — ABV from OG and FG (hydrometer)
  carbon_dioxide_produced      — CO2 from fermented glucose mass
  yeast_growth_rate            — specific growth rate (Monod)
  substrate_consumption        — dS/dt from biomass and yield
  volumetric_productivity      — P = product_conc / time
  fermentation_efficiency      — actual vs theoretical yield
  dissolved_oxygen_kla         — oxygen transfer rate from kLa
  ph_buffer_capacity           — buffering capacity near pKa
  heat_generation_rate         — heat from metabolic activity
"""
from std.math import exp, log


fn ethanol_yield(glucose_g: Float64) -> Float64:
    """Theoretical ethanol yield from glucose fermentation.

    C6H12O6 → 2 C2H5OH + 2 CO2
    Yield = 0.511 g EtOH / g glucose (Gay-Lussac)

    Args:
        glucose_g: Mass of glucose consumed (g).

    Returns:
        Theoretical ethanol mass (g).
    """
    return 0.511 * glucose_g


fn alcohol_by_volume(original_gravity: Float64, final_gravity: Float64) -> Float64:
    """Alcohol by volume from hydrometer readings (simplified).

    ABV ≈ (OG - FG) × 131.25

    Args:
        original_gravity: Original specific gravity (e.g. 1.060).
        final_gravity: Final specific gravity (e.g. 1.010).

    Returns:
        Approximate ABV (%).
    """
    return (original_gravity - final_gravity) * 131.25


fn carbon_dioxide_produced(glucose_g: Float64) -> Float64:
    """CO2 produced during alcoholic fermentation.

    Yield = 0.489 g CO2 / g glucose

    Args:
        glucose_g: Glucose mass consumed (g).

    Returns:
        CO2 mass produced (g).
    """
    return 0.489 * glucose_g


fn yeast_growth_rate(
    mu_max: Float64, substrate_conc: Float64, ks: Float64, ethanol_conc: Float64
) -> Float64:
    """Yeast-specific growth rate with ethanol inhibition.

    μ = μmax · S/(Ks+S) · (1 - P/Pm)

    Args:
        mu_max: Maximum specific growth rate (h⁻¹).
        substrate_conc: Sugar concentration (g/L).
        ks: Saturation constant (g/L).
        ethanol_conc: Ethanol concentration (g/L); inhibits above ~100 g/L.

    Returns:
        Specific growth rate μ (h⁻¹).
    """
    var pm = 100.0  # maximum tolerated ethanol g/L
    var monod = substrate_conc / (ks + substrate_conc) if (ks + substrate_conc) > 0.0 else 0.0
    var inhibition = 1.0 - ethanol_conc / pm
    if inhibition < 0.0:
        inhibition = 0.0
    return mu_max * monod * inhibition


fn substrate_consumption(
    growth_rate: Float64, biomass_conc: Float64, yield_factor: Float64
) -> Float64:
    """Substrate consumption rate (simplified, growth-associated).

    dS/dt = -(μ/Yx/s) · X

    Args:
        growth_rate: Specific growth rate μ (h⁻¹).
        biomass_conc: Biomass concentration X (g/L).
        yield_factor: Biomass yield on substrate Yx/s (g/g).

    Returns:
        Substrate consumption rate (g/L/h).
    """
    if yield_factor <= 0.0:
        return 0.0
    return (growth_rate / yield_factor) * biomass_conc


fn volumetric_productivity(
    product_conc: Float64, fermentation_time: Float64
) -> Float64:
    """Volumetric product productivity.

    P = C_p / t

    Args:
        product_conc: Final product concentration (g/L).
        fermentation_time: Total fermentation time (h).

    Returns:
        Productivity (g/L/h).
    """
    if fermentation_time <= 0.0:
        return 0.0
    return product_conc / fermentation_time


fn fermentation_efficiency(
    actual_yield: Float64, theoretical_yield: Float64
) -> Float64:
    """Fermentation efficiency relative to theoretical maximum.

    FE = actual / theoretical × 100

    Args:
        actual_yield: Measured product yield (g/g substrate).
        theoretical_yield: Theoretical maximum yield (g/g substrate).

    Returns:
        Fermentation efficiency (%).
    """
    if theoretical_yield <= 0.0:
        return 0.0
    return actual_yield / theoretical_yield * 100.0


fn dissolved_oxygen_kla(
    kla: Float64, o2_saturation: Float64, o2_actual: Float64
) -> Float64:
    """Oxygen transfer rate: OTR = kLa·(C* - C).

    Args:
        kla: Volumetric mass transfer coefficient (h⁻¹).
        o2_saturation: DO saturation concentration (mg/L).
        o2_actual: Actual DO concentration (mg/L).

    Returns:
        Oxygen transfer rate (mg O2/L/h).
    """
    var deficit = o2_saturation - o2_actual
    if deficit < 0.0:
        return 0.0
    return kla * deficit


fn ph_buffer_capacity(
    acid_base_concentration: Float64, pka: Float64, ph: Float64
) -> Float64:
    """Buffer capacity near pKa (van Slyke equation).

    β = 2.303 · Ka · [buffer] / (Ka + [H+])²

    Args:
        acid_base_concentration: Total buffer concentration (mol/L).
        pka: pKa of the buffer acid.
        ph: Current pH.

    Returns:
        Buffer capacity β (mol/L/pH unit).
    """
    from std.math import pow as fpow
    var h_plus = fpow(10.0, -ph)
    var ka = fpow(10.0, -pka)
    var denom = (ka + h_plus) * (ka + h_plus)
    if denom <= 0.0:
        return 0.0
    return 2.303 * ka * acid_base_concentration / denom


fn heat_generation_rate(
    oxygen_uptake_rate: Float64, heat_of_combustion: Float64
) -> Float64:
    """Metabolic heat generation in a fermenter.

    Q_gen = OUR · ΔH_combustion

    Args:
        oxygen_uptake_rate: Oxygen uptake rate (mol O2/L/h).
        heat_of_combustion: Heat released per mol O2 consumed (kJ/mol, ~460 for glucose).

    Returns:
        Heat generation rate (kJ/L/h).
    """
    return oxygen_uptake_rate * heat_of_combustion
