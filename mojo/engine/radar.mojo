"""
radar.mojo — Radar Systems Library. Zero Python imports.

Pure Mojo implementations of fundamental radar engineering equations
including the radar range equation, Doppler processing, range/velocity
ambiguities, resolution, antenna gain, cross section, noise power,
and signal-to-clutter ratio.

Public API:
  radar_range_equation         — Simplified R⁴ computation
  doppler_frequency            — fd = 2*v/λ
  doppler_velocity             — v = fd*λ/2
  range_from_time              — R = c*t/2
  pulse_repetition_interval    — PRI = 1/PRF
  max_unambiguous_range        — Rmax = c/(2*PRF)
  max_unambiguous_velocity     — Vmax = PRF*λ/4
  range_resolution             — ΔR = c/(2*B)
  antenna_gain_from_area       — G = 4π*Ae/λ²
  radar_cross_section_sphere   — σ = π*r²
  noise_power                  — N = k*T*B*F
  signal_to_clutter            — SCR = S/C
"""
from std.math import sqrt, abs as fabs

comptime PI: Float64 = 3.141592653589793
comptime C_LIGHT: Float64 = 3.0e8
comptime K_BOLTZMANN: Float64 = 1.38e-23


# ── radar_range_equation ─────────────────────────────────────────────────────


def radar_range_equation(
    pt: Float64,
    gt: Float64,
    gr: Float64,
    wavelength: Float64,
    sigma: Float64,
    noise_factor: Float64,
    bandwidth: Float64,
    snr_min: Float64,
) -> Float64:
    """Simplified radar range factor: Pt*Gt*Gr*λ²*σ / (SNR_min*Fn*B)."""
    return (
        pt * gt * gr * wavelength * wavelength * sigma
        / (snr_min * noise_factor * bandwidth)
    )


# ── doppler_frequency ────────────────────────────────────────────────────────


def doppler_frequency(velocity: Float64, wavelength: Float64) -> Float64:
    """Doppler frequency fd = 2*v / λ  (Hz)."""
    return 2.0 * velocity / wavelength


# ── doppler_velocity ─────────────────────────────────────────────────────────


def doppler_velocity(fd: Float64, wavelength: Float64) -> Float64:
    """Velocity from Doppler: v = fd * λ / 2  (m/s)."""
    return fd * wavelength / 2.0


# ── range_from_time ──────────────────────────────────────────────────────────


def range_from_time(round_trip_time: Float64, c: Float64) -> Float64:
    """Range R = c * t / 2  (m)."""
    return c * round_trip_time / 2.0


# ── pulse_repetition_interval ────────────────────────────────────────────────


def pulse_repetition_interval(prf: Float64) -> Float64:
    """PRI = 1 / PRF  (s)."""
    return 1.0 / prf


# ── max_unambiguous_range ────────────────────────────────────────────────────


def max_unambiguous_range(prf: Float64, c: Float64) -> Float64:
    """Rmax = c / (2 * PRF)  (m)."""
    return c / (2.0 * prf)


# ── max_unambiguous_velocity ─────────────────────────────────────────────────


def max_unambiguous_velocity(prf: Float64, wavelength: Float64) -> Float64:
    """Vmax = PRF * λ / 4  (m/s)."""
    return prf * wavelength / 4.0


# ── range_resolution ─────────────────────────────────────────────────────────


def range_resolution(bandwidth: Float64) -> Float64:
    """Range resolution ΔR = c / (2*B)  (m), c=3e8."""
    return C_LIGHT / (2.0 * bandwidth)


# ── antenna_gain_from_area ───────────────────────────────────────────────────


def antenna_gain_from_area(aperture_area: Float64, wavelength: Float64) -> Float64:
    """Antenna gain G = 4π*Ae / λ²."""
    return 4.0 * PI * aperture_area / (wavelength * wavelength)


# ── radar_cross_section_sphere ───────────────────────────────────────────────


def radar_cross_section_sphere(radius: Float64) -> Float64:
    """RCS of a large sphere σ = π*r²  (m²)."""
    return PI * radius * radius


# ── noise_power ──────────────────────────────────────────────────────────────


def noise_power(bandwidth: Float64, noise_figure: Float64, temperature: Float64) -> Float64:
    """Noise power N = k*T*B*F  (W)."""
    return K_BOLTZMANN * temperature * bandwidth * noise_figure


# ── signal_to_clutter ────────────────────────────────────────────────────────


def signal_to_clutter(signal_power: Float64, clutter_power: Float64) -> Float64:
    """Signal-to-clutter ratio SCR = S / C."""
    return signal_power / clutter_power
