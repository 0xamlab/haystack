"""bench_feature_engineering.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from feature_engineering import minmax_scale, standard_scale, robust_scale, log_transform, box_cox_transform, yeo_johnson_transform, feature_cross, quantile_rank, target_encode_smooth, binning_equal_width
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

    var _acc_minmax_scale: Float64 = 0.0
    var _t0_minmax_scale = perf_counter_ns()
    for _ in range(N):
        _acc_minmax_scale += minmax_scale(0.5, 0.5, 0.5)
    var _t1_minmax_scale = perf_counter_ns()
    var _ns_minmax_scale = Float64(_t1_minmax_scale - _t0_minmax_scale) / Float64(N)
    print("MOJO_TIMING feature_engineering::minmax_scale", _ns_minmax_scale, _acc_minmax_scale)
    var _acc_standard_scale: Float64 = 0.0
    var _t0_standard_scale = perf_counter_ns()
    for _ in range(N):
        _acc_standard_scale += standard_scale(0.5, 0.5, 0.5)
    var _t1_standard_scale = perf_counter_ns()
    var _ns_standard_scale = Float64(_t1_standard_scale - _t0_standard_scale) / Float64(N)
    print("MOJO_TIMING feature_engineering::standard_scale", _ns_standard_scale, _acc_standard_scale)
    var _acc_robust_scale: Float64 = 0.0
    var _t0_robust_scale = perf_counter_ns()
    for _ in range(N):
        _acc_robust_scale += robust_scale(0.5, 0.5, 0.5)
    var _t1_robust_scale = perf_counter_ns()
    var _ns_robust_scale = Float64(_t1_robust_scale - _t0_robust_scale) / Float64(N)
    print("MOJO_TIMING feature_engineering::robust_scale", _ns_robust_scale, _acc_robust_scale)
    var _acc_log_transform: Float64 = 0.0
    var _t0_log_transform = perf_counter_ns()
    for _ in range(N):
        _acc_log_transform += log_transform(0.5)
    var _t1_log_transform = perf_counter_ns()
    var _ns_log_transform = Float64(_t1_log_transform - _t0_log_transform) / Float64(N)
    print("MOJO_TIMING feature_engineering::log_transform", _ns_log_transform, _acc_log_transform)
    var _acc_box_cox_transform: Float64 = 0.0
    var _t0_box_cox_transform = perf_counter_ns()
    for _ in range(N):
        _acc_box_cox_transform += box_cox_transform(0.5, 0.5)
    var _t1_box_cox_transform = perf_counter_ns()
    var _ns_box_cox_transform = Float64(_t1_box_cox_transform - _t0_box_cox_transform) / Float64(N)
    print("MOJO_TIMING feature_engineering::box_cox_transform", _ns_box_cox_transform, _acc_box_cox_transform)
    var _acc_yeo_johnson_transform: Float64 = 0.0
    var _t0_yeo_johnson_transform = perf_counter_ns()
    for _ in range(N):
        _acc_yeo_johnson_transform += yeo_johnson_transform(0.5, 0.5)
    var _t1_yeo_johnson_transform = perf_counter_ns()
    var _ns_yeo_johnson_transform = Float64(_t1_yeo_johnson_transform - _t0_yeo_johnson_transform) / Float64(N)
    print("MOJO_TIMING feature_engineering::yeo_johnson_transform", _ns_yeo_johnson_transform, _acc_yeo_johnson_transform)
    var _acc_feature_cross: Float64 = 0.0
    var _t0_feature_cross = perf_counter_ns()
    for _ in range(N):
        _acc_feature_cross += feature_cross(0.5, 0.5, 0.5)
    var _t1_feature_cross = perf_counter_ns()
    var _ns_feature_cross = Float64(_t1_feature_cross - _t0_feature_cross) / Float64(N)
    print("MOJO_TIMING feature_engineering::feature_cross", _ns_feature_cross, _acc_feature_cross)
    var _acc_quantile_rank: Float64 = 0.0
    var _t0_quantile_rank = perf_counter_ns()
    for _ in range(N):
        _acc_quantile_rank += quantile_rank(0.5, 0.5, 0.5)
    var _t1_quantile_rank = perf_counter_ns()
    var _ns_quantile_rank = Float64(_t1_quantile_rank - _t0_quantile_rank) / Float64(N)
    print("MOJO_TIMING feature_engineering::quantile_rank", _ns_quantile_rank, _acc_quantile_rank)
    var _acc_target_encode_smooth: Float64 = 0.0
    var _t0_target_encode_smooth = perf_counter_ns()
    for _ in range(N):
        _acc_target_encode_smooth += target_encode_smooth(0.5, 0.5, 0.5, 0.5)
    var _t1_target_encode_smooth = perf_counter_ns()
    var _ns_target_encode_smooth = Float64(_t1_target_encode_smooth - _t0_target_encode_smooth) / Float64(N)
    print("MOJO_TIMING feature_engineering::target_encode_smooth", _ns_target_encode_smooth, _acc_target_encode_smooth)
    var _acc_binning_equal_width: Float64 = 0.0
    var _t0_binning_equal_width = perf_counter_ns()
    for _ in range(N):
        _acc_binning_equal_width += binning_equal_width(0.5, 0.5, 0.5, 0.5)
    var _t1_binning_equal_width = perf_counter_ns()
    var _ns_binning_equal_width = Float64(_t1_binning_equal_width - _t0_binning_equal_width) / Float64(N)
    print("MOJO_TIMING feature_engineering::binning_equal_width", _ns_binning_equal_width, _acc_binning_equal_width)
