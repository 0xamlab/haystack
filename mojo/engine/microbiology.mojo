"""
microbiology.mojo — Microbial growth and population calculations. Zero Python imports.

Public API:
  exponential_growth           — N(t) = N0 * exp(μ*t)
  doubling_time                — td = ln(2)/μ
  monod_growth_rate            — μ = μmax * S / (Ks + S)
  bacterial_generation_time    — from population counts at two time points
  colony_forming_units         — CFU from dilution and count
  minimum_inhibitory_conc      — MIC index from inhibition zone
  biofilm_formation_index      — relative biofilm density
  inactivation_first_order     — N(t) = N0 * exp(-k_d*t)
  d_value                      — decimal reduction time = 1/k_d * ln(10)
  z_value                      — temperature increase for 10x faster kill
"""
from std.math import exp, log, sqrt


fn exponential_growth(
    n0: Float64, growth_rate: Float64, time: Float64
) -> Float64:
    """Exponential microbial growth: N(t) = N0·exp(μ·t).

    Args:
        n0: Initial cell count (cells/mL).
        growth_rate: Specific growth rate μ (h⁻¹).
        time: Time elapsed (h).

    Returns:
        Cell count at time t (cells/mL).
    """
    if n0 < 0.0 or growth_rate < 0.0 or time < 0.0:
        return n0
    return n0 * exp(growth_rate * time)


fn doubling_time(growth_rate: Float64) -> Float64:
    """Generation (doubling) time: td = ln(2)/μ.

    Args:
        growth_rate: Specific growth rate μ (h⁻¹).

    Returns:
        Doubling time (h).
    """
    if growth_rate <= 0.0:
        return 0.0
    return log(2.0) / growth_rate


fn monod_growth_rate(
    mu_max: Float64, substrate: Float64, ks: Float64
) -> Float64:
    """Monod model specific growth rate: μ = μmax·S/(Ks+S).

    Args:
        mu_max: Maximum specific growth rate (h⁻¹).
        substrate: Substrate concentration (g/L).
        ks: Saturation constant (g/L).

    Returns:
        Specific growth rate (h⁻¹).
    """
    var denom = ks + substrate
    if denom <= 0.0:
        return 0.0
    return mu_max * substrate / denom


fn bacterial_generation_time(
    n_initial: Float64, n_final: Float64, elapsed_h: Float64
) -> Float64:
    """Generation time from two population measurements.

    g = elapsed / (log2(N_final/N_initial))

    Args:
        n_initial: Initial cell count.
        n_final: Final cell count.
        elapsed_h: Elapsed time (h).

    Returns:
        Generation time (h).
    """
    if n_initial <= 0.0 or n_final <= n_initial or elapsed_h <= 0.0:
        return 0.0
    var generations = log(n_final / n_initial) / log(2.0)
    if generations <= 0.0:
        return 0.0
    return elapsed_h / generations


fn colony_forming_units(
    colony_count: Float64, dilution_factor: Float64, volume_ml: Float64
) -> Float64:
    """CFU per mL from plate count and dilution.

    Args:
        colony_count: Number of visible colonies on plate.
        dilution_factor: Dilution applied (e.g. 0.001 = 10⁻³).
        volume_ml: Volume plated (mL).

    Returns:
        CFU/mL in original sample.
    """
    if dilution_factor <= 0.0 or volume_ml <= 0.0:
        return 0.0
    return colony_count / (dilution_factor * volume_ml)


fn minimum_inhibitory_conc(
    inhibition_zone_mm: Float64, disk_conc_ug: Float64
) -> Float64:
    """Estimated MIC from disk diffusion (Kirby-Bauer index).

    This is a simplified regression-based approximation.

    Args:
        inhibition_zone_mm: Zone of inhibition diameter (mm).
        disk_conc_ug: Antibiotic concentration on disk (μg).

    Returns:
        Relative MIC index (lower = more susceptible).
    """
    if inhibition_zone_mm <= 6.0:
        return disk_conc_ug  # no inhibition at disc edge
    return disk_conc_ug / (inhibition_zone_mm - 6.0)


fn biofilm_formation_index(
    od_sample: Float64, od_control: Float64
) -> Float64:
    """Biofilm formation index from crystal violet assay.

    Args:
        od_sample: Optical density of stained biofilm (crystal violet).
        od_control: OD of blank control well.

    Returns:
        Biofilm index (BFI), dimensionless.
    """
    if od_control <= 0.0:
        return 0.0
    return od_sample / od_control


fn inactivation_first_order(
    n0: Float64, inactivation_rate: Float64, time: Float64
) -> Float64:
    """First-order microbial inactivation: N(t) = N0·exp(-kd·t).

    Args:
        n0: Initial viable count.
        inactivation_rate: Inactivation rate constant kd (min⁻¹).
        time: Treatment time (min).

    Returns:
        Surviving cell count.
    """
    if n0 < 0.0 or inactivation_rate < 0.0 or time < 0.0:
        return n0
    return n0 * exp(-inactivation_rate * time)


fn d_value(inactivation_rate: Float64) -> Float64:
    """D-value (decimal reduction time): D = ln(10)/kd.

    Args:
        inactivation_rate: First-order inactivation constant kd (min⁻¹).

    Returns:
        D-value (min).
    """
    if inactivation_rate <= 0.0:
        return 0.0
    return log(10.0) / inactivation_rate


fn z_value(d1: Float64, d2: Float64, t1: Float64, t2: Float64) -> Float64:
    """Z-value: temperature change for 10-fold change in D-value.

    Args:
        d1: D-value at temperature T1 (min).
        d2: D-value at temperature T2 (min).
        t1: Temperature 1 (°C).
        t2: Temperature 2 (°C).

    Returns:
        Z-value (°C).
    """
    if d1 <= 0.0 or d2 <= 0.0 or d1 == d2:
        return 0.0
    return (t2 - t1) / log(d1 / d2) * log(10.0)
