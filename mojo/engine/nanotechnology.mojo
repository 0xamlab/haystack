"""
nanotechnology.mojo — Nanotechnology and nanoscale physics calculations.

Public API:
  surface_to_volume_sphere                — SA/V = 3/r
  nanoparticle_surface_area               — SA = 4π*r²
  nanoparticle_volume                     — V = 4/3*π*r³
  specific_surface_area                   — SSA = SA/mass
  quantum_confinement_energy              — E = h²/(8*m*L²)
  mean_free_path                          — λ = kT/(√2*π*d²*P)
  knudsen_number                          — Kn = λ/L
  van_der_waals_force                     — F = A*R/(6*d²)
  diffusion_coefficient_stokes_einstein   — D = kT/(6πηr)
  zeta_potential_mobility                 — ζ = η*μ/ε
  aspect_ratio                            — AR = L/D
  packing_fraction_fcc                    — π*√2/6 ≈ 0.7405
"""
from std.math import sqrt


comptime PI: Float64 = 3.141592653589793
comptime SQRT2: Float64 = 1.4142135623730951


# ── surface_to_volume_sphere ─────────────────────────────────────────────────


fn surface_to_volume_sphere(radius: Float64) -> Float64:
    """Surface-to-volume ratio for sphere: SA/V = 3/r."""
    return 3.0 / radius


# ── nanoparticle_surface_area ────────────────────────────────────────────────


fn nanoparticle_surface_area(radius: Float64) -> Float64:
    """Surface area of sphere: SA = 4πr²."""
    return 4.0 * PI * radius * radius


# ── nanoparticle_volume ──────────────────────────────────────────────────────


fn nanoparticle_volume(radius: Float64) -> Float64:
    """Volume of sphere: V = 4/3 * π * r³."""
    return (4.0 / 3.0) * PI * radius * radius * radius


# ── specific_surface_area ────────────────────────────────────────────────────


fn specific_surface_area(sa: Float64, mass: Float64) -> Float64:
    """Specific surface area: SSA = SA / mass (m²/g)."""
    return sa / mass


# ── quantum_confinement_energy ───────────────────────────────────────────────


fn quantum_confinement_energy(h: Float64, m_eff: Float64, l: Float64) -> Float64:
    """Particle-in-a-box energy: E = h² / (8 * m * L²)."""
    return (h * h) / (8.0 * m_eff * l * l)


# ── mean_free_path ───────────────────────────────────────────────────────────


fn mean_free_path(kb: Float64, t: Float64, d: Float64, p: Float64) -> Float64:
    """Mean free path: λ = kT / (√2 * π * d² * P)."""
    return (kb * t) / (SQRT2 * PI * d * d * p)


# ── knudsen_number ───────────────────────────────────────────────────────────


fn knudsen_number(mean_free_path_val: Float64, characteristic_length: Float64) -> Float64:
    """Knudsen number: Kn = λ / L."""
    return mean_free_path_val / characteristic_length


# ── van_der_waals_force ──────────────────────────────────────────────────────


fn van_der_waals_force(hamaker: Float64, radius: Float64, distance: Float64) -> Float64:
    """Van der Waals force (sphere-flat): F = A*R / (6*d²)."""
    return (hamaker * radius) / (6.0 * distance * distance)


# ── diffusion_coefficient_stokes_einstein ────────────────────────────────────


fn diffusion_coefficient_stokes_einstein(
    kb: Float64, t: Float64, viscosity: Float64, radius: Float64
) -> Float64:
    """Stokes-Einstein diffusion: D = kT / (6πηr)."""
    return (kb * t) / (6.0 * PI * viscosity * radius)


# ── zeta_potential_mobility ──────────────────────────────────────────────────


fn zeta_potential_mobility(
    viscosity: Float64, mobility: Float64, permittivity: Float64
) -> Float64:
    """Zeta potential from mobility: ζ = η*μ/ε."""
    return (viscosity * mobility) / permittivity


# ── aspect_ratio ─────────────────────────────────────────────────────────────


fn aspect_ratio(length: Float64, diameter: Float64) -> Float64:
    """Aspect ratio: AR = L / D."""
    return length / diameter


# ── packing_fraction_fcc ─────────────────────────────────────────────────────


fn packing_fraction_fcc() -> Float64:
    """FCC packing fraction: π*√2/6 ≈ 0.7405."""
    return PI * SQRT2 / 6.0
