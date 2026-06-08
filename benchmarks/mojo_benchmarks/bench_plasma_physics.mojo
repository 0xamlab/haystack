"""bench_plasma_physics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from plasma_physics import debye_length, plasma_frequency, thermal_velocity, larmor_radius, coulomb_logarithm, spitzer_resistivity, alfven_speed, mhd_beta, fusion_lawson_criterion, bremsstrahlung_power
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

    var _acc_debye_length: Float64 = 0.0
    var _t0_debye_length = perf_counter_ns()
    for _ in range(N):
        _acc_debye_length += debye_length(0.5, 0.5)
    var _t1_debye_length = perf_counter_ns()
    var _ns_debye_length = Float64(_t1_debye_length - _t0_debye_length) / Float64(N)
    print("MOJO_TIMING plasma_physics::debye_length", _ns_debye_length, _acc_debye_length)
    var _result_debye_length = debye_length(0.5, 0.5)
    var _summary_debye_length = _summary_float64(_result_debye_length)
    print("MOJO_RESULT plasma_physics::debye_length", _summary_debye_length)
    var _acc_plasma_frequency: Float64 = 0.0
    var _t0_plasma_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_plasma_frequency += plasma_frequency(0.5)
    var _t1_plasma_frequency = perf_counter_ns()
    var _ns_plasma_frequency = Float64(_t1_plasma_frequency - _t0_plasma_frequency) / Float64(N)
    print("MOJO_TIMING plasma_physics::plasma_frequency", _ns_plasma_frequency, _acc_plasma_frequency)
    var _result_plasma_frequency = plasma_frequency(0.5)
    var _summary_plasma_frequency = _summary_float64(_result_plasma_frequency)
    print("MOJO_RESULT plasma_physics::plasma_frequency", _summary_plasma_frequency)
    var _acc_thermal_velocity: Float64 = 0.0
    var _t0_thermal_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_velocity += thermal_velocity(0.5, 0.5)
    var _t1_thermal_velocity = perf_counter_ns()
    var _ns_thermal_velocity = Float64(_t1_thermal_velocity - _t0_thermal_velocity) / Float64(N)
    print("MOJO_TIMING plasma_physics::thermal_velocity", _ns_thermal_velocity, _acc_thermal_velocity)
    var _result_thermal_velocity = thermal_velocity(0.5, 0.5)
    var _summary_thermal_velocity = _summary_float64(_result_thermal_velocity)
    print("MOJO_RESULT plasma_physics::thermal_velocity", _summary_thermal_velocity)
    var _acc_larmor_radius: Float64 = 0.0
    var _t0_larmor_radius = perf_counter_ns()
    for _ in range(N):
        _acc_larmor_radius += larmor_radius(0.5, 0.5, 0.5, 0.5)
    var _t1_larmor_radius = perf_counter_ns()
    var _ns_larmor_radius = Float64(_t1_larmor_radius - _t0_larmor_radius) / Float64(N)
    print("MOJO_TIMING plasma_physics::larmor_radius", _ns_larmor_radius, _acc_larmor_radius)
    var _result_larmor_radius = larmor_radius(0.5, 0.5, 0.5, 0.5)
    var _summary_larmor_radius = _summary_float64(_result_larmor_radius)
    print("MOJO_RESULT plasma_physics::larmor_radius", _summary_larmor_radius)
    var _acc_coulomb_logarithm: Float64 = 0.0
    var _t0_coulomb_logarithm = perf_counter_ns()
    for _ in range(N):
        _acc_coulomb_logarithm += coulomb_logarithm(0.5, 0.5)
    var _t1_coulomb_logarithm = perf_counter_ns()
    var _ns_coulomb_logarithm = Float64(_t1_coulomb_logarithm - _t0_coulomb_logarithm) / Float64(N)
    print("MOJO_TIMING plasma_physics::coulomb_logarithm", _ns_coulomb_logarithm, _acc_coulomb_logarithm)
    var _result_coulomb_logarithm = coulomb_logarithm(0.5, 0.5)
    var _summary_coulomb_logarithm = _summary_float64(_result_coulomb_logarithm)
    print("MOJO_RESULT plasma_physics::coulomb_logarithm", _summary_coulomb_logarithm)
    var _acc_spitzer_resistivity: Float64 = 0.0
    var _t0_spitzer_resistivity = perf_counter_ns()
    for _ in range(N):
        _acc_spitzer_resistivity += spitzer_resistivity(0.5, 0.5)
    var _t1_spitzer_resistivity = perf_counter_ns()
    var _ns_spitzer_resistivity = Float64(_t1_spitzer_resistivity - _t0_spitzer_resistivity) / Float64(N)
    print("MOJO_TIMING plasma_physics::spitzer_resistivity", _ns_spitzer_resistivity, _acc_spitzer_resistivity)
    var _result_spitzer_resistivity = spitzer_resistivity(0.5, 0.5)
    var _summary_spitzer_resistivity = _summary_float64(_result_spitzer_resistivity)
    print("MOJO_RESULT plasma_physics::spitzer_resistivity", _summary_spitzer_resistivity)
    var _acc_alfven_speed: Float64 = 0.0
    var _t0_alfven_speed = perf_counter_ns()
    for _ in range(N):
        _acc_alfven_speed += alfven_speed(0.5, 0.5)
    var _t1_alfven_speed = perf_counter_ns()
    var _ns_alfven_speed = Float64(_t1_alfven_speed - _t0_alfven_speed) / Float64(N)
    print("MOJO_TIMING plasma_physics::alfven_speed", _ns_alfven_speed, _acc_alfven_speed)
    var _result_alfven_speed = alfven_speed(0.5, 0.5)
    var _summary_alfven_speed = _summary_float64(_result_alfven_speed)
    print("MOJO_RESULT plasma_physics::alfven_speed", _summary_alfven_speed)
    var _acc_mhd_beta: Float64 = 0.0
    var _t0_mhd_beta = perf_counter_ns()
    for _ in range(N):
        _acc_mhd_beta += mhd_beta(0.5, 0.5, 0.5)
    var _t1_mhd_beta = perf_counter_ns()
    var _ns_mhd_beta = Float64(_t1_mhd_beta - _t0_mhd_beta) / Float64(N)
    print("MOJO_TIMING plasma_physics::mhd_beta", _ns_mhd_beta, _acc_mhd_beta)
    var _result_mhd_beta = mhd_beta(0.5, 0.5, 0.5)
    var _summary_mhd_beta = _summary_float64(_result_mhd_beta)
    print("MOJO_RESULT plasma_physics::mhd_beta", _summary_mhd_beta)
    var _acc_fusion_lawson_criterion: Float64 = 0.0
    var _t0_fusion_lawson_criterion = perf_counter_ns()
    for _ in range(N):
        _acc_fusion_lawson_criterion += fusion_lawson_criterion(0.5, 0.5)
    var _t1_fusion_lawson_criterion = perf_counter_ns()
    var _ns_fusion_lawson_criterion = Float64(_t1_fusion_lawson_criterion - _t0_fusion_lawson_criterion) / Float64(N)
    print("MOJO_TIMING plasma_physics::fusion_lawson_criterion", _ns_fusion_lawson_criterion, _acc_fusion_lawson_criterion)
    var _result_fusion_lawson_criterion = fusion_lawson_criterion(0.5, 0.5)
    var _summary_fusion_lawson_criterion = _summary_float64(_result_fusion_lawson_criterion)
    print("MOJO_RESULT plasma_physics::fusion_lawson_criterion", _summary_fusion_lawson_criterion)
    var _acc_bremsstrahlung_power: Float64 = 0.0
    var _t0_bremsstrahlung_power = perf_counter_ns()
    for _ in range(N):
        _acc_bremsstrahlung_power += bremsstrahlung_power(0.5, 0.5, 0.5, 0.5)
    var _t1_bremsstrahlung_power = perf_counter_ns()
    var _ns_bremsstrahlung_power = Float64(_t1_bremsstrahlung_power - _t0_bremsstrahlung_power) / Float64(N)
    print("MOJO_TIMING plasma_physics::bremsstrahlung_power", _ns_bremsstrahlung_power, _acc_bremsstrahlung_power)
    var _result_bremsstrahlung_power = bremsstrahlung_power(0.5, 0.5, 0.5, 0.5)
    var _summary_bremsstrahlung_power = _summary_float64(_result_bremsstrahlung_power)
    print("MOJO_RESULT plasma_physics::bremsstrahlung_power", _summary_bremsstrahlung_power)
