"""Tests for Wave 32 — Distribution Fitting, Boolean Algebra, Inventory Optimization."""

from distribution_fit import (
    fit_normal,
    fit_exponential,
    fit_uniform,
    fit_weibull,
    log_likelihood_normal,
    log_likelihood_exponential,
    aic,
    bic,
    best_fit,
    qq_residuals,
)
from boolean_algebra import (
    bool_and,
    bool_or,
    bool_not,
    bool_xor,
    bool_implies,
    bool_iff,
    truth_table_2,
    eval_dnf,
    eval_cnf,
    is_tautology_2var,
    count_satisfying_2var,
    majority_vote,
    parity,
)
from inventory import (
    eoq,
    reorder_point,
    safety_stock,
    total_inventory_cost,
    newsvendor_qty,
    service_level,
    abc_classify,
    days_of_supply,
    inventory_turnover,
    fill_rate,
    periodic_review_order,
)
from std.math import abs as fabs, sqrt, log


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helper: build float lists ───────────────────────────────────────────────


def _make_normal_data() -> List[Float64]:
    """Create data that looks roughly normal: mean~5, std~1."""
    var d = List[Float64]()
    # Hand-crafted values centered around 5 with std ~1
    d.append(3.5); d.append(4.0); d.append(4.2); d.append(4.5); d.append(4.7)
    d.append(4.8); d.append(4.9); d.append(5.0); d.append(5.0); d.append(5.1)
    d.append(5.2); d.append(5.3); d.append(5.5); d.append(5.8); d.append(6.0)
    d.append(6.2); d.append(6.5); d.append(5.1); d.append(4.9); d.append(5.3)
    return d^


def _make_exp_data() -> List[Float64]:
    """Create data that looks exponential-like (all positive, right-skewed)."""
    var d = List[Float64]()
    d.append(0.1); d.append(0.2); d.append(0.3); d.append(0.5); d.append(0.7)
    d.append(0.8); d.append(1.0); d.append(1.2); d.append(1.5); d.append(2.0)
    d.append(2.5); d.append(3.0); d.append(3.5); d.append(4.0); d.append(5.0)
    d.append(0.4); d.append(0.6); d.append(0.9); d.append(1.1); d.append(1.8)
    return d^


def _make_uniform_data() -> List[Float64]:
    """Create data that looks roughly uniform on [0, 1]."""
    var d = List[Float64]()
    d.append(0.05); d.append(0.10); d.append(0.15); d.append(0.20); d.append(0.25)
    d.append(0.30); d.append(0.35); d.append(0.40); d.append(0.45); d.append(0.50)
    d.append(0.55); d.append(0.60); d.append(0.65); d.append(0.70); d.append(0.75)
    d.append(0.80); d.append(0.85); d.append(0.90); d.append(0.95); d.append(0.99)
    return d^


# ── Distribution Fitting Tests ──────────────────────────────────────────────


