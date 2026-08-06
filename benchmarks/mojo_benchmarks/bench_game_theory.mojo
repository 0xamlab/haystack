"""bench_game_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from game_theory import nash_2x2, minimax_value, dominated_strategy_check, expected_payoff, prisoners_dilemma_payoff, iterated_pd, shapley_value_3player, pareto_optimal_outcomes
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_nash_2x2 = nash_2x2([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_nash_2x2 = _summary_list_float64(_result_nash_2x2)
    print("MOJO_RESULT game_theory::nash_2x2", _summary_nash_2x2)
    var _acc_minimax_value: Float64 = 0.0
    var _t0_minimax_value = perf_counter_ns()
    for _ in range(N):
        _acc_minimax_value += minimax_value([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_minimax_value = perf_counter_ns()
    var _ns_minimax_value = Float64(_t1_minimax_value - _t0_minimax_value) / Float64(N)
    print("MOJO_TIMING game_theory::minimax_value", _ns_minimax_value, _acc_minimax_value)
    var _result_minimax_value = minimax_value([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_minimax_value = _summary_float64(_result_minimax_value)
    print("MOJO_RESULT game_theory::minimax_value", _summary_minimax_value)
    var _acc_dominated_strategy_check: Float64 = 0.0
    var _t0_dominated_strategy_check = perf_counter_ns()
    for _ in range(N):
        var _r_dominated_strategy_check = dominated_strategy_check([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_dominated_strategy_check += Float64(len(_r_dominated_strategy_check))
    var _t1_dominated_strategy_check = perf_counter_ns()
    var _ns_dominated_strategy_check = Float64(_t1_dominated_strategy_check - _t0_dominated_strategy_check) / Float64(N)
    print("MOJO_TIMING game_theory::dominated_strategy_check", _ns_dominated_strategy_check, _acc_dominated_strategy_check)
    var _result_dominated_strategy_check = dominated_strategy_check([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_dominated_strategy_check = _summary_list_bool(_result_dominated_strategy_check)
    print("MOJO_RESULT game_theory::dominated_strategy_check", _summary_dominated_strategy_check)
    var _acc_expected_payoff: Float64 = 0.0
    var _t0_expected_payoff = perf_counter_ns()
    for _ in range(N):
        _acc_expected_payoff += expected_payoff([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5)
    var _t1_expected_payoff = perf_counter_ns()
    var _ns_expected_payoff = Float64(_t1_expected_payoff - _t0_expected_payoff) / Float64(N)
    print("MOJO_TIMING game_theory::expected_payoff", _ns_expected_payoff, _acc_expected_payoff)
    var _result_expected_payoff = expected_payoff([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5)
    var _summary_expected_payoff = _summary_float64(_result_expected_payoff)
    print("MOJO_RESULT game_theory::expected_payoff", _summary_expected_payoff)
    var _acc_prisoners_dilemma_payoff: Float64 = 0.0
    var _t0_prisoners_dilemma_payoff = perf_counter_ns()
    for _ in range(N):
        var _r_prisoners_dilemma_payoff = prisoners_dilemma_payoff(True, True)
        _acc_prisoners_dilemma_payoff += Float64(len(_r_prisoners_dilemma_payoff))
    var _t1_prisoners_dilemma_payoff = perf_counter_ns()
    var _ns_prisoners_dilemma_payoff = Float64(_t1_prisoners_dilemma_payoff - _t0_prisoners_dilemma_payoff) / Float64(N)
    print("MOJO_TIMING game_theory::prisoners_dilemma_payoff", _ns_prisoners_dilemma_payoff, _acc_prisoners_dilemma_payoff)
    var _result_prisoners_dilemma_payoff = prisoners_dilemma_payoff(True, True)
    var _summary_prisoners_dilemma_payoff = _summary_list_float64(_result_prisoners_dilemma_payoff)
    print("MOJO_RESULT game_theory::prisoners_dilemma_payoff", _summary_prisoners_dilemma_payoff)
    var _acc_iterated_pd: Float64 = 0.0
    var _t0_iterated_pd = perf_counter_ns()
    for _ in range(N):
        var _r_iterated_pd = iterated_pd(5, 5, 5)
        _acc_iterated_pd += Float64(len(_r_iterated_pd))
    var _t1_iterated_pd = perf_counter_ns()
    var _ns_iterated_pd = Float64(_t1_iterated_pd - _t0_iterated_pd) / Float64(N)
    print("MOJO_TIMING game_theory::iterated_pd", _ns_iterated_pd, _acc_iterated_pd)
    var _result_iterated_pd = iterated_pd(5, 5, 5)
    var _summary_iterated_pd = _summary_list_float64(_result_iterated_pd)
    print("MOJO_RESULT game_theory::iterated_pd", _summary_iterated_pd)
    var _acc_shapley_value_3player: Float64 = 0.0
    var _t0_shapley_value_3player = perf_counter_ns()
    for _ in range(N):
        var _r_shapley_value_3player = shapley_value_3player(_lf5)
        _acc_shapley_value_3player += Float64(len(_r_shapley_value_3player))
    var _t1_shapley_value_3player = perf_counter_ns()
    var _ns_shapley_value_3player = Float64(_t1_shapley_value_3player - _t0_shapley_value_3player) / Float64(N)
    print("MOJO_TIMING game_theory::shapley_value_3player", _ns_shapley_value_3player, _acc_shapley_value_3player)
    var _result_shapley_value_3player = shapley_value_3player(_lf5)
    var _summary_shapley_value_3player = _summary_list_float64(_result_shapley_value_3player)
    print("MOJO_RESULT game_theory::shapley_value_3player", _summary_shapley_value_3player)
    var _acc_pareto_optimal_outcomes: Float64 = 0.0
    var _t0_pareto_optimal_outcomes = perf_counter_ns()
    for _ in range(N):
        var _r_pareto_optimal_outcomes = pareto_optimal_outcomes(_lf5, _lf5)
        _acc_pareto_optimal_outcomes += Float64(len(_r_pareto_optimal_outcomes))
    var _t1_pareto_optimal_outcomes = perf_counter_ns()
    var _ns_pareto_optimal_outcomes = Float64(_t1_pareto_optimal_outcomes - _t0_pareto_optimal_outcomes) / Float64(N)
    print("MOJO_TIMING game_theory::pareto_optimal_outcomes", _ns_pareto_optimal_outcomes, _acc_pareto_optimal_outcomes)
    var _result_pareto_optimal_outcomes = pareto_optimal_outcomes(_lf5, _lf5)
    var _summary_pareto_optimal_outcomes = _summary_list_bool(_result_pareto_optimal_outcomes)
    print("MOJO_RESULT game_theory::pareto_optimal_outcomes", _summary_pareto_optimal_outcomes)
