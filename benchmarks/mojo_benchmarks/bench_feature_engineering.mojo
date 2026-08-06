"""bench_feature_engineering.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from feature_engineering import minmax_scale, standard_scale, robust_scale, log_transform, box_cox_transform, yeo_johnson_transform, feature_cross, quantile_rank, target_encode_smooth, binning_equal_width
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

    var _acc_minmax_scale: Float64 = 0.0
    var _t0_minmax_scale = perf_counter_ns()
    for _ in range(N):
        _acc_minmax_scale += minmax_scale(0.5, 0.5, 0.5)
    var _t1_minmax_scale = perf_counter_ns()
    var _ns_minmax_scale = Float64(_t1_minmax_scale - _t0_minmax_scale) / Float64(N)
    print("MOJO_TIMING feature_engineering::minmax_scale", _ns_minmax_scale, _acc_minmax_scale)
    var _result_minmax_scale = minmax_scale(0.5, 0.5, 0.5)
    var _summary_minmax_scale = _summary_float64(_result_minmax_scale)
    print("MOJO_RESULT feature_engineering::minmax_scale", _summary_minmax_scale)
    var _acc_standard_scale: Float64 = 0.0
    var _t0_standard_scale = perf_counter_ns()
    for _ in range(N):
        _acc_standard_scale += standard_scale(0.5, 0.5, 0.5)
    var _t1_standard_scale = perf_counter_ns()
    var _ns_standard_scale = Float64(_t1_standard_scale - _t0_standard_scale) / Float64(N)
    print("MOJO_TIMING feature_engineering::standard_scale", _ns_standard_scale, _acc_standard_scale)
    var _result_standard_scale = standard_scale(0.5, 0.5, 0.5)
    var _summary_standard_scale = _summary_float64(_result_standard_scale)
    print("MOJO_RESULT feature_engineering::standard_scale", _summary_standard_scale)
    var _acc_robust_scale: Float64 = 0.0
    var _t0_robust_scale = perf_counter_ns()
    for _ in range(N):
        _acc_robust_scale += robust_scale(0.5, 0.5, 0.5)
    var _t1_robust_scale = perf_counter_ns()
    var _ns_robust_scale = Float64(_t1_robust_scale - _t0_robust_scale) / Float64(N)
    print("MOJO_TIMING feature_engineering::robust_scale", _ns_robust_scale, _acc_robust_scale)
    var _result_robust_scale = robust_scale(0.5, 0.5, 0.5)
    var _summary_robust_scale = _summary_float64(_result_robust_scale)
    print("MOJO_RESULT feature_engineering::robust_scale", _summary_robust_scale)
    var _acc_log_transform: Float64 = 0.0
    var _t0_log_transform = perf_counter_ns()
    for _ in range(N):
        _acc_log_transform += log_transform(0.5)
    var _t1_log_transform = perf_counter_ns()
    var _ns_log_transform = Float64(_t1_log_transform - _t0_log_transform) / Float64(N)
    print("MOJO_TIMING feature_engineering::log_transform", _ns_log_transform, _acc_log_transform)
    var _result_log_transform = log_transform(0.5)
    var _summary_log_transform = _summary_float64(_result_log_transform)
    print("MOJO_RESULT feature_engineering::log_transform", _summary_log_transform)
    var _acc_box_cox_transform: Float64 = 0.0
    var _t0_box_cox_transform = perf_counter_ns()
    for _ in range(N):
        _acc_box_cox_transform += box_cox_transform(0.5, 0.5)
    var _t1_box_cox_transform = perf_counter_ns()
    var _ns_box_cox_transform = Float64(_t1_box_cox_transform - _t0_box_cox_transform) / Float64(N)
    print("MOJO_TIMING feature_engineering::box_cox_transform", _ns_box_cox_transform, _acc_box_cox_transform)
    var _result_box_cox_transform = box_cox_transform(0.5, 0.5)
    var _summary_box_cox_transform = _summary_float64(_result_box_cox_transform)
    print("MOJO_RESULT feature_engineering::box_cox_transform", _summary_box_cox_transform)
    var _acc_yeo_johnson_transform: Float64 = 0.0
    var _t0_yeo_johnson_transform = perf_counter_ns()
    for _ in range(N):
        _acc_yeo_johnson_transform += yeo_johnson_transform(0.5, 0.5)
    var _t1_yeo_johnson_transform = perf_counter_ns()
    var _ns_yeo_johnson_transform = Float64(_t1_yeo_johnson_transform - _t0_yeo_johnson_transform) / Float64(N)
    print("MOJO_TIMING feature_engineering::yeo_johnson_transform", _ns_yeo_johnson_transform, _acc_yeo_johnson_transform)
    var _result_yeo_johnson_transform = yeo_johnson_transform(0.5, 0.5)
    var _summary_yeo_johnson_transform = _summary_float64(_result_yeo_johnson_transform)
    print("MOJO_RESULT feature_engineering::yeo_johnson_transform", _summary_yeo_johnson_transform)
    var _acc_feature_cross: Float64 = 0.0
    var _t0_feature_cross = perf_counter_ns()
    for _ in range(N):
        _acc_feature_cross += feature_cross(0.5, 0.5, 0.5)
    var _t1_feature_cross = perf_counter_ns()
    var _ns_feature_cross = Float64(_t1_feature_cross - _t0_feature_cross) / Float64(N)
    print("MOJO_TIMING feature_engineering::feature_cross", _ns_feature_cross, _acc_feature_cross)
    var _result_feature_cross = feature_cross(0.5, 0.5, 0.5)
    var _summary_feature_cross = _summary_float64(_result_feature_cross)
    print("MOJO_RESULT feature_engineering::feature_cross", _summary_feature_cross)
    var _acc_quantile_rank: Float64 = 0.0
    var _t0_quantile_rank = perf_counter_ns()
    for _ in range(N):
        _acc_quantile_rank += quantile_rank(0.5, 0.5, 0.5)
    var _t1_quantile_rank = perf_counter_ns()
    var _ns_quantile_rank = Float64(_t1_quantile_rank - _t0_quantile_rank) / Float64(N)
    print("MOJO_TIMING feature_engineering::quantile_rank", _ns_quantile_rank, _acc_quantile_rank)
    var _result_quantile_rank = quantile_rank(0.5, 0.5, 0.5)
    var _summary_quantile_rank = _summary_float64(_result_quantile_rank)
    print("MOJO_RESULT feature_engineering::quantile_rank", _summary_quantile_rank)
    var _acc_target_encode_smooth: Float64 = 0.0
    var _t0_target_encode_smooth = perf_counter_ns()
    for _ in range(N):
        _acc_target_encode_smooth += target_encode_smooth(0.5, 0.5, 0.5, 0.5)
    var _t1_target_encode_smooth = perf_counter_ns()
    var _ns_target_encode_smooth = Float64(_t1_target_encode_smooth - _t0_target_encode_smooth) / Float64(N)
    print("MOJO_TIMING feature_engineering::target_encode_smooth", _ns_target_encode_smooth, _acc_target_encode_smooth)
    var _result_target_encode_smooth = target_encode_smooth(0.5, 0.5, 0.5, 0.5)
    var _summary_target_encode_smooth = _summary_float64(_result_target_encode_smooth)
    print("MOJO_RESULT feature_engineering::target_encode_smooth", _summary_target_encode_smooth)
    var _acc_binning_equal_width: Float64 = 0.0
    var _t0_binning_equal_width = perf_counter_ns()
    for _ in range(N):
        _acc_binning_equal_width += binning_equal_width(0.5, 0.5, 0.5, 0.5)
    var _t1_binning_equal_width = perf_counter_ns()
    var _ns_binning_equal_width = Float64(_t1_binning_equal_width - _t0_binning_equal_width) / Float64(N)
    print("MOJO_TIMING feature_engineering::binning_equal_width", _ns_binning_equal_width, _acc_binning_equal_width)
    var _result_binning_equal_width = binning_equal_width(0.5, 0.5, 0.5, 0.5)
    var _summary_binning_equal_width = _summary_float64(_result_binning_equal_width)
    print("MOJO_RESULT feature_engineering::binning_equal_width", _summary_binning_equal_width)
