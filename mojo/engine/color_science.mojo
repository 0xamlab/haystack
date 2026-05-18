"""
color_science.mojo — Color Science / Colorimetry Library. Zero Python imports.

Pure Mojo implementations of fundamental colorimetry equations
including CIE76 delta-E, Lab-to-LCH conversion, sRGB luminance,
WCAG contrast ratio, colour temperature, metamerism index,
chromatic adaptation, CRI, and CIE whiteness index.

Public API:
  delta_e_76                  — CIE76 colour difference
  lab_to_lch_l                — L* passthrough
  lab_to_lch_c                — chroma C*
  lab_to_lch_h                — hue angle h°
  rgb_to_luminance            — sRGB relative luminance Y
  contrast_ratio              — WCAG contrast ratio
  wcag_aa_pass                — WCAG AA compliance check
  color_temperature_approx    — simplified CCT from R,B
  metamerism_index            — |ΔE_D65 - ΔE_A|
  chromatic_adaptation_von_kries — x * gain
  cri_from_delta_e            — CRI ≈ 100 - 4.6*ΔE
  whiteness_index_cie         — CIE whiteness W
"""
from std.math import sqrt, abs as fabs, atan2


# ── delta_e_76 ───────────────────────────────────────────────────────────────


fn delta_e_76(
    l1: Float64, a1: Float64, b1: Float64,
    l2: Float64, a2: Float64, b2: Float64,
) -> Float64:
    """CIE76 ΔE = sqrt((L1-L2)² + (a1-a2)² + (b1-b2)²)."""
    var dl = l1 - l2
    var da = a1 - a2
    var db = b1 - b2
    return sqrt(dl * dl + da * da + db * db)


# ── lab_to_lch_l ─────────────────────────────────────────────────────────────


fn lab_to_lch_l(l: Float64) -> Float64:
    """L_LCH = L (identity passthrough)."""
    return l


# ── lab_to_lch_c ─────────────────────────────────────────────────────────────


fn lab_to_lch_c(a: Float64, b: Float64) -> Float64:
    """Chroma C = sqrt(a² + b²)."""
    return sqrt(a * a + b * b)


# ── lab_to_lch_h ─────────────────────────────────────────────────────────────


fn lab_to_lch_h(a: Float64, b: Float64) -> Float64:
    """Hue h = atan2(b, a) * 180/π (degrees). Wraps negative to 0-360."""
    var h = atan2(b, a) * 180.0 / 3.141592653589793
    if h < 0.0:
        h += 360.0
    return h


# ── rgb_to_luminance ─────────────────────────────────────────────────────────


fn rgb_to_luminance(r: Float64, g: Float64, b: Float64) -> Float64:
    """sRGB relative luminance Y = 0.2126*R + 0.7152*G + 0.0722*B."""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ── contrast_ratio ───────────────────────────────────────────────────────────


fn contrast_ratio(l1: Float64, l2: Float64) -> Float64:
    """WCAG contrast ratio CR = (lighter+0.05)/(darker+0.05)."""
    var lighter = l1
    var darker = l2
    if l2 > l1:
        lighter = l2
        darker = l1
    return (lighter + 0.05) / (darker + 0.05)


# ── wcag_aa_pass ─────────────────────────────────────────────────────────────


fn wcag_aa_pass(contrast_ratio_val: Float64, font_size_pt: Float64) -> Float64:
    """Returns 1.0 if passes WCAG AA, 0.0 otherwise.
    Large text (>=18pt): CR>=3.0. Normal text: CR>=4.5."""
    if font_size_pt >= 18.0:
        if contrast_ratio_val >= 3.0:
            return 1.0
        return 0.0
    if contrast_ratio_val >= 4.5:
        return 1.0
    return 0.0


# ── color_temperature_approx ────────────────────────────────────────────────


fn color_temperature_approx(r: Float64, b: Float64) -> Float64:
    """Simplified CCT ≈ 6500 * (B/R) (Kelvin)."""
    return 6500.0 * (b / r)


# ── metamerism_index ─────────────────────────────────────────────────────────


fn metamerism_index(delta_e_d65: Float64, delta_e_a: Float64) -> Float64:
    """MI = |ΔE_D65 - ΔE_A|."""
    return fabs(delta_e_d65 - delta_e_a)


# ── chromatic_adaptation_von_kries ───────────────────────────────────────────


fn chromatic_adaptation_von_kries(x: Float64, gain: Float64) -> Float64:
    """von Kries adaptation: x_adapted = x * gain."""
    return x * gain


# ── cri_from_delta_e ─────────────────────────────────────────────────────────


fn cri_from_delta_e(avg_delta_e: Float64) -> Float64:
    """CRI ≈ 100 - 4.6 * ΔE (simplified)."""
    return 100.0 - 4.6 * avg_delta_e


# ── whiteness_index_cie ──────────────────────────────────────────────────────


fn whiteness_index_cie(
    big_y: Float64, x: Float64, y: Float64, xn: Float64, yn: Float64,
) -> Float64:
    """CIE whiteness W = Y + 800*(xn-x) + 1700*(yn-y)."""
    return big_y + 800.0 * (xn - x) + 1700.0 * (yn - y)
