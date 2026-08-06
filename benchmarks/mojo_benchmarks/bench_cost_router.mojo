"""bench_cost_router.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cost_router import request_cost_estimate, latency_cost_tradeoff, gpu_vs_cpu_routing_score, batch_vs_single_decision, quantized_vs_full_routing, moe_vs_dense_routing, cascade_model_routing, budget_remaining_fraction, sla_headroom_score, cost_per_output_token
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

    var _acc_request_cost_estimate: Float64 = 0.0
    var _t0_request_cost_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_request_cost_estimate += request_cost_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_request_cost_estimate = perf_counter_ns()
    var _ns_request_cost_estimate = Float64(_t1_request_cost_estimate - _t0_request_cost_estimate) / Float64(N)
    print("MOJO_TIMING cost_router::request_cost_estimate", _ns_request_cost_estimate, _acc_request_cost_estimate)
    var _result_request_cost_estimate = request_cost_estimate(0.5, 0.5, 0.5, 0.5)
    var _summary_request_cost_estimate = _summary_float64(_result_request_cost_estimate)
    print("MOJO_RESULT cost_router::request_cost_estimate", _summary_request_cost_estimate)
    var _acc_latency_cost_tradeoff: Float64 = 0.0
    var _t0_latency_cost_tradeoff = perf_counter_ns()
    for _ in range(N):
        _acc_latency_cost_tradeoff += latency_cost_tradeoff(0.5, 0.5, 0.5, 0.5)
    var _t1_latency_cost_tradeoff = perf_counter_ns()
    var _ns_latency_cost_tradeoff = Float64(_t1_latency_cost_tradeoff - _t0_latency_cost_tradeoff) / Float64(N)
    print("MOJO_TIMING cost_router::latency_cost_tradeoff", _ns_latency_cost_tradeoff, _acc_latency_cost_tradeoff)
    var _result_latency_cost_tradeoff = latency_cost_tradeoff(0.5, 0.5, 0.5, 0.5)
    var _summary_latency_cost_tradeoff = _summary_float64(_result_latency_cost_tradeoff)
    print("MOJO_RESULT cost_router::latency_cost_tradeoff", _summary_latency_cost_tradeoff)
    var _acc_gpu_vs_cpu_routing_score: Float64 = 0.0
    var _t0_gpu_vs_cpu_routing_score = perf_counter_ns()
    for _ in range(N):
        _acc_gpu_vs_cpu_routing_score += gpu_vs_cpu_routing_score(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_gpu_vs_cpu_routing_score = perf_counter_ns()
    var _ns_gpu_vs_cpu_routing_score = Float64(_t1_gpu_vs_cpu_routing_score - _t0_gpu_vs_cpu_routing_score) / Float64(N)
    print("MOJO_TIMING cost_router::gpu_vs_cpu_routing_score", _ns_gpu_vs_cpu_routing_score, _acc_gpu_vs_cpu_routing_score)
    var _result_gpu_vs_cpu_routing_score = gpu_vs_cpu_routing_score(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_gpu_vs_cpu_routing_score = _summary_float64(_result_gpu_vs_cpu_routing_score)
    print("MOJO_RESULT cost_router::gpu_vs_cpu_routing_score", _summary_gpu_vs_cpu_routing_score)
    var _acc_batch_vs_single_decision: Float64 = 0.0
    var _t0_batch_vs_single_decision = perf_counter_ns()
    for _ in range(N):
        _acc_batch_vs_single_decision += batch_vs_single_decision(0.5, 0.5, 0.5, 0.5)
    var _t1_batch_vs_single_decision = perf_counter_ns()
    var _ns_batch_vs_single_decision = Float64(_t1_batch_vs_single_decision - _t0_batch_vs_single_decision) / Float64(N)
    print("MOJO_TIMING cost_router::batch_vs_single_decision", _ns_batch_vs_single_decision, _acc_batch_vs_single_decision)
    var _result_batch_vs_single_decision = batch_vs_single_decision(0.5, 0.5, 0.5, 0.5)
    var _summary_batch_vs_single_decision = _summary_float64(_result_batch_vs_single_decision)
    print("MOJO_RESULT cost_router::batch_vs_single_decision", _summary_batch_vs_single_decision)
    var _acc_quantized_vs_full_routing: Float64 = 0.0
    var _t0_quantized_vs_full_routing = perf_counter_ns()
    for _ in range(N):
        _acc_quantized_vs_full_routing += quantized_vs_full_routing(0.5, 0.5, 0.5, 0.5)
    var _t1_quantized_vs_full_routing = perf_counter_ns()
    var _ns_quantized_vs_full_routing = Float64(_t1_quantized_vs_full_routing - _t0_quantized_vs_full_routing) / Float64(N)
    print("MOJO_TIMING cost_router::quantized_vs_full_routing", _ns_quantized_vs_full_routing, _acc_quantized_vs_full_routing)
    var _result_quantized_vs_full_routing = quantized_vs_full_routing(0.5, 0.5, 0.5, 0.5)
    var _summary_quantized_vs_full_routing = _summary_float64(_result_quantized_vs_full_routing)
    print("MOJO_RESULT cost_router::quantized_vs_full_routing", _summary_quantized_vs_full_routing)
    var _acc_moe_vs_dense_routing: Float64 = 0.0
    var _t0_moe_vs_dense_routing = perf_counter_ns()
    for _ in range(N):
        _acc_moe_vs_dense_routing += moe_vs_dense_routing(0.5, 0.5, 0.5, 0.5)
    var _t1_moe_vs_dense_routing = perf_counter_ns()
    var _ns_moe_vs_dense_routing = Float64(_t1_moe_vs_dense_routing - _t0_moe_vs_dense_routing) / Float64(N)
    print("MOJO_TIMING cost_router::moe_vs_dense_routing", _ns_moe_vs_dense_routing, _acc_moe_vs_dense_routing)
    var _result_moe_vs_dense_routing = moe_vs_dense_routing(0.5, 0.5, 0.5, 0.5)
    var _summary_moe_vs_dense_routing = _summary_float64(_result_moe_vs_dense_routing)
    print("MOJO_RESULT cost_router::moe_vs_dense_routing", _summary_moe_vs_dense_routing)
    var _acc_cascade_model_routing: Float64 = 0.0
    var _t0_cascade_model_routing = perf_counter_ns()
    for _ in range(N):
        _acc_cascade_model_routing += cascade_model_routing(0.5, 0.5, 0.5, 0.5)
    var _t1_cascade_model_routing = perf_counter_ns()
    var _ns_cascade_model_routing = Float64(_t1_cascade_model_routing - _t0_cascade_model_routing) / Float64(N)
    print("MOJO_TIMING cost_router::cascade_model_routing", _ns_cascade_model_routing, _acc_cascade_model_routing)
    var _result_cascade_model_routing = cascade_model_routing(0.5, 0.5, 0.5, 0.5)
    var _summary_cascade_model_routing = _summary_float64(_result_cascade_model_routing)
    print("MOJO_RESULT cost_router::cascade_model_routing", _summary_cascade_model_routing)
    var _acc_budget_remaining_fraction: Float64 = 0.0
    var _t0_budget_remaining_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_budget_remaining_fraction += budget_remaining_fraction(0.5, 0.5)
    var _t1_budget_remaining_fraction = perf_counter_ns()
    var _ns_budget_remaining_fraction = Float64(_t1_budget_remaining_fraction - _t0_budget_remaining_fraction) / Float64(N)
    print("MOJO_TIMING cost_router::budget_remaining_fraction", _ns_budget_remaining_fraction, _acc_budget_remaining_fraction)
    var _result_budget_remaining_fraction = budget_remaining_fraction(0.5, 0.5)
    var _summary_budget_remaining_fraction = _summary_float64(_result_budget_remaining_fraction)
    print("MOJO_RESULT cost_router::budget_remaining_fraction", _summary_budget_remaining_fraction)
    var _acc_sla_headroom_score: Float64 = 0.0
    var _t0_sla_headroom_score = perf_counter_ns()
    for _ in range(N):
        _acc_sla_headroom_score += sla_headroom_score(0.5, 0.5)
    var _t1_sla_headroom_score = perf_counter_ns()
    var _ns_sla_headroom_score = Float64(_t1_sla_headroom_score - _t0_sla_headroom_score) / Float64(N)
    print("MOJO_TIMING cost_router::sla_headroom_score", _ns_sla_headroom_score, _acc_sla_headroom_score)
    var _result_sla_headroom_score = sla_headroom_score(0.5, 0.5)
    var _summary_sla_headroom_score = _summary_float64(_result_sla_headroom_score)
    print("MOJO_RESULT cost_router::sla_headroom_score", _summary_sla_headroom_score)
    var _acc_cost_per_output_token: Float64 = 0.0
    var _t0_cost_per_output_token = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_output_token += cost_per_output_token(0.5, 0.5)
    var _t1_cost_per_output_token = perf_counter_ns()
    var _ns_cost_per_output_token = Float64(_t1_cost_per_output_token - _t0_cost_per_output_token) / Float64(N)
    print("MOJO_TIMING cost_router::cost_per_output_token", _ns_cost_per_output_token, _acc_cost_per_output_token)
    var _result_cost_per_output_token = cost_per_output_token(0.5, 0.5)
    var _summary_cost_per_output_token = _summary_float64(_result_cost_per_output_token)
    print("MOJO_RESULT cost_router::cost_per_output_token", _summary_cost_per_output_token)
