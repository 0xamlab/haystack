"""bench_optimization.mojo — measured gate for the `optimization` package.

Hand-written, not generated, and the name cannot collide. `benchmark_mojo_vs_python.py`
writes `bench_<lib_id>.mojo`, where `lib_id` for a module inside a package is
`<subdir>_<stem>` — so the generated files for this package are `bench_optimization_linear`,
`bench_optimization_flow` and so on, and `__init__` is in its `SKIP_FILES`. No `lib_id` is
ever the bare string `optimization`, and the generator only writes; it never unlinks.
`make bench-optimization` is the only thing that runs this file.

What is measured, and why each one is the claim that matters
-----------------------------------------------------------
Every arm below is compared against the FAIREST frozen path that can express the same
problem, and in every case the two answers are cross-checked FIRST. A timing ratio between
two different answers measures nothing, and the claims that survived measurement here are
mostly not speed claims at all — they are exactness, node count and pass count, which is
what a solver package is actually for.

1. **Two-phase simplex vs the frozen 2-variable vertex enumerator.**
   `linear_programming.lp_solve_2var` enumerates every pair of constraint lines, intersects
   them and keeps the feasible intersection with the best objective — restricted to exactly
   two variables. `optimization.linear.lp_solve` pivots, at any size. Both are run on the same
   program at a rising row count, on a family where every row is a real face of the polygon
   (see `_tangent_rows`, and the note there on why a padded program would have been the
   charitable case rather than the fair one). The objectives must agree to 1e-9 at every size.
   The speed result is modest and NON-MONOTONE, and it is printed as such rather than dressed
   up: measured here, the specialised enumerator wins at 4 rows, the simplex leads by
   1.4-1.5x between 16 and 32 rows, the lead narrows to 1.07x at 64, and by 128 rows the
   enumerator is ahead again — because the simplex's pivot COUNT grows with the rows on top of
   its tableau area, so its LOCAL rate over the last doubling is the steeper of the two
   (2.80 against 2.43). Over the whole range the ordering is the other way (simplex n^1.88,
   enumerator n^1.93), because fixed overhead at 4 rows flattens the simplex's curve; both
   exponents are printed for exactly that reason and neither alone describes the arms. So the
   surviving claim is agreement plus generality, not speed: a three-variable program is priced
   immediately below and the frozen kernel cannot state one at all.

2. **Hungarian vs the frozen greedy — exactness, not speed.**
   On `cost[i][j] = (i+1)(j+1)` the rearrangement inequality gives closed forms for both
   answers: the optimum is `n(n+1)(n+2)/6` and per-row greedy is `n(n+1)(2n+1)/6`, so the
   greedy excess is a KNOWN quantity at every n, not a measured one, and it grows without
   bound. The greedy is faster — it is O(n²) against O(n³) — and that is reported as the
   price of the exactness rather than hidden.

3. **Dinic vs Edmonds-Karp on the same residual network.**
   The baseline is built from `optimization.flow`'s own `_build_network` and its
   `graph_decision.flow_residual_capacity` / `flow_augment_amount` scalars, so the two arms
   share the data structure and the arithmetic exactly and differ ONLY in the search: one
   BFS per augmentation versus one BFS per phase with a blocking flow inside it. On a
   unit-capacity bipartite graph both push the same number of augmenting paths, so the whole
   difference is the number of breadth-first passes — which is the level structure's entire
   contribution and is measured as a count as well as a time. A depth-first Ford-Fulkerson
   would have made a much more flattering graph out of capacity magnitude; Edmonds-Karp's
   augmentation count does not depend on the capacities at all, which is why it is the
   baseline here.

4. **Branch and bound's LP bound vs blind enumeration, cross-checked against the frozen DP.**
   `combinatorial.knapsack_01_value` is an exact integer DP over the same knapsack, so it is
   an independent oracle for `optimization.integer.milp_knapsack`'s objective. The claim is
   the node census: how many nodes the relaxation bound left to explore against the `2^n`
   subsets a blind search would enumerate. It is NOT a speed claim — the frozen DP is orders
   of magnitude faster on the one shape it can express, and that ratio is printed too.

5. **Simplex scaling.** Cost per (iteration × tableau cell) across an 8x rise in size, which
   is flat if a pivot is linear in the tableau and is the honest way to state the growth
   instead of asserting a complexity. The per-solve growth exponent is printed beside it,
   because the pivot count rises with `n` as well and the normalised number deliberately
   divides that out.

Gate
----
Fails on properties, never on absolute nanoseconds. Nothing here gates on the simplex being
faster than the frozen enumerator, because it measured as faster only inside a window — see
arm 1. `⚠️` lines are measured facts that run against the package, printed on purpose:
  * simplex and the frozen enumerator must agree on the objective to 1e-9 at every row count
  * the Hungarian cost must equal `n(n+1)(n+2)/6` and greedy `n(n+1)(2n+1)/6` exactly, the
    dual certificate must be `certified`, and `assignment_cost_of` must re-derive the same
    total from the returned pairs
  * Dinic and Edmonds-Karp must report the same max-flow value, and Dinic must use strictly
    fewer breadth-first passes
  * branch and bound must equal the frozen DP's objective, report `proven_optimal`, and
    explore fewer nodes than `2^n`
  * ns per (iteration × tableau cell) must not grow more than 3x across the size range
Absolute numbers are printed for tracking.
"""
from std.math import abs as fabs, cos, log, sin, sqrt
from std.time import perf_counter_ns

