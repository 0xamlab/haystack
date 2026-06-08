"""bench_glaciology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from glaciology import glacier_mass_balance, ice_velocity_internal, basal_shear_stress, ablation_degree_day, ice_thickness_from_surface, snow_water_equivalent, equilibrium_line_altitude, calving_flux, sea_level_equivalent, albedo_feedback
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

    var _acc_glacier_mass_balance: Float64 = 0.0
    var _t0_glacier_mass_balance = perf_counter_ns()
    for _ in range(N):
        _acc_glacier_mass_balance += glacier_mass_balance(0.5, 0.5)
    var _t1_glacier_mass_balance = perf_counter_ns()
    var _ns_glacier_mass_balance = Float64(_t1_glacier_mass_balance - _t0_glacier_mass_balance) / Float64(N)
    print("MOJO_TIMING glaciology::glacier_mass_balance", _ns_glacier_mass_balance, _acc_glacier_mass_balance)
    var _result_glacier_mass_balance = glacier_mass_balance(0.5, 0.5)
    var _summary_glacier_mass_balance = _summary_float64(_result_glacier_mass_balance)
    print("MOJO_RESULT glaciology::glacier_mass_balance", _summary_glacier_mass_balance)
    var _acc_ice_velocity_internal: Float64 = 0.0
    var _t0_ice_velocity_internal = perf_counter_ns()
    for _ in range(N):
        _acc_ice_velocity_internal += ice_velocity_internal(0.5, 0.5, 0.5, 0.5)
    var _t1_ice_velocity_internal = perf_counter_ns()
    var _ns_ice_velocity_internal = Float64(_t1_ice_velocity_internal - _t0_ice_velocity_internal) / Float64(N)
    print("MOJO_TIMING glaciology::ice_velocity_internal", _ns_ice_velocity_internal, _acc_ice_velocity_internal)
    var _result_ice_velocity_internal = ice_velocity_internal(0.5, 0.5, 0.5, 0.5)
    var _summary_ice_velocity_internal = _summary_float64(_result_ice_velocity_internal)
    print("MOJO_RESULT glaciology::ice_velocity_internal", _summary_ice_velocity_internal)
    var _acc_basal_shear_stress: Float64 = 0.0
    var _t0_basal_shear_stress = perf_counter_ns()
    for _ in range(N):
        _acc_basal_shear_stress += basal_shear_stress(0.5, 0.5)
    var _t1_basal_shear_stress = perf_counter_ns()
    var _ns_basal_shear_stress = Float64(_t1_basal_shear_stress - _t0_basal_shear_stress) / Float64(N)
    print("MOJO_TIMING glaciology::basal_shear_stress", _ns_basal_shear_stress, _acc_basal_shear_stress)
    var _result_basal_shear_stress = basal_shear_stress(0.5, 0.5)
    var _summary_basal_shear_stress = _summary_float64(_result_basal_shear_stress)
    print("MOJO_RESULT glaciology::basal_shear_stress", _summary_basal_shear_stress)
    var _acc_ablation_degree_day: Float64 = 0.0
    var _t0_ablation_degree_day = perf_counter_ns()
    for _ in range(N):
        _acc_ablation_degree_day += ablation_degree_day(0.5, 0.5)
    var _t1_ablation_degree_day = perf_counter_ns()
    var _ns_ablation_degree_day = Float64(_t1_ablation_degree_day - _t0_ablation_degree_day) / Float64(N)
    print("MOJO_TIMING glaciology::ablation_degree_day", _ns_ablation_degree_day, _acc_ablation_degree_day)
    var _result_ablation_degree_day = ablation_degree_day(0.5, 0.5)
    var _summary_ablation_degree_day = _summary_float64(_result_ablation_degree_day)
    print("MOJO_RESULT glaciology::ablation_degree_day", _summary_ablation_degree_day)
    var _acc_ice_thickness_from_surface: Float64 = 0.0
    var _t0_ice_thickness_from_surface = perf_counter_ns()
    for _ in range(N):
        _acc_ice_thickness_from_surface += ice_thickness_from_surface(0.5, 0.5)
    var _t1_ice_thickness_from_surface = perf_counter_ns()
    var _ns_ice_thickness_from_surface = Float64(_t1_ice_thickness_from_surface - _t0_ice_thickness_from_surface) / Float64(N)
    print("MOJO_TIMING glaciology::ice_thickness_from_surface", _ns_ice_thickness_from_surface, _acc_ice_thickness_from_surface)
    var _result_ice_thickness_from_surface = ice_thickness_from_surface(0.5, 0.5)
    var _summary_ice_thickness_from_surface = _summary_float64(_result_ice_thickness_from_surface)
    print("MOJO_RESULT glaciology::ice_thickness_from_surface", _summary_ice_thickness_from_surface)
    var _acc_snow_water_equivalent: Float64 = 0.0
    var _t0_snow_water_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_snow_water_equivalent += snow_water_equivalent(0.5, 0.5)
    var _t1_snow_water_equivalent = perf_counter_ns()
    var _ns_snow_water_equivalent = Float64(_t1_snow_water_equivalent - _t0_snow_water_equivalent) / Float64(N)
    print("MOJO_TIMING glaciology::snow_water_equivalent", _ns_snow_water_equivalent, _acc_snow_water_equivalent)
    var _result_snow_water_equivalent = snow_water_equivalent(0.5, 0.5)
    var _summary_snow_water_equivalent = _summary_float64(_result_snow_water_equivalent)
    print("MOJO_RESULT glaciology::snow_water_equivalent", _summary_snow_water_equivalent)
    var _acc_equilibrium_line_altitude: Float64 = 0.0
    var _t0_equilibrium_line_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_equilibrium_line_altitude += equilibrium_line_altitude(0.5, 0.5, 0.5)
    var _t1_equilibrium_line_altitude = perf_counter_ns()
    var _ns_equilibrium_line_altitude = Float64(_t1_equilibrium_line_altitude - _t0_equilibrium_line_altitude) / Float64(N)
    print("MOJO_TIMING glaciology::equilibrium_line_altitude", _ns_equilibrium_line_altitude, _acc_equilibrium_line_altitude)
    var _result_equilibrium_line_altitude = equilibrium_line_altitude(0.5, 0.5, 0.5)
    var _summary_equilibrium_line_altitude = _summary_float64(_result_equilibrium_line_altitude)
    print("MOJO_RESULT glaciology::equilibrium_line_altitude", _summary_equilibrium_line_altitude)
    var _acc_calving_flux: Float64 = 0.0
    var _t0_calving_flux = perf_counter_ns()
    for _ in range(N):
        _acc_calving_flux += calving_flux(0.5, 0.5, 0.5)
    var _t1_calving_flux = perf_counter_ns()
    var _ns_calving_flux = Float64(_t1_calving_flux - _t0_calving_flux) / Float64(N)
    print("MOJO_TIMING glaciology::calving_flux", _ns_calving_flux, _acc_calving_flux)
    var _result_calving_flux = calving_flux(0.5, 0.5, 0.5)
    var _summary_calving_flux = _summary_float64(_result_calving_flux)
    print("MOJO_RESULT glaciology::calving_flux", _summary_calving_flux)
    var _acc_sea_level_equivalent: Float64 = 0.0
    var _t0_sea_level_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_sea_level_equivalent += sea_level_equivalent(0.5, 0.5)
    var _t1_sea_level_equivalent = perf_counter_ns()
    var _ns_sea_level_equivalent = Float64(_t1_sea_level_equivalent - _t0_sea_level_equivalent) / Float64(N)
    print("MOJO_TIMING glaciology::sea_level_equivalent", _ns_sea_level_equivalent, _acc_sea_level_equivalent)
    var _result_sea_level_equivalent = sea_level_equivalent(0.5, 0.5)
    var _summary_sea_level_equivalent = _summary_float64(_result_sea_level_equivalent)
    print("MOJO_RESULT glaciology::sea_level_equivalent", _summary_sea_level_equivalent)
    var _acc_albedo_feedback: Float64 = 0.0
    var _t0_albedo_feedback = perf_counter_ns()
    for _ in range(N):
        _acc_albedo_feedback += albedo_feedback(0.5, 0.5, 0.5)
    var _t1_albedo_feedback = perf_counter_ns()
    var _ns_albedo_feedback = Float64(_t1_albedo_feedback - _t0_albedo_feedback) / Float64(N)
    print("MOJO_TIMING glaciology::albedo_feedback", _ns_albedo_feedback, _acc_albedo_feedback)
    var _result_albedo_feedback = albedo_feedback(0.5, 0.5, 0.5)
    var _summary_albedo_feedback = _summary_float64(_result_albedo_feedback)
    print("MOJO_RESULT glaciology::albedo_feedback", _summary_albedo_feedback)
