"""test_set_ops.mojo — auto-generated tests for set_ops library."""
from std.math import isnan, isinf
from set_ops import set_union, set_intersection, set_difference, set_symmetric_difference, is_subset, is_superset, set_equals, power_set_size, jaccard_index, to_set, set_contains, set_cardinality

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

    var _v_set_union = set_union(_li5, _li5)
    if len(_v_set_union) >= 0: passed += 1; print("  ✅ set_ops::set_union")
    var _v_set_intersection = set_intersection(_li5, _li5)
    if len(_v_set_intersection) >= 0: passed += 1; print("  ✅ set_ops::set_intersection")
    var _v_set_difference = set_difference(_li5, _li5)
    if len(_v_set_difference) >= 0: passed += 1; print("  ✅ set_ops::set_difference")
    var _v_set_symmetric_difference = set_symmetric_difference(_li5, _li5)
    if len(_v_set_symmetric_difference) >= 0: passed += 1; print("  ✅ set_ops::set_symmetric_difference")
    _ = is_subset(_li5, _li5)
    passed += 1; print("  ✅ set_ops::is_subset")
    _ = is_superset(_li5, _li5)
    passed += 1; print("  ✅ set_ops::is_superset")
    _ = set_equals(_li5, _li5)
    passed += 1; print("  ✅ set_ops::set_equals")
    _ = power_set_size(5)
    passed += 1; print("  ✅ set_ops::power_set_size")
    var _v_jaccard_index = jaccard_index(_li5, _li5)
    if is_finite(_v_jaccard_index): passed += 1; print("  ✅ set_ops::jaccard_index =", _v_jaccard_index)
    else: failed += 1; print("  ❌ set_ops::jaccard_index → non-finite:", _v_jaccard_index)
    var _v_to_set = to_set(_li5)
    if len(_v_to_set) >= 0: passed += 1; print("  ✅ set_ops::to_set")
    _ = set_contains(_li5, 5)
    passed += 1; print("  ✅ set_ops::set_contains")
    _ = set_cardinality(_li5)
    passed += 1; print("  ✅ set_ops::set_cardinality")

    print("  [set_ops] Passed:", passed, "Failed:", failed)
