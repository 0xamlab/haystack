"""
forensics.mojo — Forensic Science Library. Zero Python imports.

Pure Mojo implementations of forensic science calculations including
time-of-death estimation, toxicology, ballistics, bloodstain analysis,
DNA match probability, and decomposition modelling.

Public API:
  time_of_death_newton          — Newton's cooling law for TOD estimation
  algor_mortis_rate             — Simplified Henssge cooling rate
  blood_alcohol_widmark         — Widmark BAC formula
  alcohol_elimination_rate      — BAC after elapsed time
  rigor_mortis_stage            — Stage of rigor mortis (0-4)
  ballistic_drop                — Bullet drop at distance
  bloodstain_impact_angle       — Impact angle from stain geometry
  dna_match_probability         — Hardy-Weinberg heterozygous probability
  fingerprint_minutiae_score    — Minutiae matching score
  glass_refractive_index_match  — RI comparison within tolerance
  decomposition_add             — Accumulated degree-days update
  toxicology_lethal_dose        — Lethal dose from LD50 and weight
"""
from std.math import log, exp, abs as fabs, asin


# ── time_of_death_newton ─────────────────────────────────────────────────────


def time_of_death_newton(
    t_body: Float64, t_ambient: Float64, t_normal: Float64, k: Float64
) -> Float64:
    """Newton's cooling law: hours since death.

    t = -ln((T_body - T_amb) / (T_norm - T_amb)) / k

    Args:
        t_body: Current body temperature.
        t_ambient: Ambient temperature.
        t_normal: Normal body temperature (e.g. 37°C).
        k: Cooling constant.

    Returns:
        Estimated hours since death.
    """
    var denom = t_normal - t_ambient
    if fabs(denom) < 1e-30:
        return 0.0
    var ratio = (t_body - t_ambient) / denom
    if ratio <= 0.0:
        return 0.0
    if fabs(k) < 1e-30:
        return 0.0
    return -log(ratio) / k


# ── algor_mortis_rate ────────────────────────────────────────────────────────


def algor_mortis_rate(body_temp: Float64, ambient_temp: Float64) -> Float64:
    """Simplified Henssge cooling rate.

    rate ≈ (body - ambient) / 10 °C/hr

    Args:
        body_temp: Body temperature (°C).
        ambient_temp: Ambient temperature (°C).

    Returns:
        Cooling rate in °C/hr.
    """
    return (body_temp - ambient_temp) / 10.0


# ── blood_alcohol_widmark ────────────────────────────────────────────────────


def blood_alcohol_widmark(
    alcohol_g: Float64, body_weight_kg: Float64, r_factor: Float64
) -> Float64:
    """Widmark BAC formula: BAC = A / (W * r).

    Args:
        alcohol_g: Mass of alcohol consumed (grams).
        body_weight_kg: Body weight (kg).
        r_factor: Widmark factor (0.68 male, 0.55 female typical).

    Returns:
        Blood alcohol concentration (g/100mL).
    """
    var denom = body_weight_kg * r_factor
    if fabs(denom) < 1e-30:
        return 0.0
    return alcohol_g / denom


# ── alcohol_elimination_rate ─────────────────────────────────────────────────


def alcohol_elimination_rate(
    bac: Float64, elapsed_hours: Float64, beta: Float64
) -> Float64:
    """BAC after linear elimination.

    BAC_current = max(0, bac - beta * t)

    Args:
        bac: Initial BAC.
        elapsed_hours: Hours elapsed.
        beta: Elimination rate (≈0.015 g/100mL/hr).

    Returns:
        Current BAC.
    """
    var result = bac - beta * elapsed_hours
    if result < 0.0:
        return 0.0
    return result


# ── rigor_mortis_stage ───────────────────────────────────────────────────────


