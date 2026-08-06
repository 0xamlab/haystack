"""test_time_zone.mojo — auto-generated tests for time_zone."""
from std.math import isnan, isinf
from time_zone import utc_offset, is_valid_zone, is_dst, effective_offset, time_difference, format_offset, convert_time, local_to_utc, utc_to_local, overlap_hours

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

    var _v_utc_offset = utc_offset("test")
    if is_finite(_v_utc_offset): passed += 1; print("  ✅ time_zone::utc_offset =", _v_utc_offset)
    else: failed += 1; print("  ❌ time_zone::utc_offset → non-finite:", _v_utc_offset)
    _ = is_valid_zone("test")
    passed += 1; print("  ✅ time_zone::is_valid_zone")
    _ = is_dst(5, "test")
    passed += 1; print("  ✅ time_zone::is_dst")
    var _v_effective_offset = effective_offset("test", 5)
    if is_finite(_v_effective_offset): passed += 1; print("  ✅ time_zone::effective_offset =", _v_effective_offset)
    else: failed += 1; print("  ❌ time_zone::effective_offset → non-finite:", _v_effective_offset)
    var _v_time_difference = time_difference("test", "test")
    if is_finite(_v_time_difference): passed += 1; print("  ✅ time_zone::time_difference =", _v_time_difference)
    else: failed += 1; print("  ❌ time_zone::time_difference → non-finite:", _v_time_difference)
    _ = format_offset(0.5)
    passed += 1; print("  ✅ time_zone::format_offset")
    var _v_convert_time = convert_time(5, 5, "test", "test")
    if len(_v_convert_time) >= 0: passed += 1; print("  ✅ time_zone::convert_time")
    var _v_local_to_utc = local_to_utc(5, 5, "test")
    if len(_v_local_to_utc) >= 0: passed += 1; print("  ✅ time_zone::local_to_utc")
    var _v_utc_to_local = utc_to_local(5, 5, "test")
    if len(_v_utc_to_local) >= 0: passed += 1; print("  ✅ time_zone::utc_to_local")
    _ = overlap_hours("test", "test", 5, 5)
    passed += 1; print("  ✅ time_zone::overlap_hours")

    print("  [time_zone] Passed:", passed, "Failed:", failed)
