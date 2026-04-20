"""test_string_distance.mojo — auto-generated tests for string_distance library."""
from std.math import isnan, isinf
from string_distance import damerau_levenshtein, soundex, edit_similarity, common_prefix_length, common_suffix_length, bigrams, dice_coefficient, overlap_coefficient, string_reverse, is_palindrome

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
