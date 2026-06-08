"""bench_sparse_attention.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sparse_attention import local_window_mask, longformer_global_score, bigbird_random_block_select, streaming_llm_sink_score, landmark_token_score, chunk_cross_attention_weight, linear_attention_kernel, recurrent_memory_update, block_sparse_density, hyper_attention_estimate
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

    var _acc_local_window_mask: Float64 = 0.0
    var _t0_local_window_mask = perf_counter_ns()
    for _ in range(N):
        _acc_local_window_mask += local_window_mask(0.5, 0.5, 0.5, 0.5)
    var _t1_local_window_mask = perf_counter_ns()
    var _ns_local_window_mask = Float64(_t1_local_window_mask - _t0_local_window_mask) / Float64(N)
    print("MOJO_TIMING sparse_attention::local_window_mask", _ns_local_window_mask, _acc_local_window_mask)
    var _result_local_window_mask = local_window_mask(0.5, 0.5, 0.5, 0.5)
    var _summary_local_window_mask = _summary_float64(_result_local_window_mask)
    print("MOJO_RESULT sparse_attention::local_window_mask", _summary_local_window_mask)
    var _acc_longformer_global_score: Float64 = 0.0
    var _t0_longformer_global_score = perf_counter_ns()
    for _ in range(N):
        _acc_longformer_global_score += longformer_global_score(0.5, 0.5, 0.5, 0.5)
    var _t1_longformer_global_score = perf_counter_ns()
    var _ns_longformer_global_score = Float64(_t1_longformer_global_score - _t0_longformer_global_score) / Float64(N)
    print("MOJO_TIMING sparse_attention::longformer_global_score", _ns_longformer_global_score, _acc_longformer_global_score)
    var _result_longformer_global_score = longformer_global_score(0.5, 0.5, 0.5, 0.5)
    var _summary_longformer_global_score = _summary_float64(_result_longformer_global_score)
    print("MOJO_RESULT sparse_attention::longformer_global_score", _summary_longformer_global_score)
    var _acc_bigbird_random_block_select: Float64 = 0.0
    var _t0_bigbird_random_block_select = perf_counter_ns()
    for _ in range(N):
        _acc_bigbird_random_block_select += bigbird_random_block_select(1.0, 8.0, 3.0, 2.0)
    var _t1_bigbird_random_block_select = perf_counter_ns()
    var _ns_bigbird_random_block_select = Float64(_t1_bigbird_random_block_select - _t0_bigbird_random_block_select) / Float64(N)
    print("MOJO_TIMING sparse_attention::bigbird_random_block_select", _ns_bigbird_random_block_select, _acc_bigbird_random_block_select)
    var _result_bigbird_random_block_select = bigbird_random_block_select(1.0, 8.0, 3.0, 2.0)
    var _summary_bigbird_random_block_select = _summary_float64(_result_bigbird_random_block_select)
    print("MOJO_RESULT sparse_attention::bigbird_random_block_select", _summary_bigbird_random_block_select)
    var _acc_streaming_llm_sink_score: Float64 = 0.0
    var _t0_streaming_llm_sink_score = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_llm_sink_score += streaming_llm_sink_score(0.5, 0.5, 0.5, 0.5)
    var _t1_streaming_llm_sink_score = perf_counter_ns()
    var _ns_streaming_llm_sink_score = Float64(_t1_streaming_llm_sink_score - _t0_streaming_llm_sink_score) / Float64(N)
    print("MOJO_TIMING sparse_attention::streaming_llm_sink_score", _ns_streaming_llm_sink_score, _acc_streaming_llm_sink_score)
    var _result_streaming_llm_sink_score = streaming_llm_sink_score(0.5, 0.5, 0.5, 0.5)
    var _summary_streaming_llm_sink_score = _summary_float64(_result_streaming_llm_sink_score)
    print("MOJO_RESULT sparse_attention::streaming_llm_sink_score", _summary_streaming_llm_sink_score)
    var _acc_landmark_token_score: Float64 = 0.0
    var _t0_landmark_token_score = perf_counter_ns()
    for _ in range(N):
        _acc_landmark_token_score += landmark_token_score(0.5, 0.5, 0.5)
    var _t1_landmark_token_score = perf_counter_ns()
    var _ns_landmark_token_score = Float64(_t1_landmark_token_score - _t0_landmark_token_score) / Float64(N)
    print("MOJO_TIMING sparse_attention::landmark_token_score", _ns_landmark_token_score, _acc_landmark_token_score)
    var _result_landmark_token_score = landmark_token_score(0.5, 0.5, 0.5)
    var _summary_landmark_token_score = _summary_float64(_result_landmark_token_score)
    print("MOJO_RESULT sparse_attention::landmark_token_score", _summary_landmark_token_score)
    var _acc_chunk_cross_attention_weight: Float64 = 0.0
    var _t0_chunk_cross_attention_weight = perf_counter_ns()
    for _ in range(N):
        _acc_chunk_cross_attention_weight += chunk_cross_attention_weight(0.5, 0.5, 0.5, 0.5)
    var _t1_chunk_cross_attention_weight = perf_counter_ns()
    var _ns_chunk_cross_attention_weight = Float64(_t1_chunk_cross_attention_weight - _t0_chunk_cross_attention_weight) / Float64(N)
    print("MOJO_TIMING sparse_attention::chunk_cross_attention_weight", _ns_chunk_cross_attention_weight, _acc_chunk_cross_attention_weight)
    var _result_chunk_cross_attention_weight = chunk_cross_attention_weight(0.5, 0.5, 0.5, 0.5)
    var _summary_chunk_cross_attention_weight = _summary_float64(_result_chunk_cross_attention_weight)
    print("MOJO_RESULT sparse_attention::chunk_cross_attention_weight", _summary_chunk_cross_attention_weight)
    var _acc_linear_attention_kernel: Float64 = 0.0
    var _t0_linear_attention_kernel = perf_counter_ns()
    for _ in range(N):
        _acc_linear_attention_kernel += linear_attention_kernel(0.5)
    var _t1_linear_attention_kernel = perf_counter_ns()
    var _ns_linear_attention_kernel = Float64(_t1_linear_attention_kernel - _t0_linear_attention_kernel) / Float64(N)
    print("MOJO_TIMING sparse_attention::linear_attention_kernel", _ns_linear_attention_kernel, _acc_linear_attention_kernel)
    var _result_linear_attention_kernel = linear_attention_kernel(0.5)
    var _summary_linear_attention_kernel = _summary_float64(_result_linear_attention_kernel)
    print("MOJO_RESULT sparse_attention::linear_attention_kernel", _summary_linear_attention_kernel)
    var _acc_recurrent_memory_update: Float64 = 0.0
    var _t0_recurrent_memory_update = perf_counter_ns()
    for _ in range(N):
        _acc_recurrent_memory_update += recurrent_memory_update(0.5, 0.5, 0.5, 0.5)
    var _t1_recurrent_memory_update = perf_counter_ns()
    var _ns_recurrent_memory_update = Float64(_t1_recurrent_memory_update - _t0_recurrent_memory_update) / Float64(N)
    print("MOJO_TIMING sparse_attention::recurrent_memory_update", _ns_recurrent_memory_update, _acc_recurrent_memory_update)
    var _result_recurrent_memory_update = recurrent_memory_update(0.5, 0.5, 0.5, 0.5)
    var _summary_recurrent_memory_update = _summary_float64(_result_recurrent_memory_update)
    print("MOJO_RESULT sparse_attention::recurrent_memory_update", _summary_recurrent_memory_update)
    var _acc_block_sparse_density: Float64 = 0.0
    var _t0_block_sparse_density = perf_counter_ns()
    for _ in range(N):
        _acc_block_sparse_density += block_sparse_density(0.5, 0.5)
    var _t1_block_sparse_density = perf_counter_ns()
    var _ns_block_sparse_density = Float64(_t1_block_sparse_density - _t0_block_sparse_density) / Float64(N)
    print("MOJO_TIMING sparse_attention::block_sparse_density", _ns_block_sparse_density, _acc_block_sparse_density)
    var _result_block_sparse_density = block_sparse_density(0.5, 0.5)
    var _summary_block_sparse_density = _summary_float64(_result_block_sparse_density)
    print("MOJO_RESULT sparse_attention::block_sparse_density", _summary_block_sparse_density)
    var _acc_hyper_attention_estimate: Float64 = 0.0
    var _t0_hyper_attention_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_hyper_attention_estimate += hyper_attention_estimate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_hyper_attention_estimate = perf_counter_ns()
    var _ns_hyper_attention_estimate = Float64(_t1_hyper_attention_estimate - _t0_hyper_attention_estimate) / Float64(N)
    print("MOJO_TIMING sparse_attention::hyper_attention_estimate", _ns_hyper_attention_estimate, _acc_hyper_attention_estimate)
    var _result_hyper_attention_estimate = hyper_attention_estimate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_hyper_attention_estimate = _summary_float64(_result_hyper_attention_estimate)
    print("MOJO_RESULT sparse_attention::hyper_attention_estimate", _summary_hyper_attention_estimate)
