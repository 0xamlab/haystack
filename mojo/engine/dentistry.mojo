"""
dentistry.mojo — Dental Science Library. Zero Python imports.

Provides dental indices, dosing, treatment estimation, and oral health metrics.

Public API:
  dmft_index                    — DMFT = D + M + F
  dmft_prevalence               — P = affected / total * 100
  plaque_index_score            — PI = sum / n
  gingival_index                — GI = sum / n
  attachment_loss               — CAL = PD + recession
  bone_loss_percentage          — BL = (orig - curr) / orig * 100
  fluoride_concentration_ppm   — C = mass / volume
  anesthesia_dose_mg            — Dose = carpules * mg/ml * ml/carpule
  max_anesthesia_dose           — Max = weight * max_per_kg
  restoration_longevity_estimate— Years ≈ 10 * material * (1/load)
  tooth_surface_area_estimate   — Total = n * avg
  treatment_cost_estimate       — Cost = units * cost * factor
"""


# ── dmft_index ───────────────────────────────────────────────────────────────


def dmft_index(decayed: Int, missing: Int, filled: Int) -> Int:
    """DMFT index: DMFT = D + M + F.

    Args:
        decayed: Number of decayed teeth.
        missing: Number of missing teeth.
        filled: Number of filled teeth.

    Returns:
        DMFT score.
    """
    return decayed + missing + filled


# ── dmft_prevalence ──────────────────────────────────────────────────────────


def dmft_prevalence(
    affected_individuals: Int, total_examined: Int
) -> Float64:
    """DMFT prevalence: P = affected / total * 100.

    Args:
        affected_individuals: Individuals with DMFT > 0.
        total_examined: Total individuals examined.

    Returns:
        Prevalence (%).
    """
    if total_examined <= 0:
        return 0.0
    return Float64(affected_individuals) / Float64(total_examined) * 100.0


# ── plaque_index_score ───────────────────────────────────────────────────────


def plaque_index_score(sum_scores: Float64, n_surfaces: Int) -> Float64:
    """Plaque index: PI = sum / n_surfaces.

    Args:
        sum_scores: Sum of plaque scores.
        n_surfaces: Number of surfaces examined.

    Returns:
        Mean plaque index score.
    """
    if n_surfaces <= 0:
        return 0.0
    return sum_scores / Float64(n_surfaces)


# ── gingival_index ───────────────────────────────────────────────────────────


def gingival_index(sum_scores: Float64, n_sites: Int) -> Float64:
    """Gingival index: GI = sum / n_sites.

    Args:
        sum_scores: Sum of gingival scores.
        n_sites: Number of sites examined.

    Returns:
        Mean gingival index score.
    """
    if n_sites <= 0:
        return 0.0
    return sum_scores / Float64(n_sites)


# ── attachment_loss ──────────────────────────────────────────────────────────


def attachment_loss(probing_depth: Float64, recession: Float64) -> Float64:
    """Clinical attachment loss: CAL = PD + recession.

    Args:
        probing_depth: Probing depth (mm).
        recession: Gingival recession (mm).

    Returns:
        Clinical attachment level (mm).
    """
    return probing_depth + recession


# ── bone_loss_percentage ─────────────────────────────────────────────────────


def bone_loss_percentage(
    original_height: Float64, current_height: Float64
) -> Float64:
    """Bone loss %: BL = (original - current) / original * 100.

    Args:
        original_height: Original bone height (mm).
        current_height: Current bone height (mm).

    Returns:
        Bone loss (%).
    """
    if original_height <= 0.0:
        return 0.0
    return (original_height - current_height) / original_height * 100.0


# ── fluoride_concentration_ppm ───────────────────────────────────────────────


def fluoride_concentration_ppm(
    mass_mg: Float64, volume_l: Float64
) -> Float64:
    """Fluoride concentration: C = mass / volume (ppm = mg/L).

    Args:
        mass_mg: Mass of fluoride (mg).
        volume_l: Volume of water (L).

    Returns:
        Concentration (ppm).
    """
    if volume_l <= 0.0:
        return 0.0
    return mass_mg / volume_l


# ── anesthesia_dose_mg ───────────────────────────────────────────────────────


def anesthesia_dose_mg(
    carpules: Float64, mg_per_ml: Float64, ml_per_carpule: Float64
) -> Float64:
    """Anesthesia dose: Dose = carpules * mg_per_ml * ml_per_carpule.

    Args:
        carpules: Number of carpules administered.
        mg_per_ml: Concentration (mg/mL).
        ml_per_carpule: Volume per carpule (mL).

    Returns:
        Total dose (mg).
    """
    return carpules * mg_per_ml * ml_per_carpule


# ── max_anesthesia_dose ──────────────────────────────────────────────────────


def max_anesthesia_dose(
    weight_kg: Float64, max_mg_per_kg: Float64
) -> Float64:
    """Maximum anesthesia dose: Max = weight * max_per_kg.

    Args:
        weight_kg: Patient weight (kg).
        max_mg_per_kg: Maximum mg per kg body weight.

    Returns:
        Maximum dose (mg).
    """
    return weight_kg * max_mg_per_kg


# ── restoration_longevity_estimate ───────────────────────────────────────────


def restoration_longevity_estimate(
    material_factor: Float64, load_factor: Float64
) -> Float64:
    """Restoration longevity: Years ≈ 10 * material_factor * (1 / load_factor).

    Args:
        material_factor: Material durability factor (dimensionless).
        load_factor: Occlusal load factor (dimensionless).

    Returns:
        Estimated longevity (years).
    """
    if load_factor <= 0.0:
        return 0.0
    return 10.0 * material_factor * (1.0 / load_factor)


# ── tooth_surface_area_estimate ──────────────────────────────────────────────


def tooth_surface_area_estimate(
    n_teeth: Int, avg_area_per_tooth: Float64
) -> Float64:
    """Tooth surface area estimate: Total = n * avg.

    Args:
        n_teeth: Number of teeth.
        avg_area_per_tooth: Average surface area per tooth (mm²).

    Returns:
        Total surface area (mm²).
    """
    return Float64(n_teeth) * avg_area_per_tooth


# ── treatment_cost_estimate ──────────────────────────────────────────────────


def treatment_cost_estimate(
    n_units: Int, cost_per_unit: Float64, complexity_factor: Float64
) -> Float64:
    """Treatment cost: Cost = units * cost_per_unit * complexity_factor.

    Args:
        n_units: Number of treatment units.
        cost_per_unit: Cost per unit (currency).
        complexity_factor: Complexity multiplier.

    Returns:
        Estimated total cost (currency).
    """
    return Float64(n_units) * cost_per_unit * complexity_factor
