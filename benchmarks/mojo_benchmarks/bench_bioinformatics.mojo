"""bench_bioinformatics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bioinformatics import gc_content, tm_basic, tm_salt_adjusted, molecular_weight_dna, sequence_identity, evalue_significance, coverage_depth, n50_from_values, phred_quality_to_error, error_to_phred_quality, codon_count, amino_acid_count
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

    var _acc_gc_content: Float64 = 0.0
    var _t0_gc_content = perf_counter_ns()
    for _ in range(N):
        _acc_gc_content += gc_content(0.5, 0.5)
    var _t1_gc_content = perf_counter_ns()
    var _ns_gc_content = Float64(_t1_gc_content - _t0_gc_content) / Float64(N)
    print("MOJO_TIMING bioinformatics::gc_content", _ns_gc_content, _acc_gc_content)
    var _acc_tm_basic: Float64 = 0.0
    var _t0_tm_basic = perf_counter_ns()
    for _ in range(N):
        _acc_tm_basic += tm_basic(0.5, 0.5, 0.5, 0.5)
    var _t1_tm_basic = perf_counter_ns()
    var _ns_tm_basic = Float64(_t1_tm_basic - _t0_tm_basic) / Float64(N)
    print("MOJO_TIMING bioinformatics::tm_basic", _ns_tm_basic, _acc_tm_basic)
    var _acc_tm_salt_adjusted: Float64 = 0.0
    var _t0_tm_salt_adjusted = perf_counter_ns()
    for _ in range(N):
        _acc_tm_salt_adjusted += tm_salt_adjusted(0.5, 0.5)
    var _t1_tm_salt_adjusted = perf_counter_ns()
    var _ns_tm_salt_adjusted = Float64(_t1_tm_salt_adjusted - _t0_tm_salt_adjusted) / Float64(N)
    print("MOJO_TIMING bioinformatics::tm_salt_adjusted", _ns_tm_salt_adjusted, _acc_tm_salt_adjusted)
    var _acc_molecular_weight_dna: Float64 = 0.0
    var _t0_molecular_weight_dna = perf_counter_ns()
    for _ in range(N):
        _acc_molecular_weight_dna += molecular_weight_dna(0.5, 0.5)
    var _t1_molecular_weight_dna = perf_counter_ns()
    var _ns_molecular_weight_dna = Float64(_t1_molecular_weight_dna - _t0_molecular_weight_dna) / Float64(N)
    print("MOJO_TIMING bioinformatics::molecular_weight_dna", _ns_molecular_weight_dna, _acc_molecular_weight_dna)
    var _acc_sequence_identity: Float64 = 0.0
    var _t0_sequence_identity = perf_counter_ns()
    for _ in range(N):
        _acc_sequence_identity += sequence_identity(0.5, 0.5)
    var _t1_sequence_identity = perf_counter_ns()
    var _ns_sequence_identity = Float64(_t1_sequence_identity - _t0_sequence_identity) / Float64(N)
    print("MOJO_TIMING bioinformatics::sequence_identity", _ns_sequence_identity, _acc_sequence_identity)
    var _acc_evalue_significance: Float64 = 0.0
    var _t0_evalue_significance = perf_counter_ns()
    for _ in range(N):
        _acc_evalue_significance += Float64(evalue_significance(0.5, 0.5))
    var _t1_evalue_significance = perf_counter_ns()
    var _ns_evalue_significance = Float64(_t1_evalue_significance - _t0_evalue_significance) / Float64(N)
    print("MOJO_TIMING bioinformatics::evalue_significance", _ns_evalue_significance, _acc_evalue_significance)
    var _acc_coverage_depth: Float64 = 0.0
    var _t0_coverage_depth = perf_counter_ns()
    for _ in range(N):
        _acc_coverage_depth += coverage_depth(0.5, 0.5)
    var _t1_coverage_depth = perf_counter_ns()
    var _ns_coverage_depth = Float64(_t1_coverage_depth - _t0_coverage_depth) / Float64(N)
    print("MOJO_TIMING bioinformatics::coverage_depth", _ns_coverage_depth, _acc_coverage_depth)
    var _acc_n50_from_values: Float64 = 0.0
    var _t0_n50_from_values = perf_counter_ns()
    for _ in range(N):
        _acc_n50_from_values += n50_from_values(0.5, 0.5)
    var _t1_n50_from_values = perf_counter_ns()
    var _ns_n50_from_values = Float64(_t1_n50_from_values - _t0_n50_from_values) / Float64(N)
    print("MOJO_TIMING bioinformatics::n50_from_values", _ns_n50_from_values, _acc_n50_from_values)
    var _acc_phred_quality_to_error: Float64 = 0.0
    var _t0_phred_quality_to_error = perf_counter_ns()
    for _ in range(N):
        _acc_phred_quality_to_error += phred_quality_to_error(0.5)
    var _t1_phred_quality_to_error = perf_counter_ns()
    var _ns_phred_quality_to_error = Float64(_t1_phred_quality_to_error - _t0_phred_quality_to_error) / Float64(N)
    print("MOJO_TIMING bioinformatics::phred_quality_to_error", _ns_phred_quality_to_error, _acc_phred_quality_to_error)
    var _acc_error_to_phred_quality: Float64 = 0.0
    var _t0_error_to_phred_quality = perf_counter_ns()
    for _ in range(N):
        _acc_error_to_phred_quality += error_to_phred_quality(0.5)
    var _t1_error_to_phred_quality = perf_counter_ns()
    var _ns_error_to_phred_quality = Float64(_t1_error_to_phred_quality - _t0_error_to_phred_quality) / Float64(N)
    print("MOJO_TIMING bioinformatics::error_to_phred_quality", _ns_error_to_phred_quality, _acc_error_to_phred_quality)
    var _acc_codon_count: Float64 = 0.0
    var _t0_codon_count = perf_counter_ns()
    for _ in range(N):
        _acc_codon_count += Float64(codon_count(5))
    var _t1_codon_count = perf_counter_ns()
    var _ns_codon_count = Float64(_t1_codon_count - _t0_codon_count) / Float64(N)
    print("MOJO_TIMING bioinformatics::codon_count", _ns_codon_count, _acc_codon_count)
    var _acc_amino_acid_count: Float64 = 0.0
    var _t0_amino_acid_count = perf_counter_ns()
    for _ in range(N):
        _acc_amino_acid_count += Float64(amino_acid_count(5))
    var _t1_amino_acid_count = perf_counter_ns()
    var _ns_amino_acid_count = Float64(_t1_amino_acid_count - _t0_amino_acid_count) / Float64(N)
    print("MOJO_TIMING bioinformatics::amino_acid_count", _ns_amino_acid_count, _acc_amino_acid_count)