def rigor_mortis_stage(hours_since_death: Float64) -> Int:
    """Stage of rigor mortis based on hours post-mortem.

    0 = none (<2h), 1 = onset (2-6h), 2 = full (6-12h),
    3 = passing (12-36h), 4 = resolved (>36h).

    Args:
        hours_since_death: Hours since death.

    Returns:
        Stage integer 0-4.
    """
    if hours_since_death < 2.0:
        return 0
    elif hours_since_death < 6.0:
        return 1
    elif hours_since_death < 12.0:
        return 2
    elif hours_since_death < 36.0:
        return 3
    else:
        return 4


# ── ballistic_drop ───────────────────────────────────────────────────────────


def ballistic_drop(
    velocity: Float64, distance: Float64, gravity: Float64
) -> Float64:
    """Bullet drop: drop = 0.5 * g * (d/v)².

    Args:
        velocity: Muzzle velocity (m/s).
        distance: Distance to target (m).
        gravity: Gravitational acceleration (m/s²).

    Returns:
        Drop distance (m).
    """
    if fabs(velocity) < 1e-30:
        return 0.0
    var t = distance / velocity
    return 0.5 * gravity * t * t


# ── bloodstain_impact_angle ──────────────────────────────────────────────────


def bloodstain_impact_angle(width: Float64, length: Float64) -> Float64:
    """Impact angle from bloodstain: θ = asin(width/length).

    Args:
        width: Stain width.
        length: Stain length.

    Returns:
        Impact angle in radians.
    """
    if fabs(length) < 1e-30:
        return 0.0
    var ratio = width / length
    if ratio > 1.0:
        ratio = 1.0
    if ratio < -1.0:
        ratio = -1.0
    return asin(ratio)


# ── dna_match_probability ────────────────────────────────────────────────────


def dna_match_probability(
    allele_freq1: Float64, allele_freq2: Float64
) -> Float64:
    """Hardy-Weinberg heterozygous match probability: P = 2*p1*p2.

    Args:
        allele_freq1: Frequency of allele 1.
        allele_freq2: Frequency of allele 2.

    Returns:
        Match probability.
    """
    return 2.0 * allele_freq1 * allele_freq2


# ── fingerprint_minutiae_score ───────────────────────────────────────────────


def fingerprint_minutiae_score(
    matching_points: Float64, total_points: Float64
) -> Float64:
    """Minutiae matching score: score = matching / total.

    Args:
        matching_points: Number of matching minutiae.
        total_points: Total minutiae examined.

    Returns:
        Score between 0 and 1.
    """
    if fabs(total_points) < 1e-30:
        return 0.0
    return matching_points / total_points


# ── glass_refractive_index_match ─────────────────────────────────────────────


def glass_refractive_index_match(
    ri1: Float64, ri2: Float64, tolerance: Float64
) -> Bool:
    """Check if two refractive indices match within tolerance.

    Args:
        ri1: Refractive index of sample 1.
        ri2: Refractive index of sample 2.
        tolerance: Acceptable difference.

    Returns:
        True if |ri1 - ri2| < tolerance.
    """
    return fabs(ri1 - ri2) < tolerance


# ── decomposition_add ────────────────────────────────────────────────────────


def decomposition_add(
    accumulated_degree_days: Float64, temp: Float64, hours: Float64
) -> Float64:
    """Update accumulated degree-days (ADD).

    ADD += max(0, temp) * hours / 24

    Args:
        accumulated_degree_days: Current ADD.
        temp: Temperature (°C).
        hours: Elapsed hours.

    Returns:
        Updated ADD.
    """
    var contribution = temp if temp > 0.0 else 0.0
    return accumulated_degree_days + contribution * hours / 24.0


# ── toxicology_lethal_dose ───────────────────────────────────────────────────


def toxicology_lethal_dose(ld50: Float64, body_weight: Float64) -> Float64:
    """Estimated lethal dose: dose = LD50 * body_weight.

    Args:
        ld50: LD50 value (mg/kg).
        body_weight: Body weight (kg).

    Returns:
        Lethal dose in mg.
    """
    return ld50 * body_weight
