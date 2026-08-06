"""test_optimization_scheduling.mojo — known-value tests for job-shop tabu search and RCPSP.

Hand-written. Every number asserted below was computed with pen and paper, or by exhaustion
over a space small enough to enumerate, BEFORE the code ran.

The load-bearing tests, and why each is worth its lines
------------------------------------------------------
1. The 2x2 job shop is solved TWICE by different means. `jobshop_schedule_from_ranks_flat`
   evaluates all FOUR disjunctive orientations one by one — 11, 7, cyclic, 11 — which is the
   whole feasible space, so the optimum is 7 by exhaustion and not by trusting a heuristic.
   The tabu search must return exactly that, and the lower bound (max(job chain 6, machine
   load 7) = 7) must MEET it, which is the only circumstance under which anything here is
   allowed to say "optimal".
2. The 3-job permutation flow shop is the honesty test. Its optimum is 8 — three 2-unit
   operations must pass through M0 (6) and the last one still needs its 2 on M1 — and the
   search finds 8. Its lower bound is only 6, so the driver reports `gap = 2` and
   `optimal_by_bound = False` while holding an optimal schedule. A heuristic that upgraded
   "I found the best one" to "this is the best one" would pass a weaker test and be wrong.
3. The cyclic orientation (`rank = [1, 0, 1, 0]`) is the failure a disjunctive flip creates.
   The DP over that graph terminates and would return a finite makespan; the test requires
   `SCHED_PRECEDENCE_CYCLE`, an empty schedule and NO makespan.
4. Determinism is asserted in both directions on both solvers: the same seed reproduces
   bit-identical start times, ranks, makespan AND search counters, and a different seed
   produces a different schedule. One direction alone is worthless — a constant satisfies the
   first and a coin satisfies the second.
5. Every rejection is a specific status. The wrapping-multiply shape
   (`n_ops = 6148914691236517206` against a 2-element list) is included because
   `n_jobs * n_ops == len(duration)` is a wrapping 64-bit multiply, so that request passes a
   naive shape guard and then reads past the end — an uncatchable process crash. It must come
   back `MODEL_ERR_LENGTH_MISMATCH`, and the fact that this suite finishes is the evidence.

6. The tolerance tests come in PAIRS, at both ends of the magnitude range, and neither half is
   worth anything alone. A 1.0 breach against 3e12 of total work must be caught (a tolerance
   inflated by a sum over the instance would swallow it) AND a 1e-13 breach against a 1e-14
   capacity must be caught (a tolerance floored at scale 1.0 swallowed exactly that), while
   1e-5 at magnitude 1e12 and 1e-27 at magnitude 1e-13 must both stay rounding. A verifier
   that flags everything passes the strict half and is as useless as one that flags nothing.
7. Two public functions may not disagree about one instance. `rcpsp_bound_flat` must never
   return a lower bound above a makespan `rcpsp_verify_flat` certifies feasible on the same
   arrays — that is asserted as a PROPERTY over a set of instances, not on one case, because
   the failure was a tolerance mismatch between the two code paths and not a bad constant.
   `rcpsp_peak_usage_flat` must refuse the start times `rcpsp_verify_flat` refuses.
8. A dimension inside the allocation ceiling can still drive unbounded work. The 2,000,000
   machine case is here because it ran for hours reporting `work_limit_hit = False`; it must
   now report the limit, and the same instance with 5 machines must NOT — one direction alone
   would pass with a work counter that simply always trips.

Exact equality is used throughout. Every duration, capacity and demand here is a small
integer, so every start time and makespan is exactly representable and a tolerance would hide
a mis-accumulation rather than absorb a rounding. The one exception is the RCPSP area bound
10/3, which is compared against the same quotient computed in the test.
"""
from optimization.model import (
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_OK,
)
from optimization.scheduling import (
    SCHED_ABSENT,
    SCHED_ERR_EMPTY_INSTANCE,
    SCHED_ERR_INVALID_VALUE,
    SCHED_ERR_UNVERIFIED,
    SCHED_ERR_WORK_BUDGET,
    SCHED_FEASIBLE,
    SCHED_LIMIT,
    SCHED_MAX_ITERS,
    SCHED_MAX_UNITS,
    SCHED_OPTIMAL,
    SCHED_PRECEDENCE_CYCLE,
    SCHED_RESOURCE_INFEASIBLE,
    SCHED_UNIT_ARRAYS,
    SCHED_VIOL_MACHINE_OVERLAP,
    SCHED_VIOL_NEGATIVE_START,
    SCHED_VIOL_NON_FINITE_START,
    SCHED_VIOL_NONE,
    SCHED_VIOL_PRECEDENCE,
    SCHED_VIOL_RESOURCE_OVER_CAPACITY,
    SCHED_VIOLATION,
    JobShopResult,
    RcpspResult,
    jobshop_bound_flat,
    jobshop_schedule_from_ranks_flat,
    jobshop_tabu_solve_flat,
    jobshop_verify_flat,
    rcpsp_bound_flat,
    rcpsp_peak_usage_flat,
    rcpsp_sgs_solve_flat,
    rcpsp_verify_flat,
    sched_status_name,
    sched_violation_name,
)
from sparse_numerics.csr import MAX_CSR_DIM


