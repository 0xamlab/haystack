"""bench_game_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from game_theory import nash_2x2, minimax_value, dominated_strategy_check, expected_payoff, prisoners_dilemma_payoff, iterated_pd, shapley_value_3player, pareto_optimal_outcomes
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

    var _acc_nash_2x2: Float64 = 0.0
    var _t0_nash_2x2 = perf_counter_ns()
    for _ in range(N):
        var _r_nash_2x2 = nash_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_nash_2x2 += Float64(len(_r_nash_2x2))
    var _t1_nash_2x2 = perf_counter_ns()
    var _ns_nash_2x2 = Float64(_t1_nash_2x2 - _t0_nash_2x2) / Float64(N)
    print("MOJO_TIMING game_theory::nash_2x2", _ns_nash_2x2, _acc_nash_2x2)
    var _acc_minimax_value: Float64 = 0.0
    var _t0_minimax_value = perf_counter_ns()
    for _ in range(N):
        _acc_minimax_value += minimax_value([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_minimax_value = perf_counter_ns()
    var _ns_minimax_value = Float64(_t1_minimax_value - _t0_minimax_value) / Float64(N)
    print("MOJO_TIMING game_theory::minimax_value", _ns_minimax_value, _acc_minimax_value)
    var _acc_dominated_strategy_check: Float64 = 0.0
    var _t0_dominated_strategy_check = perf_counter_ns()
    for _ in range(N):
        var _r_dominated_strategy_check = dominated_strategy_check([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_dominated_strategy_check += Float64(len(_r_dominated_strategy_check))
    var _t1_dominated_strategy_check = perf_counter_ns()
    var _ns_dominated_strategy_check = Float64(_t1_dominated_strategy_check - _t0_dominated_strategy_check) / Float64(N)
    print("MOJO_TIMING game_theory::dominated_strategy_check", _ns_dominated_strategy_check, _acc_dominated_strategy_check)
    var _acc_expected_payoff: Float64 = 0.0
    var _t0_expected_payoff = perf_counter_ns()
    for _ in range(N):
        _acc_expected_payoff += expected_payoff([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5)
    var _t1_expected_payoff = perf_counter_ns()
    var _ns_expected_payoff = Float64(_t1_expected_payoff - _t0_expected_payoff) / Float64(N)
    print("MOJO_TIMING game_theory::expected_payoff", _ns_expected_payoff, _acc_expected_payoff)
    var _acc_prisoners_dilemma_payoff: Float64 = 0.0
    var _t0_prisoners_dilemma_payoff = perf_counter_ns()
    for _ in range(N):
        var _r_prisoners_dilemma_payoff = prisoners_dilemma_payoff(True, True)
        _acc_prisoners_dilemma_payoff += Float64(len(_r_prisoners_dilemma_payoff))
    var _t1_prisoners_dilemma_payoff = perf_counter_ns()
    var _ns_prisoners_dilemma_payoff = Float64(_t1_prisoners_dilemma_payoff - _t0_prisoners_dilemma_payoff) / Float64(N)
    print("MOJO_TIMING game_theory::prisoners_dilemma_payoff", _ns_prisoners_dilemma_payoff, _acc_prisoners_dilemma_payoff)
    var _acc_iterated_pd: Float64 = 0.0
    var _t0_iterated_pd = perf_counter_ns()
    for _ in range(N):
        var _r_iterated_pd = iterated_pd(5, 5, 5)
        _acc_iterated_pd += Float64(len(_r_iterated_pd))
    var _t1_iterated_pd = perf_counter_ns()
    var _ns_iterated_pd = Float64(_t1_iterated_pd - _t0_iterated_pd) / Float64(N)
    print("MOJO_TIMING game_theory::iterated_pd", _ns_iterated_pd, _acc_iterated_pd)
    var _acc_shapley_value_3player: Float64 = 0.0
    var _t0_shapley_value_3player = perf_counter_ns()
    for _ in range(N):
        var _r_shapley_value_3player = shapley_value_3player(_lf5)
        _acc_shapley_value_3player += Float64(len(_r_shapley_value_3player))
    var _t1_shapley_value_3player = perf_counter_ns()
    var _ns_shapley_value_3player = Float64(_t1_shapley_value_3player - _t0_shapley_value_3player) / Float64(N)
    print("MOJO_TIMING game_theory::shapley_value_3player", _ns_shapley_value_3player, _acc_shapley_value_3player)
    var _acc_pareto_optimal_outcomes: Float64 = 0.0
    var _t0_pareto_optimal_outcomes = perf_counter_ns()
    for _ in range(N):
        var _r_pareto_optimal_outcomes = pareto_optimal_outcomes(_lf5, _lf5)
        _acc_pareto_optimal_outcomes += Float64(len(_r_pareto_optimal_outcomes))
    var _t1_pareto_optimal_outcomes = perf_counter_ns()
    var _ns_pareto_optimal_outcomes = Float64(_t1_pareto_optimal_outcomes - _t0_pareto_optimal_outcomes) / Float64(N)
    print("MOJO_TIMING game_theory::pareto_optimal_outcomes", _ns_pareto_optimal_outcomes, _acc_pareto_optimal_outcomes)
