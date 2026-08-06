"""bench_soil_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from soil_science import soil_texture_sand_silt_clay, bulk_density, particle_density_typical, total_porosity, volumetric_water_content, gravimetric_water_content, field_capacity_estimate, wilting_point_estimate, available_water, cation_exchange_capacity_estimate, soil_organic_carbon, infiltration_rate_horton
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

    var _acc_soil_texture_sand_silt_clay: Float64 = 0.0
    var _t0_soil_texture_sand_silt_clay = perf_counter_ns()
    for _ in range(N):
        _acc_soil_texture_sand_silt_clay += Float64(soil_texture_sand_silt_clay(0.5, 0.5, 0.5))
    var _t1_soil_texture_sand_silt_clay = perf_counter_ns()
    var _ns_soil_texture_sand_silt_clay = Float64(_t1_soil_texture_sand_silt_clay - _t0_soil_texture_sand_silt_clay) / Float64(N)
    print("MOJO_TIMING soil_science::soil_texture_sand_silt_clay", _ns_soil_texture_sand_silt_clay, _acc_soil_texture_sand_silt_clay)
    var _result_soil_texture_sand_silt_clay = soil_texture_sand_silt_clay(0.5, 0.5, 0.5)
    var _summary_soil_texture_sand_silt_clay = _summary_bool(_result_soil_texture_sand_silt_clay)
    print("MOJO_RESULT soil_science::soil_texture_sand_silt_clay", _summary_soil_texture_sand_silt_clay)
    var _acc_bulk_density: Float64 = 0.0
    var _t0_bulk_density = perf_counter_ns()
    for _ in range(N):
        _acc_bulk_density += bulk_density(0.5, 0.5)
    var _t1_bulk_density = perf_counter_ns()
    var _ns_bulk_density = Float64(_t1_bulk_density - _t0_bulk_density) / Float64(N)
    print("MOJO_TIMING soil_science::bulk_density", _ns_bulk_density, _acc_bulk_density)
    var _result_bulk_density = bulk_density(0.5, 0.5)
    var _summary_bulk_density = _summary_float64(_result_bulk_density)
    print("MOJO_RESULT soil_science::bulk_density", _summary_bulk_density)
    var _acc_particle_density_typical: Float64 = 0.0
    var _t0_particle_density_typical = perf_counter_ns()
    for _ in range(N):
        _acc_particle_density_typical += particle_density_typical()
    var _t1_particle_density_typical = perf_counter_ns()
    var _ns_particle_density_typical = Float64(_t1_particle_density_typical - _t0_particle_density_typical) / Float64(N)
    print("MOJO_TIMING soil_science::particle_density_typical", _ns_particle_density_typical, _acc_particle_density_typical)
    var _result_particle_density_typical = particle_density_typical()
    var _summary_particle_density_typical = _summary_float64(_result_particle_density_typical)
    print("MOJO_RESULT soil_science::particle_density_typical", _summary_particle_density_typical)
    var _acc_total_porosity: Float64 = 0.0
    var _t0_total_porosity = perf_counter_ns()
    for _ in range(N):
        _acc_total_porosity += total_porosity(0.5, 0.5)
    var _t1_total_porosity = perf_counter_ns()
    var _ns_total_porosity = Float64(_t1_total_porosity - _t0_total_porosity) / Float64(N)
    print("MOJO_TIMING soil_science::total_porosity", _ns_total_porosity, _acc_total_porosity)
    var _result_total_porosity = total_porosity(0.5, 0.5)
    var _summary_total_porosity = _summary_float64(_result_total_porosity)
    print("MOJO_RESULT soil_science::total_porosity", _summary_total_porosity)
    var _acc_volumetric_water_content: Float64 = 0.0
    var _t0_volumetric_water_content = perf_counter_ns()
    for _ in range(N):
        _acc_volumetric_water_content += volumetric_water_content(0.5, 0.5)
    var _t1_volumetric_water_content = perf_counter_ns()
    var _ns_volumetric_water_content = Float64(_t1_volumetric_water_content - _t0_volumetric_water_content) / Float64(N)
    print("MOJO_TIMING soil_science::volumetric_water_content", _ns_volumetric_water_content, _acc_volumetric_water_content)
    var _result_volumetric_water_content = volumetric_water_content(0.5, 0.5)
    var _summary_volumetric_water_content = _summary_float64(_result_volumetric_water_content)
    print("MOJO_RESULT soil_science::volumetric_water_content", _summary_volumetric_water_content)
    var _acc_gravimetric_water_content: Float64 = 0.0
    var _t0_gravimetric_water_content = perf_counter_ns()
    for _ in range(N):
        _acc_gravimetric_water_content += gravimetric_water_content(0.5, 0.5)
    var _t1_gravimetric_water_content = perf_counter_ns()
    var _ns_gravimetric_water_content = Float64(_t1_gravimetric_water_content - _t0_gravimetric_water_content) / Float64(N)
    print("MOJO_TIMING soil_science::gravimetric_water_content", _ns_gravimetric_water_content, _acc_gravimetric_water_content)
    var _result_gravimetric_water_content = gravimetric_water_content(0.5, 0.5)
    var _summary_gravimetric_water_content = _summary_float64(_result_gravimetric_water_content)
    print("MOJO_RESULT soil_science::gravimetric_water_content", _summary_gravimetric_water_content)
    var _acc_field_capacity_estimate: Float64 = 0.0
    var _t0_field_capacity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_field_capacity_estimate += field_capacity_estimate(0.5)
    var _t1_field_capacity_estimate = perf_counter_ns()
    var _ns_field_capacity_estimate = Float64(_t1_field_capacity_estimate - _t0_field_capacity_estimate) / Float64(N)
    print("MOJO_TIMING soil_science::field_capacity_estimate", _ns_field_capacity_estimate, _acc_field_capacity_estimate)
    var _result_field_capacity_estimate = field_capacity_estimate(0.5)
    var _summary_field_capacity_estimate = _summary_float64(_result_field_capacity_estimate)
    print("MOJO_RESULT soil_science::field_capacity_estimate", _summary_field_capacity_estimate)
    var _acc_wilting_point_estimate: Float64 = 0.0
    var _t0_wilting_point_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_wilting_point_estimate += wilting_point_estimate(0.5)
    var _t1_wilting_point_estimate = perf_counter_ns()
    var _ns_wilting_point_estimate = Float64(_t1_wilting_point_estimate - _t0_wilting_point_estimate) / Float64(N)
    print("MOJO_TIMING soil_science::wilting_point_estimate", _ns_wilting_point_estimate, _acc_wilting_point_estimate)
    var _result_wilting_point_estimate = wilting_point_estimate(0.5)
    var _summary_wilting_point_estimate = _summary_float64(_result_wilting_point_estimate)
    print("MOJO_RESULT soil_science::wilting_point_estimate", _summary_wilting_point_estimate)
    var _acc_available_water: Float64 = 0.0
    var _t0_available_water = perf_counter_ns()
    for _ in range(N):
        _acc_available_water += available_water(0.5, 0.5, 0.5)
    var _t1_available_water = perf_counter_ns()
    var _ns_available_water = Float64(_t1_available_water - _t0_available_water) / Float64(N)
    print("MOJO_TIMING soil_science::available_water", _ns_available_water, _acc_available_water)
    var _result_available_water = available_water(0.5, 0.5, 0.5)
    var _summary_available_water = _summary_float64(_result_available_water)
    print("MOJO_RESULT soil_science::available_water", _summary_available_water)
    var _acc_cation_exchange_capacity_estimate: Float64 = 0.0
    var _t0_cation_exchange_capacity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_cation_exchange_capacity_estimate += cation_exchange_capacity_estimate(0.5, 0.5)
    var _t1_cation_exchange_capacity_estimate = perf_counter_ns()
    var _ns_cation_exchange_capacity_estimate = Float64(_t1_cation_exchange_capacity_estimate - _t0_cation_exchange_capacity_estimate) / Float64(N)
    print("MOJO_TIMING soil_science::cation_exchange_capacity_estimate", _ns_cation_exchange_capacity_estimate, _acc_cation_exchange_capacity_estimate)
    var _result_cation_exchange_capacity_estimate = cation_exchange_capacity_estimate(0.5, 0.5)
    var _summary_cation_exchange_capacity_estimate = _summary_float64(_result_cation_exchange_capacity_estimate)
    print("MOJO_RESULT soil_science::cation_exchange_capacity_estimate", _summary_cation_exchange_capacity_estimate)
    var _acc_soil_organic_carbon: Float64 = 0.0
    var _t0_soil_organic_carbon = perf_counter_ns()
    for _ in range(N):
        _acc_soil_organic_carbon += soil_organic_carbon(0.5)
    var _t1_soil_organic_carbon = perf_counter_ns()
    var _ns_soil_organic_carbon = Float64(_t1_soil_organic_carbon - _t0_soil_organic_carbon) / Float64(N)
    print("MOJO_TIMING soil_science::soil_organic_carbon", _ns_soil_organic_carbon, _acc_soil_organic_carbon)
    var _result_soil_organic_carbon = soil_organic_carbon(0.5)
    var _summary_soil_organic_carbon = _summary_float64(_result_soil_organic_carbon)
    print("MOJO_RESULT soil_science::soil_organic_carbon", _summary_soil_organic_carbon)
    var _acc_infiltration_rate_horton: Float64 = 0.0
    var _t0_infiltration_rate_horton = perf_counter_ns()
    for _ in range(N):
        _acc_infiltration_rate_horton += infiltration_rate_horton(0.5, 0.5, 0.5, 0.5)
    var _t1_infiltration_rate_horton = perf_counter_ns()
    var _ns_infiltration_rate_horton = Float64(_t1_infiltration_rate_horton - _t0_infiltration_rate_horton) / Float64(N)
    print("MOJO_TIMING soil_science::infiltration_rate_horton", _ns_infiltration_rate_horton, _acc_infiltration_rate_horton)
    var _result_infiltration_rate_horton = infiltration_rate_horton(0.5, 0.5, 0.5, 0.5)
    var _summary_infiltration_rate_horton = _summary_float64(_result_infiltration_rate_horton)
    print("MOJO_RESULT soil_science::infiltration_rate_horton", _summary_infiltration_rate_horton)