def test_distribution_fit() raises:
    print("── Distribution Fitting Tests ──")

    # 1. fit_normal: mean close to 5
    var norm_data = _make_normal_data()
    var norm_params = fit_normal(norm_data)
    _assert_close(norm_params[0], 5.075, 0.2, "fit_normal mean ≈ 5.075")
    # 2. fit_normal: std close to ~0.65
    _assert(norm_params[1] > 0.3 and norm_params[1] < 1.5, "fit_normal std in range")
    print("  ✓ fit_normal")

    # 3. fit_exponential on exp data: rate = 1/mean
    var exp_data = _make_exp_data()
    var rate = fit_exponential(exp_data)
    _assert(rate > 0.0, "fit_exponential rate > 0")
    # Mean of exp_data ≈ 1.555, so rate ≈ 0.643
    # 4. rate reasonable range
    _assert(rate > 0.3 and rate < 2.0, "fit_exponential rate reasonable")
    print("  ✓ fit_exponential")

    # 5. fit_uniform on [0,1] data: min ≈ 0.05, max ≈ 0.99
    var uni_data = _make_uniform_data()
    var uni_params = fit_uniform(uni_data)
    _assert_close(uni_params[0], 0.05, 0.01, "fit_uniform min ≈ 0.05")
    # 6. max ≈ 0.99
    _assert_close(uni_params[1], 0.99, 0.01, "fit_uniform max ≈ 0.99")
    print("  ✓ fit_uniform")

    # 7. fit_weibull returns positive shape and scale
    var weib = fit_weibull(norm_data)
    _assert(weib[0] > 0.0, "fit_weibull shape > 0")
    # 8. scale positive
    _assert(weib[1] > 0.0, "fit_weibull scale > 0")
    print("  ✓ fit_weibull")

    # 9. log_likelihood_normal: finite value
    var ll_norm = log_likelihood_normal(norm_data, norm_params[0], norm_params[1])
    _assert(ll_norm > -1e15 and ll_norm < 1e15, "log_likelihood_normal finite")
    # 10. log_likelihood should be negative for reasonable data
    _assert(ll_norm < 0.0, "log_likelihood_normal < 0")
    print("  ✓ log_likelihood_normal")

    # 11. log_likelihood_exponential: finite
    var ll_exp = log_likelihood_exponential(exp_data, rate)
    _assert(ll_exp > -1e15 and ll_exp < 1e15, "log_likelihood_exponential finite")
    print("  ✓ log_likelihood_exponential")

    # 12. AIC: 2k - 2*LL
    var aic_val = aic(ll_norm, 2)
    _assert_close(aic_val, 4.0 - 2.0 * ll_norm, 1e-10, "aic = 2k - 2*LL")
    print("  ✓ aic")

    # 13. BIC: k*ln(n) - 2*LL
    var bic_val = bic(ll_norm, 2, 20)
    var expected_bic = 2.0 * log(20.0) - 2.0 * ll_norm
    _assert_close(bic_val, expected_bic, 1e-10, "bic = k*ln(n) - 2*LL")
    # 14. For n=20 > e^2 ≈ 7.39, BIC penalty > AIC penalty, so BIC > AIC
    _assert(bic_val > aic_val, "bic > aic for n=20")
    print("  ✓ bic")

    # 15. best_fit on normal-looking data should return 0 (normal)
    var bf = best_fit(norm_data)
    _assert(bf == 0, "best_fit normal data → 0")
    print("  ✓ best_fit")

    # 16. qq_residuals: length == data length
    var resid = qq_residuals(norm_data, norm_params[0], norm_params[1])
    _assert(len(resid) == len(norm_data), "qq_residuals length == data length")
    # 17. residuals should be small for well-fit normal data
    var max_resid: Float64 = 0.0
    for i in range(len(resid)):
        if fabs(resid[i]) > max_resid:
            max_resid = fabs(resid[i])
    _assert(max_resid < 2.0, "qq_residuals max residual < 2.0 for normal data")
    print("  ✓ qq_residuals")


# ── Boolean Algebra Tests ───────────────────────────────────────────────────


