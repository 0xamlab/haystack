"""
compiler_theory.mojo — Compiler Theory / Language Processing Library.
Zero Python imports.

Utilities for grammar analysis, AST metrics, register allocation,
instruction scheduling, and optimization heuristics.

Public API:
  is_terminal               — Check if symbol is terminal
  is_nonterminal            — Check if symbol is nonterminal
  first_follow_conflict     — LL(1) conflict check
  lr_shift_reduce_conflict  — S/R conflict detection
  reduce_reduce_conflict    — R/R conflict detection
  grammar_is_ambiguous      — Ambiguity indicator
  ast_depth                 — Depth of binary AST node
  ast_node_count            — Total nodes in binary AST
  register_pressure         — Live register count
  instruction_latency_sum   — Sum of instruction latencies
  basic_block_throughput    — IPC = instructions / cycles
  loop_unroll_benefit       — Overhead reduction from unrolling
"""


# ── is_terminal ───────────────────────────────────────────────────────────────


fn is_terminal(symbol_type: Int) -> Bool:
    """Check if symbol is terminal (type == 0)."""
    return symbol_type == 0


# ── is_nonterminal ────────────────────────────────────────────────────────────


fn is_nonterminal(symbol_type: Int) -> Bool:
    """Check if symbol is nonterminal (type == 1)."""
    return symbol_type == 1


# ── first_follow_conflict ─────────────────────────────────────────────────────


fn first_follow_conflict(first_has_epsilon: Bool, follow_overlap: Bool) -> Bool:
    """LL(1) conflict: FIRST contains ε AND FOLLOW overlaps with FIRST."""
    return first_has_epsilon and follow_overlap


# ── lr_shift_reduce_conflict ──────────────────────────────────────────────────


fn lr_shift_reduce_conflict(can_shift: Bool, can_reduce: Bool) -> Bool:
    """Shift/reduce conflict: both shift and reduce are possible."""
    return can_shift and can_reduce


# ── reduce_reduce_conflict ────────────────────────────────────────────────────


fn reduce_reduce_conflict(reduce1: Bool, reduce2: Bool) -> Bool:
    """Reduce/reduce conflict: two different reductions possible."""
    return reduce1 and reduce2


# ── grammar_is_ambiguous ──────────────────────────────────────────────────────


fn grammar_is_ambiguous(has_sr_conflict: Bool, has_rr_conflict: Bool) -> Bool:
    """Grammar is ambiguous if it has S/R or R/R conflicts."""
    return has_sr_conflict or has_rr_conflict


# ── ast_depth ─────────────────────────────────────────────────────────────────


fn ast_depth(left_depth: Int, right_depth: Int) -> Int:
    """Depth of binary AST node = 1 + max(left, right)."""
    var mx = left_depth
    if right_depth > mx:
        mx = right_depth
    return 1 + mx


# ── ast_node_count ────────────────────────────────────────────────────────────


fn ast_node_count(left_count: Int, right_count: Int) -> Int:
    """Total nodes = left + right + 1."""
    return left_count + right_count + 1


# ── register_pressure ─────────────────────────────────────────────────────────


fn register_pressure(live_in: Int, defined: Int, used: Int) -> Int:
    """Live registers after instruction = live_in - used + defined."""
    return live_in - used + defined


# ── instruction_latency_sum ───────────────────────────────────────────────────


fn instruction_latency_sum(latencies: List[Int], n: Int) -> Int:
    """Sum of instruction latencies (critical path estimate)."""
    var total = 0
    for i in range(n):
        total += latencies[i]
    return total


# ── basic_block_throughput ────────────────────────────────────────────────────


fn basic_block_throughput(n_instructions: Int, cycles: Int) -> Float64:
    """IPC = instructions / cycles."""
    return Float64(n_instructions) / Float64(cycles)


# ── loop_unroll_benefit ───────────────────────────────────────────────────────


fn loop_unroll_benefit(
    iterations: Int, overhead_per_iter: Int, unroll_factor: Int,
) -> Int:
    """Reduced overhead from unrolling.

    Original overhead = iterations * overhead_per_iter.
    After unrolling = ceil(iterations / unroll_factor) * overhead_per_iter.
    Benefit = original - after.
    """
    var original = iterations * overhead_per_iter
    var unrolled_iters = (iterations + unroll_factor - 1) // unroll_factor
    var after = unrolled_iters * overhead_per_iter
    return original - after
