"""
photonics.mojo — Photonics & Optical Engineering Library. Zero Python imports.

Pure Mojo implementations of optical physics functions including Snell's law,
Fresnel equations, fiber optics, photon energy, and diffraction.

Public API:
  snells_law_angle           — θ2 = asin((n1/n2)*sin(θ1))
  critical_angle             — θc = asin(n2/n1)
  brewster_angle             — θB = atan(n2/n1)
  fresnel_reflectance_normal — R = ((n1-n2)/(n1+n2))²
  numerical_aperture         — NA = sqrt(n_core² - n_clad²)
  photon_energy              — E = hc/λ
  wavelength_to_frequency    — f = c/λ
  frequency_to_wavelength    — λ = c/f
  beer_lambert_transmittance — T = exp(-α*L)
  beer_lambert_absorbance    — A = -log10(T)
  diffraction_grating_angle  — sin(θ) = m*λ/d
  rayleigh_resolution        — θ = 1.22 * λ / D
"""
from std.math import sqrt, abs as fabs, exp, log, sin, asin, atan


# ── Constants ─────────────────────────────────────────────────────────────────

comptime PLANCK: Float64 = 6.626e-34  # Planck constant (J·s)
comptime SPEED_OF_LIGHT: Float64 = 3.0e8  # Speed of light (m/s)
comptime LN10: Float64 = 2.302585092994046  # ln(10)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _log10(x: Float64) -> Float64:
    """log base 10 via natural log."""
    return log(x) / LN10


# ── snells_law_angle ──────────────────────────────────────────────────────────


def snells_law_angle(
    n1: Float64, n2: Float64, theta1: Float64
) -> Float64:
    """Refracted angle: θ2 = asin((n1/n2)*sin(θ1)). Angles in radians."""
    return asin((n1 / n2) * sin(theta1))


# ── critical_angle ────────────────────────────────────────────────────────────


def critical_angle(n1: Float64, n2: Float64) -> Float64:
    """Critical angle for total internal reflection: θc = asin(n2/n1).
    Requires n1 > n2. Returns radians."""
    return asin(n2 / n1)


# ── brewster_angle ────────────────────────────────────────────────────────────


def brewster_angle(n1: Float64, n2: Float64) -> Float64:
    """Brewster angle: θB = atan(n2/n1). Returns radians."""
    return atan(n2 / n1)


# ── fresnel_reflectance_normal ────────────────────────────────────────────────


def fresnel_reflectance_normal(n1: Float64, n2: Float64) -> Float64:
    """Fresnel reflectance at normal incidence: R = ((n1-n2)/(n1+n2))²."""
    var r = (n1 - n2) / (n1 + n2)
    return r * r


# ── numerical_aperture ────────────────────────────────────────────────────────


def numerical_aperture(n_core: Float64, n_clad: Float64) -> Float64:
    """NA = sqrt(n_core² - n_clad²)."""
    return sqrt(n_core * n_core - n_clad * n_clad)


# ── photon_energy ─────────────────────────────────────────────────────────────


def photon_energy(wavelength: Float64) -> Float64:
    """E = hc/λ in Joules. Wavelength in meters."""
    return PLANCK * SPEED_OF_LIGHT / wavelength


# ── wavelength_to_frequency ───────────────────────────────────────────────────


def wavelength_to_frequency(wavelength: Float64) -> Float64:
    """f = c/λ in Hz. Wavelength in meters."""
    return SPEED_OF_LIGHT / wavelength


# ── frequency_to_wavelength ───────────────────────────────────────────────────


def frequency_to_wavelength(frequency: Float64) -> Float64:
    """λ = c/f in meters. Frequency in Hz."""
    return SPEED_OF_LIGHT / frequency


# ── beer_lambert_transmittance ────────────────────────────────────────────────


def beer_lambert_transmittance(
    alpha: Float64, length: Float64
) -> Float64:
    """T = exp(-α*L) — transmittance through absorbing medium."""
    return exp(-alpha * length)


# ── beer_lambert_absorbance ───────────────────────────────────────────────────


def beer_lambert_absorbance(transmittance: Float64) -> Float64:
    """A = -log10(T) — absorbance from transmittance."""
    return -_log10(transmittance)


# ── diffraction_grating_angle ─────────────────────────────────────────────────


def diffraction_grating_angle(
    m: Float64, wavelength: Float64, d: Float64
) -> Float64:
    """sin(θ) = m*λ/d → θ = asin(m*λ/d). Returns radians."""
    return asin(m * wavelength / d)


# ── rayleigh_resolution ───────────────────────────────────────────────────────


def rayleigh_resolution(
    wavelength: Float64, aperture: Float64
) -> Float64:
    """θ = 1.22 * λ / D — Rayleigh criterion angular resolution (radians)."""
    return 1.22 * wavelength / aperture
