"""bench_population.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from population import exponential_growth, logistic_growth, logistic_simulate, lotka_volterra_step, lotka_volterra_simulate, carrying_capacity_estimate, growth_rate_estimate, competition_model, population_doubling_time, extinction_risk
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

    var _acc_exponential_growth: Float64 = 0.0
    var _t0_exponential_growth = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_growth += exponential_growth(0.5, 0.5, 0.5)
    var _t1_exponential_growth = perf_counter_ns()
    var _ns_exponential_growth = Float64(_t1_exponential_growth - _t0_exponential_growth) / Float64(N)
    print("MOJO_TIMING population::exponential_growth", _ns_exponential_growth, _acc_exponential_growth)
    var _result_exponential_growth = exponential_growth(0.5, 0.5, 0.5)
    var _summary_exponential_growth = _summary_float64(_result_exponential_growth)
    print("MOJO_RESULT population::exponential_growth", _summary_exponential_growth)
    var _acc_logistic_growth: Float64 = 0.0
    var _t0_logistic_growth = perf_counter_ns()
    for _ in range(N):
        _acc_logistic_growth += logistic_growth(0.5, 0.5, 0.5)
    var _t1_logistic_growth = perf_counter_ns()
    var _ns_logistic_growth = Float64(_t1_logistic_growth - _t0_logistic_growth) / Float64(N)
    print("MOJO_TIMING population::logistic_growth", _ns_logistic_growth, _acc_logistic_growth)
    var _result_logistic_growth = logistic_growth(0.5, 0.5, 0.5)
    var _summary_logistic_growth = _summary_float64(_result_logistic_growth)
    print("MOJO_RESULT population::logistic_growth", _summary_logistic_growth)
    var _acc_logistic_simulate: Float64 = 0.0
    var _t0_logistic_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_logistic_simulate = logistic_simulate(0.5, 0.5, 0.5, 5)
        _acc_logistic_simulate += Float64(len(_r_logistic_simulate))
    var _t1_logistic_simulate = perf_counter_ns()
    var _ns_logistic_simulate = Float64(_t1_logistic_simulate - _t0_logistic_simulate) / Float64(N)
    print("MOJO_TIMING population::logistic_simulate", _ns_logistic_simulate, _acc_logistic_simulate)
    var _result_logistic_simulate = logistic_simulate(0.5, 0.5, 0.5, 5)
    var _summary_logistic_simulate = _summary_list_float64(_result_logistic_simulate)
    print("MOJO_RESULT population::logistic_simulate", _summary_logistic_simulate)
    var _acc_lotka_volterra_step: Float64 = 0.0
    var _t0_lotka_volterra_step = perf_counter_ns()
    for _ in range(N):
        var _r_lotka_volterra_step = lotka_volterra_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_lotka_volterra_step += Float64(len(_r_lotka_volterra_step))
    var _t1_lotka_volterra_step = perf_counter_ns()
    var _ns_lotka_volterra_step = Float64(_t1_lotka_volterra_step - _t0_lotka_volterra_step) / Float64(N)
    print("MOJO_TIMING population::lotka_volterra_step", _ns_lotka_volterra_step, _acc_lotka_volterra_step)
    var _result_lotka_volterra_step = lotka_volterra_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_lotka_volterra_step = _summary_list_float64(_result_lotka_volterra_step)
    print("MOJO_RESULT population::lotka_volterra_step", _summary_lotka_volterra_step)
    var _acc_lotka_volterra_simulate: Float64 = 0.0
    var _t0_lotka_volterra_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_lotka_volterra_simulate = lotka_volterra_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_lotka_volterra_simulate += Float64(len(_r_lotka_volterra_simulate))
    var _t1_lotka_volterra_simulate = perf_counter_ns()
    var _ns_lotka_volterra_simulate = Float64(_t1_lotka_volterra_simulate - _t0_lotka_volterra_simulate) / Float64(N)
    print("MOJO_TIMING population::lotka_volterra_simulate", _ns_lotka_volterra_simulate, _acc_lotka_volterra_simulate)
    var _result_lotka_volterra_simulate = lotka_volterra_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
    var _summary_lotka_volterra_simulate = _summary_list_list_float64(_result_lotka_volterra_simulate)
    print("MOJO_RESULT population::lotka_volterra_simulate", _summary_lotka_volterra_simulate)
    var _acc_carrying_capacity_estimate: Float64 = 0.0
    var _t0_carrying_capacity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_carrying_capacity_estimate += carrying_capacity_estimate(_lf5)
    var _t1_carrying_capacity_estimate = perf_counter_ns()
    var _ns_carrying_capacity_estimate = Float64(_t1_carrying_capacity_estimate - _t0_carrying_capacity_estimate) / Float64(N)
    print("MOJO_TIMING population::carrying_capacity_estimate", _ns_carrying_capacity_estimate, _acc_carrying_capacity_estimate)
    var _result_carrying_capacity_estimate = carrying_capacity_estimate(_lf5)
    var _summary_carrying_capacity_estimate = _summary_float64(_result_carrying_capacity_estimate)
    print("MOJO_RESULT population::carrying_capacity_estimate", _summary_carrying_capacity_estimate)
    var _acc_growth_rate_estimate: Float64 = 0.0
    var _t0_growth_rate_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_growth_rate_estimate += growth_rate_estimate(0.5, 0.5, 0.5)
    var _t1_growth_rate_estimate = perf_counter_ns()
    var _ns_growth_rate_estimate = Float64(_t1_growth_rate_estimate - _t0_growth_rate_estimate) / Float64(N)
    print("MOJO_TIMING population::growth_rate_estimate", _ns_growth_rate_estimate, _acc_growth_rate_estimate)
    var _result_growth_rate_estimate = growth_rate_estimate(0.5, 0.5, 0.5)
    var _summary_growth_rate_estimate = _summary_float64(_result_growth_rate_estimate)
    print("MOJO_RESULT population::growth_rate_estimate", _summary_growth_rate_estimate)
    var _acc_competition_model: Float64 = 0.0
    var _t0_competition_model = perf_counter_ns()
    for _ in range(N):
        var _r_competition_model = competition_model(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_competition_model += Float64(len(_r_competition_model))
    var _t1_competition_model = perf_counter_ns()
    var _ns_competition_model = Float64(_t1_competition_model - _t0_competition_model) / Float64(N)
    print("MOJO_TIMING population::competition_model", _ns_competition_model, _acc_competition_model)
    var _result_competition_model = competition_model(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_competition_model = _summary_list_float64(_result_competition_model)
    print("MOJO_RESULT population::competition_model", _summary_competition_model)
    var _acc_population_doubling_time: Float64 = 0.0
    var _t0_population_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_population_doubling_time += population_doubling_time(0.5)
    var _t1_population_doubling_time = perf_counter_ns()
    var _ns_population_doubling_time = Float64(_t1_population_doubling_time - _t0_population_doubling_time) / Float64(N)
    print("MOJO_TIMING population::population_doubling_time", _ns_population_doubling_time, _acc_population_doubling_time)
    var _result_population_doubling_time = population_doubling_time(0.5)
    var _summary_population_doubling_time = _summary_float64(_result_population_doubling_time)
    print("MOJO_RESULT population::population_doubling_time", _summary_population_doubling_time)
    var _acc_extinction_risk: Float64 = 0.0
    var _t0_extinction_risk = perf_counter_ns()
    for _ in range(N):
        _acc_extinction_risk += Float64(extinction_risk(0.5, 0.5))
    var _t1_extinction_risk = perf_counter_ns()
    var _ns_extinction_risk = Float64(_t1_extinction_risk - _t0_extinction_risk) / Float64(N)
    print("MOJO_TIMING population::extinction_risk", _ns_extinction_risk, _acc_extinction_risk)
    var _result_extinction_risk = extinction_risk(0.5, 0.5)
    var _summary_extinction_risk = _summary_bool(_result_extinction_risk)
    print("MOJO_RESULT population::extinction_risk", _summary_extinction_risk)
