"""bench_proteomics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from proteomics import molecular_weight_da, isoelectric_point_approx, extinction_coefficient, protein_concentration_a280, sequence_coverage, peptide_mass_monoisotopic, peak_area_ratio, protein_abundance_index, empa_score, fdr_target_decoy
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

    var _acc_molecular_weight_da: Float64 = 0.0
    var _t0_molecular_weight_da = perf_counter_ns()
    for _ in range(N):
        _acc_molecular_weight_da += molecular_weight_da(0.5, 0.5)
    var _t1_molecular_weight_da = perf_counter_ns()
    var _ns_molecular_weight_da = Float64(_t1_molecular_weight_da - _t0_molecular_weight_da) / Float64(N)
    print("MOJO_TIMING proteomics::molecular_weight_da", _ns_molecular_weight_da, _acc_molecular_weight_da)
    var _result_molecular_weight_da = molecular_weight_da(0.5, 0.5)
    var _summary_molecular_weight_da = _summary_float64(_result_molecular_weight_da)
    print("MOJO_RESULT proteomics::molecular_weight_da", _summary_molecular_weight_da)
    var _acc_isoelectric_point_approx: Float64 = 0.0
    var _t0_isoelectric_point_approx = perf_counter_ns()
    for _ in range(N):
        _acc_isoelectric_point_approx += isoelectric_point_approx(0.5, 0.5)
    var _t1_isoelectric_point_approx = perf_counter_ns()
    var _ns_isoelectric_point_approx = Float64(_t1_isoelectric_point_approx - _t0_isoelectric_point_approx) / Float64(N)
    print("MOJO_TIMING proteomics::isoelectric_point_approx", _ns_isoelectric_point_approx, _acc_isoelectric_point_approx)
    var _result_isoelectric_point_approx = isoelectric_point_approx(0.5, 0.5)
    var _summary_isoelectric_point_approx = _summary_float64(_result_isoelectric_point_approx)
    print("MOJO_RESULT proteomics::isoelectric_point_approx", _summary_isoelectric_point_approx)
    var _acc_extinction_coefficient: Float64 = 0.0
    var _t0_extinction_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_extinction_coefficient += extinction_coefficient(0.5, 0.5, 0.5)
    var _t1_extinction_coefficient = perf_counter_ns()
    var _ns_extinction_coefficient = Float64(_t1_extinction_coefficient - _t0_extinction_coefficient) / Float64(N)
    print("MOJO_TIMING proteomics::extinction_coefficient", _ns_extinction_coefficient, _acc_extinction_coefficient)
    var _result_extinction_coefficient = extinction_coefficient(0.5, 0.5, 0.5)
    var _summary_extinction_coefficient = _summary_float64(_result_extinction_coefficient)
    print("MOJO_RESULT proteomics::extinction_coefficient", _summary_extinction_coefficient)
    var _acc_protein_concentration_a280: Float64 = 0.0
    var _t0_protein_concentration_a280 = perf_counter_ns()
    for _ in range(N):
        _acc_protein_concentration_a280 += protein_concentration_a280(0.5, 0.5, 0.5)
    var _t1_protein_concentration_a280 = perf_counter_ns()
    var _ns_protein_concentration_a280 = Float64(_t1_protein_concentration_a280 - _t0_protein_concentration_a280) / Float64(N)
    print("MOJO_TIMING proteomics::protein_concentration_a280", _ns_protein_concentration_a280, _acc_protein_concentration_a280)
    var _result_protein_concentration_a280 = protein_concentration_a280(0.5, 0.5, 0.5)
    var _summary_protein_concentration_a280 = _summary_float64(_result_protein_concentration_a280)
    print("MOJO_RESULT proteomics::protein_concentration_a280", _summary_protein_concentration_a280)
    var _acc_sequence_coverage: Float64 = 0.0
    var _t0_sequence_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_sequence_coverage += sequence_coverage(0.5, 0.5)
    var _t1_sequence_coverage = perf_counter_ns()
    var _ns_sequence_coverage = Float64(_t1_sequence_coverage - _t0_sequence_coverage) / Float64(N)
    print("MOJO_TIMING proteomics::sequence_coverage", _ns_sequence_coverage, _acc_sequence_coverage)
    var _result_sequence_coverage = sequence_coverage(0.5, 0.5)
    var _summary_sequence_coverage = _summary_float64(_result_sequence_coverage)
    print("MOJO_RESULT proteomics::sequence_coverage", _summary_sequence_coverage)
    var _acc_peptide_mass_monoisotopic: Float64 = 0.0
    var _t0_peptide_mass_monoisotopic = perf_counter_ns()
    for _ in range(N):
        _acc_peptide_mass_monoisotopic += peptide_mass_monoisotopic(0.5, 0.5)
    var _t1_peptide_mass_monoisotopic = perf_counter_ns()
    var _ns_peptide_mass_monoisotopic = Float64(_t1_peptide_mass_monoisotopic - _t0_peptide_mass_monoisotopic) / Float64(N)
    print("MOJO_TIMING proteomics::peptide_mass_monoisotopic", _ns_peptide_mass_monoisotopic, _acc_peptide_mass_monoisotopic)
    var _result_peptide_mass_monoisotopic = peptide_mass_monoisotopic(0.5, 0.5)
    var _summary_peptide_mass_monoisotopic = _summary_float64(_result_peptide_mass_monoisotopic)
    print("MOJO_RESULT proteomics::peptide_mass_monoisotopic", _summary_peptide_mass_monoisotopic)
    var _acc_peak_area_ratio: Float64 = 0.0
    var _t0_peak_area_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_peak_area_ratio += peak_area_ratio(0.5, 0.5)
    var _t1_peak_area_ratio = perf_counter_ns()
    var _ns_peak_area_ratio = Float64(_t1_peak_area_ratio - _t0_peak_area_ratio) / Float64(N)
    print("MOJO_TIMING proteomics::peak_area_ratio", _ns_peak_area_ratio, _acc_peak_area_ratio)
    var _result_peak_area_ratio = peak_area_ratio(0.5, 0.5)
    var _summary_peak_area_ratio = _summary_float64(_result_peak_area_ratio)
    print("MOJO_RESULT proteomics::peak_area_ratio", _summary_peak_area_ratio)
    var _acc_protein_abundance_index: Float64 = 0.0
    var _t0_protein_abundance_index = perf_counter_ns()
    for _ in range(N):
        _acc_protein_abundance_index += protein_abundance_index(0.5, 0.5)
    var _t1_protein_abundance_index = perf_counter_ns()
    var _ns_protein_abundance_index = Float64(_t1_protein_abundance_index - _t0_protein_abundance_index) / Float64(N)
    print("MOJO_TIMING proteomics::protein_abundance_index", _ns_protein_abundance_index, _acc_protein_abundance_index)
    var _result_protein_abundance_index = protein_abundance_index(0.5, 0.5)
    var _summary_protein_abundance_index = _summary_float64(_result_protein_abundance_index)
    print("MOJO_RESULT proteomics::protein_abundance_index", _summary_protein_abundance_index)
    var _acc_empa_score: Float64 = 0.0
    var _t0_empa_score = perf_counter_ns()
    for _ in range(N):
        _acc_empa_score += empa_score(0.5)
    var _t1_empa_score = perf_counter_ns()
    var _ns_empa_score = Float64(_t1_empa_score - _t0_empa_score) / Float64(N)
    print("MOJO_TIMING proteomics::empa_score", _ns_empa_score, _acc_empa_score)
    var _result_empa_score = empa_score(0.5)
    var _summary_empa_score = _summary_float64(_result_empa_score)
    print("MOJO_RESULT proteomics::empa_score", _summary_empa_score)
    var _acc_fdr_target_decoy: Float64 = 0.0
    var _t0_fdr_target_decoy = perf_counter_ns()
    for _ in range(N):
        _acc_fdr_target_decoy += fdr_target_decoy(0.5, 0.5)
    var _t1_fdr_target_decoy = perf_counter_ns()
    var _ns_fdr_target_decoy = Float64(_t1_fdr_target_decoy - _t0_fdr_target_decoy) / Float64(N)
    print("MOJO_TIMING proteomics::fdr_target_decoy", _ns_fdr_target_decoy, _acc_fdr_target_decoy)
    var _result_fdr_target_decoy = fdr_target_decoy(0.5, 0.5)
    var _summary_fdr_target_decoy = _summary_float64(_result_fdr_target_decoy)
    print("MOJO_RESULT proteomics::fdr_target_decoy", _summary_fdr_target_decoy)
