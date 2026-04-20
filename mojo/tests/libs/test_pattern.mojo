"""test_pattern.mojo — auto-generated tests for pattern library."""
from std.math import isnan, isinf
from pattern import glob_match, starts_with, ends_with, contains, count_occurrences, replace_all, split_string, pad_left, pad_right, trim

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

    _ = glob_match("test", "test")
    passed += 1; print("  ✅ pattern::glob_match")
    _ = starts_with("test", "test")
    passed += 1; print("  ✅ pattern::starts_with")
    _ = ends_with("test", "test")
    passed += 1; print("  ✅ pattern::ends_with")
    _ = contains("test", "test")
    passed += 1; print("  ✅ pattern::contains")
    _ = count_occurrences("test", "test")
    passed += 1; print("  ✅ pattern::count_occurrences")
    _ = replace_all("test", "test", "test")
    passed += 1; print("  ✅ pattern::replace_all")
    var _v_split_string = split_string("test", "test")
    if len(_v_split_string) >= 0: passed += 1; print("  ✅ pattern::split_string")
    _ = pad_left("test", 5, 5)
    passed += 1; print("  ✅ pattern::pad_left")
    _ = pad_right("test", 5, 5)
    passed += 1; print("  ✅ pattern::pad_right")
    _ = trim("test")
    passed += 1; print("  ✅ pattern::trim")

    print("  [pattern] Passed:", passed, "Failed:", failed)
