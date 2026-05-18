"""
psychoacoustics.mojo — Human perception of sound calculations. Zero Python imports.

Public API:
  loudness_phon_to_sone        — sones from phon level
  loudness_sone_to_phon        — phon from sone level
  critical_bandwidth           — Bark scale bandwidth (Hz)
  bark_scale                   — Bark value from frequency
  masking_threshold            — simultaneous masking threshold estimate
  speech_intelligibility_index — SII contribution from band
  equal_loudness_correction    — Rosen correction dB at frequency
  frequency_just_noticeable    — JND in frequency from Weber fraction
  temporal_masking_decay       — post-masking threshold decay
  binaural_masking_level_diff  — BMLD from binaural processing
"""
from std.math import log, exp, pow, sqrt


fn _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


fn loudness_phon_to_sone(phon: Float64) -> Float64:
    """Convert loudness level in phons to sones.

    For phon ≥ 40: sone = 2^((phon-40)/10)
    For phon < 40:  sone ≈ (phon/40)^2.642

    Args:
        phon: Loudness level (phon).

    Returns:
        Loudness (sone).
    """
    if phon < 0.0:
        return 0.0
    if phon >= 40.0:
        return pow(2.0, (phon - 40.0) / 10.0)
    return pow(phon / 40.0, 2.642)


fn loudness_sone_to_phon(sone: Float64) -> Float64:
    """Convert sone to phon.

    For sone ≥ 1: phon = 40 + 10·log2(sone)
    For sone < 1: phon ≈ 40·sone^0.378

    Args:
        sone: Loudness (sone).

    Returns:
        Loudness level (phon).
    """
    if sone <= 0.0:
        return 0.0
    if sone >= 1.0:
        return 40.0 + 10.0 * log(sone) / log(2.0)
    return 40.0 * pow(sone, 0.378)


fn critical_bandwidth(center_freq_hz: Float64) -> Float64:
    """Critical bandwidth (ERB approximation) at a center frequency.

    ERB ≈ 24.7·(4.37·f/1000 + 1)

    Args:
        center_freq_hz: Center frequency (Hz).

    Returns:
        ERB bandwidth (Hz).
    """
    return 24.7 * (4.37 * center_freq_hz / 1000.0 + 1.0)


fn bark_scale(frequency_hz: Float64) -> Float64:
    """Bark scale value from frequency (Traunmüller 1990).

    Bark = 26.81·f/(1960+f) - 0.53

    Args:
        frequency_hz: Frequency (Hz).

    Returns:
        Bark value.
    """
    return 26.81 * frequency_hz / (1960.0 + frequency_hz) - 0.53


fn masking_threshold(
    masker_spl: Float64, masker_freq_hz: Float64, target_freq_hz: Float64
) -> Float64:
    """Simultaneous masking threshold estimate (simplified excitation pattern).

    Args:
        masker_spl: Masker sound pressure level (dB SPL).
        masker_freq_hz: Masker center frequency (Hz).
        target_freq_hz: Target frequency (Hz).

    Returns:
        Approximate masking threshold at target frequency (dB SPL).
    """
    var bark_m = bark_scale(masker_freq_hz)
    var bark_t = bark_scale(target_freq_hz)
    var delta_bark = bark_t - bark_m
    # Simplified spreading function
    var spread: Float64
    if delta_bark >= 0.0:
        spread = -delta_bark * 25.0  # upper slope ~25 dB/Bark
    else:
        spread = delta_bark * 15.0   # lower slope ~15 dB/Bark
    return masker_spl + spread - 10.0


fn speech_intelligibility_index(
    speech_spl: Float64, noise_spl: Float64, band_importance: Float64
) -> Float64:
    """Speech intelligibility index contribution from one frequency band.

    SII_band = I_i · (SNR + 15) / 30  clamped to [0,1]

    Args:
        speech_spl: Speech SPL in band (dB).
        noise_spl: Noise SPL in band (dB).
        band_importance: Band importance function value I_i.

    Returns:
        SII band contribution.
    """
    var snr = speech_spl - noise_spl
    var sii = band_importance * (snr + 15.0) / 30.0
    if sii < 0.0:
        return 0.0
    if sii > band_importance:
        return band_importance
    return sii


fn equal_loudness_correction(frequency_hz: Float64, spl_db: Float64) -> Float64:
    """Approximate A-weighting correction at a frequency.

    dB(A) ≈ dB + A_weight(f)   A-weighting filter approximation.

    Args:
        frequency_hz: Frequency (Hz).
        spl_db: Sound pressure level (dB).

    Returns:
        A-weighted level (dB(A)).
    """
    # Simplified A-weighting (ITU-R 468 approximation using polynomial)
    var f = frequency_hz
    if f <= 0.0:
        return spl_db - 70.0
    var log_f = _log10(f)
    # Approximate A-weighting curve
    var a_weight = (-145.528 + 98.262 * log_f
                   - 19.509 * log_f * log_f
                   + 0.975 * log_f * log_f * log_f)
    return spl_db + a_weight


fn frequency_just_noticeable(center_freq_hz: Float64, jnd_fraction: Float64) -> Float64:
    """Just noticeable difference in frequency.

    ΔFJND = f · JND_fraction

    Args:
        center_freq_hz: Center frequency (Hz).
        jnd_fraction: Weber fraction for frequency (typically 0.003–0.01).

    Returns:
        JND in frequency (Hz).
    """
    return center_freq_hz * jnd_fraction


fn temporal_masking_decay(
    time_after_offset_ms: Float64, initial_masking_db: Float64
) -> Float64:
    """Post-masker temporal masking decay.

    Threshold ≈ initial · exp(-t/20)  (20 ms time constant)

    Args:
        time_after_offset_ms: Time after masker offset (ms).
        initial_masking_db: Masking amount at offset (dB).

    Returns:
        Remaining masking threshold above quiet threshold (dB).
    """
    if time_after_offset_ms < 0.0:
        return initial_masking_db
    return initial_masking_db * exp(-time_after_offset_ms / 20.0)


fn binaural_masking_level_diff(
    monaural_threshold: Float64, binaural_advantage_db: Float64
) -> Float64:
    """Binaural masking level difference improvement.

    BMLD threshold = monaural_threshold - binaural_advantage

    Args:
        monaural_threshold: Masked threshold with identical signals (dB SPL).
        binaural_advantage_db: BMLD improvement (typically 0–15 dB).

    Returns:
        Binaural masked threshold (dB SPL).
    """
    return monaural_threshold - binaural_advantage_db
