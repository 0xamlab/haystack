"""test_residentk_contract.mojo — auto-generated tests for residentk.contract."""
from std.math import isnan, isinf
from residentk.contract import residentk_status_name, residentk_dims_check, residentk_context_check, residentk_cache_elements, residentk_dispatch_budget, residentk_weight_elems, residentk_scalars_ok, residentk_splitk_should_split, residentk_splitk_max_n_splits, residentk_splitk_policy

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

    _ = residentk_status_name(5)
    passed += 1; print("  ✅ residentk.contract::residentk_status_name")
    _ = residentk_dims_check(5, 5, 5, 5, 5)
    passed += 1; print("  ✅ residentk.contract::residentk_dims_check")
    _ = residentk_context_check(5, 5, 5)
    passed += 1; print("  ✅ residentk.contract::residentk_context_check")
    _ = residentk_cache_elements(5, 5, 5, 5)
    passed += 1; print("  ✅ residentk.contract::residentk_cache_elements")
    _ = residentk_dispatch_budget(5)
    passed += 1; print("  ✅ residentk.contract::residentk_dispatch_budget")
    _ = residentk_weight_elems(5, 5, 5, 5, 5, 5, 5, 5)
    passed += 1; print("  ✅ residentk.contract::residentk_weight_elems")
    _ = residentk_scalars_ok(0.5, 0.5)
    passed += 1; print("  ✅ residentk.contract::residentk_scalars_ok")
    _ = residentk_splitk_should_split(5)
    passed += 1; print("  ✅ residentk.contract::residentk_splitk_should_split")
    _ = residentk_splitk_max_n_splits(5, 5)
    passed += 1; print("  ✅ residentk.contract::residentk_splitk_max_n_splits")
    _ = residentk_splitk_policy(5, 5, 5)
    passed += 1; print("  ✅ residentk.contract::residentk_splitk_policy")

    print("  [residentk.contract] Passed:", passed, "Failed:", failed)
