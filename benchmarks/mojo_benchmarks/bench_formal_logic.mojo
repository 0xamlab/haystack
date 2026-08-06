"""bench_formal_logic.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from formal_logic import truth_and, truth_or, truth_not, truth_implies, truth_iff, truth_xor, truth_nand, truth_nor, modus_ponens, modus_tollens, hypothetical_syllogism, disjunctive_syllogism, is_tautology_2var, is_contradiction_2var
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

    var _acc_truth_and: Float64 = 0.0
    var _t0_truth_and = perf_counter_ns()
    for _ in range(N):
        _acc_truth_and += Float64(truth_and(True, True))
    var _t1_truth_and = perf_counter_ns()
    var _ns_truth_and = Float64(_t1_truth_and - _t0_truth_and) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_and", _ns_truth_and, _acc_truth_and)
    var _result_truth_and = truth_and(True, True)
    var _summary_truth_and = _summary_bool(_result_truth_and)
    print("MOJO_RESULT formal_logic::truth_and", _summary_truth_and)
    var _acc_truth_or: Float64 = 0.0
    var _t0_truth_or = perf_counter_ns()
    for _ in range(N):
        _acc_truth_or += Float64(truth_or(True, True))
    var _t1_truth_or = perf_counter_ns()
    var _ns_truth_or = Float64(_t1_truth_or - _t0_truth_or) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_or", _ns_truth_or, _acc_truth_or)
    var _result_truth_or = truth_or(True, True)
    var _summary_truth_or = _summary_bool(_result_truth_or)
    print("MOJO_RESULT formal_logic::truth_or", _summary_truth_or)
    var _acc_truth_not: Float64 = 0.0
    var _t0_truth_not = perf_counter_ns()
    for _ in range(N):
        _acc_truth_not += Float64(truth_not(True))
    var _t1_truth_not = perf_counter_ns()
    var _ns_truth_not = Float64(_t1_truth_not - _t0_truth_not) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_not", _ns_truth_not, _acc_truth_not)
    var _result_truth_not = truth_not(True)
    var _summary_truth_not = _summary_bool(_result_truth_not)
    print("MOJO_RESULT formal_logic::truth_not", _summary_truth_not)
    var _acc_truth_implies: Float64 = 0.0
    var _t0_truth_implies = perf_counter_ns()
    for _ in range(N):
        _acc_truth_implies += Float64(truth_implies(True, True))
    var _t1_truth_implies = perf_counter_ns()
    var _ns_truth_implies = Float64(_t1_truth_implies - _t0_truth_implies) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_implies", _ns_truth_implies, _acc_truth_implies)
    var _result_truth_implies = truth_implies(True, True)
    var _summary_truth_implies = _summary_bool(_result_truth_implies)
    print("MOJO_RESULT formal_logic::truth_implies", _summary_truth_implies)
    var _acc_truth_iff: Float64 = 0.0
    var _t0_truth_iff = perf_counter_ns()
    for _ in range(N):
        _acc_truth_iff += Float64(truth_iff(True, True))
    var _t1_truth_iff = perf_counter_ns()
    var _ns_truth_iff = Float64(_t1_truth_iff - _t0_truth_iff) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_iff", _ns_truth_iff, _acc_truth_iff)
    var _result_truth_iff = truth_iff(True, True)
    var _summary_truth_iff = _summary_bool(_result_truth_iff)
    print("MOJO_RESULT formal_logic::truth_iff", _summary_truth_iff)
    var _acc_truth_xor: Float64 = 0.0
    var _t0_truth_xor = perf_counter_ns()
    for _ in range(N):
        _acc_truth_xor += Float64(truth_xor(True, True))
    var _t1_truth_xor = perf_counter_ns()
    var _ns_truth_xor = Float64(_t1_truth_xor - _t0_truth_xor) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_xor", _ns_truth_xor, _acc_truth_xor)
    var _result_truth_xor = truth_xor(True, True)
    var _summary_truth_xor = _summary_bool(_result_truth_xor)
    print("MOJO_RESULT formal_logic::truth_xor", _summary_truth_xor)
    var _acc_truth_nand: Float64 = 0.0
    var _t0_truth_nand = perf_counter_ns()
    for _ in range(N):
        _acc_truth_nand += Float64(truth_nand(True, True))
    var _t1_truth_nand = perf_counter_ns()
    var _ns_truth_nand = Float64(_t1_truth_nand - _t0_truth_nand) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_nand", _ns_truth_nand, _acc_truth_nand)
    var _result_truth_nand = truth_nand(True, True)
    var _summary_truth_nand = _summary_bool(_result_truth_nand)
    print("MOJO_RESULT formal_logic::truth_nand", _summary_truth_nand)
    var _acc_truth_nor: Float64 = 0.0
    var _t0_truth_nor = perf_counter_ns()
    for _ in range(N):
        _acc_truth_nor += Float64(truth_nor(True, True))
    var _t1_truth_nor = perf_counter_ns()
    var _ns_truth_nor = Float64(_t1_truth_nor - _t0_truth_nor) / Float64(N)
    print("MOJO_TIMING formal_logic::truth_nor", _ns_truth_nor, _acc_truth_nor)
    var _result_truth_nor = truth_nor(True, True)
    var _summary_truth_nor = _summary_bool(_result_truth_nor)
    print("MOJO_RESULT formal_logic::truth_nor", _summary_truth_nor)
    var _acc_modus_ponens: Float64 = 0.0
    var _t0_modus_ponens = perf_counter_ns()
    for _ in range(N):
        _acc_modus_ponens += Float64(modus_ponens(True, True))
    var _t1_modus_ponens = perf_counter_ns()
    var _ns_modus_ponens = Float64(_t1_modus_ponens - _t0_modus_ponens) / Float64(N)
    print("MOJO_TIMING formal_logic::modus_ponens", _ns_modus_ponens, _acc_modus_ponens)
    var _result_modus_ponens = modus_ponens(True, True)
    var _summary_modus_ponens = _summary_bool(_result_modus_ponens)
    print("MOJO_RESULT formal_logic::modus_ponens", _summary_modus_ponens)
    var _acc_modus_tollens: Float64 = 0.0
    var _t0_modus_tollens = perf_counter_ns()
    for _ in range(N):
        _acc_modus_tollens += Float64(modus_tollens(True, True))
    var _t1_modus_tollens = perf_counter_ns()
    var _ns_modus_tollens = Float64(_t1_modus_tollens - _t0_modus_tollens) / Float64(N)
    print("MOJO_TIMING formal_logic::modus_tollens", _ns_modus_tollens, _acc_modus_tollens)
    var _result_modus_tollens = modus_tollens(True, True)
    var _summary_modus_tollens = _summary_bool(_result_modus_tollens)
    print("MOJO_RESULT formal_logic::modus_tollens", _summary_modus_tollens)
    var _acc_hypothetical_syllogism: Float64 = 0.0
    var _t0_hypothetical_syllogism = perf_counter_ns()
    for _ in range(N):
        _acc_hypothetical_syllogism += Float64(hypothetical_syllogism(True, True))
    var _t1_hypothetical_syllogism = perf_counter_ns()
    var _ns_hypothetical_syllogism = Float64(_t1_hypothetical_syllogism - _t0_hypothetical_syllogism) / Float64(N)
    print("MOJO_TIMING formal_logic::hypothetical_syllogism", _ns_hypothetical_syllogism, _acc_hypothetical_syllogism)
    var _result_hypothetical_syllogism = hypothetical_syllogism(True, True)
    var _summary_hypothetical_syllogism = _summary_bool(_result_hypothetical_syllogism)
    print("MOJO_RESULT formal_logic::hypothetical_syllogism", _summary_hypothetical_syllogism)
    var _acc_disjunctive_syllogism: Float64 = 0.0
    var _t0_disjunctive_syllogism = perf_counter_ns()
    for _ in range(N):
        _acc_disjunctive_syllogism += Float64(disjunctive_syllogism(True, True))
    var _t1_disjunctive_syllogism = perf_counter_ns()
    var _ns_disjunctive_syllogism = Float64(_t1_disjunctive_syllogism - _t0_disjunctive_syllogism) / Float64(N)
    print("MOJO_TIMING formal_logic::disjunctive_syllogism", _ns_disjunctive_syllogism, _acc_disjunctive_syllogism)
    var _result_disjunctive_syllogism = disjunctive_syllogism(True, True)
    var _summary_disjunctive_syllogism = _summary_bool(_result_disjunctive_syllogism)
    print("MOJO_RESULT formal_logic::disjunctive_syllogism", _summary_disjunctive_syllogism)
    var _acc_is_tautology_2var: Float64 = 0.0
    var _t0_is_tautology_2var = perf_counter_ns()
    for _ in range(N):
        _acc_is_tautology_2var += Float64(is_tautology_2var(5))
    var _t1_is_tautology_2var = perf_counter_ns()
    var _ns_is_tautology_2var = Float64(_t1_is_tautology_2var - _t0_is_tautology_2var) / Float64(N)
    print("MOJO_TIMING formal_logic::is_tautology_2var", _ns_is_tautology_2var, _acc_is_tautology_2var)
    var _result_is_tautology_2var = is_tautology_2var(5)
    var _summary_is_tautology_2var = _summary_bool(_result_is_tautology_2var)
    print("MOJO_RESULT formal_logic::is_tautology_2var", _summary_is_tautology_2var)
    var _acc_is_contradiction_2var: Float64 = 0.0
    var _t0_is_contradiction_2var = perf_counter_ns()
    for _ in range(N):
        _acc_is_contradiction_2var += Float64(is_contradiction_2var(5))
    var _t1_is_contradiction_2var = perf_counter_ns()
    var _ns_is_contradiction_2var = Float64(_t1_is_contradiction_2var - _t0_is_contradiction_2var) / Float64(N)
    print("MOJO_TIMING formal_logic::is_contradiction_2var", _ns_is_contradiction_2var, _acc_is_contradiction_2var)
    var _result_is_contradiction_2var = is_contradiction_2var(5)
    var _summary_is_contradiction_2var = _summary_bool(_result_is_contradiction_2var)
    print("MOJO_RESULT formal_logic::is_contradiction_2var", _summary_is_contradiction_2var)
