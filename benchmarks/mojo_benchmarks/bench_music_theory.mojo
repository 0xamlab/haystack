"""bench_music_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from music_theory import frequency_from_midi, midi_from_frequency, cents_between, semitones_between, note_in_scale, interval_ratio_just, beat_frequency, tempo_to_beat_duration, measures_duration, transpose_midi, octave_from_midi, is_enharmonic
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

    var _acc_frequency_from_midi: Float64 = 0.0
    var _t0_frequency_from_midi = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_from_midi += frequency_from_midi(5)
    var _t1_frequency_from_midi = perf_counter_ns()
    var _ns_frequency_from_midi = Float64(_t1_frequency_from_midi - _t0_frequency_from_midi) / Float64(N)
    print("MOJO_TIMING music_theory::frequency_from_midi", _ns_frequency_from_midi, _acc_frequency_from_midi)
    var _acc_midi_from_frequency: Float64 = 0.0
    var _t0_midi_from_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_midi_from_frequency += Float64(midi_from_frequency(0.5))
    var _t1_midi_from_frequency = perf_counter_ns()
    var _ns_midi_from_frequency = Float64(_t1_midi_from_frequency - _t0_midi_from_frequency) / Float64(N)
    print("MOJO_TIMING music_theory::midi_from_frequency", _ns_midi_from_frequency, _acc_midi_from_frequency)
    var _acc_cents_between: Float64 = 0.0
    var _t0_cents_between = perf_counter_ns()
    for _ in range(N):
        _acc_cents_between += cents_between(0.5, 0.5)
    var _t1_cents_between = perf_counter_ns()
    var _ns_cents_between = Float64(_t1_cents_between - _t0_cents_between) / Float64(N)
    print("MOJO_TIMING music_theory::cents_between", _ns_cents_between, _acc_cents_between)
    var _acc_semitones_between: Float64 = 0.0
    var _t0_semitones_between = perf_counter_ns()
    for _ in range(N):
        _acc_semitones_between += Float64(semitones_between(5, 5))
    var _t1_semitones_between = perf_counter_ns()
    var _ns_semitones_between = Float64(_t1_semitones_between - _t0_semitones_between) / Float64(N)
    print("MOJO_TIMING music_theory::semitones_between", _ns_semitones_between, _acc_semitones_between)
    var _acc_note_in_scale: Float64 = 0.0
    var _t0_note_in_scale = perf_counter_ns()
    for _ in range(N):
        _acc_note_in_scale += Float64(note_in_scale(5, 5, 5))
    var _t1_note_in_scale = perf_counter_ns()
    var _ns_note_in_scale = Float64(_t1_note_in_scale - _t0_note_in_scale) / Float64(N)
    print("MOJO_TIMING music_theory::note_in_scale", _ns_note_in_scale, _acc_note_in_scale)
    var _acc_interval_ratio_just: Float64 = 0.0
    var _t0_interval_ratio_just = perf_counter_ns()
    for _ in range(N):
        _acc_interval_ratio_just += interval_ratio_just(5)
    var _t1_interval_ratio_just = perf_counter_ns()
    var _ns_interval_ratio_just = Float64(_t1_interval_ratio_just - _t0_interval_ratio_just) / Float64(N)
    print("MOJO_TIMING music_theory::interval_ratio_just", _ns_interval_ratio_just, _acc_interval_ratio_just)
    var _acc_beat_frequency: Float64 = 0.0
    var _t0_beat_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_beat_frequency += beat_frequency(0.5, 0.5)
    var _t1_beat_frequency = perf_counter_ns()
    var _ns_beat_frequency = Float64(_t1_beat_frequency - _t0_beat_frequency) / Float64(N)
    print("MOJO_TIMING music_theory::beat_frequency", _ns_beat_frequency, _acc_beat_frequency)
    var _acc_tempo_to_beat_duration: Float64 = 0.0
    var _t0_tempo_to_beat_duration = perf_counter_ns()
    for _ in range(N):
        _acc_tempo_to_beat_duration += tempo_to_beat_duration(0.5)
    var _t1_tempo_to_beat_duration = perf_counter_ns()
    var _ns_tempo_to_beat_duration = Float64(_t1_tempo_to_beat_duration - _t0_tempo_to_beat_duration) / Float64(N)
    print("MOJO_TIMING music_theory::tempo_to_beat_duration", _ns_tempo_to_beat_duration, _acc_tempo_to_beat_duration)
    var _acc_measures_duration: Float64 = 0.0
    var _t0_measures_duration = perf_counter_ns()
    for _ in range(N):
        _acc_measures_duration += measures_duration(0.5, 5, 5)
    var _t1_measures_duration = perf_counter_ns()
    var _ns_measures_duration = Float64(_t1_measures_duration - _t0_measures_duration) / Float64(N)
    print("MOJO_TIMING music_theory::measures_duration", _ns_measures_duration, _acc_measures_duration)
    var _acc_transpose_midi: Float64 = 0.0
    var _t0_transpose_midi = perf_counter_ns()
    for _ in range(N):
        _acc_transpose_midi += Float64(transpose_midi(5, 5))
    var _t1_transpose_midi = perf_counter_ns()
    var _ns_transpose_midi = Float64(_t1_transpose_midi - _t0_transpose_midi) / Float64(N)
    print("MOJO_TIMING music_theory::transpose_midi", _ns_transpose_midi, _acc_transpose_midi)
    var _acc_octave_from_midi: Float64 = 0.0
    var _t0_octave_from_midi = perf_counter_ns()
    for _ in range(N):
        _acc_octave_from_midi += Float64(octave_from_midi(5))
    var _t1_octave_from_midi = perf_counter_ns()
    var _ns_octave_from_midi = Float64(_t1_octave_from_midi - _t0_octave_from_midi) / Float64(N)
    print("MOJO_TIMING music_theory::octave_from_midi", _ns_octave_from_midi, _acc_octave_from_midi)
    var _acc_is_enharmonic: Float64 = 0.0
    var _t0_is_enharmonic = perf_counter_ns()
    for _ in range(N):
        _acc_is_enharmonic += Float64(is_enharmonic(5, 5))
    var _t1_is_enharmonic = perf_counter_ns()
    var _ns_is_enharmonic = Float64(_t1_is_enharmonic - _t0_is_enharmonic) / Float64(N)
    print("MOJO_TIMING music_theory::is_enharmonic", _ns_is_enharmonic, _acc_is_enharmonic)
