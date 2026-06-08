"""bench_pest_control.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pest_control import economic_threshold, economic_injury_level, pest_density, trap_catch_rate, spray_coverage, dilution_rate, residual_effectiveness, resistance_ratio, biocontrol_release_rate, fumigation_ct, bait_station_density, population_reduction
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

    var _acc_economic_threshold: Float64 = 0.0
    var _t0_economic_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_economic_threshold += economic_threshold(0.5, 0.5, 0.5)
    var _t1_economic_threshold = perf_counter_ns()
    var _ns_economic_threshold = Float64(_t1_economic_threshold - _t0_economic_threshold) / Float64(N)
    print("MOJO_TIMING pest_control::economic_threshold", _ns_economic_threshold, _acc_economic_threshold)
    var _result_economic_threshold = economic_threshold(0.5, 0.5, 0.5)
    var _summary_economic_threshold = _summary_float64(_result_economic_threshold)
    print("MOJO_RESULT pest_control::economic_threshold", _summary_economic_threshold)
    var _acc_economic_injury_level: Float64 = 0.0
    var _t0_economic_injury_level = perf_counter_ns()
    for _ in range(N):
        _acc_economic_injury_level += economic_injury_level(0.5, 0.5)
    var _t1_economic_injury_level = perf_counter_ns()
    var _ns_economic_injury_level = Float64(_t1_economic_injury_level - _t0_economic_injury_level) / Float64(N)
    print("MOJO_TIMING pest_control::economic_injury_level", _ns_economic_injury_level, _acc_economic_injury_level)
    var _result_economic_injury_level = economic_injury_level(0.5, 0.5)
    var _summary_economic_injury_level = _summary_float64(_result_economic_injury_level)
    print("MOJO_RESULT pest_control::economic_injury_level", _summary_economic_injury_level)
    var _acc_pest_density: Float64 = 0.0
    var _t0_pest_density = perf_counter_ns()
    for _ in range(N):
        _acc_pest_density += pest_density(0.5, 0.5)
    var _t1_pest_density = perf_counter_ns()
    var _ns_pest_density = Float64(_t1_pest_density - _t0_pest_density) / Float64(N)
    print("MOJO_TIMING pest_control::pest_density", _ns_pest_density, _acc_pest_density)
    var _result_pest_density = pest_density(0.5, 0.5)
    var _summary_pest_density = _summary_float64(_result_pest_density)
    print("MOJO_RESULT pest_control::pest_density", _summary_pest_density)
    var _acc_trap_catch_rate: Float64 = 0.0
    var _t0_trap_catch_rate = perf_counter_ns()
    for _ in range(N):
        _acc_trap_catch_rate += trap_catch_rate(0.5, 0.5, 0.5)
    var _t1_trap_catch_rate = perf_counter_ns()
    var _ns_trap_catch_rate = Float64(_t1_trap_catch_rate - _t0_trap_catch_rate) / Float64(N)
    print("MOJO_TIMING pest_control::trap_catch_rate", _ns_trap_catch_rate, _acc_trap_catch_rate)
    var _result_trap_catch_rate = trap_catch_rate(0.5, 0.5, 0.5)
    var _summary_trap_catch_rate = _summary_float64(_result_trap_catch_rate)
    print("MOJO_RESULT pest_control::trap_catch_rate", _summary_trap_catch_rate)
    var _acc_spray_coverage: Float64 = 0.0
    var _t0_spray_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_spray_coverage += spray_coverage(0.5, 0.5)
    var _t1_spray_coverage = perf_counter_ns()
    var _ns_spray_coverage = Float64(_t1_spray_coverage - _t0_spray_coverage) / Float64(N)
    print("MOJO_TIMING pest_control::spray_coverage", _ns_spray_coverage, _acc_spray_coverage)
    var _result_spray_coverage = spray_coverage(0.5, 0.5)
    var _summary_spray_coverage = _summary_float64(_result_spray_coverage)
    print("MOJO_RESULT pest_control::spray_coverage", _summary_spray_coverage)
    var _acc_dilution_rate: Float64 = 0.0
    var _t0_dilution_rate = perf_counter_ns()
    for _ in range(N):
        _acc_dilution_rate += dilution_rate(0.5, 0.5)
    var _t1_dilution_rate = perf_counter_ns()
    var _ns_dilution_rate = Float64(_t1_dilution_rate - _t0_dilution_rate) / Float64(N)
    print("MOJO_TIMING pest_control::dilution_rate", _ns_dilution_rate, _acc_dilution_rate)
    var _result_dilution_rate = dilution_rate(0.5, 0.5)
    var _summary_dilution_rate = _summary_float64(_result_dilution_rate)
    print("MOJO_RESULT pest_control::dilution_rate", _summary_dilution_rate)
    var _acc_residual_effectiveness: Float64 = 0.0
    var _t0_residual_effectiveness = perf_counter_ns()
    for _ in range(N):
        _acc_residual_effectiveness += residual_effectiveness(0.5, 0.5, 0.5)
    var _t1_residual_effectiveness = perf_counter_ns()
    var _ns_residual_effectiveness = Float64(_t1_residual_effectiveness - _t0_residual_effectiveness) / Float64(N)
    print("MOJO_TIMING pest_control::residual_effectiveness", _ns_residual_effectiveness, _acc_residual_effectiveness)
    var _result_residual_effectiveness = residual_effectiveness(0.5, 0.5, 0.5)
    var _summary_residual_effectiveness = _summary_float64(_result_residual_effectiveness)
    print("MOJO_RESULT pest_control::residual_effectiveness", _summary_residual_effectiveness)
    var _acc_resistance_ratio: Float64 = 0.0
    var _t0_resistance_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_resistance_ratio += resistance_ratio(0.5, 0.5)
    var _t1_resistance_ratio = perf_counter_ns()
    var _ns_resistance_ratio = Float64(_t1_resistance_ratio - _t0_resistance_ratio) / Float64(N)
    print("MOJO_TIMING pest_control::resistance_ratio", _ns_resistance_ratio, _acc_resistance_ratio)
    var _result_resistance_ratio = resistance_ratio(0.5, 0.5)
    var _summary_resistance_ratio = _summary_float64(_result_resistance_ratio)
    print("MOJO_RESULT pest_control::resistance_ratio", _summary_resistance_ratio)
    var _acc_biocontrol_release_rate: Float64 = 0.0
    var _t0_biocontrol_release_rate = perf_counter_ns()
    for _ in range(N):
        _acc_biocontrol_release_rate += biocontrol_release_rate(0.5, 0.5, 0.5)
    var _t1_biocontrol_release_rate = perf_counter_ns()
    var _ns_biocontrol_release_rate = Float64(_t1_biocontrol_release_rate - _t0_biocontrol_release_rate) / Float64(N)
    print("MOJO_TIMING pest_control::biocontrol_release_rate", _ns_biocontrol_release_rate, _acc_biocontrol_release_rate)
    var _result_biocontrol_release_rate = biocontrol_release_rate(0.5, 0.5, 0.5)
    var _summary_biocontrol_release_rate = _summary_float64(_result_biocontrol_release_rate)
    print("MOJO_RESULT pest_control::biocontrol_release_rate", _summary_biocontrol_release_rate)
    var _acc_fumigation_ct: Float64 = 0.0
    var _t0_fumigation_ct = perf_counter_ns()
    for _ in range(N):
        _acc_fumigation_ct += fumigation_ct(0.5, 0.5)
    var _t1_fumigation_ct = perf_counter_ns()
    var _ns_fumigation_ct = Float64(_t1_fumigation_ct - _t0_fumigation_ct) / Float64(N)
    print("MOJO_TIMING pest_control::fumigation_ct", _ns_fumigation_ct, _acc_fumigation_ct)
    var _result_fumigation_ct = fumigation_ct(0.5, 0.5)
    var _summary_fumigation_ct = _summary_float64(_result_fumigation_ct)
    print("MOJO_RESULT pest_control::fumigation_ct", _summary_fumigation_ct)
    var _acc_bait_station_density: Float64 = 0.0
    var _t0_bait_station_density = perf_counter_ns()
    for _ in range(N):
        _acc_bait_station_density += bait_station_density(0.5, 0.5)
    var _t1_bait_station_density = perf_counter_ns()
    var _ns_bait_station_density = Float64(_t1_bait_station_density - _t0_bait_station_density) / Float64(N)
    print("MOJO_TIMING pest_control::bait_station_density", _ns_bait_station_density, _acc_bait_station_density)
    var _result_bait_station_density = bait_station_density(0.5, 0.5)
    var _summary_bait_station_density = _summary_float64(_result_bait_station_density)
    print("MOJO_RESULT pest_control::bait_station_density", _summary_bait_station_density)
    var _acc_population_reduction: Float64 = 0.0
    var _t0_population_reduction = perf_counter_ns()
    for _ in range(N):
        _acc_population_reduction += population_reduction(0.5, 0.5)
    var _t1_population_reduction = perf_counter_ns()
    var _ns_population_reduction = Float64(_t1_population_reduction - _t0_population_reduction) / Float64(N)
    print("MOJO_TIMING pest_control::population_reduction", _ns_population_reduction, _acc_population_reduction)
    var _result_population_reduction = population_reduction(0.5, 0.5)
    var _summary_population_reduction = _summary_float64(_result_population_reduction)
    print("MOJO_RESULT pest_control::population_reduction", _summary_population_reduction)
