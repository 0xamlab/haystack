"""bench_palynology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from palynology import pollen_concentration, pollen_accumulation_rate, taxa_diversity_index, relative_pollen_percentage, r_value_correction, arboreal_non_arboreal_ratio, pollen_influx, spore_germination_index, pollen_productivity_estimate, pollen_transport_distance
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

    var _acc_pollen_concentration: Float64 = 0.0
    var _t0_pollen_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_concentration += pollen_concentration(0.5, 0.5, 0.5, 0.5)
    var _t1_pollen_concentration = perf_counter_ns()
    var _ns_pollen_concentration = Float64(_t1_pollen_concentration - _t0_pollen_concentration) / Float64(N)
    print("MOJO_TIMING palynology::pollen_concentration", _ns_pollen_concentration, _acc_pollen_concentration)
    var _result_pollen_concentration = pollen_concentration(0.5, 0.5, 0.5, 0.5)
    var _summary_pollen_concentration = _summary_float64(_result_pollen_concentration)
    print("MOJO_RESULT palynology::pollen_concentration", _summary_pollen_concentration)
    var _acc_pollen_accumulation_rate: Float64 = 0.0
    var _t0_pollen_accumulation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_accumulation_rate += pollen_accumulation_rate(0.5, 0.5)
    var _t1_pollen_accumulation_rate = perf_counter_ns()
    var _ns_pollen_accumulation_rate = Float64(_t1_pollen_accumulation_rate - _t0_pollen_accumulation_rate) / Float64(N)
    print("MOJO_TIMING palynology::pollen_accumulation_rate", _ns_pollen_accumulation_rate, _acc_pollen_accumulation_rate)
    var _result_pollen_accumulation_rate = pollen_accumulation_rate(0.5, 0.5)
    var _summary_pollen_accumulation_rate = _summary_float64(_result_pollen_accumulation_rate)
    print("MOJO_RESULT palynology::pollen_accumulation_rate", _summary_pollen_accumulation_rate)
    var _acc_taxa_diversity_index: Float64 = 0.0
    var _t0_taxa_diversity_index = perf_counter_ns()
    for _ in range(N):
        _acc_taxa_diversity_index += taxa_diversity_index(0.5, 0.5)
    var _t1_taxa_diversity_index = perf_counter_ns()
    var _ns_taxa_diversity_index = Float64(_t1_taxa_diversity_index - _t0_taxa_diversity_index) / Float64(N)
    print("MOJO_TIMING palynology::taxa_diversity_index", _ns_taxa_diversity_index, _acc_taxa_diversity_index)
    var _result_taxa_diversity_index = taxa_diversity_index(0.5, 0.5)
    var _summary_taxa_diversity_index = _summary_float64(_result_taxa_diversity_index)
    print("MOJO_RESULT palynology::taxa_diversity_index", _summary_taxa_diversity_index)
    var _acc_relative_pollen_percentage: Float64 = 0.0
    var _t0_relative_pollen_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_relative_pollen_percentage += relative_pollen_percentage(0.5, 0.5)
    var _t1_relative_pollen_percentage = perf_counter_ns()
    var _ns_relative_pollen_percentage = Float64(_t1_relative_pollen_percentage - _t0_relative_pollen_percentage) / Float64(N)
    print("MOJO_TIMING palynology::relative_pollen_percentage", _ns_relative_pollen_percentage, _acc_relative_pollen_percentage)
    var _result_relative_pollen_percentage = relative_pollen_percentage(0.5, 0.5)
    var _summary_relative_pollen_percentage = _summary_float64(_result_relative_pollen_percentage)
    print("MOJO_RESULT palynology::relative_pollen_percentage", _summary_relative_pollen_percentage)
    var _acc_r_value_correction: Float64 = 0.0
    var _t0_r_value_correction = perf_counter_ns()
    for _ in range(N):
        _acc_r_value_correction += r_value_correction(0.5, 0.5)
    var _t1_r_value_correction = perf_counter_ns()
    var _ns_r_value_correction = Float64(_t1_r_value_correction - _t0_r_value_correction) / Float64(N)
    print("MOJO_TIMING palynology::r_value_correction", _ns_r_value_correction, _acc_r_value_correction)
    var _result_r_value_correction = r_value_correction(0.5, 0.5)
    var _summary_r_value_correction = _summary_float64(_result_r_value_correction)
    print("MOJO_RESULT palynology::r_value_correction", _summary_r_value_correction)
    var _acc_arboreal_non_arboreal_ratio: Float64 = 0.0
    var _t0_arboreal_non_arboreal_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_arboreal_non_arboreal_ratio += arboreal_non_arboreal_ratio(0.5, 0.5)
    var _t1_arboreal_non_arboreal_ratio = perf_counter_ns()
    var _ns_arboreal_non_arboreal_ratio = Float64(_t1_arboreal_non_arboreal_ratio - _t0_arboreal_non_arboreal_ratio) / Float64(N)
    print("MOJO_TIMING palynology::arboreal_non_arboreal_ratio", _ns_arboreal_non_arboreal_ratio, _acc_arboreal_non_arboreal_ratio)
    var _result_arboreal_non_arboreal_ratio = arboreal_non_arboreal_ratio(0.5, 0.5)
    var _summary_arboreal_non_arboreal_ratio = _summary_float64(_result_arboreal_non_arboreal_ratio)
    print("MOJO_RESULT palynology::arboreal_non_arboreal_ratio", _summary_arboreal_non_arboreal_ratio)
    var _acc_pollen_influx: Float64 = 0.0
    var _t0_pollen_influx = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_influx += pollen_influx(0.5, 0.5)
    var _t1_pollen_influx = perf_counter_ns()
    var _ns_pollen_influx = Float64(_t1_pollen_influx - _t0_pollen_influx) / Float64(N)
    print("MOJO_TIMING palynology::pollen_influx", _ns_pollen_influx, _acc_pollen_influx)
    var _result_pollen_influx = pollen_influx(0.5, 0.5)
    var _summary_pollen_influx = _summary_float64(_result_pollen_influx)
    print("MOJO_RESULT palynology::pollen_influx", _summary_pollen_influx)
    var _acc_spore_germination_index: Float64 = 0.0
    var _t0_spore_germination_index = perf_counter_ns()
    for _ in range(N):
        _acc_spore_germination_index += spore_germination_index(0.5, 0.5)
    var _t1_spore_germination_index = perf_counter_ns()
    var _ns_spore_germination_index = Float64(_t1_spore_germination_index - _t0_spore_germination_index) / Float64(N)
    print("MOJO_TIMING palynology::spore_germination_index", _ns_spore_germination_index, _acc_spore_germination_index)
    var _result_spore_germination_index = spore_germination_index(0.5, 0.5)
    var _summary_spore_germination_index = _summary_float64(_result_spore_germination_index)
    print("MOJO_RESULT palynology::spore_germination_index", _summary_spore_germination_index)
    var _acc_pollen_productivity_estimate: Float64 = 0.0
    var _t0_pollen_productivity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_productivity_estimate += pollen_productivity_estimate(0.5, 0.5, 0.5)
    var _t1_pollen_productivity_estimate = perf_counter_ns()
    var _ns_pollen_productivity_estimate = Float64(_t1_pollen_productivity_estimate - _t0_pollen_productivity_estimate) / Float64(N)
    print("MOJO_TIMING palynology::pollen_productivity_estimate", _ns_pollen_productivity_estimate, _acc_pollen_productivity_estimate)
    var _result_pollen_productivity_estimate = pollen_productivity_estimate(0.5, 0.5, 0.5)
    var _summary_pollen_productivity_estimate = _summary_float64(_result_pollen_productivity_estimate)
    print("MOJO_RESULT palynology::pollen_productivity_estimate", _summary_pollen_productivity_estimate)
    var _acc_pollen_transport_distance: Float64 = 0.0
    var _t0_pollen_transport_distance = perf_counter_ns()
    for _ in range(N):
        _acc_pollen_transport_distance += pollen_transport_distance(0.5, 0.5, 0.5)
    var _t1_pollen_transport_distance = perf_counter_ns()
    var _ns_pollen_transport_distance = Float64(_t1_pollen_transport_distance - _t0_pollen_transport_distance) / Float64(N)
    print("MOJO_TIMING palynology::pollen_transport_distance", _ns_pollen_transport_distance, _acc_pollen_transport_distance)
    var _result_pollen_transport_distance = pollen_transport_distance(0.5, 0.5, 0.5)
    var _summary_pollen_transport_distance = _summary_float64(_result_pollen_transport_distance)
    print("MOJO_RESULT palynology::pollen_transport_distance", _summary_pollen_transport_distance)
