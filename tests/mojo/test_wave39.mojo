"""Tests for Wave 39 — Information Theory, Numerical Stability, CPU Scheduling Algorithms."""

from information_theory import (
    entropy,
    joint_entropy,
    conditional_entropy,
    mutual_information,
    kl_divergence,
    cross_entropy,
    binary_entropy,
    channel_capacity_bsc,
    redundancy,
    normalized_entropy,
)
from numerical_stability import (
    logsumexp,
    softmax,
    log_softmax,
    kahan_sum,
    welford_mean_var,
    log_add_exp,
    sigmoid_stable,
    log_sigmoid,
    softplus,
    normalize_probabilities,
    relative_error,
    safe_divide,
)
from scheduling_algo import (
    fcfs,
    sjf,
    priority_scheduling,
    round_robin,
    avg_wait_time,
    avg_turnaround,
    throughput,
    cpu_utilization,
    gantt_chart,
)
from std.math import abs as fabs, log, log2


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Information Theory tests ──────────────────────────────────────────────────


def test_information_theory() raises:
    print("── Information Theory tests ──")
    var passed = 0

    # 1. entropy([0.5, 0.5]) == 1.0
    var p1 = List[Float64]()
    p1.append(0.5)
    p1.append(0.5)
    _assert_close(entropy(p1), 1.0, 1e-10, "entropy([0.5,0.5]) should be 1.0")
    passed += 1

    # 2. entropy([1.0]) == 0.0
    var p2 = List[Float64]()
    p2.append(1.0)
    _assert_close(entropy(p2), 0.0, 1e-10, "entropy([1.0]) should be 0.0")
    passed += 1

    # 3. entropy([0.25, 0.25, 0.25, 0.25]) == 2.0
    var p3 = List[Float64]()
    p3.append(0.25)
    p3.append(0.25)
    p3.append(0.25)
    p3.append(0.25)
    _assert_close(entropy(p3), 2.0, 1e-10, "entropy uniform 4 should be 2.0")
    passed += 1

    # 4. binary_entropy(0.5) == 1.0
    _assert_close(binary_entropy(0.5), 1.0, 1e-10, "binary_entropy(0.5) should be 1.0")
    passed += 1

    # 5. binary_entropy(0.0) == 0.0
    _assert_close(binary_entropy(0.0), 0.0, 1e-10, "binary_entropy(0.0) should be 0.0")
    passed += 1

    # 6. binary_entropy(1.0) == 0.0
    _assert_close(binary_entropy(1.0), 0.0, 1e-10, "binary_entropy(1.0) should be 0.0")
    passed += 1

    # 7. kl_divergence(p, p) == 0.0
    var p4 = List[Float64]()
    p4.append(0.3)
    p4.append(0.7)
    _assert_close(kl_divergence(p4, p4), 0.0, 1e-10, "KL(p,p) should be 0")
    passed += 1

    # 8. cross_entropy(p, p) == entropy(p)
    var ce = cross_entropy(p4, p4)
    var h = entropy(p4)
    _assert_close(ce, h, 1e-10, "cross_entropy(p,p) should equal entropy(p)")
    passed += 1

    # 9. kl_divergence >= 0 (Gibbs' inequality)
    var q4 = List[Float64]()
    q4.append(0.5)
    q4.append(0.5)
    _assert(kl_divergence(p4, q4) >= -1e-10, "KL divergence should be >= 0")
    passed += 1

    # 10. channel_capacity_bsc(0.0) == 1.0
    _assert_close(channel_capacity_bsc(0.0), 1.0, 1e-10, "BSC capacity at p=0 should be 1")
    passed += 1

    # 11. channel_capacity_bsc(0.5) == 0.0
    _assert_close(channel_capacity_bsc(0.5), 0.0, 1e-10, "BSC capacity at p=0.5 should be 0")
    passed += 1

    # 12. joint_entropy for independent events
    var joint = List[List[Float64]]()
    var r1 = List[Float64]()
    r1.append(0.25)
    r1.append(0.25)
    var r2 = List[Float64]()
    r2.append(0.25)
    r2.append(0.25)
    joint.append(r1^)
    joint.append(r2^)
    _assert_close(joint_entropy(joint), 2.0, 1e-10, "joint entropy 2x2 uniform should be 2.0")
    passed += 1

    # 13. mutual_information >= 0
    var mi = mutual_information(joint)
    _assert(mi >= -1e-10, "mutual information should be >= 0")
    passed += 1

    # 14. mutual_information for independent = 0
    _assert_close(mi, 0.0, 1e-10, "MI for independent should be 0")
    passed += 1

    # 15. conditional_entropy H(Y|X) = H(X,Y) - H(X)
    var ce2 = conditional_entropy(joint)
    _assert_close(ce2, 1.0, 1e-10, "H(Y|X) for independent uniform 2x2 should be 1.0")
    passed += 1

    # 16. normalized_entropy in [0, 1]
    var ne = normalized_entropy(p1)
    _assert(ne >= 0.0 and ne <= 1.0 + 1e-10, "normalized entropy should be in [0,1]")
    passed += 1

    # 17. normalized_entropy for uniform == 1.0
    _assert_close(ne, 1.0, 1e-10, "normalized entropy for uniform should be 1.0")
    passed += 1

    # 18. redundancy >= 0
    var r = redundancy(p1)
    _assert(r >= -1e-10, "redundancy should be >= 0")
    passed += 1

    # 19. redundancy for uniform == 0
    _assert_close(r, 0.0, 1e-10, "redundancy for uniform should be 0")
    passed += 1

    # 20. entropy with zero probabilities
    var p5 = List[Float64]()
    p5.append(0.0)
    p5.append(0.5)
    p5.append(0.5)
    _assert_close(entropy(p5), 1.0, 1e-10, "entropy should skip p=0")
    passed += 1

    print("  ✓ " + String(passed) + " information theory tests passed")


