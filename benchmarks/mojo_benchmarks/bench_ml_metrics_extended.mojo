"""bench_ml_metrics_extended.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml_metrics_extended import auc_trapezoid, average_precision_term, ndcg_gain, ndcg_discount, map_term, f_beta_score, matthews_corr_coeff, cohen_kappa, calibration_ece_term, brier_score_term
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_auc_trapezoid: Float64 = 0.0
    var _t0_auc_trapezoid = perf_counter_ns()
    for _ in range(N):
        _acc_auc_trapezoid += auc_trapezoid(0.5, 0.5, 0.5, 0.5)
    var _t1_auc_trapezoid = perf_counter_ns()
    var _ns_auc_trapezoid = Float64(_t1_auc_trapezoid - _t0_auc_trapezoid) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::auc_trapezoid", _ns_auc_trapezoid, _acc_auc_trapezoid)
    var _result_auc_trapezoid = auc_trapezoid(0.5, 0.5, 0.5, 0.5)
    var _summary_auc_trapezoid = _summary_float64(_result_auc_trapezoid)
    print("MOJO_RESULT ml_metrics_extended::auc_trapezoid", _summary_auc_trapezoid)
    var _acc_average_precision_term: Float64 = 0.0
    var _t0_average_precision_term = perf_counter_ns()
    for _ in range(N):
        _acc_average_precision_term += average_precision_term(0.5, 0.5)
    var _t1_average_precision_term = perf_counter_ns()
    var _ns_average_precision_term = Float64(_t1_average_precision_term - _t0_average_precision_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::average_precision_term", _ns_average_precision_term, _acc_average_precision_term)
    var _result_average_precision_term = average_precision_term(0.5, 0.5)
    var _summary_average_precision_term = _summary_float64(_result_average_precision_term)
    print("MOJO_RESULT ml_metrics_extended::average_precision_term", _summary_average_precision_term)
    var _acc_ndcg_gain: Float64 = 0.0
    var _t0_ndcg_gain = perf_counter_ns()
    for _ in range(N):
        _acc_ndcg_gain += ndcg_gain(0.5)
    var _t1_ndcg_gain = perf_counter_ns()
    var _ns_ndcg_gain = Float64(_t1_ndcg_gain - _t0_ndcg_gain) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::ndcg_gain", _ns_ndcg_gain, _acc_ndcg_gain)
    var _result_ndcg_gain = ndcg_gain(0.5)
    var _summary_ndcg_gain = _summary_float64(_result_ndcg_gain)
    print("MOJO_RESULT ml_metrics_extended::ndcg_gain", _summary_ndcg_gain)
    var _acc_ndcg_discount: Float64 = 0.0
    var _t0_ndcg_discount = perf_counter_ns()
    for _ in range(N):
        _acc_ndcg_discount += ndcg_discount(0.5)
    var _t1_ndcg_discount = perf_counter_ns()
    var _ns_ndcg_discount = Float64(_t1_ndcg_discount - _t0_ndcg_discount) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::ndcg_discount", _ns_ndcg_discount, _acc_ndcg_discount)
    var _result_ndcg_discount = ndcg_discount(0.5)
    var _summary_ndcg_discount = _summary_float64(_result_ndcg_discount)
    print("MOJO_RESULT ml_metrics_extended::ndcg_discount", _summary_ndcg_discount)
    var _acc_map_term: Float64 = 0.0
    var _t0_map_term = perf_counter_ns()
    for _ in range(N):
        _acc_map_term += map_term(0.5, 0.5)
    var _t1_map_term = perf_counter_ns()
    var _ns_map_term = Float64(_t1_map_term - _t0_map_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::map_term", _ns_map_term, _acc_map_term)
    var _result_map_term = map_term(0.5, 0.5)
    var _summary_map_term = _summary_float64(_result_map_term)
    print("MOJO_RESULT ml_metrics_extended::map_term", _summary_map_term)
    var _acc_f_beta_score: Float64 = 0.0
    var _t0_f_beta_score = perf_counter_ns()
    for _ in range(N):
        _acc_f_beta_score += f_beta_score(0.5, 0.5, 0.5)
    var _t1_f_beta_score = perf_counter_ns()
    var _ns_f_beta_score = Float64(_t1_f_beta_score - _t0_f_beta_score) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::f_beta_score", _ns_f_beta_score, _acc_f_beta_score)
    var _result_f_beta_score = f_beta_score(0.5, 0.5, 0.5)
    var _summary_f_beta_score = _summary_float64(_result_f_beta_score)
    print("MOJO_RESULT ml_metrics_extended::f_beta_score", _summary_f_beta_score)
    var _acc_matthews_corr_coeff: Float64 = 0.0
    var _t0_matthews_corr_coeff = perf_counter_ns()
    for _ in range(N):
        _acc_matthews_corr_coeff += matthews_corr_coeff(0.5, 0.5, 0.5, 0.5)
    var _t1_matthews_corr_coeff = perf_counter_ns()
    var _ns_matthews_corr_coeff = Float64(_t1_matthews_corr_coeff - _t0_matthews_corr_coeff) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::matthews_corr_coeff", _ns_matthews_corr_coeff, _acc_matthews_corr_coeff)
    var _result_matthews_corr_coeff = matthews_corr_coeff(0.5, 0.5, 0.5, 0.5)
    var _summary_matthews_corr_coeff = _summary_float64(_result_matthews_corr_coeff)
    print("MOJO_RESULT ml_metrics_extended::matthews_corr_coeff", _summary_matthews_corr_coeff)
    var _acc_cohen_kappa: Float64 = 0.0
    var _t0_cohen_kappa = perf_counter_ns()
    for _ in range(N):
        _acc_cohen_kappa += cohen_kappa(0.5, 0.5)
    var _t1_cohen_kappa = perf_counter_ns()
    var _ns_cohen_kappa = Float64(_t1_cohen_kappa - _t0_cohen_kappa) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::cohen_kappa", _ns_cohen_kappa, _acc_cohen_kappa)
    var _result_cohen_kappa = cohen_kappa(0.5, 0.5)
    var _summary_cohen_kappa = _summary_float64(_result_cohen_kappa)
    print("MOJO_RESULT ml_metrics_extended::cohen_kappa", _summary_cohen_kappa)
    var _acc_calibration_ece_term: Float64 = 0.0
    var _t0_calibration_ece_term = perf_counter_ns()
    for _ in range(N):
        _acc_calibration_ece_term += calibration_ece_term(0.5, 0.5, 0.5, 0.5)
    var _t1_calibration_ece_term = perf_counter_ns()
    var _ns_calibration_ece_term = Float64(_t1_calibration_ece_term - _t0_calibration_ece_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::calibration_ece_term", _ns_calibration_ece_term, _acc_calibration_ece_term)
    var _result_calibration_ece_term = calibration_ece_term(0.5, 0.5, 0.5, 0.5)
    var _summary_calibration_ece_term = _summary_float64(_result_calibration_ece_term)
    print("MOJO_RESULT ml_metrics_extended::calibration_ece_term", _summary_calibration_ece_term)
    var _acc_brier_score_term: Float64 = 0.0
    var _t0_brier_score_term = perf_counter_ns()
    for _ in range(N):
        _acc_brier_score_term += brier_score_term(0.5, 0.5)
    var _t1_brier_score_term = perf_counter_ns()
    var _ns_brier_score_term = Float64(_t1_brier_score_term - _t0_brier_score_term) / Float64(N)
    print("MOJO_TIMING ml_metrics_extended::brier_score_term", _ns_brier_score_term, _acc_brier_score_term)
    var _result_brier_score_term = brier_score_term(0.5, 0.5)
    var _summary_brier_score_term = _summary_float64(_result_brier_score_term)
    print("MOJO_RESULT ml_metrics_extended::brier_score_term", _summary_brier_score_term)
