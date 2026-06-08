"""bench_transformer_blocks.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from transformer_blocks import multi_head_split_head, feedforward_layer1, feedforward_layer2, residual_connection, pre_norm, post_norm, causal_mask_logit, attention_head_output, gated_feedforward, dropout_scale
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

    var _acc_multi_head_split_head: Float64 = 0.0
    var _t0_multi_head_split_head = perf_counter_ns()
    for _ in range(N):
        _acc_multi_head_split_head += multi_head_split_head(0.5, 0.5, 0.5, 0.5)
    var _t1_multi_head_split_head = perf_counter_ns()
    var _ns_multi_head_split_head = Float64(_t1_multi_head_split_head - _t0_multi_head_split_head) / Float64(N)
    print("MOJO_TIMING transformer_blocks::multi_head_split_head", _ns_multi_head_split_head, _acc_multi_head_split_head)
    var _result_multi_head_split_head = multi_head_split_head(0.5, 0.5, 0.5, 0.5)
    var _summary_multi_head_split_head = _summary_float64(_result_multi_head_split_head)
    print("MOJO_RESULT transformer_blocks::multi_head_split_head", _summary_multi_head_split_head)
    var _acc_feedforward_layer1: Float64 = 0.0
    var _t0_feedforward_layer1 = perf_counter_ns()
    for _ in range(N):
        _acc_feedforward_layer1 += feedforward_layer1(0.5, 0.5, 0.5)
    var _t1_feedforward_layer1 = perf_counter_ns()
    var _ns_feedforward_layer1 = Float64(_t1_feedforward_layer1 - _t0_feedforward_layer1) / Float64(N)
    print("MOJO_TIMING transformer_blocks::feedforward_layer1", _ns_feedforward_layer1, _acc_feedforward_layer1)
    var _result_feedforward_layer1 = feedforward_layer1(0.5, 0.5, 0.5)
    var _summary_feedforward_layer1 = _summary_float64(_result_feedforward_layer1)
    print("MOJO_RESULT transformer_blocks::feedforward_layer1", _summary_feedforward_layer1)
    var _acc_feedforward_layer2: Float64 = 0.0
    var _t0_feedforward_layer2 = perf_counter_ns()
    for _ in range(N):
        _acc_feedforward_layer2 += feedforward_layer2(0.5, 0.5, 0.5)
    var _t1_feedforward_layer2 = perf_counter_ns()
    var _ns_feedforward_layer2 = Float64(_t1_feedforward_layer2 - _t0_feedforward_layer2) / Float64(N)
    print("MOJO_TIMING transformer_blocks::feedforward_layer2", _ns_feedforward_layer2, _acc_feedforward_layer2)
    var _result_feedforward_layer2 = feedforward_layer2(0.5, 0.5, 0.5)
    var _summary_feedforward_layer2 = _summary_float64(_result_feedforward_layer2)
    print("MOJO_RESULT transformer_blocks::feedforward_layer2", _summary_feedforward_layer2)
    var _acc_residual_connection: Float64 = 0.0
    var _t0_residual_connection = perf_counter_ns()
    for _ in range(N):
        _acc_residual_connection += residual_connection(0.5, 0.5)
    var _t1_residual_connection = perf_counter_ns()
    var _ns_residual_connection = Float64(_t1_residual_connection - _t0_residual_connection) / Float64(N)
    print("MOJO_TIMING transformer_blocks::residual_connection", _ns_residual_connection, _acc_residual_connection)
    var _result_residual_connection = residual_connection(0.5, 0.5)
    var _summary_residual_connection = _summary_float64(_result_residual_connection)
    print("MOJO_RESULT transformer_blocks::residual_connection", _summary_residual_connection)
    var _acc_pre_norm: Float64 = 0.0
    var _t0_pre_norm = perf_counter_ns()
    for _ in range(N):
        _acc_pre_norm += pre_norm(0.5, 0.5, 0.5)
    var _t1_pre_norm = perf_counter_ns()
    var _ns_pre_norm = Float64(_t1_pre_norm - _t0_pre_norm) / Float64(N)
    print("MOJO_TIMING transformer_blocks::pre_norm", _ns_pre_norm, _acc_pre_norm)
    var _result_pre_norm = pre_norm(0.5, 0.5, 0.5)
    var _summary_pre_norm = _summary_float64(_result_pre_norm)
    print("MOJO_RESULT transformer_blocks::pre_norm", _summary_pre_norm)
    var _acc_post_norm: Float64 = 0.0
    var _t0_post_norm = perf_counter_ns()
    for _ in range(N):
        _acc_post_norm += post_norm(0.5, 0.5, 0.5, 0.5)
    var _t1_post_norm = perf_counter_ns()
    var _ns_post_norm = Float64(_t1_post_norm - _t0_post_norm) / Float64(N)
    print("MOJO_TIMING transformer_blocks::post_norm", _ns_post_norm, _acc_post_norm)
    var _result_post_norm = post_norm(0.5, 0.5, 0.5, 0.5)
    var _summary_post_norm = _summary_float64(_result_post_norm)
    print("MOJO_RESULT transformer_blocks::post_norm", _summary_post_norm)
    var _acc_causal_mask_logit: Float64 = 0.0
    var _t0_causal_mask_logit = perf_counter_ns()
    for _ in range(N):
        _acc_causal_mask_logit += causal_mask_logit(0.5, 0.5, 0.5)
    var _t1_causal_mask_logit = perf_counter_ns()
    var _ns_causal_mask_logit = Float64(_t1_causal_mask_logit - _t0_causal_mask_logit) / Float64(N)
    print("MOJO_TIMING transformer_blocks::causal_mask_logit", _ns_causal_mask_logit, _acc_causal_mask_logit)
    var _result_causal_mask_logit = causal_mask_logit(0.5, 0.5, 0.5)
    var _summary_causal_mask_logit = _summary_float64(_result_causal_mask_logit)
    print("MOJO_RESULT transformer_blocks::causal_mask_logit", _summary_causal_mask_logit)
    var _acc_attention_head_output: Float64 = 0.0
    var _t0_attention_head_output = perf_counter_ns()
    for _ in range(N):
        _acc_attention_head_output += attention_head_output(0.5, 0.5)
    var _t1_attention_head_output = perf_counter_ns()
    var _ns_attention_head_output = Float64(_t1_attention_head_output - _t0_attention_head_output) / Float64(N)
    print("MOJO_TIMING transformer_blocks::attention_head_output", _ns_attention_head_output, _acc_attention_head_output)
    var _result_attention_head_output = attention_head_output(0.5, 0.5)
    var _summary_attention_head_output = _summary_float64(_result_attention_head_output)
    print("MOJO_RESULT transformer_blocks::attention_head_output", _summary_attention_head_output)
    var _acc_gated_feedforward: Float64 = 0.0
    var _t0_gated_feedforward = perf_counter_ns()
    for _ in range(N):
        _acc_gated_feedforward += gated_feedforward(0.5, 0.5)
    var _t1_gated_feedforward = perf_counter_ns()
    var _ns_gated_feedforward = Float64(_t1_gated_feedforward - _t0_gated_feedforward) / Float64(N)
    print("MOJO_TIMING transformer_blocks::gated_feedforward", _ns_gated_feedforward, _acc_gated_feedforward)
    var _result_gated_feedforward = gated_feedforward(0.5, 0.5)
    var _summary_gated_feedforward = _summary_float64(_result_gated_feedforward)
    print("MOJO_RESULT transformer_blocks::gated_feedforward", _summary_gated_feedforward)
    var _acc_dropout_scale: Float64 = 0.0
    var _t0_dropout_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dropout_scale += dropout_scale(0.5, 0.5)
    var _t1_dropout_scale = perf_counter_ns()
    var _ns_dropout_scale = Float64(_t1_dropout_scale - _t0_dropout_scale) / Float64(N)
    print("MOJO_TIMING transformer_blocks::dropout_scale", _ns_dropout_scale, _acc_dropout_scale)
    var _result_dropout_scale = dropout_scale(0.5, 0.5)
    var _summary_dropout_scale = _summary_float64(_result_dropout_scale)
    print("MOJO_RESULT transformer_blocks::dropout_scale", _summary_dropout_scale)
