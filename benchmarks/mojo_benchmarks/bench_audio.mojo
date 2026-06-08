"""bench_audio.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from audio import amplitude_to_db, db_to_amplitude, frequency_to_midi, midi_to_frequency, generate_sine, rms_amplitude, zero_crossing_rate, envelope, normalize_audio, mix_signals
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_amplitude_to_db = amplitude_to_db(0.5, 0.5)
    var _summary_amplitude_to_db = _summary_float64(_result_amplitude_to_db)
    print("MOJO_RESULT audio::amplitude_to_db", _summary_amplitude_to_db)
    var _acc_db_to_amplitude: Float64 = 0.0
    var _t0_db_to_amplitude = perf_counter_ns()
    for _ in range(N):
        _acc_db_to_amplitude += db_to_amplitude(0.5, 0.5)
    var _t1_db_to_amplitude = perf_counter_ns()
    var _ns_db_to_amplitude = Float64(_t1_db_to_amplitude - _t0_db_to_amplitude) / Float64(N)
    print("MOJO_TIMING audio::db_to_amplitude", _ns_db_to_amplitude, _acc_db_to_amplitude)
    var _result_db_to_amplitude = db_to_amplitude(0.5, 0.5)
    var _summary_db_to_amplitude = _summary_float64(_result_db_to_amplitude)
    print("MOJO_RESULT audio::db_to_amplitude", _summary_db_to_amplitude)
    var _acc_frequency_to_midi: Float64 = 0.0
    var _t0_frequency_to_midi = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_to_midi += frequency_to_midi(0.5)
    var _t1_frequency_to_midi = perf_counter_ns()
    var _ns_frequency_to_midi = Float64(_t1_frequency_to_midi - _t0_frequency_to_midi) / Float64(N)
    print("MOJO_TIMING audio::frequency_to_midi", _ns_frequency_to_midi, _acc_frequency_to_midi)
    var _result_frequency_to_midi = frequency_to_midi(0.5)
    var _summary_frequency_to_midi = _summary_float64(_result_frequency_to_midi)
    print("MOJO_RESULT audio::frequency_to_midi", _summary_frequency_to_midi)
    var _acc_midi_to_frequency: Float64 = 0.0
    var _t0_midi_to_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_midi_to_frequency += midi_to_frequency(0.5)
    var _t1_midi_to_frequency = perf_counter_ns()
    var _ns_midi_to_frequency = Float64(_t1_midi_to_frequency - _t0_midi_to_frequency) / Float64(N)
    print("MOJO_TIMING audio::midi_to_frequency", _ns_midi_to_frequency, _acc_midi_to_frequency)
    var _result_midi_to_frequency = midi_to_frequency(0.5)
    var _summary_midi_to_frequency = _summary_float64(_result_midi_to_frequency)
    print("MOJO_RESULT audio::midi_to_frequency", _summary_midi_to_frequency)
    var _acc_generate_sine: Float64 = 0.0
    var _t0_generate_sine = perf_counter_ns()
    for _ in range(N):
        var _r_generate_sine = generate_sine(0.5, 0.5, 5)
        _acc_generate_sine += Float64(len(_r_generate_sine))
    var _t1_generate_sine = perf_counter_ns()
    var _ns_generate_sine = Float64(_t1_generate_sine - _t0_generate_sine) / Float64(N)
    print("MOJO_TIMING audio::generate_sine", _ns_generate_sine, _acc_generate_sine)
    var _result_generate_sine = generate_sine(0.5, 0.5, 5)
    var _summary_generate_sine = _summary_list_float64(_result_generate_sine)
    print("MOJO_RESULT audio::generate_sine", _summary_generate_sine)
    var _acc_rms_amplitude: Float64 = 0.0
    var _t0_rms_amplitude = perf_counter_ns()
    for _ in range(N):
        _acc_rms_amplitude += rms_amplitude(_lf5)
    var _t1_rms_amplitude = perf_counter_ns()
    var _ns_rms_amplitude = Float64(_t1_rms_amplitude - _t0_rms_amplitude) / Float64(N)
    print("MOJO_TIMING audio::rms_amplitude", _ns_rms_amplitude, _acc_rms_amplitude)
    var _result_rms_amplitude = rms_amplitude(_lf5)
    var _summary_rms_amplitude = _summary_float64(_result_rms_amplitude)
    print("MOJO_RESULT audio::rms_amplitude", _summary_rms_amplitude)
    var _acc_zero_crossing_rate: Float64 = 0.0
    var _t0_zero_crossing_rate = perf_counter_ns()
    for _ in range(N):
        _acc_zero_crossing_rate += zero_crossing_rate(_lf5)
    var _t1_zero_crossing_rate = perf_counter_ns()
    var _ns_zero_crossing_rate = Float64(_t1_zero_crossing_rate - _t0_zero_crossing_rate) / Float64(N)
    print("MOJO_TIMING audio::zero_crossing_rate", _ns_zero_crossing_rate, _acc_zero_crossing_rate)
    var _result_zero_crossing_rate = zero_crossing_rate(_lf5)
    var _summary_zero_crossing_rate = _summary_float64(_result_zero_crossing_rate)
    print("MOJO_RESULT audio::zero_crossing_rate", _summary_zero_crossing_rate)
    var _acc_envelope: Float64 = 0.0
    var _t0_envelope = perf_counter_ns()
    for _ in range(N):
        var _r_envelope = envelope(_lf5, 5)
        _acc_envelope += Float64(len(_r_envelope))
    var _t1_envelope = perf_counter_ns()
    var _ns_envelope = Float64(_t1_envelope - _t0_envelope) / Float64(N)
    print("MOJO_TIMING audio::envelope", _ns_envelope, _acc_envelope)
    var _result_envelope = envelope(_lf5, 5)
    var _summary_envelope = _summary_list_float64(_result_envelope)
    print("MOJO_RESULT audio::envelope", _summary_envelope)
    var _acc_normalize_audio: Float64 = 0.0
    var _t0_normalize_audio = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_audio = normalize_audio(_lf5)
        _acc_normalize_audio += Float64(len(_r_normalize_audio))
    var _t1_normalize_audio = perf_counter_ns()
    var _ns_normalize_audio = Float64(_t1_normalize_audio - _t0_normalize_audio) / Float64(N)
    print("MOJO_TIMING audio::normalize_audio", _ns_normalize_audio, _acc_normalize_audio)
    var _result_normalize_audio = normalize_audio(_lf5)
    var _summary_normalize_audio = _summary_list_float64(_result_normalize_audio)
    print("MOJO_RESULT audio::normalize_audio", _summary_normalize_audio)
    var _acc_mix_signals: Float64 = 0.0
    var _t0_mix_signals = perf_counter_ns()
    for _ in range(N):
        var _r_mix_signals = mix_signals(_lf5, _lf5, 0.5)
        _acc_mix_signals += Float64(len(_r_mix_signals))
    var _t1_mix_signals = perf_counter_ns()
    var _ns_mix_signals = Float64(_t1_mix_signals - _t0_mix_signals) / Float64(N)
    print("MOJO_TIMING audio::mix_signals", _ns_mix_signals, _acc_mix_signals)
    var _result_mix_signals = mix_signals(_lf5, _lf5, 0.5)
    var _summary_mix_signals = _summary_list_float64(_result_mix_signals)
    print("MOJO_RESULT audio::mix_signals", _summary_mix_signals)
