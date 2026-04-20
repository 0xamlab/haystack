"""bench_optimization_meta.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optimization_meta import eval_objective, acceptance_probability, neighbor, simulated_annealing, particle_swarm, random_search, hill_climbing
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

    var _acc_eval_objective: Float64 = 0.0
    var _t0_eval_objective = perf_counter_ns()
    for _ in range(N):
        _acc_eval_objective += eval_objective(_lf5, 5)
    var _t1_eval_objective = perf_counter_ns()
    var _ns_eval_objective = Float64(_t1_eval_objective - _t0_eval_objective) / Float64(N)
    print("MOJO_TIMING optimization_meta::eval_objective", _ns_eval_objective, _acc_eval_objective)
    var _acc_acceptance_probability: Float64 = 0.0
    var _t0_acceptance_probability = perf_counter_ns()
    for _ in range(N):
        _acc_acceptance_probability += acceptance_probability(0.5, 0.5, 0.5)
    var _t1_acceptance_probability = perf_counter_ns()
    var _ns_acceptance_probability = Float64(_t1_acceptance_probability - _t0_acceptance_probability) / Float64(N)
    print("MOJO_TIMING optimization_meta::acceptance_probability", _ns_acceptance_probability, _acc_acceptance_probability)
    var _acc_neighbor: Float64 = 0.0
    var _t0_neighbor = perf_counter_ns()
    for _ in range(N):
        var _r_neighbor = neighbor(_lf5, 0.5)
        _acc_neighbor += Float64(len(_r_neighbor))
    var _t1_neighbor = perf_counter_ns()
    var _ns_neighbor = Float64(_t1_neighbor - _t0_neighbor) / Float64(N)
    print("MOJO_TIMING optimization_meta::neighbor", _ns_neighbor, _acc_neighbor)
    var _acc_simulated_annealing: Float64 = 0.0
    var _t0_simulated_annealing = perf_counter_ns()
    for _ in range(N):
        var _r_simulated_annealing = simulated_annealing(_lf5, 5, 0.5, 0.5, 5)
        _acc_simulated_annealing += Float64(len(_r_simulated_annealing))
    var _t1_simulated_annealing = perf_counter_ns()
    var _ns_simulated_annealing = Float64(_t1_simulated_annealing - _t0_simulated_annealing) / Float64(N)
    print("MOJO_TIMING optimization_meta::simulated_annealing", _ns_simulated_annealing, _acc_simulated_annealing)
    var _acc_particle_swarm: Float64 = 0.0
    var _t0_particle_swarm = perf_counter_ns()
    for _ in range(N):
        var _r_particle_swarm = particle_swarm(5, 5, 5, 5, 0.5, 0.5)
        _acc_particle_swarm += Float64(len(_r_particle_swarm))
    var _t1_particle_swarm = perf_counter_ns()
    var _ns_particle_swarm = Float64(_t1_particle_swarm - _t0_particle_swarm) / Float64(N)
    print("MOJO_TIMING optimization_meta::particle_swarm", _ns_particle_swarm, _acc_particle_swarm)
    var _acc_random_search: Float64 = 0.0
    var _t0_random_search = perf_counter_ns()
    for _ in range(N):
        var _r_random_search = random_search(5, 5, 5, 0.5, 0.5)
        _acc_random_search += Float64(len(_r_random_search))
    var _t1_random_search = perf_counter_ns()
    var _ns_random_search = Float64(_t1_random_search - _t0_random_search) / Float64(N)
    print("MOJO_TIMING optimization_meta::random_search", _ns_random_search, _acc_random_search)
    var _acc_hill_climbing: Float64 = 0.0
    var _t0_hill_climbing = perf_counter_ns()
    for _ in range(N):
        var _r_hill_climbing = hill_climbing(_lf5, 5, 0.5, 5)
        _acc_hill_climbing += Float64(len(_r_hill_climbing))
    var _t1_hill_climbing = perf_counter_ns()
    var _ns_hill_climbing = Float64(_t1_hill_climbing - _t0_hill_climbing) / Float64(N)
    print("MOJO_TIMING optimization_meta::hill_climbing", _ns_hill_climbing, _acc_hill_climbing)
