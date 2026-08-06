"""bench_election.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from election import pairwise_matrix, plurality, borda_count, borda_winner, condorcet_winner, instant_runoff, approval_voting, copeland_scores
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

    var _acc_pairwise_matrix: Float64 = 0.0
    var _t0_pairwise_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_pairwise_matrix = pairwise_matrix([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_pairwise_matrix += Float64(len(_r_pairwise_matrix))
    var _t1_pairwise_matrix = perf_counter_ns()
    var _ns_pairwise_matrix = Float64(_t1_pairwise_matrix - _t0_pairwise_matrix) / Float64(N)
    print("MOJO_TIMING election::pairwise_matrix", _ns_pairwise_matrix, _acc_pairwise_matrix)
    var _result_pairwise_matrix = pairwise_matrix([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_pairwise_matrix = _summary_list_list_int(_result_pairwise_matrix)
    print("MOJO_RESULT election::pairwise_matrix", _summary_pairwise_matrix)
    var _acc_plurality: Float64 = 0.0
    var _t0_plurality = perf_counter_ns()
    for _ in range(N):
        _acc_plurality += Float64(plurality([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_plurality = perf_counter_ns()
    var _ns_plurality = Float64(_t1_plurality - _t0_plurality) / Float64(N)
    print("MOJO_TIMING election::plurality", _ns_plurality, _acc_plurality)
    var _result_plurality = plurality([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_plurality = _summary_int(_result_plurality)
    print("MOJO_RESULT election::plurality", _summary_plurality)
    var _acc_borda_count: Float64 = 0.0
    var _t0_borda_count = perf_counter_ns()
    for _ in range(N):
        var _r_borda_count = borda_count([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_borda_count += Float64(len(_r_borda_count))
    var _t1_borda_count = perf_counter_ns()
    var _ns_borda_count = Float64(_t1_borda_count - _t0_borda_count) / Float64(N)
    print("MOJO_TIMING election::borda_count", _ns_borda_count, _acc_borda_count)
    var _result_borda_count = borda_count([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_borda_count = _summary_list_float64(_result_borda_count)
    print("MOJO_RESULT election::borda_count", _summary_borda_count)
    var _acc_borda_winner: Float64 = 0.0
    var _t0_borda_winner = perf_counter_ns()
    for _ in range(N):
        _acc_borda_winner += Float64(borda_winner([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_borda_winner = perf_counter_ns()
    var _ns_borda_winner = Float64(_t1_borda_winner - _t0_borda_winner) / Float64(N)
    print("MOJO_TIMING election::borda_winner", _ns_borda_winner, _acc_borda_winner)
    var _result_borda_winner = borda_winner([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_borda_winner = _summary_int(_result_borda_winner)
    print("MOJO_RESULT election::borda_winner", _summary_borda_winner)
    var _acc_condorcet_winner: Float64 = 0.0
    var _t0_condorcet_winner = perf_counter_ns()
    for _ in range(N):
        _acc_condorcet_winner += Float64(condorcet_winner([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_condorcet_winner = perf_counter_ns()
    var _ns_condorcet_winner = Float64(_t1_condorcet_winner - _t0_condorcet_winner) / Float64(N)
    print("MOJO_TIMING election::condorcet_winner", _ns_condorcet_winner, _acc_condorcet_winner)
    var _result_condorcet_winner = condorcet_winner([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_condorcet_winner = _summary_int(_result_condorcet_winner)
    print("MOJO_RESULT election::condorcet_winner", _summary_condorcet_winner)
    var _acc_instant_runoff: Float64 = 0.0
    var _t0_instant_runoff = perf_counter_ns()
    for _ in range(N):
        _acc_instant_runoff += Float64(instant_runoff([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_instant_runoff = perf_counter_ns()
    var _ns_instant_runoff = Float64(_t1_instant_runoff - _t0_instant_runoff) / Float64(N)
    print("MOJO_TIMING election::instant_runoff", _ns_instant_runoff, _acc_instant_runoff)
    var _result_instant_runoff = instant_runoff([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_instant_runoff = _summary_int(_result_instant_runoff)
    print("MOJO_RESULT election::instant_runoff", _summary_instant_runoff)
    var _acc_approval_voting: Float64 = 0.0
    var _t0_approval_voting = perf_counter_ns()
    for _ in range(N):
        _acc_approval_voting += Float64(approval_voting([[0,1,1],[1,0,1],[1,1,0]], 5))
    var _t1_approval_voting = perf_counter_ns()
    var _ns_approval_voting = Float64(_t1_approval_voting - _t0_approval_voting) / Float64(N)
    print("MOJO_TIMING election::approval_voting", _ns_approval_voting, _acc_approval_voting)
    var _result_approval_voting = approval_voting([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_approval_voting = _summary_int(_result_approval_voting)
    print("MOJO_RESULT election::approval_voting", _summary_approval_voting)
    var _acc_copeland_scores: Float64 = 0.0
    var _t0_copeland_scores = perf_counter_ns()
    for _ in range(N):
        var _r_copeland_scores = copeland_scores([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_copeland_scores += Float64(len(_r_copeland_scores))
    var _t1_copeland_scores = perf_counter_ns()
    var _ns_copeland_scores = Float64(_t1_copeland_scores - _t0_copeland_scores) / Float64(N)
    print("MOJO_TIMING election::copeland_scores", _ns_copeland_scores, _acc_copeland_scores)
    var _result_copeland_scores = copeland_scores([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_copeland_scores = _summary_list_float64(_result_copeland_scores)
    print("MOJO_RESULT election::copeland_scores", _summary_copeland_scores)
