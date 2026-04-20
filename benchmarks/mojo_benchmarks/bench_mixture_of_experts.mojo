"""bench_mixture_of_experts.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from mixture_of_experts import topk_gate_score, expert_load_fraction, load_balance_loss, router_z_loss, expert_capacity, token_dispatch_weight, sparse_gate_entropy, soft_moe_slot_score, expert_utilization, moe_ffn_output
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

    var _acc_topk_gate_score: Float64 = 0.0
    var _t0_topk_gate_score = perf_counter_ns()
    for _ in range(N):
        _acc_topk_gate_score += topk_gate_score(0.5, 0.5)
    var _t1_topk_gate_score = perf_counter_ns()
    var _ns_topk_gate_score = Float64(_t1_topk_gate_score - _t0_topk_gate_score) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::topk_gate_score", _ns_topk_gate_score, _acc_topk_gate_score)
    var _acc_expert_load_fraction: Float64 = 0.0
    var _t0_expert_load_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_expert_load_fraction += expert_load_fraction(0.5, 0.5)
    var _t1_expert_load_fraction = perf_counter_ns()
    var _ns_expert_load_fraction = Float64(_t1_expert_load_fraction - _t0_expert_load_fraction) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::expert_load_fraction", _ns_expert_load_fraction, _acc_expert_load_fraction)
    var _acc_load_balance_loss: Float64 = 0.0
    var _t0_load_balance_loss = perf_counter_ns()
    for _ in range(N):
        _acc_load_balance_loss += load_balance_loss(0.5, 0.5, 0.5)
    var _t1_load_balance_loss = perf_counter_ns()
    var _ns_load_balance_loss = Float64(_t1_load_balance_loss - _t0_load_balance_loss) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::load_balance_loss", _ns_load_balance_loss, _acc_load_balance_loss)
    var _acc_router_z_loss: Float64 = 0.0
    var _t0_router_z_loss = perf_counter_ns()
    for _ in range(N):
        _acc_router_z_loss += router_z_loss(0.5, 0.5)
    var _t1_router_z_loss = perf_counter_ns()
    var _ns_router_z_loss = Float64(_t1_router_z_loss - _t0_router_z_loss) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::router_z_loss", _ns_router_z_loss, _acc_router_z_loss)
    var _acc_expert_capacity: Float64 = 0.0
    var _t0_expert_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_expert_capacity += expert_capacity(0.5, 0.5, 0.5)
    var _t1_expert_capacity = perf_counter_ns()
    var _ns_expert_capacity = Float64(_t1_expert_capacity - _t0_expert_capacity) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::expert_capacity", _ns_expert_capacity, _acc_expert_capacity)
    var _acc_token_dispatch_weight: Float64 = 0.0
    var _t0_token_dispatch_weight = perf_counter_ns()
    for _ in range(N):
        _acc_token_dispatch_weight += token_dispatch_weight(0.5, 0.5)
    var _t1_token_dispatch_weight = perf_counter_ns()
    var _ns_token_dispatch_weight = Float64(_t1_token_dispatch_weight - _t0_token_dispatch_weight) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::token_dispatch_weight", _ns_token_dispatch_weight, _acc_token_dispatch_weight)
    var _acc_sparse_gate_entropy: Float64 = 0.0
    var _t0_sparse_gate_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_sparse_gate_entropy += sparse_gate_entropy(0.5, 0.5)
    var _t1_sparse_gate_entropy = perf_counter_ns()
    var _ns_sparse_gate_entropy = Float64(_t1_sparse_gate_entropy - _t0_sparse_gate_entropy) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::sparse_gate_entropy", _ns_sparse_gate_entropy, _acc_sparse_gate_entropy)
    var _acc_soft_moe_slot_score: Float64 = 0.0
    var _t0_soft_moe_slot_score = perf_counter_ns()
    for _ in range(N):
        _acc_soft_moe_slot_score += soft_moe_slot_score(0.5, 0.5)
    var _t1_soft_moe_slot_score = perf_counter_ns()
    var _ns_soft_moe_slot_score = Float64(_t1_soft_moe_slot_score - _t0_soft_moe_slot_score) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::soft_moe_slot_score", _ns_soft_moe_slot_score, _acc_soft_moe_slot_score)
    var _acc_expert_utilization: Float64 = 0.0
    var _t0_expert_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_expert_utilization += expert_utilization(0.5, 0.5)
    var _t1_expert_utilization = perf_counter_ns()
    var _ns_expert_utilization = Float64(_t1_expert_utilization - _t0_expert_utilization) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::expert_utilization", _ns_expert_utilization, _acc_expert_utilization)
    var _acc_moe_ffn_output: Float64 = 0.0
    var _t0_moe_ffn_output = perf_counter_ns()
    for _ in range(N):
        _acc_moe_ffn_output += moe_ffn_output(0.5, 0.5)
    var _t1_moe_ffn_output = perf_counter_ns()
    var _ns_moe_ffn_output = Float64(_t1_moe_ffn_output - _t0_moe_ffn_output) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::moe_ffn_output", _ns_moe_ffn_output, _acc_moe_ffn_output)
