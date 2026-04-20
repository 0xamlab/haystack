"""bench_ml_random_forest.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ml.random_forest import bootstrap_indices, feature_subsample, tree_predict_simple, random_forest_predict, random_forest_predict_batch, oob_score, feature_importance_rf, bagging_variance
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

    var _acc_bootstrap_indices: Float64 = 0.0
    var _t0_bootstrap_indices = perf_counter_ns()
    for _ in range(N):
        var _r_bootstrap_indices = bootstrap_indices(5, 5)
        _acc_bootstrap_indices += Float64(len(_r_bootstrap_indices))
    var _t1_bootstrap_indices = perf_counter_ns()
    var _ns_bootstrap_indices = Float64(_t1_bootstrap_indices - _t0_bootstrap_indices) / Float64(N)
    print("MOJO_TIMING ml_random_forest::bootstrap_indices", _ns_bootstrap_indices, _acc_bootstrap_indices)
    var _acc_feature_subsample: Float64 = 0.0
    var _t0_feature_subsample = perf_counter_ns()
    for _ in range(N):
        var _r_feature_subsample = feature_subsample(5, 5)
        _acc_feature_subsample += Float64(len(_r_feature_subsample))
    var _t1_feature_subsample = perf_counter_ns()
    var _ns_feature_subsample = Float64(_t1_feature_subsample - _t0_feature_subsample) / Float64(N)
    print("MOJO_TIMING ml_random_forest::feature_subsample", _ns_feature_subsample, _acc_feature_subsample)
    var _acc_tree_predict_simple: Float64 = 0.0
    var _t0_tree_predict_simple = perf_counter_ns()
    for _ in range(N):
        _acc_tree_predict_simple += tree_predict_simple([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, _li5)
    var _t1_tree_predict_simple = perf_counter_ns()
    var _ns_tree_predict_simple = Float64(_t1_tree_predict_simple - _t0_tree_predict_simple) / Float64(N)
    print("MOJO_TIMING ml_random_forest::tree_predict_simple", _ns_tree_predict_simple, _acc_tree_predict_simple)
    var _acc_random_forest_predict: Float64 = 0.0
    var _t0_random_forest_predict = perf_counter_ns()
    for _ in range(N):
        _acc_random_forest_predict += random_forest_predict([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5, 5, 5)
    var _t1_random_forest_predict = perf_counter_ns()
    var _ns_random_forest_predict = Float64(_t1_random_forest_predict - _t0_random_forest_predict) / Float64(N)
    print("MOJO_TIMING ml_random_forest::random_forest_predict", _ns_random_forest_predict, _acc_random_forest_predict)
    var _acc_random_forest_predict_batch: Float64 = 0.0
    var _t0_random_forest_predict_batch = perf_counter_ns()
    for _ in range(N):
        var _r_random_forest_predict_batch = random_forest_predict_batch([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_random_forest_predict_batch += Float64(len(_r_random_forest_predict_batch))
    var _t1_random_forest_predict_batch = perf_counter_ns()
    var _ns_random_forest_predict_batch = Float64(_t1_random_forest_predict_batch - _t0_random_forest_predict_batch) / Float64(N)
    print("MOJO_TIMING ml_random_forest::random_forest_predict_batch", _ns_random_forest_predict_batch, _acc_random_forest_predict_batch)
    var _acc_oob_score: Float64 = 0.0
    var _t0_oob_score = perf_counter_ns()
    for _ in range(N):
        _acc_oob_score += oob_score([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5, 5)
    var _t1_oob_score = perf_counter_ns()
    var _ns_oob_score = Float64(_t1_oob_score - _t0_oob_score) / Float64(N)
    print("MOJO_TIMING ml_random_forest::oob_score", _ns_oob_score, _acc_oob_score)
    var _acc_feature_importance_rf: Float64 = 0.0
    var _t0_feature_importance_rf = perf_counter_ns()
    for _ in range(N):
        var _r_feature_importance_rf = feature_importance_rf([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5, 5)
        _acc_feature_importance_rf += Float64(len(_r_feature_importance_rf))
    var _t1_feature_importance_rf = perf_counter_ns()
    var _ns_feature_importance_rf = Float64(_t1_feature_importance_rf - _t0_feature_importance_rf) / Float64(N)
    print("MOJO_TIMING ml_random_forest::feature_importance_rf", _ns_feature_importance_rf, _acc_feature_importance_rf)
    var _acc_bagging_variance: Float64 = 0.0
    var _t0_bagging_variance = perf_counter_ns()
    for _ in range(N):
        var _r_bagging_variance = bagging_variance([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_bagging_variance += Float64(len(_r_bagging_variance))
    var _t1_bagging_variance = perf_counter_ns()
    var _ns_bagging_variance = Float64(_t1_bagging_variance - _t0_bagging_variance) / Float64(N)
    print("MOJO_TIMING ml_random_forest::bagging_variance", _ns_bagging_variance, _acc_bagging_variance)
