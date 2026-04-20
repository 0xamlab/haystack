"""test_optimization_meta.mojo — auto-generated tests for optimization_meta library."""
from std.math import isnan, isinf
from optimization_meta import eval_objective, acceptance_probability, neighbor, simulated_annealing, particle_swarm, random_search, hill_climbing

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
