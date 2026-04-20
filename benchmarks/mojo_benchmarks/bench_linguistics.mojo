"""bench_linguistics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from linguistics import type_token_ratio, hapax_legomena_ratio, yules_k, heaps_law, zipfs_frequency, flesch_reading_ease, flesch_kincaid_grade, gunning_fog_index, automated_readability_index, coleman_liau_index, lexical_density, mean_word_length
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

    var _acc_type_token_ratio: Float64 = 0.0
    var _t0_type_token_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_type_token_ratio += type_token_ratio(0.5, 0.5)
    var _t1_type_token_ratio = perf_counter_ns()
    var _ns_type_token_ratio = Float64(_t1_type_token_ratio - _t0_type_token_ratio) / Float64(N)
    print("MOJO_TIMING linguistics::type_token_ratio", _ns_type_token_ratio, _acc_type_token_ratio)
    var _acc_hapax_legomena_ratio: Float64 = 0.0
    var _t0_hapax_legomena_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_hapax_legomena_ratio += hapax_legomena_ratio(0.5, 0.5)
    var _t1_hapax_legomena_ratio = perf_counter_ns()
    var _ns_hapax_legomena_ratio = Float64(_t1_hapax_legomena_ratio - _t0_hapax_legomena_ratio) / Float64(N)
    print("MOJO_TIMING linguistics::hapax_legomena_ratio", _ns_hapax_legomena_ratio, _acc_hapax_legomena_ratio)
    var _acc_yules_k: Float64 = 0.0
    var _t0_yules_k = perf_counter_ns()
    for _ in range(N):
        _acc_yules_k += yules_k(0.5, 0.5)
    var _t1_yules_k = perf_counter_ns()
    var _ns_yules_k = Float64(_t1_yules_k - _t0_yules_k) / Float64(N)
    print("MOJO_TIMING linguistics::yules_k", _ns_yules_k, _acc_yules_k)
    var _acc_heaps_law: Float64 = 0.0
    var _t0_heaps_law = perf_counter_ns()
    for _ in range(N):
        _acc_heaps_law += heaps_law(0.5, 0.5, 0.5)
    var _t1_heaps_law = perf_counter_ns()
    var _ns_heaps_law = Float64(_t1_heaps_law - _t0_heaps_law) / Float64(N)
    print("MOJO_TIMING linguistics::heaps_law", _ns_heaps_law, _acc_heaps_law)
    var _acc_zipfs_frequency: Float64 = 0.0
    var _t0_zipfs_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_zipfs_frequency += zipfs_frequency(0.5, 0.5, 0.5)
    var _t1_zipfs_frequency = perf_counter_ns()
    var _ns_zipfs_frequency = Float64(_t1_zipfs_frequency - _t0_zipfs_frequency) / Float64(N)
    print("MOJO_TIMING linguistics::zipfs_frequency", _ns_zipfs_frequency, _acc_zipfs_frequency)
    var _acc_flesch_reading_ease: Float64 = 0.0
    var _t0_flesch_reading_ease = perf_counter_ns()
    for _ in range(N):
        _acc_flesch_reading_ease += flesch_reading_ease(0.5, 0.5, 0.5)
    var _t1_flesch_reading_ease = perf_counter_ns()
    var _ns_flesch_reading_ease = Float64(_t1_flesch_reading_ease - _t0_flesch_reading_ease) / Float64(N)
    print("MOJO_TIMING linguistics::flesch_reading_ease", _ns_flesch_reading_ease, _acc_flesch_reading_ease)
    var _acc_flesch_kincaid_grade: Float64 = 0.0
    var _t0_flesch_kincaid_grade = perf_counter_ns()
    for _ in range(N):
        _acc_flesch_kincaid_grade += flesch_kincaid_grade(0.5, 0.5, 0.5)
    var _t1_flesch_kincaid_grade = perf_counter_ns()
    var _ns_flesch_kincaid_grade = Float64(_t1_flesch_kincaid_grade - _t0_flesch_kincaid_grade) / Float64(N)
    print("MOJO_TIMING linguistics::flesch_kincaid_grade", _ns_flesch_kincaid_grade, _acc_flesch_kincaid_grade)
    var _acc_gunning_fog_index: Float64 = 0.0
    var _t0_gunning_fog_index = perf_counter_ns()
    for _ in range(N):
        _acc_gunning_fog_index += gunning_fog_index(0.5, 0.5, 0.5)
    var _t1_gunning_fog_index = perf_counter_ns()
    var _ns_gunning_fog_index = Float64(_t1_gunning_fog_index - _t0_gunning_fog_index) / Float64(N)
    print("MOJO_TIMING linguistics::gunning_fog_index", _ns_gunning_fog_index, _acc_gunning_fog_index)
    var _acc_automated_readability_index: Float64 = 0.0
    var _t0_automated_readability_index = perf_counter_ns()
    for _ in range(N):
        _acc_automated_readability_index += automated_readability_index(0.5, 0.5, 0.5)
    var _t1_automated_readability_index = perf_counter_ns()
    var _ns_automated_readability_index = Float64(_t1_automated_readability_index - _t0_automated_readability_index) / Float64(N)
    print("MOJO_TIMING linguistics::automated_readability_index", _ns_automated_readability_index, _acc_automated_readability_index)
    var _acc_coleman_liau_index: Float64 = 0.0
    var _t0_coleman_liau_index = perf_counter_ns()
    for _ in range(N):
        _acc_coleman_liau_index += coleman_liau_index(0.5, 0.5)
    var _t1_coleman_liau_index = perf_counter_ns()
    var _ns_coleman_liau_index = Float64(_t1_coleman_liau_index - _t0_coleman_liau_index) / Float64(N)
    print("MOJO_TIMING linguistics::coleman_liau_index", _ns_coleman_liau_index, _acc_coleman_liau_index)
    var _acc_lexical_density: Float64 = 0.0
    var _t0_lexical_density = perf_counter_ns()
    for _ in range(N):
        _acc_lexical_density += lexical_density(0.5, 0.5)
    var _t1_lexical_density = perf_counter_ns()
    var _ns_lexical_density = Float64(_t1_lexical_density - _t0_lexical_density) / Float64(N)
    print("MOJO_TIMING linguistics::lexical_density", _ns_lexical_density, _acc_lexical_density)
    var _acc_mean_word_length: Float64 = 0.0
    var _t0_mean_word_length = perf_counter_ns()
    for _ in range(N):
        _acc_mean_word_length += mean_word_length(0.5, 0.5)
    var _t1_mean_word_length = perf_counter_ns()
    var _ns_mean_word_length = Float64(_t1_mean_word_length - _t0_mean_word_length) / Float64(N)
    print("MOJO_TIMING linguistics::mean_word_length", _ns_mean_word_length, _acc_mean_word_length)
