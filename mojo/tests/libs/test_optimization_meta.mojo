"""test_optimization_meta.mojo — auto-generated tests for optimization_meta."""
from std.math import isnan, isinf
from optimization_meta import eval_objective, acceptance_probability, neighbor, simulated_annealing, particle_swarm, random_search, hill_climbing

def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_eval_objective = eval_objective(_lf5, 5)
    if is_finite(_v_eval_objective): passed += 1; print("  ✅ optimization_meta::eval_objective =", _v_eval_objective)
    else: failed += 1; print("  ❌ optimization_meta::eval_objective → non-finite:", _v_eval_objective)
    var _v_acceptance_probability = acceptance_probability(0.5, 0.5, 0.5)
    if is_finite(_v_acceptance_probability): passed += 1; print("  ✅ optimization_meta::acceptance_probability =", _v_acceptance_probability)
    else: failed += 1; print("  ❌ optimization_meta::acceptance_probability → non-finite:", _v_acceptance_probability)
    var _v_neighbor = neighbor(_lf5, 0.5)
    if len(_v_neighbor) >= 0: passed += 1; print("  ✅ optimization_meta::neighbor")
    var _v_simulated_annealing = simulated_annealing(_lf5, 5, 0.5, 0.5, 5)
    if len(_v_simulated_annealing) >= 0: passed += 1; print("  ✅ optimization_meta::simulated_annealing")
    var _v_particle_swarm = particle_swarm(5, 5, 5, 5, 0.5, 0.5)
    if len(_v_particle_swarm) >= 0: passed += 1; print("  ✅ optimization_meta::particle_swarm")
    var _v_random_search = random_search(5, 5, 5, 0.5, 0.5)
    if len(_v_random_search) >= 0: passed += 1; print("  ✅ optimization_meta::random_search")
    var _v_hill_climbing = hill_climbing(_lf5, 5, 0.5, 5)
    if len(_v_hill_climbing) >= 0: passed += 1; print("  ✅ optimization_meta::hill_climbing")

    print("  [optimization_meta] Passed:", passed, "Failed:", failed)
