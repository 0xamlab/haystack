"""
brewing.mojo — Brewing Science Library. Zero Python imports.

Pure Mojo implementations of fundamental brewing science equations
including gravity conversions, ABV, attenuation, bitterness (IBU),
mash calculations, colour, and priming sugar.

Public API:
  original_gravity_to_plato      — OG to °Plato (simplified)
  plato_to_gravity               — °Plato to SG (simplified)
  abv_from_og_fg                 — ABV from OG and FG
  apparent_attenuation            — AA% from OG and FG
  real_attenuation                — RA from apparent attenuation
  ibu_tinseth                    — IBU via Tinseth formula
  utilization_tinseth            — hop utilization (Tinseth)
  mash_water_volume              — water volume for mash
  strike_water_temp              — strike water temperature
  color_srm_from_mcu             — SRM via Morey equation
  calories_per_12oz              — simplified calorie estimate
  priming_sugar_g                — priming sugar amount
"""
from std.math import sqrt, exp, log, abs as fabs


# ── original_gravity_to_plato ────────────────────────────────────────────────


fn original_gravity_to_plato(og: Float64) -> Float64:
    """P ≈ (OG - 1) * 1000 / 4  (simplified conversion)."""
    return (og - 1.0) * 1000.0 / 4.0


# ── plato_to_gravity ─────────────────────────────────────────────────────────


fn plato_to_gravity(plato: Float64) -> Float64:
    """SG ≈ 1 + plato * 4 / 1000  (simplified conversion)."""
    return 1.0 + plato * 4.0 / 1000.0


# ── abv_from_og_fg ───────────────────────────────────────────────────────────


fn abv_from_og_fg(og: Float64, fg: Float64) -> Float64:
    """ABV = (OG - FG) * 131.25."""
    return (og - fg) * 131.25


# ── apparent_attenuation ─────────────────────────────────────────────────────


fn apparent_attenuation(og: Float64, fg: Float64) -> Float64:
    """AA = (OG - FG) / (OG - 1.0) * 100."""
    var denom = og - 1.0
    if denom == 0.0:
        return 0.0
    return (og - fg) / denom * 100.0


# ── real_attenuation ─────────────────────────────────────────────────────────


fn real_attenuation(apparent_att: Float64) -> Float64:
    """RA ≈ apparent_att * 0.8192  (Balling correction)."""
    return apparent_att * 0.8192


# ── ibu_tinseth ──────────────────────────────────────────────────────────────


fn ibu_tinseth(
    utilization: Float64,
    alpha_acid_pct: Float64,
    weight_oz: Float64,
    volume_gal: Float64,
) -> Float64:
    """IBU = (U * AA% * W * 7490) / V."""
    if volume_gal == 0.0:
        return 0.0
    return (utilization * alpha_acid_pct * weight_oz * 7490.0) / volume_gal


# ── utilization_tinseth ──────────────────────────────────────────────────────


fn utilization_tinseth(gravity: Float64, time_min: Float64) -> Float64:
    """U = 1.65 * 0.000125^(G-1) * (1 - exp(-0.04*t)) / 4.15."""
    var bigness = 1.65 * exp((gravity - 1.0) * log(0.000125))
    var boil_factor = (1.0 - exp(-0.04 * time_min)) / 4.15
    return bigness * boil_factor


# ── mash_water_volume ────────────────────────────────────────────────────────


fn mash_water_volume(grain_weight_kg: Float64, ratio: Float64) -> Float64:
    """V = grain_weight * ratio  (litres, ratio in L/kg)."""
    return grain_weight_kg * ratio


# ── strike_water_temp ────────────────────────────────────────────────────────


fn strike_water_temp(
    target_temp: Float64, grain_temp: Float64, ratio: Float64
) -> Float64:
    """Tw = (0.2/ratio) * (target - grain) + target.

    ratio is water-to-grain ratio in L/kg (or qt/lb).
    """
    if ratio == 0.0:
        return target_temp
    return (0.2 / ratio) * (target_temp - grain_temp) + target_temp


# ── color_srm_from_mcu ──────────────────────────────────────────────────────


fn color_srm_from_mcu(mcu: Float64) -> Float64:
    """SRM = 1.4922 * MCU^0.6859  (Morey equation)."""
    if mcu <= 0.0:
        return 0.0
    return 1.4922 * exp(0.6859 * log(mcu))


# ── calories_per_12oz ────────────────────────────────────────────────────────


fn calories_per_12oz(og: Float64, fg: Float64) -> Float64:
    """Simplified calorie estimate per 12 oz serving.

    Cal ≈ 3621 * fg * ((0.8114*og + 0.1886*fg - 1)*3.55 +
                        (og - fg)*2.75*7.0) / 12.0
    Based on the alcohol and residual extract contributions.
    """
    var re = 0.8114 * og + 0.1886 * fg - 1.0
    var abw = (og - fg) * 2.75
    var cal = 3621.0 * fg * (re * 3.55 + abw * 7.0) / 12.0
    return cal


# ── priming_sugar_g ──────────────────────────────────────────────────────────


fn priming_sugar_g(
    volume_co2: Float64, temp_c: Float64, volume_beer_l: Float64
) -> Float64:
    """Priming sugar (g) ≈ volume_beer * (volume_co2 - residual) * factor.

    Residual CO2 ≈ 3.0378 - 0.050062*T + 0.00026555*T²  (simplified).
    Factor ≈ 4.0 g/L per vol CO2 for table sugar.
    """
    var residual = 3.0378 - 0.050062 * temp_c + 0.00026555 * temp_c * temp_c
    var needed = volume_co2 - residual
    if needed < 0.0:
        needed = 0.0
    return volume_beer_l * needed * 4.0
