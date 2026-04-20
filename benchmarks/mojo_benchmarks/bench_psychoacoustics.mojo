"""bench_psychoacoustics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from psychoacoustics import loudness_phon_to_sone, loudness_sone_to_phon, critical_bandwidth, bark_scale, masking_threshold, speech_intelligibility_index, equal_loudness_correction, frequency_just_noticeable, temporal_masking_decay, binaural_masking_level_diff
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

    var _acc_loudness_phon_to_sone: Float64 = 0.0
    var _t0_loudness_phon_to_sone = perf_counter_ns()
    for _ in range(N):
        _acc_loudness_phon_to_sone += loudness_phon_to_sone(0.5)
    var _t1_loudness_phon_to_sone = perf_counter_ns()
    var _ns_loudness_phon_to_sone = Float64(_t1_loudness_phon_to_sone - _t0_loudness_phon_to_sone) / Float64(N)
    print("MOJO_TIMING psychoacoustics::loudness_phon_to_sone", _ns_loudness_phon_to_sone, _acc_loudness_phon_to_sone)
    var _acc_loudness_sone_to_phon: Float64 = 0.0
    var _t0_loudness_sone_to_phon = perf_counter_ns()
    for _ in range(N):
        _acc_loudness_sone_to_phon += loudness_sone_to_phon(0.5)
    var _t1_loudness_sone_to_phon = perf_counter_ns()
    var _ns_loudness_sone_to_phon = Float64(_t1_loudness_sone_to_phon - _t0_loudness_sone_to_phon) / Float64(N)
    print("MOJO_TIMING psychoacoustics::loudness_sone_to_phon", _ns_loudness_sone_to_phon, _acc_loudness_sone_to_phon)
    var _acc_critical_bandwidth: Float64 = 0.0
    var _t0_critical_bandwidth = perf_counter_ns()
    for _ in range(N):
        _acc_critical_bandwidth += critical_bandwidth(0.5)
    var _t1_critical_bandwidth = perf_counter_ns()
    var _ns_critical_bandwidth = Float64(_t1_critical_bandwidth - _t0_critical_bandwidth) / Float64(N)
    print("MOJO_TIMING psychoacoustics::critical_bandwidth", _ns_critical_bandwidth, _acc_critical_bandwidth)
    var _acc_bark_scale: Float64 = 0.0
    var _t0_bark_scale = perf_counter_ns()
    for _ in range(N):
        _acc_bark_scale += bark_scale(0.5)
    var _t1_bark_scale = perf_counter_ns()
    var _ns_bark_scale = Float64(_t1_bark_scale - _t0_bark_scale) / Float64(N)
    print("MOJO_TIMING psychoacoustics::bark_scale", _ns_bark_scale, _acc_bark_scale)
    var _acc_masking_threshold: Float64 = 0.0
    var _t0_masking_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_masking_threshold += masking_threshold(0.5, 0.5, 0.5)
    var _t1_masking_threshold = perf_counter_ns()
    var _ns_masking_threshold = Float64(_t1_masking_threshold - _t0_masking_threshold) / Float64(N)
    print("MOJO_TIMING psychoacoustics::masking_threshold", _ns_masking_threshold, _acc_masking_threshold)
    var _acc_speech_intelligibility_index: Float64 = 0.0
    var _t0_speech_intelligibility_index = perf_counter_ns()
    for _ in range(N):
        _acc_speech_intelligibility_index += speech_intelligibility_index(0.5, 0.5, 0.5)
    var _t1_speech_intelligibility_index = perf_counter_ns()
    var _ns_speech_intelligibility_index = Float64(_t1_speech_intelligibility_index - _t0_speech_intelligibility_index) / Float64(N)
    print("MOJO_TIMING psychoacoustics::speech_intelligibility_index", _ns_speech_intelligibility_index, _acc_speech_intelligibility_index)
    var _acc_equal_loudness_correction: Float64 = 0.0
    var _t0_equal_loudness_correction = perf_counter_ns()
    for _ in range(N):
        _acc_equal_loudness_correction += equal_loudness_correction(0.5, 0.5)
    var _t1_equal_loudness_correction = perf_counter_ns()
    var _ns_equal_loudness_correction = Float64(_t1_equal_loudness_correction - _t0_equal_loudness_correction) / Float64(N)
    print("MOJO_TIMING psychoacoustics::equal_loudness_correction", _ns_equal_loudness_correction, _acc_equal_loudness_correction)
    var _acc_frequency_just_noticeable: Float64 = 0.0
    var _t0_frequency_just_noticeable = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_just_noticeable += frequency_just_noticeable(0.5, 0.5)
    var _t1_frequency_just_noticeable = perf_counter_ns()
    var _ns_frequency_just_noticeable = Float64(_t1_frequency_just_noticeable - _t0_frequency_just_noticeable) / Float64(N)
    print("MOJO_TIMING psychoacoustics::frequency_just_noticeable", _ns_frequency_just_noticeable, _acc_frequency_just_noticeable)
    var _acc_temporal_masking_decay: Float64 = 0.0
    var _t0_temporal_masking_decay = perf_counter_ns()
    for _ in range(N):
        _acc_temporal_masking_decay += temporal_masking_decay(0.5, 0.5)
    var _t1_temporal_masking_decay = perf_counter_ns()
    var _ns_temporal_masking_decay = Float64(_t1_temporal_masking_decay - _t0_temporal_masking_decay) / Float64(N)
    print("MOJO_TIMING psychoacoustics::temporal_masking_decay", _ns_temporal_masking_decay, _acc_temporal_masking_decay)
    var _acc_binaural_masking_level_diff: Float64 = 0.0
    var _t0_binaural_masking_level_diff = perf_counter_ns()
    for _ in range(N):
        _acc_binaural_masking_level_diff += binaural_masking_level_diff(0.5, 0.5)
    var _t1_binaural_masking_level_diff = perf_counter_ns()
    var _ns_binaural_masking_level_diff = Float64(_t1_binaural_masking_level_diff - _t0_binaural_masking_level_diff) / Float64(N)
    print("MOJO_TIMING psychoacoustics::binaural_masking_level_diff", _ns_binaural_masking_level_diff, _acc_binaural_masking_level_diff)
