"""bench_audio.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from audio import amplitude_to_db, db_to_amplitude, frequency_to_midi, midi_to_frequency, generate_sine, rms_amplitude, zero_crossing_rate, envelope, normalize_audio, mix_signals
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_amplitude_to_db: Float64 = 0.0
    var _t0_amplitude_to_db = perf_counter_ns()
    for _ in range(N):
        _acc_amplitude_to_db += amplitude_to_db(0.5, 0.5)
    var _t1_amplitude_to_db = perf_counter_ns()
    var _ns_amplitude_to_db = Float64(_t1_amplitude_to_db - _t0_amplitude_to_db) / Float64(N)
    print("MOJO_TIMING audio::amplitude_to_db", _ns_amplitude_to_db, _acc_amplitude_to_db)
    var _acc_db_to_amplitude: Float64 = 0.0
    var _t0_db_to_amplitude = perf_counter_ns()
    for _ in range(N):
        _acc_db_to_amplitude += db_to_amplitude(0.5, 0.5)
    var _t1_db_to_amplitude = perf_counter_ns()
    var _ns_db_to_amplitude = Float64(_t1_db_to_amplitude - _t0_db_to_amplitude) / Float64(N)
    print("MOJO_TIMING audio::db_to_amplitude", _ns_db_to_amplitude, _acc_db_to_amplitude)
    var _acc_frequency_to_midi: Float64 = 0.0
    var _t0_frequency_to_midi = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_to_midi += frequency_to_midi(0.5)
    var _t1_frequency_to_midi = perf_counter_ns()
    var _ns_frequency_to_midi = Float64(_t1_frequency_to_midi - _t0_frequency_to_midi) / Float64(N)
    print("MOJO_TIMING audio::frequency_to_midi", _ns_frequency_to_midi, _acc_frequency_to_midi)
    var _acc_midi_to_frequency: Float64 = 0.0
    var _t0_midi_to_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_midi_to_frequency += midi_to_frequency(0.5)
    var _t1_midi_to_frequency = perf_counter_ns()
    var _ns_midi_to_frequency = Float64(_t1_midi_to_frequency - _t0_midi_to_frequency) / Float64(N)
    print("MOJO_TIMING audio::midi_to_frequency", _ns_midi_to_frequency, _acc_midi_to_frequency)
    var _acc_generate_sine: Float64 = 0.0
    var _t0_generate_sine = perf_counter_ns()
    for _ in range(N):
        var _r_generate_sine = generate_sine(0.5, 0.5, 5)
        _acc_generate_sine += Float64(len(_r_generate_sine))
    var _t1_generate_sine = perf_counter_ns()
    var _ns_generate_sine = Float64(_t1_generate_sine - _t0_generate_sine) / Float64(N)
    print("MOJO_TIMING audio::generate_sine", _ns_generate_sine, _acc_generate_sine)
    var _acc_rms_amplitude: Float64 = 0.0
    var _t0_rms_amplitude = perf_counter_ns()
    for _ in range(N):
        _acc_rms_amplitude += rms_amplitude(_lf5)
    var _t1_rms_amplitude = perf_counter_ns()
    var _ns_rms_amplitude = Float64(_t1_rms_amplitude - _t0_rms_amplitude) / Float64(N)
    print("MOJO_TIMING audio::rms_amplitude", _ns_rms_amplitude, _acc_rms_amplitude)
    var _acc_zero_crossing_rate: Float64 = 0.0
    var _t0_zero_crossing_rate = perf_counter_ns()
    for _ in range(N):
        _acc_zero_crossing_rate += zero_crossing_rate(_lf5)
    var _t1_zero_crossing_rate = perf_counter_ns()
    var _ns_zero_crossing_rate = Float64(_t1_zero_crossing_rate - _t0_zero_crossing_rate) / Float64(N)
    print("MOJO_TIMING audio::zero_crossing_rate", _ns_zero_crossing_rate, _acc_zero_crossing_rate)
    var _acc_envelope: Float64 = 0.0
    var _t0_envelope = perf_counter_ns()
    for _ in range(N):
        var _r_envelope = envelope(_lf5, 5)
        _acc_envelope += Float64(len(_r_envelope))
    var _t1_envelope = perf_counter_ns()
    var _ns_envelope = Float64(_t1_envelope - _t0_envelope) / Float64(N)
    print("MOJO_TIMING audio::envelope", _ns_envelope, _acc_envelope)
    var _acc_normalize_audio: Float64 = 0.0
    var _t0_normalize_audio = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_audio = normalize_audio(_lf5)
        _acc_normalize_audio += Float64(len(_r_normalize_audio))
    var _t1_normalize_audio = perf_counter_ns()
    var _ns_normalize_audio = Float64(_t1_normalize_audio - _t0_normalize_audio) / Float64(N)
    print("MOJO_TIMING audio::normalize_audio", _ns_normalize_audio, _acc_normalize_audio)
    var _acc_mix_signals: Float64 = 0.0
    var _t0_mix_signals = perf_counter_ns()
    for _ in range(N):
        var _r_mix_signals = mix_signals(_lf5, _lf5, 0.5)
        _acc_mix_signals += Float64(len(_r_mix_signals))
    var _t1_mix_signals = perf_counter_ns()
    var _ns_mix_signals = Float64(_t1_mix_signals - _t0_mix_signals) / Float64(N)
    print("MOJO_TIMING audio::mix_signals", _ns_mix_signals, _acc_mix_signals)
