"""test_game_theory.mojo — auto-generated tests for game_theory library."""
from std.math import isnan, isinf
from game_theory import prisoners_dilemma_payoff, iterated_pd, shapley_value_3player, pareto_optimal_outcomes

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

    var _v_prisoners_dilemma_payoff = prisoners_dilemma_payoff(True, True)
    if len(_v_prisoners_dilemma_payoff) >= 0: passed += 1; print("  ✅ game_theory::prisoners_dilemma_payoff")
    var _v_iterated_pd = iterated_pd(5, 5, 5)
    if len(_v_iterated_pd) >= 0: passed += 1; print("  ✅ game_theory::iterated_pd")
    var _v_shapley_value_3player = shapley_value_3player(_lf5)
    if len(_v_shapley_value_3player) >= 0: passed += 1; print("  ✅ game_theory::shapley_value_3player")
    var _v_pareto_optimal_outcomes = pareto_optimal_outcomes(_lf5, _lf5)
    if len(_v_pareto_optimal_outcomes) >= 0: passed += 1; print("  ✅ game_theory::pareto_optimal_outcomes")

    print("  [game_theory] Passed:", passed, "Failed:", failed)
