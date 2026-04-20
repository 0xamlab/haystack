"""bench_sustainability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sustainability import carbon_footprint_transport, energy_intensity, water_intensity, waste_diversion_rate, renewable_energy_fraction, ghg_scope1, ghg_scope2, ghg_scope3_estimate, carbon_offset_cost, circular_economy_index, social_return_on_investment, esg_composite_score
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

    var _acc_carbon_footprint_transport: Float64 = 0.0
    var _t0_carbon_footprint_transport = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_footprint_transport += carbon_footprint_transport(0.5, 0.5)
    var _t1_carbon_footprint_transport = perf_counter_ns()
    var _ns_carbon_footprint_transport = Float64(_t1_carbon_footprint_transport - _t0_carbon_footprint_transport) / Float64(N)
    print("MOJO_TIMING sustainability::carbon_footprint_transport", _ns_carbon_footprint_transport, _acc_carbon_footprint_transport)
    var _acc_energy_intensity: Float64 = 0.0
    var _t0_energy_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_energy_intensity += energy_intensity(0.5, 0.5)
    var _t1_energy_intensity = perf_counter_ns()
    var _ns_energy_intensity = Float64(_t1_energy_intensity - _t0_energy_intensity) / Float64(N)
    print("MOJO_TIMING sustainability::energy_intensity", _ns_energy_intensity, _acc_energy_intensity)
    var _acc_water_intensity: Float64 = 0.0
    var _t0_water_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_water_intensity += water_intensity(0.5, 0.5)
    var _t1_water_intensity = perf_counter_ns()
    var _ns_water_intensity = Float64(_t1_water_intensity - _t0_water_intensity) / Float64(N)
    print("MOJO_TIMING sustainability::water_intensity", _ns_water_intensity, _acc_water_intensity)
    var _acc_waste_diversion_rate: Float64 = 0.0
    var _t0_waste_diversion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_waste_diversion_rate += waste_diversion_rate(0.5, 0.5)
    var _t1_waste_diversion_rate = perf_counter_ns()
    var _ns_waste_diversion_rate = Float64(_t1_waste_diversion_rate - _t0_waste_diversion_rate) / Float64(N)
    print("MOJO_TIMING sustainability::waste_diversion_rate", _ns_waste_diversion_rate, _acc_waste_diversion_rate)
    var _acc_renewable_energy_fraction: Float64 = 0.0
    var _t0_renewable_energy_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_renewable_energy_fraction += renewable_energy_fraction(0.5, 0.5)
    var _t1_renewable_energy_fraction = perf_counter_ns()
    var _ns_renewable_energy_fraction = Float64(_t1_renewable_energy_fraction - _t0_renewable_energy_fraction) / Float64(N)
    print("MOJO_TIMING sustainability::renewable_energy_fraction", _ns_renewable_energy_fraction, _acc_renewable_energy_fraction)
    var _acc_ghg_scope1: Float64 = 0.0
    var _t0_ghg_scope1 = perf_counter_ns()
    for _ in range(N):
        _acc_ghg_scope1 += ghg_scope1(0.5)
    var _t1_ghg_scope1 = perf_counter_ns()
    var _ns_ghg_scope1 = Float64(_t1_ghg_scope1 - _t0_ghg_scope1) / Float64(N)
    print("MOJO_TIMING sustainability::ghg_scope1", _ns_ghg_scope1, _acc_ghg_scope1)
    var _acc_ghg_scope2: Float64 = 0.0
    var _t0_ghg_scope2 = perf_counter_ns()
    for _ in range(N):
        _acc_ghg_scope2 += ghg_scope2(0.5, 0.5)
    var _t1_ghg_scope2 = perf_counter_ns()
    var _ns_ghg_scope2 = Float64(_t1_ghg_scope2 - _t0_ghg_scope2) / Float64(N)
    print("MOJO_TIMING sustainability::ghg_scope2", _ns_ghg_scope2, _acc_ghg_scope2)
    var _acc_ghg_scope3_estimate: Float64 = 0.0
    var _t0_ghg_scope3_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_ghg_scope3_estimate += ghg_scope3_estimate(0.5, 0.5)
    var _t1_ghg_scope3_estimate = perf_counter_ns()
    var _ns_ghg_scope3_estimate = Float64(_t1_ghg_scope3_estimate - _t0_ghg_scope3_estimate) / Float64(N)
    print("MOJO_TIMING sustainability::ghg_scope3_estimate", _ns_ghg_scope3_estimate, _acc_ghg_scope3_estimate)
    var _acc_carbon_offset_cost: Float64 = 0.0
    var _t0_carbon_offset_cost = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_offset_cost += carbon_offset_cost(0.5, 0.5)
    var _t1_carbon_offset_cost = perf_counter_ns()
    var _ns_carbon_offset_cost = Float64(_t1_carbon_offset_cost - _t0_carbon_offset_cost) / Float64(N)
    print("MOJO_TIMING sustainability::carbon_offset_cost", _ns_carbon_offset_cost, _acc_carbon_offset_cost)
    var _acc_circular_economy_index: Float64 = 0.0
    var _t0_circular_economy_index = perf_counter_ns()
    for _ in range(N):
        _acc_circular_economy_index += circular_economy_index(0.5, 0.5)
    var _t1_circular_economy_index = perf_counter_ns()
    var _ns_circular_economy_index = Float64(_t1_circular_economy_index - _t0_circular_economy_index) / Float64(N)
    print("MOJO_TIMING sustainability::circular_economy_index", _ns_circular_economy_index, _acc_circular_economy_index)
    var _acc_social_return_on_investment: Float64 = 0.0
    var _t0_social_return_on_investment = perf_counter_ns()
    for _ in range(N):
        _acc_social_return_on_investment += social_return_on_investment(0.5, 0.5)
    var _t1_social_return_on_investment = perf_counter_ns()
    var _ns_social_return_on_investment = Float64(_t1_social_return_on_investment - _t0_social_return_on_investment) / Float64(N)
    print("MOJO_TIMING sustainability::social_return_on_investment", _ns_social_return_on_investment, _acc_social_return_on_investment)
    var _acc_esg_composite_score: Float64 = 0.0
    var _t0_esg_composite_score = perf_counter_ns()
    for _ in range(N):
        _acc_esg_composite_score += esg_composite_score(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_esg_composite_score = perf_counter_ns()
    var _ns_esg_composite_score = Float64(_t1_esg_composite_score - _t0_esg_composite_score) / Float64(N)
    print("MOJO_TIMING sustainability::esg_composite_score", _ns_esg_composite_score, _acc_esg_composite_score)
