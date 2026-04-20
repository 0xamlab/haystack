"""bench_geochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geochemistry import distribution_coefficient, partition_melt, batch_melting, rare_earth_normalization, isotope_mass_balance, weathering_index, redox_potential_pe, carbonate_saturation, henry_law_gas, organic_carbon_toc
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

    var _acc_distribution_coefficient: Float64 = 0.0
    var _t0_distribution_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_distribution_coefficient += distribution_coefficient(0.5, 0.5)
    var _t1_distribution_coefficient = perf_counter_ns()
    var _ns_distribution_coefficient = Float64(_t1_distribution_coefficient - _t0_distribution_coefficient) / Float64(N)
    print("MOJO_TIMING geochemistry::distribution_coefficient", _ns_distribution_coefficient, _acc_distribution_coefficient)
    var _acc_partition_melt: Float64 = 0.0
    var _t0_partition_melt = perf_counter_ns()
    for _ in range(N):
        _acc_partition_melt += partition_melt(0.5, 0.5, 0.5)
    var _t1_partition_melt = perf_counter_ns()
    var _ns_partition_melt = Float64(_t1_partition_melt - _t0_partition_melt) / Float64(N)
    print("MOJO_TIMING geochemistry::partition_melt", _ns_partition_melt, _acc_partition_melt)
    var _acc_batch_melting: Float64 = 0.0
    var _t0_batch_melting = perf_counter_ns()
    for _ in range(N):
        _acc_batch_melting += batch_melting(0.5, 0.5, 0.5)
    var _t1_batch_melting = perf_counter_ns()
    var _ns_batch_melting = Float64(_t1_batch_melting - _t0_batch_melting) / Float64(N)
    print("MOJO_TIMING geochemistry::batch_melting", _ns_batch_melting, _acc_batch_melting)
    var _acc_rare_earth_normalization: Float64 = 0.0
    var _t0_rare_earth_normalization = perf_counter_ns()
    for _ in range(N):
        _acc_rare_earth_normalization += rare_earth_normalization(0.5, 0.5)
    var _t1_rare_earth_normalization = perf_counter_ns()
    var _ns_rare_earth_normalization = Float64(_t1_rare_earth_normalization - _t0_rare_earth_normalization) / Float64(N)
    print("MOJO_TIMING geochemistry::rare_earth_normalization", _ns_rare_earth_normalization, _acc_rare_earth_normalization)
    var _acc_isotope_mass_balance: Float64 = 0.0
    var _t0_isotope_mass_balance = perf_counter_ns()
    for _ in range(N):
        _acc_isotope_mass_balance += isotope_mass_balance(0.5, 0.5, 0.5)
    var _t1_isotope_mass_balance = perf_counter_ns()
    var _ns_isotope_mass_balance = Float64(_t1_isotope_mass_balance - _t0_isotope_mass_balance) / Float64(N)
    print("MOJO_TIMING geochemistry::isotope_mass_balance", _ns_isotope_mass_balance, _acc_isotope_mass_balance)
    var _acc_weathering_index: Float64 = 0.0
    var _t0_weathering_index = perf_counter_ns()
    for _ in range(N):
        _acc_weathering_index += weathering_index(0.5, 0.5, 0.5, 0.5)
    var _t1_weathering_index = perf_counter_ns()
    var _ns_weathering_index = Float64(_t1_weathering_index - _t0_weathering_index) / Float64(N)
    print("MOJO_TIMING geochemistry::weathering_index", _ns_weathering_index, _acc_weathering_index)
    var _acc_redox_potential_pe: Float64 = 0.0
    var _t0_redox_potential_pe = perf_counter_ns()
    for _ in range(N):
        _acc_redox_potential_pe += redox_potential_pe(0.5)
    var _t1_redox_potential_pe = perf_counter_ns()
    var _ns_redox_potential_pe = Float64(_t1_redox_potential_pe - _t0_redox_potential_pe) / Float64(N)
    print("MOJO_TIMING geochemistry::redox_potential_pe", _ns_redox_potential_pe, _acc_redox_potential_pe)
    var _acc_carbonate_saturation: Float64 = 0.0
    var _t0_carbonate_saturation = perf_counter_ns()
    for _ in range(N):
        _acc_carbonate_saturation += carbonate_saturation(0.5, 0.5, 0.5)
    var _t1_carbonate_saturation = perf_counter_ns()
    var _ns_carbonate_saturation = Float64(_t1_carbonate_saturation - _t0_carbonate_saturation) / Float64(N)
    print("MOJO_TIMING geochemistry::carbonate_saturation", _ns_carbonate_saturation, _acc_carbonate_saturation)
    var _acc_henry_law_gas: Float64 = 0.0
    var _t0_henry_law_gas = perf_counter_ns()
    for _ in range(N):
        _acc_henry_law_gas += henry_law_gas(0.5, 0.5)
    var _t1_henry_law_gas = perf_counter_ns()
    var _ns_henry_law_gas = Float64(_t1_henry_law_gas - _t0_henry_law_gas) / Float64(N)
    print("MOJO_TIMING geochemistry::henry_law_gas", _ns_henry_law_gas, _acc_henry_law_gas)
    var _acc_organic_carbon_toc: Float64 = 0.0
    var _t0_organic_carbon_toc = perf_counter_ns()
    for _ in range(N):
        _acc_organic_carbon_toc += organic_carbon_toc(0.5, 0.5)
    var _t1_organic_carbon_toc = perf_counter_ns()
    var _ns_organic_carbon_toc = Float64(_t1_organic_carbon_toc - _t0_organic_carbon_toc) / Float64(N)
    print("MOJO_TIMING geochemistry::organic_carbon_toc", _ns_organic_carbon_toc, _acc_organic_carbon_toc)
