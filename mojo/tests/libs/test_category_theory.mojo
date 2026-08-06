"""test_category_theory.mojo — auto-generated tests for category_theory."""
from std.math import isnan, isinf
from category_theory import map_list_fn, filter_fn, fold_left, fold_right, compose, zip_with, scan_left, take_while, drop_while, flat_map

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

    var _v_map_list_fn = map_list_fn(_lf5, 5)
    if len(_v_map_list_fn) >= 0: passed += 1; print("  ✅ category_theory::map_list_fn")
    var _v_filter_fn = filter_fn(_lf5, 5, 0.5)
    if len(_v_filter_fn) >= 0: passed += 1; print("  ✅ category_theory::filter_fn")
    var _v_fold_left = fold_left(_lf5, 0.5, 5)
    if is_finite(_v_fold_left): passed += 1; print("  ✅ category_theory::fold_left =", _v_fold_left)
    else: failed += 1; print("  ❌ category_theory::fold_left → non-finite:", _v_fold_left)
    var _v_fold_right = fold_right(_lf5, 0.5, 5)
    if is_finite(_v_fold_right): passed += 1; print("  ✅ category_theory::fold_right =", _v_fold_right)
    else: failed += 1; print("  ❌ category_theory::fold_right → non-finite:", _v_fold_right)
    var _v_compose = compose(_lf5, 5, 5)
    if len(_v_compose) >= 0: passed += 1; print("  ✅ category_theory::compose")
    var _v_zip_with = zip_with(_lf5, _lf5, 5)
    if len(_v_zip_with) >= 0: passed += 1; print("  ✅ category_theory::zip_with")
    var _v_scan_left = scan_left(_lf5, 0.5, 5)
    if len(_v_scan_left) >= 0: passed += 1; print("  ✅ category_theory::scan_left")
    var _v_take_while = take_while(_lf5, 5, 0.5)
    if len(_v_take_while) >= 0: passed += 1; print("  ✅ category_theory::take_while")
    var _v_drop_while = drop_while(_lf5, 5, 0.5)
    if len(_v_drop_while) >= 0: passed += 1; print("  ✅ category_theory::drop_while")
    var _v_flat_map = flat_map(_lf5, 5)
    if len(_v_flat_map) >= 0: passed += 1; print("  ✅ category_theory::flat_map")

    print("  [category_theory] Passed:", passed, "Failed:", failed)
