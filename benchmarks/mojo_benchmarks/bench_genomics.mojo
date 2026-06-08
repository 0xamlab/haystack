"""bench_genomics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from genomics import gc_content, genome_size_from_cot, coverage_depth, n50_approximation, snp_density, indel_rate, repeat_fraction, gene_density, read_mapping_efficiency, sequencing_error_rate
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

    var _acc_gc_content: Float64 = 0.0
    var _t0_gc_content = perf_counter_ns()
    for _ in range(N):
        _acc_gc_content += gc_content(0.5, 0.5, 0.5)
    var _t1_gc_content = perf_counter_ns()
    var _ns_gc_content = Float64(_t1_gc_content - _t0_gc_content) / Float64(N)
    print("MOJO_TIMING genomics::gc_content", _ns_gc_content, _acc_gc_content)
    var _result_gc_content = gc_content(0.5, 0.5, 0.5)
    var _summary_gc_content = _summary_float64(_result_gc_content)
    print("MOJO_RESULT genomics::gc_content", _summary_gc_content)
    var _acc_genome_size_from_cot: Float64 = 0.0
    var _t0_genome_size_from_cot = perf_counter_ns()
    for _ in range(N):
        _acc_genome_size_from_cot += genome_size_from_cot(0.5, 0.5)
    var _t1_genome_size_from_cot = perf_counter_ns()
    var _ns_genome_size_from_cot = Float64(_t1_genome_size_from_cot - _t0_genome_size_from_cot) / Float64(N)
    print("MOJO_TIMING genomics::genome_size_from_cot", _ns_genome_size_from_cot, _acc_genome_size_from_cot)
    var _result_genome_size_from_cot = genome_size_from_cot(0.5, 0.5)
    var _summary_genome_size_from_cot = _summary_float64(_result_genome_size_from_cot)
    print("MOJO_RESULT genomics::genome_size_from_cot", _summary_genome_size_from_cot)
    var _acc_coverage_depth: Float64 = 0.0
    var _t0_coverage_depth = perf_counter_ns()
    for _ in range(N):
        _acc_coverage_depth += coverage_depth(0.5, 0.5, 0.5)
    var _t1_coverage_depth = perf_counter_ns()
    var _ns_coverage_depth = Float64(_t1_coverage_depth - _t0_coverage_depth) / Float64(N)
    print("MOJO_TIMING genomics::coverage_depth", _ns_coverage_depth, _acc_coverage_depth)
    var _result_coverage_depth = coverage_depth(0.5, 0.5, 0.5)
    var _summary_coverage_depth = _summary_float64(_result_coverage_depth)
    print("MOJO_RESULT genomics::coverage_depth", _summary_coverage_depth)
    var _acc_n50_approximation: Float64 = 0.0
    var _t0_n50_approximation = perf_counter_ns()
    for _ in range(N):
        _acc_n50_approximation += n50_approximation(0.5, 0.5)
    var _t1_n50_approximation = perf_counter_ns()
    var _ns_n50_approximation = Float64(_t1_n50_approximation - _t0_n50_approximation) / Float64(N)
    print("MOJO_TIMING genomics::n50_approximation", _ns_n50_approximation, _acc_n50_approximation)
    var _result_n50_approximation = n50_approximation(0.5, 0.5)
    var _summary_n50_approximation = _summary_float64(_result_n50_approximation)
    print("MOJO_RESULT genomics::n50_approximation", _summary_n50_approximation)
    var _acc_snp_density: Float64 = 0.0
    var _t0_snp_density = perf_counter_ns()
    for _ in range(N):
        _acc_snp_density += snp_density(0.5, 0.5)
    var _t1_snp_density = perf_counter_ns()
    var _ns_snp_density = Float64(_t1_snp_density - _t0_snp_density) / Float64(N)
    print("MOJO_TIMING genomics::snp_density", _ns_snp_density, _acc_snp_density)
    var _result_snp_density = snp_density(0.5, 0.5)
    var _summary_snp_density = _summary_float64(_result_snp_density)
    print("MOJO_RESULT genomics::snp_density", _summary_snp_density)
    var _acc_indel_rate: Float64 = 0.0
    var _t0_indel_rate = perf_counter_ns()
    for _ in range(N):
        _acc_indel_rate += indel_rate(0.5, 0.5)
    var _t1_indel_rate = perf_counter_ns()
    var _ns_indel_rate = Float64(_t1_indel_rate - _t0_indel_rate) / Float64(N)
    print("MOJO_TIMING genomics::indel_rate", _ns_indel_rate, _acc_indel_rate)
    var _result_indel_rate = indel_rate(0.5, 0.5)
    var _summary_indel_rate = _summary_float64(_result_indel_rate)
    print("MOJO_RESULT genomics::indel_rate", _summary_indel_rate)
    var _acc_repeat_fraction: Float64 = 0.0
    var _t0_repeat_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_repeat_fraction += repeat_fraction(0.5, 0.5)
    var _t1_repeat_fraction = perf_counter_ns()
    var _ns_repeat_fraction = Float64(_t1_repeat_fraction - _t0_repeat_fraction) / Float64(N)
    print("MOJO_TIMING genomics::repeat_fraction", _ns_repeat_fraction, _acc_repeat_fraction)
    var _result_repeat_fraction = repeat_fraction(0.5, 0.5)
    var _summary_repeat_fraction = _summary_float64(_result_repeat_fraction)
    print("MOJO_RESULT genomics::repeat_fraction", _summary_repeat_fraction)
    var _acc_gene_density: Float64 = 0.0
    var _t0_gene_density = perf_counter_ns()
    for _ in range(N):
        _acc_gene_density += gene_density(0.5, 0.5)
    var _t1_gene_density = perf_counter_ns()
    var _ns_gene_density = Float64(_t1_gene_density - _t0_gene_density) / Float64(N)
    print("MOJO_TIMING genomics::gene_density", _ns_gene_density, _acc_gene_density)
    var _result_gene_density = gene_density(0.5, 0.5)
    var _summary_gene_density = _summary_float64(_result_gene_density)
    print("MOJO_RESULT genomics::gene_density", _summary_gene_density)
    var _acc_read_mapping_efficiency: Float64 = 0.0
    var _t0_read_mapping_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_read_mapping_efficiency += read_mapping_efficiency(0.5, 0.5)
    var _t1_read_mapping_efficiency = perf_counter_ns()
    var _ns_read_mapping_efficiency = Float64(_t1_read_mapping_efficiency - _t0_read_mapping_efficiency) / Float64(N)
    print("MOJO_TIMING genomics::read_mapping_efficiency", _ns_read_mapping_efficiency, _acc_read_mapping_efficiency)
    var _result_read_mapping_efficiency = read_mapping_efficiency(0.5, 0.5)
    var _summary_read_mapping_efficiency = _summary_float64(_result_read_mapping_efficiency)
    print("MOJO_RESULT genomics::read_mapping_efficiency", _summary_read_mapping_efficiency)
    var _acc_sequencing_error_rate: Float64 = 0.0
    var _t0_sequencing_error_rate = perf_counter_ns()
    for _ in range(N):
        _acc_sequencing_error_rate += sequencing_error_rate(0.5)
    var _t1_sequencing_error_rate = perf_counter_ns()
    var _ns_sequencing_error_rate = Float64(_t1_sequencing_error_rate - _t0_sequencing_error_rate) / Float64(N)
    print("MOJO_TIMING genomics::sequencing_error_rate", _ns_sequencing_error_rate, _acc_sequencing_error_rate)
    var _result_sequencing_error_rate = sequencing_error_rate(0.5)
    var _summary_sequencing_error_rate = _summary_float64(_result_sequencing_error_rate)
    print("MOJO_RESULT genomics::sequencing_error_rate", _summary_sequencing_error_rate)
