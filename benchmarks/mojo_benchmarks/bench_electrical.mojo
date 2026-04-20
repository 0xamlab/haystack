"""bench_electrical.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from electrical import ohms_law_v, ohms_law_i, ohms_law_r, power_dc, series_resistance, parallel_resistance, rc_time_constant, rc_voltage, rlc_resonance, impedance_magnitude, power_factor, capacitive_reactance, inductive_reactance, voltage_divider
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

    var _acc_ohms_law_v: Float64 = 0.0
    var _t0_ohms_law_v = perf_counter_ns()
    for _ in range(N):
        _acc_ohms_law_v += ohms_law_v(0.5, 0.5)
    var _t1_ohms_law_v = perf_counter_ns()
    var _ns_ohms_law_v = Float64(_t1_ohms_law_v - _t0_ohms_law_v) / Float64(N)
    print("MOJO_TIMING electrical::ohms_law_v", _ns_ohms_law_v, _acc_ohms_law_v)
    var _acc_ohms_law_i: Float64 = 0.0
    var _t0_ohms_law_i = perf_counter_ns()
    for _ in range(N):
        _acc_ohms_law_i += ohms_law_i(0.5, 0.5)
    var _t1_ohms_law_i = perf_counter_ns()
    var _ns_ohms_law_i = Float64(_t1_ohms_law_i - _t0_ohms_law_i) / Float64(N)
    print("MOJO_TIMING electrical::ohms_law_i", _ns_ohms_law_i, _acc_ohms_law_i)
    var _acc_ohms_law_r: Float64 = 0.0
    var _t0_ohms_law_r = perf_counter_ns()
    for _ in range(N):
        _acc_ohms_law_r += ohms_law_r(0.5, 0.5)
    var _t1_ohms_law_r = perf_counter_ns()
    var _ns_ohms_law_r = Float64(_t1_ohms_law_r - _t0_ohms_law_r) / Float64(N)
    print("MOJO_TIMING electrical::ohms_law_r", _ns_ohms_law_r, _acc_ohms_law_r)
    var _acc_power_dc: Float64 = 0.0
    var _t0_power_dc = perf_counter_ns()
    for _ in range(N):
        _acc_power_dc += power_dc(0.5, 0.5)
    var _t1_power_dc = perf_counter_ns()
    var _ns_power_dc = Float64(_t1_power_dc - _t0_power_dc) / Float64(N)
    print("MOJO_TIMING electrical::power_dc", _ns_power_dc, _acc_power_dc)
    var _acc_series_resistance: Float64 = 0.0
    var _t0_series_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_series_resistance += series_resistance(_lf5)
    var _t1_series_resistance = perf_counter_ns()
    var _ns_series_resistance = Float64(_t1_series_resistance - _t0_series_resistance) / Float64(N)
    print("MOJO_TIMING electrical::series_resistance", _ns_series_resistance, _acc_series_resistance)
    var _acc_parallel_resistance: Float64 = 0.0
    var _t0_parallel_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_parallel_resistance += parallel_resistance(_lf5)
    var _t1_parallel_resistance = perf_counter_ns()
    var _ns_parallel_resistance = Float64(_t1_parallel_resistance - _t0_parallel_resistance) / Float64(N)
    print("MOJO_TIMING electrical::parallel_resistance", _ns_parallel_resistance, _acc_parallel_resistance)
    var _acc_rc_time_constant: Float64 = 0.0
    var _t0_rc_time_constant = perf_counter_ns()
    for _ in range(N):
        _acc_rc_time_constant += rc_time_constant(0.5, 0.5)
    var _t1_rc_time_constant = perf_counter_ns()
    var _ns_rc_time_constant = Float64(_t1_rc_time_constant - _t0_rc_time_constant) / Float64(N)
    print("MOJO_TIMING electrical::rc_time_constant", _ns_rc_time_constant, _acc_rc_time_constant)
    var _acc_rc_voltage: Float64 = 0.0
    var _t0_rc_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_rc_voltage += rc_voltage(0.5, 0.5, 0.5, 0.5)
    var _t1_rc_voltage = perf_counter_ns()
    var _ns_rc_voltage = Float64(_t1_rc_voltage - _t0_rc_voltage) / Float64(N)
    print("MOJO_TIMING electrical::rc_voltage", _ns_rc_voltage, _acc_rc_voltage)
    var _acc_rlc_resonance: Float64 = 0.0
    var _t0_rlc_resonance = perf_counter_ns()
    for _ in range(N):
        _acc_rlc_resonance += rlc_resonance(0.5, 0.5)
    var _t1_rlc_resonance = perf_counter_ns()
    var _ns_rlc_resonance = Float64(_t1_rlc_resonance - _t0_rlc_resonance) / Float64(N)
    print("MOJO_TIMING electrical::rlc_resonance", _ns_rlc_resonance, _acc_rlc_resonance)
    var _acc_impedance_magnitude: Float64 = 0.0
    var _t0_impedance_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_impedance_magnitude += impedance_magnitude(0.5, 0.5)
    var _t1_impedance_magnitude = perf_counter_ns()
    var _ns_impedance_magnitude = Float64(_t1_impedance_magnitude - _t0_impedance_magnitude) / Float64(N)
    print("MOJO_TIMING electrical::impedance_magnitude", _ns_impedance_magnitude, _acc_impedance_magnitude)
    var _acc_power_factor: Float64 = 0.0
    var _t0_power_factor = perf_counter_ns()
    for _ in range(N):
        _acc_power_factor += power_factor(0.5, 0.5)
    var _t1_power_factor = perf_counter_ns()
    var _ns_power_factor = Float64(_t1_power_factor - _t0_power_factor) / Float64(N)
    print("MOJO_TIMING electrical::power_factor", _ns_power_factor, _acc_power_factor)
    var _acc_capacitive_reactance: Float64 = 0.0
    var _t0_capacitive_reactance = perf_counter_ns()
    for _ in range(N):
        _acc_capacitive_reactance += capacitive_reactance(0.5, 0.5)
    var _t1_capacitive_reactance = perf_counter_ns()
    var _ns_capacitive_reactance = Float64(_t1_capacitive_reactance - _t0_capacitive_reactance) / Float64(N)
    print("MOJO_TIMING electrical::capacitive_reactance", _ns_capacitive_reactance, _acc_capacitive_reactance)
    var _acc_inductive_reactance: Float64 = 0.0
    var _t0_inductive_reactance = perf_counter_ns()
    for _ in range(N):
        _acc_inductive_reactance += inductive_reactance(0.5, 0.5)
    var _t1_inductive_reactance = perf_counter_ns()
    var _ns_inductive_reactance = Float64(_t1_inductive_reactance - _t0_inductive_reactance) / Float64(N)
    print("MOJO_TIMING electrical::inductive_reactance", _ns_inductive_reactance, _acc_inductive_reactance)
    var _acc_voltage_divider: Float64 = 0.0
    var _t0_voltage_divider = perf_counter_ns()
    for _ in range(N):
        _acc_voltage_divider += voltage_divider(0.5, 0.5, 0.5)
    var _t1_voltage_divider = perf_counter_ns()
    var _ns_voltage_divider = Float64(_t1_voltage_divider - _t0_voltage_divider) / Float64(N)
    print("MOJO_TIMING electrical::voltage_divider", _ns_voltage_divider, _acc_voltage_divider)
