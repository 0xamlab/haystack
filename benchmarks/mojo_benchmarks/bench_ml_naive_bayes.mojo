"""bench_ml_naive_bayes.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.naive_bayes import compute_priors, gaussian_log_likelihood, gaussian_nb_fit, gaussian_nb_predict, gaussian_nb_predict_batch, accuracy, confusion_matrix, precision_recall
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

    var _acc_compute_priors: Float64 = 0.0
    var _t0_compute_priors = perf_counter_ns()
    for _ in range(N):
        var _r_compute_priors = compute_priors(_li5, 5)
        _acc_compute_priors += Float64(len(_r_compute_priors))
    var _t1_compute_priors = perf_counter_ns()
    var _ns_compute_priors = Float64(_t1_compute_priors - _t0_compute_priors) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::compute_priors", _ns_compute_priors, _acc_compute_priors)
    var _acc_gaussian_log_likelihood: Float64 = 0.0
    var _t0_gaussian_log_likelihood = perf_counter_ns()
    for _ in range(N):
        _acc_gaussian_log_likelihood += gaussian_log_likelihood(0.5, 0.5, 0.5)
    var _t1_gaussian_log_likelihood = perf_counter_ns()
    var _ns_gaussian_log_likelihood = Float64(_t1_gaussian_log_likelihood - _t0_gaussian_log_likelihood) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_log_likelihood", _ns_gaussian_log_likelihood, _acc_gaussian_log_likelihood)
    var _acc_gaussian_nb_fit: Float64 = 0.0
    var _t0_gaussian_nb_fit = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_nb_fit = gaussian_nb_fit([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _li5, 5)
        _acc_gaussian_nb_fit += Float64(len(_r_gaussian_nb_fit))
    var _t1_gaussian_nb_fit = perf_counter_ns()
    var _ns_gaussian_nb_fit = Float64(_t1_gaussian_nb_fit - _t0_gaussian_nb_fit) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_nb_fit", _ns_gaussian_nb_fit, _acc_gaussian_nb_fit)
    var _acc_gaussian_nb_predict: Float64 = 0.0
    var _t0_gaussian_nb_predict = perf_counter_ns()
    for _ in range(N):
        _acc_gaussian_nb_predict += Float64(gaussian_nb_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5))
    var _t1_gaussian_nb_predict = perf_counter_ns()
    var _ns_gaussian_nb_predict = Float64(_t1_gaussian_nb_predict - _t0_gaussian_nb_predict) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_nb_predict", _ns_gaussian_nb_predict, _acc_gaussian_nb_predict)
    var _acc_gaussian_nb_predict_batch: Float64 = 0.0
    var _t0_gaussian_nb_predict_batch = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_nb_predict_batch = gaussian_nb_predict_batch([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_gaussian_nb_predict_batch += Float64(len(_r_gaussian_nb_predict_batch))
    var _t1_gaussian_nb_predict_batch = perf_counter_ns()
    var _ns_gaussian_nb_predict_batch = Float64(_t1_gaussian_nb_predict_batch - _t0_gaussian_nb_predict_batch) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::gaussian_nb_predict_batch", _ns_gaussian_nb_predict_batch, _acc_gaussian_nb_predict_batch)
    var _acc_accuracy: Float64 = 0.0
    var _t0_accuracy = perf_counter_ns()
    for _ in range(N):
        _acc_accuracy += accuracy(_li5, _li5)
    var _t1_accuracy = perf_counter_ns()
    var _ns_accuracy = Float64(_t1_accuracy - _t0_accuracy) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::accuracy", _ns_accuracy, _acc_accuracy)
    var _acc_confusion_matrix: Float64 = 0.0
    var _t0_confusion_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_confusion_matrix = confusion_matrix(_li5, _li5, 5)
        _acc_confusion_matrix += Float64(len(_r_confusion_matrix))
    var _t1_confusion_matrix = perf_counter_ns()
    var _ns_confusion_matrix = Float64(_t1_confusion_matrix - _t0_confusion_matrix) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::confusion_matrix", _ns_confusion_matrix, _acc_confusion_matrix)
    var _acc_precision_recall: Float64 = 0.0
    var _t0_precision_recall = perf_counter_ns()
    for _ in range(N):
        var _r_precision_recall = precision_recall(_li5, _li5, 5)
        _acc_precision_recall += Float64(len(_r_precision_recall))
    var _t1_precision_recall = perf_counter_ns()
    var _ns_precision_recall = Float64(_t1_precision_recall - _t0_precision_recall) / Float64(N)
    print("MOJO_TIMING ml_naive_bayes::precision_recall", _ns_precision_recall, _acc_precision_recall)
