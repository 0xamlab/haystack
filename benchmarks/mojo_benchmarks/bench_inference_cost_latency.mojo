"""bench_inference_cost_latency.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from inference_cost_latency import prompt_token_estimate, completion_token_estimate, kv_cache_bytes, attention_flops, prefill_latency_estimate, decode_latency_estimate, request_cost_estimate, cost_latency_frontier_score, batch_efficiency_estimate, queue_delay_estimate, speculative_decode_gain_estimate
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

    var _acc_prompt_token_estimate: Float64 = 0.0
    var _t0_prompt_token_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_prompt_token_estimate += Float64(prompt_token_estimate(5, 0.5))
    var _t1_prompt_token_estimate = perf_counter_ns()
    var _ns_prompt_token_estimate = Float64(_t1_prompt_token_estimate - _t0_prompt_token_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::prompt_token_estimate", _ns_prompt_token_estimate, _acc_prompt_token_estimate)
    var _result_prompt_token_estimate = prompt_token_estimate(5, 0.5)
    var _summary_prompt_token_estimate = _summary_int(_result_prompt_token_estimate)
    print("MOJO_RESULT inference_cost_latency::prompt_token_estimate", _summary_prompt_token_estimate)
    var _acc_completion_token_estimate: Float64 = 0.0
    var _t0_completion_token_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_completion_token_estimate += Float64(completion_token_estimate(5, 0.5))
    var _t1_completion_token_estimate = perf_counter_ns()
    var _ns_completion_token_estimate = Float64(_t1_completion_token_estimate - _t0_completion_token_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::completion_token_estimate", _ns_completion_token_estimate, _acc_completion_token_estimate)
    var _result_completion_token_estimate = completion_token_estimate(5, 0.5)
    var _summary_completion_token_estimate = _summary_int(_result_completion_token_estimate)
    print("MOJO_RESULT inference_cost_latency::completion_token_estimate", _summary_completion_token_estimate)
    var _acc_kv_cache_bytes: Float64 = 0.0
    var _t0_kv_cache_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_bytes += kv_cache_bytes(5, 5, 5, 5, 5)
    var _t1_kv_cache_bytes = perf_counter_ns()
    var _ns_kv_cache_bytes = Float64(_t1_kv_cache_bytes - _t0_kv_cache_bytes) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::kv_cache_bytes", _ns_kv_cache_bytes, _acc_kv_cache_bytes)
    var _result_kv_cache_bytes = kv_cache_bytes(5, 5, 5, 5, 5)
    var _summary_kv_cache_bytes = _summary_float64(_result_kv_cache_bytes)
    print("MOJO_RESULT inference_cost_latency::kv_cache_bytes", _summary_kv_cache_bytes)
    var _acc_attention_flops: Float64 = 0.0
    var _t0_attention_flops = perf_counter_ns()
    for _ in range(N):
        _acc_attention_flops += attention_flops(5, 5, 5, 5, 5)
    var _t1_attention_flops = perf_counter_ns()
    var _ns_attention_flops = Float64(_t1_attention_flops - _t0_attention_flops) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::attention_flops", _ns_attention_flops, _acc_attention_flops)
    var _result_attention_flops = attention_flops(5, 5, 5, 5, 5)
    var _summary_attention_flops = _summary_float64(_result_attention_flops)
    print("MOJO_RESULT inference_cost_latency::attention_flops", _summary_attention_flops)
    var _acc_prefill_latency_estimate: Float64 = 0.0
    var _t0_prefill_latency_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_prefill_latency_estimate += prefill_latency_estimate(5, 0.5, 0.5)
    var _t1_prefill_latency_estimate = perf_counter_ns()
    var _ns_prefill_latency_estimate = Float64(_t1_prefill_latency_estimate - _t0_prefill_latency_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::prefill_latency_estimate", _ns_prefill_latency_estimate, _acc_prefill_latency_estimate)
    var _result_prefill_latency_estimate = prefill_latency_estimate(5, 0.5, 0.5)
    var _summary_prefill_latency_estimate = _summary_float64(_result_prefill_latency_estimate)
    print("MOJO_RESULT inference_cost_latency::prefill_latency_estimate", _summary_prefill_latency_estimate)
    var _acc_decode_latency_estimate: Float64 = 0.0
    var _t0_decode_latency_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_decode_latency_estimate += decode_latency_estimate(5, 0.5, 0.5)
    var _t1_decode_latency_estimate = perf_counter_ns()
    var _ns_decode_latency_estimate = Float64(_t1_decode_latency_estimate - _t0_decode_latency_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::decode_latency_estimate", _ns_decode_latency_estimate, _acc_decode_latency_estimate)
    var _result_decode_latency_estimate = decode_latency_estimate(5, 0.5, 0.5)
    var _summary_decode_latency_estimate = _summary_float64(_result_decode_latency_estimate)
    print("MOJO_RESULT inference_cost_latency::decode_latency_estimate", _summary_decode_latency_estimate)
    var _acc_request_cost_estimate: Float64 = 0.0
    var _t0_request_cost_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_request_cost_estimate += request_cost_estimate(5, 5, 0.5, 0.5)
    var _t1_request_cost_estimate = perf_counter_ns()
    var _ns_request_cost_estimate = Float64(_t1_request_cost_estimate - _t0_request_cost_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::request_cost_estimate", _ns_request_cost_estimate, _acc_request_cost_estimate)
    var _result_request_cost_estimate = request_cost_estimate(5, 5, 0.5, 0.5)
    var _summary_request_cost_estimate = _summary_float64(_result_request_cost_estimate)
    print("MOJO_RESULT inference_cost_latency::request_cost_estimate", _summary_request_cost_estimate)
    var _acc_cost_latency_frontier_score: Float64 = 0.0
    var _t0_cost_latency_frontier_score = perf_counter_ns()
    for _ in range(N):
        _acc_cost_latency_frontier_score += cost_latency_frontier_score(0.5, 0.5, 0.5, 0.5)
    var _t1_cost_latency_frontier_score = perf_counter_ns()
    var _ns_cost_latency_frontier_score = Float64(_t1_cost_latency_frontier_score - _t0_cost_latency_frontier_score) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::cost_latency_frontier_score", _ns_cost_latency_frontier_score, _acc_cost_latency_frontier_score)
    var _result_cost_latency_frontier_score = cost_latency_frontier_score(0.5, 0.5, 0.5, 0.5)
    var _summary_cost_latency_frontier_score = _summary_float64(_result_cost_latency_frontier_score)
    print("MOJO_RESULT inference_cost_latency::cost_latency_frontier_score", _summary_cost_latency_frontier_score)
    var _acc_batch_efficiency_estimate: Float64 = 0.0
    var _t0_batch_efficiency_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_batch_efficiency_estimate += batch_efficiency_estimate(5, 5)
    var _t1_batch_efficiency_estimate = perf_counter_ns()
    var _ns_batch_efficiency_estimate = Float64(_t1_batch_efficiency_estimate - _t0_batch_efficiency_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::batch_efficiency_estimate", _ns_batch_efficiency_estimate, _acc_batch_efficiency_estimate)
    var _result_batch_efficiency_estimate = batch_efficiency_estimate(5, 5)
    var _summary_batch_efficiency_estimate = _summary_float64(_result_batch_efficiency_estimate)
    print("MOJO_RESULT inference_cost_latency::batch_efficiency_estimate", _summary_batch_efficiency_estimate)
    var _acc_queue_delay_estimate: Float64 = 0.0
    var _t0_queue_delay_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_queue_delay_estimate += queue_delay_estimate(5, 0.5, 5)
    var _t1_queue_delay_estimate = perf_counter_ns()
    var _ns_queue_delay_estimate = Float64(_t1_queue_delay_estimate - _t0_queue_delay_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::queue_delay_estimate", _ns_queue_delay_estimate, _acc_queue_delay_estimate)
    var _result_queue_delay_estimate = queue_delay_estimate(5, 0.5, 5)
    var _summary_queue_delay_estimate = _summary_float64(_result_queue_delay_estimate)
    print("MOJO_RESULT inference_cost_latency::queue_delay_estimate", _summary_queue_delay_estimate)
    var _acc_speculative_decode_gain_estimate: Float64 = 0.0
    var _t0_speculative_decode_gain_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_speculative_decode_gain_estimate += speculative_decode_gain_estimate(0.5, 5, 0.5, 0.5)
    var _t1_speculative_decode_gain_estimate = perf_counter_ns()
    var _ns_speculative_decode_gain_estimate = Float64(_t1_speculative_decode_gain_estimate - _t0_speculative_decode_gain_estimate) / Float64(N)
    print("MOJO_TIMING inference_cost_latency::speculative_decode_gain_estimate", _ns_speculative_decode_gain_estimate, _acc_speculative_decode_gain_estimate)
    var _result_speculative_decode_gain_estimate = speculative_decode_gain_estimate(0.5, 5, 0.5, 0.5)
    var _summary_speculative_decode_gain_estimate = _summary_float64(_result_speculative_decode_gain_estimate)
    print("MOJO_RESULT inference_cost_latency::speculative_decode_gain_estimate", _summary_speculative_decode_gain_estimate)
