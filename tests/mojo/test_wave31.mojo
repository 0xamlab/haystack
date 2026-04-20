"""Tests for Wave 31 — Convex Optimization, Survival Analysis, Currency Math."""

from convex import (
    eval_function,
    compute_gradient,
    l2_norm,
    vector_sub,
    proximal_l1,
    line_search_backtrack,
    gradient_descent,
    projected_gradient_descent,
    adam_optimizer,
)
from survival import (
    SurvivalPoint,
    kaplan_meier,
    nelson_aalen,
    median_survival,
    log_rank_statistic,
    hazard_rate,
    restricted_mean,
    life_table,
    survival_at_time,
)
from currency import (
    round_currency,
    compound_interest,
    continuous_compound,
    amortization_payment,
    amortization_schedule,
    present_value,
    present_value_annuity,
    future_value_annuity,
    effective_annual_rate,
    discount_factor,
    rule_of_72,
    loan_balance_after,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helper: build float lists ───────────────────────────────────────────────


fn _lf2(a: Float64, b: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a); v.append(b)
    return v^


fn _lf3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a); v.append(b); v.append(c)
    return v^


fn _lf4(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a); v.append(b); v.append(c); v.append(d)
    return v^


fn _lb(vals: List[Bool]) -> List[Bool]:
    return List[Bool](copy=vals)


# ── Convex Optimization tests ───────────────────────────────────────────────


fn test_eval_function_quadratic() raises:
    var x = _lf2(0.0, 0.0)
    _assert_close(eval_function(x, 0), 0.0, 1e-12, "eval_function([0,0], 0)")
    print("  ✓ eval_function([0,0], quadratic) == 0")

    var x2 = _lf2(3.0, 4.0)
    _assert_close(eval_function(x2, 0), 25.0, 1e-12, "eval_function([3,4], 0)")
    print("  ✓ eval_function([3,4], quadratic) == 25")


fn test_eval_function_rosenbrock() raises:
    var x = _lf2(1.0, 1.0)
    _assert_close(eval_function(x, 1), 0.0, 1e-12, "Rosenbrock at [1,1]")
    print("  ✓ eval_function([1,1], Rosenbrock) == 0")


fn test_compute_gradient_quadratic() raises:
    var x = _lf2(0.0, 0.0)
    var g = compute_gradient(x, 0)
    _assert_close(g[0], 0.0, 1e-12, "grad[0] at origin")
    _assert_close(g[1], 0.0, 1e-12, "grad[1] at origin")
    print("  ✓ compute_gradient([0,0], quadratic) == [0,0]")

    var x2 = _lf2(3.0, -2.0)
    var g2 = compute_gradient(x2, 0)
    _assert_close(g2[0], 6.0, 1e-12, "grad[0]=6")
    _assert_close(g2[1], -4.0, 1e-12, "grad[1]=-4")
    print("  ✓ compute_gradient([3,-2], quadratic) == [6,-4]")


fn test_l2_norm() raises:
    var x = _lf2(3.0, 4.0)
    _assert_close(l2_norm(x), 5.0, 1e-12, "l2_norm([3,4])")
    print("  ✓ l2_norm([3,4]) == 5.0")

    var z = _lf2(0.0, 0.0)
    _assert_close(l2_norm(z), 0.0, 1e-12, "l2_norm([0,0])")
    print("  ✓ l2_norm([0,0]) == 0.0")


fn test_vector_sub() raises:
    var a = _lf3(5.0, 3.0, 1.0)
    var b = _lf3(1.0, 2.0, 3.0)
    var c = vector_sub(a, b)
    _assert_close(c[0], 4.0, 1e-12, "vsub[0]")
    _assert_close(c[1], 1.0, 1e-12, "vsub[1]")
    _assert_close(c[2], -2.0, 1e-12, "vsub[2]")
    print("  ✓ vector_sub([5,3,1], [1,2,3]) == [4,1,-2]")


