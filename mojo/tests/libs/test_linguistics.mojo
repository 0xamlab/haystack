"""test_linguistics.mojo — auto-generated tests for linguistics library."""
from std.math import isnan, isinf
from linguistics import type_token_ratio, hapax_legomena_ratio, yules_k, heaps_law, zipfs_frequency, flesch_reading_ease, flesch_kincaid_grade, gunning_fog_index, automated_readability_index, coleman_liau_index, lexical_density, mean_word_length

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

    var _v_type_token_ratio = type_token_ratio(0.5, 0.5)
    if is_finite(_v_type_token_ratio): passed += 1; print("  ✅ linguistics::type_token_ratio =", _v_type_token_ratio)
    else: failed += 1; print("  ❌ linguistics::type_token_ratio → non-finite:", _v_type_token_ratio)
    var _v_hapax_legomena_ratio = hapax_legomena_ratio(0.5, 0.5)
    if is_finite(_v_hapax_legomena_ratio): passed += 1; print("  ✅ linguistics::hapax_legomena_ratio =", _v_hapax_legomena_ratio)
    else: failed += 1; print("  ❌ linguistics::hapax_legomena_ratio → non-finite:", _v_hapax_legomena_ratio)
    var _v_yules_k = yules_k(0.5, 0.5)
    if is_finite(_v_yules_k): passed += 1; print("  ✅ linguistics::yules_k =", _v_yules_k)
    else: failed += 1; print("  ❌ linguistics::yules_k → non-finite:", _v_yules_k)
    var _v_heaps_law = heaps_law(0.5, 0.5, 0.5)
    if is_finite(_v_heaps_law): passed += 1; print("  ✅ linguistics::heaps_law =", _v_heaps_law)
    else: failed += 1; print("  ❌ linguistics::heaps_law → non-finite:", _v_heaps_law)
    var _v_zipfs_frequency = zipfs_frequency(0.5, 0.5, 0.5)
    if is_finite(_v_zipfs_frequency): passed += 1; print("  ✅ linguistics::zipfs_frequency =", _v_zipfs_frequency)
    else: failed += 1; print("  ❌ linguistics::zipfs_frequency → non-finite:", _v_zipfs_frequency)
    var _v_flesch_reading_ease = flesch_reading_ease(0.5, 0.5, 0.5)
    if is_finite(_v_flesch_reading_ease): passed += 1; print("  ✅ linguistics::flesch_reading_ease =", _v_flesch_reading_ease)
    else: failed += 1; print("  ❌ linguistics::flesch_reading_ease → non-finite:", _v_flesch_reading_ease)
    var _v_flesch_kincaid_grade = flesch_kincaid_grade(0.5, 0.5, 0.5)
    if is_finite(_v_flesch_kincaid_grade): passed += 1; print("  ✅ linguistics::flesch_kincaid_grade =", _v_flesch_kincaid_grade)
    else: failed += 1; print("  ❌ linguistics::flesch_kincaid_grade → non-finite:", _v_flesch_kincaid_grade)
    var _v_gunning_fog_index = gunning_fog_index(0.5, 0.5, 0.5)
    if is_finite(_v_gunning_fog_index): passed += 1; print("  ✅ linguistics::gunning_fog_index =", _v_gunning_fog_index)
    else: failed += 1; print("  ❌ linguistics::gunning_fog_index → non-finite:", _v_gunning_fog_index)
    var _v_automated_readability_index = automated_readability_index(0.5, 0.5, 0.5)
    if is_finite(_v_automated_readability_index): passed += 1; print("  ✅ linguistics::automated_readability_index =", _v_automated_readability_index)
    else: failed += 1; print("  ❌ linguistics::automated_readability_index → non-finite:", _v_automated_readability_index)
    var _v_coleman_liau_index = coleman_liau_index(0.5, 0.5)
    if is_finite(_v_coleman_liau_index): passed += 1; print("  ✅ linguistics::coleman_liau_index =", _v_coleman_liau_index)
    else: failed += 1; print("  ❌ linguistics::coleman_liau_index → non-finite:", _v_coleman_liau_index)
    var _v_lexical_density = lexical_density(0.5, 0.5)
    if is_finite(_v_lexical_density): passed += 1; print("  ✅ linguistics::lexical_density =", _v_lexical_density)
    else: failed += 1; print("  ❌ linguistics::lexical_density → non-finite:", _v_lexical_density)
    var _v_mean_word_length = mean_word_length(0.5, 0.5)
    if is_finite(_v_mean_word_length): passed += 1; print("  ✅ linguistics::mean_word_length =", _v_mean_word_length)
    else: failed += 1; print("  ❌ linguistics::mean_word_length → non-finite:", _v_mean_word_length)

    print("  [linguistics] Passed:", passed, "Failed:", failed)
