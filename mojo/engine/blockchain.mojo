"""
blockchain.mojo — Blockchain / DLT Metrics Library. Zero Python imports.

Provides functions for computing blockchain and distributed ledger metrics
including block rewards, hash rate, transaction fees, gas costs, confirmation
security, Merkle tree depth, TPS, staking APY, and token inflation.

Public API:
  block_reward_halving      — R = initial / 2^halvings
  hash_rate_to_difficulty   — D ≈ hashrate * time / 2^32
  transaction_fee_priority  — Total = base + tip
  gas_cost                  — Cost = used * price / 1e9 (ETH)
  confirmations_security    — P_attack ≈ (pct/100)^confirmations
  merkle_tree_depth         — Depth = ceil(log2(n))
  tps_throughput            — TPS = tx/time
  block_size_utilization    — U = used/max * 100
  staking_apy               — APY = rewards/staked * 100
  validator_uptime          — Uptime = online/total * 100
  finality_time_pbft        — Time ≈ 3 * round_time
  token_inflation_rate      — IR = new/total * 100
"""

from std.math import log as _log, pow as _pow


# ── helpers ──────────────────────────────────────────────────────────────────


def _log2(x: Float64) -> Float64:
    """Log base 2."""
    if x <= 0.0:
        return 0.0
    return _log(x) / _log(2.0)


def _ceil_int(x: Float64) -> Int:
    """Ceiling of a float returned as Int."""
    var i = Int(x)
    if Float64(i) < x:
        return i + 1
    return i


# ── public API ───────────────────────────────────────────────────────────────


def block_reward_halving(initial_reward: Float64, halvings: Int) -> Float64:
    """Block reward after halvings = initial_reward / 2^halvings."""
    if halvings < 0:
        return initial_reward
    return initial_reward / _pow(2.0, Float64(halvings))


def hash_rate_to_difficulty(hash_rate: Float64, block_time_sec: Float64) -> Float64:
    """Approximate mining difficulty ≈ hash_rate * block_time / 2^32."""
    return hash_rate * block_time_sec / _pow(2.0, 32.0)


def transaction_fee_priority(base_fee: Float64, tip: Float64) -> Float64:
    """Total transaction fee = base_fee + tip."""
    return base_fee + tip


def gas_cost(gas_used: Float64, gas_price_gwei: Float64) -> Float64:
    """Gas cost in ETH = gas_used * gas_price_gwei / 1e9."""
    return gas_used * gas_price_gwei / 1e9


def confirmations_security(confirmations: Int, attack_hashrate_pct: Float64) -> Float64:
    """Probability of successful attack ≈ (pct/100)^confirmations."""
    if confirmations <= 0:
        return 1.0
    return _pow(attack_hashrate_pct / 100.0, Float64(confirmations))


def merkle_tree_depth(n_transactions: Int) -> Int:
    """Merkle tree depth = ceil(log2(n)). Returns 0 for n <= 1."""
    if n_transactions <= 1:
        return 0
    return _ceil_int(_log2(Float64(n_transactions)))


def tps_throughput(transactions: Int, time_seconds: Float64) -> Float64:
    """Transactions per second = transactions / time_seconds."""
    if time_seconds == 0.0:
        return 0.0
    return Float64(transactions) / time_seconds


def block_size_utilization(used_bytes: Float64, max_bytes: Float64) -> Float64:
    """Block size utilization (%) = used_bytes / max_bytes * 100."""
    if max_bytes == 0.0:
        return 0.0
    return used_bytes / max_bytes * 100.0


def staking_apy(rewards_per_year: Float64, staked_amount: Float64) -> Float64:
    """Staking APY (%) = rewards_per_year / staked_amount * 100."""
    if staked_amount == 0.0:
        return 0.0
    return rewards_per_year / staked_amount * 100.0


def validator_uptime(online_slots: Float64, total_slots: Float64) -> Float64:
    """Validator uptime (%) = online_slots / total_slots * 100."""
    if total_slots == 0.0:
        return 0.0
    return online_slots / total_slots * 100.0


def finality_time_pbft(n_validators: Int, round_time: Float64) -> Float64:
    """PBFT finality time ≈ 3 * round_time (simplified)."""
    return 3.0 * round_time


def token_inflation_rate(new_supply: Float64, total_supply: Float64) -> Float64:
    """Token inflation rate (%) = new_supply / total_supply * 100."""
    if total_supply == 0.0:
        return 0.0
    return new_supply / total_supply * 100.0
