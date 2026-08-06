"""
audio.mojo — Audio processing primitives. Zero Python imports.

Replaces librosa basics for the decision engine with pure Mojo
implementations of amplitude/dB conversion, MIDI/frequency mapping,
sine wave generation, RMS, zero-crossing rate, envelope extraction,
normalization, and signal mixing.

Public API:
  amplitude_to_db   — 20 * log10(amplitude / ref)
  db_to_amplitude   — ref * 10^(db/20)
  frequency_to_midi  — 69 + 12 * log2(freq / 440)
  midi_to_frequency  — 440 * 2^((midi - 69) / 12)
  generate_sine      — generate sine wave samples
  rms_amplitude      — sqrt(mean(x²))
  zero_crossing_rate — fraction of sign changes
  envelope           — running max absolute value (amplitude envelope)
  normalize_audio    — scale to [-1, 1] range
  mix_signals        — weighted mix of two signals
"""
from std.math import sin, sqrt, log, pow, abs as fabs


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime LN10: Float64 = 2.302585092994046
comptime LN2: Float64 = 0.6931471805599453
comptime LOG10_E: Float64 = 0.4342944819032518   # 1/ln(10)
comptime LOG2_E: Float64 = 1.4426950408889634     # 1/ln(2)


# ── _log10 / _log2 helpers ───────────────────────────────────────────────────


def _log10(x: Float64) -> Float64:
    """Compute log base 10 via natural log."""
    return log(x) * LOG10_E


def _log2(x: Float64) -> Float64:
    """Compute log base 2 via natural log."""
    return log(x) * LOG2_E


# ── amplitude_to_db ──────────────────────────────────────────────────────────


def amplitude_to_db(amplitude: Float64, reference: Float64 = 1.0) -> Float64:
    """Convert amplitude ratio to decibels: 20 * log10(amplitude / reference)."""
    if amplitude <= 0.0 or reference <= 0.0:
        return -200.0  # floor value for silence
    return 20.0 * _log10(amplitude / reference)


# ── db_to_amplitude ──────────────────────────────────────────────────────────


def db_to_amplitude(db: Float64, reference: Float64 = 1.0) -> Float64:
    """Convert decibels to amplitude ratio: reference * 10^(db/20)."""
    return reference * pow(10.0, db / 20.0)


# ── frequency_to_midi ────────────────────────────────────────────────────────


def frequency_to_midi(freq: Float64) -> Float64:
    """Convert frequency (Hz) to MIDI note number: 69 + 12*log2(freq/440)."""
    if freq <= 0.0:
        return 0.0
    return 69.0 + 12.0 * _log2(freq / 440.0)


# ── midi_to_frequency ────────────────────────────────────────────────────────


def midi_to_frequency(midi: Float64) -> Float64:
    """Convert MIDI note number to frequency (Hz): 440 * 2^((midi-69)/12)."""
    return 440.0 * pow(2.0, (midi - 69.0) / 12.0)


# ── generate_sine ────────────────────────────────────────────────────────────


def generate_sine(freq: Float64, sample_rate: Float64, n_samples: Int) -> List[Float64]:
    """Generate n_samples of a sine wave at the given frequency and sample rate."""
    var result = List[Float64]()
    if n_samples <= 0 or sample_rate <= 0.0:
        return result^
    var omega = 2.0 * PI * freq / sample_rate
    for i in range(n_samples):
        result.append(sin(omega * Float64(i)))
    return result^


# ── rms_amplitude ────────────────────────────────────────────────────────────


def rms_amplitude(samples: List[Float64]) -> Float64:
    """Root mean square amplitude: sqrt(mean(x²))."""
    var n = len(samples)
    if n == 0:
        return 0.0
    var sum_sq: Float64 = 0.0
    for i in range(n):
        sum_sq += samples[i] * samples[i]
    return sqrt(sum_sq / Float64(n))


# ── zero_crossing_rate ───────────────────────────────────────────────────────


def zero_crossing_rate(samples: List[Float64]) -> Float64:
    """Fraction of adjacent sample pairs that have a sign change."""
    var n = len(samples)
    if n < 2:
        return 0.0
    var crossings: Int = 0
    for i in range(1, n):
        var prev_pos = samples[i - 1] >= 0.0
        var curr_pos = samples[i] >= 0.0
        if prev_pos != curr_pos:
            crossings += 1
    return Float64(crossings) / Float64(n - 1)


# ── envelope ─────────────────────────────────────────────────────────────────


def envelope(samples: List[Float64], window: Int) -> List[Float64]:
    """Amplitude envelope: running max absolute value over a window."""
    var n = len(samples)
    var result = List[Float64]()
    if n == 0 or window <= 0:
        return result^
    var hw = window // 2
    for i in range(n):
        var lo = i - hw
        var hi = i + hw
        if lo < 0:
            lo = 0
        if hi >= n:
            hi = n - 1
        var max_val: Float64 = 0.0
        for j in range(lo, hi + 1):
            var av = fabs(samples[j])
            if av > max_val:
                max_val = av
        result.append(max_val)
    return result^


# ── normalize_audio ──────────────────────────────────────────────────────────


def normalize_audio(samples: List[Float64]) -> List[Float64]:
    """Scale signal to [-1, 1] range based on peak absolute value."""
    var n = len(samples)
    var result = List[Float64]()
    if n == 0:
        return result^
    var peak: Float64 = 0.0
    for i in range(n):
        var av = fabs(samples[i])
        if av > peak:
            peak = av
    if peak == 0.0:
        for i in range(n):
            result.append(0.0)
        return result^
    for i in range(n):
        result.append(samples[i] / peak)
    return result^


# ── mix_signals ──────────────────────────────────────────────────────────────


def mix_signals(a: List[Float64], b: List[Float64], weight_a: Float64 = 0.5) -> List[Float64]:
    """Weighted mix of two signals: weight_a * a + (1 - weight_a) * b.
    Output length is the minimum of the two input lengths."""
    var na = len(a)
    var nb = len(b)
    var n = na
    if nb < n:
        n = nb
    var result = List[Float64]()
    var wb = 1.0 - weight_a
    for i in range(n):
        result.append(weight_a * a[i] + wb * b[i])
    return result^
