"""bench_agronomy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from agronomy import crop_yield_potential, nitrogen_uptake_efficiency, soil_organic_matter_decay, evapotranspiration_penman, leaf_area_index, light_use_efficiency, crop_water_stress_index, irrigation_requirement, soil_cation_exchange, growing_degree_days
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

    var _acc_crop_yield_potential: Float64 = 0.0
    var _t0_crop_yield_potential = perf_counter_ns()
    for _ in range(N):
        _acc_crop_yield_potential += crop_yield_potential(0.5, 0.5, 0.5)
    var _t1_crop_yield_potential = perf_counter_ns()
    var _ns_crop_yield_potential = Float64(_t1_crop_yield_potential - _t0_crop_yield_potential) / Float64(N)
    print("MOJO_TIMING agronomy::crop_yield_potential", _ns_crop_yield_potential, _acc_crop_yield_potential)
    var _result_crop_yield_potential = crop_yield_potential(0.5, 0.5, 0.5)
    var _summary_crop_yield_potential = _summary_float64(_result_crop_yield_potential)
    print("MOJO_RESULT agronomy::crop_yield_potential", _summary_crop_yield_potential)
    var _acc_nitrogen_uptake_efficiency: Float64 = 0.0
    var _t0_nitrogen_uptake_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_uptake_efficiency += nitrogen_uptake_efficiency(0.5, 0.5)
    var _t1_nitrogen_uptake_efficiency = perf_counter_ns()
    var _ns_nitrogen_uptake_efficiency = Float64(_t1_nitrogen_uptake_efficiency - _t0_nitrogen_uptake_efficiency) / Float64(N)
    print("MOJO_TIMING agronomy::nitrogen_uptake_efficiency", _ns_nitrogen_uptake_efficiency, _acc_nitrogen_uptake_efficiency)
    var _result_nitrogen_uptake_efficiency = nitrogen_uptake_efficiency(0.5, 0.5)
    var _summary_nitrogen_uptake_efficiency = _summary_float64(_result_nitrogen_uptake_efficiency)
    print("MOJO_RESULT agronomy::nitrogen_uptake_efficiency", _summary_nitrogen_uptake_efficiency)
    var _acc_soil_organic_matter_decay: Float64 = 0.0
    var _t0_soil_organic_matter_decay = perf_counter_ns()
    for _ in range(N):
        _acc_soil_organic_matter_decay += soil_organic_matter_decay(0.5, 0.5, 0.5)
    var _t1_soil_organic_matter_decay = perf_counter_ns()
    var _ns_soil_organic_matter_decay = Float64(_t1_soil_organic_matter_decay - _t0_soil_organic_matter_decay) / Float64(N)
    print("MOJO_TIMING agronomy::soil_organic_matter_decay", _ns_soil_organic_matter_decay, _acc_soil_organic_matter_decay)
    var _result_soil_organic_matter_decay = soil_organic_matter_decay(0.5, 0.5, 0.5)
    var _summary_soil_organic_matter_decay = _summary_float64(_result_soil_organic_matter_decay)
    print("MOJO_RESULT agronomy::soil_organic_matter_decay", _summary_soil_organic_matter_decay)
    var _acc_evapotranspiration_penman: Float64 = 0.0
    var _t0_evapotranspiration_penman = perf_counter_ns()
    for _ in range(N):
        _acc_evapotranspiration_penman += evapotranspiration_penman(0.5, 0.5, 0.5, 0.5)
    var _t1_evapotranspiration_penman = perf_counter_ns()
    var _ns_evapotranspiration_penman = Float64(_t1_evapotranspiration_penman - _t0_evapotranspiration_penman) / Float64(N)
    print("MOJO_TIMING agronomy::evapotranspiration_penman", _ns_evapotranspiration_penman, _acc_evapotranspiration_penman)
    var _result_evapotranspiration_penman = evapotranspiration_penman(0.5, 0.5, 0.5, 0.5)
    var _summary_evapotranspiration_penman = _summary_float64(_result_evapotranspiration_penman)
    print("MOJO_RESULT agronomy::evapotranspiration_penman", _summary_evapotranspiration_penman)
    var _acc_leaf_area_index: Float64 = 0.0
    var _t0_leaf_area_index = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_area_index += leaf_area_index(0.5, 0.5)
    var _t1_leaf_area_index = perf_counter_ns()
    var _ns_leaf_area_index = Float64(_t1_leaf_area_index - _t0_leaf_area_index) / Float64(N)
    print("MOJO_TIMING agronomy::leaf_area_index", _ns_leaf_area_index, _acc_leaf_area_index)
    var _result_leaf_area_index = leaf_area_index(0.5, 0.5)
    var _summary_leaf_area_index = _summary_float64(_result_leaf_area_index)
    print("MOJO_RESULT agronomy::leaf_area_index", _summary_leaf_area_index)
    var _acc_light_use_efficiency: Float64 = 0.0
    var _t0_light_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_light_use_efficiency += light_use_efficiency(0.5, 0.5)
    var _t1_light_use_efficiency = perf_counter_ns()
    var _ns_light_use_efficiency = Float64(_t1_light_use_efficiency - _t0_light_use_efficiency) / Float64(N)
    print("MOJO_TIMING agronomy::light_use_efficiency", _ns_light_use_efficiency, _acc_light_use_efficiency)
    var _result_light_use_efficiency = light_use_efficiency(0.5, 0.5)
    var _summary_light_use_efficiency = _summary_float64(_result_light_use_efficiency)
    print("MOJO_RESULT agronomy::light_use_efficiency", _summary_light_use_efficiency)
    var _acc_crop_water_stress_index: Float64 = 0.0
    var _t0_crop_water_stress_index = perf_counter_ns()
    for _ in range(N):
        _acc_crop_water_stress_index += crop_water_stress_index(0.5, 0.5, 0.5)
    var _t1_crop_water_stress_index = perf_counter_ns()
    var _ns_crop_water_stress_index = Float64(_t1_crop_water_stress_index - _t0_crop_water_stress_index) / Float64(N)
    print("MOJO_TIMING agronomy::crop_water_stress_index", _ns_crop_water_stress_index, _acc_crop_water_stress_index)
    var _result_crop_water_stress_index = crop_water_stress_index(0.5, 0.5, 0.5)
    var _summary_crop_water_stress_index = _summary_float64(_result_crop_water_stress_index)
    print("MOJO_RESULT agronomy::crop_water_stress_index", _summary_crop_water_stress_index)
    var _acc_irrigation_requirement: Float64 = 0.0
    var _t0_irrigation_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_irrigation_requirement += irrigation_requirement(0.5, 0.5, 0.5)
    var _t1_irrigation_requirement = perf_counter_ns()
    var _ns_irrigation_requirement = Float64(_t1_irrigation_requirement - _t0_irrigation_requirement) / Float64(N)
    print("MOJO_TIMING agronomy::irrigation_requirement", _ns_irrigation_requirement, _acc_irrigation_requirement)
    var _result_irrigation_requirement = irrigation_requirement(0.5, 0.5, 0.5)
    var _summary_irrigation_requirement = _summary_float64(_result_irrigation_requirement)
    print("MOJO_RESULT agronomy::irrigation_requirement", _summary_irrigation_requirement)
    var _acc_soil_cation_exchange: Float64 = 0.0
    var _t0_soil_cation_exchange = perf_counter_ns()
    for _ in range(N):
        _acc_soil_cation_exchange += soil_cation_exchange(0.5, 0.5)
    var _t1_soil_cation_exchange = perf_counter_ns()
    var _ns_soil_cation_exchange = Float64(_t1_soil_cation_exchange - _t0_soil_cation_exchange) / Float64(N)
    print("MOJO_TIMING agronomy::soil_cation_exchange", _ns_soil_cation_exchange, _acc_soil_cation_exchange)
    var _result_soil_cation_exchange = soil_cation_exchange(0.5, 0.5)
    var _summary_soil_cation_exchange = _summary_float64(_result_soil_cation_exchange)
    print("MOJO_RESULT agronomy::soil_cation_exchange", _summary_soil_cation_exchange)
    var _acc_growing_degree_days: Float64 = 0.0
    var _t0_growing_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_growing_degree_days += growing_degree_days(0.5, 0.5, 0.5)
    var _t1_growing_degree_days = perf_counter_ns()
    var _ns_growing_degree_days = Float64(_t1_growing_degree_days - _t0_growing_degree_days) / Float64(N)
    print("MOJO_TIMING agronomy::growing_degree_days", _ns_growing_degree_days, _acc_growing_degree_days)
    var _result_growing_degree_days = growing_degree_days(0.5, 0.5, 0.5)
    var _summary_growing_degree_days = _summary_float64(_result_growing_degree_days)
    print("MOJO_RESULT agronomy::growing_degree_days", _summary_growing_degree_days)
