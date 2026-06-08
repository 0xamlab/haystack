"""bench_cryptanalysis.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cryptanalysis import frequency_score_2, index_of_coincidence_2, expected_ic_random, expected_ic_english, friedman_key_length, kasiski_distance_gcd, caesar_decrypt_score, hamming_distance_bytes, entropy_bits_2, entropy_bits_4, brute_force_time_estimate, avalanche_effect
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

    var _acc_frequency_score_2: Float64 = 0.0
    var _t0_frequency_score_2 = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_score_2 += frequency_score_2(5, 5, 0.5, 0.5)
    var _t1_frequency_score_2 = perf_counter_ns()
    var _ns_frequency_score_2 = Float64(_t1_frequency_score_2 - _t0_frequency_score_2) / Float64(N)
    print("MOJO_TIMING cryptanalysis::frequency_score_2", _ns_frequency_score_2, _acc_frequency_score_2)
    var _result_frequency_score_2 = frequency_score_2(5, 5, 0.5, 0.5)
    var _summary_frequency_score_2 = _summary_float64(_result_frequency_score_2)
    print("MOJO_RESULT cryptanalysis::frequency_score_2", _summary_frequency_score_2)
    var _acc_index_of_coincidence_2: Float64 = 0.0
    var _t0_index_of_coincidence_2 = perf_counter_ns()
    for _ in range(N):
        _acc_index_of_coincidence_2 += index_of_coincidence_2(5, 5, 5)
    var _t1_index_of_coincidence_2 = perf_counter_ns()
    var _ns_index_of_coincidence_2 = Float64(_t1_index_of_coincidence_2 - _t0_index_of_coincidence_2) / Float64(N)
    print("MOJO_TIMING cryptanalysis::index_of_coincidence_2", _ns_index_of_coincidence_2, _acc_index_of_coincidence_2)
    var _result_index_of_coincidence_2 = index_of_coincidence_2(5, 5, 5)
    var _summary_index_of_coincidence_2 = _summary_float64(_result_index_of_coincidence_2)
    print("MOJO_RESULT cryptanalysis::index_of_coincidence_2", _summary_index_of_coincidence_2)
    var _acc_expected_ic_random: Float64 = 0.0
    var _t0_expected_ic_random = perf_counter_ns()
    for _ in range(N):
        _acc_expected_ic_random += expected_ic_random(5)
    var _t1_expected_ic_random = perf_counter_ns()
    var _ns_expected_ic_random = Float64(_t1_expected_ic_random - _t0_expected_ic_random) / Float64(N)
    print("MOJO_TIMING cryptanalysis::expected_ic_random", _ns_expected_ic_random, _acc_expected_ic_random)
    var _result_expected_ic_random = expected_ic_random(5)
    var _summary_expected_ic_random = _summary_float64(_result_expected_ic_random)
    print("MOJO_RESULT cryptanalysis::expected_ic_random", _summary_expected_ic_random)
    var _acc_expected_ic_english: Float64 = 0.0
    var _t0_expected_ic_english = perf_counter_ns()
    for _ in range(N):
        _acc_expected_ic_english += expected_ic_english()
    var _t1_expected_ic_english = perf_counter_ns()
    var _ns_expected_ic_english = Float64(_t1_expected_ic_english - _t0_expected_ic_english) / Float64(N)
    print("MOJO_TIMING cryptanalysis::expected_ic_english", _ns_expected_ic_english, _acc_expected_ic_english)
    var _result_expected_ic_english = expected_ic_english()
    var _summary_expected_ic_english = _summary_float64(_result_expected_ic_english)
    print("MOJO_RESULT cryptanalysis::expected_ic_english", _summary_expected_ic_english)
    var _acc_friedman_key_length: Float64 = 0.0
    var _t0_friedman_key_length = perf_counter_ns()
    for _ in range(N):
        _acc_friedman_key_length += friedman_key_length(0.5, 5)
    var _t1_friedman_key_length = perf_counter_ns()
    var _ns_friedman_key_length = Float64(_t1_friedman_key_length - _t0_friedman_key_length) / Float64(N)
    print("MOJO_TIMING cryptanalysis::friedman_key_length", _ns_friedman_key_length, _acc_friedman_key_length)
    var _result_friedman_key_length = friedman_key_length(0.5, 5)
    var _summary_friedman_key_length = _summary_float64(_result_friedman_key_length)
    print("MOJO_RESULT cryptanalysis::friedman_key_length", _summary_friedman_key_length)
    var _acc_kasiski_distance_gcd: Float64 = 0.0
    var _t0_kasiski_distance_gcd = perf_counter_ns()
    for _ in range(N):
        _acc_kasiski_distance_gcd += Float64(kasiski_distance_gcd(5, 5))
    var _t1_kasiski_distance_gcd = perf_counter_ns()
    var _ns_kasiski_distance_gcd = Float64(_t1_kasiski_distance_gcd - _t0_kasiski_distance_gcd) / Float64(N)
    print("MOJO_TIMING cryptanalysis::kasiski_distance_gcd", _ns_kasiski_distance_gcd, _acc_kasiski_distance_gcd)
    var _result_kasiski_distance_gcd = kasiski_distance_gcd(5, 5)
    var _summary_kasiski_distance_gcd = _summary_int(_result_kasiski_distance_gcd)
    print("MOJO_RESULT cryptanalysis::kasiski_distance_gcd", _summary_kasiski_distance_gcd)
    var _acc_caesar_decrypt_score: Float64 = 0.0
    var _t0_caesar_decrypt_score = perf_counter_ns()
    for _ in range(N):
        _acc_caesar_decrypt_score += caesar_decrypt_score(5, 0.5, 0.5)
    var _t1_caesar_decrypt_score = perf_counter_ns()
    var _ns_caesar_decrypt_score = Float64(_t1_caesar_decrypt_score - _t0_caesar_decrypt_score) / Float64(N)
    print("MOJO_TIMING cryptanalysis::caesar_decrypt_score", _ns_caesar_decrypt_score, _acc_caesar_decrypt_score)
    var _result_caesar_decrypt_score = caesar_decrypt_score(5, 0.5, 0.5)
    var _summary_caesar_decrypt_score = _summary_float64(_result_caesar_decrypt_score)
    print("MOJO_RESULT cryptanalysis::caesar_decrypt_score", _summary_caesar_decrypt_score)
    var _acc_hamming_distance_bytes: Float64 = 0.0
    var _t0_hamming_distance_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_hamming_distance_bytes += Float64(hamming_distance_bytes(5, 5))
    var _t1_hamming_distance_bytes = perf_counter_ns()
    var _ns_hamming_distance_bytes = Float64(_t1_hamming_distance_bytes - _t0_hamming_distance_bytes) / Float64(N)
    print("MOJO_TIMING cryptanalysis::hamming_distance_bytes", _ns_hamming_distance_bytes, _acc_hamming_distance_bytes)
    var _result_hamming_distance_bytes = hamming_distance_bytes(5, 5)
    var _summary_hamming_distance_bytes = _summary_int(_result_hamming_distance_bytes)
    print("MOJO_RESULT cryptanalysis::hamming_distance_bytes", _summary_hamming_distance_bytes)
    var _acc_entropy_bits_2: Float64 = 0.0
    var _t0_entropy_bits_2 = perf_counter_ns()
    for _ in range(N):
        _acc_entropy_bits_2 += entropy_bits_2(0.5, 0.5)
    var _t1_entropy_bits_2 = perf_counter_ns()
    var _ns_entropy_bits_2 = Float64(_t1_entropy_bits_2 - _t0_entropy_bits_2) / Float64(N)
    print("MOJO_TIMING cryptanalysis::entropy_bits_2", _ns_entropy_bits_2, _acc_entropy_bits_2)
    var _result_entropy_bits_2 = entropy_bits_2(0.5, 0.5)
    var _summary_entropy_bits_2 = _summary_float64(_result_entropy_bits_2)
    print("MOJO_RESULT cryptanalysis::entropy_bits_2", _summary_entropy_bits_2)
    var _acc_entropy_bits_4: Float64 = 0.0
    var _t0_entropy_bits_4 = perf_counter_ns()
    for _ in range(N):
        _acc_entropy_bits_4 += entropy_bits_4(0.5, 0.5, 0.5, 0.5)
    var _t1_entropy_bits_4 = perf_counter_ns()
    var _ns_entropy_bits_4 = Float64(_t1_entropy_bits_4 - _t0_entropy_bits_4) / Float64(N)
    print("MOJO_TIMING cryptanalysis::entropy_bits_4", _ns_entropy_bits_4, _acc_entropy_bits_4)
    var _result_entropy_bits_4 = entropy_bits_4(0.5, 0.5, 0.5, 0.5)
    var _summary_entropy_bits_4 = _summary_float64(_result_entropy_bits_4)
    print("MOJO_RESULT cryptanalysis::entropy_bits_4", _summary_entropy_bits_4)
    var _acc_brute_force_time_estimate: Float64 = 0.0
    var _t0_brute_force_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_brute_force_time_estimate += brute_force_time_estimate(5, 0.5)
    var _t1_brute_force_time_estimate = perf_counter_ns()
    var _ns_brute_force_time_estimate = Float64(_t1_brute_force_time_estimate - _t0_brute_force_time_estimate) / Float64(N)
    print("MOJO_TIMING cryptanalysis::brute_force_time_estimate", _ns_brute_force_time_estimate, _acc_brute_force_time_estimate)
    var _result_brute_force_time_estimate = brute_force_time_estimate(5, 0.5)
    var _summary_brute_force_time_estimate = _summary_float64(_result_brute_force_time_estimate)
    print("MOJO_RESULT cryptanalysis::brute_force_time_estimate", _summary_brute_force_time_estimate)
    var _acc_avalanche_effect: Float64 = 0.0
    var _t0_avalanche_effect = perf_counter_ns()
    for _ in range(N):
        _acc_avalanche_effect += avalanche_effect(5, 5)
    var _t1_avalanche_effect = perf_counter_ns()
    var _ns_avalanche_effect = Float64(_t1_avalanche_effect - _t0_avalanche_effect) / Float64(N)
    print("MOJO_TIMING cryptanalysis::avalanche_effect", _ns_avalanche_effect, _acc_avalanche_effect)
    var _result_avalanche_effect = avalanche_effect(5, 5)
    var _summary_avalanche_effect = _summary_float64(_result_avalanche_effect)
    print("MOJO_RESULT cryptanalysis::avalanche_effect", _summary_avalanche_effect)
