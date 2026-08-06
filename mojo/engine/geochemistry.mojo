"""
geochemistry.mojo — Chemical earth science calculations. Zero Python imports.

Public API:
  distribution_coefficient     — Kd for element between phases
  partition_melt               — fractional melting model
  batch_melting                — batch melt trace element concentration
  rare_earth_normalization     — CI chondrite normalized ratio
  isotope_mass_balance         — mixing equation for isotopes
  weathering_index             — Chemical Index of Alteration (CIA)
  redox_potential_pe           — pe from Eh
  carbonate_saturation         — Ω from ion products
  henry_law_gas                — dissolved gas from partial pressure
  organic_carbon_toc           — TOC from Leco measurement
"""
from std.math import log, exp, pow, sqrt


def _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


def distribution_coefficient(
    conc_solid: Float64, conc_liquid: Float64
) -> Float64:
    """Distribution (partition) coefficient: Kd = C_solid / C_liquid.

    Args:
        conc_solid: Element concentration in solid phase (μg/g or ppm).
        conc_liquid: Element concentration in liquid phase (μg/mL or ppm).

    Returns:
        Kd (dimensionless).
    """
    if conc_liquid <= 0.0:
        return 0.0
    return conc_solid / conc_liquid


def partition_melt(
    c0: Float64, d0: Float64, melt_fraction: Float64
) -> Float64:
    """Fractional melting trace element model: Cl = C0/(D + F*(1-D)).

    Args:
        c0: Initial element concentration in source (ppm).
        d0: Bulk distribution coefficient.
        melt_fraction: Melt fraction F (0–1).

    Returns:
        Element concentration in melt (ppm).
    """
    var denom = d0 + melt_fraction * (1.0 - d0)
    if denom <= 0.0:
        return 0.0
    return c0 / denom


def batch_melting(
    c0: Float64, d0: Float64, melt_fraction: Float64
) -> Float64:
    """Batch melting model: Cl = C0 / (D + F*(1-p)).

    Simplified (p = D for modal melting).

    Args:
        c0: Source concentration (ppm).
        d0: Bulk distribution coefficient.
        melt_fraction: Melt fraction F.

    Returns:
        Liquid concentration (ppm).
    """
    var denom = d0 + melt_fraction * (1.0 - d0)
    if denom <= 0.0:
        return 0.0
    return c0 / denom


def rare_earth_normalization(
    sample_conc: Float64, chondrite_conc: Float64
) -> Float64:
    """CI-chondrite normalised REE abundance.

    (La/La*)_N = sample / chondrite

    Args:
        sample_conc: Sample element concentration (ppm).
        chondrite_conc: CI chondrite reference value (ppm).

    Returns:
        Normalised ratio.
    """
    if chondrite_conc <= 0.0:
        return 0.0
    return sample_conc / chondrite_conc


def isotope_mass_balance(
    delta_a: Float64, fraction_a: Float64, delta_b: Float64
) -> Float64:
    """Two-component isotope mixing: δ_mix = f·δA + (1-f)·δB.

    Args:
        delta_a: Isotope ratio of end-member A (‰).
        fraction_a: Fraction of end-member A (0–1).
        delta_b: Isotope ratio of end-member B (‰).

    Returns:
        Mixed isotope ratio (‰).
    """
    return fraction_a * delta_a + (1.0 - fraction_a) * delta_b


def weathering_index(
    al2o3: Float64, cao: Float64, na2o: Float64, k2o: Float64
) -> Float64:
    """Chemical Index of Alteration: CIA = Al₂O₃/(Al₂O₃+CaO+Na₂O+K₂O)×100.

    Args:
        al2o3: Al₂O₃ (mol%).
        cao: CaO (mol%, silicate fraction only).
        na2o: Na₂O (mol%).
        k2o: K₂O (mol%).

    Returns:
        CIA (0–100; higher = more weathered).
    """
    var denom = al2o3 + cao + na2o + k2o
    if denom <= 0.0:
        return 0.0
    return al2o3 / denom * 100.0


def redox_potential_pe(eh_mv: Float64) -> Float64:
    """Convert Eh to pe (electron activity): pe = Eh/(2.303·RT/F).

    At 25°C: pe = Eh(mV) / 59.16

    Args:
        eh_mv: Redox potential Eh (mV).

    Returns:
        pe (dimensionless electron activity, log scale).
    """
    return eh_mv / 59.16


def carbonate_saturation(
    ca_conc: Float64, co3_conc: Float64, ksp: Float64
) -> Float64:
    """Carbonate saturation state: Ω = [Ca²⁺]·[CO₃²⁻] / Ksp.

    Args:
        ca_conc: Calcium ion activity (mol/L).
        co3_conc: Carbonate ion activity (mol/L).
        ksp: Solubility product of calcite/aragonite.

    Returns:
        Saturation ratio Ω (>1 = supersaturated, <1 = undersaturated).
    """
    if ksp <= 0.0:
        return 0.0
    return ca_conc * co3_conc / ksp


def henry_law_gas(
    partial_pressure: Float64, henry_constant: Float64
) -> Float64:
    """Dissolved gas concentration from Henry's law: C = KH·P.

    Args:
        partial_pressure: Partial pressure of gas (atm).
        henry_constant: Henry's law constant KH (mol/L/atm).

    Returns:
        Dissolved concentration (mol/L).
    """
    return henry_constant * partial_pressure


def organic_carbon_toc(
    total_carbon: Float64, inorganic_carbon: Float64
) -> Float64:
    """Total organic carbon: TOC = TC - TIC.

    Args:
        total_carbon: Total carbon content (wt%).
        inorganic_carbon: Total inorganic carbon (wt%).

    Returns:
        TOC (wt%).
    """
    var toc = total_carbon - inorganic_carbon
    if toc < 0.0:
        return 0.0
    return toc
