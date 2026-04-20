"""bench_cost_router.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cost_router import request_cost_estimate, latency_cost_tradeoff, gpu_vs_cpu_routing_score, batch_vs_single_decision, quantized_vs_full_routing, moe_vs_dense_routing, cascade_model_routing, budget_remaining_fraction, sla_headroom_score, cost_per_output_token
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

    var _acc_request_cost_estimate: Float64 = 0.0
    var _t0_request_cost_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_request_cost_estimate += request_cost_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_request_cost_estimate = perf_counter_ns()
    var _ns_request_cost_estimate = Float64(_t1_request_cost_estimate - _t0_request_cost_estimate) / Float64(N)
    print("MOJO_TIMING cost_router::request_cost_estimate", _ns_request_cost_estimate, _acc_request_cost_estimate)
    var _acc_latency_cost_tradeoff: Float64 = 0.0
    var _t0_latency_cost_tradeoff = perf_counter_ns()
    for _ in range(N):
        _acc_latency_cost_tradeoff += latency_cost_tradeoff(0.5, 0.5, 0.5, 0.5)
    var _t1_latency_cost_tradeoff = perf_counter_ns()
    var _ns_latency_cost_tradeoff = Float64(_t1_latency_cost_tradeoff - _t0_latency_cost_tradeoff) / Float64(N)
    print("MOJO_TIMING cost_router::latency_cost_tradeoff", _ns_latency_cost_tradeoff, _acc_latency_cost_tradeoff)
    var _acc_gpu_vs_cpu_routing_score: Float64 = 0.0
    var _t0_gpu_vs_cpu_routing_score = perf_counter_ns()
    for _ in range(N):
        _acc_gpu_vs_cpu_routing_score += gpu_vs_cpu_routing_score(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_gpu_vs_cpu_routing_score = perf_counter_ns()
    var _ns_gpu_vs_cpu_routing_score = Float64(_t1_gpu_vs_cpu_routing_score - _t0_gpu_vs_cpu_routing_score) / Float64(N)
    print("MOJO_TIMING cost_router::gpu_vs_cpu_routing_score", _ns_gpu_vs_cpu_routing_score, _acc_gpu_vs_cpu_routing_score)
    var _acc_batch_vs_single_decision: Float64 = 0.0
    var _t0_batch_vs_single_decision = perf_counter_ns()
    for _ in range(N):
        _acc_batch_vs_single_decision += batch_vs_single_decision(0.5, 0.5, 0.5, 0.5)
    var _t1_batch_vs_single_decision = perf_counter_ns()
    var _ns_batch_vs_single_decision = Float64(_t1_batch_vs_single_decision - _t0_batch_vs_single_decision) / Float64(N)
    print("MOJO_TIMING cost_router::batch_vs_single_decision", _ns_batch_vs_single_decision, _acc_batch_vs_single_decision)
    var _acc_quantized_vs_full_routing: Float64 = 0.0
    var _t0_quantized_vs_full_routing = perf_counter_ns()
    for _ in range(N):
        _acc_quantized_vs_full_routing += quantized_vs_full_routing(0.5, 0.5, 0.5, 0.5)
    var _t1_quantized_vs_full_routing = perf_counter_ns()
    var _ns_quantized_vs_full_routing = Float64(_t1_quantized_vs_full_routing - _t0_quantized_vs_full_routing) / Float64(N)
    print("MOJO_TIMING cost_router::quantized_vs_full_routing", _ns_quantized_vs_full_routing, _acc_quantized_vs_full_routing)
    var _acc_moe_vs_dense_routing: Float64 = 0.0
    var _t0_moe_vs_dense_routing = perf_counter_ns()
    for _ in range(N):
        _acc_moe_vs_dense_routing += moe_vs_dense_routing(0.5, 0.5, 0.5, 0.5)
    var _t1_moe_vs_dense_routing = perf_counter_ns()
    var _ns_moe_vs_dense_routing = Float64(_t1_moe_vs_dense_routing - _t0_moe_vs_dense_routing) / Float64(N)
    print("MOJO_TIMING cost_router::moe_vs_dense_routing", _ns_moe_vs_dense_routing, _acc_moe_vs_dense_routing)
    var _acc_cascade_model_routing: Float64 = 0.0
    var _t0_cascade_model_routing = perf_counter_ns()
    for _ in range(N):
        _acc_cascade_model_routing += cascade_model_routing(0.5, 0.5, 0.5, 0.5)
    var _t1_cascade_model_routing = perf_counter_ns()
    var _ns_cascade_model_routing = Float64(_t1_cascade_model_routing - _t0_cascade_model_routing) / Float64(N)
    print("MOJO_TIMING cost_router::cascade_model_routing", _ns_cascade_model_routing, _acc_cascade_model_routing)
    var _acc_budget_remaining_fraction: Float64 = 0.0
    var _t0_budget_remaining_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_budget_remaining_fraction += budget_remaining_fraction(0.5, 0.5)
    var _t1_budget_remaining_fraction = perf_counter_ns()
    var _ns_budget_remaining_fraction = Float64(_t1_budget_remaining_fraction - _t0_budget_remaining_fraction) / Float64(N)
    print("MOJO_TIMING cost_router::budget_remaining_fraction", _ns_budget_remaining_fraction, _acc_budget_remaining_fraction)
    var _acc_sla_headroom_score: Float64 = 0.0
    var _t0_sla_headroom_score = perf_counter_ns()
    for _ in range(N):
        _acc_sla_headroom_score += sla_headroom_score(0.5, 0.5)
    var _t1_sla_headroom_score = perf_counter_ns()
    var _ns_sla_headroom_score = Float64(_t1_sla_headroom_score - _t0_sla_headroom_score) / Float64(N)
    print("MOJO_TIMING cost_router::sla_headroom_score", _ns_sla_headroom_score, _acc_sla_headroom_score)
    var _acc_cost_per_output_token: Float64 = 0.0
    var _t0_cost_per_output_token = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_output_token += cost_per_output_token(0.5, 0.5)
    var _t1_cost_per_output_token = perf_counter_ns()
    var _ns_cost_per_output_token = Float64(_t1_cost_per_output_token - _t0_cost_per_output_token) / Float64(N)
    print("MOJO_TIMING cost_router::cost_per_output_token", _ns_cost_per_output_token, _acc_cost_per_output_token)