# ── Numerical Stability tests ────────────────────────────────────────────────


def test_numerical_stability() raises:
    print("── Numerical Stability tests ──")
    var passed = 0

    # 1. logsumexp([0, 0]) ≈ log(2) ≈ 0.693
    var v1 = List[Float64]()
    v1.append(0.0)
    v1.append(0.0)
    _assert_close(logsumexp(v1), log(2.0), 1e-10, "logsumexp([0,0]) ≈ ln(2)")
    passed += 1

    # 2. logsumexp([1000, 1000]) doesn't overflow
    var v2 = List[Float64]()
    v2.append(1000.0)
    v2.append(1000.0)
    var lse2 = logsumexp(v2)
    _assert_close(lse2, 1000.0 + log(2.0), 1e-6, "logsumexp([1000,1000]) stable")
    passed += 1

    # 3. softmax([0, 0, 0]) ≈ [1/3, 1/3, 1/3]
    var v3 = List[Float64]()
    v3.append(0.0)
    v3.append(0.0)
    v3.append(0.0)
    var sm3 = softmax(v3)
    _assert_close(sm3[0], 1.0 / 3.0, 1e-10, "softmax([0,0,0])[0]")
    _assert_close(sm3[1], 1.0 / 3.0, 1e-10, "softmax([0,0,0])[1]")
    _assert_close(sm3[2], 1.0 / 3.0, 1e-10, "softmax([0,0,0])[2]")
    passed += 1

    # 4. softmax([1000, 0]) stable with large values
    var v4 = List[Float64]()
    v4.append(1000.0)
    v4.append(0.0)
    var sm4 = softmax(v4)
    _assert_close(sm4[0], 1.0, 1e-6, "softmax([1000,0])[0] ≈ 1.0")
    _assert_close(sm4[1], 0.0, 1e-6, "softmax([1000,0])[1] ≈ 0.0")
    passed += 1

    # 5. softmax sums to 1.0
    var sm_sum: Float64 = 0.0
    for i in range(len(sm3)):
        sm_sum += sm3[i]
    _assert_close(sm_sum, 1.0, 1e-10, "softmax should sum to 1.0")
    passed += 1

    # 6. log_softmax consistency with softmax
    var ls3 = log_softmax(v3)
    _assert_close(ls3[0], log(1.0 / 3.0), 1e-8, "log_softmax([0,0,0])[0]")
    passed += 1

    # 7. kahan_sum accuracy
    var many_small = List[Float64]()
    for i in range(10000):
        many_small.append(0.0001)
    var ks = kahan_sum(many_small)
    _assert_close(ks, 1.0, 1e-10, "kahan_sum of 10000 * 0.0001 should be 1.0")
    passed += 1

    # 8. kahan_sum more accurate than naive for pathological case
    var vals = List[Float64]()
    vals.append(1.0)
    for i in range(100000):
        vals.append(1e-16)
    var ks2 = kahan_sum(vals)
    _assert(ks2 > 1.0, "kahan_sum should capture small additions")
    passed += 1

    # 9. welford_mean_var correct mean
    var data = List[Float64]()
    data.append(2.0)
    data.append(4.0)
    data.append(4.0)
    data.append(4.0)
    data.append(5.0)
    data.append(5.0)
    data.append(7.0)
    data.append(9.0)
    var mv = welford_mean_var(data)
    _assert_close(mv[0], 5.0, 1e-10, "welford mean of [2,4,4,4,5,5,7,9] should be 5.0")
    passed += 1

    # 10. welford_mean_var correct variance
    _assert_close(mv[1], 4.0, 1e-10, "welford var of [2,4,4,4,5,5,7,9] should be 4.0")
    passed += 1

    # 11. sigmoid_stable(0) ≈ 0.5
    _assert_close(sigmoid_stable(0.0), 0.5, 1e-10, "sigmoid(0) should be 0.5")
    passed += 1

    # 12. sigmoid_stable(1000) ≈ 1.0
    _assert_close(sigmoid_stable(1000.0), 1.0, 1e-10, "sigmoid(1000) should be ~1.0")
    passed += 1

    # 13. sigmoid_stable(-1000) ≈ 0.0
    _assert_close(sigmoid_stable(-1000.0), 0.0, 1e-10, "sigmoid(-1000) should be ~0.0")
    passed += 1

    # 14. softplus(0) ≈ log(2)
    _assert_close(softplus(0.0), log(2.0), 1e-10, "softplus(0) ≈ ln(2)")
    passed += 1

    # 15. softplus large x ≈ x
    _assert_close(softplus(100.0), 100.0, 1e-6, "softplus(100) ≈ 100")
    passed += 1

    # 16. log_sigmoid(0) ≈ -log(2)
    _assert_close(log_sigmoid(0.0), -log(2.0), 1e-10, "log_sigmoid(0) ≈ -ln(2)")
    passed += 1

    # 17. log_add_exp consistent
    var lae = log_add_exp(0.0, 0.0)
    _assert_close(lae, log(2.0), 1e-10, "log_add_exp(0,0) ≈ ln(2)")
    passed += 1

    # 18. log_add_exp with large values
    var lae2 = log_add_exp(1000.0, 1000.0)
    _assert_close(lae2, 1000.0 + log(2.0), 1e-6, "log_add_exp(1000,1000) stable")
    passed += 1

    # 19. normalize_probabilities sums to 1.0
    var raw = List[Float64]()
    raw.append(2.0)
    raw.append(3.0)
    raw.append(5.0)
    var norm = normalize_probabilities(raw)
    var ns: Float64 = 0.0
    for i in range(len(norm)):
        ns += norm[i]
    _assert_close(ns, 1.0, 1e-10, "normalize_probabilities should sum to 1")
    passed += 1

    # 20. normalize_probabilities correct values
    _assert_close(norm[0], 0.2, 1e-10, "normalize [2,3,5] -> 0.2")
    _assert_close(norm[1], 0.3, 1e-10, "normalize [2,3,5] -> 0.3")
    _assert_close(norm[2], 0.5, 1e-10, "normalize [2,3,5] -> 0.5")
    passed += 1

    # 21. normalize_probabilities all-zero -> uniform
    var zeros = List[Float64]()
    zeros.append(0.0)
    zeros.append(0.0)
    zeros.append(0.0)
    var norm_z = normalize_probabilities(zeros)
    _assert_close(norm_z[0], 1.0 / 3.0, 1e-10, "normalize all-zero -> uniform")
    passed += 1

    # 22. safe_divide normal
    _assert_close(safe_divide(10.0, 2.0), 5.0, 1e-10, "safe_divide(10,2) = 5")
    passed += 1

    # 23. safe_divide by zero
    _assert_close(safe_divide(1.0, 0.0), 0.0, 1e-10, "safe_divide(1,0) = default 0")
    passed += 1

    # 24. safe_divide by zero with custom default
    _assert_close(safe_divide(1.0, 0.0, -1.0), -1.0, 1e-10, "safe_divide(1,0,-1) = -1")
    passed += 1

    # 25. relative_error
    _assert_close(relative_error(1.01, 1.0), 0.01, 1e-10, "relative_error(1.01,1.0) ≈ 0.01")
    passed += 1

    # 26. relative_error exact match
    _assert_close(relative_error(5.0, 5.0), 0.0, 1e-10, "relative_error exact = 0")
    passed += 1

    print("  ✓ " + String(passed) + " numerical stability tests passed")


