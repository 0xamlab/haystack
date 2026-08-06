"""
neuropharmacology.mojo — CNS drug action calculations. Zero Python imports.

Public API:
  receptor_occupancy_brain      — brain receptor occupancy from plasma/Kd
  blood_brain_barrier_efflux    — P-gp efflux ratio
  receptor_binding_ki           — Ki from IC50 and radioligand Kd
  synapse_neurotransmitter_level — from release, reuptake, degradation
  bbb_penetration_ratio         — brain/plasma Kp
  cns_drug_exposure             — Kp,uu from free fractions
  d2_receptor_occupancy         — antipsychotic D2 occupancy
  minimal_effective_dose_cns    — from EC50 and Emax
  cns_side_effect_threshold     — occupancy at adjacent receptor
  neuronal_firing_modulation    — Hz change from drug
"""
from std.math import log, exp, pow


def receptor_occupancy_brain(
    free_plasma_conc: Float64, kp_uu: Float64, kd: Float64
) -> Float64:
    """Brain receptor occupancy from plasma concentration and Kp,uu.

    occ = C_brain_free / (Kd + C_brain_free)  where C_brain = Cp_free × Kp,uu

    Args:
        free_plasma_conc: Free (unbound) drug in plasma (nM).
        kp_uu: Brain-to-plasma free fraction ratio.
        kd: Receptor dissociation constant (nM).

    Returns:
        Receptor occupancy (0–1).
    """
    var c_brain = free_plasma_conc * kp_uu
    var denom = kd + c_brain
    if denom <= 0.0:
        return 0.0
    return c_brain / denom


def blood_brain_barrier_efflux(
    a_to_b_papp: Float64, b_to_a_papp: Float64
) -> Float64:
    """P-glycoprotein efflux ratio from bidirectional transport.

    ER = Papp(B→A) / Papp(A→B)

    Args:
        a_to_b_papp: Apical-to-basal apparent permeability (10⁻⁶ cm/s).
        b_to_a_papp: Basal-to-apical apparent permeability.

    Returns:
        Efflux ratio (>2 = P-gp substrate, poor CNS penetration).
    """
    if a_to_b_papp <= 0.0:
        return 0.0
    return b_to_a_papp / a_to_b_papp


def receptor_binding_ki(
    ic50: Float64, radioligand_conc: Float64, radioligand_kd: Float64
) -> Float64:
    """Ki from competition binding (Cheng-Prusoff equation).

    Ki = IC50 / (1 + [L] / Kd_L)

    Args:
        ic50: Measured IC50 of competing drug (nM).
        radioligand_conc: Radioligand concentration (nM).
        radioligand_kd: Radioligand Kd (nM).

    Returns:
        True Ki (nM).
    """
    return ic50 / (1.0 + radioligand_conc / radioligand_kd)


def synapse_neurotransmitter_level(
    release_rate: Float64, reuptake_rate: Float64, degradation_rate: Float64
) -> Float64:
    """Steady-state synaptic neurotransmitter: SS = release / (reuptake + degradation).

    Args:
        release_rate: Vesicular release (nM/s).
        reuptake_rate: Transporter reuptake constant (s⁻¹).
        degradation_rate: Enzymatic degradation constant (s⁻¹).

    Returns:
        Steady-state cleft concentration (nM).
    """
    var clearance = reuptake_rate + degradation_rate
    if clearance <= 0.0:
        return 0.0
    return release_rate / clearance


def bbb_penetration_ratio(
    brain_conc: Float64, plasma_conc: Float64
) -> Float64:
    """Brain-to-plasma concentration ratio Kp.

    Args:
        brain_conc: Total drug concentration in brain homogenate (ng/g).
        plasma_conc: Total drug concentration in plasma (ng/mL).

    Returns:
        Kp (dimensionless; >0.3 considered CNS penetrant).
    """
    if plasma_conc <= 0.0:
        return 0.0
    return brain_conc / plasma_conc


def cns_drug_exposure(
    kp: Float64, free_fraction_brain: Float64, free_fraction_plasma: Float64
) -> Float64:
    """Unbound CNS drug exposure ratio Kp,uu.

    Kp,uu = Kp × fu_brain / fu_plasma

    Args:
        kp: Brain-to-plasma total concentration ratio.
        free_fraction_brain: Unbound fraction in brain (fu,brain).
        free_fraction_plasma: Unbound fraction in plasma (fu,plasma).

    Returns:
        Kp,uu (free drug ratio; ~1 = no active efflux or influx).
    """
    if free_fraction_plasma <= 0.0:
        return 0.0
    return kp * free_fraction_brain / free_fraction_plasma


def d2_receptor_occupancy(
    plasma_conc: Float64, ec50: Float64
) -> Float64:
    """Antipsychotic D2 receptor occupancy (Emax model).

    RO% = 100 × Cp / (EC50 + Cp)

    Args:
        plasma_conc: Free antipsychotic plasma concentration (nM).
        ec50: EC50 for D2 occupancy (nM).

    Returns:
        D2 occupancy (%; 60–80% = therapeutic range).
    """
    var denom = ec50 + plasma_conc
    if denom <= 0.0:
        return 0.0
    return 100.0 * plasma_conc / denom


def minimal_effective_dose_cns(
    ec20_nM: Float64, fu_plasma: Float64,
    kp_uu: Float64, clearance_l_per_h: Float64
) -> Float64:
    """Dose required for minimal CNS effect (20% receptor occupancy).

    Dose = EC20_brain_free × CL / (fu_plasma × Kp,uu)

    Args:
        ec20_nM: Free brain concentration for 20% occupancy (nM, from Ki).
        fu_plasma: Unbound fraction in plasma.
        kp_uu: Brain-to-plasma free drug ratio.
        clearance_l_per_h: Systemic clearance (L/h).

    Returns:
        Minimum effective dose rate (nmol/h).
    """
    var c_plasma_free = ec20_nM / kp_uu
    if fu_plasma <= 0.0:
        return 0.0
    var c_plasma_total = c_plasma_free / fu_plasma
    return c_plasma_total * clearance_l_per_h


def cns_side_effect_threshold(
    therapeutic_occupancy: Float64, selectivity_ratio: Float64
) -> Float64:
    """Estimated off-target receptor occupancy causing side effects.

    occ_off = therapeutic_occupancy / selectivity_ratio

    Args:
        therapeutic_occupancy: On-target occupancy fraction (0–1).
        selectivity_ratio: Ki(off) / Ki(on) — fold selectivity.

    Returns:
        Off-target occupancy estimate (0–1).
    """
    if selectivity_ratio <= 0.0:
        return 0.0
    return therapeutic_occupancy / selectivity_ratio


def neuronal_firing_modulation(
    baseline_hz: Float64, drug_effect: Float64, receptor_occupancy: Float64
) -> Float64:
    """Modulated neuronal firing rate from drug action.

    Hz_new = baseline × (1 + effect × occupancy)

    Args:
        baseline_hz: Baseline firing rate (Hz).
        drug_effect: Maximum fractional change (positive = excitatory).
        receptor_occupancy: Current receptor occupancy (0–1).

    Returns:
        Modulated firing rate (Hz).
    """
    return baseline_hz * (1.0 + drug_effect * receptor_occupancy)
