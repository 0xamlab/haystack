"""bench_causal.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from causal import ate, att, propensity_score, ipw_estimate, diff_in_diff, regression_discontinuity, iv_estimate, stratified_ate, cohens_d, needed_sample_size_ate
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

    var _acc_ate: Float64 = 0.0
    var _t0_ate = perf_counter_ns()
    for _ in range(N):
        _acc_ate += ate(_lf5, _lf5)
    var _t1_ate = perf_counter_ns()
    var _ns_ate = Float64(_t1_ate - _t0_ate) / Float64(N)
    print("MOJO_TIMING causal::ate", _ns_ate, _acc_ate)
    var _acc_att: Float64 = 0.0
    var _t0_att = perf_counter_ns()
    for _ in range(N):
        _acc_att += att(_lf5, _lf5)
    var _t1_att = perf_counter_ns()
    var _ns_att = Float64(_t1_att - _t0_att) / Float64(N)
    print("MOJO_TIMING causal::att", _ns_att, _acc_att)
    var _acc_propensity_score: Float64 = 0.0
    var _t0_propensity_score = perf_counter_ns()
    for _ in range(N):
        var _r_propensity_score = propensity_score(_lf5, _li5)
        _acc_propensity_score += Float64(len(_r_propensity_score))
    var _t1_propensity_score = perf_counter_ns()
    var _ns_propensity_score = Float64(_t1_propensity_score - _t0_propensity_score) / Float64(N)
    print("MOJO_TIMING causal::propensity_score", _ns_propensity_score, _acc_propensity_score)
    var _acc_ipw_estimate: Float64 = 0.0
    var _t0_ipw_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_ipw_estimate += ipw_estimate(_lf5, _li5, _lf5)
    var _t1_ipw_estimate = perf_counter_ns()
    var _ns_ipw_estimate = Float64(_t1_ipw_estimate - _t0_ipw_estimate) / Float64(N)
    print("MOJO_TIMING causal::ipw_estimate", _ns_ipw_estimate, _acc_ipw_estimate)
    var _acc_diff_in_diff: Float64 = 0.0
    var _t0_diff_in_diff = perf_counter_ns()
    for _ in range(N):
        _acc_diff_in_diff += diff_in_diff(_lf5, _lf5, _lf5, _lf5)
    var _t1_diff_in_diff = perf_counter_ns()
    var _ns_diff_in_diff = Float64(_t1_diff_in_diff - _t0_diff_in_diff) / Float64(N)
    print("MOJO_TIMING causal::diff_in_diff", _ns_diff_in_diff, _acc_diff_in_diff)
    var _acc_regression_discontinuity: Float64 = 0.0
    var _t0_regression_discontinuity = perf_counter_ns()
    for _ in range(N):
        _acc_regression_discontinuity += regression_discontinuity(_lf5, _lf5, 0.5)
    var _t1_regression_discontinuity = perf_counter_ns()
    var _ns_regression_discontinuity = Float64(_t1_regression_discontinuity - _t0_regression_discontinuity) / Float64(N)
    print("MOJO_TIMING causal::regression_discontinuity", _ns_regression_discontinuity, _acc_regression_discontinuity)
    var _acc_iv_estimate: Float64 = 0.0
    var _t0_iv_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_iv_estimate += iv_estimate(_lf5, _lf5, _lf5)
    var _t1_iv_estimate = perf_counter_ns()
    var _ns_iv_estimate = Float64(_t1_iv_estimate - _t0_iv_estimate) / Float64(N)
    print("MOJO_TIMING causal::iv_estimate", _ns_iv_estimate, _acc_iv_estimate)
    var _acc_stratified_ate: Float64 = 0.0
    var _t0_stratified_ate = perf_counter_ns()
    for _ in range(N):
        _acc_stratified_ate += stratified_ate(_lf5, _li5, _li5, 5)
    var _t1_stratified_ate = perf_counter_ns()
    var _ns_stratified_ate = Float64(_t1_stratified_ate - _t0_stratified_ate) / Float64(N)
    print("MOJO_TIMING causal::stratified_ate", _ns_stratified_ate, _acc_stratified_ate)
    var _acc_cohens_d: Float64 = 0.0
    var _t0_cohens_d = perf_counter_ns()
    for _ in range(N):
        _acc_cohens_d += cohens_d(_lf5, _lf5)
    var _t1_cohens_d = perf_counter_ns()
    var _ns_cohens_d = Float64(_t1_cohens_d - _t0_cohens_d) / Float64(N)
    print("MOJO_TIMING causal::cohens_d", _ns_cohens_d, _acc_cohens_d)
    var _acc_needed_sample_size_ate: Float64 = 0.0
    var _t0_needed_sample_size_ate = perf_counter_ns()
    for _ in range(N):
        _acc_needed_sample_size_ate += Float64(needed_sample_size_ate(0.5, 0.5, 0.5, 0.5))
    var _t1_needed_sample_size_ate = perf_counter_ns()
    var _ns_needed_sample_size_ate = Float64(_t1_needed_sample_size_ate - _t0_needed_sample_size_ate) / Float64(N)
    print("MOJO_TIMING causal::needed_sample_size_ate", _ns_needed_sample_size_ate, _acc_needed_sample_size_ate)
