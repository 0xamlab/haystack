"""bench_string_distance.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from string_distance import damerau_levenshtein, soundex, edit_similarity, common_prefix_length, common_suffix_length, bigrams, dice_coefficient, overlap_coefficient, string_reverse, is_palindrome
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

    var _acc_damerau_levenshtein: Float64 = 0.0
    var _t0_damerau_levenshtein = perf_counter_ns()
    for _ in range(N):
        _acc_damerau_levenshtein += Float64(damerau_levenshtein("test", "test"))
    var _t1_damerau_levenshtein = perf_counter_ns()
    var _ns_damerau_levenshtein = Float64(_t1_damerau_levenshtein - _t0_damerau_levenshtein) / Float64(N)
    print("MOJO_TIMING string_distance::damerau_levenshtein", _ns_damerau_levenshtein, _acc_damerau_levenshtein)
    var _acc_soundex: Float64 = 0.0
    var _t0_soundex = perf_counter_ns()
    for _ in range(N):
        _ = soundex("test")
    var _t1_soundex = perf_counter_ns()
    var _ns_soundex = Float64(_t1_soundex - _t0_soundex) / Float64(N)
    print("MOJO_TIMING string_distance::soundex", _ns_soundex, _acc_soundex)
    var _acc_edit_similarity: Float64 = 0.0
    var _t0_edit_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_edit_similarity += edit_similarity("test", "test")
    var _t1_edit_similarity = perf_counter_ns()
    var _ns_edit_similarity = Float64(_t1_edit_similarity - _t0_edit_similarity) / Float64(N)
    print("MOJO_TIMING string_distance::edit_similarity", _ns_edit_similarity, _acc_edit_similarity)
    var _acc_common_prefix_length: Float64 = 0.0
    var _t0_common_prefix_length = perf_counter_ns()
    for _ in range(N):
        _acc_common_prefix_length += Float64(common_prefix_length("test", "test"))
    var _t1_common_prefix_length = perf_counter_ns()
    var _ns_common_prefix_length = Float64(_t1_common_prefix_length - _t0_common_prefix_length) / Float64(N)
    print("MOJO_TIMING string_distance::common_prefix_length", _ns_common_prefix_length, _acc_common_prefix_length)
    var _acc_common_suffix_length: Float64 = 0.0
    var _t0_common_suffix_length = perf_counter_ns()
    for _ in range(N):
        _acc_common_suffix_length += Float64(common_suffix_length("test", "test"))
    var _t1_common_suffix_length = perf_counter_ns()
    var _ns_common_suffix_length = Float64(_t1_common_suffix_length - _t0_common_suffix_length) / Float64(N)
    print("MOJO_TIMING string_distance::common_suffix_length", _ns_common_suffix_length, _acc_common_suffix_length)
    var _acc_bigrams: Float64 = 0.0
    var _t0_bigrams = perf_counter_ns()
    for _ in range(N):
        var _r_bigrams = bigrams("test")
        _acc_bigrams += Float64(len(_r_bigrams))
    var _t1_bigrams = perf_counter_ns()
    var _ns_bigrams = Float64(_t1_bigrams - _t0_bigrams) / Float64(N)
    print("MOJO_TIMING string_distance::bigrams", _ns_bigrams, _acc_bigrams)
    var _acc_dice_coefficient: Float64 = 0.0
    var _t0_dice_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_dice_coefficient += dice_coefficient("test", "test")
    var _t1_dice_coefficient = perf_counter_ns()
    var _ns_dice_coefficient = Float64(_t1_dice_coefficient - _t0_dice_coefficient) / Float64(N)
    print("MOJO_TIMING string_distance::dice_coefficient", _ns_dice_coefficient, _acc_dice_coefficient)
    var _acc_overlap_coefficient: Float64 = 0.0
    var _t0_overlap_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_overlap_coefficient += overlap_coefficient("test", "test")
    var _t1_overlap_coefficient = perf_counter_ns()
    var _ns_overlap_coefficient = Float64(_t1_overlap_coefficient - _t0_overlap_coefficient) / Float64(N)
    print("MOJO_TIMING string_distance::overlap_coefficient", _ns_overlap_coefficient, _acc_overlap_coefficient)
    var _acc_string_reverse: Float64 = 0.0
    var _t0_string_reverse = perf_counter_ns()
    for _ in range(N):
        _ = string_reverse("test")
    var _t1_string_reverse = perf_counter_ns()
    var _ns_string_reverse = Float64(_t1_string_reverse - _t0_string_reverse) / Float64(N)
    print("MOJO_TIMING string_distance::string_reverse", _ns_string_reverse, _acc_string_reverse)
    var _acc_is_palindrome: Float64 = 0.0
    var _t0_is_palindrome = perf_counter_ns()
    for _ in range(N):
        _acc_is_palindrome += Float64(is_palindrome("test"))
    var _t1_is_palindrome = perf_counter_ns()
    var _ns_is_palindrome = Float64(_t1_is_palindrome - _t0_is_palindrome) / Float64(N)
    print("MOJO_TIMING string_distance::is_palindrome", _ns_is_palindrome, _acc_is_palindrome)
