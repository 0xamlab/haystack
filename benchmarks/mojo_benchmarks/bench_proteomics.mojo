"""bench_proteomics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from proteomics import molecular_weight_da, isoelectric_point_approx, extinction_coefficient, protein_concentration_a280, sequence_coverage, peptide_mass_monoisotopic, peak_area_ratio, protein_abundance_index, empa_score, fdr_target_decoy
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

    var _acc_molecular_weight_da: Float64 = 0.0
    var _t0_molecular_weight_da = perf_counter_ns()
    for _ in range(N):
        _acc_molecular_weight_da += molecular_weight_da(0.5, 0.5)
    var _t1_molecular_weight_da = perf_counter_ns()
    var _ns_molecular_weight_da = Float64(_t1_molecular_weight_da - _t0_molecular_weight_da) / Float64(N)
    print("MOJO_TIMING proteomics::molecular_weight_da", _ns_molecular_weight_da, _acc_molecular_weight_da)
    var _acc_isoelectric_point_approx: Float64 = 0.0
    var _t0_isoelectric_point_approx = perf_counter_ns()
    for _ in range(N):
        _acc_isoelectric_point_approx += isoelectric_point_approx(0.5, 0.5)
    var _t1_isoelectric_point_approx = perf_counter_ns()
    var _ns_isoelectric_point_approx = Float64(_t1_isoelectric_point_approx - _t0_isoelectric_point_approx) / Float64(N)
    print("MOJO_TIMING proteomics::isoelectric_point_approx", _ns_isoelectric_point_approx, _acc_isoelectric_point_approx)
    var _acc_extinction_coefficient: Float64 = 0.0
    var _t0_extinction_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_extinction_coefficient += extinction_coefficient(0.5, 0.5, 0.5)
    var _t1_extinction_coefficient = perf_counter_ns()
    var _ns_extinction_coefficient = Float64(_t1_extinction_coefficient - _t0_extinction_coefficient) / Float64(N)
    print("MOJO_TIMING proteomics::extinction_coefficient", _ns_extinction_coefficient, _acc_extinction_coefficient)
    var _acc_protein_concentration_a280: Float64 = 0.0
    var _t0_protein_concentration_a280 = perf_counter_ns()
    for _ in range(N):
        _acc_protein_concentration_a280 += protein_concentration_a280(0.5, 0.5, 0.5)
    var _t1_protein_concentration_a280 = perf_counter_ns()
    var _ns_protein_concentration_a280 = Float64(_t1_protein_concentration_a280 - _t0_protein_concentration_a280) / Float64(N)
    print("MOJO_TIMING proteomics::protein_concentration_a280", _ns_protein_concentration_a280, _acc_protein_concentration_a280)
    var _acc_sequence_coverage: Float64 = 0.0
    var _t0_sequence_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_sequence_coverage += sequence_coverage(0.5, 0.5)
    var _t1_sequence_coverage = perf_counter_ns()
    var _ns_sequence_coverage = Float64(_t1_sequence_coverage - _t0_sequence_coverage) / Float64(N)
    print("MOJO_TIMING proteomics::sequence_coverage", _ns_sequence_coverage, _acc_sequence_coverage)
    var _acc_peptide_mass_monoisotopic: Float64 = 0.0
    var _t0_peptide_mass_monoisotopic = perf_counter_ns()
    for _ in range(N):
        _acc_peptide_mass_monoisotopic += peptide_mass_monoisotopic(0.5, 0.5)
    var _t1_peptide_mass_monoisotopic = perf_counter_ns()
    var _ns_peptide_mass_monoisotopic = Float64(_t1_peptide_mass_monoisotopic - _t0_peptide_mass_monoisotopic) / Float64(N)
    print("MOJO_TIMING proteomics::peptide_mass_monoisotopic", _ns_peptide_mass_monoisotopic, _acc_peptide_mass_monoisotopic)
    var _acc_peak_area_ratio: Float64 = 0.0
    var _t0_peak_area_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_peak_area_ratio += peak_area_ratio(0.5, 0.5)
    var _t1_peak_area_ratio = perf_counter_ns()
    var _ns_peak_area_ratio = Float64(_t1_peak_area_ratio - _t0_peak_area_ratio) / Float64(N)
    print("MOJO_TIMING proteomics::peak_area_ratio", _ns_peak_area_ratio, _acc_peak_area_ratio)
    var _acc_protein_abundance_index: Float64 = 0.0
    var _t0_protein_abundance_index = perf_counter_ns()
    for _ in range(N):
        _acc_protein_abundance_index += protein_abundance_index(0.5, 0.5)
    var _t1_protein_abundance_index = perf_counter_ns()
    var _ns_protein_abundance_index = Float64(_t1_protein_abundance_index - _t0_protein_abundance_index) / Float64(N)
    print("MOJO_TIMING proteomics::protein_abundance_index", _ns_protein_abundance_index, _acc_protein_abundance_index)
    var _acc_empa_score: Float64 = 0.0
    var _t0_empa_score = perf_counter_ns()
    for _ in range(N):
        _acc_empa_score += empa_score(0.5)
    var _t1_empa_score = perf_counter_ns()
    var _ns_empa_score = Float64(_t1_empa_score - _t0_empa_score) / Float64(N)
    print("MOJO_TIMING proteomics::empa_score", _ns_empa_score, _acc_empa_score)
    var _acc_fdr_target_decoy: Float64 = 0.0
    var _t0_fdr_target_decoy = perf_counter_ns()
    for _ in range(N):
        _acc_fdr_target_decoy += fdr_target_decoy(0.5, 0.5)
    var _t1_fdr_target_decoy = perf_counter_ns()
    var _ns_fdr_target_decoy = Float64(_t1_fdr_target_decoy - _t0_fdr_target_decoy) / Float64(N)
    print("MOJO_TIMING proteomics::fdr_target_decoy", _ns_fdr_target_decoy, _acc_fdr_target_decoy)
