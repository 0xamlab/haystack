"""test_text_fuzzy.mojo — auto-generated tests for text.fuzzy."""
from std.math import isnan, isinf
from text.fuzzy import levenshtein_distance, normalized_levenshtein, jaro_similarity, jaro_winkler_similarity, hamming_distance, longest_common_subsequence, fuzzy_ratio

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    _ = levenshtein_distance("test", "test")
    passed += 1; print("  ✅ text.fuzzy::levenshtein_distance")
    var _v_normalized_levenshtein = normalized_levenshtein("test", "test")
    if is_finite(_v_normalized_levenshtein): passed += 1; print("  ✅ text.fuzzy::normalized_levenshtein =", _v_normalized_levenshtein)
    else: failed += 1; print("  ❌ text.fuzzy::normalized_levenshtein → non-finite:", _v_normalized_levenshtein)
    var _v_jaro_similarity = jaro_similarity("test", "test")
    if is_finite(_v_jaro_similarity): passed += 1; print("  ✅ text.fuzzy::jaro_similarity =", _v_jaro_similarity)
    else: failed += 1; print("  ❌ text.fuzzy::jaro_similarity → non-finite:", _v_jaro_similarity)
    var _v_jaro_winkler_similarity = jaro_winkler_similarity("test", "test", 0.5)
    if is_finite(_v_jaro_winkler_similarity): passed += 1; print("  ✅ text.fuzzy::jaro_winkler_similarity =", _v_jaro_winkler_similarity)
    else: failed += 1; print("  ❌ text.fuzzy::jaro_winkler_similarity → non-finite:", _v_jaro_winkler_similarity)
    _ = hamming_distance("test", "test")
    passed += 1; print("  ✅ text.fuzzy::hamming_distance")
    _ = longest_common_subsequence("test", "test")
    passed += 1; print("  ✅ text.fuzzy::longest_common_subsequence")
    var _v_fuzzy_ratio = fuzzy_ratio("test", "test")
    if is_finite(_v_fuzzy_ratio): passed += 1; print("  ✅ text.fuzzy::fuzzy_ratio =", _v_fuzzy_ratio)
    else: failed += 1; print("  ❌ text.fuzzy::fuzzy_ratio → non-finite:", _v_fuzzy_ratio)

    print("  [text.fuzzy] Passed:", passed, "Failed:", failed)
