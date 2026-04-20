"""bench_epidemiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from epidemiology import sir_step, sir_simulate, seir_step, basic_reproduction_number, herd_immunity_threshold, effective_reproduction, doubling_time, attack_rate, case_fatality_rate, incidence_rate
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

    var _acc_sir_step: Float64 = 0.0
    var _t0_sir_step = perf_counter_ns()
    for _ in range(N):
        var _r_sir_step = sir_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_sir_step += Float64(len(_r_sir_step))
    var _t1_sir_step = perf_counter_ns()
    var _ns_sir_step = Float64(_t1_sir_step - _t0_sir_step) / Float64(N)
    print("MOJO_TIMING epidemiology::sir_step", _ns_sir_step, _acc_sir_step)
    var _acc_sir_simulate: Float64 = 0.0
    var _t0_sir_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_sir_simulate = sir_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_sir_simulate += Float64(len(_r_sir_simulate))
    var _t1_sir_simulate = perf_counter_ns()
    var _ns_sir_simulate = Float64(_t1_sir_simulate - _t0_sir_simulate) / Float64(N)
    print("MOJO_TIMING epidemiology::sir_simulate", _ns_sir_simulate, _acc_sir_simulate)
    var _acc_seir_step: Float64 = 0.0
    var _t0_seir_step = perf_counter_ns()
    for _ in range(N):
        var _r_seir_step = seir_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_seir_step += Float64(len(_r_seir_step))
    var _t1_seir_step = perf_counter_ns()
    var _ns_seir_step = Float64(_t1_seir_step - _t0_seir_step) / Float64(N)
    print("MOJO_TIMING epidemiology::seir_step", _ns_seir_step, _acc_seir_step)
    var _acc_basic_reproduction_number: Float64 = 0.0
    var _t0_basic_reproduction_number = perf_counter_ns()
    for _ in range(N):
        _acc_basic_reproduction_number += basic_reproduction_number(0.5, 0.5)
    var _t1_basic_reproduction_number = perf_counter_ns()
    var _ns_basic_reproduction_number = Float64(_t1_basic_reproduction_number - _t0_basic_reproduction_number) / Float64(N)
    print("MOJO_TIMING epidemiology::basic_reproduction_number", _ns_basic_reproduction_number, _acc_basic_reproduction_number)
    var _acc_herd_immunity_threshold: Float64 = 0.0
    var _t0_herd_immunity_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_herd_immunity_threshold += herd_immunity_threshold(0.5)
    var _t1_herd_immunity_threshold = perf_counter_ns()
    var _ns_herd_immunity_threshold = Float64(_t1_herd_immunity_threshold - _t0_herd_immunity_threshold) / Float64(N)
    print("MOJO_TIMING epidemiology::herd_immunity_threshold", _ns_herd_immunity_threshold, _acc_herd_immunity_threshold)
    var _acc_effective_reproduction: Float64 = 0.0
    var _t0_effective_reproduction = perf_counter_ns()
    for _ in range(N):
        _acc_effective_reproduction += effective_reproduction(0.5, 0.5)
    var _t1_effective_reproduction = perf_counter_ns()
    var _ns_effective_reproduction = Float64(_t1_effective_reproduction - _t0_effective_reproduction) / Float64(N)
    print("MOJO_TIMING epidemiology::effective_reproduction", _ns_effective_reproduction, _acc_effective_reproduction)
    var _acc_doubling_time: Float64 = 0.0
    var _t0_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time += doubling_time(0.5)
    var _t1_doubling_time = perf_counter_ns()
    var _ns_doubling_time = Float64(_t1_doubling_time - _t0_doubling_time) / Float64(N)
    print("MOJO_TIMING epidemiology::doubling_time", _ns_doubling_time, _acc_doubling_time)
    var _acc_attack_rate: Float64 = 0.0
    var _t0_attack_rate = perf_counter_ns()
    for _ in range(N):
        _acc_attack_rate += attack_rate(0.5)
    var _t1_attack_rate = perf_counter_ns()
    var _ns_attack_rate = Float64(_t1_attack_rate - _t0_attack_rate) / Float64(N)
    print("MOJO_TIMING epidemiology::attack_rate", _ns_attack_rate, _acc_attack_rate)
    var _acc_case_fatality_rate: Float64 = 0.0
    var _t0_case_fatality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_case_fatality_rate += case_fatality_rate(5, 5)
    var _t1_case_fatality_rate = perf_counter_ns()
    var _ns_case_fatality_rate = Float64(_t1_case_fatality_rate - _t0_case_fatality_rate) / Float64(N)
    print("MOJO_TIMING epidemiology::case_fatality_rate", _ns_case_fatality_rate, _acc_case_fatality_rate)
    var _acc_incidence_rate: Float64 = 0.0
    var _t0_incidence_rate = perf_counter_ns()
    for _ in range(N):
        _acc_incidence_rate += incidence_rate(5, 5, 0.5)
    var _t1_incidence_rate = perf_counter_ns()
    var _ns_incidence_rate = Float64(_t1_incidence_rate - _t0_incidence_rate) / Float64(N)
    print("MOJO_TIMING epidemiology::incidence_rate", _ns_incidence_rate, _acc_incidence_rate)
