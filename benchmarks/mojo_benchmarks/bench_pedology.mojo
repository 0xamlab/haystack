"""bench_pedology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pedology import soil_development_index, clay_illuviation_ratio, rubification_index, organic_horizon_depth, base_saturation_percent, solum_thickness_estimate, profile_development_index, biological_weathering_index, translocation_coefficient, soil_age_from_pedogenesis
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

    var _acc_soil_development_index: Float64 = 0.0
    var _t0_soil_development_index = perf_counter_ns()
    for _ in range(N):
        _acc_soil_development_index += soil_development_index(0.5, 0.5, 0.5)
    var _t1_soil_development_index = perf_counter_ns()
    var _ns_soil_development_index = Float64(_t1_soil_development_index - _t0_soil_development_index) / Float64(N)
    print("MOJO_TIMING pedology::soil_development_index", _ns_soil_development_index, _acc_soil_development_index)
    var _acc_clay_illuviation_ratio: Float64 = 0.0
    var _t0_clay_illuviation_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_clay_illuviation_ratio += clay_illuviation_ratio(0.5, 0.5)
    var _t1_clay_illuviation_ratio = perf_counter_ns()
    var _ns_clay_illuviation_ratio = Float64(_t1_clay_illuviation_ratio - _t0_clay_illuviation_ratio) / Float64(N)
    print("MOJO_TIMING pedology::clay_illuviation_ratio", _ns_clay_illuviation_ratio, _acc_clay_illuviation_ratio)
    var _acc_rubification_index: Float64 = 0.0
    var _t0_rubification_index = perf_counter_ns()
    for _ in range(N):
        _acc_rubification_index += rubification_index(0.5, 0.5, 0.5)
    var _t1_rubification_index = perf_counter_ns()
    var _ns_rubification_index = Float64(_t1_rubification_index - _t0_rubification_index) / Float64(N)
    print("MOJO_TIMING pedology::rubification_index", _ns_rubification_index, _acc_rubification_index)
    var _acc_organic_horizon_depth: Float64 = 0.0
    var _t0_organic_horizon_depth = perf_counter_ns()
    for _ in range(N):
        _acc_organic_horizon_depth += organic_horizon_depth(0.5, 0.5)
    var _t1_organic_horizon_depth = perf_counter_ns()
    var _ns_organic_horizon_depth = Float64(_t1_organic_horizon_depth - _t0_organic_horizon_depth) / Float64(N)
    print("MOJO_TIMING pedology::organic_horizon_depth", _ns_organic_horizon_depth, _acc_organic_horizon_depth)
    var _acc_base_saturation_percent: Float64 = 0.0
    var _t0_base_saturation_percent = perf_counter_ns()
    for _ in range(N):
        _acc_base_saturation_percent += base_saturation_percent(0.5, 0.5)
    var _t1_base_saturation_percent = perf_counter_ns()
    var _ns_base_saturation_percent = Float64(_t1_base_saturation_percent - _t0_base_saturation_percent) / Float64(N)
    print("MOJO_TIMING pedology::base_saturation_percent", _ns_base_saturation_percent, _acc_base_saturation_percent)
    var _acc_solum_thickness_estimate: Float64 = 0.0
    var _t0_solum_thickness_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_solum_thickness_estimate += solum_thickness_estimate(0.5, 0.5, 0.5)
    var _t1_solum_thickness_estimate = perf_counter_ns()
    var _ns_solum_thickness_estimate = Float64(_t1_solum_thickness_estimate - _t0_solum_thickness_estimate) / Float64(N)
    print("MOJO_TIMING pedology::solum_thickness_estimate", _ns_solum_thickness_estimate, _acc_solum_thickness_estimate)
    var _acc_profile_development_index: Float64 = 0.0
    var _t0_profile_development_index = perf_counter_ns()
    for _ in range(N):
        _acc_profile_development_index += profile_development_index(0.5, 0.5, 0.5)
    var _t1_profile_development_index = perf_counter_ns()
    var _ns_profile_development_index = Float64(_t1_profile_development_index - _t0_profile_development_index) / Float64(N)
    print("MOJO_TIMING pedology::profile_development_index", _ns_profile_development_index, _acc_profile_development_index)
    var _acc_biological_weathering_index: Float64 = 0.0
    var _t0_biological_weathering_index = perf_counter_ns()
    for _ in range(N):
        _acc_biological_weathering_index += biological_weathering_index(0.5, 0.5)
    var _t1_biological_weathering_index = perf_counter_ns()
    var _ns_biological_weathering_index = Float64(_t1_biological_weathering_index - _t0_biological_weathering_index) / Float64(N)
    print("MOJO_TIMING pedology::biological_weathering_index", _ns_biological_weathering_index, _acc_biological_weathering_index)
    var _acc_translocation_coefficient: Float64 = 0.0
    var _t0_translocation_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_translocation_coefficient += translocation_coefficient(0.5, 0.5)
    var _t1_translocation_coefficient = perf_counter_ns()
    var _ns_translocation_coefficient = Float64(_t1_translocation_coefficient - _t0_translocation_coefficient) / Float64(N)
    print("MOJO_TIMING pedology::translocation_coefficient", _ns_translocation_coefficient, _acc_translocation_coefficient)
    var _acc_soil_age_from_pedogenesis: Float64 = 0.0
    var _t0_soil_age_from_pedogenesis = perf_counter_ns()
    for _ in range(N):
        _acc_soil_age_from_pedogenesis += soil_age_from_pedogenesis(0.5, 0.5)
    var _t1_soil_age_from_pedogenesis = perf_counter_ns()
    var _ns_soil_age_from_pedogenesis = Float64(_t1_soil_age_from_pedogenesis - _t0_soil_age_from_pedogenesis) / Float64(N)
    print("MOJO_TIMING pedology::soil_age_from_pedogenesis", _ns_soil_age_from_pedogenesis, _acc_soil_age_from_pedogenesis)