def test_boolean_algebra() raises:
    print("── Boolean Algebra Tests ──")

    # 18. bool_and(True, True) == True
    _assert(bool_and(True, True) == True, "AND(T,T)=T")
    # 19. bool_and(True, False) == False
    _assert(bool_and(True, False) == False, "AND(T,F)=F")
    # 20. bool_and(False, False) == False
    _assert(bool_and(False, False) == False, "AND(F,F)=F")
    print("  ✓ bool_and")

    # 21. bool_or(False, False) == False
    _assert(bool_or(False, False) == False, "OR(F,F)=F")
    # 22. bool_or(True, False) == True
    _assert(bool_or(True, False) == True, "OR(T,F)=T")
    # 23. bool_or(True, True) == True
    _assert(bool_or(True, True) == True, "OR(T,T)=T")
    print("  ✓ bool_or")

    # 24. bool_not(True) == False
    _assert(bool_not(True) == False, "NOT(T)=F")
    # 25. bool_not(False) == True
    _assert(bool_not(False) == True, "NOT(F)=T")
    print("  ✓ bool_not")

    # 26. bool_xor(True, True) == False
    _assert(bool_xor(True, True) == False, "XOR(T,T)=F")
    # 27. bool_xor(True, False) == True
    _assert(bool_xor(True, False) == True, "XOR(T,F)=T")
    # 28. bool_xor(False, False) == False
    _assert(bool_xor(False, False) == False, "XOR(F,F)=F")
    print("  ✓ bool_xor")

    # 29. bool_implies(True, False) == False
    _assert(bool_implies(True, False) == False, "IMPLIES(T,F)=F")
    # 30. bool_implies(False, True) == True
    _assert(bool_implies(False, True) == True, "IMPLIES(F,T)=T")
    # 31. bool_implies(False, False) == True
    _assert(bool_implies(False, False) == True, "IMPLIES(F,F)=T")
    # 32. bool_implies(True, True) == True
    _assert(bool_implies(True, True) == True, "IMPLIES(T,T)=T")
    print("  ✓ bool_implies")

    # 33. bool_iff(True, True) == True
    _assert(bool_iff(True, True) == True, "IFF(T,T)=T")
    # 34. bool_iff(True, False) == False
    _assert(bool_iff(True, False) == False, "IFF(T,F)=F")
    print("  ✓ bool_iff")

    # 35. truth_table_2(0) for AND: 4 rows, only TT→T
    var tt_and = truth_table_2(0)
    _assert(len(tt_and) == 4, "truth_table_2 AND has 4 rows")
    # Row 3 is (True, True) -> True, others False
    # 36. Only last row True for AND
    var and_true_count = 0
    for i in range(4):
        if tt_and[i][2]:
            and_true_count += 1
    _assert(and_true_count == 1, "truth_table AND: only 1 true row")
    print("  ✓ truth_table_2 AND")

    # 37. is_tautology_2var: AND is not a tautology
    _assert(is_tautology_2var(0) == False, "AND is not tautology")
    # 38. OR is not a tautology
    _assert(is_tautology_2var(1) == False, "OR is not tautology")
    # 39. IMPLIES is not a tautology
    _assert(is_tautology_2var(3) == False, "IMPLIES is not tautology")
    print("  ✓ is_tautology_2var")

    # 40. count_satisfying_2var(0) AND == 1
    _assert(count_satisfying_2var(0) == 1, "count_satisfying AND = 1")
    # 41. count_satisfying_2var(1) OR == 3
    _assert(count_satisfying_2var(1) == 3, "count_satisfying OR = 3")
    # 42. count_satisfying_2var(2) XOR == 2
    _assert(count_satisfying_2var(2) == 2, "count_satisfying XOR = 2")
    # 43. count_satisfying_2var(3) IMPLIES == 3
    _assert(count_satisfying_2var(3) == 3, "count_satisfying IMPLIES = 3")
    # 44. count_satisfying_2var(4) IFF == 2
    _assert(count_satisfying_2var(4) == 2, "count_satisfying IFF = 2")
    print("  ✓ count_satisfying_2var")

    # 45. eval_dnf: (x1 AND x2) OR (NOT x1 AND x3) with [T, T, F] → True (first clause)
    var vals_dnf = List[Bool]()
    vals_dnf.append(True); vals_dnf.append(True); vals_dnf.append(False)
    var clauses_dnf = List[List[Int]]()
    var c1 = List[Int](); c1.append(1); c1.append(2)
    var c2 = List[Int](); c2.append(-1); c2.append(3)
    clauses_dnf.append(c1^); clauses_dnf.append(c2^)
    _assert(eval_dnf(vals_dnf, clauses_dnf) == True, "eval_dnf (x1∧x2)∨(¬x1∧x3) with TTF = True")
    print("  ✓ eval_dnf")

    # 46. eval_cnf: (x1 OR x2) AND (NOT x1 OR x3) with [T, F, T] → True
    var vals_cnf = List[Bool]()
    vals_cnf.append(True); vals_cnf.append(False); vals_cnf.append(True)
    var clauses_cnf = List[List[Int]]()
    var cc1 = List[Int](); cc1.append(1); cc1.append(2)
    var cc2 = List[Int](); cc2.append(-1); cc2.append(3)
    clauses_cnf.append(cc1^); clauses_cnf.append(cc2^)
    _assert(eval_cnf(vals_cnf, clauses_cnf) == True, "eval_cnf (x1∨x2)∧(¬x1∨x3) with TFT = True")

    # 47. eval_cnf: same formula with [T, F, F] → False (second clause fails)
    var vals_cnf2 = List[Bool]()
    vals_cnf2.append(True); vals_cnf2.append(False); vals_cnf2.append(False)
    _assert(eval_cnf(vals_cnf2, clauses_cnf) == False, "eval_cnf with TFF = False")
    print("  ✓ eval_cnf")

    # 48. majority_vote([True, True, False]) == True
    var maj_vals = List[Bool]()
    maj_vals.append(True); maj_vals.append(True); maj_vals.append(False)
    _assert(majority_vote(maj_vals) == True, "majority_vote [T,T,F] = T")
    # 49. majority_vote([True, False, False]) == False
    var maj_vals2 = List[Bool]()
    maj_vals2.append(True); maj_vals2.append(False); maj_vals2.append(False)
    _assert(majority_vote(maj_vals2) == False, "majority_vote [T,F,F] = F")
    print("  ✓ majority_vote")

    # 50. parity([True, True]) == False (even number of True)
    var par_vals = List[Bool]()
    par_vals.append(True); par_vals.append(True)
    _assert(parity(par_vals) == False, "parity [T,T] = F")
    # 51. parity([True, True, True]) == True (odd number)
    var par_vals2 = List[Bool]()
    par_vals2.append(True); par_vals2.append(True); par_vals2.append(True)
    _assert(parity(par_vals2) == True, "parity [T,T,T] = T")
    # 52. parity([False, False]) == False
    var par_vals3 = List[Bool]()
    par_vals3.append(False); par_vals3.append(False)
    _assert(parity(par_vals3) == False, "parity [F,F] = F")
    print("  ✓ parity")


