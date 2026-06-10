"""test_json_writer.mojo — auto-generated tests for json.writer."""
from std.math import isnan, isinf
from json.writer import json_escape_string, json_object_start, json_object_end, json_add_string, json_add_int, json_add_float, json_add_bool, json_add_null, json_add_array_float, json_add_raw

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

    _ = json_escape_string("test")
    passed += 1; print("  ✅ json.writer::json_escape_string")
    _ = json_object_start()
    passed += 1; print("  ✅ json.writer::json_object_start")
    _ = json_object_end("test")
    passed += 1; print("  ✅ json.writer::json_object_end")
    _ = json_add_string("test", "test", "test")
    passed += 1; print("  ✅ json.writer::json_add_string")
    _ = json_add_int("test", "test", 5)
    passed += 1; print("  ✅ json.writer::json_add_int")
    _ = json_add_float("test", "test", 0.5)
    passed += 1; print("  ✅ json.writer::json_add_float")
    _ = json_add_bool("test", "test", True)
    passed += 1; print("  ✅ json.writer::json_add_bool")
    _ = json_add_null("test", "test")
    passed += 1; print("  ✅ json.writer::json_add_null")
    _ = json_add_array_float("test", "test", _lf5)
    passed += 1; print("  ✅ json.writer::json_add_array_float")
    _ = json_add_raw("test", "test", "test")
    passed += 1; print("  ✅ json.writer::json_add_raw")

    print("  [json.writer] Passed:", passed, "Failed:", failed)
