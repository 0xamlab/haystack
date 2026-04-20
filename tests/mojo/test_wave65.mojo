"""Tests for Wave 65 — Voting, Pharmacokinetics, Compiler Theory."""

from voting import (
    plurality_winner,
    borda_score,
    condorcet_pairwise,
    approval_score,
    majority_threshold,
    quota_droop,
    quota_hare,
    dhondt_divisor,
    sainte_lague_divisor,
    power_index_banzhaf,
    spoiler_effect,
)
from pharmacokinetics import (
    one_compartment_oral,
    one_compartment_iv,
    half_life,
    elimination_rate,
    clearance,
    bioavailability,
    loading_dose,
    maintenance_dose,
    steady_state_concentration,
    time_to_peak,
    accumulation_factor,
    drug_auc_trapezoidal,
)
from compiler_theory import (
    is_terminal,
    is_nonterminal,
    first_follow_conflict,
    lr_shift_reduce_conflict,
    reduce_reduce_conflict,
    grammar_is_ambiguous,
    ast_depth,
    ast_node_count,
    register_pressure,
    instruction_latency_sum,
    basic_block_throughput,
    loop_unroll_benefit,
)
from std.math import abs as fabs, log as _ln, exp as _exp


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Voting Tests ──────────────────────────────────────────────────────────────


fn test_plurality_winner() raises:
    print("  test_plurality_winner...")
    # 5 voters: 0,1,0,2,0 → candidate 0 wins with 3 votes
    var votes = List[Int]()
    votes.append(0); votes.append(1); votes.append(0); votes.append(2); votes.append(0)
    _assert(plurality_winner(votes, 3) == 0, "candidate 0 wins plurality")
    # All vote for candidate 1
    var votes2 = List[Int]()
    votes2.append(1); votes2.append(1); votes2.append(1)
    _assert(plurality_winner(votes2, 3) == 1, "candidate 1 unanimous")
    # Tie: 0,0,1,1 → candidate 0 wins (first max)
    var votes3 = List[Int]()
    votes3.append(0); votes3.append(0); votes3.append(1); votes3.append(1)
    _assert(plurality_winner(votes3, 2) == 0, "tie goes to first")


fn test_borda_score() raises:
    print("  test_borda_score...")
    # 2 voters, 3 candidates. Flat ranks: [rank_of_c0, rank_of_c1, rank_of_c2] per voter
    # Voter 0: c0=0th, c1=1st, c2=2nd → points: c0=2, c1=1, c2=0
    # Voter 1: c0=1st, c1=0th, c2=2nd → points: c0=1, c1=2, c2=0
    var ranks = List[Int]()
    ranks.append(0); ranks.append(1); ranks.append(2)
    ranks.append(1); ranks.append(0); ranks.append(2)
    _assert(borda_score(ranks, 3, 0) == 3, "borda c0=3")  # 2+1
    _assert(borda_score(ranks, 3, 1) == 3, "borda c1=3")  # 1+2
    _assert(borda_score(ranks, 3, 2) == 0, "borda c2=0")  # 0+0


fn test_condorcet_pairwise() raises:
    print("  test_condorcet_pairwise...")
    _assert(condorcet_pairwise(60, 40) == 1, "a wins")
    _assert(condorcet_pairwise(30, 70) == -1, "b wins")
    _assert(condorcet_pairwise(50, 50) == 0, "tie")


fn test_approval_score() raises:
    print("  test_approval_score...")
    var approvals = List[Int]()
    approvals.append(1); approvals.append(0); approvals.append(1)
    approvals.append(1); approvals.append(0)
    _assert(approval_score(approvals, 5) == 3, "3 approvals")
    var none_approved = List[Int]()
    none_approved.append(0); none_approved.append(0); none_approved.append(0)
    _assert(approval_score(none_approved, 3) == 0, "0 approvals")


fn test_majority_threshold() raises:
    print("  test_majority_threshold...")
    _assert(majority_threshold(100) == 51, "majority of 100 = 51")
    _assert(majority_threshold(101) == 51, "majority of 101 = 51")
    _assert(majority_threshold(1) == 1, "majority of 1 = 1")
    _assert(majority_threshold(10) == 6, "majority of 10 = 6")


