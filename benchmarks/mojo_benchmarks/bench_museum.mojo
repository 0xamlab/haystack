"""bench_museum.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from museum import lux_hours_annual, uv_exposure, relative_humidity_from_temps, moisture_content_equilibrium, time_weighted_preservation_index, light_damage_reciprocity, climate_stability_score, storage_density, collection_growth_rate, insurance_value_appreciation, visitor_density, conservation_priority_score
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

    var _acc_lux_hours_annual: Float64 = 0.0
    var _t0_lux_hours_annual = perf_counter_ns()
    for _ in range(N):
        _acc_lux_hours_annual += lux_hours_annual(0.5, 0.5, 0.5)
    var _t1_lux_hours_annual = perf_counter_ns()
    var _ns_lux_hours_annual = Float64(_t1_lux_hours_annual - _t0_lux_hours_annual) / Float64(N)
    print("MOJO_TIMING museum::lux_hours_annual", _ns_lux_hours_annual, _acc_lux_hours_annual)
    var _result_lux_hours_annual = lux_hours_annual(0.5, 0.5, 0.5)
    var _summary_lux_hours_annual = _summary_float64(_result_lux_hours_annual)
    print("MOJO_RESULT museum::lux_hours_annual", _summary_lux_hours_annual)
    var _acc_uv_exposure: Float64 = 0.0
    var _t0_uv_exposure = perf_counter_ns()
    for _ in range(N):
        _acc_uv_exposure += uv_exposure(0.5, 0.5)
    var _t1_uv_exposure = perf_counter_ns()
    var _ns_uv_exposure = Float64(_t1_uv_exposure - _t0_uv_exposure) / Float64(N)
    print("MOJO_TIMING museum::uv_exposure", _ns_uv_exposure, _acc_uv_exposure)
    var _result_uv_exposure = uv_exposure(0.5, 0.5)
    var _summary_uv_exposure = _summary_float64(_result_uv_exposure)
    print("MOJO_RESULT museum::uv_exposure", _summary_uv_exposure)
    var _acc_relative_humidity_from_temps: Float64 = 0.0
    var _t0_relative_humidity_from_temps = perf_counter_ns()
    for _ in range(N):
        _acc_relative_humidity_from_temps += relative_humidity_from_temps(0.5, 0.5)
    var _t1_relative_humidity_from_temps = perf_counter_ns()
    var _ns_relative_humidity_from_temps = Float64(_t1_relative_humidity_from_temps - _t0_relative_humidity_from_temps) / Float64(N)
    print("MOJO_TIMING museum::relative_humidity_from_temps", _ns_relative_humidity_from_temps, _acc_relative_humidity_from_temps)
    var _result_relative_humidity_from_temps = relative_humidity_from_temps(0.5, 0.5)
    var _summary_relative_humidity_from_temps = _summary_float64(_result_relative_humidity_from_temps)
    print("MOJO_RESULT museum::relative_humidity_from_temps", _summary_relative_humidity_from_temps)
    var _acc_moisture_content_equilibrium: Float64 = 0.0
    var _t0_moisture_content_equilibrium = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_equilibrium += moisture_content_equilibrium(0.5, 0.5)
    var _t1_moisture_content_equilibrium = perf_counter_ns()
    var _ns_moisture_content_equilibrium = Float64(_t1_moisture_content_equilibrium - _t0_moisture_content_equilibrium) / Float64(N)
    print("MOJO_TIMING museum::moisture_content_equilibrium", _ns_moisture_content_equilibrium, _acc_moisture_content_equilibrium)
    var _result_moisture_content_equilibrium = moisture_content_equilibrium(0.5, 0.5)
    var _summary_moisture_content_equilibrium = _summary_float64(_result_moisture_content_equilibrium)
    print("MOJO_RESULT museum::moisture_content_equilibrium", _summary_moisture_content_equilibrium)
    var _acc_time_weighted_preservation_index: Float64 = 0.0
    var _t0_time_weighted_preservation_index = perf_counter_ns()
    for _ in range(N):
        _acc_time_weighted_preservation_index += time_weighted_preservation_index(0.5, 0.5, 0.5)
    var _t1_time_weighted_preservation_index = perf_counter_ns()
    var _ns_time_weighted_preservation_index = Float64(_t1_time_weighted_preservation_index - _t0_time_weighted_preservation_index) / Float64(N)
    print("MOJO_TIMING museum::time_weighted_preservation_index", _ns_time_weighted_preservation_index, _acc_time_weighted_preservation_index)
    var _result_time_weighted_preservation_index = time_weighted_preservation_index(0.5, 0.5, 0.5)
    var _summary_time_weighted_preservation_index = _summary_float64(_result_time_weighted_preservation_index)
    print("MOJO_RESULT museum::time_weighted_preservation_index", _summary_time_weighted_preservation_index)
    var _acc_light_damage_reciprocity: Float64 = 0.0
    var _t0_light_damage_reciprocity = perf_counter_ns()
    for _ in range(N):
        _acc_light_damage_reciprocity += light_damage_reciprocity(0.5, 0.5)
    var _t1_light_damage_reciprocity = perf_counter_ns()
    var _ns_light_damage_reciprocity = Float64(_t1_light_damage_reciprocity - _t0_light_damage_reciprocity) / Float64(N)
    print("MOJO_TIMING museum::light_damage_reciprocity", _ns_light_damage_reciprocity, _acc_light_damage_reciprocity)
    var _result_light_damage_reciprocity = light_damage_reciprocity(0.5, 0.5)
    var _summary_light_damage_reciprocity = _summary_float64(_result_light_damage_reciprocity)
    print("MOJO_RESULT museum::light_damage_reciprocity", _summary_light_damage_reciprocity)
    var _acc_climate_stability_score: Float64 = 0.0
    var _t0_climate_stability_score = perf_counter_ns()
    for _ in range(N):
        _acc_climate_stability_score += climate_stability_score(0.5, 0.5)
    var _t1_climate_stability_score = perf_counter_ns()
    var _ns_climate_stability_score = Float64(_t1_climate_stability_score - _t0_climate_stability_score) / Float64(N)
    print("MOJO_TIMING museum::climate_stability_score", _ns_climate_stability_score, _acc_climate_stability_score)
    var _result_climate_stability_score = climate_stability_score(0.5, 0.5)
    var _summary_climate_stability_score = _summary_float64(_result_climate_stability_score)
    print("MOJO_RESULT museum::climate_stability_score", _summary_climate_stability_score)
    var _acc_storage_density: Float64 = 0.0
    var _t0_storage_density = perf_counter_ns()
    for _ in range(N):
        _acc_storage_density += storage_density(0.5, 0.5)
    var _t1_storage_density = perf_counter_ns()
    var _ns_storage_density = Float64(_t1_storage_density - _t0_storage_density) / Float64(N)
    print("MOJO_TIMING museum::storage_density", _ns_storage_density, _acc_storage_density)
    var _result_storage_density = storage_density(0.5, 0.5)
    var _summary_storage_density = _summary_float64(_result_storage_density)
    print("MOJO_RESULT museum::storage_density", _summary_storage_density)
    var _acc_collection_growth_rate: Float64 = 0.0
    var _t0_collection_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_collection_growth_rate += collection_growth_rate(0.5, 0.5, 0.5)
    var _t1_collection_growth_rate = perf_counter_ns()
    var _ns_collection_growth_rate = Float64(_t1_collection_growth_rate - _t0_collection_growth_rate) / Float64(N)
    print("MOJO_TIMING museum::collection_growth_rate", _ns_collection_growth_rate, _acc_collection_growth_rate)
    var _result_collection_growth_rate = collection_growth_rate(0.5, 0.5, 0.5)
    var _summary_collection_growth_rate = _summary_float64(_result_collection_growth_rate)
    print("MOJO_RESULT museum::collection_growth_rate", _summary_collection_growth_rate)
    var _acc_insurance_value_appreciation: Float64 = 0.0
    var _t0_insurance_value_appreciation = perf_counter_ns()
    for _ in range(N):
        _acc_insurance_value_appreciation += insurance_value_appreciation(0.5, 0.5, 0.5)
    var _t1_insurance_value_appreciation = perf_counter_ns()
    var _ns_insurance_value_appreciation = Float64(_t1_insurance_value_appreciation - _t0_insurance_value_appreciation) / Float64(N)
    print("MOJO_TIMING museum::insurance_value_appreciation", _ns_insurance_value_appreciation, _acc_insurance_value_appreciation)
    var _result_insurance_value_appreciation = insurance_value_appreciation(0.5, 0.5, 0.5)
    var _summary_insurance_value_appreciation = _summary_float64(_result_insurance_value_appreciation)
    print("MOJO_RESULT museum::insurance_value_appreciation", _summary_insurance_value_appreciation)
    var _acc_visitor_density: Float64 = 0.0
    var _t0_visitor_density = perf_counter_ns()
    for _ in range(N):
        _acc_visitor_density += visitor_density(0.5, 0.5)
    var _t1_visitor_density = perf_counter_ns()
    var _ns_visitor_density = Float64(_t1_visitor_density - _t0_visitor_density) / Float64(N)
    print("MOJO_TIMING museum::visitor_density", _ns_visitor_density, _acc_visitor_density)
    var _result_visitor_density = visitor_density(0.5, 0.5)
    var _summary_visitor_density = _summary_float64(_result_visitor_density)
    print("MOJO_RESULT museum::visitor_density", _summary_visitor_density)
    var _acc_conservation_priority_score: Float64 = 0.0
    var _t0_conservation_priority_score = perf_counter_ns()
    for _ in range(N):
        _acc_conservation_priority_score += conservation_priority_score(0.5, 0.5, 0.5)
    var _t1_conservation_priority_score = perf_counter_ns()
    var _ns_conservation_priority_score = Float64(_t1_conservation_priority_score - _t0_conservation_priority_score) / Float64(N)
    print("MOJO_TIMING museum::conservation_priority_score", _ns_conservation_priority_score, _acc_conservation_priority_score)
    var _result_conservation_priority_score = conservation_priority_score(0.5, 0.5, 0.5)
    var _summary_conservation_priority_score = _summary_float64(_result_conservation_priority_score)
    print("MOJO_RESULT museum::conservation_priority_score", _summary_conservation_priority_score)
