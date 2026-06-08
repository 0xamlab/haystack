"""bench_compiler_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compiler_theory import is_terminal, is_nonterminal, first_follow_conflict, lr_shift_reduce_conflict, reduce_reduce_conflict, grammar_is_ambiguous, ast_depth, ast_node_count, register_pressure, instruction_latency_sum, basic_block_throughput, loop_unroll_benefit
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

    var _acc_is_terminal: Float64 = 0.0
    var _t0_is_terminal = perf_counter_ns()
    for _ in range(N):
        _acc_is_terminal += Float64(is_terminal(5))
    var _t1_is_terminal = perf_counter_ns()
    var _ns_is_terminal = Float64(_t1_is_terminal - _t0_is_terminal) / Float64(N)
    print("MOJO_TIMING compiler_theory::is_terminal", _ns_is_terminal, _acc_is_terminal)
    var _result_is_terminal = is_terminal(5)
    var _summary_is_terminal = _summary_bool(_result_is_terminal)
    print("MOJO_RESULT compiler_theory::is_terminal", _summary_is_terminal)
    var _acc_is_nonterminal: Float64 = 0.0
    var _t0_is_nonterminal = perf_counter_ns()
    for _ in range(N):
        _acc_is_nonterminal += Float64(is_nonterminal(5))
    var _t1_is_nonterminal = perf_counter_ns()
    var _ns_is_nonterminal = Float64(_t1_is_nonterminal - _t0_is_nonterminal) / Float64(N)
    print("MOJO_TIMING compiler_theory::is_nonterminal", _ns_is_nonterminal, _acc_is_nonterminal)
    var _result_is_nonterminal = is_nonterminal(5)
    var _summary_is_nonterminal = _summary_bool(_result_is_nonterminal)
    print("MOJO_RESULT compiler_theory::is_nonterminal", _summary_is_nonterminal)
    var _acc_first_follow_conflict: Float64 = 0.0
    var _t0_first_follow_conflict = perf_counter_ns()
    for _ in range(N):
        _acc_first_follow_conflict += Float64(first_follow_conflict(True, True))
    var _t1_first_follow_conflict = perf_counter_ns()
    var _ns_first_follow_conflict = Float64(_t1_first_follow_conflict - _t0_first_follow_conflict) / Float64(N)
    print("MOJO_TIMING compiler_theory::first_follow_conflict", _ns_first_follow_conflict, _acc_first_follow_conflict)
    var _result_first_follow_conflict = first_follow_conflict(True, True)
    var _summary_first_follow_conflict = _summary_bool(_result_first_follow_conflict)
    print("MOJO_RESULT compiler_theory::first_follow_conflict", _summary_first_follow_conflict)
    var _acc_lr_shift_reduce_conflict: Float64 = 0.0
    var _t0_lr_shift_reduce_conflict = perf_counter_ns()
    for _ in range(N):
        _acc_lr_shift_reduce_conflict += Float64(lr_shift_reduce_conflict(True, True))
    var _t1_lr_shift_reduce_conflict = perf_counter_ns()
    var _ns_lr_shift_reduce_conflict = Float64(_t1_lr_shift_reduce_conflict - _t0_lr_shift_reduce_conflict) / Float64(N)
    print("MOJO_TIMING compiler_theory::lr_shift_reduce_conflict", _ns_lr_shift_reduce_conflict, _acc_lr_shift_reduce_conflict)
    var _result_lr_shift_reduce_conflict = lr_shift_reduce_conflict(True, True)
    var _summary_lr_shift_reduce_conflict = _summary_bool(_result_lr_shift_reduce_conflict)
    print("MOJO_RESULT compiler_theory::lr_shift_reduce_conflict", _summary_lr_shift_reduce_conflict)
    var _acc_reduce_reduce_conflict: Float64 = 0.0
    var _t0_reduce_reduce_conflict = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_reduce_conflict += Float64(reduce_reduce_conflict(True, True))
    var _t1_reduce_reduce_conflict = perf_counter_ns()
    var _ns_reduce_reduce_conflict = Float64(_t1_reduce_reduce_conflict - _t0_reduce_reduce_conflict) / Float64(N)
    print("MOJO_TIMING compiler_theory::reduce_reduce_conflict", _ns_reduce_reduce_conflict, _acc_reduce_reduce_conflict)
    var _result_reduce_reduce_conflict = reduce_reduce_conflict(True, True)
    var _summary_reduce_reduce_conflict = _summary_bool(_result_reduce_reduce_conflict)
    print("MOJO_RESULT compiler_theory::reduce_reduce_conflict", _summary_reduce_reduce_conflict)
    var _acc_grammar_is_ambiguous: Float64 = 0.0
    var _t0_grammar_is_ambiguous = perf_counter_ns()
    for _ in range(N):
        _acc_grammar_is_ambiguous += Float64(grammar_is_ambiguous(True, True))
    var _t1_grammar_is_ambiguous = perf_counter_ns()
    var _ns_grammar_is_ambiguous = Float64(_t1_grammar_is_ambiguous - _t0_grammar_is_ambiguous) / Float64(N)
    print("MOJO_TIMING compiler_theory::grammar_is_ambiguous", _ns_grammar_is_ambiguous, _acc_grammar_is_ambiguous)
    var _result_grammar_is_ambiguous = grammar_is_ambiguous(True, True)
    var _summary_grammar_is_ambiguous = _summary_bool(_result_grammar_is_ambiguous)
    print("MOJO_RESULT compiler_theory::grammar_is_ambiguous", _summary_grammar_is_ambiguous)
    var _acc_ast_depth: Float64 = 0.0
    var _t0_ast_depth = perf_counter_ns()
    for _ in range(N):
        _acc_ast_depth += Float64(ast_depth(5, 5))
    var _t1_ast_depth = perf_counter_ns()
    var _ns_ast_depth = Float64(_t1_ast_depth - _t0_ast_depth) / Float64(N)
    print("MOJO_TIMING compiler_theory::ast_depth", _ns_ast_depth, _acc_ast_depth)
    var _result_ast_depth = ast_depth(5, 5)
    var _summary_ast_depth = _summary_int(_result_ast_depth)
    print("MOJO_RESULT compiler_theory::ast_depth", _summary_ast_depth)
    var _acc_ast_node_count: Float64 = 0.0
    var _t0_ast_node_count = perf_counter_ns()
    for _ in range(N):
        _acc_ast_node_count += Float64(ast_node_count(5, 5))
    var _t1_ast_node_count = perf_counter_ns()
    var _ns_ast_node_count = Float64(_t1_ast_node_count - _t0_ast_node_count) / Float64(N)
    print("MOJO_TIMING compiler_theory::ast_node_count", _ns_ast_node_count, _acc_ast_node_count)
    var _result_ast_node_count = ast_node_count(5, 5)
    var _summary_ast_node_count = _summary_int(_result_ast_node_count)
    print("MOJO_RESULT compiler_theory::ast_node_count", _summary_ast_node_count)
    var _acc_register_pressure: Float64 = 0.0
    var _t0_register_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_register_pressure += Float64(register_pressure(5, 5, 5))
    var _t1_register_pressure = perf_counter_ns()
    var _ns_register_pressure = Float64(_t1_register_pressure - _t0_register_pressure) / Float64(N)
    print("MOJO_TIMING compiler_theory::register_pressure", _ns_register_pressure, _acc_register_pressure)
    var _result_register_pressure = register_pressure(5, 5, 5)
    var _summary_register_pressure = _summary_int(_result_register_pressure)
    print("MOJO_RESULT compiler_theory::register_pressure", _summary_register_pressure)
    var _acc_instruction_latency_sum: Float64 = 0.0
    var _t0_instruction_latency_sum = perf_counter_ns()
    for _ in range(N):
        _acc_instruction_latency_sum += Float64(instruction_latency_sum(_li5, 5))
    var _t1_instruction_latency_sum = perf_counter_ns()
    var _ns_instruction_latency_sum = Float64(_t1_instruction_latency_sum - _t0_instruction_latency_sum) / Float64(N)
    print("MOJO_TIMING compiler_theory::instruction_latency_sum", _ns_instruction_latency_sum, _acc_instruction_latency_sum)
    var _result_instruction_latency_sum = instruction_latency_sum(_li5, 5)
    var _summary_instruction_latency_sum = _summary_int(_result_instruction_latency_sum)
    print("MOJO_RESULT compiler_theory::instruction_latency_sum", _summary_instruction_latency_sum)
    var _acc_basic_block_throughput: Float64 = 0.0
    var _t0_basic_block_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_basic_block_throughput += basic_block_throughput(5, 5)
    var _t1_basic_block_throughput = perf_counter_ns()
    var _ns_basic_block_throughput = Float64(_t1_basic_block_throughput - _t0_basic_block_throughput) / Float64(N)
    print("MOJO_TIMING compiler_theory::basic_block_throughput", _ns_basic_block_throughput, _acc_basic_block_throughput)
    var _result_basic_block_throughput = basic_block_throughput(5, 5)
    var _summary_basic_block_throughput = _summary_float64(_result_basic_block_throughput)
    print("MOJO_RESULT compiler_theory::basic_block_throughput", _summary_basic_block_throughput)
    var _acc_loop_unroll_benefit: Float64 = 0.0
    var _t0_loop_unroll_benefit = perf_counter_ns()
    for _ in range(N):
        _acc_loop_unroll_benefit += Float64(loop_unroll_benefit(5, 5, 5))
    var _t1_loop_unroll_benefit = perf_counter_ns()
    var _ns_loop_unroll_benefit = Float64(_t1_loop_unroll_benefit - _t0_loop_unroll_benefit) / Float64(N)
    print("MOJO_TIMING compiler_theory::loop_unroll_benefit", _ns_loop_unroll_benefit, _acc_loop_unroll_benefit)
    var _result_loop_unroll_benefit = loop_unroll_benefit(5, 5, 5)
    var _summary_loop_unroll_benefit = _summary_int(_result_loop_unroll_benefit)
    print("MOJO_RESULT compiler_theory::loop_unroll_benefit", _summary_loop_unroll_benefit)
