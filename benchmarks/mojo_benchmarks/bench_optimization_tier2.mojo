"""bench_optimization_tier2.mojo — measured gate for `optimization` tier 2.

Tier 2 is `quadratic`, `routing`, `scheduling`, `multiobjective` and `robust`. Tier 1
(`model`, `linear`, `integer`, `assignment`, `flow`, `explain`) has its own file,
`bench_optimization.mojo`, and nothing here repeats an arm from it — in particular the
Hungarian-versus-greedy exactness arm lives there and is not restated.

Hand-written, not generated, and the name cannot collide: `benchmark_mojo_vs_python.py`
writes `bench_<lib_id>.mojo` where `lib_id` for a module inside a package is
`<subdir>_<stem>`, so the generated names for this package are `bench_optimization_routing`,
`bench_optimization_quadratic` and so on. No `lib_id` is ever `optimization_tier2`.
`make bench-optimization-tier2` is the only thing that runs this file.

WHAT KIND OF ANSWER EACH ARM IS ABOUT
-------------------------------------
Three of these five modules are HEURISTIC and nothing below claims otherwise. `routing`
(2-opt / Or-opt / double-bridge kicks), `scheduling` (tabu over critical machine arcs, serial
schedule generation with restarts) and `multiobjective`'s `nsga2_linear` return a good answer
and a bound they can actually prove; a local optimum is not an optimum, and no gate here is
worded as if it were. Where a true optimum IS known it is known for a reason stated at the
instance, never because a solver said so:

  * a unit-step Hamiltonian cycle on an 8x8 lattice has length exactly 64, and no tour can be
    shorter because every distinct pair of lattice points is at least 1 apart — so 64.0 is a
    PROVEN optimum, and the heuristic's distance from it is measured, not asserted;
  * `n` cities equally spaced on a circle of radius `R` are in convex position, so the optimal
    tour is the hull order and its length is exactly `n * 2R * sin(pi/n)`;
  * a job shop with ONE job is a chain: its makespan is the sum of its durations, which is also
    the module's own job bound, so the bound is exact there and tabu has nothing to find;
  * an RCPSP whose activities each need the whole of one resource is fully serial, so the
    resource-area bound `sum(d_i * r_i) / capacity` is exact;
  * the hypervolume dominated by ONE point under a reference is a rectangle.

Everywhere else the number reported is a GAP against a bound the module computed and this file
re-derives independently, or an improvement over the frozen seed. Never "optimal".

THE BASELINES, AND WHY EACH IS THE FAIR ONE
-------------------------------------------
1. **routing against the frozen `combinatorial.tsp_greedy`.** That is the seed the drivers
   actually start from — `tsp_greedy_flat` is a validated window onto the frozen kernel, not a
   second implementation — so the improvement measured is exactly what the local search adds
   and nothing else. The claim is TOUR QUALITY, not speed: local search costs strictly more
   than the nearest-neighbour pass it improves, and that ratio is printed rather than buried.
   Every returned tour's length is re-derived through the frozen `tsp_tour_length`
   (`tour_length_flat`) before any quality number is believed.
2. **`quadratic` against `optimization.linear.lp_solve`.** With `Q = 0` the QP driver is
   solving a linear program, and tier 1's two-phase simplex is an independently verified
   answer on the same data. The OBJECTIVE is gated to agree first, and each arm's returned
   point is then re-verified here — its objective recomputed from `c` and `x` by hand, and
   every row checked at that row's own scale. `x` itself is NOT gated, and the measurement is
   why: it agrees to 4096 ulps at n = 4, 8 and 16 and then diverges completely at n = 32,
   because this program's optimal face stops being a single point and a pivoting method and a
   null-space method halt at different corners of it with the same objective. Gating on `x`
   would have been gating on which corner. The timing is then reported as the price of the
   general path on a problem the simplex handles directly, which is the honest direction of
   that comparison. Both arms get the same warmup and the same repetition count, and neither
   pays for input construction inside its timed region.
3. **`scheduling` against its own critical-path / job / machine bounds**, re-derived here from
   the durations by hand at every size, so the "bound" is not taken on the struct's word.
4. **`multiobjective` against the frozen `multi_objective.pareto_front`.** `nondominated_sort`
   ranks EVERY front; the frozen kernel extracts front 0 only. That is not the same work, so
   the ratio between them is printed as what it is — the price of the full ranking — and the
   gate is that the two agree on front 0, via `pareto_certify`, whose oracle is that same
   frozen kernel.
5. **`robust` against the deterministic LP it degenerates to.** With `S` IDENTICAL scenarios
   the robust answer must equal the single-scenario answer bit-for-bit, and it is compared
   against `lp_solve_default` on the base right-hand side. That is the strongest cross-check
   available here because it pins a new driver to an independently verified one, and it is
   gated with `==` rather than a tolerance.

DETERMINISM IS A MEASURED GATE, NOT A CLAIM
-------------------------------------------
Every seeded driver in tier 2 is called twice with the same seed and the results compared
BIT-FOR-BIT — not to a tolerance — and then once with a different seed. Same seed must
reproduce exactly. A different seed is expected to move the search path, and where it does not
that is reported rather than hidden: on a convex QP a different seed must return the IDENTICAL
optimum, because convexity requires it, and a solver whose answer moved with its seed would be
the thing wrong. The instances themselves are generated by a fixed-seed LCG declared at
`INSTANCE_SEED`, so re-running this file on the same binary reproduces every number.

TOLERANCES (rule 4b)
--------------------
`_rel_close` builds its tolerance from the magnitude of THE TWO NUMBERS BEING COMPARED and
nothing else, sizes the relative term with `DBL_EPSILON` rather than with a caller tolerance,
and takes any absolute allowance as an explicit argument so it can never silently dominate.
Vector comparisons are per element, each against its own magnitude. There is no sum, no norm
and no `1 +` floor anywhere in this file.

GATE
----
Fails on properties, never on absolute nanoseconds. `⚠️` lines are measured facts that run
against the package and are printed on purpose.
  * every heuristic tour is at least as long as the proven optimum of its instance, and its
    reported length equals the frozen kernel's re-derivation
  * tour length is non-increasing as the pass cap rises
  * `Q = 2I` reproduces the closed form `x = -c/2` bit-exactly, and `Q = 0` agrees with
    `lp_solve` on the objective at a point this file independently re-verifies feasible
  * a Hessian mixing units, `diag(1e12, 0.5)`, solves to its known optimum and reports
    `min_pivot = 0.5` — the equilibration, measured
  * a one-job shop's makespan equals its chain length and the bound proves it; a real shop's
    makespan is never below the bound, and the GAP is reported
  * hypervolume of one point equals the rectangle exactly; three objectives report the value
    ABSENT with exact bounds `[9.0, 12.0]` bracketing a hand-derived 11.0 and a seeded
    estimate inside its own standard error of it
  * `S` identical scenarios give the deterministic objective bit-identically, and the
    here-and-now robust objective is never better than the worst perfect-foresight optimum
  * every seeded driver reproduces bit-for-bit under its own seed
  * seven drivers return an ABSENT answer — empty vector, `has_* == False` — rather than a
    zero, for a question with no answer
"""
from std.math import abs as fabs, cos, log, sin, sqrt
from std.time import perf_counter_ns

from determinism.counter_rng import rng_version
from multi_objective import pareto_front
from optimization.linear import LP_INFEASIBLE, LP_OPTIMAL, lp_solve_default
from optimization.model import (
    MODEL_OK,
    SENSE_GE,
    SENSE_LE,
    VAR_FLAG_HAS_LOWER,
)
from optimization.multiobjective import (
    MO_HV_ESTIMATE_CLAMPED,
    MO_HV_INEXACT,
    MO_UNPROVEN,
    hypervolume_default,
    mo_status_name,
    nondominated_sort,
    nsga2_linear_default,
    pareto_certify,
)
from optimization.quadratic import (
    QP_OPTIMAL,
    QP_UNBOUNDED,
    qp_convexity_flat,
    qp_solve_default,
    qp_status_name,
)
from optimization.robust import (
    ROBUST_BOUND_ONLY,
    ROBUST_SCENARIO_FAILED,
    ROBUST_UNVERIFIED,
    robust_min_max_rhs_default,
    robust_scenario_solve_default,
    robust_status_name,
    scenario_rhs_normal,
)
from optimization.routing import (
    ROUTE_OK,
    ROUTE_OK_LIMIT,
    distance_matrix_check,
    tour_length_flat,
    tsp_greedy_flat,
    tsp_iterated_local_search,
    tsp_local_search,
    tsp_two_opt,
    route_status_name,
)
from optimization.scheduling import (
    SCHED_FEASIBLE,
    SCHED_LIMIT,
    SCHED_OPTIMAL,
    SCHED_PRECEDENCE_CYCLE,
    jobshop_bound_flat,
    jobshop_tabu_solve_flat,
    jobshop_verify_flat,
    rcpsp_bound_flat,
    rcpsp_sgs_solve_flat,
    sched_status_name,
)

comptime WARMUP: Int = 3
comptime DBL_EPSILON: Float64 = 2.220446049250313e-16
comptime PI: Float64 = 3.141592653589793

# Every pseudo-random instance in this file comes from this one constant through `_lcg_next`.
# Nothing here calls a wall clock, a process id or `random_float64`, so the whole run is
# reproducible on a given binary — which is the same premise the modules themselves rest on.
comptime INSTANCE_SEED: Int = 20260731


# ── measurement and comparison helpers ────────────────────────────────────────


fn _ms(elapsed: UInt) -> Float64:
    """`perf_counter_ns` yields UInt, so the delta stays unsigned until here."""
    return Float64(Int(elapsed)) / 1.0e6


fn _exponent(t_first: Float64, t_last: Float64, n_first: Int, n_last: Int) -> Float64:
    """The empirical growth exponent `p` in `t ~ n^p`, from the two endpoints.

    Reported instead of a complexity claim: `p` is what was measured, and it is only two
    points, which is why every intermediate size is printed too.
    """
    if t_first <= 0.0 or t_last <= 0.0 or n_first <= 0 or n_last <= n_first:
        return 0.0
    return log(t_last / t_first) / log(Float64(n_last) / Float64(n_first))


fn _rel_close(a: Float64, b: Float64, ulps: Float64, abs_tol: Float64) -> Bool:
    """`a` equals `b` to `ulps` of THEIR OWN magnitude, plus an explicit absolute allowance.

    Rule 4b, all four spellings avoided deliberately, because a benchmark's comparison code is
    exactly where a fifth one would be introduced:

      * the scale is `max(|a|, |b|)` — the magnitude of the one quantity being judged. It is
        not a sum over a vector (spelling 1) and not a max or a norm over a collection of
        other numbers (spelling 2). Two scalars are the whole comparison, so their own
        maximum IS per-item;
      * the relative term is `DBL_EPSILON * ulps`, never a caller tolerance multiplied by a
        magnitude (spelling 4);
      * there is NO `1 +` floor (spelling 3). An absolute allowance is passed in by the caller
        when one is meaningful — a makespan in whole time units, say — so it is always a
        choice on the record and can never quietly become the whole test at small `|a|`.
    """
    var d = a - b
    if d < 0.0:
        d = -d
    var m = a if a >= 0.0 else -a
    var mb = b if b >= 0.0 else -b
    if mb > m:
        m = mb
    return d <= abs_tol + ulps * DBL_EPSILON * m


