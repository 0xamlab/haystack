"""bench_epigenetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from epigenetics import methylation_index, dna_methylation_age, histone_acetylation_ratio, chromatin_accessibility, imprinting_ratio, cpg_observed_expected, gene_silencing_efficiency, enhancer_activity_index, polycomb_enrichment, transcription_factor_occupancy
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

    var _acc_methylation_index: Float64 = 0.0
    var _t0_methylation_index = perf_counter_ns()
    for _ in range(N):
        _acc_methylation_index += methylation_index(0.5, 0.5)
    var _t1_methylation_index = perf_counter_ns()
    var _ns_methylation_index = Float64(_t1_methylation_index - _t0_methylation_index) / Float64(N)
    print("MOJO_TIMING epigenetics::methylation_index", _ns_methylation_index, _acc_methylation_index)
    var _acc_dna_methylation_age: Float64 = 0.0
    var _t0_dna_methylation_age = perf_counter_ns()
    for _ in range(N):
        _acc_dna_methylation_age += dna_methylation_age(0.5, 0.5, 0.5)
    var _t1_dna_methylation_age = perf_counter_ns()
    var _ns_dna_methylation_age = Float64(_t1_dna_methylation_age - _t0_dna_methylation_age) / Float64(N)
    print("MOJO_TIMING epigenetics::dna_methylation_age", _ns_dna_methylation_age, _acc_dna_methylation_age)
    var _acc_histone_acetylation_ratio: Float64 = 0.0
    var _t0_histone_acetylation_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_histone_acetylation_ratio += histone_acetylation_ratio(0.5, 0.5)
    var _t1_histone_acetylation_ratio = perf_counter_ns()
    var _ns_histone_acetylation_ratio = Float64(_t1_histone_acetylation_ratio - _t0_histone_acetylation_ratio) / Float64(N)
    print("MOJO_TIMING epigenetics::histone_acetylation_ratio", _ns_histone_acetylation_ratio, _acc_histone_acetylation_ratio)
    var _acc_chromatin_accessibility: Float64 = 0.0
    var _t0_chromatin_accessibility = perf_counter_ns()
    for _ in range(N):
        _acc_chromatin_accessibility += chromatin_accessibility(0.5, 0.5, 0.5)
    var _t1_chromatin_accessibility = perf_counter_ns()
    var _ns_chromatin_accessibility = Float64(_t1_chromatin_accessibility - _t0_chromatin_accessibility) / Float64(N)
    print("MOJO_TIMING epigenetics::chromatin_accessibility", _ns_chromatin_accessibility, _acc_chromatin_accessibility)
    var _acc_imprinting_ratio: Float64 = 0.0
    var _t0_imprinting_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_imprinting_ratio += imprinting_ratio(0.5, 0.5)
    var _t1_imprinting_ratio = perf_counter_ns()
    var _ns_imprinting_ratio = Float64(_t1_imprinting_ratio - _t0_imprinting_ratio) / Float64(N)
    print("MOJO_TIMING epigenetics::imprinting_ratio", _ns_imprinting_ratio, _acc_imprinting_ratio)
    var _acc_cpg_observed_expected: Float64 = 0.0
    var _t0_cpg_observed_expected = perf_counter_ns()
    for _ in range(N):
        _acc_cpg_observed_expected += cpg_observed_expected(0.5, 0.5, 0.5, 0.5)
    var _t1_cpg_observed_expected = perf_counter_ns()
    var _ns_cpg_observed_expected = Float64(_t1_cpg_observed_expected - _t0_cpg_observed_expected) / Float64(N)
    print("MOJO_TIMING epigenetics::cpg_observed_expected", _ns_cpg_observed_expected, _acc_cpg_observed_expected)
    var _acc_gene_silencing_efficiency: Float64 = 0.0
    var _t0_gene_silencing_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_gene_silencing_efficiency += gene_silencing_efficiency(0.5, 0.5)
    var _t1_gene_silencing_efficiency = perf_counter_ns()
    var _ns_gene_silencing_efficiency = Float64(_t1_gene_silencing_efficiency - _t0_gene_silencing_efficiency) / Float64(N)
    print("MOJO_TIMING epigenetics::gene_silencing_efficiency", _ns_gene_silencing_efficiency, _acc_gene_silencing_efficiency)
    var _acc_enhancer_activity_index: Float64 = 0.0
    var _t0_enhancer_activity_index = perf_counter_ns()
    for _ in range(N):
        _acc_enhancer_activity_index += enhancer_activity_index(0.5, 0.5)
    var _t1_enhancer_activity_index = perf_counter_ns()
    var _ns_enhancer_activity_index = Float64(_t1_enhancer_activity_index - _t0_enhancer_activity_index) / Float64(N)
    print("MOJO_TIMING epigenetics::enhancer_activity_index", _ns_enhancer_activity_index, _acc_enhancer_activity_index)
    var _acc_polycomb_enrichment: Float64 = 0.0
    var _t0_polycomb_enrichment = perf_counter_ns()
    for _ in range(N):
        _acc_polycomb_enrichment += polycomb_enrichment(0.5, 0.5)
    var _t1_polycomb_enrichment = perf_counter_ns()
    var _ns_polycomb_enrichment = Float64(_t1_polycomb_enrichment - _t0_polycomb_enrichment) / Float64(N)
    print("MOJO_TIMING epigenetics::polycomb_enrichment", _ns_polycomb_enrichment, _acc_polycomb_enrichment)
    var _acc_transcription_factor_occupancy: Float64 = 0.0
    var _t0_transcription_factor_occupancy = perf_counter_ns()
    for _ in range(N):
        _acc_transcription_factor_occupancy += transcription_factor_occupancy(0.5, 0.5, 0.5)
    var _t1_transcription_factor_occupancy = perf_counter_ns()
    var _ns_transcription_factor_occupancy = Float64(_t1_transcription_factor_occupancy - _t0_transcription_factor_occupancy) / Float64(N)
    print("MOJO_TIMING epigenetics::transcription_factor_occupancy", _ns_transcription_factor_occupancy, _acc_transcription_factor_occupancy)