fn test_quota_droop() raises:
    print("  test_quota_droop...")
    # Droop(100, 4) = floor(100/5)+1 = 21
    _assert(quota_droop(100, 4) == 21, "droop 100,4 = 21")
    # Droop(120, 5) = floor(120/6)+1 = 21
    _assert(quota_droop(120, 5) == 21, "droop 120,5 = 21")
    # Droop(10, 1) = floor(10/2)+1 = 6
    _assert(quota_droop(10, 1) == 6, "droop 10,1 = 6")


fn test_quota_hare() raises:
    print("  test_quota_hare...")
    _assert_close(quota_hare(100, 4), 25.0, 1e-9, "hare 100,4 = 25")
    _assert_close(quota_hare(120, 5), 24.0, 1e-9, "hare 120,5 = 24")
    _assert_close(quota_hare(10, 3), 3.333333, 1e-4, "hare 10,3 ≈ 3.33")


fn test_dhondt_divisor() raises:
    print("  test_dhondt_divisor...")
    _assert(dhondt_divisor(0) == 1, "dhondt 0 seats = 1")
    _assert(dhondt_divisor(3) == 4, "dhondt 3 seats = 4")
    _assert(dhondt_divisor(10) == 11, "dhondt 10 seats = 11")


fn test_sainte_lague_divisor() raises:
    print("  test_sainte_lague_divisor...")
    _assert(sainte_lague_divisor(0) == 1, "sl 0 seats = 1")
    _assert(sainte_lague_divisor(1) == 3, "sl 1 seat = 3")
    _assert(sainte_lague_divisor(5) == 11, "sl 5 seats = 11")


fn test_power_index_banzhaf() raises:
    print("  test_power_index_banzhaf...")
    # wins_with=6, wins_without=2, total=16 → power = 4/16 = 0.25
    _assert_close(power_index_banzhaf(6, 2, 16), 0.25, 1e-9, "banzhaf 0.25")
    _assert_close(power_index_banzhaf(8, 8, 16), 0.0, 1e-9, "banzhaf 0 (no swing)")


fn test_spoiler_effect() raises:
    print("  test_spoiler_effect...")
    _assert(spoiler_effect(0, 1), "spoiler: winner changed")
    _assert(not spoiler_effect(2, 2), "no spoiler: same winner")


# ── Pharmacokinetics Tests ────────────────────────────────────────────────────


fn test_one_compartment_iv() raises:
    print("  test_one_compartment_iv...")
    # dose=500, ke=0.1, vd=50, t=0 → C = 500/50 * exp(0) = 10.0
    _assert_close(one_compartment_iv(500.0, 0.1, 50.0, 0.0), 10.0, 1e-9, "iv t=0")
    # t=10 → C = 10 * exp(-1) ≈ 3.6788
    _assert_close(one_compartment_iv(500.0, 0.1, 50.0, 10.0), 10.0 * _exp(-1.0), 1e-4, "iv t=10")


fn test_one_compartment_oral() raises:
    print("  test_one_compartment_oral...")
    # At t=0, both exponentials are 1, so C(0) = 0
    _assert_close(one_compartment_oral(500.0, 1.0, 0.1, 50.0, 0.0), 0.0, 1e-9, "oral t=0")
    # At t=2, dose=500, ka=1.0, ke=0.1, vd=50
    # C(2) = (500*1.0)/(50*(1.0-0.1)) * (exp(-0.2) - exp(-2.0))
    var expected = (500.0 * 1.0) / (50.0 * 0.9) * (_exp(-0.2) - _exp(-2.0))
    _assert_close(one_compartment_oral(500.0, 1.0, 0.1, 50.0, 2.0), expected, 1e-6, "oral t=2")


fn test_half_life() raises:
    print("  test_half_life...")
    # ke=0.1 → t½ = ln2/0.1 ≈ 6.9315
    _assert_close(half_life(0.1), 6.931471805599453, 1e-6, "t½ ke=0.1")
    _assert_close(half_life(1.0), 0.6931471805599453, 1e-6, "t½ ke=1.0")


fn test_elimination_rate() raises:
    print("  test_elimination_rate...")
    # t½=6.9315 → ke ≈ 0.1
    _assert_close(elimination_rate(6.931471805599453), 0.1, 1e-6, "ke from t½")
    # Round-trip: ke → t½ → ke
    _assert_close(elimination_rate(half_life(0.25)), 0.25, 1e-9, "round-trip ke")


