"""
paleomagnetism.mojo — Ancient geomagnetic field calculations. Zero Python imports.

Public API:
  virtual_geomagnetic_pole_lat  — VGP latitude from inclination
  paleolatitude                 — from magnetic inclination
  geomagnetic_intensity         — relative paleointensity proxy
  declination_correction        — local to geographic
  magnetic_reversal_rate        — from polarity timescale
  koenigsberger_ratio           — NRM / induced magnetisation
  stability_index               — Thellier-type alteration check
  rock_magnetic_susceptibility  — mass-normalised χ
  anhysteretic_remanence        — ARM efficiency
  coercivity_spectrum_median    — median destructive field
"""
from std.math import sqrt, log, exp, cos


def virtual_geomagnetic_pole_lat(inclination_deg: Float64) -> Float64:
    """Paleolatitude from magnetic inclination: tan(I) = 2·tan(λ).

    Args:
        inclination_deg: Magnetic inclination I (degrees).

    Returns:
        Paleolatitude λ (degrees).
    """
    var pi = 3.141592653589793
    var i_rad = inclination_deg * pi / 180.0
    var tan_lambda = 0.5 * (sin_approx(i_rad) / cos_approx(i_rad))
    var lambda_rad = atan_approx(tan_lambda)
    return lambda_rad * 180.0 / pi


def sin_approx(x: Float64) -> Float64:
    var x2 = x * x
    return x * (1.0 - x2 / 6.0 + x2 * x2 / 120.0)


def cos_approx(x: Float64) -> Float64:
    var x2 = x * x
    return 1.0 - x2 / 2.0 + x2 * x2 / 24.0


def atan_approx(x: Float64) -> Float64:
    if x < 0.0:
        return -atan_approx(-x)
    if x > 1.0:
        var pi_2 = 1.5707963267948966
        return pi_2 - atan_approx(1.0 / x)
    var x2 = x * x
    return x * (1.0 - x2 / 3.0 + x2 * x2 / 5.0 - x2 * x2 * x2 / 7.0)


def paleolatitude(inclination_deg: Float64) -> Float64:
    """Paleolatitude from paleomagnetic inclination (dipole formula).

    tan(I) = 2·tan(λ)  →  λ = atan(tan(I)/2)

    Args:
        inclination_deg: Inclination in degrees.

    Returns:
        Paleolatitude (degrees; positive = northern hemisphere).
    """
    var pi = 3.141592653589793
    var i_rad = inclination_deg * pi / 180.0
    var tan_i = sin_approx(i_rad) / (cos_approx(i_rad) + 1e-15)
    return atan_approx(tan_i / 2.0) * 180.0 / pi


def geomagnetic_intensity(
    nrm: Float64, susceptibility: Float64
) -> Float64:
    """Relative paleointensity proxy: RPI = NRM / χ.

    Args:
        nrm: Natural remanent magnetisation (A/m).
        susceptibility: Magnetic susceptibility (SI).

    Returns:
        RPI proxy (normalised, dimensionless).
    """
    if susceptibility <= 0.0:
        return 0.0
    return nrm / susceptibility


def declination_correction(
    observed_dec: Float64, site_azimuth: Float64
) -> Float64:
    """Geographic declination corrected for sampling orientation.

    Args:
        observed_dec: Measured paleodeclination (°).
        site_azimuth: Orientation of reference direction (°).

    Returns:
        Geographically corrected declination (°).
    """
    return observed_dec - site_azimuth


def magnetic_reversal_rate(
    n_reversals: Float64, timespan_myr: Float64
) -> Float64:
    """Geomagnetic reversal frequency over a geological interval.

    rate = n_reversals / timespan

    Args:
        n_reversals: Number of polarity reversals.
        timespan_myr: Duration of interval (Myr).

    Returns:
        Reversal rate (reversals/Myr).
    """
    if timespan_myr <= 0.0:
        return 0.0
    return n_reversals / timespan_myr


def koenigsberger_ratio(
    nrm: Float64, field_strength: Float64, susceptibility: Float64
) -> Float64:
    """Koenigsberger ratio Q = NRM / (χ·H).

    Args:
        nrm: Natural remanent magnetisation (A/m).
        field_strength: Present geomagnetic field H (A/m).
        susceptibility: Low-field susceptibility χ (SI).

    Returns:
        Q ratio (>1 = NRM dominates over induced magnetisation).
    """
    var induced = susceptibility * field_strength
    if induced <= 0.0:
        return 0.0
    return nrm / induced


def stability_index(
    nrm_before: Float64, nrm_after_heating: Float64
) -> Float64:
    """Thellier alteration check: alteration = |NRM_after - NRM_before| / NRM_before.

    Args:
        nrm_before: NRM measured before in-field step.
        nrm_after_heating: pTRM check NRM after re-heating.

    Returns:
        Fractional alteration (0 = unaltered, >0.05 = altered sample).
    """
    if nrm_before <= 0.0:
        return 0.0
    var diff = nrm_after_heating - nrm_before
    if diff < 0.0:
        diff = -diff
    return diff / nrm_before


def rock_magnetic_susceptibility(
    measured_susceptibility: Float64, mass_g: Float64
) -> Float64:
    """Mass-normalised magnetic susceptibility χ_mass.

    Args:
        measured_susceptibility: Bulk χ (SI).
        mass_g: Sample mass (g).

    Returns:
        Mass-specific susceptibility (m³/kg × 10⁻⁸).
    """
    if mass_g <= 0.0:
        return 0.0
    return measured_susceptibility / (mass_g * 1e-3) * 1e8


def anhysteretic_remanence(arm: Float64, bias_field_mt: Float64) -> Float64:
    """ARM efficiency: normalised ARM susceptibility χARM.

    χARM = ARM / bias_field

    Args:
        arm: Anhysteretic remanent magnetisation (A/m).
        bias_field_mt: DC bias field during ARM acquisition (mT).

    Returns:
        ARM susceptibility (A/m/mT).
    """
    if bias_field_mt <= 0.0:
        return 0.0
    return arm / bias_field_mt


def coercivity_spectrum_median(
    h_upper: Float64, h_lower: Float64
) -> Float64:
    """Median destructive field from coercivity window bounds.

    MDF ≈ (H_upper + H_lower) / 2

    Args:
        h_upper: Field demagnetising 75% of NRM (mT).
        h_lower: Field demagnetising 25% of NRM (mT).

    Returns:
        Median destructive field MDF (mT).
    """
    return (h_upper + h_lower) / 2.0
