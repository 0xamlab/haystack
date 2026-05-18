"""
cosmology.mojo — Cosmology Library. Zero Python imports.

Provides Hubble-law kinematics, distance measures, redshift utilities,
critical density, Schwarzschild radius, Stefan-Boltzmann luminosity,
and Wien's displacement law.

Public API:
  hubble_velocity              — v = H0 * d
  hubble_distance              — d = v / H0
  lookback_time_approx         — t ≈ z / (H0*(1+z))  (Gyr)
  comoving_distance_approx     — d_c ≈ c*z / H0  (small z)
  luminosity_distance           — d_L = d_c*(1+z)
  angular_diameter_distance     — d_A = d_c/(1+z)
  redshift_from_wavelength      — z = (λ_obs - λ_em) / λ_em
  cosmic_scale_factor           — a = 1/(1+z)
  critical_density              — ρ_c = 3H0²/(8πG)
  schwarzschild_radius          — r_s = 2GM/c²
  stefan_boltzmann_luminosity   — L = 4πR²σT⁴
  wien_peak_wavelength          — λ_max = b/T
"""
from std.math import exp


# ── Hubble law ───────────────────────────────────────────────────────────────


fn hubble_velocity(h0: Float64, distance_mpc: Float64) -> Float64:
    """Recession velocity v = H0 * d  (km/s).

    h0 in km/s/Mpc, distance_mpc in Mpc.
    """
    return h0 * distance_mpc


fn hubble_distance(h0: Float64, velocity: Float64) -> Float64:
    """Hubble distance d = v / H0  (Mpc).

    h0 in km/s/Mpc, velocity in km/s.
    """
    return velocity / h0


# ── Lookback & comoving distance ─────────────────────────────────────────────


fn lookback_time_approx(z: Float64, h0: Float64) -> Float64:
    """Approximate lookback time: t ≈ z / (H0*(1+z)).

    h0 in km/s/Mpc.  Returns time in seconds; caller may convert to Gyr.
    Simplified — valid for moderate z only.
    """
    # Convert H0 from km/s/Mpc to 1/s:  1 Mpc = 3.0857e22 m = 3.0857e19 km
    var h0_per_sec = h0 / 3.0857e19
    return z / (h0_per_sec * (1.0 + z))


fn comoving_distance_approx(
    z: Float64, c: Float64, h0: Float64
) -> Float64:
    """Approximate comoving distance for small z: d_c ≈ c*z / H0.

    c in km/s, h0 in km/s/Mpc.  Returns Mpc.
    """
    return c * z / h0


# ── Distance measures ────────────────────────────────────────────────────────


fn luminosity_distance(
    comoving_dist: Float64, z: Float64
) -> Float64:
    """Luminosity distance: d_L = d_c * (1 + z)."""
    return comoving_dist * (1.0 + z)


fn angular_diameter_distance(
    comoving_dist: Float64, z: Float64
) -> Float64:
    """Angular diameter distance: d_A = d_c / (1 + z)."""
    return comoving_dist / (1.0 + z)


# ── Redshift utilities ───────────────────────────────────────────────────────


fn redshift_from_wavelength(
    observed: Float64, emitted: Float64
) -> Float64:
    """Cosmological redshift: z = (λ_obs - λ_em) / λ_em."""
    return (observed - emitted) / emitted


fn cosmic_scale_factor(z: Float64) -> Float64:
    """Cosmic scale factor: a = 1 / (1 + z)."""
    return 1.0 / (1.0 + z)


# ── Density & radii ─────────────────────────────────────────────────────────


fn critical_density(h0: Float64) -> Float64:
    """Critical density of the universe: ρ_c = 3*H0² / (8*π*G).

    h0 in km/s/Mpc.  Returns kg/m³.
    G = 6.674e-11 m³/(kg·s²).
    """
    var pi: Float64 = 3.141592653589793
    var G: Float64 = 6.674e-11
    # Convert H0 from km/s/Mpc to 1/s
    var h0_si = h0 / 3.0857e19  # 1 Mpc ≈ 3.0857e19 km
    return 3.0 * h0_si * h0_si / (8.0 * pi * G)


fn schwarzschild_radius(mass: Float64) -> Float64:
    """Schwarzschild radius: r_s = 2*G*M / c².

    mass in kg.  Returns metres.
    G = 6.674e-11, c = 3e8 m/s.
    """
    var G: Float64 = 6.674e-11
    var c: Float64 = 3.0e8
    return 2.0 * G * mass / (c * c)


# ── Radiation laws ───────────────────────────────────────────────────────────


fn stefan_boltzmann_luminosity(
    radius: Float64, temperature: Float64
) -> Float64:
    """Stefan-Boltzmann luminosity: L = 4*π*R²*σ*T⁴.

    radius in metres, temperature in Kelvin.
    σ = 5.670374419e-8 W/(m²·K⁴).
    """
    var pi: Float64 = 3.141592653589793
    var sigma: Float64 = 5.670374419e-8
    var t2 = temperature * temperature
    var t4 = t2 * t2
    return 4.0 * pi * radius * radius * sigma * t4


fn wien_peak_wavelength(temperature: Float64) -> Float64:
    """Wien's displacement law: λ_max = b / T.

    b = 2.897771955e-3 m·K.  Returns wavelength in metres.
    """
    var b: Float64 = 2.897771955e-3
    return b / temperature
