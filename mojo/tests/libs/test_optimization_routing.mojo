"""test_optimization_routing.mojo — known-value tests for TSP local search and VRP.

Hand-written. Every expected number below is either computed with pen and paper, given by a
closed form, or produced by an EXHAUSTIVE oracle in this file — never by running the code and
writing down what came out.

The three oracles, in increasing strength:

  * `_brute_force_optimum` enumerates all `(n-1)!` tours through the factorial number system
    (no recursion) and prices each one with the public `tour_length_flat`, i.e. through the
    frozen `combinatorial.tsp_tour_length`. For n <= 6 that is the true global optimum, so
    "the heuristic found the optimum on this instance" is a measured fact here rather than a
    hope. It is also the only honest way to talk about optimality in this package: the module
    itself never claims it.
  * `_no_improving_two_opt` re-derives the 2-opt neighbourhood in TEST code and prices every
    neighbour with `tour_length_flat`. It is what checks the `local_optimum` flag rather than
    trusting it — a certificate is only as good as the weakest condition actually verified.
  * the frozen kernels are called DIRECTLY (`tsp_greedy` / `tsp_tour_length` on the nested
    matrix) and their tour and length are compared entry by entry with `tsp_greedy_flat`,
    which is what shows the driver is a window onto the frozen seed and not a second
    implementation of it.

Load-bearing instances, and why each exists:

  * a 4-city instance with only three distinct tours (103, 6, 105 — all three priced here).
    The greedy seed takes the 103 one, 2-opt takes the 6 one, so `improvement` must be
    exactly 97;
  * an ASYMMETRIC 3-city instance where the two directed cycles cost 201 and 102 and the
    four-edge symmetric 2-opt delta for the reversal is EXACTLY ZERO. Only the asymmetry
    correction (`skew[j] - skew[i]` = -99) makes the improving move visible, so this instance
    fails outright if the reversal silently assumes symmetry;
  * eight points on a unit circle, whose optimal tour is the convex-hull order with the
    closed-form length `8 * 2 * sin(pi/8)`. Nearest-neighbour already finds it there, so the
    test is that the local search REPORTS a local optimum with zero improvement instead of
    inventing a move;
  * a collinear six-city instance where nearest-neighbour scores 62 against an optimum of 48;
  * a triangle-inequality violating matrix, which must still yield a valid permutation;
  * a VRP with two symmetric arms whose optimum (8.0) is hand-computable, plus a time-window
    instance where the cheapest single-vehicle routing MISSES a window and the driver must
    say `no_solution_found` rather than return it.

Exact equality is used wherever the arithmetic is exact — the distances are small integers,
so a tolerance there would hide a real mis-accumulation rather than absorb a rounding. The
circle instance and the sqrt-bearing matrices are compared with an explicit relative epsilon.
"""
from combinatorial import tsp_greedy, tsp_tour_length
from optimization.routing import (
    ROUTE_ABSENT,
    ROUTE_ERR_DISTANCE,
    ROUTE_ERR_INSTANCE,
    ROUTE_ERR_LENGTH_MISMATCH,
    ROUTE_ERR_NOT_A_PERMUTATION,
    ROUTE_ERR_SHAPE,
    ROUTE_ERR_TOO_LARGE,
    ROUTE_INFEASIBLE_PROVEN,
    ROUTE_MAX_NODES,
    ROUTE_MAX_PASSES,
    ROUTE_NO_SOLUTION_FOUND,
    ROUTE_OK,
    ROUTE_OK_LIMIT,
    RouteSolution,
    RouteTour,
    distance_matrix_check,
    route_node_ceiling,
    route_status_name,
    tour_check,
    tour_length_flat,
    tsp_greedy_flat,
    tsp_iterated_local_search,
    tsp_local_search,
    tsp_or_opt,
    tsp_perturb_double_bridge,
    tsp_two_opt,
    vrp_capacity_solve,
    vrp_check,
    vrp_time_window_solve,
    vrp_vehicle_bound,
)
from sparse_numerics.csr import MAX_CSR_DIM
from std.math import abs as fabs, sin, sqrt

comptime PI: Float64 = 3.141592653589793


# ── small builders ────────────────────────────────────────────────────────────


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _close(a: Float64, b: Float64) -> Bool:
    """Relative comparison for the sqrt-bearing instances only."""
    var scale = fabs(a)
    if fabs(b) > scale:
        scale = fabs(b)
    return fabs(a - b) <= 1e-12 * (1.0 + scale)


fn _line_matrix(xs: List[Float64]) -> List[Float64]:
    """Flat |x_i - x_j| matrix for collinear points."""
    var out = List[Float64]()
    for i in range(len(xs)):
        for j in range(len(xs)):
            out.append(fabs(xs[i] - xs[j]))
    return out^


fn _circle_matrix(n: Int) -> List[Float64]:
    """Euclidean distances between `n` points equally spaced on the unit circle."""
    var xs = List[Float64]()
    var ys = List[Float64]()
    for k in range(n):
        var angle = 2.0 * PI * Float64(k) / Float64(n)
        xs.append(_cos(angle))
        ys.append(sin(angle))
    var out = List[Float64]()
    for i in range(n):
        for j in range(n):
            var dx = xs[i] - xs[j]
            var dy = ys[i] - ys[j]
            out.append(sqrt(dx * dx + dy * dy))
    return out^


fn _cos(x: Float64) -> Float64:
    """cos via sin, so only one transcendental is imported."""
    return sin(x + 0.5 * PI)


fn _nested_of(distance: List[Float64], n: Int) -> List[List[Float64]]:
    var out = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(distance[i * n + j])
        out.append(row^)
    return out^


# ── oracles ───────────────────────────────────────────────────────────────────


fn _factorial(m: Int) -> Int:
    var out = 1
    for k in range(2, m + 1):
        out *= k
    return out


fn _kth_permutation(m: Int, k: Int) -> List[Int]:
    """The `k`-th permutation of `0..m-1` in factorial-number-system order. No recursion."""
    var pool = List[Int]()
    for i in range(m):
        pool.append(i)
    var out = List[Int]()
    var rest = k
    for pos in range(m):
        var slots = m - pos
        var block = _factorial(slots - 1)
        var pick = rest // block
        rest = rest % block
        out.append(pool[pick])
        var trimmed = List[Int]()
        for i in range(len(pool)):
            if i != pick:
                trimmed.append(pool[i])
        pool = trimmed^
    return out^


fn _brute_force_optimum(distance: List[Float64], n: Int) -> Float64:
    """Exhaustive minimum over all `(n-1)!` closed tours, priced by `tour_length_flat`.

    The true global optimum, so the heuristics can be checked against it rather than against
    each other. Priced through the public wrapper on purpose: the oracle and the driver then
    agree on what a tour length IS, and only the search differs.
    """
    var best = 0.0
    var have = False
    var total = _factorial(n - 1)
    for k in range(total):
        var tail = _kth_permutation(n - 1, k)
        var tour = List[Int]()
        tour.append(0)
        for i in range(len(tail)):
            tour.append(tail[i] + 1)
        tour.append(0)
        var scored = tour_length_flat(distance, n, tour)
        if scored.status != ROUTE_OK or not scored.has_value:
            continue
        if not have or scored.value < best:
            best = scored.value
            have = True
    return best


fn _no_improving_two_opt(distance: List[Float64], n: Int, tour: List[Int]) -> Bool:
    """True when no 2-opt neighbour of `tour` is strictly shorter. Re-derived here.

    This is what CHECKS the `local_optimum` flag. The neighbourhood is rebuilt from the
    definition (reverse every span `i..j` with `1 <= i < j <= n-1`) and every neighbour is
    priced by `tour_length_flat`, so a bug shared between the delta arithmetic and this test
    is not possible — no delta appears here at all.
    """
    var base = tour_length_flat(distance, n, tour)
    if base.status != ROUTE_OK or not base.has_value:
        return False
    for i in range(1, n):
        for j in range(i + 1, n):
            var candidate = List[Int]()
            for k in range(n):
                candidate.append(tour[k])
            var lo = i
            var hi = j
            while lo < hi:
                var tmp = candidate[lo]
                candidate[lo] = candidate[hi]
                candidate[hi] = tmp
                lo += 1
                hi -= 1
            candidate.append(candidate[0])
            var scored = tour_length_flat(distance, n, candidate)
            if scored.status != ROUTE_OK or not scored.has_value:
                return False
            if scored.value < base.value - 1e-12 * (1.0 + fabs(base.value)):
                return False
    return True


fn _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for k in range(len(a)):
        if a[k] != b[k]:
            return False
    return True


fn _partitions(stops: List[Int], route_start: List[Int], n_routes: Int) -> Bool:
    """THE layout oracle: `n_routes + 1` offsets that partition `stops` exactly.

    Re-derived from `RouteSolution`'s documented contract in TEST code so it cannot inherit the
    module's own idea of the layout. Four conditions, and the loop a caller writes
    (`for v in range(n_routes_used): stops[route_start[v] : route_start[v + 1]]`) is correct if
    and only if all four hold: the offset count IS the route count, the offsets start at 0, they
    end at `len(stops)`, and they strictly increase — no empty slot, no gap, no overlap.

    This is the assertion that catches the defect it was written for: `route_start = [0, 3, 3, 5,
    8]` beside `n_routes_used = 3` fails it on the count (5 offsets, 3 routes) and on strictness
    (`3 -> 3`), while every other field in the struct looked healthy.
    """
    if n_routes < 0:
        return False
    if len(route_start) != n_routes + 1:
        return False
    if route_start[0] != 0:
        return False
    if route_start[n_routes] != len(stops):
        return False
    for v in range(n_routes):
        if route_start[v + 1] <= route_start[v]:
            return False
    return True


