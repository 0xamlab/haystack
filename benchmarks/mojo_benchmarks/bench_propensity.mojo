"""bench_propensity.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from propensity import propensity_scores, nearest_neighbor_match, caliper_match, matched_ate, balance_check, propensity_overlap, trimmed_sample, stratified_estimate, match_quality
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

    var _acc_propensity_scores: Float64 = 0.0
    var _t0_propensity_scores = perf_counter_ns()
    for _ in range(N):
        var _r_propensity_scores = propensity_scores([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5)
        _acc_propensity_scores += Float64(len(_r_propensity_scores))
    var _t1_propensity_scores = perf_counter_ns()
    var _ns_propensity_scores = Float64(_t1_propensity_scores - _t0_propensity_scores) / Float64(N)
    print("MOJO_TIMING propensity::propensity_scores", _ns_propensity_scores, _acc_propensity_scores)
    var _acc_nearest_neighbor_match: Float64 = 0.0
    var _t0_nearest_neighbor_match = perf_counter_ns()
    for _ in range(N):
        var _r_nearest_neighbor_match = nearest_neighbor_match(_lf5, _lf5)
        _acc_nearest_neighbor_match += Float64(len(_r_nearest_neighbor_match))
    var _t1_nearest_neighbor_match = perf_counter_ns()
    var _ns_nearest_neighbor_match = Float64(_t1_nearest_neighbor_match - _t0_nearest_neighbor_match) / Float64(N)
    print("MOJO_TIMING propensity::nearest_neighbor_match", _ns_nearest_neighbor_match, _acc_nearest_neighbor_match)
    var _acc_caliper_match: Float64 = 0.0
    var _t0_caliper_match = perf_counter_ns()
    for _ in range(N):
        var _r_caliper_match = caliper_match(_lf5, _lf5, 0.5)
        _acc_caliper_match += Float64(len(_r_caliper_match))
    var _t1_caliper_match = perf_counter_ns()
    var _ns_caliper_match = Float64(_t1_caliper_match - _t0_caliper_match) / Float64(N)
    print("MOJO_TIMING propensity::caliper_match", _ns_caliper_match, _acc_caliper_match)
    var _acc_matched_ate: Float64 = 0.0
    var _t0_matched_ate = perf_counter_ns()
    for _ in range(N):
        _acc_matched_ate += matched_ate(_lf5, _li5, _li5)
    var _t1_matched_ate = perf_counter_ns()
    var _ns_matched_ate = Float64(_t1_matched_ate - _t0_matched_ate) / Float64(N)
    print("MOJO_TIMING propensity::matched_ate", _ns_matched_ate, _acc_matched_ate)
    var _acc_balance_check: Float64 = 0.0
    var _t0_balance_check = perf_counter_ns()
    for _ in range(N):
        _acc_balance_check += balance_check(_lf5, _lf5)
    var _t1_balance_check = perf_counter_ns()
    var _ns_balance_check = Float64(_t1_balance_check - _t0_balance_check) / Float64(N)
    print("MOJO_TIMING propensity::balance_check", _ns_balance_check, _acc_balance_check)
    var _acc_propensity_overlap: Float64 = 0.0
    var _t0_propensity_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_propensity_overlap += propensity_overlap(_lf5, _li5)
    var _t1_propensity_overlap = perf_counter_ns()
    var _ns_propensity_overlap = Float64(_t1_propensity_overlap - _t0_propensity_overlap) / Float64(N)
    print("MOJO_TIMING propensity::propensity_overlap", _ns_propensity_overlap, _acc_propensity_overlap)
    var _acc_trimmed_sample: Float64 = 0.0
    var _t0_trimmed_sample = perf_counter_ns()
    for _ in range(N):
        var _r_trimmed_sample = trimmed_sample(_lf5, _li5, 0.5, 0.5)
        _acc_trimmed_sample += Float64(len(_r_trimmed_sample))
    var _t1_trimmed_sample = perf_counter_ns()
    var _ns_trimmed_sample = Float64(_t1_trimmed_sample - _t0_trimmed_sample) / Float64(N)
    print("MOJO_TIMING propensity::trimmed_sample", _ns_trimmed_sample, _acc_trimmed_sample)
    var _acc_stratified_estimate: Float64 = 0.0
    var _t0_stratified_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_stratified_estimate += stratified_estimate(_lf5, _li5, _lf5, 5)
    var _t1_stratified_estimate = perf_counter_ns()
    var _ns_stratified_estimate = Float64(_t1_stratified_estimate - _t0_stratified_estimate) / Float64(N)
    print("MOJO_TIMING propensity::stratified_estimate", _ns_stratified_estimate, _acc_stratified_estimate)
    var _acc_match_quality: Float64 = 0.0
    var _t0_match_quality = perf_counter_ns()
    for _ in range(N):
        _acc_match_quality += match_quality(_li5)
    var _t1_match_quality = perf_counter_ns()
    var _ns_match_quality = Float64(_t1_match_quality - _t0_match_quality) / Float64(N)
    print("MOJO_TIMING propensity::match_quality", _ns_match_quality, _acc_match_quality)
