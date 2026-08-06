"""Wave 16 test suite — Probability, Multi-Objective Optimization, Scheduler."""

from probability import (
    bayes,
    joint_probability,
    total_probability,
    factorial,
    combinations,
    permutations,
    binomial_pmf,
    poisson_pmf,
    entropy,
    kl_divergence,
    mutual_information,
)
from multi_objective import (
    is_dominated,
    pareto_front,
    weighted_score,
    normalize_objectives,
    ideal_point,
    nadir_point,
    topsis_rank,
)
from scheduler import Task, CriticalPathResult, Scheduler
from std.math import abs as fabs


def assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + msg)


def _int_list1(v0: Int) -> List[Int]:
    var l = List[Int]()
    l.append(v0)
    return l^


def _int_list2(v0: Int, v1: Int) -> List[Int]:
    var l = List[Int]()
    l.append(v0)
    l.append(v1)
    return l^


def _int_list3(v0: Int, v1: Int, v2: Int) -> List[Int]:
    var l = List[Int]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    return l^


def _float_list2(v0: Float64, v1: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    return l^


def _float_list3(v0: Float64, v1: Float64, v2: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    return l^


def _bool_list2(v0: Bool, v1: Bool) -> List[Bool]:
    var l = List[Bool]()
    l.append(v0)
    l.append(v1)
    return l^


def main() raises:
    print("━━━ Wave 16 test suite (Probability, Multi-Objective, Scheduler) ━━━\n")

    # ── Probability ──

    # Bayes: P(disease|positive) with P(disease)=0.01, P(positive|disease)=0.95, P(positive)=0.05
    var posterior = bayes(0.01, 0.95, 0.05)
    assert_true(fabs(posterior - 0.19) < 0.01, "Bayes: P(disease|positive) ≈ 0.19")

    # Joint probability
    var jp = joint_probability(0.3, 0.8)
    assert_true(fabs(jp - 0.24) < 0.01, "Joint: P(A∩B) = 0.3 * 0.8 = 0.24")

    # Total probability
    var priors = _float_list2(0.01, 0.99)
    var likelihoods = _float_list2(0.95, 0.04)
    var tp = total_probability(priors, likelihoods)
    assert_true(fabs(tp - 0.0491) < 0.001, "Total probability ≈ 0.0491")

    # Factorial
    assert_true(fabs(factorial(5) - 120.0) < 0.1, "5! = 120")
    assert_true(fabs(factorial(0) - 1.0) < 0.1, "0! = 1")
    assert_true(fabs(factorial(1) - 1.0) < 0.1, "1! = 1")

    # Combinations
    assert_true(fabs(combinations(10, 3) - 120.0) < 0.1, "C(10,3) = 120")
    assert_true(fabs(combinations(5, 0) - 1.0) < 0.1, "C(5,0) = 1")
    assert_true(fabs(combinations(5, 5) - 1.0) < 0.1, "C(5,5) = 1")

    # Permutations
    assert_true(fabs(permutations(5, 3) - 60.0) < 0.1, "P(5,3) = 60")
    assert_true(fabs(permutations(4, 4) - 24.0) < 0.1, "P(4,4) = 24")

    # Binomial PMF: P(X=3) for Binomial(5, 0.5) = C(5,3) * 0.5^3 * 0.5^2 = 10 * 0.03125 = 0.3125
    var binom = binomial_pmf(3, 5, 0.5)
    assert_true(fabs(binom - 0.3125) < 0.001, "Binomial PMF: P(X=3|n=5,p=0.5) ≈ 0.3125")

    # Poisson PMF: P(X=2) for Poisson(3) = 9*exp(-3)/2 ≈ 0.2240
    var pois = poisson_pmf(2, 3.0)
    assert_true(fabs(pois - 0.2240) < 0.01, "Poisson PMF: P(X=2|λ=3) ≈ 0.224")

    # Entropy of fair coin: H = log2(2) = 1 bit
    var fair = _float_list2(0.5, 0.5)
    assert_true(fabs(entropy(fair) - 1.0) < 0.01, "Entropy of fair coin = 1 bit")

    # Entropy of certain outcome: H = 0 bits
    var certain = _float_list2(1.0, 0.0)
    assert_true(fabs(entropy(certain)) < 0.01, "Entropy of certain outcome = 0 bits")

    # KL divergence: same distribution => 0
    var p1 = _float_list2(0.5, 0.5)
    var q1 = _float_list2(0.5, 0.5)
    assert_true(fabs(kl_divergence(p1, q1)) < 0.01, "KL(P||P) = 0")

    # KL divergence: different distributions
    var p2 = _float_list2(0.9, 0.1)
    var q2 = _float_list2(0.5, 0.5)
    var kl = kl_divergence(p2, q2)
    assert_true(kl > 0.0, "KL(P||Q) > 0 for different distributions")

    # Mutual information: independent vars => MI = 0
    var joint_indep = List[List[Float64]]()
    joint_indep.append(_float_list2(0.25, 0.25))
    joint_indep.append(_float_list2(0.25, 0.25))
    assert_true(fabs(mutual_information(joint_indep)) < 0.01, "MI of independent = 0")

    print("✅ Probability")

    # ── Multi-objective ──

    # 3 solutions with 2 objectives (both maximize)
    var objs = List[List[Float64]]()
    objs.append(_float_list2(5.0, 3.0))
    objs.append(_float_list2(8.0, 7.0))
    objs.append(_float_list2(3.0, 9.0))
    var max_flags = _bool_list2(True, True)
    var front = pareto_front(objs, max_flags)
    assert_true(len(front) == 2, "Pareto front has 2 solutions")
    # Solutions 1 and 2 should be on the front (0 is dominated by 1)
    assert_true(front[0] == 1, "Pareto front includes solution 1")
    assert_true(front[1] == 2, "Pareto front includes solution 2")

    # is_dominated: solution 0 is dominated by solution 1
    var dom_a = _float_list2(5.0, 3.0)
    var dom_b = _float_list2(8.0, 7.0)
    assert_true(is_dominated(dom_a, dom_b, max_flags), "Solution (5,3) dominated by (8,7)")
    assert_true(not is_dominated(dom_b, dom_a, max_flags), "Solution (8,7) NOT dominated by (5,3)")

    # Weighted score
    var vals = _float_list2(0.8, 0.6)
    var wts = _float_list2(0.7, 0.3)
    var ws = weighted_score(vals, wts)
    assert_true(fabs(ws - 0.74) < 0.01, "Weighted score: 0.8*0.7 + 0.6*0.3 = 0.74")

    # Normalize objectives
    var norm_objs = List[List[Float64]]()
    norm_objs.append(_float_list2(1.0, 10.0))
    norm_objs.append(_float_list2(5.0, 20.0))
    norm_objs.append(_float_list2(3.0, 15.0))
    var normed = normalize_objectives(norm_objs)
    assert_true(fabs(normed[0][0] - 0.0) < 0.01, "Normalize: min maps to 0")
    assert_true(fabs(normed[1][0] - 1.0) < 0.01, "Normalize: max maps to 1")
    assert_true(fabs(normed[2][0] - 0.5) < 0.01, "Normalize: mid maps to 0.5")

    # Ideal and nadir points
    var ip = ideal_point(objs, max_flags)
    assert_true(fabs(ip[0] - 8.0) < 0.01, "Ideal obj0 = 8 (max)")
    assert_true(fabs(ip[1] - 9.0) < 0.01, "Ideal obj1 = 9 (max)")
    var np_val = nadir_point(objs, max_flags)
    assert_true(fabs(np_val[0] - 3.0) < 0.01, "Nadir obj0 = 3 (min for max obj)")
    assert_true(fabs(np_val[1] - 3.0) < 0.01, "Nadir obj1 = 3 (min for max obj)")

    # TOPSIS
    var topsis_alts = List[List[Float64]]()
    topsis_alts.append(_float_list2(5.0, 3.0))
    topsis_alts.append(_float_list2(8.0, 7.0))
    topsis_alts.append(_float_list2(3.0, 9.0))
    var topsis_w = _float_list2(0.5, 0.5)
    var topsis_scores = topsis_rank(topsis_alts, topsis_w, max_flags)
    assert_true(len(topsis_scores) == 3, "TOPSIS: 3 scores")
    # Solution 1 (8,7) should have highest score
    assert_true(topsis_scores[1] > topsis_scores[0], "TOPSIS: solution 1 > solution 0")

    print("✅ Multi-objective (Pareto)")

    # ── Scheduler ──
    var sched = Scheduler()
    sched.add_task("compile", 1, 100, List[Int]())
    sched.add_task("test", 2, 50, _int_list1(0))      # depends on compile
    sched.add_task("deploy", 3, 30, _int_list1(1))     # depends on test
    sched.add_task("notify", 1, 10, _int_list1(2))     # depends on deploy
    var order = sched.schedule()
    assert_true(order[0] == 0, "Schedule: compile first")
    assert_true(order[1] == 1, "Schedule: test second")
    assert_true(order[2] == 2, "Schedule: deploy third")
    assert_true(order[3] == 3, "Schedule: notify last")

    # Critical path
    var cp = sched.critical_path()
    assert_true(cp.total_time == 190, "Critical path time: 100+50+30+10 = 190")
    assert_true(len(cp.path) == 4, "Critical path has 4 tasks")

    # Total estimated time
    assert_true(sched.total_estimated_time() == 190, "Total estimated: 190ms")

    # can_run / mark_complete / get_ready_tasks
    var ready = sched.get_ready_tasks()
    assert_true(len(ready) == 1, "Initially only 1 task ready")
    assert_true(ready[0] == 0, "Compile is ready")
    assert_true(sched.can_run(0), "Can run compile")
    assert_true(not sched.can_run(1), "Cannot run test yet")

    sched.mark_complete(0)
    var ready2 = sched.get_ready_tasks()
    assert_true(len(ready2) == 1, "After compile done: 1 task ready")
    assert_true(ready2[0] == 1, "Test is now ready")
    assert_true(sched.can_run(1), "Can run test after compile done")

    sched.mark_complete(1)
    sched.mark_complete(2)
    sched.mark_complete(3)
    var ready3 = sched.get_ready_tasks()
    assert_true(len(ready3) == 0, "All done: no tasks ready")

    # Test with parallel tasks
    var sched2 = Scheduler()
    sched2.add_task("init", 1, 50, List[Int]())
    sched2.add_task("task_a", 3, 100, _int_list1(0))    # depends on init, high priority
    sched2.add_task("task_b", 2, 80, _int_list1(0))     # depends on init, medium priority
    sched2.add_task("task_c", 1, 60, _int_list1(0))     # depends on init, low priority
    sched2.add_task("final", 1, 20, _int_list3(1, 2, 3))  # depends on all three
    var order2 = sched2.schedule()
    assert_true(order2[0] == 0, "Parallel: init first")
    # After init, task_a (priority 3) should come first
    assert_true(order2[1] == 1, "Parallel: task_a (priority 3) runs first")
    assert_true(order2[4] == 4, "Parallel: final runs last")

    print("✅ Scheduler")

    print("\n✅ All Wave 16 tests passed")
