"""bench_election.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from election import pairwise_matrix, plurality, borda_count, borda_winner, condorcet_winner, instant_runoff, approval_voting, copeland_scores
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

    var _acc_pairwise_matrix: Float64 = 0.0
    var _t0_pairwise_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_pairwise_matrix = pairwise_matrix([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_pairwise_matrix += Float64(len(_r_pairwise_matrix))
    var _t1_pairwise_matrix = perf_counter_ns()
    var _ns_pairwise_matrix = Float64(_t1_pairwise_matrix - _t0_pairwise_matrix) / Float64(N)
    print("MOJO_TIMING election::pairwise_matrix", _ns_pairwise_matrix, _acc_pairwise_matrix)
    var _acc_plurality: Float64 = 0.0
    var _t0_plurality = perf_counter_ns()
    for _ in range(N):
        _acc_plurality += Float64(plurality([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_plurality = perf_counter_ns()
    var _ns_plurality = Float64(_t1_plurality - _t0_plurality) / Float64(N)
    print("MOJO_TIMING election::plurality", _ns_plurality, _acc_plurality)
    var _acc_borda_count: Float64 = 0.0
    var _t0_borda_count = perf_counter_ns()
    for _ in range(N):
        var _r_borda_count = borda_count([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_borda_count += Float64(len(_r_borda_count))
    var _t1_borda_count = perf_counter_ns()
    var _ns_borda_count = Float64(_t1_borda_count - _t0_borda_count) / Float64(N)
    print("MOJO_TIMING election::borda_count", _ns_borda_count, _acc_borda_count)
    var _acc_borda_winner: Float64 = 0.0
    var _t0_borda_winner = perf_counter_ns()
    for _ in range(N):
        _acc_borda_winner += Float64(borda_winner([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_borda_winner = perf_counter_ns()
    var _ns_borda_winner = Float64(_t1_borda_winner - _t0_borda_winner) / Float64(N)
    print("MOJO_TIMING election::borda_winner", _ns_borda_winner, _acc_borda_winner)
    var _acc_condorcet_winner: Float64 = 0.0
    var _t0_condorcet_winner = perf_counter_ns()
    for _ in range(N):
        _acc_condorcet_winner += Float64(condorcet_winner([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_condorcet_winner = perf_counter_ns()
    var _ns_condorcet_winner = Float64(_t1_condorcet_winner - _t0_condorcet_winner) / Float64(N)
    print("MOJO_TIMING election::condorcet_winner", _ns_condorcet_winner, _acc_condorcet_winner)
    var _acc_instant_runoff: Float64 = 0.0
    var _t0_instant_runoff = perf_counter_ns()
    for _ in range(N):
        _acc_instant_runoff += Float64(instant_runoff([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_instant_runoff = perf_counter_ns()
    var _ns_instant_runoff = Float64(_t1_instant_runoff - _t0_instant_runoff) / Float64(N)
    print("MOJO_TIMING election::instant_runoff", _ns_instant_runoff, _acc_instant_runoff)
    var _acc_approval_voting: Float64 = 0.0
    var _t0_approval_voting = perf_counter_ns()
    for _ in range(N):
        _acc_approval_voting += Float64(approval_voting([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_approval_voting = perf_counter_ns()
    var _ns_approval_voting = Float64(_t1_approval_voting - _t0_approval_voting) / Float64(N)
    print("MOJO_TIMING election::approval_voting", _ns_approval_voting, _acc_approval_voting)
    var _acc_copeland_scores: Float64 = 0.0
    var _t0_copeland_scores = perf_counter_ns()
    for _ in range(N):
        var _r_copeland_scores = copeland_scores([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_copeland_scores += Float64(len(_r_copeland_scores))
    var _t1_copeland_scores = perf_counter_ns()
    var _ns_copeland_scores = Float64(_t1_copeland_scores - _t0_copeland_scores) / Float64(N)
    print("MOJO_TIMING election::copeland_scores", _ns_copeland_scores, _acc_copeland_scores)
