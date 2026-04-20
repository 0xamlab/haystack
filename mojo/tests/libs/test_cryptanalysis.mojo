"""test_cryptanalysis.mojo — auto-generated tests for cryptanalysis library."""
from std.math import isnan, isinf
from cryptanalysis import frequency_score_2, index_of_coincidence_2, expected_ic_random, expected_ic_english, friedman_key_length, kasiski_distance_gcd, caesar_decrypt_score, hamming_distance_bytes, entropy_bits_2, entropy_bits_4, brute_force_time_estimate, avalanche_effect

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_frequency_score_2 = frequency_score_2(5, 5, 0.5, 0.5)
    if is_finite(_v_frequency_score_2): passed += 1; print("  ✅ cryptanalysis::frequency_score_2 =", _v_frequency_score_2)
    else: failed += 1; print("  ❌ cryptanalysis::frequency_score_2 → non-finite:", _v_frequency_score_2)
    var _v_index_of_coincidence_2 = index_of_coincidence_2(5, 5, 5)
    if is_finite(_v_index_of_coincidence_2): passed += 1; print("  ✅ cryptanalysis::index_of_coincidence_2 =", _v_index_of_coincidence_2)
    else: failed += 1; print("  ❌ cryptanalysis::index_of_coincidence_2 → non-finite:", _v_index_of_coincidence_2)
    var _v_expected_ic_random = expected_ic_random(5)
    if is_finite(_v_expected_ic_random): passed += 1; print("  ✅ cryptanalysis::expected_ic_random =", _v_expected_ic_random)
    else: failed += 1; print("  ❌ cryptanalysis::expected_ic_random → non-finite:", _v_expected_ic_random)
    var _v_expected_ic_english = expected_ic_english()
    if is_finite(_v_expected_ic_english): passed += 1; print("  ✅ cryptanalysis::expected_ic_english =", _v_expected_ic_english)
    else: failed += 1; print("  ❌ cryptanalysis::expected_ic_english → non-finite:", _v_expected_ic_english)
    var _v_friedman_key_length = friedman_key_length(0.5, 5)
    if is_finite(_v_friedman_key_length): passed += 1; print("  ✅ cryptanalysis::friedman_key_length =", _v_friedman_key_length)
    else: failed += 1; print("  ❌ cryptanalysis::friedman_key_length → non-finite:", _v_friedman_key_length)
    _ = kasiski_distance_gcd(5, 5)
    passed += 1; print("  ✅ cryptanalysis::kasiski_distance_gcd")
    var _v_caesar_decrypt_score = caesar_decrypt_score(5, 0.5, 0.5)
    if is_finite(_v_caesar_decrypt_score): passed += 1; print("  ✅ cryptanalysis::caesar_decrypt_score =", _v_caesar_decrypt_score)
    else: failed += 1; print("  ❌ cryptanalysis::caesar_decrypt_score → non-finite:", _v_caesar_decrypt_score)
    _ = hamming_distance_bytes(5, 5)
    passed += 1; print("  ✅ cryptanalysis::hamming_distance_bytes")
    var _v_entropy_bits_2 = entropy_bits_2(0.5, 0.5)
    if is_finite(_v_entropy_bits_2): passed += 1; print("  ✅ cryptanalysis::entropy_bits_2 =", _v_entropy_bits_2)
    else: failed += 1; print("  ❌ cryptanalysis::entropy_bits_2 → non-finite:", _v_entropy_bits_2)
    var _v_entropy_bits_4 = entropy_bits_4(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_entropy_bits_4): passed += 1; print("  ✅ cryptanalysis::entropy_bits_4 =", _v_entropy_bits_4)
    else: failed += 1; print("  ❌ cryptanalysis::entropy_bits_4 → non-finite:", _v_entropy_bits_4)
    var _v_brute_force_time_estimate = brute_force_time_estimate(5, 0.5)
    if is_finite(_v_brute_force_time_estimate): passed += 1; print("  ✅ cryptanalysis::brute_force_time_estimate =", _v_brute_force_time_estimate)
    else: failed += 1; print("  ❌ cryptanalysis::brute_force_time_estimate → non-finite:", _v_brute_force_time_estimate)
    var _v_avalanche_effect = avalanche_effect(5, 5)
    if is_finite(_v_avalanche_effect): passed += 1; print("  ✅ cryptanalysis::avalanche_effect =", _v_avalanche_effect)
    else: failed += 1; print("  ❌ cryptanalysis::avalanche_effect → non-finite:", _v_avalanche_effect)

    print("  [cryptanalysis] Passed:", passed, "Failed:", failed)
