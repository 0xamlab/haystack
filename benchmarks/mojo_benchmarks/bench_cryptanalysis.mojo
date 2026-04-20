"""bench_cryptanalysis.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cryptanalysis import frequency_score_2, index_of_coincidence_2, expected_ic_random, expected_ic_english, friedman_key_length, kasiski_distance_gcd, caesar_decrypt_score, hamming_distance_bytes, entropy_bits_2, entropy_bits_4, brute_force_time_estimate, avalanche_effect
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

    var _acc_frequency_score_2: Float64 = 0.0
    var _t0_frequency_score_2 = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_score_2 += frequency_score_2(5, 5, 0.5, 0.5)
    var _t1_frequency_score_2 = perf_counter_ns()
    var _ns_frequency_score_2 = Float64(_t1_frequency_score_2 - _t0_frequency_score_2) / Float64(N)
    print("MOJO_TIMING cryptanalysis::frequency_score_2", _ns_frequency_score_2, _acc_frequency_score_2)
    var _acc_index_of_coincidence_2: Float64 = 0.0
    var _t0_index_of_coincidence_2 = perf_counter_ns()
    for _ in range(N):
        _acc_index_of_coincidence_2 += index_of_coincidence_2(5, 5, 5)
    var _t1_index_of_coincidence_2 = perf_counter_ns()
    var _ns_index_of_coincidence_2 = Float64(_t1_index_of_coincidence_2 - _t0_index_of_coincidence_2) / Float64(N)
    print("MOJO_TIMING cryptanalysis::index_of_coincidence_2", _ns_index_of_coincidence_2, _acc_index_of_coincidence_2)
    var _acc_expected_ic_random: Float64 = 0.0
    var _t0_expected_ic_random = perf_counter_ns()
    for _ in range(N):
        _acc_expected_ic_random += expected_ic_random(5)
    var _t1_expected_ic_random = perf_counter_ns()
    var _ns_expected_ic_random = Float64(_t1_expected_ic_random - _t0_expected_ic_random) / Float64(N)
    print("MOJO_TIMING cryptanalysis::expected_ic_random", _ns_expected_ic_random, _acc_expected_ic_random)
    var _acc_expected_ic_english: Float64 = 0.0
    var _t0_expected_ic_english = perf_counter_ns()
    for _ in range(N):
        _acc_expected_ic_english += expected_ic_english()
    var _t1_expected_ic_english = perf_counter_ns()
    var _ns_expected_ic_english = Float64(_t1_expected_ic_english - _t0_expected_ic_english) / Float64(N)
    print("MOJO_TIMING cryptanalysis::expected_ic_english", _ns_expected_ic_english, _acc_expected_ic_english)
    var _acc_friedman_key_length: Float64 = 0.0
    var _t0_friedman_key_length = perf_counter_ns()
    for _ in range(N):
        _acc_friedman_key_length += friedman_key_length(0.5, 5)
    var _t1_friedman_key_length = perf_counter_ns()
    var _ns_friedman_key_length = Float64(_t1_friedman_key_length - _t0_friedman_key_length) / Float64(N)
    print("MOJO_TIMING cryptanalysis::friedman_key_length", _ns_friedman_key_length, _acc_friedman_key_length)
    var _acc_kasiski_distance_gcd: Float64 = 0.0
    var _t0_kasiski_distance_gcd = perf_counter_ns()
    for _ in range(N):
        _acc_kasiski_distance_gcd += Float64(kasiski_distance_gcd(5, 5))
    var _t1_kasiski_distance_gcd = perf_counter_ns()
    var _ns_kasiski_distance_gcd = Float64(_t1_kasiski_distance_gcd - _t0_kasiski_distance_gcd) / Float64(N)
    print("MOJO_TIMING cryptanalysis::kasiski_distance_gcd", _ns_kasiski_distance_gcd, _acc_kasiski_distance_gcd)
    var _acc_caesar_decrypt_score: Float64 = 0.0
    var _t0_caesar_decrypt_score = perf_counter_ns()
    for _ in range(N):
        _acc_caesar_decrypt_score += caesar_decrypt_score(5, 0.5, 0.5)
    var _t1_caesar_decrypt_score = perf_counter_ns()
    var _ns_caesar_decrypt_score = Float64(_t1_caesar_decrypt_score - _t0_caesar_decrypt_score) / Float64(N)
    print("MOJO_TIMING cryptanalysis::caesar_decrypt_score", _ns_caesar_decrypt_score, _acc_caesar_decrypt_score)
    var _acc_hamming_distance_bytes: Float64 = 0.0
    var _t0_hamming_distance_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_hamming_distance_bytes += Float64(hamming_distance_bytes(5, 5))
    var _t1_hamming_distance_bytes = perf_counter_ns()
    var _ns_hamming_distance_bytes = Float64(_t1_hamming_distance_bytes - _t0_hamming_distance_bytes) / Float64(N)
    print("MOJO_TIMING cryptanalysis::hamming_distance_bytes", _ns_hamming_distance_bytes, _acc_hamming_distance_bytes)
    var _acc_entropy_bits_2: Float64 = 0.0
    var _t0_entropy_bits_2 = perf_counter_ns()
    for _ in range(N):
        _acc_entropy_bits_2 += entropy_bits_2(0.5, 0.5)
    var _t1_entropy_bits_2 = perf_counter_ns()
    var _ns_entropy_bits_2 = Float64(_t1_entropy_bits_2 - _t0_entropy_bits_2) / Float64(N)
    print("MOJO_TIMING cryptanalysis::entropy_bits_2", _ns_entropy_bits_2, _acc_entropy_bits_2)
    var _acc_entropy_bits_4: Float64 = 0.0
    var _t0_entropy_bits_4 = perf_counter_ns()
    for _ in range(N):
        _acc_entropy_bits_4 += entropy_bits_4(0.5, 0.5, 0.5, 0.5)
    var _t1_entropy_bits_4 = perf_counter_ns()
    var _ns_entropy_bits_4 = Float64(_t1_entropy_bits_4 - _t0_entropy_bits_4) / Float64(N)
    print("MOJO_TIMING cryptanalysis::entropy_bits_4", _ns_entropy_bits_4, _acc_entropy_bits_4)
    var _acc_brute_force_time_estimate: Float64 = 0.0
    var _t0_brute_force_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_brute_force_time_estimate += brute_force_time_estimate(5, 0.5)
    var _t1_brute_force_time_estimate = perf_counter_ns()
    var _ns_brute_force_time_estimate = Float64(_t1_brute_force_time_estimate - _t0_brute_force_time_estimate) / Float64(N)
    print("MOJO_TIMING cryptanalysis::brute_force_time_estimate", _ns_brute_force_time_estimate, _acc_brute_force_time_estimate)
    var _acc_avalanche_effect: Float64 = 0.0
    var _t0_avalanche_effect = perf_counter_ns()
    for _ in range(N):
        _acc_avalanche_effect += avalanche_effect(5, 5)
    var _t1_avalanche_effect = perf_counter_ns()
    var _ns_avalanche_effect = Float64(_t1_avalanche_effect - _t0_avalanche_effect) / Float64(N)
    print("MOJO_TIMING cryptanalysis::avalanche_effect", _ns_avalanche_effect, _acc_avalanche_effect)
