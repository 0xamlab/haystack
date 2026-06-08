"""bench_biogeochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from biogeochemistry import net_ecosystem_production, carbon_use_efficiency, nitrogen_mineralisation, denitrification_rate, phosphorus_sorption, methane_oxidation, soil_carbon_turnover, weathering_co2_consumption, nitrogen_fixation_estimate, global_carbon_budget
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

    var _acc_net_ecosystem_production: Float64 = 0.0
    var _t0_net_ecosystem_production = perf_counter_ns()
    for _ in range(N):
        _acc_net_ecosystem_production += net_ecosystem_production(0.5, 0.5)
    var _t1_net_ecosystem_production = perf_counter_ns()
    var _ns_net_ecosystem_production = Float64(_t1_net_ecosystem_production - _t0_net_ecosystem_production) / Float64(N)
    print("MOJO_TIMING biogeochemistry::net_ecosystem_production", _ns_net_ecosystem_production, _acc_net_ecosystem_production)
    var _result_net_ecosystem_production = net_ecosystem_production(0.5, 0.5)
    var _summary_net_ecosystem_production = _summary_float64(_result_net_ecosystem_production)
    print("MOJO_RESULT biogeochemistry::net_ecosystem_production", _summary_net_ecosystem_production)
    var _acc_carbon_use_efficiency: Float64 = 0.0
    var _t0_carbon_use_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_use_efficiency += carbon_use_efficiency(0.5, 0.5)
    var _t1_carbon_use_efficiency = perf_counter_ns()
    var _ns_carbon_use_efficiency = Float64(_t1_carbon_use_efficiency - _t0_carbon_use_efficiency) / Float64(N)
    print("MOJO_TIMING biogeochemistry::carbon_use_efficiency", _ns_carbon_use_efficiency, _acc_carbon_use_efficiency)
    var _result_carbon_use_efficiency = carbon_use_efficiency(0.5, 0.5)
    var _summary_carbon_use_efficiency = _summary_float64(_result_carbon_use_efficiency)
    print("MOJO_RESULT biogeochemistry::carbon_use_efficiency", _summary_carbon_use_efficiency)
    var _acc_nitrogen_mineralisation: Float64 = 0.0
    var _t0_nitrogen_mineralisation = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_mineralisation += nitrogen_mineralisation(0.5, 0.5, 0.5)
    var _t1_nitrogen_mineralisation = perf_counter_ns()
    var _ns_nitrogen_mineralisation = Float64(_t1_nitrogen_mineralisation - _t0_nitrogen_mineralisation) / Float64(N)
    print("MOJO_TIMING biogeochemistry::nitrogen_mineralisation", _ns_nitrogen_mineralisation, _acc_nitrogen_mineralisation)
    var _result_nitrogen_mineralisation = nitrogen_mineralisation(0.5, 0.5, 0.5)
    var _summary_nitrogen_mineralisation = _summary_float64(_result_nitrogen_mineralisation)
    print("MOJO_RESULT biogeochemistry::nitrogen_mineralisation", _summary_nitrogen_mineralisation)
    var _acc_denitrification_rate: Float64 = 0.0
    var _t0_denitrification_rate = perf_counter_ns()
    for _ in range(N):
        _acc_denitrification_rate += denitrification_rate(0.5, 0.5, 0.5)
    var _t1_denitrification_rate = perf_counter_ns()
    var _ns_denitrification_rate = Float64(_t1_denitrification_rate - _t0_denitrification_rate) / Float64(N)
    print("MOJO_TIMING biogeochemistry::denitrification_rate", _ns_denitrification_rate, _acc_denitrification_rate)
    var _result_denitrification_rate = denitrification_rate(0.5, 0.5, 0.5)
    var _summary_denitrification_rate = _summary_float64(_result_denitrification_rate)
    print("MOJO_RESULT biogeochemistry::denitrification_rate", _summary_denitrification_rate)
    var _acc_phosphorus_sorption: Float64 = 0.0
    var _t0_phosphorus_sorption = perf_counter_ns()
    for _ in range(N):
        _acc_phosphorus_sorption += phosphorus_sorption(0.5, 0.5, 0.5)
    var _t1_phosphorus_sorption = perf_counter_ns()
    var _ns_phosphorus_sorption = Float64(_t1_phosphorus_sorption - _t0_phosphorus_sorption) / Float64(N)
    print("MOJO_TIMING biogeochemistry::phosphorus_sorption", _ns_phosphorus_sorption, _acc_phosphorus_sorption)
    var _result_phosphorus_sorption = phosphorus_sorption(0.5, 0.5, 0.5)
    var _summary_phosphorus_sorption = _summary_float64(_result_phosphorus_sorption)
    print("MOJO_RESULT biogeochemistry::phosphorus_sorption", _summary_phosphorus_sorption)
    var _acc_methane_oxidation: Float64 = 0.0
    var _t0_methane_oxidation = perf_counter_ns()
    for _ in range(N):
        _acc_methane_oxidation += methane_oxidation(0.5, 0.5)
    var _t1_methane_oxidation = perf_counter_ns()
    var _ns_methane_oxidation = Float64(_t1_methane_oxidation - _t0_methane_oxidation) / Float64(N)
    print("MOJO_TIMING biogeochemistry::methane_oxidation", _ns_methane_oxidation, _acc_methane_oxidation)
    var _result_methane_oxidation = methane_oxidation(0.5, 0.5)
    var _summary_methane_oxidation = _summary_float64(_result_methane_oxidation)
    print("MOJO_RESULT biogeochemistry::methane_oxidation", _summary_methane_oxidation)
    var _acc_soil_carbon_turnover: Float64 = 0.0
    var _t0_soil_carbon_turnover = perf_counter_ns()
    for _ in range(N):
        _acc_soil_carbon_turnover += soil_carbon_turnover(0.5, 0.5, 0.5)
    var _t1_soil_carbon_turnover = perf_counter_ns()
    var _ns_soil_carbon_turnover = Float64(_t1_soil_carbon_turnover - _t0_soil_carbon_turnover) / Float64(N)
    print("MOJO_TIMING biogeochemistry::soil_carbon_turnover", _ns_soil_carbon_turnover, _acc_soil_carbon_turnover)
    var _result_soil_carbon_turnover = soil_carbon_turnover(0.5, 0.5, 0.5)
    var _summary_soil_carbon_turnover = _summary_float64(_result_soil_carbon_turnover)
    print("MOJO_RESULT biogeochemistry::soil_carbon_turnover", _summary_soil_carbon_turnover)
    var _acc_weathering_co2_consumption: Float64 = 0.0
    var _t0_weathering_co2_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_weathering_co2_consumption += weathering_co2_consumption(0.5, 0.5)
    var _t1_weathering_co2_consumption = perf_counter_ns()
    var _ns_weathering_co2_consumption = Float64(_t1_weathering_co2_consumption - _t0_weathering_co2_consumption) / Float64(N)
    print("MOJO_TIMING biogeochemistry::weathering_co2_consumption", _ns_weathering_co2_consumption, _acc_weathering_co2_consumption)
    var _result_weathering_co2_consumption = weathering_co2_consumption(0.5, 0.5)
    var _summary_weathering_co2_consumption = _summary_float64(_result_weathering_co2_consumption)
    print("MOJO_RESULT biogeochemistry::weathering_co2_consumption", _summary_weathering_co2_consumption)
    var _acc_nitrogen_fixation_estimate: Float64 = 0.0
    var _t0_nitrogen_fixation_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_fixation_estimate += nitrogen_fixation_estimate(0.5)
    var _t1_nitrogen_fixation_estimate = perf_counter_ns()
    var _ns_nitrogen_fixation_estimate = Float64(_t1_nitrogen_fixation_estimate - _t0_nitrogen_fixation_estimate) / Float64(N)
    print("MOJO_TIMING biogeochemistry::nitrogen_fixation_estimate", _ns_nitrogen_fixation_estimate, _acc_nitrogen_fixation_estimate)
    var _result_nitrogen_fixation_estimate = nitrogen_fixation_estimate(0.5)
    var _summary_nitrogen_fixation_estimate = _summary_float64(_result_nitrogen_fixation_estimate)
    print("MOJO_RESULT biogeochemistry::nitrogen_fixation_estimate", _summary_nitrogen_fixation_estimate)
    var _acc_global_carbon_budget: Float64 = 0.0
    var _t0_global_carbon_budget = perf_counter_ns()
    for _ in range(N):
        _acc_global_carbon_budget += global_carbon_budget(0.5, 0.5, 0.5, 0.5)
    var _t1_global_carbon_budget = perf_counter_ns()
    var _ns_global_carbon_budget = Float64(_t1_global_carbon_budget - _t0_global_carbon_budget) / Float64(N)
    print("MOJO_TIMING biogeochemistry::global_carbon_budget", _ns_global_carbon_budget, _acc_global_carbon_budget)
    var _result_global_carbon_budget = global_carbon_budget(0.5, 0.5, 0.5, 0.5)
    var _summary_global_carbon_budget = _summary_float64(_result_global_carbon_budget)
    print("MOJO_RESULT biogeochemistry::global_carbon_budget", _summary_global_carbon_budget)