fn test_proximal_l1() raises:
    var x = _lf3(0.5, -0.5, 2.0)
    var result = proximal_l1(x, 1.0)
    _assert_close(result[0], 0.0, 1e-12, "prox[0]")
    _assert_close(result[1], 0.0, 1e-12, "prox[1]")
    _assert_close(result[2], 1.0, 1e-12, "prox[2]")
    print("  ✓ proximal_l1([0.5,-0.5,2.0], 1.0) == [0,0,1]")

    var x2 = _lf2(3.0, -3.0)
    var r2 = proximal_l1(x2, 0.5)
    _assert_close(r2[0], 2.5, 1e-12, "prox_l1 shrink positive")
    _assert_close(r2[1], -2.5, 1e-12, "prox_l1 shrink negative")
    print("  ✓ proximal_l1([3,-3], 0.5) == [2.5,-2.5]")


fn test_gradient_descent_quadratic() raises:
    var x0 = _lf2(5.0, 5.0)
    var result = gradient_descent(x0, 0.1, 1000, 1e-8, 0)
    _assert_close(result[0], 0.0, 1e-4, "GD x[0]")
    _assert_close(result[1], 0.0, 1e-4, "GD x[1]")
    print("  ✓ gradient_descent([5,5]) ≈ [0,0] for quadratic")


fn test_gradient_descent_converges() raises:
    var x0 = _lf2(10.0, -10.0)
    var result = gradient_descent(x0, 0.1, 2000, 1e-10, 0)
    var fval = eval_function(result, 0)
    _assert(fval < 1e-6, "GD should converge to near-zero objective")
    print("  ✓ gradient_descent from [10,-10] converges (f=" + String(fval) + ")")


fn test_projected_gradient_descent() raises:
    var x0 = _lf2(5.0, 5.0)
    var result = projected_gradient_descent(x0, 0.1, 1000, 1.0, 3.0, 0)
    # Result should be within bounds [1, 3]
    _assert(result[0] >= 1.0 - 1e-10, "PGD x[0] >= lower")
    _assert(result[0] <= 3.0 + 1e-10, "PGD x[0] <= upper")
    _assert(result[1] >= 1.0 - 1e-10, "PGD x[1] >= lower")
    _assert(result[1] <= 3.0 + 1e-10, "PGD x[1] <= upper")
    # For quadratic, optimal within [1,3] is at lower bound
    _assert_close(result[0], 1.0, 1e-4, "PGD x[0] at lower bound")
    _assert_close(result[1], 1.0, 1e-4, "PGD x[1] at lower bound")
    print("  ✓ projected_gradient_descent within bounds [1,3]")


fn test_adam_optimizer() raises:
    var x0 = _lf2(5.0, 5.0)
    var result = adam_optimizer(x0, 0.1, 1000, 0)
    _assert(fabs(result[0]) < 0.5, "Adam x[0] near 0")
    _assert(fabs(result[1]) < 0.5, "Adam x[1] near 0")
    print("  ✓ adam_optimizer([5,5]) converges near [0,0]")


fn test_line_search() raises:
    var x = _lf2(5.0, 5.0)
    var g = compute_gradient(x, 0)
    var step = line_search_backtrack(x, g, 0)
    _assert(step > 0.0, "line_search step > 0")
    _assert(step <= 1.0, "line_search step <= 1")
    print("  ✓ line_search_backtrack returns valid step (" + String(step) + ")")


# ── Survival Analysis tests ─────────────────────────────────────────────────


fn test_kaplan_meier_basic() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.0); times.append(3.0)
    times.append(4.0); times.append(5.0)
    var events = List[Bool]()
    events.append(True); events.append(True); events.append(True)
    events.append(True); events.append(True)

    var km = kaplan_meier(times, events)
    # First point should be (0, 1.0)
    _assert_close(km[0].time, 0.0, 1e-12, "KM t=0")
    _assert_close(km[0].survival, 1.0, 1e-12, "KM S(0)=1")
    print("  ✓ kaplan_meier first point S=1.0 at t=0")

    # Survival should decrease
    _assert(km[1].survival < km[0].survival, "KM survival decreases")
    print("  ✓ kaplan_meier survival decreases over time")

    # With 5 subjects all dying: S(1)=4/5, S(2)=3/5, etc.
    _assert_close(km[1].survival, 0.8, 1e-12, "KM S(1)=0.8")
    _assert_close(km[2].survival, 0.6, 1e-12, "KM S(2)=0.6")
    _assert_close(km[3].survival, 0.4, 1e-12, "KM S(3)=0.4")
    print("  ✓ kaplan_meier values correct: 0.8, 0.6, 0.4...")