fn test_clearance() raises:
    print("  test_clearance...")
    _assert_close(clearance(0.1, 50.0), 5.0, 1e-9, "Cl = 5.0")
    _assert_close(clearance(0.5, 20.0), 10.0, 1e-9, "Cl = 10.0")


fn test_bioavailability() raises:
    print("  test_bioavailability...")
    _assert_close(bioavailability(80.0, 100.0), 0.8, 1e-9, "F = 0.8")
    _assert_close(bioavailability(100.0, 100.0), 1.0, 1e-9, "F = 1.0 (100%)")


fn test_loading_dose() raises:
    print("  test_loading_dose...")
    _assert_close(loading_dose(10.0, 50.0), 500.0, 1e-9, "LD = 500")


fn test_maintenance_dose() raises:
    print("  test_maintenance_dose...")
    # Css=10, Cl=5, tau=8 → MD = 400
    _assert_close(maintenance_dose(10.0, 5.0, 8.0), 400.0, 1e-9, "MD = 400")


fn test_steady_state() raises:
    print("  test_steady_state...")
    # dose=400, tau=8, Cl=5 → Css = 400/(8*5) = 10.0
    _assert_close(steady_state_concentration(400.0, 8.0, 5.0), 10.0, 1e-9, "Css = 10")


fn test_time_to_peak() raises:
    print("  test_time_to_peak...")
    # ka=1.0, ke=0.1 → tmax = ln(1.0/0.1)/(1.0-0.1) = ln(10)/0.9
    var expected = _ln(10.0) / 0.9
    _assert_close(time_to_peak(1.0, 0.1), expected, 1e-6, "tmax ka=1,ke=0.1")


fn test_accumulation_factor() raises:
    print("  test_accumulation_factor...")
    # ke=0.1, tau=6.9315 → exp(-0.69315) ≈ 0.5 → R = 1/(1-0.5) = 2.0
    _assert_close(accumulation_factor(0.1, 6.931471805599453), 2.0, 1e-4, "R ≈ 2.0")


fn test_drug_auc_trapezoidal() raises:
    print("  test_drug_auc_trapezoidal...")
    # c1=10, c2=8, t1=0, t2=2 → (10+8)/2 * 2 = 18
    _assert_close(drug_auc_trapezoidal(10.0, 8.0, 0.0, 2.0), 18.0, 1e-9, "AUC = 18")
    # c1=5, c2=5, t1=1, t2=4 → (5+5)/2 * 3 = 15
    _assert_close(drug_auc_trapezoidal(5.0, 5.0, 1.0, 4.0), 15.0, 1e-9, "AUC = 15")


# ── Compiler Theory Tests ────────────────────────────────────────────────────


fn test_is_terminal_nonterminal() raises:
    print("  test_is_terminal_nonterminal...")
    _assert(is_terminal(0), "0 is terminal")
    _assert(not is_terminal(1), "1 is not terminal")
    _assert(is_nonterminal(1), "1 is nonterminal")
    _assert(not is_nonterminal(0), "0 is not nonterminal")
    _assert(not is_nonterminal(2), "2 is not nonterminal")


fn test_first_follow_conflict() raises:
    print("  test_first_follow_conflict...")
    _assert(first_follow_conflict(True, True), "conflict: eps + overlap")
    _assert(not first_follow_conflict(True, False), "no conflict: eps, no overlap")
    _assert(not first_follow_conflict(False, True), "no conflict: no eps")
    _assert(not first_follow_conflict(False, False), "no conflict: neither")


fn test_lr_shift_reduce_conflict() raises:
    print("  test_lr_shift_reduce_conflict...")
    _assert(lr_shift_reduce_conflict(True, True), "S/R conflict")
    _assert(not lr_shift_reduce_conflict(True, False), "no S/R: can't reduce")
    _assert(not lr_shift_reduce_conflict(False, True), "no S/R: can't shift")


fn test_reduce_reduce_conflict() raises:
    print("  test_reduce_reduce_conflict...")
    _assert(reduce_reduce_conflict(True, True), "R/R conflict")
    _assert(not reduce_reduce_conflict(True, False), "no R/R: only one reduce")


