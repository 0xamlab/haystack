"""bench_dendrology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dendrology import tree_height_from_hypsometer, sin_approx, cos_approx, crown_area, crown_competition_factor, stem_taper_percentage, heartwood_ratio, sapwood_area_from_dbh, root_biomass_allometric, leaf_biomass_allometric, tree_age_from_rings, foliar_nitrogen_content
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

    var _acc_tree_height_from_hypsometer: Float64 = 0.0
    var _t0_tree_height_from_hypsometer = perf_counter_ns()
    for _ in range(N):
        _acc_tree_height_from_hypsometer += tree_height_from_hypsometer(0.5, 0.5, 0.5)
    var _t1_tree_height_from_hypsometer = perf_counter_ns()
    var _ns_tree_height_from_hypsometer = Float64(_t1_tree_height_from_hypsometer - _t0_tree_height_from_hypsometer) / Float64(N)
    print("MOJO_TIMING dendrology::tree_height_from_hypsometer", _ns_tree_height_from_hypsometer, _acc_tree_height_from_hypsometer)
    var _acc_sin_approx: Float64 = 0.0
    var _t0_sin_approx = perf_counter_ns()
    for _ in range(N):
        _acc_sin_approx += sin_approx(0.5)
    var _t1_sin_approx = perf_counter_ns()
    var _ns_sin_approx = Float64(_t1_sin_approx - _t0_sin_approx) / Float64(N)
    print("MOJO_TIMING dendrology::sin_approx", _ns_sin_approx, _acc_sin_approx)
    var _acc_cos_approx: Float64 = 0.0
    var _t0_cos_approx = perf_counter_ns()
    for _ in range(N):
        _acc_cos_approx += cos_approx(0.5)
    var _t1_cos_approx = perf_counter_ns()
    var _ns_cos_approx = Float64(_t1_cos_approx - _t0_cos_approx) / Float64(N)
    print("MOJO_TIMING dendrology::cos_approx", _ns_cos_approx, _acc_cos_approx)
    var _acc_crown_area: Float64 = 0.0
    var _t0_crown_area = perf_counter_ns()
    for _ in range(N):
        _acc_crown_area += crown_area(0.5, 0.5)
    var _t1_crown_area = perf_counter_ns()
    var _ns_crown_area = Float64(_t1_crown_area - _t0_crown_area) / Float64(N)
    print("MOJO_TIMING dendrology::crown_area", _ns_crown_area, _acc_crown_area)
    var _acc_crown_competition_factor: Float64 = 0.0
    var _t0_crown_competition_factor = perf_counter_ns()
    for _ in range(N):
        _acc_crown_competition_factor += crown_competition_factor(0.5, 0.5)
    var _t1_crown_competition_factor = perf_counter_ns()
    var _ns_crown_competition_factor = Float64(_t1_crown_competition_factor - _t0_crown_competition_factor) / Float64(N)
    print("MOJO_TIMING dendrology::crown_competition_factor", _ns_crown_competition_factor, _acc_crown_competition_factor)
    var _acc_stem_taper_percentage: Float64 = 0.0
    var _t0_stem_taper_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_stem_taper_percentage += stem_taper_percentage(0.5, 0.5)
    var _t1_stem_taper_percentage = perf_counter_ns()
    var _ns_stem_taper_percentage = Float64(_t1_stem_taper_percentage - _t0_stem_taper_percentage) / Float64(N)
    print("MOJO_TIMING dendrology::stem_taper_percentage", _ns_stem_taper_percentage, _acc_stem_taper_percentage)
    var _acc_heartwood_ratio: Float64 = 0.0
    var _t0_heartwood_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_heartwood_ratio += heartwood_ratio(0.5, 0.5)
    var _t1_heartwood_ratio = perf_counter_ns()
    var _ns_heartwood_ratio = Float64(_t1_heartwood_ratio - _t0_heartwood_ratio) / Float64(N)
    print("MOJO_TIMING dendrology::heartwood_ratio", _ns_heartwood_ratio, _acc_heartwood_ratio)
    var _acc_sapwood_area_from_dbh: Float64 = 0.0
    var _t0_sapwood_area_from_dbh = perf_counter_ns()
    for _ in range(N):
        _acc_sapwood_area_from_dbh += sapwood_area_from_dbh(0.5, 0.5)
    var _t1_sapwood_area_from_dbh = perf_counter_ns()
    var _ns_sapwood_area_from_dbh = Float64(_t1_sapwood_area_from_dbh - _t0_sapwood_area_from_dbh) / Float64(N)
    print("MOJO_TIMING dendrology::sapwood_area_from_dbh", _ns_sapwood_area_from_dbh, _acc_sapwood_area_from_dbh)
    var _acc_root_biomass_allometric: Float64 = 0.0
    var _t0_root_biomass_allometric = perf_counter_ns()
    for _ in range(N):
        _acc_root_biomass_allometric += root_biomass_allometric(0.5)
    var _t1_root_biomass_allometric = perf_counter_ns()
    var _ns_root_biomass_allometric = Float64(_t1_root_biomass_allometric - _t0_root_biomass_allometric) / Float64(N)
    print("MOJO_TIMING dendrology::root_biomass_allometric", _ns_root_biomass_allometric, _acc_root_biomass_allometric)
    var _acc_leaf_biomass_allometric: Float64 = 0.0
    var _t0_leaf_biomass_allometric = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_biomass_allometric += leaf_biomass_allometric(0.5, 0.5)
    var _t1_leaf_biomass_allometric = perf_counter_ns()
    var _ns_leaf_biomass_allometric = Float64(_t1_leaf_biomass_allometric - _t0_leaf_biomass_allometric) / Float64(N)
    print("MOJO_TIMING dendrology::leaf_biomass_allometric", _ns_leaf_biomass_allometric, _acc_leaf_biomass_allometric)
    var _acc_tree_age_from_rings: Float64 = 0.0
    var _t0_tree_age_from_rings = perf_counter_ns()
    for _ in range(N):
        _acc_tree_age_from_rings += tree_age_from_rings(0.5, 0.5)
    var _t1_tree_age_from_rings = perf_counter_ns()
    var _ns_tree_age_from_rings = Float64(_t1_tree_age_from_rings - _t0_tree_age_from_rings) / Float64(N)
    print("MOJO_TIMING dendrology::tree_age_from_rings", _ns_tree_age_from_rings, _acc_tree_age_from_rings)
    var _acc_foliar_nitrogen_content: Float64 = 0.0
    var _t0_foliar_nitrogen_content = perf_counter_ns()
    for _ in range(N):
        _acc_foliar_nitrogen_content += foliar_nitrogen_content(0.5, 0.5)
    var _t1_foliar_nitrogen_content = perf_counter_ns()
    var _ns_foliar_nitrogen_content = Float64(_t1_foliar_nitrogen_content - _t0_foliar_nitrogen_content) / Float64(N)
    print("MOJO_TIMING dendrology::foliar_nitrogen_content", _ns_foliar_nitrogen_content, _acc_foliar_nitrogen_content)
