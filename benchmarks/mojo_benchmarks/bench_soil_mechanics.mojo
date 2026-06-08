"""bench_soil_mechanics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from soil_mechanics import bearing_capacity_terzaghi, settlement_elastic, consolidation_degree, void_ratio, relative_density, liquid_limit_plasticity, shear_strength_mohr_coulomb, lateral_earth_pressure_ka, compression_index, hydraulic_conductivity_hazen
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

    var _acc_bearing_capacity_terzaghi: Float64 = 0.0
    var _t0_bearing_capacity_terzaghi = perf_counter_ns()
    for _ in range(N):
        _acc_bearing_capacity_terzaghi += bearing_capacity_terzaghi(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bearing_capacity_terzaghi = perf_counter_ns()
    var _ns_bearing_capacity_terzaghi = Float64(_t1_bearing_capacity_terzaghi - _t0_bearing_capacity_terzaghi) / Float64(N)
    print("MOJO_TIMING soil_mechanics::bearing_capacity_terzaghi", _ns_bearing_capacity_terzaghi, _acc_bearing_capacity_terzaghi)
    var _result_bearing_capacity_terzaghi = bearing_capacity_terzaghi(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_bearing_capacity_terzaghi = _summary_float64(_result_bearing_capacity_terzaghi)
    print("MOJO_RESULT soil_mechanics::bearing_capacity_terzaghi", _summary_bearing_capacity_terzaghi)
    var _acc_settlement_elastic: Float64 = 0.0
    var _t0_settlement_elastic = perf_counter_ns()
    for _ in range(N):
        _acc_settlement_elastic += settlement_elastic(0.5, 0.5, 0.5, 0.5)
    var _t1_settlement_elastic = perf_counter_ns()
    var _ns_settlement_elastic = Float64(_t1_settlement_elastic - _t0_settlement_elastic) / Float64(N)
    print("MOJO_TIMING soil_mechanics::settlement_elastic", _ns_settlement_elastic, _acc_settlement_elastic)
    var _result_settlement_elastic = settlement_elastic(0.5, 0.5, 0.5, 0.5)
    var _summary_settlement_elastic = _summary_float64(_result_settlement_elastic)
    print("MOJO_RESULT soil_mechanics::settlement_elastic", _summary_settlement_elastic)
    var _acc_consolidation_degree: Float64 = 0.0
    var _t0_consolidation_degree = perf_counter_ns()
    for _ in range(N):
        _acc_consolidation_degree += consolidation_degree(0.5)
    var _t1_consolidation_degree = perf_counter_ns()
    var _ns_consolidation_degree = Float64(_t1_consolidation_degree - _t0_consolidation_degree) / Float64(N)
    print("MOJO_TIMING soil_mechanics::consolidation_degree", _ns_consolidation_degree, _acc_consolidation_degree)
    var _result_consolidation_degree = consolidation_degree(0.5)
    var _summary_consolidation_degree = _summary_float64(_result_consolidation_degree)
    print("MOJO_RESULT soil_mechanics::consolidation_degree", _summary_consolidation_degree)
    var _acc_void_ratio: Float64 = 0.0
    var _t0_void_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_void_ratio += void_ratio(0.5, 0.5, 0.5)
    var _t1_void_ratio = perf_counter_ns()
    var _ns_void_ratio = Float64(_t1_void_ratio - _t0_void_ratio) / Float64(N)
    print("MOJO_TIMING soil_mechanics::void_ratio", _ns_void_ratio, _acc_void_ratio)
    var _result_void_ratio = void_ratio(0.5, 0.5, 0.5)
    var _summary_void_ratio = _summary_float64(_result_void_ratio)
    print("MOJO_RESULT soil_mechanics::void_ratio", _summary_void_ratio)
    var _acc_relative_density: Float64 = 0.0
    var _t0_relative_density = perf_counter_ns()
    for _ in range(N):
        _acc_relative_density += relative_density(0.5, 0.5, 0.5)
    var _t1_relative_density = perf_counter_ns()
    var _ns_relative_density = Float64(_t1_relative_density - _t0_relative_density) / Float64(N)
    print("MOJO_TIMING soil_mechanics::relative_density", _ns_relative_density, _acc_relative_density)
    var _result_relative_density = relative_density(0.5, 0.5, 0.5)
    var _summary_relative_density = _summary_float64(_result_relative_density)
    print("MOJO_RESULT soil_mechanics::relative_density", _summary_relative_density)
    var _acc_liquid_limit_plasticity: Float64 = 0.0
    var _t0_liquid_limit_plasticity = perf_counter_ns()
    for _ in range(N):
        _acc_liquid_limit_plasticity += liquid_limit_plasticity(0.5, 0.5)
    var _t1_liquid_limit_plasticity = perf_counter_ns()
    var _ns_liquid_limit_plasticity = Float64(_t1_liquid_limit_plasticity - _t0_liquid_limit_plasticity) / Float64(N)
    print("MOJO_TIMING soil_mechanics::liquid_limit_plasticity", _ns_liquid_limit_plasticity, _acc_liquid_limit_plasticity)
    var _result_liquid_limit_plasticity = liquid_limit_plasticity(0.5, 0.5)
    var _summary_liquid_limit_plasticity = _summary_float64(_result_liquid_limit_plasticity)
    print("MOJO_RESULT soil_mechanics::liquid_limit_plasticity", _summary_liquid_limit_plasticity)
    var _acc_shear_strength_mohr_coulomb: Float64 = 0.0
    var _t0_shear_strength_mohr_coulomb = perf_counter_ns()
    for _ in range(N):
        _acc_shear_strength_mohr_coulomb += shear_strength_mohr_coulomb(0.5, 0.5, 0.5)
    var _t1_shear_strength_mohr_coulomb = perf_counter_ns()
    var _ns_shear_strength_mohr_coulomb = Float64(_t1_shear_strength_mohr_coulomb - _t0_shear_strength_mohr_coulomb) / Float64(N)
    print("MOJO_TIMING soil_mechanics::shear_strength_mohr_coulomb", _ns_shear_strength_mohr_coulomb, _acc_shear_strength_mohr_coulomb)
    var _result_shear_strength_mohr_coulomb = shear_strength_mohr_coulomb(0.5, 0.5, 0.5)
    var _summary_shear_strength_mohr_coulomb = _summary_float64(_result_shear_strength_mohr_coulomb)
    print("MOJO_RESULT soil_mechanics::shear_strength_mohr_coulomb", _summary_shear_strength_mohr_coulomb)
    var _acc_lateral_earth_pressure_ka: Float64 = 0.0
    var _t0_lateral_earth_pressure_ka = perf_counter_ns()
    for _ in range(N):
        _acc_lateral_earth_pressure_ka += lateral_earth_pressure_ka(0.5)
    var _t1_lateral_earth_pressure_ka = perf_counter_ns()
    var _ns_lateral_earth_pressure_ka = Float64(_t1_lateral_earth_pressure_ka - _t0_lateral_earth_pressure_ka) / Float64(N)
    print("MOJO_TIMING soil_mechanics::lateral_earth_pressure_ka", _ns_lateral_earth_pressure_ka, _acc_lateral_earth_pressure_ka)
    var _result_lateral_earth_pressure_ka = lateral_earth_pressure_ka(0.5)
    var _summary_lateral_earth_pressure_ka = _summary_float64(_result_lateral_earth_pressure_ka)
    print("MOJO_RESULT soil_mechanics::lateral_earth_pressure_ka", _summary_lateral_earth_pressure_ka)
    var _acc_compression_index: Float64 = 0.0
    var _t0_compression_index = perf_counter_ns()
    for _ in range(N):
        _acc_compression_index += compression_index(0.5)
    var _t1_compression_index = perf_counter_ns()
    var _ns_compression_index = Float64(_t1_compression_index - _t0_compression_index) / Float64(N)
    print("MOJO_TIMING soil_mechanics::compression_index", _ns_compression_index, _acc_compression_index)
    var _result_compression_index = compression_index(0.5)
    var _summary_compression_index = _summary_float64(_result_compression_index)
    print("MOJO_RESULT soil_mechanics::compression_index", _summary_compression_index)
    var _acc_hydraulic_conductivity_hazen: Float64 = 0.0
    var _t0_hydraulic_conductivity_hazen = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_conductivity_hazen += hydraulic_conductivity_hazen(0.5)
    var _t1_hydraulic_conductivity_hazen = perf_counter_ns()
    var _ns_hydraulic_conductivity_hazen = Float64(_t1_hydraulic_conductivity_hazen - _t0_hydraulic_conductivity_hazen) / Float64(N)
    print("MOJO_TIMING soil_mechanics::hydraulic_conductivity_hazen", _ns_hydraulic_conductivity_hazen, _acc_hydraulic_conductivity_hazen)
    var _result_hydraulic_conductivity_hazen = hydraulic_conductivity_hazen(0.5)
    var _summary_hydraulic_conductivity_hazen = _summary_float64(_result_hydraulic_conductivity_hazen)
    print("MOJO_RESULT soil_mechanics::hydraulic_conductivity_hazen", _summary_hydraulic_conductivity_hazen)
