"""bench_wood_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from wood_science import moisture_content, fiber_saturation_point, shrinkage_coefficient, modulus_of_rupture, modulus_of_elasticity, wood_density_at_mc, thermal_conductivity_wood, charring_rate, section_modulus, wood_hardness_janka
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

    var _acc_moisture_content: Float64 = 0.0
    var _t0_moisture_content = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content += moisture_content(0.5, 0.5)
    var _t1_moisture_content = perf_counter_ns()
    var _ns_moisture_content = Float64(_t1_moisture_content - _t0_moisture_content) / Float64(N)
    print("MOJO_TIMING wood_science::moisture_content", _ns_moisture_content, _acc_moisture_content)
    var _result_moisture_content = moisture_content(0.5, 0.5)
    var _summary_moisture_content = _summary_float64(_result_moisture_content)
    print("MOJO_RESULT wood_science::moisture_content", _summary_moisture_content)
    var _acc_fiber_saturation_point: Float64 = 0.0
    var _t0_fiber_saturation_point = perf_counter_ns()
    for _ in range(N):
        _acc_fiber_saturation_point += fiber_saturation_point(0.5)
    var _t1_fiber_saturation_point = perf_counter_ns()
    var _ns_fiber_saturation_point = Float64(_t1_fiber_saturation_point - _t0_fiber_saturation_point) / Float64(N)
    print("MOJO_TIMING wood_science::fiber_saturation_point", _ns_fiber_saturation_point, _acc_fiber_saturation_point)
    var _result_fiber_saturation_point = fiber_saturation_point(0.5)
    var _summary_fiber_saturation_point = _summary_float64(_result_fiber_saturation_point)
    print("MOJO_RESULT wood_science::fiber_saturation_point", _summary_fiber_saturation_point)
    var _acc_shrinkage_coefficient: Float64 = 0.0
    var _t0_shrinkage_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_shrinkage_coefficient += shrinkage_coefficient(0.5, 0.5, 0.5)
    var _t1_shrinkage_coefficient = perf_counter_ns()
    var _ns_shrinkage_coefficient = Float64(_t1_shrinkage_coefficient - _t0_shrinkage_coefficient) / Float64(N)
    print("MOJO_TIMING wood_science::shrinkage_coefficient", _ns_shrinkage_coefficient, _acc_shrinkage_coefficient)
    var _result_shrinkage_coefficient = shrinkage_coefficient(0.5, 0.5, 0.5)
    var _summary_shrinkage_coefficient = _summary_float64(_result_shrinkage_coefficient)
    print("MOJO_RESULT wood_science::shrinkage_coefficient", _summary_shrinkage_coefficient)
    var _acc_modulus_of_rupture: Float64 = 0.0
    var _t0_modulus_of_rupture = perf_counter_ns()
    for _ in range(N):
        _acc_modulus_of_rupture += modulus_of_rupture(0.5, 0.5, 0.5, 0.5)
    var _t1_modulus_of_rupture = perf_counter_ns()
    var _ns_modulus_of_rupture = Float64(_t1_modulus_of_rupture - _t0_modulus_of_rupture) / Float64(N)
    print("MOJO_TIMING wood_science::modulus_of_rupture", _ns_modulus_of_rupture, _acc_modulus_of_rupture)
    var _result_modulus_of_rupture = modulus_of_rupture(0.5, 0.5, 0.5, 0.5)
    var _summary_modulus_of_rupture = _summary_float64(_result_modulus_of_rupture)
    print("MOJO_RESULT wood_science::modulus_of_rupture", _summary_modulus_of_rupture)
    var _acc_modulus_of_elasticity: Float64 = 0.0
    var _t0_modulus_of_elasticity = perf_counter_ns()
    for _ in range(N):
        _acc_modulus_of_elasticity += modulus_of_elasticity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_modulus_of_elasticity = perf_counter_ns()
    var _ns_modulus_of_elasticity = Float64(_t1_modulus_of_elasticity - _t0_modulus_of_elasticity) / Float64(N)
    print("MOJO_TIMING wood_science::modulus_of_elasticity", _ns_modulus_of_elasticity, _acc_modulus_of_elasticity)
    var _result_modulus_of_elasticity = modulus_of_elasticity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_modulus_of_elasticity = _summary_float64(_result_modulus_of_elasticity)
    print("MOJO_RESULT wood_science::modulus_of_elasticity", _summary_modulus_of_elasticity)
    var _acc_wood_density_at_mc: Float64 = 0.0
    var _t0_wood_density_at_mc = perf_counter_ns()
    for _ in range(N):
        _acc_wood_density_at_mc += wood_density_at_mc(0.5, 0.5)
    var _t1_wood_density_at_mc = perf_counter_ns()
    var _ns_wood_density_at_mc = Float64(_t1_wood_density_at_mc - _t0_wood_density_at_mc) / Float64(N)
    print("MOJO_TIMING wood_science::wood_density_at_mc", _ns_wood_density_at_mc, _acc_wood_density_at_mc)
    var _result_wood_density_at_mc = wood_density_at_mc(0.5, 0.5)
    var _summary_wood_density_at_mc = _summary_float64(_result_wood_density_at_mc)
    print("MOJO_RESULT wood_science::wood_density_at_mc", _summary_wood_density_at_mc)
    var _acc_thermal_conductivity_wood: Float64 = 0.0
    var _t0_thermal_conductivity_wood = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_wood += thermal_conductivity_wood(0.5, 0.5)
    var _t1_thermal_conductivity_wood = perf_counter_ns()
    var _ns_thermal_conductivity_wood = Float64(_t1_thermal_conductivity_wood - _t0_thermal_conductivity_wood) / Float64(N)
    print("MOJO_TIMING wood_science::thermal_conductivity_wood", _ns_thermal_conductivity_wood, _acc_thermal_conductivity_wood)
    var _result_thermal_conductivity_wood = thermal_conductivity_wood(0.5, 0.5)
    var _summary_thermal_conductivity_wood = _summary_float64(_result_thermal_conductivity_wood)
    print("MOJO_RESULT wood_science::thermal_conductivity_wood", _summary_thermal_conductivity_wood)
    var _acc_charring_rate: Float64 = 0.0
    var _t0_charring_rate = perf_counter_ns()
    for _ in range(N):
        _acc_charring_rate += charring_rate(0.5, 0.5)
    var _t1_charring_rate = perf_counter_ns()
    var _ns_charring_rate = Float64(_t1_charring_rate - _t0_charring_rate) / Float64(N)
    print("MOJO_TIMING wood_science::charring_rate", _ns_charring_rate, _acc_charring_rate)
    var _result_charring_rate = charring_rate(0.5, 0.5)
    var _summary_charring_rate = _summary_float64(_result_charring_rate)
    print("MOJO_RESULT wood_science::charring_rate", _summary_charring_rate)
    var _acc_section_modulus: Float64 = 0.0
    var _t0_section_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_section_modulus += section_modulus(0.5, 0.5)
    var _t1_section_modulus = perf_counter_ns()
    var _ns_section_modulus = Float64(_t1_section_modulus - _t0_section_modulus) / Float64(N)
    print("MOJO_TIMING wood_science::section_modulus", _ns_section_modulus, _acc_section_modulus)
    var _result_section_modulus = section_modulus(0.5, 0.5)
    var _summary_section_modulus = _summary_float64(_result_section_modulus)
    print("MOJO_RESULT wood_science::section_modulus", _summary_section_modulus)
    var _acc_wood_hardness_janka: Float64 = 0.0
    var _t0_wood_hardness_janka = perf_counter_ns()
    for _ in range(N):
        _acc_wood_hardness_janka += wood_hardness_janka(0.5)
    var _t1_wood_hardness_janka = perf_counter_ns()
    var _ns_wood_hardness_janka = Float64(_t1_wood_hardness_janka - _t0_wood_hardness_janka) / Float64(N)
    print("MOJO_TIMING wood_science::wood_hardness_janka", _ns_wood_hardness_janka, _acc_wood_hardness_janka)
    var _result_wood_hardness_janka = wood_hardness_janka(0.5)
    var _summary_wood_hardness_janka = _summary_float64(_result_wood_hardness_janka)
    print("MOJO_RESULT wood_science::wood_hardness_janka", _summary_wood_hardness_janka)
