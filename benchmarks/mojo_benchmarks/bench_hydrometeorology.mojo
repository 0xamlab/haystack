"""bench_hydrometeorology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydrometeorology import runoff_curve_number, rational_method_peak_flow, time_of_concentration, green_ampt_infiltration, palmer_drought_index, actual_evapotranspiration, snow_water_equivalent, rain_intensity_from_depth, antecedent_moisture_condition, flood_frequency_factor
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

    var _acc_runoff_curve_number: Float64 = 0.0
    var _t0_runoff_curve_number = perf_counter_ns()
    for _ in range(N):
        _acc_runoff_curve_number += runoff_curve_number(0.5, 0.5)
    var _t1_runoff_curve_number = perf_counter_ns()
    var _ns_runoff_curve_number = Float64(_t1_runoff_curve_number - _t0_runoff_curve_number) / Float64(N)
    print("MOJO_TIMING hydrometeorology::runoff_curve_number", _ns_runoff_curve_number, _acc_runoff_curve_number)
    var _acc_rational_method_peak_flow: Float64 = 0.0
    var _t0_rational_method_peak_flow = perf_counter_ns()
    for _ in range(N):
        _acc_rational_method_peak_flow += rational_method_peak_flow(0.5, 0.5, 0.5)
    var _t1_rational_method_peak_flow = perf_counter_ns()
    var _ns_rational_method_peak_flow = Float64(_t1_rational_method_peak_flow - _t0_rational_method_peak_flow) / Float64(N)
    print("MOJO_TIMING hydrometeorology::rational_method_peak_flow", _ns_rational_method_peak_flow, _acc_rational_method_peak_flow)
    var _acc_time_of_concentration: Float64 = 0.0
    var _t0_time_of_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_time_of_concentration += time_of_concentration(0.5, 0.5)
    var _t1_time_of_concentration = perf_counter_ns()
    var _ns_time_of_concentration = Float64(_t1_time_of_concentration - _t0_time_of_concentration) / Float64(N)
    print("MOJO_TIMING hydrometeorology::time_of_concentration", _ns_time_of_concentration, _acc_time_of_concentration)
    var _acc_green_ampt_infiltration: Float64 = 0.0
    var _t0_green_ampt_infiltration = perf_counter_ns()
    for _ in range(N):
        _acc_green_ampt_infiltration += green_ampt_infiltration(0.5, 0.5, 0.5, 0.5)
    var _t1_green_ampt_infiltration = perf_counter_ns()
    var _ns_green_ampt_infiltration = Float64(_t1_green_ampt_infiltration - _t0_green_ampt_infiltration) / Float64(N)
    print("MOJO_TIMING hydrometeorology::green_ampt_infiltration", _ns_green_ampt_infiltration, _acc_green_ampt_infiltration)
    var _acc_palmer_drought_index: Float64 = 0.0
    var _t0_palmer_drought_index = perf_counter_ns()
    for _ in range(N):
        _acc_palmer_drought_index += palmer_drought_index(0.5, 0.5, 0.5)
    var _t1_palmer_drought_index = perf_counter_ns()
    var _ns_palmer_drought_index = Float64(_t1_palmer_drought_index - _t0_palmer_drought_index) / Float64(N)
    print("MOJO_TIMING hydrometeorology::palmer_drought_index", _ns_palmer_drought_index, _acc_palmer_drought_index)
    var _acc_actual_evapotranspiration: Float64 = 0.0
    var _t0_actual_evapotranspiration = perf_counter_ns()
    for _ in range(N):
        _acc_actual_evapotranspiration += actual_evapotranspiration(0.5, 0.5)
    var _t1_actual_evapotranspiration = perf_counter_ns()
    var _ns_actual_evapotranspiration = Float64(_t1_actual_evapotranspiration - _t0_actual_evapotranspiration) / Float64(N)
    print("MOJO_TIMING hydrometeorology::actual_evapotranspiration", _ns_actual_evapotranspiration, _acc_actual_evapotranspiration)
    var _acc_snow_water_equivalent: Float64 = 0.0
    var _t0_snow_water_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_snow_water_equivalent += snow_water_equivalent(0.5, 0.5)
    var _t1_snow_water_equivalent = perf_counter_ns()
    var _ns_snow_water_equivalent = Float64(_t1_snow_water_equivalent - _t0_snow_water_equivalent) / Float64(N)
    print("MOJO_TIMING hydrometeorology::snow_water_equivalent", _ns_snow_water_equivalent, _acc_snow_water_equivalent)
    var _acc_rain_intensity_from_depth: Float64 = 0.0
    var _t0_rain_intensity_from_depth = perf_counter_ns()
    for _ in range(N):
        _acc_rain_intensity_from_depth += rain_intensity_from_depth(0.5, 0.5)
    var _t1_rain_intensity_from_depth = perf_counter_ns()
    var _ns_rain_intensity_from_depth = Float64(_t1_rain_intensity_from_depth - _t0_rain_intensity_from_depth) / Float64(N)
    print("MOJO_TIMING hydrometeorology::rain_intensity_from_depth", _ns_rain_intensity_from_depth, _acc_rain_intensity_from_depth)
    var _acc_antecedent_moisture_condition: Float64 = 0.0
    var _t0_antecedent_moisture_condition = perf_counter_ns()
    for _ in range(N):
        _acc_antecedent_moisture_condition += antecedent_moisture_condition(0.5, 0.5)
    var _t1_antecedent_moisture_condition = perf_counter_ns()
    var _ns_antecedent_moisture_condition = Float64(_t1_antecedent_moisture_condition - _t0_antecedent_moisture_condition) / Float64(N)
    print("MOJO_TIMING hydrometeorology::antecedent_moisture_condition", _ns_antecedent_moisture_condition, _acc_antecedent_moisture_condition)
    var _acc_flood_frequency_factor: Float64 = 0.0
    var _t0_flood_frequency_factor = perf_counter_ns()
    for _ in range(N):
        _acc_flood_frequency_factor += flood_frequency_factor(0.5)
    var _t1_flood_frequency_factor = perf_counter_ns()
    var _ns_flood_frequency_factor = Float64(_t1_flood_frequency_factor - _t0_flood_frequency_factor) / Float64(N)
    print("MOJO_TIMING hydrometeorology::flood_frequency_factor", _ns_flood_frequency_factor, _acc_flood_frequency_factor)
