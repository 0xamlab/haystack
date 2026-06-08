"""bench_composites.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from composites import rule_of_mixtures_modulus, inverse_rule_of_mixtures, composite_density, fiber_volume_fraction, laminate_thickness, specific_stiffness, specific_strength, halpin_tsai, critical_fiber_length, shear_lag_stress_transfer, impact_energy_charpy, void_content
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

    var _acc_rule_of_mixtures_modulus: Float64 = 0.0
    var _t0_rule_of_mixtures_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_rule_of_mixtures_modulus += rule_of_mixtures_modulus(0.5, 0.5, 0.5)
    var _t1_rule_of_mixtures_modulus = perf_counter_ns()
    var _ns_rule_of_mixtures_modulus = Float64(_t1_rule_of_mixtures_modulus - _t0_rule_of_mixtures_modulus) / Float64(N)
    print("MOJO_TIMING composites::rule_of_mixtures_modulus", _ns_rule_of_mixtures_modulus, _acc_rule_of_mixtures_modulus)
    var _result_rule_of_mixtures_modulus = rule_of_mixtures_modulus(0.5, 0.5, 0.5)
    var _summary_rule_of_mixtures_modulus = _summary_float64(_result_rule_of_mixtures_modulus)
    print("MOJO_RESULT composites::rule_of_mixtures_modulus", _summary_rule_of_mixtures_modulus)
    var _acc_inverse_rule_of_mixtures: Float64 = 0.0
    var _t0_inverse_rule_of_mixtures = perf_counter_ns()
    for _ in range(N):
        _acc_inverse_rule_of_mixtures += inverse_rule_of_mixtures(0.5, 0.5, 0.5)
    var _t1_inverse_rule_of_mixtures = perf_counter_ns()
    var _ns_inverse_rule_of_mixtures = Float64(_t1_inverse_rule_of_mixtures - _t0_inverse_rule_of_mixtures) / Float64(N)
    print("MOJO_TIMING composites::inverse_rule_of_mixtures", _ns_inverse_rule_of_mixtures, _acc_inverse_rule_of_mixtures)
    var _result_inverse_rule_of_mixtures = inverse_rule_of_mixtures(0.5, 0.5, 0.5)
    var _summary_inverse_rule_of_mixtures = _summary_float64(_result_inverse_rule_of_mixtures)
    print("MOJO_RESULT composites::inverse_rule_of_mixtures", _summary_inverse_rule_of_mixtures)
    var _acc_composite_density: Float64 = 0.0
    var _t0_composite_density = perf_counter_ns()
    for _ in range(N):
        _acc_composite_density += composite_density(0.5, 0.5, 0.5)
    var _t1_composite_density = perf_counter_ns()
    var _ns_composite_density = Float64(_t1_composite_density - _t0_composite_density) / Float64(N)
    print("MOJO_TIMING composites::composite_density", _ns_composite_density, _acc_composite_density)
    var _result_composite_density = composite_density(0.5, 0.5, 0.5)
    var _summary_composite_density = _summary_float64(_result_composite_density)
    print("MOJO_RESULT composites::composite_density", _summary_composite_density)
    var _acc_fiber_volume_fraction: Float64 = 0.0
    var _t0_fiber_volume_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_fiber_volume_fraction += fiber_volume_fraction(0.5, 0.5, 0.5, 0.5)
    var _t1_fiber_volume_fraction = perf_counter_ns()
    var _ns_fiber_volume_fraction = Float64(_t1_fiber_volume_fraction - _t0_fiber_volume_fraction) / Float64(N)
    print("MOJO_TIMING composites::fiber_volume_fraction", _ns_fiber_volume_fraction, _acc_fiber_volume_fraction)
    var _result_fiber_volume_fraction = fiber_volume_fraction(0.5, 0.5, 0.5, 0.5)
    var _summary_fiber_volume_fraction = _summary_float64(_result_fiber_volume_fraction)
    print("MOJO_RESULT composites::fiber_volume_fraction", _summary_fiber_volume_fraction)
    var _acc_laminate_thickness: Float64 = 0.0
    var _t0_laminate_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_laminate_thickness += laminate_thickness(0.5, 0.5)
    var _t1_laminate_thickness = perf_counter_ns()
    var _ns_laminate_thickness = Float64(_t1_laminate_thickness - _t0_laminate_thickness) / Float64(N)
    print("MOJO_TIMING composites::laminate_thickness", _ns_laminate_thickness, _acc_laminate_thickness)
    var _result_laminate_thickness = laminate_thickness(0.5, 0.5)
    var _summary_laminate_thickness = _summary_float64(_result_laminate_thickness)
    print("MOJO_RESULT composites::laminate_thickness", _summary_laminate_thickness)
    var _acc_specific_stiffness: Float64 = 0.0
    var _t0_specific_stiffness = perf_counter_ns()
    for _ in range(N):
        _acc_specific_stiffness += specific_stiffness(0.5, 0.5)
    var _t1_specific_stiffness = perf_counter_ns()
    var _ns_specific_stiffness = Float64(_t1_specific_stiffness - _t0_specific_stiffness) / Float64(N)
    print("MOJO_TIMING composites::specific_stiffness", _ns_specific_stiffness, _acc_specific_stiffness)
    var _result_specific_stiffness = specific_stiffness(0.5, 0.5)
    var _summary_specific_stiffness = _summary_float64(_result_specific_stiffness)
    print("MOJO_RESULT composites::specific_stiffness", _summary_specific_stiffness)
    var _acc_specific_strength: Float64 = 0.0
    var _t0_specific_strength = perf_counter_ns()
    for _ in range(N):
        _acc_specific_strength += specific_strength(0.5, 0.5)
    var _t1_specific_strength = perf_counter_ns()
    var _ns_specific_strength = Float64(_t1_specific_strength - _t0_specific_strength) / Float64(N)
    print("MOJO_TIMING composites::specific_strength", _ns_specific_strength, _acc_specific_strength)
    var _result_specific_strength = specific_strength(0.5, 0.5)
    var _summary_specific_strength = _summary_float64(_result_specific_strength)
    print("MOJO_RESULT composites::specific_strength", _summary_specific_strength)
    var _acc_halpin_tsai: Float64 = 0.0
    var _t0_halpin_tsai = perf_counter_ns()
    for _ in range(N):
        _acc_halpin_tsai += halpin_tsai(0.5, 0.5, 0.5, 0.5)
    var _t1_halpin_tsai = perf_counter_ns()
    var _ns_halpin_tsai = Float64(_t1_halpin_tsai - _t0_halpin_tsai) / Float64(N)
    print("MOJO_TIMING composites::halpin_tsai", _ns_halpin_tsai, _acc_halpin_tsai)
    var _result_halpin_tsai = halpin_tsai(0.5, 0.5, 0.5, 0.5)
    var _summary_halpin_tsai = _summary_float64(_result_halpin_tsai)
    print("MOJO_RESULT composites::halpin_tsai", _summary_halpin_tsai)
    var _acc_critical_fiber_length: Float64 = 0.0
    var _t0_critical_fiber_length = perf_counter_ns()
    for _ in range(N):
        _acc_critical_fiber_length += critical_fiber_length(0.5, 0.5, 0.5)
    var _t1_critical_fiber_length = perf_counter_ns()
    var _ns_critical_fiber_length = Float64(_t1_critical_fiber_length - _t0_critical_fiber_length) / Float64(N)
    print("MOJO_TIMING composites::critical_fiber_length", _ns_critical_fiber_length, _acc_critical_fiber_length)
    var _result_critical_fiber_length = critical_fiber_length(0.5, 0.5, 0.5)
    var _summary_critical_fiber_length = _summary_float64(_result_critical_fiber_length)
    print("MOJO_RESULT composites::critical_fiber_length", _summary_critical_fiber_length)
    var _acc_shear_lag_stress_transfer: Float64 = 0.0
    var _t0_shear_lag_stress_transfer = perf_counter_ns()
    for _ in range(N):
        _acc_shear_lag_stress_transfer += shear_lag_stress_transfer(0.5, 0.5, 0.5)
    var _t1_shear_lag_stress_transfer = perf_counter_ns()
    var _ns_shear_lag_stress_transfer = Float64(_t1_shear_lag_stress_transfer - _t0_shear_lag_stress_transfer) / Float64(N)
    print("MOJO_TIMING composites::shear_lag_stress_transfer", _ns_shear_lag_stress_transfer, _acc_shear_lag_stress_transfer)
    var _result_shear_lag_stress_transfer = shear_lag_stress_transfer(0.5, 0.5, 0.5)
    var _summary_shear_lag_stress_transfer = _summary_float64(_result_shear_lag_stress_transfer)
    print("MOJO_RESULT composites::shear_lag_stress_transfer", _summary_shear_lag_stress_transfer)
    var _acc_impact_energy_charpy: Float64 = 0.0
    var _t0_impact_energy_charpy = perf_counter_ns()
    for _ in range(N):
        _acc_impact_energy_charpy += impact_energy_charpy(0.5, 0.5)
    var _t1_impact_energy_charpy = perf_counter_ns()
    var _ns_impact_energy_charpy = Float64(_t1_impact_energy_charpy - _t0_impact_energy_charpy) / Float64(N)
    print("MOJO_TIMING composites::impact_energy_charpy", _ns_impact_energy_charpy, _acc_impact_energy_charpy)
    var _result_impact_energy_charpy = impact_energy_charpy(0.5, 0.5)
    var _summary_impact_energy_charpy = _summary_float64(_result_impact_energy_charpy)
    print("MOJO_RESULT composites::impact_energy_charpy", _summary_impact_energy_charpy)
    var _acc_void_content: Float64 = 0.0
    var _t0_void_content = perf_counter_ns()
    for _ in range(N):
        _acc_void_content += void_content(0.5, 0.5)
    var _t1_void_content = perf_counter_ns()
    var _ns_void_content = Float64(_t1_void_content - _t0_void_content) / Float64(N)
    print("MOJO_TIMING composites::void_content", _ns_void_content, _acc_void_content)
    var _result_void_content = void_content(0.5, 0.5)
    var _summary_void_content = _summary_float64(_result_void_content)
    print("MOJO_RESULT composites::void_content", _summary_void_content)
