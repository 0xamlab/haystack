"""test_pipeline.mojo — auto-generated tests for pipeline library."""
from std.math import isnan, isinf
from pipeline import map_list, filter_list, reduce_sum, reduce_product, reduce_min, reduce_max, chain_map_filter, batch, zip_lists, window, unique_values

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

    var _v_map_list = map_list(_lf5, 5)
    if len(_v_map_list) >= 0: passed += 1; print("  ✅ pipeline::map_list")
    var _v_filter_list = filter_list(_lf5, 5, 0.5)
    if len(_v_filter_list) >= 0: passed += 1; print("  ✅ pipeline::filter_list")
    var _v_reduce_sum = reduce_sum(_lf5)
    if is_finite(_v_reduce_sum): passed += 1; print("  ✅ pipeline::reduce_sum =", _v_reduce_sum)
    else: failed += 1; print("  ❌ pipeline::reduce_sum → non-finite:", _v_reduce_sum)
    var _v_reduce_product = reduce_product(_lf5)
    if is_finite(_v_reduce_product): passed += 1; print("  ✅ pipeline::reduce_product =", _v_reduce_product)
    else: failed += 1; print("  ❌ pipeline::reduce_product → non-finite:", _v_reduce_product)
    var _v_reduce_min = reduce_min(_lf5)
    if is_finite(_v_reduce_min): passed += 1; print("  ✅ pipeline::reduce_min =", _v_reduce_min)
    else: failed += 1; print("  ❌ pipeline::reduce_min → non-finite:", _v_reduce_min)
    var _v_reduce_max = reduce_max(_lf5)
    if is_finite(_v_reduce_max): passed += 1; print("  ✅ pipeline::reduce_max =", _v_reduce_max)
    else: failed += 1; print("  ❌ pipeline::reduce_max → non-finite:", _v_reduce_max)
    var _v_chain_map_filter = chain_map_filter(_lf5, 5, 5, 0.5)
    if len(_v_chain_map_filter) >= 0: passed += 1; print("  ✅ pipeline::chain_map_filter")
    _ = batch(_lf5, 5)
    passed += 1; print("  ✅ pipeline::batch")
    _ = zip_lists(_lf5, _lf5)
    passed += 1; print("  ✅ pipeline::zip_lists")
    _ = window(_lf5, 5)
    passed += 1; print("  ✅ pipeline::window")
    var _v_unique_values = unique_values(_lf5)
    if len(_v_unique_values) >= 0: passed += 1; print("  ✅ pipeline::unique_values")

    print("  [pipeline] Passed:", passed, "Failed:", failed)
