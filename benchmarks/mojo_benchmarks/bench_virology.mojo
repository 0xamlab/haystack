"""bench_virology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from virology import basic_reproduction_number, viral_doubling_time, plaque_forming_units, burst_size, eclipse_period, neutralisation_titre, antiviral_ic50, virus_decay_rate, infection_threshold, herd_immunity_threshold_viro
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_basic_reproduction_number: Float64 = 0.0
    var _t0_basic_reproduction_number = perf_counter_ns()
    for _ in range(N):
        _acc_basic_reproduction_number += basic_reproduction_number(0.5, 0.5, 0.5)
    var _t1_basic_reproduction_number = perf_counter_ns()
    var _ns_basic_reproduction_number = Float64(_t1_basic_reproduction_number - _t0_basic_reproduction_number) / Float64(N)
    print("MOJO_TIMING virology::basic_reproduction_number", _ns_basic_reproduction_number, _acc_basic_reproduction_number)
    var _result_basic_reproduction_number = basic_reproduction_number(0.5, 0.5, 0.5)
    var _summary_basic_reproduction_number = _summary_float64(_result_basic_reproduction_number)
    print("MOJO_RESULT virology::basic_reproduction_number", _summary_basic_reproduction_number)
    var _acc_viral_doubling_time: Float64 = 0.0
    var _t0_viral_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_viral_doubling_time += viral_doubling_time(0.5)
    var _t1_viral_doubling_time = perf_counter_ns()
    var _ns_viral_doubling_time = Float64(_t1_viral_doubling_time - _t0_viral_doubling_time) / Float64(N)
    print("MOJO_TIMING virology::viral_doubling_time", _ns_viral_doubling_time, _acc_viral_doubling_time)
    var _result_viral_doubling_time = viral_doubling_time(0.5)
    var _summary_viral_doubling_time = _summary_float64(_result_viral_doubling_time)
    print("MOJO_RESULT virology::viral_doubling_time", _summary_viral_doubling_time)
    var _acc_plaque_forming_units: Float64 = 0.0
    var _t0_plaque_forming_units = perf_counter_ns()
    for _ in range(N):
        _acc_plaque_forming_units += plaque_forming_units(0.5, 0.5, 0.5)
    var _t1_plaque_forming_units = perf_counter_ns()
    var _ns_plaque_forming_units = Float64(_t1_plaque_forming_units - _t0_plaque_forming_units) / Float64(N)
    print("MOJO_TIMING virology::plaque_forming_units", _ns_plaque_forming_units, _acc_plaque_forming_units)
    var _result_plaque_forming_units = plaque_forming_units(0.5, 0.5, 0.5)
    var _summary_plaque_forming_units = _summary_float64(_result_plaque_forming_units)
    print("MOJO_RESULT virology::plaque_forming_units", _summary_plaque_forming_units)
    var _acc_burst_size: Float64 = 0.0
    var _t0_burst_size = perf_counter_ns()
    for _ in range(N):
        _acc_burst_size += burst_size(0.5, 0.5)
    var _t1_burst_size = perf_counter_ns()
    var _ns_burst_size = Float64(_t1_burst_size - _t0_burst_size) / Float64(N)
    print("MOJO_TIMING virology::burst_size", _ns_burst_size, _acc_burst_size)
    var _result_burst_size = burst_size(0.5, 0.5)
    var _summary_burst_size = _summary_float64(_result_burst_size)
    print("MOJO_RESULT virology::burst_size", _summary_burst_size)
    var _acc_eclipse_period: Float64 = 0.0
    var _t0_eclipse_period = perf_counter_ns()
    for _ in range(N):
        _acc_eclipse_period += eclipse_period(0.5, 0.5)
    var _t1_eclipse_period = perf_counter_ns()
    var _ns_eclipse_period = Float64(_t1_eclipse_period - _t0_eclipse_period) / Float64(N)
    print("MOJO_TIMING virology::eclipse_period", _ns_eclipse_period, _acc_eclipse_period)
    var _result_eclipse_period = eclipse_period(0.5, 0.5)
    var _summary_eclipse_period = _summary_float64(_result_eclipse_period)
    print("MOJO_RESULT virology::eclipse_period", _summary_eclipse_period)
    var _acc_neutralisation_titre: Float64 = 0.0
    var _t0_neutralisation_titre = perf_counter_ns()
    for _ in range(N):
        _acc_neutralisation_titre += neutralisation_titre(0.5)
    var _t1_neutralisation_titre = perf_counter_ns()
    var _ns_neutralisation_titre = Float64(_t1_neutralisation_titre - _t0_neutralisation_titre) / Float64(N)
    print("MOJO_TIMING virology::neutralisation_titre", _ns_neutralisation_titre, _acc_neutralisation_titre)
    var _result_neutralisation_titre = neutralisation_titre(0.5)
    var _summary_neutralisation_titre = _summary_float64(_result_neutralisation_titre)
    print("MOJO_RESULT virology::neutralisation_titre", _summary_neutralisation_titre)
    var _acc_antiviral_ic50: Float64 = 0.0
    var _t0_antiviral_ic50 = perf_counter_ns()
    for _ in range(N):
        _acc_antiviral_ic50 += antiviral_ic50(0.5, 0.5, 0.5, 0.5)
    var _t1_antiviral_ic50 = perf_counter_ns()
    var _ns_antiviral_ic50 = Float64(_t1_antiviral_ic50 - _t0_antiviral_ic50) / Float64(N)
    print("MOJO_TIMING virology::antiviral_ic50", _ns_antiviral_ic50, _acc_antiviral_ic50)
    var _result_antiviral_ic50 = antiviral_ic50(0.5, 0.5, 0.5, 0.5)
    var _summary_antiviral_ic50 = _summary_float64(_result_antiviral_ic50)
    print("MOJO_RESULT virology::antiviral_ic50", _summary_antiviral_ic50)
    var _acc_virus_decay_rate: Float64 = 0.0
    var _t0_virus_decay_rate = perf_counter_ns()
    for _ in range(N):
        _acc_virus_decay_rate += virus_decay_rate(0.5, 0.5, 0.5)
    var _t1_virus_decay_rate = perf_counter_ns()
    var _ns_virus_decay_rate = Float64(_t1_virus_decay_rate - _t0_virus_decay_rate) / Float64(N)
    print("MOJO_TIMING virology::virus_decay_rate", _ns_virus_decay_rate, _acc_virus_decay_rate)
    var _result_virus_decay_rate = virus_decay_rate(0.5, 0.5, 0.5)
    var _summary_virus_decay_rate = _summary_float64(_result_virus_decay_rate)
    print("MOJO_RESULT virology::virus_decay_rate", _summary_virus_decay_rate)
    var _acc_infection_threshold: Float64 = 0.0
    var _t0_infection_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_infection_threshold += infection_threshold(0.5, 0.5, 0.5)
    var _t1_infection_threshold = perf_counter_ns()
    var _ns_infection_threshold = Float64(_t1_infection_threshold - _t0_infection_threshold) / Float64(N)
    print("MOJO_TIMING virology::infection_threshold", _ns_infection_threshold, _acc_infection_threshold)
    var _result_infection_threshold = infection_threshold(0.5, 0.5, 0.5)
    var _summary_infection_threshold = _summary_float64(_result_infection_threshold)
    print("MOJO_RESULT virology::infection_threshold", _summary_infection_threshold)
    var _acc_herd_immunity_threshold_viro: Float64 = 0.0
    var _t0_herd_immunity_threshold_viro = perf_counter_ns()
    for _ in range(N):
        _acc_herd_immunity_threshold_viro += herd_immunity_threshold_viro(0.5)
    var _t1_herd_immunity_threshold_viro = perf_counter_ns()
    var _ns_herd_immunity_threshold_viro = Float64(_t1_herd_immunity_threshold_viro - _t0_herd_immunity_threshold_viro) / Float64(N)
    print("MOJO_TIMING virology::herd_immunity_threshold_viro", _ns_herd_immunity_threshold_viro, _acc_herd_immunity_threshold_viro)
    var _result_herd_immunity_threshold_viro = herd_immunity_threshold_viro(0.5)
    var _summary_herd_immunity_threshold_viro = _summary_float64(_result_herd_immunity_threshold_viro)
    print("MOJO_RESULT virology::herd_immunity_threshold_viro", _summary_herd_immunity_threshold_viro)
