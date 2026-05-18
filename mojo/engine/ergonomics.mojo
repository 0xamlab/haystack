"""
ergonomics.mojo — Ergonomics & Human Factors Library. Zero Python imports.

Pure Mojo implementations of ergonomic assessment, noise exposure, visual
perception, and human performance models.

Public API:
  niosh_rwl                       — RWL = LC * HM * VM * DM * AM * FM * CM
  lifting_index                   — LI = L / RWL
  metabolic_rate_walking          — simplified metabolic rate (W)
  heat_stress_index               — HSI = M_heat / E_max * 100
  decibel_addition                — L_total = 10*log10(10^(L1/10) + 10^(L2/10))
  noise_dose                      — D = T / T_allowed
  cumulative_noise_dose_2         — D = t1/ta1 + t2/ta2
  visual_angle_minutes            — θ in arc-minutes
  fitts_law_movement_time         — MT = a + b*log2(2D/W)
  hicks_law_reaction_time         — RT = a + b*log2(n+1)
  comfort_temperature_pmv_simplified — simplified neutral temp estimate
  body_mass_index                 — BMI = weight / height²
"""
from std.math import exp, log, atan2, abs as fabs


# ── Constants ─────────────────────────────────────────────────────────────────

comptime LN2: Float64 = 0.6931471805599453
comptime LN10: Float64 = 2.302585092994046
comptime PI: Float64 = 3.14159265358979323846


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _log2(x: Float64) -> Float64:
    return log(x) / LN2


fn _log10(x: Float64) -> Float64:
    return log(x) / LN10


fn _pow10(x: Float64) -> Float64:
    return exp(x * LN10)


# ── niosh_rwl ─────────────────────────────────────────────────────────────────


fn niosh_rwl(
    lc: Float64,
    hm: Float64,
    vm: Float64,
    dm: Float64,
    am: Float64,
    fm: Float64,
    cm: Float64,
) -> Float64:
    """NIOSH Recommended Weight Limit: RWL = LC * HM * VM * DM * AM * FM * CM."""
    return lc * hm * vm * dm * am * fm * cm


# ── lifting_index ─────────────────────────────────────────────────────────────


fn lifting_index(load_weight: Float64, rwl: Float64) -> Float64:
    """Lifting Index: LI = L / RWL. Values > 1.0 indicate risk."""
    return load_weight / rwl


# ── metabolic_rate_walking ────────────────────────────────────────────────────


fn metabolic_rate_walking(
    body_mass: Float64, speed: Float64, grade: Float64
) -> Float64:
    """Simplified metabolic rate for walking (W).
    M = body_mass * (2.0 + 3.0*speed + grade*speed*0.5)."""
    return body_mass * (2.0 + 3.0 * speed + grade * speed * 0.5)


# ── heat_stress_index ─────────────────────────────────────────────────────────


fn heat_stress_index(
    metabolic_heat: Float64, evaporative_capacity: Float64
) -> Float64:
    """Heat Stress Index: HSI = M_heat / E_max * 100 (%)."""
    return metabolic_heat / evaporative_capacity * 100.0


# ── decibel_addition ──────────────────────────────────────────────────────────


fn decibel_addition(db1: Float64, db2: Float64) -> Float64:
    """Add two decibel levels: L = 10*log10(10^(L1/10) + 10^(L2/10))."""
    var p1 = _pow10(db1 / 10.0)
    var p2 = _pow10(db2 / 10.0)
    return 10.0 * _log10(p1 + p2)


# ── noise_dose ────────────────────────────────────────────────────────────────


fn noise_dose(exposure_time: Float64, allowed_time: Float64) -> Float64:
    """Noise dose fraction: D = T / T_allowed."""
    return exposure_time / allowed_time


# ── cumulative_noise_dose_2 ───────────────────────────────────────────────────


fn cumulative_noise_dose_2(
    t1: Float64, ta1: Float64, t2: Float64, ta2: Float64
) -> Float64:
    """Cumulative noise dose for two exposures: D = t1/ta1 + t2/ta2."""
    return t1 / ta1 + t2 / ta2


# ── visual_angle_minutes ──────────────────────────────────────────────────────


fn visual_angle_minutes(object_size: Float64, distance: Float64) -> Float64:
    """Visual angle in arc-minutes: θ = 2*atan(size/(2*dist)) * (180/π) * 60."""
    var half_angle = atan2(object_size / 2.0, distance)
    return 2.0 * half_angle * (180.0 / PI) * 60.0


# ── fitts_law_movement_time ──────────────────────────────────────────────────


fn fitts_law_movement_time(
    a: Float64, b: Float64, distance: Float64, width: Float64
) -> Float64:
    """Fitts' Law: MT = a + b*log2(2*D/W)."""
    return a + b * _log2(2.0 * distance / width)


# ── hicks_law_reaction_time ──────────────────────────────────────────────────


fn hicks_law_reaction_time(
    a: Float64, b: Float64, n_choices: Float64
) -> Float64:
    """Hick's Law: RT = a + b*log2(n+1)."""
    return a + b * _log2(n_choices + 1.0)


# ── comfort_temperature_pmv_simplified ────────────────────────────────────────


fn comfort_temperature_pmv_simplified(
    met: Float64, clo: Float64, air_temp: Float64
) -> Float64:
    """Simplified PMV comfort estimate.
    Returns approximate neutral temperature: 22 + (clo-0.5)*3 - (met-1.0)*2.
    Negative return means environment is cooler than neutral."""
    var neutral = 22.0 + (clo - 0.5) * 3.0 - (met - 1.0) * 2.0
    return air_temp - neutral


# ── body_mass_index ───────────────────────────────────────────────────────────


fn body_mass_index(weight_kg: Float64, height_m: Float64) -> Float64:
    """BMI = weight / height²."""
    return weight_kg / (height_m * height_m)
