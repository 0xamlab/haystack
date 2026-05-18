"""
textile.mojo — Textile Engineering Library. Zero Python imports.

Provides yarn count conversions, fabric properties, and textile testing
metrics for textile engineering calculations.

Public API:
  tex_to_denier             — D = tex * 9
  denier_to_tex             — tex = denier / 9
  yarn_count_ne             — Ne = L / W (simplified English cotton count)
  tex_from_diameter_density — tex = π/4 * d² * ρ * 1000
  twist_per_meter           — TPM = TPI * 39.37
  twist_multiplier          — TM = TPI / sqrt(Ne)
  fabric_gsm                — GSM = weight / area
  fabric_cover_factor       — CF = threads / sqrt(count)
  pilling_resistance_score  — Normalized: grade / 5.0
  moisture_regain           — MR = (wet-dry)/dry * 100
  shrinkage_percentage      — S = (L0-Lf)/L0 * 100
  breaking_tenacity         — T = F / tex (cN/tex)
"""
from std.math import sqrt, abs as fabs


# ── Constants ────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793


# ── tex_to_denier ────────────────────────────────────────────────────────────


fn tex_to_denier(tex: Float64) -> Float64:
    """Convert tex to denier: D = tex * 9.

    Args:
        tex: Yarn linear density in tex.

    Returns:
        Denier value.
    """
    return tex * 9.0


# ── denier_to_tex ────────────────────────────────────────────────────────────


fn denier_to_tex(denier: Float64) -> Float64:
    """Convert denier to tex: tex = denier / 9.

    Args:
        denier: Yarn linear density in denier.

    Returns:
        Tex value.
    """
    return denier / 9.0


# ── yarn_count_ne ────────────────────────────────────────────────────────────


fn yarn_count_ne(length_hanks: Float64, weight_grains: Float64) -> Float64:
    """English cotton yarn count (simplified): Ne = L / W.

    Full formula: Ne = (length_hanks * 840) / weight_grains.
    Simplified as Ne = L / W where L and W are in consistent units.

    Args:
        length_hanks: Length in hanks.
        weight_grains: Weight in appropriate units.

    Returns:
        English cotton count Ne.
    """
    if fabs(weight_grains) < 1e-30:
        return 0.0
    return length_hanks / weight_grains


# ── tex_from_diameter_density ────────────────────────────────────────────────


fn tex_from_diameter_density(
    diameter_mm: Float64, density: Float64
) -> Float64:
    """Tex from fibre diameter and density (simplified).

    tex = π/4 * d² * ρ * 1000.

    Args:
        diameter_mm: Fibre diameter in mm.
        density: Fibre density (g/cm³).

    Returns:
        Linear density in tex.
    """
    return PI / 4.0 * diameter_mm * diameter_mm * density * 1000.0


# ── twist_per_meter ──────────────────────────────────────────────────────────


fn twist_per_meter(tpi: Float64) -> Float64:
    """Convert twists per inch to twists per meter: TPM = TPI * 39.37.

    Args:
        tpi: Twists per inch.

    Returns:
        Twists per meter.
    """
    return tpi * 39.37


# ── twist_multiplier ─────────────────────────────────────────────────────────


fn twist_multiplier(tpi: Float64, count_ne: Float64) -> Float64:
    """Twist multiplier: TM = TPI / sqrt(Ne).

    Args:
        tpi: Twists per inch.
        count_ne: English cotton count.

    Returns:
        Twist multiplier.
    """
    if count_ne <= 0.0:
        return 0.0
    return tpi / sqrt(count_ne)


# ── fabric_gsm ───────────────────────────────────────────────────────────────


fn fabric_gsm(weight_g: Float64, area_m2: Float64) -> Float64:
    """Fabric weight in GSM (grams per square meter).

    Args:
        weight_g: Weight in grams.
        area_m2: Area in square meters.

    Returns:
        GSM value.
    """
    if fabs(area_m2) < 1e-30:
        return 0.0
    return weight_g / area_m2


# ── fabric_cover_factor ──────────────────────────────────────────────────────


fn fabric_cover_factor(
    threads_per_cm: Float64, yarn_count: Float64
) -> Float64:
    """Fabric cover factor: CF = threads / sqrt(count).

    Args:
        threads_per_cm: Thread density (threads/cm).
        yarn_count: Yarn count (Ne or similar).

    Returns:
        Cover factor.
    """
    if yarn_count <= 0.0:
        return 0.0
    return threads_per_cm / sqrt(yarn_count)


# ── pilling_resistance_score ─────────────────────────────────────────────────


fn pilling_resistance_score(cycles: Int, grade: Float64) -> Float64:
    """Normalized pilling resistance score: grade / 5.0.

    Args:
        cycles: Number of pilling cycles (informational).
        grade: Pilling grade (1-5 scale).

    Returns:
        Normalized score [0, 1].
    """
    return grade / 5.0


# ── moisture_regain ──────────────────────────────────────────────────────────


fn moisture_regain(wet_weight: Float64, dry_weight: Float64) -> Float64:
    """Moisture regain: MR = (wet - dry) / dry * 100.

    Args:
        wet_weight: Wet weight of sample.
        dry_weight: Dry weight of sample.

    Returns:
        Moisture regain percentage.
    """
    if fabs(dry_weight) < 1e-30:
        return 0.0
    return (wet_weight - dry_weight) / dry_weight * 100.0


# ── shrinkage_percentage ─────────────────────────────────────────────────────


fn shrinkage_percentage(
    original_length: Float64, final_length: Float64
) -> Float64:
    """Shrinkage percentage: S = (L0 - Lf) / L0 * 100.

    Args:
        original_length: Original length.
        final_length: Length after treatment.

    Returns:
        Shrinkage percentage.
    """
    if fabs(original_length) < 1e-30:
        return 0.0
    return (original_length - final_length) / original_length * 100.0


# ── breaking_tenacity ────────────────────────────────────────────────────────


fn breaking_tenacity(breaking_force_n: Float64, tex_val: Float64) -> Float64:
    """Breaking tenacity: T = F / tex (cN/tex when F in cN).

    Args:
        breaking_force_n: Breaking force (cN or N).
        tex_val: Linear density in tex.

    Returns:
        Tenacity (force/tex).
    """
    if fabs(tex_val) < 1e-30:
        return 0.0
    return breaking_force_n / tex_val
