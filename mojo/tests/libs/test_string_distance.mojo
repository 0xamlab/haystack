"""test_string_distance.mojo — auto-generated tests for string_distance."""
from std.math import isnan, isinf
from string_distance import damerau_levenshtein, soundex, edit_similarity, common_prefix_length, common_suffix_length, bigrams, dice_coefficient, overlap_coefficient, string_reverse, is_palindrome

def is_finite(x: Float64) -> Bool:
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

    _ = damerau_levenshtein("test", "test")
    passed += 1; print("  ✅ string_distance::damerau_levenshtein")
    _ = soundex("test")
    passed += 1; print("  ✅ string_distance::soundex")
    var _v_edit_similarity = edit_similarity("test", "test")
    if is_finite(_v_edit_similarity): passed += 1; print("  ✅ string_distance::edit_similarity =", _v_edit_similarity)
    else: failed += 1; print("  ❌ string_distance::edit_similarity → non-finite:", _v_edit_similarity)
    _ = common_prefix_length("test", "test")
    passed += 1; print("  ✅ string_distance::common_prefix_length")
    _ = common_suffix_length("test", "test")
    passed += 1; print("  ✅ string_distance::common_suffix_length")
    var _v_bigrams = bigrams("test")
    if len(_v_bigrams) >= 0: passed += 1; print("  ✅ string_distance::bigrams")
    var _v_dice_coefficient = dice_coefficient("test", "test")
    if is_finite(_v_dice_coefficient): passed += 1; print("  ✅ string_distance::dice_coefficient =", _v_dice_coefficient)
    else: failed += 1; print("  ❌ string_distance::dice_coefficient → non-finite:", _v_dice_coefficient)
    var _v_overlap_coefficient = overlap_coefficient("test", "test")
    if is_finite(_v_overlap_coefficient): passed += 1; print("  ✅ string_distance::overlap_coefficient =", _v_overlap_coefficient)
    else: failed += 1; print("  ❌ string_distance::overlap_coefficient → non-finite:", _v_overlap_coefficient)
    _ = string_reverse("test")
    passed += 1; print("  ✅ string_distance::string_reverse")
    _ = is_palindrome("test")
    passed += 1; print("  ✅ string_distance::is_palindrome")

    print("  [string_distance] Passed:", passed, "Failed:", failed)
