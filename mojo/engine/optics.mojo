"""
optics.mojo — Optics & Photonics equations. Zero Python imports.

Replaces custom optics code with pure Mojo implementations of
refraction, reflection, thin lens, diffraction, and photon energy.

Public API:
  snells_law                — Angle of refraction (degrees)
  critical_angle            — Critical angle for total internal reflection
  fresnel_reflectance_normal — Normal-incidence reflectance
  thin_lens_equation        — Image distance from thin lens formula
  magnification             — Transverse magnification M = -di/do
  wavelength_to_frequency   — f = c/λ  (Hz)
  photon_energy             — E = hc/λ (eV)
  diffraction_limit         — Airy disk angular radius (arcseconds)
  brewster_angle            — Brewster polarisation angle (degrees)
  numerical_aperture        — NA = n·sin(θ)
"""
from std.math import sin, cos, sqrt, asin, atan


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime C_LIGHT: Float64 = 3.0e8          # m/s
comptime H_PLANCK: Float64 = 6.626e-34     # J·s
comptime EV_JOULE: Float64 = 1.602e-19     # J per eV


# ── helpers ──────────────────────────────────────────────────────────────────


def _deg_to_rad(deg: Float64) -> Float64:
    return deg * PI / 180.0


def _rad_to_deg(rad: Float64) -> Float64:
    return rad * 180.0 / PI


# ── snells_law ───────────────────────────────────────────────────────────────


def snells_law(n1: Float64, theta1_deg: Float64, n2: Float64) -> Float64:
    """Angle of refraction in degrees via Snell's law: n1·sin(θ1)=n2·sin(θ2)."""
    var sin_theta2 = n1 * sin(_deg_to_rad(theta1_deg)) / n2
    if sin_theta2 > 1.0 or sin_theta2 < -1.0:
        return -1.0  # total internal reflection
    return _rad_to_deg(asin(sin_theta2))


# ── critical_angle ───────────────────────────────────────────────────────────


def critical_angle(n1: Float64, n2: Float64) -> Float64:
    """Critical angle for total internal reflection (degrees). Returns -1 if n2>=n1."""
    if n2 >= n1:
        return -1.0
    return _rad_to_deg(asin(n2 / n1))


# ── fresnel_reflectance_normal ───────────────────────────────────────────────


def fresnel_reflectance_normal(n1: Float64, n2: Float64) -> Float64:
    """Normal-incidence Fresnel reflectance: R = ((n1-n2)/(n1+n2))²."""
    var r = (n1 - n2) / (n1 + n2)
    return r * r


# ── thin_lens_equation ───────────────────────────────────────────────────────


def thin_lens_equation(f: Float64, do_: Float64) -> Float64:
    """Image distance from thin lens equation: 1/di = 1/f - 1/do."""
    var inv_di = 1.0 / f - 1.0 / do_
    if inv_di == 0.0:
        return 1.0e18  # effectively infinity
    return 1.0 / inv_di


# ── magnification ────────────────────────────────────────────────────────────


def magnification(di: Float64, do_: Float64) -> Float64:
    """Transverse magnification M = -di/do."""
    return -di / do_


# ── wavelength_to_frequency ──────────────────────────────────────────────────


def wavelength_to_frequency(wavelength_nm: Float64) -> Float64:
    """Frequency in Hz from wavelength in nm: f = c/λ."""
    return C_LIGHT / (wavelength_nm * 1.0e-9)


# ── photon_energy ────────────────────────────────────────────────────────────


def photon_energy(wavelength_nm: Float64) -> Float64:
    """Photon energy in eV from wavelength in nm: E = hc/λ."""
    var lam = wavelength_nm * 1.0e-9
    return (H_PLANCK * C_LIGHT / lam) / EV_JOULE


# ── diffraction_limit ────────────────────────────────────────────────────────


def diffraction_limit(wavelength_nm: Float64, aperture_mm: Float64) -> Float64:
    """Airy disk angular radius in arcseconds: θ ≈ 1.22·λ/D."""
    var lam = wavelength_nm * 1.0e-9
    var d = aperture_mm * 1.0e-3
    var rad = 1.22 * lam / d
    return rad * (180.0 / PI) * 3600.0  # radians → arcseconds


# ── brewster_angle ───────────────────────────────────────────────────────────


def brewster_angle(n1: Float64, n2: Float64) -> Float64:
    """Brewster's angle in degrees: θ_B = atan(n2/n1)."""
    return _rad_to_deg(atan(n2 / n1))


# ── numerical_aperture ───────────────────────────────────────────────────────


def numerical_aperture(n: Float64, half_angle_deg: Float64) -> Float64:
    """Numerical aperture: NA = n·sin(θ)."""
    return n * sin(_deg_to_rad(half_angle_deg))