from combinatorial import knapsack_01_value
from graph_decision import flow_augment_amount
from linear_programming import lp_solve_2var
from optimization.assignment import (
    ASSIGN_OK,
    assignment_cost_of,
    assignment_solve,
    greedy_assignment_flat,
)
from optimization.flow import (
    FLOW_EPS,
    FLOW_OK,
    FlowNetwork,
    _build_network,
    _twin,
    max_flow_dinic,
)
from optimization.integer import MILP_OPTIMAL, milp_knapsack, milp_status_name
from optimization.linear import LP_OPTIMAL, lp_solve_default, lp_status_name
from optimization.model import SENSE_LE

comptime WARMUP: Int = 3


fn _ms(elapsed: UInt) -> Float64:
    """`perf_counter_ns` yields UInt, so the delta stays unsigned until here."""
    return Float64(Int(elapsed)) / 1.0e6


fn _ns_per(elapsed: UInt, work: Int, reps: Int) -> Float64:
    if work <= 0 or reps <= 0:
        return 0.0
    return Float64(Int(elapsed)) / Float64(work * reps)


fn _le(n: Int) -> List[Int]:
    var out = List[Int]()
    for _ in range(n):
        out.append(SENSE_LE)
    return out^


fn _exponent(t_first: Float64, t_last: Float64, n_first: Int, n_last: Int) -> Float64:
    """The empirical growth exponent `p` in `t ~ n^p`, from the two endpoints.

    Reported instead of a complexity claim: `p` is what was measured, and it is only two
    points, which is why the intermediate sizes are printed too.
    """
    if t_first <= 0.0 or t_last <= 0.0 or n_first <= 0 or n_last <= n_first:
        return 0.0
    return log(t_last / t_first) / log(Float64(n_last) / Float64(n_first))


# ── 1. the shared two-variable program ────────────────────────────────────────


fn _tangent_rows(m: Int) -> List[List[Float64]]:
    """`m` tangents to the unit circle in the first quadrant: `cos θ x + sin θ y <= 1`.

    Chosen over a family of padding rows on purpose. A padding row far outside the feasible
    region is REJECTED by the frozen `is_feasible` on its first violated constraint, so a
    padded program measures the enumerator's early exit rather than its work — the charitable
    case, not the fair one. Here every row is a genuine face of the polygon, so every one of
    the O(m²) line intersections the enumerator forms is a candidate it has to scan all `m`
    rows to classify, and the polygon has `m` real vertices to deduplicate against.

    It is also a real modelling pattern rather than a contrivance: this is the polyhedral
    outer approximation of a norm ball. `θ_i = (i + 0.5)·(π/2)/m` keeps the row set symmetric
    about 45° without putting a row exactly on it, so for even `m` the optimum of `x + y` is
    the single symmetric vertex and the two arms cannot pick different tied vertices.
    """
    var rows = List[List[Float64]]()
    var step = 1.5707963267948966 / Float64(m)
    for i in range(m):
        var theta = (Float64(i) + 0.5) * step
        var r = List[Float64]()
        r.append(cos(theta))
        r.append(sin(theta))
        rows.append(r^)
    return rows^


fn _ones(m: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(m):
        out.append(1.0)
    return out^


fn _flatten(rows: List[List[Float64]], cols: Int) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(rows)):
        for j in range(cols):
            out.append(rows[i][j])
    return out^


# ── 2. the product cost matrix, whose two answers are both closed forms ───────


