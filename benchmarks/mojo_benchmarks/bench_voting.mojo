"""bench_voting.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from voting import plurality_winner, borda_score, condorcet_pairwise, approval_score, majority_threshold, quota_droop, quota_hare, dhondt_divisor, sainte_lague_divisor, power_index_banzhaf, spoiler_effect
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

    var _acc_plurality_winner: Float64 = 0.0
    var _t0_plurality_winner = perf_counter_ns()
    for _ in range(N):
        _acc_plurality_winner += Float64(plurality_winner(_li5, 5))
    var _t1_plurality_winner = perf_counter_ns()
    var _ns_plurality_winner = Float64(_t1_plurality_winner - _t0_plurality_winner) / Float64(N)
    print("MOJO_TIMING voting::plurality_winner", _ns_plurality_winner, _acc_plurality_winner)
    var _result_plurality_winner = plurality_winner(_li5, 5)
    var _summary_plurality_winner = _summary_int(_result_plurality_winner)
    print("MOJO_RESULT voting::plurality_winner", _summary_plurality_winner)
    var _acc_borda_score: Float64 = 0.0
    var _t0_borda_score = perf_counter_ns()
    for _ in range(N):
        _acc_borda_score += Float64(borda_score(_li5, 5, 5))
    var _t1_borda_score = perf_counter_ns()
    var _ns_borda_score = Float64(_t1_borda_score - _t0_borda_score) / Float64(N)
    print("MOJO_TIMING voting::borda_score", _ns_borda_score, _acc_borda_score)
    var _result_borda_score = borda_score(_li5, 5, 5)
    var _summary_borda_score = _summary_int(_result_borda_score)
    print("MOJO_RESULT voting::borda_score", _summary_borda_score)
    var _acc_condorcet_pairwise: Float64 = 0.0
    var _t0_condorcet_pairwise = perf_counter_ns()
    for _ in range(N):
        _acc_condorcet_pairwise += Float64(condorcet_pairwise(5, 5))
    var _t1_condorcet_pairwise = perf_counter_ns()
    var _ns_condorcet_pairwise = Float64(_t1_condorcet_pairwise - _t0_condorcet_pairwise) / Float64(N)
    print("MOJO_TIMING voting::condorcet_pairwise", _ns_condorcet_pairwise, _acc_condorcet_pairwise)
    var _result_condorcet_pairwise = condorcet_pairwise(5, 5)
    var _summary_condorcet_pairwise = _summary_int(_result_condorcet_pairwise)
    print("MOJO_RESULT voting::condorcet_pairwise", _summary_condorcet_pairwise)
    var _acc_approval_score: Float64 = 0.0
    var _t0_approval_score = perf_counter_ns()
    for _ in range(N):
        _acc_approval_score += Float64(approval_score(_li5, 5))
    var _t1_approval_score = perf_counter_ns()
    var _ns_approval_score = Float64(_t1_approval_score - _t0_approval_score) / Float64(N)
    print("MOJO_TIMING voting::approval_score", _ns_approval_score, _acc_approval_score)
    var _result_approval_score = approval_score(_li5, 5)
    var _summary_approval_score = _summary_int(_result_approval_score)
    print("MOJO_RESULT voting::approval_score", _summary_approval_score)
    var _acc_majority_threshold: Float64 = 0.0
    var _t0_majority_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_majority_threshold += Float64(majority_threshold(5))
    var _t1_majority_threshold = perf_counter_ns()
    var _ns_majority_threshold = Float64(_t1_majority_threshold - _t0_majority_threshold) / Float64(N)
    print("MOJO_TIMING voting::majority_threshold", _ns_majority_threshold, _acc_majority_threshold)
    var _result_majority_threshold = majority_threshold(5)
    var _summary_majority_threshold = _summary_int(_result_majority_threshold)
    print("MOJO_RESULT voting::majority_threshold", _summary_majority_threshold)
    var _acc_quota_droop: Float64 = 0.0
    var _t0_quota_droop = perf_counter_ns()
    for _ in range(N):
        _acc_quota_droop += Float64(quota_droop(5, 5))
    var _t1_quota_droop = perf_counter_ns()
    var _ns_quota_droop = Float64(_t1_quota_droop - _t0_quota_droop) / Float64(N)
    print("MOJO_TIMING voting::quota_droop", _ns_quota_droop, _acc_quota_droop)
    var _result_quota_droop = quota_droop(5, 5)
    var _summary_quota_droop = _summary_int(_result_quota_droop)
    print("MOJO_RESULT voting::quota_droop", _summary_quota_droop)
    var _acc_quota_hare: Float64 = 0.0
    var _t0_quota_hare = perf_counter_ns()
    for _ in range(N):
        _acc_quota_hare += quota_hare(5, 5)
    var _t1_quota_hare = perf_counter_ns()
    var _ns_quota_hare = Float64(_t1_quota_hare - _t0_quota_hare) / Float64(N)
    print("MOJO_TIMING voting::quota_hare", _ns_quota_hare, _acc_quota_hare)
    var _result_quota_hare = quota_hare(5, 5)
    var _summary_quota_hare = _summary_float64(_result_quota_hare)
    print("MOJO_RESULT voting::quota_hare", _summary_quota_hare)
    var _acc_dhondt_divisor: Float64 = 0.0
    var _t0_dhondt_divisor = perf_counter_ns()
    for _ in range(N):
        _acc_dhondt_divisor += Float64(dhondt_divisor(5))
    var _t1_dhondt_divisor = perf_counter_ns()
    var _ns_dhondt_divisor = Float64(_t1_dhondt_divisor - _t0_dhondt_divisor) / Float64(N)
    print("MOJO_TIMING voting::dhondt_divisor", _ns_dhondt_divisor, _acc_dhondt_divisor)
    var _result_dhondt_divisor = dhondt_divisor(5)
    var _summary_dhondt_divisor = _summary_int(_result_dhondt_divisor)
    print("MOJO_RESULT voting::dhondt_divisor", _summary_dhondt_divisor)
    var _acc_sainte_lague_divisor: Float64 = 0.0
    var _t0_sainte_lague_divisor = perf_counter_ns()
    for _ in range(N):
        _acc_sainte_lague_divisor += Float64(sainte_lague_divisor(5))
    var _t1_sainte_lague_divisor = perf_counter_ns()
    var _ns_sainte_lague_divisor = Float64(_t1_sainte_lague_divisor - _t0_sainte_lague_divisor) / Float64(N)
    print("MOJO_TIMING voting::sainte_lague_divisor", _ns_sainte_lague_divisor, _acc_sainte_lague_divisor)
    var _result_sainte_lague_divisor = sainte_lague_divisor(5)
    var _summary_sainte_lague_divisor = _summary_int(_result_sainte_lague_divisor)
    print("MOJO_RESULT voting::sainte_lague_divisor", _summary_sainte_lague_divisor)
    var _acc_power_index_banzhaf: Float64 = 0.0
    var _t0_power_index_banzhaf = perf_counter_ns()
    for _ in range(N):
        _acc_power_index_banzhaf += power_index_banzhaf(5, 5, 5)
    var _t1_power_index_banzhaf = perf_counter_ns()
    var _ns_power_index_banzhaf = Float64(_t1_power_index_banzhaf - _t0_power_index_banzhaf) / Float64(N)
    print("MOJO_TIMING voting::power_index_banzhaf", _ns_power_index_banzhaf, _acc_power_index_banzhaf)
    var _result_power_index_banzhaf = power_index_banzhaf(5, 5, 5)
    var _summary_power_index_banzhaf = _summary_float64(_result_power_index_banzhaf)
    print("MOJO_RESULT voting::power_index_banzhaf", _summary_power_index_banzhaf)
    var _acc_spoiler_effect: Float64 = 0.0
    var _t0_spoiler_effect = perf_counter_ns()
    for _ in range(N):
        _acc_spoiler_effect += Float64(spoiler_effect(5, 5))
    var _t1_spoiler_effect = perf_counter_ns()
    var _ns_spoiler_effect = Float64(_t1_spoiler_effect - _t0_spoiler_effect) / Float64(N)
    print("MOJO_TIMING voting::spoiler_effect", _ns_spoiler_effect, _acc_spoiler_effect)
    var _result_spoiler_effect = spoiler_effect(5, 5)
    var _summary_spoiler_effect = _summary_bool(_result_spoiler_effect)
    print("MOJO_RESULT voting::spoiler_effect", _summary_spoiler_effect)
