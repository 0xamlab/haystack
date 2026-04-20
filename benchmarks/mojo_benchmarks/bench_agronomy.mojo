"""bench_agronomy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from agronomy import crop_yield_potential, nitrogen_uptake_efficiency, soil_organic_matter_decay, evapotranspiration_penman, leaf_area_index, light_use_efficiency, crop_water_stress_index, irrigation_requirement, soil_cation_exchange, growing_degree_days
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

    var _acc_crop_yield_potential: Float64 = 0.0
    var _t0_crop_yield_potential = perf_counter_ns()
    for _ in range(N):
        _acc_crop_yield_potential += crop_yield_potential(0.5, 0.5, 0.5)
    var _t1_crop_yield_potential = perf_counter_ns()
    var _ns_crop_yield_potential = Float64(_t1_crop_yield_potential - _t0_crop_yield_potential) / Float64(N)
    print("MOJO_TIMING agronomy::crop_yield_potential", _ns_crop_yield_potential, _acc_crop_yield_potential)
    var _acc_nitrogen_uptake_efficiency: Float64 = 0.0
    var _t0_nitrogen_uptake_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_uptake_efficiency += nitrogen_uptake_efficiency(0.5, 0.5)
    var _t1_nitrogen_uptake_efficiency = perf_counter_ns()
    var _ns_nitrogen_uptake_efficiency = Float64(_t1_nitrogen_uptake_efficiency - _t0_nitrogen_uptake_efficiency) / Float64(N)
    print("MOJO_TIMING agronomy::nitrogen_uptake_efficiency", _ns_nitrogen_uptake_efficiency, _acc_nitrogen_uptake_efficiency)
    var _acc_soil_organic_matter_decay: Float64 = 0.0
    var _t0_soil_organic_matter_decay = perf_counter_ns()
    for _ in range(N):
        _acc_soil_organic_matter_decay += soil_organic_matter_decay(0.5, 0.5, 0.5)
    var _t1_soil_organic_matter_decay = perf_counter_ns()
    var _ns_soil_organic_matter_decay = Float64(_t1_soil_organic_matter_decay - _t0_soil_organic_matter_decay) / Float64(N)
    print("MOJO_TIMING agronomy::soil_organic_matter_decay", _ns_soil_organic_matter_decay, _acc_soil_organic_matter_decay)
    var _acc_evapotranspiration_penman: Float64 = 0.0
    var _t0_evapotranspiration_penman = perf_counter_ns()
    for _ in range(N):
        _acc_evapotranspiration_penman += evapotranspiration_penman(0.5, 0.5, 0.5, 0.5)
    var _t1_evapotranspiration_penman = perf_counter_ns()
    var _ns_evapotranspiration_penman = Float64(_t1_evapotranspiration_penman - _t0_evapotranspiration_penman) / Float64(N)
    print("MOJO_TIMING agronomy::evapotranspiration_penman", _ns_evapotranspiration_penman, _acc_evapotranspiration_penman)
    var _acc_leaf_area_index: Float64 = 0.0
    var _t0_leaf_area_index = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_area_index += leaf_area_index(0.5, 0.5)
    var _t1_leaf_area_index = perf_counter_ns()
    var _ns_leaf_area_index = Float64(_t1_leaf_area_index - _t0_leaf_area_index) / Float64(N)
    print("MOJO_TIMING agronomy::leaf_area_index", _ns_leaf_area_index, _acc_leaf_area_index)
    var _acc_light_use_efficiency: Float64 = 0.0
    var _t0_light_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_light_use_efficiency += light_use_efficiency(0.5, 0.5)
    var _t1_light_use_efficiency = perf_counter_ns()
    var _ns_light_use_efficiency = Float64(_t1_light_use_efficiency - _t0_light_use_efficiency) / Float64(N)
    print("MOJO_TIMING agronomy::light_use_efficiency", _ns_light_use_efficiency, _acc_light_use_efficiency)
    var _acc_crop_water_stress_index: Float64 = 0.0
    var _t0_crop_water_stress_index = perf_counter_ns()
    for _ in range(N):
        _acc_crop_water_stress_index += crop_water_stress_index(0.5, 0.5, 0.5)
    var _t1_crop_water_stress_index = perf_counter_ns()
    var _ns_crop_water_stress_index = Float64(_t1_crop_water_stress_index - _t0_crop_water_stress_index) / Float64(N)
    print("MOJO_TIMING agronomy::crop_water_stress_index", _ns_crop_water_stress_index, _acc_crop_water_stress_index)
    var _acc_irrigation_requirement: Float64 = 0.0
    var _t0_irrigation_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_irrigation_requirement += irrigation_requirement(0.5, 0.5, 0.5)
    var _t1_irrigation_requirement = perf_counter_ns()
    var _ns_irrigation_requirement = Float64(_t1_irrigation_requirement - _t0_irrigation_requirement) / Float64(N)
    print("MOJO_TIMING agronomy::irrigation_requirement", _ns_irrigation_requirement, _acc_irrigation_requirement)
    var _acc_soil_cation_exchange: Float64 = 0.0
    var _t0_soil_cation_exchange = perf_counter_ns()
    for _ in range(N):
        _acc_soil_cation_exchange += soil_cation_exchange(0.5, 0.5)
    var _t1_soil_cation_exchange = perf_counter_ns()
    var _ns_soil_cation_exchange = Float64(_t1_soil_cation_exchange - _t0_soil_cation_exchange) / Float64(N)
    print("MOJO_TIMING agronomy::soil_cation_exchange", _ns_soil_cation_exchange, _acc_soil_cation_exchange)
    var _acc_growing_degree_days: Float64 = 0.0
    var _t0_growing_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_growing_degree_days += growing_degree_days(0.5, 0.5, 0.5)
    var _t1_growing_degree_days = perf_counter_ns()
    var _ns_growing_degree_days = Float64(_t1_growing_degree_days - _t0_growing_degree_days) / Float64(N)
    print("MOJO_TIMING agronomy::growing_degree_days", _ns_growing_degree_days, _acc_growing_degree_days)
