"""
acoustics.mojo — Acoustics Library. Zero Python imports.

Provides sound level calculations, wave properties, room acoustics,
and Doppler effect computations.

Public API:
  sound_pressure_level           — SPL = 20*log10(p/p_ref)
  sound_intensity_level          — SIL = 10*log10(I/I_ref)
  sound_power_level              — SWL = 10*log10(W/W_ref)
  inverse_square_law_pressure    — SPL at distance d
  wavelength                     — λ = c/f
  resonant_frequency_pipe_open   — f = c/(2*L)
  resonant_frequency_pipe_closed — f = c/(4*L)
  doppler_frequency              — f' = f0*(c+v_o)/(c+v_s)
  reverberation_time_sabine      — T60 = 0.161*V/A
  noise_reduction_coefficient    — NRC = (α250+α500+α1000+α2000)/4
  decibel_sum_2                  — combined level of two sources
  distance_doubling_attenuation  — 6 dB (spherical spreading)
"""
from std.math import log, pow, abs as fabs


# ── helpers ──────────────────────────────────────────────────────────────────

def _log10(x: Float64) -> Float64:
    """log base 10 via natural log."""
    return log(x) / log(10.0)


# ── sound_pressure_level ─────────────────────────────────────────────────────


def sound_pressure_level(p: Float64, p_ref: Float64) -> Float64:
    """Sound pressure level: SPL = 20*log10(p/p_ref).

    Args:
        p: Sound pressure (Pa).
        p_ref: Reference pressure (typically 20e-6 Pa).

    Returns:
        SPL in dB.
    """
    if fabs(p_ref) < 1e-30:
        return 0.0
    return 20.0 * _log10(p / p_ref)


# ── sound_intensity_level ────────────────────────────────────────────────────


def sound_intensity_level(i: Float64, i_ref: Float64) -> Float64:
    """Sound intensity level: SIL = 10*log10(I/I_ref).

    Args:
        i: Sound intensity (W/m²).
        i_ref: Reference intensity (typically 1e-12 W/m²).

    Returns:
        SIL in dB.
    """
    if fabs(i_ref) < 1e-30:
        return 0.0
    return 10.0 * _log10(i / i_ref)


# ── sound_power_level ────────────────────────────────────────────────────────


def sound_power_level(w: Float64, w_ref: Float64) -> Float64:
    """Sound power level: SWL = 10*log10(W/W_ref).

    Args:
        w: Sound power (W).
        w_ref: Reference power (typically 1e-12 W).

    Returns:
        SWL in dB.
    """
    if fabs(w_ref) < 1e-30:
        return 0.0
    return 10.0 * _log10(w / w_ref)


# ── inverse_square_law_pressure ──────────────────────────────────────────────


def inverse_square_law_pressure(
    spl_ref: Float64, d_ref: Float64, d: Float64
) -> Float64:
    """SPL at distance d using inverse square law.

    SPL = SPL_ref - 20*log10(d/d_ref).

    Args:
        spl_ref: Reference SPL (dB).
        d_ref: Reference distance (m).
        d: Target distance (m).

    Returns:
        SPL at distance d (dB).
    """
    if fabs(d_ref) < 1e-30:
        return spl_ref
    return spl_ref - 20.0 * _log10(d / d_ref)


# ── wavelength ───────────────────────────────────────────────────────────────


def wavelength(speed_of_sound: Float64, frequency: Float64) -> Float64:
    """Wavelength: λ = c/f.

    Args:
        speed_of_sound: Speed of sound (m/s).
        frequency: Frequency (Hz).

    Returns:
        Wavelength in meters.
    """
    if fabs(frequency) < 1e-30:
        return 0.0
    return speed_of_sound / frequency


# ── resonant_frequency_pipe_open ─────────────────────────────────────────────


def resonant_frequency_pipe_open(
    speed_of_sound: Float64, length: Float64
) -> Float64:
    """Fundamental resonant frequency of an open pipe: f = c/(2*L).

    Args:
        speed_of_sound: Speed of sound (m/s).
        length: Pipe length (m).

    Returns:
        Frequency in Hz.
    """
    if fabs(length) < 1e-30:
        return 0.0
    return speed_of_sound / (2.0 * length)


# ── resonant_frequency_pipe_closed ───────────────────────────────────────────


def resonant_frequency_pipe_closed(
    speed_of_sound: Float64, length: Float64
) -> Float64:
    """Fundamental resonant frequency of a closed pipe: f = c/(4*L).

    Args:
        speed_of_sound: Speed of sound (m/s).
        length: Pipe length (m).

    Returns:
        Frequency in Hz.
    """
    if fabs(length) < 1e-30:
        return 0.0
    return speed_of_sound / (4.0 * length)


# ── doppler_frequency ────────────────────────────────────────────────────────


def doppler_frequency(
    f0: Float64, v_sound: Float64, v_source: Float64, v_observer: Float64
) -> Float64:
    """Doppler effect: f' = f0 * (c + v_observer) / (c + v_source).

    Convention: positive v_observer = moving toward source,
    positive v_source = moving away from observer.

    Args:
        f0: Emitted frequency (Hz).
        v_sound: Speed of sound (m/s).
        v_source: Source velocity (m/s).
        v_observer: Observer velocity (m/s).

    Returns:
        Observed frequency (Hz).
    """
    var denom = v_sound + v_source
    if fabs(denom) < 1e-30:
        return 0.0
    return f0 * (v_sound + v_observer) / denom


# ── reverberation_time_sabine ────────────────────────────────────────────────


def reverberation_time_sabine(
    volume: Float64, absorption: Float64
) -> Float64:
    """Sabine reverberation time: T60 = 0.161 * V / A.

    Args:
        volume: Room volume (m³).
        absorption: Total absorption (m² Sabins).

    Returns:
        Reverberation time T60 in seconds.
    """
    if fabs(absorption) < 1e-30:
        return 0.0
    return 0.161 * volume / absorption


# ── noise_reduction_coefficient ──────────────────────────────────────────────


def noise_reduction_coefficient(
    alpha_250: Float64,
    alpha_500: Float64,
    alpha_1000: Float64,
    alpha_2000: Float64,
) -> Float64:
    """Noise Reduction Coefficient: NRC = (α250+α500+α1000+α2000)/4.

    Args:
        alpha_250: Absorption coefficient at 250 Hz.
        alpha_500: Absorption coefficient at 500 Hz.
        alpha_1000: Absorption coefficient at 1000 Hz.
        alpha_2000: Absorption coefficient at 2000 Hz.

    Returns:
        NRC value.
    """
    return (alpha_250 + alpha_500 + alpha_1000 + alpha_2000) / 4.0


# ── decibel_sum_2 ────────────────────────────────────────────────────────────


def decibel_sum_2(db1: Float64, db2: Float64) -> Float64:
    """Sum of two decibel levels: L = 10*log10(10^(L1/10) + 10^(L2/10)).

    Args:
        db1: First sound level (dB).
        db2: Second sound level (dB).

    Returns:
        Combined sound level (dB).
    """
    var p1 = pow(10.0, db1 / 10.0)
    var p2 = pow(10.0, db2 / 10.0)
    return 10.0 * _log10(p1 + p2)


# ── distance_doubling_attenuation ────────────────────────────────────────────


def distance_doubling_attenuation() -> Float64:
    """Attenuation when distance doubles (spherical spreading).

    Always returns 6.0 dB.

    Returns:
        6.0 dB.
    """
    return 6.0
