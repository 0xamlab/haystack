"""bench_food_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from food_science import water_activity, ph_from_h_concentration, shelf_life_q10, thermal_death_time, d_value_from_z, pasteurization_units, brix_to_sugar_g_per_l, caloric_density, moisture_content_wet_basis, moisture_content_dry_basis, freezing_point_depression, blanching_time_estimate
from std.time import perf_counter_ns

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
    var _acc_ph_from_h_concentration: Float64 = 0.0
    var _t0_ph_from_h_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_ph_from_h_concentration += ph_from_h_concentration(0.5)
    var _t1_ph_from_h_concentration = perf_counter_ns()
    var _ns_ph_from_h_concentration = Float64(_t1_ph_from_h_concentration - _t0_ph_from_h_concentration) / Float64(N)
    print("MOJO_TIMING food_science::ph_from_h_concentration", _ns_ph_from_h_concentration, _acc_ph_from_h_concentration)
    var _acc_shelf_life_q10: Float64 = 0.0
    var _t0_shelf_life_q10 = perf_counter_ns()
    for _ in range(N):
        _acc_shelf_life_q10 += shelf_life_q10(0.5, 0.5, 0.5)
    var _t1_shelf_life_q10 = perf_counter_ns()
    var _ns_shelf_life_q10 = Float64(_t1_shelf_life_q10 - _t0_shelf_life_q10) / Float64(N)
    print("MOJO_TIMING food_science::shelf_life_q10", _ns_shelf_life_q10, _acc_shelf_life_q10)
    var _acc_thermal_death_time: Float64 = 0.0
    var _t0_thermal_death_time = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_death_time += thermal_death_time(0.5, 0.5)
    var _t1_thermal_death_time = perf_counter_ns()
    var _ns_thermal_death_time = Float64(_t1_thermal_death_time - _t0_thermal_death_time) / Float64(N)
    print("MOJO_TIMING food_science::thermal_death_time", _ns_thermal_death_time, _acc_thermal_death_time)
    var _acc_d_value_from_z: Float64 = 0.0
    var _t0_d_value_from_z = perf_counter_ns()
    for _ in range(N):
        _acc_d_value_from_z += d_value_from_z(0.5, 0.5, 0.5, 0.5)
    var _t1_d_value_from_z = perf_counter_ns()
    var _ns_d_value_from_z = Float64(_t1_d_value_from_z - _t0_d_value_from_z) / Float64(N)
    print("MOJO_TIMING food_science::d_value_from_z", _ns_d_value_from_z, _acc_d_value_from_z)
    var _acc_pasteurization_units: Float64 = 0.0
    var _t0_pasteurization_units = perf_counter_ns()
    for _ in range(N):
        _acc_pasteurization_units += pasteurization_units(0.5, 0.5, 0.5, 0.5)
    var _t1_pasteurization_units = perf_counter_ns()
    var _ns_pasteurization_units = Float64(_t1_pasteurization_units - _t0_pasteurization_units) / Float64(N)
    print("MOJO_TIMING food_science::pasteurization_units", _ns_pasteurization_units, _acc_pasteurization_units)
    var _acc_brix_to_sugar_g_per_l: Float64 = 0.0
    var _t0_brix_to_sugar_g_per_l = perf_counter_ns()
    for _ in range(N):
        _acc_brix_to_sugar_g_per_l += brix_to_sugar_g_per_l(0.5)
    var _t1_brix_to_sugar_g_per_l = perf_counter_ns()
    var _ns_brix_to_sugar_g_per_l = Float64(_t1_brix_to_sugar_g_per_l - _t0_brix_to_sugar_g_per_l) / Float64(N)
    print("MOJO_TIMING food_science::brix_to_sugar_g_per_l", _ns_brix_to_sugar_g_per_l, _acc_brix_to_sugar_g_per_l)
    var _acc_caloric_density: Float64 = 0.0
    var _t0_caloric_density = perf_counter_ns()
    for _ in range(N):
        _acc_caloric_density += caloric_density(0.5, 0.5, 0.5, 0.5)
    var _t1_caloric_density = perf_counter_ns()
    var _ns_caloric_density = Float64(_t1_caloric_density - _t0_caloric_density) / Float64(N)
    print("MOJO_TIMING food_science::caloric_density", _ns_caloric_density, _acc_caloric_density)
    var _acc_moisture_content_wet_basis: Float64 = 0.0
    var _t0_moisture_content_wet_basis = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_wet_basis += moisture_content_wet_basis(0.5, 0.5)
    var _t1_moisture_content_wet_basis = perf_counter_ns()
    var _ns_moisture_content_wet_basis = Float64(_t1_moisture_content_wet_basis - _t0_moisture_content_wet_basis) / Float64(N)
    print("MOJO_TIMING food_science::moisture_content_wet_basis", _ns_moisture_content_wet_basis, _acc_moisture_content_wet_basis)
    var _acc_moisture_content_dry_basis: Float64 = 0.0
    var _t0_moisture_content_dry_basis = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_dry_basis += moisture_content_dry_basis(0.5, 0.5)
    var _t1_moisture_content_dry_basis = perf_counter_ns()
    var _ns_moisture_content_dry_basis = Float64(_t1_moisture_content_dry_basis - _t0_moisture_content_dry_basis) / Float64(N)
    print("MOJO_TIMING food_science::moisture_content_dry_basis", _ns_moisture_content_dry_basis, _acc_moisture_content_dry_basis)
    var _acc_freezing_point_depression: Float64 = 0.0
    var _t0_freezing_point_depression = perf_counter_ns()
    for _ in range(N):
        _acc_freezing_point_depression += freezing_point_depression(0.5, 0.5)
    var _t1_freezing_point_depression = perf_counter_ns()
    var _ns_freezing_point_depression = Float64(_t1_freezing_point_depression - _t0_freezing_point_depression) / Float64(N)
    print("MOJO_TIMING food_science::freezing_point_depression", _ns_freezing_point_depression, _acc_freezing_point_depression)
    var _acc_blanching_time_estimate: Float64 = 0.0
    var _t0_blanching_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_blanching_time_estimate += blanching_time_estimate(0.5, 0.5)
    var _t1_blanching_time_estimate = perf_counter_ns()
    var _ns_blanching_time_estimate = Float64(_t1_blanching_time_estimate - _t0_blanching_time_estimate) / Float64(N)
    print("MOJO_TIMING food_science::blanching_time_estimate", _ns_blanching_time_estimate, _acc_blanching_time_estimate)
