"""bench_inference_engine.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from inference_engine import batch_padding_mask, dynamic_batching_priority, kv_cache_hit_ratio, latency_percentile_estimate, throughput_tokens_per_sec, speculative_decode_accept_rate, continuous_batching_capacity, quantized_inference_speedup, prefill_time_estimate, decode_time_per_token
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

    var _acc_batch_padding_mask: Float64 = 0.0
    var _t0_batch_padding_mask = perf_counter_ns()
    for _ in range(N):
        _acc_batch_padding_mask += batch_padding_mask(0.5, 0.5)
    var _t1_batch_padding_mask = perf_counter_ns()
    var _ns_batch_padding_mask = Float64(_t1_batch_padding_mask - _t0_batch_padding_mask) / Float64(N)
    print("MOJO_TIMING inference_engine::batch_padding_mask", _ns_batch_padding_mask, _acc_batch_padding_mask)
    var _acc_dynamic_batching_priority: Float64 = 0.0
    var _t0_dynamic_batching_priority = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_batching_priority += dynamic_batching_priority(0.5, 0.5, 0.5)
    var _t1_dynamic_batching_priority = perf_counter_ns()
    var _ns_dynamic_batching_priority = Float64(_t1_dynamic_batching_priority - _t0_dynamic_batching_priority) / Float64(N)
    print("MOJO_TIMING inference_engine::dynamic_batching_priority", _ns_dynamic_batching_priority, _acc_dynamic_batching_priority)
    var _acc_kv_cache_hit_ratio: Float64 = 0.0
    var _t0_kv_cache_hit_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_hit_ratio += kv_cache_hit_ratio(0.5, 0.5)
    var _t1_kv_cache_hit_ratio = perf_counter_ns()
    var _ns_kv_cache_hit_ratio = Float64(_t1_kv_cache_hit_ratio - _t0_kv_cache_hit_ratio) / Float64(N)
    print("MOJO_TIMING inference_engine::kv_cache_hit_ratio", _ns_kv_cache_hit_ratio, _acc_kv_cache_hit_ratio)
    var _acc_latency_percentile_estimate: Float64 = 0.0
    var _t0_latency_percentile_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_latency_percentile_estimate += latency_percentile_estimate(0.5, 0.5, 0.5)
    var _t1_latency_percentile_estimate = perf_counter_ns()
    var _ns_latency_percentile_estimate = Float64(_t1_latency_percentile_estimate - _t0_latency_percentile_estimate) / Float64(N)
    print("MOJO_TIMING inference_engine::latency_percentile_estimate", _ns_latency_percentile_estimate, _acc_latency_percentile_estimate)
    var _acc_throughput_tokens_per_sec: Float64 = 0.0
    var _t0_throughput_tokens_per_sec = perf_counter_ns()
    for _ in range(N):
        _acc_throughput_tokens_per_sec += throughput_tokens_per_sec(0.5, 0.5, 0.5)
    var _t1_throughput_tokens_per_sec = perf_counter_ns()
    var _ns_throughput_tokens_per_sec = Float64(_t1_throughput_tokens_per_sec - _t0_throughput_tokens_per_sec) / Float64(N)
    print("MOJO_TIMING inference_engine::throughput_tokens_per_sec", _ns_throughput_tokens_per_sec, _acc_throughput_tokens_per_sec)
    var _acc_speculative_decode_accept_rate: Float64 = 0.0
    var _t0_speculative_decode_accept_rate = perf_counter_ns()
    for _ in range(N):
        _acc_speculative_decode_accept_rate += speculative_decode_accept_rate(0.5, 0.5)
    var _t1_speculative_decode_accept_rate = perf_counter_ns()
    var _ns_speculative_decode_accept_rate = Float64(_t1_speculative_decode_accept_rate - _t0_speculative_decode_accept_rate) / Float64(N)
    print("MOJO_TIMING inference_engine::speculative_decode_accept_rate", _ns_speculative_decode_accept_rate, _acc_speculative_decode_accept_rate)
    var _acc_continuous_batching_capacity: Float64 = 0.0
    var _t0_continuous_batching_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_continuous_batching_capacity += continuous_batching_capacity(0.5, 0.5, 0.5)
    var _t1_continuous_batching_capacity = perf_counter_ns()
    var _ns_continuous_batching_capacity = Float64(_t1_continuous_batching_capacity - _t0_continuous_batching_capacity) / Float64(N)
    print("MOJO_TIMING inference_engine::continuous_batching_capacity", _ns_continuous_batching_capacity, _acc_continuous_batching_capacity)
    var _acc_quantized_inference_speedup: Float64 = 0.0
    var _t0_quantized_inference_speedup = perf_counter_ns()
    for _ in range(N):
        _acc_quantized_inference_speedup += quantized_inference_speedup(0.5, 0.5, 0.5)
    var _t1_quantized_inference_speedup = perf_counter_ns()
    var _ns_quantized_inference_speedup = Float64(_t1_quantized_inference_speedup - _t0_quantized_inference_speedup) / Float64(N)
    print("MOJO_TIMING inference_engine::quantized_inference_speedup", _ns_quantized_inference_speedup, _acc_quantized_inference_speedup)
    var _acc_prefill_time_estimate: Float64 = 0.0
    var _t0_prefill_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_prefill_time_estimate += prefill_time_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_prefill_time_estimate = perf_counter_ns()
    var _ns_prefill_time_estimate = Float64(_t1_prefill_time_estimate - _t0_prefill_time_estimate) / Float64(N)
    print("MOJO_TIMING inference_engine::prefill_time_estimate", _ns_prefill_time_estimate, _acc_prefill_time_estimate)
    var _acc_decode_time_per_token: Float64 = 0.0
    var _t0_decode_time_per_token = perf_counter_ns()
    for _ in range(N):
        _acc_decode_time_per_token += decode_time_per_token(0.5, 0.5, 0.5)
    var _t1_decode_time_per_token = perf_counter_ns()
    var _ns_decode_time_per_token = Float64(_t1_decode_time_per_token - _t0_decode_time_per_token) / Float64(N)
    print("MOJO_TIMING inference_engine::decode_time_per_token", _ns_decode_time_per_token, _acc_decode_time_per_token)
