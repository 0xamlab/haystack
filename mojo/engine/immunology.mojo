"""
immunology.mojo — Immune response and antibody calculations. Zero Python imports.

Public API:
  antibody_titer               — titer from dilution and OD threshold
  seroconversion_rate          — fraction achieving protective titer
  antigen_antibody_binding     — equilibrium bound fraction (Ka model)
  complement_activation        — C3 cleavage rate estimate
  t_cell_proliferation         — logistic growth model
  innate_response_decay        — cytokine clearance first-order
  vaccine_efficacy             — VE = 1 - RR (attack rate ratio)
  herd_immunity_threshold      — HIT = 1 - 1/R0
  antibody_avidity_index       — AI = OD_urea / OD_pbs * 100
  opsonisation_index           — phagocytosis enhancement factor
"""
from std.math import exp, log


def antibody_titer(dilution_factor: Float64, od_ratio: Float64) -> Float64:
    """Antibody titer from serial dilution ELISA.

    Titer = 1 / (dilution · OD_ratio)

    Args:
        dilution_factor: Dilution at which signal crosses threshold (e.g. 0.001 = 1:1000).
        od_ratio: OD_sample / OD_background ratio at threshold.

    Returns:
        Reciprocal titer.
    """
    if dilution_factor <= 0.0 or od_ratio <= 0.0:
        return 0.0
    return 1.0 / (dilution_factor * od_ratio)


def seroconversion_rate(
    n_seroconverted: Float64, n_total: Float64
) -> Float64:
    """Seroconversion rate in a vaccinated cohort.

    Args:
        n_seroconverted: Number achieving protective titer.
        n_total: Total number vaccinated.

    Returns:
        Seroconversion rate (0–1).
    """
    if n_total <= 0.0:
        return 0.0
    return n_seroconverted / n_total


def antigen_antibody_binding(
    ka: Float64, antigen_conc: Float64, antibody_conc: Float64
) -> Float64:
    """Equilibrium antigen-antibody bound fraction.

    From Ka = [Ab·Ag] / ([Ab][Ag]), solving quadratic for [Ab·Ag].
    Simplified: bound_fraction ≈ Ka·[Ab] / (1 + Ka·[Ab])

    Args:
        ka: Association constant Ka (L/mol).
        antigen_conc: Free antigen concentration (mol/L).
        antibody_conc: Antibody concentration (mol/L).

    Returns:
        Bound antigen fraction (0–1).
    """
    var denom = 1.0 + ka * antibody_conc
    if denom <= 0.0:
        return 0.0
    return ka * antibody_conc / denom


def complement_activation(
    antibody_conc: Float64, threshold: Float64, rate_constant: Float64
) -> Float64:
    """Complement C3 cleavage rate (simplified threshold model).

    Args:
        antibody_conc: IgG concentration triggering complement (μg/mL).
        threshold: Minimum concentration for classical pathway (μg/mL).
        rate_constant: Cleavage rate constant (min⁻¹).

    Returns:
        C3 cleavage rate (arbitrary units).
    """
    if antibody_conc <= threshold:
        return 0.0
    return rate_constant * (antibody_conc - threshold)


def t_cell_proliferation(
    n0: Float64, max_cells: Float64, growth_rate: Float64, time: Float64
) -> Float64:
    """Logistic growth model for T-cell clonal expansion.

    N(t) = K / (1 + ((K - N0)/N0) * exp(-r*t))

    Args:
        n0: Initial T-cell count (cells/mL).
        max_cells: Carrying capacity K (cells/mL).
        growth_rate: Net growth rate r (h⁻¹).
        time: Time (h).

    Returns:
        T-cell count at time t.
    """
    if max_cells <= 0.0 or n0 <= 0.0:
        return n0
    var ratio = (max_cells - n0) / n0
    var denom = 1.0 + ratio * exp(-growth_rate * time)
    if denom <= 0.0:
        return max_cells
    return max_cells / denom


def innate_response_decay(
    c0: Float64, decay_rate: Float64, time: Float64
) -> Float64:
    """Cytokine clearance (first-order kinetics): C(t) = C0·exp(-k·t).

    Args:
        c0: Initial cytokine concentration (pg/mL).
        decay_rate: Clearance rate constant (h⁻¹).
        time: Time after peak (h).

    Returns:
        Cytokine concentration (pg/mL).
    """
    if c0 < 0.0 or decay_rate < 0.0:
        return c0
    return c0 * exp(-decay_rate * time)


def vaccine_efficacy(
    attack_rate_vaccinated: Float64, attack_rate_unvaccinated: Float64
) -> Float64:
    """Vaccine efficacy from attack rates.

    VE = 1 - (ARV / ARU)  =  1 - RR

    Args:
        attack_rate_vaccinated: Attack rate in vaccinated group (fraction).
        attack_rate_unvaccinated: Attack rate in unvaccinated group (fraction).

    Returns:
        Vaccine efficacy (0–1).
    """
    if attack_rate_unvaccinated <= 0.0:
        return 0.0
    var rr = attack_rate_vaccinated / attack_rate_unvaccinated
    return 1.0 - rr


def herd_immunity_threshold(r0: Float64) -> Float64:
    """Herd immunity threshold: HIT = 1 - 1/R0.

    Args:
        r0: Basic reproduction number.

    Returns:
        Minimum fraction to vaccinate for herd immunity (0–1).
    """
    if r0 <= 1.0:
        return 0.0
    return 1.0 - 1.0 / r0


def antibody_avidity_index(od_urea: Float64, od_pbs: Float64) -> Float64:
    """Antibody avidity index from chaotrope elution ELISA.

    AI = (OD_urea / OD_PBS) × 100 (%)

    Args:
        od_urea: OD after urea wash.
        od_pbs: OD with PBS control.

    Returns:
        Avidity index (%).
    """
    if od_pbs <= 0.0:
        return 0.0
    return (od_urea / od_pbs) * 100.0


def opsonisation_index(
    phagocytosis_immune: Float64, phagocytosis_control: Float64
) -> Float64:
    """Opsonisation index (phagocytic enhancement by antibodies).

    OI = (FI_immune / FI_control) - 1

    Args:
        phagocytosis_immune: Phagocytosis in presence of immune serum (%).
        phagocytosis_control: Phagocytosis with control serum (%).

    Returns:
        Opsonisation index (0 = no enhancement).
    """
    if phagocytosis_control <= 0.0:
        return 0.0
    return (phagocytosis_immune / phagocytosis_control) - 1.0
