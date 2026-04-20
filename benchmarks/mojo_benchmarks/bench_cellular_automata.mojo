"""bench_cellular_automata.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cellular_automata import elementary_rule, rule_step_1d, game_of_life_cell, game_of_life_step, totalistic_rule, langtons_ant_step, wireworld_cell, rule110_cell, majority_rule, parity_rule
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

    var _acc_elementary_rule: Float64 = 0.0
    var _t0_elementary_rule = perf_counter_ns()
    for _ in range(N):
        _acc_elementary_rule += Float64(elementary_rule(5, 5, 5, 5))
    var _t1_elementary_rule = perf_counter_ns()
    var _ns_elementary_rule = Float64(_t1_elementary_rule - _t0_elementary_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::elementary_rule", _ns_elementary_rule, _acc_elementary_rule)
    var _acc_rule_step_1d: Float64 = 0.0
    var _t0_rule_step_1d = perf_counter_ns()
    for _ in range(N):
        var _r_rule_step_1d = rule_step_1d(_li5, 5, 5)
        _acc_rule_step_1d += Float64(len(_r_rule_step_1d))
    var _t1_rule_step_1d = perf_counter_ns()
    var _ns_rule_step_1d = Float64(_t1_rule_step_1d - _t0_rule_step_1d) / Float64(N)
    print("MOJO_TIMING cellular_automata::rule_step_1d", _ns_rule_step_1d, _acc_rule_step_1d)
    var _acc_game_of_life_cell: Float64 = 0.0
    var _t0_game_of_life_cell = perf_counter_ns()
    for _ in range(N):
        _acc_game_of_life_cell += Float64(game_of_life_cell(True, 5))
    var _t1_game_of_life_cell = perf_counter_ns()
    var _ns_game_of_life_cell = Float64(_t1_game_of_life_cell - _t0_game_of_life_cell) / Float64(N)
    print("MOJO_TIMING cellular_automata::game_of_life_cell", _ns_game_of_life_cell, _acc_game_of_life_cell)
    var _acc_game_of_life_step: Float64 = 0.0
    var _t0_game_of_life_step = perf_counter_ns()
    for _ in range(N):
        _acc_game_of_life_step += Float64(game_of_life_step(_li5, 5, 5, 5, 5))
    var _t1_game_of_life_step = perf_counter_ns()
    var _ns_game_of_life_step = Float64(_t1_game_of_life_step - _t0_game_of_life_step) / Float64(N)
    print("MOJO_TIMING cellular_automata::game_of_life_step", _ns_game_of_life_step, _acc_game_of_life_step)
    var _acc_totalistic_rule: Float64 = 0.0
    var _t0_totalistic_rule = perf_counter_ns()
    for _ in range(N):
        _acc_totalistic_rule += Float64(totalistic_rule(5, 5, 5))
    var _t1_totalistic_rule = perf_counter_ns()
    var _ns_totalistic_rule = Float64(_t1_totalistic_rule - _t0_totalistic_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::totalistic_rule", _ns_totalistic_rule, _acc_totalistic_rule)
    var _acc_langtons_ant_step: Float64 = 0.0
    var _t0_langtons_ant_step = perf_counter_ns()
    for _ in range(N):
        var _r_langtons_ant_step = langtons_ant_step(5, 5)
        _acc_langtons_ant_step += Float64(len(_r_langtons_ant_step))
    var _t1_langtons_ant_step = perf_counter_ns()
    var _ns_langtons_ant_step = Float64(_t1_langtons_ant_step - _t0_langtons_ant_step) / Float64(N)
    print("MOJO_TIMING cellular_automata::langtons_ant_step", _ns_langtons_ant_step, _acc_langtons_ant_step)
    var _acc_wireworld_cell: Float64 = 0.0
    var _t0_wireworld_cell = perf_counter_ns()
    for _ in range(N):
        _acc_wireworld_cell += Float64(wireworld_cell(5, 5))
    var _t1_wireworld_cell = perf_counter_ns()
    var _ns_wireworld_cell = Float64(_t1_wireworld_cell - _t0_wireworld_cell) / Float64(N)
    print("MOJO_TIMING cellular_automata::wireworld_cell", _ns_wireworld_cell, _acc_wireworld_cell)
    var _acc_rule110_cell: Float64 = 0.0
    var _t0_rule110_cell = perf_counter_ns()
    for _ in range(N):
        _acc_rule110_cell += Float64(rule110_cell(5, 5, 5))
    var _t1_rule110_cell = perf_counter_ns()
    var _ns_rule110_cell = Float64(_t1_rule110_cell - _t0_rule110_cell) / Float64(N)
    print("MOJO_TIMING cellular_automata::rule110_cell", _ns_rule110_cell, _acc_rule110_cell)
    var _acc_majority_rule: Float64 = 0.0
    var _t0_majority_rule = perf_counter_ns()
    for _ in range(N):
        _acc_majority_rule += Float64(majority_rule(5, 5))
    var _t1_majority_rule = perf_counter_ns()
    var _ns_majority_rule = Float64(_t1_majority_rule - _t0_majority_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::majority_rule", _ns_majority_rule, _acc_majority_rule)
    var _acc_parity_rule: Float64 = 0.0
    var _t0_parity_rule = perf_counter_ns()
    for _ in range(N):
        _acc_parity_rule += Float64(parity_rule(5))
    var _t1_parity_rule = perf_counter_ns()
    var _ns_parity_rule = Float64(_t1_parity_rule - _t0_parity_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::parity_rule", _ns_parity_rule, _acc_parity_rule)
