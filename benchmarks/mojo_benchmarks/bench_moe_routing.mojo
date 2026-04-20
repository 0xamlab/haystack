"""bench_moe_routing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from moe_routing import noisy_top_k_gate, switch_transformer_gate, expert_parallel_shard_id, gshard_gate_weight, expert_dropout_mask, combined_jitter_noise, aux_loss_coefficient, expert_choice_gate, cosine_router_score, heterogeneous_expert_capacity
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

    var _acc_noisy_top_k_gate: Float64 = 0.0
    var _t0_noisy_top_k_gate = perf_counter_ns()
    for _ in range(N):
        _acc_noisy_top_k_gate += noisy_top_k_gate(0.5, 0.5, 0.5)
    var _t1_noisy_top_k_gate = perf_counter_ns()
    var _ns_noisy_top_k_gate = Float64(_t1_noisy_top_k_gate - _t0_noisy_top_k_gate) / Float64(N)
    print("MOJO_TIMING moe_routing::noisy_top_k_gate", _ns_noisy_top_k_gate, _acc_noisy_top_k_gate)
    var _acc_switch_transformer_gate: Float64 = 0.0
    var _t0_switch_transformer_gate = perf_counter_ns()
    for _ in range(N):
        _acc_switch_transformer_gate += switch_transformer_gate(0.5, 0.5, 0.5)
    var _t1_switch_transformer_gate = perf_counter_ns()
    var _ns_switch_transformer_gate = Float64(_t1_switch_transformer_gate - _t0_switch_transformer_gate) / Float64(N)
    print("MOJO_TIMING moe_routing::switch_transformer_gate", _ns_switch_transformer_gate, _acc_switch_transformer_gate)
    var _acc_expert_parallel_shard_id: Float64 = 0.0
    var _t0_expert_parallel_shard_id = perf_counter_ns()
    for _ in range(N):
        _acc_expert_parallel_shard_id += expert_parallel_shard_id(0.5, 0.5)
    var _t1_expert_parallel_shard_id = perf_counter_ns()
    var _ns_expert_parallel_shard_id = Float64(_t1_expert_parallel_shard_id - _t0_expert_parallel_shard_id) / Float64(N)
    print("MOJO_TIMING moe_routing::expert_parallel_shard_id", _ns_expert_parallel_shard_id, _acc_expert_parallel_shard_id)
    var _acc_gshard_gate_weight: Float64 = 0.0
    var _t0_gshard_gate_weight = perf_counter_ns()
    for _ in range(N):
        _acc_gshard_gate_weight += gshard_gate_weight(0.5, 0.5, 0.5)
    var _t1_gshard_gate_weight = perf_counter_ns()
    var _ns_gshard_gate_weight = Float64(_t1_gshard_gate_weight - _t0_gshard_gate_weight) / Float64(N)
    print("MOJO_TIMING moe_routing::gshard_gate_weight", _ns_gshard_gate_weight, _acc_gshard_gate_weight)
    var _acc_expert_dropout_mask: Float64 = 0.0
    var _t0_expert_dropout_mask = perf_counter_ns()
    for _ in range(N):
        _acc_expert_dropout_mask += expert_dropout_mask(0.5, 0.5, 0.5)
    var _t1_expert_dropout_mask = perf_counter_ns()
    var _ns_expert_dropout_mask = Float64(_t1_expert_dropout_mask - _t0_expert_dropout_mask) / Float64(N)
    print("MOJO_TIMING moe_routing::expert_dropout_mask", _ns_expert_dropout_mask, _acc_expert_dropout_mask)
    var _acc_combined_jitter_noise: Float64 = 0.0
    var _t0_combined_jitter_noise = perf_counter_ns()
    for _ in range(N):
        _acc_combined_jitter_noise += combined_jitter_noise(0.5, 0.5, 0.5)
    var _t1_combined_jitter_noise = perf_counter_ns()
    var _ns_combined_jitter_noise = Float64(_t1_combined_jitter_noise - _t0_combined_jitter_noise) / Float64(N)
    print("MOJO_TIMING moe_routing::combined_jitter_noise", _ns_combined_jitter_noise, _acc_combined_jitter_noise)
    var _acc_aux_loss_coefficient: Float64 = 0.0
    var _t0_aux_loss_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_aux_loss_coefficient += aux_loss_coefficient(0.5, 0.5, 0.5)
    var _t1_aux_loss_coefficient = perf_counter_ns()
    var _ns_aux_loss_coefficient = Float64(_t1_aux_loss_coefficient - _t0_aux_loss_coefficient) / Float64(N)
    print("MOJO_TIMING moe_routing::aux_loss_coefficient", _ns_aux_loss_coefficient, _acc_aux_loss_coefficient)
    var _acc_expert_choice_gate: Float64 = 0.0
    var _t0_expert_choice_gate = perf_counter_ns()
    for _ in range(N):
        _acc_expert_choice_gate += expert_choice_gate(0.5, 0.5, 0.5)
    var _t1_expert_choice_gate = perf_counter_ns()
    var _ns_expert_choice_gate = Float64(_t1_expert_choice_gate - _t0_expert_choice_gate) / Float64(N)
    print("MOJO_TIMING moe_routing::expert_choice_gate", _ns_expert_choice_gate, _acc_expert_choice_gate)
    var _acc_cosine_router_score: Float64 = 0.0
    var _t0_cosine_router_score = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_router_score += cosine_router_score(0.5, 0.5, 0.5)
    var _t1_cosine_router_score = perf_counter_ns()
    var _ns_cosine_router_score = Float64(_t1_cosine_router_score - _t0_cosine_router_score) / Float64(N)
    print("MOJO_TIMING moe_routing::cosine_router_score", _ns_cosine_router_score, _acc_cosine_router_score)
    var _acc_heterogeneous_expert_capacity: Float64 = 0.0
    var _t0_heterogeneous_expert_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_heterogeneous_expert_capacity += heterogeneous_expert_capacity(0.5, 0.5)
    var _t1_heterogeneous_expert_capacity = perf_counter_ns()
    var _ns_heterogeneous_expert_capacity = Float64(_t1_heterogeneous_expert_capacity - _t0_heterogeneous_expert_capacity) / Float64(N)
    print("MOJO_TIMING moe_routing::heterogeneous_expert_capacity", _ns_heterogeneous_expert_capacity, _acc_heterogeneous_expert_capacity)
