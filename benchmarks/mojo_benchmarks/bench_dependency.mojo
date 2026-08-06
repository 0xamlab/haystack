"""bench_dependency.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dependency import resolve_order, has_cycle, transitive_deps, dependency_depth, is_compatible, find_conflicts, install_plan, reverse_deps
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

    var _acc_resolve_order: Float64 = 0.0
    var _t0_resolve_order = perf_counter_ns()
    for _ in range(N):
        var _r_resolve_order = resolve_order(5, [[0,1,1],[1,0,1],[1,1,0]])
        _acc_resolve_order += Float64(len(_r_resolve_order))
    var _t1_resolve_order = perf_counter_ns()
    var _ns_resolve_order = Float64(_t1_resolve_order - _t0_resolve_order) / Float64(N)
    print("MOJO_TIMING dependency::resolve_order", _ns_resolve_order, _acc_resolve_order)
    var _result_resolve_order = resolve_order(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_resolve_order = _summary_list_int(_result_resolve_order)
    print("MOJO_RESULT dependency::resolve_order", _summary_resolve_order)
    var _acc_has_cycle: Float64 = 0.0
    var _t0_has_cycle = perf_counter_ns()
    for _ in range(N):
        _acc_has_cycle += Float64(has_cycle(5, [[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_has_cycle = perf_counter_ns()
    var _ns_has_cycle = Float64(_t1_has_cycle - _t0_has_cycle) / Float64(N)
    print("MOJO_TIMING dependency::has_cycle", _ns_has_cycle, _acc_has_cycle)
    var _result_has_cycle = has_cycle(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_has_cycle = _summary_bool(_result_has_cycle)
    print("MOJO_RESULT dependency::has_cycle", _summary_has_cycle)
    var _acc_transitive_deps: Float64 = 0.0
    var _t0_transitive_deps = perf_counter_ns()
    for _ in range(N):
        var _r_transitive_deps = transitive_deps(5, [[0,1,1],[1,0,1],[1,1,0]])
        _acc_transitive_deps += Float64(len(_r_transitive_deps))
    var _t1_transitive_deps = perf_counter_ns()
    var _ns_transitive_deps = Float64(_t1_transitive_deps - _t0_transitive_deps) / Float64(N)
    print("MOJO_TIMING dependency::transitive_deps", _ns_transitive_deps, _acc_transitive_deps)
    var _result_transitive_deps = transitive_deps(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_transitive_deps = _summary_list_int(_result_transitive_deps)
    print("MOJO_RESULT dependency::transitive_deps", _summary_transitive_deps)
    var _acc_dependency_depth: Float64 = 0.0
    var _t0_dependency_depth = perf_counter_ns()
    for _ in range(N):
        _acc_dependency_depth += Float64(dependency_depth(5, [[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_dependency_depth = perf_counter_ns()
    var _ns_dependency_depth = Float64(_t1_dependency_depth - _t0_dependency_depth) / Float64(N)
    print("MOJO_TIMING dependency::dependency_depth", _ns_dependency_depth, _acc_dependency_depth)
    var _result_dependency_depth = dependency_depth(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_dependency_depth = _summary_int(_result_dependency_depth)
    print("MOJO_RESULT dependency::dependency_depth", _summary_dependency_depth)
    var _acc_is_compatible: Float64 = 0.0
    var _t0_is_compatible = perf_counter_ns()
    for _ in range(N):
        _acc_is_compatible += Float64(is_compatible(5, 5, 5))
    var _t1_is_compatible = perf_counter_ns()
    var _ns_is_compatible = Float64(_t1_is_compatible - _t0_is_compatible) / Float64(N)
    print("MOJO_TIMING dependency::is_compatible", _ns_is_compatible, _acc_is_compatible)
    var _result_is_compatible = is_compatible(5, 5, 5)
    var _summary_is_compatible = _summary_bool(_result_is_compatible)
    print("MOJO_RESULT dependency::is_compatible", _summary_is_compatible)
    var _acc_find_conflicts: Float64 = 0.0
    var _t0_find_conflicts = perf_counter_ns()
    for _ in range(N):
        var _r_find_conflicts = find_conflicts([[0,1,1],[1,0,1],[1,1,0]])
        _acc_find_conflicts += Float64(len(_r_find_conflicts))
    var _t1_find_conflicts = perf_counter_ns()
    var _ns_find_conflicts = Float64(_t1_find_conflicts - _t0_find_conflicts) / Float64(N)
    print("MOJO_TIMING dependency::find_conflicts", _ns_find_conflicts, _acc_find_conflicts)
    var _result_find_conflicts = find_conflicts([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_find_conflicts = _summary_list_list_int(_result_find_conflicts)
    print("MOJO_RESULT dependency::find_conflicts", _summary_find_conflicts)
    var _acc_install_plan: Float64 = 0.0
    var _t0_install_plan = perf_counter_ns()
    for _ in range(N):
        var _r_install_plan = install_plan(5, [[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_install_plan += Float64(len(_r_install_plan))
    var _t1_install_plan = perf_counter_ns()
    var _ns_install_plan = Float64(_t1_install_plan - _t0_install_plan) / Float64(N)
    print("MOJO_TIMING dependency::install_plan", _ns_install_plan, _acc_install_plan)
    var _result_install_plan = install_plan(5, [[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_install_plan = _summary_list_int(_result_install_plan)
    print("MOJO_RESULT dependency::install_plan", _summary_install_plan)
    var _acc_reverse_deps: Float64 = 0.0
    var _t0_reverse_deps = perf_counter_ns()
    for _ in range(N):
        var _r_reverse_deps = reverse_deps(5, [[0,1,1],[1,0,1],[1,1,0]])
        _acc_reverse_deps += Float64(len(_r_reverse_deps))
    var _t1_reverse_deps = perf_counter_ns()
    var _ns_reverse_deps = Float64(_t1_reverse_deps - _t0_reverse_deps) / Float64(N)
    print("MOJO_TIMING dependency::reverse_deps", _ns_reverse_deps, _acc_reverse_deps)
    var _result_reverse_deps = reverse_deps(5, [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_reverse_deps = _summary_list_int(_result_reverse_deps)
    print("MOJO_RESULT dependency::reverse_deps", _summary_reverse_deps)
