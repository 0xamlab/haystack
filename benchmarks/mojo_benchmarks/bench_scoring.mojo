"""bench_scoring.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from scoring import sigmoid, logit, log_odds_to_score, score_to_log_odds, woe, iv, gini_coefficient, ks_statistic, score_band, linear_score, normalize_score
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

    var _acc_sigmoid: Float64 = 0.0
    var _t0_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_sigmoid += sigmoid(0.5)
    var _t1_sigmoid = perf_counter_ns()
    var _ns_sigmoid = Float64(_t1_sigmoid - _t0_sigmoid) / Float64(N)
    print("MOJO_TIMING scoring::sigmoid", _ns_sigmoid, _acc_sigmoid)
    var _acc_logit: Float64 = 0.0
    var _t0_logit = perf_counter_ns()
    for _ in range(N):
        _acc_logit += logit(0.5)
    var _t1_logit = perf_counter_ns()
    var _ns_logit = Float64(_t1_logit - _t0_logit) / Float64(N)
    print("MOJO_TIMING scoring::logit", _ns_logit, _acc_logit)
    var _acc_log_odds_to_score: Float64 = 0.0
    var _t0_log_odds_to_score = perf_counter_ns()
    for _ in range(N):
        _acc_log_odds_to_score += log_odds_to_score(0.5, 0.5, 0.5)
    var _t1_log_odds_to_score = perf_counter_ns()
    var _ns_log_odds_to_score = Float64(_t1_log_odds_to_score - _t0_log_odds_to_score) / Float64(N)
    print("MOJO_TIMING scoring::log_odds_to_score", _ns_log_odds_to_score, _acc_log_odds_to_score)
    var _acc_score_to_log_odds: Float64 = 0.0
    var _t0_score_to_log_odds = perf_counter_ns()
    for _ in range(N):
        _acc_score_to_log_odds += score_to_log_odds(0.5, 0.5, 0.5)
    var _t1_score_to_log_odds = perf_counter_ns()
    var _ns_score_to_log_odds = Float64(_t1_score_to_log_odds - _t0_score_to_log_odds) / Float64(N)
    print("MOJO_TIMING scoring::score_to_log_odds", _ns_score_to_log_odds, _acc_score_to_log_odds)
    var _acc_woe: Float64 = 0.0
    var _t0_woe = perf_counter_ns()
    for _ in range(N):
        _acc_woe += woe(5, 5, 5, 5)
    var _t1_woe = perf_counter_ns()
    var _ns_woe = Float64(_t1_woe - _t0_woe) / Float64(N)
    print("MOJO_TIMING scoring::woe", _ns_woe, _acc_woe)
    var _acc_iv: Float64 = 0.0
    var _t0_iv = perf_counter_ns()
    for _ in range(N):
        _acc_iv += iv(_lf5, _lf5, _lf5)
    var _t1_iv = perf_counter_ns()
    var _ns_iv = Float64(_t1_iv - _t0_iv) / Float64(N)
    print("MOJO_TIMING scoring::iv", _ns_iv, _acc_iv)
    var _acc_gini_coefficient: Float64 = 0.0
    var _t0_gini_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_gini_coefficient += gini_coefficient(_lf5, _lf5)
    var _t1_gini_coefficient = perf_counter_ns()
    var _ns_gini_coefficient = Float64(_t1_gini_coefficient - _t0_gini_coefficient) / Float64(N)
    print("MOJO_TIMING scoring::gini_coefficient", _ns_gini_coefficient, _acc_gini_coefficient)
    var _acc_ks_statistic: Float64 = 0.0
    var _t0_ks_statistic = perf_counter_ns()
    for _ in range(N):
        _acc_ks_statistic += ks_statistic(_lf5, _lf5)
    var _t1_ks_statistic = perf_counter_ns()
    var _ns_ks_statistic = Float64(_t1_ks_statistic - _t0_ks_statistic) / Float64(N)
    print("MOJO_TIMING scoring::ks_statistic", _ns_ks_statistic, _acc_ks_statistic)
    var _acc_score_band: Float64 = 0.0
    var _t0_score_band = perf_counter_ns()
    for _ in range(N):
        _ = score_band(0.5, _lf5, ["a","b","c","d","e"])
    var _t1_score_band = perf_counter_ns()
    var _ns_score_band = Float64(_t1_score_band - _t0_score_band) / Float64(N)
    print("MOJO_TIMING scoring::score_band", _ns_score_band, _acc_score_band)
    var _acc_linear_score: Float64 = 0.0
    var _t0_linear_score = perf_counter_ns()
    for _ in range(N):
        _acc_linear_score += linear_score(_lf5, _lf5, 0.5)
    var _t1_linear_score = perf_counter_ns()
    var _ns_linear_score = Float64(_t1_linear_score - _t0_linear_score) / Float64(N)
    print("MOJO_TIMING scoring::linear_score", _ns_linear_score, _acc_linear_score)
    var _acc_normalize_score: Float64 = 0.0
    var _t0_normalize_score = perf_counter_ns()
    for _ in range(N):
        _acc_normalize_score += normalize_score(0.5, 0.5, 0.5)
    var _t1_normalize_score = perf_counter_ns()
    var _ns_normalize_score = Float64(_t1_normalize_score - _t0_normalize_score) / Float64(N)
    print("MOJO_TIMING scoring::normalize_score", _ns_normalize_score, _acc_normalize_score)
