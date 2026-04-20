"""bench_genomics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from genomics import gc_content, genome_size_from_cot, coverage_depth, n50_approximation, snp_density, indel_rate, repeat_fraction, gene_density, read_mapping_efficiency, sequencing_error_rate
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
        _acc_gc_content += gc_content(0.5, 0.5, 0.5)
    var _t1_gc_content = perf_counter_ns()
    var _ns_gc_content = Float64(_t1_gc_content - _t0_gc_content) / Float64(N)
    print("MOJO_TIMING genomics::gc_content", _ns_gc_content, _acc_gc_content)
    var _acc_genome_size_from_cot: Float64 = 0.0
    var _t0_genome_size_from_cot = perf_counter_ns()
    for _ in range(N):
        _acc_genome_size_from_cot += genome_size_from_cot(0.5, 0.5)
    var _t1_genome_size_from_cot = perf_counter_ns()
    var _ns_genome_size_from_cot = Float64(_t1_genome_size_from_cot - _t0_genome_size_from_cot) / Float64(N)
    print("MOJO_TIMING genomics::genome_size_from_cot", _ns_genome_size_from_cot, _acc_genome_size_from_cot)
    var _acc_coverage_depth: Float64 = 0.0
    var _t0_coverage_depth = perf_counter_ns()
    for _ in range(N):
        _acc_coverage_depth += coverage_depth(0.5, 0.5, 0.5)
    var _t1_coverage_depth = perf_counter_ns()
    var _ns_coverage_depth = Float64(_t1_coverage_depth - _t0_coverage_depth) / Float64(N)
    print("MOJO_TIMING genomics::coverage_depth", _ns_coverage_depth, _acc_coverage_depth)
    var _acc_n50_approximation: Float64 = 0.0
    var _t0_n50_approximation = perf_counter_ns()
    for _ in range(N):
        _acc_n50_approximation += n50_approximation(0.5, 0.5)
    var _t1_n50_approximation = perf_counter_ns()
    var _ns_n50_approximation = Float64(_t1_n50_approximation - _t0_n50_approximation) / Float64(N)
    print("MOJO_TIMING genomics::n50_approximation", _ns_n50_approximation, _acc_n50_approximation)
    var _acc_snp_density: Float64 = 0.0
    var _t0_snp_density = perf_counter_ns()
    for _ in range(N):
        _acc_snp_density += snp_density(0.5, 0.5)
    var _t1_snp_density = perf_counter_ns()
    var _ns_snp_density = Float64(_t1_snp_density - _t0_snp_density) / Float64(N)
    print("MOJO_TIMING genomics::snp_density", _ns_snp_density, _acc_snp_density)
    var _acc_indel_rate: Float64 = 0.0
    var _t0_indel_rate = perf_counter_ns()
    for _ in range(N):
        _acc_indel_rate += indel_rate(0.5, 0.5)
    var _t1_indel_rate = perf_counter_ns()
    var _ns_indel_rate = Float64(_t1_indel_rate - _t0_indel_rate) / Float64(N)
    print("MOJO_TIMING genomics::indel_rate", _ns_indel_rate, _acc_indel_rate)
    var _acc_repeat_fraction: Float64 = 0.0
    var _t0_repeat_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_repeat_fraction += repeat_fraction(0.5, 0.5)
    var _t1_repeat_fraction = perf_counter_ns()
    var _ns_repeat_fraction = Float64(_t1_repeat_fraction - _t0_repeat_fraction) / Float64(N)
    print("MOJO_TIMING genomics::repeat_fraction", _ns_repeat_fraction, _acc_repeat_fraction)
    var _acc_gene_density: Float64 = 0.0
    var _t0_gene_density = perf_counter_ns()
    for _ in range(N):
        _acc_gene_density += gene_density(0.5, 0.5)
    var _t1_gene_density = perf_counter_ns()
    var _ns_gene_density = Float64(_t1_gene_density - _t0_gene_density) / Float64(N)
    print("MOJO_TIMING genomics::gene_density", _ns_gene_density, _acc_gene_density)
    var _acc_read_mapping_efficiency: Float64 = 0.0
    var _t0_read_mapping_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_read_mapping_efficiency += read_mapping_efficiency(0.5, 0.5)
    var _t1_read_mapping_efficiency = perf_counter_ns()
    var _ns_read_mapping_efficiency = Float64(_t1_read_mapping_efficiency - _t0_read_mapping_efficiency) / Float64(N)
    print("MOJO_TIMING genomics::read_mapping_efficiency", _ns_read_mapping_efficiency, _acc_read_mapping_efficiency)
    var _acc_sequencing_error_rate: Float64 = 0.0
    var _t0_sequencing_error_rate = perf_counter_ns()
    for _ in range(N):
        _acc_sequencing_error_rate += sequencing_error_rate(0.5)
    var _t1_sequencing_error_rate = perf_counter_ns()
    var _ns_sequencing_error_rate = Float64(_t1_sequencing_error_rate - _t0_sequencing_error_rate) / Float64(N)
    print("MOJO_TIMING genomics::sequencing_error_rate", _ns_sequencing_error_rate, _acc_sequencing_error_rate)