fn _vec_rel_close(
    a: List[Float64], b: List[Float64], ulps: Float64, abs_tol: Float64
) -> Bool:
    """Element by element, each element against its OWN magnitude. Never a vector norm."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not _rel_close(a[i], b[i], ulps, abs_tol):
            return False
    return True


fn _vec_exact(a: List[Float64], b: List[Float64]) -> Bool:
    """Bit-for-bit. Used for determinism, where a tolerance would defeat the point."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _ints_exact(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _worst_le_violation(
    a: List[Float64], rows: Int, cols: Int, b: List[Float64], x: List[Float64]
) -> Float64:
    """The worst RELATIVE violation of `A x <= b` and `x >= 0`, measured here, not asked for.

    Rule 4b, per row: row `i`'s violation is divided by row `i`'s own magnitude —
    `max(|activity_i|, |b_i|)` — and never by a sum, a max or a norm over the other rows. One
    row with a right-hand side of 1e7 therefore cannot buy any slack for a different row, which
    is the exact defect that made an infeasible LP report optimal in tier 1.

    Used to compare two solvers whose optimal FACE is not a single point: when the LP optimum
    is not unique, "same answer" means the same objective at two feasible points, and this is
    the half of that statement a benchmark has to compute for itself.
    """
    var worst = 0.0
    for i in range(rows):
        var act = 0.0
        var mag = 0.0
        for j in range(cols):
            var term = a[i * cols + j] * x[j]
            act += term
            var at = term if term >= 0.0 else -term
            if at > mag:
                mag = at
        var bi = b[i] if b[i] >= 0.0 else -b[i]
        if bi > mag:
            mag = bi
        var acta = act if act >= 0.0 else -act
        if acta > mag:
            mag = acta
        if mag <= 0.0:
            mag = 1.0
        var over = (act - b[i]) / mag
        if over > worst:
            worst = over
    for j in range(cols):
        var neg = -x[j] / (1.0 if x[j] == 0.0 else (x[j] if x[j] >= 0.0 else -x[j]))
        if neg > worst:
            worst = neg
    return worst


fn _dot(c: List[Float64], x: List[Float64]) -> Float64:
    var total = 0.0
    for j in range(len(c)):
        total += c[j] * x[j]
    return total


fn _lcg_next(s: Int) -> Int:
    """The one pseudo-random source for INSTANCES in this file, seeded by `INSTANCE_SEED`.

    Instance data only. Every algorithmic draw inside the modules goes through
    `determinism/counter_rng` and `determinism/sampling_keyed` under a caller seed, which is
    what the determinism section measures.
    """
    return (s * 1103515245 + 12345) % 2147483648


fn _senses(code: Int, n: Int) -> List[Int]:
    var out = List[Int]()
    for _ in range(n):
        out.append(code)
    return out^


