"""bench_mineralogy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from mineralogy import mineral_density, mohs_hardness_scratch, crystal_d_spacing, mineral_formula_weight, solubility_product, geochemical_activity, mineral_saturation_index, specific_gravity_ratio, thermal_conductivity_mixing, birefringence
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

    var _acc_mineral_density: Float64 = 0.0
    var _t0_mineral_density = perf_counter_ns()
    for _ in range(N):
        _acc_mineral_density += mineral_density(0.5, 0.5)
    var _t1_mineral_density = perf_counter_ns()
    var _ns_mineral_density = Float64(_t1_mineral_density - _t0_mineral_density) / Float64(N)
    print("MOJO_TIMING mineralogy::mineral_density", _ns_mineral_density, _acc_mineral_density)
    var _result_mineral_density = mineral_density(0.5, 0.5)
    var _summary_mineral_density = _summary_float64(_result_mineral_density)
    print("MOJO_RESULT mineralogy::mineral_density", _summary_mineral_density)
    var _acc_mohs_hardness_scratch: Float64 = 0.0
    var _t0_mohs_hardness_scratch = perf_counter_ns()
    for _ in range(N):
        _acc_mohs_hardness_scratch += mohs_hardness_scratch(0.5, 0.5)
    var _t1_mohs_hardness_scratch = perf_counter_ns()
    var _ns_mohs_hardness_scratch = Float64(_t1_mohs_hardness_scratch - _t0_mohs_hardness_scratch) / Float64(N)
    print("MOJO_TIMING mineralogy::mohs_hardness_scratch", _ns_mohs_hardness_scratch, _acc_mohs_hardness_scratch)
    var _result_mohs_hardness_scratch = mohs_hardness_scratch(0.5, 0.5)
    var _summary_mohs_hardness_scratch = _summary_float64(_result_mohs_hardness_scratch)
    print("MOJO_RESULT mineralogy::mohs_hardness_scratch", _summary_mohs_hardness_scratch)
    var _acc_crystal_d_spacing: Float64 = 0.0
    var _t0_crystal_d_spacing = perf_counter_ns()
    for _ in range(N):
        _acc_crystal_d_spacing += crystal_d_spacing(0.5, 0.5, 0.5)
    var _t1_crystal_d_spacing = perf_counter_ns()
    var _ns_crystal_d_spacing = Float64(_t1_crystal_d_spacing - _t0_crystal_d_spacing) / Float64(N)
    print("MOJO_TIMING mineralogy::crystal_d_spacing", _ns_crystal_d_spacing, _acc_crystal_d_spacing)
    var _result_crystal_d_spacing = crystal_d_spacing(0.5, 0.5, 0.5)
    var _summary_crystal_d_spacing = _summary_float64(_result_crystal_d_spacing)
    print("MOJO_RESULT mineralogy::crystal_d_spacing", _summary_crystal_d_spacing)
    var _acc_mineral_formula_weight: Float64 = 0.0
    var _t0_mineral_formula_weight = perf_counter_ns()
    for _ in range(N):
        _acc_mineral_formula_weight += mineral_formula_weight(0.5, 0.5, 0.5, 0.5)
    var _t1_mineral_formula_weight = perf_counter_ns()
    var _ns_mineral_formula_weight = Float64(_t1_mineral_formula_weight - _t0_mineral_formula_weight) / Float64(N)
    print("MOJO_TIMING mineralogy::mineral_formula_weight", _ns_mineral_formula_weight, _acc_mineral_formula_weight)
    var _result_mineral_formula_weight = mineral_formula_weight(0.5, 0.5, 0.5, 0.5)
    var _summary_mineral_formula_weight = _summary_float64(_result_mineral_formula_weight)
    print("MOJO_RESULT mineralogy::mineral_formula_weight", _summary_mineral_formula_weight)
    var _acc_solubility_product: Float64 = 0.0
    var _t0_solubility_product = perf_counter_ns()
    for _ in range(N):
        _acc_solubility_product += solubility_product(0.5, 0.5, 0.5, 0.5)
    var _t1_solubility_product = perf_counter_ns()
    var _ns_solubility_product = Float64(_t1_solubility_product - _t0_solubility_product) / Float64(N)
    print("MOJO_TIMING mineralogy::solubility_product", _ns_solubility_product, _acc_solubility_product)
    var _result_solubility_product = solubility_product(0.5, 0.5, 0.5, 0.5)
    var _summary_solubility_product = _summary_float64(_result_solubility_product)
    print("MOJO_RESULT mineralogy::solubility_product", _summary_solubility_product)
    var _acc_geochemical_activity: Float64 = 0.0
    var _t0_geochemical_activity = perf_counter_ns()
    for _ in range(N):
        _acc_geochemical_activity += geochemical_activity(0.5, 0.5)
    var _t1_geochemical_activity = perf_counter_ns()
    var _ns_geochemical_activity = Float64(_t1_geochemical_activity - _t0_geochemical_activity) / Float64(N)
    print("MOJO_TIMING mineralogy::geochemical_activity", _ns_geochemical_activity, _acc_geochemical_activity)
    var _result_geochemical_activity = geochemical_activity(0.5, 0.5)
    var _summary_geochemical_activity = _summary_float64(_result_geochemical_activity)
    print("MOJO_RESULT mineralogy::geochemical_activity", _summary_geochemical_activity)
    var _acc_mineral_saturation_index: Float64 = 0.0
    var _t0_mineral_saturation_index = perf_counter_ns()
    for _ in range(N):
        _acc_mineral_saturation_index += mineral_saturation_index(0.5, 0.5)
    var _t1_mineral_saturation_index = perf_counter_ns()
    var _ns_mineral_saturation_index = Float64(_t1_mineral_saturation_index - _t0_mineral_saturation_index) / Float64(N)
    print("MOJO_TIMING mineralogy::mineral_saturation_index", _ns_mineral_saturation_index, _acc_mineral_saturation_index)
    var _result_mineral_saturation_index = mineral_saturation_index(0.5, 0.5)
    var _summary_mineral_saturation_index = _summary_float64(_result_mineral_saturation_index)
    print("MOJO_RESULT mineralogy::mineral_saturation_index", _summary_mineral_saturation_index)
    var _acc_specific_gravity_ratio: Float64 = 0.0
    var _t0_specific_gravity_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_specific_gravity_ratio += specific_gravity_ratio(0.5)
    var _t1_specific_gravity_ratio = perf_counter_ns()
    var _ns_specific_gravity_ratio = Float64(_t1_specific_gravity_ratio - _t0_specific_gravity_ratio) / Float64(N)
    print("MOJO_TIMING mineralogy::specific_gravity_ratio", _ns_specific_gravity_ratio, _acc_specific_gravity_ratio)
    var _result_specific_gravity_ratio = specific_gravity_ratio(0.5)
    var _summary_specific_gravity_ratio = _summary_float64(_result_specific_gravity_ratio)
    print("MOJO_RESULT mineralogy::specific_gravity_ratio", _summary_specific_gravity_ratio)
    var _acc_thermal_conductivity_mixing: Float64 = 0.0
    var _t0_thermal_conductivity_mixing = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_mixing += thermal_conductivity_mixing(0.5, 0.5, 0.5)
    var _t1_thermal_conductivity_mixing = perf_counter_ns()
    var _ns_thermal_conductivity_mixing = Float64(_t1_thermal_conductivity_mixing - _t0_thermal_conductivity_mixing) / Float64(N)
    print("MOJO_TIMING mineralogy::thermal_conductivity_mixing", _ns_thermal_conductivity_mixing, _acc_thermal_conductivity_mixing)
    var _result_thermal_conductivity_mixing = thermal_conductivity_mixing(0.5, 0.5, 0.5)
    var _summary_thermal_conductivity_mixing = _summary_float64(_result_thermal_conductivity_mixing)
    print("MOJO_RESULT mineralogy::thermal_conductivity_mixing", _summary_thermal_conductivity_mixing)
    var _acc_birefringence: Float64 = 0.0
    var _t0_birefringence = perf_counter_ns()
    for _ in range(N):
        _acc_birefringence += birefringence(0.5, 0.5)
    var _t1_birefringence = perf_counter_ns()
    var _ns_birefringence = Float64(_t1_birefringence - _t0_birefringence) / Float64(N)
    print("MOJO_TIMING mineralogy::birefringence", _ns_birefringence, _acc_birefringence)
    var _result_birefringence = birefringence(0.5, 0.5)
    var _summary_birefringence = _summary_float64(_result_birefringence)
    print("MOJO_RESULT mineralogy::birefringence", _summary_birefringence)
