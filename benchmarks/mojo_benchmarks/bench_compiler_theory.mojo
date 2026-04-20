"""bench_compiler_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compiler_theory import is_terminal, is_nonterminal, first_follow_conflict, lr_shift_reduce_conflict, reduce_reduce_conflict, grammar_is_ambiguous, ast_depth, ast_node_count, register_pressure, instruction_latency_sum, basic_block_throughput, loop_unroll_benefit
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

    var _acc_is_terminal: Float64 = 0.0
    var _t0_is_terminal = perf_counter_ns()
    for _ in range(N):
        _acc_is_terminal += Float64(is_terminal(5))
    var _t1_is_terminal = perf_counter_ns()
    var _ns_is_terminal = Float64(_t1_is_terminal - _t0_is_terminal) / Float64(N)
    print("MOJO_TIMING compiler_theory::is_terminal", _ns_is_terminal, _acc_is_terminal)
    var _acc_is_nonterminal: Float64 = 0.0
    var _t0_is_nonterminal = perf_counter_ns()
    for _ in range(N):
        _acc_is_nonterminal += Float64(is_nonterminal(5))
    var _t1_is_nonterminal = perf_counter_ns()
    var _ns_is_nonterminal = Float64(_t1_is_nonterminal - _t0_is_nonterminal) / Float64(N)
    print("MOJO_TIMING compiler_theory::is_nonterminal", _ns_is_nonterminal, _acc_is_nonterminal)
    var _acc_first_follow_conflict: Float64 = 0.0
    var _t0_first_follow_conflict = perf_counter_ns()
    for _ in range(N):
        _acc_first_follow_conflict += Float64(first_follow_conflict(True, True))
    var _t1_first_follow_conflict = perf_counter_ns()
    var _ns_first_follow_conflict = Float64(_t1_first_follow_conflict - _t0_first_follow_conflict) / Float64(N)
    print("MOJO_TIMING compiler_theory::first_follow_conflict", _ns_first_follow_conflict, _acc_first_follow_conflict)
    var _acc_lr_shift_reduce_conflict: Float64 = 0.0
    var _t0_lr_shift_reduce_conflict = perf_counter_ns()
    for _ in range(N):
        _acc_lr_shift_reduce_conflict += Float64(lr_shift_reduce_conflict(True, True))
    var _t1_lr_shift_reduce_conflict = perf_counter_ns()
    var _ns_lr_shift_reduce_conflict = Float64(_t1_lr_shift_reduce_conflict - _t0_lr_shift_reduce_conflict) / Float64(N)
    print("MOJO_TIMING compiler_theory::lr_shift_reduce_conflict", _ns_lr_shift_reduce_conflict, _acc_lr_shift_reduce_conflict)
    var _acc_reduce_reduce_conflict: Float64 = 0.0
    var _t0_reduce_reduce_conflict = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_reduce_conflict += Float64(reduce_reduce_conflict(True, True))
    var _t1_reduce_reduce_conflict = perf_counter_ns()
    var _ns_reduce_reduce_conflict = Float64(_t1_reduce_reduce_conflict - _t0_reduce_reduce_conflict) / Float64(N)
    print("MOJO_TIMING compiler_theory::reduce_reduce_conflict", _ns_reduce_reduce_conflict, _acc_reduce_reduce_conflict)
    var _acc_grammar_is_ambiguous: Float64 = 0.0
    var _t0_grammar_is_ambiguous = perf_counter_ns()
    for _ in range(N):
        _acc_grammar_is_ambiguous += Float64(grammar_is_ambiguous(True, True))
    var _t1_grammar_is_ambiguous = perf_counter_ns()
    var _ns_grammar_is_ambiguous = Float64(_t1_grammar_is_ambiguous - _t0_grammar_is_ambiguous) / Float64(N)
    print("MOJO_TIMING compiler_theory::grammar_is_ambiguous", _ns_grammar_is_ambiguous, _acc_grammar_is_ambiguous)
    var _acc_ast_depth: Float64 = 0.0
    var _t0_ast_depth = perf_counter_ns()
    for _ in range(N):
        _acc_ast_depth += Float64(ast_depth(5, 5))
    var _t1_ast_depth = perf_counter_ns()
    var _ns_ast_depth = Float64(_t1_ast_depth - _t0_ast_depth) / Float64(N)
    print("MOJO_TIMING compiler_theory::ast_depth", _ns_ast_depth, _acc_ast_depth)
    var _acc_ast_node_count: Float64 = 0.0
    var _t0_ast_node_count = perf_counter_ns()
    for _ in range(N):
        _acc_ast_node_count += Float64(ast_node_count(5, 5))
    var _t1_ast_node_count = perf_counter_ns()
    var _ns_ast_node_count = Float64(_t1_ast_node_count - _t0_ast_node_count) / Float64(N)
    print("MOJO_TIMING compiler_theory::ast_node_count", _ns_ast_node_count, _acc_ast_node_count)
    var _acc_register_pressure: Float64 = 0.0
    var _t0_register_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_register_pressure += Float64(register_pressure(5, 5, 5))
    var _t1_register_pressure = perf_counter_ns()
    var _ns_register_pressure = Float64(_t1_register_pressure - _t0_register_pressure) / Float64(N)
    print("MOJO_TIMING compiler_theory::register_pressure", _ns_register_pressure, _acc_register_pressure)
    var _acc_instruction_latency_sum: Float64 = 0.0
    var _t0_instruction_latency_sum = perf_counter_ns()
    for _ in range(N):
        _acc_instruction_latency_sum += Float64(instruction_latency_sum(_li5, 5))
    var _t1_instruction_latency_sum = perf_counter_ns()
    var _ns_instruction_latency_sum = Float64(_t1_instruction_latency_sum - _t0_instruction_latency_sum) / Float64(N)
    print("MOJO_TIMING compiler_theory::instruction_latency_sum", _ns_instruction_latency_sum, _acc_instruction_latency_sum)
    var _acc_basic_block_throughput: Float64 = 0.0
    var _t0_basic_block_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_basic_block_throughput += basic_block_throughput(5, 5)
    var _t1_basic_block_throughput = perf_counter_ns()
    var _ns_basic_block_throughput = Float64(_t1_basic_block_throughput - _t0_basic_block_throughput) / Float64(N)
    print("MOJO_TIMING compiler_theory::basic_block_throughput", _ns_basic_block_throughput, _acc_basic_block_throughput)
    var _acc_loop_unroll_benefit: Float64 = 0.0
    var _t0_loop_unroll_benefit = perf_counter_ns()
    for _ in range(N):
        _acc_loop_unroll_benefit += Float64(loop_unroll_benefit(5, 5, 5))
    var _t1_loop_unroll_benefit = perf_counter_ns()
    var _ns_loop_unroll_benefit = Float64(_t1_loop_unroll_benefit - _t0_loop_unroll_benefit) / Float64(N)
    print("MOJO_TIMING compiler_theory::loop_unroll_benefit", _ns_loop_unroll_benefit, _acc_loop_unroll_benefit)