fn test_kaplan_meier_censored() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.0); times.append(3.0)
    times.append(4.0); times.append(5.0)
    var events = List[Bool]()
    events.append(True); events.append(False); events.append(True)
    events.append(False); events.append(False)

    var km = kaplan_meier(times, events)
    _assert_close(km[0].survival, 1.0, 1e-12, "KM censored S(0)")
    # With censoring at end, S should stay above 0
    _assert(km[len(km) - 1].survival > 0.0, "KM with censoring ends > 0")
    print("  ✓ kaplan_meier with censoring")


fn test_median_survival() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.0); times.append(3.0)
    times.append(4.0); times.append(5.0)
    var events = List[Bool]()
    events.append(True); events.append(True); events.append(True)
    events.append(True); events.append(True)

    var km = kaplan_meier(times, events)
    var med = median_survival(km)
    # S drops below 0.5 at t=3 (S(3)=0.4)
    _assert_close(med, 3.0, 1e-12, "median_survival == 3.0")
    print("  ✓ median_survival == 3.0")


fn test_nelson_aalen() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.0); times.append(3.0)
    var events = List[Bool]()
    events.append(True); events.append(True); events.append(True)

    var na = nelson_aalen(times, events)
    # Cumulative hazard should increase
    _assert(len(na) >= 2, "nelson_aalen has entries")
    _assert(na[1][1] > na[0][1], "cumulative hazard increases")
    var last = na[len(na) - 1].copy()
    _assert(last[1] > na[1][1], "cumulative hazard keeps increasing")
    print("  ✓ nelson_aalen cumulative hazard increases")


fn test_survival_at_time() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.0); times.append(3.0)
    times.append(4.0); times.append(5.0)
    var events = List[Bool]()
    events.append(True); events.append(True); events.append(True)
    events.append(True); events.append(True)

    var km = kaplan_meier(times, events)
    var s0 = survival_at_time(km, 0.0)
    _assert_close(s0, 1.0, 1e-12, "S(0) == 1.0")
    print("  ✓ survival_at_time(0) == 1.0")

    var s1_5 = survival_at_time(km, 1.5)
    _assert_close(s1_5, 0.8, 1e-12, "S(1.5) == 0.8 (step function)")
    print("  ✓ survival_at_time(1.5) == 0.8")


fn test_restricted_mean() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.0); times.append(3.0)
    times.append(4.0); times.append(5.0)
    var events = List[Bool]()
    events.append(True); events.append(True); events.append(True)
    events.append(True); events.append(True)

    var km = kaplan_meier(times, events)
    var rmst = restricted_mean(km, 5.0)
    _assert(rmst > 0.0, "RMST > 0")
    # Area under step function: 1.0*1 + 0.8*1 + 0.6*1 + 0.4*1 + 0.2*1 = 3.0
    _assert_close(rmst, 3.0, 0.1, "RMST ≈ 3.0")
    print("  ✓ restricted_mean > 0 (" + String(rmst) + ")")


fn test_log_rank_statistic() raises:
    # Group 1: faster failures
    var t1 = List[Float64]()
    t1.append(1.0); t1.append(2.0); t1.append(3.0)
    var e1 = List[Bool]()
    e1.append(True); e1.append(True); e1.append(True)

    # Group 2: slower failures
    var t2 = List[Float64]()
    t2.append(4.0); t2.append(5.0); t2.append(6.0)
    var e2 = List[Bool]()
    e2.append(True); e2.append(True); e2.append(True)

    var stat = log_rank_statistic(t1, e1, t2, e2)
    _assert(stat >= 0.0, "log_rank >= 0")
    _assert(stat < 1e10, "log_rank finite")
    print("  ✓ log_rank_statistic finite (" + String(stat) + ")")