fn _read_as_documented(sol: RouteSolution) -> List[Int]:
    """The customers a caller reaches by following the struct's documented layout, in order.

    Literally `for v in range(n_routes_used): stops[route_start[v] : route_start[v + 1]]`. On the
    defect this pins, this returned `[1, 5, 3, 7, 4]` for `stops = [1, 5, 3, 7, 4, 6, 8, 2]` —
    three customers silently dropped — which is how "an answer whose route boundaries are wrong"
    becomes visible as a missing-freight count rather than a crash.
    """
    var out = List[Int]()
    if sol.n_routes_used < 0 or len(sol.route_start) < sol.n_routes_used + 1:
        return out^
    for v in range(sol.n_routes_used):
        for k in range(sol.route_start[v], sol.route_start[v + 1]):
            out.append(sol.stops[k])
    return out^


fn _read_offsets_as_documented(sol: RouteSolution) -> List[Int]:
    """Offsets into `_read_as_documented(sol)`, so the reconstruction can be re-audited."""
    var out = List[Int]()
    out.append(0)
    if sol.n_routes_used < 0 or len(sol.route_start) < sol.n_routes_used + 1:
        return out^
    var acc = 0
    for v in range(sol.n_routes_used):
        acc += sol.route_start[v + 1] - sol.route_start[v]
        out.append(acc)
    return out^


fn _status_matches_local_opt_tour(r: RouteTour) -> Bool:
    """`ROUTE_OK` if and only if `local_optimum` — a status may not deny a field beside it.

    Code 120's name is `verified_local_optimum_of_the_declared_moves_not_proven_optimal`, so
    returning it with `local_optimum = False` is one value making two contradictory claims and a
    caller can act on neither.
    """
    if r.status != ROUTE_OK and r.status != ROUTE_OK_LIMIT:
        return True
    return (r.status == ROUTE_OK) == r.local_optimum


fn _status_matches_local_opt_solution(s: RouteSolution) -> Bool:
    """The same self-consistency requirement for a routing."""
    if s.status != ROUTE_OK and s.status != ROUTE_OK_LIMIT:
        return True
    return (s.status == ROUTE_OK) == s.local_optimum


