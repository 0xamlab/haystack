"""bench_hydrometeorology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydrometeorology import runoff_curve_number, rational_method_peak_flow, time_of_concentration, green_ampt_infiltration, palmer_drought_index, actual_evapotranspiration, snow_water_equivalent, rain_intensity_from_depth, antecedent_moisture_condition, flood_frequency_factor
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

    var _acc_runoff_curve_number: Float64 = 0.0
    var _t0_runoff_curve_number = perf_counter_ns()
    for _ in range(N):
        _acc_runoff_curve_number += runoff_curve_number(0.5, 0.5)
    var _t1_runoff_curve_number = perf_counter_ns()
    var _ns_runoff_curve_number = Float64(_t1_runoff_curve_number - _t0_runoff_curve_number) / Float64(N)
    print("MOJO_TIMING hydrometeorology::runoff_curve_number", _ns_runoff_curve_number, _acc_runoff_curve_number)
    var _result_runoff_curve_number = runoff_curve_number(0.5, 0.5)
    var _summary_runoff_curve_number = _summary_float64(_result_runoff_curve_number)
    print("MOJO_RESULT hydrometeorology::runoff_curve_number", _summary_runoff_curve_number)
    var _acc_rational_method_peak_flow: Float64 = 0.0
    var _t0_rational_method_peak_flow = perf_counter_ns()
    for _ in range(N):
        _acc_rational_method_peak_flow += rational_method_peak_flow(0.5, 0.5, 0.5)
    var _t1_rational_method_peak_flow = perf_counter_ns()
    var _ns_rational_method_peak_flow = Float64(_t1_rational_method_peak_flow - _t0_rational_method_peak_flow) / Float64(N)
    print("MOJO_TIMING hydrometeorology::rational_method_peak_flow", _ns_rational_method_peak_flow, _acc_rational_method_peak_flow)
    var _result_rational_method_peak_flow = rational_method_peak_flow(0.5, 0.5, 0.5)
    var _summary_rational_method_peak_flow = _summary_float64(_result_rational_method_peak_flow)
    print("MOJO_RESULT hydrometeorology::rational_method_peak_flow", _summary_rational_method_peak_flow)
    var _acc_time_of_concentration: Float64 = 0.0
    var _t0_time_of_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_time_of_concentration += time_of_concentration(0.5, 0.5)
    var _t1_time_of_concentration = perf_counter_ns()
    var _ns_time_of_concentration = Float64(_t1_time_of_concentration - _t0_time_of_concentration) / Float64(N)
    print("MOJO_TIMING hydrometeorology::time_of_concentration", _ns_time_of_concentration, _acc_time_of_concentration)
    var _result_time_of_concentration = time_of_concentration(0.5, 0.5)
    var _summary_time_of_concentration = _summary_float64(_result_time_of_concentration)
    print("MOJO_RESULT hydrometeorology::time_of_concentration", _summary_time_of_concentration)
    var _acc_green_ampt_infiltration: Float64 = 0.0
    var _t0_green_ampt_infiltration = perf_counter_ns()
    for _ in range(N):
        _acc_green_ampt_infiltration += green_ampt_infiltration(0.5, 0.5, 0.5, 0.5)
    var _t1_green_ampt_infiltration = perf_counter_ns()
    var _ns_green_ampt_infiltration = Float64(_t1_green_ampt_infiltration - _t0_green_ampt_infiltration) / Float64(N)
    print("MOJO_TIMING hydrometeorology::green_ampt_infiltration", _ns_green_ampt_infiltration, _acc_green_ampt_infiltration)
    var _result_green_ampt_infiltration = green_ampt_infiltration(0.5, 0.5, 0.5, 0.5)
    var _summary_green_ampt_infiltration = _summary_float64(_result_green_ampt_infiltration)
    print("MOJO_RESULT hydrometeorology::green_ampt_infiltration", _summary_green_ampt_infiltration)
    var _acc_palmer_drought_index: Float64 = 0.0
    var _t0_palmer_drought_index = perf_counter_ns()
    for _ in range(N):
        _acc_palmer_drought_index += palmer_drought_index(0.5, 0.5, 0.5)
    var _t1_palmer_drought_index = perf_counter_ns()
    var _ns_palmer_drought_index = Float64(_t1_palmer_drought_index - _t0_palmer_drought_index) / Float64(N)
    print("MOJO_TIMING hydrometeorology::palmer_drought_index", _ns_palmer_drought_index, _acc_palmer_drought_index)
    var _result_palmer_drought_index = palmer_drought_index(0.5, 0.5, 0.5)
    var _summary_palmer_drought_index = _summary_float64(_result_palmer_drought_index)
    print("MOJO_RESULT hydrometeorology::palmer_drought_index", _summary_palmer_drought_index)
    var _acc_actual_evapotranspiration: Float64 = 0.0
    var _t0_actual_evapotranspiration = perf_counter_ns()
    for _ in range(N):
        _acc_actual_evapotranspiration += actual_evapotranspiration(0.5, 0.5)
    var _t1_actual_evapotranspiration = perf_counter_ns()
    var _ns_actual_evapotranspiration = Float64(_t1_actual_evapotranspiration - _t0_actual_evapotranspiration) / Float64(N)
    print("MOJO_TIMING hydrometeorology::actual_evapotranspiration", _ns_actual_evapotranspiration, _acc_actual_evapotranspiration)
    var _result_actual_evapotranspiration = actual_evapotranspiration(0.5, 0.5)
    var _summary_actual_evapotranspiration = _summary_float64(_result_actual_evapotranspiration)
    print("MOJO_RESULT hydrometeorology::actual_evapotranspiration", _summary_actual_evapotranspiration)
    var _acc_snow_water_equivalent: Float64 = 0.0
    var _t0_snow_water_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_snow_water_equivalent += snow_water_equivalent(0.5, 0.5)
    var _t1_snow_water_equivalent = perf_counter_ns()
    var _ns_snow_water_equivalent = Float64(_t1_snow_water_equivalent - _t0_snow_water_equivalent) / Float64(N)
    print("MOJO_TIMING hydrometeorology::snow_water_equivalent", _ns_snow_water_equivalent, _acc_snow_water_equivalent)
    var _result_snow_water_equivalent = snow_water_equivalent(0.5, 0.5)
    var _summary_snow_water_equivalent = _summary_float64(_result_snow_water_equivalent)
    print("MOJO_RESULT hydrometeorology::snow_water_equivalent", _summary_snow_water_equivalent)
    var _acc_rain_intensity_from_depth: Float64 = 0.0
    var _t0_rain_intensity_from_depth = perf_counter_ns()
    for _ in range(N):
        _acc_rain_intensity_from_depth += rain_intensity_from_depth(0.5, 0.5)
    var _t1_rain_intensity_from_depth = perf_counter_ns()
    var _ns_rain_intensity_from_depth = Float64(_t1_rain_intensity_from_depth - _t0_rain_intensity_from_depth) / Float64(N)
    print("MOJO_TIMING hydrometeorology::rain_intensity_from_depth", _ns_rain_intensity_from_depth, _acc_rain_intensity_from_depth)
    var _result_rain_intensity_from_depth = rain_intensity_from_depth(0.5, 0.5)
    var _summary_rain_intensity_from_depth = _summary_float64(_result_rain_intensity_from_depth)
    print("MOJO_RESULT hydrometeorology::rain_intensity_from_depth", _summary_rain_intensity_from_depth)
    var _acc_antecedent_moisture_condition: Float64 = 0.0
    var _t0_antecedent_moisture_condition = perf_counter_ns()
    for _ in range(N):
        _acc_antecedent_moisture_condition += antecedent_moisture_condition(0.5, 0.5)
    var _t1_antecedent_moisture_condition = perf_counter_ns()
    var _ns_antecedent_moisture_condition = Float64(_t1_antecedent_moisture_condition - _t0_antecedent_moisture_condition) / Float64(N)
    print("MOJO_TIMING hydrometeorology::antecedent_moisture_condition", _ns_antecedent_moisture_condition, _acc_antecedent_moisture_condition)
    var _result_antecedent_moisture_condition = antecedent_moisture_condition(0.5, 0.5)
    var _summary_antecedent_moisture_condition = _summary_float64(_result_antecedent_moisture_condition)
    print("MOJO_RESULT hydrometeorology::antecedent_moisture_condition", _summary_antecedent_moisture_condition)
    var _acc_flood_frequency_factor: Float64 = 0.0
    var _t0_flood_frequency_factor = perf_counter_ns()
    for _ in range(N):
        _acc_flood_frequency_factor += flood_frequency_factor(0.5)
    var _t1_flood_frequency_factor = perf_counter_ns()
    var _ns_flood_frequency_factor = Float64(_t1_flood_frequency_factor - _t0_flood_frequency_factor) / Float64(N)
    print("MOJO_TIMING hydrometeorology::flood_frequency_factor", _ns_flood_frequency_factor, _acc_flood_frequency_factor)
    var _result_flood_frequency_factor = flood_frequency_factor(0.5)
    var _summary_flood_frequency_factor = _summary_float64(_result_flood_frequency_factor)
    print("MOJO_RESULT hydrometeorology::flood_frequency_factor", _summary_flood_frequency_factor)
