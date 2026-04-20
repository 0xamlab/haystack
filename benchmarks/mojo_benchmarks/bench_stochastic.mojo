"""bench_stochastic.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from stochastic import random_walk_1d, random_walk_2d, brownian_motion, geometric_brownian_motion, poisson_process, ornstein_uhlenbeck, birth_death_process, monte_carlo_pi, expected_hitting_time, first_passage_time
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

    var _acc_random_walk_1d: Float64 = 0.0
    var _t0_random_walk_1d = perf_counter_ns()
    for _ in range(N):
        var _r_random_walk_1d = random_walk_1d(5)
        _acc_random_walk_1d += Float64(len(_r_random_walk_1d))
    var _t1_random_walk_1d = perf_counter_ns()
    var _ns_random_walk_1d = Float64(_t1_random_walk_1d - _t0_random_walk_1d) / Float64(N)
    print("MOJO_TIMING stochastic::random_walk_1d", _ns_random_walk_1d, _acc_random_walk_1d)
    var _acc_random_walk_2d: Float64 = 0.0
    var _t0_random_walk_2d = perf_counter_ns()
    for _ in range(N):
        var _r_random_walk_2d = random_walk_2d(5)
        _acc_random_walk_2d += Float64(len(_r_random_walk_2d))
    var _t1_random_walk_2d = perf_counter_ns()
    var _ns_random_walk_2d = Float64(_t1_random_walk_2d - _t0_random_walk_2d) / Float64(N)
    print("MOJO_TIMING stochastic::random_walk_2d", _ns_random_walk_2d, _acc_random_walk_2d)
    var _acc_brownian_motion: Float64 = 0.0
    var _t0_brownian_motion = perf_counter_ns()
    for _ in range(N):
        var _r_brownian_motion = brownian_motion(5, 0.5)
        _acc_brownian_motion += Float64(len(_r_brownian_motion))
    var _t1_brownian_motion = perf_counter_ns()
    var _ns_brownian_motion = Float64(_t1_brownian_motion - _t0_brownian_motion) / Float64(N)
    print("MOJO_TIMING stochastic::brownian_motion", _ns_brownian_motion, _acc_brownian_motion)
    var _acc_geometric_brownian_motion: Float64 = 0.0
    var _t0_geometric_brownian_motion = perf_counter_ns()
    for _ in range(N):
        var _r_geometric_brownian_motion = geometric_brownian_motion(0.5, 0.5, 0.5, 0.5, 5)
        _acc_geometric_brownian_motion += Float64(len(_r_geometric_brownian_motion))
    var _t1_geometric_brownian_motion = perf_counter_ns()
    var _ns_geometric_brownian_motion = Float64(_t1_geometric_brownian_motion - _t0_geometric_brownian_motion) / Float64(N)
    print("MOJO_TIMING stochastic::geometric_brownian_motion", _ns_geometric_brownian_motion, _acc_geometric_brownian_motion)
    var _acc_poisson_process: Float64 = 0.0
    var _t0_poisson_process = perf_counter_ns()
    for _ in range(N):
        var _r_poisson_process = poisson_process(0.5, 0.5)
        _acc_poisson_process += Float64(len(_r_poisson_process))
    var _t1_poisson_process = perf_counter_ns()
    var _ns_poisson_process = Float64(_t1_poisson_process - _t0_poisson_process) / Float64(N)
    print("MOJO_TIMING stochastic::poisson_process", _ns_poisson_process, _acc_poisson_process)
    var _acc_ornstein_uhlenbeck: Float64 = 0.0
    var _t0_ornstein_uhlenbeck = perf_counter_ns()
    for _ in range(N):
        var _r_ornstein_uhlenbeck = ornstein_uhlenbeck(0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_ornstein_uhlenbeck += Float64(len(_r_ornstein_uhlenbeck))
    var _t1_ornstein_uhlenbeck = perf_counter_ns()
    var _ns_ornstein_uhlenbeck = Float64(_t1_ornstein_uhlenbeck - _t0_ornstein_uhlenbeck) / Float64(N)
    print("MOJO_TIMING stochastic::ornstein_uhlenbeck", _ns_ornstein_uhlenbeck, _acc_ornstein_uhlenbeck)
    var _acc_birth_death_process: Float64 = 0.0
    var _t0_birth_death_process = perf_counter_ns()
    for _ in range(N):
        var _r_birth_death_process = birth_death_process(0.5, 0.5, 5, 5)
        _acc_birth_death_process += Float64(len(_r_birth_death_process))
    var _t1_birth_death_process = perf_counter_ns()
    var _ns_birth_death_process = Float64(_t1_birth_death_process - _t0_birth_death_process) / Float64(N)
    print("MOJO_TIMING stochastic::birth_death_process", _ns_birth_death_process, _acc_birth_death_process)
    var _acc_monte_carlo_pi: Float64 = 0.0
    var _t0_monte_carlo_pi = perf_counter_ns()
    for _ in range(N):
        _acc_monte_carlo_pi += monte_carlo_pi(5)
    var _t1_monte_carlo_pi = perf_counter_ns()
    var _ns_monte_carlo_pi = Float64(_t1_monte_carlo_pi - _t0_monte_carlo_pi) / Float64(N)
    print("MOJO_TIMING stochastic::monte_carlo_pi", _ns_monte_carlo_pi, _acc_monte_carlo_pi)
    var _acc_expected_hitting_time: Float64 = 0.0
    var _t0_expected_hitting_time = perf_counter_ns()
    for _ in range(N):
        _acc_expected_hitting_time += expected_hitting_time(0.5, 5)
    var _t1_expected_hitting_time = perf_counter_ns()
    var _ns_expected_hitting_time = Float64(_t1_expected_hitting_time - _t0_expected_hitting_time) / Float64(N)
    print("MOJO_TIMING stochastic::expected_hitting_time", _ns_expected_hitting_time, _acc_expected_hitting_time)
    var _acc_first_passage_time: Float64 = 0.0
    var _t0_first_passage_time = perf_counter_ns()
    for _ in range(N):
        _acc_first_passage_time += first_passage_time(5, 0.5)
    var _t1_first_passage_time = perf_counter_ns()
    var _ns_first_passage_time = Float64(_t1_first_passage_time - _t0_first_passage_time) / Float64(N)
    print("MOJO_TIMING stochastic::first_passage_time", _ns_first_passage_time, _acc_first_passage_time)