fn test_life_table() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.5); times.append(3.0)
    times.append(4.5); times.append(6.0)
    var events = List[Bool]()
    events.append(True); events.append(True); events.append(True)
    events.append(True); events.append(True)

    var intervals = List[Float64]()
    intervals.append(0.0); intervals.append(3.0); intervals.append(6.0)

    var lt = life_table(times, events, intervals)
    _assert(len(lt) == 3, "life_table has 3 intervals")
    # First interval [0, 3): n_risk=5, n_event=2 (t=1 and t=2.5)
    _assert_close(lt[0][0], 0.0, 1e-12, "interval start=0")
    _assert_close(lt[0][1], 5.0, 1e-12, "n_risk=5")
    _assert_close(lt[0][2], 2.0, 1e-12, "n_event=2 in [0,3)")
    print("  ✓ life_table correct interval counts")


fn test_hazard_rate() raises:
    var times = List[Float64]()
    times.append(1.0); times.append(2.0); times.append(3.0)
    times.append(4.0); times.append(5.0)
    var events = List[Bool]()
    events.append(True); events.append(True); events.append(True)
    events.append(True); events.append(True)

    var hr = hazard_rate(times, events, 2.0)
    _assert(len(hr) > 0, "hazard_rate has entries")
    _assert(hr[0][1] > 0.0, "hazard rate > 0")
    print("  ✓ hazard_rate returns positive values")


# ── Currency Math tests ──────────────────────────────────────────────────────


fn test_round_currency() raises:
    _assert_close(round_currency(1.235, 2), 1.24, 1e-10, "round 1.235")
    print("  ✓ round_currency(1.235, 2) ≈ 1.24")

    _assert_close(round_currency(1.456, 2), 1.46, 1e-10, "round 1.456")
    print("  ✓ round_currency(1.456, 2) ≈ 1.46")

    _assert_close(round_currency(99.999, 0), 100.0, 1e-10, "round to 0 dec")
    print("  ✓ round_currency(99.999, 0) ≈ 100")


fn test_compound_interest() raises:
    var fv = compound_interest(1000.0, 0.05, 10)
    _assert_close(fv, 1628.89, 0.01, "compound_interest(1000, 0.05, 10)")
    print("  ✓ compound_interest(1000, 0.05, 10) ≈ 1628.89")


fn test_continuous_compound() raises:
    var fv = continuous_compound(1000.0, 0.05, 10.0)
    _assert_close(fv, 1648.72, 0.01, "continuous_compound(1000, 0.05, 10)")
    print("  ✓ continuous_compound(1000, 0.05, 10) ≈ 1648.72")


fn test_amortization_payment() raises:
    var pmt = amortization_payment(100000.0, 0.005, 360)
    _assert_close(pmt, 599.55, 0.01, "amort_pmt(100k, 0.5%, 360)")
    print("  ✓ amortization_payment(100000, 0.005, 360) ≈ 599.55")


fn test_present_value() raises:
    var pv = present_value(1000.0, 0.05, 5)
    _assert_close(pv, 783.53, 0.01, "PV(1000, 0.05, 5)")
    print("  ✓ present_value(1000, 0.05, 5) ≈ 783.53")


fn test_effective_annual_rate() raises:
    var ear = effective_annual_rate(0.12, 12)
    _assert_close(ear, 0.1268, 0.001, "EAR(0.12, 12)")
    print("  ✓ effective_annual_rate(0.12, 12) ≈ 0.1268")


fn test_rule_of_72() raises:
    var years = rule_of_72(0.06)
    _assert_close(years, 12.0, 1e-10, "rule_of_72(0.06)")
    print("  ✓ rule_of_72(0.06) == 12.0")


fn test_discount_factor() raises:
    var df = discount_factor(0.05, 1)
    _assert_close(df, 0.9524, 0.001, "DF(0.05, 1)")
    print("  ✓ discount_factor(0.05, 1) ≈ 0.9524")

    var df10 = discount_factor(0.05, 10)
    _assert(df10 < df, "DF decreases with more periods")
    print("  ✓ discount_factor decreases with periods")


