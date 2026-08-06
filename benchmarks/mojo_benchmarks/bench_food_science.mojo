"""bench_food_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from food_science import water_activity, ph_from_h_concentration, shelf_life_q10, thermal_death_time, d_value_from_z, pasteurization_units, brix_to_sugar_g_per_l, caloric_density, moisture_content_wet_basis, moisture_content_dry_basis, freezing_point_depression, blanching_time_estimate
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

    var _acc_water_activity: Float64 = 0.0
    var _t0_water_activity = perf_counter_ns()
    for _ in range(N):
        _acc_water_activity += water_activity(0.5)
    var _t1_water_activity = perf_counter_ns()
    var _ns_water_activity = Float64(_t1_water_activity - _t0_water_activity) / Float64(N)
    print("MOJO_TIMING food_science::water_activity", _ns_water_activity, _acc_water_activity)
    var _result_water_activity = water_activity(0.5)
    var _summary_water_activity = _summary_float64(_result_water_activity)
    print("MOJO_RESULT food_science::water_activity", _summary_water_activity)
    var _acc_ph_from_h_concentration: Float64 = 0.0
    var _t0_ph_from_h_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_ph_from_h_concentration += ph_from_h_concentration(0.5)
    var _t1_ph_from_h_concentration = perf_counter_ns()
    var _ns_ph_from_h_concentration = Float64(_t1_ph_from_h_concentration - _t0_ph_from_h_concentration) / Float64(N)
    print("MOJO_TIMING food_science::ph_from_h_concentration", _ns_ph_from_h_concentration, _acc_ph_from_h_concentration)
    var _result_ph_from_h_concentration = ph_from_h_concentration(0.5)
    var _summary_ph_from_h_concentration = _summary_float64(_result_ph_from_h_concentration)
    print("MOJO_RESULT food_science::ph_from_h_concentration", _summary_ph_from_h_concentration)
    var _acc_shelf_life_q10: Float64 = 0.0
    var _t0_shelf_life_q10 = perf_counter_ns()
    for _ in range(N):
        _acc_shelf_life_q10 += shelf_life_q10(0.5, 0.5, 0.5)
    var _t1_shelf_life_q10 = perf_counter_ns()
    var _ns_shelf_life_q10 = Float64(_t1_shelf_life_q10 - _t0_shelf_life_q10) / Float64(N)
    print("MOJO_TIMING food_science::shelf_life_q10", _ns_shelf_life_q10, _acc_shelf_life_q10)
    var _result_shelf_life_q10 = shelf_life_q10(0.5, 0.5, 0.5)
    var _summary_shelf_life_q10 = _summary_float64(_result_shelf_life_q10)
    print("MOJO_RESULT food_science::shelf_life_q10", _summary_shelf_life_q10)
    var _acc_thermal_death_time: Float64 = 0.0
    var _t0_thermal_death_time = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_death_time += thermal_death_time(0.5, 0.5)
    var _t1_thermal_death_time = perf_counter_ns()
    var _ns_thermal_death_time = Float64(_t1_thermal_death_time - _t0_thermal_death_time) / Float64(N)
    print("MOJO_TIMING food_science::thermal_death_time", _ns_thermal_death_time, _acc_thermal_death_time)
    var _result_thermal_death_time = thermal_death_time(0.5, 0.5)
    var _summary_thermal_death_time = _summary_float64(_result_thermal_death_time)
    print("MOJO_RESULT food_science::thermal_death_time", _summary_thermal_death_time)
    var _acc_d_value_from_z: Float64 = 0.0
    var _t0_d_value_from_z = perf_counter_ns()
    for _ in range(N):
        _acc_d_value_from_z += d_value_from_z(0.5, 0.5, 0.5, 0.5)
    var _t1_d_value_from_z = perf_counter_ns()
    var _ns_d_value_from_z = Float64(_t1_d_value_from_z - _t0_d_value_from_z) / Float64(N)
    print("MOJO_TIMING food_science::d_value_from_z", _ns_d_value_from_z, _acc_d_value_from_z)
    var _result_d_value_from_z = d_value_from_z(0.5, 0.5, 0.5, 0.5)
    var _summary_d_value_from_z = _summary_float64(_result_d_value_from_z)
    print("MOJO_RESULT food_science::d_value_from_z", _summary_d_value_from_z)
    var _acc_pasteurization_units: Float64 = 0.0
    var _t0_pasteurization_units = perf_counter_ns()
    for _ in range(N):
        _acc_pasteurization_units += pasteurization_units(0.5, 0.5, 0.5, 0.5)
    var _t1_pasteurization_units = perf_counter_ns()
    var _ns_pasteurization_units = Float64(_t1_pasteurization_units - _t0_pasteurization_units) / Float64(N)
    print("MOJO_TIMING food_science::pasteurization_units", _ns_pasteurization_units, _acc_pasteurization_units)
    var _result_pasteurization_units = pasteurization_units(0.5, 0.5, 0.5, 0.5)
    var _summary_pasteurization_units = _summary_float64(_result_pasteurization_units)
    print("MOJO_RESULT food_science::pasteurization_units", _summary_pasteurization_units)
    var _acc_brix_to_sugar_g_per_l: Float64 = 0.0
    var _t0_brix_to_sugar_g_per_l = perf_counter_ns()
    for _ in range(N):
        _acc_brix_to_sugar_g_per_l += brix_to_sugar_g_per_l(0.5)
    var _t1_brix_to_sugar_g_per_l = perf_counter_ns()
    var _ns_brix_to_sugar_g_per_l = Float64(_t1_brix_to_sugar_g_per_l - _t0_brix_to_sugar_g_per_l) / Float64(N)
    print("MOJO_TIMING food_science::brix_to_sugar_g_per_l", _ns_brix_to_sugar_g_per_l, _acc_brix_to_sugar_g_per_l)
    var _result_brix_to_sugar_g_per_l = brix_to_sugar_g_per_l(0.5)
    var _summary_brix_to_sugar_g_per_l = _summary_float64(_result_brix_to_sugar_g_per_l)
    print("MOJO_RESULT food_science::brix_to_sugar_g_per_l", _summary_brix_to_sugar_g_per_l)
    var _acc_caloric_density: Float64 = 0.0
    var _t0_caloric_density = perf_counter_ns()
    for _ in range(N):
        _acc_caloric_density += caloric_density(0.5, 0.5, 0.5, 0.5)
    var _t1_caloric_density = perf_counter_ns()
    var _ns_caloric_density = Float64(_t1_caloric_density - _t0_caloric_density) / Float64(N)
    print("MOJO_TIMING food_science::caloric_density", _ns_caloric_density, _acc_caloric_density)
    var _result_caloric_density = caloric_density(0.5, 0.5, 0.5, 0.5)
    var _summary_caloric_density = _summary_float64(_result_caloric_density)
    print("MOJO_RESULT food_science::caloric_density", _summary_caloric_density)
    var _acc_moisture_content_wet_basis: Float64 = 0.0
    var _t0_moisture_content_wet_basis = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_wet_basis += moisture_content_wet_basis(0.5, 0.5)
    var _t1_moisture_content_wet_basis = perf_counter_ns()
    var _ns_moisture_content_wet_basis = Float64(_t1_moisture_content_wet_basis - _t0_moisture_content_wet_basis) / Float64(N)
    print("MOJO_TIMING food_science::moisture_content_wet_basis", _ns_moisture_content_wet_basis, _acc_moisture_content_wet_basis)
    var _result_moisture_content_wet_basis = moisture_content_wet_basis(0.5, 0.5)
    var _summary_moisture_content_wet_basis = _summary_float64(_result_moisture_content_wet_basis)
    print("MOJO_RESULT food_science::moisture_content_wet_basis", _summary_moisture_content_wet_basis)
    var _acc_moisture_content_dry_basis: Float64 = 0.0
    var _t0_moisture_content_dry_basis = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_dry_basis += moisture_content_dry_basis(0.5, 0.5)
    var _t1_moisture_content_dry_basis = perf_counter_ns()
    var _ns_moisture_content_dry_basis = Float64(_t1_moisture_content_dry_basis - _t0_moisture_content_dry_basis) / Float64(N)
    print("MOJO_TIMING food_science::moisture_content_dry_basis", _ns_moisture_content_dry_basis, _acc_moisture_content_dry_basis)
    var _result_moisture_content_dry_basis = moisture_content_dry_basis(0.5, 0.5)
    var _summary_moisture_content_dry_basis = _summary_float64(_result_moisture_content_dry_basis)
    print("MOJO_RESULT food_science::moisture_content_dry_basis", _summary_moisture_content_dry_basis)
    var _acc_freezing_point_depression: Float64 = 0.0
    var _t0_freezing_point_depression = perf_counter_ns()
    for _ in range(N):
        _acc_freezing_point_depression += freezing_point_depression(0.5, 0.5)
    var _t1_freezing_point_depression = perf_counter_ns()
    var _ns_freezing_point_depression = Float64(_t1_freezing_point_depression - _t0_freezing_point_depression) / Float64(N)
    print("MOJO_TIMING food_science::freezing_point_depression", _ns_freezing_point_depression, _acc_freezing_point_depression)
    var _result_freezing_point_depression = freezing_point_depression(0.5, 0.5)
    var _summary_freezing_point_depression = _summary_float64(_result_freezing_point_depression)
    print("MOJO_RESULT food_science::freezing_point_depression", _summary_freezing_point_depression)
    var _acc_blanching_time_estimate: Float64 = 0.0
    var _t0_blanching_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_blanching_time_estimate += blanching_time_estimate(0.5, 0.5)
    var _t1_blanching_time_estimate = perf_counter_ns()
    var _ns_blanching_time_estimate = Float64(_t1_blanching_time_estimate - _t0_blanching_time_estimate) / Float64(N)
    print("MOJO_TIMING food_science::blanching_time_estimate", _ns_blanching_time_estimate, _acc_blanching_time_estimate)
    var _result_blanching_time_estimate = blanching_time_estimate(0.5, 0.5)
    var _summary_blanching_time_estimate = _summary_float64(_result_blanching_time_estimate)
    print("MOJO_RESULT food_science::blanching_time_estimate", _summary_blanching_time_estimate)
