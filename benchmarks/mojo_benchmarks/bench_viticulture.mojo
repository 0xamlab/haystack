"""bench_viticulture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from viticulture import brix_to_potential_alcohol, chaptalization_sugar, total_acidity_as_tartaric, ph_buffer_capacity, growing_degree_days_wine, winkler_index_daily, yield_tonnes_per_hectare, vine_density, pruning_weight_ratio, must_volume_from_grapes, sulfite_molecular_so2, fermentation_progress
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

    var _acc_brix_to_potential_alcohol: Float64 = 0.0
    var _t0_brix_to_potential_alcohol = perf_counter_ns()
    for _ in range(N):
        _acc_brix_to_potential_alcohol += brix_to_potential_alcohol(0.5)
    var _t1_brix_to_potential_alcohol = perf_counter_ns()
    var _ns_brix_to_potential_alcohol = Float64(_t1_brix_to_potential_alcohol - _t0_brix_to_potential_alcohol) / Float64(N)
    print("MOJO_TIMING viticulture::brix_to_potential_alcohol", _ns_brix_to_potential_alcohol, _acc_brix_to_potential_alcohol)
    var _acc_chaptalization_sugar: Float64 = 0.0
    var _t0_chaptalization_sugar = perf_counter_ns()
    for _ in range(N):
        _acc_chaptalization_sugar += chaptalization_sugar(0.5, 0.5, 0.5)
    var _t1_chaptalization_sugar = perf_counter_ns()
    var _ns_chaptalization_sugar = Float64(_t1_chaptalization_sugar - _t0_chaptalization_sugar) / Float64(N)
    print("MOJO_TIMING viticulture::chaptalization_sugar", _ns_chaptalization_sugar, _acc_chaptalization_sugar)
    var _acc_total_acidity_as_tartaric: Float64 = 0.0
    var _t0_total_acidity_as_tartaric = perf_counter_ns()
    for _ in range(N):
        _acc_total_acidity_as_tartaric += total_acidity_as_tartaric(0.5)
    var _t1_total_acidity_as_tartaric = perf_counter_ns()
    var _ns_total_acidity_as_tartaric = Float64(_t1_total_acidity_as_tartaric - _t0_total_acidity_as_tartaric) / Float64(N)
    print("MOJO_TIMING viticulture::total_acidity_as_tartaric", _ns_total_acidity_as_tartaric, _acc_total_acidity_as_tartaric)
    var _acc_ph_buffer_capacity: Float64 = 0.0
    var _t0_ph_buffer_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_ph_buffer_capacity += ph_buffer_capacity(0.5, 0.5)
    var _t1_ph_buffer_capacity = perf_counter_ns()
    var _ns_ph_buffer_capacity = Float64(_t1_ph_buffer_capacity - _t0_ph_buffer_capacity) / Float64(N)
    print("MOJO_TIMING viticulture::ph_buffer_capacity", _ns_ph_buffer_capacity, _acc_ph_buffer_capacity)
    var _acc_growing_degree_days_wine: Float64 = 0.0
    var _t0_growing_degree_days_wine = perf_counter_ns()
    for _ in range(N):
        _acc_growing_degree_days_wine += growing_degree_days_wine(0.5, 0.5, 0.5)
    var _t1_growing_degree_days_wine = perf_counter_ns()
    var _ns_growing_degree_days_wine = Float64(_t1_growing_degree_days_wine - _t0_growing_degree_days_wine) / Float64(N)
    print("MOJO_TIMING viticulture::growing_degree_days_wine", _ns_growing_degree_days_wine, _acc_growing_degree_days_wine)
    var _acc_winkler_index_daily: Float64 = 0.0
    var _t0_winkler_index_daily = perf_counter_ns()
    for _ in range(N):
        _acc_winkler_index_daily += winkler_index_daily(0.5)
    var _t1_winkler_index_daily = perf_counter_ns()
    var _ns_winkler_index_daily = Float64(_t1_winkler_index_daily - _t0_winkler_index_daily) / Float64(N)
    print("MOJO_TIMING viticulture::winkler_index_daily", _ns_winkler_index_daily, _acc_winkler_index_daily)
    var _acc_yield_tonnes_per_hectare: Float64 = 0.0
    var _t0_yield_tonnes_per_hectare = perf_counter_ns()
    for _ in range(N):
        _acc_yield_tonnes_per_hectare += yield_tonnes_per_hectare(0.5, 0.5)
    var _t1_yield_tonnes_per_hectare = perf_counter_ns()
    var _ns_yield_tonnes_per_hectare = Float64(_t1_yield_tonnes_per_hectare - _t0_yield_tonnes_per_hectare) / Float64(N)
    print("MOJO_TIMING viticulture::yield_tonnes_per_hectare", _ns_yield_tonnes_per_hectare, _acc_yield_tonnes_per_hectare)
    var _acc_vine_density: Float64 = 0.0
    var _t0_vine_density = perf_counter_ns()
    for _ in range(N):
        _acc_vine_density += vine_density(0.5, 0.5, 0.5)
    var _t1_vine_density = perf_counter_ns()
    var _ns_vine_density = Float64(_t1_vine_density - _t0_vine_density) / Float64(N)
    print("MOJO_TIMING viticulture::vine_density", _ns_vine_density, _acc_vine_density)
    var _acc_pruning_weight_ratio: Float64 = 0.0
    var _t0_pruning_weight_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_pruning_weight_ratio += pruning_weight_ratio(0.5, 0.5)
    var _t1_pruning_weight_ratio = perf_counter_ns()
    var _ns_pruning_weight_ratio = Float64(_t1_pruning_weight_ratio - _t0_pruning_weight_ratio) / Float64(N)
    print("MOJO_TIMING viticulture::pruning_weight_ratio", _ns_pruning_weight_ratio, _acc_pruning_weight_ratio)
    var _acc_must_volume_from_grapes: Float64 = 0.0
    var _t0_must_volume_from_grapes = perf_counter_ns()
    for _ in range(N):
        _acc_must_volume_from_grapes += must_volume_from_grapes(0.5, 0.5)
    var _t1_must_volume_from_grapes = perf_counter_ns()
    var _ns_must_volume_from_grapes = Float64(_t1_must_volume_from_grapes - _t0_must_volume_from_grapes) / Float64(N)
    print("MOJO_TIMING viticulture::must_volume_from_grapes", _ns_must_volume_from_grapes, _acc_must_volume_from_grapes)
    var _acc_sulfite_molecular_so2: Float64 = 0.0
    var _t0_sulfite_molecular_so2 = perf_counter_ns()
    for _ in range(N):
        _acc_sulfite_molecular_so2 += sulfite_molecular_so2(0.5, 0.5)
    var _t1_sulfite_molecular_so2 = perf_counter_ns()
    var _ns_sulfite_molecular_so2 = Float64(_t1_sulfite_molecular_so2 - _t0_sulfite_molecular_so2) / Float64(N)
    print("MOJO_TIMING viticulture::sulfite_molecular_so2", _ns_sulfite_molecular_so2, _acc_sulfite_molecular_so2)
    var _acc_fermentation_progress: Float64 = 0.0
    var _t0_fermentation_progress = perf_counter_ns()
    for _ in range(N):
        _acc_fermentation_progress += fermentation_progress(0.5, 0.5)
    var _t1_fermentation_progress = perf_counter_ns()
    var _ns_fermentation_progress = Float64(_t1_fermentation_progress - _t0_fermentation_progress) / Float64(N)
    print("MOJO_TIMING viticulture::fermentation_progress", _ns_fermentation_progress, _acc_fermentation_progress)
