"""
structural.mojo — Structural Engineering Library. Zero Python imports.

Pure Mojo implementations for structural analysis: stress, deflection,
buckling, combined stress, and natural frequency calculations.

Public API:
  bending_stress                    — σ = M/S
  shear_stress_beam                 — τ = V/A
  moment_of_inertia_rect            — I = bh³/12
  section_modulus_rect              — S = bh²/6
  deflection_cantilever_point       — δ = PL³/(3EI)
  deflection_simply_supported_center — δ = PL³/(48EI)
  euler_buckling_load               — Pcr = π²EI/(kL)²
  slenderness_ratio                 — λ = L/r
  axial_stress                      — σ = P/A
  combined_stress_von_mises         — σ_vm = sqrt(sx²-sx*sy+sy²+3*txy²)
  safety_factor                     — FS = σ_u/σ_w
  natural_frequency_cantilever      — f = (1.875²/(2π))*sqrt(EI/(m*L⁴))
"""
from std.math import sqrt, log, exp, abs as fabs


# ── Constants ────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793
comptime TWO_PI: Float64 = 6.283185307179586


# ── bending_stress ───────────────────────────────────────────────────────────


def bending_stress(moment: Float64, section_modulus: Float64) -> Float64:
    """Bending stress σ = M / S."""
    return moment / section_modulus


# ── shear_stress_beam ────────────────────────────────────────────────────────


def shear_stress_beam(shear_force: Float64, area: Float64) -> Float64:
    """Average shear stress τ = V / A."""
    return shear_force / area


# ── moment_of_inertia_rect ──────────────────────────────────────────────────


def moment_of_inertia_rect(width: Float64, height: Float64) -> Float64:
    """Moment of inertia for a rectangle I = bh³/12."""
    return width * height * height * height / 12.0


# ── section_modulus_rect ─────────────────────────────────────────────────────


def section_modulus_rect(width: Float64, height: Float64) -> Float64:
    """Section modulus for a rectangle S = bh²/6."""
    return width * height * height / 6.0


# ── deflection_cantilever_point ──────────────────────────────────────────────


def deflection_cantilever_point(
    force: Float64, length: Float64, ei: Float64
) -> Float64:
    """Cantilever deflection at tip under point load δ = PL³/(3EI)."""
    return force * length * length * length / (3.0 * ei)


# ── deflection_simply_supported_center ───────────────────────────────────────


def deflection_simply_supported_center(
    force: Float64, length: Float64, ei: Float64
) -> Float64:
    """Simply supported beam mid-span deflection δ = PL³/(48EI)."""
    return force * length * length * length / (48.0 * ei)


# ── euler_buckling_load ─────────────────────────────────────────────────────


def euler_buckling_load(
    ei: Float64, length: Float64, k: Float64
) -> Float64:
    """Euler critical buckling load Pcr = π²EI / (kL)²."""
    var kl = k * length
    return PI * PI * ei / (kl * kl)


# ── slenderness_ratio ───────────────────────────────────────────────────────


def slenderness_ratio(
    length: Float64, radius_of_gyration: Float64
) -> Float64:
    """Slenderness ratio λ = L / r."""
    return length / radius_of_gyration


# ── axial_stress ─────────────────────────────────────────────────────────────


def axial_stress(force: Float64, area: Float64) -> Float64:
    """Axial stress σ = P / A."""
    return force / area


# ── combined_stress_von_mises ────────────────────────────────────────────────


def combined_stress_von_mises(
    sx: Float64, sy: Float64, txy: Float64
) -> Float64:
    """Von Mises equivalent stress σ_vm = sqrt(sx²-sx*sy+sy²+3*txy²)."""
    return sqrt(sx * sx - sx * sy + sy * sy + 3.0 * txy * txy)


# ── safety_factor ────────────────────────────────────────────────────────────


def safety_factor(
    ultimate_strength: Float64, working_stress: Float64
) -> Float64:
    """Safety factor FS = σ_u / σ_w."""
    return ultimate_strength / working_stress


# ── natural_frequency_cantilever ─────────────────────────────────────────────


def natural_frequency_cantilever(
    ei: Float64, mass_per_length: Float64, length: Float64
) -> Float64:
    """First natural frequency of a cantilever beam.
    f = (1.875² / (2π)) * sqrt(EI / (m * L⁴))
    """
    var beta1_sq: Float64 = 3.515625  # 1.875²
    var l4 = length * length * length * length
    return (beta1_sq / TWO_PI) * sqrt(ei / (mass_per_length * l4))
