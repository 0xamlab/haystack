"""
optimization.scheduling — job-shop tabu search and RCPSP, where the schedule is VERIFIED
against the caller's own constraints before it is returned, and the bound is the only thing
allowed to claim optimality. Zero Python.

Why this file exists
--------------------
Nothing in the tree schedules a shop or a project.

  * `scheduling_algo.mojo` is CPU scheduling on ONE server — `fcfs`, `sjf`,
    `priority_scheduling`, `round_robin`. It takes and returns `List[List[Int]]`, so it
    cannot cross the wire at all, its times are `Int`, and it has no concept of a machine
    routing, a disjunctive arc or a renewable resource.
  * `scheduler.mojo`'s `Scheduler.critical_path()` is the tree's only critical path. It is
    `Int`-only, it is a struct-taking API, and — the reason it cannot be wrapped here — it
    returns a NUMBER for a cyclic dependency graph: Kahn's queue drains early, every task
    on or after the cycle keeps `dist = 0`, and the result is a plausible `total_time` for
    a project that cannot be executed at all. A cycle is precisely the failure a
    disjunctive-arc flip creates, so a driver that inherits that silence is unusable.
  * `graph.algorithms.topological_sort` is frozen, correct, and returns a SHORT order for a
    cyclic graph, which is exactly the certificate the above is missing. It is the cycle
    oracle for every schedule this module builds, and the order its longest-path DP runs
    in.

Why not Dijkstra
----------------
`graph.algorithms.dijkstra` is frozen and is deliberately NOT used for the critical path. A
critical path is a LONGEST path; Dijkstra computes a shortest one and its greedy invariant
requires non-negative weights, so the usual trick — negate the durations — makes every
weight non-positive and Dijkstra returns a wrong number rather than an error. The frozen
kernel that legitimately serves a longest path is `topological_sort`, because a DAG's
longest path is a one-pass DP in topological order, and that is what runs here. The frozen
`heap` IS used, for the RCPSP decision-point queue where the keys really are wanted in
ascending order.

A heuristic result is not an optimum, and this module never pretends otherwise
------------------------------------------------------------------------------
Tabu search and a serial schedule-generation scheme are HEURISTICS. There is therefore no
`proven_optimal` flag anywhere in this file. What there is:

  * `lower_bound` — a bound this module actually holds and can defend. For the job shop it
    is `max(longest job chain, heaviest machine load)`; both are valid because every
    operation of a job runs in sequence and every operation on a machine runs one at a
    time. For the RCPSP it is `max(critical path through the precedences, Σ dᵢ·rᵢ / capᵣ)`;
    the second is valid because `[0, T]` offers only `T·capᵣ` resource-time.
  * `makespan` — the incumbent, which is an UPPER bound.
  * `gap` = incumbent − bound, and `optimal_by_bound`, which is true only when the two
    MEET. That flag is a statement about the bound, never about the search: no amount of
    local search proves a makespan optimal, and a status of `SCHED_OPTIMAL` here means "the
    bound closed", nothing else.
  * a makespan BELOW the lower bound is a contradiction between two things this file
    computed, so it is reported as `SCHED_ERR_UNVERIFIED` with no numbers rather than
    returned as a record-breaking answer.

Every returned schedule is verified, and the verifier is the public one
----------------------------------------------------------------------
`jobshop_tabu_solve_flat` runs its final schedule through the same code path as
`jobshop_verify_flat`, and `rcpsp_sgs_solve_flat` through `rcpsp_verify_flat`. Precedence,
machine exclusivity and the resource profile are re-checked against the CALLER's arrays,
not against the search's internal bookkeeping — a schedule that satisfies a bug's idea of
the constraints is the exact failure this costs an O(n²) pass to prevent. If verification
fails, the answer is withheld under `SCHED_ERR_UNVERIFIED`: an unverified schedule must
never leave under a success status.

The disjunctive cycle is checked on EVERY neighbour, not argued away
-------------------------------------------------------------------
Van Laarhoven's theorem says reversing a single critical machine arc cannot create a cycle,
and this module does not rely on it. Every trial orientation goes through
`topological_sort`, and a short order means the neighbour is discarded and counted in
`cycles_rejected`. The theorem is a reason to expect the count to be zero, not a substitute
for looking: an implementation bug in the critical-path extraction would otherwise produce
a makespan computed from a cyclic graph, which is finite, wrong, and silent.

Tolerances scale with what they judge (rule 4b)
-----------------------------------------------
Every comparison here — a precedence, an overlap, a capacity — is between two quantities of
a known magnitude, and its allowance is `(SCHED_ULP_BUDGET + terms) · DBL_EPSILON · scale`
where `scale` is `max(|a|, |b|)` over exactly THOSE quantities and `terms` is the number of
additions that produced the sum being judged. Nothing sums over the instance. A tolerance
built from `Σᵢ durationᵢ` would let a long project's units pay for a short activity's
overlap, and a plain relative test (`violation / (1 + magnitude)`) shrinks with the magnitude
while the violation does not — 200 units of overlap at time 1e9 is 4.5 million ulps and
unambiguously real. `terms` is included because a usage sum over `k` activities can
accumulate `k` ulps; it is the length of THAT sum, not a count of anything else.

`scale` has NO FLOOR, and that is the other half of the rule. `max(1, |a|, |b|)` is not the
magnitude of `a` and `b` when both are below 1 — it is an ABSOLUTE allowance of
`1024 · DBL_EPSILON` handed to every small comparison, sized by nothing in the problem. It
shipped that way, and it was measured: two operations of duration 1e-13 starting at the same
instant on one machine verified as a valid schedule, a demand of 2e-13 verified against a
capacity of exactly 0.0, and `rcpsp_bound_flat` returned a "lower bound" of 10.0 for an
instance whose own verifier certified a makespan of 1.0 — because the screen was tolerant by
2.27e-13 while the area bound divided exactly. A floor that dominates the judged magnitude is
the same defect as an aggregate that dominates it (rule 4b); both let something other than
the quantity being judged decide the verdict. See `_rel_slop`.

A bound is also checked against a makespan that DEMONSTRABLY exists. Every activity fits
alone (that is what the pre-search capacity screen proves), so running them one at a time in
topological order is always feasible and `Σᵢ durationᵢ` is always an ACHIEVABLE makespan.
`_rcpsp_bound` therefore clamps its lower bound there: a lower bound above a reachable
makespan is not a bound, it is a contradiction, and it must not be expressible.

Ceilings (rule 1c)
------------------
`sparse_numerics.csr.MAX_CSR_DIM` is the one shared dimension ceiling and is imported, not
redefined or lowered. It is justified there as the largest single pointer array the 512 MiB
resident-dataset budget tolerates — ONE object. This module holds far more than one array
per unit of its dimensions: per operation there are `start`, `finish`, `crit_pred`,
`mach_pred`, `pos_in_seq`, `seq`, `best_seq`, the topological order, the seen mask, the
critical path, the machine buckets and — the expensive one — the frozen `Graph`, which
allocates TWO `List`s per node. `SCHED_UNIT_ARRAYS = 32` is that count with headroom, and
`SCHED_MAX_UNITS = MAX_CSR_DIM // SCHED_UNIT_ARRAYS` makes `units × arrays × 8 bytes` equal
the same 512 MiB, for the whole request instead of for one array.

The bound is also tied to the PAYLOAD and not merely to the ceiling. `n_jobs × n_ops` is
proven equal to `len(duration)` by `sparse_numerics.csr.dims_fit`, which divides instead of
multiplying because `rows * cols == length` is a wrapping 64-bit multiply and therefore not
a bound at all (`3 * 6148914691236517206 == 2`). `n_machines` is charged against the same
unit budget alongside the operation count, because a machine no operation uses still costs
a bucket offset. Nothing here takes a dimension that the arrays do not have to match.

Work is bounded separately, because the work is not linear
----------------------------------------------------------
Machine exclusivity and a resource profile are PAIRWISE statements ("no two operations on
one machine overlap", "the activities running at this instant fit"), and they are checked as
such rather than by sorting: the check is then the constraint itself, with no reliance on an
ordering being right. That is quadratic, and the serial SGS is worse. So an inner-step
counter is charged against `SCHED_MAX_WORK`, and tripping it is a STATUS:
`SCHED_ERR_WORK_BUDGET` when there is no verified schedule to report, and `SCHED_LIMIT` with
`work_limit_hit` when there is one. A verifier that gives up returns neither "valid" nor
"invalid" — 139 is not a pass.

EVERY loop bound that multiplies into the cost is charged, `n_machines` included, and that
qualifier is the whole point. Bounding MEMORY is not bounding WORK: `n_machines` was inside
the allocation ceiling and tied to nothing in the payload, and `_mach_pred_of` and `_ranks_of`
each scan every machine block on EVERY tabu trial. Charging only `n` per trial let 20
operations plus a declared 2,000,000 machines — a ~200 byte request — spend 3.6 s at 200
iterations and 31 s at 2,000, with `work_limit_hit = False` and charged work of 47M against a
134M ceiling. Extrapolated to the permitted `max_iters`, ~4.5 hours inside the worker, which
presents to a client as a hang and takes every resident dataset with it. A trial now costs
`n + n_machines`, a dispatch `n · n_jobs + n_machines`, `_seq_from_ranks` `n · n_machines`,
and `_jssp_audit` starts its counter at `n + n_machines`. `tabu_tenure` is in the trial cost
for the same reason — the tabu scan sits inside the candidate loop, and a range check on a
parameter is not a work bound either.

Determinism, and the tie-break rules in full
--------------------------------------------
A heuristic whose answer moves between runs cannot be used in a decision that has to be
explained, which is the whole reason this package exists. So there is no `random_float64`
and no `seed(` anywhere here: every draw comes from `determinism/`, which is counter-based,
so a draw is a pure function of its coordinates and is identical no matter what the search
did beforehand.

  * `_op_key(seed, restart, op)` = `rng_uniform` at coordinates
    `(master_seed = seed, replication_id = restart, dim0 = op)`. It is a tie-break of the
    dispatch, so it depends on the unit being ordered and not on the order of the scan.
  * the tabu neighbourhood is scanned in `permutation_keyed(n_cand, seed, stream,
    iteration × n_operations)` order. The stride is the operation count, which is `≥ n_cand`
    because the critical path visits each operation at most once, so no two iterations share
    a draw coordinate.
  * three named streams — `optimization.scheduling.jobshop`, `...jobshop.neighbourhood` and
    `...rcpsp` — so the construction, the neighbourhood scan and the project search never
    consume each other's draws.

Job-shop dispatch, in priority order: smallest earliest start; then shortest duration; then
smallest `_op_key`; then smallest machine index; then smallest operation id. The keyed draw
sits above the machine index because below it, it was unreachable — see `_dispatch`, where the
consequence was that every seed produced the same schedule. A tabu move is
chosen by: smallest trial makespan; then earliest position in the keyed scan order.
Longest-path ties prefer the CHAIN predecessor over the machine predecessor, so the critical
path an equal-length pair produces is fixed. RCPSP restart 0 lists activities by largest
tail (most-total-successors first), ties by smallest `_op_key`, then smallest id; every
later restart lists them by smallest `_op_key` among the eligible set, which is a uniform
keyed random activity list.

Status codes (rule 4e)
----------------------
This module owns 130-139 and emits nothing else of its own. Already handed out in the shared
`optimization.model` status chain: 0-30 model, 40-42 lin, 60-63 lp, 80-86 explain, 100-105
milp. (`optimization.flow` 0-21 and `optimization.assignment` 0-13 are self-contained
namespaces with their own tables and are not part of this chain.) Two SHARED model codes are
reused rather than duplicated, exactly as `linear` and `explain` reuse them:
`MODEL_ERR_LENGTH_MISMATCH` (1) for arrays that do not match the declared dimensions and
`MODEL_ERR_DIMENSION_TOO_LARGE` (2) for the allocation ceiling. A clean audit returns
`MODEL_OK` (0). `sched_status_name` falls through to `model_status_name`, so one integer has
one meaning across the package.

`SCHED_VIOL_*` are NOT status codes. They are a separate vocabulary naming WHICH constraint
an audited schedule broke, and they live in their own numbering starting at 0.
"""
from std.math import abs as fabs

from determinism.counter_rng import rng_uniform
from determinism.sampling_keyed import permutation_keyed
from determinism.streams import stream_id
from graph.algorithms import Graph, graph_add_edge, graph_new, topological_sort
from heap import heap_pop_min, heap_push_min
from optimization.model import MODEL_ERR_DIMENSION_TOO_LARGE
from optimization.model import MODEL_ERR_LENGTH_MISMATCH
from optimization.model import MODEL_OK
from optimization.model import model_finite as _finite
from optimization.model import model_status_name
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes: 130-139, and only 130-139 ───────────────────────────────────
# See the module docstring for the ranges the rest of the package already holds. A caller
# that logs an integer has to be able to recover one meaning from it, which is why nothing
# below re-uses a number another module in this package already spent.

