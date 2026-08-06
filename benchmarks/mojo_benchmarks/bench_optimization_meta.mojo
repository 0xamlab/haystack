"""bench_optimization_meta.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optimization_meta import eval_objective, acceptance_probability, neighbor, simulated_annealing, particle_swarm, random_search, hill_climbing
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

    var _acc_eval_objective: Float64 = 0.0
    var _t0_eval_objective = perf_counter_ns()
    for _ in range(N):
        _acc_eval_objective += eval_objective(_lf5, 5)
    var _t1_eval_objective = perf_counter_ns()
    var _ns_eval_objective = Float64(_t1_eval_objective - _t0_eval_objective) / Float64(N)
    print("MOJO_TIMING optimization_meta::eval_objective", _ns_eval_objective, _acc_eval_objective)
    var _result_eval_objective = eval_objective(_lf5, 5)
    var _summary_eval_objective = _summary_float64(_result_eval_objective)
    print("MOJO_RESULT optimization_meta::eval_objective", _summary_eval_objective)
    var _acc_acceptance_probability: Float64 = 0.0
    var _t0_acceptance_probability = perf_counter_ns()
    for _ in range(N):
        _acc_acceptance_probability += acceptance_probability(0.5, 0.5, 0.5)
    var _t1_acceptance_probability = perf_counter_ns()
    var _ns_acceptance_probability = Float64(_t1_acceptance_probability - _t0_acceptance_probability) / Float64(N)
    print("MOJO_TIMING optimization_meta::acceptance_probability", _ns_acceptance_probability, _acc_acceptance_probability)
    var _result_acceptance_probability = acceptance_probability(0.5, 0.5, 0.5)
    var _summary_acceptance_probability = _summary_float64(_result_acceptance_probability)
    print("MOJO_RESULT optimization_meta::acceptance_probability", _summary_acceptance_probability)
    var _acc_neighbor: Float64 = 0.0
    var _t0_neighbor = perf_counter_ns()
    for _ in range(N):
        var _r_neighbor = neighbor(_lf5, 0.5)
        _acc_neighbor += Float64(len(_r_neighbor))
    var _t1_neighbor = perf_counter_ns()
    var _ns_neighbor = Float64(_t1_neighbor - _t0_neighbor) / Float64(N)
    print("MOJO_TIMING optimization_meta::neighbor", _ns_neighbor, _acc_neighbor)
    var _result_neighbor = neighbor(_lf5, 0.5)
    var _summary_neighbor = _summary_list_float64(_result_neighbor)
    print("MOJO_RESULT optimization_meta::neighbor", _summary_neighbor)
    var _acc_simulated_annealing: Float64 = 0.0
    var _t0_simulated_annealing = perf_counter_ns()
    for _ in range(N):
        var _r_simulated_annealing = simulated_annealing(_lf5, 5, 0.5, 0.5, 5)
        _acc_simulated_annealing += Float64(len(_r_simulated_annealing))
    var _t1_simulated_annealing = perf_counter_ns()
    var _ns_simulated_annealing = Float64(_t1_simulated_annealing - _t0_simulated_annealing) / Float64(N)
    print("MOJO_TIMING optimization_meta::simulated_annealing", _ns_simulated_annealing, _acc_simulated_annealing)
    var _result_simulated_annealing = simulated_annealing(_lf5, 5, 0.5, 0.5, 5)
    var _summary_simulated_annealing = _summary_list_float64(_result_simulated_annealing)
    print("MOJO_RESULT optimization_meta::simulated_annealing", _summary_simulated_annealing)
    var _acc_particle_swarm: Float64 = 0.0
    var _t0_particle_swarm = perf_counter_ns()
    for _ in range(N):
        var _r_particle_swarm = particle_swarm(5, 5, 5, 5, 0.5, 0.5)
        _acc_particle_swarm += Float64(len(_r_particle_swarm))
    var _t1_particle_swarm = perf_counter_ns()
    var _ns_particle_swarm = Float64(_t1_particle_swarm - _t0_particle_swarm) / Float64(N)
    print("MOJO_TIMING optimization_meta::particle_swarm", _ns_particle_swarm, _acc_particle_swarm)
    var _result_particle_swarm = particle_swarm(5, 5, 5, 5, 0.5, 0.5)
    var _summary_particle_swarm = _summary_list_float64(_result_particle_swarm)
    print("MOJO_RESULT optimization_meta::particle_swarm", _summary_particle_swarm)
    var _acc_random_search: Float64 = 0.0
    var _t0_random_search = perf_counter_ns()
    for _ in range(N):
        var _r_random_search = random_search(5, 5, 5, 0.5, 0.5)
        _acc_random_search += Float64(len(_r_random_search))
    var _t1_random_search = perf_counter_ns()
    var _ns_random_search = Float64(_t1_random_search - _t0_random_search) / Float64(N)
    print("MOJO_TIMING optimization_meta::random_search", _ns_random_search, _acc_random_search)
    var _result_random_search = random_search(5, 5, 5, 0.5, 0.5)
    var _summary_random_search = _summary_list_float64(_result_random_search)
    print("MOJO_RESULT optimization_meta::random_search", _summary_random_search)
    var _acc_hill_climbing: Float64 = 0.0
    var _t0_hill_climbing = perf_counter_ns()
    for _ in range(N):
        var _r_hill_climbing = hill_climbing(_lf5, 5, 0.5, 5)
        _acc_hill_climbing += Float64(len(_r_hill_climbing))
    var _t1_hill_climbing = perf_counter_ns()
    var _ns_hill_climbing = Float64(_t1_hill_climbing - _t0_hill_climbing) / Float64(N)
    print("MOJO_TIMING optimization_meta::hill_climbing", _ns_hill_climbing, _acc_hill_climbing)
    var _result_hill_climbing = hill_climbing(_lf5, 5, 0.5, 5)
    var _summary_hill_climbing = _summary_list_float64(_result_hill_climbing)
    print("MOJO_RESULT optimization_meta::hill_climbing", _summary_hill_climbing)
