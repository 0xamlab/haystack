"""bench_electrical.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from electrical import ohms_law_v, ohms_law_i, ohms_law_r, power_dc, series_resistance, parallel_resistance, rc_time_constant, rc_voltage, rlc_resonance, impedance_magnitude, power_factor, capacitive_reactance, inductive_reactance, voltage_divider
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

    var _acc_ohms_law_v: Float64 = 0.0
    var _t0_ohms_law_v = perf_counter_ns()
    for _ in range(N):
        _acc_ohms_law_v += ohms_law_v(0.5, 0.5)
    var _t1_ohms_law_v = perf_counter_ns()
    var _ns_ohms_law_v = Float64(_t1_ohms_law_v - _t0_ohms_law_v) / Float64(N)
    print("MOJO_TIMING electrical::ohms_law_v", _ns_ohms_law_v, _acc_ohms_law_v)
    var _result_ohms_law_v = ohms_law_v(0.5, 0.5)
    var _summary_ohms_law_v = _summary_float64(_result_ohms_law_v)
    print("MOJO_RESULT electrical::ohms_law_v", _summary_ohms_law_v)
    var _acc_ohms_law_i: Float64 = 0.0
    var _t0_ohms_law_i = perf_counter_ns()
    for _ in range(N):
        _acc_ohms_law_i += ohms_law_i(0.5, 0.5)
    var _t1_ohms_law_i = perf_counter_ns()
    var _ns_ohms_law_i = Float64(_t1_ohms_law_i - _t0_ohms_law_i) / Float64(N)
    print("MOJO_TIMING electrical::ohms_law_i", _ns_ohms_law_i, _acc_ohms_law_i)
    var _result_ohms_law_i = ohms_law_i(0.5, 0.5)
    var _summary_ohms_law_i = _summary_float64(_result_ohms_law_i)
    print("MOJO_RESULT electrical::ohms_law_i", _summary_ohms_law_i)
    var _acc_ohms_law_r: Float64 = 0.0
    var _t0_ohms_law_r = perf_counter_ns()
    for _ in range(N):
        _acc_ohms_law_r += ohms_law_r(0.5, 0.5)
    var _t1_ohms_law_r = perf_counter_ns()
    var _ns_ohms_law_r = Float64(_t1_ohms_law_r - _t0_ohms_law_r) / Float64(N)
    print("MOJO_TIMING electrical::ohms_law_r", _ns_ohms_law_r, _acc_ohms_law_r)
    var _result_ohms_law_r = ohms_law_r(0.5, 0.5)
    var _summary_ohms_law_r = _summary_float64(_result_ohms_law_r)
    print("MOJO_RESULT electrical::ohms_law_r", _summary_ohms_law_r)
    var _acc_power_dc: Float64 = 0.0
    var _t0_power_dc = perf_counter_ns()
    for _ in range(N):
        _acc_power_dc += power_dc(0.5, 0.5)
    var _t1_power_dc = perf_counter_ns()
    var _ns_power_dc = Float64(_t1_power_dc - _t0_power_dc) / Float64(N)
    print("MOJO_TIMING electrical::power_dc", _ns_power_dc, _acc_power_dc)
    var _result_power_dc = power_dc(0.5, 0.5)
    var _summary_power_dc = _summary_float64(_result_power_dc)
    print("MOJO_RESULT electrical::power_dc", _summary_power_dc)
    var _acc_series_resistance: Float64 = 0.0
    var _t0_series_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_series_resistance += series_resistance(_lf5)
    var _t1_series_resistance = perf_counter_ns()
    var _ns_series_resistance = Float64(_t1_series_resistance - _t0_series_resistance) / Float64(N)
    print("MOJO_TIMING electrical::series_resistance", _ns_series_resistance, _acc_series_resistance)
    var _result_series_resistance = series_resistance(_lf5)
    var _summary_series_resistance = _summary_float64(_result_series_resistance)
    print("MOJO_RESULT electrical::series_resistance", _summary_series_resistance)
    var _acc_parallel_resistance: Float64 = 0.0
    var _t0_parallel_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_parallel_resistance += parallel_resistance(_lf5)
    var _t1_parallel_resistance = perf_counter_ns()
    var _ns_parallel_resistance = Float64(_t1_parallel_resistance - _t0_parallel_resistance) / Float64(N)
    print("MOJO_TIMING electrical::parallel_resistance", _ns_parallel_resistance, _acc_parallel_resistance)
    var _result_parallel_resistance = parallel_resistance(_lf5)
    var _summary_parallel_resistance = _summary_float64(_result_parallel_resistance)
    print("MOJO_RESULT electrical::parallel_resistance", _summary_parallel_resistance)
    var _acc_rc_time_constant: Float64 = 0.0
    var _t0_rc_time_constant = perf_counter_ns()
    for _ in range(N):
        _acc_rc_time_constant += rc_time_constant(0.5, 0.5)
    var _t1_rc_time_constant = perf_counter_ns()
    var _ns_rc_time_constant = Float64(_t1_rc_time_constant - _t0_rc_time_constant) / Float64(N)
    print("MOJO_TIMING electrical::rc_time_constant", _ns_rc_time_constant, _acc_rc_time_constant)
    var _result_rc_time_constant = rc_time_constant(0.5, 0.5)
    var _summary_rc_time_constant = _summary_float64(_result_rc_time_constant)
    print("MOJO_RESULT electrical::rc_time_constant", _summary_rc_time_constant)
    var _acc_rc_voltage: Float64 = 0.0
    var _t0_rc_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_rc_voltage += rc_voltage(0.5, 0.5, 0.5, 0.5)
    var _t1_rc_voltage = perf_counter_ns()
    var _ns_rc_voltage = Float64(_t1_rc_voltage - _t0_rc_voltage) / Float64(N)
    print("MOJO_TIMING electrical::rc_voltage", _ns_rc_voltage, _acc_rc_voltage)
    var _result_rc_voltage = rc_voltage(0.5, 0.5, 0.5, 0.5)
    var _summary_rc_voltage = _summary_float64(_result_rc_voltage)
    print("MOJO_RESULT electrical::rc_voltage", _summary_rc_voltage)
    var _acc_rlc_resonance: Float64 = 0.0
    var _t0_rlc_resonance = perf_counter_ns()
    for _ in range(N):
        _acc_rlc_resonance += rlc_resonance(0.5, 0.5)
    var _t1_rlc_resonance = perf_counter_ns()
    var _ns_rlc_resonance = Float64(_t1_rlc_resonance - _t0_rlc_resonance) / Float64(N)
    print("MOJO_TIMING electrical::rlc_resonance", _ns_rlc_resonance, _acc_rlc_resonance)
    var _result_rlc_resonance = rlc_resonance(0.5, 0.5)
    var _summary_rlc_resonance = _summary_float64(_result_rlc_resonance)
    print("MOJO_RESULT electrical::rlc_resonance", _summary_rlc_resonance)
    var _acc_impedance_magnitude: Float64 = 0.0
    var _t0_impedance_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_impedance_magnitude += impedance_magnitude(0.5, 0.5)
    var _t1_impedance_magnitude = perf_counter_ns()
    var _ns_impedance_magnitude = Float64(_t1_impedance_magnitude - _t0_impedance_magnitude) / Float64(N)
    print("MOJO_TIMING electrical::impedance_magnitude", _ns_impedance_magnitude, _acc_impedance_magnitude)
    var _result_impedance_magnitude = impedance_magnitude(0.5, 0.5)
    var _summary_impedance_magnitude = _summary_float64(_result_impedance_magnitude)
    print("MOJO_RESULT electrical::impedance_magnitude", _summary_impedance_magnitude)
    var _acc_power_factor: Float64 = 0.0
    var _t0_power_factor = perf_counter_ns()
    for _ in range(N):
        _acc_power_factor += power_factor(0.5, 0.5)
    var _t1_power_factor = perf_counter_ns()
    var _ns_power_factor = Float64(_t1_power_factor - _t0_power_factor) / Float64(N)
    print("MOJO_TIMING electrical::power_factor", _ns_power_factor, _acc_power_factor)
    var _result_power_factor = power_factor(0.5, 0.5)
    var _summary_power_factor = _summary_float64(_result_power_factor)
    print("MOJO_RESULT electrical::power_factor", _summary_power_factor)
    var _acc_capacitive_reactance: Float64 = 0.0
    var _t0_capacitive_reactance = perf_counter_ns()
    for _ in range(N):
        _acc_capacitive_reactance += capacitive_reactance(0.5, 0.5)
    var _t1_capacitive_reactance = perf_counter_ns()
    var _ns_capacitive_reactance = Float64(_t1_capacitive_reactance - _t0_capacitive_reactance) / Float64(N)
    print("MOJO_TIMING electrical::capacitive_reactance", _ns_capacitive_reactance, _acc_capacitive_reactance)
    var _result_capacitive_reactance = capacitive_reactance(0.5, 0.5)
    var _summary_capacitive_reactance = _summary_float64(_result_capacitive_reactance)
    print("MOJO_RESULT electrical::capacitive_reactance", _summary_capacitive_reactance)
    var _acc_inductive_reactance: Float64 = 0.0
    var _t0_inductive_reactance = perf_counter_ns()
    for _ in range(N):
        _acc_inductive_reactance += inductive_reactance(0.5, 0.5)
    var _t1_inductive_reactance = perf_counter_ns()
    var _ns_inductive_reactance = Float64(_t1_inductive_reactance - _t0_inductive_reactance) / Float64(N)
    print("MOJO_TIMING electrical::inductive_reactance", _ns_inductive_reactance, _acc_inductive_reactance)
    var _result_inductive_reactance = inductive_reactance(0.5, 0.5)
    var _summary_inductive_reactance = _summary_float64(_result_inductive_reactance)
    print("MOJO_RESULT electrical::inductive_reactance", _summary_inductive_reactance)
    var _acc_voltage_divider: Float64 = 0.0
    var _t0_voltage_divider = perf_counter_ns()
    for _ in range(N):
        _acc_voltage_divider += voltage_divider(0.5, 0.5, 0.5)
    var _t1_voltage_divider = perf_counter_ns()
    var _ns_voltage_divider = Float64(_t1_voltage_divider - _t0_voltage_divider) / Float64(N)
    print("MOJO_TIMING electrical::voltage_divider", _ns_voltage_divider, _acc_voltage_divider)
    var _result_voltage_divider = voltage_divider(0.5, 0.5, 0.5)
    var _summary_voltage_divider = _summary_float64(_result_voltage_divider)
    print("MOJO_RESULT electrical::voltage_divider", _summary_voltage_divider)
