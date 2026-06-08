"""bench_chaos.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from chaos import logistic_map, lorenz_step, lorenz_simulate, lyapunov_exponent_logistic, henon_map, tent_map, bifurcation_diagram, sensitivity_to_initial, feigenbaum_ratio, is_chaotic
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

    var _acc_logistic_map: Float64 = 0.0
    var _t0_logistic_map = perf_counter_ns()
    for _ in range(N):
        var _r_logistic_map = logistic_map(0.5, 0.5, 5)
        _acc_logistic_map += Float64(len(_r_logistic_map))
    var _t1_logistic_map = perf_counter_ns()
    var _ns_logistic_map = Float64(_t1_logistic_map - _t0_logistic_map) / Float64(N)
    print("MOJO_TIMING chaos::logistic_map", _ns_logistic_map, _acc_logistic_map)
    var _result_logistic_map = logistic_map(0.5, 0.5, 5)
    var _summary_logistic_map = _summary_list_float64(_result_logistic_map)
    print("MOJO_RESULT chaos::logistic_map", _summary_logistic_map)
    var _acc_lorenz_step: Float64 = 0.0
    var _t0_lorenz_step = perf_counter_ns()
    for _ in range(N):
        var _r_lorenz_step = lorenz_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_lorenz_step += Float64(len(_r_lorenz_step))
    var _t1_lorenz_step = perf_counter_ns()
    var _ns_lorenz_step = Float64(_t1_lorenz_step - _t0_lorenz_step) / Float64(N)
    print("MOJO_TIMING chaos::lorenz_step", _ns_lorenz_step, _acc_lorenz_step)
    var _result_lorenz_step = lorenz_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_lorenz_step = _summary_list_float64(_result_lorenz_step)
    print("MOJO_RESULT chaos::lorenz_step", _summary_lorenz_step)
    var _acc_lorenz_simulate: Float64 = 0.0
    var _t0_lorenz_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_lorenz_simulate = lorenz_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_lorenz_simulate += Float64(len(_r_lorenz_simulate))
    var _t1_lorenz_simulate = perf_counter_ns()
    var _ns_lorenz_simulate = Float64(_t1_lorenz_simulate - _t0_lorenz_simulate) / Float64(N)
    print("MOJO_TIMING chaos::lorenz_simulate", _ns_lorenz_simulate, _acc_lorenz_simulate)
    var _result_lorenz_simulate = lorenz_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
    var _summary_lorenz_simulate = _summary_list_list_float64(_result_lorenz_simulate)
    print("MOJO_RESULT chaos::lorenz_simulate", _summary_lorenz_simulate)
    var _acc_lyapunov_exponent_logistic: Float64 = 0.0
    var _t0_lyapunov_exponent_logistic = perf_counter_ns()
    for _ in range(N):
        _acc_lyapunov_exponent_logistic += lyapunov_exponent_logistic(0.5, 5, 5)
    var _t1_lyapunov_exponent_logistic = perf_counter_ns()
    var _ns_lyapunov_exponent_logistic = Float64(_t1_lyapunov_exponent_logistic - _t0_lyapunov_exponent_logistic) / Float64(N)
    print("MOJO_TIMING chaos::lyapunov_exponent_logistic", _ns_lyapunov_exponent_logistic, _acc_lyapunov_exponent_logistic)
    var _result_lyapunov_exponent_logistic = lyapunov_exponent_logistic(0.5, 5, 5)
    var _summary_lyapunov_exponent_logistic = _summary_float64(_result_lyapunov_exponent_logistic)
    print("MOJO_RESULT chaos::lyapunov_exponent_logistic", _summary_lyapunov_exponent_logistic)
    var _acc_henon_map: Float64 = 0.0
    var _t0_henon_map = perf_counter_ns()
    for _ in range(N):
        var _r_henon_map = henon_map(0.5, 0.5, 0.5, 0.5, 5)
        _acc_henon_map += Float64(len(_r_henon_map))
    var _t1_henon_map = perf_counter_ns()
    var _ns_henon_map = Float64(_t1_henon_map - _t0_henon_map) / Float64(N)
    print("MOJO_TIMING chaos::henon_map", _ns_henon_map, _acc_henon_map)
    var _result_henon_map = henon_map(0.5, 0.5, 0.5, 0.5, 5)
    var _summary_henon_map = _summary_list_list_float64(_result_henon_map)
    print("MOJO_RESULT chaos::henon_map", _summary_henon_map)
    var _acc_tent_map: Float64 = 0.0
    var _t0_tent_map = perf_counter_ns()
    for _ in range(N):
        var _r_tent_map = tent_map(0.5, 0.5, 5)
        _acc_tent_map += Float64(len(_r_tent_map))
    var _t1_tent_map = perf_counter_ns()
    var _ns_tent_map = Float64(_t1_tent_map - _t0_tent_map) / Float64(N)
    print("MOJO_TIMING chaos::tent_map", _ns_tent_map, _acc_tent_map)
    var _result_tent_map = tent_map(0.5, 0.5, 5)
    var _summary_tent_map = _summary_list_float64(_result_tent_map)
    print("MOJO_RESULT chaos::tent_map", _summary_tent_map)
    var _acc_bifurcation_diagram: Float64 = 0.0
    var _t0_bifurcation_diagram = perf_counter_ns()
    for _ in range(N):
        var _r_bifurcation_diagram = bifurcation_diagram(0.5, 0.5, 5, 5, 5)
        _acc_bifurcation_diagram += Float64(len(_r_bifurcation_diagram))
    var _t1_bifurcation_diagram = perf_counter_ns()
    var _ns_bifurcation_diagram = Float64(_t1_bifurcation_diagram - _t0_bifurcation_diagram) / Float64(N)
    print("MOJO_TIMING chaos::bifurcation_diagram", _ns_bifurcation_diagram, _acc_bifurcation_diagram)
    var _result_bifurcation_diagram = bifurcation_diagram(0.5, 0.5, 5, 5, 5)
    var _summary_bifurcation_diagram = _summary_list_list_float64(_result_bifurcation_diagram)
    print("MOJO_RESULT chaos::bifurcation_diagram", _summary_bifurcation_diagram)
    var _acc_sensitivity_to_initial: Float64 = 0.0
    var _t0_sensitivity_to_initial = perf_counter_ns()
    for _ in range(N):
        var _r_sensitivity_to_initial = sensitivity_to_initial(0.5, 0.5, 0.5, 5)
        _acc_sensitivity_to_initial += Float64(len(_r_sensitivity_to_initial))
    var _t1_sensitivity_to_initial = perf_counter_ns()
    var _ns_sensitivity_to_initial = Float64(_t1_sensitivity_to_initial - _t0_sensitivity_to_initial) / Float64(N)
    print("MOJO_TIMING chaos::sensitivity_to_initial", _ns_sensitivity_to_initial, _acc_sensitivity_to_initial)
    var _result_sensitivity_to_initial = sensitivity_to_initial(0.5, 0.5, 0.5, 5)
    var _summary_sensitivity_to_initial = _summary_list_float64(_result_sensitivity_to_initial)
    print("MOJO_RESULT chaos::sensitivity_to_initial", _summary_sensitivity_to_initial)
    var _acc_feigenbaum_ratio: Float64 = 0.0
    var _t0_feigenbaum_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_feigenbaum_ratio += feigenbaum_ratio(0.5, 0.5, 0.5)
    var _t1_feigenbaum_ratio = perf_counter_ns()
    var _ns_feigenbaum_ratio = Float64(_t1_feigenbaum_ratio - _t0_feigenbaum_ratio) / Float64(N)
    print("MOJO_TIMING chaos::feigenbaum_ratio", _ns_feigenbaum_ratio, _acc_feigenbaum_ratio)
    var _result_feigenbaum_ratio = feigenbaum_ratio(0.5, 0.5, 0.5)
    var _summary_feigenbaum_ratio = _summary_float64(_result_feigenbaum_ratio)
    print("MOJO_RESULT chaos::feigenbaum_ratio", _summary_feigenbaum_ratio)
    var _acc_is_chaotic: Float64 = 0.0
    var _t0_is_chaotic = perf_counter_ns()
    for _ in range(N):
        _acc_is_chaotic += Float64(is_chaotic(0.5))
    var _t1_is_chaotic = perf_counter_ns()
    var _ns_is_chaotic = Float64(_t1_is_chaotic - _t0_is_chaotic) / Float64(N)
    print("MOJO_TIMING chaos::is_chaotic", _ns_is_chaotic, _acc_is_chaotic)
    var _result_is_chaotic = is_chaotic(0.5)
    var _summary_is_chaotic = _summary_bool(_result_is_chaotic)
    print("MOJO_RESULT chaos::is_chaotic", _summary_is_chaotic)