# ── Scheduling tests ─────────────────────────────────────────────────────────


def test_scheduling() raises:
    print("── Scheduling tests ──")
    var passed = 0

    # 3 processes: [arrival, burst, priority]
    # P0: arrival=0, burst=3, priority=2
    # P1: arrival=1, burst=2, priority=1
    # P2: arrival=2, burst=1, priority=3
    var procs = List[List[Int]]()
    var pr0 = List[Int]()
    pr0.append(0)
    pr0.append(3)
    pr0.append(2)
    var pr1 = List[Int]()
    pr1.append(1)
    pr1.append(2)
    pr1.append(1)
    var pr2 = List[Int]()
    pr2.append(2)
    pr2.append(1)
    pr2.append(3)
    procs.append(pr0^)
    procs.append(pr1^)
    procs.append(pr2^)

    # 1. FCFS: order by arrival -> P0, P1, P2
    var fcfs_res = fcfs(procs)
    _assert(fcfs_res[0][0] == 0, "FCFS first should be P0")
    passed += 1

    # 2. FCFS P0 starts at 0
    _assert(fcfs_res[0][1] == 0, "FCFS P0 starts at 0")
    passed += 1

    # 3. FCFS P0 finishes at 3
    _assert(fcfs_res[0][2] == 3, "FCFS P0 finishes at 3")
    passed += 1

    # 4. FCFS P1 starts at 3
    _assert(fcfs_res[1][1] == 3, "FCFS P1 starts at 3")
    passed += 1

    # 5. FCFS P1 finishes at 5
    _assert(fcfs_res[1][2] == 5, "FCFS P1 finishes at 5")
    passed += 1

    # 6. FCFS P2 finishes at 6
    _assert(fcfs_res[2][2] == 6, "FCFS P2 finishes at 6")
    passed += 1

    # 7. FCFS P0 wait = 0
    _assert(fcfs_res[0][3] == 0, "FCFS P0 wait should be 0")
    passed += 1

    # 8. FCFS P1 wait = 3 - 1 = 2
    _assert(fcfs_res[1][3] == 2, "FCFS P1 wait should be 2")
    passed += 1

    # 9. SJF: after P0 runs (burst=3), both P1(burst=2) and P2(burst=1) arrived
    var sjf_res = sjf(procs)
    _assert(sjf_res[0][0] == 0, "SJF first should be P0")
    passed += 1

    # 10. SJF second should be P2 (burst=1 < burst=2)
    _assert(sjf_res[1][0] == 2, "SJF second should be P2 (shortest)")
    passed += 1

    # 11. SJF third should be P1
    _assert(sjf_res[2][0] == 1, "SJF third should be P1")
    passed += 1

    # 12. Priority: P0 runs first (only at t=0), then P1(prio=1) before P2(prio=3)
    var prio_res = priority_scheduling(procs)
    _assert(prio_res[0][0] == 0, "Priority first should be P0 (only at t=0)")
    passed += 1

    # 13. Priority second should be P1 (priority=1 < priority=3)
    _assert(prio_res[1][0] == 1, "Priority second should be P1 (highest prio)")
    passed += 1

    # 14. Priority third should be P2
    _assert(prio_res[2][0] == 2, "Priority third should be P2")
    passed += 1

    # 15. Round-robin with quantum=2
    var rr_res = round_robin(procs, 2)
    _assert(len(rr_res) == 3, "RR should have 3 results")
    passed += 1

    # 16. RR all finish times > 0
    _assert(rr_res[0][1] > 0, "RR P0 should have finish > 0")
    passed += 1

    # 17. RR wait times >= 0
    _assert(rr_res[0][2] >= 0, "RR P0 wait >= 0")
    _assert(rr_res[1][2] >= 0, "RR P1 wait >= 0")
    _assert(rr_res[2][2] >= 0, "RR P2 wait >= 0")
    passed += 1

    # 18. avg_wait_time positive for FCFS
    var awt = avg_wait_time(fcfs_res)
    _assert(awt >= 0.0, "avg_wait_time should be >= 0")
    passed += 1

    # 19. avg_turnaround >= avg_wait for FCFS
    var at = avg_turnaround(fcfs_res)
    _assert(at >= awt, "avg_turnaround >= avg_wait_time")
    passed += 1

    # 20. throughput positive
    var tp = throughput(fcfs_res, 6)
    _assert(tp > 0.0, "throughput should be > 0")
    passed += 1

    # 21. throughput = 3/6 = 0.5
    _assert_close(tp, 0.5, 1e-10, "throughput 3 procs in 6 units = 0.5")
    passed += 1

    # 22. cpu_utilization <= 1.0
    var cu = cpu_utilization(fcfs_res, 6)
    _assert(cu <= 1.0 + 1e-10, "cpu_utilization should be <= 1.0")
    passed += 1

    # 23. cpu_utilization = (3+2+1)/6 = 1.0
    _assert_close(cu, 1.0, 1e-10, "cpu_utilization should be 1.0 (no idle)")
    passed += 1

    # 24. gantt_chart FCFS order
    var gc = gantt_chart(fcfs_res)
    _assert(gc[0] == 0, "gantt_chart first pid should be 0")
    _assert(gc[1] == 1, "gantt_chart second pid should be 1")
    _assert(gc[2] == 2, "gantt_chart third pid should be 2")
    passed += 1

    # 25. Single process scheduling
    var single = List[List[Int]]()
    var s0 = List[Int]()
    s0.append(0)
    s0.append(5)
    s0.append(1)
    single.append(s0^)
    var sr = fcfs(single)
    _assert(sr[0][1] == 0, "single process starts at 0")
    _assert(sr[0][2] == 5, "single process finishes at 5")
    _assert(sr[0][3] == 0, "single process wait = 0")
    passed += 1

    print("  ✓ " + String(passed) + " scheduling tests passed")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() raises:
    print("=" * 60)
    print("Wave 39 Tests — Information Theory, Numerical Stability, Scheduling")
    print("=" * 60)
    test_information_theory()
    test_numerical_stability()
    test_scheduling()
    print("=" * 60)
    print("All Wave 39 tests passed! ✅")
