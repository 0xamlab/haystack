"""bench_bioinformatics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bioinformatics import gc_content, tm_basic, tm_salt_adjusted, molecular_weight_dna, sequence_identity, evalue_significance, coverage_depth, n50_from_values, phred_quality_to_error, error_to_phred_quality, codon_count, amino_acid_count
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
        _acc_gc_content += gc_content(0.5, 0.5)
    var _t1_gc_content = perf_counter_ns()
    var _ns_gc_content = Float64(_t1_gc_content - _t0_gc_content) / Float64(N)
    print("MOJO_TIMING bioinformatics::gc_content", _ns_gc_content, _acc_gc_content)
    var _result_gc_content = gc_content(0.5, 0.5)
    var _summary_gc_content = _summary_float64(_result_gc_content)
    print("MOJO_RESULT bioinformatics::gc_content", _summary_gc_content)
    var _acc_tm_basic: Float64 = 0.0
    var _t0_tm_basic = perf_counter_ns()
    for _ in range(N):
        _acc_tm_basic += tm_basic(0.5, 0.5, 0.5, 0.5)
    var _t1_tm_basic = perf_counter_ns()
    var _ns_tm_basic = Float64(_t1_tm_basic - _t0_tm_basic) / Float64(N)
    print("MOJO_TIMING bioinformatics::tm_basic", _ns_tm_basic, _acc_tm_basic)
    var _result_tm_basic = tm_basic(0.5, 0.5, 0.5, 0.5)
    var _summary_tm_basic = _summary_float64(_result_tm_basic)
    print("MOJO_RESULT bioinformatics::tm_basic", _summary_tm_basic)
    var _acc_tm_salt_adjusted: Float64 = 0.0
    var _t0_tm_salt_adjusted = perf_counter_ns()
    for _ in range(N):
        _acc_tm_salt_adjusted += tm_salt_adjusted(0.5, 0.5)
    var _t1_tm_salt_adjusted = perf_counter_ns()
    var _ns_tm_salt_adjusted = Float64(_t1_tm_salt_adjusted - _t0_tm_salt_adjusted) / Float64(N)
    print("MOJO_TIMING bioinformatics::tm_salt_adjusted", _ns_tm_salt_adjusted, _acc_tm_salt_adjusted)
    var _result_tm_salt_adjusted = tm_salt_adjusted(0.5, 0.5)
    var _summary_tm_salt_adjusted = _summary_float64(_result_tm_salt_adjusted)
    print("MOJO_RESULT bioinformatics::tm_salt_adjusted", _summary_tm_salt_adjusted)
    var _acc_molecular_weight_dna: Float64 = 0.0
    var _t0_molecular_weight_dna = perf_counter_ns()
    for _ in range(N):
        _acc_molecular_weight_dna += molecular_weight_dna(0.5, 0.5)
    var _t1_molecular_weight_dna = perf_counter_ns()
    var _ns_molecular_weight_dna = Float64(_t1_molecular_weight_dna - _t0_molecular_weight_dna) / Float64(N)
    print("MOJO_TIMING bioinformatics::molecular_weight_dna", _ns_molecular_weight_dna, _acc_molecular_weight_dna)
    var _result_molecular_weight_dna = molecular_weight_dna(0.5, 0.5)
    var _summary_molecular_weight_dna = _summary_float64(_result_molecular_weight_dna)
    print("MOJO_RESULT bioinformatics::molecular_weight_dna", _summary_molecular_weight_dna)
    var _acc_sequence_identity: Float64 = 0.0
    var _t0_sequence_identity = perf_counter_ns()
    for _ in range(N):
        _acc_sequence_identity += sequence_identity(0.5, 0.5)
    var _t1_sequence_identity = perf_counter_ns()
    var _ns_sequence_identity = Float64(_t1_sequence_identity - _t0_sequence_identity) / Float64(N)
    print("MOJO_TIMING bioinformatics::sequence_identity", _ns_sequence_identity, _acc_sequence_identity)
    var _result_sequence_identity = sequence_identity(0.5, 0.5)
    var _summary_sequence_identity = _summary_float64(_result_sequence_identity)
    print("MOJO_RESULT bioinformatics::sequence_identity", _summary_sequence_identity)
    var _acc_evalue_significance: Float64 = 0.0
    var _t0_evalue_significance = perf_counter_ns()
    for _ in range(N):
        _acc_evalue_significance += Float64(evalue_significance(0.5, 0.5))
    var _t1_evalue_significance = perf_counter_ns()
    var _ns_evalue_significance = Float64(_t1_evalue_significance - _t0_evalue_significance) / Float64(N)
    print("MOJO_TIMING bioinformatics::evalue_significance", _ns_evalue_significance, _acc_evalue_significance)
    var _result_evalue_significance = evalue_significance(0.5, 0.5)
    var _summary_evalue_significance = _summary_bool(_result_evalue_significance)
    print("MOJO_RESULT bioinformatics::evalue_significance", _summary_evalue_significance)
    var _acc_coverage_depth: Float64 = 0.0
    var _t0_coverage_depth = perf_counter_ns()
    for _ in range(N):
        _acc_coverage_depth += coverage_depth(0.5, 0.5)
    var _t1_coverage_depth = perf_counter_ns()
    var _ns_coverage_depth = Float64(_t1_coverage_depth - _t0_coverage_depth) / Float64(N)
    print("MOJO_TIMING bioinformatics::coverage_depth", _ns_coverage_depth, _acc_coverage_depth)
    var _result_coverage_depth = coverage_depth(0.5, 0.5)
    var _summary_coverage_depth = _summary_float64(_result_coverage_depth)
    print("MOJO_RESULT bioinformatics::coverage_depth", _summary_coverage_depth)
    var _acc_n50_from_values: Float64 = 0.0
    var _t0_n50_from_values = perf_counter_ns()
    for _ in range(N):
        _acc_n50_from_values += n50_from_values(0.5, 0.5)
    var _t1_n50_from_values = perf_counter_ns()
    var _ns_n50_from_values = Float64(_t1_n50_from_values - _t0_n50_from_values) / Float64(N)
    print("MOJO_TIMING bioinformatics::n50_from_values", _ns_n50_from_values, _acc_n50_from_values)
    var _result_n50_from_values = n50_from_values(0.5, 0.5)
    var _summary_n50_from_values = _summary_float64(_result_n50_from_values)
    print("MOJO_RESULT bioinformatics::n50_from_values", _summary_n50_from_values)
    var _acc_phred_quality_to_error: Float64 = 0.0
    var _t0_phred_quality_to_error = perf_counter_ns()
    for _ in range(N):
        _acc_phred_quality_to_error += phred_quality_to_error(0.5)
    var _t1_phred_quality_to_error = perf_counter_ns()
    var _ns_phred_quality_to_error = Float64(_t1_phred_quality_to_error - _t0_phred_quality_to_error) / Float64(N)
    print("MOJO_TIMING bioinformatics::phred_quality_to_error", _ns_phred_quality_to_error, _acc_phred_quality_to_error)
    var _result_phred_quality_to_error = phred_quality_to_error(0.5)
    var _summary_phred_quality_to_error = _summary_float64(_result_phred_quality_to_error)
    print("MOJO_RESULT bioinformatics::phred_quality_to_error", _summary_phred_quality_to_error)
    var _acc_error_to_phred_quality: Float64 = 0.0
    var _t0_error_to_phred_quality = perf_counter_ns()
    for _ in range(N):
        _acc_error_to_phred_quality += error_to_phred_quality(0.5)
    var _t1_error_to_phred_quality = perf_counter_ns()
    var _ns_error_to_phred_quality = Float64(_t1_error_to_phred_quality - _t0_error_to_phred_quality) / Float64(N)
    print("MOJO_TIMING bioinformatics::error_to_phred_quality", _ns_error_to_phred_quality, _acc_error_to_phred_quality)
    var _result_error_to_phred_quality = error_to_phred_quality(0.5)
    var _summary_error_to_phred_quality = _summary_float64(_result_error_to_phred_quality)
    print("MOJO_RESULT bioinformatics::error_to_phred_quality", _summary_error_to_phred_quality)
    var _acc_codon_count: Float64 = 0.0
    var _t0_codon_count = perf_counter_ns()
    for _ in range(N):
        _acc_codon_count += Float64(codon_count(5))
    var _t1_codon_count = perf_counter_ns()
    var _ns_codon_count = Float64(_t1_codon_count - _t0_codon_count) / Float64(N)
    print("MOJO_TIMING bioinformatics::codon_count", _ns_codon_count, _acc_codon_count)
    var _result_codon_count = codon_count(5)
    var _summary_codon_count = _summary_int(_result_codon_count)
    print("MOJO_RESULT bioinformatics::codon_count", _summary_codon_count)
    var _acc_amino_acid_count: Float64 = 0.0
    var _t0_amino_acid_count = perf_counter_ns()
    for _ in range(N):
        _acc_amino_acid_count += Float64(amino_acid_count(5))
    var _t1_amino_acid_count = perf_counter_ns()
    var _ns_amino_acid_count = Float64(_t1_amino_acid_count - _t0_amino_acid_count) / Float64(N)
    print("MOJO_TIMING bioinformatics::amino_acid_count", _ns_amino_acid_count, _acc_amino_acid_count)
    var _result_amino_acid_count = amino_acid_count(5)
    var _summary_amino_acid_count = _summary_int(_result_amino_acid_count)
    print("MOJO_RESULT bioinformatics::amino_acid_count", _summary_amino_acid_count)
