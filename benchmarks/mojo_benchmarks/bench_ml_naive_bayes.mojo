"""bench_ml_naive_bayes.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.naive_bayes import compute_priors, gaussian_log_likelihood, gaussian_nb_fit, gaussian_nb_predict, gaussian_nb_predict_batch, accuracy, confusion_matrix, precision_recall
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

    var _acc_compute_priors: Float64 = 0.0
    var _t0_compute_priors = perf_counter_ns()
    for _ in range(N):
        var _r_compute_priors = compute_priors(_li5, 5)
        _acc_compute_priors += Float64(len(_r_compute_priors))
    var _t1_compute_priors = perf_counter_ns()
    var _ns_compute_priors = Float64(_t1_compute_priors - _t0_compute_priors) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::compute_priors", _ns_compute_priors, _acc_compute_priors)
    var _result_compute_priors = compute_priors(_li5, 5)
    var _summary_compute_priors = _summary_list_float64(_result_compute_priors)
    print("MOJO_RESULT ml_naive_bayes::compute_priors", _summary_compute_priors)
    var _acc_gaussian_log_likelihood: Float64 = 0.0
    var _t0_gaussian_log_likelihood = perf_counter_ns()
    for _ in range(N):
        _acc_gaussian_log_likelihood += gaussian_log_likelihood(0.5, 0.5, 0.5)
    var _t1_gaussian_log_likelihood = perf_counter_ns()
    var _ns_gaussian_log_likelihood = Float64(_t1_gaussian_log_likelihood - _t0_gaussian_log_likelihood) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_log_likelihood", _ns_gaussian_log_likelihood, _acc_gaussian_log_likelihood)
    var _result_gaussian_log_likelihood = gaussian_log_likelihood(0.5, 0.5, 0.5)
    var _summary_gaussian_log_likelihood = _summary_float64(_result_gaussian_log_likelihood)
    print("MOJO_RESULT ml_naive_bayes::gaussian_log_likelihood", _summary_gaussian_log_likelihood)
    var _acc_gaussian_nb_fit: Float64 = 0.0
    var _t0_gaussian_nb_fit = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_nb_fit = gaussian_nb_fit([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
        _acc_gaussian_nb_fit += Float64(len(_r_gaussian_nb_fit))
    var _t1_gaussian_nb_fit = perf_counter_ns()
    var _ns_gaussian_nb_fit = Float64(_t1_gaussian_nb_fit - _t0_gaussian_nb_fit) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_nb_fit", _ns_gaussian_nb_fit, _acc_gaussian_nb_fit)
    var _result_gaussian_nb_fit = gaussian_nb_fit([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
    var _summary_gaussian_nb_fit = _summary_list_list_float64(_result_gaussian_nb_fit)
    print("MOJO_RESULT ml_naive_bayes::gaussian_nb_fit", _summary_gaussian_nb_fit)
    var _acc_gaussian_nb_predict: Float64 = 0.0
    var _t0_gaussian_nb_predict = perf_counter_ns()
    for _ in range(N):
        _acc_gaussian_nb_predict += Float64(gaussian_nb_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5))
    var _t1_gaussian_nb_predict = perf_counter_ns()
    var _ns_gaussian_nb_predict = Float64(_t1_gaussian_nb_predict - _t0_gaussian_nb_predict) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_nb_predict", _ns_gaussian_nb_predict, _acc_gaussian_nb_predict)
    var _result_gaussian_nb_predict = gaussian_nb_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5)
    var _summary_gaussian_nb_predict = _summary_int(_result_gaussian_nb_predict)
    print("MOJO_RESULT ml_naive_bayes::gaussian_nb_predict", _summary_gaussian_nb_predict)
    var _acc_gaussian_nb_predict_batch: Float64 = 0.0
    var _t0_gaussian_nb_predict_batch = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_nb_predict_batch = gaussian_nb_predict_batch([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_gaussian_nb_predict_batch += Float64(len(_r_gaussian_nb_predict_batch))
    var _t1_gaussian_nb_predict_batch = perf_counter_ns()
    var _ns_gaussian_nb_predict_batch = Float64(_t1_gaussian_nb_predict_batch - _t0_gaussian_nb_predict_batch) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_nb_predict_batch", _ns_gaussian_nb_predict_batch, _acc_gaussian_nb_predict_batch)
    var _result_gaussian_nb_predict_batch = gaussian_nb_predict_batch([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_gaussian_nb_predict_batch = _summary_list_int(_result_gaussian_nb_predict_batch)
    print("MOJO_RESULT ml_naive_bayes::gaussian_nb_predict_batch", _summary_gaussian_nb_predict_batch)
    var _acc_accuracy: Float64 = 0.0
    var _t0_accuracy = perf_counter_ns()
    for _ in range(N):
        _acc_accuracy += accuracy(_li5, _li5)
    var _t1_accuracy = perf_counter_ns()
    var _ns_accuracy = Float64(_t1_accuracy - _t0_accuracy) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::accuracy", _ns_accuracy, _acc_accuracy)
    var _result_accuracy = accuracy(_li5, _li5)
    var _summary_accuracy = _summary_float64(_result_accuracy)
    print("MOJO_RESULT ml_naive_bayes::accuracy", _summary_accuracy)
    var _acc_confusion_matrix: Float64 = 0.0
    var _t0_confusion_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_confusion_matrix = confusion_matrix(_li5, _li5, 5)
        _acc_confusion_matrix += Float64(len(_r_confusion_matrix))
    var _t1_confusion_matrix = perf_counter_ns()
    var _ns_confusion_matrix = Float64(_t1_confusion_matrix - _t0_confusion_matrix) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::confusion_matrix", _ns_confusion_matrix, _acc_confusion_matrix)
    var _result_confusion_matrix = confusion_matrix(_li5, _li5, 5)
    var _summary_confusion_matrix = _summary_list_list_int(_result_confusion_matrix)
    print("MOJO_RESULT ml_naive_bayes::confusion_matrix", _summary_confusion_matrix)
    var _acc_precision_recall: Float64 = 0.0
    var _t0_precision_recall = perf_counter_ns()
    for _ in range(N):
        var _r_precision_recall = precision_recall(_li5, _li5, 5)
        _acc_precision_recall += Float64(len(_r_precision_recall))
    var _t1_precision_recall = perf_counter_ns()
    var _ns_precision_recall = Float64(_t1_precision_recall - _t0_precision_recall) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::precision_recall", _ns_precision_recall, _acc_precision_recall)
    var _result_precision_recall = precision_recall(_li5, _li5, 5)
    var _summary_precision_recall = _summary_list_float64(_result_precision_recall)
    print("MOJO_RESULT ml_naive_bayes::precision_recall", _summary_precision_recall)
