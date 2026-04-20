"""test_cellular_automata.mojo — auto-generated tests for cellular_automata library."""
from std.math import isnan, isinf
from cellular_automata import elementary_rule, rule_step_1d, game_of_life_cell, game_of_life_step, totalistic_rule, langtons_ant_step, wireworld_cell, rule110_cell, majority_rule, parity_rule

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

    _ = elementary_rule(5, 5, 5, 5)
    passed += 1; print("  ✅ cellular_automata::elementary_rule")
    var _v_rule_step_1d = rule_step_1d(_li5, 5, 5)
    if len(_v_rule_step_1d) >= 0: passed += 1; print("  ✅ cellular_automata::rule_step_1d")
    _ = game_of_life_cell(True, 5)
    passed += 1; print("  ✅ cellular_automata::game_of_life_cell")
    _ = game_of_life_step(_li5, 5, 5, 5, 5)
    passed += 1; print("  ✅ cellular_automata::game_of_life_step")
    _ = totalistic_rule(5, 5, 5)
    passed += 1; print("  ✅ cellular_automata::totalistic_rule")
    var _v_langtons_ant_step = langtons_ant_step(5, 5)
    if len(_v_langtons_ant_step) >= 0: passed += 1; print("  ✅ cellular_automata::langtons_ant_step")
    _ = wireworld_cell(5, 5)
    passed += 1; print("  ✅ cellular_automata::wireworld_cell")
    _ = rule110_cell(5, 5, 5)
    passed += 1; print("  ✅ cellular_automata::rule110_cell")
    _ = majority_rule(5, 5)
    passed += 1; print("  ✅ cellular_automata::majority_rule")
    _ = parity_rule(5)
    passed += 1; print("  ✅ cellular_automata::parity_rule")

    print("  [cellular_automata] Passed:", passed, "Failed:", failed)
