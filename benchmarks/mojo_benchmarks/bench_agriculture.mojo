"""bench_agriculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from agriculture import growing_degree_days, crop_water_need, irrigation_efficiency, fertilizer_rate, seed_rate, harvest_index, yield_per_hectare, soil_ph_lime_requirement, water_use_efficiency, photosynthetically_active_radiation, leaf_area_index, nitrogen_use_efficiency
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

    var _acc_growing_degree_days: Float64 = 0.0
    var _t0_growing_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_growing_degree_days += growing_degree_days(0.5, 0.5, 0.5)
    var _t1_growing_degree_days = perf_counter_ns()
    var _ns_growing_degree_days = Float64(_t1_growing_degree_days - _t0_growing_degree_days) / Float64(N)
    print("MOJO_TIMING agriculture::growing_degree_days", _ns_growing_degree_days, _acc_growing_degree_days)
    var _acc_crop_water_need: Float64 = 0.0
    var _t0_crop_water_need = perf_counter_ns()
    for _ in range(N):
        _acc_crop_water_need += crop_water_need(0.5, 0.5)
    var _t1_crop_water_need = perf_counter_ns()
    var _ns_crop_water_need = Float64(_t1_crop_water_need - _t0_crop_water_need) / Float64(N)
    print("MOJO_TIMING agriculture::crop_water_need", _ns_crop_water_need, _acc_crop_water_need)
    var _acc_irrigation_efficiency: Float64 = 0.0
    var _t0_irrigation_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_irrigation_efficiency += irrigation_efficiency(0.5, 0.5)
    var _t1_irrigation_efficiency = perf_counter_ns()
    var _ns_irrigation_efficiency = Float64(_t1_irrigation_efficiency - _t0_irrigation_efficiency) / Float64(N)
    print("MOJO_TIMING agriculture::irrigation_efficiency", _ns_irrigation_efficiency, _acc_irrigation_efficiency)
    var _acc_fertilizer_rate: Float64 = 0.0
    var _t0_fertilizer_rate = perf_counter_ns()
    for _ in range(N):
        _acc_fertilizer_rate += fertilizer_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_fertilizer_rate = perf_counter_ns()
    var _ns_fertilizer_rate = Float64(_t1_fertilizer_rate - _t0_fertilizer_rate) / Float64(N)
    print("MOJO_TIMING agriculture::fertilizer_rate", _ns_fertilizer_rate, _acc_fertilizer_rate)
    var _acc_seed_rate: Float64 = 0.0
    var _t0_seed_rate = perf_counter_ns()
    for _ in range(N):
        _acc_seed_rate += seed_rate(0.5, 0.5, 0.5)
    var _t1_seed_rate = perf_counter_ns()
    var _ns_seed_rate = Float64(_t1_seed_rate - _t0_seed_rate) / Float64(N)
    print("MOJO_TIMING agriculture::seed_rate", _ns_seed_rate, _acc_seed_rate)
    var _acc_harvest_index: Float64 = 0.0
    var _t0_harvest_index = perf_counter_ns()
    for _ in range(N):
        _acc_harvest_index += harvest_index(0.5, 0.5)
    var _t1_harvest_index = perf_counter_ns()
    var _ns_harvest_index = Float64(_t1_harvest_index - _t0_harvest_index) / Float64(N)
    print("MOJO_TIMING agriculture::harvest_index", _ns_harvest_index, _acc_harvest_index)
    var _acc_yield_per_hectare: Float64 = 0.0
    var _t0_yield_per_hectare = perf_counter_ns()
    for _ in range(N):
        _acc_yield_per_hectare += yield_per_hectare(0.5, 0.5)
    var _t1_yield_per_hectare = perf_counter_ns()
    var _ns_yield_per_hectare = Float64(_t1_yield_per_hectare - _t0_yield_per_hectare) / Float64(N)
    print("MOJO_TIMING agriculture::yield_per_hectare", _ns_yield_per_hectare, _acc_yield_per_hectare)
    var _acc_soil_ph_lime_requirement: Float64 = 0.0
    var _t0_soil_ph_lime_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_soil_ph_lime_requirement += soil_ph_lime_requirement(0.5, 0.5, 0.5)
    var _t1_soil_ph_lime_requirement = perf_counter_ns()
    var _ns_soil_ph_lime_requirement = Float64(_t1_soil_ph_lime_requirement - _t0_soil_ph_lime_requirement) / Float64(N)
    print("MOJO_TIMING agriculture::soil_ph_lime_requirement", _ns_soil_ph_lime_requirement, _acc_soil_ph_lime_requirement)
    var _acc_water_use_efficiency: Float64 = 0.0
    var _t0_water_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_water_use_efficiency += water_use_efficiency(0.5, 0.5)
    var _t1_water_use_efficiency = perf_counter_ns()
    var _ns_water_use_efficiency = Float64(_t1_water_use_efficiency - _t0_water_use_efficiency) / Float64(N)
    print("MOJO_TIMING agriculture::water_use_efficiency", _ns_water_use_efficiency, _acc_water_use_efficiency)
    var _acc_photosynthetically_active_radiation: Float64 = 0.0
    var _t0_photosynthetically_active_radiation = perf_counter_ns()
    for _ in range(N):
        _acc_photosynthetically_active_radiation += photosynthetically_active_radiation(0.5)
    var _t1_photosynthetically_active_radiation = perf_counter_ns()
    var _ns_photosynthetically_active_radiation = Float64(_t1_photosynthetically_active_radiation - _t0_photosynthetically_active_radiation) / Float64(N)
    print("MOJO_TIMING agriculture::photosynthetically_active_radiation", _ns_photosynthetically_active_radiation, _acc_photosynthetically_active_radiation)
    var _acc_leaf_area_index: Float64 = 0.0
    var _t0_leaf_area_index = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_area_index += leaf_area_index(0.5, 0.5)
    var _t1_leaf_area_index = perf_counter_ns()
    var _ns_leaf_area_index = Float64(_t1_leaf_area_index - _t0_leaf_area_index) / Float64(N)
    print("MOJO_TIMING agriculture::leaf_area_index", _ns_leaf_area_index, _acc_leaf_area_index)
    var _acc_nitrogen_use_efficiency: Float64 = 0.0
    var _t0_nitrogen_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_use_efficiency += nitrogen_use_efficiency(0.5, 0.5)
    var _t1_nitrogen_use_efficiency = perf_counter_ns()
    var _ns_nitrogen_use_efficiency = Float64(_t1_nitrogen_use_efficiency - _t0_nitrogen_use_efficiency) / Float64(N)
    print("MOJO_TIMING agriculture::nitrogen_use_efficiency", _ns_nitrogen_use_efficiency, _acc_nitrogen_use_efficiency)
