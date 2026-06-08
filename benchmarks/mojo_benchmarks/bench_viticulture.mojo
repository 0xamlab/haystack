"""bench_viticulture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from viticulture import brix_to_potential_alcohol, chaptalization_sugar, total_acidity_as_tartaric, ph_buffer_capacity, growing_degree_days_wine, winkler_index_daily, yield_tonnes_per_hectare, vine_density, pruning_weight_ratio, must_volume_from_grapes, sulfite_molecular_so2, fermentation_progress
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

    var _acc_brix_to_potential_alcohol: Float64 = 0.0
    var _t0_brix_to_potential_alcohol = perf_counter_ns()
    for _ in range(N):
        _acc_brix_to_potential_alcohol += brix_to_potential_alcohol(0.5)
    var _t1_brix_to_potential_alcohol = perf_counter_ns()
    var _ns_brix_to_potential_alcohol = Float64(_t1_brix_to_potential_alcohol - _t0_brix_to_potential_alcohol) / Float64(N)
    print("MOJO_TIMING viticulture::brix_to_potential_alcohol", _ns_brix_to_potential_alcohol, _acc_brix_to_potential_alcohol)
    var _result_brix_to_potential_alcohol = brix_to_potential_alcohol(0.5)
    var _summary_brix_to_potential_alcohol = _summary_float64(_result_brix_to_potential_alcohol)
    print("MOJO_RESULT viticulture::brix_to_potential_alcohol", _summary_brix_to_potential_alcohol)
    var _acc_chaptalization_sugar: Float64 = 0.0
    var _t0_chaptalization_sugar = perf_counter_ns()
    for _ in range(N):
        _acc_chaptalization_sugar += chaptalization_sugar(0.5, 0.5, 0.5)
    var _t1_chaptalization_sugar = perf_counter_ns()
    var _ns_chaptalization_sugar = Float64(_t1_chaptalization_sugar - _t0_chaptalization_sugar) / Float64(N)
    print("MOJO_TIMING viticulture::chaptalization_sugar", _ns_chaptalization_sugar, _acc_chaptalization_sugar)
    var _result_chaptalization_sugar = chaptalization_sugar(0.5, 0.5, 0.5)
    var _summary_chaptalization_sugar = _summary_float64(_result_chaptalization_sugar)
    print("MOJO_RESULT viticulture::chaptalization_sugar", _summary_chaptalization_sugar)
    var _acc_total_acidity_as_tartaric: Float64 = 0.0
    var _t0_total_acidity_as_tartaric = perf_counter_ns()
    for _ in range(N):
        _acc_total_acidity_as_tartaric += total_acidity_as_tartaric(0.5)
    var _t1_total_acidity_as_tartaric = perf_counter_ns()
    var _ns_total_acidity_as_tartaric = Float64(_t1_total_acidity_as_tartaric - _t0_total_acidity_as_tartaric) / Float64(N)
    print("MOJO_TIMING viticulture::total_acidity_as_tartaric", _ns_total_acidity_as_tartaric, _acc_total_acidity_as_tartaric)
    var _result_total_acidity_as_tartaric = total_acidity_as_tartaric(0.5)
    var _summary_total_acidity_as_tartaric = _summary_float64(_result_total_acidity_as_tartaric)
    print("MOJO_RESULT viticulture::total_acidity_as_tartaric", _summary_total_acidity_as_tartaric)
    var _acc_ph_buffer_capacity: Float64 = 0.0
    var _t0_ph_buffer_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_ph_buffer_capacity += ph_buffer_capacity(0.5, 0.5)
    var _t1_ph_buffer_capacity = perf_counter_ns()
    var _ns_ph_buffer_capacity = Float64(_t1_ph_buffer_capacity - _t0_ph_buffer_capacity) / Float64(N)
    print("MOJO_TIMING viticulture::ph_buffer_capacity", _ns_ph_buffer_capacity, _acc_ph_buffer_capacity)
    var _result_ph_buffer_capacity = ph_buffer_capacity(0.5, 0.5)
    var _summary_ph_buffer_capacity = _summary_float64(_result_ph_buffer_capacity)
    print("MOJO_RESULT viticulture::ph_buffer_capacity", _summary_ph_buffer_capacity)
    var _acc_growing_degree_days_wine: Float64 = 0.0
    var _t0_growing_degree_days_wine = perf_counter_ns()
    for _ in range(N):
        _acc_growing_degree_days_wine += growing_degree_days_wine(0.5, 0.5, 0.5)
    var _t1_growing_degree_days_wine = perf_counter_ns()
    var _ns_growing_degree_days_wine = Float64(_t1_growing_degree_days_wine - _t0_growing_degree_days_wine) / Float64(N)
    print("MOJO_TIMING viticulture::growing_degree_days_wine", _ns_growing_degree_days_wine, _acc_growing_degree_days_wine)
    var _result_growing_degree_days_wine = growing_degree_days_wine(0.5, 0.5, 0.5)
    var _summary_growing_degree_days_wine = _summary_float64(_result_growing_degree_days_wine)
    print("MOJO_RESULT viticulture::growing_degree_days_wine", _summary_growing_degree_days_wine)
    var _acc_winkler_index_daily: Float64 = 0.0
    var _t0_winkler_index_daily = perf_counter_ns()
    for _ in range(N):
        _acc_winkler_index_daily += winkler_index_daily(0.5)
    var _t1_winkler_index_daily = perf_counter_ns()
    var _ns_winkler_index_daily = Float64(_t1_winkler_index_daily - _t0_winkler_index_daily) / Float64(N)
    print("MOJO_TIMING viticulture::winkler_index_daily", _ns_winkler_index_daily, _acc_winkler_index_daily)
    var _result_winkler_index_daily = winkler_index_daily(0.5)
    var _summary_winkler_index_daily = _summary_float64(_result_winkler_index_daily)
    print("MOJO_RESULT viticulture::winkler_index_daily", _summary_winkler_index_daily)
    var _acc_yield_tonnes_per_hectare: Float64 = 0.0
    var _t0_yield_tonnes_per_hectare = perf_counter_ns()
    for _ in range(N):
        _acc_yield_tonnes_per_hectare += yield_tonnes_per_hectare(0.5, 0.5)
    var _t1_yield_tonnes_per_hectare = perf_counter_ns()
    var _ns_yield_tonnes_per_hectare = Float64(_t1_yield_tonnes_per_hectare - _t0_yield_tonnes_per_hectare) / Float64(N)
    print("MOJO_TIMING viticulture::yield_tonnes_per_hectare", _ns_yield_tonnes_per_hectare, _acc_yield_tonnes_per_hectare)
    var _result_yield_tonnes_per_hectare = yield_tonnes_per_hectare(0.5, 0.5)
    var _summary_yield_tonnes_per_hectare = _summary_float64(_result_yield_tonnes_per_hectare)
    print("MOJO_RESULT viticulture::yield_tonnes_per_hectare", _summary_yield_tonnes_per_hectare)
    var _acc_vine_density: Float64 = 0.0
    var _t0_vine_density = perf_counter_ns()
    for _ in range(N):
        _acc_vine_density += vine_density(0.5, 0.5, 0.5)
    var _t1_vine_density = perf_counter_ns()
    var _ns_vine_density = Float64(_t1_vine_density - _t0_vine_density) / Float64(N)
    print("MOJO_TIMING viticulture::vine_density", _ns_vine_density, _acc_vine_density)
    var _result_vine_density = vine_density(0.5, 0.5, 0.5)
    var _summary_vine_density = _summary_float64(_result_vine_density)
    print("MOJO_RESULT viticulture::vine_density", _summary_vine_density)
    var _acc_pruning_weight_ratio: Float64 = 0.0
    var _t0_pruning_weight_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_pruning_weight_ratio += pruning_weight_ratio(0.5, 0.5)
    var _t1_pruning_weight_ratio = perf_counter_ns()
    var _ns_pruning_weight_ratio = Float64(_t1_pruning_weight_ratio - _t0_pruning_weight_ratio) / Float64(N)
    print("MOJO_TIMING viticulture::pruning_weight_ratio", _ns_pruning_weight_ratio, _acc_pruning_weight_ratio)
    var _result_pruning_weight_ratio = pruning_weight_ratio(0.5, 0.5)
    var _summary_pruning_weight_ratio = _summary_float64(_result_pruning_weight_ratio)
    print("MOJO_RESULT viticulture::pruning_weight_ratio", _summary_pruning_weight_ratio)
    var _acc_must_volume_from_grapes: Float64 = 0.0
    var _t0_must_volume_from_grapes = perf_counter_ns()
    for _ in range(N):
        _acc_must_volume_from_grapes += must_volume_from_grapes(0.5, 0.5)
    var _t1_must_volume_from_grapes = perf_counter_ns()
    var _ns_must_volume_from_grapes = Float64(_t1_must_volume_from_grapes - _t0_must_volume_from_grapes) / Float64(N)
    print("MOJO_TIMING viticulture::must_volume_from_grapes", _ns_must_volume_from_grapes, _acc_must_volume_from_grapes)
    var _result_must_volume_from_grapes = must_volume_from_grapes(0.5, 0.5)
    var _summary_must_volume_from_grapes = _summary_float64(_result_must_volume_from_grapes)
    print("MOJO_RESULT viticulture::must_volume_from_grapes", _summary_must_volume_from_grapes)
    var _acc_sulfite_molecular_so2: Float64 = 0.0
    var _t0_sulfite_molecular_so2 = perf_counter_ns()
    for _ in range(N):
        _acc_sulfite_molecular_so2 += sulfite_molecular_so2(0.5, 0.5)
    var _t1_sulfite_molecular_so2 = perf_counter_ns()
    var _ns_sulfite_molecular_so2 = Float64(_t1_sulfite_molecular_so2 - _t0_sulfite_molecular_so2) / Float64(N)
    print("MOJO_TIMING viticulture::sulfite_molecular_so2", _ns_sulfite_molecular_so2, _acc_sulfite_molecular_so2)
    var _result_sulfite_molecular_so2 = sulfite_molecular_so2(0.5, 0.5)
    var _summary_sulfite_molecular_so2 = _summary_float64(_result_sulfite_molecular_so2)
    print("MOJO_RESULT viticulture::sulfite_molecular_so2", _summary_sulfite_molecular_so2)
    var _acc_fermentation_progress: Float64 = 0.0
    var _t0_fermentation_progress = perf_counter_ns()
    for _ in range(N):
        _acc_fermentation_progress += fermentation_progress(0.5, 0.5)
    var _t1_fermentation_progress = perf_counter_ns()
    var _ns_fermentation_progress = Float64(_t1_fermentation_progress - _t0_fermentation_progress) / Float64(N)
    print("MOJO_TIMING viticulture::fermentation_progress", _ns_fermentation_progress, _acc_fermentation_progress)
    var _result_fermentation_progress = fermentation_progress(0.5, 0.5)
    var _summary_fermentation_progress = _summary_float64(_result_fermentation_progress)
    print("MOJO_RESULT viticulture::fermentation_progress", _summary_fermentation_progress)