fn _lattice(n: Int) -> List[Float64]:
    """`n` distinct points on a deterministic 2D lattice, Euclidean. No randomness anywhere.

    Used for the WORK-BOUND probes, which need an instance big enough that an unclamped effort
    knob would be a bomb: 13 * (k % 7) + k // 7 and 11 * (k // 7) + 2 * (k % 7) are injective on
    k, so no two cities coincide and no off-diagonal distance is zero.
    """
    var xs = List[Float64]()
    var ys = List[Float64]()
    for k in range(n):
        xs.append(Float64(k % 7) * 13.0 + Float64(k // 7))
        ys.append(Float64(k // 7) * 11.0 + Float64(k % 7) * 2.0)
    return _euclid(xs, ys)


fn _ramp_demand(n: Int) -> List[Float64]:
    """Depot 0.0 then 1..4 cycling, so no single demand can exceed the capacities used here."""
    var out = List[Float64]()
    out.append(0.0)
    for k in range(1, n):
        out.append(Float64(1 + (k % 4)))
    return out^


# ── the instances ─────────────────────────────────────────────────────────────


fn _four_city() -> List[Float64]:
    """4 cities, 3 distinct tours: 0-1-2-3-0 = 103, 0-1-3-2-0 = 6, 0-2-1-3-0 = 105.

    Symmetric, with d[3][0] = 100 as the trap the greedy seed walks into: nearest-neighbour
    takes 0-1-2-3 and then has to pay 100 to get home.
    """
    return _floats(
        0.0, 1.0, 2.0, 100.0,
        1.0, 0.0, 1.0, 2.0,
        2.0, 1.0, 0.0, 1.0,
        100.0, 2.0, 1.0, 0.0,
    )


fn _asymmetric_three() -> List[Float64]:
    """3 cities, two directed cycles: 0->1->2->0 = 102 and 0->2->1->0 = 201.

    d[0][1] = 100, d[1][2] = 1, d[2][0] = 1 (cycle A = 102);
    d[0][2] = 1, d[2][1] = 100, d[1][0] = 100 (cycle B = 201).

    Nearest-neighbour from 0 takes the 1-cost arc to city 2 and is then trapped into B = 201.
    The 2-opt reversal that fixes it has a four-edge symmetric delta of EXACTLY ZERO
    (d[0][1] + d[2][0] - d[0][2] - d[1][0] = 100 + 1 - 1 - 100), so it is invisible without
    the asymmetry correction, which is -99 here. That is why this instance exists.
    """
    return _floats(
        0.0, 100.0, 1.0,
        100.0, 0.0, 1.0,
        1.0, 100.0, 0.0,
    )


fn _six_on_a_line() -> List[Float64]:
    """Collinear cities at x = 0, 1, -2, 4, -8, 16.

    Nearest-neighbour scores 1+3+6+12+24+16 = 62. The optimum is the sweep
    -8 -> -2 -> 0 -> 1 -> 4 -> 16 and back, i.e. 2 * (16 - (-8)) = 48 for any collinear
    instance, which `_brute_force_optimum` confirms independently.
    """
    return _line_matrix(_floats(0.0, 1.0, -2.0, 4.0, -8.0, 16.0))


fn _triangle_violating() -> List[Float64]:
    """3 cities with d[1][2] = 10 against d[1][0] + d[0][2] = 2. Symmetric.

    Every 3-city tour is the same cycle, so the length is 1 + 10 + 1 = 12 whatever the search
    does; what is tested is that a valid permutation still comes back and that
    `distance_matrix_check` reports the violation as 8 rather than rejecting the instance.
    """
    return _floats(
        0.0, 1.0, 1.0,
        1.0, 0.0, 10.0,
        1.0, 10.0, 0.0,
    )


fn _two_arms() -> List[Float64]:
    """Depot at 0, customers at x = 1, 2, -1, -2. Travel cost = |dx|.

    With demand 5 each and capacity 10, exactly two customers fit per vehicle, so the optimum
    is one vehicle per arm: (0->1->2->0) = 4 and (0->3->4->0) = 4, total 8.
    """
    return _line_matrix(_floats(0.0, 1.0, 2.0, -1.0, -2.0))


fn _window_line() -> List[Float64]:
    """Depot at 0, customers at x = 1, 2, -1. Travel time = distance."""
    return _line_matrix(_floats(0.0, 1.0, 2.0, -1.0))


fn _euclid(xs: List[Float64], ys: List[Float64]) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(xs)):
        for j in range(len(xs)):
            var dx = xs[i] - xs[j]
            var dy = ys[i] - ys[j]
            out.append(sqrt(dx * dx + dy * dy))
    return out^


fn _scattered() -> List[Float64]:
    """Depot at the origin plus 8 scattered customers, Euclidean.

    Chosen because the CONSTRUCTION order matters here: with `max_passes = 0` the answer is
    the raw cheapest-insertion result, so a different keyed insertion order shows up directly
    in the total. That is what makes the seed's reach into the answer observable.
    """
    return _euclid(
        _floats(0.0, 3.0, 4.0, 1.0, -3.0, -4.0, -1.0, 2.0, -2.0),
        _floats(0.0, 0.0, 1.0, 3.0, 0.0, 1.0, -3.0, -2.0, 2.0),
    )


fn _nine_windowed() -> List[Float64]:
    """The 9-city symmetric matrix from the route-layout reproduction, verbatim.

    Kept exactly as reported so the regression is the finding's own instance and not a
    re-derivation of it: with `capacity = 7`, `n_vehicles = 4`, `max_passes = 60`,
    `n_restarts = 3` and `seed = 11`, relocation empties one route, and the solver used to
    return `n_routes_used = 3` beside `route_start = [0, 3, 3, 5, 8]`.
    """
    return _floats(
        0.0, 20.808652046296352, 78.31347265523236, 109.1237828955487, 61.55485358605382,
        86.83317338428775, 46.48655719675, 46.2709412051008, 70.06425622000071,
        20.808652046296352, 0.0, 90.55385138155316, 106.21205202094427,
        62.24146527851192, 83.40863264500773, 64.49806198649529, 33.61547262833296,
        84.40379138208375,
        78.31347265523236, 90.55385138155316, 0.0, 75.23961719703958,
        48.104053884311114, 65.55150646638164, 40.49691346633326, 82.76472678572652,
        12.806248474425109,
        109.1237828955487, 106.21205202094427, 75.23961719703958, 0.0, 48.25971404924107,
        22.803508502014125, 100.96038825895516, 76.05918750624946, 85.02352615450205,
        61.55485358605382, 62.24146527851192, 48.104053884311114, 48.25971404924107, 0.0,
        27.513632979639873, 57.0087712613905, 40.199502489404914, 51.47815070779405,
        86.83317338428775, 83.40863264500773, 65.55150646638164, 22.803508502014125,
        27.513632979639873, 0.0, 83.60023923219018, 53.71219600767081, 72.78049189533726,
        46.48655719675, 64.49806198649529, 40.49691346633326, 100.96038825895516,
        57.0087712613905, 83.60023923219018, 0.0, 72.40165743651887, 28.635642129169064,
        46.2709412051008, 33.61547262833296, 82.76472678572652, 76.05918750624946,
        40.199502489404914, 53.71219600767081, 72.40165743651887, 0.0, 81.4002457051925,
        70.06425622000071, 84.40379138208375, 12.806248474425109, 85.02352615450205,
        51.47815070779405, 72.78049189533726, 28.635642129169064, 81.4002457051925, 0.0,
    )


fn main() raises:
    var passed: Int = 0
    var failed: Int = 0
    print("[optimization.routing]")

    # ── status vocabulary: ten codes, ten distinct names ─────────────────────
    # A duplicated name makes two defects indistinguishable in a log, which is the same
    # failure as a duplicated code — the defect rule 4e exists for.
    var names = List[String]()
    for code in range(120, 130):
        names.append(route_status_name(code))
    var distinct = True
    for i in range(len(names)):
        if names[i] == "unknown_status_" + String(120 + i):
            distinct = False
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                distinct = False
    if (
        distinct
        and route_status_name(119) == "unknown_status_119"
        and route_status_name(130) == "unknown_status_130"
        and route_status_name(0) == "unknown_status_0"
    ):
        passed += 1
        print("  ✅ 10 status codes 120-129 have distinct names; outside the range is unknown")
    else:
        failed += 1
        print("  ❌ status names are not distinct or leak outside 120-129")

    # ── the ceiling is DERIVED from the one shared ceiling, not invented ─────
    if (
        route_node_ceiling() == ROUTE_MAX_NODES
        and ROUTE_MAX_NODES == 4096
        and 2 * ROUTE_MAX_NODES * ROUTE_MAX_NODES <= MAX_CSR_DIM
    ):
        passed += 1
        print("  ✅ node ceiling 4096: two live n^2 arrays fit inside MAX_CSR_DIM")
    else:
        failed += 1
        print("  ❌ node ceiling arithmetic:", route_node_ceiling(), MAX_CSR_DIM)

    # ── shape guards: the generated A-Z call shape must not index past the end ─
    # The generated suite calls every contract function with a 5-element list and n = 5, so
    # `distance[24]` on a 5-element list is what a missing guard would do here.
    var five = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var az_two_opt = tsp_two_opt(five, 5, 5)
    var az_greedy = tsp_greedy_flat(five, 5)
    var az_len = tour_length_flat(five, 5, _ints(1, 2, 3, 4, 5))
    var az_census = distance_matrix_check(five, 5)
    var az_ils = tsp_iterated_local_search(five, 5, 5, 5, 5, UInt64(42))
    var az_perturb = tsp_perturb_double_bridge(five, 5, _ints(1, 2, 3, 4, 5), UInt64(42), 5)
    if (
        az_two_opt.status == ROUTE_ERR_SHAPE
        and len(az_two_opt.tour) == 0
        and not az_two_opt.has_length
        and az_two_opt.improvement == ROUTE_ABSENT
        and az_greedy.status == ROUTE_ERR_SHAPE
        and az_len.status == ROUTE_ERR_SHAPE
        and not az_len.has_value
        and az_census.status == ROUTE_ERR_SHAPE
        and az_ils.status == ROUTE_ERR_SHAPE
        and az_perturb.status == ROUTE_ERR_SHAPE
    ):
        passed += 1
        print("  ✅ n=5 against a 5-cell matrix is rejected everywhere, nothing indexed")
    else:
        failed += 1
        print("  ❌ A-Z shape guard:", az_two_opt.status, az_greedy.status, az_len.status)

    # ── the wrapping multiply is not a bound ─────────────────────────────────
    # `n * n == len(distance)` wraps: 3037000500^2 overflows Int. The ceiling is checked
    # BEFORE any product, so this is `dimension_too_large` and never an index.
    var wrap = tsp_two_opt(_floats(0.0, 1.0), 3037000500, 5)
    var over = tsp_two_opt(_floats(0.0), ROUTE_MAX_NODES + 1, 5)
    var zero = tsp_two_opt(_floats(), 0, 5)
    if (
        wrap.status == ROUTE_ERR_TOO_LARGE
        and over.status == ROUTE_ERR_TOO_LARGE
        and zero.status == ROUTE_ERR_SHAPE
        and len(wrap.tour) == 0
    ):
        passed += 1
        print("  ✅ a wrapping n^2 and an over-ceiling n are refused; n=0 has no tour")
    else:
        failed += 1
        print("  ❌ dimension bounds:", wrap.status, over.status, zero.status)

    # ── the frozen greedy's 1e308 sentinel is a crash, so it is refused ──────
    # `tsp_greedy` seeds best_dist at 1e308 and returns -1 when nothing is strictly closer,
    # then writes visited[-1]. Distances are therefore capped at 1e300.
    var sentinel = _floats(
        0.0, 1e308, 1e308,
        1e308, 0.0, 1e308,
        1e308, 1e308, 0.0,
    )
    var nan_matrix = _floats(0.0, 1.0, 1.0, 0.0)
    nan_matrix[1] = 0.0 / 0.0
    var negative = _floats(0.0, -1.0, -1.0, 0.0)
    var s_res = tsp_two_opt(sentinel, 3, 10)
    var n_res = tsp_two_opt(nan_matrix, 2, 10)
    var neg_res = tsp_two_opt(negative, 2, 10)
    var s_census = distance_matrix_check(sentinel, 3)
    if (
        s_res.status == ROUTE_ERR_DISTANCE
        and n_res.status == ROUTE_ERR_DISTANCE
        and neg_res.status == ROUTE_ERR_DISTANCE
        and s_census.status == ROUTE_ERR_DISTANCE
        and s_census.defect_index == 1
        and len(s_res.tour) == 0
    ):
        passed += 1
        print("  ✅ 1e308, NaN and negative distances are refused by name, not indexed")
    else:
        failed += 1
        print("  ❌ distance validation:", s_res.status, n_res.status, neg_res.status)

    # ── four cities, all three tours priced by hand ──────────────────────────
    var four = _four_city()
    var t_abcd = tour_length_flat(four, 4, _ints(0, 1, 2, 3, 0))
    var t_abdc = tour_length_flat(four, 4, _ints(0, 1, 3, 2, 0))
    var t_acbd = tour_length_flat(four, 4, _ints(0, 2, 1, 3, 0))
    if (
        t_abcd.value == 103.0
        and t_abdc.value == 6.0
        and t_acbd.value == 105.0
        and t_abcd.has_value
        and _brute_force_optimum(four, 4) == 6.0
    ):
        passed += 1
        print("  ✅ the three distinct 4-city tours cost 103, 6, 105; the optimum is 6")
    else:
        failed += 1
        print("  ❌ 4-city enumeration:", t_abcd.value, t_abdc.value, t_acbd.value)

    # ── the frozen seed, reported honestly, and identical to the frozen call ─
    var nested_four = _nested_of(four, 4)
    var frozen_tour = tsp_greedy(nested_four)
    var frozen_len = tsp_tour_length(nested_four, frozen_tour)
    var seed_four = tsp_greedy_flat(four, 4)
    # The status must AGREE with `local_optimum`: nearest-neighbour is not a local optimum of
    # anything, so the code cannot be 120, whose name reads
    # `verified_local_optimum_of_the_declared_moves_not_proven_optimal`.
    if (
        seed_four.status == ROUTE_OK_LIMIT
        and seed_four.tour_length == 103.0
        and seed_four.tour_length == frozen_len
        and _same_ints(seed_four.tour, frozen_tour)
        and seed_four.is_permutation
        and not seed_four.local_optimum
        and seed_four.improvement == 0.0
    ):
        passed += 1
        print("  ✅ tsp_greedy_flat is the frozen tour exactly: 103, and claims no optimality")
    else:
        failed += 1
        print("  ❌ greedy window:", seed_four.status, seed_four.tour_length, frozen_len)

    # ── 2-opt takes the 103 tour to the 6 tour, and says what it bought ──────
    var opt_four = tsp_two_opt(four, 4, 100)
    if (
        opt_four.status == ROUTE_OK
        and opt_four.tour_length == 6.0
        and opt_four.seed_length == 103.0
        and opt_four.improvement == 97.0
        and opt_four.local_optimum
        and opt_four.is_permutation
        and _same_ints(opt_four.tour, _ints(0, 1, 3, 2, 0))
        and opt_four.moves_applied == 1
        and opt_four.two_opt_enabled
        and not opt_four.or_opt_enabled
        and opt_four.tour_length == _brute_force_optimum(four, 4)
    ):
        passed += 1
        print("  ✅ 2-opt: 103 -> 6 in one move, improvement 97, equals the exhaustive optimum")
    else:
        failed += 1
        print(
            "  ❌ 2-opt on 4 cities:",
            opt_four.status,
            opt_four.tour_length,
            opt_four.improvement,
            opt_four.moves_applied,
        )

    # ── the local_optimum flag is CHECKED, not trusted ──────────────────────
    if _no_improving_two_opt(four, 4, opt_four.tour) and opt_four.local_optimum:
        passed += 1
        print("  ✅ the claimed 2-opt local optimum survives an independent full rescan")
    else:
        failed += 1
        print("  ❌ local_optimum claimed but a rescan found an improving move")

    # ── monotone non-increase across passes, and an honest pass limit ────────
    var line = _six_on_a_line()
    var prev_len = 0.0
    var monotone = True
    var saw_limit = False
    var saw_final = False
    var final_len = 0.0
    for cap in range(0, 9):
        var run = tsp_local_search(line, 6, cap, True, True, 3)
        if run.status != ROUTE_OK and run.status != ROUTE_OK_LIMIT:
            monotone = False
            continue
        if not run.is_permutation:
            monotone = False
        if cap > 0 and run.tour_length > prev_len:
            monotone = False
        if run.status == ROUTE_OK_LIMIT:
            saw_limit = True
            if run.local_optimum:
                monotone = False
        if run.status == ROUTE_OK and run.local_optimum:
            saw_final = True
            final_len = run.tour_length
        prev_len = run.tour_length
    if monotone and saw_limit and saw_final:
        passed += 1
        print("  ✅ tour length is non-increasing in max_passes; the cap reports OK_LIMIT")
    else:
        failed += 1
        print("  ❌ monotonicity:", monotone, saw_limit, saw_final, final_len)

    # ── the collinear instance: 62 greedy, 48 optimal, oracle agrees ─────────
    var line_seed = tsp_greedy_flat(line, 6)
    var line_opt = _brute_force_optimum(line, 6)
    var line_search = tsp_local_search(line, 6, 200, True, True, 3)
    if (
        line_seed.tour_length == 62.0
        and line_opt == 48.0
        and line_search.status == ROUTE_OK
        and line_search.is_permutation
        and line_search.tour_length == 48.0
        and line_search.improvement == 14.0
        and line_search.local_optimum
        and _no_improving_two_opt(line, 6, line_search.tour)
    ):
        passed += 1
        print("  ✅ collinear 6-city: greedy 62, exhaustive optimum 48, search reaches 48")
    else:
        failed += 1
        print(
            "  ❌ collinear instance:",
            line_seed.tour_length,
            line_opt,
            line_search.tour_length,
            line_search.status,
        )

    # ── or-opt alone is a real move set, and reports itself as one ───────────
    var line_or = tsp_or_opt(line, 6, 200, 3)
    var line_two = tsp_two_opt(line, 6, 200)
    if (
        line_or.status == ROUTE_OK
        and line_or.is_permutation
        and line_or.or_opt_enabled
        and not line_or.two_opt_enabled
        and line_or.max_segment == 3
        and line_or.tour_length <= 62.0
        and line_two.status == ROUTE_OK
        and line_two.is_permutation
        and line_two.tour_length <= 62.0
        and tour_check(line_or.tour, 6).is_permutation
        and tour_check(line_two.tour, 6).is_permutation
    ):
        passed += 1
        print("  ✅ or-opt and 2-opt each return a verified permutation no worse than the seed")
    else:
        failed += 1
        print("  ❌ single move families:", line_or.status, line_or.tour_length, line_two.tour_length)

    # ── an empty move set must NOT claim a local optimum ────────────────────
    # "No improving move exists" is a claim about a scan. With both families off, or with an
    # Or-opt-only run on 3 cities (whose Or-opt neighbourhood is empty), nothing was scanned,
    # so `local_optimum` must be False and `moves_evaluated` must be 0 to say why. The one
    # honest exception is n <= 2, where there is exactly one tour.
    var nothing = tsp_local_search(line, 6, 100, False, False, 3)
    var vacuous_or = tsp_or_opt(_triangle_violating(), 3, 100, 2)
    var one_city = tsp_two_opt(_floats(0.0), 1, 100)
    var two_city = tsp_two_opt(_floats(0.0, 3.0, 4.0, 0.0), 2, 100)
    # A double bridge needs four segments, so on 3 cities no kick exists: the tour must come
    # back untouched with `kicks == 0` rather than counting a kick that never happened.
    var no_kick = tsp_perturb_double_bridge(
        _triangle_violating(), 3, _ints(0, 1, 2, 0), UInt64(9), 0
    )
    if (
        no_kick.status == ROUTE_OK_LIMIT
        and no_kick.kicks == 0
        and no_kick.improvement == 0.0
        and _same_ints(no_kick.tour, _ints(0, 1, 2, 0))
        and nothing.status == ROUTE_OK_LIMIT
        and not nothing.local_optimum
        and nothing.moves_evaluated == 0
        and nothing.tour_length == 62.0
        and nothing.improvement == 0.0
        and vacuous_or.status == ROUTE_OK_LIMIT
        and vacuous_or.moves_evaluated == 0
        and not vacuous_or.local_optimum
        and vacuous_or.is_permutation
        and one_city.status == ROUTE_OK
        and one_city.local_optimum
        and one_city.tour_length == 0.0
        and _same_ints(one_city.tour, _ints(0, 0))
        and two_city.status == ROUTE_OK
        and two_city.local_optimum
        and two_city.tour_length == 7.0
        and _same_ints(two_city.tour, _ints(0, 1, 0))
    ):
        passed += 1
        print("  ✅ an unsearched neighbourhood reports no local optimum; n<=2 is the exception")
    else:
        failed += 1
        print(
            "  ❌ vacuous local optimum:",
            nothing.local_optimum,
            nothing.moves_evaluated,
            vacuous_or.local_optimum,
            one_city.local_optimum,
            two_city.tour_length,
        )

    # ── max_segment is reported CLAMPED to what was actually searched ───────
    # A segment of n-1 cities has nowhere to be reinserted, so asking for 9 on 6 cities
    # searches 4. Reporting 9 would overstate the neighbourhood that was covered.
    var big_seg = tsp_or_opt(line, 6, 100, 9)
    var zero_seg = tsp_or_opt(line, 6, 100, 0)
    if (
        big_seg.max_segment == 4
        and big_seg.status == ROUTE_OK
        and big_seg.is_permutation
        and zero_seg.max_segment == 1
        and zero_seg.is_permutation
    ):
        passed += 1
        print("  ✅ max_segment 9 on 6 cities is reported as the 4 that were searched")
    else:
        failed += 1
        print("  ❌ max_segment clamping:", big_seg.max_segment, zero_seg.max_segment)

    # ── asymmetry: the correction is what makes the improving move visible ───
    var asym = _asymmetric_three()
    var asym_seed = tsp_greedy_flat(asym, 3)
    var asym_opt = tsp_two_opt(asym, 3, 50)
    var asym_census = distance_matrix_check(asym, 3)
    var cycle_a = tour_length_flat(asym, 3, _ints(0, 1, 2, 0))
    var cycle_b = tour_length_flat(asym, 3, _ints(0, 2, 1, 0))
    if (
        cycle_a.value == 102.0
        and cycle_b.value == 201.0
        and asym_seed.tour_length == 201.0
        and asym_opt.status == ROUTE_OK
        and asym_opt.tour_length == 102.0
        and asym_opt.improvement == 99.0
        and _same_ints(asym_opt.tour, _ints(0, 1, 2, 0))
        and asym_opt.asymmetric
        and asym_opt.max_asymmetry == 99.0
        and asym_census.status == ROUTE_OK
        and not asym_census.symmetric
        and asym_census.max_asymmetry == 99.0
        and asym_census.asymmetry_row == 1
        and asym_census.asymmetry_col == 2
    ):
        passed += 1
        print("  ✅ asymmetric 3-city: 201 -> 102 via the -99 skew correction, asymmetry reported")
    else:
        failed += 1
        print(
            "  ❌ asymmetric handling:",
            asym_seed.tour_length,
            asym_opt.tour_length,
            asym_opt.max_asymmetry,
            asym_census.symmetric,
        )

    # ── eight points on a circle: the closed form, and no invented move ──────
    var circle = _circle_matrix(8)
    var hull = 8.0 * 2.0 * sin(PI / 8.0)
    var circle_seed = tsp_greedy_flat(circle, 8)
    var circle_search = tsp_local_search(circle, 8, 200, True, True, 3)
    var circle_census = distance_matrix_check(circle, 8)
    if (
        _close(circle_seed.tour_length, hull)
        and circle_search.status == ROUTE_OK
        and _close(circle_search.tour_length, hull)
        and circle_search.local_optimum
        and circle_search.moves_applied == 0
        and circle_search.improvement == 0.0
        and circle_search.is_permutation
        and _same_ints(circle_search.tour, _ints(0, 1, 2, 3, 4, 5, 6, 7, 0))
        and circle_census.symmetric
        and circle_census.triangle_checked
        and circle_census.triangle_ok
    ):
        passed += 1
        print("  ✅ circle of 8: hull order, length 8*2*sin(pi/8), zero moves, zero improvement")
    else:
        failed += 1
        print(
            "  ❌ circle instance:",
            circle_seed.tour_length,
            hull,
            circle_search.tour_length,
            circle_search.moves_applied,
        )

    # ── a violated triangle inequality still yields a permutation ───────────
    var tri = _triangle_violating()
    var tri_search = tsp_local_search(tri, 3, 50, True, True, 2)
    var tri_census = distance_matrix_check(tri, 3)
    var tri_check = tour_check(tri_search.tour, 3)
    if (
        tri_search.status == ROUTE_OK
        and tri_search.is_permutation
        and tri_search.tour_length == 12.0
        and tri_check.is_permutation
        and tri_check.closed
        and tri_census.status == ROUTE_OK
        and tri_census.triangle_checked
        and not tri_census.triangle_ok
        and tri_census.max_triangle_violation == 8.0
    ):
        passed += 1
        print("  ✅ triangle inequality violated by 8: still a valid tour of length 12")
    else:
        failed += 1
        print(
            "  ❌ triangle violation:",
            tri_search.status,
            tri_search.tour_length,
            tri_census.max_triangle_violation,
        )

    # ── tour_check and the wrapper that stops the frozen kernel crashing ─────
    # `tsp_tour_length` indexes distances[tour[i]][tour[i+1]] with no range check, so the
    # out-of-range tour below is an uncatchable crash if it reaches the frozen kernel.
    var good = tour_check(_ints(0, 1, 2, 3, 0), 4)
    var open_tour = tour_check(_ints(0, 1, 2, 3), 4)
    var repeated = tour_check(_ints(0, 1, 1, 3, 0), 4)
    var unclosed = tour_check(_ints(0, 1, 2, 3, 1), 4)
    var out_of_range = tour_length_flat(four, 4, _ints(0, 1, 9, 3, 0))
    var partial = tour_length_flat(four, 4, _ints(0, 1, 2, 0))
    if (
        good.status == ROUTE_OK
        and good.is_permutation
        and good.closed
        and open_tour.status == ROUTE_ERR_NOT_A_PERMUTATION
        and not open_tour.length_ok
        and repeated.status == ROUTE_ERR_NOT_A_PERMUTATION
        and repeated.n_repeated == 1
        and repeated.n_missing == 1
        and repeated.first_missing_city == 2
        and unclosed.is_permutation
        and not unclosed.closed
        and unclosed.status == ROUTE_ERR_NOT_A_PERMUTATION
        and out_of_range.status == ROUTE_ERR_NOT_A_PERMUTATION
        and not out_of_range.has_value
        and partial.status == ROUTE_ERR_NOT_A_PERMUTATION
        and not partial.has_value
    ):
        passed += 1
        print("  ✅ tour_check names which condition failed; a bad tour never reaches the kernel")
    else:
        failed += 1
        print(
            "  ❌ tour validation:",
            good.status,
            open_tour.status,
            repeated.n_repeated,
            out_of_range.status,
        )

    # ── determinism: the perturbation is a pure function of (seed, kick) ─────
    var start_tour = _ints(0, 1, 2, 3, 4, 5, 0)
    var kick_a1 = tsp_perturb_double_bridge(line, 6, start_tour, UInt64(7), 0)
    var kick_a2 = tsp_perturb_double_bridge(line, 6, start_tour, UInt64(7), 0)
    var kick_b = tsp_perturb_double_bridge(line, 6, start_tour, UInt64(2), 0)
    var kick_next = tsp_perturb_double_bridge(line, 6, start_tour, UInt64(7), 1)
    # A single seed pair could differ by coincidence, so the seed's REACH is measured too:
    # eight seeds at the same kick index must address several distinct cut triples, and every
    # one of them must still be a permutation.
    var kicked = List[List[Int]]()
    var all_perms = True
    for s in range(1, 9):
        var k = tsp_perturb_double_bridge(line, 6, start_tour, UInt64(s), 0)
        if k.status != ROUTE_OK_LIMIT or not k.is_permutation:
            all_perms = False
        kicked.append(k.tour.copy())
    var n_distinct = 0
    for i in range(len(kicked)):
        var fresh = True
        for j in range(i):
            if _same_ints(kicked[i], kicked[j]):
                fresh = False
        if fresh:
            n_distinct += 1
    # A kick searched nothing, so its status is the one that says so.
    if (
        kick_a1.status == ROUTE_OK_LIMIT
        and _same_ints(kick_a1.tour, kick_a2.tour)
        and kick_a1.tour_length == kick_a2.tour_length
        and kick_a1.is_permutation
        and not _same_ints(kick_a1.tour, kick_b.tour)
        and not _same_ints(kick_a1.tour, kick_next.tour)
        and kick_b.is_permutation
        and kick_next.is_permutation
        and not kick_a1.local_optimum
        and all_perms
        and n_distinct >= 4
    ):
        passed += 1
        print(
            "  ✅ double-bridge: same (seed, kick) bit-identical; 8 seeds reach",
            n_distinct,
            "distinct tours",
        )
    else:
        failed += 1
        print(
            "  ❌ kick determinism:",
            kick_a1.status,
            kick_a1.tour_length,
            kick_b.tour_length,
            n_distinct,
            all_perms,
        )

    # ── determinism: the whole iterated search reproduces, and kicks help ────
    var ils_a1 = tsp_iterated_local_search(line, 6, 200, 3, 12, UInt64(11))
    var ils_a2 = tsp_iterated_local_search(line, 6, 200, 3, 12, UInt64(11))
    var ils_b = tsp_iterated_local_search(line, 6, 200, 3, 12, UInt64(2026))
    if (
        ils_a1.status == ROUTE_OK
        and _same_ints(ils_a1.tour, ils_a2.tour)
        and ils_a1.tour_length == ils_a2.tour_length
        and ils_a1.moves_evaluated == ils_a2.moves_evaluated
        and ils_a1.kicks == 12
        and ils_a1.is_permutation
        and ils_b.is_permutation
        and ils_a1.tour_length == 48.0
        and ils_b.tour_length == 48.0
        and ils_a1.tour_length <= line_seed.tour_length
    ):
        passed += 1
        print("  ✅ iterated local search: same seed bit-identical, both seeds reach 48")
    else:
        failed += 1
        print(
            "  ❌ ILS determinism:",
            ils_a1.tour_length,
            ils_a2.tour_length,
            ils_b.tour_length,
            ils_a1.moves_evaluated,
            ils_a2.moves_evaluated,
        )

    # ── vehicle bounds from the frozen bin packers ───────────────────────────
    var bound_even = vrp_vehicle_bound(_floats(5.0, 5.0, 5.0, 5.0), 10.0)
    var bound_gap = vrp_vehicle_bound(_floats(6.0, 6.0, 6.0), 10.0)
    var bound_over = vrp_vehicle_bound(_floats(11.0, 1.0), 10.0)
    var bound_bad = vrp_vehicle_bound(_floats(1.0), 0.0)
    if (
        bound_even.status == ROUTE_OK
        and bound_even.has_bound
        and bound_even.lower_bound == 2
        and bound_even.ffd_bins == 2
        and bound_even.ff_bins == 2
        and bound_even.total_demand == 20.0
        and bound_even.max_demand == 5.0
        and bound_gap.lower_bound == 2
        and bound_gap.ffd_bins == 3
        and bound_over.status == ROUTE_INFEASIBLE_PROVEN
        and not bound_over.has_bound
        and bound_over.n_oversized == 1
        and bound_over.defect_index == 0
        and bound_bad.status == ROUTE_ERR_INSTANCE
    ):
        passed += 1
        print("  ✅ vehicle bounds: 4x5/10 -> lb 2 = ffd 2; 3x6/10 -> lb 2 < ffd 3; 11 > 10 proven")
    else:
        failed += 1
        print(
            "  ❌ vehicle bounds:",
            bound_even.lower_bound,
            bound_even.ffd_bins,
            bound_gap.ffd_bins,
            bound_over.status,
        )

    # ── capacity VRP: the hand-computed optimum, re-audited ─────────────────
    var arms = _two_arms()
    var demands = _floats(0.0, 5.0, 5.0, 5.0, 5.0)
    var cap_sol = vrp_capacity_solve(arms, 5, demands, 10.0, 2, 50, 3, UInt64(5))
    var cap_audit = vrp_check(
        arms, 5, demands, 10.0, List[Float64](), List[Float64](), List[Float64](),
        cap_sol.stops, cap_sol.route_start,
    )
    if (
        cap_sol.status == ROUTE_OK
        and cap_sol.feasible
        and not cap_sol.proven_infeasible
        and cap_sol.has_total
        and cap_sol.total_distance == 8.0
        and cap_sol.n_routes_used == 2
        and cap_sol.lower_bound_vehicles == 2
        and cap_sol.ffd_bins == 2
        and cap_sol.max_capacity_excess == 0.0
        and len(cap_sol.stops) == 4
        and cap_sol.route_load[0] == 10.0
        and cap_sol.route_load[1] == 10.0
        and cap_audit.status == ROUTE_OK
        and cap_audit.feasible
        and cap_audit.all_served
        and cap_audit.n_served == 4
        and cap_audit.total_distance == 8.0
    ):
        passed += 1
        print("  ✅ capacity VRP: total 8.0 on two arms, two full vehicles, audit agrees")
    else:
        failed += 1
        print(
            "  ❌ capacity VRP:",
            cap_sol.status,
            cap_sol.total_distance,
            cap_sol.n_routes_used,
            cap_audit.feasible,
        )

    # ── infeasibility that is PROVEN, versus a search that merely failed ─────
    var too_big = vrp_capacity_solve(arms, 5, demands, 4.0, 4, 50, 1, UInt64(5))
    var too_few = vrp_capacity_solve(arms, 5, demands, 10.0, 1, 50, 1, UInt64(5))
    if (
        too_big.status == ROUTE_INFEASIBLE_PROVEN
        and too_big.proven_infeasible
        and not too_big.feasible
        and not too_big.has_total
        and len(too_big.stops) == 0
        and too_big.defect_node == 1
        and too_few.status == ROUTE_INFEASIBLE_PROVEN
        and too_few.lower_bound_vehicles == 2
        and len(too_few.stops) == 0
    ):
        passed += 1
        print("  ✅ demand 5 > capacity 4 and lb 2 > 1 vehicle are PROVEN, with no routes")
    else:
        failed += 1
        print(
            "  ❌ proven infeasibility:",
            too_big.status,
            too_big.defect_node,
            too_few.status,
            too_few.lower_bound_vehicles,
        )

    # ── a rounding artifact must not become a PROOF of infeasibility ────────
    # 0.1 + 0.2 == 0.30000000000000004 in Float64, so ceil(total / 0.3) is 2 and `2 > 1
    # vehicle` used to come back as ROUTE_INFEASIBLE_PROVEN — for an instance one vehicle
    # serves exactly, and which this module's own per-route capacity check accepts. The frozen
    # FFD still splits them (its comparison is exact), which is precisely why `ffd_bins` is
    # reported and never used to prove anything.
    var tight_dist = _floats(
        0.0, 1.0, 2.0,
        1.0, 0.0, 1.0,
        2.0, 1.0, 0.0,
    )
    var tight_demand = _floats(0.0, 0.1, 0.2)
    var tight = vrp_capacity_solve(tight_dist, 3, tight_demand, 0.3, 1, 20, 1, UInt64(1))
    var tight_bound = vrp_vehicle_bound(_floats(0.1, 0.2), 0.3)
    var exact_fit = vrp_capacity_solve(
        tight_dist, 3, _floats(0.0, 3.0, 3.0), 6.0, 1, 20, 1, UInt64(1)
    )
    if (
        tight.status == ROUTE_OK
        and tight.feasible
        and not tight.proven_infeasible
        and tight.lower_bound_vehicles == 1
        and tight.ffd_bins == 2
        and tight.n_routes_used == 1
        and tight.total_distance == 4.0
        and tight_bound.lower_bound == 1
        and tight_bound.ffd_bins == 2
        and exact_fit.status == ROUTE_OK
        and exact_fit.lower_bound_vehicles == 1
        and exact_fit.total_distance == 4.0
    ):
        passed += 1
        print("  ✅ 0.1+0.2 vs capacity 0.3 is served by one vehicle, not proven infeasible")
    else:
        failed += 1
        print(
            "  ❌ rounding-driven false proof:",
            tight.status,
            tight.lower_bound_vehicles,
            tight.ffd_bins,
            tight_bound.lower_bound,
            exact_fit.status,
        )

    # ── time windows are HARD, and a failed search says so honestly ─────────
    # Customer 3 must start by t=1 and customer 2 by t=2; one vehicle cannot do both
    # (0->3 at t=1 then 3->2 arrives t=4, or 0->2 at t=2 then 2->3 arrives t=5). Nothing in
    # the data PROVES infeasibility, so one vehicle must come back "no solution found" —
    # not a route that misses a window, and not a claim of infeasibility.
    var wl = _window_line()
    var wl_demand = _floats(0.0, 1.0, 1.0, 1.0)
    var ready = _floats(0.0, 0.0, 0.0, 0.0)
    var due = _floats(100.0, 100.0, 2.0, 1.0)
    var service = _floats(0.0, 0.0, 0.0, 0.0)
    var one_van = vrp_time_window_solve(
        wl, 4, wl_demand, 10.0, 1, ready, due, service, 50, 3, UInt64(3)
    )
    var two_vans = vrp_time_window_solve(
        wl, 4, wl_demand, 10.0, 2, ready, due, service, 50, 3, UInt64(3)
    )
    # One vehicle taking 3 then 2 then 1: it reaches 3 at t=1 (its due time exactly), then 2
    # at t=4 against a due time of 2, so the lateness is exactly 2 at sequence position 1.
    var missed = vrp_check(
        wl, 4, wl_demand, 10.0, ready, due, service, _ints(3, 2, 1), _ints(0, 3)
    )
    if (
        one_van.status == ROUTE_NO_SOLUTION_FOUND
        and not one_van.proven_infeasible
        and not one_van.feasible
        and not one_van.has_total
        and len(one_van.stops) == 0
        and one_van.lower_bound_vehicles == 1
        and two_vans.status == ROUTE_OK
        and two_vans.feasible
        and two_vans.total_distance == 6.0
        and two_vans.n_routes_used == 2
        and two_vans.windowed
        and missed.status == ROUTE_OK
        and not missed.feasible
        and missed.all_served
        and missed.n_window_violations == 1
        and missed.max_lateness == 2.0
        and missed.defect_vehicle == 0
        and missed.defect_stop == 1
        and missed.defect_node == 2
    ):
        passed += 1
        print("  ✅ windows: 1 van = no_solution_found (not infeasible), 2 vans = 6.0, audit finds the late stop")
    else:
        failed += 1
        print(
            "  ❌ time windows:",
            one_van.status,
            two_vans.status,
            two_vans.total_distance,
            missed.max_lateness,
            missed.defect_node,
        )

    # ── a window reachable only by a DETOUR must never be "proven" impossible ─
    # d[0][2] = 10 against a due time of 3, but the detour 0 -> 1 -> 2 arrives at t = 2, and
    # this matrix violates the triangle inequality on purpose. A proof built on the direct arc
    # called this instance infeasible; it is not. `_earliest_arrival_bound` uses
    # min(direct, cheapest-arc-out-of-depot + cheapest-arc-into-c) = min(10, 1 + 1) = 2, which
    # refutes nothing here — correctly, since a feasible routing exists.
    #
    # It also shows what the keyed restarts buy: restart 0 offers customer 2 first (tightest
    # due time), and a route that starts 0 -> 2 can never meet the window, so restarts 1..5
    # fail honestly; the keyed order at 7 restarts puts 1 first and finds the real answer.
    var detour = _floats(
        0.0, 1.0, 10.0, 1.0,
        1.0, 0.0, 1.0, 5.0,
        10.0, 1.0, 0.0, 5.0,
        1.0, 5.0, 5.0, 0.0,
    )
    var det_demand = _floats(0.0, 1.0, 1.0, 1.0)
    var det_ready = _floats(0.0, 0.0, 0.0, 0.0)
    var det_due = _floats(100.0, 100.0, 3.0, 100.0)
    var det_svc = _floats(0.0, 0.0, 0.0, 0.0)
    var det_few = vrp_time_window_solve(
        detour, 4, det_demand, 10.0, 1, det_ready, det_due, det_svc, 60, 3, UInt64(4)
    )
    var det_many = vrp_time_window_solve(
        detour, 4, det_demand, 10.0, 1, det_ready, det_due, det_svc, 60, 7, UInt64(4)
    )
    var det_witness = vrp_check(
        detour, 4, det_demand, 10.0, det_ready, det_due, det_svc, _ints(1, 2, 3),
        _ints(0, 3),
    )
    var det_census = distance_matrix_check(detour, 4)
    if (
        det_few.status == ROUTE_NO_SOLUTION_FOUND
        and not det_few.proven_infeasible
        and len(det_few.stops) == 0
        and det_many.status == ROUTE_OK
        and det_many.feasible
        and det_many.total_distance == 8.0
        and _same_ints(det_many.stops, _ints(1, 2, 3))
        and det_many.restarts_feasible == 1
        and det_witness.feasible
        and det_witness.all_served
        and det_witness.max_lateness == 0.0
        and det_witness.total_distance == 8.0
        and not det_census.triangle_ok
    ):
        passed += 1
        print("  ✅ a detour-only window is never PROVEN impossible; 7 restarts find the 8.0 route")
    else:
        failed += 1
        print(
            "  ❌ detour reachability:",
            det_few.status,
            det_many.status,
            det_many.total_distance,
            det_witness.feasible,
            det_census.triangle_ok,
        )

    # ── window infeasibility that IS proven from the data ────────────────────
    var unreachable = _floats(100.0, 100.0, 1.0, 100.0)
    var proven_late = vrp_time_window_solve(
        wl, 4, wl_demand, 10.0, 3, ready, unreachable, service, 50, 1, UInt64(3)
    )
    var no_return_due = _floats(3.0, 100.0, 100.0, 100.0)
    var proven_home = vrp_time_window_solve(
        wl, 4, wl_demand, 10.0, 3, ready, no_return_due, service, 50, 1, UInt64(3)
    )
    if (
        proven_late.status == ROUTE_INFEASIBLE_PROVEN
        and proven_late.proven_infeasible
        and proven_late.defect_node == 2
        and len(proven_late.stops) == 0
        and proven_home.status == ROUTE_INFEASIBLE_PROVEN
        and proven_home.defect_node == 2
    ):
        passed += 1
        print("  ✅ a stop unreachable before its due time, or unable to get home, is PROVEN")
    else:
        failed += 1
        print(
            "  ❌ proven window infeasibility:",
            proven_late.status,
            proven_late.defect_node,
            proven_home.status,
            proven_home.defect_node,
        )

    # ── the audit rejects what it cannot index and reports what it can ──────
    var depot_as_stop = vrp_check(
        arms, 5, demands, 10.0, List[Float64](), List[Float64](), List[Float64](),
        _ints(1, 0, 2), _ints(0, 3),
    )
    var bad_offsets = vrp_check(
        arms, 5, demands, 10.0, List[Float64](), List[Float64](), List[Float64](),
        _ints(1, 2), _ints(0, 5),
    )
    var duplicated = vrp_check(
        arms, 5, demands, 10.0, List[Float64](), List[Float64](), List[Float64](),
        _ints(1, 1), _ints(0, 2),
    )
    var overloaded = vrp_check(
        arms, 5, demands, 10.0, List[Float64](), List[Float64](), List[Float64](),
        _ints(1, 2, 3, 4), _ints(0, 4),
    )
    var half_windows = vrp_check(
        wl, 4, wl_demand, 10.0, ready, due, List[Float64](), _ints(1), _ints(0, 1)
    )
    if (
        depot_as_stop.status == ROUTE_ERR_NOT_A_PERMUTATION
        and depot_as_stop.defect_stop == 1
        and depot_as_stop.defect_node == 0
        and bad_offsets.status == ROUTE_ERR_LENGTH_MISMATCH
        and duplicated.status == ROUTE_OK
        and not duplicated.feasible
        and not duplicated.all_served
        and duplicated.n_duplicated == 1
        and duplicated.n_missing == 3
        and overloaded.status == ROUTE_OK
        and not overloaded.feasible
        and overloaded.all_served
        and overloaded.n_capacity_violations == 1
        and overloaded.max_capacity_excess == 10.0
        and overloaded.defect_vehicle == 0
        and half_windows.status == ROUTE_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ audit: depot/offset breaks rejected; duplicate and overload reported with data")
    else:
        failed += 1
        print(
            "  ❌ audit behaviour:",
            depot_as_stop.status,
            bad_offsets.status,
            duplicated.n_duplicated,
            overloaded.max_capacity_excess,
            half_windows.status,
        )

    # ── VRP determinism, and a pass limit that is still a verified answer ───
    # With `max_passes = 0` nothing is improved, so the answer IS the keyed construction and
    # the seed reaches it visibly. The status must then be OK_LIMIT — and the routes must
    # still be audited feasible, because a limit is not a licence to return a broken answer.
    var scattered = _scattered()
    var s_demand = _floats(0.0, 2.0, 1.0, 3.0, 2.0, 1.0, 3.0, 1.0, 2.0)
    var raw_a1 = vrp_capacity_solve(scattered, 9, s_demand, 6.0, 3, 0, 4, UInt64(1))
    var raw_a2 = vrp_capacity_solve(scattered, 9, s_demand, 6.0, 3, 0, 4, UInt64(1))
    var raw_b = vrp_capacity_solve(scattered, 9, s_demand, 6.0, 3, 0, 4, UInt64(2))
    var improved_a = vrp_capacity_solve(scattered, 9, s_demand, 6.0, 3, 50, 4, UInt64(1))
    var raw_audit = vrp_check(
        scattered, 9, s_demand, 6.0, List[Float64](), List[Float64](), List[Float64](),
        raw_a1.stops, raw_a1.route_start,
    )
    if (
        raw_a1.status == ROUTE_OK_LIMIT
        and raw_a1.feasible
        and _same_ints(raw_a1.stops, raw_a2.stops)
        and raw_a1.total_distance == raw_a2.total_distance
        and raw_a1.passes == raw_a2.passes
        and not raw_a1.local_optimum
        and raw_b.feasible
        and raw_b.total_distance != raw_a1.total_distance
        and not _same_ints(raw_a1.stops, raw_b.stops)
        and raw_audit.feasible
        and raw_audit.all_served
        and raw_audit.n_served == 8
        and _close(raw_audit.total_distance, raw_a1.total_distance)
        and improved_a.status == ROUTE_OK
        and improved_a.local_optimum
        and improved_a.feasible
        and improved_a.total_distance < raw_a1.total_distance
        and improved_a.n_routes_used == 3
        and improved_a.lower_bound_vehicles == 3
    ):
        passed += 1
        print("  ✅ VRP: same seed bit-identical, seed 2 differs, OK_LIMIT still audited feasible")
    else:
        failed += 1
        print(
            "  ❌ VRP determinism:",
            raw_a1.status,
            raw_a1.total_distance,
            raw_b.total_distance,
            improved_a.total_distance,
            improved_a.status,
        )

    # ── a depot-only instance has a real zero, not an absence ───────────────
    var solo = vrp_capacity_solve(
        _floats(0.0), 1, _floats(0.0), 10.0, 1, 10, 1, UInt64(1)
    )
    var bad_depot_demand = vrp_capacity_solve(
        arms, 5, _floats(1.0, 5.0, 5.0, 5.0, 5.0), 10.0, 2, 10, 1, UInt64(1)
    )
    var bad_vehicles = vrp_capacity_solve(arms, 5, demands, 10.0, 0, 10, 1, UInt64(1))
    var short_demand = vrp_capacity_solve(arms, 5, _floats(0.0, 5.0), 10.0, 2, 10, 1, UInt64(1))
    if (
        solo.status == ROUTE_OK
        and solo.feasible
        and solo.has_total
        and solo.total_distance == 0.0
        and solo.n_routes_used == 0
        and bad_depot_demand.status == ROUTE_ERR_INSTANCE
        and bad_vehicles.status == ROUTE_ERR_INSTANCE
        and short_demand.status == ROUTE_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ depot only = 0.0 served by 0 vehicles; a depot demand or 0 vans is rejected")
    else:
        failed += 1
        print(
            "  ❌ degenerate instances:",
            solo.status,
            solo.total_distance,
            bad_depot_demand.status,
            bad_vehicles.status,
            short_demand.status,
        )

    # ── REGRESSION: n_routes_used and route_start are ONE claim ─────────────
    # The reproduction verbatim. Relocation empties a route here, and the solver used to append
    # an offset for the emptied SLOT while counting only the non-empty ones:
    #   status=120, feasible=True, total_distance=550.411793825003, n_routes_used=3,
    #   route_start=[0, 3, 3, 5, 8], stops=[1, 5, 3, 7, 4, 6, 8, 2], route_load=[7, 0, 7, 7].
    # A caller following the documented layout read [1,5,3,7,4] and dropped customers 6, 8, 2;
    # feeding that reconstruction back through this module's own `vrp_check` returned
    # feasible=False, n_served=5 of 8, n_missing=3 — a routing that is not a routing under a
    # success status. The empty slot is now removed, so the two fields cannot disagree.
    var nine = _nine_windowed()
    var nine_demand = _floats(0.0, 2.0, 1.0, 3.0, 4.0, 2.0, 2.0, 3.0, 4.0)
    var nine_ready = _floats(0.0, 44.0, 31.0, 38.0, 17.0, 39.0, 1.0, 25.0, 11.0)
    var nine_due = _floats(600.0, 436.0, 308.0, 208.0, 390.0, 480.0, 300.0, 245.0, 450.0)
    var nine_service = _floats(0.0, 4.0, 2.0, 2.0, 1.0, 1.0, 4.0, 2.0, 1.0)
    var empty_slot = vrp_time_window_solve(
        nine, 9, nine_demand, 7.0, 4, nine_ready, nine_due, nine_service, 60, 3,
        UInt64(11),
    )
    # Read exactly as documented, then re-audited by the module's own public checker.
    var reread = _read_as_documented(empty_slot)
    var reread_offsets = _read_offsets_as_documented(empty_slot)
    var reread_audit = vrp_check(
        nine, 9, nine_demand, 7.0, nine_ready, nine_due, nine_service, reread,
        reread_offsets,
    )
    # The per-vehicle arrays must be indexed by the same `v`, and the totals must reconcile:
    # `route_load[1] = 0.0` used to attribute nothing to a vehicle while the real third route's
    # load of 7.0 sat at index 3, past `n_routes_used`.
    var slot_dist_sum = 0.0
    var slot_loads_positive = True
    for v in range(empty_slot.n_routes_used):
        slot_dist_sum += empty_slot.route_distance[v]
        if empty_slot.route_load[v] <= 0.0:
            slot_loads_positive = False
    if (
        (empty_slot.status == ROUTE_OK or empty_slot.status == ROUTE_OK_LIMIT)
        and empty_slot.feasible
        and _close(empty_slot.total_distance, 550.411793825003)
        and _same_ints(empty_slot.stops, _ints(1, 5, 3, 7, 4, 6, 8, 2))
        and empty_slot.n_routes_used == 3
        and _partitions(empty_slot.stops, empty_slot.route_start, empty_slot.n_routes_used)
        and len(empty_slot.route_load) == empty_slot.n_routes_used
        and len(empty_slot.route_distance) == empty_slot.n_routes_used
        and len(empty_slot.route_return_time) == empty_slot.n_routes_used
        and slot_loads_positive
        and _close(slot_dist_sum, empty_slot.total_distance)
        and _same_ints(reread, empty_slot.stops)
        and reread_audit.status == ROUTE_OK
        and reread_audit.feasible
        and reread_audit.all_served
        and reread_audit.n_served == 8
        and reread_audit.n_missing == 0
        and _close(reread_audit.total_distance, empty_slot.total_distance)
    ):
        passed += 1
        print("  ✅ an emptied route is removed, not slotted: the offsets partition the tour")
    else:
        failed += 1
        print(
            "  ❌ route layout:",
            empty_slot.n_routes_used,
            len(empty_slot.route_start),
            len(empty_slot.stops),
            reread_audit.n_served,
            reread_audit.n_missing,
            empty_slot.total_distance,
        )

    # ── the partition invariant holds on EVERY answer, not just that one ─────
    # A sweep, because the empty-route case was measured at 14 in 567 solves: one instance and
    # one seed is a witness, a family is the invariant. Every feasible answer must satisfy the
    # documented layout AND round-trip through `vrp_check` with every customer served once.
    var sweep_ok = True
    var sweep_checked = 0
    var sweep_scattered = _scattered()
    var sweep_s_demand = _floats(0.0, 2.0, 1.0, 3.0, 2.0, 1.0, 3.0, 1.0, 2.0)
    for s in range(1, 25):
        var w = vrp_time_window_solve(
            nine, 9, nine_demand, 7.0, 4, nine_ready, nine_due, nine_service, 60, 3,
            UInt64(s),
        )
        var c = vrp_capacity_solve(
            sweep_scattered, 9, sweep_s_demand, 6.0, 4, 50, 3, UInt64(s)
        )
        if w.status == ROUTE_OK or w.status == ROUTE_OK_LIMIT:
            sweep_checked += 1
            if not _partitions(w.stops, w.route_start, w.n_routes_used):
                sweep_ok = False
            if len(w.route_load) != w.n_routes_used:
                sweep_ok = False
            var wa = vrp_check(
                nine, 9, nine_demand, 7.0, nine_ready, nine_due, nine_service,
                _read_as_documented(w), _read_offsets_as_documented(w),
            )
            if not (wa.feasible and wa.all_served and wa.n_served == 8):
                sweep_ok = False
        if c.status == ROUTE_OK or c.status == ROUTE_OK_LIMIT:
            sweep_checked += 1
            if not _partitions(c.stops, c.route_start, c.n_routes_used):
                sweep_ok = False
            if len(c.route_distance) != c.n_routes_used:
                sweep_ok = False
            var ca = vrp_check(
                sweep_scattered, 9, sweep_s_demand, 6.0, List[Float64](),
                List[Float64](), List[Float64](), _read_as_documented(c),
                _read_offsets_as_documented(c),
            )
            if not (ca.feasible and ca.all_served and ca.n_served == 8):
                sweep_ok = False
    if sweep_ok and sweep_checked >= 24:
        passed += 1
        print(
            "  ✅ the documented layout round-trips through vrp_check on",
            sweep_checked,
            "answers",
        )
    else:
        failed += 1
        print("  ❌ layout sweep:", sweep_ok, sweep_checked)

    # ── REGRESSION: the status may not contradict `local_optimum` ────────────
    # Both reproductions verbatim. `tsp_local_search(six_city, 6, 10, False, False, 1)` scanned
    # nothing (both families off) and `tsp_or_opt(three_city, 3, 10, 1)` has an empty Or-opt
    # neighbourhood below n = 4; both returned status 120, whose name is
    # `verified_local_optimum_of_the_declared_moves_not_proven_optimal`, beside
    # `local_optimum = False`. One value, two contradictory claims.
    var no_family = tsp_local_search(line, 6, 10, False, False, 1)
    var empty_hood = tsp_or_opt(_triangle_violating(), 3, 10, 1)
    var agree = True
    var checked_agree = 0
    var tours = List[RouteTour]()
    tours.append(no_family.copy())
    tours.append(empty_hood.copy())
    tours.append(tsp_greedy_flat(four, 4).copy())
    tours.append(tsp_two_opt(four, 4, 100).copy())
    tours.append(tsp_two_opt(line, 6, 0).copy())
    tours.append(tsp_or_opt(line, 6, 200, 3).copy())
    tours.append(tsp_local_search(circle, 8, 200, True, True, 3).copy())
    tours.append(tsp_iterated_local_search(line, 6, 200, 3, 12, UInt64(11)).copy())
    tours.append(
        tsp_perturb_double_bridge(line, 6, start_tour, UInt64(7), 0).copy()
    )
    tours.append(tsp_two_opt(_floats(0.0), 1, 100).copy())
    tours.append(tsp_two_opt(_floats(0.0, 3.0, 4.0, 0.0), 2, 100).copy())
    for i in range(len(tours)):
        checked_agree += 1
        if not _status_matches_local_opt_tour(tours[i]):
            agree = False
    var sols = List[RouteSolution]()
    sols.append(vrp_capacity_solve(arms, 5, demands, 10.0, 2, 50, 3, UInt64(5)).copy())
    sols.append(
        vrp_capacity_solve(scattered, 9, s_demand, 6.0, 3, 0, 4, UInt64(1)).copy()
    )
    sols.append(
        vrp_capacity_solve(scattered, 9, s_demand, 6.0, 3, 50, 4, UInt64(1)).copy()
    )
    sols.append(empty_slot.copy())
    sols.append(solo.copy())
    for i in range(len(sols)):
        checked_agree += 1
        if not _status_matches_local_opt_solution(sols[i]):
            agree = False
    if (
        agree
        and checked_agree >= 16
        and no_family.status == ROUTE_OK_LIMIT
        and not no_family.local_optimum
        and no_family.moves_evaluated == 0
        and no_family.passes == 0
        and no_family.is_permutation
        and empty_hood.status == ROUTE_OK_LIMIT
        and not empty_hood.local_optimum
        and empty_hood.moves_evaluated == 0
        and route_status_name(ROUTE_OK_LIMIT)
        == "verified_but_not_a_local_optimum_of_the_declared_moves"
    ):
        passed += 1
        print("  ✅ ROUTE_OK iff local_optimum, on", checked_agree, "returned values")
    else:
        failed += 1
        print(
            "  ❌ status vs local_optimum:",
            agree,
            checked_agree,
            no_family.status,
            no_family.local_optimum,
            empty_hood.status,
            empty_hood.local_optimum,
        )

    # ── REGRESSION: a nonzero diagonal is a defect, not a tour length ────────
    # `tour_length_flat(distance=[7.5], n=1, tour=[0, 0])` answered has_value=True, value=7.5,
    # and `tsp_two_opt(distance=[7.5], n=1, max_passes=5)` answered status=120 with
    # tour_length=7.5 and local_optimum=True — for a tour of one city, which traverses no legs
    # and whose only length is 0.0. The frozen `tsp_tour_length` sums d[0][0] there.
    var self_loop_len = tour_length_flat(_floats(7.5), 1, _ints(0, 0))
    var self_loop_search = tsp_two_opt(_floats(7.5), 1, 5)
    var self_loop_census = distance_matrix_check(_floats(7.5), 1)
    var inner_diag = _floats(
        0.0, 1.0, 2.0,
        1.0, 3.0, 1.0,
        2.0, 1.0, 0.0,
    )
    var inner_census = distance_matrix_check(inner_diag, 3)
    var inner_search = tsp_two_opt(inner_diag, 3, 5)
    var zero_diag_one = tour_length_flat(_floats(0.0), 1, _ints(0, 0))
    if (
        self_loop_len.status == ROUTE_ERR_DISTANCE
        and not self_loop_len.has_value
        and self_loop_search.status == ROUTE_ERR_DISTANCE
        and len(self_loop_search.tour) == 0
        and not self_loop_search.has_length
        and not self_loop_search.local_optimum
        and self_loop_census.status == ROUTE_ERR_DISTANCE
        and self_loop_census.defect_index == 0
        and inner_census.status == ROUTE_ERR_DISTANCE
        and inner_census.defect_index == 4
        and inner_search.status == ROUTE_ERR_DISTANCE
        and zero_diag_one.status == ROUTE_OK
        and zero_diag_one.has_value
        and zero_diag_one.value == 0.0
        and route_status_name(ROUTE_ERR_DISTANCE)
        == "distance_non_finite_negative_above_1e300_or_nonzero_diagonal"
    ):
        passed += 1
        print("  ✅ d[c][c] != 0 is refused by index; a one-city tour is 0.0, never the self-loop")
    else:
        failed += 1
        print(
            "  ❌ diagonal validation:",
            self_loop_len.status,
            self_loop_len.value,
            self_loop_search.status,
            inner_census.defect_index,
            zero_diag_one.value,
        )

    # ── REGRESSION: the effort knobs bound the work, not just the iterations ─
    # `n_kicks` was clamped to ROUTE_MAX_PASSES = 65536 and `n_restarts` to 4096, and each
    # iteration runs a FULL search: measured, `vrp_capacity_solve` at n = 40 with 4096 restarts
    # extrapolated to ~150 s and at n = 100 to ~40 minutes of single-threaded compute from one
    # integer in an 80 KB payload — a hang to every other client of the worker. One shared work
    # budget now bounds the total, and the COUNT ACTUALLY ATTEMPTED is what comes back, so a
    # request for a million is visibly not honoured rather than silently accepted.
    var big = _lattice(40)
    var big_demand = _ramp_demand(40)
    var kick_bomb = tsp_iterated_local_search(big, 40, 65536, 3, 1000000, UInt64(7))
    var restart_bomb = vrp_capacity_solve(big, 40, big_demand, 20.0, 40, 200, 1000000, UInt64(7))
    var restart_small = vrp_capacity_solve(big, 40, big_demand, 20.0, 40, 200, 2, UInt64(7))
    if (
        (kick_bomb.status == ROUTE_OK or kick_bomb.status == ROUTE_OK_LIMIT)
        and kick_bomb.is_permutation
        and tour_check(kick_bomb.tour, 40).is_permutation
        and kick_bomb.kicks >= 1
        and kick_bomb.kicks < ROUTE_MAX_PASSES
        and kick_bomb.tour_length <= kick_bomb.seed_length
        and (restart_bomb.status == ROUTE_OK or restart_bomb.status == ROUTE_OK_LIMIT)
        and restart_bomb.feasible
        and restart_bomb.restarts >= 1
        and restart_bomb.restarts < ROUTE_MAX_NODES
        and _partitions(
            restart_bomb.stops, restart_bomb.route_start, restart_bomb.n_routes_used
        )
        and restart_small.restarts == 2
        and restart_small.feasible
    ):
        passed += 1
        print(
            "  ✅ work budget: 1000000 kicks ran",
            kick_bomb.kicks,
            "and 1000000 restarts ran",
            restart_bomb.restarts,
        )
    else:
        failed += 1
        print(
            "  ❌ work bound:",
            kick_bomb.status,
            kick_bomb.kicks,
            restart_bomb.status,
            restart_bomb.restarts,
            restart_small.restarts,
        )

    # ── REGRESSION: the VRP scan must not claim an optimum it never looked for ─
    # `_improve_routes` set `local_optimum = True` whenever the scan found no improving move,
    # INCLUDING when it examined nothing, while `_local_search` guarded the identical claim.
    # One invariant, two strengths, one file. Now both count what they examined. The three cases
    # that separate the claims, on the same instance:
    #   * `max_passes = 0` — nothing was scanned at all, so the flag is False and the status says
    #     so, even though the routes are audited feasible;
    #   * a real scan that finds nothing improving (relocation would overload the other vehicle)
    #     — the flag is True and the status is ROUTE_OK;
    #   * one customer — the neighbourhood is genuinely empty, but there is only ONE distinct
    #     routing, so the claim is honest rather than vacuous.
    var pair_dist = _floats(
        0.0, 1.0, 2.0,
        1.0, 0.0, 3.0,
        2.0, 3.0, 0.0,
    )
    var pair_demand = _floats(0.0, 6.0, 6.0)
    var unscanned = vrp_capacity_solve(pair_dist, 3, pair_demand, 10.0, 2, 0, 1, UInt64(1))
    var scanned = vrp_capacity_solve(pair_dist, 3, pair_demand, 10.0, 2, 20, 1, UInt64(1))
    var single = vrp_capacity_solve(_floats(0.0, 5.0, 5.0, 0.0), 2, _floats(0.0, 3.0), 10.0, 2, 20, 1, UInt64(1))
    if (
        unscanned.status == ROUTE_OK_LIMIT
        and not unscanned.local_optimum
        and unscanned.feasible
        and unscanned.n_routes_used == 2
        and unscanned.total_distance == 6.0
        and scanned.status == ROUTE_OK
        and scanned.local_optimum
        and scanned.feasible
        and scanned.total_distance == 6.0
        and _partitions(scanned.stops, scanned.route_start, scanned.n_routes_used)
        and single.status == ROUTE_OK
        and single.local_optimum
        and single.n_routes_used == 1
        and single.total_distance == 10.0
        and _partitions(single.stops, single.route_start, single.n_routes_used)
    ):
        passed += 1
        print("  ✅ VRP local_optimum needs a scan: 0 passes says False, a real scan says True")
    else:
        failed += 1
        print(
            "  ❌ VRP vacuous local optimum:",
            unscanned.status,
            unscanned.local_optimum,
            scanned.status,
            scanned.local_optimum,
            single.status,
            single.local_optimum,
        )

    print("  [optimization.routing] Passed:", passed, "Failed:", failed)
