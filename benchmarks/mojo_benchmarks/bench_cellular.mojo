"""bench_cellular.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cellular import grid_create, grid_randomize, count_alive, grid_to_density, count_neighbors, game_of_life_step, is_still_life, population_history, rule_lookup, elementary_ca_step, run_elementary_ca
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

    var _acc_grid_create: Float64 = 0.0
    var _t0_grid_create = perf_counter_ns()
    for _ in range(N):
        var _r_grid_create = grid_create(5, 5)
        _acc_grid_create += Float64(len(_r_grid_create))
    var _t1_grid_create = perf_counter_ns()
    var _ns_grid_create = Float64(_t1_grid_create - _t0_grid_create) / Float64(N)
    print("MOJO_TIMING cellular::grid_create", _ns_grid_create, _acc_grid_create)
    var _acc_grid_randomize: Float64 = 0.0
    var _t0_grid_randomize = perf_counter_ns()
    for _ in range(N):
        var _r_grid_randomize = grid_randomize(5, 5, 0.5)
        _acc_grid_randomize += Float64(len(_r_grid_randomize))
    var _t1_grid_randomize = perf_counter_ns()
    var _ns_grid_randomize = Float64(_t1_grid_randomize - _t0_grid_randomize) / Float64(N)
    print("MOJO_TIMING cellular::grid_randomize", _ns_grid_randomize, _acc_grid_randomize)
    var _acc_count_alive: Float64 = 0.0
    var _t0_count_alive = perf_counter_ns()
    for _ in range(N):
        _acc_count_alive += Float64(count_alive([[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_count_alive = perf_counter_ns()
    var _ns_count_alive = Float64(_t1_count_alive - _t0_count_alive) / Float64(N)
    print("MOJO_TIMING cellular::count_alive", _ns_count_alive, _acc_count_alive)
    var _acc_grid_to_density: Float64 = 0.0
    var _t0_grid_to_density = perf_counter_ns()
    for _ in range(N):
        _acc_grid_to_density += grid_to_density([[0,1,1],[1,0,1],[1,1,0]])
    var _t1_grid_to_density = perf_counter_ns()
    var _ns_grid_to_density = Float64(_t1_grid_to_density - _t0_grid_to_density) / Float64(N)
    print("MOJO_TIMING cellular::grid_to_density", _ns_grid_to_density, _acc_grid_to_density)
    var _acc_count_neighbors: Float64 = 0.0
    var _t0_count_neighbors = perf_counter_ns()
    for _ in range(N):
        _acc_count_neighbors += Float64(count_neighbors([[0,1,1],[1,0,1],[1,1,0]], 5, 5, 5, 5))
    var _t1_count_neighbors = perf_counter_ns()
    var _ns_count_neighbors = Float64(_t1_count_neighbors - _t0_count_neighbors) / Float64(N)
    print("MOJO_TIMING cellular::count_neighbors", _ns_count_neighbors, _acc_count_neighbors)
    var _acc_game_of_life_step: Float64 = 0.0
    var _t0_game_of_life_step = perf_counter_ns()
    for _ in range(N):
        var _r_game_of_life_step = game_of_life_step([[0,1,1],[1,0,1],[1,1,0]], 5, 5)
        _acc_game_of_life_step += Float64(len(_r_game_of_life_step))
    var _t1_game_of_life_step = perf_counter_ns()
    var _ns_game_of_life_step = Float64(_t1_game_of_life_step - _t0_game_of_life_step) / Float64(N)
    print("MOJO_TIMING cellular::game_of_life_step", _ns_game_of_life_step, _acc_game_of_life_step)
    var _acc_is_still_life: Float64 = 0.0
    var _t0_is_still_life = perf_counter_ns()
    for _ in range(N):
        _acc_is_still_life += Float64(is_still_life([[0,1,1],[1,0,1],[1,1,0]], 5, 5))
    var _t1_is_still_life = perf_counter_ns()
    var _ns_is_still_life = Float64(_t1_is_still_life - _t0_is_still_life) / Float64(N)
    print("MOJO_TIMING cellular::is_still_life", _ns_is_still_life, _acc_is_still_life)
    var _acc_population_history: Float64 = 0.0
    var _t0_population_history = perf_counter_ns()
    for _ in range(N):
        var _r_population_history = population_history([[0,1,1],[1,0,1],[1,1,0]], 5, 5, 5)
        _acc_population_history += Float64(len(_r_population_history))
    var _t1_population_history = perf_counter_ns()
    var _ns_population_history = Float64(_t1_population_history - _t0_population_history) / Float64(N)
    print("MOJO_TIMING cellular::population_history", _ns_population_history, _acc_population_history)
    var _acc_rule_lookup: Float64 = 0.0
    var _t0_rule_lookup = perf_counter_ns()
    for _ in range(N):
        _acc_rule_lookup += Float64(rule_lookup(5, 5, 5, 5))
    var _t1_rule_lookup = perf_counter_ns()
    var _ns_rule_lookup = Float64(_t1_rule_lookup - _t0_rule_lookup) / Float64(N)
    print("MOJO_TIMING cellular::rule_lookup", _ns_rule_lookup, _acc_rule_lookup)
    var _acc_elementary_ca_step: Float64 = 0.0
    var _t0_elementary_ca_step = perf_counter_ns()
    for _ in range(N):
        var _r_elementary_ca_step = elementary_ca_step(_li5, 5)
        _acc_elementary_ca_step += Float64(len(_r_elementary_ca_step))
    var _t1_elementary_ca_step = perf_counter_ns()
    var _ns_elementary_ca_step = Float64(_t1_elementary_ca_step - _t0_elementary_ca_step) / Float64(N)
    print("MOJO_TIMING cellular::elementary_ca_step", _ns_elementary_ca_step, _acc_elementary_ca_step)
    var _acc_run_elementary_ca: Float64 = 0.0
    var _t0_run_elementary_ca = perf_counter_ns()
    for _ in range(N):
        var _r_run_elementary_ca = run_elementary_ca(_li5, 5, 5)
        _acc_run_elementary_ca += Float64(len(_r_run_elementary_ca))
    var _t1_run_elementary_ca = perf_counter_ns()
    var _ns_run_elementary_ca = Float64(_t1_run_elementary_ca - _t0_run_elementary_ca) / Float64(N)
    print("MOJO_TIMING cellular::run_elementary_ca", _ns_run_elementary_ca, _acc_run_elementary_ca)