fn test_grammar_is_ambiguous() raises:
    print("  test_grammar_is_ambiguous...")
    _assert(grammar_is_ambiguous(True, False), "ambiguous: S/R")
    _assert(grammar_is_ambiguous(False, True), "ambiguous: R/R")
    _assert(grammar_is_ambiguous(True, True), "ambiguous: both")
    _assert(not grammar_is_ambiguous(False, False), "not ambiguous")


fn test_ast_depth() raises:
    print("  test_ast_depth...")
    _assert(ast_depth(0, 0) == 1, "leaf depth = 1")
    _assert(ast_depth(3, 5) == 6, "depth = 1 + max(3,5) = 6")
    _assert(ast_depth(7, 2) == 8, "depth = 1 + max(7,2) = 8")


fn test_ast_node_count() raises:
    print("  test_ast_node_count...")
    _assert(ast_node_count(0, 0) == 1, "single node = 1")
    _assert(ast_node_count(3, 4) == 8, "3+4+1 = 8")
    _assert(ast_node_count(10, 5) == 16, "10+5+1 = 16")


fn test_register_pressure() raises:
    print("  test_register_pressure...")
    # live_in=5, defined=2, used=3 → 5-3+2 = 4
    _assert(register_pressure(5, 2, 3) == 4, "pressure = 4")
    _assert(register_pressure(0, 1, 0) == 1, "pressure = 1")
    _assert(register_pressure(10, 0, 5) == 5, "pressure = 5")


fn test_instruction_latency_sum() raises:
    print("  test_instruction_latency_sum...")
    var lats = List[Int]()
    lats.append(3); lats.append(1); lats.append(4); lats.append(1); lats.append(5)
    _assert(instruction_latency_sum(lats, 5) == 14, "sum = 14")
    var lats2 = List[Int]()
    lats2.append(2); lats2.append(2)
    _assert(instruction_latency_sum(lats2, 2) == 4, "sum = 4")


fn test_basic_block_throughput() raises:
    print("  test_basic_block_throughput...")
    _assert_close(basic_block_throughput(10, 5), 2.0, 1e-9, "IPC = 2.0")
    _assert_close(basic_block_throughput(7, 10), 0.7, 1e-9, "IPC = 0.7")


fn test_loop_unroll_benefit() raises:
    print("  test_loop_unroll_benefit...")
    # 100 iters, 2 overhead each, unroll by 4 → orig=200, after=25*2=50, benefit=150
    _assert(loop_unroll_benefit(100, 2, 4) == 150, "unroll benefit = 150")
    # 10 iters, 3 overhead, unroll by 5 → orig=30, after=2*3=6, benefit=24
    _assert(loop_unroll_benefit(10, 3, 5) == 24, "unroll benefit = 24")
    # 7 iters, 1 overhead, unroll by 3 → orig=7, after=ceil(7/3)*1=3, benefit=4
    _assert(loop_unroll_benefit(7, 1, 3) == 4, "unroll benefit = 4")


# ── Main ──────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 65 Tests ===")

    # Voting
    print("─ Voting ─")
    test_plurality_winner()
    test_borda_score()
    test_condorcet_pairwise()
    test_approval_score()
    test_majority_threshold()
    test_quota_droop()
    test_quota_hare()
    test_dhondt_divisor()
    test_sainte_lague_divisor()
    test_power_index_banzhaf()
    test_spoiler_effect()

    # Pharmacokinetics
    print("─ Pharmacokinetics ─")
    test_one_compartment_iv()
    test_one_compartment_oral()
    test_half_life()
    test_elimination_rate()
    test_clearance()
    test_bioavailability()
    test_loading_dose()
    test_maintenance_dose()
    test_steady_state()
    test_time_to_peak()
    test_accumulation_factor()
    test_drug_auc_trapezoidal()

    # Compiler Theory
    print("─ Compiler Theory ─")
    test_is_terminal_nonterminal()
    test_first_follow_conflict()
    test_lr_shift_reduce_conflict()
    test_reduce_reduce_conflict()
    test_grammar_is_ambiguous()
    test_ast_depth()
    test_ast_node_count()
    test_register_pressure()
    test_instruction_latency_sum()
    test_basic_block_throughput()
    test_loop_unroll_benefit()

    print("=== All Wave 65 tests passed! ===")
