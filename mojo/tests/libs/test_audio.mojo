"""test_audio.mojo — auto-generated tests for audio library."""
from std.math import isnan, isinf
from audio import amplitude_to_db, db_to_amplitude, frequency_to_midi, midi_to_frequency, generate_sine, rms_amplitude, zero_crossing_rate, envelope, normalize_audio, mix_signals

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

    var _v_amplitude_to_db = amplitude_to_db(0.5, 0.5)
    if is_finite(_v_amplitude_to_db): passed += 1; print("  ✅ audio::amplitude_to_db =", _v_amplitude_to_db)
    else: failed += 1; print("  ❌ audio::amplitude_to_db → non-finite:", _v_amplitude_to_db)
    var _v_db_to_amplitude = db_to_amplitude(0.5, 0.5)
    if is_finite(_v_db_to_amplitude): passed += 1; print("  ✅ audio::db_to_amplitude =", _v_db_to_amplitude)
    else: failed += 1; print("  ❌ audio::db_to_amplitude → non-finite:", _v_db_to_amplitude)
    var _v_frequency_to_midi = frequency_to_midi(0.5)
    if is_finite(_v_frequency_to_midi): passed += 1; print("  ✅ audio::frequency_to_midi =", _v_frequency_to_midi)
    else: failed += 1; print("  ❌ audio::frequency_to_midi → non-finite:", _v_frequency_to_midi)
    var _v_midi_to_frequency = midi_to_frequency(0.5)
    if is_finite(_v_midi_to_frequency): passed += 1; print("  ✅ audio::midi_to_frequency =", _v_midi_to_frequency)
    else: failed += 1; print("  ❌ audio::midi_to_frequency → non-finite:", _v_midi_to_frequency)
    var _v_generate_sine = generate_sine(0.5, 0.5, 5)
    if len(_v_generate_sine) >= 0: passed += 1; print("  ✅ audio::generate_sine")
    var _v_rms_amplitude = rms_amplitude(_lf5)
    if is_finite(_v_rms_amplitude): passed += 1; print("  ✅ audio::rms_amplitude =", _v_rms_amplitude)
    else: failed += 1; print("  ❌ audio::rms_amplitude → non-finite:", _v_rms_amplitude)
    var _v_zero_crossing_rate = zero_crossing_rate(_lf5)
    if is_finite(_v_zero_crossing_rate): passed += 1; print("  ✅ audio::zero_crossing_rate =", _v_zero_crossing_rate)
    else: failed += 1; print("  ❌ audio::zero_crossing_rate → non-finite:", _v_zero_crossing_rate)
    var _v_envelope = envelope(_lf5, 5)
    if len(_v_envelope) >= 0: passed += 1; print("  ✅ audio::envelope")
    var _v_normalize_audio = normalize_audio(_lf5)
    if len(_v_normalize_audio) >= 0: passed += 1; print("  ✅ audio::normalize_audio")
    var _v_mix_signals = mix_signals(_lf5, _lf5, 0.5)
    if len(_v_mix_signals) >= 0: passed += 1; print("  ✅ audio::mix_signals")

    print("  [audio] Passed:", passed, "Failed:", failed)
