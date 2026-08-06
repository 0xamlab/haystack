"""bench_agriculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from agriculture import growing_degree_days, crop_water_need, irrigation_efficiency, fertilizer_rate, seed_rate, harvest_index, yield_per_hectare, soil_ph_lime_requirement, water_use_efficiency, photosynthetically_active_radiation, leaf_area_index, nitrogen_use_efficiency
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

    var _acc_growing_degree_days: Float64 = 0.0
    var _t0_growing_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_growing_degree_days += growing_degree_days(0.5, 0.5, 0.5)
    var _t1_growing_degree_days = perf_counter_ns()
    var _ns_growing_degree_days = Float64(_t1_growing_degree_days - _t0_growing_degree_days) / Float64(N)
    print("MOJO_TIMING agriculture::growing_degree_days", _ns_growing_degree_days, _acc_growing_degree_days)
    var _result_growing_degree_days = growing_degree_days(0.5, 0.5, 0.5)
    var _summary_growing_degree_days = _summary_float64(_result_growing_degree_days)
    print("MOJO_RESULT agriculture::growing_degree_days", _summary_growing_degree_days)
    var _acc_crop_water_need: Float64 = 0.0
    var _t0_crop_water_need = perf_counter_ns()
    for _ in range(N):
        _acc_crop_water_need += crop_water_need(0.5, 0.5)
    var _t1_crop_water_need = perf_counter_ns()
    var _ns_crop_water_need = Float64(_t1_crop_water_need - _t0_crop_water_need) / Float64(N)
    print("MOJO_TIMING agriculture::crop_water_need", _ns_crop_water_need, _acc_crop_water_need)
    var _result_crop_water_need = crop_water_need(0.5, 0.5)
    var _summary_crop_water_need = _summary_float64(_result_crop_water_need)
    print("MOJO_RESULT agriculture::crop_water_need", _summary_crop_water_need)
    var _acc_irrigation_efficiency: Float64 = 0.0
    var _t0_irrigation_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_irrigation_efficiency += irrigation_efficiency(0.5, 0.5)
    var _t1_irrigation_efficiency = perf_counter_ns()
    var _ns_irrigation_efficiency = Float64(_t1_irrigation_efficiency - _t0_irrigation_efficiency) / Float64(N)
    print("MOJO_TIMING agriculture::irrigation_efficiency", _ns_irrigation_efficiency, _acc_irrigation_efficiency)
    var _result_irrigation_efficiency = irrigation_efficiency(0.5, 0.5)
    var _summary_irrigation_efficiency = _summary_float64(_result_irrigation_efficiency)
    print("MOJO_RESULT agriculture::irrigation_efficiency", _summary_irrigation_efficiency)
    var _acc_fertilizer_rate: Float64 = 0.0
    var _t0_fertilizer_rate = perf_counter_ns()
    for _ in range(N):
        _acc_fertilizer_rate += fertilizer_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_fertilizer_rate = perf_counter_ns()
    var _ns_fertilizer_rate = Float64(_t1_fertilizer_rate - _t0_fertilizer_rate) / Float64(N)
    print("MOJO_TIMING agriculture::fertilizer_rate", _ns_fertilizer_rate, _acc_fertilizer_rate)
    var _result_fertilizer_rate = fertilizer_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_fertilizer_rate = _summary_float64(_result_fertilizer_rate)
    print("MOJO_RESULT agriculture::fertilizer_rate", _summary_fertilizer_rate)
    var _acc_seed_rate: Float64 = 0.0
    var _t0_seed_rate = perf_counter_ns()
    for _ in range(N):
        _acc_seed_rate += seed_rate(0.5, 0.5, 0.5)
    var _t1_seed_rate = perf_counter_ns()
    var _ns_seed_rate = Float64(_t1_seed_rate - _t0_seed_rate) / Float64(N)
    print("MOJO_TIMING agriculture::seed_rate", _ns_seed_rate, _acc_seed_rate)
    var _result_seed_rate = seed_rate(0.5, 0.5, 0.5)
    var _summary_seed_rate = _summary_float64(_result_seed_rate)
    print("MOJO_RESULT agriculture::seed_rate", _summary_seed_rate)
    var _acc_harvest_index: Float64 = 0.0
    var _t0_harvest_index = perf_counter_ns()
    for _ in range(N):
        _acc_harvest_index += harvest_index(0.5, 0.5)
    var _t1_harvest_index = perf_counter_ns()
    var _ns_harvest_index = Float64(_t1_harvest_index - _t0_harvest_index) / Float64(N)
    print("MOJO_TIMING agriculture::harvest_index", _ns_harvest_index, _acc_harvest_index)
    var _result_harvest_index = harvest_index(0.5, 0.5)
    var _summary_harvest_index = _summary_float64(_result_harvest_index)
    print("MOJO_RESULT agriculture::harvest_index", _summary_harvest_index)
    var _acc_yield_per_hectare: Float64 = 0.0
    var _t0_yield_per_hectare = perf_counter_ns()
    for _ in range(N):
        _acc_yield_per_hectare += yield_per_hectare(0.5, 0.5)
    var _t1_yield_per_hectare = perf_counter_ns()
    var _ns_yield_per_hectare = Float64(_t1_yield_per_hectare - _t0_yield_per_hectare) / Float64(N)
    print("MOJO_TIMING agriculture::yield_per_hectare", _ns_yield_per_hectare, _acc_yield_per_hectare)
    var _result_yield_per_hectare = yield_per_hectare(0.5, 0.5)
    var _summary_yield_per_hectare = _summary_float64(_result_yield_per_hectare)
    print("MOJO_RESULT agriculture::yield_per_hectare", _summary_yield_per_hectare)
    var _acc_soil_ph_lime_requirement: Float64 = 0.0
    var _t0_soil_ph_lime_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_soil_ph_lime_requirement += soil_ph_lime_requirement(0.5, 0.5, 0.5)
    var _t1_soil_ph_lime_requirement = perf_counter_ns()
    var _ns_soil_ph_lime_requirement = Float64(_t1_soil_ph_lime_requirement - _t0_soil_ph_lime_requirement) / Float64(N)
    print("MOJO_TIMING agriculture::soil_ph_lime_requirement", _ns_soil_ph_lime_requirement, _acc_soil_ph_lime_requirement)
    var _result_soil_ph_lime_requirement = soil_ph_lime_requirement(0.5, 0.5, 0.5)
    var _summary_soil_ph_lime_requirement = _summary_float64(_result_soil_ph_lime_requirement)
    print("MOJO_RESULT agriculture::soil_ph_lime_requirement", _summary_soil_ph_lime_requirement)
    var _acc_water_use_efficiency: Float64 = 0.0
    var _t0_water_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_water_use_efficiency += water_use_efficiency(0.5, 0.5)
    var _t1_water_use_efficiency = perf_counter_ns()
    var _ns_water_use_efficiency = Float64(_t1_water_use_efficiency - _t0_water_use_efficiency) / Float64(N)
    print("MOJO_TIMING agriculture::water_use_efficiency", _ns_water_use_efficiency, _acc_water_use_efficiency)
    var _result_water_use_efficiency = water_use_efficiency(0.5, 0.5)
    var _summary_water_use_efficiency = _summary_float64(_result_water_use_efficiency)
    print("MOJO_RESULT agriculture::water_use_efficiency", _summary_water_use_efficiency)
    var _acc_photosynthetically_active_radiation: Float64 = 0.0
    var _t0_photosynthetically_active_radiation = perf_counter_ns()
    for _ in range(N):
        _acc_photosynthetically_active_radiation += photosynthetically_active_radiation(0.5)
    var _t1_photosynthetically_active_radiation = perf_counter_ns()
    var _ns_photosynthetically_active_radiation = Float64(_t1_photosynthetically_active_radiation - _t0_photosynthetically_active_radiation) / Float64(N)
    print("MOJO_TIMING agriculture::photosynthetically_active_radiation", _ns_photosynthetically_active_radiation, _acc_photosynthetically_active_radiation)
    var _result_photosynthetically_active_radiation = photosynthetically_active_radiation(0.5)
    var _summary_photosynthetically_active_radiation = _summary_float64(_result_photosynthetically_active_radiation)
    print("MOJO_RESULT agriculture::photosynthetically_active_radiation", _summary_photosynthetically_active_radiation)
    var _acc_leaf_area_index: Float64 = 0.0
    var _t0_leaf_area_index = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_area_index += leaf_area_index(0.5, 0.5)
    var _t1_leaf_area_index = perf_counter_ns()
    var _ns_leaf_area_index = Float64(_t1_leaf_area_index - _t0_leaf_area_index) / Float64(N)
    print("MOJO_TIMING agriculture::leaf_area_index", _ns_leaf_area_index, _acc_leaf_area_index)
    var _result_leaf_area_index = leaf_area_index(0.5, 0.5)
    var _summary_leaf_area_index = _summary_float64(_result_leaf_area_index)
    print("MOJO_RESULT agriculture::leaf_area_index", _summary_leaf_area_index)
    var _acc_nitrogen_use_efficiency: Float64 = 0.0
    var _t0_nitrogen_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_use_efficiency += nitrogen_use_efficiency(0.5, 0.5)
    var _t1_nitrogen_use_efficiency = perf_counter_ns()
    var _ns_nitrogen_use_efficiency = Float64(_t1_nitrogen_use_efficiency - _t0_nitrogen_use_efficiency) / Float64(N)
    print("MOJO_TIMING agriculture::nitrogen_use_efficiency", _ns_nitrogen_use_efficiency, _acc_nitrogen_use_efficiency)
    var _result_nitrogen_use_efficiency = nitrogen_use_efficiency(0.5, 0.5)
    var _summary_nitrogen_use_efficiency = _summary_float64(_result_nitrogen_use_efficiency)
    print("MOJO_RESULT agriculture::nitrogen_use_efficiency", _summary_nitrogen_use_efficiency)
