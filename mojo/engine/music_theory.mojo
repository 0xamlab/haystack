"""
music_theory.mojo — Music Theory Computations Library. Zero Python imports.

Pure Mojo implementations for MIDI/frequency conversion, intervals in cents
and semitones, scale membership, just intonation ratios, beat frequency,
tempo/duration calculations, transposition, octave, and enharmonic checks.

Public API:
  frequency_from_midi   — MIDI note to Hz
  midi_from_frequency   — Hz to MIDI note number
  cents_between         — Interval in cents between two frequencies
  semitones_between     — Absolute semitone interval
  note_in_scale         — Check if note class is in major/minor scale
  interval_ratio_just   — Just intonation ratio for common intervals
  beat_frequency        — Beat frequency = |f1 - f2|
  tempo_to_beat_duration — Duration of one beat in seconds
  measures_duration     — Total duration of measures
  transpose_midi        — Transpose MIDI note by interval
  octave_from_midi      — MIDI octave number
  is_enharmonic         — Same pitch class (mod 12)
"""
from std.math import abs as fabs, log


# ── Constants ────────────────────────────────────────────────────────────────

comptime LN2: Float64 = 0.6931471805599453


# ── Helpers ──────────────────────────────────────────────────────────────────


fn _log2(x: Float64) -> Float64:
    """Compute log base 2 via natural log."""
    return log(x) / LN2


fn _pow2(x: Float64) -> Float64:
    """Compute 2^x using exp-like approach via repeated squaring for int part
    and log identity for fractional part."""
    # 2^x = e^(x * ln2)
    # Use Taylor series for exp
    var val = x * LN2
    var result: Float64 = 1.0
    var term: Float64 = 1.0
    for i in range(1, 30):
        term *= val / Float64(i)
        result += term
    return result


# ── frequency_from_midi ──────────────────────────────────────────────────────


fn frequency_from_midi(midi_note: Int) -> Float64:
    """Convert MIDI note number to frequency in Hz.
    Formula: 440 * 2^((n - 69) / 12)."""
    var exponent = Float64(midi_note - 69) / 12.0
    return 440.0 * _pow2(exponent)


# ── midi_from_frequency ──────────────────────────────────────────────────────


fn midi_from_frequency(freq: Float64) -> Int:
    """Convert frequency in Hz to nearest MIDI note number.
    Formula: round(69 + 12 * log2(freq / 440))."""
    if freq <= 0.0:
        return 0
    var val = 69.0 + 12.0 * _log2(freq / 440.0)
    # Round to nearest int
    if val >= 0.0:
        return Int(val + 0.5)
    else:
        return Int(val - 0.5)


# ── cents_between ────────────────────────────────────────────────────────────


fn cents_between(freq1: Float64, freq2: Float64) -> Float64:
    """Interval in cents between two frequencies.
    cents = 1200 * log2(f2 / f1)."""
    if freq1 <= 0.0 or freq2 <= 0.0:
        return 0.0
    return 1200.0 * _log2(freq2 / freq1)


# ── semitones_between ────────────────────────────────────────────────────────


fn semitones_between(midi1: Int, midi2: Int) -> Int:
    """Absolute semitone interval between two MIDI notes."""
    var diff = midi1 - midi2
    if diff < 0:
        return -diff
    return diff


# ── note_in_scale ────────────────────────────────────────────────────────────


fn note_in_scale(note_class: Int, scale_root: Int, scale_pattern_idx: Int) -> Bool:
    """Check if note class (0-11) is in major (0) or natural minor (1) scale
    rooted at scale_root (0-11).
    Major intervals: 0,2,4,5,7,9,11
    Minor intervals: 0,2,3,5,7,8,10"""
    var offset = (note_class - scale_root + 12) % 12
    if scale_pattern_idx == 0:
        # Major scale
        return (offset == 0 or offset == 2 or offset == 4 or offset == 5
                or offset == 7 or offset == 9 or offset == 11)
    else:
        # Natural minor scale
        return (offset == 0 or offset == 2 or offset == 3 or offset == 5
                or offset == 7 or offset == 8 or offset == 10)


# ── interval_ratio_just ──────────────────────────────────────────────────────


fn interval_ratio_just(semitones: Int) -> Float64:
    """Just intonation frequency ratio for common intervals (0-12 semitones).
    Returns the ratio. For non-standard intervals, falls back to equal temp."""
    # Common just ratios
    if semitones == 0:
        return 1.0          # unison
    elif semitones == 1:
        return 16.0 / 15.0  # minor second
    elif semitones == 2:
        return 9.0 / 8.0    # major second
    elif semitones == 3:
        return 6.0 / 5.0    # minor third
    elif semitones == 4:
        return 5.0 / 4.0    # major third
    elif semitones == 5:
        return 4.0 / 3.0    # perfect fourth
    elif semitones == 6:
        return 45.0 / 32.0  # tritone (augmented fourth)
    elif semitones == 7:
        return 3.0 / 2.0    # perfect fifth
    elif semitones == 8:
        return 8.0 / 5.0    # minor sixth
    elif semitones == 9:
        return 5.0 / 3.0    # major sixth
    elif semitones == 10:
        return 9.0 / 5.0    # minor seventh
    elif semitones == 11:
        return 15.0 / 8.0   # major seventh
    elif semitones == 12:
        return 2.0           # octave
    # Fallback: equal temperament
    return _pow2(Float64(semitones) / 12.0)


# ── beat_frequency ───────────────────────────────────────────────────────────


fn beat_frequency(freq1: Float64, freq2: Float64) -> Float64:
    """Beat frequency = |f1 - f2|."""
    return fabs(freq1 - freq2)


# ── tempo_to_beat_duration ───────────────────────────────────────────────────


fn tempo_to_beat_duration(bpm: Float64) -> Float64:
    """Duration of one beat in seconds given tempo in BPM."""
    if bpm <= 0.0:
        return 0.0
    return 60.0 / bpm


# ── measures_duration ────────────────────────────────────────────────────────


fn measures_duration(bpm: Float64, beats_per_measure: Int, num_measures: Int) -> Float64:
    """Total duration in seconds for num_measures at given tempo and time sig."""
    if bpm <= 0.0:
        return 0.0
    var beat_dur = 60.0 / bpm
    return beat_dur * Float64(beats_per_measure) * Float64(num_measures)


# ── transpose_midi ───────────────────────────────────────────────────────────


fn transpose_midi(midi_note: Int, semitones: Int) -> Int:
    """Transpose MIDI note by given number of semitones."""
    return midi_note + semitones


# ── octave_from_midi ─────────────────────────────────────────────────────────


fn octave_from_midi(midi_note: Int) -> Int:
    """MIDI octave number. MIDI note 0 = C-1, 60 = C4."""
    return (midi_note // 12) - 1


# ── is_enharmonic ────────────────────────────────────────────────────────────


fn is_enharmonic(midi1: Int, midi2: Int) -> Bool:
    """Check if two MIDI notes are enharmonic (same pitch class, mod 12)."""
    return (midi1 % 12) == (midi2 % 12)
