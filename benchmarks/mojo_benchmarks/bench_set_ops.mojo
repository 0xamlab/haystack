"""bench_set_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from set_ops import set_union, set_intersection, set_difference, set_symmetric_difference, is_subset, is_superset, set_equals, power_set_size, jaccard_index, to_set, set_contains, set_cardinality
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_set_union: Float64 = 0.0
    var _t0_set_union = perf_counter_ns()
    for _ in range(N):
        var _r_set_union = set_union(_li5, _li5)
        _acc_set_union += Float64(len(_r_set_union))
    var _t1_set_union = perf_counter_ns()
    var _ns_set_union = Float64(_t1_set_union - _t0_set_union) / Float64(N)
    print("MOJO_TIMING set_ops::set_union", _ns_set_union, _acc_set_union)
    var _acc_set_intersection: Float64 = 0.0
    var _t0_set_intersection = perf_counter_ns()
    for _ in range(N):
        var _r_set_intersection = set_intersection(_li5, _li5)
        _acc_set_intersection += Float64(len(_r_set_intersection))
    var _t1_set_intersection = perf_counter_ns()
    var _ns_set_intersection = Float64(_t1_set_intersection - _t0_set_intersection) / Float64(N)
    print("MOJO_TIMING set_ops::set_intersection", _ns_set_intersection, _acc_set_intersection)
    var _acc_set_difference: Float64 = 0.0
    var _t0_set_difference = perf_counter_ns()
    for _ in range(N):
        var _r_set_difference = set_difference(_li5, _li5)
        _acc_set_difference += Float64(len(_r_set_difference))
    var _t1_set_difference = perf_counter_ns()
    var _ns_set_difference = Float64(_t1_set_difference - _t0_set_difference) / Float64(N)
    print("MOJO_TIMING set_ops::set_difference", _ns_set_difference, _acc_set_difference)
    var _acc_set_symmetric_difference: Float64 = 0.0
    var _t0_set_symmetric_difference = perf_counter_ns()
    for _ in range(N):
        var _r_set_symmetric_difference = set_symmetric_difference(_li5, _li5)
        _acc_set_symmetric_difference += Float64(len(_r_set_symmetric_difference))
    var _t1_set_symmetric_difference = perf_counter_ns()
    var _ns_set_symmetric_difference = Float64(_t1_set_symmetric_difference - _t0_set_symmetric_difference) / Float64(N)
    print("MOJO_TIMING set_ops::set_symmetric_difference", _ns_set_symmetric_difference, _acc_set_symmetric_difference)
    var _acc_is_subset: Float64 = 0.0
    var _t0_is_subset = perf_counter_ns()
    for _ in range(N):
        _acc_is_subset += Float64(is_subset(_li5, _li5))
    var _t1_is_subset = perf_counter_ns()
    var _ns_is_subset = Float64(_t1_is_subset - _t0_is_subset) / Float64(N)
    print("MOJO_TIMING set_ops::is_subset", _ns_is_subset, _acc_is_subset)
    var _acc_is_superset: Float64 = 0.0
    var _t0_is_superset = perf_counter_ns()
    for _ in range(N):
        _acc_is_superset += Float64(is_superset(_li5, _li5))
    var _t1_is_superset = perf_counter_ns()
    var _ns_is_superset = Float64(_t1_is_superset - _t0_is_superset) / Float64(N)
    print("MOJO_TIMING set_ops::is_superset", _ns_is_superset, _acc_is_superset)
    var _acc_set_equals: Float64 = 0.0
    var _t0_set_equals = perf_counter_ns()
    for _ in range(N):
        _acc_set_equals += Float64(set_equals(_li5, _li5))
    var _t1_set_equals = perf_counter_ns()
    var _ns_set_equals = Float64(_t1_set_equals - _t0_set_equals) / Float64(N)
    print("MOJO_TIMING set_ops::set_equals", _ns_set_equals, _acc_set_equals)
    var _acc_power_set_size: Float64 = 0.0
    var _t0_power_set_size = perf_counter_ns()
    for _ in range(N):
        _acc_power_set_size += Float64(power_set_size(5))
    var _t1_power_set_size = perf_counter_ns()
    var _ns_power_set_size = Float64(_t1_power_set_size - _t0_power_set_size) / Float64(N)
    print("MOJO_TIMING set_ops::power_set_size", _ns_power_set_size, _acc_power_set_size)
    var _acc_jaccard_index: Float64 = 0.0
    var _t0_jaccard_index = perf_counter_ns()
    for _ in range(N):
        _acc_jaccard_index += jaccard_index(_li5, _li5)
    var _t1_jaccard_index = perf_counter_ns()
    var _ns_jaccard_index = Float64(_t1_jaccard_index - _t0_jaccard_index) / Float64(N)
    print("MOJO_TIMING set_ops::jaccard_index", _ns_jaccard_index, _acc_jaccard_index)
    var _acc_to_set: Float64 = 0.0
    var _t0_to_set = perf_counter_ns()
    for _ in range(N):
        var _r_to_set = to_set(_li5)
        _acc_to_set += Float64(len(_r_to_set))
    var _t1_to_set = perf_counter_ns()
    var _ns_to_set = Float64(_t1_to_set - _t0_to_set) / Float64(N)
    print("MOJO_TIMING set_ops::to_set", _ns_to_set, _acc_to_set)
    var _acc_set_contains: Float64 = 0.0
    var _t0_set_contains = perf_counter_ns()
    for _ in range(N):
        _acc_set_contains += Float64(set_contains(_li5, 5))
    var _t1_set_contains = perf_counter_ns()
    var _ns_set_contains = Float64(_t1_set_contains - _t0_set_contains) / Float64(N)
    print("MOJO_TIMING set_ops::set_contains", _ns_set_contains, _acc_set_contains)
    var _acc_set_cardinality: Float64 = 0.0
    var _t0_set_cardinality = perf_counter_ns()
    for _ in range(N):
        _acc_set_cardinality += Float64(set_cardinality(_li5))
    var _t1_set_cardinality = perf_counter_ns()
    var _ns_set_cardinality = Float64(_t1_set_cardinality - _t0_set_cardinality) / Float64(N)
    print("MOJO_TIMING set_ops::set_cardinality", _ns_set_cardinality, _acc_set_cardinality)
