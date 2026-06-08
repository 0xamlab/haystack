"""bench_multi_objective.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from multi_objective import is_dominated, pareto_front, weighted_score, normalize_objectives, ideal_point, nadir_point, topsis_rank
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

    var _acc_is_dominated: Float64 = 0.0
    var _t0_is_dominated = perf_counter_ns()
    for _ in range(N):
        _acc_is_dominated += Float64(is_dominated(_lf5, _lf5, _lb5))
    var _t1_is_dominated = perf_counter_ns()
    var _ns_is_dominated = Float64(_t1_is_dominated - _t0_is_dominated) / Float64(N)
    print("MOJO_TIMING multi_objective::is_dominated", _ns_is_dominated, _acc_is_dominated)
    var _result_is_dominated = is_dominated(_lf5, _lf5, _lb5)
    var _summary_is_dominated = _summary_bool(_result_is_dominated)
    print("MOJO_RESULT multi_objective::is_dominated", _summary_is_dominated)
    var _acc_pareto_front: Float64 = 0.0
    var _t0_pareto_front = perf_counter_ns()
    for _ in range(N):
        var _r_pareto_front = pareto_front([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
        _acc_pareto_front += Float64(len(_r_pareto_front))
    var _t1_pareto_front = perf_counter_ns()
    var _ns_pareto_front = Float64(_t1_pareto_front - _t0_pareto_front) / Float64(N)
    print("MOJO_TIMING multi_objective::pareto_front", _ns_pareto_front, _acc_pareto_front)
    var _result_pareto_front = pareto_front([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
    var _summary_pareto_front = _summary_list_int(_result_pareto_front)
    print("MOJO_RESULT multi_objective::pareto_front", _summary_pareto_front)
    var _acc_weighted_score: Float64 = 0.0
    var _t0_weighted_score = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_score += weighted_score(_lf5, _lf5)
    var _t1_weighted_score = perf_counter_ns()
    var _ns_weighted_score = Float64(_t1_weighted_score - _t0_weighted_score) / Float64(N)
    print("MOJO_TIMING multi_objective::weighted_score", _ns_weighted_score, _acc_weighted_score)
    var _result_weighted_score = weighted_score(_lf5, _lf5)
    var _summary_weighted_score = _summary_float64(_result_weighted_score)
    print("MOJO_RESULT multi_objective::weighted_score", _summary_weighted_score)
    var _acc_normalize_objectives: Float64 = 0.0
    var _t0_normalize_objectives = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_objectives = normalize_objectives([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_normalize_objectives += Float64(len(_r_normalize_objectives))
    var _t1_normalize_objectives = perf_counter_ns()
    var _ns_normalize_objectives = Float64(_t1_normalize_objectives - _t0_normalize_objectives) / Float64(N)
    print("MOJO_TIMING multi_objective::normalize_objectives", _ns_normalize_objectives, _acc_normalize_objectives)
    var _result_normalize_objectives = normalize_objectives([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_normalize_objectives = _summary_list_list_float64(_result_normalize_objectives)
    print("MOJO_RESULT multi_objective::normalize_objectives", _summary_normalize_objectives)
    var _acc_ideal_point: Float64 = 0.0
    var _t0_ideal_point = perf_counter_ns()
    for _ in range(N):
        var _r_ideal_point = ideal_point([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
        _acc_ideal_point += Float64(len(_r_ideal_point))
    var _t1_ideal_point = perf_counter_ns()
    var _ns_ideal_point = Float64(_t1_ideal_point - _t0_ideal_point) / Float64(N)
    print("MOJO_TIMING multi_objective::ideal_point", _ns_ideal_point, _acc_ideal_point)
    var _result_ideal_point = ideal_point([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
    var _summary_ideal_point = _summary_list_float64(_result_ideal_point)
    print("MOJO_RESULT multi_objective::ideal_point", _summary_ideal_point)
    var _acc_nadir_point: Float64 = 0.0
    var _t0_nadir_point = perf_counter_ns()
    for _ in range(N):
        var _r_nadir_point = nadir_point([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
        _acc_nadir_point += Float64(len(_r_nadir_point))
    var _t1_nadir_point = perf_counter_ns()
    var _ns_nadir_point = Float64(_t1_nadir_point - _t0_nadir_point) / Float64(N)
    print("MOJO_TIMING multi_objective::nadir_point", _ns_nadir_point, _acc_nadir_point)
    var _result_nadir_point = nadir_point([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lb5)
    var _summary_nadir_point = _summary_list_float64(_result_nadir_point)
    print("MOJO_RESULT multi_objective::nadir_point", _summary_nadir_point)
    var _acc_topsis_rank: Float64 = 0.0
    var _t0_topsis_rank = perf_counter_ns()
    for _ in range(N):
        var _r_topsis_rank = topsis_rank([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lb5)
        _acc_topsis_rank += Float64(len(_r_topsis_rank))
    var _t1_topsis_rank = perf_counter_ns()
    var _ns_topsis_rank = Float64(_t1_topsis_rank - _t0_topsis_rank) / Float64(N)
    print("MOJO_TIMING multi_objective::topsis_rank", _ns_topsis_rank, _acc_topsis_rank)
    var _result_topsis_rank = topsis_rank([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lb5)
    var _summary_topsis_rank = _summary_list_float64(_result_topsis_rank)
    print("MOJO_RESULT multi_objective::topsis_rank", _summary_topsis_rank)
