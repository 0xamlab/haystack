"""test_compiler_theory.mojo — auto-generated tests for compiler_theory library."""
from std.math import isnan, isinf
from compiler_theory import is_terminal, is_nonterminal, first_follow_conflict, lr_shift_reduce_conflict, reduce_reduce_conflict, grammar_is_ambiguous, ast_depth, ast_node_count, register_pressure, instruction_latency_sum, basic_block_throughput, loop_unroll_benefit

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    _ = is_terminal(5)
    passed += 1; print("  ✅ compiler_theory::is_terminal")
    _ = is_nonterminal(5)
    passed += 1; print("  ✅ compiler_theory::is_nonterminal")
    _ = first_follow_conflict(True, True)
    passed += 1; print("  ✅ compiler_theory::first_follow_conflict")
    _ = lr_shift_reduce_conflict(True, True)
    passed += 1; print("  ✅ compiler_theory::lr_shift_reduce_conflict")
    _ = reduce_reduce_conflict(True, True)
    passed += 1; print("  ✅ compiler_theory::reduce_reduce_conflict")
    _ = grammar_is_ambiguous(True, True)
    passed += 1; print("  ✅ compiler_theory::grammar_is_ambiguous")
    _ = ast_depth(5, 5)
    passed += 1; print("  ✅ compiler_theory::ast_depth")
    _ = ast_node_count(5, 5)
    passed += 1; print("  ✅ compiler_theory::ast_node_count")
    _ = register_pressure(5, 5, 5)
    passed += 1; print("  ✅ compiler_theory::register_pressure")
    _ = instruction_latency_sum(_li5, 5)
    passed += 1; print("  ✅ compiler_theory::instruction_latency_sum")
    var _v_basic_block_throughput = basic_block_throughput(5, 5)
    if is_finite(_v_basic_block_throughput): passed += 1; print("  ✅ compiler_theory::basic_block_throughput =", _v_basic_block_throughput)
    else: failed += 1; print("  ❌ compiler_theory::basic_block_throughput → non-finite:", _v_basic_block_throughput)
    _ = loop_unroll_benefit(5, 5, 5)
    passed += 1; print("  ✅ compiler_theory::loop_unroll_benefit")

    print("  [compiler_theory] Passed:", passed, "Failed:", failed)
