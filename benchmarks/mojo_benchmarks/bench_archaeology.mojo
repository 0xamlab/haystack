"""bench_archaeology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from archaeology import radiocarbon_age_bp, calibrated_date_linear, stratigraphy_depth_to_age_linear, artifact_density, site_area_from_scatter, ceramic_seriation_similarity, dating_uncertainty_combined, occupation_span, discard_rate, surveyed_area_coverage, excavation_volume, artifact_diversity_index
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

    var _acc_radiocarbon_age_bp: Float64 = 0.0
    var _t0_radiocarbon_age_bp = perf_counter_ns()
    for _ in range(N):
        _acc_radiocarbon_age_bp += radiocarbon_age_bp(0.5, 0.5)
    var _t1_radiocarbon_age_bp = perf_counter_ns()
    var _ns_radiocarbon_age_bp = Float64(_t1_radiocarbon_age_bp - _t0_radiocarbon_age_bp) / Float64(N)
    print("MOJO_TIMING archaeology::radiocarbon_age_bp", _ns_radiocarbon_age_bp, _acc_radiocarbon_age_bp)
    var _acc_calibrated_date_linear: Float64 = 0.0
    var _t0_calibrated_date_linear = perf_counter_ns()
    for _ in range(N):
        _acc_calibrated_date_linear += calibrated_date_linear(0.5, 0.5)
    var _t1_calibrated_date_linear = perf_counter_ns()
    var _ns_calibrated_date_linear = Float64(_t1_calibrated_date_linear - _t0_calibrated_date_linear) / Float64(N)
    print("MOJO_TIMING archaeology::calibrated_date_linear", _ns_calibrated_date_linear, _acc_calibrated_date_linear)
    var _acc_stratigraphy_depth_to_age_linear: Float64 = 0.0
    var _t0_stratigraphy_depth_to_age_linear = perf_counter_ns()
    for _ in range(N):
        _acc_stratigraphy_depth_to_age_linear += stratigraphy_depth_to_age_linear(0.5, 0.5)
    var _t1_stratigraphy_depth_to_age_linear = perf_counter_ns()
    var _ns_stratigraphy_depth_to_age_linear = Float64(_t1_stratigraphy_depth_to_age_linear - _t0_stratigraphy_depth_to_age_linear) / Float64(N)
    print("MOJO_TIMING archaeology::stratigraphy_depth_to_age_linear", _ns_stratigraphy_depth_to_age_linear, _acc_stratigraphy_depth_to_age_linear)
    var _acc_artifact_density: Float64 = 0.0
    var _t0_artifact_density = perf_counter_ns()
    for _ in range(N):
        _acc_artifact_density += artifact_density(0.5, 0.5)
    var _t1_artifact_density = perf_counter_ns()
    var _ns_artifact_density = Float64(_t1_artifact_density - _t0_artifact_density) / Float64(N)
    print("MOJO_TIMING archaeology::artifact_density", _ns_artifact_density, _acc_artifact_density)
    var _acc_site_area_from_scatter: Float64 = 0.0
    var _t0_site_area_from_scatter = perf_counter_ns()
    for _ in range(N):
        _acc_site_area_from_scatter += site_area_from_scatter(0.5, 0.5)
    var _t1_site_area_from_scatter = perf_counter_ns()
    var _ns_site_area_from_scatter = Float64(_t1_site_area_from_scatter - _t0_site_area_from_scatter) / Float64(N)
    print("MOJO_TIMING archaeology::site_area_from_scatter", _ns_site_area_from_scatter, _acc_site_area_from_scatter)
    var _acc_ceramic_seriation_similarity: Float64 = 0.0
    var _t0_ceramic_seriation_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_ceramic_seriation_similarity += ceramic_seriation_similarity(0.5, 0.5, 0.5)
    var _t1_ceramic_seriation_similarity = perf_counter_ns()
    var _ns_ceramic_seriation_similarity = Float64(_t1_ceramic_seriation_similarity - _t0_ceramic_seriation_similarity) / Float64(N)
    print("MOJO_TIMING archaeology::ceramic_seriation_similarity", _ns_ceramic_seriation_similarity, _acc_ceramic_seriation_similarity)
    var _acc_dating_uncertainty_combined: Float64 = 0.0
    var _t0_dating_uncertainty_combined = perf_counter_ns()
    for _ in range(N):
        _acc_dating_uncertainty_combined += dating_uncertainty_combined(0.5, 0.5)
    var _t1_dating_uncertainty_combined = perf_counter_ns()
    var _ns_dating_uncertainty_combined = Float64(_t1_dating_uncertainty_combined - _t0_dating_uncertainty_combined) / Float64(N)
    print("MOJO_TIMING archaeology::dating_uncertainty_combined", _ns_dating_uncertainty_combined, _acc_dating_uncertainty_combined)
    var _acc_occupation_span: Float64 = 0.0
    var _t0_occupation_span = perf_counter_ns()
    for _ in range(N):
        _acc_occupation_span += occupation_span(0.5, 0.5)
    var _t1_occupation_span = perf_counter_ns()
    var _ns_occupation_span = Float64(_t1_occupation_span - _t0_occupation_span) / Float64(N)
    print("MOJO_TIMING archaeology::occupation_span", _ns_occupation_span, _acc_occupation_span)
    var _acc_discard_rate: Float64 = 0.0
    var _t0_discard_rate = perf_counter_ns()
    for _ in range(N):
        _acc_discard_rate += discard_rate(0.5, 0.5, 0.5)
    var _t1_discard_rate = perf_counter_ns()
    var _ns_discard_rate = Float64(_t1_discard_rate - _t0_discard_rate) / Float64(N)
    print("MOJO_TIMING archaeology::discard_rate", _ns_discard_rate, _acc_discard_rate)
    var _acc_surveyed_area_coverage: Float64 = 0.0
    var _t0_surveyed_area_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_surveyed_area_coverage += surveyed_area_coverage(0.5, 0.5)
    var _t1_surveyed_area_coverage = perf_counter_ns()
    var _ns_surveyed_area_coverage = Float64(_t1_surveyed_area_coverage - _t0_surveyed_area_coverage) / Float64(N)
    print("MOJO_TIMING archaeology::surveyed_area_coverage", _ns_surveyed_area_coverage, _acc_surveyed_area_coverage)
    var _acc_excavation_volume: Float64 = 0.0
    var _t0_excavation_volume = perf_counter_ns()
    for _ in range(N):
        _acc_excavation_volume += excavation_volume(0.5, 0.5, 0.5)
    var _t1_excavation_volume = perf_counter_ns()
    var _ns_excavation_volume = Float64(_t1_excavation_volume - _t0_excavation_volume) / Float64(N)
    print("MOJO_TIMING archaeology::excavation_volume", _ns_excavation_volume, _acc_excavation_volume)
    var _acc_artifact_diversity_index: Float64 = 0.0
    var _t0_artifact_diversity_index = perf_counter_ns()
    for _ in range(N):
        _acc_artifact_diversity_index += artifact_diversity_index(0.5, 0.5)
    var _t1_artifact_diversity_index = perf_counter_ns()
    var _ns_artifact_diversity_index = Float64(_t1_artifact_diversity_index - _t0_artifact_diversity_index) / Float64(N)
    print("MOJO_TIMING archaeology::artifact_diversity_index", _ns_artifact_diversity_index, _acc_artifact_diversity_index)
