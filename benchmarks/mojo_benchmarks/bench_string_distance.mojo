"""bench_string_distance.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from string_distance import damerau_levenshtein, soundex, edit_similarity, common_prefix_length, common_suffix_length, bigrams, dice_coefficient, overlap_coefficient, string_reverse, is_palindrome
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

    var _acc_damerau_levenshtein: Float64 = 0.0
    var _t0_damerau_levenshtein = perf_counter_ns()
    for _ in range(N):
        _acc_damerau_levenshtein += Float64(damerau_levenshtein("test", "test"))
    var _t1_damerau_levenshtein = perf_counter_ns()
    var _ns_damerau_levenshtein = Float64(_t1_damerau_levenshtein - _t0_damerau_levenshtein) / Float64(N)
    print("MOJO_TIMING string_distance::damerau_levenshtein", _ns_damerau_levenshtein, _acc_damerau_levenshtein)
    var _result_damerau_levenshtein = damerau_levenshtein("test", "test")
    var _summary_damerau_levenshtein = _summary_int(_result_damerau_levenshtein)
    print("MOJO_RESULT string_distance::damerau_levenshtein", _summary_damerau_levenshtein)
    var _acc_soundex: Float64 = 0.0
    var _t0_soundex = perf_counter_ns()
    for _ in range(N):
        _ = soundex("test")
    var _t1_soundex = perf_counter_ns()
    var _ns_soundex = Float64(_t1_soundex - _t0_soundex) / Float64(N)
    print("MOJO_TIMING string_distance::soundex", _ns_soundex, _acc_soundex)
    var _result_soundex = soundex("test")
    var _summary_soundex = _summary_string(_result_soundex)
    print("MOJO_RESULT string_distance::soundex", _summary_soundex)
    var _acc_edit_similarity: Float64 = 0.0
    var _t0_edit_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_edit_similarity += edit_similarity("test", "test")
    var _t1_edit_similarity = perf_counter_ns()
    var _ns_edit_similarity = Float64(_t1_edit_similarity - _t0_edit_similarity) / Float64(N)
    print("MOJO_TIMING string_distance::edit_similarity", _ns_edit_similarity, _acc_edit_similarity)
    var _result_edit_similarity = edit_similarity("test", "test")
    var _summary_edit_similarity = _summary_float64(_result_edit_similarity)
    print("MOJO_RESULT string_distance::edit_similarity", _summary_edit_similarity)
    var _acc_common_prefix_length: Float64 = 0.0
    var _t0_common_prefix_length = perf_counter_ns()
    for _ in range(N):
        _acc_common_prefix_length += Float64(common_prefix_length("test", "test"))
    var _t1_common_prefix_length = perf_counter_ns()
    var _ns_common_prefix_length = Float64(_t1_common_prefix_length - _t0_common_prefix_length) / Float64(N)
    print("MOJO_TIMING string_distance::common_prefix_length", _ns_common_prefix_length, _acc_common_prefix_length)
    var _result_common_prefix_length = common_prefix_length("test", "test")
    var _summary_common_prefix_length = _summary_int(_result_common_prefix_length)
    print("MOJO_RESULT string_distance::common_prefix_length", _summary_common_prefix_length)
    var _acc_common_suffix_length: Float64 = 0.0
    var _t0_common_suffix_length = perf_counter_ns()
    for _ in range(N):
        _acc_common_suffix_length += Float64(common_suffix_length("test", "test"))
    var _t1_common_suffix_length = perf_counter_ns()
    var _ns_common_suffix_length = Float64(_t1_common_suffix_length - _t0_common_suffix_length) / Float64(N)
    print("MOJO_TIMING string_distance::common_suffix_length", _ns_common_suffix_length, _acc_common_suffix_length)
    var _result_common_suffix_length = common_suffix_length("test", "test")
    var _summary_common_suffix_length = _summary_int(_result_common_suffix_length)
    print("MOJO_RESULT string_distance::common_suffix_length", _summary_common_suffix_length)
    var _acc_bigrams: Float64 = 0.0
    var _t0_bigrams = perf_counter_ns()
    for _ in range(N):
        var _r_bigrams = bigrams("test")
        _acc_bigrams += Float64(len(_r_bigrams))
    var _t1_bigrams = perf_counter_ns()
    var _ns_bigrams = Float64(_t1_bigrams - _t0_bigrams) / Float64(N)
    print("MOJO_TIMING string_distance::bigrams", _ns_bigrams, _acc_bigrams)
    var _result_bigrams = bigrams("test")
    var _summary_bigrams = _summary_list_string(_result_bigrams)
    print("MOJO_RESULT string_distance::bigrams", _summary_bigrams)
    var _acc_dice_coefficient: Float64 = 0.0
    var _t0_dice_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_dice_coefficient += dice_coefficient("test", "test")
    var _t1_dice_coefficient = perf_counter_ns()
    var _ns_dice_coefficient = Float64(_t1_dice_coefficient - _t0_dice_coefficient) / Float64(N)
    print("MOJO_TIMING string_distance::dice_coefficient", _ns_dice_coefficient, _acc_dice_coefficient)
    var _result_dice_coefficient = dice_coefficient("test", "test")
    var _summary_dice_coefficient = _summary_float64(_result_dice_coefficient)
    print("MOJO_RESULT string_distance::dice_coefficient", _summary_dice_coefficient)
    var _acc_overlap_coefficient: Float64 = 0.0
    var _t0_overlap_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_overlap_coefficient += overlap_coefficient("test", "test")
    var _t1_overlap_coefficient = perf_counter_ns()
    var _ns_overlap_coefficient = Float64(_t1_overlap_coefficient - _t0_overlap_coefficient) / Float64(N)
    print("MOJO_TIMING string_distance::overlap_coefficient", _ns_overlap_coefficient, _acc_overlap_coefficient)
    var _result_overlap_coefficient = overlap_coefficient("test", "test")
    var _summary_overlap_coefficient = _summary_float64(_result_overlap_coefficient)
    print("MOJO_RESULT string_distance::overlap_coefficient", _summary_overlap_coefficient)
    var _acc_string_reverse: Float64 = 0.0
    var _t0_string_reverse = perf_counter_ns()
    for _ in range(N):
        _ = string_reverse("test")
    var _t1_string_reverse = perf_counter_ns()
    var _ns_string_reverse = Float64(_t1_string_reverse - _t0_string_reverse) / Float64(N)
    print("MOJO_TIMING string_distance::string_reverse", _ns_string_reverse, _acc_string_reverse)
    var _result_string_reverse = string_reverse("test")
    var _summary_string_reverse = _summary_string(_result_string_reverse)
    print("MOJO_RESULT string_distance::string_reverse", _summary_string_reverse)
    var _acc_is_palindrome: Float64 = 0.0
    var _t0_is_palindrome = perf_counter_ns()
    for _ in range(N):
        _acc_is_palindrome += Float64(is_palindrome("test"))
    var _t1_is_palindrome = perf_counter_ns()
    var _ns_is_palindrome = Float64(_t1_is_palindrome - _t0_is_palindrome) / Float64(N)
    print("MOJO_TIMING string_distance::is_palindrome", _ns_is_palindrome, _acc_is_palindrome)
    var _result_is_palindrome = is_palindrome("test")
    var _summary_is_palindrome = _summary_bool(_result_is_palindrome)
    print("MOJO_RESULT string_distance::is_palindrome", _summary_is_palindrome)