fn test_amortization_schedule() raises:
    var sched = amortization_schedule(100000.0, 0.005, 360)
    _assert(len(sched) == 360, "schedule has 360 periods")
    # Final balance should be ~0
    var final_bal = sched[359][3]
    _assert(fabs(final_bal) < 0.01, "final balance ≈ 0, got " + String(final_bal))
    print("  ✓ amortization_schedule final balance ≈ 0")

    # First payment: interest = 100000 * 0.005 = 500
    _assert_close(sched[0][1], 500.0, 0.01, "first interest = 500")
    print("  ✓ amortization_schedule first interest = 500")


fn test_present_value_annuity() raises:
    var pva = present_value_annuity(100.0, 0.05, 10)
    # PVA = 100 * (1 - 1.05^-10) / 0.05 ≈ 772.17
    _assert_close(pva, 772.17, 0.1, "PVA(100, 0.05, 10)")
    print("  ✓ present_value_annuity(100, 0.05, 10) ≈ 772.17")


fn test_future_value_annuity() raises:
    var fva = future_value_annuity(100.0, 0.05, 10)
    # FVA = 100 * (1.05^10 - 1) / 0.05 ≈ 1257.79
    _assert_close(fva, 1257.79, 0.1, "FVA(100, 0.05, 10)")
    print("  ✓ future_value_annuity(100, 0.05, 10) ≈ 1257.79")


fn test_loan_balance_after() raises:
    var bal = loan_balance_after(100000.0, 0.005, 360, 360)
    _assert(fabs(bal) < 0.01, "loan_balance_after full term ≈ 0")
    print("  ✓ loan_balance_after(100000, 0.005, 360, 360) ≈ 0")

    var bal_half = loan_balance_after(100000.0, 0.005, 360, 180)
    _assert(bal_half > 0.0, "balance after 180 payments > 0")
    _assert(bal_half < 100000.0, "balance after 180 payments < principal")
    print("  ✓ loan_balance_after 180 payments: " + String(bal_half))


fn test_compound_vs_continuous() raises:
    # Continuous compounding always yields more than discrete
    var discrete = compound_interest(1000.0, 0.10, 5)
    var continuous = continuous_compound(1000.0, 0.10, 5.0)
    _assert(continuous > discrete, "continuous > discrete compounding")
    print("  ✓ continuous_compound > compound_interest")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=" * 60)
    print("Wave 31 — Convex Optimization, Survival Analysis, Currency Math")
    print("=" * 60)

    print("\n── Convex Optimization tests ──")
    test_eval_function_quadratic()          # 2 assertions
    test_eval_function_rosenbrock()         # 1
    test_compute_gradient_quadratic()       # 4
    test_l2_norm()                          # 2
    test_vector_sub()                       # 3
    test_proximal_l1()                      # 5
    test_gradient_descent_quadratic()       # 2
    test_gradient_descent_converges()       # 1
    test_projected_gradient_descent()       # 6
    test_adam_optimizer()                    # 2
    test_line_search()                      # 2

    print("\n── Survival Analysis tests ──")
    test_kaplan_meier_basic()               # 6
    test_kaplan_meier_censored()            # 2
    test_median_survival()                  # 1
    test_nelson_aalen()                     # 3
    test_survival_at_time()                 # 2
    test_restricted_mean()                  # 2
    test_log_rank_statistic()               # 2
    test_life_table()                       # 4
    test_hazard_rate()                      # 2

    print("\n── Currency Math tests ──")
    test_round_currency()                   # 3
    test_compound_interest()                # 1
    test_continuous_compound()              # 1
    test_amortization_payment()             # 1
    test_present_value()                    # 1
    test_effective_annual_rate()            # 1
    test_rule_of_72()                       # 1
    test_discount_factor()                  # 2
    test_amortization_schedule()            # 3
    test_present_value_annuity()            # 1
    test_future_value_annuity()             # 1
    test_loan_balance_after()               # 3
    test_compound_vs_continuous()           # 1

    print("\n" + "=" * 60)
    print("Wave 31 — ALL TESTS PASSED ✅  (66 assertions)")
    print("=" * 60)
