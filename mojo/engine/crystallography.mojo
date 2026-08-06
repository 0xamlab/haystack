"""
crystallography.mojo — Crystallography Library. Zero Python imports.

Provides Bragg diffraction, d-spacing, unit cell volumes, atomic packing
factors, Scherrer analysis, and crystal density calculations.

Public API:
  bragg_angle                   — θ = asin(nλ/(2d))
  d_spacing_cubic               — d = a / sqrt(h²+k²+l²)
  lattice_parameter_from_d      — a = d * sqrt(h²+k²+l²)
  unit_cell_volume_cubic        — V = a³
  unit_cell_volume_tetragonal   — V = a²*c
  unit_cell_volume_orthorhombic — V = a*b*c
  atomic_packing_factor_fcc     — APF = π√2/6
  atomic_packing_factor_bcc     — APF = π√3/8
  scherrer_crystallite_size     — L = Kλ/(β*cos(θ))
  interplanar_angle_cubic       — cos(φ) formula
  density_from_crystal          — ρ = Z*M/(Na*V)
  structure_factor_magnitude    — |F| = sqrt(f_real² + f_imag²)
"""
from std.math import sqrt, asin, cos, abs as fabs


# ── bragg_angle ──────────────────────────────────────────────────────────────


def bragg_angle(n: Float64, wavelength: Float64, d_spacing: Float64) -> Float64:
    """Bragg angle: θ = asin(nλ/(2d)).

    Args:
        n: Diffraction order.
        wavelength: X-ray wavelength (same units as d).
        d_spacing: Interplanar spacing.

    Returns:
        Bragg angle in radians, or 0 if invalid.
    """
    if fabs(d_spacing) < 1e-30:
        return 0.0
    var arg = n * wavelength / (2.0 * d_spacing)
    if arg < -1.0 or arg > 1.0:
        return 0.0
    return asin(arg)


# ── d_spacing_cubic ──────────────────────────────────────────────────────────


def d_spacing_cubic(
    a: Float64, h: Float64, k: Float64, l: Float64
) -> Float64:
    """Cubic d-spacing: d = a / sqrt(h²+k²+l²).

    Args:
        a: Lattice parameter.
        h: Miller index h.
        k: Miller index k.
        l: Miller index l.

    Returns:
        Interplanar spacing, or 0 if h=k=l=0.
    """
    var hkl2 = h * h + k * k + l * l
    if hkl2 < 1e-30:
        return 0.0
    return a / sqrt(hkl2)


# ── lattice_parameter_from_d ─────────────────────────────────────────────────


def lattice_parameter_from_d(
    d: Float64, h: Float64, k: Float64, l: Float64
) -> Float64:
    """Lattice parameter from d-spacing: a = d * sqrt(h²+k²+l²).

    Args:
        d: Measured d-spacing.
        h: Miller index h.
        k: Miller index k.
        l: Miller index l.

    Returns:
        Lattice parameter.
    """
    var hkl2 = h * h + k * k + l * l
    return d * sqrt(hkl2)


# ── unit_cell_volume_cubic ───────────────────────────────────────────────────


def unit_cell_volume_cubic(a: Float64) -> Float64:
    """Cubic unit cell volume: V = a³.

    Args:
        a: Lattice parameter.

    Returns:
        Volume.
    """
    return a * a * a


# ── unit_cell_volume_tetragonal ──────────────────────────────────────────────


def unit_cell_volume_tetragonal(a: Float64, c: Float64) -> Float64:
    """Tetragonal unit cell volume: V = a²*c.

    Args:
        a: Lattice parameter a.
        c: Lattice parameter c.

    Returns:
        Volume.
    """
    return a * a * c


# ── unit_cell_volume_orthorhombic ────────────────────────────────────────────


