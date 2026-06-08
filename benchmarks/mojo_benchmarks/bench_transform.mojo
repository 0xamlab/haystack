"""bench_transform.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from transform import log_transform, log1p_transform, box_cox, standardize, min_max_scale, robust_scale, quantile_transform, power_transform, clamp_values, rank_transform, abs_transform, reciprocal_transform
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

    var _acc_log_transform: Float64 = 0.0
    var _t0_log_transform = perf_counter_ns()
    for _ in range(N):
        var _r_log_transform = log_transform(_lf5)
        _acc_log_transform += Float64(len(_r_log_transform))
    var _t1_log_transform = perf_counter_ns()
    var _ns_log_transform = Float64(_t1_log_transform - _t0_log_transform) / Float64(N)
    print("MOJO_TIMING transform::log_transform", _ns_log_transform, _acc_log_transform)
    var _result_log_transform = log_transform(_lf5)
    var _summary_log_transform = _summary_list_float64(_result_log_transform)
    print("MOJO_RESULT transform::log_transform", _summary_log_transform)
    var _acc_log1p_transform: Float64 = 0.0
    var _t0_log1p_transform = perf_counter_ns()
    for _ in range(N):
        var _r_log1p_transform = log1p_transform(_lf5)
        _acc_log1p_transform += Float64(len(_r_log1p_transform))
    var _t1_log1p_transform = perf_counter_ns()
    var _ns_log1p_transform = Float64(_t1_log1p_transform - _t0_log1p_transform) / Float64(N)
    print("MOJO_TIMING transform::log1p_transform", _ns_log1p_transform, _acc_log1p_transform)
    var _result_log1p_transform = log1p_transform(_lf5)
    var _summary_log1p_transform = _summary_list_float64(_result_log1p_transform)
    print("MOJO_RESULT transform::log1p_transform", _summary_log1p_transform)
    var _acc_box_cox: Float64 = 0.0
    var _t0_box_cox = perf_counter_ns()
    for _ in range(N):
        var _r_box_cox = box_cox(_lf5, 0.5)
        _acc_box_cox += Float64(len(_r_box_cox))
    var _t1_box_cox = perf_counter_ns()
    var _ns_box_cox = Float64(_t1_box_cox - _t0_box_cox) / Float64(N)
    print("MOJO_TIMING transform::box_cox", _ns_box_cox, _acc_box_cox)
    var _result_box_cox = box_cox(_lf5, 0.5)
    var _summary_box_cox = _summary_list_float64(_result_box_cox)
    print("MOJO_RESULT transform::box_cox", _summary_box_cox)
    var _acc_standardize: Float64 = 0.0
    var _t0_standardize = perf_counter_ns()
    for _ in range(N):
        var _r_standardize = standardize(_lf5)
        _acc_standardize += Float64(len(_r_standardize))
    var _t1_standardize = perf_counter_ns()
    var _ns_standardize = Float64(_t1_standardize - _t0_standardize) / Float64(N)
    print("MOJO_TIMING transform::standardize", _ns_standardize, _acc_standardize)
    var _result_standardize = standardize(_lf5)
    var _summary_standardize = _summary_list_float64(_result_standardize)
    print("MOJO_RESULT transform::standardize", _summary_standardize)
    var _acc_min_max_scale: Float64 = 0.0
    var _t0_min_max_scale = perf_counter_ns()
    for _ in range(N):
        var _r_min_max_scale = min_max_scale(_lf5, 0.5, 0.5)
        _acc_min_max_scale += Float64(len(_r_min_max_scale))
    var _t1_min_max_scale = perf_counter_ns()
    var _ns_min_max_scale = Float64(_t1_min_max_scale - _t0_min_max_scale) / Float64(N)
    print("MOJO_TIMING transform::min_max_scale", _ns_min_max_scale, _acc_min_max_scale)
    var _result_min_max_scale = min_max_scale(_lf5, 0.5, 0.5)
    var _summary_min_max_scale = _summary_list_float64(_result_min_max_scale)
    print("MOJO_RESULT transform::min_max_scale", _summary_min_max_scale)
    var _acc_robust_scale: Float64 = 0.0
    var _t0_robust_scale = perf_counter_ns()
    for _ in range(N):
        var _r_robust_scale = robust_scale(_lf5)
        _acc_robust_scale += Float64(len(_r_robust_scale))
    var _t1_robust_scale = perf_counter_ns()
    var _ns_robust_scale = Float64(_t1_robust_scale - _t0_robust_scale) / Float64(N)
    print("MOJO_TIMING transform::robust_scale", _ns_robust_scale, _acc_robust_scale)
    var _result_robust_scale = robust_scale(_lf5)
    var _summary_robust_scale = _summary_list_float64(_result_robust_scale)
    print("MOJO_RESULT transform::robust_scale", _summary_robust_scale)
    var _acc_quantile_transform: Float64 = 0.0
    var _t0_quantile_transform = perf_counter_ns()
    for _ in range(N):
        var _r_quantile_transform = quantile_transform(_lf5)
        _acc_quantile_transform += Float64(len(_r_quantile_transform))
    var _t1_quantile_transform = perf_counter_ns()
    var _ns_quantile_transform = Float64(_t1_quantile_transform - _t0_quantile_transform) / Float64(N)
    print("MOJO_TIMING transform::quantile_transform", _ns_quantile_transform, _acc_quantile_transform)
    var _result_quantile_transform = quantile_transform(_lf5)
    var _summary_quantile_transform = _summary_list_float64(_result_quantile_transform)
    print("MOJO_RESULT transform::quantile_transform", _summary_quantile_transform)
    var _acc_power_transform: Float64 = 0.0
    var _t0_power_transform = perf_counter_ns()
    for _ in range(N):
        var _r_power_transform = power_transform(_lf5, 0.5)
        _acc_power_transform += Float64(len(_r_power_transform))
    var _t1_power_transform = perf_counter_ns()
    var _ns_power_transform = Float64(_t1_power_transform - _t0_power_transform) / Float64(N)
    print("MOJO_TIMING transform::power_transform", _ns_power_transform, _acc_power_transform)
    var _result_power_transform = power_transform(_lf5, 0.5)
    var _summary_power_transform = _summary_list_float64(_result_power_transform)
    print("MOJO_RESULT transform::power_transform", _summary_power_transform)
    var _acc_clamp_values: Float64 = 0.0
    var _t0_clamp_values = perf_counter_ns()
    for _ in range(N):
        var _r_clamp_values = clamp_values(_lf5, 0.5, 0.5)
        _acc_clamp_values += Float64(len(_r_clamp_values))
    var _t1_clamp_values = perf_counter_ns()
    var _ns_clamp_values = Float64(_t1_clamp_values - _t0_clamp_values) / Float64(N)
    print("MOJO_TIMING transform::clamp_values", _ns_clamp_values, _acc_clamp_values)
    var _result_clamp_values = clamp_values(_lf5, 0.5, 0.5)
    var _summary_clamp_values = _summary_list_float64(_result_clamp_values)
    print("MOJO_RESULT transform::clamp_values", _summary_clamp_values)
    var _acc_rank_transform: Float64 = 0.0
    var _t0_rank_transform = perf_counter_ns()
    for _ in range(N):
        var _r_rank_transform = rank_transform(_lf5)
        _acc_rank_transform += Float64(len(_r_rank_transform))
    var _t1_rank_transform = perf_counter_ns()
    var _ns_rank_transform = Float64(_t1_rank_transform - _t0_rank_transform) / Float64(N)
    print("MOJO_TIMING transform::rank_transform", _ns_rank_transform, _acc_rank_transform)
    var _result_rank_transform = rank_transform(_lf5)
    var _summary_rank_transform = _summary_list_float64(_result_rank_transform)
    print("MOJO_RESULT transform::rank_transform", _summary_rank_transform)
    var _acc_abs_transform: Float64 = 0.0
    var _t0_abs_transform = perf_counter_ns()
    for _ in range(N):
        var _r_abs_transform = abs_transform(_lf5)
        _acc_abs_transform += Float64(len(_r_abs_transform))
    var _t1_abs_transform = perf_counter_ns()
    var _ns_abs_transform = Float64(_t1_abs_transform - _t0_abs_transform) / Float64(N)
    print("MOJO_TIMING transform::abs_transform", _ns_abs_transform, _acc_abs_transform)
    var _result_abs_transform = abs_transform(_lf5)
    var _summary_abs_transform = _summary_list_float64(_result_abs_transform)
    print("MOJO_RESULT transform::abs_transform", _summary_abs_transform)
    var _acc_reciprocal_transform: Float64 = 0.0
    var _t0_reciprocal_transform = perf_counter_ns()
    for _ in range(N):
        var _r_reciprocal_transform = reciprocal_transform(_lf5)
        _acc_reciprocal_transform += Float64(len(_r_reciprocal_transform))
    var _t1_reciprocal_transform = perf_counter_ns()
    var _ns_reciprocal_transform = Float64(_t1_reciprocal_transform - _t0_reciprocal_transform) / Float64(N)
    print("MOJO_TIMING transform::reciprocal_transform", _ns_reciprocal_transform, _acc_reciprocal_transform)
    var _result_reciprocal_transform = reciprocal_transform(_lf5)
    var _summary_reciprocal_transform = _summary_list_float64(_result_reciprocal_transform)
    print("MOJO_RESULT transform::reciprocal_transform", _summary_reciprocal_transform)