# A verified schedule whose makespan MEETS the lower bound. Optimality here follows from the
# BOUND, never from the search — see `optimal_by_bound`.
comptime SCHED_OPTIMAL: Int = 130
# A verified schedule with a positive gap, and the driver had nothing further to offer: an
# orientation was priced exactly as asked (`jobshop_schedule_from_ranks_flat`), or no search
# budget was requested at all (`rcpsp_sgs_solve_flat` with `max_restarts == 0`).
#
# NOT reachable from `jobshop_tabu_solve_flat`'s empty-neighbourhood exit, and the reason is
# worth recording so nobody "fixes" that branch into a wrong status: if the critical path
# contains no machine arc then every arc on it is a job arc, its first operation starts at 0
# (that is what `crit_pred == -1` means), and each following start equals the previous finish —
# so the makespan is the sum of durations along a sub-chain of ONE job, which is at most the
# job bound, which is at most `lower_bound`. Since the makespan is also at least the bound, the
# two are equal and the search already exited as `SCHED_OPTIMAL`. The branch stays because it
# is what stops the loop from spinning if that reasoning ever ceases to hold.
comptime SCHED_FEASIBLE: Int = 131
# A verified schedule with a positive gap, and a LIMIT stopped the search — the iteration
# budget, the restart budget or the work ceiling. More budget could plausibly help.
comptime SCHED_LIMIT: Int = 132
# The precedence graph (or the caller's disjunctive orientation) contains a cycle, so NO
# schedule exists. `cycle_op` names one operation on or downstream of the cycle.
comptime SCHED_PRECEDENCE_CYCLE: Int = 133
# One activity demands more of a resource than that resource's capacity, so no schedule
# exists at any time. The activity and the resource are both reported.
comptime SCHED_RESOURCE_INFEASIBLE: Int = 134
# An AUDITED schedule (the caller's own) violates a constraint. The `violation` field says
# which, with the operations, the machine or the resource, and the time. `rcpsp_peak_usage_flat`
# also returns it for a non-finite or negative start — the same strength `_rcpsp_audit` applies to
# the same invariant — but carries no `violation` field, so `rcpsp_verify_flat` is where the KIND
# comes from.
comptime SCHED_VIOLATION: Int = 135
# INTERNAL DEFECT, surfaced instead of an answer: a schedule this module built failed the
# verification it must pass, or two quantities it computed contradict each other. No numbers
# are returned under this status.
comptime SCHED_ERR_UNVERIFIED: Int = 136
# A duration, demand, capacity, index or search parameter the driver cannot use: negative,
# non-finite, or out of range.
comptime SCHED_ERR_INVALID_VALUE: Int = 137
# There is nothing to schedule (no jobs, no operations, no machines, no activities). The
# makespan of nothing is arguably 0.0, but its critical path and its gap do not exist, so
# the request is rejected rather than answered with a number that explains nothing.
comptime SCHED_ERR_EMPTY_INSTANCE: Int = 138
# The pairwise verification or the search exceeded `SCHED_MAX_WORK` inner steps before any
# verified schedule existed. NOT a pass: no verdict was reached.
comptime SCHED_ERR_WORK_BUDGET: Int = 139

# ── violation kinds: a separate vocabulary, NOT status codes ──────────────────

comptime SCHED_VIOL_NONE: Int = 0
comptime SCHED_VIOL_NON_FINITE_START: Int = 1
comptime SCHED_VIOL_NEGATIVE_START: Int = 2
comptime SCHED_VIOL_PRECEDENCE: Int = 3
comptime SCHED_VIOL_MACHINE_OVERLAP: Int = 4
comptime SCHED_VIOL_RESOURCE_OVER_CAPACITY: Int = 5

# ── absence markers ───────────────────────────────────────────────────────────
# A magnitude cannot be negative, so -1.0 says "never measured", the convention
# `model.MODEL_VIOLATION_ABSENT` and `linear.LP_INFEASIBILITY_ABSENT` already use. 0.0 would
# read as "no violation", which is the claim these values exist to substantiate.
comptime SCHED_ABSENT: Float64 = -1.0

# ── tolerances ────────────────────────────────────────────────────────────────

# The spacing between consecutive Float64 values at 1.0.
comptime SCHED_DBL_EPSILON: Float64 = 2.220446049250313e-16

# How many ulps of the JUDGED magnitude a comparison may absorb before a violation counts as
# real. Matches `linear.LP_FEAS_ULP_BUDGET`, and generous on purpose: it is a ROUNDING
# budget, which is the only thing a relative term can legitimately explain away. The number
# of additions in the sum being judged is added on top, because a sum of `k` like-magnitude
# terms can accumulate `k` ulps.
comptime SCHED_ULP_BUDGET: Float64 = 1024.0

# ── ceilings ──────────────────────────────────────────────────────────────────

# Arrays this module holds live per unit of its dimensions. Counted on the widest path
# (`jobshop_tabu_solve_flat`): start, finish-derived crit_pred, mach_pred, seq, best_seq,
# pos_in_seq, the topological order, the seen mask, the critical path, two bucket arrays,
# plus the frozen `Graph`, whose constructor allocates TWO `List` headers PER NODE and is
# therefore worth several slots on its own. 32 covers that with headroom; raise it if a new
# per-unit array appears, which is cheaper than discovering the budget was blown by an array
# nobody counted.
comptime SCHED_UNIT_ARRAYS: Int = 32

# The shared ceiling, DIVIDED — never redefined and never lowered, because other packages
# depend on `MAX_CSR_DIM`. 2^26 / 32 = 2^21 units, and 2^21 units x 32 arrays x 8 bytes is
# 512 MiB total: the same single-object budget `csr.mojo` justified, now covering the whole
# request instead of one array. Operations and machines are charged against ONE budget
# together, since a machine that no operation uses still costs a bucket offset.
comptime SCHED_MAX_UNITS: Int = MAX_CSR_DIM // SCHED_UNIT_ARRAYS

# Inner-step budget, separate from the allocation ceiling because the work here is not
# linear in the dimensions: machine exclusivity and the resource profile are pairwise, and
# the serial SGS tries a decision point per placed activity. Tripping it is a status, never
# a silent truncation.
comptime SCHED_MAX_WORK: Int = 1 << 27

# The largest search budget a caller may request. A bigger number is refused rather than
# clamped: silently running a different search than the one asked for is the failure mode.
comptime SCHED_MAX_ITERS: Int = 1 << 20
comptime SCHED_MAX_TENURE: Int = 1 << 12

# Distinguishes a negative seed from a non-negative one without ever negating `Int.MIN`.
comptime SCHED_NEGATIVE_SEED_BIT: UInt64 = 1 << 63


