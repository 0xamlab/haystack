"""bench_music_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from music_theory import frequency_from_midi, midi_from_frequency, cents_between, semitones_between, note_in_scale, interval_ratio_just, beat_frequency, tempo_to_beat_duration, measures_duration, transpose_midi, octave_from_midi, is_enharmonic
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

    var _acc_frequency_from_midi: Float64 = 0.0
    var _t0_frequency_from_midi = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_from_midi += frequency_from_midi(5)
    var _t1_frequency_from_midi = perf_counter_ns()
    var _ns_frequency_from_midi = Float64(_t1_frequency_from_midi - _t0_frequency_from_midi) / Float64(N)
    print("MOJO_TIMING music_theory::frequency_from_midi", _ns_frequency_from_midi, _acc_frequency_from_midi)
    var _result_frequency_from_midi = frequency_from_midi(5)
    var _summary_frequency_from_midi = _summary_float64(_result_frequency_from_midi)
    print("MOJO_RESULT music_theory::frequency_from_midi", _summary_frequency_from_midi)
    var _acc_midi_from_frequency: Float64 = 0.0
    var _t0_midi_from_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_midi_from_frequency += Float64(midi_from_frequency(0.5))
    var _t1_midi_from_frequency = perf_counter_ns()
    var _ns_midi_from_frequency = Float64(_t1_midi_from_frequency - _t0_midi_from_frequency) / Float64(N)
    print("MOJO_TIMING music_theory::midi_from_frequency", _ns_midi_from_frequency, _acc_midi_from_frequency)
    var _result_midi_from_frequency = midi_from_frequency(0.5)
    var _summary_midi_from_frequency = _summary_int(_result_midi_from_frequency)
    print("MOJO_RESULT music_theory::midi_from_frequency", _summary_midi_from_frequency)
    var _acc_cents_between: Float64 = 0.0
    var _t0_cents_between = perf_counter_ns()
    for _ in range(N):
        _acc_cents_between += cents_between(0.5, 0.5)
    var _t1_cents_between = perf_counter_ns()
    var _ns_cents_between = Float64(_t1_cents_between - _t0_cents_between) / Float64(N)
    print("MOJO_TIMING music_theory::cents_between", _ns_cents_between, _acc_cents_between)
    var _result_cents_between = cents_between(0.5, 0.5)
    var _summary_cents_between = _summary_float64(_result_cents_between)
    print("MOJO_RESULT music_theory::cents_between", _summary_cents_between)
    var _acc_semitones_between: Float64 = 0.0
    var _t0_semitones_between = perf_counter_ns()
    for _ in range(N):
        _acc_semitones_between += Float64(semitones_between(5, 5))
    var _t1_semitones_between = perf_counter_ns()
    var _ns_semitones_between = Float64(_t1_semitones_between - _t0_semitones_between) / Float64(N)
    print("MOJO_TIMING music_theory::semitones_between", _ns_semitones_between, _acc_semitones_between)
    var _result_semitones_between = semitones_between(5, 5)
    var _summary_semitones_between = _summary_int(_result_semitones_between)
    print("MOJO_RESULT music_theory::semitones_between", _summary_semitones_between)
    var _acc_note_in_scale: Float64 = 0.0
    var _t0_note_in_scale = perf_counter_ns()
    for _ in range(N):
        _acc_note_in_scale += Float64(note_in_scale(5, 5, 5))
    var _t1_note_in_scale = perf_counter_ns()
    var _ns_note_in_scale = Float64(_t1_note_in_scale - _t0_note_in_scale) / Float64(N)
    print("MOJO_TIMING music_theory::note_in_scale", _ns_note_in_scale, _acc_note_in_scale)
    var _result_note_in_scale = note_in_scale(5, 5, 5)
    var _summary_note_in_scale = _summary_bool(_result_note_in_scale)
    print("MOJO_RESULT music_theory::note_in_scale", _summary_note_in_scale)
    var _acc_interval_ratio_just: Float64 = 0.0
    var _t0_interval_ratio_just = perf_counter_ns()
    for _ in range(N):
        _acc_interval_ratio_just += interval_ratio_just(5)
    var _t1_interval_ratio_just = perf_counter_ns()
    var _ns_interval_ratio_just = Float64(_t1_interval_ratio_just - _t0_interval_ratio_just) / Float64(N)
    print("MOJO_TIMING music_theory::interval_ratio_just", _ns_interval_ratio_just, _acc_interval_ratio_just)
    var _result_interval_ratio_just = interval_ratio_just(5)
    var _summary_interval_ratio_just = _summary_float64(_result_interval_ratio_just)
    print("MOJO_RESULT music_theory::interval_ratio_just", _summary_interval_ratio_just)
    var _acc_beat_frequency: Float64 = 0.0
    var _t0_beat_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_beat_frequency += beat_frequency(0.5, 0.5)
    var _t1_beat_frequency = perf_counter_ns()
    var _ns_beat_frequency = Float64(_t1_beat_frequency - _t0_beat_frequency) / Float64(N)
    print("MOJO_TIMING music_theory::beat_frequency", _ns_beat_frequency, _acc_beat_frequency)
    var _result_beat_frequency = beat_frequency(0.5, 0.5)
    var _summary_beat_frequency = _summary_float64(_result_beat_frequency)
    print("MOJO_RESULT music_theory::beat_frequency", _summary_beat_frequency)
    var _acc_tempo_to_beat_duration: Float64 = 0.0
    var _t0_tempo_to_beat_duration = perf_counter_ns()
    for _ in range(N):
        _acc_tempo_to_beat_duration += tempo_to_beat_duration(0.5)
    var _t1_tempo_to_beat_duration = perf_counter_ns()
    var _ns_tempo_to_beat_duration = Float64(_t1_tempo_to_beat_duration - _t0_tempo_to_beat_duration) / Float64(N)
    print("MOJO_TIMING music_theory::tempo_to_beat_duration", _ns_tempo_to_beat_duration, _acc_tempo_to_beat_duration)
    var _result_tempo_to_beat_duration = tempo_to_beat_duration(0.5)
    var _summary_tempo_to_beat_duration = _summary_float64(_result_tempo_to_beat_duration)
    print("MOJO_RESULT music_theory::tempo_to_beat_duration", _summary_tempo_to_beat_duration)
    var _acc_measures_duration: Float64 = 0.0
    var _t0_measures_duration = perf_counter_ns()
    for _ in range(N):
        _acc_measures_duration += measures_duration(0.5, 5, 5)
    var _t1_measures_duration = perf_counter_ns()
    var _ns_measures_duration = Float64(_t1_measures_duration - _t0_measures_duration) / Float64(N)
    print("MOJO_TIMING music_theory::measures_duration", _ns_measures_duration, _acc_measures_duration)
    var _result_measures_duration = measures_duration(0.5, 5, 5)
    var _summary_measures_duration = _summary_float64(_result_measures_duration)
    print("MOJO_RESULT music_theory::measures_duration", _summary_measures_duration)
    var _acc_transpose_midi: Float64 = 0.0
    var _t0_transpose_midi = perf_counter_ns()
    for _ in range(N):
        _acc_transpose_midi += Float64(transpose_midi(5, 5))
    var _t1_transpose_midi = perf_counter_ns()
    var _ns_transpose_midi = Float64(_t1_transpose_midi - _t0_transpose_midi) / Float64(N)
    print("MOJO_TIMING music_theory::transpose_midi", _ns_transpose_midi, _acc_transpose_midi)
    var _result_transpose_midi = transpose_midi(5, 5)
    var _summary_transpose_midi = _summary_int(_result_transpose_midi)
    print("MOJO_RESULT music_theory::transpose_midi", _summary_transpose_midi)
    var _acc_octave_from_midi: Float64 = 0.0
    var _t0_octave_from_midi = perf_counter_ns()
    for _ in range(N):
        _acc_octave_from_midi += Float64(octave_from_midi(5))
    var _t1_octave_from_midi = perf_counter_ns()
    var _ns_octave_from_midi = Float64(_t1_octave_from_midi - _t0_octave_from_midi) / Float64(N)
    print("MOJO_TIMING music_theory::octave_from_midi", _ns_octave_from_midi, _acc_octave_from_midi)
    var _result_octave_from_midi = octave_from_midi(5)
    var _summary_octave_from_midi = _summary_int(_result_octave_from_midi)
    print("MOJO_RESULT music_theory::octave_from_midi", _summary_octave_from_midi)
    var _acc_is_enharmonic: Float64 = 0.0
    var _t0_is_enharmonic = perf_counter_ns()
    for _ in range(N):
        _acc_is_enharmonic += Float64(is_enharmonic(5, 5))
    var _t1_is_enharmonic = perf_counter_ns()
    var _ns_is_enharmonic = Float64(_t1_is_enharmonic - _t0_is_enharmonic) / Float64(N)
    print("MOJO_TIMING music_theory::is_enharmonic", _ns_is_enharmonic, _acc_is_enharmonic)
    var _result_is_enharmonic = is_enharmonic(5, 5)
    var _summary_is_enharmonic = _summary_bool(_result_is_enharmonic)
    print("MOJO_RESULT music_theory::is_enharmonic", _summary_is_enharmonic)
