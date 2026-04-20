"""bench_ml_metrics_extended.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml_metrics_extended import auc_trapezoid, average_precision_term, ndcg_gain, ndcg_discount, map_term, f_beta_score, matthews_corr_coeff, cohen_kappa, calibration_ece_term, brier_score_term
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

    var _acc_auc_trapezoid: Float64 = 0.0
    var _t0_auc_trapezoid = perf_counter_ns()
    for _ in range(N):
        _acc_auc_trapezoid += auc_trapezoid(0.5, 0.5, 0.5, 0.5)
    var _t1_auc_trapezoid = perf_counter_ns()
    var _ns_auc_trapezoid = Float64(_t1_auc_trapezoid - _t0_auc_trapezoid) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::auc_trapezoid", _ns_auc_trapezoid, _acc_auc_trapezoid)
    var _acc_average_precision_term: Float64 = 0.0
    var _t0_average_precision_term = perf_counter_ns()
    for _ in range(N):
        _acc_average_precision_term += average_precision_term(0.5, 0.5)
    var _t1_average_precision_term = perf_counter_ns()
    var _ns_average_precision_term = Float64(_t1_average_precision_term - _t0_average_precision_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::average_precision_term", _ns_average_precision_term, _acc_average_precision_term)
    var _acc_ndcg_gain: Float64 = 0.0
    var _t0_ndcg_gain = perf_counter_ns()
    for _ in range(N):
        _acc_ndcg_gain += ndcg_gain(0.5)
    var _t1_ndcg_gain = perf_counter_ns()
    var _ns_ndcg_gain = Float64(_t1_ndcg_gain - _t0_ndcg_gain) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::ndcg_gain", _ns_ndcg_gain, _acc_ndcg_gain)
    var _acc_ndcg_discount: Float64 = 0.0
    var _t0_ndcg_discount = perf_counter_ns()
    for _ in range(N):
        _acc_ndcg_discount += ndcg_discount(0.5)
    var _t1_ndcg_discount = perf_counter_ns()
    var _ns_ndcg_discount = Float64(_t1_ndcg_discount - _t0_ndcg_discount) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::ndcg_discount", _ns_ndcg_discount, _acc_ndcg_discount)
    var _acc_map_term: Float64 = 0.0
    var _t0_map_term = perf_counter_ns()
    for _ in range(N):
        _acc_map_term += map_term(0.5, 0.5)
    var _t1_map_term = perf_counter_ns()
    var _ns_map_term = Float64(_t1_map_term - _t0_map_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::map_term", _ns_map_term, _acc_map_term)
    var _acc_f_beta_score: Float64 = 0.0
    var _t0_f_beta_score = perf_counter_ns()
    for _ in range(N):
        _acc_f_beta_score += f_beta_score(0.5, 0.5, 0.5)
    var _t1_f_beta_score = perf_counter_ns()
    var _ns_f_beta_score = Float64(_t1_f_beta_score - _t0_f_beta_score) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::f_beta_score", _ns_f_beta_score, _acc_f_beta_score)
    var _acc_matthews_corr_coeff: Float64 = 0.0
    var _t0_matthews_corr_coeff = perf_counter_ns()
    for _ in range(N):
        _acc_matthews_corr_coeff += matthews_corr_coeff(0.5, 0.5, 0.5, 0.5)
    var _t1_matthews_corr_coeff = perf_counter_ns()
    var _ns_matthews_corr_coeff = Float64(_t1_matthews_corr_coeff - _t0_matthews_corr_coeff) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::matthews_corr_coeff", _ns_matthews_corr_coeff, _acc_matthews_corr_coeff)
    var _acc_cohen_kappa: Float64 = 0.0
    var _t0_cohen_kappa = perf_counter_ns()
    for _ in range(N):
        _acc_cohen_kappa += cohen_kappa(0.5, 0.5)
    var _t1_cohen_kappa = perf_counter_ns()
    var _ns_cohen_kappa = Float64(_t1_cohen_kappa - _t0_cohen_kappa) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::cohen_kappa", _ns_cohen_kappa, _acc_cohen_kappa)
    var _acc_calibration_ece_term: Float64 = 0.0
    var _t0_calibration_ece_term = perf_counter_ns()
    for _ in range(N):
        _acc_calibration_ece_term += calibration_ece_term(0.5, 0.5, 0.5, 0.5)
    var _t1_calibration_ece_term = perf_counter_ns()
    var _ns_calibration_ece_term = Float64(_t1_calibration_ece_term - _t0_calibration_ece_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::calibration_ece_term", _ns_calibration_ece_term, _acc_calibration_ece_term)
    var _acc_brier_score_term: Float64 = 0.0
    var _t0_brier_score_term = perf_counter_ns()
    for _ in range(N):
        _acc_brier_score_term += brier_score_term(0.5, 0.5)
    var _t1_brier_score_term = perf_counter_ns()
    var _ns_brier_score_term = Float64(_t1_brier_score_term - _t0_brier_score_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::brier_score_term", _ns_brier_score_term, _acc_brier_score_term)
