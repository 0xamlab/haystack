"""bench_transformer_blocks.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from transformer_blocks import multi_head_split_head, feedforward_layer1, feedforward_layer2, residual_connection, pre_norm, post_norm, causal_mask_logit, attention_head_output, gated_feedforward, dropout_scale
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

    var _acc_multi_head_split_head: Float64 = 0.0
    var _t0_multi_head_split_head = perf_counter_ns()
    for _ in range(N):
        _acc_multi_head_split_head += multi_head_split_head(0.5, 0.5, 0.5, 0.5)
    var _t1_multi_head_split_head = perf_counter_ns()
    var _ns_multi_head_split_head = Float64(_t1_multi_head_split_head - _t0_multi_head_split_head) / Float64(N)
    print("MOJO_TIMING transformer_blocks::multi_head_split_head", _ns_multi_head_split_head, _acc_multi_head_split_head)
    var _acc_feedforward_layer1: Float64 = 0.0
    var _t0_feedforward_layer1 = perf_counter_ns()
    for _ in range(N):
        _acc_feedforward_layer1 += feedforward_layer1(0.5, 0.5, 0.5)
    var _t1_feedforward_layer1 = perf_counter_ns()
    var _ns_feedforward_layer1 = Float64(_t1_feedforward_layer1 - _t0_feedforward_layer1) / Float64(N)
    print("MOJO_TIMING transformer_blocks::feedforward_layer1", _ns_feedforward_layer1, _acc_feedforward_layer1)
    var _acc_feedforward_layer2: Float64 = 0.0
    var _t0_feedforward_layer2 = perf_counter_ns()
    for _ in range(N):
        _acc_feedforward_layer2 += feedforward_layer2(0.5, 0.5, 0.5)
    var _t1_feedforward_layer2 = perf_counter_ns()
    var _ns_feedforward_layer2 = Float64(_t1_feedforward_layer2 - _t0_feedforward_layer2) / Float64(N)
    print("MOJO_TIMING transformer_blocks::feedforward_layer2", _ns_feedforward_layer2, _acc_feedforward_layer2)
    var _acc_residual_connection: Float64 = 0.0
    var _t0_residual_connection = perf_counter_ns()
    for _ in range(N):
        _acc_residual_connection += residual_connection(0.5, 0.5)
    var _t1_residual_connection = perf_counter_ns()
    var _ns_residual_connection = Float64(_t1_residual_connection - _t0_residual_connection) / Float64(N)
    print("MOJO_TIMING transformer_blocks::residual_connection", _ns_residual_connection, _acc_residual_connection)
    var _acc_pre_norm: Float64 = 0.0
    var _t0_pre_norm = perf_counter_ns()
    for _ in range(N):
        _acc_pre_norm += pre_norm(0.5, 0.5, 0.5)
    var _t1_pre_norm = perf_counter_ns()
    var _ns_pre_norm = Float64(_t1_pre_norm - _t0_pre_norm) / Float64(N)
    print("MOJO_TIMING transformer_blocks::pre_norm", _ns_pre_norm, _acc_pre_norm)
    var _acc_post_norm: Float64 = 0.0
    var _t0_post_norm = perf_counter_ns()
    for _ in range(N):
        _acc_post_norm += post_norm(0.5, 0.5, 0.5, 0.5)
    var _t1_post_norm = perf_counter_ns()
    var _ns_post_norm = Float64(_t1_post_norm - _t0_post_norm) / Float64(N)
    print("MOJO_TIMING transformer_blocks::post_norm", _ns_post_norm, _acc_post_norm)
    var _acc_causal_mask_logit: Float64 = 0.0
    var _t0_causal_mask_logit = perf_counter_ns()
    for _ in range(N):
        _acc_causal_mask_logit += causal_mask_logit(0.5, 0.5, 0.5)
    var _t1_causal_mask_logit = perf_counter_ns()
    var _ns_causal_mask_logit = Float64(_t1_causal_mask_logit - _t0_causal_mask_logit) / Float64(N)
    print("MOJO_TIMING transformer_blocks::causal_mask_logit", _ns_causal_mask_logit, _acc_causal_mask_logit)
    var _acc_attention_head_output: Float64 = 0.0
    var _t0_attention_head_output = perf_counter_ns()
    for _ in range(N):
        _acc_attention_head_output += attention_head_output(0.5, 0.5)
    var _t1_attention_head_output = perf_counter_ns()
    var _ns_attention_head_output = Float64(_t1_attention_head_output - _t0_attention_head_output) / Float64(N)
    print("MOJO_TIMING transformer_blocks::attention_head_output", _ns_attention_head_output, _acc_attention_head_output)
    var _acc_gated_feedforward: Float64 = 0.0
    var _t0_gated_feedforward = perf_counter_ns()
    for _ in range(N):
        _acc_gated_feedforward += gated_feedforward(0.5, 0.5)
    var _t1_gated_feedforward = perf_counter_ns()
    var _ns_gated_feedforward = Float64(_t1_gated_feedforward - _t0_gated_feedforward) / Float64(N)
    print("MOJO_TIMING transformer_blocks::gated_feedforward", _ns_gated_feedforward, _acc_gated_feedforward)
    var _acc_dropout_scale: Float64 = 0.0
    var _t0_dropout_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dropout_scale += dropout_scale(0.5, 0.5)
    var _t1_dropout_scale = perf_counter_ns()
    var _ns_dropout_scale = Float64(_t1_dropout_scale - _t0_dropout_scale) / Float64(N)
    print("MOJO_TIMING transformer_blocks::dropout_scale", _ns_dropout_scale, _acc_dropout_scale)
