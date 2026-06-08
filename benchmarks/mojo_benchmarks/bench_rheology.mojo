"""bench_rheology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from rheology import shear_stress, shear_rate, dynamic_viscosity, power_law_viscosity, bingham_yield_stress, reynolds_number_non_newton, creep_compliance, stress_relaxation_modulus, viscosity_arrhenius, thixotropy_index
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

    var _acc_shear_stress: Float64 = 0.0
    var _t0_shear_stress = perf_counter_ns()
    for _ in range(N):
        _acc_shear_stress += shear_stress(0.5, 0.5)
    var _t1_shear_stress = perf_counter_ns()
    var _ns_shear_stress = Float64(_t1_shear_stress - _t0_shear_stress) / Float64(N)
    print("MOJO_TIMING rheology::shear_stress", _ns_shear_stress, _acc_shear_stress)
    var _result_shear_stress = shear_stress(0.5, 0.5)
    var _summary_shear_stress = _summary_float64(_result_shear_stress)
    print("MOJO_RESULT rheology::shear_stress", _summary_shear_stress)
    var _acc_shear_rate: Float64 = 0.0
    var _t0_shear_rate = perf_counter_ns()
    for _ in range(N):
        _acc_shear_rate += shear_rate(0.5, 0.5)
    var _t1_shear_rate = perf_counter_ns()
    var _ns_shear_rate = Float64(_t1_shear_rate - _t0_shear_rate) / Float64(N)
    print("MOJO_TIMING rheology::shear_rate", _ns_shear_rate, _acc_shear_rate)
    var _result_shear_rate = shear_rate(0.5, 0.5)
    var _summary_shear_rate = _summary_float64(_result_shear_rate)
    print("MOJO_RESULT rheology::shear_rate", _summary_shear_rate)
    var _acc_dynamic_viscosity: Float64 = 0.0
    var _t0_dynamic_viscosity = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_viscosity += dynamic_viscosity(0.5, 0.5)
    var _t1_dynamic_viscosity = perf_counter_ns()
    var _ns_dynamic_viscosity = Float64(_t1_dynamic_viscosity - _t0_dynamic_viscosity) / Float64(N)
    print("MOJO_TIMING rheology::dynamic_viscosity", _ns_dynamic_viscosity, _acc_dynamic_viscosity)
    var _result_dynamic_viscosity = dynamic_viscosity(0.5, 0.5)
    var _summary_dynamic_viscosity = _summary_float64(_result_dynamic_viscosity)
    print("MOJO_RESULT rheology::dynamic_viscosity", _summary_dynamic_viscosity)
    var _acc_power_law_viscosity: Float64 = 0.0
    var _t0_power_law_viscosity = perf_counter_ns()
    for _ in range(N):
        _acc_power_law_viscosity += power_law_viscosity(0.5, 0.5, 0.5)
    var _t1_power_law_viscosity = perf_counter_ns()
    var _ns_power_law_viscosity = Float64(_t1_power_law_viscosity - _t0_power_law_viscosity) / Float64(N)
    print("MOJO_TIMING rheology::power_law_viscosity", _ns_power_law_viscosity, _acc_power_law_viscosity)
    var _result_power_law_viscosity = power_law_viscosity(0.5, 0.5, 0.5)
    var _summary_power_law_viscosity = _summary_float64(_result_power_law_viscosity)
    print("MOJO_RESULT rheology::power_law_viscosity", _summary_power_law_viscosity)
    var _acc_bingham_yield_stress: Float64 = 0.0
    var _t0_bingham_yield_stress = perf_counter_ns()
    for _ in range(N):
        _acc_bingham_yield_stress += bingham_yield_stress(0.5, 0.5, 0.5)
    var _t1_bingham_yield_stress = perf_counter_ns()
    var _ns_bingham_yield_stress = Float64(_t1_bingham_yield_stress - _t0_bingham_yield_stress) / Float64(N)
    print("MOJO_TIMING rheology::bingham_yield_stress", _ns_bingham_yield_stress, _acc_bingham_yield_stress)
    var _result_bingham_yield_stress = bingham_yield_stress(0.5, 0.5, 0.5)
    var _summary_bingham_yield_stress = _summary_float64(_result_bingham_yield_stress)
    print("MOJO_RESULT rheology::bingham_yield_stress", _summary_bingham_yield_stress)
    var _acc_reynolds_number_non_newton: Float64 = 0.0
    var _t0_reynolds_number_non_newton = perf_counter_ns()
    for _ in range(N):
        _acc_reynolds_number_non_newton += reynolds_number_non_newton(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_reynolds_number_non_newton = perf_counter_ns()
    var _ns_reynolds_number_non_newton = Float64(_t1_reynolds_number_non_newton - _t0_reynolds_number_non_newton) / Float64(N)
    print("MOJO_TIMING rheology::reynolds_number_non_newton", _ns_reynolds_number_non_newton, _acc_reynolds_number_non_newton)
    var _result_reynolds_number_non_newton = reynolds_number_non_newton(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_reynolds_number_non_newton = _summary_float64(_result_reynolds_number_non_newton)
    print("MOJO_RESULT rheology::reynolds_number_non_newton", _summary_reynolds_number_non_newton)
    var _acc_creep_compliance: Float64 = 0.0
    var _t0_creep_compliance = perf_counter_ns()
    for _ in range(N):
        _acc_creep_compliance += creep_compliance(0.5, 0.5, 0.5)
    var _t1_creep_compliance = perf_counter_ns()
    var _ns_creep_compliance = Float64(_t1_creep_compliance - _t0_creep_compliance) / Float64(N)
    print("MOJO_TIMING rheology::creep_compliance", _ns_creep_compliance, _acc_creep_compliance)
    var _result_creep_compliance = creep_compliance(0.5, 0.5, 0.5)
    var _summary_creep_compliance = _summary_float64(_result_creep_compliance)
    print("MOJO_RESULT rheology::creep_compliance", _summary_creep_compliance)
    var _acc_stress_relaxation_modulus: Float64 = 0.0
    var _t0_stress_relaxation_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_stress_relaxation_modulus += stress_relaxation_modulus(0.5, 0.5, 0.5)
    var _t1_stress_relaxation_modulus = perf_counter_ns()
    var _ns_stress_relaxation_modulus = Float64(_t1_stress_relaxation_modulus - _t0_stress_relaxation_modulus) / Float64(N)
    print("MOJO_TIMING rheology::stress_relaxation_modulus", _ns_stress_relaxation_modulus, _acc_stress_relaxation_modulus)
    var _result_stress_relaxation_modulus = stress_relaxation_modulus(0.5, 0.5, 0.5)
    var _summary_stress_relaxation_modulus = _summary_float64(_result_stress_relaxation_modulus)
    print("MOJO_RESULT rheology::stress_relaxation_modulus", _summary_stress_relaxation_modulus)
    var _acc_viscosity_arrhenius: Float64 = 0.0
    var _t0_viscosity_arrhenius = perf_counter_ns()
    for _ in range(N):
        _acc_viscosity_arrhenius += viscosity_arrhenius(0.5, 0.5, 0.5)
    var _t1_viscosity_arrhenius = perf_counter_ns()
    var _ns_viscosity_arrhenius = Float64(_t1_viscosity_arrhenius - _t0_viscosity_arrhenius) / Float64(N)
    print("MOJO_TIMING rheology::viscosity_arrhenius", _ns_viscosity_arrhenius, _acc_viscosity_arrhenius)
    var _result_viscosity_arrhenius = viscosity_arrhenius(0.5, 0.5, 0.5)
    var _summary_viscosity_arrhenius = _summary_float64(_result_viscosity_arrhenius)
    print("MOJO_RESULT rheology::viscosity_arrhenius", _summary_viscosity_arrhenius)
    var _acc_thixotropy_index: Float64 = 0.0
    var _t0_thixotropy_index = perf_counter_ns()
    for _ in range(N):
        _acc_thixotropy_index += thixotropy_index(0.5, 0.5)
    var _t1_thixotropy_index = perf_counter_ns()
    var _ns_thixotropy_index = Float64(_t1_thixotropy_index - _t0_thixotropy_index) / Float64(N)
    print("MOJO_TIMING rheology::thixotropy_index", _ns_thixotropy_index, _acc_thixotropy_index)
    var _result_thixotropy_index = thixotropy_index(0.5, 0.5)
    var _summary_thixotropy_index = _summary_float64(_result_thixotropy_index)
    print("MOJO_RESULT rheology::thixotropy_index", _summary_thixotropy_index)
