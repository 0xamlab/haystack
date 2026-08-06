"""
nutrition.mojo — Nutritional Science equations. Zero Python imports.

Replaces custom health code with pure Mojo implementations of BMI,
BMR, TDEE, macros, body composition, and cardiovascular estimates.

Public API:
  bmi                  — BMI = weight/height²
  bmi_category         — 0=underweight, 1=normal, 2=overweight, 3=obese
  bmr_mifflin          — Mifflin-St Jeor BMR
  tdee                 — TDEE = BMR·activity_level
  caloric_deficit      — Daily caloric deficit for target loss
  macro_split          — [protein_g, fat_g, carb_g]
  ideal_body_weight    — Devine formula IBW
  body_fat_estimate    — Deurenberg BF% from BMI
  water_intake         — Daily water (liters)
  heart_rate_max       — 220 - age
  target_heart_rate    — [low_bpm, high_bpm]
  vo2max_estimate      — VO2max ≈ 15.3·(HRmax/HRrest)
"""


# ── bmi ──────────────────────────────────────────────────────────────────────


def bmi(weight_kg: Float64, height_m: Float64) -> Float64:
    """Body Mass Index: BMI = weight / height²."""
    return weight_kg / (height_m * height_m)


# ── bmi_category ─────────────────────────────────────────────────────────────


def bmi_category(bmi_val: Float64) -> Int:
    """Classify BMI: 0=underweight, 1=normal, 2=overweight, 3=obese."""
    if bmi_val < 18.5:
        return 0
    elif bmi_val < 25.0:
        return 1
    elif bmi_val < 30.0:
        return 2
    else:
        return 3


# ── bmr_mifflin ──────────────────────────────────────────────────────────────


def bmr_mifflin(weight_kg: Float64, height_cm: Float64, age: Int, is_male: Bool) -> Float64:
    """Mifflin-St Jeor BMR (kcal/day).
    Male:   10·W + 6.25·H - 5·A + 5
    Female: 10·W + 6.25·H - 5·A - 161
    """
    var base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * Float64(age)
    if is_male:
        return base + 5.0
    return base - 161.0


# ── tdee ─────────────────────────────────────────────────────────────────────


def tdee(bmr_val: Float64, activity_level: Float64) -> Float64:
    """Total Daily Energy Expenditure: TDEE = BMR·activity_level (1.2–1.9)."""
    return bmr_val * activity_level


# ── caloric_deficit ──────────────────────────────────────────────────────────


def caloric_deficit(tdee_val: Float64, target_loss_kg_per_week: Float64) -> Float64:
    """Daily caloric deficit needed: deficit = target_loss · 7700 / 7."""
    return target_loss_kg_per_week * 7700.0 / 7.0


# ── macro_split ──────────────────────────────────────────────────────────────


def macro_split(calories: Float64, protein_pct: Float64, fat_pct: Float64) -> List[Float64]:
    """Returns [protein_g, fat_g, carb_g]. Protein=4cal/g, fat=9cal/g, carb=4cal/g."""
    var carb_pct = 1.0 - protein_pct - fat_pct
    var protein_g = (calories * protein_pct) / 4.0
    var fat_g = (calories * fat_pct) / 9.0
    var carb_g = (calories * carb_pct) / 4.0
    var result = List[Float64]()
    result.append(protein_g)
    result.append(fat_g)
    result.append(carb_g)
    return result^


# ── ideal_body_weight ────────────────────────────────────────────────────────


def ideal_body_weight(height_cm: Float64, is_male: Bool) -> Float64:
    """Devine formula IBW (kg).
    Male:   50 + 2.3·((height_cm/2.54) - 60)
    Female: 45.5 + 2.3·((height_cm/2.54) - 60)
    """
    var inches = height_cm / 2.54
    if is_male:
        return 50.0 + 2.3 * (inches - 60.0)
    return 45.5 + 2.3 * (inches - 60.0)


# ── body_fat_estimate ────────────────────────────────────────────────────────


def body_fat_estimate(bmi_val: Float64, age: Int, is_male: Bool) -> Float64:
    """Deurenberg formula: BF% = 1.20·BMI + 0.23·age - 10.8·sex - 5.4.
    sex = 1 for male, 0 for female.
    """
    var sex_factor: Float64 = 1.0 if is_male else 0.0
    return 1.20 * bmi_val + 0.23 * Float64(age) - 10.8 * sex_factor - 5.4


# ── water_intake ─────────────────────────────────────────────────────────────


def water_intake(weight_kg: Float64) -> Float64:
    """Recommended daily water intake in liters: weight · 0.033."""
    return weight_kg * 0.033


# ── heart_rate_max ───────────────────────────────────────────────────────────


def heart_rate_max(age: Int) -> Int:
    """Maximum heart rate: 220 - age."""
    return 220 - age


# ── target_heart_rate ────────────────────────────────────────────────────────


def target_heart_rate(hr_max: Int, intensity_low: Float64, intensity_high: Float64) -> List[Float64]:
    """Target heart rate zone: [low_bpm, high_bpm]."""
    var result = List[Float64]()
    result.append(Float64(hr_max) * intensity_low)
    result.append(Float64(hr_max) * intensity_high)
    return result^


# ── vo2max_estimate ──────────────────────────────────────────────────────────


def vo2max_estimate(hr_rest: Int, hr_max: Int) -> Float64:
    """VO2max estimate: 15.3 · (HRmax / HRrest)."""
    return 15.3 * (Float64(hr_max) / Float64(hr_rest))