# ── Inventory Optimization Tests ────────────────────────────────────────────


def test_inventory() raises:
    print("── Inventory Optimization Tests ──")

    # 53. eoq(1000, 50, 2) ≈ sqrt(50000) ≈ 223.607
    var q = eoq(1000.0, 50.0, 2.0)
    _assert_close(q, 223.607, 0.01, "eoq(1000,50,2) ≈ 223.607")
    print("  ✓ eoq")

    # 54. reorder_point(10, 5, 20) == 70
    var rop = reorder_point(10.0, 5.0, 20.0)
    _assert_close(rop, 70.0, 1e-10, "reorder_point(10,5,20) = 70")
    print("  ✓ reorder_point")

    # 55. safety_stock(1.96, 10, 4) ≈ 39.2
    var ss = safety_stock(1.96, 10.0, 4.0)
    _assert_close(ss, 39.2, 0.1, "safety_stock(1.96,10,4) ≈ 39.2")
    print("  ✓ safety_stock")

    # 56. total_inventory_cost at EOQ is approximately minimized
    var tc_eoq = total_inventory_cost(1000.0, q, 50.0, 2.0)
    # Cost at EOQ should be ≈ 447.21
    _assert_close(tc_eoq, 447.214, 0.1, "total_inventory_cost at EOQ ≈ 447.21")
    # 57. Cost at different Q should be higher
    var tc_other = total_inventory_cost(1000.0, 100.0, 50.0, 2.0)
    _assert(tc_other > tc_eoq, "total_inventory_cost: non-EOQ Q has higher cost")
    # 58. Cost at yet another Q is also higher
    var tc_other2 = total_inventory_cost(1000.0, 500.0, 50.0, 2.0)
    _assert(tc_other2 > tc_eoq, "total_inventory_cost: Q=500 has higher cost")
    print("  ✓ total_inventory_cost")

    # 59. newsvendor_qty: reasonable positive value
    var nv = newsvendor_qty(100.0, 20.0, 10.0, 5.0)
    _assert(nv > 0.0, "newsvendor_qty > 0")
    # Cu/(Cu+Co) = 10/15 = 0.667, z ≈ 0.43 → Q* ≈ 100 + 0.43*20 ≈ 108.6
    _assert(nv > 90.0 and nv < 130.0, "newsvendor_qty in reasonable range")
    print("  ✓ newsvendor_qty")

    # 60. service_level(0) ≈ 0.5
    var sl0 = service_level(0.0)
    _assert_close(sl0, 0.5, 0.01, "service_level(0) ≈ 0.5")
    # 61. service_level(1.96) ≈ 0.975
    var sl196 = service_level(1.96)
    _assert_close(sl196, 0.975, 0.01, "service_level(1.96) ≈ 0.975")
    # 62. service_level(-1.96) ≈ 0.025
    var sl_neg = service_level(-1.96)
    _assert_close(sl_neg, 0.025, 0.01, "service_level(-1.96) ≈ 0.025")
    print("  ✓ service_level")

    # 63. abc_classify: items sorted by value
    var abc_vals = List[Float64]()
    # Item 0: 50, Item 1: 5, Item 2: 100, Item 3: 10, Item 4: 35
    abc_vals.append(50.0); abc_vals.append(5.0); abc_vals.append(100.0)
    abc_vals.append(10.0); abc_vals.append(35.0)
    var classes = abc_classify(abc_vals)
    _assert(len(classes) == 5, "abc_classify returns 5 classes")
    # Total = 200. Sorted desc: Item2(100), Item0(50), Item4(35), Item3(10), Item1(5)
    # Cumulative: 100/200=50%→ after item2 cum=50% (>20%, so B or higher)
    # Item2 at 50% is first, but 50%>20% so it's B. Actually cumulative:
    # Item2: 100/200=0.5 → >0.20 → B
    # Hmm, wait: cum after item2 = 0.5 → B (since 0.5 <= 0.50)
    # Item0: cum = 150/200=0.75 → C
    # Item4: cum = 185/200=0.925 → C
    # Item3: cum = 195/200=0.975 → C
    # Item1: cum = 200/200=1.0 → C
    # But item2 should be A? Let's re-check: 100/200 = 0.5, which is > 0.20
    # With this data no single item is ≤ 20% unless value is ≤ 40
    # 64. Highest value item (index 2) should be A or B (class 0 or 1)
    _assert(classes[2] <= 1, "abc_classify: highest value item is A or B")
    # 65. Lowest value item (index 1, val=5) should be C (class 2)
    _assert(classes[1] == 2, "abc_classify: lowest value item is C")
    print("  ✓ abc_classify")

    # 66. days_of_supply(100, 10) == 10
    _assert_close(days_of_supply(100.0, 10.0), 10.0, 1e-10, "days_of_supply(100,10) = 10")
    # 67. days_of_supply(0, 10) == 0
    _assert_close(days_of_supply(0.0, 10.0), 0.0, 1e-10, "days_of_supply(0,10) = 0")
    print("  ✓ days_of_supply")

    # 68. inventory_turnover(10000, 2000) == 5.0
    _assert_close(inventory_turnover(10000.0, 2000.0), 5.0, 1e-10, "inventory_turnover = 5.0")
    print("  ✓ inventory_turnover")

    # 69. fill_rate(95, 100) == 0.95
    _assert_close(fill_rate(95, 100), 0.95, 1e-10, "fill_rate(95,100) = 0.95")
    # 70. fill_rate(100, 100) == 1.0
    _assert_close(fill_rate(100, 100), 1.0, 1e-10, "fill_rate(100,100) = 1.0")
    print("  ✓ fill_rate")

    # 71. periodic_review_order(100, 40, 10) == 50
    _assert_close(periodic_review_order(100.0, 40.0, 10.0), 50.0, 1e-10, "periodic_review_order = 50")
    # 72. periodic_review_order when on_hand + on_order > target → 0
    _assert_close(periodic_review_order(50.0, 40.0, 20.0), 0.0, 1e-10, "periodic_review_order = 0 when excess")
    print("  ✓ periodic_review_order")


# ── main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 32 Tests ===\n")
    test_distribution_fit()
    print()
    test_boolean_algebra()
    print()
    test_inventory()
    print("\n=== All Wave 32 tests passed! (72 assertions) ===")
