"""bench_population_genetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from population_genetics import hardy_weinberg_freq, allele_frequency_drift, selection_coefficient, effective_population_size, nucleotide_diversity, tajimas_d_simplified, fst_wright, inbreeding_coefficient, mutation_load, linkage_disequilibrium
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

    var _acc_hardy_weinberg_freq: Float64 = 0.0
    var _t0_hardy_weinberg_freq = perf_counter_ns()
    for _ in range(N):
        _acc_hardy_weinberg_freq += hardy_weinberg_freq(0.5)
    var _t1_hardy_weinberg_freq = perf_counter_ns()
    var _ns_hardy_weinberg_freq = Float64(_t1_hardy_weinberg_freq - _t0_hardy_weinberg_freq) / Float64(N)
    print("MOJO_TIMING population_genetics::hardy_weinberg_freq", _ns_hardy_weinberg_freq, _acc_hardy_weinberg_freq)
    var _result_hardy_weinberg_freq = hardy_weinberg_freq(0.5)
    var _summary_hardy_weinberg_freq = _summary_float64(_result_hardy_weinberg_freq)
    print("MOJO_RESULT population_genetics::hardy_weinberg_freq", _summary_hardy_weinberg_freq)
    var _acc_allele_frequency_drift: Float64 = 0.0
    var _t0_allele_frequency_drift = perf_counter_ns()
    for _ in range(N):
        _acc_allele_frequency_drift += allele_frequency_drift(0.5, 0.5)
    var _t1_allele_frequency_drift = perf_counter_ns()
    var _ns_allele_frequency_drift = Float64(_t1_allele_frequency_drift - _t0_allele_frequency_drift) / Float64(N)
    print("MOJO_TIMING population_genetics::allele_frequency_drift", _ns_allele_frequency_drift, _acc_allele_frequency_drift)
    var _result_allele_frequency_drift = allele_frequency_drift(0.5, 0.5)
    var _summary_allele_frequency_drift = _summary_float64(_result_allele_frequency_drift)
    print("MOJO_RESULT population_genetics::allele_frequency_drift", _summary_allele_frequency_drift)
    var _acc_selection_coefficient: Float64 = 0.0
    var _t0_selection_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_selection_coefficient += selection_coefficient(0.5, 0.5, 0.5)
    var _t1_selection_coefficient = perf_counter_ns()
    var _ns_selection_coefficient = Float64(_t1_selection_coefficient - _t0_selection_coefficient) / Float64(N)
    print("MOJO_TIMING population_genetics::selection_coefficient", _ns_selection_coefficient, _acc_selection_coefficient)
    var _result_selection_coefficient = selection_coefficient(0.5, 0.5, 0.5)
    var _summary_selection_coefficient = _summary_float64(_result_selection_coefficient)
    print("MOJO_RESULT population_genetics::selection_coefficient", _summary_selection_coefficient)
    var _acc_effective_population_size: Float64 = 0.0
    var _t0_effective_population_size = perf_counter_ns()
    for _ in range(N):
        _acc_effective_population_size += effective_population_size(0.5, 0.5)
    var _t1_effective_population_size = perf_counter_ns()
    var _ns_effective_population_size = Float64(_t1_effective_population_size - _t0_effective_population_size) / Float64(N)
    print("MOJO_TIMING population_genetics::effective_population_size", _ns_effective_population_size, _acc_effective_population_size)
    var _result_effective_population_size = effective_population_size(0.5, 0.5)
    var _summary_effective_population_size = _summary_float64(_result_effective_population_size)
    print("MOJO_RESULT population_genetics::effective_population_size", _summary_effective_population_size)
    var _acc_nucleotide_diversity: Float64 = 0.0
    var _t0_nucleotide_diversity = perf_counter_ns()
    for _ in range(N):
        _acc_nucleotide_diversity += nucleotide_diversity(0.5, 0.5)
    var _t1_nucleotide_diversity = perf_counter_ns()
    var _ns_nucleotide_diversity = Float64(_t1_nucleotide_diversity - _t0_nucleotide_diversity) / Float64(N)
    print("MOJO_TIMING population_genetics::nucleotide_diversity", _ns_nucleotide_diversity, _acc_nucleotide_diversity)
    var _result_nucleotide_diversity = nucleotide_diversity(0.5, 0.5)
    var _summary_nucleotide_diversity = _summary_float64(_result_nucleotide_diversity)
    print("MOJO_RESULT population_genetics::nucleotide_diversity", _summary_nucleotide_diversity)
    var _acc_tajimas_d_simplified: Float64 = 0.0
    var _t0_tajimas_d_simplified = perf_counter_ns()
    for _ in range(N):
        _acc_tajimas_d_simplified += tajimas_d_simplified(0.5, 0.5, 0.5)
    var _t1_tajimas_d_simplified = perf_counter_ns()
    var _ns_tajimas_d_simplified = Float64(_t1_tajimas_d_simplified - _t0_tajimas_d_simplified) / Float64(N)
    print("MOJO_TIMING population_genetics::tajimas_d_simplified", _ns_tajimas_d_simplified, _acc_tajimas_d_simplified)
    var _result_tajimas_d_simplified = tajimas_d_simplified(0.5, 0.5, 0.5)
    var _summary_tajimas_d_simplified = _summary_float64(_result_tajimas_d_simplified)
    print("MOJO_RESULT population_genetics::tajimas_d_simplified", _summary_tajimas_d_simplified)
    var _acc_fst_wright: Float64 = 0.0
    var _t0_fst_wright = perf_counter_ns()
    for _ in range(N):
        _acc_fst_wright += fst_wright(0.5, 0.5)
    var _t1_fst_wright = perf_counter_ns()
    var _ns_fst_wright = Float64(_t1_fst_wright - _t0_fst_wright) / Float64(N)
    print("MOJO_TIMING population_genetics::fst_wright", _ns_fst_wright, _acc_fst_wright)
    var _result_fst_wright = fst_wright(0.5, 0.5)
    var _summary_fst_wright = _summary_float64(_result_fst_wright)
    print("MOJO_RESULT population_genetics::fst_wright", _summary_fst_wright)
    var _acc_inbreeding_coefficient: Float64 = 0.0
    var _t0_inbreeding_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_inbreeding_coefficient += inbreeding_coefficient(0.5, 0.5)
    var _t1_inbreeding_coefficient = perf_counter_ns()
    var _ns_inbreeding_coefficient = Float64(_t1_inbreeding_coefficient - _t0_inbreeding_coefficient) / Float64(N)
    print("MOJO_TIMING population_genetics::inbreeding_coefficient", _ns_inbreeding_coefficient, _acc_inbreeding_coefficient)
    var _result_inbreeding_coefficient = inbreeding_coefficient(0.5, 0.5)
    var _summary_inbreeding_coefficient = _summary_float64(_result_inbreeding_coefficient)
    print("MOJO_RESULT population_genetics::inbreeding_coefficient", _summary_inbreeding_coefficient)
    var _acc_mutation_load: Float64 = 0.0
    var _t0_mutation_load = perf_counter_ns()
    for _ in range(N):
        _acc_mutation_load += mutation_load(0.5, 0.5)
    var _t1_mutation_load = perf_counter_ns()
    var _ns_mutation_load = Float64(_t1_mutation_load - _t0_mutation_load) / Float64(N)
    print("MOJO_TIMING population_genetics::mutation_load", _ns_mutation_load, _acc_mutation_load)
    var _result_mutation_load = mutation_load(0.5, 0.5)
    var _summary_mutation_load = _summary_float64(_result_mutation_load)
    print("MOJO_RESULT population_genetics::mutation_load", _summary_mutation_load)
    var _acc_linkage_disequilibrium: Float64 = 0.0
    var _t0_linkage_disequilibrium = perf_counter_ns()
    for _ in range(N):
        _acc_linkage_disequilibrium += linkage_disequilibrium(0.5, 0.5, 0.5)
    var _t1_linkage_disequilibrium = perf_counter_ns()
    var _ns_linkage_disequilibrium = Float64(_t1_linkage_disequilibrium - _t0_linkage_disequilibrium) / Float64(N)
    print("MOJO_TIMING population_genetics::linkage_disequilibrium", _ns_linkage_disequilibrium, _acc_linkage_disequilibrium)
    var _result_linkage_disequilibrium = linkage_disequilibrium(0.5, 0.5, 0.5)
    var _summary_linkage_disequilibrium = _summary_float64(_result_linkage_disequilibrium)
    print("MOJO_RESULT population_genetics::linkage_disequilibrium", _summary_linkage_disequilibrium)
