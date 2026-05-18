"""
laundry.mojo — Laundry / Textile Care Science Library. Zero Python imports.

Pure Mojo implementations of laundry and textile care equations including
water usage, detergent dosing, wash energy, spin physics, drying estimates,
fabric wear, stain removal, colour fastness, and water hardness compensation.

Public API:
  water_usage_liters              — W = load * ratio
  detergent_dose_ml               — dose scaled by soil level
  wash_temperature_energy         — energy to heat wash water (kWh)
  spin_g_force                    — centrifugal G-force in drum
  moisture_retention              — % moisture remaining
  drying_time_estimate            — estimated drying minutes
  energy_per_cycle                — kWh consumed per cycle
  cost_per_wash                   — monetary cost per wash
  fabric_wear_cycles              — washes until min strength
  stain_removal_efficiency        — % stain removed
  color_fastness_delta_e          — CIE ΔE colour difference
  water_hardness_compensation     — adjusted detergent dose
"""
from std.math import sqrt, abs as fabs


# ── water_usage_liters ───────────────────────────────────────────────────────


fn water_usage_liters(load_kg: Float64, water_ratio: Float64) -> Float64:
    """W = load * ratio  (litres per kg of laundry)."""
    return load_kg * water_ratio


# ── detergent_dose_ml ────────────────────────────────────────────────────────


fn detergent_dose_ml(load_kg: Float64, soil_level: Float64, base_dose: Float64) -> Float64:
    """D = base * load * soil  (soil: 1=light, 1.5=normal, 2=heavy)."""
    return base_dose * load_kg * soil_level


# ── wash_temperature_energy ──────────────────────────────────────────────────


fn wash_temperature_energy(volume_l: Float64, delta_t: Float64, specific_heat: Float64) -> Float64:
    """E = V * ΔT * cp / 3600  (kWh, cp ≈ 4.186 kJ/L·K)."""
    return volume_l * delta_t * specific_heat / 3600.0


# ── spin_g_force ─────────────────────────────────────────────────────────────


fn spin_g_force(rpm: Float64, drum_radius_m: Float64) -> Float64:
    """G = (2π·RPM/60)² · R / 9.81."""
    comptime PI: Float64 = 3.141592653589793
    var omega = 2.0 * PI * rpm / 60.0
    return omega * omega * drum_radius_m / 9.81


# ── moisture_retention ───────────────────────────────────────────────────────


fn moisture_retention(wet_weight: Float64, dry_weight: Float64) -> Float64:
    """MR = (wet - dry) / dry * 100  (%)."""
    return (wet_weight - dry_weight) / dry_weight * 100.0


# ── drying_time_estimate ─────────────────────────────────────────────────────


fn drying_time_estimate(moisture_pct: Float64, drying_rate: Float64) -> Float64:
    """t = moisture / rate  (minutes)."""
    return moisture_pct / drying_rate


# ── energy_per_cycle ─────────────────────────────────────────────────────────


fn energy_per_cycle(power_kw: Float64, cycle_minutes: Float64) -> Float64:
    """E = P * t/60  (kWh)."""
    return power_kw * cycle_minutes / 60.0


# ── cost_per_wash ────────────────────────────────────────────────────────────


fn cost_per_wash(energy_kwh: Float64, water_l: Float64, energy_rate: Float64, water_rate: Float64) -> Float64:
    """Cost = E * er + W * wr."""
    return energy_kwh * energy_rate + water_l * water_rate


# ── fabric_wear_cycles ──────────────────────────────────────────────────────


fn fabric_wear_cycles(initial_strength: Float64, strength_per_wash: Float64, min_strength: Float64) -> Float64:
    """N = (initial - min) / per_wash."""
    return (initial_strength - min_strength) / strength_per_wash


# ── stain_removal_efficiency ─────────────────────────────────────────────────


fn stain_removal_efficiency(initial_stain: Float64, remaining_stain: Float64) -> Float64:
    """E = (initial - remaining) / initial * 100  (%)."""
    return (initial_stain - remaining_stain) / initial_stain * 100.0


# ── color_fastness_delta_e ───────────────────────────────────────────────────


fn color_fastness_delta_e(l1: Float64, a1: Float64, b1: Float64,
                          l2: Float64, a2: Float64, b2: Float64) -> Float64:
    """ΔE = sqrt((L1-L2)² + (a1-a2)² + (b1-b2)²)."""
    var dl = l1 - l2
    var da = a1 - a2
    var db = b1 - b2
    return sqrt(dl * dl + da * da + db * db)


# ── water_hardness_compensation ──────────────────────────────────────────────


fn water_hardness_compensation(base_dose: Float64, hardness_ppm: Float64, factor: Float64) -> Float64:
    """Dose = base * (1 + hardness * factor / 1000)."""
    return base_dose * (1.0 + hardness_ppm * factor / 1000.0)
