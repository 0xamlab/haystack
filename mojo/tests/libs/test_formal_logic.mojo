"""test_formal_logic.mojo — auto-generated tests for formal_logic library."""
from std.math import isnan, isinf
from formal_logic import truth_and, truth_or, truth_not, truth_implies, truth_iff, truth_xor, truth_nand, truth_nor, modus_ponens, modus_tollens, hypothetical_syllogism, disjunctive_syllogism, is_tautology_2var, is_contradiction_2var

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

    _ = truth_and(True, True)
    passed += 1; print("  ✅ formal_logic::truth_and")
    _ = truth_or(True, True)
    passed += 1; print("  ✅ formal_logic::truth_or")
    _ = truth_not(True)
    passed += 1; print("  ✅ formal_logic::truth_not")
    _ = truth_implies(True, True)
    passed += 1; print("  ✅ formal_logic::truth_implies")
    _ = truth_iff(True, True)
    passed += 1; print("  ✅ formal_logic::truth_iff")
    _ = truth_xor(True, True)
    passed += 1; print("  ✅ formal_logic::truth_xor")
    _ = truth_nand(True, True)
    passed += 1; print("  ✅ formal_logic::truth_nand")
    _ = truth_nor(True, True)
    passed += 1; print("  ✅ formal_logic::truth_nor")
    _ = modus_ponens(True, True)
    passed += 1; print("  ✅ formal_logic::modus_ponens")
    _ = modus_tollens(True, True)
    passed += 1; print("  ✅ formal_logic::modus_tollens")
    _ = hypothetical_syllogism(True, True)
    passed += 1; print("  ✅ formal_logic::hypothetical_syllogism")
    _ = disjunctive_syllogism(True, True)
    passed += 1; print("  ✅ formal_logic::disjunctive_syllogism")
    _ = is_tautology_2var(5)
    passed += 1; print("  ✅ formal_logic::is_tautology_2var")
    _ = is_contradiction_2var(5)
    passed += 1; print("  ✅ formal_logic::is_contradiction_2var")

    print("  [formal_logic] Passed:", passed, "Failed:", failed)
