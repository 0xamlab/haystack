"""bench_continuous_batching.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from continuous_batching import iteration_level_batch_size, preemption_score, admission_control_accept, chunked_prefill_chunks, decode_throughput_tokens, streaming_first_token_latency, sequence_completion_fraction, head_of_line_blocking_score, beam_memory_per_request, batching_efficiency
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

    var _acc_iteration_level_batch_size: Float64 = 0.0
    var _t0_iteration_level_batch_size = perf_counter_ns()
    for _ in range(N):
        _acc_iteration_level_batch_size += iteration_level_batch_size(0.5, 0.5)
    var _t1_iteration_level_batch_size = perf_counter_ns()
    var _ns_iteration_level_batch_size = Float64(_t1_iteration_level_batch_size - _t0_iteration_level_batch_size) / Float64(N)
    print("MOJO_TIMING continuous_batching::iteration_level_batch_size", _ns_iteration_level_batch_size, _acc_iteration_level_batch_size)
    var _acc_preemption_score: Float64 = 0.0
    var _t0_preemption_score = perf_counter_ns()
    for _ in range(N):
        _acc_preemption_score += preemption_score(0.5, 0.5, 0.5)
    var _t1_preemption_score = perf_counter_ns()
    var _ns_preemption_score = Float64(_t1_preemption_score - _t0_preemption_score) / Float64(N)
    print("MOJO_TIMING continuous_batching::preemption_score", _ns_preemption_score, _acc_preemption_score)
    var _acc_admission_control_accept: Float64 = 0.0
    var _t0_admission_control_accept = perf_counter_ns()
    for _ in range(N):
        _acc_admission_control_accept += admission_control_accept(0.5, 0.5, 0.5)
    var _t1_admission_control_accept = perf_counter_ns()
    var _ns_admission_control_accept = Float64(_t1_admission_control_accept - _t0_admission_control_accept) / Float64(N)
    print("MOJO_TIMING continuous_batching::admission_control_accept", _ns_admission_control_accept, _acc_admission_control_accept)
    var _acc_chunked_prefill_chunks: Float64 = 0.0
    var _t0_chunked_prefill_chunks = perf_counter_ns()
    for _ in range(N):
        _acc_chunked_prefill_chunks += chunked_prefill_chunks(0.5, 0.5)
    var _t1_chunked_prefill_chunks = perf_counter_ns()
    var _ns_chunked_prefill_chunks = Float64(_t1_chunked_prefill_chunks - _t0_chunked_prefill_chunks) / Float64(N)
    print("MOJO_TIMING continuous_batching::chunked_prefill_chunks", _ns_chunked_prefill_chunks, _acc_chunked_prefill_chunks)
    var _acc_decode_throughput_tokens: Float64 = 0.0
    var _t0_decode_throughput_tokens = perf_counter_ns()
    for _ in range(N):
        _acc_decode_throughput_tokens += decode_throughput_tokens(0.5, 0.5)
    var _t1_decode_throughput_tokens = perf_counter_ns()
    var _ns_decode_throughput_tokens = Float64(_t1_decode_throughput_tokens - _t0_decode_throughput_tokens) / Float64(N)
    print("MOJO_TIMING continuous_batching::decode_throughput_tokens", _ns_decode_throughput_tokens, _acc_decode_throughput_tokens)
    var _acc_streaming_first_token_latency: Float64 = 0.0
    var _t0_streaming_first_token_latency = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_first_token_latency += streaming_first_token_latency(0.5, 0.5)
    var _t1_streaming_first_token_latency = perf_counter_ns()
    var _ns_streaming_first_token_latency = Float64(_t1_streaming_first_token_latency - _t0_streaming_first_token_latency) / Float64(N)
    print("MOJO_TIMING continuous_batching::streaming_first_token_latency", _ns_streaming_first_token_latency, _acc_streaming_first_token_latency)
    var _acc_sequence_completion_fraction: Float64 = 0.0
    var _t0_sequence_completion_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_sequence_completion_fraction += sequence_completion_fraction(0.5, 0.5)
    var _t1_sequence_completion_fraction = perf_counter_ns()
    var _ns_sequence_completion_fraction = Float64(_t1_sequence_completion_fraction - _t0_sequence_completion_fraction) / Float64(N)
    print("MOJO_TIMING continuous_batching::sequence_completion_fraction", _ns_sequence_completion_fraction, _acc_sequence_completion_fraction)
    var _acc_head_of_line_blocking_score: Float64 = 0.0
    var _t0_head_of_line_blocking_score = perf_counter_ns()
    for _ in range(N):
        _acc_head_of_line_blocking_score += head_of_line_blocking_score(0.5, 0.5)
    var _t1_head_of_line_blocking_score = perf_counter_ns()
    var _ns_head_of_line_blocking_score = Float64(_t1_head_of_line_blocking_score - _t0_head_of_line_blocking_score) / Float64(N)
    print("MOJO_TIMING continuous_batching::head_of_line_blocking_score", _ns_head_of_line_blocking_score, _acc_head_of_line_blocking_score)
    var _acc_beam_memory_per_request: Float64 = 0.0
    var _t0_beam_memory_per_request = perf_counter_ns()
    for _ in range(N):
        _acc_beam_memory_per_request += beam_memory_per_request(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_beam_memory_per_request = perf_counter_ns()
    var _ns_beam_memory_per_request = Float64(_t1_beam_memory_per_request - _t0_beam_memory_per_request) / Float64(N)
    print("MOJO_TIMING continuous_batching::beam_memory_per_request", _ns_beam_memory_per_request, _acc_beam_memory_per_request)
    var _acc_batching_efficiency: Float64 = 0.0
    var _t0_batching_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_batching_efficiency += batching_efficiency(0.5, 0.5)
    var _t1_batching_efficiency = perf_counter_ns()
    var _ns_batching_efficiency = Float64(_t1_batching_efficiency - _t0_batching_efficiency) / Float64(N)
    print("MOJO_TIMING continuous_batching::batching_efficiency", _ns_batching_efficiency, _acc_batching_efficiency)
