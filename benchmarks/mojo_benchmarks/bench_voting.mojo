"""bench_voting.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from voting import plurality_winner, borda_score, condorcet_pairwise, approval_score, majority_threshold, quota_droop, quota_hare, dhondt_divisor, sainte_lague_divisor, power_index_banzhaf, spoiler_effect
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

    var _acc_plurality_winner: Float64 = 0.0
    var _t0_plurality_winner = perf_counter_ns()
    for _ in range(N):
        _acc_plurality_winner += Float64(plurality_winner(_li5, 5))
    var _t1_plurality_winner = perf_counter_ns()
    var _ns_plurality_winner = Float64(_t1_plurality_winner - _t0_plurality_winner) / Float64(N)
    print("MOJO_TIMING voting::plurality_winner", _ns_plurality_winner, _acc_plurality_winner)
    var _acc_borda_score: Float64 = 0.0
    var _t0_borda_score = perf_counter_ns()
    for _ in range(N):
        _acc_borda_score += Float64(borda_score(_li5, 5, 5))
    var _t1_borda_score = perf_counter_ns()
    var _ns_borda_score = Float64(_t1_borda_score - _t0_borda_score) / Float64(N)
    print("MOJO_TIMING voting::borda_score", _ns_borda_score, _acc_borda_score)
    var _acc_condorcet_pairwise: Float64 = 0.0
    var _t0_condorcet_pairwise = perf_counter_ns()
    for _ in range(N):
        _acc_condorcet_pairwise += Float64(condorcet_pairwise(5, 5))
    var _t1_condorcet_pairwise = perf_counter_ns()
    var _ns_condorcet_pairwise = Float64(_t1_condorcet_pairwise - _t0_condorcet_pairwise) / Float64(N)
    print("MOJO_TIMING voting::condorcet_pairwise", _ns_condorcet_pairwise, _acc_condorcet_pairwise)
    var _acc_approval_score: Float64 = 0.0
    var _t0_approval_score = perf_counter_ns()
    for _ in range(N):
        _acc_approval_score += Float64(approval_score(_li5, 5))
    var _t1_approval_score = perf_counter_ns()
    var _ns_approval_score = Float64(_t1_approval_score - _t0_approval_score) / Float64(N)
    print("MOJO_TIMING voting::approval_score", _ns_approval_score, _acc_approval_score)
    var _acc_majority_threshold: Float64 = 0.0
    var _t0_majority_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_majority_threshold += Float64(majority_threshold(5))
    var _t1_majority_threshold = perf_counter_ns()
    var _ns_majority_threshold = Float64(_t1_majority_threshold - _t0_majority_threshold) / Float64(N)
    print("MOJO_TIMING voting::majority_threshold", _ns_majority_threshold, _acc_majority_threshold)
    var _acc_quota_droop: Float64 = 0.0
    var _t0_quota_droop = perf_counter_ns()
    for _ in range(N):
        _acc_quota_droop += Float64(quota_droop(5, 5))
    var _t1_quota_droop = perf_counter_ns()
    var _ns_quota_droop = Float64(_t1_quota_droop - _t0_quota_droop) / Float64(N)
    print("MOJO_TIMING voting::quota_droop", _ns_quota_droop, _acc_quota_droop)
    var _acc_quota_hare: Float64 = 0.0
    var _t0_quota_hare = perf_counter_ns()
    for _ in range(N):
        _acc_quota_hare += quota_hare(5, 5)
    var _t1_quota_hare = perf_counter_ns()
    var _ns_quota_hare = Float64(_t1_quota_hare - _t0_quota_hare) / Float64(N)
    print("MOJO_TIMING voting::quota_hare", _ns_quota_hare, _acc_quota_hare)
    var _acc_dhondt_divisor: Float64 = 0.0
    var _t0_dhondt_divisor = perf_counter_ns()
    for _ in range(N):
        _acc_dhondt_divisor += Float64(dhondt_divisor(5))
    var _t1_dhondt_divisor = perf_counter_ns()
    var _ns_dhondt_divisor = Float64(_t1_dhondt_divisor - _t0_dhondt_divisor) / Float64(N)
    print("MOJO_TIMING voting::dhondt_divisor", _ns_dhondt_divisor, _acc_dhondt_divisor)
    var _acc_sainte_lague_divisor: Float64 = 0.0
    var _t0_sainte_lague_divisor = perf_counter_ns()
    for _ in range(N):
        _acc_sainte_lague_divisor += Float64(sainte_lague_divisor(5))
    var _t1_sainte_lague_divisor = perf_counter_ns()
    var _ns_sainte_lague_divisor = Float64(_t1_sainte_lague_divisor - _t0_sainte_lague_divisor) / Float64(N)
    print("MOJO_TIMING voting::sainte_lague_divisor", _ns_sainte_lague_divisor, _acc_sainte_lague_divisor)
    var _acc_power_index_banzhaf: Float64 = 0.0
    var _t0_power_index_banzhaf = perf_counter_ns()
    for _ in range(N):
        _acc_power_index_banzhaf += power_index_banzhaf(5, 5, 5)
    var _t1_power_index_banzhaf = perf_counter_ns()
    var _ns_power_index_banzhaf = Float64(_t1_power_index_banzhaf - _t0_power_index_banzhaf) / Float64(N)
    print("MOJO_TIMING voting::power_index_banzhaf", _ns_power_index_banzhaf, _acc_power_index_banzhaf)
    var _acc_spoiler_effect: Float64 = 0.0
    var _t0_spoiler_effect = perf_counter_ns()
    for _ in range(N):
        _acc_spoiler_effect += Float64(spoiler_effect(5, 5))
    var _t1_spoiler_effect = perf_counter_ns()
    var _ns_spoiler_effect = Float64(_t1_spoiler_effect - _t0_spoiler_effect) / Float64(N)
    print("MOJO_TIMING voting::spoiler_effect", _ns_spoiler_effect, _acc_spoiler_effect)
