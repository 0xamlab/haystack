"""bench_regression_tree.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from regression_tree import mse_reduction, best_split, build_tree, RegressionTree
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

    var _acc_mse_reduction: Float64 = 0.0
    var _t0_mse_reduction = perf_counter_ns()
    for _ in range(N):
        _acc_mse_reduction += mse_reduction(_lf5, _li5, _li5)
    var _t1_mse_reduction = perf_counter_ns()
    var _ns_mse_reduction = Float64(_t1_mse_reduction - _t0_mse_reduction) / Float64(N)
    print("MOJO_TIMING regression_tree::mse_reduction", _ns_mse_reduction, _acc_mse_reduction)
    var _acc_best_split: Float64 = 0.0
    var _t0_best_split = perf_counter_ns()
    for _ in range(N):
        var _r_best_split = best_split([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _li5)
        _acc_best_split += Float64(len(_r_best_split))
    var _t1_best_split = perf_counter_ns()
    var _ns_best_split = Float64(_t1_best_split - _t0_best_split) / Float64(N)
    print("MOJO_TIMING regression_tree::best_split", _ns_best_split, _acc_best_split)
    var _keeper_build_tree = List[RegressionTree]()
    _keeper_build_tree.append(build_tree([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5, 5))
    var _acc_build_tree: Float64 = 0.0
    var _t0_build_tree = perf_counter_ns()
    for _ in range(N):
        _keeper_build_tree[0] = build_tree([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5, 5)
        _acc_build_tree += Float64(len(_keeper_build_tree))
    var _t1_build_tree = perf_counter_ns()
    var _ns_build_tree = Float64(_t1_build_tree - _t0_build_tree) / Float64(N)
    print("MOJO_TIMING regression_tree::build_tree", _ns_build_tree, _acc_build_tree)
