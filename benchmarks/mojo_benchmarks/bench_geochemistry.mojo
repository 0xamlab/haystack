"""bench_geochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geochemistry import distribution_coefficient, partition_melt, batch_melting, rare_earth_normalization, isotope_mass_balance, weathering_index, redox_potential_pe, carbonate_saturation, henry_law_gas, organic_carbon_toc
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

    var _acc_distribution_coefficient: Float64 = 0.0
    var _t0_distribution_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_distribution_coefficient += distribution_coefficient(0.5, 0.5)
    var _t1_distribution_coefficient = perf_counter_ns()
    var _ns_distribution_coefficient = Float64(_t1_distribution_coefficient - _t0_distribution_coefficient) / Float64(N)
    print("MOJO_TIMING geochemistry::distribution_coefficient", _ns_distribution_coefficient, _acc_distribution_coefficient)
    var _result_distribution_coefficient = distribution_coefficient(0.5, 0.5)
    var _summary_distribution_coefficient = _summary_float64(_result_distribution_coefficient)
    print("MOJO_RESULT geochemistry::distribution_coefficient", _summary_distribution_coefficient)
    var _acc_partition_melt: Float64 = 0.0
    var _t0_partition_melt = perf_counter_ns()
    for _ in range(N):
        _acc_partition_melt += partition_melt(0.5, 0.5, 0.5)
    var _t1_partition_melt = perf_counter_ns()
    var _ns_partition_melt = Float64(_t1_partition_melt - _t0_partition_melt) / Float64(N)
    print("MOJO_TIMING geochemistry::partition_melt", _ns_partition_melt, _acc_partition_melt)
    var _result_partition_melt = partition_melt(0.5, 0.5, 0.5)
    var _summary_partition_melt = _summary_float64(_result_partition_melt)
    print("MOJO_RESULT geochemistry::partition_melt", _summary_partition_melt)
    var _acc_batch_melting: Float64 = 0.0
    var _t0_batch_melting = perf_counter_ns()
    for _ in range(N):
        _acc_batch_melting += batch_melting(0.5, 0.5, 0.5)
    var _t1_batch_melting = perf_counter_ns()
    var _ns_batch_melting = Float64(_t1_batch_melting - _t0_batch_melting) / Float64(N)
    print("MOJO_TIMING geochemistry::batch_melting", _ns_batch_melting, _acc_batch_melting)
    var _result_batch_melting = batch_melting(0.5, 0.5, 0.5)
    var _summary_batch_melting = _summary_float64(_result_batch_melting)
    print("MOJO_RESULT geochemistry::batch_melting", _summary_batch_melting)
    var _acc_rare_earth_normalization: Float64 = 0.0
    var _t0_rare_earth_normalization = perf_counter_ns()
    for _ in range(N):
        _acc_rare_earth_normalization += rare_earth_normalization(0.5, 0.5)
    var _t1_rare_earth_normalization = perf_counter_ns()
    var _ns_rare_earth_normalization = Float64(_t1_rare_earth_normalization - _t0_rare_earth_normalization) / Float64(N)
    print("MOJO_TIMING geochemistry::rare_earth_normalization", _ns_rare_earth_normalization, _acc_rare_earth_normalization)
    var _result_rare_earth_normalization = rare_earth_normalization(0.5, 0.5)
    var _summary_rare_earth_normalization = _summary_float64(_result_rare_earth_normalization)
    print("MOJO_RESULT geochemistry::rare_earth_normalization", _summary_rare_earth_normalization)
    var _acc_isotope_mass_balance: Float64 = 0.0
    var _t0_isotope_mass_balance = perf_counter_ns()
    for _ in range(N):
        _acc_isotope_mass_balance += isotope_mass_balance(0.5, 0.5, 0.5)
    var _t1_isotope_mass_balance = perf_counter_ns()
    var _ns_isotope_mass_balance = Float64(_t1_isotope_mass_balance - _t0_isotope_mass_balance) / Float64(N)
    print("MOJO_TIMING geochemistry::isotope_mass_balance", _ns_isotope_mass_balance, _acc_isotope_mass_balance)
    var _result_isotope_mass_balance = isotope_mass_balance(0.5, 0.5, 0.5)
    var _summary_isotope_mass_balance = _summary_float64(_result_isotope_mass_balance)
    print("MOJO_RESULT geochemistry::isotope_mass_balance", _summary_isotope_mass_balance)
    var _acc_weathering_index: Float64 = 0.0
    var _t0_weathering_index = perf_counter_ns()
    for _ in range(N):
        _acc_weathering_index += weathering_index(0.5, 0.5, 0.5, 0.5)
    var _t1_weathering_index = perf_counter_ns()
    var _ns_weathering_index = Float64(_t1_weathering_index - _t0_weathering_index) / Float64(N)
    print("MOJO_TIMING geochemistry::weathering_index", _ns_weathering_index, _acc_weathering_index)
    var _result_weathering_index = weathering_index(0.5, 0.5, 0.5, 0.5)
    var _summary_weathering_index = _summary_float64(_result_weathering_index)
    print("MOJO_RESULT geochemistry::weathering_index", _summary_weathering_index)
    var _acc_redox_potential_pe: Float64 = 0.0
    var _t0_redox_potential_pe = perf_counter_ns()
    for _ in range(N):
        _acc_redox_potential_pe += redox_potential_pe(0.5)
    var _t1_redox_potential_pe = perf_counter_ns()
    var _ns_redox_potential_pe = Float64(_t1_redox_potential_pe - _t0_redox_potential_pe) / Float64(N)
    print("MOJO_TIMING geochemistry::redox_potential_pe", _ns_redox_potential_pe, _acc_redox_potential_pe)
    var _result_redox_potential_pe = redox_potential_pe(0.5)
    var _summary_redox_potential_pe = _summary_float64(_result_redox_potential_pe)
    print("MOJO_RESULT geochemistry::redox_potential_pe", _summary_redox_potential_pe)
    var _acc_carbonate_saturation: Float64 = 0.0
    var _t0_carbonate_saturation = perf_counter_ns()
    for _ in range(N):
        _acc_carbonate_saturation += carbonate_saturation(0.5, 0.5, 0.5)
    var _t1_carbonate_saturation = perf_counter_ns()
    var _ns_carbonate_saturation = Float64(_t1_carbonate_saturation - _t0_carbonate_saturation) / Float64(N)
    print("MOJO_TIMING geochemistry::carbonate_saturation", _ns_carbonate_saturation, _acc_carbonate_saturation)
    var _result_carbonate_saturation = carbonate_saturation(0.5, 0.5, 0.5)
    var _summary_carbonate_saturation = _summary_float64(_result_carbonate_saturation)
    print("MOJO_RESULT geochemistry::carbonate_saturation", _summary_carbonate_saturation)
    var _acc_henry_law_gas: Float64 = 0.0
    var _t0_henry_law_gas = perf_counter_ns()
    for _ in range(N):
        _acc_henry_law_gas += henry_law_gas(0.5, 0.5)
    var _t1_henry_law_gas = perf_counter_ns()
    var _ns_henry_law_gas = Float64(_t1_henry_law_gas - _t0_henry_law_gas) / Float64(N)
    print("MOJO_TIMING geochemistry::henry_law_gas", _ns_henry_law_gas, _acc_henry_law_gas)
    var _result_henry_law_gas = henry_law_gas(0.5, 0.5)
    var _summary_henry_law_gas = _summary_float64(_result_henry_law_gas)
    print("MOJO_RESULT geochemistry::henry_law_gas", _summary_henry_law_gas)
    var _acc_organic_carbon_toc: Float64 = 0.0
    var _t0_organic_carbon_toc = perf_counter_ns()
    for _ in range(N):
        _acc_organic_carbon_toc += organic_carbon_toc(0.5, 0.5)
    var _t1_organic_carbon_toc = perf_counter_ns()
    var _ns_organic_carbon_toc = Float64(_t1_organic_carbon_toc - _t0_organic_carbon_toc) / Float64(N)
    print("MOJO_TIMING geochemistry::organic_carbon_toc", _ns_organic_carbon_toc, _acc_organic_carbon_toc)
    var _result_organic_carbon_toc = organic_carbon_toc(0.5, 0.5)
    var _summary_organic_carbon_toc = _summary_float64(_result_organic_carbon_toc)
    print("MOJO_RESULT geochemistry::organic_carbon_toc", _summary_organic_carbon_toc)
