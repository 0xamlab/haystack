"""
veterinary.mojo — Veterinary Science Library. Zero Python imports.

Pure Mojo implementations of fundamental veterinary medicine equations
including drug dosing, fluid therapy, caloric requirements, body condition,
anesthesia MAC, gestation periods, heart rate ranges, packed cell volume,
and blood volume estimates.

Public API:
  dose_mg                      — Dose = weight * dose_per_kg
  fluid_rate_ml_hr             — Rate = total / hours
  fluid_deficit                — Deficit = weight * dehydration/100 * 1000
  maintenance_fluid_dog        — Rate ≈ 60 * weight (mL/day)
  caloric_requirement_dog      — RER = 70 * weight^0.75 (kcal/day)
  body_condition_score_ideal   — Returns 5.0 for dogs/cats on 1-9 scale
  anesthesia_mac               — Typical MAC values by species/agent
  gestation_period_days        — Gestation by species code
  heart_rate_normal_range_low  — Low normal HR by species
  heart_rate_normal_range_high — High normal HR by species
  packed_cell_volume_normal    — PCV midpoint by species
  blood_volume_estimate        — Blood volume mL by species
"""
from std.math import abs as fabs

# Species codes: 0=Dog, 1=Cat, 2=Horse, 3=Cow
# Agent codes: 0=Isoflurane, 1=Sevoflurane


# ── dose_mg ──────────────────────────────────────────────────────────────────


def dose_mg(weight_kg: Float64, dose_per_kg: Float64) -> Float64:
    """Drug dose (mg) = weight * dose_per_kg."""
    return weight_kg * dose_per_kg


# ── fluid_rate_ml_hr ─────────────────────────────────────────────────────────


def fluid_rate_ml_hr(total_ml: Float64, hours: Float64) -> Float64:
    """Fluid rate = total_ml / hours  (mL/hr)."""
    return total_ml / hours


# ── fluid_deficit ────────────────────────────────────────────────────────────


def fluid_deficit(weight_kg: Float64, dehydration_pct: Float64) -> Float64:
    """Fluid deficit = weight * dehydration/100 * 1000  (mL)."""
    return weight_kg * dehydration_pct / 100.0 * 1000.0


# ── maintenance_fluid_dog ────────────────────────────────────────────────────


def maintenance_fluid_dog(weight_kg: Float64) -> Float64:
    """Maintenance fluid rate ≈ 60 * weight  (mL/day, simplified)."""
    return 60.0 * weight_kg


# ── caloric_requirement_dog ──────────────────────────────────────────────────


def caloric_requirement_dog(weight_kg: Float64) -> Float64:
    """Resting energy requirement RER = 70 * weight^0.75  (kcal/day)."""
    # weight^0.75 = exp(0.75 * ln(weight))
    # Use successive sqrt approach: w^0.75 = w * w^(-0.25) = w / w^0.25
    # Or simply: w^0.75 = (w^3)^0.25 = sqrt(sqrt(w^3))
    var w3 = weight_kg * weight_kg * weight_kg
    var s1 = _sqrt_approx(w3)
    var s2 = _sqrt_approx(s1)
    return 70.0 * s2


def _sqrt_approx(x: Float64) -> Float64:
    """Newton's method sqrt for internal use."""
    if x <= 0.0:
        return 0.0
    var guess = x * 0.5
    for _ in range(20):
        guess = (guess + x / guess) * 0.5
    return guess


# ── body_condition_score_ideal ───────────────────────────────────────────────


def body_condition_score_ideal(species_code: Int) -> Float64:
    """Ideal BCS on 1-9 scale. Dog(0)=5.0, Cat(1)=5.0."""
    return 5.0


# ── anesthesia_mac ───────────────────────────────────────────────────────────


def anesthesia_mac(species_code: Int, agent_code: Int) -> Float64:
    """Typical MAC. Dog/iso=1.3, Cat/iso=1.6, Dog/sevo=2.4, Cat/sevo=3.1."""
    if species_code == 0:  # Dog
        if agent_code == 0:
            return 1.3
        return 2.4  # Sevoflurane
    # Cat (default)
    if agent_code == 0:
        return 1.6
    return 3.1  # Sevoflurane


# ── gestation_period_days ────────────────────────────────────────────────────


def gestation_period_days(species_code: Int) -> Float64:
    """Gestation: Dog(0)=63, Cat(1)=65, Horse(2)=340, Cow(3)=283."""
    if species_code == 0:
        return 63.0
    elif species_code == 1:
        return 65.0
    elif species_code == 2:
        return 340.0
    elif species_code == 3:
        return 283.0
    return 0.0


# ── heart_rate_normal_range_low ──────────────────────────────────────────────


def heart_rate_normal_range_low(species_code: Int) -> Float64:
    """Low normal HR: Dog(0)=60, Cat(1)=120, Horse(2)=28."""
    if species_code == 0:
        return 60.0
    elif species_code == 1:
        return 120.0
    elif species_code == 2:
        return 28.0
    return 0.0


# ── heart_rate_normal_range_high ─────────────────────────────────────────────


def heart_rate_normal_range_high(species_code: Int) -> Float64:
    """High normal HR: Dog(0)=140, Cat(1)=220, Horse(2)=44."""
    if species_code == 0:
        return 140.0
    elif species_code == 1:
        return 220.0
    elif species_code == 2:
        return 44.0
    return 0.0


# ── packed_cell_volume_normal ────────────────────────────────────────────────


def packed_cell_volume_normal(species_code: Int) -> Float64:
    """PCV midpoint: Dog(0)=46.0, Cat(1)=37.5."""
    if species_code == 0:
        return 46.0
    elif species_code == 1:
        return 37.5
    return 0.0


# ── blood_volume_estimate ────────────────────────────────────────────────────


def blood_volume_estimate(weight_kg: Float64, species_code: Int) -> Float64:
    """Blood volume: Dog=90 mL/kg, Cat=60 mL/kg."""
    if species_code == 0:
        return weight_kg * 90.0
    elif species_code == 1:
        return weight_kg * 60.0
    return 0.0
