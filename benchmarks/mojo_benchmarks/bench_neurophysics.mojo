"""bench_neurophysics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from neurophysics import nernst_potential, goldman_equation, membrane_time_constant, cable_length_constant, action_potential_threshold, firing_rate_simple, synaptic_current, integrate_and_fire_voltage, eeg_spectral_power, conduction_velocity
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

    var _acc_nernst_potential: Float64 = 0.0
    var _t0_nernst_potential = perf_counter_ns()
    for _ in range(N):
        _acc_nernst_potential += nernst_potential(0.5, 0.5, 0.5, 0.5)
    var _t1_nernst_potential = perf_counter_ns()
    var _ns_nernst_potential = Float64(_t1_nernst_potential - _t0_nernst_potential) / Float64(N)
    print("MOJO_TIMING neurophysics::nernst_potential", _ns_nernst_potential, _acc_nernst_potential)
    var _result_nernst_potential = nernst_potential(0.5, 0.5, 0.5, 0.5)
    var _summary_nernst_potential = _summary_float64(_result_nernst_potential)
    print("MOJO_RESULT neurophysics::nernst_potential", _summary_nernst_potential)
    var _acc_goldman_equation: Float64 = 0.0
    var _t0_goldman_equation = perf_counter_ns()
    for _ in range(N):
        _acc_goldman_equation += goldman_equation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_goldman_equation = perf_counter_ns()
    var _ns_goldman_equation = Float64(_t1_goldman_equation - _t0_goldman_equation) / Float64(N)
    print("MOJO_TIMING neurophysics::goldman_equation", _ns_goldman_equation, _acc_goldman_equation)
    var _result_goldman_equation = goldman_equation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_goldman_equation = _summary_float64(_result_goldman_equation)
    print("MOJO_RESULT neurophysics::goldman_equation", _summary_goldman_equation)
    var _acc_membrane_time_constant: Float64 = 0.0
    var _t0_membrane_time_constant = perf_counter_ns()
    for _ in range(N):
        _acc_membrane_time_constant += membrane_time_constant(0.5, 0.5)
    var _t1_membrane_time_constant = perf_counter_ns()
    var _ns_membrane_time_constant = Float64(_t1_membrane_time_constant - _t0_membrane_time_constant) / Float64(N)
    print("MOJO_TIMING neurophysics::membrane_time_constant", _ns_membrane_time_constant, _acc_membrane_time_constant)
    var _result_membrane_time_constant = membrane_time_constant(0.5, 0.5)
    var _summary_membrane_time_constant = _summary_float64(_result_membrane_time_constant)
    print("MOJO_RESULT neurophysics::membrane_time_constant", _summary_membrane_time_constant)
    var _acc_cable_length_constant: Float64 = 0.0
    var _t0_cable_length_constant = perf_counter_ns()
    for _ in range(N):
        _acc_cable_length_constant += cable_length_constant(0.5, 0.5)
    var _t1_cable_length_constant = perf_counter_ns()
    var _ns_cable_length_constant = Float64(_t1_cable_length_constant - _t0_cable_length_constant) / Float64(N)
    print("MOJO_TIMING neurophysics::cable_length_constant", _ns_cable_length_constant, _acc_cable_length_constant)
    var _result_cable_length_constant = cable_length_constant(0.5, 0.5)
    var _summary_cable_length_constant = _summary_float64(_result_cable_length_constant)
    print("MOJO_RESULT neurophysics::cable_length_constant", _summary_cable_length_constant)
    var _acc_action_potential_threshold: Float64 = 0.0
    var _t0_action_potential_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_action_potential_threshold += action_potential_threshold(0.5, 0.5, 0.5)
    var _t1_action_potential_threshold = perf_counter_ns()
    var _ns_action_potential_threshold = Float64(_t1_action_potential_threshold - _t0_action_potential_threshold) / Float64(N)
    print("MOJO_TIMING neurophysics::action_potential_threshold", _ns_action_potential_threshold, _acc_action_potential_threshold)
    var _result_action_potential_threshold = action_potential_threshold(0.5, 0.5, 0.5)
    var _summary_action_potential_threshold = _summary_float64(_result_action_potential_threshold)
    print("MOJO_RESULT neurophysics::action_potential_threshold", _summary_action_potential_threshold)
    var _acc_firing_rate_simple: Float64 = 0.0
    var _t0_firing_rate_simple = perf_counter_ns()
    for _ in range(N):
        _acc_firing_rate_simple += firing_rate_simple(0.5, 0.5)
    var _t1_firing_rate_simple = perf_counter_ns()
    var _ns_firing_rate_simple = Float64(_t1_firing_rate_simple - _t0_firing_rate_simple) / Float64(N)
    print("MOJO_TIMING neurophysics::firing_rate_simple", _ns_firing_rate_simple, _acc_firing_rate_simple)
    var _result_firing_rate_simple = firing_rate_simple(0.5, 0.5)
    var _summary_firing_rate_simple = _summary_float64(_result_firing_rate_simple)
    print("MOJO_RESULT neurophysics::firing_rate_simple", _summary_firing_rate_simple)
    var _acc_synaptic_current: Float64 = 0.0
    var _t0_synaptic_current = perf_counter_ns()
    for _ in range(N):
        _acc_synaptic_current += synaptic_current(0.5, 0.5, 0.5)
    var _t1_synaptic_current = perf_counter_ns()
    var _ns_synaptic_current = Float64(_t1_synaptic_current - _t0_synaptic_current) / Float64(N)
    print("MOJO_TIMING neurophysics::synaptic_current", _ns_synaptic_current, _acc_synaptic_current)
    var _result_synaptic_current = synaptic_current(0.5, 0.5, 0.5)
    var _summary_synaptic_current = _summary_float64(_result_synaptic_current)
    print("MOJO_RESULT neurophysics::synaptic_current", _summary_synaptic_current)
    var _acc_integrate_and_fire_voltage: Float64 = 0.0
    var _t0_integrate_and_fire_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_integrate_and_fire_voltage += integrate_and_fire_voltage(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_integrate_and_fire_voltage = perf_counter_ns()
    var _ns_integrate_and_fire_voltage = Float64(_t1_integrate_and_fire_voltage - _t0_integrate_and_fire_voltage) / Float64(N)
    print("MOJO_TIMING neurophysics::integrate_and_fire_voltage", _ns_integrate_and_fire_voltage, _acc_integrate_and_fire_voltage)
    var _result_integrate_and_fire_voltage = integrate_and_fire_voltage(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_integrate_and_fire_voltage = _summary_float64(_result_integrate_and_fire_voltage)
    print("MOJO_RESULT neurophysics::integrate_and_fire_voltage", _summary_integrate_and_fire_voltage)
    var _acc_eeg_spectral_power: Float64 = 0.0
    var _t0_eeg_spectral_power = perf_counter_ns()
    for _ in range(N):
        _acc_eeg_spectral_power += eeg_spectral_power(0.5, 0.5)
    var _t1_eeg_spectral_power = perf_counter_ns()
    var _ns_eeg_spectral_power = Float64(_t1_eeg_spectral_power - _t0_eeg_spectral_power) / Float64(N)
    print("MOJO_TIMING neurophysics::eeg_spectral_power", _ns_eeg_spectral_power, _acc_eeg_spectral_power)
    var _result_eeg_spectral_power = eeg_spectral_power(0.5, 0.5)
    var _summary_eeg_spectral_power = _summary_float64(_result_eeg_spectral_power)
    print("MOJO_RESULT neurophysics::eeg_spectral_power", _summary_eeg_spectral_power)
    var _acc_conduction_velocity: Float64 = 0.0
    var _t0_conduction_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_conduction_velocity += conduction_velocity(0.5)
    var _t1_conduction_velocity = perf_counter_ns()
    var _ns_conduction_velocity = Float64(_t1_conduction_velocity - _t0_conduction_velocity) / Float64(N)
    print("MOJO_TIMING neurophysics::conduction_velocity", _ns_conduction_velocity, _acc_conduction_velocity)
    var _result_conduction_velocity = conduction_velocity(0.5)
    var _summary_conduction_velocity = _summary_float64(_result_conduction_velocity)
    print("MOJO_RESULT neurophysics::conduction_velocity", _summary_conduction_velocity)
