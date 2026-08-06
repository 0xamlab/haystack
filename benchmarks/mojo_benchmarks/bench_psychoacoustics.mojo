"""bench_psychoacoustics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from psychoacoustics import loudness_phon_to_sone, loudness_sone_to_phon, critical_bandwidth, bark_scale, masking_threshold, speech_intelligibility_index, equal_loudness_correction, frequency_just_noticeable, temporal_masking_decay, binaural_masking_level_diff
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_loudness_phon_to_sone: Float64 = 0.0
    var _t0_loudness_phon_to_sone = perf_counter_ns()
    for _ in range(N):
        _acc_loudness_phon_to_sone += loudness_phon_to_sone(0.5)
    var _t1_loudness_phon_to_sone = perf_counter_ns()
    var _ns_loudness_phon_to_sone = Float64(_t1_loudness_phon_to_sone - _t0_loudness_phon_to_sone) / Float64(N)
    print("MOJO_TIMING psychoacoustics::loudness_phon_to_sone", _ns_loudness_phon_to_sone, _acc_loudness_phon_to_sone)
    var _result_loudness_phon_to_sone = loudness_phon_to_sone(0.5)
    var _summary_loudness_phon_to_sone = _summary_float64(_result_loudness_phon_to_sone)
    print("MOJO_RESULT psychoacoustics::loudness_phon_to_sone", _summary_loudness_phon_to_sone)
    var _acc_loudness_sone_to_phon: Float64 = 0.0
    var _t0_loudness_sone_to_phon = perf_counter_ns()
    for _ in range(N):
        _acc_loudness_sone_to_phon += loudness_sone_to_phon(0.5)
    var _t1_loudness_sone_to_phon = perf_counter_ns()
    var _ns_loudness_sone_to_phon = Float64(_t1_loudness_sone_to_phon - _t0_loudness_sone_to_phon) / Float64(N)
    print("MOJO_TIMING psychoacoustics::loudness_sone_to_phon", _ns_loudness_sone_to_phon, _acc_loudness_sone_to_phon)
    var _result_loudness_sone_to_phon = loudness_sone_to_phon(0.5)
    var _summary_loudness_sone_to_phon = _summary_float64(_result_loudness_sone_to_phon)
    print("MOJO_RESULT psychoacoustics::loudness_sone_to_phon", _summary_loudness_sone_to_phon)
    var _acc_critical_bandwidth: Float64 = 0.0
    var _t0_critical_bandwidth = perf_counter_ns()
    for _ in range(N):
        _acc_critical_bandwidth += critical_bandwidth(0.5)
    var _t1_critical_bandwidth = perf_counter_ns()
    var _ns_critical_bandwidth = Float64(_t1_critical_bandwidth - _t0_critical_bandwidth) / Float64(N)
    print("MOJO_TIMING psychoacoustics::critical_bandwidth", _ns_critical_bandwidth, _acc_critical_bandwidth)
    var _result_critical_bandwidth = critical_bandwidth(0.5)
    var _summary_critical_bandwidth = _summary_float64(_result_critical_bandwidth)
    print("MOJO_RESULT psychoacoustics::critical_bandwidth", _summary_critical_bandwidth)
    var _acc_bark_scale: Float64 = 0.0
    var _t0_bark_scale = perf_counter_ns()
    for _ in range(N):
        _acc_bark_scale += bark_scale(0.5)
    var _t1_bark_scale = perf_counter_ns()
    var _ns_bark_scale = Float64(_t1_bark_scale - _t0_bark_scale) / Float64(N)
    print("MOJO_TIMING psychoacoustics::bark_scale", _ns_bark_scale, _acc_bark_scale)
    var _result_bark_scale = bark_scale(0.5)
    var _summary_bark_scale = _summary_float64(_result_bark_scale)
    print("MOJO_RESULT psychoacoustics::bark_scale", _summary_bark_scale)
    var _acc_masking_threshold: Float64 = 0.0
    var _t0_masking_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_masking_threshold += masking_threshold(0.5, 0.5, 0.5)
    var _t1_masking_threshold = perf_counter_ns()
    var _ns_masking_threshold = Float64(_t1_masking_threshold - _t0_masking_threshold) / Float64(N)
    print("MOJO_TIMING psychoacoustics::masking_threshold", _ns_masking_threshold, _acc_masking_threshold)
    var _result_masking_threshold = masking_threshold(0.5, 0.5, 0.5)
    var _summary_masking_threshold = _summary_float64(_result_masking_threshold)
    print("MOJO_RESULT psychoacoustics::masking_threshold", _summary_masking_threshold)
    var _acc_speech_intelligibility_index: Float64 = 0.0
    var _t0_speech_intelligibility_index = perf_counter_ns()
    for _ in range(N):
        _acc_speech_intelligibility_index += speech_intelligibility_index(0.5, 0.5, 0.5)
    var _t1_speech_intelligibility_index = perf_counter_ns()
    var _ns_speech_intelligibility_index = Float64(_t1_speech_intelligibility_index - _t0_speech_intelligibility_index) / Float64(N)
    print("MOJO_TIMING psychoacoustics::speech_intelligibility_index", _ns_speech_intelligibility_index, _acc_speech_intelligibility_index)
    var _result_speech_intelligibility_index = speech_intelligibility_index(0.5, 0.5, 0.5)
    var _summary_speech_intelligibility_index = _summary_float64(_result_speech_intelligibility_index)
    print("MOJO_RESULT psychoacoustics::speech_intelligibility_index", _summary_speech_intelligibility_index)
    var _acc_equal_loudness_correction: Float64 = 0.0
    var _t0_equal_loudness_correction = perf_counter_ns()
    for _ in range(N):
        _acc_equal_loudness_correction += equal_loudness_correction(0.5, 0.5)
    var _t1_equal_loudness_correction = perf_counter_ns()
    var _ns_equal_loudness_correction = Float64(_t1_equal_loudness_correction - _t0_equal_loudness_correction) / Float64(N)
    print("MOJO_TIMING psychoacoustics::equal_loudness_correction", _ns_equal_loudness_correction, _acc_equal_loudness_correction)
    var _result_equal_loudness_correction = equal_loudness_correction(0.5, 0.5)
    var _summary_equal_loudness_correction = _summary_float64(_result_equal_loudness_correction)
    print("MOJO_RESULT psychoacoustics::equal_loudness_correction", _summary_equal_loudness_correction)
    var _acc_frequency_just_noticeable: Float64 = 0.0
    var _t0_frequency_just_noticeable = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_just_noticeable += frequency_just_noticeable(0.5, 0.5)
    var _t1_frequency_just_noticeable = perf_counter_ns()
    var _ns_frequency_just_noticeable = Float64(_t1_frequency_just_noticeable - _t0_frequency_just_noticeable) / Float64(N)
    print("MOJO_TIMING psychoacoustics::frequency_just_noticeable", _ns_frequency_just_noticeable, _acc_frequency_just_noticeable)
    var _result_frequency_just_noticeable = frequency_just_noticeable(0.5, 0.5)
    var _summary_frequency_just_noticeable = _summary_float64(_result_frequency_just_noticeable)
    print("MOJO_RESULT psychoacoustics::frequency_just_noticeable", _summary_frequency_just_noticeable)
    var _acc_temporal_masking_decay: Float64 = 0.0
    var _t0_temporal_masking_decay = perf_counter_ns()
    for _ in range(N):
        _acc_temporal_masking_decay += temporal_masking_decay(0.5, 0.5)
    var _t1_temporal_masking_decay = perf_counter_ns()
    var _ns_temporal_masking_decay = Float64(_t1_temporal_masking_decay - _t0_temporal_masking_decay) / Float64(N)
    print("MOJO_TIMING psychoacoustics::temporal_masking_decay", _ns_temporal_masking_decay, _acc_temporal_masking_decay)
    var _result_temporal_masking_decay = temporal_masking_decay(0.5, 0.5)
    var _summary_temporal_masking_decay = _summary_float64(_result_temporal_masking_decay)
    print("MOJO_RESULT psychoacoustics::temporal_masking_decay", _summary_temporal_masking_decay)
    var _acc_binaural_masking_level_diff: Float64 = 0.0
    var _t0_binaural_masking_level_diff = perf_counter_ns()
    for _ in range(N):
        _acc_binaural_masking_level_diff += binaural_masking_level_diff(0.5, 0.5)
    var _t1_binaural_masking_level_diff = perf_counter_ns()
    var _ns_binaural_masking_level_diff = Float64(_t1_binaural_masking_level_diff - _t0_binaural_masking_level_diff) / Float64(N)
    print("MOJO_TIMING psychoacoustics::binaural_masking_level_diff", _ns_binaural_masking_level_diff, _acc_binaural_masking_level_diff)
    var _result_binaural_masking_level_diff = binaural_masking_level_diff(0.5, 0.5)
    var _summary_binaural_masking_level_diff = _summary_float64(_result_binaural_masking_level_diff)
    print("MOJO_RESULT psychoacoustics::binaural_masking_level_diff", _summary_binaural_masking_level_diff)
