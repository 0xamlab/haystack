"""bench_blockchain.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from blockchain import block_reward_halving, hash_rate_to_difficulty, transaction_fee_priority, gas_cost, confirmations_security, merkle_tree_depth, tps_throughput, block_size_utilization, staking_apy, validator_uptime, finality_time_pbft, token_inflation_rate
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

    var _acc_block_reward_halving: Float64 = 0.0
    var _t0_block_reward_halving = perf_counter_ns()
    for _ in range(N):
        _acc_block_reward_halving += block_reward_halving(0.5, 5)
    var _t1_block_reward_halving = perf_counter_ns()
    var _ns_block_reward_halving = Float64(_t1_block_reward_halving - _t0_block_reward_halving) / Float64(N)
    print("MOJO_TIMING blockchain::block_reward_halving", _ns_block_reward_halving, _acc_block_reward_halving)
    var _acc_hash_rate_to_difficulty: Float64 = 0.0
    var _t0_hash_rate_to_difficulty = perf_counter_ns()
    for _ in range(N):
        _acc_hash_rate_to_difficulty += hash_rate_to_difficulty(0.5, 0.5)
    var _t1_hash_rate_to_difficulty = perf_counter_ns()
    var _ns_hash_rate_to_difficulty = Float64(_t1_hash_rate_to_difficulty - _t0_hash_rate_to_difficulty) / Float64(N)
    print("MOJO_TIMING blockchain::hash_rate_to_difficulty", _ns_hash_rate_to_difficulty, _acc_hash_rate_to_difficulty)
    var _acc_transaction_fee_priority: Float64 = 0.0
    var _t0_transaction_fee_priority = perf_counter_ns()
    for _ in range(N):
        _acc_transaction_fee_priority += transaction_fee_priority(0.5, 0.5)
    var _t1_transaction_fee_priority = perf_counter_ns()
    var _ns_transaction_fee_priority = Float64(_t1_transaction_fee_priority - _t0_transaction_fee_priority) / Float64(N)
    print("MOJO_TIMING blockchain::transaction_fee_priority", _ns_transaction_fee_priority, _acc_transaction_fee_priority)
    var _acc_gas_cost: Float64 = 0.0
    var _t0_gas_cost = perf_counter_ns()
    for _ in range(N):
        _acc_gas_cost += gas_cost(0.5, 0.5)
    var _t1_gas_cost = perf_counter_ns()
    var _ns_gas_cost = Float64(_t1_gas_cost - _t0_gas_cost) / Float64(N)
    print("MOJO_TIMING blockchain::gas_cost", _ns_gas_cost, _acc_gas_cost)
    var _acc_confirmations_security: Float64 = 0.0
    var _t0_confirmations_security = perf_counter_ns()
    for _ in range(N):
        _acc_confirmations_security += confirmations_security(5, 0.5)
    var _t1_confirmations_security = perf_counter_ns()
    var _ns_confirmations_security = Float64(_t1_confirmations_security - _t0_confirmations_security) / Float64(N)
    print("MOJO_TIMING blockchain::confirmations_security", _ns_confirmations_security, _acc_confirmations_security)
    var _acc_merkle_tree_depth: Float64 = 0.0
    var _t0_merkle_tree_depth = perf_counter_ns()
    for _ in range(N):
        _acc_merkle_tree_depth += Float64(merkle_tree_depth(5))
    var _t1_merkle_tree_depth = perf_counter_ns()
    var _ns_merkle_tree_depth = Float64(_t1_merkle_tree_depth - _t0_merkle_tree_depth) / Float64(N)
    print("MOJO_TIMING blockchain::merkle_tree_depth", _ns_merkle_tree_depth, _acc_merkle_tree_depth)
    var _acc_tps_throughput: Float64 = 0.0
    var _t0_tps_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_tps_throughput += tps_throughput(5, 0.5)
    var _t1_tps_throughput = perf_counter_ns()
    var _ns_tps_throughput = Float64(_t1_tps_throughput - _t0_tps_throughput) / Float64(N)
    print("MOJO_TIMING blockchain::tps_throughput", _ns_tps_throughput, _acc_tps_throughput)
    var _acc_block_size_utilization: Float64 = 0.0
    var _t0_block_size_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_block_size_utilization += block_size_utilization(0.5, 0.5)
    var _t1_block_size_utilization = perf_counter_ns()
    var _ns_block_size_utilization = Float64(_t1_block_size_utilization - _t0_block_size_utilization) / Float64(N)
    print("MOJO_TIMING blockchain::block_size_utilization", _ns_block_size_utilization, _acc_block_size_utilization)
    var _acc_staking_apy: Float64 = 0.0
    var _t0_staking_apy = perf_counter_ns()
    for _ in range(N):
        _acc_staking_apy += staking_apy(0.5, 0.5)
    var _t1_staking_apy = perf_counter_ns()
    var _ns_staking_apy = Float64(_t1_staking_apy - _t0_staking_apy) / Float64(N)
    print("MOJO_TIMING blockchain::staking_apy", _ns_staking_apy, _acc_staking_apy)
    var _acc_validator_uptime: Float64 = 0.0
    var _t0_validator_uptime = perf_counter_ns()
    for _ in range(N):
        _acc_validator_uptime += validator_uptime(0.5, 0.5)
    var _t1_validator_uptime = perf_counter_ns()
    var _ns_validator_uptime = Float64(_t1_validator_uptime - _t0_validator_uptime) / Float64(N)
    print("MOJO_TIMING blockchain::validator_uptime", _ns_validator_uptime, _acc_validator_uptime)
    var _acc_finality_time_pbft: Float64 = 0.0
    var _t0_finality_time_pbft = perf_counter_ns()
    for _ in range(N):
        _acc_finality_time_pbft += finality_time_pbft(5, 0.5)
    var _t1_finality_time_pbft = perf_counter_ns()
    var _ns_finality_time_pbft = Float64(_t1_finality_time_pbft - _t0_finality_time_pbft) / Float64(N)
    print("MOJO_TIMING blockchain::finality_time_pbft", _ns_finality_time_pbft, _acc_finality_time_pbft)
    var _acc_token_inflation_rate: Float64 = 0.0
    var _t0_token_inflation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_token_inflation_rate += token_inflation_rate(0.5, 0.5)
    var _t1_token_inflation_rate = perf_counter_ns()
    var _ns_token_inflation_rate = Float64(_t1_token_inflation_rate - _t0_token_inflation_rate) / Float64(N)
    print("MOJO_TIMING blockchain::token_inflation_rate", _ns_token_inflation_rate, _acc_token_inflation_rate)