fn sched_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number.

    Falls through to `model_status_name` for the shared codes this module reuses
    (`MODEL_OK`, `MODEL_ERR_LENGTH_MISMATCH`, `MODEL_ERR_DIMENSION_TOO_LARGE`), so one
    integer keeps one meaning across `optimization/`.
    """
    if code == SCHED_OPTIMAL:
        return "optimal_by_lower_bound"
    if code == SCHED_FEASIBLE:
        return "feasible_not_proven_optimal"
    if code == SCHED_LIMIT:
        return "limit_reached_feasible_not_proven_optimal"
    if code == SCHED_PRECEDENCE_CYCLE:
        return "precedence_cycle_no_schedule_exists"
    if code == SCHED_RESOURCE_INFEASIBLE:
        return "demand_exceeds_capacity_no_schedule_exists"
    if code == SCHED_VIOLATION:
        return "audited_schedule_violates_a_constraint"
    if code == SCHED_ERR_UNVERIFIED:
        return "internal_schedule_failed_verification"
    if code == SCHED_ERR_INVALID_VALUE:
        return "invalid_duration_demand_capacity_index_or_parameter"
    if code == SCHED_ERR_EMPTY_INSTANCE:
        return "nothing_to_schedule"
    if code == SCHED_ERR_WORK_BUDGET:
        return "work_budget_exceeded_no_verdict"
    return model_status_name(code)


fn sched_violation_name(kind: Int) -> String:
    """Name for a violation kind. A separate vocabulary from the status codes on purpose."""
    if kind == SCHED_VIOL_NONE:
        return "none"
    if kind == SCHED_VIOL_NON_FINITE_START:
        return "non_finite_start_time"
    if kind == SCHED_VIOL_NEGATIVE_START:
        return "negative_start_time"
    if kind == SCHED_VIOL_PRECEDENCE:
        return "precedence_violated"
    if kind == SCHED_VIOL_MACHINE_OVERLAP:
        return "two_operations_on_one_machine_at_once"
    if kind == SCHED_VIOL_RESOURCE_OVER_CAPACITY:
        return "resource_over_capacity"
    return "unknown_violation"


# ── numeric helpers ───────────────────────────────────────────────────────────


fn _rel_slop(scale: Float64, terms: Int) -> Float64:
    """Rounding allowance for a comparison at magnitude `scale` after `terms` additions.

    `scale` must be the magnitude of the quantities being compared (never a sum over the
    instance) and `terms` the length of the sum being judged. Sized by DBL_EPSILON, not by
    any caller tolerance, so it can only ever absorb what floating point explains.

    There is NO FLOOR on `scale`, and that absence is load-bearing. A floor of 1.0 turns this
    into an ABSOLUTE allowance of `1024 * DBL_EPSILON` for every comparison below unit
    magnitude — a slop sized by nothing in the instance, which can exceed 100% of the quantity
    being judged. Measured, with the floor in place: `jobshop_verify_flat` certified two
    operations of duration 1e-13 both starting at 0.0 on ONE machine as a valid schedule, and
    `rcpsp_verify_flat` certified a demand of 2e-13 against a capacity of exactly 0.0 as
    feasible. That is rule 4b's failure mode inverted — a tolerance that does not SHRINK with
    the thing it judges — and it is the same defect as a tolerance that grows with the
    instance: a flat contradiction absorbed and reported under a success status.

    `scale == 0.0` therefore yields an allowance of exactly 0.0, which is correct: zero is
    exactly representable, so a comparison at magnitude zero has no rounding to forgive.
    """
    var t = Float64(terms)
    if t < 0.0:
        t = 0.0
    var s = scale
    if not _finite(s) or s < 0.0:
        # A non-finite scale would make the allowance NaN, and `x > NaN` is False for EVERY x,
        # so the threshold would pass having counted nothing (rule 4d). No allowance at all is
        # the only safe reading; the comparison then judges the raw quantities.
        s = 0.0
    return (SCHED_ULP_BUDGET + t) * SCHED_DBL_EPSILON * s


fn _scale2(a: Float64, b: Float64) -> Float64:
    """max(|a|, |b|) — the magnitude a comparison between `a` and `b` lives at.

    No 1.0 floor: see `_rel_slop`. Two quantities of magnitude 1e-13 live at 1e-13, and a
    tolerance that pretends they live at 1.0 permits one whole unit of whatever is being
    compared. A non-finite argument contributes nothing rather than poisoning the result.
    """
    var s = 0.0
    if _finite(a) and fabs(a) > s:
        s = fabs(a)
    if _finite(b) and fabs(b) > s:
        s = fabs(b)
    return s


fn _seed_key(seed: Int) -> UInt64:
    """The `master_seed` coordinate for a caller's `seed`, total over every `Int`.

    A negative seed is folded with `~seed` (never `-seed`, which overflows at `Int.MIN`) and
    tagged with the top bit, so the map is injective: seed `-1` does not alias seed `0`.
    """
    if seed >= 0:
        return UInt64(seed)
    return UInt64(~seed) | SCHED_NEGATIVE_SEED_BIT


fn _op_key(key: UInt64, stream: UInt64, restart: Int, op: Int) -> Float64:
    """Keyed priority of one unit — the last tie-break of every construction here.

    A pure function of `(seed, restart, op)`: `rng_uniform` at `master_seed = key`,
    `replication_id = restart`, `dim0 = op`. Because it is addressed by the unit rather than
    consumed in scan order, two seeds explore different dispatch orders while one seed
    reproduces bit-for-bit whatever the search did beforehand.
    """
    var r = restart
    if r < 0:
        r = 0
    var o = op
    if o < 0:
        o = 0
    return rng_uniform(key, 0, UInt64(r), UInt64(o), 0, stream, 0)


# ── return-only result structs ────────────────────────────────────────────────
# Declared in THIS file. `apps/runtime/mojo_inventory.py` parses struct specs one file at a
# time, so a public function returning a struct owned by another module is dropped from the
# contract and from the dispatch with no error anywhere.


@fieldwise_init
struct JobShopBound(Copyable, Movable):
    """Lower bounds on a job shop's makespan, and which job or machine attains them.

    Both bounds are valid, and cheap: a job's operations run in sequence, so the longest job
    chain is a bound; a machine runs one operation at a time, so its total load is a bound.
    `lower_bound` is the larger. `has_bound` is the authority — a rejected instance has no
    bound, and 0.0 would read as "no work to do".
    """

    var status: Int
    var has_bound: Bool
    var lower_bound: Float64
    var job_bound: Float64
    var machine_bound: Float64
    var critical_job: Int
    var critical_machine: Int
    var n_operations: Int
    var total_work: Float64


@fieldwise_init
struct JobShopAudit(Copyable, Movable):
    """The verdict on a schedule SOMEBODY ELSE produced, against the caller's own arrays.

    Conditions covered, all of them, and this list is the promise: every start time finite;
    every start time non-negative; every operation of a job starting no earlier than its
    predecessor finishes; and no two operations sharing a machine overlapping. The first
    violation is described in full (`first_op`, `second_op`, `machine`, `time`), and
    `n_violations` counts every one found so a caller learns whether it has one problem or a
    hundred. `worst_violation` is the largest magnitude in units of TIME: a precedence
    shortfall, or the length of the interval two operations share on one machine.

    "Overlapping" means the shared interval `[max(start), min(finish))` has POSITIVE length,
    which is the same `[t, t)` milestone convention `RcpspAudit`, `_first_over_capacity`,
    `_usage_at` and `_fits_at` apply — one rule at one strength across the file. A
    zero-duration operation occupies no instant and so collides with nothing. The pairwise
    form `end_a > start_b and end_b > start_a` is NOT that predicate: it reported
    `machine_overlap` with `worst_violation = 0.0` for a milestone at `[5, 5)` inside another
    operation's `[0, 10)`, which is a false infeasibility verdict whose own reported magnitude
    said the interval was empty.

    `feasible` is True only when `status == MODEL_OK`. A work-budget stop is
    `SCHED_ERR_WORK_BUDGET` with `feasible = False`: no verdict was reached, and that is not
    a pass.

    `makespan` on a VIOLATING schedule is the span of the caller's own start times — a
    description of what they handed over, not a claim that it is achievable. It is absent
    entirely when a start time is not finite, because then there is no span.
    """

    var status: Int
    var feasible: Bool
    var violation: Int
    var n_violations: Int
    var first_op: Int
    var second_op: Int
    var machine: Int
    var has_time: Bool
    var time: Float64
    var worst_violation: Float64
    var has_makespan: Bool
    var makespan: Float64
    var n_operations: Int


@fieldwise_init
struct JobShopSchedule(Copyable, Movable):
    """The earliest-start schedule of one disjunctive orientation, or the cycle that denies it.

    `start` is the semi-active schedule implied by the machine sequences: every operation as
    early as its job predecessor and its machine predecessor allow. `critical_ops` is the
    chain that produced the makespan, in order, because a makespan with no explanation
    cannot be acted on. `machine_rank` is the normalised 0-based position of each operation
    on its machine, so a caller can feed the answer back in and reproduce it exactly.

    A cyclic orientation has NO schedule: `SCHED_PRECEDENCE_CYCLE`, `cycle_op` naming one
    operation on or downstream of the cycle, `n_ordered` counting how many operations could
    be ordered at all, and every list empty. A makespan computed from a cyclic graph is
    finite and wrong, which is why it is not computed.
    """

    var status: Int
    var feasible: Bool
    var verified: Bool
    var has_makespan: Bool
    var makespan: Float64
    var has_bound: Bool
    var lower_bound: Float64
    var has_gap: Bool
    var gap: Float64
    var optimal_by_bound: Bool
    var cycle_op: Int
    var n_ordered: Int
    var n_operations: Int
    var start: List[Float64]
    var critical_ops: List[Int]
    var machine_rank: List[Int]


@fieldwise_init
struct JobShopResult(Copyable, Movable):
    """A tabu-search schedule, its bound, the gap between them, and the search's own history.

    There is no `proven_optimal` field. `optimal_by_bound` is true when `makespan` meets
    `lower_bound`, which is a statement about the bound; the search itself proves nothing.
    `iteration_limit_hit` / `work_limit_hit` say whether a budget stopped the search, so a
    caller can tell "this is as good as this neighbourhood gets" from "buy more iterations".
    `cycles_rejected` counts trial orientations discarded as cyclic — expected to be zero,
    and reported because a non-zero count is evidence about the neighbourhood, not noise.

    `start` and `machine_rank` are the decision; `critical_ops` is its explanation. All three
    are empty unless the schedule passed verification against the caller's arrays.
    """

    var status: Int
    var feasible: Bool
    var verified: Bool
    var has_makespan: Bool
    var makespan: Float64
    var has_bound: Bool
    var lower_bound: Float64
    var has_gap: Bool
    var gap: Float64
    var has_relative_gap: Bool
    var relative_gap: Float64
    var optimal_by_bound: Bool
    var initial_makespan: Float64
    var iterations: Int
    var moves_evaluated: Int
    var improvements: Int
    var cycles_rejected: Int
    var restarts: Int
    var iteration_limit_hit: Bool
    var work_limit_hit: Bool
    var neighbourhood_exhausted: Bool
    var n_operations: Int
    var start: List[Float64]
    var critical_ops: List[Int]
    var machine_rank: List[Int]


@fieldwise_init
struct RcpspBound(Copyable, Movable):
    """Lower bounds on a project's makespan, plus the critical path that justifies one.

    `cp_bound` is the longest path through the precedences alone — valid because resources
    can only delay. `resource_bound` is `max_r Σᵢ dᵢ·rᵢ / capᵣ`, valid because `[0, T]`
    offers only `T·capᵣ` resource-time. `critical_ops` is the actual path, in order.

    Both are clamped at `Σᵢ dᵢ`, which is an ACHIEVABLE makespan (run the activities one at a
    time in topological order; each fits alone, or the instance was already rejected as
    `SCHED_RESOURCE_INFEASIBLE`). A lower bound above a makespan the same module certifies
    feasible is a contradiction, not a bound, so it is not expressible here — see `_rcpsp_bound`.

    A cycle means no schedule exists and therefore no bound: `SCHED_PRECEDENCE_CYCLE` with
    `cycle_act` naming an activity on or downstream of it.
    """

    var status: Int
    var has_bound: Bool
    var lower_bound: Float64
    var cp_bound: Float64
    var has_resource_bound: Bool
    var resource_bound: Float64
    var binding_resource: Int
    var cycle_act: Int
    var n_ordered: Int
    var n_activities: Int
    var critical_ops: List[Int]


@fieldwise_init
struct RcpspAudit(Copyable, Movable):
    """The verdict on a project schedule, against the caller's precedences AND capacities.

    Conditions covered, all of them: every start finite; every start non-negative; every
    precedence edge satisfied; and, at every instant where the resource profile can peak,
    every resource within its capacity. The profile is piecewise constant and only rises at a
    start, so checking each activity's own start instant covers every maximum — there is no
    instant in between where more is running.

    A violation reports WHERE and WHEN, never just a boolean: `resource`, `time`, the activity
    that was running, and `worst_violation` in the units of the reported `violation` kind —
    resource units for a capacity breach, time for a precedence shortfall.

    A zero-duration activity occupies the empty interval `[t, t)` and therefore consumes
    nothing at any instant — the standard milestone convention, applied identically here, in
    `_fits_at` and in the pre-search capacity screen so that one rule has one strength.
    """

    var status: Int
    var feasible: Bool
    var violation: Int
    var n_violations: Int
    var first_act: Int
    var second_act: Int
    var resource: Int
    var has_time: Bool
    var time: Float64
    var worst_violation: Float64
    var has_makespan: Bool
    var makespan: Float64
    var n_activities: Int


@fieldwise_init
struct RcpspPeak(Copyable, Movable):
    """The peak of each resource's profile under a given schedule, and when it occurs.

    One entry per resource, in resource order: the maximum usage, the earliest instant that
    attains it, and 1 when that maximum exceeds capacity. `n_over` counts the resources over
    capacity, so a caller learns the whole picture instead of the first failure.

    `peak` of a resource nothing demands is 0.0 — the sum of nothing, a real answer — but
    `peak_time` is `SCHED_ABSENT`, because no instant was measured and 0.0 there would name an
    instant that need not belong to the schedule. A schedule with a non-finite or negative start
    has no profile at all: `SCHED_VIOLATION`, every list empty, at the same strength
    `rcpsp_verify_flat` applies (rule 3 — one invariant, one strength).
    """

    var status: Int
    var n_resources: Int
    var n_over: Int
    var has_makespan: Bool
    var makespan: Float64
    var peak: List[Float64]
    var peak_time: List[Float64]
    var over_capacity: List[Int]


@fieldwise_init
struct RcpspResult(Copyable, Movable):
    """A resource-feasible project schedule, its bounds, its gap and its explanation.

    `order` is the activity list that produced the schedule — the decision a planner can
    re-run. `critical_ops` walks back from the last-finishing activity through the
    predecessors that actually determined each start; when a start was set by resource
    availability rather than by a predecessor the walk stops there and
    `resource_delayed_at` names that activity, because "the project is late because of a
    resource, not a dependency" is the answer a caller needs and a precedence path alone
    would misreport.

    No `proven_optimal`. `optimal_by_bound` is true only when the incumbent meets
    `lower_bound`.
    """

    var status: Int
    var feasible: Bool
    var verified: Bool
    var has_makespan: Bool
    var makespan: Float64
    var has_bound: Bool
    var lower_bound: Float64
    var cp_bound: Float64
    var has_resource_bound: Bool
    var resource_bound: Float64
    var has_gap: Bool
    var gap: Float64
    var has_relative_gap: Bool
    var relative_gap: Float64
    var optimal_by_bound: Bool
    var initial_makespan: Float64
    var schedules_built: Int
    var improvements: Int
    var restarts: Int
    var work_limit_hit: Bool
    var budget_limit_hit: Bool
    var resource_delayed_at: Int
    var infeasible_act: Int
    var infeasible_resource: Int
    var cycle_act: Int
    var n_activities: Int
    var start: List[Float64]
    var order: List[Int]
    var critical_ops: List[Int]


# ── internal, Mojo-level only ─────────────────────────────────────────────────


@fieldwise_init
struct _Sched(Copyable, Movable):
    """The earliest-start schedule of one orientation, or the evidence that it is cyclic."""

    var acyclic: Bool
    var n_ordered: Int
    var cycle_op: Int
    var makespan: Float64
    var last_op: Int
    var start: List[Float64]
    var crit_pred: List[Int]


@fieldwise_init
struct _Buckets(Copyable, Movable):
    """Operations grouped by machine: block `m` is `items[start[m] : start[m + 1]]`."""

    var start: List[Int]
    var items: List[Int]


@fieldwise_init
struct _Sgs(Copyable, Movable):
    """One serial-SGS pass: a schedule, or the reason there is none.

    `work_limit` and `ok` are separate because they are different answers. A pass that ran out
    of work budget leaves a *previous* incumbent usable and reports `SCHED_LIMIT`; a pass that
    found no feasible decision point at all contradicts `_first_over_capacity` and is an
    internal defect. Collapsing them would report a bug as a budget.
    """

    var ok: Bool
    var work_limit: Bool
    var start: List[Float64]


# ── shape and value validation ────────────────────────────────────────────────


fn _jssp_defect(
    duration: List[Float64], machine_of: List[Int],
    n_jobs: Int, n_ops: Int, n_machines: Int
) -> Int:
    """`MODEL_OK`, or the code for the first defect in a job-shop instance.

    Order matters: dimensions before lengths before values, because indexing on an unchecked
    dimension is an uncatchable process crash and not an exception. `dims_fit` is what proves
    `n_jobs * n_ops == len(duration)` — it divides, where a multiply wraps and is no bound.
    """
    if n_jobs <= 0 or n_ops <= 0 or n_machines <= 0:
        return SCHED_ERR_EMPTY_INSTANCE
    if not dims_fit(n_jobs, n_ops, len(duration)):
        return MODEL_ERR_LENGTH_MISMATCH
    if len(machine_of) != len(duration):
        return MODEL_ERR_LENGTH_MISMATCH
    var n = len(duration)
    if n > SCHED_MAX_UNITS or n_machines > SCHED_MAX_UNITS:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if n + n_machines > SCHED_MAX_UNITS:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    var total = 0.0
    for i in range(n):
        if not _finite(duration[i]) or duration[i] < 0.0:
            return SCHED_ERR_INVALID_VALUE
        if machine_of[i] < 0 or machine_of[i] >= n_machines:
            return SCHED_ERR_INVALID_VALUE
        total += duration[i]
    # Individually finite durations can still sum past the Float64 range, and then the answer
    # stops existing rather than becoming large: the job bound overflows to +inf, the makespan
    # overflows to +inf, and `gap = inf - inf` is NaN — a NaN returned under a SUCCESS status,
    # which is precisely what rule 4 forbids. Every makespan and every bound this module
    # reports is at most this sum, so bounding it here bounds all of them, in ONE place.
    if not _finite(total):
        return SCHED_ERR_INVALID_VALUE
    return MODEL_OK


fn _rcpsp_defect(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    pred_from: List[Int], pred_to: List[Int], n_acts: Int, n_res: Int
) -> Int:
    """`MODEL_OK`, or the code for the first defect in an RCPSP instance.

    `n_res == 0` is admitted: a project with no renewable resources is the pure precedence
    problem, and answering it is not a defect. A precedence edge naming an activity that
    does not exist IS one — a dropped edge changes the answer, so it is rejected rather than
    skipped.
    """
    if n_acts <= 0 or n_res < 0:
        return SCHED_ERR_EMPTY_INSTANCE
    if len(duration) != n_acts:
        return MODEL_ERR_LENGTH_MISMATCH
    if not dims_fit(n_acts, n_res, len(demand)):
        return MODEL_ERR_LENGTH_MISMATCH
    if len(capacity) != n_res:
        return MODEL_ERR_LENGTH_MISMATCH
    if len(pred_from) != len(pred_to):
        return MODEL_ERR_LENGTH_MISMATCH
    if n_acts > SCHED_MAX_UNITS or n_res > SCHED_MAX_UNITS:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if n_acts + n_res > SCHED_MAX_UNITS:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if len(demand) > SCHED_MAX_UNITS or len(pred_from) > SCHED_MAX_UNITS:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    var total = 0.0
    for i in range(n_acts):
        if not _finite(duration[i]) or duration[i] < 0.0:
            return SCHED_ERR_INVALID_VALUE
        total += duration[i]
    # Every schedule this module produces is at worst fully serial, so its makespan is at most
    # this sum. An overflowing sum therefore makes the answer NaN rather than large — see the
    # same guard in `_jssp_defect`.
    if not _finite(total):
        return SCHED_ERR_INVALID_VALUE
    for r in range(n_res):
        if not _finite(capacity[r]) or capacity[r] < 0.0:
            return SCHED_ERR_INVALID_VALUE
    for i in range(len(demand)):
        if not _finite(demand[i]) or demand[i] < 0.0:
            return SCHED_ERR_INVALID_VALUE
    for e in range(len(pred_from)):
        if pred_from[e] < 0 or pred_from[e] >= n_acts:
            return SCHED_ERR_INVALID_VALUE
        if pred_to[e] < 0 or pred_to[e] >= n_acts:
            return SCHED_ERR_INVALID_VALUE
    return MODEL_OK


fn _first_over_capacity(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    n_acts: Int, n_res: Int
) -> Int:
    """Flat index `i * n_res + r` of the first demand no capacity can ever satisfy, else -1.

    Checked BEFORE any search: an activity that does not fit alone cannot fit beside
    anything, so the instance is infeasible at every instant and a schedule does not exist.

    A ZERO-DURATION activity is skipped, and that is not an oversight — it is the same
    convention `_usage_at` and `_fits_at` apply. A milestone occupies the empty interval
    `[t, t)`, so it contributes nothing to the profile at any instant; declaring the instance
    infeasible here while the profile check finds nothing wrong would be one invariant
    enforced at two different strengths, which reads as defence in depth and delivers one
    arbitrary behaviour per call site.

    The allowance is `DBL_EPSILON` against `max(demand, capacity)` and nothing else, so a
    capacity of exactly 0.0 admits no positive demand and a capacity of 1e-14 admits no demand
    of 1e-13. Floored at scale 1.0 this screen forgave an absolute 2.27e-13, which is how
    `rcpsp_bound_flat` came to report a lower bound of 10.0 for an instance whose own verifier
    certified a makespan of 1.0.
    """
    for i in range(n_acts):
        if duration[i] <= 0.0:
            continue
        for r in range(n_res):
            var d = demand[i * n_res + r]
            if d <= 0.0:
                continue
            if d > capacity[r] + _rel_slop(_scale2(d, capacity[r]), 1):
                return i * n_res + r
    return -1


# ── machine buckets ───────────────────────────────────────────────────────────


fn _machine_buckets(machine_of: List[Int], n: Int, n_machines: Int) -> _Buckets:
    """Operations grouped by machine, ascending operation id inside each block.

    A counting pass then a fill pass — the same shape `graph_analytics.adjacency` uses for a
    CSR row build, and stable by construction, which is what keeps the initial orientation
    reproducible.
    """
    var offs = List[Int]()
    for _ in range(n_machines + 1):
        offs.append(0)
    for i in range(n):
        offs[machine_of[i] + 1] += 1
    for m in range(n_machines):
        offs[m + 1] += offs[m]
    var cursor = List[Int]()
    for m in range(n_machines):
        cursor.append(offs[m])
    var items = List[Int]()
    for _ in range(n):
        items.append(-1)
    for i in range(n):
        var m = machine_of[i]
        items[cursor[m]] = i
        cursor[m] += 1
    return _Buckets(offs^, items^)


fn _mach_pred_of(seq: List[Int], offs: List[Int], n: Int, n_machines: Int) -> List[Int]:
    """`mach_pred[o]` = the operation immediately before `o` on its machine, or -1.

    The `>= 0` guard is not redundant with the constructions that fill `seq`. An unfilled slot
    holds -1, and `pred[-1]` in this dialect addresses the LAST element rather than failing, so
    a single unfilled slot would silently corrupt another operation's predecessor and produce a
    plausible wrong makespan. Skipping is the only behaviour that cannot invent an arc.
    """
    var pred = List[Int]()
    for _ in range(n):
        pred.append(-1)
    for m in range(n_machines):
        for p in range(offs[m] + 1, offs[m + 1]):
            if seq[p] >= 0 and seq[p - 1] >= 0:
                pred[seq[p]] = seq[p - 1]
    return pred^


# ── the disjunctive graph, its cycle check and its longest path ───────────────


fn _schedule_of(
    duration: List[Float64], n_ops: Int, mach_pred: List[Int]
) -> _Sched:
    """Earliest-start schedule of one orientation, via the FROZEN topological sort.

    The two arc sets are the job chains (operation `k` of a job before operation `k + 1`)
    and the machine sequences (`mach_pred`). `topological_sort` returns a SHORT order for a
    cyclic graph, and that is the cycle certificate: a makespan computed from a cyclic
    disjunctive graph is finite and wrong, so none is computed. `cycle_op` is the lowest
    operation the order never reached.

    Longest-path ties prefer the CHAIN predecessor over the machine predecessor, so the
    critical path of an equal-length pair is fixed rather than dependent on arc order.
    """
    var n = len(duration)
    var g = graph_new(n)
    for o in range(n):
        if o % n_ops != n_ops - 1:
            graph_add_edge(g, o, o + 1, duration[o])
        var mp = mach_pred[o]
        if mp >= 0:
            graph_add_edge(g, mp, o, duration[mp])
    var order = topological_sort(g)

    var start = List[Float64]()
    var crit = List[Int]()
    for _ in range(n):
        start.append(0.0)
        crit.append(-1)

    if len(order) < n:
        var seen = List[Bool]()
        for _ in range(n):
            seen.append(False)
        for i in range(len(order)):
            seen[order[i]] = True
        var first = -1
        for o in range(n):
            if not seen[o]:
                first = o
                break
        return _Sched(False, len(order), first, SCHED_ABSENT, -1, start^, crit^)

    for i in range(len(order)):
        var o = order[i]
        var best = 0.0
        var arg = -1
        if o % n_ops != 0:
            var cp = o - 1
            var f = start[cp] + duration[cp]
            if f >= best:
                best = f
                arg = cp
        var mp = mach_pred[o]
        if mp >= 0:
            var fm = start[mp] + duration[mp]
            if fm > best:
                best = fm
                arg = mp
        start[o] = best
        crit[o] = arg

    var span = 0.0
    var last = 0
    for o in range(n):
        var f = start[o] + duration[o]
        if f > span:
            span = f
            last = o
    return _Sched(True, n, -1, span, last, start^, crit^)


fn _critical_ops(sched: _Sched, n: Int) -> List[Int]:
    """The chain that produced the makespan, in order, from the `crit_pred` walk.

    Bounded at `n` steps. A DAG's walk cannot revisit a node, so exceeding that is a defect
    in this file and returns an empty path, which every caller treats as `SCHED_ERR_UNVERIFIED`
    rather than as "there is no explanation".
    """
    var back = List[Int]()
    if not sched.acyclic or sched.last_op < 0 or n <= 0:
        return back^
    var cur = sched.last_op
    var steps = 0
    while cur >= 0 and steps <= n:
        back.append(cur)
        cur = sched.crit_pred[cur]
        steps += 1
    if steps > n:
        var empty = List[Int]()
        return empty^
    var out = List[Int]()
    for i in range(len(back)):
        out.append(back[len(back) - 1 - i])
    return out^


# ── job-shop verification ─────────────────────────────────────────────────────


fn _jssp_audit(
    duration: List[Float64], machine_of: List[Int], n_jobs: Int, n_ops: Int,
    n_machines: Int, start: List[Float64]
) -> JobShopAudit:
    """Verify a job-shop schedule against the caller's arrays. THE verifier of this module.

    Both the public `jobshop_verify_flat` and the search's final self-check call this, so a
    returned schedule is judged by the same code a caller would judge it with — a search
    that verified itself against its own bookkeeping proves nothing.

    Machine exclusivity is checked as the pairwise statement it is, not by sorting: two
    operations on one machine collide exactly when the interval they SHARE,
    `[max(start), min(finish))`, has positive length. That relies on no ordering being correct,
    and its cost is what `SCHED_MAX_WORK` bounds.

    One quantity decides and that same quantity is reported. The equivalent-looking pair
    `start[a] + d[a] > start[b] AND start[b] + d[b] > start[a]` is NOT equivalent for an empty
    interval — both differences are positive for a `[5, 5)` milestone inside a `[0, 10)`
    operation — so it returned `machine_overlap` with `worst_violation = 0.0`, a verdict its own
    magnitude contradicted. See the milestone convention on `JobShopAudit`.
    """
    var defect = _jssp_defect(duration, machine_of, n_jobs, n_ops, n_machines)
    if defect != MODEL_OK:
        return JobShopAudit(
            defect, False, SCHED_VIOL_NONE, 0, -1, -1, -1, False, SCHED_ABSENT,
            SCHED_ABSENT, False, SCHED_ABSENT, 0
        )
    var n = len(duration)
    if len(start) != n:
        return JobShopAudit(
            MODEL_ERR_LENGTH_MISMATCH, False, SCHED_VIOL_NONE, 0, -1, -1, -1, False,
            SCHED_ABSENT, SCHED_ABSENT, False, SCHED_ABSENT, n
        )

    for o in range(n):
        if not _finite(start[o]):
            return JobShopAudit(
                SCHED_VIOLATION, False, SCHED_VIOL_NON_FINITE_START, 1, o, -1,
                machine_of[o], False, SCHED_ABSENT, SCHED_ABSENT, False, SCHED_ABSENT, n
            )
    for o in range(n):
        # Zero is exactly representable, so a comparison against it has no rounding to forgive:
        # `_rel_slop(_scale2(s, 0.0), k)` is `1024 * DBL_EPSILON * |s|`, which is smaller than
        # `|s|` for every s, so the tolerant form is EXACTLY `start < 0`. Written literally so
        # nobody restores a floor here and turns "negative" into "below minus one unit".
        if start[o] < 0.0:
            return JobShopAudit(
                SCHED_VIOLATION, False, SCHED_VIOL_NEGATIVE_START, 1, o, -1,
                machine_of[o], True, start[o], -start[o], False, SCHED_ABSENT, n
            )

    var span = 0.0
    for o in range(n):
        var f = start[o] + duration[o]
        if f > span:
            span = f

    var kind = SCHED_VIOL_NONE
    var count = 0
    var first_op = -1
    var second_op = -1
    var machine = -1
    var at = SCHED_ABSENT
    var worst = SCHED_ABSENT

    for o in range(n):
        if o % n_ops == n_ops - 1:
            continue
        var need = start[o] + duration[o]
        var slack = start[o + 1] - need
        if slack < -_rel_slop(_scale2(need, start[o + 1]), 1):
            count += 1
            if -slack > worst:
                worst = -slack
            if kind == SCHED_VIOL_NONE:
                kind = SCHED_VIOL_PRECEDENCE
                first_op = o
                second_op = o + 1
                machine = machine_of[o]
                at = need

    var buckets = _machine_buckets(machine_of, n, n_machines)
    # `_machine_buckets` and the loop below both walk every MACHINE, whether or not any
    # operation uses it, so the machine count is part of this pass's cost and is charged as
    # such. Starting the counter at 0 charged nothing for a declared machine count bounded only
    # by the allocation ceiling — see the work section of the module docstring.
    var work = n + n_machines
    for m in range(n_machines):
        var lo = buckets.start[m]
        var hi = buckets.start[m + 1]
        for i in range(lo, hi):
            work += hi - i
            if work > SCHED_MAX_WORK:
                return JobShopAudit(
                    SCHED_ERR_WORK_BUDGET, False, SCHED_VIOL_NONE, count, first_op,
                    second_op, machine, False, SCHED_ABSENT, worst, True, span, n
                )
            var a = buckets.items[i]
            for j in range(i + 1, hi):
                var b = buckets.items[j]
                var ea = start[a] + duration[a]
                var eb = start[b] + duration[b]
                # The shared interval, computed ONCE and used for both the verdict and the
                # magnitude. `min(end) - max(start)` is not `min(over_ab, over_ba)`: when one
                # operation CONTAINS the other those differ — a = [0, 10), b = [2, 3) gives
                # over_ab = 8 and over_ba = 3 while the operations collide for 1 unit of time.
                # Reporting 3 there would overstate the breach a caller has to fix.
                #
                # And DECIDING on `over_ab > 0 and over_ba > 0` while measuring the interval was
                # worse than an overstatement: for a zero-length milestone at [5, 5) inside
                # a = [0, 10) both differences are positive and the interval is empty, so the
                # pair was reported as `machine_overlap` with `worst_violation = 0.0` — the
                # code's own evidence that nothing collided. One quantity decides and is
                # reported: the length of the interval the two operations actually share.
                #
                # Named `ov_*` and not `lo`/`hi`: those are the bucket bounds of the loops this
                # sits inside, and shadowing a loop bound with a time is the kind of thing that
                # survives review and breaks on the next edit.
                var ov_lo = start[a]
                if start[b] > ov_lo:
                    ov_lo = start[b]
                var ov_hi = ea
                if eb < ov_hi:
                    ov_hi = eb
                var mag = ov_hi - ov_lo
                # The judged quantity is `mag`, a difference of two instants, so the allowance
                # is DBL_EPSILON against the magnitude of THOSE instants and of nothing else.
                if mag > _rel_slop(_scale2(ov_lo, ov_hi), 1):
                    count += 1
                    if mag > worst:
                        worst = mag
                    if kind == SCHED_VIOL_NONE:
                        kind = SCHED_VIOL_MACHINE_OVERLAP
                        first_op = a
                        second_op = b
                        machine = m
                        at = ov_lo

    if kind == SCHED_VIOL_NONE:
        return JobShopAudit(
            MODEL_OK, True, SCHED_VIOL_NONE, 0, -1, -1, -1, False, SCHED_ABSENT,
            0.0, True, span, n
        )
    return JobShopAudit(
        SCHED_VIOLATION, False, kind, count, first_op, second_op, machine, True, at,
        worst, True, span, n
    )


# ── job-shop bounds ───────────────────────────────────────────────────────────


fn _jssp_bound(
    duration: List[Float64], machine_of: List[Int], n_jobs: Int, n_ops: Int,
    n_machines: Int
) -> JobShopBound:
    """The two cheap valid bounds, and the larger of them."""
    var defect = _jssp_defect(duration, machine_of, n_jobs, n_ops, n_machines)
    if defect != MODEL_OK:
        return JobShopBound(defect, False, SCHED_ABSENT, SCHED_ABSENT, SCHED_ABSENT, -1, -1, 0, SCHED_ABSENT)
    var n = len(duration)
    var job_bound = 0.0
    var critical_job = -1
    for j in range(n_jobs):
        var total = 0.0
        for k in range(n_ops):
            total += duration[j * n_ops + k]
        if critical_job < 0 or total > job_bound:
            job_bound = total
            critical_job = j
    var load = List[Float64]()
    for _ in range(n_machines):
        load.append(0.0)
    var work = 0.0
    for o in range(n):
        load[machine_of[o]] += duration[o]
        work += duration[o]
    var machine_bound = 0.0
    var critical_machine = -1
    for m in range(n_machines):
        if critical_machine < 0 or load[m] > machine_bound:
            machine_bound = load[m]
            critical_machine = m
    var lb = job_bound
    if machine_bound > lb:
        lb = machine_bound
    return JobShopBound(
        MODEL_OK, True, lb, job_bound, machine_bound, critical_job, critical_machine, n, work
    )


# ── job-shop construction ─────────────────────────────────────────────────────


fn _dispatch(
    duration: List[Float64], machine_of: List[Int], n_jobs: Int, n_ops: Int,
    n_machines: Int, offs: List[Int], key: UInt64, stream: UInt64, restart: Int
) -> List[Int]:
    """Machine sequences from an earliest-start dispatch, laid out in `offs` blocks.

    Priority, in order and stated so the answer can be reproduced by hand: smallest earliest
    start; then shortest duration; then smallest `_op_key(seed, restart, op)`; then smallest
    machine index; then smallest operation id.

    The keyed draw sits ABOVE the machine index deliberately. With the machine index first it
    decided nearly every tie — the candidate set holds at most one operation per job and those
    are usually on different machines — so the keyed tie-break was unreachable, every seed
    produced the same dispatch, and each "restart" rebuilt the schedule it had just left. Both
    orders are arbitrary; this one is arbitrary AND diversifying, and the machine index remains
    the deterministic fallback for the (never observed) case of colliding keys.

    The orientation this returns is ACYCLIC by construction: the dispatch order is a linear
    extension of the job chains, and each machine's sequence is that same order restricted to
    its operations, so every arc of the disjunctive graph points forward in one total order.
    The caller still runs the cycle check — a construction whose invariant is only argued is
    exactly what this module refuses to trust.
    """
    var n = len(duration)
    var pos = List[Int]()
    var job_free = List[Float64]()
    for _ in range(n_jobs):
        pos.append(0)
        job_free.append(0.0)
    var mach_free = List[Float64]()
    var cursor = List[Int]()
    for m in range(n_machines):
        mach_free.append(0.0)
        cursor.append(offs[m])
    var seq = List[Int]()
    for _ in range(n):
        seq.append(-1)

    for _ in range(n):
        var pick = -1
        var pick_est = 0.0
        var pick_dur = 0.0
        var pick_mach = 0
        var pick_key = 0.0
        for j in range(n_jobs):
            if pos[j] >= n_ops:
                continue
            var o = j * n_ops + pos[j]
            var m = machine_of[o]
            var est = job_free[j]
            if mach_free[m] > est:
                est = mach_free[m]
            var dur = duration[o]
            var mk = _op_key(key, stream, restart, o)
            var better = False
            if pick < 0:
                better = True
            elif est < pick_est:
                better = True
            elif est == pick_est:
                if dur < pick_dur:
                    better = True
                elif dur == pick_dur:
                    if mk < pick_key:
                        better = True
                    elif mk == pick_key and m < pick_mach:
                        better = True
            if better:
                pick = o
                pick_est = est
                pick_dur = dur
                pick_mach = m
                pick_key = mk
        if pick < 0:
            break
        var jj = pick // n_ops
        var mm = machine_of[pick]
        var finish = pick_est + duration[pick]
        job_free[jj] = finish
        mach_free[mm] = finish
        pos[jj] += 1
        seq[cursor[mm]] = pick
        cursor[mm] += 1
    return seq^


fn _ranks_of(seq: List[Int], offs: List[Int], n: Int, n_machines: Int) -> List[Int]:
    """0-based position of each operation inside its machine's block.

    The `>= 0` guard is the same one `_mach_pred_of` carries and for the same reason: an
    unfilled slot holds -1, and `rank[-1]` addresses the LAST entry in this dialect rather
    than failing, so it would silently mis-report another operation's position.
    """
    var rank = List[Int]()
    for _ in range(n):
        rank.append(-1)
    for m in range(n_machines):
        for p in range(offs[m], offs[m + 1]):
            if seq[p] >= 0:
                rank[seq[p]] = p - offs[m]
    return rank^


fn _pos_of(seq: List[Int], n: Int) -> List[Int]:
    """Index of each operation inside `seq`."""
    var at = List[Int]()
    for _ in range(n):
        at.append(-1)
    for p in range(len(seq)):
        if seq[p] >= 0:
            at[seq[p]] = p
    return at^


fn _seq_from_ranks(
    machine_of: List[Int], rank: List[Int], n: Int, n_machines: Int
) -> List[Int]:
    """Machine sequences from caller-supplied ranks: ascending `rank`, ties by operation id.

    `rank` is a SORT KEY, not required to be a permutation, so no orientation a caller can
    express is rejected for its numbering — only for being cyclic, which is a property of the
    order and not of the integers. Insertion placement is quadratic per machine and is
    charged against the work budget by the caller.
    """
    var seq = List[Int]()
    for m in range(n_machines):
        var block = List[Int]()
        for o in range(n):
            if machine_of[o] != m:
                continue
            var at = len(block)
            for p in range(len(block)):
                if rank[o] < rank[block[p]]:
                    at = p
                    break
            block.append(o)
            for q in range(len(block) - 1, at, -1):
                var tmp = block[q]
                block[q] = block[q - 1]
                block[q - 1] = tmp
        for p in range(len(block)):
            seq.append(block[p])
    return seq^


# ── public: job shop ──────────────────────────────────────────────────────────


fn jobshop_bound_flat(
    duration: List[Float64], machine_of: List[Int],
    n_jobs: Int, n_ops: Int, n_machines: Int
) -> JobShopBound:
    """Lower bounds on the makespan of a job shop, with no schedule built.

    `duration` and `machine_of` are `n_jobs x n_ops` row-major: operation `k` of job `j` is
    index `j * n_ops + k`, runs on machine `machine_of[...]`, and the operations of a job run
    in ascending `k`. Both bounds are valid for EVERY schedule, which is what makes the gap
    a real gap; neither is achievable in general.
    """
    return _jssp_bound(duration, machine_of, n_jobs, n_ops, n_machines)


fn jobshop_verify_flat(
    duration: List[Float64], machine_of: List[Int],
    n_jobs: Int, n_ops: Int, n_machines: Int, start: List[Float64]
) -> JobShopAudit:
    """Verify a job-shop schedule: every precedence, every machine, every start time.

    Independent of any solver — this answers "is this schedule a schedule", including for one
    produced elsewhere. The conditions covered are listed on `JobShopAudit` and that list is
    exhaustive for this problem: a schedule satisfying all of them is executable.
    """
    return _jssp_audit(duration, machine_of, n_jobs, n_ops, n_machines, start)


fn jobshop_schedule_from_ranks_flat(
    duration: List[Float64], machine_of: List[Int],
    n_jobs: Int, n_ops: Int, n_machines: Int, rank: List[Int]
) -> JobShopSchedule:
    """Earliest-start schedule of a caller-supplied disjunctive orientation, or its cycle.

    Each machine runs its operations in ascending `rank`, ties broken by operation id. The
    result is the semi-active schedule that orientation implies, its makespan, its critical
    path and the normalised ranks actually used — feed those back in and the answer repeats.

    A cyclic orientation is `SCHED_PRECEDENCE_CYCLE` with every list empty. This is the
    specific failure a disjunctive flip creates, and the reason it cannot be answered with a
    number: the DP over a cyclic graph terminates and returns a finite makespan for a
    schedule that cannot exist.
    """
    var defect = _jssp_defect(duration, machine_of, n_jobs, n_ops, n_machines)
    var n = len(duration)
    if defect != MODEL_OK:
        return _no_schedule(defect, -1, 0, n if defect != SCHED_ERR_EMPTY_INSTANCE else 0)
    if len(rank) != n:
        return _no_schedule(MODEL_ERR_LENGTH_MISMATCH, -1, 0, n)
    var buckets = _machine_buckets(machine_of, n, n_machines)
    # `_seq_from_ranks` scans every OPERATION once per MACHINE, so its cost is `n * n_machines`
    # before any insertion happens — charged with a DIVISION because the product is a wrapping
    # 64-bit multiply and therefore no bound at all. Leaving the machine count out charged
    # nothing for a dimension bounded only by the allocation ceiling (rule 1c), which is the
    # same under-count that let the tabu search run for hours.
    if n_machines > SCHED_MAX_WORK // n:
        return _no_schedule(SCHED_ERR_WORK_BUDGET, -1, 0, n)
    var work = n * n_machines
    for m in range(n_machines):
        var k = buckets.start[m + 1] - buckets.start[m]
        if k > SCHED_MAX_WORK // (k + 1):
            return _no_schedule(SCHED_ERR_WORK_BUDGET, -1, 0, n)
        work += k * k
        if work > SCHED_MAX_WORK:
            return _no_schedule(SCHED_ERR_WORK_BUDGET, -1, 0, n)
    var seq = _seq_from_ranks(machine_of, rank, n, n_machines)
    var mach_pred = _mach_pred_of(seq, buckets.start, n, n_machines)
    var sched = _schedule_of(duration, n_ops, mach_pred)
    if not sched.acyclic:
        return _no_schedule(SCHED_PRECEDENCE_CYCLE, sched.cycle_op, sched.n_ordered, n)

    var audit = _jssp_audit(duration, machine_of, n_jobs, n_ops, n_machines, sched.start)
    var crit = _critical_ops(sched, n)
    if audit.status == SCHED_ERR_WORK_BUDGET:
        return _no_schedule(SCHED_ERR_WORK_BUDGET, -1, sched.n_ordered, n)
    if not audit.feasible or len(crit) == 0:
        return _no_schedule(SCHED_ERR_UNVERIFIED, -1, sched.n_ordered, n)

    var bound = _jssp_bound(duration, machine_of, n_jobs, n_ops, n_machines)
    var lb = bound.lower_bound
    # `n + 2` and not `2`: both the makespan and the bound are sums of up to `n` durations, so
    # both can carry `n` ulps of accumulation. See `bound_terms` in `jobshop_tabu_solve_flat`.
    var slop = _rel_slop(_scale2(sched.makespan, lb), n + 2)
    if sched.makespan < lb - slop:
        return _no_schedule(SCHED_ERR_UNVERIFIED, -1, sched.n_ordered, n)
    var gap = sched.makespan - lb
    if gap < 0.0:
        gap = 0.0
    var optimal = gap <= slop
    var status = SCHED_OPTIMAL if optimal else SCHED_FEASIBLE
    var ranks = _ranks_of(seq, buckets.start, n, n_machines)
    return JobShopSchedule(
        status, True, True, True, sched.makespan, True, lb, True, gap, optimal, -1,
        sched.n_ordered, n, sched.start.copy(), crit^, ranks^
    )


fn _no_schedule(status: Int, cycle_op: Int, n_ordered: Int, n: Int) -> JobShopSchedule:
    """A `JobShopSchedule` carrying no numbers — every list empty, every flag False."""
    return JobShopSchedule(
        status, False, False, False, SCHED_ABSENT, False, SCHED_ABSENT, False,
        SCHED_ABSENT, False, cycle_op, n_ordered, n, List[Float64](), List[Int](),
        List[Int]()
    )


fn _no_result(status: Int, n: Int) -> JobShopResult:
    """A `JobShopResult` carrying no numbers. A rejected request has no schedule at all."""
    return JobShopResult(
        status, False, False, False, SCHED_ABSENT, False, SCHED_ABSENT, False,
        SCHED_ABSENT, False, SCHED_ABSENT, False, SCHED_ABSENT, 0, 0, 0, 0, 0, False,
        False, False, n, List[Float64](), List[Int](), List[Int]()
    )


fn jobshop_tabu_solve_flat(
    duration: List[Float64], machine_of: List[Int],
    n_jobs: Int, n_ops: Int, n_machines: Int,
    seed: Int, max_iters: Int, tabu_tenure: Int, stall_limit: Int
) -> JobShopResult:
    """Tabu search over critical machine swaps. A good schedule, a real bound, an honest gap.

    The neighbourhood is the classic one: reverse a machine arc that lies on the critical
    path. Reversing an arc off the critical path cannot shorten the makespan, so the move set
    is complete for improvement and small. Every trial orientation is checked for a cycle by
    the frozen topological sort and discarded if cyclic; the count is reported.

    A move is chosen by smallest trial makespan among admissible candidates, where admissible
    means "not tabu, or better than the incumbent" (aspiration). Candidates are scanned in
    `permutation_keyed` order so ties are broken reproducibly by the seed, and the applied
    swap is forbidden for `tabu_tenure` iterations. After `stall_limit` iterations with no
    improvement the search restarts from a fresh keyed dispatch, keeping the incumbent.

    `max_iters` may be 0 — that returns the construction alone, under `SCHED_LIMIT`, because
    the driver had moves it was not allowed to try. Negative, or above `SCHED_MAX_ITERS`, is
    refused rather than clamped: running a different search than the one requested is the
    failure mode a clamp creates.

    The returned schedule has passed `jobshop_verify_flat` against the caller's own arrays,
    and its makespan has been checked against the lower bound in both directions. Nothing is
    returned as optimal that the bound does not prove optimal.
    """
    var defect = _jssp_defect(duration, machine_of, n_jobs, n_ops, n_machines)
    var n = len(duration)
    if defect != MODEL_OK:
        return _no_result(defect, n if defect != SCHED_ERR_EMPTY_INSTANCE else 0)
    if max_iters < 0 or max_iters > SCHED_MAX_ITERS:
        return _no_result(SCHED_ERR_INVALID_VALUE, n)
    if tabu_tenure < 1 or tabu_tenure > SCHED_MAX_TENURE:
        return _no_result(SCHED_ERR_INVALID_VALUE, n)
    if stall_limit < 1:
        return _no_result(SCHED_ERR_INVALID_VALUE, n)
    # The dispatch scans one candidate per unfinished job for each of the `n` placements, so a
    # construction costs `n * n_jobs` steps before any search happens. Checked with a DIVISION
    # for the same reason `dims_fit` divides: the product is a wrapping multiply.
    if n_jobs > SCHED_MAX_WORK // n:
        return _no_result(SCHED_ERR_WORK_BUDGET, n)

    var bound = _jssp_bound(duration, machine_of, n_jobs, n_ops, n_machines)
    var lb = bound.lower_bound
    var buckets = _machine_buckets(machine_of, n, n_machines)
    var key = _seed_key(seed)
    var stream = stream_id("optimization.scheduling.jobshop")
    # A SECOND name, because the construction's per-operation keys and the neighbourhood's
    # permutation are different concerns. Sharing a stream would let the tie-break for
    # operation 0 of restart 0 sit on the same draw coordinate as the first swap of the
    # neighbourhood scan — deterministic either way, but correlated for no reason, which is
    # exactly what `determinism/streams.mojo` names streams to avoid.
    var scan_stream = stream_id("optimization.scheduling.jobshop.neighbourhood")

    var seq = _dispatch(
        duration, machine_of, n_jobs, n_ops, n_machines, buckets.start, key, stream, 0
    )
    # A dispatch costs `n * n_jobs` steps for the scan plus `n_machines` for the per-machine
    # cursors it builds, and a restart pays both again. Charging only the `n` of the schedule
    # rebuild left the restart loop able to spend `max_iters * n * n_jobs` steps against a
    # budget that never noticed — a hang rather than a status on a large instance. The
    # pre-check above keeps the product inside the budget, so it cannot overflow, and a single
    # dispatch that eats the whole budget stops the search at once.
    var dispatch_cost = n * n_jobs + n_machines
    # One trial orientation costs `_mach_pred_of` (a pass over every MACHINE block), plus
    # `_schedule_of` (a pass over every operation), plus the tabu-list scan (a pass over every
    # TENURE slot). Charging `n` alone made the other two free, and both are bounded by a
    # RANGE CHECK rather than by anything in the payload:
    #
    #   * `n_machines` only has to satisfy `n + n_machines <= SCHED_MAX_UNITS`, so 20 operations
    #     declaring 2,000,000 machines ran for hours with `work_limit_hit = False`.
    #   * `tabu_tenure` only has to satisfy `<= SCHED_MAX_TENURE = 4096`, and the tabu scan sits
    #     INSIDE the candidate loop. Measured on a 9-operation instance at tenure 4096: 24 ms at
    #     2,000 iterations and 236 ms at 20,000, linear, with charged work of 12 per trial
    #     against a per-trial reality of ~4,100 — the permitted `max_iters` extrapolates to ~12 s
    #     while the ceiling sees 1.2e7 of 1.3e8.
    #
    # Bounding memory, or a parameter's range, is not bounding work: every loop bound that
    # multiplies into the cost is charged here (rule 1c). All three terms are at most
    # `SCHED_MAX_UNITS`, so the sum cannot overflow.
    var trial_cost = n + n_machines + tabu_tenure
    # `terms` for every makespan-against-bound comparison below. A makespan is a sum of
    # durations along a chain of at most `n` operations and the bound is a sum of at most `n`
    # durations, so BOTH sides can carry `n` ulps of accumulation; `terms = 2` under-sized the
    # allowance for exactly the two quantities being judged, and the consequence of under-sizing
    # it here is `SCHED_ERR_UNVERIFIED` — an internal-defect status — for a caller's legitimate
    # instance. This is still the length of THOSE sums and not a count of anything else.
    var bound_terms = n + 2
    var at = _pos_of(seq, n)
    var mach_pred = _mach_pred_of(seq, buckets.start, n, n_machines)
    var cur = _schedule_of(duration, n_ops, mach_pred)
    if not cur.acyclic:
        # The construction is a linear extension of the chains, so this is unreachable
        # unless this file is wrong — which is exactly when a status beats a number.
        return _no_result(SCHED_ERR_UNVERIFIED, n)
    var initial_makespan = cur.makespan
    var best = cur.makespan
    var best_seq = seq.copy()

    var tabu_a = List[Int]()
    var tabu_b = List[Int]()
    var tabu_until = List[Int]()
    for _ in range(tabu_tenure):
        tabu_a.append(-1)
        tabu_b.append(-1)
        tabu_until.append(0)
    var tabu_at = 0

    var iterations = 0
    var moves = 0
    var improvements = 0
    var cycles = 0
    var restarts = 0
    var stall = 0
    var work = dispatch_cost
    var work_limit = False
    var exhausted = False

    while iterations < max_iters:
        var slop_best = _rel_slop(_scale2(best, lb), bound_terms)
        if best <= lb + slop_best:
            break
        if work > SCHED_MAX_WORK:
            work_limit = True
            break
        iterations += 1

        var crit = _critical_ops(cur, n)
        if len(crit) == 0:
            return _no_result(SCHED_ERR_UNVERIFIED, n)
        var cand_a = List[Int]()
        var cand_b = List[Int]()
        for i in range(len(crit) - 1):
            var u = crit[i]
            var v = crit[i + 1]
            if mach_pred[v] == u:
                cand_a.append(u)
                cand_b.append(v)
        if len(cand_a) == 0:
            # No machine arc lies on the critical path, so no swap in this move class can
            # shorten the makespan. That is the end of the search, not a limit: a restart
            # would rebuild the same neighbourhood from the same keyed dispatch.
            iterations -= 1
            exhausted = True
            break

        var pick = -1
        var pick_span = 0.0
        var scan = permutation_keyed(
            len(cand_a), key, scan_stream, UInt64(iterations) * UInt64(n)
        )
        for t in range(len(scan)):
            # INSIDE the scan, not only between passes: one pass evaluates up to `n_cand`
            # trials of `n` steps each, so a budget checked once per pass bounds nothing on a
            # large instance. The partial `pick` is discarded below — the incumbent is what
            # gets returned, and it is already verified.
            if work > SCHED_MAX_WORK:
                work_limit = True
                break
            var c = scan[t]
            var u = cand_a[c]
            var v = cand_b[c]
            var pu = at[u]
            seq[pu] = v
            seq[pu + 1] = u
            at[u] = pu + 1
            at[v] = pu
            var trial_pred = _mach_pred_of(seq, buckets.start, n, n_machines)
            var trial = _schedule_of(duration, n_ops, trial_pred)
            work += trial_cost
            moves += 1
            seq[pu] = u
            seq[pu + 1] = v
            at[u] = pu
            at[v] = pu + 1
            if not trial.acyclic:
                cycles += 1
                continue
            var tabu = False
            for q in range(len(tabu_a)):
                if tabu_until[q] > iterations:
                    if tabu_a[q] == u and tabu_b[q] == v:
                        tabu = True
                    elif tabu_a[q] == v and tabu_b[q] == u:
                        tabu = True
            var aspires = trial.makespan < best - _rel_slop(
                _scale2(trial.makespan, best), bound_terms
            )
            if tabu and not aspires:
                continue
            if pick < 0 or trial.makespan < pick_span:
                pick = c
                pick_span = trial.makespan

        if work_limit:
            break
        if pick < 0:
            # Every candidate was tabu or cyclic. Staying put would rebuild the identical
            # state next pass and spin the whole budget, so diversify now.
            stall = stall_limit
        else:
            var u = cand_a[pick]
            var v = cand_b[pick]
            var pu = at[u]
            seq[pu] = v
            seq[pu + 1] = u
            at[u] = pu + 1
            at[v] = pu
            tabu_a[tabu_at] = u
            tabu_b[tabu_at] = v
            # `+ 1` because the test below is `until > iteration` and the move is applied at
            # iteration `iterations`: without it a tenure of 1 forbids the move for ZERO
            # passes, which is a tabu list that does not hold anything and a documented
            # promise ("forbidden for `tabu_tenure` iterations") that was off by one.
            tabu_until[tabu_at] = iterations + tabu_tenure + 1
            tabu_at = (tabu_at + 1) % len(tabu_a)
            mach_pred = _mach_pred_of(seq, buckets.start, n, n_machines)
            cur = _schedule_of(duration, n_ops, mach_pred)
            work += trial_cost
            if not cur.acyclic:
                return _no_result(SCHED_ERR_UNVERIFIED, n)
            if cur.makespan < best - _rel_slop(_scale2(cur.makespan, best), bound_terms):
                best = cur.makespan
                best_seq = seq.copy()
                improvements += 1
                stall = 0
            else:
                stall += 1

        if stall >= stall_limit:
            restarts += 1
            seq = _dispatch(
                duration, machine_of, n_jobs, n_ops, n_machines, buckets.start, key,
                stream, restarts
            )
            at = _pos_of(seq, n)
            mach_pred = _mach_pred_of(seq, buckets.start, n, n_machines)
            cur = _schedule_of(duration, n_ops, mach_pred)
            work += trial_cost + dispatch_cost
            if not cur.acyclic:
                return _no_result(SCHED_ERR_UNVERIFIED, n)
            stall = 0
            if cur.makespan < best - _rel_slop(_scale2(cur.makespan, best), bound_terms):
                best = cur.makespan
                best_seq = seq.copy()
                improvements += 1

    var final_pred = _mach_pred_of(best_seq, buckets.start, n, n_machines)
    var final = _schedule_of(duration, n_ops, final_pred)
    if not final.acyclic:
        return _no_result(SCHED_ERR_UNVERIFIED, n)
    var audit = _jssp_audit(duration, machine_of, n_jobs, n_ops, n_machines, final.start)
    var crit_final = _critical_ops(final, n)
    if audit.status == SCHED_ERR_WORK_BUDGET:
        # The verifier ran out of budget, so it reached NO verdict. Reporting that as
        # `internal_schedule_failed_verification` would accuse the search of a defect it may
        # not have, and a wrong status travels further than a wrong number.
        return _no_result(SCHED_ERR_WORK_BUDGET, n)
    if not audit.feasible or len(crit_final) == 0:
        return _no_result(SCHED_ERR_UNVERIFIED, n)
    var slop = _rel_slop(_scale2(final.makespan, lb), bound_terms)
    if final.makespan < lb - slop:
        return _no_result(SCHED_ERR_UNVERIFIED, n)
    if fabs(audit.makespan - final.makespan) > _rel_slop(
        _scale2(audit.makespan, final.makespan), bound_terms
    ):
        return _no_result(SCHED_ERR_UNVERIFIED, n)

    var gap = final.makespan - lb
    if gap < 0.0:
        gap = 0.0
    var optimal = gap <= slop
    var iter_limit = (not optimal) and iterations >= max_iters
    var status = SCHED_FEASIBLE
    if optimal:
        status = SCHED_OPTIMAL
    elif work_limit or iter_limit:
        status = SCHED_LIMIT
    elif not exhausted:
        status = SCHED_LIMIT
    var rel = SCHED_ABSENT
    var has_rel = lb > 0.0
    if has_rel:
        rel = gap / lb
    var ranks = _ranks_of(best_seq, buckets.start, n, n_machines)
    return JobShopResult(
        status, True, True, True, final.makespan, True, lb, True, gap, has_rel, rel,
        optimal, initial_makespan, iterations, moves, improvements, cycles, restarts,
        iter_limit, work_limit, exhausted, n, final.start.copy(), crit_final^, ranks^
    )


# ── RCPSP: precedence structures ──────────────────────────────────────────────


@fieldwise_init
struct _Prec(Copyable, Movable):
    """Precedence adjacency in both directions, plus a topological order or its absence."""

    var acyclic: Bool
    var cycle_act: Int
    var order: List[Int]
    var pred_start: List[Int]
    var pred_items: List[Int]
    var succ_start: List[Int]
    var succ_items: List[Int]


fn _prec_of(pred_from: List[Int], pred_to: List[Int], n_acts: Int) -> _Prec:
    """Predecessor and successor adjacency, and the frozen topological order.

    `topological_sort` returning fewer than `n_acts` nodes IS the cycle certificate, and it
    catches a self-loop as well: an activity that precedes itself never reaches in-degree 0.
    """
    var g = graph_new(n_acts)
    var pred_count = List[Int]()
    var succ_count = List[Int]()
    for _ in range(n_acts + 1):
        pred_count.append(0)
        succ_count.append(0)
    for e in range(len(pred_from)):
        graph_add_edge(g, pred_from[e], pred_to[e], 1.0)
        pred_count[pred_to[e] + 1] += 1
        succ_count[pred_from[e] + 1] += 1
    for i in range(n_acts):
        pred_count[i + 1] += pred_count[i]
        succ_count[i + 1] += succ_count[i]
    var pcur = List[Int]()
    var scur = List[Int]()
    for i in range(n_acts):
        pcur.append(pred_count[i])
        scur.append(succ_count[i])
    var pitems = List[Int]()
    var sitems = List[Int]()
    for _ in range(len(pred_from)):
        pitems.append(-1)
        sitems.append(-1)
    for e in range(len(pred_from)):
        var a = pred_from[e]
        var b = pred_to[e]
        pitems[pcur[b]] = a
        pcur[b] += 1
        sitems[scur[a]] = b
        scur[a] += 1

    var order = topological_sort(g)
    if len(order) < n_acts:
        var seen = List[Bool]()
        for _ in range(n_acts):
            seen.append(False)
        for i in range(len(order)):
            seen[order[i]] = True
        var first = -1
        for a in range(n_acts):
            if not seen[a]:
                first = a
                break
        return _Prec(False, first, order^, pred_count^, pitems^, succ_count^, sitems^)
    return _Prec(True, -1, order^, pred_count^, pitems^, succ_count^, sitems^)


fn _cp_forward(duration: List[Float64], prec: _Prec) -> List[Float64]:
    """Earliest start of every activity from the precedences alone — a longest-path DP."""
    var n = len(duration)
    var es = List[Float64]()
    for _ in range(n):
        es.append(0.0)
    for i in range(len(prec.order)):
        var a = prec.order[i]
        var best = 0.0
        for p in range(prec.pred_start[a], prec.pred_start[a + 1]):
            var q = prec.pred_items[p]
            var f = es[q] + duration[q]
            if f > best:
                best = f
        es[a] = best
    return es^


fn _cp_tail(duration: List[Float64], prec: _Prec) -> List[Float64]:
    """Longest path from each activity to the end, inclusive of its own duration.

    Computed over the REVERSE of the frozen topological order, which is a valid reverse
    linear extension for the same reason the forward pass works.
    """
    var n = len(duration)
    var tail = List[Float64]()
    for _ in range(n):
        tail.append(0.0)
    for i in range(len(prec.order) - 1, -1, -1):
        var a = prec.order[i]
        var best = 0.0
        for p in range(prec.succ_start[a], prec.succ_start[a + 1]):
            var s = prec.succ_items[p]
            if tail[s] > best:
                best = tail[s]
        tail[a] = duration[a] + best
    return tail^


fn _rcpsp_bound(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    pred_from: List[Int], pred_to: List[Int], n_acts: Int, n_res: Int
) -> RcpspBound:
    """The precedence bound with its path, and the resource-area bound with its resource."""
    var defect = _rcpsp_defect(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res
    )
    if defect != MODEL_OK:
        return RcpspBound(
            defect, False, SCHED_ABSENT, SCHED_ABSENT, False, SCHED_ABSENT, -1, -1, 0,
            0, List[Int]()
        )
    var over = _first_over_capacity(duration, demand, capacity, n_acts, n_res)
    if over >= 0:
        return RcpspBound(
            SCHED_RESOURCE_INFEASIBLE, False, SCHED_ABSENT, SCHED_ABSENT, False,
            SCHED_ABSENT, over % n_res, -1, 0, n_acts, List[Int]()
        )
    var prec = _prec_of(pred_from, pred_to, n_acts)
    if not prec.acyclic:
        return RcpspBound(
            SCHED_PRECEDENCE_CYCLE, False, SCHED_ABSENT, SCHED_ABSENT, False,
            SCHED_ABSENT, -1, prec.cycle_act, len(prec.order), n_acts, List[Int]()
        )
    var es = _cp_forward(duration, prec)
    var cp = 0.0
    var last = 0
    for a in range(n_acts):
        var f = es[a] + duration[a]
        if f > cp:
            cp = f
            last = a
    var back = List[Int]()
    var cur = last
    var steps = 0
    while cur >= 0 and steps <= n_acts:
        back.append(cur)
        var nxt = -1
        for p in range(prec.pred_start[cur], prec.pred_start[cur + 1]):
            var q = prec.pred_items[p]
            var f = es[q] + duration[q]
            # `n_acts + 1` terms, matching the same walk in `rcpsp_sgs_solve_flat`: `f` and
            # `es[cur]` are both sums accumulated along a chain of up to `n_acts` activities, and
            # an allowance too tight here does not report a violation — it silently truncates the
            # critical path that is supposed to EXPLAIN the bound.
            if f >= es[cur] - _rel_slop(
                _scale2(f, es[cur]), n_acts + 1
            ) and es[cur] > 0.0:
                nxt = q
                break
        cur = nxt
        steps += 1
    var path = List[Int]()
    for i in range(len(back)):
        path.append(back[len(back) - 1 - i])

    var res_bound = 0.0
    var binding = -1
    for r in range(n_res):
        var area = 0.0
        for a in range(n_acts):
            area += duration[a] * demand[a * n_res + r]
        # A resource-time area that overflows makes the bound +inf, and then `gap` is
        # `inf - inf` = NaN under a success status. The durations are already known to sum
        # finitely; a demand large enough to overflow the PRODUCT is a value this driver
        # cannot price, and saying so beats returning a NaN gap.
        if not _finite(area):
            return RcpspBound(
                SCHED_ERR_INVALID_VALUE, False, SCHED_ABSENT, SCHED_ABSENT, False,
                SCHED_ABSENT, r, -1, len(prec.order), n_acts, List[Int]()
            )
        if area <= 0.0:
            continue
        if capacity[r] <= 0.0:
            # A positive area needs an activity with a positive duration AND a positive demand
            # for `r`, and `_first_over_capacity` compares that demand against `capacity[r]` with
            # an allowance of `1024 * DBL_EPSILON * demand` — strictly smaller than the demand
            # itself — so a capacity of 0.0 (or below) is always caught there. Reaching here
            # means the screen and this loop disagree, which is a defect in this file and not an
            # answer. It used to be REACHABLE: with `_rel_slop` floored at scale 1.0 the screen
            # forgave an absolute 2.27e-13, so `capacity = [0.0]` with `demand = [1e-13]` walked
            # straight into this branch and `rcpsp_sgs_solve_flat` propagated the internal-defect
            # status for a caller's legitimate input.
            return RcpspBound(
                SCHED_ERR_UNVERIFIED, False, SCHED_ABSENT, SCHED_ABSENT, False,
                SCHED_ABSENT, r, -1, len(prec.order), n_acts, List[Int]()
            )
        var need = area / capacity[r]
        if not _finite(need):
            return RcpspBound(
                SCHED_ERR_INVALID_VALUE, False, SCHED_ABSENT, SCHED_ABSENT, False,
                SCHED_ABSENT, r, -1, len(prec.order), n_acts, List[Int]()
            )
        if need > res_bound:
            res_bound = need
            binding = r

    # A makespan of `Σ duration` DEMONSTRABLY exists: every activity fits alone (that is what
    # `_first_over_capacity` just proved), so running them one at a time in topological order is
    # resource-feasible and precedence-feasible. No lower bound may exceed it — a "lower bound"
    # above a reachable makespan is not a bound but a contradiction between two numbers this
    # file computed, and `rcpsp_sgs_solve_flat` can only answer such a contradiction by
    # withholding the schedule under `SCHED_ERR_UNVERIFIED`. So the clamp lives HERE, where the
    # bound is produced, and it is stated as an invariant rather than left to a downstream
    # check: `rcpsp_bound_flat` must not be able to emit a bound above a makespan
    # `rcpsp_verify_flat` would certify on the same data.
    #
    # `cp` cannot exceed the serial sum in exact arithmetic (a path is a subset of the
    # activities), and neither can `area / capacity` once every demand is known to fit, so this
    # only ever bites the rounding of the area sum and its division — which is exactly the
    # residue that would otherwise be reported as an internal defect.
    #
    # BOTH reported bounds are clamped, before `lower_bound` is taken as their maximum, so that
    # the three fields stay mutually consistent: `lower_bound == max(cp_bound, resource_bound)`
    # and `lower_bound <= Σ dᵢ`. Clamping only the maximum could return a `lower_bound` BELOW the
    # `cp_bound` printed beside it — two mutually exclusive claims in one value, which is a
    # caller's problem however small the discrepancy.
    var serial = 0.0
    for a in range(n_acts):
        serial += duration[a]
    if cp > serial:
        cp = serial
    if res_bound > serial:
        res_bound = serial
    var lb = cp
    if binding >= 0 and res_bound > lb:
        lb = res_bound
    return RcpspBound(
        MODEL_OK, True, lb, cp, binding >= 0, res_bound if binding >= 0 else SCHED_ABSENT,
        binding, -1, len(prec.order), n_acts, path^
    )


# ── RCPSP: the resource profile ───────────────────────────────────────────────


fn _usage_at(
    duration: List[Float64], demand: List[Float64], n_acts: Int, n_res: Int,
    start: List[Float64], placed: List[Bool], t: Float64, r: Int, skip: Int
) -> Float64:
    """Total demand for resource `r` at instant `t`, over the placed activities.

    An activity is running at `t` when `start <= t < finish`, with the finish compared
    OPEN so a hand-off — one activity ending exactly where the next begins — is not an
    overlap. Both comparisons carry a slop at the magnitude of the two times involved.
    """
    var total = 0.0
    for a in range(n_acts):
        if a == skip or not placed[a]:
            continue
        if duration[a] <= 0.0:
            continue
        var s = start[a]
        var f = s + duration[a]
        if t < s - _rel_slop(_scale2(t, s), 1):
            continue
        if t > f - _rel_slop(_scale2(t, f), 1):
            continue
        total += demand[a * n_res + r]
    return total


fn _fits_at(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    n_acts: Int, n_res: Int, start: List[Float64], placed: List[Bool], act: Int,
    t: Float64, mut work: Int
) -> Bool:
    """True when `act` can run over `[t, t + d)` without any resource exceeding capacity.

    The profile is piecewise constant and rises ONLY at a start, so the maximum over the
    interval is attained at `t` or at the start of an activity inside it. Those are the only
    instants checked, and that is a complete check rather than a sample.
    """
    var d = duration[act]
    if d <= 0.0:
        return True
    var instants = List[Float64]()
    instants.append(t)
    # The instant list costs a pass over every activity whether or not any demand is positive,
    # and the loop below costs `n_res` per instant for the same reason. Charging only inside the
    # `need > 0` branch left both free, so an instance of all-zero demands paid nothing for work
    # it really did — every loop bound that multiplies into the cost is charged.
    work += n_acts
    for a in range(n_acts):
        if not placed[a] or duration[a] <= 0.0:
            continue
        var s = start[a]
        if s > t and s < t + d:
            instants.append(s)
    for i in range(len(instants)):
        var tau = instants[i]
        work += n_res
        for r in range(n_res):
            var need = demand[act * n_res + r]
            if need <= 0.0:
                continue
            var used = _usage_at(
                duration, demand, n_acts, n_res, start, placed, tau, r, act
            )
            work += n_acts
            var total = used + need
            if total > capacity[r] + _rel_slop(_scale2(total, capacity[r]), n_acts):
                return False
    return True


fn _rcpsp_sgs(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    n_acts: Int, n_res: Int, prec: _Prec, order: List[Int], mut work: Int
) -> _Sgs:
    """Serial schedule generation: each activity as early as precedences AND resources allow.

    Decision points are the earliest precedence-feasible start and the finish times of the
    activities already placed — the classic result that an optimal serial schedule needs no
    other candidate. They are drawn from the FROZEN min-heap so they arrive in ascending
    order without a sort, and `heap_pop_min` is only called with a non-empty heap because it
    returns 0.0 for an empty one, which would read as "time zero".

    `ok = False` means no candidate fit, which cannot happen — after the last finish nothing is
    running and every demand fits by `_first_over_capacity` — and is therefore reported by the
    caller as an internal defect rather than patched over. `work_limit = True` is the separate
    outcome where the pass was cut short: the work here is cubic in the activity count, so the
    budget has to be checked INSIDE the pass and not only between passes.
    """
    var start = List[Float64]()
    var placed = List[Bool]()
    for _ in range(n_acts):
        start.append(0.0)
        placed.append(False)
    for idx in range(len(order)):
        if work > SCHED_MAX_WORK:
            return _Sgs(False, True, List[Float64]())
        var a = order[idx]
        var es = 0.0
        for p in range(prec.pred_start[a], prec.pred_start[a + 1]):
            var q = prec.pred_items[p]
            var f = start[q] + duration[q]
            if f > es:
                es = f
        var t = es
        if duration[a] > 0.0:
            var heap = List[Float64]()
            heap_push_min(heap, es)
            # The decision-point heap is built from a pass over every activity, so that pass is
            # charged before it runs rather than after the placement succeeds.
            work += n_acts
            for s in range(n_acts):
                if not placed[s] or duration[s] <= 0.0:
                    continue
                var f = start[s] + duration[s]
                if f > es:
                    heap_push_min(heap, f)
            var found = False
            var last_try = SCHED_ABSENT
            while len(heap) > 0:
                if work > SCHED_MAX_WORK:
                    return _Sgs(False, True, List[Float64]())
                var tc = heap_pop_min(heap)
                if tc == last_try:
                    continue
                last_try = tc
                if _fits_at(
                    duration, demand, capacity, n_acts, n_res, start, placed, a, tc, work
                ):
                    t = tc
                    found = True
                    break
            if not found:
                return _Sgs(False, False, List[Float64]())
        start[a] = t
        placed[a] = True
        work += n_acts
    return _Sgs(True, False, start^)


fn _rcpsp_audit(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    pred_from: List[Int], pred_to: List[Int], n_acts: Int, n_res: Int,
    start: List[Float64]
) -> RcpspAudit:
    """Verify a project schedule against the caller's precedences and capacities.

    THE verifier of the RCPSP side: `rcpsp_verify_flat` and the search's final self-check are
    the same code. A resource violation reports the resource, the instant and the excess, not
    a boolean — "resource 2 is 3.0 over at time 7.0" is actionable and "infeasible" is not.
    """
    var defect = _rcpsp_defect(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res
    )
    if defect != MODEL_OK:
        return RcpspAudit(
            defect, False, SCHED_VIOL_NONE, 0, -1, -1, -1, False, SCHED_ABSENT,
            SCHED_ABSENT, False, SCHED_ABSENT, 0
        )
    if len(start) != n_acts:
        return RcpspAudit(
            MODEL_ERR_LENGTH_MISMATCH, False, SCHED_VIOL_NONE, 0, -1, -1, -1, False,
            SCHED_ABSENT, SCHED_ABSENT, False, SCHED_ABSENT, n_acts
        )
    for a in range(n_acts):
        if not _finite(start[a]):
            return RcpspAudit(
                SCHED_VIOLATION, False, SCHED_VIOL_NON_FINITE_START, 1, a, -1, -1,
                False, SCHED_ABSENT, SCHED_ABSENT, False, SCHED_ABSENT, n_acts
            )
    for a in range(n_acts):
        # Literal `< 0.0` for the reason given in `_jssp_audit`: against exact zero the relative
        # allowance is provably a no-op, and spelling it out keeps it that way.
        if start[a] < 0.0:
            return RcpspAudit(
                SCHED_VIOLATION, False, SCHED_VIOL_NEGATIVE_START, 1, a, -1, -1, True,
                start[a], -start[a], False, SCHED_ABSENT, n_acts
            )
    var span = 0.0
    for a in range(n_acts):
        var f = start[a] + duration[a]
        if f > span:
            span = f

    var kind = SCHED_VIOL_NONE
    var count = 0
    var first_act = -1
    var second_act = -1
    var resource = -1
    var at = SCHED_ABSENT
    var worst = SCHED_ABSENT

    for e in range(len(pred_from)):
        var u = pred_from[e]
        var v = pred_to[e]
        var need = start[u] + duration[u]
        var slack = start[v] - need
        if slack < -_rel_slop(_scale2(need, start[v]), 1):
            count += 1
            if -slack > worst:
                worst = -slack
            if kind == SCHED_VIOL_NONE:
                kind = SCHED_VIOL_PRECEDENCE
                first_act = u
                second_act = v
                at = need

    var placed = List[Bool]()
    for _ in range(n_acts):
        placed.append(True)
    var work = 0
    for j in range(n_acts):
        if duration[j] <= 0.0:
            continue
        var tau = start[j]
        for r in range(n_res):
            var used = _usage_at(
                duration, demand, n_acts, n_res, start, placed, tau, r, -1
            )
            work += n_acts
            if work > SCHED_MAX_WORK:
                return RcpspAudit(
                    SCHED_ERR_WORK_BUDGET, False, SCHED_VIOL_NONE, count, first_act,
                    second_act, resource, False, SCHED_ABSENT, worst, True, span, n_acts
                )
            var excess = used - capacity[r]
            if excess > _rel_slop(_scale2(used, capacity[r]), n_acts):
                count += 1
                if excess > worst:
                    worst = excess
                if kind == SCHED_VIOL_NONE:
                    kind = SCHED_VIOL_RESOURCE_OVER_CAPACITY
                    first_act = j
                    resource = r
                    at = tau

    if kind == SCHED_VIOL_NONE:
        return RcpspAudit(
            MODEL_OK, True, SCHED_VIOL_NONE, 0, -1, -1, -1, False, SCHED_ABSENT, 0.0,
            True, span, n_acts
        )
    return RcpspAudit(
        SCHED_VIOLATION, False, kind, count, first_act, second_act, resource, True, at,
        worst, True, span, n_acts
    )


# ── public: RCPSP ─────────────────────────────────────────────────────────────


fn rcpsp_bound_flat(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    pred_from: List[Int], pred_to: List[Int], n_acts: Int, n_res: Int
) -> RcpspBound:
    """Lower bounds on a project's makespan, with the critical path that justifies one.

    `demand` is `n_acts x n_res` row-major; `pred_from[e]` must finish before `pred_to[e]`
    starts. Both bounds hold for every schedule. A cycle means no schedule exists, and an
    activity demanding more than a resource's capacity means the same at every instant — both
    are statuses, not bounds of 0.0.
    """
    return _rcpsp_bound(duration, demand, capacity, pred_from, pred_to, n_acts, n_res)


fn rcpsp_verify_flat(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    pred_from: List[Int], pred_to: List[Int], n_acts: Int, n_res: Int,
    start: List[Float64]
) -> RcpspAudit:
    """Verify a project schedule: every precedence, and every resource at every peak instant.

    Answers "is this schedule executable" for a schedule from anywhere. A resource over its
    limit at ANY instant is infeasible, and the instant and the resource are both reported.
    """
    return _rcpsp_audit(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res, start
    )


fn rcpsp_peak_usage_flat(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    n_acts: Int, n_res: Int, start: List[Float64]
) -> RcpspPeak:
    """The peak of every resource profile under a schedule, when it happens, and if it fits.

    The profile rises only at a start, so its maximum is attained at one of them; the
    earliest such instant is reported. Precedences are NOT examined here — this is the
    resource picture alone, and `rcpsp_verify_flat` is the whole verdict.

    A start time still has to BE a start time. A non-finite or negative start is refused as
    `SCHED_VIOLATION` at the same strength `_rcpsp_audit` refuses it, and for the reason rule 3
    gives: one declared input invariant enforced at two strengths in one file means the
    behaviour a caller sees depends on which public function it happened to call. It returned
    `MODEL_OK` with a usable-looking profile for `start = [-5.0, 0.0]` while `rcpsp_verify_flat`
    on the same arrays returned `negative_start_time`, and the `makespan` it reported alongside
    was `max(start + duration)` — silently ignoring that the schedule began at -5. The KIND of
    violation is not carried here (`RcpspPeak` has no such field); `rcpsp_verify_flat` names it.

    `peak_time[r]` is `SCHED_ABSENT` for a resource no positive-duration activity ever demands,
    because there is then no instant to report. It used to be initialised to 0.0 and left there,
    which named an instant that need not belong to the schedule at all.
    """
    var empty_edges = List[Int]()
    var defect = _rcpsp_defect(
        duration, demand, capacity, empty_edges, empty_edges, n_acts, n_res
    )
    if defect != MODEL_OK:
        return RcpspPeak(
            defect, 0, 0, False, SCHED_ABSENT, List[Float64](), List[Float64](),
            List[Int]()
        )
    if len(start) != n_acts:
        return RcpspPeak(
            MODEL_ERR_LENGTH_MISMATCH, n_res, 0, False, SCHED_ABSENT, List[Float64](),
            List[Float64](), List[Int]()
        )
    for a in range(n_acts):
        if not _finite(start[a]):
            return RcpspPeak(
                SCHED_VIOLATION, n_res, 0, False, SCHED_ABSENT,
                List[Float64](), List[Float64](), List[Int]()
            )
    for a in range(n_acts):
        if start[a] < 0.0:
            return RcpspPeak(
                SCHED_VIOLATION, n_res, 0, False, SCHED_ABSENT,
                List[Float64](), List[Float64](), List[Int]()
            )
    var peak = List[Float64]()
    var when = List[Float64]()
    var over = List[Int]()
    for _ in range(n_res):
        peak.append(0.0)
        # SCHED_ABSENT, not 0.0: "no instant was measured" is not "the peak happened at time
        # zero". Every start reaching this point is non-negative, so -1.0 is unambiguous.
        when.append(SCHED_ABSENT)
        over.append(0)
    var placed = List[Bool]()
    for _ in range(n_acts):
        placed.append(True)
    var span = 0.0
    for a in range(n_acts):
        var f = start[a] + duration[a]
        if f > span:
            span = f
    var work = 0
    for j in range(n_acts):
        if duration[j] <= 0.0:
            continue
        var tau = start[j]
        for r in range(n_res):
            var used = _usage_at(
                duration, demand, n_acts, n_res, start, placed, tau, r, -1
            )
            work += n_acts
            if work > SCHED_MAX_WORK:
                return RcpspPeak(
                    SCHED_ERR_WORK_BUDGET, n_res, 0, False, SCHED_ABSENT,
                    List[Float64](), List[Float64](), List[Int]()
                )
            # Strictly greater, OR equal at an earlier instant: the reported time has to be
            # the EARLIEST instant attaining the peak, not the first activity index that
            # happens to see it. Scanning in activity order and keeping the first match
            # reported time 3.0 for a profile that already peaked at 0.0. `when[r] < 0.0` is
            # the unmeasured state, which every real instant must displace.
            if (
                used > peak[r]
                or (used == peak[r] and (when[r] < 0.0 or tau < when[r]))
            ):
                peak[r] = used
                when[r] = tau
    var n_over = 0
    for r in range(n_res):
        if peak[r] > capacity[r] + _rel_slop(_scale2(peak[r], capacity[r]), n_acts):
            over[r] = 1
            n_over += 1
    return RcpspPeak(MODEL_OK, n_res, n_over, True, span, peak^, when^, over^)


fn _no_rcpsp(
    status: Int, cycle_act: Int, bad_act: Int, bad_res: Int, n_acts: Int
) -> RcpspResult:
    """An `RcpspResult` carrying no numbers — no schedule, no bound, no gap.

    The culprit fields are the exception: a caller holding `SCHED_PRECEDENCE_CYCLE` or
    `SCHED_RESOURCE_INFEASIBLE` needs to know WHICH activity or resource denies the schedule,
    and that is evidence about the input rather than an answer about a schedule.
    """
    return RcpspResult(
        status, False, False, False, SCHED_ABSENT, False, SCHED_ABSENT, SCHED_ABSENT,
        False, SCHED_ABSENT, False, SCHED_ABSENT, False, SCHED_ABSENT, False,
        SCHED_ABSENT, 0, 0, 0, False, False, -1, bad_act, bad_res, cycle_act, n_acts,
        List[Float64](), List[Int](), List[Int]()
    )


fn rcpsp_sgs_solve_flat(
    duration: List[Float64], demand: List[Float64], capacity: List[Float64],
    pred_from: List[Int], pred_to: List[Int], n_acts: Int, n_res: Int,
    seed: Int, max_restarts: Int
) -> RcpspResult:
    """Multi-start serial schedule generation for the RCPSP, verified and bounded.

    Restart 0 lists activities by largest tail (longest path to the end — the classic
    most-total-successors rule), ties by smallest `_op_key`, then by smallest id. Every later
    restart lists them by smallest `_op_key` among the eligible set, which is a uniform keyed
    random activity list; a list is only ever extended with an activity whose predecessors
    are already on it, so every list is precedence-feasible by construction.

    `max_restarts` is the number of ADDITIONAL randomised lists, so `0` returns the
    deterministic rule alone. The incumbent is the best over all of them, and it has passed
    `rcpsp_verify_flat` against the caller's arrays before it is returned.

    `resource_delayed_at` is the honest part of the explanation: when the last-finishing
    activity's start was set by resource contention rather than by a predecessor, the
    critical chain stops there and that activity is named. A precedence-only "critical path"
    would otherwise present a resource delay as a dependency, which is a wrong answer to
    "what do I change". An instance no schedule can satisfy names BOTH culprits —
    `infeasible_act` and `infeasible_resource` — because "infeasible" alone is not actionable.
    """
    var defect = _rcpsp_defect(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res
    )
    if defect != MODEL_OK:
        var shown = n_acts if defect != SCHED_ERR_EMPTY_INSTANCE else 0
        return _no_rcpsp(defect, -1, -1, -1, shown)
    if max_restarts < 0 or max_restarts > SCHED_MAX_ITERS:
        return _no_rcpsp(SCHED_ERR_INVALID_VALUE, -1, -1, -1, n_acts)
    var over = _first_over_capacity(duration, demand, capacity, n_acts, n_res)
    if over >= 0:
        return _no_rcpsp(
            SCHED_RESOURCE_INFEASIBLE, -1, over // n_res, over % n_res, n_acts
        )
    var prec = _prec_of(pred_from, pred_to, n_acts)
    if not prec.acyclic:
        return _no_rcpsp(SCHED_PRECEDENCE_CYCLE, prec.cycle_act, -1, -1, n_acts)

    var bound = _rcpsp_bound(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res
    )
    if not bound.has_bound:
        # PROPAGATE the bound's own status rather than calling it an internal defect. The
        # defect check, the capacity check and the cycle check have all already passed, so the
        # remaining reason is a value this driver cannot price — and reporting
        # `internal_schedule_failed_verification` for a caller's overflowing demand would send
        # them looking in the wrong place.
        return _no_rcpsp(bound.status, -1, -1, -1, n_acts)
    var lb = bound.lower_bound
    # `terms` for every makespan-against-bound comparison below. A makespan is a sum of
    # durations along a chain of up to `n_acts` activities, and the lower bound is either such a
    # chain or `Σᵢ dᵢ·rᵢ / capᵣ` — a sum over `n_acts` products. Both sides can therefore carry
    # `n_acts` ulps of accumulation, and `terms = 2` under-sized the allowance for exactly the
    # two quantities being judged. That matters because the consequence of under-sizing it is
    # `SCHED_ERR_UNVERIFIED` — an internal-defect status with no numbers — for a caller's
    # perfectly good instance. It is still the length of THOSE sums, not a count of anything
    # else, and the bound is separately clamped at `Σᵢ dᵢ` so the check cannot paper over a real
    # contradiction.
    var bound_terms = n_acts + 2
    var tail = _cp_tail(duration, prec)
    var key = _seed_key(seed)
    var stream = stream_id("optimization.scheduling.rcpsp")

    var best_start = List[Float64]()
    var best_order = List[Int]()
    var best_span = SCHED_ABSENT
    var initial_span = SCHED_ABSENT
    var built = 0
    var improvements = 0
    var work = 0
    var work_limit = False

    for restart in range(max_restarts + 1):
        if work > SCHED_MAX_WORK:
            work_limit = True
            break
        var remaining = List[Int]()
        for a in range(n_acts):
            remaining.append(prec.pred_start[a + 1] - prec.pred_start[a])
        var listed = List[Bool]()
        for _ in range(n_acts):
            listed.append(False)
        var order = List[Int]()
        var aborted = False
        for _ in range(n_acts):
            if work > SCHED_MAX_WORK:
                aborted = True
                break
            var pick = -1
            var pick_tail = 0.0
            var pick_key = 0.0
            for a in range(n_acts):
                if listed[a] or remaining[a] > 0:
                    continue
                var k = _op_key(key, stream, restart, a)
                var better = False
                if pick < 0:
                    better = True
                elif restart == 0:
                    if tail[a] > pick_tail:
                        better = True
                    elif tail[a] == pick_tail and k < pick_key:
                        better = True
                elif k < pick_key:
                    better = True
                if better:
                    pick = a
                    pick_tail = tail[a]
                    pick_key = k
            if pick < 0:
                break
            order.append(pick)
            listed[pick] = True
            for p in range(prec.succ_start[pick], prec.succ_start[pick + 1]):
                remaining[prec.succ_items[p]] -= 1
            work += n_acts
        if aborted:
            work_limit = True
            break
        if len(order) != n_acts:
            # Every activity has to become eligible in a DAG, so a short list means the
            # eligibility bookkeeping here disagrees with the topological sort.
            return _no_rcpsp(SCHED_ERR_UNVERIFIED, -1, -1, -1, n_acts)

        var pass_out = _rcpsp_sgs(
            duration, demand, capacity, n_acts, n_res, prec, order, work
        )
        if pass_out.work_limit:
            work_limit = True
            break
        built += 1
        if not pass_out.ok or len(pass_out.start) != n_acts:
            return _no_rcpsp(SCHED_ERR_UNVERIFIED, -1, -1, -1, n_acts)
        var start = pass_out.start.copy()
        var span = 0.0
        for a in range(n_acts):
            var f = start[a] + duration[a]
            if f > span:
                span = f
        if restart == 0:
            initial_span = span
        if best_span < 0.0 or span < best_span - _rel_slop(
            _scale2(span, best_span), bound_terms
        ):
            if best_span >= 0.0:
                improvements += 1
            best_span = span
            best_start = start.copy()
            best_order = order.copy()
        var slop_now = _rel_slop(_scale2(best_span, lb), bound_terms)
        if best_span <= lb + slop_now:
            break

    if len(best_start) != n_acts:
        # The work ceiling tripped before ONE schedule existed, so there is nothing to report.
        return _no_rcpsp(SCHED_ERR_WORK_BUDGET, -1, -1, -1, n_acts)
    var audit = _rcpsp_audit(
        duration, demand, capacity, pred_from, pred_to, n_acts, n_res, best_start
    )
    if audit.status == SCHED_ERR_WORK_BUDGET:
        # No verdict, not a failed verdict — see the same distinction in the job-shop driver.
        return _no_rcpsp(SCHED_ERR_WORK_BUDGET, -1, -1, -1, n_acts)
    if not audit.feasible:
        return _no_rcpsp(SCHED_ERR_UNVERIFIED, -1, -1, -1, n_acts)
    var slop = _rel_slop(_scale2(best_span, lb), bound_terms)
    if best_span < lb - slop:
        return _no_rcpsp(SCHED_ERR_UNVERIFIED, -1, -1, -1, n_acts)
    if fabs(audit.makespan - best_span) > _rel_slop(
        _scale2(audit.makespan, best_span), bound_terms
    ):
        return _no_rcpsp(SCHED_ERR_UNVERIFIED, -1, -1, -1, n_acts)

    # The explanation: walk back from the last finish through the predecessor that actually
    # set each start, and stop at the activity whose start no predecessor explains.
    var last = 0
    for a in range(n_acts):
        var f = best_start[a] + duration[a]
        if f > best_start[last] + duration[last]:
            last = a
    var back = List[Int]()
    var delayed = -1
    var cur = last
    var steps = 0
    while cur >= 0 and steps <= n_acts:
        back.append(cur)
        var nxt = -1
        for p in range(prec.pred_start[cur], prec.pred_start[cur + 1]):
            var q = prec.pred_items[p]
            var f = best_start[q] + duration[q]
            # `n_acts + 1` terms: both `f` and `best_start[cur]` are sums accumulated along a
            # chain of up to `n_acts` activities, and an allowance too tight here does not report
            # a violation — it silently blames a RESOURCE for a start a predecessor explains.
            if fabs(f - best_start[cur]) <= _rel_slop(
                _scale2(f, best_start[cur]), n_acts + 1
            ):
                nxt = q
                break
        # Strictly positive, literally: see `_jssp_audit` on why the tolerant form against exact
        # zero is a no-op. A start of 0.0 needs no explanation, so it is not a delay.
        if nxt < 0 and best_start[cur] > 0.0:
            delayed = cur
        cur = nxt
        steps += 1
    var chain = List[Int]()
    for i in range(len(back)):
        chain.append(back[len(back) - 1 - i])

    var gap = best_span - lb
    if gap < 0.0:
        gap = 0.0
    var optimal = gap <= slop
    # A restart budget that was consumed without closing the gap IS a limit: more lists could
    # help. `max_restarts == 0` is not, because the caller asked for one construction and got
    # it — the driver was not cut short, it was not asked for more.
    #
    # `built == max_restarts + 1` is load-bearing: without it a run the WORK ceiling cut short
    # after one of a hundred restarts would also claim its restart budget was exhausted, and a
    # caller reading `budget_limit_hit` would buy restarts that were never the constraint.
    var budget_limit = (
        (not optimal) and max_restarts > 0 and built == max_restarts + 1
    )
    var status = SCHED_FEASIBLE
    if optimal:
        status = SCHED_OPTIMAL
    elif work_limit or budget_limit:
        status = SCHED_LIMIT
    var rel = SCHED_ABSENT
    var has_rel = lb > 0.0
    if has_rel:
        rel = gap / lb
    return RcpspResult(
        status, True, True, True, best_span, True, lb, bound.cp_bound,
        bound.has_resource_bound, bound.resource_bound, True, gap, has_rel, rel,
        optimal, initial_span, built, improvements, built - 1, work_limit,
        budget_limit, delayed, -1, -1, -1, n_acts, best_start^, best_order^, chain^
    )
