"""bench_mixture_of_experts.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from mixture_of_experts import topk_gate_score, expert_load_fraction, load_balance_loss, router_z_loss, expert_capacity, token_dispatch_weight, sparse_gate_entropy, soft_moe_slot_score, expert_utilization, moe_ffn_output
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

    var _acc_topk_gate_score: Float64 = 0.0
    var _t0_topk_gate_score = perf_counter_ns()
    for _ in range(N):
        _acc_topk_gate_score += topk_gate_score(0.5, 0.5)
    var _t1_topk_gate_score = perf_counter_ns()
    var _ns_topk_gate_score = Float64(_t1_topk_gate_score - _t0_topk_gate_score) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::topk_gate_score", _ns_topk_gate_score, _acc_topk_gate_score)
    var _result_topk_gate_score = topk_gate_score(0.5, 0.5)
    var _summary_topk_gate_score = _summary_float64(_result_topk_gate_score)
    print("MOJO_RESULT mixture_of_experts::topk_gate_score", _summary_topk_gate_score)
    var _acc_expert_load_fraction: Float64 = 0.0
    var _t0_expert_load_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_expert_load_fraction += expert_load_fraction(0.5, 0.5)
    var _t1_expert_load_fraction = perf_counter_ns()
    var _ns_expert_load_fraction = Float64(_t1_expert_load_fraction - _t0_expert_load_fraction) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::expert_load_fraction", _ns_expert_load_fraction, _acc_expert_load_fraction)
    var _result_expert_load_fraction = expert_load_fraction(0.5, 0.5)
    var _summary_expert_load_fraction = _summary_float64(_result_expert_load_fraction)
    print("MOJO_RESULT mixture_of_experts::expert_load_fraction", _summary_expert_load_fraction)
    var _acc_load_balance_loss: Float64 = 0.0
    var _t0_load_balance_loss = perf_counter_ns()
    for _ in range(N):
        _acc_load_balance_loss += load_balance_loss(0.5, 0.5, 0.5)
    var _t1_load_balance_loss = perf_counter_ns()
    var _ns_load_balance_loss = Float64(_t1_load_balance_loss - _t0_load_balance_loss) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::load_balance_loss", _ns_load_balance_loss, _acc_load_balance_loss)
    var _result_load_balance_loss = load_balance_loss(0.5, 0.5, 0.5)
    var _summary_load_balance_loss = _summary_float64(_result_load_balance_loss)
    print("MOJO_RESULT mixture_of_experts::load_balance_loss", _summary_load_balance_loss)
    var _acc_router_z_loss: Float64 = 0.0
    var _t0_router_z_loss = perf_counter_ns()
    for _ in range(N):
        _acc_router_z_loss += router_z_loss(0.5, 0.5)
    var _t1_router_z_loss = perf_counter_ns()
    var _ns_router_z_loss = Float64(_t1_router_z_loss - _t0_router_z_loss) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::router_z_loss", _ns_router_z_loss, _acc_router_z_loss)
    var _result_router_z_loss = router_z_loss(0.5, 0.5)
    var _summary_router_z_loss = _summary_float64(_result_router_z_loss)
    print("MOJO_RESULT mixture_of_experts::router_z_loss", _summary_router_z_loss)
    var _acc_expert_capacity: Float64 = 0.0
    var _t0_expert_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_expert_capacity += expert_capacity(0.5, 0.5, 0.5)
    var _t1_expert_capacity = perf_counter_ns()
    var _ns_expert_capacity = Float64(_t1_expert_capacity - _t0_expert_capacity) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::expert_capacity", _ns_expert_capacity, _acc_expert_capacity)
    var _result_expert_capacity = expert_capacity(0.5, 0.5, 0.5)
    var _summary_expert_capacity = _summary_float64(_result_expert_capacity)
    print("MOJO_RESULT mixture_of_experts::expert_capacity", _summary_expert_capacity)
    var _acc_token_dispatch_weight: Float64 = 0.0
    var _t0_token_dispatch_weight = perf_counter_ns()
    for _ in range(N):
        _acc_token_dispatch_weight += token_dispatch_weight(0.5, 0.5)
    var _t1_token_dispatch_weight = perf_counter_ns()
    var _ns_token_dispatch_weight = Float64(_t1_token_dispatch_weight - _t0_token_dispatch_weight) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::token_dispatch_weight", _ns_token_dispatch_weight, _acc_token_dispatch_weight)
    var _result_token_dispatch_weight = token_dispatch_weight(0.5, 0.5)
    var _summary_token_dispatch_weight = _summary_float64(_result_token_dispatch_weight)
    print("MOJO_RESULT mixture_of_experts::token_dispatch_weight", _summary_token_dispatch_weight)
    var _acc_sparse_gate_entropy: Float64 = 0.0
    var _t0_sparse_gate_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_sparse_gate_entropy += sparse_gate_entropy(0.5, 0.5)
    var _t1_sparse_gate_entropy = perf_counter_ns()
    var _ns_sparse_gate_entropy = Float64(_t1_sparse_gate_entropy - _t0_sparse_gate_entropy) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::sparse_gate_entropy", _ns_sparse_gate_entropy, _acc_sparse_gate_entropy)
    var _result_sparse_gate_entropy = sparse_gate_entropy(0.5, 0.5)
    var _summary_sparse_gate_entropy = _summary_float64(_result_sparse_gate_entropy)
    print("MOJO_RESULT mixture_of_experts::sparse_gate_entropy", _summary_sparse_gate_entropy)
    var _acc_soft_moe_slot_score: Float64 = 0.0
    var _t0_soft_moe_slot_score = perf_counter_ns()
    for _ in range(N):
        _acc_soft_moe_slot_score += soft_moe_slot_score(0.5, 0.5)
    var _t1_soft_moe_slot_score = perf_counter_ns()
    var _ns_soft_moe_slot_score = Float64(_t1_soft_moe_slot_score - _t0_soft_moe_slot_score) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::soft_moe_slot_score", _ns_soft_moe_slot_score, _acc_soft_moe_slot_score)
    var _result_soft_moe_slot_score = soft_moe_slot_score(0.5, 0.5)
    var _summary_soft_moe_slot_score = _summary_float64(_result_soft_moe_slot_score)
    print("MOJO_RESULT mixture_of_experts::soft_moe_slot_score", _summary_soft_moe_slot_score)
    var _acc_expert_utilization: Float64 = 0.0
    var _t0_expert_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_expert_utilization += expert_utilization(0.5, 0.5)
    var _t1_expert_utilization = perf_counter_ns()
    var _ns_expert_utilization = Float64(_t1_expert_utilization - _t0_expert_utilization) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::expert_utilization", _ns_expert_utilization, _acc_expert_utilization)
    var _result_expert_utilization = expert_utilization(0.5, 0.5)
    var _summary_expert_utilization = _summary_float64(_result_expert_utilization)
    print("MOJO_RESULT mixture_of_experts::expert_utilization", _summary_expert_utilization)
    var _acc_moe_ffn_output: Float64 = 0.0
    var _t0_moe_ffn_output = perf_counter_ns()
    for _ in range(N):
        _acc_moe_ffn_output += moe_ffn_output(0.5, 0.5)
    var _t1_moe_ffn_output = perf_counter_ns()
    var _ns_moe_ffn_output = Float64(_t1_moe_ffn_output - _t0_moe_ffn_output) / Float64(N)
    print("MOJO_TIMING mixture_of_experts::moe_ffn_output", _ns_moe_ffn_output, _acc_moe_ffn_output)
    var _result_moe_ffn_output = moe_ffn_output(0.5, 0.5)
    var _summary_moe_ffn_output = _summary_float64(_result_moe_ffn_output)
    print("MOJO_RESULT mixture_of_experts::moe_ffn_output", _summary_moe_ffn_output)