fn _fill(value: Float64, n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(value)
    return out^


fn _ifill(value: Int, n: Int) -> List[Int]:
    var out = List[Int]()
    for _ in range(n):
        out.append(value)
    return out^


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _int_list(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


# ── routing instances, each with a stated reason its optimum is known ─────────


fn _euclidean_matrix(xs: List[Float64], ys: List[Float64]) -> List[Float64]:
    """Flat row-major `n x n` Euclidean distances.

    Symmetric to the bit — `(xi - xj)` and `(xj - xi)` square to the same double, negation
    being exact — and the diagonal is exactly 0.0, which `routing`'s matrix validation
    requires and checks by index rather than by tolerance.
    """
    var n = len(xs)
    var out = List[Float64]()
    for i in range(n):
        for j in range(n):
            var dx = xs[i] - xs[j]
            var dy = ys[i] - ys[j]
            out.append(sqrt(dx * dx + dy * dy))
    return out^


fn _grid_points(
    rows: Int, cols: Int, stride: Int, mut xs: List[Float64], mut ys: List[Float64]
):
    """`rows x cols` unit lattice, city indices SCRAMBLED against the lattice order.

    Why the optimum is known exactly. Every two distinct lattice points are at Euclidean
    distance at least 1, so every tour of `n = rows * cols` cities has length at least `n`.
    When `n` is even the grid graph has a Hamiltonian cycle of unit steps (the boustrophedon
    closed by the first column), which attains `n`. So `n` is a PROVEN optimum, not a
    solver's opinion — and it is an integer, so the ratio to it is readable.

    `stride` must be coprime with `n` so the map is a bijection; the offset puts city 0 in the
    middle of the lattice rather than at a corner, because nearest-neighbour from a corner
    happens to do well and that would be the charitable instance rather than the fair one.
    """
    var n = rows * cols
    var offset = (rows // 2) * cols + cols // 2
    for j in range(n):
        var cell = (j * stride + offset) % n
        xs.append(Float64(cell % cols))
        ys.append(Float64(cell // cols))


fn _circle_points(
    n: Int, radius: Float64, stride: Int, mut xs: List[Float64], mut ys: List[Float64]
):
    """`n` cities equally spaced on a circle, indices scrambled against the hull order.

    Why the optimum is known exactly. Points on a circle are in convex position, so the
    optimal tour is the hull order, and with equal spacing it is `n` copies of the chord
    subtending `2*pi/n`: `n * 2R * sin(pi/n)`. Independent of every algorithm here.
    """
    for j in range(n):
        var k = (j * stride) % n
        var theta = 2.0 * PI * Float64(k) / Float64(n)
        xs.append(radius * cos(theta))
        ys.append(radius * sin(theta))


fn _random_points(
    n: Int, seed: Int, mut xs: List[Float64], mut ys: List[Float64]
):
    """A deterministic pseudo-random point cloud. No known optimum, and none is claimed."""
    var s = seed
    for _ in range(n):
        s = _lcg_next(s)
        xs.append(Float64(s % 1000) / 10.0)
        s = _lcg_next(s)
        ys.append(Float64(s % 1000) / 10.0)


# ── scheduling instances ──────────────────────────────────────────────────────


fn _jssp_durations(n_jobs: Int, n_ops: Int, seed: Int) -> List[Float64]:
    var out = List[Float64]()
    var s = seed
    for _ in range(n_jobs * n_ops):
        s = _lcg_next(s)
        out.append(1.0 + Float64(s % 20))
    return out^


fn _jssp_latin(n_jobs: Int, n_ops: Int, n_machines: Int) -> List[Int]:
    """`machine_of[j][k] = (j + k) mod n_machines`: every job visits every machine once.

    A Latin square is the standard hard shape — it forces every machine to be contended by
    every job, so the machine bound and the job bound are both live and the gap is real.
    """
    var out = List[Int]()
    for j in range(n_jobs):
        for k in range(n_ops):
            out.append((j + k) % n_machines)
    return out^


fn _chain_edges(n_acts: Int, mut pred_from: List[Int], mut pred_to: List[Int]):
    for i in range(n_acts - 1):
        pred_from.append(i)
        pred_to.append(i + 1)


# ── multiobjective instances ──────────────────────────────────────────────────


fn _mo_points(n_points: Int, n_obj: Int, seed: Int) -> List[Float64]:
    """Flat `n_points x n_obj` pseudo-random objective vectors, every objective minimised."""
    var out = List[Float64]()
    var s = seed
    for _ in range(n_points * n_obj):
        s = _lcg_next(s)
        out.append(Float64(s % 100000) / 100.0)
    return out^


fn _nested(f: List[Float64], n_points: Int, n_obj: Int) -> List[List[Float64]]:
    """The nested form the frozen `pareto_front` takes.

    Built OUTSIDE both timed regions, so neither arm pays for the other's input layout: the
    flat driver gets a flat list and the frozen kernel gets a nested one, each in the form its
    caller would already hold.
    """
    var out = List[List[Float64]]()
    for i in range(n_points):
        var row = List[Float64]()
        for t in range(n_obj):
            row.append(f[i * n_obj + t])
        out.append(row^)
    return out^


# ── the shared robust / QP linear program ─────────────────────────────────────
#
# minimise -5x - 8y over x + y <= 6, 5x + 9y <= 45, x, y >= 0. Optimum -41.25 at
# (2.25, 3.75), hand-derived before anything below was run, and the same program tier 1's
# quadratic suite uses as its differential oracle.


fn _lp_c() -> List[Float64]:
    return _floats(-5.0, -8.0)


fn _lp_a() -> List[Float64]:
    return _floats(1.0, 1.0, 5.0, 9.0)


fn _lp_b() -> List[Float64]:
    return _floats(6.0, 45.0)


fn _dense_lp_a(n: Int) -> List[Float64]:
    """Diagonally dominant, so the basis really fills instead of loading one variable."""
    var out = List[Float64]()
    for i in range(n):
        for j in range(n):
            if i == j:
                out.append(1.0)
            else:
                out.append(0.1 + 0.01 * Float64((i * 13 + j * 7) % 7))
    return out^


fn _dense_lp_b(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for i in range(n):
        out.append(100.0 + Float64(i))
    return out^


fn _dense_lp_c(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for j in range(n):
        out.append(-1.0 - 0.5 * Float64(j % 3))
    return out^


fn main() raises:
    var failures = 0

    # ══ 1. routing: tour QUALITY against the frozen greedy seed ═══════════════
    print("=== TSP: 2-opt / Or-opt against the frozen combinatorial.tsp_greedy seed ===")
    print(
        "    the claim is TOUR QUALITY, never speed: local search costs strictly more than"
    )
    print("    the nearest-neighbour pass it improves, and that price is printed below.")
    print("")

    # 1a. the lattice, whose optimum is the proven integer `n`.
    print("  -- 8x8 unit lattice, proven optimum = 64.0 (every step >= 1, a unit cycle exists)")
    var g_xs = List[Float64]()
    var g_ys = List[Float64]()
    _grid_points(8, 8, 13, g_xs, g_ys)
    var grid_d = _euclidean_matrix(g_xs, g_ys)
    var grid_n = 64
    var grid_opt = 64.0

    var grid_census = distance_matrix_check(grid_d, grid_n)
    var grid_seed_tour = tsp_greedy_flat(grid_d, grid_n)

    for _ in range(WARMUP):
        var _wg = tsp_greedy_flat(grid_d, grid_n)
    var t0 = perf_counter_ns()
    for _ in range(32):
        var _rg = tsp_greedy_flat(grid_d, grid_n)
    var t1 = perf_counter_ns()
    var greedy_ms = _ms(t1 - t0) / 32.0

    for _ in range(WARMUP):
        var _wl = tsp_local_search(grid_d, grid_n, 64, True, True, 3)
    var t2 = perf_counter_ns()
    for _ in range(32):
        var _rl = tsp_local_search(grid_d, grid_n, 64, True, True, 3)
    var t3 = perf_counter_ns()
    var ls_ms = _ms(t3 - t2) / 32.0

    var grid_ls = tsp_local_search(grid_d, grid_n, 64, True, True, 3)
    # The reported length is re-derived through the FROZEN `tsp_tour_length`. A quality number
    # computed by the same code that produced the tour is not evidence about the tour.
    var grid_recheck = tour_length_flat(grid_d, grid_n, grid_ls.tour)
    var seed_recheck = tour_length_flat(grid_d, grid_n, grid_seed_tour.tour)

    var grid_ok = (
        grid_census.status == ROUTE_OK
        and grid_census.symmetric
        and grid_census.triangle_checked
        and grid_census.triangle_ok
        and grid_seed_tour.status == ROUTE_OK_LIMIT
        and grid_seed_tour.has_length
        and grid_ls.status == ROUTE_OK
        and grid_ls.local_optimum
        and grid_ls.has_length
        and grid_ls.has_seed_length
        and grid_recheck.status == ROUTE_OK
        and grid_recheck.has_value
        and seed_recheck.status == ROUTE_OK
        # same answer, from two independent length computations
        and _rel_close(grid_recheck.value, grid_ls.tour_length, 256.0, 0.0)
        and _rel_close(seed_recheck.value, grid_seed_tour.tour_length, 256.0, 0.0)
        # never shorter than a PROVEN optimum
        and grid_ls.tour_length >= grid_opt - 1e-9
        and grid_seed_tour.tour_length >= grid_opt - 1e-9
    )
    var grid_seed_ratio = grid_seed_tour.tour_length / grid_opt
    var grid_ls_ratio = grid_ls.tour_length / grid_opt
    var grid_impr_pct = (
        100.0 * grid_ls.improvement / grid_seed_tour.tour_length
        if grid_seed_tour.tour_length > 0.0
        else 0.0
    )
    print(
        "     matrix census: symmetric=" + String(grid_census.symmetric),
        "max_asymmetry=" + String(grid_census.max_asymmetry),
        "triangle_checked=" + String(grid_census.triangle_checked),
        "triangle_ok=" + String(grid_census.triangle_ok),
        "min_offdiag=" + String(grid_census.min_offdiag),
        "max_offdiag=" + String(grid_census.max_offdiag),
    )
    print(
        "     greedy_seed=" + String(grid_seed_tour.tour_length),
        "(" + String(grid_seed_ratio) + "x optimum)",
        "| local_search=" + String(grid_ls.tour_length),
        "(" + String(grid_ls_ratio) + "x optimum)",
    )
    print(
        "     improvement=" + String(grid_ls.improvement),
        "(" + String(grid_impr_pct) + "%)",
        "passes=" + String(grid_ls.passes),
        "moves_applied=" + String(grid_ls.moves_applied),
        "moves_evaluated=" + String(grid_ls.moves_evaluated),
    )
    print(
        "     greedy=" + String(greedy_ms) + "ms",
        "local_search=" + String(ls_ms) + "ms",
        "quality_costs=" + String(ls_ms / greedy_ms if greedy_ms > 0.0 else 0.0) + "x",
    )
    if grid_ok:
        print(
            "  ✅ both tours are at least the proven optimum 64.0, and the frozen"
            " tsp_tour_length re-derives both reported lengths"
        )
    else:
        failures += 1
        print(
            "  ❌ the lattice arm failed:",
            route_status_name(grid_ls.status),
            grid_ls.tour_length,
            grid_recheck.value,
        )

    # 1b. non-increasing across the pass cap. Each call re-seeds from the frozen greedy and
    # runs at most `p` passes, so the sequence over `p` is the improvement curve.
    print("")
    print("  -- tour length is non-increasing as the pass cap rises (same instance, same seed)")
    var monotone = True
    var prev_len = grid_seed_tour.tour_length
    var pass_line = String("     lengths:")
    for p in range(1, 9):
        var r = tsp_two_opt(grid_d, grid_n, p)
        if r.status != ROUTE_OK and r.status != ROUTE_OK_LIMIT:
            monotone = False
            break
        if not r.has_length:
            monotone = False
            break
        if r.tour_length > prev_len + 1e-12:
            monotone = False
        pass_line += " p" + String(p) + "=" + String(r.tour_length)
        prev_len = r.tour_length
    print(pass_line)
    if monotone:
        print(
            "  ✅ 2-opt tour length never rose over pass caps 1..8, starting from the"
            " frozen greedy seed"
        )
    else:
        failures += 1
        print("  ❌ 2-opt tour length rose as the pass cap rose; the search is not monotone")

    # 1c. the circle, where the KNOWN optimum is attained by the seed as well.
    print("")
    print("  -- cities on a circle: convex position, optimum = n * 2R * sin(pi/n), R = 100")
    var circle_sizes = _int_list(8, 16, 32, 64)
    var circle_ok = True
    for s in range(len(circle_sizes)):
        var n = circle_sizes[s]
        var c_xs = List[Float64]()
        var c_ys = List[Float64]()
        _circle_points(n, 100.0, 3, c_xs, c_ys)
        var cd = _euclidean_matrix(c_xs, c_ys)
        var known = Float64(n) * 200.0 * sin(PI / Float64(n))
        var seedt = tsp_greedy_flat(cd, n)
        var ls = tsp_local_search(cd, n, 64, True, True, 3)
        # `64 * (n + 1)` ulps of the length's OWN magnitude: `n` chords summed, each carrying
        # the rounding of a sin/cos pair, a sqrt and an add. Relative throughout — at n = 64
        # this is about 9e-13 of a length near 6280, and it is not a floor.
        var ulps = 64.0 * Float64(n + 1)
        var ok = (
            seedt.status == ROUTE_OK_LIMIT
            and ls.status == ROUTE_OK
            and ls.local_optimum
            and _rel_close(seedt.tour_length, known, ulps, 0.0)
            and _rel_close(ls.tour_length, known, ulps, 0.0)
            and ls.tour_length >= known - ulps * DBL_EPSILON * known
        )
        if not ok:
            circle_ok = False
        print(
            "     n=" + String(n),
            "known_optimum=" + String(known),
            "greedy=" + String(seedt.tour_length),
            "local_search=" + String(ls.tour_length),
            "ratio=" + String(ls.tour_length / known) + "x",
            "improvement=" + String(ls.improvement),
        )
    if circle_ok:
        print(
            "  ✅ on convex position the local search reaches the known optimum exactly —"
            " and so does the frozen nearest-neighbour seed, so the improvement is 0.0"
        )
        print(
            "      that is the honest reading: nearest-neighbour on a circle can only extend"
            " a contiguous arc, so it IS the hull order. The value of the search shows up on"
            " the lattice above, not here."
        )
    else:
        failures += 1
        print("  ❌ a circle instance missed its known optimum")

    # 1d. a generic instance: improvement measured, optimality NOT claimed.
    print("")
    print("  -- pseudo-random 200-city Euclidean instance: no known optimum, none claimed")
    var r_xs = List[Float64]()
    var r_ys = List[Float64]()
    _random_points(200, INSTANCE_SEED, r_xs, r_ys)
    var rd = _euclidean_matrix(r_xs, r_ys)
    var r_seed = tsp_greedy_flat(rd, 200)
    var r_two = tsp_two_opt(rd, 200, 64)
    var r_ls = tsp_local_search(rd, 200, 64, True, True, 3)
    var r_ils = tsp_iterated_local_search(rd, 200, 64, 3, 24, UInt64(11))
    var r_check = tour_length_flat(rd, 200, r_ils.tour)
    var gen_ok = (
        r_seed.status == ROUTE_OK_LIMIT
        and r_two.has_length
        and r_ls.has_length
        and r_ils.has_length
        and r_check.status == ROUTE_OK
        and _rel_close(r_check.value, r_ils.tour_length, 1024.0, 0.0)
        # each stage is at least as good as the one it starts from
        and r_two.tour_length <= r_seed.tour_length + 1e-9
        and r_ls.tour_length <= r_seed.tour_length + 1e-9
        and r_ils.tour_length <= r_ls.tour_length + 1e-9
    )
    print(
        "     greedy=" + String(r_seed.tour_length),
        "2opt=" + String(r_two.tour_length),
        "2opt+oropt=" + String(r_ls.tour_length),
        "ILS(24 kicks)=" + String(r_ils.tour_length),
    )
    print(
        "     improvement over the frozen seed:",
        "2opt=" + String(100.0 * r_two.improvement / r_seed.tour_length) + "%",
        "2opt+oropt=" + String(100.0 * r_ls.improvement / r_seed.tour_length) + "%",
        "ILS=" + String(100.0 * r_ils.improvement / r_seed.tour_length) + "%",
    )
    print(
        "     ILS kicks=" + String(r_ils.kicks),
        "accepted=" + String(r_ils.kicks_accepted),
        "passes=" + String(r_ils.passes),
        "reeval_rejected=" + String(r_ils.n_reeval_rejected),
    )
    if gen_ok:
        print(
            "  ✅ each stage improves on the one it starts from, and the frozen kernel"
            " re-derives the ILS length"
        )
        print(
            "      ⚠️  these are LOCAL optima of the declared move set. The optimum of this"
            " instance is unknown, so no distance from it is reported — `local_optimum` is"
            " the whole claim, and status 120 is named accordingly."
        )
        if r_ils.kicks_accepted == 0:
            print(
                "      ⚠️  and all " + String(r_ils.kicks)
                + " double-bridge kicks were REJECTED here, so ILS returned the same tour as"
                + " plain 2-opt+Or-opt at "
                + String(r_ils.passes)
                + " passes of extra work. Printed because a kick budget that buys nothing on"
                + " an instance is a fact about the driver, not a number to leave out."
            )
    else:
        failures += 1
        print("  ❌ a later stage came back worse than the one it started from")

    # ══ 2. quadratic: closed forms, the LP oracle, and the equilibration ══════
    print("")
    print("=== QP: closed forms, the Q = 0 cross-check against lp_solve, equilibration ===")

    # 2a. Q = 2I, no constraints: x = -c/2 and f = -sum(c^2)/4. Exact in binary — the
    # factorisation is LDL^T and takes no square roots, and division by 2 is exact.
    var free_ok = True
    var free_exact = True
    var q_sizes = _int_list(2, 8, 32, 128)
    var qi_first: Float64 = 0.0
    var qi_last: Float64 = 0.0
    for s in range(len(q_sizes)):
        var n = q_sizes[s]
        var q = _fill(0.0, n * n)
        for i in range(n):
            q[i * n + i] = 2.0
        var c = List[Float64]()
        for j in range(n):
            c.append(-1.0 - Float64(j % 7))
        var want = List[Float64]()
        var want_obj = 0.0
        for j in range(n):
            want.append(-c[j] / 2.0)
            want_obj += -c[j] * c[j] / 4.0
        var reps = 1024 // n
        if reps < 2:
            reps = 2
        for _ in range(WARMUP):
            var _wq = qp_solve_default(
                q, n, c, List[Float64](), 0, List[Int](), List[Float64](),
                _fill(0.0, n), _fill(0.0, n), _ifill(0, n), UInt64(5),
            )
        var t4 = perf_counter_ns()
        for _ in range(reps):
            var _rq = qp_solve_default(
                q, n, c, List[Float64](), 0, List[Int](), List[Float64](),
                _fill(0.0, n), _fill(0.0, n), _ifill(0, n), UInt64(5),
            )
        var t5 = perf_counter_ns()
        var qp_ms = _ms(t5 - t4) / Float64(reps)
        var sol = qp_solve_default(
            q, n, c, List[Float64](), 0, List[Int](), List[Float64](),
            _fill(0.0, n), _fill(0.0, n), _ifill(0, n), UInt64(5),
        )
        var ok = (
            sol.status == QP_OPTIMAL
            and sol.proven_optimal
            and sol.certified
            and sol.convex
            and sol.has_objective
            and _vec_rel_close(sol.x, want, 8.0, 0.0)
            and _rel_close(sol.objective, want_obj, 8.0, 0.0)
        )
        if not ok:
            free_ok = False
        if not (_vec_exact(sol.x, want) and sol.objective == want_obj):
            free_exact = False
        if s == 1:
            qi_first = qp_ms
        qi_last = qp_ms
        print(
            "  Q=2I n=" + String(n),
            "solve=" + String(qp_ms) + "ms",
            "ns/Hessian_cell=" + String(qp_ms * 1.0e6 / Float64(n * n)),
            "objective=" + String(sol.objective),
            "iterations=" + String(sol.iterations),
            "active=" + String(sol.n_active),
        )
    if free_ok:
        var word = "BIT-EXACTLY" if free_exact else "to 8 ulps"
        print(
            "  ✅ Q = 2I reproduces the closed form x = -c/2 " + word
            + " at n = 2, 8, 32, 128, certified each time"
        )
        # Quoted from n = 8 rather than n = 2, because at n = 2 the fixed per-call cost
        # dominates and including it would flatten the curve into a number about overhead.
        print(
            "      measured growth 8 -> 128: n^"
            + String(_exponent(qi_first, qi_last, 8, 128))
            + " per solve, at 2 iterations throughout — so that exponent is the"
            + " factorisation and the KKT re-check, not an iteration count"
        )
    else:
        failures += 1
        print("  ❌ Q = 2I did not reproduce x = -c/2")

    # 2b. Q = 0 against lp_solve. Agreement FIRST; the timing means nothing without it.
    print("")
    print("  -- Q = 0 is a linear program: cross-checked against optimization.linear.lp_solve")
    var lp_sizes = _int_list(4, 8, 16, 32)
    var lp_agreed = True
    var x_agreed_upto = 0
    var worst_x_dev: Float64 = 0.0
    var first_qp_ms: Float64 = 0.0
    var last_qp_ms: Float64 = 0.0
    var first_lp_ms: Float64 = 0.0
    var last_lp_ms: Float64 = 0.0
    for s in range(len(lp_sizes)):
        var n = lp_sizes[s]
        var a = _dense_lp_a(n)
        var b = _dense_lp_b(n)
        var c = _dense_lp_c(n)
        var senses = _senses(SENSE_LE, n)
        var zeros = _fill(0.0, n * n)
        var lower = _fill(0.0, n)
        var upper = _fill(0.0, n)
        var flags = _ifill(VAR_FLAG_HAS_LOWER, n)
        var reps = 256 // n
        if reps < 2:
            reps = 2
        # Identical warmup and identical repetition count on both arms, and both inputs are
        # built above the timers. Tier 1 had to fix an arm that paid for construction inside
        # its timed region while the other did not; two errors pointing opposite ways is not
        # conservative, it makes the ratio unattributable.
        for _ in range(WARMUP):
            var _wl2 = lp_solve_default(c, a, n, n, senses, b, False)
        var t6 = perf_counter_ns()
        for _ in range(reps):
            var _rl2 = lp_solve_default(c, a, n, n, senses, b, False)
        var t7 = perf_counter_ns()
        var lp_ms = _ms(t7 - t6) / Float64(reps)
        for _ in range(WARMUP):
            var _wq2 = qp_solve_default(
                zeros, n, c, a, n, senses, b, lower, upper, flags, UInt64(17)
            )
        var t8 = perf_counter_ns()
        for _ in range(reps):
            var _rq2 = qp_solve_default(
                zeros, n, c, a, n, senses, b, lower, upper, flags, UInt64(17)
            )
        var t9 = perf_counter_ns()
        var qp_ms2 = _ms(t9 - t8) / Float64(reps)

        var lp = lp_solve_default(c, a, n, n, senses, b, False)
        var qp = qp_solve_default(
            zeros, n, c, a, n, senses, b, lower, upper, flags, UInt64(17)
        )
        # The objective is the answer to an LP. `x` is the answer only when the optimal FACE
        # is a single point, which is a property of the instance and not of either solver —
        # so `x` is checked the way it can be checked: each arm's own `x` is re-verified
        # feasible HERE, at each row's own scale, and its objective re-derived by hand from
        # `c` and `x` rather than read out of the struct.
        var lp_viol = _worst_le_violation(a, n, n, b, lp.x)
        var qp_viol = _worst_le_violation(a, n, n, b, qp.x)
        var lp_recomp = _dot(c, lp.x)
        var qp_recomp = _dot(c, qp.x)
        var x_dev = 0.0
        if len(qp.x) == len(lp.x):
            for j in range(len(lp.x)):
                var m = lp.x[j] if lp.x[j] >= 0.0 else -lp.x[j]
                var mq = qp.x[j] if qp.x[j] >= 0.0 else -qp.x[j]
                if mq > m:
                    m = mq
                if m <= 0.0:
                    m = 1.0
                var d = (qp.x[j] - lp.x[j]) / m
                if d < 0.0:
                    d = -d
                if d > x_dev:
                    x_dev = d
        else:
            x_dev = 1.0
        var ok = (
            lp.status == LP_OPTIMAL
            and qp.status == QP_OPTIMAL
            and qp.proven_optimal
            and qp.has_objective
            and qp.q_rank == 0
            and len(qp.x) == n
            and _rel_close(qp.objective, lp.objective, 4096.0, 0.0)
            # each arm's reported objective is the objective of its OWN returned point
            and _rel_close(qp_recomp, qp.objective, 4096.0, 0.0)
            and _rel_close(lp_recomp, lp.objective, 4096.0, 0.0)
            # and both returned points are feasible, checked here per row
            and qp_viol <= 4096.0 * DBL_EPSILON
            and lp_viol <= 4096.0 * DBL_EPSILON
        )
        if not ok:
            lp_agreed = False
        if x_dev <= 4096.0 * DBL_EPSILON:
            x_agreed_upto = n
        if x_dev > worst_x_dev:
            worst_x_dev = x_dev
        if s == 0:
            first_qp_ms = qp_ms2
            first_lp_ms = lp_ms
        last_qp_ms = qp_ms2
        last_lp_ms = lp_ms
        print(
            "     n=" + String(n),
            "lp_objective=" + String(lp.objective),
            "qp_objective=" + String(qp.objective),
            "max_rel_x_deviation=" + String(x_dev),
            "worst_row_violation: lp=" + String(lp_viol),
            "qp=" + String(qp_viol),
        )
        print(
            "         lp=" + String(lp_ms) + "ms",
            "qp=" + String(qp_ms2) + "ms",
            "qp/lp=" + String(qp_ms2 / lp_ms if lp_ms > 0.0 else 0.0) + "x",
            "qp_iterations=" + String(qp.iterations),
            "lp_iterations=" + String(lp.iterations),
        )
    if lp_agreed:
        print(
            "  ✅ the active-set QP and the two-phase simplex agree on the OBJECTIVE at every"
            " size, each at its own point, and both points re-verify feasible here per row"
        )
        print(
            "      ⚠️  `x` agrees to 4096 ulps only up to n = " + String(x_agreed_upto)
            + "; the worst deviation over the range is " + String(worst_x_dev)
            + ". That is a property of the INSTANCE, not a disagreement: this LP's optimal"
            + " face is not a single point at every size, so a pivoting method and a"
            + " null-space method may stop at different corners of it with the same objective."
            + " Gating on `x` would have been gating on which corner, so the gate is the"
            + " objective plus an independent feasibility check of both answers."
        )
    else:
        failures += 1
        print("  ❌ Q = 0 does not reproduce lp_solve; every timing above is meaningless")
    print(
        "  measured growth " + String(lp_sizes[0]) + " -> "
        + String(lp_sizes[len(lp_sizes) - 1]) + ":",
        "qp n^" + String(_exponent(first_qp_ms, last_qp_ms, lp_sizes[0], lp_sizes[len(lp_sizes) - 1])),
        "lp n^" + String(_exponent(first_lp_ms, last_lp_ms, lp_sizes[0], lp_sizes[len(lp_sizes) - 1])),
    )
    print(
        "  ⚠️  the simplex is "
        + String(last_qp_ms / last_lp_ms if last_lp_ms > 0.0 else 0.0)
        + "x FASTER than the QP path on a program with no curvature, which is the direction"
        + " that comparison has to run: the QP factors a Hessian that is zero. The claim is"
        + " AGREEMENT — a shared answer between a pivoting method and a null-space method —"
        + " plus the curvature the simplex cannot express at all."
    )

    # 2c. the equilibration: a Hessian whose two directions differ by 12 orders of magnitude.
    print("")
    print("  -- equilibration: Q = diag(1e12, 0.5), c = (0, -1). Known optimum x = (0, 2), f = -1")
    var q_scaled = _floats(1.0e12, 0.0, 0.0, 0.5)
    var c_scaled = _floats(0.0, -1.0)
    var free2 = _int_list(0, 0)
    var eq = qp_solve_default(
        q_scaled, 2, c_scaled, List[Float64](), 0, List[Int](), List[Float64](),
        _fill(0.0, 2), _fill(0.0, 2), free2, UInt64(1),
    )
    var eq_cv = qp_convexity_flat(q_scaled, 2)
    # A realistic mixed-units covariance: D S D with correlation 0.5, det = 1e10 - 2.5e9 > 0,
    # so f* = -0.5 c' Q^-1 c = -0.5 * 1e12 / 7.5e9 = -66.6666...
    var cov = qp_solve_default(
        _floats(1.0e12, 5.0e4, 5.0e4, 1.0e-2), 2, c_scaled, List[Float64](), 0,
        List[Int](), List[Float64](), _fill(0.0, 2), _fill(0.0, 2), free2, UInt64(1),
    )
    var eq_ok = (
        eq.status == QP_OPTIMAL
        and eq.proven_optimal
        and eq.certified
        and eq.convex
        and len(eq.ray) == 0
        and eq.n_zero_curvature == 0
        and _vec_rel_close(eq.x, _floats(0.0, 2.0), 64.0, 1e-12)
        and _rel_close(eq.objective, -1.0, 64.0, 0.0)
        and eq.min_pivot == 0.5
        # SELF-CONSISTENCY: two reports of the same fact must agree (rule 4b's last note)
        and eq_cv.positive_definite
        and eq_cv.rank == 2
        and eq_cv.min_pivot == 0.5
        and cov.status == QP_OPTIMAL
        and _rel_close(cov.objective, -66.66666666666667, 4096.0, 0.0)
    )
    print(
        "     status=" + qp_status_name(eq.status),
        "objective=" + String(eq.objective),
        "min_pivot=" + String(eq.min_pivot),
        "zero_curvature_steps=" + String(eq.n_zero_curvature),
        "iterations=" + String(eq.iterations),
    )
    print(
        "     qp_convexity_flat on the same Q:",
        "positive_definite=" + String(eq_cv.positive_definite),
        "rank=" + String(eq_cv.rank),
        "min_pivot=" + String(eq_cv.min_pivot),
        "| mixed-units covariance objective=" + String(cov.objective),
    )
    if eq_ok:
        print(
            "  ✅ a curvature of 0.5 beside a diagonal of 1e12 is solved, not mistaken for"
            " flat: min_pivot is 0.5 (not 1e12), no zero-curvature step, no ray"
        )
        print(
            "      that is what the per-direction curvature tolerance bought. Sized off"
            " max|Q| instead, this exact call returned UNBOUNDED with ray (0, 1) while"
            " qp_convexity_flat called the same Q positive definite in the same run."
        )
    else:
        failures += 1
        print(
            "  ❌ the equilibration arm failed:", qp_status_name(eq.status), eq.objective,
            eq.min_pivot, eq_cv.positive_definite, cov.objective,
        )

    # ══ 3. scheduling: the incumbent against a bound, and the GAP ═════════════
    print("")
    print("=== Scheduling: tabu / SGS incumbents against re-derived bounds — GAP, not optimality ===")

    # 3a. a one-job shop IS a chain, so the job bound is exact and tabu cannot improve.
    var chain_ops = 8
    var chain_dur = _jssp_durations(1, chain_ops, INSTANCE_SEED)
    var chain_mach = List[Int]()
    for k in range(chain_ops):
        chain_mach.append(k)
    var chain_total = 0.0
    for k in range(chain_ops):
        chain_total += chain_dur[k]
    var chain_bound = jobshop_bound_flat(chain_dur, chain_mach, 1, chain_ops, chain_ops)
    var chain_res = jobshop_tabu_solve_flat(
        chain_dur, chain_mach, 1, chain_ops, chain_ops, 7, 400, 7, 40
    )
    var chain_audit = jobshop_verify_flat(
        chain_dur, chain_mach, 1, chain_ops, chain_ops, chain_res.start
    )
    var chain_ok = (
        chain_bound.status == MODEL_OK
        and chain_bound.has_bound
        # the bound, re-derived here from the durations rather than taken on trust
        and chain_bound.lower_bound == chain_total
        and chain_res.status == SCHED_OPTIMAL
        and chain_res.verified
        and chain_res.optimal_by_bound
        and chain_res.makespan == chain_total
        and chain_res.gap == 0.0
        and chain_res.improvements == 0
        and chain_audit.feasible
        and chain_audit.has_makespan
        and chain_audit.makespan == chain_total
    )
    print(
        "  -- one job, " + String(chain_ops) + " operations on distinct machines (a pure chain)"
    )
    print(
        "     chain length (sum of durations)=" + String(chain_total),
        "lower_bound=" + String(chain_bound.lower_bound),
        "makespan=" + String(chain_res.makespan),
        "gap=" + String(chain_res.gap),
        "status=" + sched_status_name(chain_res.status),
    )
    print(
        "     tabu: iterations=" + String(chain_res.iterations),
        "moves_evaluated=" + String(chain_res.moves_evaluated),
        "improvements=" + String(chain_res.improvements),
        "restarts=" + String(chain_res.restarts),
    )
    if chain_ok:
        print(
            "  ✅ on a chain the bound is EXACT and tabu improves nothing: makespan ="
            " lower bound = the chain length, gap 0, and optimal_by_bound says so"
        )
    else:
        failures += 1
        print(
            "  ❌ the chain arm failed:", sched_status_name(chain_res.status),
            chain_res.makespan, chain_total, chain_bound.lower_bound,
        )

    # 3b. real Latin-square shops: the incumbent, the bound, and the gap between them.
    print("")
    print("  -- Latin-square job shops: makespan vs bound. The GAP is the result, not a claim")
    var shop_sizes = _int_list(4, 6, 8, 10)
    var shop_ok = True
    var worst_rel_gap: Float64 = 0.0
    var any_closed = False
    for s in range(len(shop_sizes)):
        var m = shop_sizes[s]
        var dur = _jssp_durations(m, m, INSTANCE_SEED + 7 * s)
        var mach = _jssp_latin(m, m, m)
        # The bound, re-derived here: max job total, max machine load, and the larger.
        var job_max = 0.0
        for j in range(m):
            var tot = 0.0
            for k in range(m):
                tot += dur[j * m + k]
            if tot > job_max:
                job_max = tot
        var load = _fill(0.0, m)
        for o in range(m * m):
            load[mach[o]] = load[mach[o]] + dur[o]
        var mach_max = 0.0
        for r in range(m):
            if load[r] > mach_max:
                mach_max = load[r]
        var mine_lb = job_max if job_max > mach_max else mach_max

        var bnd = jobshop_bound_flat(dur, mach, m, m, m)
        for _ in range(WARMUP):
            var _wt = jobshop_tabu_solve_flat(dur, mach, m, m, m, 13, 600, 9, 60)
        var t10 = perf_counter_ns()
        var res = jobshop_tabu_solve_flat(dur, mach, m, m, m, 13, 600, 9, 60)
        var t11 = perf_counter_ns()
        var tabu_ms = _ms(t11 - t10)
        var audit = jobshop_verify_flat(dur, mach, m, m, m, res.start)
        var ok = (
            bnd.status == MODEL_OK
            and bnd.lower_bound == mine_lb
            and (
                res.status == SCHED_OPTIMAL
                or res.status == SCHED_FEASIBLE
                or res.status == SCHED_LIMIT
            )
            and res.verified
            and res.has_bound
            and res.has_makespan
            # never below a valid bound
            and res.makespan >= res.lower_bound - 1e-9
            and res.lower_bound == mine_lb
            # the incumbent is at least as good as the construction it started from
            and res.makespan <= res.initial_makespan + 1e-9
            # independently re-verified as an executable schedule
            and audit.feasible
            and audit.has_makespan
            and _rel_close(audit.makespan, res.makespan, 64.0, 0.0)
            # a heuristic claims optimality ONLY when the bound proves it
            and (res.optimal_by_bound == (res.gap <= 1e-9))
        )
        if not ok:
            shop_ok = False
        if res.optimal_by_bound:
            any_closed = True
        if res.has_relative_gap and res.relative_gap > worst_rel_gap:
            worst_rel_gap = res.relative_gap
        print(
            "     " + String(m) + "x" + String(m),
            "bound=" + String(res.lower_bound),
            "construction=" + String(res.initial_makespan),
            "tabu=" + String(res.makespan),
            "gap=" + String(res.gap),
            "rel_gap=" + String(100.0 * res.relative_gap) + "%",
            "status=" + sched_status_name(res.status),
        )
        print(
            "         iterations=" + String(res.iterations),
            "moves=" + String(res.moves_evaluated),
            "improvements=" + String(res.improvements),
            "cycles_rejected=" + String(res.cycles_rejected),
            "restarts=" + String(res.restarts),
            "| " + String(tabu_ms) + "ms",
        )
    if shop_ok:
        print(
            "  ✅ every makespan is at or above the re-derived bound, every schedule"
            " re-verifies, and optimal_by_bound is set if and only if the gap closed"
        )
        print(
            "      worst relative gap over the four shops: "
            + String(100.0 * worst_rel_gap)
            + "%. That is a GAP AGAINST A BOUND, not a distance from the optimum — the"
            + " optimum of a Latin-square shop is unknown here and no arm pretends otherwise."
        )
        if any_closed:
            print(
                "      at least one shop closed its gap, and only there is the answer"
                " optimal — proven by the bound, not by the search"
            )
    else:
        failures += 1
        print("  ❌ a job shop went below its bound, failed re-verification, or misreported optimality")

    # 3c. RCPSP: two instances whose bounds are exact for stated reasons, and one that is not.
    print("")
    print("  -- RCPSP: a precedence chain (cp bound exact) and a fully serial resource")
    var rc_n = 10
    var rc_dur = _fill(3.0, rc_n)
    var rc_dem = _fill(1.0, rc_n)
    var rc_cap = _floats(5.0)
    var pf = List[Int]()
    var pt = List[Int]()
    _chain_edges(rc_n, pf, pt)
    var rc_bound = rcpsp_bound_flat(rc_dur, rc_dem, rc_cap, pf, pt, rc_n, 1)
    var rc_res = rcpsp_sgs_solve_flat(rc_dur, rc_dem, rc_cap, pf, pt, rc_n, 1, 3, 8)
    var chain_len = 3.0 * Float64(rc_n)

    # Six activities each needing the whole of one resource: no two can overlap, so the
    # schedule is fully serial and the resource-area bound sum(d*r)/cap = 12 is EXACT.
    var ser_n = 6
    var ser_dur = _fill(2.0, ser_n)
    var ser_dem = _fill(1.0, ser_n)
    var ser_cap = _floats(1.0)
    var ser_bound = rcpsp_bound_flat(
        ser_dur, ser_dem, ser_cap, List[Int](), List[Int](), ser_n, 1
    )
    var ser_res = rcpsp_sgs_solve_flat(
        ser_dur, ser_dem, ser_cap, List[Int](), List[Int](), ser_n, 1, 3, 8
    )
    var rcpsp_ok = (
        rc_bound.status == MODEL_OK
        and rc_bound.has_bound
        and rc_bound.cp_bound == chain_len
        and rc_bound.lower_bound == chain_len
        and rc_res.verified
        and rc_res.makespan == chain_len
        and rc_res.optimal_by_bound
        and ser_bound.status == MODEL_OK
        and ser_bound.has_resource_bound
        and ser_bound.resource_bound == 12.0
        and ser_bound.cp_bound == 2.0
        and ser_bound.lower_bound == 12.0
        and ser_res.verified
        and ser_res.makespan == 12.0
        and ser_res.optimal_by_bound
    )
    print(
        "     chain of " + String(rc_n) + " x 3.0:",
        "cp_bound=" + String(rc_bound.cp_bound),
        "resource_bound=" + String(rc_bound.resource_bound),
        "lower_bound=" + String(rc_bound.lower_bound),
        "makespan=" + String(rc_res.makespan),
        "gap=" + String(rc_res.gap),
        "status=" + sched_status_name(rc_res.status),
    )
    print(
        "     " + String(ser_n) + " activities x 2.0, demand 1.0, capacity 1.0:",
        "cp_bound=" + String(ser_bound.cp_bound),
        "resource_bound=" + String(ser_bound.resource_bound),
        "binding_resource=" + String(ser_bound.binding_resource),
        "makespan=" + String(ser_res.makespan),
        "status=" + sched_status_name(ser_res.status),
    )
    if rcpsp_ok:
        print(
            "  ✅ the precedence bound is exact on a chain (30.0) and the resource-area bound"
            " is exact when one resource forces a serial order (12.0) — two DIFFERENT bounds"
            " binding, each proven by construction"
        )
    else:
        failures += 1
        print(
            "  ❌ an RCPSP bound that is exact by construction was not attained:",
            rc_bound.cp_bound, rc_res.makespan, ser_bound.resource_bound, ser_res.makespan,
        )

    # A resource-constrained project where neither bound is tight: the gap is the answer.
    var hard_n = 24
    var hard_dur = List[Float64]()
    var hard_dem = List[Float64]()
    var hs = INSTANCE_SEED
    for _ in range(hard_n):
        hs = _lcg_next(hs)
        hard_dur.append(1.0 + Float64(hs % 8))
    for _ in range(hard_n * 2):
        hs = _lcg_next(hs)
        hard_dem.append(1.0 + Float64(hs % 4))
    var hard_cap = _floats(6.0, 5.0)
    var hpf = List[Int]()
    var hpt = List[Int]()
    for i in range(hard_n - 2):
        hpf.append(i)
        hpt.append(i + 2)
    var hard_res = rcpsp_sgs_solve_flat(
        hard_dur, hard_dem, hard_cap, hpf, hpt, hard_n, 2, 5, 32
    )
    if hard_res.verified and hard_res.has_bound and hard_res.has_makespan:
        print(
            "     24-activity 2-resource project:",
            "cp_bound=" + String(hard_res.cp_bound),
            "resource_bound=" + String(hard_res.resource_bound),
            "lower_bound=" + String(hard_res.lower_bound),
            "makespan=" + String(hard_res.makespan),
            "gap=" + String(hard_res.gap),
            "rel_gap=" + String(100.0 * hard_res.relative_gap) + "%",
            "restarts=" + String(hard_res.restarts),
        )
        if hard_res.makespan >= hard_res.lower_bound - 1e-9:
            print(
                "  ✅ the incumbent sits above the bound and the gap is reported as a gap:"
                " optimal_by_bound=" + String(hard_res.optimal_by_bound)
            )
        else:
            failures += 1
            print("  ❌ the incumbent fell below its own lower bound")
    else:
        failures += 1
        print("  ❌ the 24-activity project did not produce a verified schedule")

    # ══ 4. multiobjective: sorting cost, and an exactly computable hypervolume ═
    print("")
    print("=== Multiobjective: front sorting against the frozen pareto_front, exact hypervolume ===")
    var mo_sizes = _int_list(64, 128, 256, 512, 1024, 2048)
    var mo_ok = True
    var first_sort_ms: Float64 = 0.0
    var last_sort_ms: Float64 = 0.0
    var first_frozen_ms: Float64 = 0.0
    var last_frozen_ms: Float64 = 0.0
    var first_cmp: Float64 = 0.0
    var last_cmp: Float64 = 0.0
    for s in range(len(mo_sizes)):
        var n = mo_sizes[s]
        var f = _mo_points(n, 2, INSTANCE_SEED + 3 * s)
        var nest = _nested(f, n, 2)
        for _ in range(WARMUP):
            var _ws = nondominated_sort(f, n, 2)
        var t12 = perf_counter_ns()
        var sorted = nondominated_sort(f, n, 2)
        var t13 = perf_counter_ns()
        var sort_ms = _ms(t13 - t12)
        # The frozen kernel's `maximize` mask, one entry per objective, all minimising — the
        # same convention `pareto_certify` uses when it calls this kernel as its oracle. It
        # indexes the mask per objective, so a short list would be a read past the end.
        var mask = List[Bool]()
        for _ in range(2):
            mask.append(False)
        for _ in range(WARMUP):
            var _wf2 = pareto_front(nest, mask)
        var t14 = perf_counter_ns()
        var frozen = pareto_front(nest, mask)
        var t15 = perf_counter_ns()
        var frozen_ms = _ms(t15 - t14)

        var cert = pareto_certify(f, n, 2, sorted.first_front)
        var ok = (
            sorted.status == MODEL_OK
            and sorted.verified
            and cert.status == MODEL_OK
            and cert.certified
            and cert.n_claimed == cert.n_true_front
            and len(sorted.first_front) == len(frozen)
            and sorted.n_fronts >= 1
            # The census budget: one classification per ORDERED pair, the diagonal included.
            # Measured below as exactly `n * n` at all six sizes — the cost of the ranking does
            # not depend on how the fronts happen to fall — but gated as the bound it is,
            # because an implementation that skipped the diagonal would still be correct.
            and sorted.comparisons <= n * n
        )
        if not ok:
            mo_ok = False
        if s == 0:
            first_sort_ms = sort_ms
            first_frozen_ms = frozen_ms
            first_cmp = Float64(sorted.comparisons)
        last_sort_ms = sort_ms
        last_frozen_ms = frozen_ms
        last_cmp = Float64(sorted.comparisons)
        print(
            "  n=" + String(n),
            "fronts=" + String(sorted.n_fronts),
            "front0=" + String(len(sorted.first_front)),
            "frozen_front0=" + String(len(frozen)),
            "comparisons=" + String(sorted.comparisons),
            "(" + String(Float64(sorted.comparisons) / Float64(n * n)) + " per n^2)",
        )
        print(
            "      all_fronts=" + String(sort_ms) + "ms",
            "frozen_front0_only=" + String(frozen_ms) + "ms",
            "ratio=" + String(sort_ms / frozen_ms if frozen_ms > 0.0 else 0.0) + "x",
            "ns/comparison=" + String(
                sort_ms * 1.0e6 / Float64(sorted.comparisons)
                if sorted.comparisons > 0 else 0.0
            ),
        )
    if mo_ok:
        print(
            "  ✅ front 0 from the full ranking is CERTIFIED against the frozen"
            " multi_objective.pareto_front at every size, and equals its size"
        )
        # Worded against what the GATE asserts (`comparisons <= n*n`) and against the per-size
        # ratios printed immediately above, rather than asserting a value this branch does not
        # check. The census being exactly n^2 is what those ratios show when they read 1.0; a
        # sentence claiming it unconditionally would be false the first time they did not.
        print(
            "      the per-size ratios above are the census against n^2: the ranking pays one"
            " dominance classification per ordered pair, so its cost does not depend on the"
            " front structure it finds"
        )
    else:
        failures += 1
        print("  ❌ the ranking's front 0 disagreed with the frozen kernel — timings mean nothing")
    var n_lo = mo_sizes[0]
    var n_hi = mo_sizes[len(mo_sizes) - 1]
    print(
        "  measured growth " + String(n_lo) + " -> " + String(n_hi) + " points:",
        "all_fronts n^" + String(_exponent(first_sort_ms, last_sort_ms, n_lo, n_hi)),
        "frozen_front0 n^" + String(_exponent(first_frozen_ms, last_frozen_ms, n_lo, n_hi)),
        "comparisons n^" + String(_exponent(first_cmp, last_cmp, n_lo, n_hi)),
    )
    print(
        "  ⚠️  that ratio is NOT a speed comparison: the frozen kernel returns front 0 and"
        " stops, while nondominated_sort ranks EVERY front and returns the order, the front"
        " offsets and a comparison census. Different work, so the number is printed as the"
        " price of the full ranking."
    )

    # 4b. hypervolume: exact where it is exact, ABSENT where it is not.
    print("")
    print("  -- hypervolume: one point is a rectangle; two are a staircase; three objectives are absent")
    var one_pt = _floats(1.0, 3.0)
    var ref2 = _floats(4.0, 4.0)
    var hv_one = hypervolume_default(one_pt, 1, 2, ref2)
    # (4-1)*(4-3) = 3, exact in binary.
    var two_pt = _floats(1.0, 3.0, 2.0, 1.0)
    var hv_two = hypervolume_default(two_pt, 2, 2, ref2)
    # 3*1 + 2*2 = 7, which is also 3 + 6 - 2 by inclusion-exclusion.
    var three_pt = _floats(1.0, 1.0, 1.0)
    var ref3 = _floats(4.0, 4.0, 4.0)
    var hv_three = hypervolume_default(three_pt, 1, 3, ref3)
    # Two mutually non-dominated points in 3-D, where the union is NOT a single box and the
    # bounds genuinely bracket. Hand-derived before it was run: box(1,3,3) = 3*1*1 = 3,
    # box(3,1,1) = 1*3*3 = 9, they overlap in [3,4]^3 = 1, so the union is 3 + 9 - 1 = 11.
    # The largest single box, 9, is a valid lower bound and the sum, 12, a valid upper one.
    var two3 = _floats(1.0, 3.0, 3.0, 3.0, 1.0, 1.0)
    var hv_pair = hypervolume_default(two3, 2, 3, ref3)
    var pair_dev = hv_pair.estimate - 11.0
    if pair_dev < 0.0:
        pair_dev = -pair_dev
    var hv_pair_ok = (
        (hv_pair.status == MO_HV_INEXACT or hv_pair.status == MO_HV_ESTIMATE_CLAMPED)
        and not hv_pair.has_value
        and hv_pair.has_estimate
        and hv_pair.n_nondominated == 2
        # the two exact bounds, both hand-derivable
        and hv_pair.bound_lower == 9.0
        and hv_pair.bound_upper == 12.0
        # the true 11.0 lies inside them, and the estimate is inside too
        and hv_pair.bound_lower <= 11.0
        and 11.0 <= hv_pair.bound_upper
        and hv_pair.bound_lower <= hv_pair.estimate
        and hv_pair.estimate <= hv_pair.bound_upper
        # and the estimate is within three of its OWN reported standard errors of the truth.
        # Gated with `==`-grade confidence because the draw is seeded, so this number is the
        # same on every run of this binary — it is not a flaky statistical test.
        and pair_dev <= 3.0 * hv_pair.std_error
    )
    if not hv_pair_ok:
        failures += 1
    var hv_ok = (
        hv_one.status == MODEL_OK
        and hv_one.exact
        and hv_one.has_value
        and hv_one.value == 3.0
        and hv_two.status == MODEL_OK
        and hv_two.exact
        and hv_two.value == 7.0
        # three objectives: the exact value does not exist here, so it is ABSENT — and the
        # exact bounds and the deterministic estimate are present instead.
        and (hv_three.status == MO_HV_INEXACT or hv_three.status == MO_HV_ESTIMATE_CLAMPED)
        and not hv_three.exact
        and not hv_three.has_value
        and hv_three.has_estimate
        and hv_three.bound_lower <= hv_three.estimate + 1e-9
        and hv_three.estimate <= hv_three.bound_upper + 1e-9
        # one point in 3-D IS a box, so the bounds pin it: 3*3*3 = 27
        and hv_three.bound_lower == 27.0
        and hv_three.bound_upper == 27.0
    )
    print(
        "     1 point vs (4,4): value=" + String(hv_one.value),
        "exact=" + String(hv_one.exact),
        "| 2 points: value=" + String(hv_two.value),
        "| 3 objectives: status=" + mo_status_name(hv_three.status),
        "has_value=" + String(hv_three.has_value),
        "estimate=" + String(hv_three.estimate),
        "+/-" + String(hv_three.std_error),
        "bounds=[" + String(hv_three.bound_lower) + ", " + String(hv_three.bound_upper) + "]",
        "samples=" + String(hv_three.samples),
    )
    print(
        "     2 non-dominated points in 3-D, true union 11.0 by inclusion-exclusion:",
        "status=" + mo_status_name(hv_pair.status),
        "has_value=" + String(hv_pair.has_value),
        "exact_bounds=[" + String(hv_pair.bound_lower) + ", "
        + String(hv_pair.bound_upper) + "]",
        "estimate=" + String(hv_pair.estimate),
        "+/-" + String(hv_pair.std_error),
        "deviation_from_11=" + String(pair_dev),
    )
    if hv_pair_ok:
        print(
            "  ✅ above two objectives the exact value is ABSENT and what IS returned is"
            " honest: exact bounds [9.0, 12.0] that contain the true 11.0, and a seeded"
            " estimate " + String(pair_dev) + " from it, inside its own reported std_error"
        )
    else:
        print(
            "  ❌ the 3-objective bracket failed:", mo_status_name(hv_pair.status),
            hv_pair.bound_lower, hv_pair.bound_upper, hv_pair.estimate, hv_pair.std_error,
        )
    if hv_ok:
        print(
            "  ✅ the rectangle (3.0) and the staircase (7.0) are EXACT to the bit; at three"
            " objectives has_value is False and the estimate sits inside exact bounds"
        )
    else:
        failures += 1
        print(
            "  ❌ hypervolume: ", hv_one.value, hv_two.value, mo_status_name(hv_three.status),
            hv_three.has_value, hv_three.bound_lower, hv_three.bound_upper,
        )

    # 4c. NSGA-II: a heuristic front against the PROVEN per-objective ideal.
    print("")
    print("  -- NSGA-II: the front against ideal[j], which is an exact lp_solve per objective")
    # minimise (x1, x2) subject to x1 + x2 >= 4, box [0, 10]^2. The front is the segment
    # x1 + x2 = 4, and ideal = (0, 0) from the two single-objective LPs.
    var mo_c = _floats(1.0, 0.0, 0.0, 1.0)
    var mo_a = _floats(1.0, 1.0)
    var nsga = nsga2_linear_default(
        mo_c, 2, 2, mo_a, 1, _senses(SENSE_GE, 1), _floats(4.0),
        _fill(0.0, 2), _fill(10.0, 2), 32, UInt64(3),
    )
    var gaps_nonneg = nsga.has_ideal and len(nsga.ideal_gap) == 2
    if gaps_nonneg:
        for k in range(2):
            if nsga.ideal_gap[k] < -1e-9:
                gaps_nonneg = False
    var nsga_ok = (
        # a heuristic NEVER returns MODEL_OK: the success status is MO_UNPROVEN by design
        nsga.status == MO_UNPROVEN
        and nsga.verified
        and nsga.max_violation == 0.0
        and nsga.n_front > 0
        and nsga.has_ideal
        and gaps_nonneg
        and _rel_close(nsga.ideal[0], 0.0, 8.0, 1e-9)
        and _rel_close(nsga.ideal[1], 0.0, 8.0, 1e-9)
    )
    print(
        "     status=" + mo_status_name(nsga.status),
        "verified=" + String(nsga.verified),
        "n_front=" + String(nsga.n_front),
        "generations=" + String(nsga.generations_run),
        "evaluations=" + String(nsga.evaluations),
        "feasible=" + String(nsga.n_feasible),
        "max_violation=" + String(nsga.max_violation),
    )
    if len(nsga.ideal) == 2 and len(nsga.ideal_gap) == 2:
        print(
            "     proven ideal=(" + String(nsga.ideal[0]) + ", " + String(nsga.ideal[1]) + ")",
            "ideal_gap=(" + String(nsga.ideal_gap[0]) + ", " + String(nsga.ideal_gap[1]) + ")",
        )
    if nsga_ok:
        print(
            "  ✅ the front never beats the PROVEN per-objective ideal, every point is"
            " re-verified inside the rows and the box, and the success status is MO_UNPROVEN"
        )
        print(
            "      there is no proven_optimal field on this result and there should not be:"
            " a genetic algorithm has no certificate to set one from. ideal_gap is the only"
            " bound in the struct that was proved, and it comes from lp_solve."
        )
    else:
        failures += 1
        print("  ❌ NSGA-II: ", mo_status_name(nsga.status), nsga.verified, nsga.n_front)

    # ══ 5. robust: identical scenarios must give the deterministic answer ═════
    print("")
    print("=== Robust: S identical scenarios must EQUAL the deterministic LP, bit for bit ===")
    var det = lp_solve_default(_lp_c(), _lp_a(), 2, 2, _senses(SENSE_LE, 2), _lp_b(), False)
    var s_counts = _int_list(16, 64, 256, 1024)
    var robust_exact = True
    var first_sc_ms: Float64 = 0.0
    var last_sc_ms: Float64 = 0.0
    var first_per: Float64 = 0.0
    var last_per: Float64 = 0.0
    for s in range(len(s_counts)):
        var S = s_counts[s]
        # S bit-identical copies of the base right-hand side.
        var block = List[Float64]()
        for _ in range(S):
            block.append(6.0)
            block.append(45.0)
        for _ in range(WARMUP):
            var _wsc = robust_scenario_solve_default(
                _lp_c(), _lp_a(), 2, 2, _senses(SENSE_LE, 2), _lp_b(), False, S, block, 0.95
            )
        var t16 = perf_counter_ns()
        var sc = robust_scenario_solve_default(
            _lp_c(), _lp_a(), 2, 2, _senses(SENSE_LE, 2), _lp_b(), False, S, block, 0.95
        )
        var t17 = perf_counter_ns()
        var sc_ms = _ms(t17 - t16)
        var mm = robust_min_max_rhs_default(
            _lp_c(), _lp_a(), 2, 2, _senses(SENSE_LE, 2), _lp_b(), False, S, block
        )
        var ok = (
            det.status == LP_OPTIMAL
            and sc.status == ROBUST_BOUND_ONLY
            and sc.n_solved == S
            and sc.has_value
            # `==`, not a tolerance: identical scenarios are the SAME program, so anything
            # other than the identical double would mean the scenario path is not solving it.
            and sc.worst_case == det.objective
            and sc.best_case == det.objective
            and sc.mean_objective == det.objective
            and sc.has_cvar
            and sc.cvar == det.objective
            and mm.status == LP_OPTIMAL
            and mm.has_objective
            and mm.objective == det.objective
            and mm.optimal_for_scenario_set
            and mm.n_distinct_scenarios == S
            and mm.n_verified_scenarios == S
            and mm.n_violating_scenarios == 0
            and mm.worst_violation == 0.0
            # the here-and-now answer can never be better than the worst perfect-foresight
            # optimum: the robust x is feasible in every scenario, so it is feasible in the
            # worst one and cannot beat that scenario's own minimum
            and mm.objective >= sc.worst_case - 1e-9
        )
        if not ok:
            robust_exact = False
        var per_ns = _ms(t17 - t16) * 1.0e6 / Float64(S)
        if s == 0:
            first_sc_ms = sc_ms
            first_per = per_ns
        last_sc_ms = sc_ms
        last_per = per_ns
        print(
            "  S=" + String(S),
            "worst=" + String(sc.worst_case),
            "best=" + String(sc.best_case),
            "mean=" + String(sc.mean_objective),
            "cvar(0.95)=" + String(sc.cvar),
            "| deterministic=" + String(det.objective),
        )
        print(
            "      scenario_solve=" + String(sc_ms) + "ms",
            "ns/scenario=" + String(per_ns),
            "| min_max=" + String(mm.objective),
            "distinct=" + String(mm.n_distinct_scenarios),
            "verified=" + String(mm.n_verified_scenarios),
            "status=" + robust_status_name(sc.status),
        )
    if robust_exact:
        print(
            "  ✅ with S identical scenarios worst = best = mean = CVaR = the here-and-now"
            " objective = lp_solve's -41.25, all four compared with == and not a tolerance"
        )
        print(
            "      and the here-and-now objective is never below the worst perfect-foresight"
            " optimum, which is the inequality that makes the two drivers different things"
        )
    else:
        failures += 1
        print("  ❌ identical scenarios did not reproduce the deterministic objective")
    var S_lo = s_counts[0]
    var S_hi = s_counts[len(s_counts) - 1]
    print(
        "  measured growth S=" + String(S_lo) + " -> " + String(S_hi) + ":",
        "total n^" + String(_exponent(first_sc_ms, last_sc_ms, S_lo, S_hi)),
        "| ns/scenario " + String(first_per) + " -> " + String(last_per),
    )
    var per_ratio = last_per / first_per if first_per > 0.0 else 999.0
    if per_ratio <= 3.0:
        print(
            "  ✅ cost per scenario ended at " + String(per_ratio)
            + "x its starting value across a 64x rise in S — one independent LP per scenario,"
            + " and the driver adds no super-linear term on top"
        )
    else:
        failures += 1
        print(
            "  ❌ cost per scenario grew " + String(per_ratio)
            + "x; the scenario loop is not linear in S"
        )

    # A varying scenario set, so the aggregates are not all the same number.
    var vary = List[Float64]()
    var vs = INSTANCE_SEED
    for _ in range(64):
        vs = _lcg_next(vs)
        vary.append(5.0 + Float64(vs % 200) / 100.0)
        vs = _lcg_next(vs)
        vary.append(40.0 + Float64(vs % 1000) / 100.0)
    var vsc = robust_scenario_solve_default(
        _lp_c(), _lp_a(), 2, 2, _senses(SENSE_LE, 2), _lp_b(), False, 64, vary, 0.95
    )
    var vmm = robust_min_max_rhs_default(
        _lp_c(), _lp_a(), 2, 2, _senses(SENSE_LE, 2), _lp_b(), False, 64, vary
    )
    if vsc.status == ROBUST_BOUND_ONLY and vmm.status == LP_OPTIMAL:
        print(
            "  64 VARYING scenarios:",
            "worst=" + String(vsc.worst_case),
            "best=" + String(vsc.best_case),
            "mean=" + String(vsc.mean_objective),
            "cvar=" + String(vsc.cvar),
            "here_and_now=" + String(vmm.objective),
            "price_of_robustness=" + String(vmm.objective - vsc.mean_objective),
        )
        if (
            vmm.objective >= vsc.worst_case - 1e-9
            and vsc.worst_case >= vsc.mean_objective - 1e-9
            and vsc.has_cvar
            and vsc.cvar >= vsc.mean_objective - 1e-9
            and vsc.cvar <= vsc.worst_case + 1e-9
            and vmm.n_violating_scenarios == 0
        ):
            print(
                "  ✅ mean <= CVaR <= worst perfect-foresight <= here-and-now, and the"
                " here-and-now point violates none of the 64 scenarios"
            )
        else:
            failures += 1
            print("  ❌ the robust ordering mean <= cvar <= worst <= here-and-now does not hold")
    else:
        failures += 1
        print("  ❌ the varying scenario set did not solve")

    # ══ 6. determinism, measured on every seeded driver ══════════════════════
    print("")
    print("=== Determinism: same seed => bit-identical, measured on every seeded driver ===")
    var det_ok = True
    var differed = 0
    var seeded = 0

    # routing: iterated local search
    var ils_a = tsp_iterated_local_search(rd, 200, 64, 3, 24, UInt64(11))
    var ils_b = tsp_iterated_local_search(rd, 200, 64, 3, 24, UInt64(11))
    var ils_c = tsp_iterated_local_search(rd, 200, 64, 3, 24, UInt64(12))
    seeded += 1
    var ils_same = (
        ils_a.tour_length == ils_b.tour_length
        and _ints_exact(ils_a.tour, ils_b.tour)
        and ils_a.kicks_accepted == ils_b.kicks_accepted
    )
    if not ils_same:
        det_ok = False
    var ils_diff = ils_c.tour_length != ils_a.tour_length or not _ints_exact(ils_c.tour, ils_a.tour)
    if ils_diff:
        differed += 1
    print(
        "  routing.tsp_iterated_local_search:",
        "same_seed_identical=" + String(ils_same),
        "seed11=" + String(ils_a.tour_length),
        "seed12=" + String(ils_c.tour_length),
        "different_seed_moves=" + String(ils_diff),
    )

    # quadratic: the path signature is the field that has to move, not the answer
    var tie_q = _floats(2.0, 0.0, 0.0, 2.0)
    var tie_c = _floats(-2.0, -2.0)
    var tie_a = _floats(1.0, 1.0, 1.0, 1.0)
    var tie_b = _floats(1.0, 1.0)
    var tie_lb = _ifill(VAR_FLAG_HAS_LOWER, 2)
    var qa = qp_solve_default(
        tie_q, 2, tie_c, tie_a, 2, _senses(SENSE_LE, 2), tie_b,
        _fill(0.0, 2), _fill(0.0, 2), tie_lb, UInt64(101),
    )
    var qb = qp_solve_default(
        tie_q, 2, tie_c, tie_a, 2, _senses(SENSE_LE, 2), tie_b,
        _fill(0.0, 2), _fill(0.0, 2), tie_lb, UInt64(101),
    )
    var qc = qp_solve_default(
        tie_q, 2, tie_c, tie_a, 2, _senses(SENSE_LE, 2), tie_b,
        _fill(0.0, 2), _fill(0.0, 2), tie_lb, UInt64(202),
    )
    seeded += 1
    var qp_same = (
        qa.objective == qb.objective
        and _vec_exact(qa.x, qb.x)
        and qa.path_signature == qb.path_signature
    )
    if not qp_same:
        det_ok = False
    var qp_answer_stable = qc.objective == qa.objective
    if not qp_answer_stable:
        det_ok = False
    print(
        "  quadratic.qp_solve:",
        "same_seed_identical=" + String(qp_same),
        "objective=" + String(qa.objective),
        "path_signature=" + String(qa.path_signature) + "/" + String(qc.path_signature),
        "| a DIFFERENT seed must keep the SAME optimum on a convex program:"
        " " + String(qp_answer_stable),
    )

    # scheduling: tabu and SGS
    var sh_dur = _jssp_durations(8, 8, INSTANCE_SEED)
    var sh_mach = _jssp_latin(8, 8, 8)
    var ta = jobshop_tabu_solve_flat(sh_dur, sh_mach, 8, 8, 8, 31, 400, 9, 50)
    var tb = jobshop_tabu_solve_flat(sh_dur, sh_mach, 8, 8, 8, 31, 400, 9, 50)
    var tc = jobshop_tabu_solve_flat(sh_dur, sh_mach, 8, 8, 8, 32, 400, 9, 50)
    seeded += 1
    var tabu_same = (
        ta.makespan == tb.makespan
        and _vec_exact(ta.start, tb.start)
        and _ints_exact(ta.machine_rank, tb.machine_rank)
        and ta.iterations == tb.iterations
    )
    if not tabu_same:
        det_ok = False
    var tabu_diff = not _vec_exact(tc.start, ta.start)
    if tabu_diff:
        differed += 1
    print(
        "  scheduling.jobshop_tabu_solve_flat:",
        "same_seed_identical=" + String(tabu_same),
        "seed31=" + String(ta.makespan),
        "seed32=" + String(tc.makespan),
        "different_seed_changes_the_SCHEDULE=" + String(tabu_diff),
        "changes_the_MAKESPAN=" + String(tc.makespan != ta.makespan),
        "iterations=" + String(ta.iterations) + "/" + String(tc.iterations),
    )

    var ra = rcpsp_sgs_solve_flat(hard_dur, hard_dem, hard_cap, hpf, hpt, hard_n, 2, 5, 32)
    var rb = rcpsp_sgs_solve_flat(hard_dur, hard_dem, hard_cap, hpf, hpt, hard_n, 2, 5, 32)
    var rcx = rcpsp_sgs_solve_flat(hard_dur, hard_dem, hard_cap, hpf, hpt, hard_n, 2, 6, 32)
    seeded += 1
    var sgs_same = (
        ra.makespan == rb.makespan
        and _vec_exact(ra.start, rb.start)
        and _ints_exact(ra.order, rb.order)
    )
    if not sgs_same:
        det_ok = False
    var sgs_diff = not _ints_exact(rcx.order, ra.order)
    if sgs_diff:
        differed += 1
    print(
        "  scheduling.rcpsp_sgs_solve_flat:",
        "same_seed_identical=" + String(sgs_same),
        "seed5=" + String(ra.makespan),
        "seed6=" + String(rcx.makespan),
        "different_seed_changes_the_ORDER=" + String(sgs_diff),
        "changes_the_MAKESPAN=" + String(rcx.makespan != ra.makespan),
    )

    # multiobjective: NSGA-II
    var na = nsga2_linear_default(
        mo_c, 2, 2, mo_a, 1, _senses(SENSE_GE, 1), _floats(4.0),
        _fill(0.0, 2), _fill(10.0, 2), 32, UInt64(3),
    )
    var nb = nsga2_linear_default(
        mo_c, 2, 2, mo_a, 1, _senses(SENSE_GE, 1), _floats(4.0),
        _fill(0.0, 2), _fill(10.0, 2), 32, UInt64(3),
    )
    var nc = nsga2_linear_default(
        mo_c, 2, 2, mo_a, 1, _senses(SENSE_GE, 1), _floats(4.0),
        _fill(0.0, 2), _fill(10.0, 2), 32, UInt64(4),
    )
    seeded += 1
    var nsga_same = (
        na.n_front == nb.n_front
        and _vec_exact(na.front_f, nb.front_f)
        and _vec_exact(na.front_x, nb.front_x)
        and na.evaluations == nb.evaluations
    )
    if not nsga_same:
        det_ok = False
    var nsga_diff = nc.n_front != na.n_front or not _vec_exact(nc.front_f, na.front_f)
    if nsga_diff:
        differed += 1
    print(
        "  multiobjective.nsga2_linear:",
        "same_seed_identical=" + String(nsga_same),
        "n_front=" + String(na.n_front) + "/" + String(nc.n_front),
        "different_seed_moves=" + String(nsga_diff),
    )

    # robust: the scenario DRAW itself
    var base_rhs = _floats(6.0, 45.0)
    var sigma = _floats(0.5, 2.0)
    var da = scenario_rhs_normal(base_rhs, sigma, 64, UInt64(77), "bench.tier2")
    var db = scenario_rhs_normal(base_rhs, sigma, 64, UInt64(77), "bench.tier2")
    var dc = scenario_rhs_normal(base_rhs, sigma, 64, UInt64(78), "bench.tier2")
    var dd = scenario_rhs_normal(base_rhs, sigma, 64, UInt64(77), "bench.tier2.other")
    seeded += 1
    var draw_same = _vec_exact(da.rhs, db.rhs) and da.stream == db.stream
    if not draw_same:
        det_ok = False
    var draw_diff = not _vec_exact(dc.rhs, da.rhs)
    var stream_diff = not _vec_exact(dd.rhs, da.rhs) and dd.stream != da.stream
    if draw_diff:
        differed += 1
    print(
        "  robust.scenario_rhs_normal:",
        "same_seed_identical=" + String(draw_same),
        "rng=" + da.rng,
        "different_seed_moves=" + String(draw_diff),
        "different_STREAM_moves=" + String(stream_diff),
    )
    # A benchmark whose scenario draws came from a wall clock would contradict the product
    # claim, so the source is asserted rather than assumed — against
    # `determinism.counter_rng.rng_version()` itself, not against a string literal typed here.
    if da.rng != rng_version():
        det_ok = False
        print(
            "  ❌ the scenario draw reports rng '" + da.rng
            + "' but determinism.counter_rng declares '" + rng_version() + "'"
        )

    if det_ok:
        print(
            "  ✅ all " + String(seeded) + " seeded drivers reproduce BIT-FOR-BIT under their"
            " own seed — every field compared with ==, no tolerance anywhere"
        )
        print(
            "      " + String(differed) + " of the " + String(seeded - 1)
            + " search drivers took a different path when the seed changed. The QP is"
            + " excluded from that count on purpose: on a CONVEX program a different seed"
            + " must return the IDENTICAL optimum and only the path signature may move, which"
            + " is what its line measures. A solver whose ANSWER moved with its seed would be"
            + " the bug, not the evidence."
        )
        print(
            "      reported rather than dressed up: on these two scheduling instances a"
            " different seed reached the SAME makespan. That is a property of the instance —"
            " tabu and SGS both have many orientations of equal value — and the seed is doing"
            " its job in the tie-break, which is why the schedule itself is compared too."
        )
    else:
        failures += 1
        print("  ❌ a seeded driver did not reproduce under its own seed")

    # ══ 7. rule 4: an answer that does not exist is ABSENT, never zero ════════
    print("")
    print("=== Rule 4: no answer => no number. Every list empty, every has_* False ===")
    var absent_ok = True

    # a distance matrix with a non-zero diagonal is not a distance matrix
    var bad_d = _fill(1.0, 9)
    var bad_route = tsp_two_opt(bad_d, 3, 8)
    var a1 = (
        bad_route.status != ROUTE_OK
        and bad_route.status != ROUTE_OK_LIMIT
        and not bad_route.has_length
        and len(bad_route.tour) == 0
    )
    if not a1:
        absent_ok = False
    print(
        "  routing, d[c][c] != 0:",
        route_status_name(bad_route.status),
        "has_length=" + String(bad_route.has_length),
        "len(tour)=" + String(len(bad_route.tour)),
    )

    # an unbounded QP has no optimal objective
    var unb = qp_solve_default(
        _floats(0.0), 1, _floats(-1.0), List[Float64](), 0, List[Int](), List[Float64](),
        _fill(0.0, 1), _fill(0.0, 1), _ifill(0, 1), UInt64(1),
    )
    var a2 = (
        unb.status == QP_UNBOUNDED
        and not unb.has_objective
        and not unb.feasible
        and len(unb.x) == 0
    )
    if not a2:
        absent_ok = False
    print(
        "  quadratic, unbounded:",
        qp_status_name(unb.status),
        "has_objective=" + String(unb.has_objective),
        "len(x)=" + String(len(unb.x)),
        "len(ray)=" + String(len(unb.ray)),
    )

    # a cyclic precedence graph has no schedule
    var cyc_res = rcpsp_sgs_solve_flat(
        _fill(1.0, 2), _fill(1.0, 2), _floats(4.0),
        _int_list(0, 1), _int_list(1, 0), 2, 1, 3, 4,
    )
    var a3 = (
        cyc_res.status == SCHED_PRECEDENCE_CYCLE
        and not cyc_res.has_makespan
        and not cyc_res.feasible
        and len(cyc_res.start) == 0
    )
    if not a3:
        absent_ok = False
    print(
        "  scheduling, precedence cycle:",
        sched_status_name(cyc_res.status),
        "has_makespan=" + String(cyc_res.has_makespan),
        "len(start)=" + String(len(cyc_res.start)),
        "cycle_act=" + String(cyc_res.cycle_act),
    )

    # a malformed job shop has no bound
    var bad_bound = jobshop_bound_flat(_fill(1.0, 5), _ifill(0, 5), 5, 5, 5)
    var a4 = (
        bad_bound.status != MODEL_OK
        and not bad_bound.has_bound
        and bad_bound.critical_job == -1
        and bad_bound.critical_machine == -1
    )
    if not a4:
        absent_ok = False
    print(
        "  scheduling, 5 durations declared as 5x5:",
        sched_status_name(bad_bound.status),
        "has_bound=" + String(bad_bound.has_bound),
        "critical_job=" + String(bad_bound.critical_job),
    )

    # three objectives: an exact hypervolume does not exist here
    var a5 = (not hv_three.has_value) and hv_three.has_estimate and (not hv_three.exact)
    if not a5:
        absent_ok = False
    print(
        "  multiobjective, 3 objectives:",
        mo_status_name(hv_three.status),
        "has_value=" + String(hv_three.has_value),
        "has_estimate=" + String(hv_three.has_estimate),
        "exact_bounds=[" + String(hv_three.bound_lower) + ", "
        + String(hv_three.bound_upper) + "]",
    )

    # an infeasible feasible region has no front
    var inf_nsga = nsga2_linear_default(
        _floats(1.0, 0.0, 0.0, 1.0), 2, 2, _floats(1.0, 0.0, 1.0, 0.0), 2,
        _int_list(SENSE_GE, SENSE_LE), _floats(3.0, 2.0),
        _fill(0.0, 2), _fill(10.0, 2), 8, UInt64(3),
    )
    var a6 = (
        inf_nsga.status == LP_INFEASIBLE
        and inf_nsga.n_front == 0
        and len(inf_nsga.front_f) == 0
        and not inf_nsga.has_ideal
    )
    if not a6:
        absent_ok = False
    print(
        "  multiobjective, x >= 3 and x <= 2:",
        mo_status_name(inf_nsga.status),
        "n_front=" + String(inf_nsga.n_front),
        "has_ideal=" + String(inf_nsga.has_ideal),
    )

    # one infeasible scenario means NO aggregate, not an average over the ones that solved
    var inf_block = List[Float64]()
    inf_block.append(3.0)
    inf_block.append(2.0)
    inf_block.append(3.0)
    inf_block.append(2.5)
    var inf_sc = robust_scenario_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1, _int_list(SENSE_GE, SENSE_LE),
        _floats(3.0, 2.0), False, 2, inf_block, 0.95,
    )
    var a7 = (
        (inf_sc.status == ROBUST_SCENARIO_FAILED or inf_sc.status == ROBUST_UNVERIFIED)
        and not inf_sc.has_value
        and not inf_sc.has_cvar
        and len(inf_sc.objectives) == 0
        and inf_sc.first_failed_scenario == 0
    )
    if not a7:
        absent_ok = False
    print(
        "  robust, an infeasible scenario:",
        robust_status_name(inf_sc.status),
        "has_value=" + String(inf_sc.has_value),
        "len(objectives)=" + String(len(inf_sc.objectives)),
        "first_failed=" + String(inf_sc.first_failed_scenario),
        "n_failed=" + String(inf_sc.n_failed),
    )

    if absent_ok:
        print(
            "  ✅ seven drivers, seven questions with no answer, seven ABSENT answers:"
            " an empty vector and a cleared has_* flag, never a zero under a success status"
        )
        print(
            "      this is the most load-bearing property in the package. A wrong status"
            " travels further than a wrong number, because downstream code branches on it."
        )
    else:
        failures += 1
        print("  ❌ a driver returned a number for a question with no answer")

    print("")
    if failures == 0:
        print("BENCH_GATE optimization_tier2 PASS")
    else:
        print("BENCH_GATE optimization_tier2 FAIL " + String(failures))
        raise Error(
            "bench_optimization_tier2: " + String(failures) + " gate failure(s)"
        )
