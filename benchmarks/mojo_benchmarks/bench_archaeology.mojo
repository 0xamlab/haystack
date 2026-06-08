"""bench_archaeology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from archaeology import radiocarbon_age_bp, calibrated_date_linear, stratigraphy_depth_to_age_linear, artifact_density, site_area_from_scatter, ceramic_seriation_similarity, dating_uncertainty_combined, occupation_span, discard_rate, surveyed_area_coverage, excavation_volume, artifact_diversity_index
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

    var _acc_radiocarbon_age_bp: Float64 = 0.0
    var _t0_radiocarbon_age_bp = perf_counter_ns()
    for _ in range(N):
        _acc_radiocarbon_age_bp += radiocarbon_age_bp(0.5, 0.5)
    var _t1_radiocarbon_age_bp = perf_counter_ns()
    var _ns_radiocarbon_age_bp = Float64(_t1_radiocarbon_age_bp - _t0_radiocarbon_age_bp) / Float64(N)
    print("MOJO_TIMING archaeology::radiocarbon_age_bp", _ns_radiocarbon_age_bp, _acc_radiocarbon_age_bp)
    var _result_radiocarbon_age_bp = radiocarbon_age_bp(0.5, 0.5)
    var _summary_radiocarbon_age_bp = _summary_float64(_result_radiocarbon_age_bp)
    print("MOJO_RESULT archaeology::radiocarbon_age_bp", _summary_radiocarbon_age_bp)
    var _acc_calibrated_date_linear: Float64 = 0.0
    var _t0_calibrated_date_linear = perf_counter_ns()
    for _ in range(N):
        _acc_calibrated_date_linear += calibrated_date_linear(0.5, 0.5)
    var _t1_calibrated_date_linear = perf_counter_ns()
    var _ns_calibrated_date_linear = Float64(_t1_calibrated_date_linear - _t0_calibrated_date_linear) / Float64(N)
    print("MOJO_TIMING archaeology::calibrated_date_linear", _ns_calibrated_date_linear, _acc_calibrated_date_linear)
    var _result_calibrated_date_linear = calibrated_date_linear(0.5, 0.5)
    var _summary_calibrated_date_linear = _summary_float64(_result_calibrated_date_linear)
    print("MOJO_RESULT archaeology::calibrated_date_linear", _summary_calibrated_date_linear)
    var _acc_stratigraphy_depth_to_age_linear: Float64 = 0.0
    var _t0_stratigraphy_depth_to_age_linear = perf_counter_ns()
    for _ in range(N):
        _acc_stratigraphy_depth_to_age_linear += stratigraphy_depth_to_age_linear(0.5, 0.5)
    var _t1_stratigraphy_depth_to_age_linear = perf_counter_ns()
    var _ns_stratigraphy_depth_to_age_linear = Float64(_t1_stratigraphy_depth_to_age_linear - _t0_stratigraphy_depth_to_age_linear) / Float64(N)
    print("MOJO_TIMING archaeology::stratigraphy_depth_to_age_linear", _ns_stratigraphy_depth_to_age_linear, _acc_stratigraphy_depth_to_age_linear)
    var _result_stratigraphy_depth_to_age_linear = stratigraphy_depth_to_age_linear(0.5, 0.5)
    var _summary_stratigraphy_depth_to_age_linear = _summary_float64(_result_stratigraphy_depth_to_age_linear)
    print("MOJO_RESULT archaeology::stratigraphy_depth_to_age_linear", _summary_stratigraphy_depth_to_age_linear)
    var _acc_artifact_density: Float64 = 0.0
    var _t0_artifact_density = perf_counter_ns()
    for _ in range(N):
        _acc_artifact_density += artifact_density(0.5, 0.5)
    var _t1_artifact_density = perf_counter_ns()
    var _ns_artifact_density = Float64(_t1_artifact_density - _t0_artifact_density) / Float64(N)
    print("MOJO_TIMING archaeology::artifact_density", _ns_artifact_density, _acc_artifact_density)
    var _result_artifact_density = artifact_density(0.5, 0.5)
    var _summary_artifact_density = _summary_float64(_result_artifact_density)
    print("MOJO_RESULT archaeology::artifact_density", _summary_artifact_density)
    var _acc_site_area_from_scatter: Float64 = 0.0
    var _t0_site_area_from_scatter = perf_counter_ns()
    for _ in range(N):
        _acc_site_area_from_scatter += site_area_from_scatter(0.5, 0.5)
    var _t1_site_area_from_scatter = perf_counter_ns()
    var _ns_site_area_from_scatter = Float64(_t1_site_area_from_scatter - _t0_site_area_from_scatter) / Float64(N)
    print("MOJO_TIMING archaeology::site_area_from_scatter", _ns_site_area_from_scatter, _acc_site_area_from_scatter)
    var _result_site_area_from_scatter = site_area_from_scatter(0.5, 0.5)
    var _summary_site_area_from_scatter = _summary_float64(_result_site_area_from_scatter)
    print("MOJO_RESULT archaeology::site_area_from_scatter", _summary_site_area_from_scatter)
    var _acc_ceramic_seriation_similarity: Float64 = 0.0
    var _t0_ceramic_seriation_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_ceramic_seriation_similarity += ceramic_seriation_similarity(0.5, 0.5, 0.5)
    var _t1_ceramic_seriation_similarity = perf_counter_ns()
    var _ns_ceramic_seriation_similarity = Float64(_t1_ceramic_seriation_similarity - _t0_ceramic_seriation_similarity) / Float64(N)
    print("MOJO_TIMING archaeology::ceramic_seriation_similarity", _ns_ceramic_seriation_similarity, _acc_ceramic_seriation_similarity)
    var _result_ceramic_seriation_similarity = ceramic_seriation_similarity(0.5, 0.5, 0.5)
    var _summary_ceramic_seriation_similarity = _summary_float64(_result_ceramic_seriation_similarity)
    print("MOJO_RESULT archaeology::ceramic_seriation_similarity", _summary_ceramic_seriation_similarity)
    var _acc_dating_uncertainty_combined: Float64 = 0.0
    var _t0_dating_uncertainty_combined = perf_counter_ns()
    for _ in range(N):
        _acc_dating_uncertainty_combined += dating_uncertainty_combined(0.5, 0.5)
    var _t1_dating_uncertainty_combined = perf_counter_ns()
    var _ns_dating_uncertainty_combined = Float64(_t1_dating_uncertainty_combined - _t0_dating_uncertainty_combined) / Float64(N)
    print("MOJO_TIMING archaeology::dating_uncertainty_combined", _ns_dating_uncertainty_combined, _acc_dating_uncertainty_combined)
    var _result_dating_uncertainty_combined = dating_uncertainty_combined(0.5, 0.5)
    var _summary_dating_uncertainty_combined = _summary_float64(_result_dating_uncertainty_combined)
    print("MOJO_RESULT archaeology::dating_uncertainty_combined", _summary_dating_uncertainty_combined)
    var _acc_occupation_span: Float64 = 0.0
    var _t0_occupation_span = perf_counter_ns()
    for _ in range(N):
        _acc_occupation_span += occupation_span(0.5, 0.5)
    var _t1_occupation_span = perf_counter_ns()
    var _ns_occupation_span = Float64(_t1_occupation_span - _t0_occupation_span) / Float64(N)
    print("MOJO_TIMING archaeology::occupation_span", _ns_occupation_span, _acc_occupation_span)
    var _result_occupation_span = occupation_span(0.5, 0.5)
    var _summary_occupation_span = _summary_float64(_result_occupation_span)
    print("MOJO_RESULT archaeology::occupation_span", _summary_occupation_span)
    var _acc_discard_rate: Float64 = 0.0
    var _t0_discard_rate = perf_counter_ns()
    for _ in range(N):
        _acc_discard_rate += discard_rate(0.5, 0.5, 0.5)
    var _t1_discard_rate = perf_counter_ns()
    var _ns_discard_rate = Float64(_t1_discard_rate - _t0_discard_rate) / Float64(N)
    print("MOJO_TIMING archaeology::discard_rate", _ns_discard_rate, _acc_discard_rate)
    var _result_discard_rate = discard_rate(0.5, 0.5, 0.5)
    var _summary_discard_rate = _summary_float64(_result_discard_rate)
    print("MOJO_RESULT archaeology::discard_rate", _summary_discard_rate)
    var _acc_surveyed_area_coverage: Float64 = 0.0
    var _t0_surveyed_area_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_surveyed_area_coverage += surveyed_area_coverage(0.5, 0.5)
    var _t1_surveyed_area_coverage = perf_counter_ns()
    var _ns_surveyed_area_coverage = Float64(_t1_surveyed_area_coverage - _t0_surveyed_area_coverage) / Float64(N)
    print("MOJO_TIMING archaeology::surveyed_area_coverage", _ns_surveyed_area_coverage, _acc_surveyed_area_coverage)
    var _result_surveyed_area_coverage = surveyed_area_coverage(0.5, 0.5)
    var _summary_surveyed_area_coverage = _summary_float64(_result_surveyed_area_coverage)
    print("MOJO_RESULT archaeology::surveyed_area_coverage", _summary_surveyed_area_coverage)
    var _acc_excavation_volume: Float64 = 0.0
    var _t0_excavation_volume = perf_counter_ns()
    for _ in range(N):
        _acc_excavation_volume += excavation_volume(0.5, 0.5, 0.5)
    var _t1_excavation_volume = perf_counter_ns()
    var _ns_excavation_volume = Float64(_t1_excavation_volume - _t0_excavation_volume) / Float64(N)
    print("MOJO_TIMING archaeology::excavation_volume", _ns_excavation_volume, _acc_excavation_volume)
    var _result_excavation_volume = excavation_volume(0.5, 0.5, 0.5)
    var _summary_excavation_volume = _summary_float64(_result_excavation_volume)
    print("MOJO_RESULT archaeology::excavation_volume", _summary_excavation_volume)
    var _acc_artifact_diversity_index: Float64 = 0.0
    var _t0_artifact_diversity_index = perf_counter_ns()
    for _ in range(N):
        _acc_artifact_diversity_index += artifact_diversity_index(0.5, 0.5)
    var _t1_artifact_diversity_index = perf_counter_ns()
    var _ns_artifact_diversity_index = Float64(_t1_artifact_diversity_index - _t0_artifact_diversity_index) / Float64(N)
    print("MOJO_TIMING archaeology::artifact_diversity_index", _ns_artifact_diversity_index, _acc_artifact_diversity_index)
    var _result_artifact_diversity_index = artifact_diversity_index(0.5, 0.5)
    var _summary_artifact_diversity_index = _summary_float64(_result_artifact_diversity_index)
    print("MOJO_RESULT archaeology::artifact_diversity_index", _summary_artifact_diversity_index)
