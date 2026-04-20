"""bench_palynology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from palynology import pollen_concentration, pollen_accumulation_rate, taxa_diversity_index, relative_pollen_percentage, r_value_correction, arboreal_non_arboreal_ratio, pollen_influx, spore_germination_index, pollen_productivity_estimate, pollen_transport_distance
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

    var _acc_pollen_concentration: Float64 = 0.0
    var _t0_pollen_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_concentration += pollen_concentration(0.5, 0.5, 0.5, 0.5)
    var _t1_pollen_concentration = perf_counter_ns()
    var _ns_pollen_concentration = Float64(_t1_pollen_concentration - _t0_pollen_concentration) / Float64(N)
    print("MOJO_TIMING palynology::pollen_concentration", _ns_pollen_concentration, _acc_pollen_concentration)
    var _acc_pollen_accumulation_rate: Float64 = 0.0
    var _t0_pollen_accumulation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_accumulation_rate += pollen_accumulation_rate(0.5, 0.5)
    var _t1_pollen_accumulation_rate = perf_counter_ns()
    var _ns_pollen_accumulation_rate = Float64(_t1_pollen_accumulation_rate - _t0_pollen_accumulation_rate) / Float64(N)
    print("MOJO_TIMING palynology::pollen_accumulation_rate", _ns_pollen_accumulation_rate, _acc_pollen_accumulation_rate)
    var _acc_taxa_diversity_index: Float64 = 0.0
    var _t0_taxa_diversity_index = perf_counter_ns()
    for _ in range(N):
        _acc_taxa_diversity_index += taxa_diversity_index(0.5, 0.5)
    var _t1_taxa_diversity_index = perf_counter_ns()
    var _ns_taxa_diversity_index = Float64(_t1_taxa_diversity_index - _t0_taxa_diversity_index) / Float64(N)
    print("MOJO_TIMING palynology::taxa_diversity_index", _ns_taxa_diversity_index, _acc_taxa_diversity_index)
    var _acc_relative_pollen_percentage: Float64 = 0.0
    var _t0_relative_pollen_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_relative_pollen_percentage += relative_pollen_percentage(0.5, 0.5)
    var _t1_relative_pollen_percentage = perf_counter_ns()
    var _ns_relative_pollen_percentage = Float64(_t1_relative_pollen_percentage - _t0_relative_pollen_percentage) / Float64(N)
    print("MOJO_TIMING palynology::relative_pollen_percentage", _ns_relative_pollen_percentage, _acc_relative_pollen_percentage)
    var _acc_r_value_correction: Float64 = 0.0
    var _t0_r_value_correction = perf_counter_ns()
    for _ in range(N):
        _acc_r_value_correction += r_value_correction(0.5, 0.5)
    var _t1_r_value_correction = perf_counter_ns()
    var _ns_r_value_correction = Float64(_t1_r_value_correction - _t0_r_value_correction) / Float64(N)
    print("MOJO_TIMING palynology::r_value_correction", _ns_r_value_correction, _acc_r_value_correction)
    var _acc_arboreal_non_arboreal_ratio: Float64 = 0.0
    var _t0_arboreal_non_arboreal_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_arboreal_non_arboreal_ratio += arboreal_non_arboreal_ratio(0.5, 0.5)
    var _t1_arboreal_non_arboreal_ratio = perf_counter_ns()
    var _ns_arboreal_non_arboreal_ratio = Float64(_t1_arboreal_non_arboreal_ratio - _t0_arboreal_non_arboreal_ratio) / Float64(N)
    print("MOJO_TIMING palynology::arboreal_non_arboreal_ratio", _ns_arboreal_non_arboreal_ratio, _acc_arboreal_non_arboreal_ratio)
    var _acc_pollen_influx: Float64 = 0.0
    var _t0_pollen_influx = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_influx += pollen_influx(0.5, 0.5)
    var _t1_pollen_influx = perf_counter_ns()
    var _ns_pollen_influx = Float64(_t1_pollen_influx - _t0_pollen_influx) / Float64(N)
    print("MOJO_TIMING palynology::pollen_influx", _ns_pollen_influx, _acc_pollen_influx)
    var _acc_spore_germination_index: Float64 = 0.0
    var _t0_spore_germination_index = perf_counter_ns()
    for _ in range(N):
        _acc_spore_germination_index += spore_germination_index(0.5, 0.5)
    var _t1_spore_germination_index = perf_counter_ns()
    var _ns_spore_germination_index = Float64(_t1_spore_germination_index - _t0_spore_germination_index) / Float64(N)
    print("MOJO_TIMING palynology::spore_germination_index", _ns_spore_germination_index, _acc_spore_germination_index)
    var _acc_pollen_productivity_estimate: Float64 = 0.0
    var _t0_pollen_productivity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_productivity_estimate += pollen_productivity_estimate(0.5, 0.5, 0.5)
    var _t1_pollen_productivity_estimate = perf_counter_ns()
    var _ns_pollen_productivity_estimate = Float64(_t1_pollen_productivity_estimate - _t0_pollen_productivity_estimate) / Float64(N)
    print("MOJO_TIMING palynology::pollen_productivity_estimate", _ns_pollen_productivity_estimate, _acc_pollen_productivity_estimate)
    var _acc_pollen_transport_distance: Float64 = 0.0
    var _t0_pollen_transport_distance = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_transport_distance += pollen_transport_distance(0.5, 0.5, 0.5)
    var _t1_pollen_transport_distance = perf_counter_ns()
    var _ns_pollen_transport_distance = Float64(_t1_pollen_transport_distance - _t0_pollen_transport_distance) / Float64(N)
    print("MOJO_TIMING palynology::pollen_transport_distance", _ns_pollen_transport_distance, _acc_pollen_transport_distance)
