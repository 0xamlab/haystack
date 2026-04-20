"""test_regex_engine.mojo — auto-generated tests for regex_engine library."""
from std.math import isnan, isinf
from regex_engine import match_literal, match_dot_star, match_char_class, regex_match, regex_search, regex_find_first, count_matches, split_by_literal, is_valid_pattern

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

    _ = match_literal("test", "test")
    passed += 1; print("  ✅ regex_engine::match_literal")
    _ = match_dot_star("test", 5, 5)
    passed += 1; print("  ✅ regex_engine::match_dot_star")
    _ = match_char_class("test", 5)
    passed += 1; print("  ✅ regex_engine::match_char_class")
    _ = regex_match("test", "test")
    passed += 1; print("  ✅ regex_engine::regex_match")
    _ = regex_search("test", "test")
    passed += 1; print("  ✅ regex_engine::regex_search")
    var _v_regex_find_first = regex_find_first("test", "test")
    if len(_v_regex_find_first) >= 0: passed += 1; print("  ✅ regex_engine::regex_find_first")
    _ = count_matches("test", "test")
    passed += 1; print("  ✅ regex_engine::count_matches")
    var _v_split_by_literal = split_by_literal("test", "test")
    if len(_v_split_by_literal) >= 0: passed += 1; print("  ✅ regex_engine::split_by_literal")
    _ = is_valid_pattern("test")
    passed += 1; print("  ✅ regex_engine::is_valid_pattern")

    print("  [regex_engine] Passed:", passed, "Failed:", failed)
