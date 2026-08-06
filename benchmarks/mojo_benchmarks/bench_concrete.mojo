"""bench_concrete.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from concrete import water_cement_ratio, compressive_strength_abrams, cement_content, aggregate_volume, slump_estimate, maturity_nurse_saul, modulus_of_elasticity, splitting_tensile_strength, drying_shrinkage_estimate, carbonation_depth, rebar_development_length, concrete_density_estimate
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

    var _acc_water_cement_ratio: Float64 = 0.0
    var _t0_water_cement_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_water_cement_ratio += water_cement_ratio(0.5, 0.5)
    var _t1_water_cement_ratio = perf_counter_ns()
    var _ns_water_cement_ratio = Float64(_t1_water_cement_ratio - _t0_water_cement_ratio) / Float64(N)
    print("MOJO_TIMING concrete::water_cement_ratio", _ns_water_cement_ratio, _acc_water_cement_ratio)
    var _result_water_cement_ratio = water_cement_ratio(0.5, 0.5)
    var _summary_water_cement_ratio = _summary_float64(_result_water_cement_ratio)
    print("MOJO_RESULT concrete::water_cement_ratio", _summary_water_cement_ratio)
    var _acc_compressive_strength_abrams: Float64 = 0.0
    var _t0_compressive_strength_abrams = perf_counter_ns()
    for _ in range(N):
        _acc_compressive_strength_abrams += compressive_strength_abrams(0.5, 0.5, 0.5)
    var _t1_compressive_strength_abrams = perf_counter_ns()
    var _ns_compressive_strength_abrams = Float64(_t1_compressive_strength_abrams - _t0_compressive_strength_abrams) / Float64(N)
    print("MOJO_TIMING concrete::compressive_strength_abrams", _ns_compressive_strength_abrams, _acc_compressive_strength_abrams)
    var _result_compressive_strength_abrams = compressive_strength_abrams(0.5, 0.5, 0.5)
    var _summary_compressive_strength_abrams = _summary_float64(_result_compressive_strength_abrams)
    print("MOJO_RESULT concrete::compressive_strength_abrams", _summary_compressive_strength_abrams)
    var _acc_cement_content: Float64 = 0.0
    var _t0_cement_content = perf_counter_ns()
    for _ in range(N):
        _acc_cement_content += cement_content(0.5, 0.5)
    var _t1_cement_content = perf_counter_ns()
    var _ns_cement_content = Float64(_t1_cement_content - _t0_cement_content) / Float64(N)
    print("MOJO_TIMING concrete::cement_content", _ns_cement_content, _acc_cement_content)
    var _result_cement_content = cement_content(0.5, 0.5)
    var _summary_cement_content = _summary_float64(_result_cement_content)
    print("MOJO_RESULT concrete::cement_content", _summary_cement_content)
    var _acc_aggregate_volume: Float64 = 0.0
    var _t0_aggregate_volume = perf_counter_ns()
    for _ in range(N):
        _acc_aggregate_volume += aggregate_volume(0.5, 0.5, 0.5, 0.5)
    var _t1_aggregate_volume = perf_counter_ns()
    var _ns_aggregate_volume = Float64(_t1_aggregate_volume - _t0_aggregate_volume) / Float64(N)
    print("MOJO_TIMING concrete::aggregate_volume", _ns_aggregate_volume, _acc_aggregate_volume)
    var _result_aggregate_volume = aggregate_volume(0.5, 0.5, 0.5, 0.5)
    var _summary_aggregate_volume = _summary_float64(_result_aggregate_volume)
    print("MOJO_RESULT concrete::aggregate_volume", _summary_aggregate_volume)
    var _acc_slump_estimate: Float64 = 0.0
    var _t0_slump_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_slump_estimate += slump_estimate(0.5)
    var _t1_slump_estimate = perf_counter_ns()
    var _ns_slump_estimate = Float64(_t1_slump_estimate - _t0_slump_estimate) / Float64(N)
    print("MOJO_TIMING concrete::slump_estimate", _ns_slump_estimate, _acc_slump_estimate)
    var _result_slump_estimate = slump_estimate(0.5)
    var _summary_slump_estimate = _summary_float64(_result_slump_estimate)
    print("MOJO_RESULT concrete::slump_estimate", _summary_slump_estimate)
    var _acc_maturity_nurse_saul: Float64 = 0.0
    var _t0_maturity_nurse_saul = perf_counter_ns()
    for _ in range(N):
        _acc_maturity_nurse_saul += maturity_nurse_saul(0.5, 0.5, 0.5)
    var _t1_maturity_nurse_saul = perf_counter_ns()
    var _ns_maturity_nurse_saul = Float64(_t1_maturity_nurse_saul - _t0_maturity_nurse_saul) / Float64(N)
    print("MOJO_TIMING concrete::maturity_nurse_saul", _ns_maturity_nurse_saul, _acc_maturity_nurse_saul)
    var _result_maturity_nurse_saul = maturity_nurse_saul(0.5, 0.5, 0.5)
    var _summary_maturity_nurse_saul = _summary_float64(_result_maturity_nurse_saul)
    print("MOJO_RESULT concrete::maturity_nurse_saul", _summary_maturity_nurse_saul)
    var _acc_modulus_of_elasticity: Float64 = 0.0
    var _t0_modulus_of_elasticity = perf_counter_ns()
    for _ in range(N):
        _acc_modulus_of_elasticity += modulus_of_elasticity(0.5)
    var _t1_modulus_of_elasticity = perf_counter_ns()
    var _ns_modulus_of_elasticity = Float64(_t1_modulus_of_elasticity - _t0_modulus_of_elasticity) / Float64(N)
    print("MOJO_TIMING concrete::modulus_of_elasticity", _ns_modulus_of_elasticity, _acc_modulus_of_elasticity)
    var _result_modulus_of_elasticity = modulus_of_elasticity(0.5)
    var _summary_modulus_of_elasticity = _summary_float64(_result_modulus_of_elasticity)
    print("MOJO_RESULT concrete::modulus_of_elasticity", _summary_modulus_of_elasticity)
    var _acc_splitting_tensile_strength: Float64 = 0.0
    var _t0_splitting_tensile_strength = perf_counter_ns()
    for _ in range(N):
        _acc_splitting_tensile_strength += splitting_tensile_strength(0.5)
    var _t1_splitting_tensile_strength = perf_counter_ns()
    var _ns_splitting_tensile_strength = Float64(_t1_splitting_tensile_strength - _t0_splitting_tensile_strength) / Float64(N)
    print("MOJO_TIMING concrete::splitting_tensile_strength", _ns_splitting_tensile_strength, _acc_splitting_tensile_strength)
    var _result_splitting_tensile_strength = splitting_tensile_strength(0.5)
    var _summary_splitting_tensile_strength = _summary_float64(_result_splitting_tensile_strength)
    print("MOJO_RESULT concrete::splitting_tensile_strength", _summary_splitting_tensile_strength)
    var _acc_drying_shrinkage_estimate: Float64 = 0.0
    var _t0_drying_shrinkage_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_drying_shrinkage_estimate += drying_shrinkage_estimate(0.5, 0.5)
    var _t1_drying_shrinkage_estimate = perf_counter_ns()
    var _ns_drying_shrinkage_estimate = Float64(_t1_drying_shrinkage_estimate - _t0_drying_shrinkage_estimate) / Float64(N)
    print("MOJO_TIMING concrete::drying_shrinkage_estimate", _ns_drying_shrinkage_estimate, _acc_drying_shrinkage_estimate)
    var _result_drying_shrinkage_estimate = drying_shrinkage_estimate(0.5, 0.5)
    var _summary_drying_shrinkage_estimate = _summary_float64(_result_drying_shrinkage_estimate)
    print("MOJO_RESULT concrete::drying_shrinkage_estimate", _summary_drying_shrinkage_estimate)
    var _acc_carbonation_depth: Float64 = 0.0
    var _t0_carbonation_depth = perf_counter_ns()
    for _ in range(N):
        _acc_carbonation_depth += carbonation_depth(0.5, 0.5)
    var _t1_carbonation_depth = perf_counter_ns()
    var _ns_carbonation_depth = Float64(_t1_carbonation_depth - _t0_carbonation_depth) / Float64(N)
    print("MOJO_TIMING concrete::carbonation_depth", _ns_carbonation_depth, _acc_carbonation_depth)
    var _result_carbonation_depth = carbonation_depth(0.5, 0.5)
    var _summary_carbonation_depth = _summary_float64(_result_carbonation_depth)
    print("MOJO_RESULT concrete::carbonation_depth", _summary_carbonation_depth)
    var _acc_rebar_development_length: Float64 = 0.0
    var _t0_rebar_development_length = perf_counter_ns()
    for _ in range(N):
        _acc_rebar_development_length += rebar_development_length(0.5, 0.5, 0.5)
    var _t1_rebar_development_length = perf_counter_ns()
    var _ns_rebar_development_length = Float64(_t1_rebar_development_length - _t0_rebar_development_length) / Float64(N)
    print("MOJO_TIMING concrete::rebar_development_length", _ns_rebar_development_length, _acc_rebar_development_length)
    var _result_rebar_development_length = rebar_development_length(0.5, 0.5, 0.5)
    var _summary_rebar_development_length = _summary_float64(_result_rebar_development_length)
    print("MOJO_RESULT concrete::rebar_development_length", _summary_rebar_development_length)
    var _acc_concrete_density_estimate: Float64 = 0.0
    var _t0_concrete_density_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_concrete_density_estimate += concrete_density_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_concrete_density_estimate = perf_counter_ns()
    var _ns_concrete_density_estimate = Float64(_t1_concrete_density_estimate - _t0_concrete_density_estimate) / Float64(N)
    print("MOJO_TIMING concrete::concrete_density_estimate", _ns_concrete_density_estimate, _acc_concrete_density_estimate)
    var _result_concrete_density_estimate = concrete_density_estimate(0.5, 0.5, 0.5, 0.5)
    var _summary_concrete_density_estimate = _summary_float64(_result_concrete_density_estimate)
    print("MOJO_RESULT concrete::concrete_density_estimate", _summary_concrete_density_estimate)
