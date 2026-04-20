"""bench_text_fuzzy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from text.fuzzy import levenshtein_distance, normalized_levenshtein, jaro_similarity, jaro_winkler_similarity, hamming_distance, longest_common_subsequence, fuzzy_ratio
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

    var _acc_levenshtein_distance: Float64 = 0.0
    var _t0_levenshtein_distance = perf_counter_ns()
    for _ in range(N):
        _acc_levenshtein_distance += Float64(levenshtein_distance("test", "test"))
    var _t1_levenshtein_distance = perf_counter_ns()
    var _ns_levenshtein_distance = Float64(_t1_levenshtein_distance - _t0_levenshtein_distance) / Float64(N)
    print("MOJO_TIMING text_fuzzy::levenshtein_distance", _ns_levenshtein_distance, _acc_levenshtein_distance)
    var _acc_normalized_levenshtein: Float64 = 0.0
    var _t0_normalized_levenshtein = perf_counter_ns()
    for _ in range(N):
        _acc_normalized_levenshtein += normalized_levenshtein("test", "test")
    var _t1_normalized_levenshtein = perf_counter_ns()
    var _ns_normalized_levenshtein = Float64(_t1_normalized_levenshtein - _t0_normalized_levenshtein) / Float64(N)
    print("MOJO_TIMING text_fuzzy::normalized_levenshtein", _ns_normalized_levenshtein, _acc_normalized_levenshtein)
    var _acc_jaro_similarity: Float64 = 0.0
    var _t0_jaro_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_jaro_similarity += jaro_similarity("test", "test")
    var _t1_jaro_similarity = perf_counter_ns()
    var _ns_jaro_similarity = Float64(_t1_jaro_similarity - _t0_jaro_similarity) / Float64(N)
    print("MOJO_TIMING text_fuzzy::jaro_similarity", _ns_jaro_similarity, _acc_jaro_similarity)
    var _acc_jaro_winkler_similarity: Float64 = 0.0
    var _t0_jaro_winkler_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_jaro_winkler_similarity += jaro_winkler_similarity("test", "test", 0.5)
    var _t1_jaro_winkler_similarity = perf_counter_ns()
    var _ns_jaro_winkler_similarity = Float64(_t1_jaro_winkler_similarity - _t0_jaro_winkler_similarity) / Float64(N)
    print("MOJO_TIMING text_fuzzy::jaro_winkler_similarity", _ns_jaro_winkler_similarity, _acc_jaro_winkler_similarity)
    var _acc_hamming_distance: Float64 = 0.0
    var _t0_hamming_distance = perf_counter_ns()
    for _ in range(N):
        _acc_hamming_distance += Float64(hamming_distance("test", "test"))
    var _t1_hamming_distance = perf_counter_ns()
    var _ns_hamming_distance = Float64(_t1_hamming_distance - _t0_hamming_distance) / Float64(N)
    print("MOJO_TIMING text_fuzzy::hamming_distance", _ns_hamming_distance, _acc_hamming_distance)
    var _acc_longest_common_subsequence: Float64 = 0.0
    var _t0_longest_common_subsequence = perf_counter_ns()
    for _ in range(N):
        _acc_longest_common_subsequence += Float64(longest_common_subsequence("test", "test"))
    var _t1_longest_common_subsequence = perf_counter_ns()
    var _ns_longest_common_subsequence = Float64(_t1_longest_common_subsequence - _t0_longest_common_subsequence) / Float64(N)
    print("MOJO_TIMING text_fuzzy::longest_common_subsequence", _ns_longest_common_subsequence, _acc_longest_common_subsequence)
    var _acc_fuzzy_ratio: Float64 = 0.0
    var _t0_fuzzy_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_fuzzy_ratio += fuzzy_ratio("test", "test")
    var _t1_fuzzy_ratio = perf_counter_ns()
    var _ns_fuzzy_ratio = Float64(_t1_fuzzy_ratio - _t0_fuzzy_ratio) / Float64(N)
    print("MOJO_TIMING text_fuzzy::fuzzy_ratio", _ns_fuzzy_ratio, _acc_fuzzy_ratio)
