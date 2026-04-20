"""bench_biogeochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from biogeochemistry import net_ecosystem_production, carbon_use_efficiency, nitrogen_mineralisation, denitrification_rate, phosphorus_sorption, methane_oxidation, soil_carbon_turnover, weathering_co2_consumption, nitrogen_fixation_estimate, global_carbon_budget
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

    var _acc_net_ecosystem_production: Float64 = 0.0
    var _t0_net_ecosystem_production = perf_counter_ns()
    for _ in range(N):
        _acc_net_ecosystem_production += net_ecosystem_production(0.5, 0.5)
    var _t1_net_ecosystem_production = perf_counter_ns()
    var _ns_net_ecosystem_production = Float64(_t1_net_ecosystem_production - _t0_net_ecosystem_production) / Float64(N)
    print("MOJO_TIMING biogeochemistry::net_ecosystem_production", _ns_net_ecosystem_production, _acc_net_ecosystem_production)
    var _acc_carbon_use_efficiency: Float64 = 0.0
    var _t0_carbon_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_use_efficiency += carbon_use_efficiency(0.5, 0.5)
    var _t1_carbon_use_efficiency = perf_counter_ns()
    var _ns_carbon_use_efficiency = Float64(_t1_carbon_use_efficiency - _t0_carbon_use_efficiency) / Float64(N)
    print("MOJO_TIMING biogeochemistry::carbon_use_efficiency", _ns_carbon_use_efficiency, _acc_carbon_use_efficiency)
    var _acc_nitrogen_mineralisation: Float64 = 0.0
    var _t0_nitrogen_mineralisation = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_mineralisation += nitrogen_mineralisation(0.5, 0.5, 0.5)
    var _t1_nitrogen_mineralisation = perf_counter_ns()
    var _ns_nitrogen_mineralisation = Float64(_t1_nitrogen_mineralisation - _t0_nitrogen_mineralisation) / Float64(N)
    print("MOJO_TIMING biogeochemistry::nitrogen_mineralisation", _ns_nitrogen_mineralisation, _acc_nitrogen_mineralisation)
    var _acc_denitrification_rate: Float64 = 0.0
    var _t0_denitrification_rate = perf_counter_ns()
    for _ in range(N):
        _acc_denitrification_rate += denitrification_rate(0.5, 0.5, 0.5)
    var _t1_denitrification_rate = perf_counter_ns()
    var _ns_denitrification_rate = Float64(_t1_denitrification_rate - _t0_denitrification_rate) / Float64(N)
    print("MOJO_TIMING biogeochemistry::denitrification_rate", _ns_denitrification_rate, _acc_denitrification_rate)
    var _acc_phosphorus_sorption: Float64 = 0.0
    var _t0_phosphorus_sorption = perf_counter_ns()
    for _ in range(N):
        _acc_phosphorus_sorption += phosphorus_sorption(0.5, 0.5, 0.5)
    var _t1_phosphorus_sorption = perf_counter_ns()
    var _ns_phosphorus_sorption = Float64(_t1_phosphorus_sorption - _t0_phosphorus_sorption) / Float64(N)
    print("MOJO_TIMING biogeochemistry::phosphorus_sorption", _ns_phosphorus_sorption, _acc_phosphorus_sorption)
    var _acc_methane_oxidation: Float64 = 0.0
    var _t0_methane_oxidation = perf_counter_ns()
    for _ in range(N):
        _acc_methane_oxidation += methane_oxidation(0.5, 0.5)
    var _t1_methane_oxidation = perf_counter_ns()
    var _ns_methane_oxidation = Float64(_t1_methane_oxidation - _t0_methane_oxidation) / Float64(N)
    print("MOJO_TIMING biogeochemistry::methane_oxidation", _ns_methane_oxidation, _acc_methane_oxidation)
    var _acc_soil_carbon_turnover: Float64 = 0.0
    var _t0_soil_carbon_turnover = perf_counter_ns()
    for _ in range(N):
        _acc_soil_carbon_turnover += soil_carbon_turnover(0.5, 0.5, 0.5)
    var _t1_soil_carbon_turnover = perf_counter_ns()
    var _ns_soil_carbon_turnover = Float64(_t1_soil_carbon_turnover - _t0_soil_carbon_turnover) / Float64(N)
    print("MOJO_TIMING biogeochemistry::soil_carbon_turnover", _ns_soil_carbon_turnover, _acc_soil_carbon_turnover)
    var _acc_weathering_co2_consumption: Float64 = 0.0
    var _t0_weathering_co2_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_weathering_co2_consumption += weathering_co2_consumption(0.5, 0.5)
    var _t1_weathering_co2_consumption = perf_counter_ns()
    var _ns_weathering_co2_consumption = Float64(_t1_weathering_co2_consumption - _t0_weathering_co2_consumption) / Float64(N)
    print("MOJO_TIMING biogeochemistry::weathering_co2_consumption", _ns_weathering_co2_consumption, _acc_weathering_co2_consumption)
    var _acc_nitrogen_fixation_estimate: Float64 = 0.0
    var _t0_nitrogen_fixation_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_fixation_estimate += nitrogen_fixation_estimate(0.5)
    var _t1_nitrogen_fixation_estimate = perf_counter_ns()
    var _ns_nitrogen_fixation_estimate = Float64(_t1_nitrogen_fixation_estimate - _t0_nitrogen_fixation_estimate) / Float64(N)
    print("MOJO_TIMING biogeochemistry::nitrogen_fixation_estimate", _ns_nitrogen_fixation_estimate, _acc_nitrogen_fixation_estimate)
    var _acc_global_carbon_budget: Float64 = 0.0
    var _t0_global_carbon_budget = perf_counter_ns()
    for _ in range(N):
        _acc_global_carbon_budget += global_carbon_budget(0.5, 0.5, 0.5, 0.5)
    var _t1_global_carbon_budget = perf_counter_ns()
    var _ns_global_carbon_budget = Float64(_t1_global_carbon_budget - _t0_global_carbon_budget) / Float64(N)
    print("MOJO_TIMING biogeochemistry::global_carbon_budget", _ns_global_carbon_budget, _acc_global_carbon_budget)
