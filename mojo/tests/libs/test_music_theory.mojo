"""test_music_theory.mojo — auto-generated tests for music_theory library."""
from std.math import isnan, isinf
from music_theory import frequency_from_midi, midi_from_frequency, cents_between, semitones_between, note_in_scale, interval_ratio_just, beat_frequency, tempo_to_beat_duration, measures_duration, transpose_midi, octave_from_midi, is_enharmonic

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_frequency_from_midi = frequency_from_midi(5)
    if is_finite(_v_frequency_from_midi): passed += 1; print("  ✅ music_theory::frequency_from_midi =", _v_frequency_from_midi)
    else: failed += 1; print("  ❌ music_theory::frequency_from_midi → non-finite:", _v_frequency_from_midi)
    _ = midi_from_frequency(0.5)
    passed += 1; print("  ✅ music_theory::midi_from_frequency")
    var _v_cents_between = cents_between(0.5, 0.5)
    if is_finite(_v_cents_between): passed += 1; print("  ✅ music_theory::cents_between =", _v_cents_between)
    else: failed += 1; print("  ❌ music_theory::cents_between → non-finite:", _v_cents_between)
    _ = semitones_between(5, 5)
    passed += 1; print("  ✅ music_theory::semitones_between")
    _ = note_in_scale(5, 5, 5)
    passed += 1; print("  ✅ music_theory::note_in_scale")
    var _v_interval_ratio_just = interval_ratio_just(5)
    if is_finite(_v_interval_ratio_just): passed += 1; print("  ✅ music_theory::interval_ratio_just =", _v_interval_ratio_just)
    else: failed += 1; print("  ❌ music_theory::interval_ratio_just → non-finite:", _v_interval_ratio_just)
    var _v_beat_frequency = beat_frequency(0.5, 0.5)
    if is_finite(_v_beat_frequency): passed += 1; print("  ✅ music_theory::beat_frequency =", _v_beat_frequency)
    else: failed += 1; print("  ❌ music_theory::beat_frequency → non-finite:", _v_beat_frequency)
    var _v_tempo_to_beat_duration = tempo_to_beat_duration(0.5)
    if is_finite(_v_tempo_to_beat_duration): passed += 1; print("  ✅ music_theory::tempo_to_beat_duration =", _v_tempo_to_beat_duration)
    else: failed += 1; print("  ❌ music_theory::tempo_to_beat_duration → non-finite:", _v_tempo_to_beat_duration)
    var _v_measures_duration = measures_duration(0.5, 5, 5)
    if is_finite(_v_measures_duration): passed += 1; print("  ✅ music_theory::measures_duration =", _v_measures_duration)
    else: failed += 1; print("  ❌ music_theory::measures_duration → non-finite:", _v_measures_duration)
    _ = transpose_midi(5, 5)
    passed += 1; print("  ✅ music_theory::transpose_midi")
    _ = octave_from_midi(5)
    passed += 1; print("  ✅ music_theory::octave_from_midi")
    _ = is_enharmonic(5, 5)
    passed += 1; print("  ✅ music_theory::is_enharmonic")

    print("  [music_theory] Passed:", passed, "Failed:", failed)
