"""
seismology.mojo — Seismology Library. Zero Python imports.

Pure Mojo implementations of seismological functions including magnitude
scales, seismic energy, wave travel times, and recurrence models.

Public API:
  richter_magnitude            — ML = log10(A) + 3*log10(D) - 2.92
  moment_magnitude             — Mw = (2/3)*log10(M0) - 10.7
  seismic_moment               — M0 = 10^(1.5*Mw + 16.05)
  energy_from_magnitude        — E = 10^(1.5*Mw + 4.8)
  peak_ground_acceleration     — Simplified PGA attenuation
  travel_time_p_wave           — t = d / vp
  travel_time_s_wave           — t = d / vs
  ts_tp_difference             — Δt = d*(1/vs - 1/vp)
  epicenter_distance_from_ts_tp — d = Δt / (1/vs - 1/vp)
  intensity_mmi_from_pga       — MMI ≈ 2*log10(pga) + 1
  gutenberg_richter_rate       — N = 10^(a - b*M)
  recurrence_interval          — T = 1 / rate
"""
from std.math import sqrt, abs as fabs, exp, log


# ── Helpers ───────────────────────────────────────────────────────────────────


def _log10(x: Float64) -> Float64:
    """log base 10 via natural log."""
    return log(x) / log(10.0)


def _pow10(x: Float64) -> Float64:
    """10^x via exp."""
    return exp(x * log(10.0))


# ── richter_magnitude ─────────────────────────────────────────────────────────


def richter_magnitude(amplitude: Float64, distance: Float64) -> Float64:
    """ML = log10(A) + 3*log10(D) - 2.92 (simplified local magnitude)."""
    return _log10(amplitude) + 3.0 * _log10(distance) - 2.92


# ── moment_magnitude ──────────────────────────────────────────────────────────


def moment_magnitude(seismic_moment_val: Float64) -> Float64:
    """Mw = (2/3)*log10(M0) - 10.7."""
    return (2.0 / 3.0) * _log10(seismic_moment_val) - 10.7


# ── seismic_moment ────────────────────────────────────────────────────────────


def seismic_moment(mw: Float64) -> Float64:
    """M0 = 10^(1.5*Mw + 16.05)."""
    return _pow10(1.5 * mw + 16.05)


# ── energy_from_magnitude ─────────────────────────────────────────────────────


def energy_from_magnitude(mw: Float64) -> Float64:
    """E = 10^(1.5*Mw + 4.8) in Joules."""
    return _pow10(1.5 * mw + 4.8)


# ── peak_ground_acceleration ──────────────────────────────────────────────────


def peak_ground_acceleration(
    magnitude: Float64, distance: Float64, site_coeff: Float64
) -> Float64:
    """PGA = site * 10^(0.5*M - 1.5*log10(R) - 0.5) (simplified)."""
    var exponent = 0.5 * magnitude - 1.5 * _log10(distance) - 0.5
    return site_coeff * _pow10(exponent)


# ── travel_time_p_wave ────────────────────────────────────────────────────────


def travel_time_p_wave(distance_km: Float64, vp: Float64) -> Float64:
    """P-wave travel time: t = d / vp seconds."""
    return distance_km / vp


# ── travel_time_s_wave ────────────────────────────────────────────────────────


def travel_time_s_wave(distance_km: Float64, vs: Float64) -> Float64:
    """S-wave travel time: t = d / vs seconds."""
    return distance_km / vs


# ── ts_tp_difference ──────────────────────────────────────────────────────────


def ts_tp_difference(
    distance_km: Float64, vp: Float64, vs: Float64
) -> Float64:
    """Δt = d * (1/vs - 1/vp)."""
    return distance_km * (1.0 / vs - 1.0 / vp)


# ── epicenter_distance_from_ts_tp ─────────────────────────────────────────────


def epicenter_distance_from_ts_tp(
    delta_t: Float64, vp: Float64, vs: Float64
) -> Float64:
    """d = Δt / (1/vs - 1/vp)."""
    var denom = 1.0 / vs - 1.0 / vp
    # Equal wave speeds (or a nan payload) zero or poison the denominator and
    # would yield inf/nan, which cannot cross the JSON result wire.
    if denom == 0.0 or denom != denom or delta_t != delta_t:
        return 0.0
    return delta_t / denom


# ── intensity_mmi_from_pga ────────────────────────────────────────────────────


def intensity_mmi_from_pga(pga: Float64) -> Float64:
    """MMI ≈ 2.0 * log10(pga) + 1.0 (simplified)."""
    return 2.0 * _log10(pga) + 1.0


# ── gutenberg_richter_rate ────────────────────────────────────────────────────


def gutenberg_richter_rate(
    a: Float64, b: Float64, magnitude: Float64
) -> Float64:
    """N = 10^(a - b*M) — expected annual rate of events ≥ M."""
    return _pow10(a - b * magnitude)


# ── recurrence_interval ───────────────────────────────────────────────────────


def recurrence_interval(rate: Float64) -> Float64:
    """T = 1 / rate years."""
    return 1.0 / rate
