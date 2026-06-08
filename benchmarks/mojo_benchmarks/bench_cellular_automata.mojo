"""bench_cellular_automata.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cellular_automata import elementary_rule, rule_step_1d, game_of_life_cell, game_of_life_step, totalistic_rule, langtons_ant_step, wireworld_cell, rule110_cell, majority_rule, parity_rule
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_elementary_rule: Float64 = 0.0
    var _t0_elementary_rule = perf_counter_ns()
    for _ in range(N):
        _acc_elementary_rule += Float64(elementary_rule(5, 5, 5, 5))
    var _t1_elementary_rule = perf_counter_ns()
    var _ns_elementary_rule = Float64(_t1_elementary_rule - _t0_elementary_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::elementary_rule", _ns_elementary_rule, _acc_elementary_rule)
    var _result_elementary_rule = elementary_rule(5, 5, 5, 5)
    var _summary_elementary_rule = _summary_int(_result_elementary_rule)
    print("MOJO_RESULT cellular_automata::elementary_rule", _summary_elementary_rule)
    var _acc_rule_step_1d: Float64 = 0.0
    var _t0_rule_step_1d = perf_counter_ns()
    for _ in range(N):
        var _r_rule_step_1d = rule_step_1d(_li5, 5, 5)
        _acc_rule_step_1d += Float64(len(_r_rule_step_1d))
    var _t1_rule_step_1d = perf_counter_ns()
    var _ns_rule_step_1d = Float64(_t1_rule_step_1d - _t0_rule_step_1d) / Float64(N)
    print("MOJO_TIMING cellular_automata::rule_step_1d", _ns_rule_step_1d, _acc_rule_step_1d)
    var _result_rule_step_1d = rule_step_1d(_li5, 5, 5)
    var _summary_rule_step_1d = _summary_list_int(_result_rule_step_1d)
    print("MOJO_RESULT cellular_automata::rule_step_1d", _summary_rule_step_1d)
    var _acc_game_of_life_cell: Float64 = 0.0
    var _t0_game_of_life_cell = perf_counter_ns()
    for _ in range(N):
        _acc_game_of_life_cell += Float64(game_of_life_cell(True, 5))
    var _t1_game_of_life_cell = perf_counter_ns()
    var _ns_game_of_life_cell = Float64(_t1_game_of_life_cell - _t0_game_of_life_cell) / Float64(N)
    print("MOJO_TIMING cellular_automata::game_of_life_cell", _ns_game_of_life_cell, _acc_game_of_life_cell)
    var _result_game_of_life_cell = game_of_life_cell(True, 5)
    var _summary_game_of_life_cell = _summary_bool(_result_game_of_life_cell)
    print("MOJO_RESULT cellular_automata::game_of_life_cell", _summary_game_of_life_cell)
    var _acc_game_of_life_step: Float64 = 0.0
    var _t0_game_of_life_step = perf_counter_ns()
    for _ in range(N):
        _acc_game_of_life_step += Float64(game_of_life_step(_li5, 5, 5, 5, 5))
    var _t1_game_of_life_step = perf_counter_ns()
    var _ns_game_of_life_step = Float64(_t1_game_of_life_step - _t0_game_of_life_step) / Float64(N)
    print("MOJO_TIMING cellular_automata::game_of_life_step", _ns_game_of_life_step, _acc_game_of_life_step)
    var _result_game_of_life_step = game_of_life_step(_li5, 5, 5, 5, 5)
    var _summary_game_of_life_step = _summary_int(_result_game_of_life_step)
    print("MOJO_RESULT cellular_automata::game_of_life_step", _summary_game_of_life_step)
    var _acc_totalistic_rule: Float64 = 0.0
    var _t0_totalistic_rule = perf_counter_ns()
    for _ in range(N):
        _acc_totalistic_rule += Float64(totalistic_rule(5, 5, 5))
    var _t1_totalistic_rule = perf_counter_ns()
    var _ns_totalistic_rule = Float64(_t1_totalistic_rule - _t0_totalistic_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::totalistic_rule", _ns_totalistic_rule, _acc_totalistic_rule)
    var _result_totalistic_rule = totalistic_rule(5, 5, 5)
    var _summary_totalistic_rule = _summary_int(_result_totalistic_rule)
    print("MOJO_RESULT cellular_automata::totalistic_rule", _summary_totalistic_rule)
    var _acc_langtons_ant_step: Float64 = 0.0
    var _t0_langtons_ant_step = perf_counter_ns()
    for _ in range(N):
        var _r_langtons_ant_step = langtons_ant_step(5, 5)
        _acc_langtons_ant_step += Float64(len(_r_langtons_ant_step))
    var _t1_langtons_ant_step = perf_counter_ns()
    var _ns_langtons_ant_step = Float64(_t1_langtons_ant_step - _t0_langtons_ant_step) / Float64(N)
    print("MOJO_TIMING cellular_automata::langtons_ant_step", _ns_langtons_ant_step, _acc_langtons_ant_step)
    var _result_langtons_ant_step = langtons_ant_step(5, 5)
    var _summary_langtons_ant_step = _summary_list_int(_result_langtons_ant_step)
    print("MOJO_RESULT cellular_automata::langtons_ant_step", _summary_langtons_ant_step)
    var _acc_wireworld_cell: Float64 = 0.0
    var _t0_wireworld_cell = perf_counter_ns()
    for _ in range(N):
        _acc_wireworld_cell += Float64(wireworld_cell(5, 5))
    var _t1_wireworld_cell = perf_counter_ns()
    var _ns_wireworld_cell = Float64(_t1_wireworld_cell - _t0_wireworld_cell) / Float64(N)
    print("MOJO_TIMING cellular_automata::wireworld_cell", _ns_wireworld_cell, _acc_wireworld_cell)
    var _result_wireworld_cell = wireworld_cell(5, 5)
    var _summary_wireworld_cell = _summary_int(_result_wireworld_cell)
    print("MOJO_RESULT cellular_automata::wireworld_cell", _summary_wireworld_cell)
    var _acc_rule110_cell: Float64 = 0.0
    var _t0_rule110_cell = perf_counter_ns()
    for _ in range(N):
        _acc_rule110_cell += Float64(rule110_cell(5, 5, 5))
    var _t1_rule110_cell = perf_counter_ns()
    var _ns_rule110_cell = Float64(_t1_rule110_cell - _t0_rule110_cell) / Float64(N)
    print("MOJO_TIMING cellular_automata::rule110_cell", _ns_rule110_cell, _acc_rule110_cell)
    var _result_rule110_cell = rule110_cell(5, 5, 5)
    var _summary_rule110_cell = _summary_int(_result_rule110_cell)
    print("MOJO_RESULT cellular_automata::rule110_cell", _summary_rule110_cell)
    var _acc_majority_rule: Float64 = 0.0
    var _t0_majority_rule = perf_counter_ns()
    for _ in range(N):
        _acc_majority_rule += Float64(majority_rule(5, 5))
    var _t1_majority_rule = perf_counter_ns()
    var _ns_majority_rule = Float64(_t1_majority_rule - _t0_majority_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::majority_rule", _ns_majority_rule, _acc_majority_rule)
    var _result_majority_rule = majority_rule(5, 5)
    var _summary_majority_rule = _summary_int(_result_majority_rule)
    print("MOJO_RESULT cellular_automata::majority_rule", _summary_majority_rule)
    var _acc_parity_rule: Float64 = 0.0
    var _t0_parity_rule = perf_counter_ns()
    for _ in range(N):
        _acc_parity_rule += Float64(parity_rule(5))
    var _t1_parity_rule = perf_counter_ns()
    var _ns_parity_rule = Float64(_t1_parity_rule - _t0_parity_rule) / Float64(N)
    print("MOJO_TIMING cellular_automata::parity_rule", _ns_parity_rule, _acc_parity_rule)
    var _result_parity_rule = parity_rule(5)
    var _summary_parity_rule = _summary_int(_result_parity_rule)
    print("MOJO_RESULT cellular_automata::parity_rule", _summary_parity_rule)
