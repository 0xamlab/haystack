"""bench_decision_analysis.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from decision_analysis import expected_value, expected_utility, decision_matrix_best, minimax_regret, hurwicz_criterion, value_of_perfect_info, sensitivity_range, maximin, maximax, laplace_criterion
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

    var _acc_expected_value: Float64 = 0.0
    var _t0_expected_value = perf_counter_ns()
    for _ in range(N):
        _acc_expected_value += expected_value(_lf5, _lf5)
    var _t1_expected_value = perf_counter_ns()
    var _ns_expected_value = Float64(_t1_expected_value - _t0_expected_value) / Float64(N)
    print("MOJO_TIMING decision_analysis::expected_value", _ns_expected_value, _acc_expected_value)
    var _acc_expected_utility: Float64 = 0.0
    var _t0_expected_utility = perf_counter_ns()
    for _ in range(N):
        _acc_expected_utility += expected_utility(_lf5, _lf5, 0.5)
    var _t1_expected_utility = perf_counter_ns()
    var _ns_expected_utility = Float64(_t1_expected_utility - _t0_expected_utility) / Float64(N)
    print("MOJO_TIMING decision_analysis::expected_utility", _ns_expected_utility, _acc_expected_utility)
    var _acc_decision_matrix_best: Float64 = 0.0
    var _t0_decision_matrix_best = perf_counter_ns()
    for _ in range(N):
        _acc_decision_matrix_best += Float64(decision_matrix_best([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5))
    var _t1_decision_matrix_best = perf_counter_ns()
    var _ns_decision_matrix_best = Float64(_t1_decision_matrix_best - _t0_decision_matrix_best) / Float64(N)
    print("MOJO_TIMING decision_analysis::decision_matrix_best", _ns_decision_matrix_best, _acc_decision_matrix_best)
    var _acc_minimax_regret: Float64 = 0.0
    var _t0_minimax_regret = perf_counter_ns()
    for _ in range(N):
        _acc_minimax_regret += Float64(minimax_regret([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_minimax_regret = perf_counter_ns()
    var _ns_minimax_regret = Float64(_t1_minimax_regret - _t0_minimax_regret) / Float64(N)
    print("MOJO_TIMING decision_analysis::minimax_regret", _ns_minimax_regret, _acc_minimax_regret)
    var _acc_hurwicz_criterion: Float64 = 0.0
    var _t0_hurwicz_criterion = perf_counter_ns()
    for _ in range(N):
        _acc_hurwicz_criterion += Float64(hurwicz_criterion([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5))
    var _t1_hurwicz_criterion = perf_counter_ns()
    var _ns_hurwicz_criterion = Float64(_t1_hurwicz_criterion - _t0_hurwicz_criterion) / Float64(N)
    print("MOJO_TIMING decision_analysis::hurwicz_criterion", _ns_hurwicz_criterion, _acc_hurwicz_criterion)
    var _acc_value_of_perfect_info: Float64 = 0.0
    var _t0_value_of_perfect_info = perf_counter_ns()
    for _ in range(N):
        _acc_value_of_perfect_info += value_of_perfect_info([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _t1_value_of_perfect_info = perf_counter_ns()
    var _ns_value_of_perfect_info = Float64(_t1_value_of_perfect_info - _t0_value_of_perfect_info) / Float64(N)
    print("MOJO_TIMING decision_analysis::value_of_perfect_info", _ns_value_of_perfect_info, _acc_value_of_perfect_info)
    var _acc_sensitivity_range: Float64 = 0.0
    var _t0_sensitivity_range = perf_counter_ns()
    for _ in range(N):
        var _r_sensitivity_range = sensitivity_range([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_sensitivity_range += Float64(len(_r_sensitivity_range))
    var _t1_sensitivity_range = perf_counter_ns()
    var _ns_sensitivity_range = Float64(_t1_sensitivity_range - _t0_sensitivity_range) / Float64(N)
    print("MOJO_TIMING decision_analysis::sensitivity_range", _ns_sensitivity_range, _acc_sensitivity_range)
    var _acc_maximin: Float64 = 0.0
    var _t0_maximin = perf_counter_ns()
    for _ in range(N):
        _acc_maximin += Float64(maximin([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_maximin = perf_counter_ns()
    var _ns_maximin = Float64(_t1_maximin - _t0_maximin) / Float64(N)
    print("MOJO_TIMING decision_analysis::maximin", _ns_maximin, _acc_maximin)
    var _acc_maximax: Float64 = 0.0
    var _t0_maximax = perf_counter_ns()
    for _ in range(N):
        _acc_maximax += Float64(maximax([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_maximax = perf_counter_ns()
    var _ns_maximax = Float64(_t1_maximax - _t0_maximax) / Float64(N)
    print("MOJO_TIMING decision_analysis::maximax", _ns_maximax, _acc_maximax)
    var _acc_laplace_criterion: Float64 = 0.0
    var _t0_laplace_criterion = perf_counter_ns()
    for _ in range(N):
        _acc_laplace_criterion += Float64(laplace_criterion([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_laplace_criterion = perf_counter_ns()
    var _ns_laplace_criterion = Float64(_t1_laplace_criterion - _t0_laplace_criterion) / Float64(N)
    print("MOJO_TIMING decision_analysis::laplace_criterion", _ns_laplace_criterion, _acc_laplace_criterion)
