"""bench_epidemiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from epidemiology import sir_step, sir_simulate, seir_step, basic_reproduction_number, herd_immunity_threshold, effective_reproduction, doubling_time, attack_rate, case_fatality_rate, incidence_rate
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

    var _acc_sir_step: Float64 = 0.0
    var _t0_sir_step = perf_counter_ns()
    for _ in range(N):
        var _r_sir_step = sir_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_sir_step += Float64(len(_r_sir_step))
    var _t1_sir_step = perf_counter_ns()
    var _ns_sir_step = Float64(_t1_sir_step - _t0_sir_step) / Float64(N)
    print("MOJO_TIMING epidemiology::sir_step", _ns_sir_step, _acc_sir_step)
    var _result_sir_step = sir_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_sir_step = _summary_list_float64(_result_sir_step)
    print("MOJO_RESULT epidemiology::sir_step", _summary_sir_step)
    var _acc_sir_simulate: Float64 = 0.0
    var _t0_sir_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_sir_simulate = sir_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_sir_simulate += Float64(len(_r_sir_simulate))
    var _t1_sir_simulate = perf_counter_ns()
    var _ns_sir_simulate = Float64(_t1_sir_simulate - _t0_sir_simulate) / Float64(N)
    print("MOJO_TIMING epidemiology::sir_simulate", _ns_sir_simulate, _acc_sir_simulate)
    var _result_sir_simulate = sir_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
    var _summary_sir_simulate = _summary_list_list_float64(_result_sir_simulate)
    print("MOJO_RESULT epidemiology::sir_simulate", _summary_sir_simulate)
    var _acc_seir_step: Float64 = 0.0
    var _t0_seir_step = perf_counter_ns()
    for _ in range(N):
        var _r_seir_step = seir_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_seir_step += Float64(len(_r_seir_step))
    var _t1_seir_step = perf_counter_ns()
    var _ns_seir_step = Float64(_t1_seir_step - _t0_seir_step) / Float64(N)
    print("MOJO_TIMING epidemiology::seir_step", _ns_seir_step, _acc_seir_step)
    var _result_seir_step = seir_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_seir_step = _summary_list_float64(_result_seir_step)
    print("MOJO_RESULT epidemiology::seir_step", _summary_seir_step)
    var _acc_basic_reproduction_number: Float64 = 0.0
    var _t0_basic_reproduction_number = perf_counter_ns()
    for _ in range(N):
        _acc_basic_reproduction_number += basic_reproduction_number(0.5, 0.5)
    var _t1_basic_reproduction_number = perf_counter_ns()
    var _ns_basic_reproduction_number = Float64(_t1_basic_reproduction_number - _t0_basic_reproduction_number) / Float64(N)
    print("MOJO_TIMING epidemiology::basic_reproduction_number", _ns_basic_reproduction_number, _acc_basic_reproduction_number)
    var _result_basic_reproduction_number = basic_reproduction_number(0.5, 0.5)
    var _summary_basic_reproduction_number = _summary_float64(_result_basic_reproduction_number)
    print("MOJO_RESULT epidemiology::basic_reproduction_number", _summary_basic_reproduction_number)
    var _acc_herd_immunity_threshold: Float64 = 0.0
    var _t0_herd_immunity_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_herd_immunity_threshold += herd_immunity_threshold(0.5)
    var _t1_herd_immunity_threshold = perf_counter_ns()
    var _ns_herd_immunity_threshold = Float64(_t1_herd_immunity_threshold - _t0_herd_immunity_threshold) / Float64(N)
    print("MOJO_TIMING epidemiology::herd_immunity_threshold", _ns_herd_immunity_threshold, _acc_herd_immunity_threshold)
    var _result_herd_immunity_threshold = herd_immunity_threshold(0.5)
    var _summary_herd_immunity_threshold = _summary_float64(_result_herd_immunity_threshold)
    print("MOJO_RESULT epidemiology::herd_immunity_threshold", _summary_herd_immunity_threshold)
    var _acc_effective_reproduction: Float64 = 0.0
    var _t0_effective_reproduction = perf_counter_ns()
    for _ in range(N):
        _acc_effective_reproduction += effective_reproduction(0.5, 0.5)
    var _t1_effective_reproduction = perf_counter_ns()
    var _ns_effective_reproduction = Float64(_t1_effective_reproduction - _t0_effective_reproduction) / Float64(N)
    print("MOJO_TIMING epidemiology::effective_reproduction", _ns_effective_reproduction, _acc_effective_reproduction)
    var _result_effective_reproduction = effective_reproduction(0.5, 0.5)
    var _summary_effective_reproduction = _summary_float64(_result_effective_reproduction)
    print("MOJO_RESULT epidemiology::effective_reproduction", _summary_effective_reproduction)
    var _acc_doubling_time: Float64 = 0.0
    var _t0_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time += doubling_time(0.5)
    var _t1_doubling_time = perf_counter_ns()
    var _ns_doubling_time = Float64(_t1_doubling_time - _t0_doubling_time) / Float64(N)
    print("MOJO_TIMING epidemiology::doubling_time", _ns_doubling_time, _acc_doubling_time)
    var _result_doubling_time = doubling_time(0.5)
    var _summary_doubling_time = _summary_float64(_result_doubling_time)
    print("MOJO_RESULT epidemiology::doubling_time", _summary_doubling_time)
    var _acc_attack_rate: Float64 = 0.0
    var _t0_attack_rate = perf_counter_ns()
    for _ in range(N):
        _acc_attack_rate += attack_rate(0.5)
    var _t1_attack_rate = perf_counter_ns()
    var _ns_attack_rate = Float64(_t1_attack_rate - _t0_attack_rate) / Float64(N)
    print("MOJO_TIMING epidemiology::attack_rate", _ns_attack_rate, _acc_attack_rate)
    var _result_attack_rate = attack_rate(0.5)
    var _summary_attack_rate = _summary_float64(_result_attack_rate)
    print("MOJO_RESULT epidemiology::attack_rate", _summary_attack_rate)
    var _acc_case_fatality_rate: Float64 = 0.0
    var _t0_case_fatality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_case_fatality_rate += case_fatality_rate(5, 5)
    var _t1_case_fatality_rate = perf_counter_ns()
    var _ns_case_fatality_rate = Float64(_t1_case_fatality_rate - _t0_case_fatality_rate) / Float64(N)
    print("MOJO_TIMING epidemiology::case_fatality_rate", _ns_case_fatality_rate, _acc_case_fatality_rate)
    var _result_case_fatality_rate = case_fatality_rate(5, 5)
    var _summary_case_fatality_rate = _summary_float64(_result_case_fatality_rate)
    print("MOJO_RESULT epidemiology::case_fatality_rate", _summary_case_fatality_rate)
    var _acc_incidence_rate: Float64 = 0.0
    var _t0_incidence_rate = perf_counter_ns()
    for _ in range(N):
        _acc_incidence_rate += incidence_rate(5, 5, 0.5)
    var _t1_incidence_rate = perf_counter_ns()
    var _ns_incidence_rate = Float64(_t1_incidence_rate - _t0_incidence_rate) / Float64(N)
    print("MOJO_TIMING epidemiology::incidence_rate", _ns_incidence_rate, _acc_incidence_rate)
    var _result_incidence_rate = incidence_rate(5, 5, 0.5)
    var _summary_incidence_rate = _summary_float64(_result_incidence_rate)
    print("MOJO_RESULT epidemiology::incidence_rate", _summary_incidence_rate)
