"""bench_ml_metrics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.metrics import accuracy, mse, rmse, mae, r2_score, confusion_matrix, precision_recall_f1, PRF1Result
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

    var _acc_accuracy: Float64 = 0.0
    var _t0_accuracy = perf_counter_ns()
    for _ in range(N):
        _acc_accuracy += accuracy(_lf5, _lf5)
    var _t1_accuracy = perf_counter_ns()
    var _ns_accuracy = Float64(_t1_accuracy - _t0_accuracy) / Float64(N)
    print("MOJO_TIMING ml_metrics::accuracy", _ns_accuracy, _acc_accuracy)
    var _acc_mse: Float64 = 0.0
    var _t0_mse = perf_counter_ns()
    for _ in range(N):
        _acc_mse += mse(_lf5, _lf5)
    var _t1_mse = perf_counter_ns()
    var _ns_mse = Float64(_t1_mse - _t0_mse) / Float64(N)
    print("MOJO_TIMING ml_metrics::mse", _ns_mse, _acc_mse)
    var _acc_rmse: Float64 = 0.0
    var _t0_rmse = perf_counter_ns()
    for _ in range(N):
        _acc_rmse += rmse(_lf5, _lf5)
    var _t1_rmse = perf_counter_ns()
    var _ns_rmse = Float64(_t1_rmse - _t0_rmse) / Float64(N)
    print("MOJO_TIMING ml_metrics::rmse", _ns_rmse, _acc_rmse)
    var _acc_mae: Float64 = 0.0
    var _t0_mae = perf_counter_ns()
    for _ in range(N):
        _acc_mae += mae(_lf5, _lf5)
    var _t1_mae = perf_counter_ns()
    var _ns_mae = Float64(_t1_mae - _t0_mae) / Float64(N)
    print("MOJO_TIMING ml_metrics::mae", _ns_mae, _acc_mae)
    var _acc_r2_score: Float64 = 0.0
    var _t0_r2_score = perf_counter_ns()
    for _ in range(N):
        _acc_r2_score += r2_score(_lf5, _lf5)
    var _t1_r2_score = perf_counter_ns()
    var _ns_r2_score = Float64(_t1_r2_score - _t0_r2_score) / Float64(N)
    print("MOJO_TIMING ml_metrics::r2_score", _ns_r2_score, _acc_r2_score)
    var _acc_confusion_matrix: Float64 = 0.0
    var _t0_confusion_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_confusion_matrix = confusion_matrix(_li5, _li5, 5)
        _acc_confusion_matrix += Float64(len(_r_confusion_matrix))
    var _t1_confusion_matrix = perf_counter_ns()
    var _ns_confusion_matrix = Float64(_t1_confusion_matrix - _t0_confusion_matrix) / Float64(N)
    print("MOJO_TIMING ml_metrics::confusion_matrix", _ns_confusion_matrix, _acc_confusion_matrix)
    var _keeper_precision_recall_f1 = List[PRF1Result]()
    _keeper_precision_recall_f1.append(precision_recall_f1(_li5, _li5))
    var _acc_precision_recall_f1: Float64 = 0.0
    var _t0_precision_recall_f1 = perf_counter_ns()
    for _ in range(N):
        _keeper_precision_recall_f1[0] = precision_recall_f1(_li5, _li5)
        _acc_precision_recall_f1 += Float64(len(_keeper_precision_recall_f1))
    var _t1_precision_recall_f1 = perf_counter_ns()
    var _ns_precision_recall_f1 = Float64(_t1_precision_recall_f1 - _t0_precision_recall_f1) / Float64(N)
    print("MOJO_TIMING ml_metrics::precision_recall_f1", _ns_precision_recall_f1, _acc_precision_recall_f1)
