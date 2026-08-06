"""bench_epigenetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from epigenetics import methylation_index, dna_methylation_age, histone_acetylation_ratio, chromatin_accessibility, imprinting_ratio, cpg_observed_expected, gene_silencing_efficiency, enhancer_activity_index, polycomb_enrichment, transcription_factor_occupancy
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

    var _acc_methylation_index: Float64 = 0.0
    var _t0_methylation_index = perf_counter_ns()
    for _ in range(N):
        _acc_methylation_index += methylation_index(0.5, 0.5)
    var _t1_methylation_index = perf_counter_ns()
    var _ns_methylation_index = Float64(_t1_methylation_index - _t0_methylation_index) / Float64(N)
    print("MOJO_TIMING epigenetics::methylation_index", _ns_methylation_index, _acc_methylation_index)
    var _result_methylation_index = methylation_index(0.5, 0.5)
    var _summary_methylation_index = _summary_float64(_result_methylation_index)
    print("MOJO_RESULT epigenetics::methylation_index", _summary_methylation_index)
    var _acc_dna_methylation_age: Float64 = 0.0
    var _t0_dna_methylation_age = perf_counter_ns()
    for _ in range(N):
        _acc_dna_methylation_age += dna_methylation_age(0.5, 0.5, 0.5)
    var _t1_dna_methylation_age = perf_counter_ns()
    var _ns_dna_methylation_age = Float64(_t1_dna_methylation_age - _t0_dna_methylation_age) / Float64(N)
    print("MOJO_TIMING epigenetics::dna_methylation_age", _ns_dna_methylation_age, _acc_dna_methylation_age)
    var _result_dna_methylation_age = dna_methylation_age(0.5, 0.5, 0.5)
    var _summary_dna_methylation_age = _summary_float64(_result_dna_methylation_age)
    print("MOJO_RESULT epigenetics::dna_methylation_age", _summary_dna_methylation_age)
    var _acc_histone_acetylation_ratio: Float64 = 0.0
    var _t0_histone_acetylation_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_histone_acetylation_ratio += histone_acetylation_ratio(0.5, 0.5)
    var _t1_histone_acetylation_ratio = perf_counter_ns()
    var _ns_histone_acetylation_ratio = Float64(_t1_histone_acetylation_ratio - _t0_histone_acetylation_ratio) / Float64(N)
    print("MOJO_TIMING epigenetics::histone_acetylation_ratio", _ns_histone_acetylation_ratio, _acc_histone_acetylation_ratio)
    var _result_histone_acetylation_ratio = histone_acetylation_ratio(0.5, 0.5)
    var _summary_histone_acetylation_ratio = _summary_float64(_result_histone_acetylation_ratio)
    print("MOJO_RESULT epigenetics::histone_acetylation_ratio", _summary_histone_acetylation_ratio)
    var _acc_chromatin_accessibility: Float64 = 0.0
    var _t0_chromatin_accessibility = perf_counter_ns()
    for _ in range(N):
        _acc_chromatin_accessibility += chromatin_accessibility(0.5, 0.5, 0.5)
    var _t1_chromatin_accessibility = perf_counter_ns()
    var _ns_chromatin_accessibility = Float64(_t1_chromatin_accessibility - _t0_chromatin_accessibility) / Float64(N)
    print("MOJO_TIMING epigenetics::chromatin_accessibility", _ns_chromatin_accessibility, _acc_chromatin_accessibility)
    var _result_chromatin_accessibility = chromatin_accessibility(0.5, 0.5, 0.5)
    var _summary_chromatin_accessibility = _summary_float64(_result_chromatin_accessibility)
    print("MOJO_RESULT epigenetics::chromatin_accessibility", _summary_chromatin_accessibility)
    var _acc_imprinting_ratio: Float64 = 0.0
    var _t0_imprinting_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_imprinting_ratio += imprinting_ratio(0.5, 0.5)
    var _t1_imprinting_ratio = perf_counter_ns()
    var _ns_imprinting_ratio = Float64(_t1_imprinting_ratio - _t0_imprinting_ratio) / Float64(N)
    print("MOJO_TIMING epigenetics::imprinting_ratio", _ns_imprinting_ratio, _acc_imprinting_ratio)
    var _result_imprinting_ratio = imprinting_ratio(0.5, 0.5)
    var _summary_imprinting_ratio = _summary_float64(_result_imprinting_ratio)
    print("MOJO_RESULT epigenetics::imprinting_ratio", _summary_imprinting_ratio)
    var _acc_cpg_observed_expected: Float64 = 0.0
    var _t0_cpg_observed_expected = perf_counter_ns()
    for _ in range(N):
        _acc_cpg_observed_expected += cpg_observed_expected(0.5, 0.5, 0.5, 0.5)
    var _t1_cpg_observed_expected = perf_counter_ns()
    var _ns_cpg_observed_expected = Float64(_t1_cpg_observed_expected - _t0_cpg_observed_expected) / Float64(N)
    print("MOJO_TIMING epigenetics::cpg_observed_expected", _ns_cpg_observed_expected, _acc_cpg_observed_expected)
    var _result_cpg_observed_expected = cpg_observed_expected(0.5, 0.5, 0.5, 0.5)
    var _summary_cpg_observed_expected = _summary_float64(_result_cpg_observed_expected)
    print("MOJO_RESULT epigenetics::cpg_observed_expected", _summary_cpg_observed_expected)
    var _acc_gene_silencing_efficiency: Float64 = 0.0
    var _t0_gene_silencing_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_gene_silencing_efficiency += gene_silencing_efficiency(0.5, 0.5)
    var _t1_gene_silencing_efficiency = perf_counter_ns()
    var _ns_gene_silencing_efficiency = Float64(_t1_gene_silencing_efficiency - _t0_gene_silencing_efficiency) / Float64(N)
    print("MOJO_TIMING epigenetics::gene_silencing_efficiency", _ns_gene_silencing_efficiency, _acc_gene_silencing_efficiency)
    var _result_gene_silencing_efficiency = gene_silencing_efficiency(0.5, 0.5)
    var _summary_gene_silencing_efficiency = _summary_float64(_result_gene_silencing_efficiency)
    print("MOJO_RESULT epigenetics::gene_silencing_efficiency", _summary_gene_silencing_efficiency)
    var _acc_enhancer_activity_index: Float64 = 0.0
    var _t0_enhancer_activity_index = perf_counter_ns()
    for _ in range(N):
        _acc_enhancer_activity_index += enhancer_activity_index(0.5, 0.5)
    var _t1_enhancer_activity_index = perf_counter_ns()
    var _ns_enhancer_activity_index = Float64(_t1_enhancer_activity_index - _t0_enhancer_activity_index) / Float64(N)
    print("MOJO_TIMING epigenetics::enhancer_activity_index", _ns_enhancer_activity_index, _acc_enhancer_activity_index)
    var _result_enhancer_activity_index = enhancer_activity_index(0.5, 0.5)
    var _summary_enhancer_activity_index = _summary_float64(_result_enhancer_activity_index)
    print("MOJO_RESULT epigenetics::enhancer_activity_index", _summary_enhancer_activity_index)
    var _acc_polycomb_enrichment: Float64 = 0.0
    var _t0_polycomb_enrichment = perf_counter_ns()
    for _ in range(N):
        _acc_polycomb_enrichment += polycomb_enrichment(0.5, 0.5)
    var _t1_polycomb_enrichment = perf_counter_ns()
    var _ns_polycomb_enrichment = Float64(_t1_polycomb_enrichment - _t0_polycomb_enrichment) / Float64(N)
    print("MOJO_TIMING epigenetics::polycomb_enrichment", _ns_polycomb_enrichment, _acc_polycomb_enrichment)
    var _result_polycomb_enrichment = polycomb_enrichment(0.5, 0.5)
    var _summary_polycomb_enrichment = _summary_float64(_result_polycomb_enrichment)
    print("MOJO_RESULT epigenetics::polycomb_enrichment", _summary_polycomb_enrichment)
    var _acc_transcription_factor_occupancy: Float64 = 0.0
    var _t0_transcription_factor_occupancy = perf_counter_ns()
    for _ in range(N):
        _acc_transcription_factor_occupancy += transcription_factor_occupancy(0.5, 0.5, 0.5)
    var _t1_transcription_factor_occupancy = perf_counter_ns()
    var _ns_transcription_factor_occupancy = Float64(_t1_transcription_factor_occupancy - _t0_transcription_factor_occupancy) / Float64(N)
    print("MOJO_TIMING epigenetics::transcription_factor_occupancy", _ns_transcription_factor_occupancy, _acc_transcription_factor_occupancy)
    var _result_transcription_factor_occupancy = transcription_factor_occupancy(0.5, 0.5, 0.5)
    var _summary_transcription_factor_occupancy = _summary_float64(_result_transcription_factor_occupancy)
    print("MOJO_RESULT epigenetics::transcription_factor_occupancy", _summary_transcription_factor_occupancy)