fn _product_cost(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for i in range(n):
        for j in range(n):
            out.append(Float64((i + 1) * (j + 1)))
    return out^


fn _lcg_cost(n: Int, seed: Int) -> List[Float64]:
    """A deterministic pseudo-random matrix, for a generic-instance timing point."""
    var out = List[Float64]()
    var s = seed
    for _ in range(n * n):
        s = (s * 1103515245 + 12345) % 2147483648
        out.append(1.0 + Float64(s % 1000))
    return out^


# ── 3. Edmonds-Karp over `optimization.flow`'s own residual network ───────────


fn _bipartite_unit(
    n: Int, mut src: List[Int], mut dst: List[Int], mut cap: List[Float64]
) -> Int:
    """`s -> L_i -> R_j -> t`, every capacity 1, three choices per left node.

    Node 0 is the source, `1..n` the left side, `n+1..2n` the right side and `2n+1` the
    sink. `j = i` is always available, so a perfect matching exists and the max flow is
    exactly `n` — a value both arms can be checked against independently of each other.
    Returns `n_nodes`.
    """
    var sink = 2 * n + 1
    for i in range(n):
        src.append(0)
        dst.append(1 + i)
        cap.append(1.0)
    for i in range(n):
        for d in range(3):
            src.append(1 + i)
            dst.append(n + 1 + ((i + d) % n))
            cap.append(1.0)
    for j in range(n):
        src.append(n + 1 + j)
        dst.append(sink)
        cap.append(1.0)
    return sink + 1


fn _ek_max_flow(
    mut net: FlowNetwork, source: Int, sink: Int,
    mut augmentations: Int, mut bfs_passes: Int,
) -> Float64:
    """Shortest-augmenting-path max flow: one BFS per augmenting path.

    The fairest baseline available, and deliberately not a strawman: it is the same residual
    network `optimization.flow` builds, the same `flow_augment_amount` fold for the
    bottleneck and the same `FlowNetwork.residual` derivation, so nothing but the search
    strategy differs. A depth-first Ford-Fulkerson would have made a flattering graph out of
    capacity magnitude instead; Edmonds-Karp's augmentation count does not depend on the
    capacities at all, which is why it is the one to beat.
    """
    var total = 0.0
    var parent_arc = List[Int]()
    for _ in range(net.n_nodes):
        parent_arc.append(-1)
    while True:
        for i in range(net.n_nodes):
            parent_arc[i] = -1
        var queue = List[Int]()
        var front = 0
        var seen = List[Bool]()
        for _ in range(net.n_nodes):
            seen.append(False)
        seen[source] = True
        queue.append(source)
        bfs_passes += 1
        var reached = False
        while front < len(queue):
            var u = queue[front]
            front += 1
            if u == sink:
                reached = True
                break
            for p in range(net.arc_ptr[u], net.arc_ptr[u + 1]):
                var a = net.arc_at[p]
                if net.residual(a) > FLOW_EPS:
                    var v = net.arc_head[a]
                    if not seen[v]:
                        seen[v] = True
                        parent_arc[v] = a
                        queue.append(v)
        if not reached and not seen[sink]:
            return total
        # Bottleneck as a fold of the frozen per-step scalar, seeded with the last arc's
        # own residual rather than a sentinel.
        var v2 = sink
        var b = net.residual(parent_arc[sink])
        while v2 != source:
            var a = parent_arc[v2]
            b = flow_augment_amount(b, net.residual(a))
            v2 = net.tail(a)
        if b <= FLOW_EPS:
            return total
        var v3 = sink
        while v3 != source:
            var a = parent_arc[v3]
            net.arc_flow[a] = net.arc_flow[a] + b
            var t = _twin(a)
            net.arc_flow[t] = net.arc_flow[t] - b
            v3 = net.tail(a)
        total += b
        augmentations += 1


# ── 4. the knapsack both the tree and the frozen DP can express ──────────────


fn _knap_weights(n: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(n):
        out.append(7 + (i * 13) % 29)
    return out^


fn _knap_values(n: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(n):
        out.append(11 + (i * 17) % 37)
    return out^


fn _to_float(values: List[Int]) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(values)):
        out.append(Float64(values[i]))
    return out^


# ── 5. a dense square LP for the scaling arm ─────────────────────────────────


fn _dense_lp_a(n: Int) -> List[Float64]:
    """Diagonally dominant, so every variable is worth using and the basis really fills.

    A matrix of comparable coefficients gives an optimum that loads one or two variables and
    terminates in a handful of pivots at every size, which measures per-pivot cost only. With
    `a[j][j] = 1` against off-diagonals near 0.1 each variable has its own cheap row, so the
    basis fills and the reported per-solve growth reflects real work rather than a fixed
    handful of pivots. Measured iteration counts are 8 / 10 / 19 / 15 across n = 8..64 — they
    rise with `n` but NOT monotonically, so the per-solve growth is not a clean product of
    count and area, and the exponent is quoted as a measurement rather than as a derivation.
    """
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
        out.append(1.0 + 0.5 * Float64(j % 3))
    return out^


fn main() raises:
    var failures = 0

    # ── 1. simplex vs the frozen 2-variable vertex enumerator ────────────────
    print("=== LP: two-phase simplex vs frozen lp_solve_2var (2 vars, rising rows) ===")

    # One hand-computed program first, so the two arms are pinned to a number a human
    # derived before either was run: maximise 3x + 5y over x <= 4, 2y <= 12, 3x + 2y <= 18,
    # whose optimum is 36 at (2, 6).
    var hand_rows = List[List[Float64]]()
    var hr0 = List[Float64]()
    hr0.append(1.0)
    hr0.append(0.0)
    hand_rows.append(hr0^)
    var hr1 = List[Float64]()
    hr1.append(0.0)
    hr1.append(2.0)
    hand_rows.append(hr1^)
    var hr2 = List[Float64]()
    hr2.append(3.0)
    hr2.append(2.0)
    hand_rows.append(hr2^)
    var hand_b = List[Float64]()
    hand_b.append(4.0)
    hand_b.append(12.0)
    hand_b.append(18.0)
    var hand_c = List[Float64]()
    hand_c.append(3.0)
    hand_c.append(5.0)
    var hand_mine = lp_solve_default(
        hand_c, _flatten(hand_rows, 2), 3, 2, _le(3), hand_b, True
    )
    var hand_frozen = lp_solve_2var(hand_c, hand_rows, hand_b)
    if (
        hand_mine.status == LP_OPTIMAL
        and hand_mine.has_objective
        and len(hand_frozen) == 3
        and fabs(hand_mine.objective - 36.0) <= 1e-9
        and fabs(hand_frozen[2] - 36.0) <= 1e-9
        and fabs(hand_mine.x[0] - 2.0) <= 1e-9
        and fabs(hand_mine.x[1] - 6.0) <= 1e-9
    ):
        print("  ✅ both arms return the hand-computed 36.0 at (2, 6)")
    else:
        failures += 1
        print("  ❌ the hand-computed 2-var program came back wrong from one of the arms")

    var row_counts = List[Int]()
    row_counts.append(4)
    row_counts.append(8)
    row_counts.append(16)
    row_counts.append(32)
    row_counts.append(64)
    row_counts.append(128)
    var lp_agreed = True
    var first_simplex_us: Float64 = 0.0
    var last_simplex_us: Float64 = 0.0
    var prev_simplex_us: Float64 = 0.0
    var first_frozen_us: Float64 = 0.0
    var last_frozen_us: Float64 = 0.0
    var prev_frozen_us: Float64 = 0.0
    var best_ratio: Float64 = 0.0
    var best_ratio_m = 0
    for s in range(len(row_counts)):
        var m = row_counts[s]
        var nested = _tangent_rows(m)
        var b = _ones(m)
        var flat = _flatten(nested, 2)
        var c = List[Float64]()
        c.append(1.0)
        c.append(1.0)
        var senses = _le(m)

        var reps = 4096 // m
        if reps < 2:
            reps = 2
        for _ in range(WARMUP):
            var _w = lp_solve_default(c, flat, m, 2, senses, b, True)
        var t0 = perf_counter_ns()
        for _ in range(reps):
            var _r = lp_solve_default(c, flat, m, 2, senses, b, True)
        var t1 = perf_counter_ns()
        var simplex_us = _ms(t1 - t0) * 1000.0 / Float64(reps)

        for _ in range(WARMUP):
            var _wf = lp_solve_2var(c, nested, b)
        var t2 = perf_counter_ns()
        for _ in range(reps):
            var _rf = lp_solve_2var(c, nested, b)
        var t3 = perf_counter_ns()
        var frozen_us = _ms(t3 - t2) * 1000.0 / Float64(reps)

        var mine = lp_solve_default(c, flat, m, 2, senses, b, True)
        var theirs = lp_solve_2var(c, nested, b)
        # The polygon circumscribes the unit disc, so its max of x + y is above sqrt(2) and
        # falls towards it as rows are added: a known bound on the answer, independent of
        # both algorithms.
        var ok = (
            mine.status == LP_OPTIMAL
            and mine.has_objective
            and len(theirs) == 3
            and fabs(mine.objective - theirs[2]) <= 1e-9
            and mine.objective >= sqrt(2.0) - 1e-12
            and mine.objective <= 1.5
        )
        if not ok:
            lp_agreed = False
        if s == 0:
            first_simplex_us = simplex_us
            first_frozen_us = frozen_us
        prev_simplex_us = last_simplex_us
        prev_frozen_us = last_frozen_us
        last_simplex_us = simplex_us
        last_frozen_us = frozen_us
        var ratio = frozen_us / simplex_us if simplex_us > 0.0 else 0.0
        if ratio > best_ratio:
            best_ratio = ratio
            best_ratio_m = m
        print(
            "  rows=" + String(m),
            "objective=" + String(mine.objective),
            "simplex=" + String(simplex_us) + "us",
            "iters=" + String(mine.iterations),
            "frozen_enum=" + String(frozen_us) + "us",
            "frozen/simplex=" + String(ratio) + "x",
        )

    print("")
    if lp_agreed:
        print(
            "  ✅ simplex and the frozen vertex enumerator agree to 1e-9 at every row count,"
            " and the optimum stays inside [sqrt(2), 1.5]"
        )
    else:
        failures += 1
        print("  ❌ simplex and the frozen enumerator disagree — the timings mean nothing")
    # Two exponents, because the whole-range one is flattened by fixed overhead at 4 rows and
    # quoting only it would misstate both arms' growth. The last doubling is the local rate;
    # the per-size lines above are the actual evidence. The two orderings DISAGREE, and that is
    # the finding rather than a wrinkle to pick a side of: over the last doubling the simplex is
    # steeper (its pivot count grows with the rows AND so does its tableau), while over the
    # whole range the enumerator is, because the simplex pays a fixed cost that dominates at
    # 4 rows. That is why the middle of the range is a window rather than a crossover — and why
    # quoting either exponent on its own would be a claim the data does not make.
    var m_first = row_counts[0]
    var m_last = row_counts[len(row_counts) - 1]
    var m_prev = row_counts[len(row_counts) - 2]
    print(
        "  measured growth " + String(m_first) + " -> " + String(m_last) + " rows:",
        "simplex n^" + String(_exponent(first_simplex_us, last_simplex_us, m_first, m_last)),
        "frozen_enum n^" + String(_exponent(first_frozen_us, last_frozen_us, m_first, m_last)),
    )
    print(
        "  over the last doubling (" + String(m_prev) + " -> " + String(m_last) + "):",
        "simplex n^" + String(_exponent(prev_simplex_us, last_simplex_us, m_prev, m_last)),
        "frozen_enum n^" + String(_exponent(prev_frozen_us, last_frozen_us, m_prev, m_last)),
    )
    # Reported as a window, which is what it measured as. Claiming the peak ratio as "the"
    # speedup would be claiming a number that stops being true two sizes later.
    print(
        "  ⚠️  the simplex's speed advantage here is a WINDOW, not a crossover: best "
        + String(best_ratio)
        + "x at "
        + String(best_ratio_m)
        + " rows, and at "
        + String(m_last)
        + " rows the ratio is "
        + String(last_frozen_us / last_simplex_us)
        + "x. Against a specialised 2-variable kernel the durable claim is generality."
    )

    # The generality the simplex buys, priced on a program the frozen kernel cannot state
    # at all: three variables. There is no baseline to compare against here BECAUSE that is
    # the point — `lp_solve_2var` takes a two-column `A` and enumerates pairs of lines.
    var c3 = List[Float64]()
    c3.append(5.0)
    c3.append(4.0)
    c3.append(3.0)
    var a3 = List[Float64]()
    a3.append(2.0)
    a3.append(3.0)
    a3.append(1.0)
    a3.append(4.0)
    a3.append(1.0)
    a3.append(2.0)
    a3.append(3.0)
    a3.append(4.0)
    a3.append(2.0)
    var b3 = List[Float64]()
    b3.append(5.0)
    b3.append(11.0)
    b3.append(8.0)
    for _ in range(WARMUP):
        var _w3 = lp_solve_default(c3, a3, 3, 3, _le(3), b3, True)
    var t4 = perf_counter_ns()
    for _ in range(64):
        var _r3 = lp_solve_default(c3, a3, 3, 3, _le(3), b3, True)
    var t5 = perf_counter_ns()
    var three_us = _ms(t5 - t4) * 1000.0 / 64.0
    var sol3 = lp_solve_default(c3, a3, 3, 3, _le(3), b3, True)
    print(
        "  3-var program (frozen kernel cannot express it):",
        String(three_us) + "us",
        "status=" + lp_status_name(sol3.status),
        "objective=" + String(sol3.objective),
    )
    if sol3.status == LP_OPTIMAL and fabs(sol3.objective - 13.0) <= 1e-9:
        print("  ✅ the 3-variable optimum is the hand-computed 13.0")
    else:
        failures += 1
        print("  ❌ the 3-variable optimum is wrong")

    # ── 2. Hungarian vs the frozen greedy ────────────────────────────────────
    print("")
    print("=== Assignment: exact Hungarian vs frozen combinatorial.assignment_greedy ===")
    var a_sizes = List[Int]()
    a_sizes.append(3)
    a_sizes.append(32)
    a_sizes.append(128)
    var exact_holds = True
    var last_slow: Float64 = 0.0
    var last_excess_pct: Float64 = 0.0
    var last_a_n = 0
    for s in range(len(a_sizes)):
        var n = a_sizes[s]
        var cost = _product_cost(n)
        var expect_opt = Float64(n * (n + 1) * (n + 2)) / 6.0
        var expect_greedy = Float64(n * (n + 1) * (2 * n + 1)) / 6.0

        var reps = 1
        if n <= 32:
            reps = 16
        for _ in range(WARMUP):
            var _wa = assignment_solve(cost, n, n)
        var t6 = perf_counter_ns()
        for _ in range(reps):
            var _ra = assignment_solve(cost, n, n)
        var t7 = perf_counter_ns()
        var hung_ms = _ms(t7 - t6) / Float64(reps)

        for _ in range(WARMUP):
            var _wg = greedy_assignment_flat(cost, n, n)
        var t8 = perf_counter_ns()
        for _ in range(reps):
            var _rg = greedy_assignment_flat(cost, n, n)
        var t9 = perf_counter_ns()
        var greedy_ms = _ms(t9 - t8) / Float64(reps)

        var opt = assignment_solve(cost, n, n)
        var gre = greedy_assignment_flat(cost, n, n)
        var recheck = assignment_cost_of(cost, n, n, opt.col_of_row)
        var ok = (
            opt.status == ASSIGN_OK
            and opt.perfect
            and opt.has_cost
            and opt.dual_certified
            and fabs(opt.total_cost - expect_opt) <= 1e-9
            and gre.status == ASSIGN_OK
            and gre.has_cost
            and fabs(gre.total_cost - expect_greedy) <= 1e-9
            and recheck.status == ASSIGN_OK
            and recheck.perfect
            and fabs(recheck.total_cost - opt.total_cost) <= 1e-9
        )
        if not ok:
            exact_holds = False
        var excess = gre.total_cost - opt.total_cost
        var excess_pct = 100.0 * excess / opt.total_cost if opt.total_cost > 0.0 else 0.0
        var slow = hung_ms / greedy_ms if greedy_ms > 0.0 else 0.0
        last_slow = slow
        last_excess_pct = excess_pct
        last_a_n = n
        print(
            "  n=" + String(n),
            "hungarian=" + String(opt.total_cost),
            "greedy=" + String(gre.total_cost),
            "greedy_excess=" + String(excess),
            "(" + String(excess_pct) + "%)",
        )
        print(
            "      hungarian=" + String(hung_ms) + "ms",
            "greedy=" + String(greedy_ms) + "ms",
            "exactness_costs=" + String(slow) + "x",
            "augmentations=" + String(opt.augmentations),
            "warm_started=" + String(opt.warm_started),
        )

    if exact_holds:
        print(
            "  ✅ Hungarian hits the closed-form optimum n(n+1)(n+2)/6 with a certified dual,"
            " greedy hits n(n+1)(2n+1)/6, and assignment_cost_of re-derives the same total"
        )
    else:
        failures += 1
        print("  ❌ a closed form, the dual certificate or the re-derived cost did not hold")
    # The trade, stated as a trade. O(n³) against O(n²) cannot come out ahead on time, and a
    # benchmark that buried this ratio would be selling the wrong thing.
    print(
        "  ⚠️  the frozen greedy is "
        + String(last_slow)
        + "x FASTER at n="
        + String(last_a_n)
        + " and "
        + String(last_excess_pct)
        + "% WRONG there — the claim is exactness, never speed"
    )

    # A generic instance, where the greedy excess is measured rather than proven.
    var rnd = _lcg_cost(128, 20260730)
    var ropt = assignment_solve(rnd, 128, 128)
    var rgre = greedy_assignment_flat(rnd, 128, 128)
    if ropt.status == ASSIGN_OK and rgre.status == ASSIGN_OK and rgre.has_cost:
        var rex = 100.0 * (rgre.total_cost - ropt.total_cost) / ropt.total_cost
        print(
            "  pseudo-random 128x128:",
            "hungarian=" + String(ropt.total_cost),
            "greedy=" + String(rgre.total_cost),
            "greedy_excess=" + String(rex) + "%",
        )
        if rgre.total_cost >= ropt.total_cost - 1e-9:
            print("  ✅ the greedy cost never undercuts the optimum on the generic instance")
        else:
            failures += 1
            print("  ❌ the greedy beat the 'optimum' — one of the two is wrong")
    else:
        failures += 1
        print("  ❌ the generic 128x128 instance did not solve")

    # ── 3. Dinic vs Edmonds-Karp on the same residual network ────────────────
    print("")
    print("=== Max flow: Dinic vs Edmonds-Karp (same FlowNetwork, same residual scalar) ===")
    var f_sizes = List[Int]()
    f_sizes.append(128)
    f_sizes.append(256)
    f_sizes.append(512)
    var flow_agreed = True
    var dinic_fewer_passes = True
    var first_dinic_ms: Float64 = 0.0
    var last_dinic_ms: Float64 = 0.0
    var first_ek_ms: Float64 = 0.0
    var last_ek_ms: Float64 = 0.0
    for s in range(len(f_sizes)):
        var n = f_sizes[s]
        var src = List[Int]()
        var dst = List[Int]()
        var cap = List[Float64]()
        var n_nodes = _bipartite_unit(n, src, dst, cap)
        var sink = 2 * n + 1

        for _ in range(WARMUP):
            var _wd = max_flow_dinic(src, dst, cap, n_nodes, 0, sink)
        var t10 = perf_counter_ns()
        var dinic = max_flow_dinic(src, dst, cap, n_nodes, 0, sink)
        var t11 = perf_counter_ns()
        var dinic_ms = _ms(t11 - t10)

        # LIKE FOR LIKE, deliberately. `max_flow_dinic` builds its own residual network inside
        # the region timed above, so the baseline must pay for construction inside its region
        # too — and must get the same warmup. Timing a warmed arm that includes construction
        # against a cold arm that excludes it is two errors pointing in opposite directions,
        # which is not the same thing as no error: it makes the ratio unattributable rather
        # than conservative.
        var ek_aug = 0
        var ek_passes = 0
        for _ in range(WARMUP):
            var _wn = _build_network(src, dst, cap, List[Float64](), n_nodes)
            var _wa = 0
            var _wp = 0
            var _we = _ek_max_flow(_wn, 0, sink, _wa, _wp)
        var t12 = perf_counter_ns()
        var net = _build_network(src, dst, cap, List[Float64](), n_nodes)
        var ek_value = _ek_max_flow(net, 0, sink, ek_aug, ek_passes)
        var t13 = perf_counter_ns()
        var ek_ms = _ms(t13 - t12)

        var ok = (
            dinic.status == FLOW_OK
            and dinic.has_value
            and fabs(dinic.value - Float64(n)) <= 1e-9
            and fabs(ek_value - dinic.value) <= 1e-9
        )
        if not ok:
            flow_agreed = False
        if dinic.phases >= ek_passes:
            dinic_fewer_passes = False
        if s == 0:
            first_dinic_ms = dinic_ms
            first_ek_ms = ek_ms
        last_dinic_ms = dinic_ms
        last_ek_ms = ek_ms
        var speed = ek_ms / dinic_ms if dinic_ms > 0.0 else 0.0
        print(
            "  left=" + String(n),
            "V=" + String(n_nodes),
            "E=" + String(len(src)),
            "dinic_value=" + String(dinic.value),
            "ek_value=" + String(ek_value),
        )
        print(
            "      dinic=" + String(dinic_ms) + "ms",
            "phases(BFS)=" + String(dinic.phases),
            "augmentations=" + String(dinic.augmentations),
            "| ek=" + String(ek_ms) + "ms",
            "BFS=" + String(ek_passes),
            "augmentations=" + String(ek_aug),
            "| speedup=" + String(speed) + "x",
        )

    if flow_agreed:
        print(
            "  ✅ Dinic and Edmonds-Karp report the same max flow, and it is the known n"
        )
    else:
        failures += 1
        print("  ❌ the two max-flow arms disagree — the timings mean nothing")
    if dinic_fewer_passes:
        print(
            "  ✅ Dinic pays for strictly fewer breadth-first passes at every size — the"
            " level structure, priced"
        )
        print(
            "      every s->L->R->t path here has the same length, so ONE level graph"
            " admits all of them and one blocking flow finishes the problem: 1 BFS against"
            " one per augmenting path, for the same augmentation count"
        )
    else:
        failures += 1
        print("  ❌ Dinic did not use fewer BFS passes; the level-structure claim fails")
    print(
        "  measured growth 128 -> 512 left nodes:",
        "dinic n^" + String(_exponent(first_dinic_ms, last_dinic_ms, 128, 512)),
        "edmonds_karp n^" + String(_exponent(first_ek_ms, last_ek_ms, 128, 512)),
    )

    # ── 4. branch and bound's node census vs 2^n, cross-checked on the DP ────
    print("")
    print("=== MILP: branch and bound vs the frozen knapsack DP, and vs 2^n ===")
    var k_sizes = List[Int]()
    k_sizes.append(12)
    k_sizes.append(18)
    k_sizes.append(24)
    var milp_agreed = True
    var pruned_hard = True
    var last_bb_ms: Float64 = 0.0
    var last_dp_ms: Float64 = 0.0
    var last_n = 0
    for s in range(len(k_sizes)):
        var n = k_sizes[s]
        var wi = _knap_weights(n)
        var vi = _knap_values(n)
        var total_w = 0
        for i in range(n):
            total_w += wi[i]
        var capacity = total_w // 2
        var wf = _to_float(wi)
        var vf = _to_float(vi)

        var t14 = perf_counter_ns()
        var bb = milp_knapsack(vf, wf, Float64(capacity), 200000)
        var t15 = perf_counter_ns()
        var bb_ms = _ms(t15 - t14)

        var t16 = perf_counter_ns()
        var dp = knapsack_01_value(wi, vi, capacity)
        var t17 = perf_counter_ns()
        var dp_ms = _ms(t17 - t16)

        var subsets = 1.0
        for _ in range(n):
            subsets *= 2.0
        var ok = (
            bb.status == MILP_OPTIMAL
            and bb.feasible
            and bb.proven_optimal
            and bb.has_objective
            and fabs(bb.objective - Float64(dp)) <= 1e-9
        )
        if not ok:
            milp_agreed = False
        if Float64(bb.nodes_explored) >= subsets:
            pruned_hard = False
        last_bb_ms = bb_ms
        last_dp_ms = dp_ms
        last_n = n
        print(
            "  n=" + String(n),
            "capacity=" + String(capacity),
            "bb_objective=" + String(bb.objective),
            "dp_objective=" + String(dp),
            "status=" + milp_status_name(bb.status),
        )
        print(
            "      nodes_explored=" + String(bb.nodes_explored),
            "pruned=" + String(bb.nodes_pruned),
            "infeasible=" + String(bb.nodes_infeasible),
            "integral=" + String(bb.nodes_integral),
            "branched=" + String(bb.nodes_branched),
            "2^n=" + String(subsets),
            "reduction=" + String(subsets / Float64(bb.nodes_explored)) + "x",
        )
        print(
            "      relaxation=" + String(bb.relaxation_objective),
            "gap=" + String(bb.gap),
            "max_depth=" + String(bb.max_depth),
            "lp_iterations=" + String(bb.lp_iterations),
            "| bb=" + String(bb_ms) + "ms",
            "frozen_dp=" + String(dp_ms) + "ms",
        )

    if milp_agreed:
        print(
            "  ✅ branch and bound matches the frozen integer DP exactly and reports"
            " proven_optimal"
        )
    else:
        failures += 1
        print("  ❌ branch and bound disagrees with the frozen DP, or did not prove optimality")
    if pruned_hard:
        print("  ✅ the LP bound left far fewer nodes than the 2^n subsets of a blind search")
    else:
        failures += 1
        print("  ❌ the search explored at least 2^n nodes; the bound is not pruning")
    # Said out loud so the node-count reduction is not read as a speed win. It is not one:
    # a table over integer weights beats a tree of LP relaxations on the shape the table can
    # express, and the tree's value is the shapes it cannot — real-valued prices, several
    # constraints, continuous variables alongside the discrete ones.
    if last_dp_ms > 0.0:
        print(
            "  ⚠️  on this shape the frozen integer DP is "
            + String(last_bb_ms / last_dp_ms)
            + "x FASTER than branch and bound at n="
            + String(last_n)
            + " — the claim above is node count and generality, never speed"
        )

    # ── 5. simplex scaling: cost per (iteration x tableau cell) ──────────────
    print("")
    print("=== Simplex scaling: ns per (iteration x tableau cell), dense n x n LP ===")
    var d_sizes = List[Int]()
    d_sizes.append(8)
    d_sizes.append(16)
    d_sizes.append(32)
    d_sizes.append(64)
    var first_per_cell: Float64 = 0.0
    var last_per_cell: Float64 = 0.0
    var first_solve_ms: Float64 = 0.0
    var last_solve_ms: Float64 = 0.0
    var all_optimal = True
    for s in range(len(d_sizes)):
        var n = d_sizes[s]
        var a = _dense_lp_a(n)
        var b = _dense_lp_b(n)
        var c = _dense_lp_c(n)
        var senses = _le(n)
        var reps = 512 // n
        if reps < 2:
            reps = 2
        for _ in range(WARMUP):
            var _wd2 = lp_solve_default(c, a, n, n, senses, b, True)
        var t18 = perf_counter_ns()
        for _ in range(reps):
            var _rd = lp_solve_default(c, a, n, n, senses, b, True)
        var t19 = perf_counter_ns()
        var per_solve_ms = _ms(t19 - t18) / Float64(reps)
        var sol = lp_solve_default(c, a, n, n, senses, b, True)
        if sol.status != LP_OPTIMAL or not sol.has_objective:
            all_optimal = False
        # One pivot touches every cell of the tableau: `rows` rows by
        # `cols + slacks + artificials` = `n + n + n` columns for an all-LE program.
        var cells = n * 3 * n
        var iters = sol.iterations
        if iters < 1:
            iters = 1
        var per_cell = _ns_per(t19 - t18, cells * iters, reps)
        if s == 0:
            first_per_cell = per_cell
            first_solve_ms = per_solve_ms
        last_per_cell = per_cell
        last_solve_ms = per_solve_ms
        print(
            "  n=" + String(n),
            "solve=" + String(per_solve_ms) + "ms",
            "iterations=" + String(iters),
            "cells=" + String(cells),
            "ns/(iter*cell)=" + String(per_cell),
            "objective=" + String(sol.objective),
        )

    if not all_optimal:
        failures += 1
        print("  ❌ a dense LP in the scaling arm did not reach an optimum")
    print(
        "  measured growth 8 -> 64: per solve n^"
        + String(_exponent(first_solve_ms, last_solve_ms, 8, 64))
        + " (that is the pivot count times the tableau area, both rising with n)"
    )
    var cell_growth = last_per_cell / first_per_cell if first_per_cell > 0.0 else 999.0
    if cell_growth <= 3.0:
        # Stated as a RATIO, not as growth: measured here the value FELL (larger tableaux
        # amortise the fixed per-solve cost over more cells), so calling it "grew 0.23x" would
        # describe the opposite of what happened. The gate is that it does not grow.
        print(
            "  ✅ ns per (iteration x cell) ended at "
            + String(cell_growth)
            + "x its starting value across an 8x size increase — a pivot is linear in the"
            + " tableau, and this ratio does not rise"
        )
    else:
        failures += 1
        print(
            "  ❌ ns per (iteration x cell) grew "
            + String(cell_growth)
            + "x; a pivot is not linear in the tableau"
        )

    print("")
    if failures == 0:
        print("BENCH_GATE optimization PASS")
    else:
        print("BENCH_GATE optimization FAIL " + String(failures))
        raise Error("bench_optimization: " + String(failures) + " gate failure(s)")
