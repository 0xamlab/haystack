"""bench_dendrology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dendrology import tree_height_from_hypsometer, sin_approx, cos_approx, crown_area, crown_competition_factor, stem_taper_percentage, heartwood_ratio, sapwood_area_from_dbh, root_biomass_allometric, leaf_biomass_allometric, tree_age_from_rings, foliar_nitrogen_content
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

    var _acc_tree_height_from_hypsometer: Float64 = 0.0
    var _t0_tree_height_from_hypsometer = perf_counter_ns()
    for _ in range(N):
        _acc_tree_height_from_hypsometer += tree_height_from_hypsometer(0.5, 0.5, 0.5)
    var _t1_tree_height_from_hypsometer = perf_counter_ns()
    var _ns_tree_height_from_hypsometer = Float64(_t1_tree_height_from_hypsometer - _t0_tree_height_from_hypsometer) / Float64(N)
    print("MOJO_TIMING dendrology::tree_height_from_hypsometer", _ns_tree_height_from_hypsometer, _acc_tree_height_from_hypsometer)
    var _result_tree_height_from_hypsometer = tree_height_from_hypsometer(0.5, 0.5, 0.5)
    var _summary_tree_height_from_hypsometer = _summary_float64(_result_tree_height_from_hypsometer)
    print("MOJO_RESULT dendrology::tree_height_from_hypsometer", _summary_tree_height_from_hypsometer)
    var _acc_sin_approx: Float64 = 0.0
    var _t0_sin_approx = perf_counter_ns()
    for _ in range(N):
        _acc_sin_approx += sin_approx(0.5)
    var _t1_sin_approx = perf_counter_ns()
    var _ns_sin_approx = Float64(_t1_sin_approx - _t0_sin_approx) / Float64(N)
    print("MOJO_TIMING dendrology::sin_approx", _ns_sin_approx, _acc_sin_approx)
    var _result_sin_approx = sin_approx(0.5)
    var _summary_sin_approx = _summary_float64(_result_sin_approx)
    print("MOJO_RESULT dendrology::sin_approx", _summary_sin_approx)
    var _acc_cos_approx: Float64 = 0.0
    var _t0_cos_approx = perf_counter_ns()
    for _ in range(N):
        _acc_cos_approx += cos_approx(0.5)
    var _t1_cos_approx = perf_counter_ns()
    var _ns_cos_approx = Float64(_t1_cos_approx - _t0_cos_approx) / Float64(N)
    print("MOJO_TIMING dendrology::cos_approx", _ns_cos_approx, _acc_cos_approx)
    var _result_cos_approx = cos_approx(0.5)
    var _summary_cos_approx = _summary_float64(_result_cos_approx)
    print("MOJO_RESULT dendrology::cos_approx", _summary_cos_approx)
    var _acc_crown_area: Float64 = 0.0
    var _t0_crown_area = perf_counter_ns()
    for _ in range(N):
        _acc_crown_area += crown_area(0.5, 0.5)
    var _t1_crown_area = perf_counter_ns()
    var _ns_crown_area = Float64(_t1_crown_area - _t0_crown_area) / Float64(N)
    print("MOJO_TIMING dendrology::crown_area", _ns_crown_area, _acc_crown_area)
    var _result_crown_area = crown_area(0.5, 0.5)
    var _summary_crown_area = _summary_float64(_result_crown_area)
    print("MOJO_RESULT dendrology::crown_area", _summary_crown_area)
    var _acc_crown_competition_factor: Float64 = 0.0
    var _t0_crown_competition_factor = perf_counter_ns()
    for _ in range(N):
        _acc_crown_competition_factor += crown_competition_factor(0.5, 0.5)
    var _t1_crown_competition_factor = perf_counter_ns()
    var _ns_crown_competition_factor = Float64(_t1_crown_competition_factor - _t0_crown_competition_factor) / Float64(N)
    print("MOJO_TIMING dendrology::crown_competition_factor", _ns_crown_competition_factor, _acc_crown_competition_factor)
    var _result_crown_competition_factor = crown_competition_factor(0.5, 0.5)
    var _summary_crown_competition_factor = _summary_float64(_result_crown_competition_factor)
    print("MOJO_RESULT dendrology::crown_competition_factor", _summary_crown_competition_factor)
    var _acc_stem_taper_percentage: Float64 = 0.0
    var _t0_stem_taper_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_stem_taper_percentage += stem_taper_percentage(0.5, 0.5)
    var _t1_stem_taper_percentage = perf_counter_ns()
    var _ns_stem_taper_percentage = Float64(_t1_stem_taper_percentage - _t0_stem_taper_percentage) / Float64(N)
    print("MOJO_TIMING dendrology::stem_taper_percentage", _ns_stem_taper_percentage, _acc_stem_taper_percentage)
    var _result_stem_taper_percentage = stem_taper_percentage(0.5, 0.5)
    var _summary_stem_taper_percentage = _summary_float64(_result_stem_taper_percentage)
    print("MOJO_RESULT dendrology::stem_taper_percentage", _summary_stem_taper_percentage)
    var _acc_heartwood_ratio: Float64 = 0.0
    var _t0_heartwood_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_heartwood_ratio += heartwood_ratio(0.5, 0.5)
    var _t1_heartwood_ratio = perf_counter_ns()
    var _ns_heartwood_ratio = Float64(_t1_heartwood_ratio - _t0_heartwood_ratio) / Float64(N)
    print("MOJO_TIMING dendrology::heartwood_ratio", _ns_heartwood_ratio, _acc_heartwood_ratio)
    var _result_heartwood_ratio = heartwood_ratio(0.5, 0.5)
    var _summary_heartwood_ratio = _summary_float64(_result_heartwood_ratio)
    print("MOJO_RESULT dendrology::heartwood_ratio", _summary_heartwood_ratio)
    var _acc_sapwood_area_from_dbh: Float64 = 0.0
    var _t0_sapwood_area_from_dbh = perf_counter_ns()
    for _ in range(N):
        _acc_sapwood_area_from_dbh += sapwood_area_from_dbh(0.5, 0.5)
    var _t1_sapwood_area_from_dbh = perf_counter_ns()
    var _ns_sapwood_area_from_dbh = Float64(_t1_sapwood_area_from_dbh - _t0_sapwood_area_from_dbh) / Float64(N)
    print("MOJO_TIMING dendrology::sapwood_area_from_dbh", _ns_sapwood_area_from_dbh, _acc_sapwood_area_from_dbh)
    var _result_sapwood_area_from_dbh = sapwood_area_from_dbh(0.5, 0.5)
    var _summary_sapwood_area_from_dbh = _summary_float64(_result_sapwood_area_from_dbh)
    print("MOJO_RESULT dendrology::sapwood_area_from_dbh", _summary_sapwood_area_from_dbh)
    var _acc_root_biomass_allometric: Float64 = 0.0
    var _t0_root_biomass_allometric = perf_counter_ns()
    for _ in range(N):
        _acc_root_biomass_allometric += root_biomass_allometric(0.5)
    var _t1_root_biomass_allometric = perf_counter_ns()
    var _ns_root_biomass_allometric = Float64(_t1_root_biomass_allometric - _t0_root_biomass_allometric) / Float64(N)
    print("MOJO_TIMING dendrology::root_biomass_allometric", _ns_root_biomass_allometric, _acc_root_biomass_allometric)
    var _result_root_biomass_allometric = root_biomass_allometric(0.5)
    var _summary_root_biomass_allometric = _summary_float64(_result_root_biomass_allometric)
    print("MOJO_RESULT dendrology::root_biomass_allometric", _summary_root_biomass_allometric)
    var _acc_leaf_biomass_allometric: Float64 = 0.0
    var _t0_leaf_biomass_allometric = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_biomass_allometric += leaf_biomass_allometric(0.5, 0.5)
    var _t1_leaf_biomass_allometric = perf_counter_ns()
    var _ns_leaf_biomass_allometric = Float64(_t1_leaf_biomass_allometric - _t0_leaf_biomass_allometric) / Float64(N)
    print("MOJO_TIMING dendrology::leaf_biomass_allometric", _ns_leaf_biomass_allometric, _acc_leaf_biomass_allometric)
    var _result_leaf_biomass_allometric = leaf_biomass_allometric(0.5, 0.5)
    var _summary_leaf_biomass_allometric = _summary_float64(_result_leaf_biomass_allometric)
    print("MOJO_RESULT dendrology::leaf_biomass_allometric", _summary_leaf_biomass_allometric)
    var _acc_tree_age_from_rings: Float64 = 0.0
    var _t0_tree_age_from_rings = perf_counter_ns()
    for _ in range(N):
        _acc_tree_age_from_rings += tree_age_from_rings(0.5, 0.5)
    var _t1_tree_age_from_rings = perf_counter_ns()
    var _ns_tree_age_from_rings = Float64(_t1_tree_age_from_rings - _t0_tree_age_from_rings) / Float64(N)
    print("MOJO_TIMING dendrology::tree_age_from_rings", _ns_tree_age_from_rings, _acc_tree_age_from_rings)
    var _result_tree_age_from_rings = tree_age_from_rings(0.5, 0.5)
    var _summary_tree_age_from_rings = _summary_float64(_result_tree_age_from_rings)
    print("MOJO_RESULT dendrology::tree_age_from_rings", _summary_tree_age_from_rings)
    var _acc_foliar_nitrogen_content: Float64 = 0.0
    var _t0_foliar_nitrogen_content = perf_counter_ns()
    for _ in range(N):
        _acc_foliar_nitrogen_content += foliar_nitrogen_content(0.5, 0.5)
    var _t1_foliar_nitrogen_content = perf_counter_ns()
    var _ns_foliar_nitrogen_content = Float64(_t1_foliar_nitrogen_content - _t0_foliar_nitrogen_content) / Float64(N)
    print("MOJO_TIMING dendrology::foliar_nitrogen_content", _ns_foliar_nitrogen_content, _acc_foliar_nitrogen_content)
    var _result_foliar_nitrogen_content = foliar_nitrogen_content(0.5, 0.5)
    var _summary_foliar_nitrogen_content = _summary_float64(_result_foliar_nitrogen_content)
    print("MOJO_RESULT dendrology::foliar_nitrogen_content", _summary_foliar_nitrogen_content)
