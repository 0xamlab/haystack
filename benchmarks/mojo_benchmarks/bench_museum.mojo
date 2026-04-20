"""bench_museum.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from museum import lux_hours_annual, uv_exposure, relative_humidity_from_temps, moisture_content_equilibrium, time_weighted_preservation_index, light_damage_reciprocity, climate_stability_score, storage_density, collection_growth_rate, insurance_value_appreciation, visitor_density, conservation_priority_score
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

    var _acc_lux_hours_annual: Float64 = 0.0
    var _t0_lux_hours_annual = perf_counter_ns()
    for _ in range(N):
        _acc_lux_hours_annual += lux_hours_annual(0.5, 0.5, 0.5)
    var _t1_lux_hours_annual = perf_counter_ns()
    var _ns_lux_hours_annual = Float64(_t1_lux_hours_annual - _t0_lux_hours_annual) / Float64(N)
    print("MOJO_TIMING museum::lux_hours_annual", _ns_lux_hours_annual, _acc_lux_hours_annual)
    var _acc_uv_exposure: Float64 = 0.0
    var _t0_uv_exposure = perf_counter_ns()
    for _ in range(N):
        _acc_uv_exposure += uv_exposure(0.5, 0.5)
    var _t1_uv_exposure = perf_counter_ns()
    var _ns_uv_exposure = Float64(_t1_uv_exposure - _t0_uv_exposure) / Float64(N)
    print("MOJO_TIMING museum::uv_exposure", _ns_uv_exposure, _acc_uv_exposure)
    var _acc_relative_humidity_from_temps: Float64 = 0.0
    var _t0_relative_humidity_from_temps = perf_counter_ns()
    for _ in range(N):
        _acc_relative_humidity_from_temps += relative_humidity_from_temps(0.5, 0.5)
    var _t1_relative_humidity_from_temps = perf_counter_ns()
    var _ns_relative_humidity_from_temps = Float64(_t1_relative_humidity_from_temps - _t0_relative_humidity_from_temps) / Float64(N)
    print("MOJO_TIMING museum::relative_humidity_from_temps", _ns_relative_humidity_from_temps, _acc_relative_humidity_from_temps)
    var _acc_moisture_content_equilibrium: Float64 = 0.0
    var _t0_moisture_content_equilibrium = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_equilibrium += moisture_content_equilibrium(0.5, 0.5)
    var _t1_moisture_content_equilibrium = perf_counter_ns()
    var _ns_moisture_content_equilibrium = Float64(_t1_moisture_content_equilibrium - _t0_moisture_content_equilibrium) / Float64(N)
    print("MOJO_TIMING museum::moisture_content_equilibrium", _ns_moisture_content_equilibrium, _acc_moisture_content_equilibrium)
    var _acc_time_weighted_preservation_index: Float64 = 0.0
    var _t0_time_weighted_preservation_index = perf_counter_ns()
    for _ in range(N):
        _acc_time_weighted_preservation_index += time_weighted_preservation_index(0.5, 0.5, 0.5)
    var _t1_time_weighted_preservation_index = perf_counter_ns()
    var _ns_time_weighted_preservation_index = Float64(_t1_time_weighted_preservation_index - _t0_time_weighted_preservation_index) / Float64(N)
    print("MOJO_TIMING museum::time_weighted_preservation_index", _ns_time_weighted_preservation_index, _acc_time_weighted_preservation_index)
    var _acc_light_damage_reciprocity: Float64 = 0.0
    var _t0_light_damage_reciprocity = perf_counter_ns()
    for _ in range(N):
        _acc_light_damage_reciprocity += light_damage_reciprocity(0.5, 0.5)
    var _t1_light_damage_reciprocity = perf_counter_ns()
    var _ns_light_damage_reciprocity = Float64(_t1_light_damage_reciprocity - _t0_light_damage_reciprocity) / Float64(N)
    print("MOJO_TIMING museum::light_damage_reciprocity", _ns_light_damage_reciprocity, _acc_light_damage_reciprocity)
    var _acc_climate_stability_score: Float64 = 0.0
    var _t0_climate_stability_score = perf_counter_ns()
    for _ in range(N):
        _acc_climate_stability_score += climate_stability_score(0.5, 0.5)
    var _t1_climate_stability_score = perf_counter_ns()
    var _ns_climate_stability_score = Float64(_t1_climate_stability_score - _t0_climate_stability_score) / Float64(N)
    print("MOJO_TIMING museum::climate_stability_score", _ns_climate_stability_score, _acc_climate_stability_score)
    var _acc_storage_density: Float64 = 0.0
    var _t0_storage_density = perf_counter_ns()
    for _ in range(N):
        _acc_storage_density += storage_density(0.5, 0.5)
    var _t1_storage_density = perf_counter_ns()
    var _ns_storage_density = Float64(_t1_storage_density - _t0_storage_density) / Float64(N)
    print("MOJO_TIMING museum::storage_density", _ns_storage_density, _acc_storage_density)
    var _acc_collection_growth_rate: Float64 = 0.0
    var _t0_collection_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_collection_growth_rate += collection_growth_rate(0.5, 0.5, 0.5)
    var _t1_collection_growth_rate = perf_counter_ns()
    var _ns_collection_growth_rate = Float64(_t1_collection_growth_rate - _t0_collection_growth_rate) / Float64(N)
    print("MOJO_TIMING museum::collection_growth_rate", _ns_collection_growth_rate, _acc_collection_growth_rate)
    var _acc_insurance_value_appreciation: Float64 = 0.0
    var _t0_insurance_value_appreciation = perf_counter_ns()
    for _ in range(N):
        _acc_insurance_value_appreciation += insurance_value_appreciation(0.5, 0.5, 0.5)
    var _t1_insurance_value_appreciation = perf_counter_ns()
    var _ns_insurance_value_appreciation = Float64(_t1_insurance_value_appreciation - _t0_insurance_value_appreciation) / Float64(N)
    print("MOJO_TIMING museum::insurance_value_appreciation", _ns_insurance_value_appreciation, _acc_insurance_value_appreciation)
    var _acc_visitor_density: Float64 = 0.0
    var _t0_visitor_density = perf_counter_ns()
    for _ in range(N):
        _acc_visitor_density += visitor_density(0.5, 0.5)
    var _t1_visitor_density = perf_counter_ns()
    var _ns_visitor_density = Float64(_t1_visitor_density - _t0_visitor_density) / Float64(N)
    print("MOJO_TIMING museum::visitor_density", _ns_visitor_density, _acc_visitor_density)
    var _acc_conservation_priority_score: Float64 = 0.0
    var _t0_conservation_priority_score = perf_counter_ns()
    for _ in range(N):
        _acc_conservation_priority_score += conservation_priority_score(0.5, 0.5, 0.5)
    var _t1_conservation_priority_score = perf_counter_ns()
    var _ns_conservation_priority_score = Float64(_t1_conservation_priority_score - _t0_conservation_priority_score) / Float64(N)
    print("MOJO_TIMING museum::conservation_priority_score", _ns_conservation_priority_score, _acc_conservation_priority_score)
