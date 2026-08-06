"""
virology.mojo — Viral biology and infection dynamics calculations. Zero Python imports.

Public API:
  basic_reproduction_number    — R0 from infection parameters
  viral_doubling_time          — from growth rate
  plaque_forming_units         — PFU from dilution and count
  burst_size                   — viral particles per infected cell
  eclipse_period               — latent period before burst
  neutralisation_titre         — NT50 from dilution series
  antiviral_ic50               — from dose-response
  virus_decay_rate             — first-order inactivation
  infection_threshold          — minimum infectious dose
  herd_immunity_threshold_viro — 1 - 1/R0
"""
from std.math import log, exp, pow


def basic_reproduction_number(
    beta: Float64, infectious_period: Float64, population: Float64
) -> Float64:
    """Basic reproduction number R0 = β·N·D.

    Args:
        beta: Transmission rate per susceptible per infectious per day.
        infectious_period: Mean duration of infectiousness (days).
        population: Susceptible population size N.

    Returns:
        Basic reproduction number R0.
    """
    return beta * population * infectious_period


def viral_doubling_time(growth_rate: Float64) -> Float64:
    """Viral doubling time: T_d = ln2 / r.

    Args:
        growth_rate: Exponential growth rate r (per hour or per day).

    Returns:
        Doubling time (same units as 1/r).
    """
    if growth_rate <= 0.0:
        return 0.0
    return log(2.0) / growth_rate


def plaque_forming_units(
    plaque_count: Float64, dilution: Float64, volume_ml: Float64
) -> Float64:
    """Viral titre: PFU/mL from plaque assay.

    PFU/mL = count / (dilution × volume)

    Args:
        plaque_count: Number of plaques on plate.
        dilution: Dilution factor applied (e.g. 0.001 = 10⁻³).
        volume_ml: Volume of inoculum plated (mL).

    Returns:
        Viral titre (PFU/mL).
    """
    if dilution <= 0.0 or volume_ml <= 0.0:
        return 0.0
    return plaque_count / (dilution * volume_ml)


def burst_size(
    progeny_particles: Float64, initial_infected_cells: Float64
) -> Float64:
    """Burst size: average progeny virions per infected cell.

    Args:
        progeny_particles: Total infectious particles released.
        initial_infected_cells: Number of initially infected cells.

    Returns:
        Burst size (particles/cell).
    """
    if initial_infected_cells <= 0.0:
        return 0.0
    return progeny_particles / initial_infected_cells


def eclipse_period(
    time_of_burst: Float64, adsorption_time: Float64
) -> Float64:
    """Eclipse period from adsorption to first burst.

    eclipse = t_burst - t_adsorption

    Args:
        time_of_burst: Time when first progeny are released (h).
        adsorption_time: Time of virus adsorption to cell (h).

    Returns:
        Eclipse period (h).
    """
    var ep = time_of_burst - adsorption_time
    if ep < 0.0:
        return 0.0
    return ep


def neutralisation_titre(
    log2_dilution_at_50_inhibition: Float64
) -> Float64:
    """Neutralisation titre from 50% inhibition dilution.

    NT50 = 2^log2_dilution

    Args:
        log2_dilution_at_50_inhibition: log2 of dilution factor at 50% neutralisation.

    Returns:
        Reciprocal neutralisation titre.
    """
    return pow(2.0, log2_dilution_at_50_inhibition)


def antiviral_ic50(
    conc_high: Float64, conc_low: Float64,
    inhibition_high: Float64, inhibition_low: Float64
) -> Float64:
    """IC50 by linear interpolation between two concentration-response points.

    Args:
        conc_high: Higher concentration (μM).
        conc_low: Lower concentration (μM).
        inhibition_high: % inhibition at conc_high.
        inhibition_low: % inhibition at conc_low.

    Returns:
        IC50 (μM).
    """
    if inhibition_high == inhibition_low:
        return (conc_high + conc_low) / 2.0
    var slope = (inhibition_high - inhibition_low) / (conc_high - conc_low)
    if slope == 0.0:
        return (conc_high + conc_low) / 2.0
    return conc_low + (50.0 - inhibition_low) / slope


def virus_decay_rate(
    initial_titre: Float64, final_titre: Float64, time: Float64
) -> Float64:
    """First-order viral inactivation rate constant: k = ln(N0/N)/t.

    Args:
        initial_titre: Initial virus titre (PFU/mL).
        final_titre: Titre after time t.
        time: Elapsed time (h or min).

    Returns:
        Decay rate constant k (per unit time).
    """
    if final_titre <= 0.0 or initial_titre <= 0.0 or time <= 0.0:
        return 0.0
    return log(initial_titre / final_titre) / time


def infection_threshold(
    dose: Float64, id50: Float64, probit_slope: Float64
) -> Float64:
    """Probability of infection from dose (probit model simplified).

    P = 0.5 × (1 + (dose - ID50) / (ID50 × slope))  (linear approx)

    Args:
        dose: Infectious dose (viral particles or PFU).
        id50: Median infectious dose ID50.
        probit_slope: Slope of dose-response curve.

    Returns:
        Probability of infection (0–1).
    """
    if id50 <= 0.0:
        return 0.0
    var p = 0.5 + probit_slope * (dose - id50) / id50
    if p < 0.0:
        return 0.0
    if p > 1.0:
        return 1.0
    return p


def herd_immunity_threshold_viro(r0: Float64) -> Float64:
    """Herd immunity threshold for virus: HIT = 1 - 1/R0.

    Args:
        r0: Basic reproduction number.

    Returns:
        Minimum immune fraction needed for herd immunity (0–1).
    """
    if r0 <= 1.0:
        return 0.0
    return 1.0 - 1.0 / r0
