"""bench_glaciology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from glaciology import glacier_mass_balance, ice_velocity_internal, basal_shear_stress, ablation_degree_day, ice_thickness_from_surface, snow_water_equivalent, equilibrium_line_altitude, calving_flux, sea_level_equivalent, albedo_feedback
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

    var _acc_glacier_mass_balance: Float64 = 0.0
    var _t0_glacier_mass_balance = perf_counter_ns()
    for _ in range(N):
        _acc_glacier_mass_balance += glacier_mass_balance(0.5, 0.5)
    var _t1_glacier_mass_balance = perf_counter_ns()
    var _ns_glacier_mass_balance = Float64(_t1_glacier_mass_balance - _t0_glacier_mass_balance) / Float64(N)
    print("MOJO_TIMING glaciology::glacier_mass_balance", _ns_glacier_mass_balance, _acc_glacier_mass_balance)
    var _acc_ice_velocity_internal: Float64 = 0.0
    var _t0_ice_velocity_internal = perf_counter_ns()
    for _ in range(N):
        _acc_ice_velocity_internal += ice_velocity_internal(0.5, 0.5, 0.5, 0.5)
    var _t1_ice_velocity_internal = perf_counter_ns()
    var _ns_ice_velocity_internal = Float64(_t1_ice_velocity_internal - _t0_ice_velocity_internal) / Float64(N)
    print("MOJO_TIMING glaciology::ice_velocity_internal", _ns_ice_velocity_internal, _acc_ice_velocity_internal)
    var _acc_basal_shear_stress: Float64 = 0.0
    var _t0_basal_shear_stress = perf_counter_ns()
    for _ in range(N):
        _acc_basal_shear_stress += basal_shear_stress(0.5, 0.5)
    var _t1_basal_shear_stress = perf_counter_ns()
    var _ns_basal_shear_stress = Float64(_t1_basal_shear_stress - _t0_basal_shear_stress) / Float64(N)
    print("MOJO_TIMING glaciology::basal_shear_stress", _ns_basal_shear_stress, _acc_basal_shear_stress)
    var _acc_ablation_degree_day: Float64 = 0.0
    var _t0_ablation_degree_day = perf_counter_ns()
    for _ in range(N):
        _acc_ablation_degree_day += ablation_degree_day(0.5, 0.5)
    var _t1_ablation_degree_day = perf_counter_ns()
    var _ns_ablation_degree_day = Float64(_t1_ablation_degree_day - _t0_ablation_degree_day) / Float64(N)
    print("MOJO_TIMING glaciology::ablation_degree_day", _ns_ablation_degree_day, _acc_ablation_degree_day)
    var _acc_ice_thickness_from_surface: Float64 = 0.0
    var _t0_ice_thickness_from_surface = perf_counter_ns()
    for _ in range(N):
        _acc_ice_thickness_from_surface += ice_thickness_from_surface(0.5, 0.5)
    var _t1_ice_thickness_from_surface = perf_counter_ns()
    var _ns_ice_thickness_from_surface = Float64(_t1_ice_thickness_from_surface - _t0_ice_thickness_from_surface) / Float64(N)
    print("MOJO_TIMING glaciology::ice_thickness_from_surface", _ns_ice_thickness_from_surface, _acc_ice_thickness_from_surface)
    var _acc_snow_water_equivalent: Float64 = 0.0
    var _t0_snow_water_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_snow_water_equivalent += snow_water_equivalent(0.5, 0.5)
    var _t1_snow_water_equivalent = perf_counter_ns()
    var _ns_snow_water_equivalent = Float64(_t1_snow_water_equivalent - _t0_snow_water_equivalent) / Float64(N)
    print("MOJO_TIMING glaciology::snow_water_equivalent", _ns_snow_water_equivalent, _acc_snow_water_equivalent)
    var _acc_equilibrium_line_altitude: Float64 = 0.0
    var _t0_equilibrium_line_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_equilibrium_line_altitude += equilibrium_line_altitude(0.5, 0.5, 0.5)
    var _t1_equilibrium_line_altitude = perf_counter_ns()
    var _ns_equilibrium_line_altitude = Float64(_t1_equilibrium_line_altitude - _t0_equilibrium_line_altitude) / Float64(N)
    print("MOJO_TIMING glaciology::equilibrium_line_altitude", _ns_equilibrium_line_altitude, _acc_equilibrium_line_altitude)
    var _acc_calving_flux: Float64 = 0.0
    var _t0_calving_flux = perf_counter_ns()
    for _ in range(N):
        _acc_calving_flux += calving_flux(0.5, 0.5, 0.5)
    var _t1_calving_flux = perf_counter_ns()
    var _ns_calving_flux = Float64(_t1_calving_flux - _t0_calving_flux) / Float64(N)
    print("MOJO_TIMING glaciology::calving_flux", _ns_calving_flux, _acc_calving_flux)
    var _acc_sea_level_equivalent: Float64 = 0.0
    var _t0_sea_level_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_sea_level_equivalent += sea_level_equivalent(0.5, 0.5)
    var _t1_sea_level_equivalent = perf_counter_ns()
    var _ns_sea_level_equivalent = Float64(_t1_sea_level_equivalent - _t0_sea_level_equivalent) / Float64(N)
    print("MOJO_TIMING glaciology::sea_level_equivalent", _ns_sea_level_equivalent, _acc_sea_level_equivalent)
    var _acc_albedo_feedback: Float64 = 0.0
    var _t0_albedo_feedback = perf_counter_ns()
    for _ in range(N):
        _acc_albedo_feedback += albedo_feedback(0.5, 0.5, 0.5)
    var _t1_albedo_feedback = perf_counter_ns()
    var _ns_albedo_feedback = Float64(_t1_albedo_feedback - _t0_albedo_feedback) / Float64(N)
    print("MOJO_TIMING glaciology::albedo_feedback", _ns_albedo_feedback, _acc_albedo_feedback)
