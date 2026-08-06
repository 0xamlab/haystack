"""bench_latency_optimizer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from latency_optimizer import early_exit_confidence, adaptive_depth_score, prefill_decode_split_latency, async_speculation_gain, token_streaming_headroom, layer_skip_quality_cost, partial_forward_savings, kv_prefetch_overlap, attention_skip_score, output_caching_hit_benefit
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

    var _acc_early_exit_confidence: Float64 = 0.0
    var _t0_early_exit_confidence = perf_counter_ns()
    for _ in range(N):
        _acc_early_exit_confidence += early_exit_confidence(0.5, 0.5, 0.5)
    var _t1_early_exit_confidence = perf_counter_ns()
    var _ns_early_exit_confidence = Float64(_t1_early_exit_confidence - _t0_early_exit_confidence) / Float64(N)
    print("MOJO_TIMING latency_optimizer::early_exit_confidence", _ns_early_exit_confidence, _acc_early_exit_confidence)
    var _result_early_exit_confidence = early_exit_confidence(0.5, 0.5, 0.5)
    var _summary_early_exit_confidence = _summary_float64(_result_early_exit_confidence)
    print("MOJO_RESULT latency_optimizer::early_exit_confidence", _summary_early_exit_confidence)
    var _acc_adaptive_depth_score: Float64 = 0.0
    var _t0_adaptive_depth_score = perf_counter_ns()
    for _ in range(N):
        _acc_adaptive_depth_score += adaptive_depth_score(0.5, 0.5, 0.5)
    var _t1_adaptive_depth_score = perf_counter_ns()
    var _ns_adaptive_depth_score = Float64(_t1_adaptive_depth_score - _t0_adaptive_depth_score) / Float64(N)
    print("MOJO_TIMING latency_optimizer::adaptive_depth_score", _ns_adaptive_depth_score, _acc_adaptive_depth_score)
    var _result_adaptive_depth_score = adaptive_depth_score(0.5, 0.5, 0.5)
    var _summary_adaptive_depth_score = _summary_float64(_result_adaptive_depth_score)
    print("MOJO_RESULT latency_optimizer::adaptive_depth_score", _summary_adaptive_depth_score)
    var _acc_prefill_decode_split_latency: Float64 = 0.0
    var _t0_prefill_decode_split_latency = perf_counter_ns()
    for _ in range(N):
        _acc_prefill_decode_split_latency += prefill_decode_split_latency(0.5, 0.5, 0.5, 0.5)
    var _t1_prefill_decode_split_latency = perf_counter_ns()
    var _ns_prefill_decode_split_latency = Float64(_t1_prefill_decode_split_latency - _t0_prefill_decode_split_latency) / Float64(N)
    print("MOJO_TIMING latency_optimizer::prefill_decode_split_latency", _ns_prefill_decode_split_latency, _acc_prefill_decode_split_latency)
    var _result_prefill_decode_split_latency = prefill_decode_split_latency(0.5, 0.5, 0.5, 0.5)
    var _summary_prefill_decode_split_latency = _summary_float64(_result_prefill_decode_split_latency)
    print("MOJO_RESULT latency_optimizer::prefill_decode_split_latency", _summary_prefill_decode_split_latency)
    var _acc_async_speculation_gain: Float64 = 0.0
    var _t0_async_speculation_gain = perf_counter_ns()
    for _ in range(N):
        _acc_async_speculation_gain += async_speculation_gain(0.5, 0.5, 0.5)
    var _t1_async_speculation_gain = perf_counter_ns()
    var _ns_async_speculation_gain = Float64(_t1_async_speculation_gain - _t0_async_speculation_gain) / Float64(N)
    print("MOJO_TIMING latency_optimizer::async_speculation_gain", _ns_async_speculation_gain, _acc_async_speculation_gain)
    var _result_async_speculation_gain = async_speculation_gain(0.5, 0.5, 0.5)
    var _summary_async_speculation_gain = _summary_float64(_result_async_speculation_gain)
    print("MOJO_RESULT latency_optimizer::async_speculation_gain", _summary_async_speculation_gain)
    var _acc_token_streaming_headroom: Float64 = 0.0
    var _t0_token_streaming_headroom = perf_counter_ns()
    for _ in range(N):
        _acc_token_streaming_headroom += token_streaming_headroom(0.5, 0.5, 0.5)
    var _t1_token_streaming_headroom = perf_counter_ns()
    var _ns_token_streaming_headroom = Float64(_t1_token_streaming_headroom - _t0_token_streaming_headroom) / Float64(N)
    print("MOJO_TIMING latency_optimizer::token_streaming_headroom", _ns_token_streaming_headroom, _acc_token_streaming_headroom)
    var _result_token_streaming_headroom = token_streaming_headroom(0.5, 0.5, 0.5)
    var _summary_token_streaming_headroom = _summary_float64(_result_token_streaming_headroom)
    print("MOJO_RESULT latency_optimizer::token_streaming_headroom", _summary_token_streaming_headroom)
    var _acc_layer_skip_quality_cost: Float64 = 0.0
    var _t0_layer_skip_quality_cost = perf_counter_ns()
    for _ in range(N):
        _acc_layer_skip_quality_cost += layer_skip_quality_cost(0.5, 0.5, 0.5)
    var _t1_layer_skip_quality_cost = perf_counter_ns()
    var _ns_layer_skip_quality_cost = Float64(_t1_layer_skip_quality_cost - _t0_layer_skip_quality_cost) / Float64(N)
    print("MOJO_TIMING latency_optimizer::layer_skip_quality_cost", _ns_layer_skip_quality_cost, _acc_layer_skip_quality_cost)
    var _result_layer_skip_quality_cost = layer_skip_quality_cost(0.5, 0.5, 0.5)
    var _summary_layer_skip_quality_cost = _summary_float64(_result_layer_skip_quality_cost)
    print("MOJO_RESULT latency_optimizer::layer_skip_quality_cost", _summary_layer_skip_quality_cost)
    var _acc_partial_forward_savings: Float64 = 0.0
    var _t0_partial_forward_savings = perf_counter_ns()
    for _ in range(N):
        _acc_partial_forward_savings += partial_forward_savings(0.5, 0.5, 0.5, 0.5)
    var _t1_partial_forward_savings = perf_counter_ns()
    var _ns_partial_forward_savings = Float64(_t1_partial_forward_savings - _t0_partial_forward_savings) / Float64(N)
    print("MOJO_TIMING latency_optimizer::partial_forward_savings", _ns_partial_forward_savings, _acc_partial_forward_savings)
    var _result_partial_forward_savings = partial_forward_savings(0.5, 0.5, 0.5, 0.5)
    var _summary_partial_forward_savings = _summary_float64(_result_partial_forward_savings)
    print("MOJO_RESULT latency_optimizer::partial_forward_savings", _summary_partial_forward_savings)
    var _acc_kv_prefetch_overlap: Float64 = 0.0
    var _t0_kv_prefetch_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_kv_prefetch_overlap += kv_prefetch_overlap(0.5, 0.5)
    var _t1_kv_prefetch_overlap = perf_counter_ns()
    var _ns_kv_prefetch_overlap = Float64(_t1_kv_prefetch_overlap - _t0_kv_prefetch_overlap) / Float64(N)
    print("MOJO_TIMING latency_optimizer::kv_prefetch_overlap", _ns_kv_prefetch_overlap, _acc_kv_prefetch_overlap)
    var _result_kv_prefetch_overlap = kv_prefetch_overlap(0.5, 0.5)
    var _summary_kv_prefetch_overlap = _summary_float64(_result_kv_prefetch_overlap)
    print("MOJO_RESULT latency_optimizer::kv_prefetch_overlap", _summary_kv_prefetch_overlap)
    var _acc_attention_skip_score: Float64 = 0.0
    var _t0_attention_skip_score = perf_counter_ns()
    for _ in range(N):
        _acc_attention_skip_score += attention_skip_score(0.5, 0.5, 0.5)
    var _t1_attention_skip_score = perf_counter_ns()
    var _ns_attention_skip_score = Float64(_t1_attention_skip_score - _t0_attention_skip_score) / Float64(N)
    print("MOJO_TIMING latency_optimizer::attention_skip_score", _ns_attention_skip_score, _acc_attention_skip_score)
    var _result_attention_skip_score = attention_skip_score(0.5, 0.5, 0.5)
    var _summary_attention_skip_score = _summary_float64(_result_attention_skip_score)
    print("MOJO_RESULT latency_optimizer::attention_skip_score", _summary_attention_skip_score)
    var _acc_output_caching_hit_benefit: Float64 = 0.0
    var _t0_output_caching_hit_benefit = perf_counter_ns()
    for _ in range(N):
        _acc_output_caching_hit_benefit += output_caching_hit_benefit(0.5, 0.5, 0.5)
    var _t1_output_caching_hit_benefit = perf_counter_ns()
    var _ns_output_caching_hit_benefit = Float64(_t1_output_caching_hit_benefit - _t0_output_caching_hit_benefit) / Float64(N)
    print("MOJO_TIMING latency_optimizer::output_caching_hit_benefit", _ns_output_caching_hit_benefit, _acc_output_caching_hit_benefit)
    var _result_output_caching_hit_benefit = output_caching_hit_benefit(0.5, 0.5, 0.5)
    var _summary_output_caching_hit_benefit = _summary_float64(_result_output_caching_hit_benefit)
    print("MOJO_RESULT latency_optimizer::output_caching_hit_benefit", _summary_output_caching_hit_benefit)