def unit_cell_volume_orthorhombic(
    a: Float64, b: Float64, c: Float64
) -> Float64:
    """Orthorhombic unit cell volume: V = a*b*c.

    Args:
        a: Lattice parameter a.
        b: Lattice parameter b.
        c: Lattice parameter c.

    Returns:
        Volume.
    """
    return a * b * c


# ── atomic_packing_factor_fcc ────────────────────────────────────────────────


def atomic_packing_factor_fcc() -> Float64:
    """FCC atomic packing factor: APF = π√2/6 ≈ 0.7405.

    Returns:
        APF for FCC.
    """
    comptime PI: Float64 = 3.141592653589793
    return PI * sqrt(2.0) / 6.0


# ── atomic_packing_factor_bcc ────────────────────────────────────────────────


def atomic_packing_factor_bcc() -> Float64:
    """BCC atomic packing factor: APF = π√3/8 ≈ 0.6802.

    Returns:
        APF for BCC.
    """
    comptime PI: Float64 = 3.141592653589793
    return PI * sqrt(3.0) / 8.0


# ── scherrer_crystallite_size ────────────────────────────────────────────────


def scherrer_crystallite_size(
    k: Float64, wavelength: Float64, fwhm_rad: Float64, theta: Float64
) -> Float64:
    """Scherrer equation: L = Kλ/(β*cos(θ)).

    Args:
        k: Shape factor (~0.9).
        wavelength: X-ray wavelength.
        fwhm_rad: Full width at half maximum (radians).
        theta: Bragg angle (radians).

    Returns:
        Crystallite size, or 0 if denominator is zero.
    """
    var denom = fwhm_rad * cos(theta)
    if fabs(denom) < 1e-30:
        return 0.0
    return k * wavelength / denom


# ── interplanar_angle_cubic ──────────────────────────────────────────────────


def interplanar_angle_cubic(
    h1: Float64, k1: Float64, l1: Float64,
    h2: Float64, k2: Float64, l2: Float64,
) -> Float64:
    """Interplanar angle in cubic: cos(φ) = dot / (mag1*mag2).

    Args:
        h1, k1, l1: Miller indices of plane 1.
        h2, k2, l2: Miller indices of plane 2.

    Returns:
        Angle in radians between the two planes, or 0 if invalid.
    """
    var dot = h1 * h2 + k1 * k2 + l1 * l2
    var m1 = h1 * h1 + k1 * k1 + l1 * l1
    var m2 = h2 * h2 + k2 * k2 + l2 * l2
    var denom = sqrt(m1 * m2)
    if fabs(denom) < 1e-30:
        return 0.0
    var cos_phi = dot / denom
    # Clamp to [-1, 1]
    if cos_phi > 1.0:
        cos_phi = 1.0
    if cos_phi < -1.0:
        cos_phi = -1.0
    # acos via asin: acos(x) = π/2 - asin(x)
    comptime HALF_PI: Float64 = 1.5707963267948966
    return HALF_PI - asin(cos_phi)


# ── density_from_crystal ─────────────────────────────────────────────────────


def density_from_crystal(
    z: Float64, molar_mass: Float64, avogadro: Float64, volume: Float64
) -> Float64:
    """Crystal density: ρ = Z*M/(Na*V).

    Args:
        z: Number of formula units per cell.
        molar_mass: Molar mass (g/mol).
        avogadro: Avogadro's number.
        volume: Unit cell volume (cm³).

    Returns:
        Density (g/cm³), or 0 if denominator is zero.
    """
    var denom = avogadro * volume
    if fabs(denom) < 1e-30:
        return 0.0
    return z * molar_mass / denom


# ── structure_factor_magnitude ───────────────────────────────────────────────


def structure_factor_magnitude(
    f_real: Float64, f_imag: Float64
) -> Float64:
    """Structure factor magnitude: |F| = sqrt(f_real² + f_imag²).

    Args:
        f_real: Real part.
        f_imag: Imaginary part.

    Returns:
        Magnitude.
    """
    return sqrt(f_real * f_real + f_imag * f_imag)
