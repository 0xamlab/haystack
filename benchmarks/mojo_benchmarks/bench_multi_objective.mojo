"""bench_multi_objective.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from multi_objective import is_dominated, pareto_front, weighted_score, normalize_objectives, ideal_point, nadir_point, topsis_rank
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

    var _acc_is_dominated: Float64 = 0.0
    var _t0_is_dominated = perf_counter_ns()
    for _ in range(N):
        _acc_is_dominated += Float64(is_dominated(_lf5, _lf5, _lb5))
    var _t1_is_dominated = perf_counter_ns()
    var _ns_is_dominated = Float64(_t1_is_dominated - _t0_is_dominated) / Float64(N)
    print("MOJO_TIMING multi_objective::is_dominated", _ns_is_dominated, _acc_is_dominated)
    var _acc_pareto_front: Float64 = 0.0
    var _t0_pareto_front = perf_counter_ns()
    for _ in range(N):
        var _r_pareto_front = pareto_front([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
        _acc_pareto_front += Float64(len(_r_pareto_front))
    var _t1_pareto_front = perf_counter_ns()
    var _ns_pareto_front = Float64(_t1_pareto_front - _t0_pareto_front) / Float64(N)
    print("MOJO_TIMING multi_objective::pareto_front", _ns_pareto_front, _acc_pareto_front)
    var _acc_weighted_score: Float64 = 0.0
    var _t0_weighted_score = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_score += weighted_score(_lf5, _lf5)
    var _t1_weighted_score = perf_counter_ns()
    var _ns_weighted_score = Float64(_t1_weighted_score - _t0_weighted_score) / Float64(N)
    print("MOJO_TIMING multi_objective::weighted_score", _ns_weighted_score, _acc_weighted_score)
    var _acc_normalize_objectives: Float64 = 0.0
    var _t0_normalize_objectives = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_objectives = normalize_objectives([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_normalize_objectives += Float64(len(_r_normalize_objectives))
    var _t1_normalize_objectives = perf_counter_ns()
    var _ns_normalize_objectives = Float64(_t1_normalize_objectives - _t0_normalize_objectives) / Float64(N)
    print("MOJO_TIMING multi_objective::normalize_objectives", _ns_normalize_objectives, _acc_normalize_objectives)
    var _acc_ideal_point: Float64 = 0.0
    var _t0_ideal_point = perf_counter_ns()
    for _ in range(N):
        var _r_ideal_point = ideal_point([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
        _acc_ideal_point += Float64(len(_r_ideal_point))
    var _t1_ideal_point = perf_counter_ns()
    var _ns_ideal_point = Float64(_t1_ideal_point - _t0_ideal_point) / Float64(N)
    print("MOJO_TIMING multi_objective::ideal_point", _ns_ideal_point, _acc_ideal_point)
    var _acc_nadir_point: Float64 = 0.0
    var _t0_nadir_point = perf_counter_ns()
    for _ in range(N):
        var _r_nadir_point = nadir_point([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
        _acc_nadir_point += Float64(len(_r_nadir_point))
    var _t1_nadir_point = perf_counter_ns()
    var _ns_nadir_point = Float64(_t1_nadir_point - _t0_nadir_point) / Float64(N)
    print("MOJO_TIMING multi_objective::nadir_point", _ns_nadir_point, _acc_nadir_point)
    var _acc_topsis_rank: Float64 = 0.0
    var _t0_topsis_rank = perf_counter_ns()
    for _ in range(N):
        var _r_topsis_rank = topsis_rank([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lb5)
        _acc_topsis_rank += Float64(len(_r_topsis_rank))
    var _t1_topsis_rank = perf_counter_ns()
    var _ns_topsis_rank = Float64(_t1_topsis_rank - _t0_topsis_rank) / Float64(N)
    print("MOJO_TIMING multi_objective::topsis_rank", _ns_topsis_rank, _acc_topsis_rank)
