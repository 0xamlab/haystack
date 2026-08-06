"""bench_linguistics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from linguistics import type_token_ratio, hapax_legomena_ratio, yules_k, heaps_law, zipfs_frequency, flesch_reading_ease, flesch_kincaid_grade, gunning_fog_index, automated_readability_index, coleman_liau_index, lexical_density, mean_word_length
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

    var _acc_type_token_ratio: Float64 = 0.0
    var _t0_type_token_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_type_token_ratio += type_token_ratio(0.5, 0.5)
    var _t1_type_token_ratio = perf_counter_ns()
    var _ns_type_token_ratio = Float64(_t1_type_token_ratio - _t0_type_token_ratio) / Float64(N)
    print("MOJO_TIMING linguistics::type_token_ratio", _ns_type_token_ratio, _acc_type_token_ratio)
    var _result_type_token_ratio = type_token_ratio(0.5, 0.5)
    var _summary_type_token_ratio = _summary_float64(_result_type_token_ratio)
    print("MOJO_RESULT linguistics::type_token_ratio", _summary_type_token_ratio)
    var _acc_hapax_legomena_ratio: Float64 = 0.0
    var _t0_hapax_legomena_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_hapax_legomena_ratio += hapax_legomena_ratio(0.5, 0.5)
    var _t1_hapax_legomena_ratio = perf_counter_ns()
    var _ns_hapax_legomena_ratio = Float64(_t1_hapax_legomena_ratio - _t0_hapax_legomena_ratio) / Float64(N)
    print("MOJO_TIMING linguistics::hapax_legomena_ratio", _ns_hapax_legomena_ratio, _acc_hapax_legomena_ratio)
    var _result_hapax_legomena_ratio = hapax_legomena_ratio(0.5, 0.5)
    var _summary_hapax_legomena_ratio = _summary_float64(_result_hapax_legomena_ratio)
    print("MOJO_RESULT linguistics::hapax_legomena_ratio", _summary_hapax_legomena_ratio)
    var _acc_yules_k: Float64 = 0.0
    var _t0_yules_k = perf_counter_ns()
    for _ in range(N):
        _acc_yules_k += yules_k(0.5, 0.5)
    var _t1_yules_k = perf_counter_ns()
    var _ns_yules_k = Float64(_t1_yules_k - _t0_yules_k) / Float64(N)
    print("MOJO_TIMING linguistics::yules_k", _ns_yules_k, _acc_yules_k)
    var _result_yules_k = yules_k(0.5, 0.5)
    var _summary_yules_k = _summary_float64(_result_yules_k)
    print("MOJO_RESULT linguistics::yules_k", _summary_yules_k)
    var _acc_heaps_law: Float64 = 0.0
    var _t0_heaps_law = perf_counter_ns()
    for _ in range(N):
        _acc_heaps_law += heaps_law(0.5, 0.5, 0.5)
    var _t1_heaps_law = perf_counter_ns()
    var _ns_heaps_law = Float64(_t1_heaps_law - _t0_heaps_law) / Float64(N)
    print("MOJO_TIMING linguistics::heaps_law", _ns_heaps_law, _acc_heaps_law)
    var _result_heaps_law = heaps_law(0.5, 0.5, 0.5)
    var _summary_heaps_law = _summary_float64(_result_heaps_law)
    print("MOJO_RESULT linguistics::heaps_law", _summary_heaps_law)
    var _acc_zipfs_frequency: Float64 = 0.0
    var _t0_zipfs_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_zipfs_frequency += zipfs_frequency(0.5, 0.5, 0.5)
    var _t1_zipfs_frequency = perf_counter_ns()
    var _ns_zipfs_frequency = Float64(_t1_zipfs_frequency - _t0_zipfs_frequency) / Float64(N)
    print("MOJO_TIMING linguistics::zipfs_frequency", _ns_zipfs_frequency, _acc_zipfs_frequency)
    var _result_zipfs_frequency = zipfs_frequency(0.5, 0.5, 0.5)
    var _summary_zipfs_frequency = _summary_float64(_result_zipfs_frequency)
    print("MOJO_RESULT linguistics::zipfs_frequency", _summary_zipfs_frequency)
    var _acc_flesch_reading_ease: Float64 = 0.0
    var _t0_flesch_reading_ease = perf_counter_ns()
    for _ in range(N):
        _acc_flesch_reading_ease += flesch_reading_ease(0.5, 0.5, 0.5)
    var _t1_flesch_reading_ease = perf_counter_ns()
    var _ns_flesch_reading_ease = Float64(_t1_flesch_reading_ease - _t0_flesch_reading_ease) / Float64(N)
    print("MOJO_TIMING linguistics::flesch_reading_ease", _ns_flesch_reading_ease, _acc_flesch_reading_ease)
    var _result_flesch_reading_ease = flesch_reading_ease(0.5, 0.5, 0.5)
    var _summary_flesch_reading_ease = _summary_float64(_result_flesch_reading_ease)
    print("MOJO_RESULT linguistics::flesch_reading_ease", _summary_flesch_reading_ease)
    var _acc_flesch_kincaid_grade: Float64 = 0.0
    var _t0_flesch_kincaid_grade = perf_counter_ns()
    for _ in range(N):
        _acc_flesch_kincaid_grade += flesch_kincaid_grade(0.5, 0.5, 0.5)
    var _t1_flesch_kincaid_grade = perf_counter_ns()
    var _ns_flesch_kincaid_grade = Float64(_t1_flesch_kincaid_grade - _t0_flesch_kincaid_grade) / Float64(N)
    print("MOJO_TIMING linguistics::flesch_kincaid_grade", _ns_flesch_kincaid_grade, _acc_flesch_kincaid_grade)
    var _result_flesch_kincaid_grade = flesch_kincaid_grade(0.5, 0.5, 0.5)
    var _summary_flesch_kincaid_grade = _summary_float64(_result_flesch_kincaid_grade)
    print("MOJO_RESULT linguistics::flesch_kincaid_grade", _summary_flesch_kincaid_grade)
    var _acc_gunning_fog_index: Float64 = 0.0
    var _t0_gunning_fog_index = perf_counter_ns()
    for _ in range(N):
        _acc_gunning_fog_index += gunning_fog_index(0.5, 0.5, 0.5)
    var _t1_gunning_fog_index = perf_counter_ns()
    var _ns_gunning_fog_index = Float64(_t1_gunning_fog_index - _t0_gunning_fog_index) / Float64(N)
    print("MOJO_TIMING linguistics::gunning_fog_index", _ns_gunning_fog_index, _acc_gunning_fog_index)
    var _result_gunning_fog_index = gunning_fog_index(0.5, 0.5, 0.5)
    var _summary_gunning_fog_index = _summary_float64(_result_gunning_fog_index)
    print("MOJO_RESULT linguistics::gunning_fog_index", _summary_gunning_fog_index)
    var _acc_automated_readability_index: Float64 = 0.0
    var _t0_automated_readability_index = perf_counter_ns()
    for _ in range(N):
        _acc_automated_readability_index += automated_readability_index(0.5, 0.5, 0.5)
    var _t1_automated_readability_index = perf_counter_ns()
    var _ns_automated_readability_index = Float64(_t1_automated_readability_index - _t0_automated_readability_index) / Float64(N)
    print("MOJO_TIMING linguistics::automated_readability_index", _ns_automated_readability_index, _acc_automated_readability_index)
    var _result_automated_readability_index = automated_readability_index(0.5, 0.5, 0.5)
    var _summary_automated_readability_index = _summary_float64(_result_automated_readability_index)
    print("MOJO_RESULT linguistics::automated_readability_index", _summary_automated_readability_index)
    var _acc_coleman_liau_index: Float64 = 0.0
    var _t0_coleman_liau_index = perf_counter_ns()
    for _ in range(N):
        _acc_coleman_liau_index += coleman_liau_index(0.5, 0.5)
    var _t1_coleman_liau_index = perf_counter_ns()
    var _ns_coleman_liau_index = Float64(_t1_coleman_liau_index - _t0_coleman_liau_index) / Float64(N)
    print("MOJO_TIMING linguistics::coleman_liau_index", _ns_coleman_liau_index, _acc_coleman_liau_index)
    var _result_coleman_liau_index = coleman_liau_index(0.5, 0.5)
    var _summary_coleman_liau_index = _summary_float64(_result_coleman_liau_index)
    print("MOJO_RESULT linguistics::coleman_liau_index", _summary_coleman_liau_index)
    var _acc_lexical_density: Float64 = 0.0
    var _t0_lexical_density = perf_counter_ns()
    for _ in range(N):
        _acc_lexical_density += lexical_density(0.5, 0.5)
    var _t1_lexical_density = perf_counter_ns()
    var _ns_lexical_density = Float64(_t1_lexical_density - _t0_lexical_density) / Float64(N)
    print("MOJO_TIMING linguistics::lexical_density", _ns_lexical_density, _acc_lexical_density)
    var _result_lexical_density = lexical_density(0.5, 0.5)
    var _summary_lexical_density = _summary_float64(_result_lexical_density)
    print("MOJO_RESULT linguistics::lexical_density", _summary_lexical_density)
    var _acc_mean_word_length: Float64 = 0.0
    var _t0_mean_word_length = perf_counter_ns()
    for _ in range(N):
        _acc_mean_word_length += mean_word_length(0.5, 0.5)
    var _t1_mean_word_length = perf_counter_ns()
    var _ns_mean_word_length = Float64(_t1_mean_word_length - _t0_mean_word_length) / Float64(N)
    print("MOJO_TIMING linguistics::mean_word_length", _ns_mean_word_length, _acc_mean_word_length)
    var _result_mean_word_length = mean_word_length(0.5, 0.5)
    var _summary_mean_word_length = _summary_float64(_result_mean_word_length)
    print("MOJO_RESULT linguistics::mean_word_length", _summary_mean_word_length)
