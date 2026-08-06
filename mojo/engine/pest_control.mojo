"""
pest_control.mojo — Pest Control / Integrated Pest Management Library.

Provides economic thresholds, population monitoring, chemical application,
and biocontrol calculations for IPM programmes.

Public API:
  economic_threshold       — ET = cost / (value * damage)
  economic_injury_level    — EIL = ET * gain
  pest_density             — PD = count / area
  trap_catch_rate          — TCR = caught / (traps * days)
  spray_coverage           — Coverage = volume / area (L/ha)
  dilution_rate            — Rate = concentrate / (concentrate + water)
  residual_effectiveness   — Eff = initial * exp(-0.693*days/half_life)
  resistance_ratio         — RR = LD50_R / LD50_S
  biocontrol_release_rate  — Release = target * area / ratio
  fumigation_ct            — CT = C * T (g·h/m³)
  bait_station_density     — BSD = stations / area * 10000
  population_reduction     — Reduction = (before - after) / before * 100
"""
from std.math import exp


# ── economic_threshold ───────────────────────────────────────────────────────


def economic_threshold(
    control_cost: Float64, crop_value: Float64, damage_per_pest: Float64
) -> Float64:
    """Economic threshold: ET = cost / (value * damage_per_pest).

    Args:
        control_cost: Cost of control action per unit area.
        crop_value: Crop value per unit area.
        damage_per_pest: Proportional damage caused per pest unit.

    Returns:
        Economic threshold (pest density triggering action).
    """
    return control_cost / (crop_value * damage_per_pest)


# ── economic_injury_level ────────────────────────────────────────────────────


def economic_injury_level(et: Float64, gain_threshold: Float64) -> Float64:
    """Economic injury level (simplified): EIL = ET * gain.

    Args:
        et: Economic threshold.
        gain_threshold: Gain/safety multiplier.

    Returns:
        Economic injury level.
    """
    return et * gain_threshold


# ── pest_density ─────────────────────────────────────────────────────────────


def pest_density(count: Float64, sample_area: Float64) -> Float64:
    """Pest density: PD = count / area.

    Args:
        count: Total pest count in sample.
        sample_area: Area sampled (m² or ha).

    Returns:
        Pest density (per unit area).
    """
    return count / sample_area


# ── trap_catch_rate ──────────────────────────────────────────────────────────


def trap_catch_rate(caught: Float64, traps: Float64, days: Float64) -> Float64:
    """Trap catch rate: TCR = caught / (traps * days).

    Args:
        caught: Total insects caught.
        traps: Number of traps deployed.
        days: Number of trapping days.

    Returns:
        Catch rate (insects per trap per day).
    """
    return caught / (traps * days)


# ── spray_coverage ───────────────────────────────────────────────────────────


def spray_coverage(volume_applied: Float64, area: Float64) -> Float64:
    """Spray coverage: Coverage = volume / area (L/ha).

    Args:
        volume_applied: Volume of spray applied (L).
        area: Area treated (ha).

    Returns:
        Application rate in L/ha.
    """
    return volume_applied / area


# ── dilution_rate ────────────────────────────────────────────────────────────


def dilution_rate(concentrate_ml: Float64, water_ml: Float64) -> Float64:
    """Dilution rate: Rate = concentrate / (concentrate + water).

    Args:
        concentrate_ml: Volume of concentrate (mL).
        water_ml: Volume of water/solvent (mL).

    Returns:
        Dilution ratio (0–1).
    """
    return concentrate_ml / (concentrate_ml + water_ml)


# ── residual_effectiveness ───────────────────────────────────────────────────


def residual_effectiveness(
    initial_kill_pct: Float64, half_life_days: Float64, days_elapsed: Float64
) -> Float64:
    """Residual effectiveness with exponential decay.

    Eff = initial * exp(-0.693 * days / half_life).

    Args:
        initial_kill_pct: Initial kill percentage (0–100).
        half_life_days: Half-life of the active ingredient (days).
        days_elapsed: Days since application.

    Returns:
        Remaining effectiveness (%).
    """
    return initial_kill_pct * exp(-0.693 * days_elapsed / half_life_days)


# ── resistance_ratio ─────────────────────────────────────────────────────────


def resistance_ratio(ld50_resistant: Float64, ld50_susceptible: Float64) -> Float64:
    """Resistance ratio: RR = LD50_R / LD50_S.

    Args:
        ld50_resistant: LD50 of resistant strain.
        ld50_susceptible: LD50 of susceptible strain.

    Returns:
        Resistance ratio (>1 indicates resistance).
    """
    return ld50_resistant / ld50_susceptible


# ── biocontrol_release_rate ──────────────────────────────────────────────────


def biocontrol_release_rate(
    target_density: Float64, predator_prey_ratio: Float64, area: Float64
) -> Float64:
    """Biocontrol agent release rate.

    Release = target_density * area / predator_prey_ratio.

    Args:
        target_density: Target pest density per unit area.
        predator_prey_ratio: Desired predator-to-prey ratio.
        area: Treatment area.

    Returns:
        Number of biocontrol agents to release.
    """
    return target_density * area / predator_prey_ratio


# ── fumigation_ct ────────────────────────────────────────────────────────────


def fumigation_ct(concentration: Float64, time_hours: Float64) -> Float64:
    """Fumigation CT product: CT = C * T (g·h/m³).

    Args:
        concentration: Fumigant concentration (g/m³).
        time_hours: Exposure time (hours).

    Returns:
        CT product (g·h/m³).
    """
    return concentration * time_hours


# ── bait_station_density ─────────────────────────────────────────────────────


def bait_station_density(stations: Float64, area_m2: Float64) -> Float64:
    """Bait station density: BSD = stations / area * 10000 (per hectare).

    Args:
        stations: Number of bait stations.
        area_m2: Area in m².

    Returns:
        Station density per hectare.
    """
    return stations / area_m2 * 10000.0


# ── population_reduction ─────────────────────────────────────────────────────


def population_reduction(before: Float64, after: Float64) -> Float64:
    """Population reduction percentage: (before - after) / before * 100.

    Args:
        before: Population count before treatment.
        after: Population count after treatment.

    Returns:
        Percentage reduction (0–100).
    """
    return (before - after) / before * 100.0
