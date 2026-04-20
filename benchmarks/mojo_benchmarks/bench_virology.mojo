"""bench_virology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from virology import basic_reproduction_number, viral_doubling_time, plaque_forming_units, burst_size, eclipse_period, neutralisation_titre, antiviral_ic50, virus_decay_rate, infection_threshold, herd_immunity_threshold_viro
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

    var _acc_basic_reproduction_number: Float64 = 0.0
    var _t0_basic_reproduction_number = perf_counter_ns()
    for _ in range(N):
        _acc_basic_reproduction_number += basic_reproduction_number(0.5, 0.5, 0.5)
    var _t1_basic_reproduction_number = perf_counter_ns()
    var _ns_basic_reproduction_number = Float64(_t1_basic_reproduction_number - _t0_basic_reproduction_number) / Float64(N)
    print("MOJO_TIMING virology::basic_reproduction_number", _ns_basic_reproduction_number, _acc_basic_reproduction_number)
    var _acc_viral_doubling_time: Float64 = 0.0
    var _t0_viral_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_viral_doubling_time += viral_doubling_time(0.5)
    var _t1_viral_doubling_time = perf_counter_ns()
    var _ns_viral_doubling_time = Float64(_t1_viral_doubling_time - _t0_viral_doubling_time) / Float64(N)
    print("MOJO_TIMING virology::viral_doubling_time", _ns_viral_doubling_time, _acc_viral_doubling_time)
    var _acc_plaque_forming_units: Float64 = 0.0
    var _t0_plaque_forming_units = perf_counter_ns()
    for _ in range(N):
        _acc_plaque_forming_units += plaque_forming_units(0.5, 0.5, 0.5)
    var _t1_plaque_forming_units = perf_counter_ns()
    var _ns_plaque_forming_units = Float64(_t1_plaque_forming_units - _t0_plaque_forming_units) / Float64(N)
    print("MOJO_TIMING virology::plaque_forming_units", _ns_plaque_forming_units, _acc_plaque_forming_units)
    var _acc_burst_size: Float64 = 0.0
    var _t0_burst_size = perf_counter_ns()
    for _ in range(N):
        _acc_burst_size += burst_size(0.5, 0.5)
    var _t1_burst_size = perf_counter_ns()
    var _ns_burst_size = Float64(_t1_burst_size - _t0_burst_size) / Float64(N)
    print("MOJO_TIMING virology::burst_size", _ns_burst_size, _acc_burst_size)
    var _acc_eclipse_period: Float64 = 0.0
    var _t0_eclipse_period = perf_counter_ns()
    for _ in range(N):
        _acc_eclipse_period += eclipse_period(0.5, 0.5)
    var _t1_eclipse_period = perf_counter_ns()
    var _ns_eclipse_period = Float64(_t1_eclipse_period - _t0_eclipse_period) / Float64(N)
    print("MOJO_TIMING virology::eclipse_period", _ns_eclipse_period, _acc_eclipse_period)
    var _acc_neutralisation_titre: Float64 = 0.0
    var _t0_neutralisation_titre = perf_counter_ns()
    for _ in range(N):
        _acc_neutralisation_titre += neutralisation_titre(0.5)
    var _t1_neutralisation_titre = perf_counter_ns()
    var _ns_neutralisation_titre = Float64(_t1_neutralisation_titre - _t0_neutralisation_titre) / Float64(N)
    print("MOJO_TIMING virology::neutralisation_titre", _ns_neutralisation_titre, _acc_neutralisation_titre)
    var _acc_antiviral_ic50: Float64 = 0.0
    var _t0_antiviral_ic50 = perf_counter_ns()
    for _ in range(N):
        _acc_antiviral_ic50 += antiviral_ic50(0.5, 0.5, 0.5, 0.5)
    var _t1_antiviral_ic50 = perf_counter_ns()
    var _ns_antiviral_ic50 = Float64(_t1_antiviral_ic50 - _t0_antiviral_ic50) / Float64(N)
    print("MOJO_TIMING virology::antiviral_ic50", _ns_antiviral_ic50, _acc_antiviral_ic50)
    var _acc_virus_decay_rate: Float64 = 0.0
    var _t0_virus_decay_rate = perf_counter_ns()
    for _ in range(N):
        _acc_virus_decay_rate += virus_decay_rate(0.5, 0.5, 0.5)
    var _t1_virus_decay_rate = perf_counter_ns()
    var _ns_virus_decay_rate = Float64(_t1_virus_decay_rate - _t0_virus_decay_rate) / Float64(N)
    print("MOJO_TIMING virology::virus_decay_rate", _ns_virus_decay_rate, _acc_virus_decay_rate)
    var _acc_infection_threshold: Float64 = 0.0
    var _t0_infection_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_infection_threshold += infection_threshold(0.5, 0.5, 0.5)
    var _t1_infection_threshold = perf_counter_ns()
    var _ns_infection_threshold = Float64(_t1_infection_threshold - _t0_infection_threshold) / Float64(N)
    print("MOJO_TIMING virology::infection_threshold", _ns_infection_threshold, _acc_infection_threshold)
    var _acc_herd_immunity_threshold_viro: Float64 = 0.0
    var _t0_herd_immunity_threshold_viro = perf_counter_ns()
    for _ in range(N):
        _acc_herd_immunity_threshold_viro += herd_immunity_threshold_viro(0.5)
    var _t1_herd_immunity_threshold_viro = perf_counter_ns()
    var _ns_herd_immunity_threshold_viro = Float64(_t1_herd_immunity_threshold_viro - _t0_herd_immunity_threshold_viro) / Float64(N)
    print("MOJO_TIMING virology::herd_immunity_threshold_viro", _ns_herd_immunity_threshold_viro, _acc_herd_immunity_threshold_viro)
