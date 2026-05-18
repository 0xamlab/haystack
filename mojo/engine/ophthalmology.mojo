"""
ophthalmology.mojo — Eye optics and visual system calculations. Zero Python imports.

Public API:
  visual_acuity_decimal         — from Snellen fraction
  refractive_error_spherical    — dioptric power from radius
  lens_power                    — lensmaker's equation
  intraocular_pressure          — IOP from tonometry
  corneal_radius_from_keratometry — K-reading to radius
  retinal_image_size            — magnification and size
  depth_of_focus                — from pupil and acuity
  critical_flicker_frequency    — CFF from luminance
  contrast_sensitivity          — CS from threshold
  dark_adaptation_kinetics      — rhodopsin regeneration
"""
from std.math import log, sqrt, exp


fn visual_acuity_decimal(
    snellen_numerator: Float64, snellen_denominator: Float64
) -> Float64:
    """Visual acuity as decimal from Snellen notation.

    VA = numerator / denominator

    Args:
        snellen_numerator: Test distance (e.g. 20 for 20 feet).
        snellen_denominator: Row denominator (e.g. 20 = 20/20 = 1.0).

    Returns:
        Decimal visual acuity (1.0 = 20/20).
    """
    if snellen_denominator <= 0.0:
        return 0.0
    return snellen_numerator / snellen_denominator


fn refractive_error_spherical(
    far_point_m: Float64
) -> Float64:
    """Refractive error from far point distance.

    D = 1 / far_point_m  (positive = hyperopia, negative = myopia)

    Args:
        far_point_m: Far point distance from eye (m; negative if virtual/behind eye).

    Returns:
        Refractive error (diopters; negative = myope).
    """
    if far_point_m == 0.0:
        return 0.0
    return 1.0 / far_point_m


fn lens_power(
    n_lens: Float64, n_medium: Float64,
    radius1_m: Float64, radius2_m: Float64
) -> Float64:
    """Lensmaker's equation: P = (n_l - n_m) × (1/R1 - 1/R2).

    Args:
        n_lens: Refractive index of lens.
        n_medium: Refractive index of surrounding medium (~1.336 for aqueous).
        radius1_m: Front radius of curvature (m; positive = convex toward incident light).
        radius2_m: Back radius of curvature (m; negative for typical convergent lens).

    Returns:
        Lens power (diopters).
    """
    var curvature_diff = 0.0
    if radius1_m != 0.0:
        curvature_diff = curvature_diff + 1.0 / radius1_m
    if radius2_m != 0.0:
        curvature_diff = curvature_diff - 1.0 / radius2_m
    return (n_lens - n_medium) * curvature_diff


fn intraocular_pressure(
    applanation_force_g: Float64, corneal_thickness_um: Float64
) -> Float64:
    """Goldmann IOP with corneal thickness correction.

    IOP_corrected = IOP_measured + (550 - CCT) × 0.07

    Args:
        applanation_force_g: Applanation tonometer reading (mmHg equivalent).
        corneal_thickness_um: Central corneal thickness (μm; 550 = average).

    Returns:
        Corrected IOP (mmHg).
    """
    return applanation_force_g + (550.0 - corneal_thickness_um) * 0.07


fn corneal_radius_from_keratometry(
    k_diopters: Float64
) -> Float64:
    """Corneal radius from K-reading.

    R = (n_cornea - 1) / K  with n_cornea = 1.3375 (keratometer index)

    Args:
        k_diopters: Keratometry reading (diopters).

    Returns:
        Corneal radius of curvature (mm).
    """
    if k_diopters <= 0.0:
        return 0.0
    return 337.5 / k_diopters


fn retinal_image_size(
    object_size_m: Float64, object_distance_m: Float64, focal_length_m: Float64
) -> Float64:
    """Retinal image size from thin lens approximation.

    h' = h × f / d_object

    Args:
        object_size_m: Object height (m).
        object_distance_m: Object distance from eye (m).
        focal_length_m: Focal length of eye (~17 mm = 0.017 m).

    Returns:
        Retinal image size (mm).
    """
    if object_distance_m <= 0.0:
        return 0.0
    return object_size_m * focal_length_m / object_distance_m * 1000.0


fn depth_of_focus(
    pupil_diameter_mm: Float64, visual_acuity_arcmin: Float64
) -> Float64:
    """Depth of focus from pupil size and acuity.

    DoF ≈ 2 × VA_arcmin / (3438 × pupil_mm)  (diopters)

    Args:
        pupil_diameter_mm: Pupil diameter (mm).
        visual_acuity_arcmin: Minimum angle of resolution (arcmin; 1 = 20/20).

    Returns:
        Depth of focus (diopters).
    """
    if pupil_diameter_mm <= 0.0:
        return 0.0
    return 2.0 * visual_acuity_arcmin / (3438.0 * pupil_diameter_mm / 1000.0)


fn critical_flicker_frequency(
    luminance_cd_m2: Float64, k: Float64, a: Float64
) -> Float64:
    """Critical flicker fusion frequency (Ferry-Porter law).

    CFF = a × log10(L) + k

    Args:
        luminance_cd_m2: Stimulus luminance (cd/m²).
        k: Intercept constant.
        a: Slope constant (~14 Hz per log unit).

    Returns:
        CFF (Hz; typical 5–50 Hz depending on luminance).
    """
    if luminance_cd_m2 <= 0.0:
        return k
    return a * log(luminance_cd_m2) / log(10.0) + k


fn contrast_sensitivity(
    grating_modulation: Float64, threshold_modulation: Float64
) -> Float64:
    """Contrast sensitivity from modulation threshold.

    CS = 1 / threshold_modulation

    Args:
        grating_modulation: Stimulus contrast modulation.
        threshold_modulation: Detection threshold modulation.

    Returns:
        Contrast sensitivity (>100 at peak spatial frequency).
    """
    if threshold_modulation <= 0.0:
        return 0.0
    return 1.0 / threshold_modulation


fn dark_adaptation_kinetics(
    time_min: Float64, final_threshold: Float64, rate: Float64
) -> Float64:
    """Rhodopsin-driven dark adaptation threshold over time.

    threshold(t) = final + A × exp(-k × t)

    Args:
        time_min: Time in dark (minutes).
        final_threshold: Absolute final threshold (log units above absolute).
        rate: Adaptation rate constant k (min⁻¹).

    Returns:
        Log threshold at time t (log units; decreases with time).
    """
    var a = 3.0  # typical initial elevation above final threshold (log units)
    return final_threshold + a * exp(-rate * time_min)
