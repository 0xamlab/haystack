"""bench_metabolomics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from metabolomics import metabolite_fold_change, pathway_enrichment_score, chemical_similarity_index, metabolic_flux_ratio, isotope_label_fraction, metabolite_half_life, normalization_zscore, principal_component_variance, vip_score, metabolic_distance
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

    var _acc_metabolite_fold_change: Float64 = 0.0
    var _t0_metabolite_fold_change = perf_counter_ns()
    for _ in range(N):
        _acc_metabolite_fold_change += metabolite_fold_change(0.5, 0.5)
    var _t1_metabolite_fold_change = perf_counter_ns()
    var _ns_metabolite_fold_change = Float64(_t1_metabolite_fold_change - _t0_metabolite_fold_change) / Float64(N)
    print("MOJO_TIMING metabolomics::metabolite_fold_change", _ns_metabolite_fold_change, _acc_metabolite_fold_change)
    var _acc_pathway_enrichment_score: Float64 = 0.0
    var _t0_pathway_enrichment_score = perf_counter_ns()
    for _ in range(N):
        _acc_pathway_enrichment_score += pathway_enrichment_score(0.5, 0.5, 0.5, 0.5)
    var _t1_pathway_enrichment_score = perf_counter_ns()
    var _ns_pathway_enrichment_score = Float64(_t1_pathway_enrichment_score - _t0_pathway_enrichment_score) / Float64(N)
    print("MOJO_TIMING metabolomics::pathway_enrichment_score", _ns_pathway_enrichment_score, _acc_pathway_enrichment_score)
    var _acc_chemical_similarity_index: Float64 = 0.0
    var _t0_chemical_similarity_index = perf_counter_ns()
    for _ in range(N):
        _acc_chemical_similarity_index += chemical_similarity_index(0.5, 0.5, 0.5)
    var _t1_chemical_similarity_index = perf_counter_ns()
    var _ns_chemical_similarity_index = Float64(_t1_chemical_similarity_index - _t0_chemical_similarity_index) / Float64(N)
    print("MOJO_TIMING metabolomics::chemical_similarity_index", _ns_chemical_similarity_index, _acc_chemical_similarity_index)
    var _acc_metabolic_flux_ratio: Float64 = 0.0
    var _t0_metabolic_flux_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_flux_ratio += metabolic_flux_ratio(0.5, 0.5)
    var _t1_metabolic_flux_ratio = perf_counter_ns()
    var _ns_metabolic_flux_ratio = Float64(_t1_metabolic_flux_ratio - _t0_metabolic_flux_ratio) / Float64(N)
    print("MOJO_TIMING metabolomics::metabolic_flux_ratio", _ns_metabolic_flux_ratio, _acc_metabolic_flux_ratio)
    var _acc_isotope_label_fraction: Float64 = 0.0
    var _t0_isotope_label_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_isotope_label_fraction += isotope_label_fraction(0.5, 0.5)
    var _t1_isotope_label_fraction = perf_counter_ns()
    var _ns_isotope_label_fraction = Float64(_t1_isotope_label_fraction - _t0_isotope_label_fraction) / Float64(N)
    print("MOJO_TIMING metabolomics::isotope_label_fraction", _ns_isotope_label_fraction, _acc_isotope_label_fraction)
    var _acc_metabolite_half_life: Float64 = 0.0
    var _t0_metabolite_half_life = perf_counter_ns()
    for _ in range(N):
        _acc_metabolite_half_life += metabolite_half_life(0.5)
    var _t1_metabolite_half_life = perf_counter_ns()
    var _ns_metabolite_half_life = Float64(_t1_metabolite_half_life - _t0_metabolite_half_life) / Float64(N)
    print("MOJO_TIMING metabolomics::metabolite_half_life", _ns_metabolite_half_life, _acc_metabolite_half_life)
    var _acc_normalization_zscore: Float64 = 0.0
    var _t0_normalization_zscore = perf_counter_ns()
    for _ in range(N):
        _acc_normalization_zscore += normalization_zscore(0.5, 0.5, 0.5)
    var _t1_normalization_zscore = perf_counter_ns()
    var _ns_normalization_zscore = Float64(_t1_normalization_zscore - _t0_normalization_zscore) / Float64(N)
    print("MOJO_TIMING metabolomics::normalization_zscore", _ns_normalization_zscore, _acc_normalization_zscore)
    var _acc_principal_component_variance: Float64 = 0.0
    var _t0_principal_component_variance = perf_counter_ns()
    for _ in range(N):
        _acc_principal_component_variance += principal_component_variance(0.5, 0.5)
    var _t1_principal_component_variance = perf_counter_ns()
    var _ns_principal_component_variance = Float64(_t1_principal_component_variance - _t0_principal_component_variance) / Float64(N)
    print("MOJO_TIMING metabolomics::principal_component_variance", _ns_principal_component_variance, _acc_principal_component_variance)
    var _acc_vip_score: Float64 = 0.0
    var _t0_vip_score = perf_counter_ns()
    for _ in range(N):
        _acc_vip_score += vip_score(0.5, 0.5, 0.5)
    var _t1_vip_score = perf_counter_ns()
    var _ns_vip_score = Float64(_t1_vip_score - _t0_vip_score) / Float64(N)
    print("MOJO_TIMING metabolomics::vip_score", _ns_vip_score, _acc_vip_score)
    var _acc_metabolic_distance: Float64 = 0.0
    var _t0_metabolic_distance = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_distance += metabolic_distance(0.5, 0.5)
    var _t1_metabolic_distance = perf_counter_ns()
    var _ns_metabolic_distance = Float64(_t1_metabolic_distance - _t0_metabolic_distance) / Float64(N)
    print("MOJO_TIMING metabolomics::metabolic_distance", _ns_metabolic_distance, _acc_metabolic_distance)
