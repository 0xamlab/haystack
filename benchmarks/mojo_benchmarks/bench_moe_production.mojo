"""bench_moe_production.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from moe_production import token_drop_fraction, expert_load_imbalance, communication_efficiency_moe, expert_affinity_score, capacity_overflow_penalty, expert_shard_memory_bytes, routing_entropy_balance, gradient_through_router, expert_activation_sparsity, dynamic_capacity_factor
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

    var _acc_token_drop_fraction: Float64 = 0.0
    var _t0_token_drop_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_token_drop_fraction += token_drop_fraction(0.5, 0.5)
    var _t1_token_drop_fraction = perf_counter_ns()
    var _ns_token_drop_fraction = Float64(_t1_token_drop_fraction - _t0_token_drop_fraction) / Float64(N)
    print("MOJO_TIMING moe_production::token_drop_fraction", _ns_token_drop_fraction, _acc_token_drop_fraction)
    var _result_token_drop_fraction = token_drop_fraction(0.5, 0.5)
    var _summary_token_drop_fraction = _summary_float64(_result_token_drop_fraction)
    print("MOJO_RESULT moe_production::token_drop_fraction", _summary_token_drop_fraction)
    var _acc_expert_load_imbalance: Float64 = 0.0
    var _t0_expert_load_imbalance = perf_counter_ns()
    for _ in range(N):
        _acc_expert_load_imbalance += expert_load_imbalance(0.5, 0.5)
    var _t1_expert_load_imbalance = perf_counter_ns()
    var _ns_expert_load_imbalance = Float64(_t1_expert_load_imbalance - _t0_expert_load_imbalance) / Float64(N)
    print("MOJO_TIMING moe_production::expert_load_imbalance", _ns_expert_load_imbalance, _acc_expert_load_imbalance)
    var _result_expert_load_imbalance = expert_load_imbalance(0.5, 0.5)
    var _summary_expert_load_imbalance = _summary_float64(_result_expert_load_imbalance)
    print("MOJO_RESULT moe_production::expert_load_imbalance", _summary_expert_load_imbalance)
    var _acc_communication_efficiency_moe: Float64 = 0.0
    var _t0_communication_efficiency_moe = perf_counter_ns()
    for _ in range(N):
        _acc_communication_efficiency_moe += communication_efficiency_moe(0.5, 0.5)
    var _t1_communication_efficiency_moe = perf_counter_ns()
    var _ns_communication_efficiency_moe = Float64(_t1_communication_efficiency_moe - _t0_communication_efficiency_moe) / Float64(N)
    print("MOJO_TIMING moe_production::communication_efficiency_moe", _ns_communication_efficiency_moe, _acc_communication_efficiency_moe)
    var _result_communication_efficiency_moe = communication_efficiency_moe(0.5, 0.5)
    var _summary_communication_efficiency_moe = _summary_float64(_result_communication_efficiency_moe)
    print("MOJO_RESULT moe_production::communication_efficiency_moe", _summary_communication_efficiency_moe)
    var _acc_expert_affinity_score: Float64 = 0.0
    var _t0_expert_affinity_score = perf_counter_ns()
    for _ in range(N):
        _acc_expert_affinity_score += expert_affinity_score(0.5, 0.5, 0.5)
    var _t1_expert_affinity_score = perf_counter_ns()
    var _ns_expert_affinity_score = Float64(_t1_expert_affinity_score - _t0_expert_affinity_score) / Float64(N)
    print("MOJO_TIMING moe_production::expert_affinity_score", _ns_expert_affinity_score, _acc_expert_affinity_score)
    var _result_expert_affinity_score = expert_affinity_score(0.5, 0.5, 0.5)
    var _summary_expert_affinity_score = _summary_float64(_result_expert_affinity_score)
    print("MOJO_RESULT moe_production::expert_affinity_score", _summary_expert_affinity_score)
    var _acc_capacity_overflow_penalty: Float64 = 0.0
    var _t0_capacity_overflow_penalty = perf_counter_ns()
    for _ in range(N):
        _acc_capacity_overflow_penalty += capacity_overflow_penalty(0.5, 0.5, 0.5)
    var _t1_capacity_overflow_penalty = perf_counter_ns()
    var _ns_capacity_overflow_penalty = Float64(_t1_capacity_overflow_penalty - _t0_capacity_overflow_penalty) / Float64(N)
    print("MOJO_TIMING moe_production::capacity_overflow_penalty", _ns_capacity_overflow_penalty, _acc_capacity_overflow_penalty)
    var _result_capacity_overflow_penalty = capacity_overflow_penalty(0.5, 0.5, 0.5)
    var _summary_capacity_overflow_penalty = _summary_float64(_result_capacity_overflow_penalty)
    print("MOJO_RESULT moe_production::capacity_overflow_penalty", _summary_capacity_overflow_penalty)
    var _acc_expert_shard_memory_bytes: Float64 = 0.0
    var _t0_expert_shard_memory_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_expert_shard_memory_bytes += expert_shard_memory_bytes(0.5, 0.5, 0.5)
    var _t1_expert_shard_memory_bytes = perf_counter_ns()
    var _ns_expert_shard_memory_bytes = Float64(_t1_expert_shard_memory_bytes - _t0_expert_shard_memory_bytes) / Float64(N)
    print("MOJO_TIMING moe_production::expert_shard_memory_bytes", _ns_expert_shard_memory_bytes, _acc_expert_shard_memory_bytes)
    var _result_expert_shard_memory_bytes = expert_shard_memory_bytes(0.5, 0.5, 0.5)
    var _summary_expert_shard_memory_bytes = _summary_float64(_result_expert_shard_memory_bytes)
    print("MOJO_RESULT moe_production::expert_shard_memory_bytes", _summary_expert_shard_memory_bytes)
    var _acc_routing_entropy_balance: Float64 = 0.0
    var _t0_routing_entropy_balance = perf_counter_ns()
    for _ in range(N):
        _acc_routing_entropy_balance += routing_entropy_balance(0.5, 0.5)
    var _t1_routing_entropy_balance = perf_counter_ns()
    var _ns_routing_entropy_balance = Float64(_t1_routing_entropy_balance - _t0_routing_entropy_balance) / Float64(N)
    print("MOJO_TIMING moe_production::routing_entropy_balance", _ns_routing_entropy_balance, _acc_routing_entropy_balance)
    var _result_routing_entropy_balance = routing_entropy_balance(0.5, 0.5)
    var _summary_routing_entropy_balance = _summary_float64(_result_routing_entropy_balance)
    print("MOJO_RESULT moe_production::routing_entropy_balance", _summary_routing_entropy_balance)
    var _acc_gradient_through_router: Float64 = 0.0
    var _t0_gradient_through_router = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_through_router += gradient_through_router(0.5, 0.5)
    var _t1_gradient_through_router = perf_counter_ns()
    var _ns_gradient_through_router = Float64(_t1_gradient_through_router - _t0_gradient_through_router) / Float64(N)
    print("MOJO_TIMING moe_production::gradient_through_router", _ns_gradient_through_router, _acc_gradient_through_router)
    var _result_gradient_through_router = gradient_through_router(0.5, 0.5)
    var _summary_gradient_through_router = _summary_float64(_result_gradient_through_router)
    print("MOJO_RESULT moe_production::gradient_through_router", _summary_gradient_through_router)
    var _acc_expert_activation_sparsity: Float64 = 0.0
    var _t0_expert_activation_sparsity = perf_counter_ns()
    for _ in range(N):
        _acc_expert_activation_sparsity += expert_activation_sparsity(0.5, 0.5)
    var _t1_expert_activation_sparsity = perf_counter_ns()
    var _ns_expert_activation_sparsity = Float64(_t1_expert_activation_sparsity - _t0_expert_activation_sparsity) / Float64(N)
    print("MOJO_TIMING moe_production::expert_activation_sparsity", _ns_expert_activation_sparsity, _acc_expert_activation_sparsity)
    var _result_expert_activation_sparsity = expert_activation_sparsity(0.5, 0.5)
    var _summary_expert_activation_sparsity = _summary_float64(_result_expert_activation_sparsity)
    print("MOJO_RESULT moe_production::expert_activation_sparsity", _summary_expert_activation_sparsity)
    var _acc_dynamic_capacity_factor: Float64 = 0.0
    var _t0_dynamic_capacity_factor = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_capacity_factor += dynamic_capacity_factor(0.5, 0.5, 0.5, 0.5)
    var _t1_dynamic_capacity_factor = perf_counter_ns()
    var _ns_dynamic_capacity_factor = Float64(_t1_dynamic_capacity_factor - _t0_dynamic_capacity_factor) / Float64(N)
    print("MOJO_TIMING moe_production::dynamic_capacity_factor", _ns_dynamic_capacity_factor, _acc_dynamic_capacity_factor)
    var _result_dynamic_capacity_factor = dynamic_capacity_factor(0.5, 0.5, 0.5, 0.5)
    var _summary_dynamic_capacity_factor = _summary_float64(_result_dynamic_capacity_factor)
    print("MOJO_RESULT moe_production::dynamic_capacity_factor", _summary_dynamic_capacity_factor)