def _f(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _i(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _same_f(a: List[Float64], b: List[Float64]) -> Bool:
    """Bit-for-bit equality of two schedules. Exact on purpose — see the module docstring."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _same_i(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _bound_at_most_verified(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    pred_from: List[Int], pred_to: List[Int], n_acts: Int, n_res: Int,
    start: List[Float64]
) -> Bool:
    """A lower bound may never exceed a makespan the SAME module certifies feasible.

    `cp_bound` is a path through the precedences and the area bound is `Σ dᵢrᵢ / capᵣ`; both
    hold for EVERY schedule, so both are at most the makespan of any schedule
    `rcpsp_verify_flat` accepts. Vacuously true when either side declines to answer — the claim
    is that the two cannot both speak and contradict each other.

    The allowance is 1e-12 RELATIVE to the certified makespan, which is far above the accumulated
    rounding of either quantity and far below the 10x contradiction this pins.
    """
    var b = rcpsp_bound_flat(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res
    )
    var a = rcpsp_verify_flat(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res, start
    )
    if not b.has_bound:
        return True
    # The three bound fields must agree with each other whatever the verifier says. Clamping the
    # maximum alone could report a `lower_bound` BELOW the `cp_bound` printed beside it, and two
    # mutually exclusive claims in one returned value leave a caller able to use neither.
    var expect = b.cp_bound
    if b.has_resource_bound and b.resource_bound > expect:
        expect = b.resource_bound
    if b.lower_bound != expect:
        return False
    if not a.feasible or not a.has_makespan:
        return True
    return b.lower_bound <= a.makespan + 1.0e-12 * a.makespan


def _no_numbers(r: JobShopResult) -> Bool:
    """A rejected job-shop request carries no schedule, no bound and no gap."""
    return (
        not r.feasible
        and not r.verified
        and not r.has_makespan
        and not r.has_bound
        and not r.has_gap
        and not r.optimal_by_bound
        and len(r.start) == 0
        and len(r.critical_ops) == 0
        and len(r.machine_rank) == 0
    )


def _identical(a: JobShopResult, b: JobShopResult) -> Bool:
    """Everything a caller can observe, including the search's own history."""
    return (
        a.status == b.status
        and a.makespan == b.makespan
        and a.lower_bound == b.lower_bound
        and a.gap == b.gap
        and a.initial_makespan == b.initial_makespan
        and a.iterations == b.iterations
        and a.moves_evaluated == b.moves_evaluated
        and a.improvements == b.improvements
        and a.restarts == b.restarts
        and a.cycles_rejected == b.cycles_rejected
        and _same_f(a.start, b.start)
        and _same_i(a.machine_rank, b.machine_rank)
        and _same_i(a.critical_ops, b.critical_ops)
    )


def _identical_r(a: RcpspResult, b: RcpspResult) -> Bool:
    return (
        a.status == b.status
        and a.makespan == b.makespan
        and a.lower_bound == b.lower_bound
        and a.gap == b.gap
        and a.initial_makespan == b.initial_makespan
        and a.schedules_built == b.schedules_built
        and a.improvements == b.improvements
        and a.resource_delayed_at == b.resource_delayed_at
        and _same_f(a.start, b.start)
        and _same_i(a.order, b.order)
        and _same_i(a.critical_ops, b.critical_ops)
    )


# ── the 2x2 instance, worked by hand ─────────────────────────────────────────
# Operations, with op id = job * n_ops + k:
#   A = op0, job 0 first,  machine 0, duration 3
#   B = op1, job 0 second, machine 1, duration 2
#   C = op2, job 1 first,  machine 1, duration 2
#   D = op3, job 1 second, machine 0, duration 4
# Machine 0 holds {A, D}; machine 1 holds {B, C}. Job chains: A -> B and C -> D.
#
# The four orientations, enumerated:
#   A<D, B<C : A 0-3, B 3-5, C 5-7, D 7-11            -> 11
#   A<D, C<B : C 0-2, A 0-3, B 3-5, D 3-7             ->  7
#   D<A, B<C : A needs D, D needs C, C needs B, B needs A -> CYCLE
#   D<A, C<B : C 0-2, D 2-6, A 6-9, B 9-11            -> 11
# So the optimum is 7. Bounds: job chains 5 and 6 -> 6; machine loads 3+4=7 and 2+2=4 -> 7.
# max(6, 7) = 7, which MEETS the optimum.


def _dur22() -> List[Float64]:
    return _f(3.0, 2.0, 2.0, 4.0)


def _mach22() -> List[Int]:
    return _i(0, 1, 1, 0)


def main() raises:
    var passed = 0
    var failed = 0

    # ── bounds are the two cheap valid ones, and the larger wins ─────────────
    var b22 = jobshop_bound_flat(_dur22(), _mach22(), 2, 2, 2)
    if (
        b22.status == MODEL_OK
        and b22.has_bound
        and b22.job_bound == 6.0
        and b22.machine_bound == 7.0
        and b22.lower_bound == 7.0
        and b22.critical_job == 1
        and b22.critical_machine == 0
        and b22.n_operations == 4
        and b22.total_work == 11.0
    ):
        passed += 1
        print("  ✅ 2x2 bounds: job chain 6, machine load 7, bound 7")
    else:
        failed += 1
        print(
            "  ❌ 2x2 bounds:", b22.status, b22.job_bound, b22.machine_bound,
            b22.lower_bound, b22.critical_job, b22.critical_machine, b22.total_work
        )

    # ── the whole feasible space, enumerated: the optimum is 7 ───────────────
    var o1 = jobshop_schedule_from_ranks_flat(
        _dur22(), _mach22(), 2, 2, 2, _i(0, 0, 1, 1)
    )
    var o2 = jobshop_schedule_from_ranks_flat(
        _dur22(), _mach22(), 2, 2, 2, _i(0, 1, 0, 1)
    )
    var o3 = jobshop_schedule_from_ranks_flat(
        _dur22(), _mach22(), 2, 2, 2, _i(1, 0, 1, 0)
    )
    var o4 = jobshop_schedule_from_ranks_flat(
        _dur22(), _mach22(), 2, 2, 2, _i(1, 1, 0, 0)
    )
    if (
        o1.status == SCHED_FEASIBLE
        and o1.makespan == 11.0
        and o1.gap == 4.0
        and not o1.optimal_by_bound
        and o2.status == SCHED_OPTIMAL
        and o2.makespan == 7.0
        and o2.gap == 0.0
        and o2.optimal_by_bound
        and _same_f(o2.start, _f(0.0, 3.0, 0.0, 3.0))
        and o4.status == SCHED_FEASIBLE
        and o4.makespan == 11.0
    ):
        passed += 1
        print("  ✅ all four orientations priced: 11, 7, cyclic, 11 — optimum is 7")
    else:
        failed += 1
        print(
            "  ❌ orientation enumeration:", o1.status, o1.makespan, o2.status,
            o2.makespan, o4.status, o4.makespan
        )

    # ── a cyclic orientation has NO schedule, not a finite makespan ──────────
    if (
        o3.status == SCHED_PRECEDENCE_CYCLE
        and not o3.feasible
        and not o3.has_makespan
        and not o3.has_bound
        and o3.cycle_op == 0
        and o3.n_ordered == 0
        and len(o3.start) == 0
        and len(o3.critical_ops) == 0
        and len(o3.machine_rank) == 0
    ):
        passed += 1
        print("  ✅ the cyclic orientation is refused, with the operation named")
    else:
        failed += 1
        print(
            "  ❌ cycle:", o3.status, o3.has_makespan, o3.cycle_op, o3.n_ordered,
            len(o3.start)
        )

    # ── tabu search reaches the enumerated optimum, and the bound proves it ──
    var t22 = jobshop_tabu_solve_flat(_dur22(), _mach22(), 2, 2, 2, 7, 50, 3, 3)
    var crit_ok = len(t22.critical_ops) == 2
    if crit_ok:
        crit_ok = t22.critical_ops[0] == 0 and t22.critical_ops[1] == 3
    if (
        t22.status == SCHED_OPTIMAL
        and t22.feasible
        and t22.verified
        and t22.has_makespan
        and t22.makespan == 7.0
        and t22.lower_bound == 7.0
        and t22.gap == 0.0
        and t22.has_relative_gap
        and t22.relative_gap == 0.0
        and t22.optimal_by_bound
        and t22.cycles_rejected == 0
        and _same_f(t22.start, _f(0.0, 3.0, 0.0, 3.0))
        and _same_i(t22.machine_rank, _i(0, 1, 0, 1))
        and crit_ok
    ):
        passed += 1
        print("  ✅ tabu finds makespan 7 with critical path A -> D and gap 0")
    else:
        failed += 1
        print(
            "  ❌ tabu 2x2:", t22.status, t22.makespan, t22.gap, t22.optimal_by_bound,
            len(t22.critical_ops)
        )

    # ── the answer round-trips through its own ranks ─────────────────────────
    var replay = jobshop_schedule_from_ranks_flat(
        _dur22(), _mach22(), 2, 2, 2, t22.machine_rank
    )
    var audit22 = jobshop_verify_flat(_dur22(), _mach22(), 2, 2, 2, t22.start)
    if (
        replay.status == SCHED_OPTIMAL
        and replay.makespan == t22.makespan
        and _same_f(replay.start, t22.start)
        and audit22.status == MODEL_OK
        and audit22.feasible
        and audit22.violation == SCHED_VIOL_NONE
        and audit22.n_violations == 0
        and audit22.makespan == 7.0
        and audit22.worst_violation == 0.0
    ):
        passed += 1
        print("  ✅ the reported ranks reproduce the schedule, and it verifies clean")
    else:
        failed += 1
        print(
            "  ❌ round trip:", replay.status, replay.makespan, audit22.status,
            audit22.feasible, audit22.makespan
        )

    # ── a chain of precedences: the makespan IS the chain, tabu cannot help ──
    # One job, four operations of 1, 2, 3, 4 on four machines. Starts are the prefix sums
    # 0, 1, 3, 6 and the makespan is 10 = the job bound, so the bound is exact and the
    # search has nothing to improve.
    var chain_d = _f(1.0, 2.0, 3.0, 4.0)
    var chain_m = _i(0, 1, 2, 3)
    var cb = jobshop_bound_flat(chain_d, chain_m, 1, 4, 4)
    var ct = jobshop_tabu_solve_flat(chain_d, chain_m, 1, 4, 4, 11, 25, 4, 6)
    var chain_crit = len(ct.critical_ops) == 4
    if chain_crit:
        for i in range(4):
            if ct.critical_ops[i] != i:
                chain_crit = False
    if (
        cb.job_bound == 10.0
        and cb.machine_bound == 4.0
        and cb.lower_bound == 10.0
        and cb.critical_machine == 3
        and ct.status == SCHED_OPTIMAL
        and ct.makespan == 10.0
        and ct.initial_makespan == 10.0
        and ct.gap == 0.0
        and ct.optimal_by_bound
        and ct.iterations == 0
        and ct.improvements == 0
        and _same_f(ct.start, _f(0.0, 1.0, 3.0, 6.0))
        and chain_crit
    ):
        passed += 1
        print("  ✅ a pure chain: makespan 10 == chain length, 0 iterations spent")
    else:
        failed += 1
        print(
            "  ❌ chain:", cb.lower_bound, ct.status, ct.makespan, ct.iterations,
            ct.improvements, len(ct.critical_ops)
        )

    # ── verification catches each kind, with the operations and the time ─────
    # start = [0, 3, 0, 2]: every precedence holds (B at 3 >= 0+3, D at 2 >= 0+2) but A
    # occupies machine 0 over [0, 3) and D over [2, 6). Overlap of 1 at time 2.
    var overlap = jobshop_verify_flat(_dur22(), _mach22(), 2, 2, 2, _f(0.0, 3.0, 0.0, 2.0))
    # start = [0, 1, 0, 3]: B starts at 1 but A finishes at 3 — short by 2. The same
    # schedule also puts B and C on machine 1 at once, so there are two violations and the
    # first one found is reported in full.
    var prec = jobshop_verify_flat(_dur22(), _mach22(), 2, 2, 2, _f(0.0, 1.0, 0.0, 3.0))
    var negative = jobshop_verify_flat(
        _dur22(), _mach22(), 2, 2, 2, _f(-1.0, 3.0, 0.0, 3.0)
    )
    var infinite = 1e308 * 10.0
    var nonfinite = jobshop_verify_flat(
        _dur22(), _mach22(), 2, 2, 2, _f(infinite, 3.0, 0.0, 3.0)
    )
    var short = jobshop_verify_flat(_dur22(), _mach22(), 2, 2, 2, _f(0.0, 3.0, 0.0))
    if (
        overlap.status == SCHED_VIOLATION
        and overlap.violation == SCHED_VIOL_MACHINE_OVERLAP
        and overlap.first_op == 0
        and overlap.second_op == 3
        and overlap.machine == 0
        and overlap.has_time
        and overlap.time == 2.0
        and overlap.worst_violation == 1.0
        and overlap.n_violations == 1
        and overlap.makespan == 6.0
        and prec.violation == SCHED_VIOL_PRECEDENCE
        and prec.first_op == 0
        and prec.second_op == 1
        and prec.time == 3.0
        and prec.worst_violation == 2.0
        and prec.n_violations == 2
        and negative.violation == SCHED_VIOL_NEGATIVE_START
        and negative.first_op == 0
        and nonfinite.violation == SCHED_VIOL_NON_FINITE_START
        and not nonfinite.has_makespan
        and short.status == MODEL_ERR_LENGTH_MISMATCH
        and not short.feasible
    ):
        passed += 1
        print("  ✅ overlap, precedence, negative, non-finite and short starts all named")
    else:
        failed += 1
        print(
            "  ❌ verification:", overlap.violation, overlap.machine, overlap.time,
            overlap.worst_violation, prec.violation, prec.n_violations,
            negative.violation, nonfinite.violation, short.status
        )

    # ── the heuristic finds the optimum and still refuses to claim it ────────
    # Three jobs, each machine 0 then machine 1, every duration 2. Machine 0 must process
    # 3 x 2 = 6 units, and whichever job leaves it last still needs 2 on machine 1, so 8 is
    # optimal. The bound this module holds is max(chain 4, load 6) = 6, so the gap is 2 and
    # `optimal_by_bound` must be False even though the schedule IS optimal.
    var flow_d = _f(2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
    var flow_m = _i(0, 1, 0, 1, 0, 1)
    var fr = jobshop_tabu_solve_flat(flow_d, flow_m, 3, 2, 2, 1, 20, 5, 20)
    var fa = jobshop_verify_flat(flow_d, flow_m, 3, 2, 2, fr.start)
    if (
        fr.status == SCHED_LIMIT
        and fr.makespan == 8.0
        and fr.lower_bound == 6.0
        and fr.gap == 2.0
        and not fr.optimal_by_bound
        and fr.iteration_limit_hit
        and not fr.work_limit_hit
        and fr.verified
        and fa.status == MODEL_OK
        and fa.makespan == 8.0
    ):
        passed += 1
        print("  ✅ flow shop: holds the optimum 8, reports gap 2, claims nothing")
    else:
        failed += 1
        print(
            "  ❌ flow shop:", fr.status, fr.makespan, fr.lower_bound, fr.gap,
            fr.optimal_by_bound, fr.iteration_limit_hit, fa.status
        )

    # ── the search improves on its own construction ──────────────────────────
    # A 3x3 instance where the dispatch rule gives 12 and a critical swap gives 11.
    var d33 = _f(3.0, 2.0, 2.0, 2.0, 1.0, 4.0, 4.0, 3.0, 1.0)
    var m33 = _i(0, 1, 2, 0, 2, 1, 1, 2, 0)
    var r33 = jobshop_tabu_solve_flat(d33, m33, 3, 3, 3, 1, 60, 5, 4)
    var a33 = jobshop_verify_flat(d33, m33, 3, 3, 3, r33.start)
    if (
        r33.status == SCHED_LIMIT
        and r33.initial_makespan == 12.0
        and r33.makespan == 11.0
        and r33.improvements == 1
        and r33.lower_bound == 10.0
        and r33.gap == 1.0
        and not r33.optimal_by_bound
        and r33.cycles_rejected == 0
        and r33.moves_evaluated > 0
        and r33.restarts > 0
        and a33.status == MODEL_OK
        and a33.makespan == 11.0
    ):
        passed += 1
        print("  ✅ tabu improves 12 -> 11 on the 3x3, and the 11 verifies")
    else:
        failed += 1
        print(
            "  ❌ 3x3:", r33.status, r33.initial_makespan, r33.makespan,
            r33.improvements, r33.gap, r33.cycles_rejected, a33.status
        )

    # ── determinism, both directions, on the job shop ────────────────────────
    # Four jobs of two unit operations, two machines contested. Each machine carries four
    # unit operations, so the makespan is 4 and the bound is 4 — several distinct optimal
    # schedules exist, which is exactly what makes the seed's choice observable.
    var eq_d = _f(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    var eq_m = _i(0, 1, 0, 1, 1, 0, 1, 0)
    var s1a = jobshop_tabu_solve_flat(eq_d, eq_m, 4, 2, 2, 1, 30, 5, 20)
    var s1b = jobshop_tabu_solve_flat(eq_d, eq_m, 4, 2, 2, 1, 30, 5, 20)
    var s2 = jobshop_tabu_solve_flat(eq_d, eq_m, 4, 2, 2, 2, 30, 5, 20)
    var ea = jobshop_verify_flat(eq_d, eq_m, 4, 2, 2, s2.start)
    if (
        _identical(s1a, s1b)
        and s1a.status == SCHED_OPTIMAL
        and s1a.makespan == 4.0
        and s1a.lower_bound == 4.0
        and s2.makespan == 4.0
        and not _same_f(s1a.start, s2.start)
        and ea.status == MODEL_OK
        and ea.makespan == 4.0
    ):
        passed += 1
        print("  ✅ same seed is bit-identical; a different seed schedules differently")
    else:
        failed += 1
        print(
            "  ❌ job-shop determinism:", _identical(s1a, s1b), s1a.makespan,
            s2.makespan, _same_f(s1a.start, s2.start), ea.status
        )

    # ── every rejection is its own status, and none of them indexes anything ─
    var wrap = jobshop_bound_flat(_f(1.0, 2.0), _i(0, 0), 3, 6148914691236517206, 1)
    var too_big = jobshop_bound_flat(chain_d, chain_m, 1, 4, MAX_CSR_DIM)
    var empty = jobshop_bound_flat(chain_d, chain_m, 0, 4, 4)
    var bad_machine = jobshop_bound_flat(chain_d, _i(0, 1, 2, 9), 1, 4, 4)
    var neg_dur = jobshop_bound_flat(_f(1.0, -2.0, 3.0, 4.0), chain_m, 1, 4, 4)
    var nf_dur = jobshop_bound_flat(_f(1.0, infinite, 3.0, 4.0), chain_m, 1, 4, 4)
    var mismatch = jobshop_bound_flat(chain_d, _i(0, 1, 2), 1, 4, 4)
    if (
        wrap.status == MODEL_ERR_LENGTH_MISMATCH
        and not wrap.has_bound
        and too_big.status == MODEL_ERR_DIMENSION_TOO_LARGE
        and empty.status == SCHED_ERR_EMPTY_INSTANCE
        and bad_machine.status == SCHED_ERR_INVALID_VALUE
        and neg_dur.status == SCHED_ERR_INVALID_VALUE
        and nf_dur.status == SCHED_ERR_INVALID_VALUE
        and mismatch.status == MODEL_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ wrapping shape, ceiling, empty, bad machine and bad duration refused")
    else:
        failed += 1
        print(
            "  ❌ rejections:", wrap.status, too_big.status, empty.status,
            bad_machine.status, neg_dur.status, nf_dur.status, mismatch.status
        )

    # ── search parameters are refused, never clamped ─────────────────────────
    var p_neg = jobshop_tabu_solve_flat(_dur22(), _mach22(), 2, 2, 2, 1, -1, 3, 3)
    var p_huge = jobshop_tabu_solve_flat(
        _dur22(), _mach22(), 2, 2, 2, 1, SCHED_MAX_ITERS + 1, 3, 3
    )
    var p_ten = jobshop_tabu_solve_flat(_dur22(), _mach22(), 2, 2, 2, 1, 5, 0, 3)
    var p_stall = jobshop_tabu_solve_flat(_dur22(), _mach22(), 2, 2, 2, 1, 5, 3, 0)
    if (
        p_neg.status == SCHED_ERR_INVALID_VALUE
        and _no_numbers(p_neg)
        and p_huge.status == SCHED_ERR_INVALID_VALUE
        and p_ten.status == SCHED_ERR_INVALID_VALUE
        and p_stall.status == SCHED_ERR_INVALID_VALUE
    ):
        passed += 1
        print("  ✅ a bad iteration, tenure or stall budget is refused with no schedule")
    else:
        failed += 1
        print(
            "  ❌ parameters:", p_neg.status, p_huge.status, p_ten.status, p_stall.status
        )

    # ── the generated A-Z sample arguments must not index past any end ───────
    # `tests/generate_mojo_tests.py` calls every contract function with 5-element lists and
    # 5 for every Int, so `n_jobs * n_ops == 25` against a 5-element array. Each entry point
    # has to reject that rather than read `duration[24]`, which would crash the worker.
    var g5f = _f(0.5, 0.5, 0.5, 0.5, 0.5)
    var g5i = _i(5, 5, 5, 5, 5)
    var gen_a = jobshop_bound_flat(g5f, g5i, 5, 5, 5)
    var gen_b = jobshop_verify_flat(g5f, g5i, 5, 5, 5, g5f)
    var gen_c = jobshop_schedule_from_ranks_flat(g5f, g5i, 5, 5, 5, g5i)
    var gen_d = jobshop_tabu_solve_flat(g5f, g5i, 5, 5, 5, 5, 5, 5, 5)
    var gen_e = rcpsp_bound_flat(g5f, g5f, g5f, g5i, g5i, 5, 5)
    var gen_g = rcpsp_verify_flat(g5f, g5f, g5f, g5i, g5i, 5, 5, g5f)
    var gen_h = rcpsp_peak_usage_flat(g5f, g5f, g5f, 5, 5, g5f)
    var gen_j = rcpsp_sgs_solve_flat(g5f, g5f, g5f, g5i, g5i, 5, 5, 5, 5)
    if (
        gen_a.status == MODEL_ERR_LENGTH_MISMATCH
        and gen_b.status == MODEL_ERR_LENGTH_MISMATCH
        and gen_c.status == MODEL_ERR_LENGTH_MISMATCH
        and gen_d.status == MODEL_ERR_LENGTH_MISMATCH
        and gen_e.status == MODEL_ERR_LENGTH_MISMATCH
        and gen_g.status == MODEL_ERR_LENGTH_MISMATCH
        and gen_h.status == MODEL_ERR_LENGTH_MISMATCH
        and gen_j.status == MODEL_ERR_LENGTH_MISMATCH
        and not gen_c.has_makespan
        and not gen_j.has_makespan
    ):
        passed += 1
        print("  ✅ all eight array entry points refuse the generated sample arguments")
    else:
        failed += 1
        print(
            "  ❌ generated args:", gen_a.status, gen_b.status, gen_c.status,
            gen_d.status, gen_e.status, gen_g.status, gen_h.status, gen_j.status
        )

    # ── the ceiling is the shared one, divided by the arrays actually held ───
    if (
        SCHED_MAX_UNITS * SCHED_UNIT_ARRAYS == MAX_CSR_DIM
        and SCHED_MAX_UNITS < MAX_CSR_DIM
        and SCHED_UNIT_ARRAYS > 1
    ):
        passed += 1
        print("  ✅ the unit ceiling is MAX_CSR_DIM / 32 exactly, not a second number")
    else:
        failed += 1
        print("  ❌ ceiling arithmetic:", SCHED_MAX_UNITS, SCHED_UNIT_ARRAYS, MAX_CSR_DIM)

    # ── RCPSP bounds: the precedence path and the resource area ──────────────
    # Two activities, durations 2 and 3, each needing 2 of a capacity-3 resource. They
    # cannot overlap, so the makespan is 5. The critical path is the longer activity alone
    # (3) and the area bound is (2*2 + 3*2)/3 = 10/3, so the bound is 10/3 and the gap is
    # real: 5 is optimal and this module cannot prove it.
    var two_d = _f(2.0, 3.0)
    var two_dem = _f(2.0, 2.0)
    var cap3 = _f(3.0)
    var none_i = _i()
    var rb = rcpsp_bound_flat(two_d, two_dem, cap3, none_i, none_i, 2, 1)
    var area = 10.0 / 3.0
    if (
        rb.status == MODEL_OK
        and rb.has_bound
        and rb.cp_bound == 3.0
        and rb.has_resource_bound
        and rb.resource_bound == area
        and rb.lower_bound == area
        and rb.binding_resource == 0
        and len(rb.critical_ops) == 1
        and rb.critical_ops[0] == 1
        and rb.n_activities == 2
    ):
        passed += 1
        print("  ✅ RCPSP bounds: critical path 3, area 10/3, bound 10/3")
    else:
        failed += 1
        print(
            "  ❌ RCPSP bounds:", rb.status, rb.cp_bound, rb.resource_bound,
            rb.lower_bound, rb.binding_resource, len(rb.critical_ops)
        )

    # ── the resource forces a serial schedule, and the delay is explained ────
    var two_r0 = rcpsp_sgs_solve_flat(two_d, two_dem, cap3, none_i, none_i, 2, 1, 5, 0)
    var two_r4 = rcpsp_sgs_solve_flat(two_d, two_dem, cap3, none_i, none_i, 2, 1, 5, 4)
    var two_audit = rcpsp_verify_flat(
        two_d, two_dem, cap3, none_i, none_i, 2, 1, two_r4.start
    )
    if (
        two_r0.status == SCHED_FEASIBLE
        and two_r0.makespan == 5.0
        and not two_r0.budget_limit_hit
        and two_r4.status == SCHED_LIMIT
        and two_r4.makespan == 5.0
        and two_r4.budget_limit_hit
        and two_r4.schedules_built == 5
        and not two_r4.optimal_by_bound
        and two_r4.resource_delayed_at >= 0
        and two_audit.status == MODEL_OK
        and two_audit.makespan == 5.0
    ):
        passed += 1
        print("  ✅ two 2-of-3 activities serialise to 5; the delay names a resource")
    else:
        failed += 1
        print(
            "  ❌ RCPSP serial:", two_r0.status, two_r0.makespan, two_r4.status,
            two_r4.makespan, two_r4.schedules_built, two_r4.resource_delayed_at,
            two_audit.status
        )

    # ── a chain: the makespan IS the chain, and the bound is exact ───────────
    var ch_d = _f(1.0, 2.0, 3.0)
    var ch_dem = _f(1.0, 1.0, 1.0)
    var cap2 = _f(2.0)
    var ch_r = rcpsp_sgs_solve_flat(ch_d, ch_dem, cap2, _i(0, 1), _i(1, 2), 3, 1, 3, 2)
    var ch_crit = len(ch_r.critical_ops) == 3
    if ch_crit:
        for i in range(3):
            if ch_r.critical_ops[i] != i:
                ch_crit = False
    if (
        ch_r.status == SCHED_OPTIMAL
        and ch_r.makespan == 6.0
        and ch_r.cp_bound == 6.0
        and ch_r.lower_bound == 6.0
        and ch_r.gap == 0.0
        and ch_r.optimal_by_bound
        and ch_r.resource_delayed_at == -1
        and _same_f(ch_r.start, _f(0.0, 1.0, 3.0))
        and ch_crit
    ):
        passed += 1
        print("  ✅ an RCPSP chain: makespan 6 == critical path, explained by precedences")
    else:
        failed += 1
        print(
            "  ❌ RCPSP chain:", ch_r.status, ch_r.makespan, ch_r.lower_bound,
            ch_r.resource_delayed_at, len(ch_r.critical_ops)
        )

    # ── activities DO run in parallel up to the capacity ─────────────────────
    # A needs 2 of 2, B and C need 1 each, all of duration 2. B and C fit together, A does
    # not fit with anything: the makespan is 4 and the area bound (2*2 + 2 + 2)/2 = 4 makes
    # it provably optimal.
    var pk_d = _f(2.0, 2.0, 2.0)
    var pk_dem = _f(2.0, 1.0, 1.0)
    var pack = rcpsp_sgs_solve_flat(pk_d, pk_dem, cap2, none_i, none_i, 3, 1, 4, 3)
    var pack_audit = rcpsp_verify_flat(
        pk_d, pk_dem, cap2, none_i, none_i, 3, 1, pack.start
    )
    if (
        pack.status == SCHED_OPTIMAL
        and pack.makespan == 4.0
        and pack.lower_bound == 4.0
        and pack.optimal_by_bound
        and pack.start[1] == pack.start[2]
        and pack_audit.status == MODEL_OK
    ):
        passed += 1
        print("  ✅ two 1-of-2 activities share the resource; makespan 4 meets the bound")
    else:
        failed += 1
        print(
            "  ❌ RCPSP packing:", pack.status, pack.makespan, pack.lower_bound,
            pack.start[0], pack.start[1], pack.start[2], pack_audit.status
        )

    # ── a demand no capacity can meet is infeasible, and says which ──────────
    var infeas = rcpsp_sgs_solve_flat(
        two_d, _f(5.0, 2.0), cap3, none_i, none_i, 2, 1, 5, 2
    )
    var infeas_b = rcpsp_bound_flat(two_d, _f(5.0, 2.0), cap3, none_i, none_i, 2, 1)
    if (
        infeas.status == SCHED_RESOURCE_INFEASIBLE
        and not infeas.feasible
        and not infeas.has_makespan
        and not infeas.has_bound
        and infeas.infeasible_act == 0
        and infeas.infeasible_resource == 0
        and len(infeas.start) == 0
        and infeas_b.status == SCHED_RESOURCE_INFEASIBLE
        and infeas_b.binding_resource == 0
        and not infeas_b.has_bound
    ):
        passed += 1
        print("  ✅ demand 5 against capacity 3 is infeasible: activity 0, resource 0")
    else:
        failed += 1
        print(
            "  ❌ RCPSP infeasible:", infeas.status, infeas.infeasible_act,
            infeas.infeasible_resource, len(infeas.start), infeas_b.status
        )

    # ── a precedence cycle, including a self-loop, has no schedule ───────────
    var cyc = rcpsp_sgs_solve_flat(two_d, two_dem, cap3, _i(0, 1), _i(1, 0), 2, 1, 1, 0)
    var self_loop = rcpsp_bound_flat(two_d, two_dem, cap3, _i(0), _i(0), 2, 1)
    var bad_edge = rcpsp_bound_flat(two_d, two_dem, cap3, _i(0), _i(7), 2, 1)
    if (
        cyc.status == SCHED_PRECEDENCE_CYCLE
        and cyc.cycle_act == 0
        and not cyc.has_makespan
        and len(cyc.start) == 0
        and self_loop.status == SCHED_PRECEDENCE_CYCLE
        and self_loop.cycle_act == 0
        and bad_edge.status == SCHED_ERR_INVALID_VALUE
    ):
        passed += 1
        print("  ✅ a 2-cycle and a self-loop are both refused; a stray edge is a value")
    else:
        failed += 1
        print(
            "  ❌ RCPSP cycle:", cyc.status, cyc.cycle_act, self_loop.status,
            bad_edge.status
        )

    # ── the resource conflict must be REPORTED, with the time and resource ───
    # Both activities at time 0 demand 2 + 2 = 4 of a capacity-3 resource.
    var conflict = rcpsp_verify_flat(
        two_d, two_dem, cap3, none_i, none_i, 2, 1, _f(0.0, 0.0)
    )
    var conflict_peak = rcpsp_peak_usage_flat(two_d, two_dem, cap3, 2, 1, _f(0.0, 0.0))
    var clean_peak = rcpsp_peak_usage_flat(two_d, two_dem, cap3, 2, 1, _f(3.0, 0.0))
    if (
        conflict.status == SCHED_VIOLATION
        and conflict.violation == SCHED_VIOL_RESOURCE_OVER_CAPACITY
        and conflict.resource == 0
        and conflict.has_time
        and conflict.time == 0.0
        and conflict.worst_violation == 1.0
        and conflict.makespan == 3.0
        and conflict_peak.status == MODEL_OK
        and conflict_peak.peak[0] == 4.0
        and conflict_peak.peak_time[0] == 0.0
        and conflict_peak.over_capacity[0] == 1
        and conflict_peak.n_over == 1
        and clean_peak.peak[0] == 2.0
        and clean_peak.peak_time[0] == 0.0
        and clean_peak.n_over == 0
        and clean_peak.makespan == 5.0
    ):
        passed += 1
        print("  ✅ the resource conflict reports resource 0 at time 0, over by 1")
    else:
        failed += 1
        print(
            "  ❌ RCPSP conflict:", conflict.violation, conflict.resource,
            conflict.time, conflict.worst_violation, conflict_peak.peak[0],
            conflict_peak.peak_time[0], clean_peak.peak[0], clean_peak.peak_time[0]
        )

    # ── an RCPSP precedence violation is counted, not just the first ─────────
    # start = [0, 0, 0] on the chain 0 -> 1 -> 2 breaks both edges AND puts 3 units of a
    # capacity-2 resource on at once, at three separate start instants.
    var ch_bad = rcpsp_verify_flat(
        ch_d, ch_dem, cap2, _i(0, 1), _i(1, 2), 3, 1, _f(0.0, 0.0, 0.0)
    )
    var ch_ok = rcpsp_verify_flat(
        ch_d, ch_dem, cap2, _i(0, 1), _i(1, 2), 3, 1, _f(0.0, 1.0, 3.0)
    )
    if (
        ch_bad.status == SCHED_VIOLATION
        and ch_bad.violation == SCHED_VIOL_PRECEDENCE
        and ch_bad.first_act == 0
        and ch_bad.second_act == 1
        and ch_bad.time == 1.0
        and ch_bad.worst_violation == 2.0
        and ch_bad.n_violations == 5
        and ch_ok.status == MODEL_OK
        and ch_ok.feasible
        and ch_ok.makespan == 6.0
        and ch_ok.n_violations == 0
    ):
        passed += 1
        print("  ✅ 2 broken precedences + 3 over-capacity instants = 5 violations")
    else:
        failed += 1
        print(
            "  ❌ RCPSP audit:", ch_bad.violation, ch_bad.first_act, ch_bad.time,
            ch_bad.worst_violation, ch_bad.n_violations, ch_ok.status, ch_ok.makespan
        )

    # ── determinism, both directions, on the RCPSP ───────────────────────────
    # Four unit activities and a capacity of 1: they must run one after another, so every
    # schedule has makespan 4 and the ORDER is the whole decision — which makes the seed's
    # choice observable, and the area bound 4/1 = 4 proves every one of them optimal.
    var ser_d = _f(1.0, 1.0, 1.0, 1.0)
    var ser_dem = _f(1.0, 1.0, 1.0, 1.0)
    var cap1 = _f(1.0)
    var q1a = rcpsp_sgs_solve_flat(ser_d, ser_dem, cap1, none_i, none_i, 4, 1, 1, 3)
    var q1b = rcpsp_sgs_solve_flat(ser_d, ser_dem, cap1, none_i, none_i, 4, 1, 1, 3)
    var q2 = rcpsp_sgs_solve_flat(ser_d, ser_dem, cap1, none_i, none_i, 4, 1, 2, 3)
    var q_audit = rcpsp_verify_flat(
        ser_d, ser_dem, cap1, none_i, none_i, 4, 1, q2.start
    )
    if (
        _identical_r(q1a, q1b)
        and q1a.status == SCHED_OPTIMAL
        and q1a.makespan == 4.0
        and q1a.lower_bound == 4.0
        and q1a.optimal_by_bound
        and q2.makespan == 4.0
        and not _same_i(q1a.order, q2.order)
        and not _same_f(q1a.start, q2.start)
        and q_audit.status == MODEL_OK
        and q_audit.makespan == 4.0
    ):
        passed += 1
        print("  ✅ RCPSP: same seed is bit-identical, a different seed orders differently")
    else:
        failed += 1
        print(
            "  ❌ RCPSP determinism:", _identical_r(q1a, q1b), q1a.makespan,
            q2.makespan, _same_i(q1a.order, q2.order), q_audit.status
        )

    # ── a project with no resources at all is the pure precedence problem ────
    var no_res = rcpsp_sgs_solve_flat(
        ch_d, _f(), _f(), _i(0, 1), _i(1, 2), 3, 0, 3, 1
    )
    var milestone = rcpsp_sgs_solve_flat(
        _f(0.0, 2.0), two_dem, cap3, _i(0), _i(1), 2, 1, 3, 1
    )
    if (
        no_res.status == SCHED_OPTIMAL
        and no_res.makespan == 6.0
        and no_res.cp_bound == 6.0
        and not no_res.has_resource_bound
        and _same_f(no_res.start, _f(0.0, 1.0, 3.0))
        and milestone.status == SCHED_OPTIMAL
        and milestone.makespan == 2.0
        and _same_f(milestone.start, _f(0.0, 0.0))
    ):
        passed += 1
        print("  ✅ no resources, and a zero-duration milestone, both schedule correctly")
    else:
        failed += 1
        print(
            "  ❌ degenerate RCPSP:", no_res.status, no_res.makespan,
            no_res.has_resource_bound, milestone.status, milestone.makespan
        )

    # ── ft06: an EXTERNAL known value, and the honesty test at scale ─────────
    # Fisher & Thompson's 6x6 job shop, whose optimal makespan of 55 is published and was not
    # computed here. The construction gives 88, the search reaches 55 — and still reports
    # `gap = 8` against its own bound of 47 with `optimal_by_bound = False`, because holding
    # the optimum is not the same as proving it. This is the assertion that would fail first if
    # the neighbourhood, the tabu list or the keyed scan order ever silently changed.
    var ft_m = _i(
        2, 0, 1, 3, 5, 4,
        1, 2, 4, 5, 0, 3,
        2, 3, 5, 0, 1, 4,
        1, 0, 2, 3, 4, 5,
        2, 1, 4, 5, 0, 3,
        1, 3, 5, 0, 4, 2,
    )
    var ft_d = _f(
        1.0, 3.0, 6.0, 7.0, 3.0, 6.0,
        8.0, 5.0, 10.0, 10.0, 10.0, 4.0,
        5.0, 4.0, 8.0, 9.0, 1.0, 7.0,
        5.0, 5.0, 5.0, 3.0, 8.0, 9.0,
        9.0, 3.0, 5.0, 4.0, 3.0, 1.0,
        3.0, 3.0, 9.0, 10.0, 4.0, 1.0,
    )
    var ft = jobshop_tabu_solve_flat(ft_d, ft_m, 6, 6, 6, 1, 4000, 12, 60)
    var ft_audit = jobshop_verify_flat(ft_d, ft_m, 6, 6, 6, ft.start)
    var ft_replay = jobshop_schedule_from_ranks_flat(
        ft_d, ft_m, 6, 6, 6, ft.machine_rank
    )
    if (
        ft.status == SCHED_LIMIT
        and ft.makespan == 55.0
        and ft.initial_makespan == 88.0
        and ft.lower_bound == 47.0
        and ft.gap == 8.0
        and not ft.optimal_by_bound
        and ft.verified
        and ft.cycles_rejected == 0
        and ft.improvements > 5
        and ft_audit.status == MODEL_OK
        and ft_audit.makespan == 55.0
        and ft_replay.makespan == 55.0
        and len(ft.critical_ops) > 1
    ):
        passed += 1
        print("  ✅ ft06: 88 -> 55, the published optimum, still reported as gap 8")
    else:
        failed += 1
        print(
            "  ❌ ft06:", ft.status, ft.makespan, ft.initial_makespan, ft.lower_bound,
            ft.gap, ft.optimal_by_bound, ft.cycles_rejected, ft_audit.status,
            ft_replay.makespan
        )

    # ── a violation at a huge magnitude is still a violation (rule 4b) ───────
    # Three unit-length jobs of duration 1e12 on ONE machine, and a schedule whose third
    # operation starts 1.0 too early. The instance's total work is 3e12, so a tolerance built
    # as `tol * (1 + Σ durations)` — the tier-1 defect — would be about 3000 and would swallow
    # this 1.0 overlap entirely, reporting an unexecutable schedule as valid. Sized by
    # DBL_EPSILON against the magnitude of the two operations compared, the allowance is about
    # 2e-4 and the overlap is caught.
    var big_d = _f(1.0e12, 1.0e12, 1.0e12)
    var big_m = _i(0, 0, 0)
    var big_bad = jobshop_verify_flat(
        big_d, big_m, 3, 1, 1, _f(0.0, 1.0e12, 2.0e12 - 1.0)
    )
    var big_ok = jobshop_verify_flat(big_d, big_m, 3, 1, 1, _f(0.0, 1.0e12, 2.0e12))
    # 1e-5 at magnitude 1e12 is 21 ulps — inside the rounding budget, so it is NOT a breach.
    var big_noise = jobshop_verify_flat(
        big_d, big_m, 3, 1, 1, _f(0.0, 1.0e12, 2.0e12 - 1.0e-5)
    )
    var big_prec = jobshop_verify_flat(
        big_d, big_m, 1, 3, 1, _f(0.0, 1.0e12, 2.0e12 - 1.0)
    )
    if (
        big_bad.status == SCHED_VIOLATION
        and big_bad.violation == SCHED_VIOL_MACHINE_OVERLAP
        and big_bad.worst_violation == 1.0
        and big_ok.status == MODEL_OK
        and big_ok.feasible
        and big_noise.status == MODEL_OK
        and big_prec.status == SCHED_VIOLATION
        and big_prec.violation == SCHED_VIOL_PRECEDENCE
        and big_prec.worst_violation == 1.0
    ):
        passed += 1
        print("  ✅ a 1.0 breach against 3e12 of total work is caught; 1e-5 is rounding")
    else:
        failed += 1
        print(
            "  ❌ tolerance scaling:", big_bad.violation, big_bad.worst_violation,
            big_ok.status, big_noise.status, big_prec.violation
        )

    # ── durations that individually pass and together overflow ──────────────
    # Each of these is finite, so a per-element `_finite` check admits them, and their sum is
    # +inf. Left unguarded the job bound is +inf, the makespan is +inf and `gap = inf - inf`
    # is NaN — a NaN returned under a SUCCESS status, which is the exact shape of defect this
    # package exists to remove.
    var huge = _f(1.0e308, 1.0e308, 1.0, 1.0)
    var of_bound = jobshop_bound_flat(huge, chain_m, 1, 4, 4)
    var of_solve = jobshop_tabu_solve_flat(huge, chain_m, 1, 4, 4, 1, 10, 3, 3)
    var of_rcpsp = rcpsp_sgs_solve_flat(
        _f(1.0e308, 1.0e308), two_dem, cap3, none_i, none_i, 2, 1, 1, 1
    )
    # Durations sum finitely and every demand fits the capacity, so both earlier screens pass;
    # it is the resource-time AREA (1e8 * 1e300, twice) that overflows.
    var of_area = rcpsp_bound_flat(
        _f(1.0e8, 1.0e8), _f(1.0e300, 1.0e300), _f(1.0e300), none_i, none_i, 2, 1
    )
    if (
        of_bound.status == SCHED_ERR_INVALID_VALUE
        and not of_bound.has_bound
        and of_solve.status == SCHED_ERR_INVALID_VALUE
        and _no_numbers(of_solve)
        and of_rcpsp.status == SCHED_ERR_INVALID_VALUE
        and not of_rcpsp.has_gap
        and of_area.status == SCHED_ERR_INVALID_VALUE
        and not of_area.has_bound
    ):
        passed += 1
        print("  ✅ finite durations that sum to +inf are refused, not answered with NaN")
    else:
        failed += 1
        print(
            "  ❌ overflow guards:", of_bound.status, of_solve.status, of_rcpsp.status,
            of_area.status
        )

    # ── the milestone convention has ONE strength everywhere ─────────────────
    # A zero-duration activity occupies [t, t) and consumes nothing, so a demand of 9 against
    # a capacity of 3 is not infeasible for it. The pre-search screen, `_fits_at` and the
    # audit must all agree — a screen that rejected this while the audit found nothing wrong
    # would be one rule enforced at two strengths.
    var ms_d = _f(0.0, 2.0)
    var ms_dem = _f(9.0, 2.0)
    var ms_r = rcpsp_sgs_solve_flat(ms_d, ms_dem, cap3, _i(0), _i(1), 2, 1, 3, 1)
    var ms_a = rcpsp_verify_flat(ms_d, ms_dem, cap3, _i(0), _i(1), 2, 1, ms_r.start)
    var ms_p = rcpsp_peak_usage_flat(ms_d, ms_dem, cap3, 2, 1, ms_r.start)
    if (
        ms_r.status == SCHED_OPTIMAL
        and ms_r.makespan == 2.0
        and _same_f(ms_r.start, _f(0.0, 0.0))
        and ms_a.status == MODEL_OK
        and ms_a.feasible
        and ms_p.peak[0] == 2.0
        and ms_p.n_over == 0
    ):
        passed += 1
        print("  ✅ a milestone consumes nothing: screen, solver and audit all agree")
    else:
        failed += 1
        print(
            "  ❌ milestone convention:", ms_r.status, ms_r.makespan, ms_a.status,
            ms_p.peak[0], ms_p.n_over
        )

    # ── a tolerance floored at scale 1.0 is an ABSOLUTE allowance (rule 4b) ──
    # `_rel_slop` used `max(1, |a|, |b|)` as the magnitude of the compared quantities, so every
    # comparison below unit magnitude carried a flat 1024 * DBL_EPSILON ~= 2.27e-13 of slop —
    # sized by nothing in the instance and, at these magnitudes, larger than the whole quantity
    # being judged. The measured consequence, verbatim: `rcpsp_bound_flat` claimed no schedule
    # finishes before t = 10 while `rcpsp_verify_flat` certified `start = [0.0]` as feasible with
    # a makespan of 1.0, and `rcpsp_sgs_solve_flat` — having built exactly that schedule and
    # noticed the contradiction — withheld everything under `SCHED_ERR_UNVERIFIED`, an
    # internal-defect status handed to a caller for a legitimate input.
    #
    # Sized by DBL_EPSILON against the demand and the capacity themselves, 1e-13 against a
    # capacity of 1e-14 is 10x over and all three functions now say the same thing: infeasible.
    var tiny_d = _f(1.0)
    var tiny_dem = _f(1.0e-13)
    var tiny_cap = _f(1.0e-14)
    var tiny_b = rcpsp_bound_flat(tiny_d, tiny_dem, tiny_cap, none_i, none_i, 1, 1)
    var tiny_v = rcpsp_verify_flat(
        tiny_d, tiny_dem, tiny_cap, none_i, none_i, 1, 1, _f(0.0)
    )
    var tiny_s = rcpsp_sgs_solve_flat(
        tiny_d, tiny_dem, tiny_cap, none_i, none_i, 1, 1, 3, 1
    )
    # Read out of the arrays rather than written as `1.0e-13 - 1.0e-14`: a `FloatLiteral`
    # expression is folded at arbitrary precision and then rounded once, which is NOT the
    # Float64 subtraction the audit performs.
    var tiny_excess = tiny_dem[0] - tiny_cap[0]
    # The zero-capacity form is worse, because 0.0 is an ordinary value: the screen passed it
    # (1e-13 > 0.0 + 2.27e-13 is False) and execution reached the `capacity <= 0` branch inside
    # `_rcpsp_bound` whose own comment says it cannot be reached.
    var zero_cap = _f(0.0)
    var zc_b = rcpsp_bound_flat(tiny_d, tiny_dem, zero_cap, none_i, none_i, 1, 1)
    var zc_v = rcpsp_verify_flat(
        tiny_d, _f(2.0e-13), zero_cap, none_i, none_i, 1, 1, _f(0.0)
    )
    var zc_s = rcpsp_sgs_solve_flat(tiny_d, tiny_dem, zero_cap, none_i, none_i, 1, 1, 3, 1)
    if (
        tiny_b.status == SCHED_RESOURCE_INFEASIBLE
        and not tiny_b.has_bound
        and tiny_b.lower_bound == SCHED_ABSENT
        and tiny_b.binding_resource == 0
        and tiny_v.status == SCHED_VIOLATION
        and tiny_v.violation == SCHED_VIOL_RESOURCE_OVER_CAPACITY
        and not tiny_v.feasible
        and tiny_v.worst_violation == tiny_excess
        and tiny_s.status == SCHED_RESOURCE_INFEASIBLE
        and tiny_s.infeasible_act == 0
        and tiny_s.infeasible_resource == 0
        and zc_b.status == SCHED_RESOURCE_INFEASIBLE
        and zc_v.status == SCHED_VIOLATION
        and zc_v.violation == SCHED_VIOL_RESOURCE_OVER_CAPACITY
        and zc_s.status == SCHED_RESOURCE_INFEASIBLE
        and zc_s.infeasible_resource == 0
    ):
        passed += 1
        print("  ✅ 1e-13 of demand against 1e-14 (and against 0.0) of capacity is refused")
    else:
        failed += 1
        print(
            "  ❌ sub-unit capacity:", tiny_b.status, tiny_b.lower_bound, tiny_v.status,
            tiny_v.violation, tiny_v.worst_violation, tiny_s.status, zc_b.status,
            zc_v.status, zc_s.status
        )

    # ── the same floor certified a total collision on the machine side ───────
    # Two operations of duration 1e-13 both starting at 0.0 on ONE machine occupy it
    # simultaneously for their ENTIRE duration, and were reported `MODEL_OK, feasible = True`.
    # The pair below is what makes the fix meaningful rather than merely strict: the exact
    # hand-off at 1e-13 and a 1e-27 discrepancy at magnitude 1e-13 must both remain clean.
    var nano_d = _f(1.0e-13, 1.0e-13)
    var nano_m = _i(0, 0)
    var nano_bad = jobshop_verify_flat(nano_d, nano_m, 2, 1, 1, _f(0.0, 0.0))
    var nano_handoff = jobshop_verify_flat(nano_d, nano_m, 2, 1, 1, _f(0.0, 1.0e-13))
    var nano_noise = jobshop_verify_flat(
        nano_d, nano_m, 2, 1, 1, _f(0.0, 9.99999999999999e-14)
    )
    if (
        nano_bad.status == SCHED_VIOLATION
        and nano_bad.violation == SCHED_VIOL_MACHINE_OVERLAP
        and not nano_bad.feasible
        and nano_bad.worst_violation == 1.0e-13
        and nano_bad.n_violations == 1
        and nano_handoff.status == MODEL_OK
        and nano_handoff.feasible
        and nano_noise.status == MODEL_OK
        and nano_noise.feasible
    ):
        passed += 1
        print("  ✅ a 1e-13 collision is a collision; a 1e-13 hand-off and 1e-27 are not")
    else:
        failed += 1
        print(
            "  ❌ sub-unit overlap:", nano_bad.status, nano_bad.violation,
            nano_bad.worst_violation, nano_handoff.status, nano_noise.status
        )

    # ── a bound may never exceed a makespan this module certifies feasible ───
    # Asserted as a property, over every RCPSP instance in this file plus the two that produced
    # the contradiction, because the defect was a mismatch between two code paths' tolerances
    # and not a wrong constant. `bound_never` holding is the invariant; `clamp_b` pins the
    # clamp that makes it hold when the area quotient rounds UP past the serial makespan —
    # 1e-14 / 9.999999999999999e-15 is 1.0000000000000002, and a schedule of makespan 1.0
    # verifies feasible, so the unclamped quotient is a lower bound above a reachable makespan.
    var ser30_d = List[Float64]()
    var ser30_dem = List[Float64]()
    for _ in range(30):
        ser30_d.append(0.1)
        ser30_dem.append(1.0)
    var ser30_start = List[Float64]()
    for k in range(30):
        ser30_start.append(0.1 * Float64(k))
    var hair = _f(9.999999999999999e-15)
    var clamp_b = rcpsp_bound_flat(tiny_d, _f(1.0e-14), hair, none_i, none_i, 1, 1)
    var clamp_v = rcpsp_verify_flat(
        tiny_d, _f(1.0e-14), hair, none_i, none_i, 1, 1, _f(0.0)
    )
    var bound_never = (
        _bound_at_most_verified(two_d, two_dem, cap3, none_i, none_i, 2, 1, _f(0.0, 3.0))
        and _bound_at_most_verified(
            ch_d, ch_dem, cap2, _i(0, 1), _i(1, 2), 3, 1, _f(0.0, 1.0, 3.0)
        )
        and _bound_at_most_verified(
            pk_d, pk_dem, cap2, none_i, none_i, 3, 1, _f(2.0, 0.0, 0.0)
        )
        and _bound_at_most_verified(
            ser_d, ser_dem, cap1, none_i, none_i, 4, 1, _f(0.0, 1.0, 2.0, 3.0)
        )
        and _bound_at_most_verified(ms_d, ms_dem, cap3, _i(0), _i(1), 2, 1, _f(0.0, 0.0))
        and _bound_at_most_verified(
            tiny_d, tiny_dem, tiny_cap, none_i, none_i, 1, 1, _f(0.0)
        )
        and _bound_at_most_verified(tiny_d, tiny_dem, zero_cap, none_i, none_i, 1, 1, _f(0.0))
        and _bound_at_most_verified(tiny_d, _f(1.0e-14), hair, none_i, none_i, 1, 1, _f(0.0))
        and _bound_at_most_verified(
            tiny_d, _f(1.0e-14), _f(1.0e-14), none_i, none_i, 1, 1, _f(0.0)
        )
        and _bound_at_most_verified(
            ser30_d, ser30_dem, cap1, none_i, none_i, 30, 1, ser30_start
        )
    )
    if (
        bound_never
        and clamp_v.feasible
        and clamp_v.makespan == 1.0
        and clamp_b.has_bound
        and clamp_b.lower_bound <= 1.0
        and clamp_b.resource_bound <= 1.0
    ):
        passed += 1
        print("  ✅ no lower bound exceeds a makespan the verifier certifies, ever")
    else:
        failed += 1
        print(
            "  ❌ bound vs verifier:", bound_never, clamp_b.lower_bound,
            clamp_b.resource_bound, clamp_v.feasible, clamp_v.makespan
        )

    # ── a zero-length milestone collides with nothing (one rule, one strength) ─
    # Operation 2 is a milestone occupying [5, 5) on machine 0 while operation 0 occupies
    # [0, 10). Every job precedence holds and no two operations share any instant, but the
    # pairwise form `end_a > start_b and end_b > start_a` is positive in both directions for an
    # EMPTY interval, so this valid schedule came back `SCHED_VIOLATION / machine_overlap` with
    # `worst_violation = 0.0` — the code's own evidence that nothing collided. The second case
    # is the guard against over-correcting: give operation 2 a real duration and the collision
    # must reappear, with the length of the shared interval as its magnitude.
    var mile_d = _f(10.0, 0.0, 0.0, 0.0)
    var mile_m = _i(0, 1, 0, 1)
    var mile_ok = jobshop_verify_flat(mile_d, mile_m, 2, 2, 2, _f(0.0, 10.0, 5.0, 5.0))
    var mile_bad = jobshop_verify_flat(
        _f(10.0, 0.0, 2.0, 0.0), mile_m, 2, 2, 2, _f(0.0, 10.0, 5.0, 7.0)
    )
    if (
        mile_ok.status == MODEL_OK
        and mile_ok.feasible
        and mile_ok.violation == SCHED_VIOL_NONE
        and mile_ok.n_violations == 0
        and mile_ok.worst_violation == 0.0
        and mile_ok.makespan == 10.0
        and mile_bad.status == SCHED_VIOLATION
        and mile_bad.violation == SCHED_VIOL_MACHINE_OVERLAP
        and mile_bad.first_op == 0
        and mile_bad.second_op == 2
        and mile_bad.time == 5.0
        and mile_bad.worst_violation == 2.0
        and mile_bad.n_violations == 1
    ):
        passed += 1
        print("  ✅ a [5, 5) milestone inside [0, 10) is not an overlap; [5, 7) is")
    else:
        failed += 1
        print(
            "  ❌ milestone overlap:", mile_ok.status, mile_ok.violation,
            mile_ok.worst_violation, mile_bad.violation, mile_bad.worst_violation,
            mile_bad.second_op, mile_bad.n_violations
        )

    # ── a machine count charged against MEMORY was not charged against WORK ──
    # 20 operations (4 jobs x 5 ops) using machines 0-4, declaring 2,000,000 of them. That
    # satisfies `n + n_machines <= SCHED_MAX_UNITS`, so the ALLOCATION ceiling admits it, and
    # nothing in the payload has to use a machine. `_mach_pred_of` and `_ranks_of` each scan
    # every machine block on EVERY tabu trial, but the counter charged only `n`: measured 3.57 s
    # at 200 iterations and 30.89 s at 2,000, both with `work_limit_hit = False` and charged work
    # of 47M against the 134M ceiling — extrapolating to ~4.5 hours at the permitted `max_iters`
    # from a ~200 byte request, which presents to a client as a hang.
    #
    # Both directions are asserted. The 2,000,000-machine run must report the limit it hit, and
    # the identical instance with 5 machines must NOT — a counter that always trips would pass
    # the first assertion and destroy the search.
    var hang_d = _f(
        3.0, 2.0, 4.0, 1.0, 5.0,
        2.0, 4.0, 3.0, 5.0, 1.0,
        4.0, 1.0, 2.0, 3.0, 5.0,
        1.0, 5.0, 3.0, 2.0, 4.0,
    )
    var hang_m = _i(
        0, 1, 2, 3, 4,
        1, 0, 3, 2, 4,
        2, 3, 0, 4, 1,
        3, 4, 1, 0, 2,
    )
    var many_mach = jobshop_tabu_solve_flat(hang_d, hang_m, 4, 5, 2000000, 11, 2000, 7, 4)
    var few_mach = jobshop_tabu_solve_flat(hang_d, hang_m, 4, 5, 5, 11, 2000, 7, 4)
    # The ranks driver charges `n * n_machines` for `_seq_from_ranks` the same way, and this
    # 4-operation orientation stays inside the budget, so it must still answer.
    var many_ranks = jobshop_schedule_from_ranks_flat(
        _dur22(), _mach22(), 2, 2, 2000000, _i(0, 1, 0, 1)
    )
    # `tabu_tenure` is the same shape of under-count found by sweeping the rest of the module:
    # bounded only by `SCHED_MAX_TENURE`, scanned once per candidate INSIDE the neighbourhood
    # loop, and charged as nothing. Measured before the fix on this 9-operation instance: 24 ms
    # at 2,000 iterations and 236 ms at 20,000, linear in `max_iters`, with `work_limit_hit`
    # always False. The pair is asserted for the same reason as the machine count — the maximum
    # tenure must now trip the budget, and a tenure of 4 on the same instance must not.
    var big_tenure = jobshop_tabu_solve_flat(d33, m33, 3, 3, 3, 1, 200000, 4096, 4)
    var small_tenure = jobshop_tabu_solve_flat(d33, m33, 3, 3, 3, 1, 200000, 4, 4)
    if (
        big_tenure.work_limit_hit
        and big_tenure.status == SCHED_LIMIT
        and big_tenure.verified
        and big_tenure.iterations < 200000
        and not small_tenure.work_limit_hit
        and small_tenure.iterations == 200000
        and many_mach.work_limit_hit
        and many_mach.status == SCHED_LIMIT
        and many_mach.verified
        and many_mach.iterations < 2000
        and many_mach.lower_bound == 17.0
        and not few_mach.work_limit_hit
        and few_mach.iterations == 2000
        and few_mach.makespan == many_mach.makespan
        and many_ranks.status == SCHED_OPTIMAL
        and many_ranks.makespan == 7.0
    ):
        passed += 1
        print("  ✅ unused machines and a 4096 tabu tenure trip the budget, not a hang")
    else:
        failed += 1
        print(
            "  ❌ machine work budget:", many_mach.status, many_mach.work_limit_hit,
            many_mach.iterations, many_mach.makespan, few_mach.work_limit_hit,
            few_mach.iterations, few_mach.makespan, many_ranks.status,
            big_tenure.work_limit_hit, big_tenure.iterations,
            small_tenure.work_limit_hit, small_tenure.iterations
        )

    # ── the peak profile refuses the starts the verdict function refuses ─────
    # One invariant, one strength (rule 3). `rcpsp_peak_usage_flat` validated only finiteness, so
    # a schedule beginning at -5 came back `MODEL_OK` with a usable-looking profile and a
    # makespan of 1.0 computed as `max(start + duration)` alone, while `rcpsp_verify_flat` on the
    # same arrays returned `negative_start_time`. And `peak_time` was initialised to 0.0 and left
    # there for a resource nothing demands, naming an instant that need not belong to the
    # schedule at all; absent is the only honest answer.
    var pk_neg = rcpsp_peak_usage_flat(ser_d, ser_dem, cap2, 4, 1, _f(-5.0, 0.0, 1.0, 2.0))
    var pk_neg_v = rcpsp_verify_flat(
        ser_d, ser_dem, cap2, none_i, none_i, 4, 1, _f(-5.0, 0.0, 1.0, 2.0)
    )
    var pk_nf = rcpsp_peak_usage_flat(
        ser_d, ser_dem, cap2, 4, 1, _f(infinite, 0.0, 1.0, 2.0)
    )
    var pk_absent = rcpsp_peak_usage_flat(_f(0.0), _f(1.0), _f(1.0), 1, 1, _f(0.0))
    if (
        pk_neg.status == SCHED_VIOLATION
        and len(pk_neg.peak) == 0
        and len(pk_neg.peak_time) == 0
        and not pk_neg.has_makespan
        and pk_neg_v.status == SCHED_VIOLATION
        and pk_neg_v.violation == SCHED_VIOL_NEGATIVE_START
        and pk_nf.status == SCHED_VIOLATION
        and pk_absent.status == MODEL_OK
        and pk_absent.peak[0] == 0.0
        and pk_absent.peak_time[0] == SCHED_ABSENT
        and pk_absent.n_over == 0
    ):
        passed += 1
        print("  ✅ the peak profile refuses a negative start; an unmeasured peak has no time")
    else:
        failed += 1
        print(
            "  ❌ peak invariants:", pk_neg.status, len(pk_neg.peak), pk_neg_v.violation,
            pk_nf.status, pk_absent.peak[0], pk_absent.peak_time[0]
        )

    # ── one name per status code, all distinct, and the shared chain intact ──
    # A duplicated name makes two defects indistinguishable in a log, which is the same
    # failure as a duplicated code — and codes 130-139 are this module's whole allocation.
    var names = List[String]()
    for code in range(130, 140):
        names.append(sched_status_name(code))
    var distinct = True
    for i in range(len(names)):
        # Falling through to the model chain would name a code of this module
        # "unknown_status_<code>", which is the symptom of a code with no entry.
        var unknown = String("unknown_status_")
        unknown += String(130 + i)
        if names[i] == unknown:
            distinct = False
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                distinct = False
    var chain_intact = (
        sched_status_name(MODEL_OK) == "ok"
        and sched_status_name(MODEL_ERR_LENGTH_MISMATCH)
        == "parallel_arrays_length_mismatch"
        and sched_status_name(MODEL_ERR_DIMENSION_TOO_LARGE) == "dimension_too_large"
        and sched_status_name(129) == "unknown_status_129"
        and sched_status_name(140) == "unknown_status_140"
    )
    var viol_names = List[String]()
    for kind in range(0, 6):
        viol_names.append(sched_violation_name(kind))
    var viol_distinct = True
    for i in range(len(viol_names)):
        if viol_names[i] == "unknown_violation":
            viol_distinct = False
        for j in range(i + 1, len(viol_names)):
            if viol_names[i] == viol_names[j]:
                viol_distinct = False
    if (
        distinct
        and chain_intact
        and viol_distinct
        and sched_violation_name(6) == "unknown_violation"
        and SCHED_ERR_WORK_BUDGET == 139
        and SCHED_ERR_UNVERIFIED == 136
    ):
        passed += 1
        print("  ✅ 130-139 have ten distinct names; the model chain still answers 0/1/2")
    else:
        failed += 1
        print("  ❌ status names:", distinct, chain_intact, viol_distinct)

    print("  [optimization.scheduling] Passed:", passed, "Failed:", failed)
