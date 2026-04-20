"""bench_pest_control.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pest_control import economic_threshold, economic_injury_level, pest_density, trap_catch_rate, spray_coverage, dilution_rate, residual_effectiveness, resistance_ratio, biocontrol_release_rate, fumigation_ct, bait_station_density, population_reduction
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

    var _acc_economic_threshold: Float64 = 0.0
    var _t0_economic_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_economic_threshold += economic_threshold(0.5, 0.5, 0.5)
    var _t1_economic_threshold = perf_counter_ns()
    var _ns_economic_threshold = Float64(_t1_economic_threshold - _t0_economic_threshold) / Float64(N)
    print("MOJO_TIMING pest_control::economic_threshold", _ns_economic_threshold, _acc_economic_threshold)
    var _acc_economic_injury_level: Float64 = 0.0
    var _t0_economic_injury_level = perf_counter_ns()
    for _ in range(N):
        _acc_economic_injury_level += economic_injury_level(0.5, 0.5)
    var _t1_economic_injury_level = perf_counter_ns()
    var _ns_economic_injury_level = Float64(_t1_economic_injury_level - _t0_economic_injury_level) / Float64(N)
    print("MOJO_TIMING pest_control::economic_injury_level", _ns_economic_injury_level, _acc_economic_injury_level)
    var _acc_pest_density: Float64 = 0.0
    var _t0_pest_density = perf_counter_ns()
    for _ in range(N):
        _acc_pest_density += pest_density(0.5, 0.5)
    var _t1_pest_density = perf_counter_ns()
    var _ns_pest_density = Float64(_t1_pest_density - _t0_pest_density) / Float64(N)
    print("MOJO_TIMING pest_control::pest_density", _ns_pest_density, _acc_pest_density)
    var _acc_trap_catch_rate: Float64 = 0.0
    var _t0_trap_catch_rate = perf_counter_ns()
    for _ in range(N):
        _acc_trap_catch_rate += trap_catch_rate(0.5, 0.5, 0.5)
    var _t1_trap_catch_rate = perf_counter_ns()
    var _ns_trap_catch_rate = Float64(_t1_trap_catch_rate - _t0_trap_catch_rate) / Float64(N)
    print("MOJO_TIMING pest_control::trap_catch_rate", _ns_trap_catch_rate, _acc_trap_catch_rate)
    var _acc_spray_coverage: Float64 = 0.0
    var _t0_spray_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_spray_coverage += spray_coverage(0.5, 0.5)
    var _t1_spray_coverage = perf_counter_ns()
    var _ns_spray_coverage = Float64(_t1_spray_coverage - _t0_spray_coverage) / Float64(N)
    print("MOJO_TIMING pest_control::spray_coverage", _ns_spray_coverage, _acc_spray_coverage)
    var _acc_dilution_rate: Float64 = 0.0
    var _t0_dilution_rate = perf_counter_ns()
    for _ in range(N):
        _acc_dilution_rate += dilution_rate(0.5, 0.5)
    var _t1_dilution_rate = perf_counter_ns()
    var _ns_dilution_rate = Float64(_t1_dilution_rate - _t0_dilution_rate) / Float64(N)
    print("MOJO_TIMING pest_control::dilution_rate", _ns_dilution_rate, _acc_dilution_rate)
    var _acc_residual_effectiveness: Float64 = 0.0
    var _t0_residual_effectiveness = perf_counter_ns()
    for _ in range(N):
        _acc_residual_effectiveness += residual_effectiveness(0.5, 0.5, 0.5)
    var _t1_residual_effectiveness = perf_counter_ns()
    var _ns_residual_effectiveness = Float64(_t1_residual_effectiveness - _t0_residual_effectiveness) / Float64(N)
    print("MOJO_TIMING pest_control::residual_effectiveness", _ns_residual_effectiveness, _acc_residual_effectiveness)
    var _acc_resistance_ratio: Float64 = 0.0
    var _t0_resistance_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_resistance_ratio += resistance_ratio(0.5, 0.5)
    var _t1_resistance_ratio = perf_counter_ns()
    var _ns_resistance_ratio = Float64(_t1_resistance_ratio - _t0_resistance_ratio) / Float64(N)
    print("MOJO_TIMING pest_control::resistance_ratio", _ns_resistance_ratio, _acc_resistance_ratio)
    var _acc_biocontrol_release_rate: Float64 = 0.0
    var _t0_biocontrol_release_rate = perf_counter_ns()
    for _ in range(N):
        _acc_biocontrol_release_rate += biocontrol_release_rate(0.5, 0.5, 0.5)
    var _t1_biocontrol_release_rate = perf_counter_ns()
    var _ns_biocontrol_release_rate = Float64(_t1_biocontrol_release_rate - _t0_biocontrol_release_rate) / Float64(N)
    print("MOJO_TIMING pest_control::biocontrol_release_rate", _ns_biocontrol_release_rate, _acc_biocontrol_release_rate)
    var _acc_fumigation_ct: Float64 = 0.0
    var _t0_fumigation_ct = perf_counter_ns()
    for _ in range(N):
        _acc_fumigation_ct += fumigation_ct(0.5, 0.5)
    var _t1_fumigation_ct = perf_counter_ns()
    var _ns_fumigation_ct = Float64(_t1_fumigation_ct - _t0_fumigation_ct) / Float64(N)
    print("MOJO_TIMING pest_control::fumigation_ct", _ns_fumigation_ct, _acc_fumigation_ct)
    var _acc_bait_station_density: Float64 = 0.0
    var _t0_bait_station_density = perf_counter_ns()
    for _ in range(N):
        _acc_bait_station_density += bait_station_density(0.5, 0.5)
    var _t1_bait_station_density = perf_counter_ns()
    var _ns_bait_station_density = Float64(_t1_bait_station_density - _t0_bait_station_density) / Float64(N)
    print("MOJO_TIMING pest_control::bait_station_density", _ns_bait_station_density, _acc_bait_station_density)
    var _acc_population_reduction: Float64 = 0.0
    var _t0_population_reduction = perf_counter_ns()
    for _ in range(N):
        _acc_population_reduction += population_reduction(0.5, 0.5)
    var _t1_population_reduction = perf_counter_ns()
    var _ns_population_reduction = Float64(_t1_population_reduction - _t0_population_reduction) / Float64(N)
    print("MOJO_TIMING pest_control::population_reduction", _ns_population_reduction, _acc_population_reduction)
