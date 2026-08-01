"""
geospatial.join — spatial joins driven by the cell index, and route matrices.

Zero Python imports. Every distance and every shortest path comes out of a frozen kernel:

  | quantity                          | frozen kernel called unchanged                  |
  | --------------------------------- | ----------------------------------------------- |
  | metre distance under any metric   | `geodesy.*` / `geometry.distance_2d` via `frame` |
  | road-network adjacency (CSR)      | `graph_analytics.adjacency.graph_csr_from_triplets` |
  | single-source shortest paths      | `graph_analytics.adjacency.graph_csr_dijkstra`   |
  | candidate pruning                 | `index.grid_build_flat` / `grid_window_flat`      |
  | ring membership                   | `polygon.points_in_ring_flat`                    |

What this module adds is the composition and the refusals. The pieces above have never been
driven end to end: there is no path in the tree from two coordinate arrays to a joined pair
list, and none from coordinates plus an edge list to a road-network travel matrix.

The radius join is a real join, not a nested loop
------------------------------------------------
`join_within_flat` indexes the RIGHT side once and probes it with each left point's own
search box, so cost is O(n_left * candidates per box) rather than O(n_left * n_right).
`candidates_examined` and `full_scan_cost` come back so the saving is measured on the
caller's data. The search box is derived from the radius by dividing metres by a LOWER bound
on metres per degree, which makes the box a SUPERSET of the true disc — conservative in the
only direction that is safe, since a box that is too small silently drops pairs.

Near the antimeridian that box would need to WRAP, and a clipped box would silently drop
every pair across the seam. So a degree-frame join whose search box would cross the seam is
REFUSED with `GEO_ERR_ANTIMERIDIAN` and the offending left point's index, rather than
returning a join that is quietly incomplete. Splitting the input at the seam is a decision
only the caller can make.

A budget that is reached is a DIFFERENT status, not a quiet truncation
----------------------------------------------------------------------
Two budgets bound this module: `max_pairs` (what the caller will accept) and
`GEO_MAX_CANDIDATE_WORK` (what the kernel will spend). Reaching either returns
`GEO_OK_TRUNCATED`, never `GEO_OK`, because a partial join that reports success is
indistinguishable from a complete one — and the caller that stops looking is the failure this
package exists to prevent. `truncated` carries the same fact as a flag.

Route matrices: the crow-flies one and the network one, kept apart
-----------------------------------------------------------------
`route_matrix_flat` is the geodesic or planar matrix — the crow-flies lower bound. It is not
a travel matrix and is not named as if it were.

`network_route_matrix_flat` is the travel matrix: node coordinates plus a directed edge list
become a weighted CSR (frozen), and one frozen Dijkstra runs per origin. Edge weights are the
metric distance between the two endpoint coordinates, so the graph and the geometry cannot
disagree. An unreachable pair is ABSENT — `reachable[i * n_dests + j]` is False and the
distance slot is 0.0 — never the `1e18` that the older frozen shortest-path kernels return
and no caller can tell from a real distance. That distinction is inherited from
`graph_csr_dijkstra`, which already reports `reached` separately, and is the reason it is the
kernel called rather than `graph.weighted.shortest_path_dijkstra`.

Status codes: 700-729 via `geospatial.contract`. No codes are minted here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_geospatial_join.mojo
benchmark: benchmarks/mojo_benchmarks/bench_geospatial.mojo
docs: gitbook/engine/geospatial.md
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from graph_analytics.adjacency import (
    GRAPH_OK,
    graph_csr_dijkstra,
    graph_csr_from_triplets,
)
from sorting import mergesort

from geospatial.contract import (
    GEO_ERR_ANTIMERIDIAN,
    GEO_ERR_BUDGET,
    GEO_ERR_COUNT,
    GEO_ERR_LAYOUT,
    GEO_ERR_METRIC_NO_CONVERGENCE,
    GEO_ERR_PARAM,
    GEO_M_PER_DEG,
    GEO_MAX_CANDIDATE_WORK,
    GEO_MAX_LAT_DEG,
    GEO_MAX_LON_DEG,
    GEO_MAX_MATRIX_CELLS,
    GEO_MAX_POINTS,
    GEO_MAX_RING_VERTICES,
    GEO_FRAME_LATLON_DEG,
    GEO_OK,
    GEO_OK_TRUNCATED,
    geo_cells_fit,
    geo_degree_box_half,
    geo_finite,
    geo_finite_or_zero,
    geo_is_degree_frame,
    geo_lat_of,
    geo_metric_defect,
    geo_offsets_defect,
    geo_pair_range_defect,
    geo_points_defect,
)
from geospatial.frame import frame_metric_distance, frame_metric_undefined
from geospatial.index import grid_build_flat, grid_window_flat
from geospatial.polygon import (
    GEO_PIP_BOUNDARY,
    GEO_PIP_OUTSIDE,
    points_in_ring_flat,
    ring_planar_defect_flat,
)

#: Points per cell the internal index targets. Four keeps the pointer array at n/4 entries
#: while leaving each bucket small enough that a window covering a handful of cells examines
#: tens of candidates rather than thousands. Exposed as a constant rather than a parameter
#: because a join's caller has no way to reason about it and a wrong value only costs speed.
comptime GEO_JOIN_TARGET_PER_CELL: Int = 4

#: The most pairs a join will emit: two Int arrays plus a Float64, so 2^22 pairs is ~100 MB.
#: Declared here rather than in `contract` because the `dim max_pairs <= ...` block below
#: names it, and the capability gate resolves such a name only against a same-file `comptime`
#: — a ceiling declared in one file and tested in another can drift with no gate noticing.
comptime GEO_MAX_PAIRS: Int = 1 << 22


@fieldwise_init
struct GeoJoin(Copyable, Movable):
    """Pairs within a radius, with the cost of finding them.

    Pairs come back ordered by left id then right id — a total order, so the result is a
    function of the input and not of the index layout. `truncated` and the
    `GEO_OK_TRUNCATED` status carry the same fact twice on purpose: a caller reading only the
    status and a caller reading only the flag both learn that pairs are missing.

    `candidates_examined` and `cells_examined` are the two halves of the search cost, reported
    separately because they scale differently and BOTH are charged against the work ceiling. A
    large radius over a sparse right side is nearly all cells: a search box can cover 42 000
    index cells and examine zero candidates, so a ceiling on candidates alone would price it
    at nothing while it ran for minutes.
    """

    var status: Int
    var n_left: Int
    var n_right: Int
    var n_pairs: Int
    var truncated: Bool
    var candidates_examined: Int
    var cells_examined: Int
    var full_scan_cost: Int
    var has_selectivity: Bool
    var selectivity: Float64
    var seam_point: Int
    var left_ids: List[Int]
    var right_ids: List[Int]
    var distance_m: List[Float64]


@fieldwise_init
struct GeoRingJoin(Copyable, Movable):
    """Which ring of a multipolygon each point falls in.

    `ring_of_point[i]` is -1 when no ring contains point `i`, and the LOWEST ring index when
    several do. `n_multi` counts the points several rings claimed, so overlapping rings are
    visible rather than silently resolved. `code_of_point[i]` is the `GEO_PIP_*` code for the
    ring that won, so a point on a shared edge is reported as `GEO_PIP_BOUNDARY` rather than
    presented as interior.

    `cells_examined` is the index cells the ring boxes covered, reported beside
    `candidates_examined` because both are charged: a wide ring box over a clustered point set
    reads cells and examines nothing.
    """

    var status: Int
    var n_points: Int
    var n_rings: Int
    var n_matched: Int
    var n_boundary: Int
    var n_multi: Int
    var candidates_examined: Int
    var cells_examined: Int
    var full_scan_cost: Int
    var rings_refused: Int
    var ring_of_point: List[Int]
    var code_of_point: List[Int]


@fieldwise_init
struct GeoRouteMatrix(Copyable, Movable):
    """An origins x destinations matrix of metre distances, row-major.

    `reachable` is the authority for the network variant: a pair with no path has
    `reachable = False` and a distance slot of 0.0, which is representable, and 0.0 must not
    be read as "the same place". For the crow-flies variant every pair is reachable by
    definition and the list is all True.
    """

    var status: Int
    var n_rows: Int
    var n_cols: Int
    var n_cells: Int
    var n_unreachable: Int
    var network: Bool
    var has_extremes: Bool
    var min_distance_m: Float64
    var max_distance_m: Float64
    var distance_m: List[Float64]
    var reachable: List[Bool]


# ── refusal constructors ──────────────────────────────────────────────────────


fn _no_join(status: Int, n_left: Int, n_right: Int, seam_point: Int) -> GeoJoin:
    var l = List[Int]()
    var r = List[Int]()
    var d = List[Float64]()
    return GeoJoin(
        status, n_left, n_right, 0, False, 0, 0, 0, False, 0.0, seam_point, l^, r^, d^
    )


fn _no_ring_join(status: Int, n_points: Int, n_rings: Int) -> GeoRingJoin:
    var a = List[Int]()
    var b = List[Int]()
    return GeoRingJoin(status, n_points, n_rings, 0, 0, 0, 0, 0, 0, 0, a^, b^)


fn _no_matrix(status: Int, rows: Int, cols: Int, network: Bool) -> GeoRouteMatrix:
    var d = List[Float64]()
    var r = List[Bool]()
    return GeoRouteMatrix(status, rows, cols, 0, 0, network, False, 0.0, 0.0, d^, r^)


# ── radius join ───────────────────────────────────────────────────────────────


# The parameter PACKING below is load-bearing, not style. `mojo_inventory` parses a
# signature inside a TEN-LINE lookahead window and silently drops a function whose signature
# closes later — no error, the function simply is not in the contract. Do not reflow.
fn join_within_flat(
    lxs: List[Float64], lys: List[Float64], n_left: Int,
    rxs: List[Float64], rys: List[Float64], n_right: Int,
    radius_m: Float64, frame: Int, metric: Int, max_pairs: Int,
) -> GeoJoin:
    """Every (left, right) pair within `radius_m` metres, indexed on the right side.

    The right side is indexed ONCE (`index.grid_build_flat`) and each left point probes it
    with its own search box (`index.grid_window_flat`), so the pair search never forms the
    full cross product. The box is a superset of the true disc — see `contract.geo_degree_box_half` — and
    the exact metre distance from the frozen metric is what admits a pair, so the box only
    ever removes work, never changes the answer.

    Both operands are in ONE frame by signature, so degrees cannot be joined against metres.
    A degree-frame search box that would cross the antimeridian is refused with
    `GEO_ERR_ANTIMERIDIAN` and `seam_point` naming the first left point involved, because the
    alternative — clipping the box at +-180 — silently drops every pair across the seam.

    `radius_m` must be finite and non-negative; a zero radius is a legitimate request that
    matches only exactly coincident points — including, in a self-join, every point with
    itself, since `d = 0.0 <= 0.0`.

    Both halves of the probe cost are charged against `contract.GEO_MAX_CANDIDATE_WORK`: the
    candidates examined AND the cells covered. They are independent quantities — a wide radius
    over a clustered right side covers tens of thousands of empty cells per box and examines no
    candidate — so charging candidates alone let a request with a declared and reported cost of
    ZERO run for minutes. Exceeding the ceiling truncates (`GEO_OK_TRUNCATED`, `truncated`
    True), it does not silently return the pairs found so far under a plain OK.

    @capability join_within_flat
    complexity: O(n_right log n_right + n_left * (cells_per_box + candidates_per_box))
    counts:
    - n_left <= len(lxs, lys) [kernel_validated]
    - n_right <= len(rxs, rys) [kernel_validated]
    - dim max_pairs <= GEO_MAX_PAIRS [kernel_validated]
    @endcapability
    """
    var md = geo_metric_defect(frame, metric)
    if md != GEO_OK:
        return _no_join(md, n_left, n_right, -1)
    if not geo_finite(radius_m) or radius_m < 0.0:
        return _no_join(GEO_ERR_PARAM, n_left, n_right, -1)
    if max_pairs < 0 or max_pairs > GEO_MAX_PAIRS:
        return _no_join(GEO_ERR_PARAM, n_left, n_right, -1)
    var ld = geo_points_defect(lxs, lys, n_left, frame, GEO_MAX_POINTS)
    if ld != GEO_OK:
        return _no_join(ld, n_left, n_right, -1)
    var rd = geo_points_defect(rxs, rys, n_right, frame, GEO_MAX_POINTS)
    if rd != GEO_OK:
        return _no_join(rd, n_left, n_right, -1)

    var grid = grid_build_flat(rxs, rys, n_right, frame, GEO_JOIN_TARGET_PER_CELL)
    if grid.status != GEO_OK:
        return _no_join(grid.status, n_left, n_right, -1)

    var degrees = geo_is_degree_frame(frame)
    var x_is_lat = frame == GEO_FRAME_LATLON_DEG
    var lat_half = radius_m / GEO_M_PER_DEG
    var left_ids = List[Int]()
    var right_ids = List[Int]()
    var dists = List[Float64]()
    var candidates = 0
    #: Index cells read, and the SUM of both costs, which is the quantity the ceiling bounds.
    #: `grid_window_flat` declares its own cost as O(cells covered + candidates examined) and
    #: the two are independent: a 200 km radius over a right side clustered on a diagonal
    #: covers ~42 000 cells per box and examines no candidate at all. Charging candidates
    #: alone measured 636 us per left point at a charged cost of ZERO, which at the admitted
    #: `n_left` ceiling is eleven minutes of work the budget could not see.
    var cells = 0
    var work = 0
    var truncated = False
    for i in range(n_left):
        var half_x = radius_m
        var half_y = radius_m
        if degrees:
            var lat = geo_lat_of(lxs[i], lys[i], frame)
            var lon_half = geo_degree_box_half(radius_m, lat)
            # The frame decides which axis carries longitude; nothing here assumes an order.
            if x_is_lat:
                half_x = lat_half
                half_y = lon_half
            else:
                half_x = lon_half
                half_y = lat_half
        var qminx = lxs[i] - half_x
        var qmaxx = lxs[i] + half_x
        var qminy = lys[i] - half_y
        var qmaxy = lys[i] + half_y
        if degrees:
            var lon_lo = qminx
            var lon_hi = qmaxx
            if x_is_lat:
                lon_lo = qminy
                lon_hi = qmaxy
            if lon_lo < -GEO_MAX_LON_DEG or lon_hi > GEO_MAX_LON_DEG:
                return _no_join(GEO_ERR_ANTIMERIDIAN, n_left, n_right, i)
            # Latitude does not wrap: a box reaching past a pole is clamped, which is
            # correct — there is no data beyond +-90 to miss.
            if x_is_lat:
                if qminx < -GEO_MAX_LAT_DEG:
                    qminx = -GEO_MAX_LAT_DEG
                if qmaxx > GEO_MAX_LAT_DEG:
                    qmaxx = GEO_MAX_LAT_DEG
            else:
                if qminy < -GEO_MAX_LAT_DEG:
                    qminy = -GEO_MAX_LAT_DEG
                if qmaxy > GEO_MAX_LAT_DEG:
                    qmaxy = GEO_MAX_LAT_DEG
        var win = grid_window_flat(
            grid.cell_start, grid.cell_items, rxs, rys, n_right, grid.side,
            grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
            qminx, qminy, qmaxx, qmaxy, frame,
        )
        if win.status != GEO_OK:
            return _no_join(win.status, n_left, n_right, -1)
        candidates += win.candidates_examined
        cells += win.cells_examined
        work += win.cells_examined + win.candidates_examined
        if work > GEO_MAX_CANDIDATE_WORK:
            truncated = True
            break
        # The matching right ids for THIS left point, as exact Float64 so the frozen
        # `sorting.mergesort` can order them in O(m log m). An id is at most
        # GEO_MAX_POINTS - 1 = 2^20 - 1, far inside the 2^53 integers Float64 represents
        # exactly, so the round trip through `Int(...)` below is lossless — which is the only
        # reason a Float64 sort may carry an integer key at all.
        #
        # The first version of this loop emitted in cell order and then insertion-sorted each
        # left point's run in place. That is O(m^2), and `max_pairs` allows m = 2^22, so a
        # single left point matching a dense right side turned a bounded candidate scan into
        # 1.7e13 comparisons at a declared cost of O(m log m) — rule 1c's defect exactly.
        var hits = List[Float64]()
        for c in range(len(win.ids)):
            var j = win.ids[c]
            var d = frame_metric_distance(lxs[i], lys[i], rxs[j], rys[j], frame, metric)
            if frame_metric_undefined(
                d, lxs[i], lys[i], rxs[j], rys[j], frame, metric
            ):
                # A metric that could not measure this pair must not admit it as "0 m apart",
                # which is what makes an antipodal pair look like the closest match there is.
                return _no_join(GEO_ERR_METRIC_NO_CONVERGENCE, n_left, n_right, i)
            if d <= radius_m:
                hits.append(Float64(j))
        var ordered = mergesort(hits)
        for c in range(len(ordered)):
            if len(left_ids) >= max_pairs:
                truncated = True
                break
            var j = Int(ordered[c])
            left_ids.append(i)
            right_ids.append(j)
            dists.append(
                geo_finite_or_zero(
                    frame_metric_distance(lxs[i], lys[i], rxs[j], rys[j], frame, metric)
                )
            )
        if truncated:
            break

    # The result is ordered by left id (the outer loop) then right id (the sort above), which
    # is a TOTAL order and therefore independent of `GEO_JOIN_TARGET_PER_CELL` and of the cell
    # layout it produces. That matters beyond tidiness: it means the pair list is a function of
    # the caller's data, so changing the index's internal resolution cannot change the answer,
    # and a truncated join keeps the smallest right ids rather than whichever cell was read
    # first.
    var full = n_left * n_right
    var has_sel = full > 0
    var sel = 0.0
    if has_sel:
        sel = Float64(candidates) / Float64(full)
    var status = GEO_OK_TRUNCATED if truncated else GEO_OK
    return GeoJoin(
        status,
        n_left,
        n_right,
        len(left_ids),
        truncated,
        candidates,
        cells,
        full,
        has_sel,
        geo_finite_or_zero(sel),
        -1,
        left_ids^,
        right_ids^,
        dists^,
    )


# ── point-in-ring join ────────────────────────────────────────────────────────


# Packing is load-bearing — see the note above `join_within_flat`.
fn join_point_in_rings_flat(
    pxs: List[Float64], pys: List[Float64], n_points: Int,
    ring_xs: List[Float64], ring_ys: List[Float64],
    ring_offsets: List[Int], n_rings: Int, frame: Int,
) -> GeoRingJoin:
    """Assign each point to the first ring of a multipolygon that contains it.

    Rings arrive CSR-style: ring `g` occupies `[ring_offsets[g], ring_offsets[g + 1])` in the
    coordinate arrays, validated by `contract.geo_offsets_defect` — the same four conditions
    `sparse_numerics.csr.csr_validate_flat` checks, because an unchecked offsets array is the
    same uncatchable abort.

    The points are indexed once and each ring probes the index with its own bounding box, so
    the cost is O(candidates) rather than O(n_points * n_rings). `full_scan_cost` is that
    product, so the saving is measured.

    Two decisions a caller must know about:

    * A point on a shared EDGE of two adjacent rings belongs to the lower-indexed ring, and
      `code_of_point` says `GEO_PIP_BOUNDARY` rather than `GEO_PIP_INSIDE`. Every tiling has
      shared edges, so "the point is on a boundary" must be an answer and not an error, and
      the tiebreak must be deterministic rather than layout-dependent.
    * A ring that is not admissible as a planar ring — an antimeridian edge, a pole
      encirclement, fewer than three vertices — is SKIPPED and counted in `rings_refused`.
      Refusing the whole join because one ring of a thousand is broken would make the useful
      answer unreachable; silently treating that ring as empty would hide it. The count is
      the middle path and it is not zero when something was dropped.

    The real work is `sum over rings of (candidates in that ring's box) * (its vertex count)`,
    and that sum is accumulated as the loop runs and stopped at `GEO_MAX_CANDIDATE_WORK` with
    `GEO_ERR_BUDGET`. Charging `n_points * n_rings` alone — which is what the first version of
    this function did — leaves the vertex factor free: a thousand 2000-vertex rings over a
    thousand points is 1e6 by that measure and 2e9 edge tests in reality. The budget cannot be
    decided up front without giving up the index's whole benefit, since the point of the box
    probe is that candidates are far below `n_points`, so it is checked incrementally against
    the next ring's cost before that ring is paid for.

    The CELLS each ring's box covers are charged as well, and for the same reason one step
    further out: an index probe costs O(cells covered + candidates examined), so a thousand
    wide rings over a clustered point set can read millions of empty cells while examining no
    candidate and paying nothing. `cells_examined` reports the total beside
    `candidates_examined`.

    @capability join_point_in_rings_flat
    complexity: O(n_points + total_vertices + sum over rings of (cells_in_box + candidates * vertices))
    counts:
    - n_points <= len(pxs, pys) [kernel_validated]
    - n_rings + 1 == len(ring_offsets) [kernel_validated]
    @endcapability
    """
    var pd = geo_points_defect(pxs, pys, n_points, frame, GEO_MAX_POINTS)
    if pd != GEO_OK:
        return _no_ring_join(pd, n_points, n_rings)
    var n_vertices = len(ring_xs)
    if len(ring_ys) < n_vertices:
        n_vertices = len(ring_ys)
    var od = geo_offsets_defect(ring_offsets, n_rings, n_vertices, GEO_MAX_POINTS)
    if od != GEO_OK:
        return _no_ring_join(od, n_points, n_rings)
    if not geo_cells_fit(n_points, n_rings, GEO_MAX_CANDIDATE_WORK):
        return _no_ring_join(GEO_ERR_BUDGET, n_points, n_rings)

    var ring_of = List[Int]()
    var code_of = List[Int]()
    for _ in range(n_points):
        ring_of.append(-1)
        code_of.append(GEO_PIP_OUTSIDE)
    if n_points == 0 or n_rings == 0:
        return GeoRingJoin(
            GEO_OK, n_points, n_rings, 0, 0, 0, 0, 0, n_points * n_rings, 0,
            ring_of^, code_of^,
        )

    var grid = grid_build_flat(pxs, pys, n_points, frame, GEO_JOIN_TARGET_PER_CELL)
    if grid.status != GEO_OK:
        return _no_ring_join(grid.status, n_points, n_rings)

    var candidates = 0
    var refused = 0
    #: Edge tests spent so far, i.e. sum of (candidates in box) * (ring vertices), PLUS the
    #: index cells each box covered. The quantity `GEO_MAX_CANDIDATE_WORK` actually bounds;
    #: `candidates` alone does not, because a candidate costs one edge test per ring vertex and
    #: because a box that examines no candidate at all still reads every cell it covers.
    var work = 0
    var cells = 0
    var multi = List[Int]()
    for _ in range(n_points):
        multi.append(0)
    for g in range(n_rings):
        var s = ring_offsets[g]
        var e = ring_offsets[g + 1]
        var m = e - s
        if m < 3 or m > GEO_MAX_RING_VERTICES:
            refused += 1
            continue
        var vx = List[Float64]()
        var vy = List[Float64]()
        var ok = True
        var min_x = ring_xs[s]
        var max_x = ring_xs[s]
        var min_y = ring_ys[s]
        var max_y = ring_ys[s]
        for t in range(s, e):
            if geo_pair_range_defect(ring_xs[t], ring_ys[t], frame) != GEO_OK:
                ok = False
                break
            vx.append(ring_xs[t])
            vy.append(ring_ys[t])
            if ring_xs[t] < min_x:
                min_x = ring_xs[t]
            if ring_xs[t] > max_x:
                max_x = ring_xs[t]
            if ring_ys[t] < min_y:
                min_y = ring_ys[t]
            if ring_ys[t] > max_y:
                max_y = ring_ys[t]
        if not ok:
            refused += 1
            continue
        if ring_planar_defect_flat(vx, vy, m, frame) != GEO_OK:
            refused += 1
            continue
        var win = grid_window_flat(
            grid.cell_start, grid.cell_items, pxs, pys, n_points, grid.side,
            grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
            min_x, min_y, max_x, max_y, frame,
        )
        if win.status != GEO_OK:
            return _no_ring_join(win.status, n_points, n_rings)
        candidates += win.candidates_examined
        cells += win.cells_examined
        # The cells this probe has just read, charged after the fact because one probe is
        # bounded by side * side <= GEO_MAX_GRID_CELLS and cannot itself run away; it is the
        # SUM over rings that can.
        if win.cells_examined > GEO_MAX_CANDIDATE_WORK - work:
            return _no_ring_join(GEO_ERR_BUDGET, n_points, n_rings)
        work += win.cells_examined
        # The edge tests this ring is about to cost, charged BEFORE they are spent. Refusing
        # here rather than truncating is deliberate: a ring-membership answer that silently
        # stops after ring 400 of 1000 reports "outside" for every later point, which is the
        # absence-read-as-zero defect wearing a status of OK.
        if not geo_cells_fit(len(win.ids), m, GEO_MAX_CANDIDATE_WORK - work):
            return _no_ring_join(GEO_ERR_BUDGET, n_points, n_rings)
        work += len(win.ids) * m
        var cand_x = List[Float64]()
        var cand_y = List[Float64]()
        for c in range(len(win.ids)):
            cand_x.append(pxs[win.ids[c]])
            cand_y.append(pys[win.ids[c]])
        var cls = points_in_ring_flat(
            cand_x, cand_y, len(win.ids), vx, vy, m, frame
        )
        if cls.status != GEO_OK:
            refused += 1
            continue
        for c in range(len(win.ids)):
            var code = cls.codes[c]
            if code == GEO_PIP_OUTSIDE:
                continue
            var pid = win.ids[c]
            multi[pid] += 1
            if ring_of[pid] < 0:
                ring_of[pid] = g
                code_of[pid] = code

    var matched = 0
    var boundary = 0
    var many = 0
    for i in range(n_points):
        if ring_of[i] >= 0:
            matched += 1
            if code_of[i] == GEO_PIP_BOUNDARY:
                boundary += 1
        if multi[i] > 1:
            many += 1
    return GeoRingJoin(
        GEO_OK,
        n_points,
        n_rings,
        matched,
        boundary,
        many,
        candidates,
        cells,
        n_points * n_rings,
        refused,
        ring_of^,
        code_of^,
    )


# ── route matrices ────────────────────────────────────────────────────────────


# Packing is load-bearing — see the note above `join_within_flat`.
fn route_matrix_flat(
    oxs: List[Float64], oys: List[Float64], n_origins: Int,
    dxs: List[Float64], dys: List[Float64], n_dests: Int,
    frame: Int, metric: Int,
) -> GeoRouteMatrix:
    """The CROW-FLIES matrix: metre distance from every origin to every destination.

    Row-major, `n_origins * n_dests` cells, each one a call into the frozen metric. This is
    a lower bound on travel distance and is not a travel matrix — `network_route_matrix_flat`
    is that, and the two are separate functions so a caller cannot get one while believing it
    asked for the other.

    The cell count is charged against `GEO_MAX_MATRIX_CELLS` BEFORE anything is allocated,
    and by DIVISION (`contract.geo_cells_fit`), since `n_origins * n_dests` is a wrapping
    multiply. That one ceiling bounds both the allocation and the work, because they are the
    same number here — which is not generally true, and is why the ceiling is named for
    cells rather than for bytes.

    @capability route_matrix_flat
    complexity: O(n_origins * n_dests)
    counts:
    - n_origins <= len(oxs, oys) [kernel_validated]
    - n_dests <= len(dxs, dys) [kernel_validated]
    @endcapability
    """
    var md = geo_metric_defect(frame, metric)
    if md != GEO_OK:
        return _no_matrix(md, n_origins, n_dests, False)
    var od = geo_points_defect(oxs, oys, n_origins, frame, GEO_MAX_POINTS)
    if od != GEO_OK:
        return _no_matrix(od, n_origins, n_dests, False)
    var dd = geo_points_defect(dxs, dys, n_dests, frame, GEO_MAX_POINTS)
    if dd != GEO_OK:
        return _no_matrix(dd, n_origins, n_dests, False)
    if not geo_cells_fit(n_origins, n_dests, GEO_MAX_MATRIX_CELLS):
        return _no_matrix(GEO_ERR_BUDGET, n_origins, n_dests, False)
    var cells = n_origins * n_dests
    var dist = List[Float64]()
    var reach = List[Bool]()
    var lo = 0.0
    var hi = 0.0
    var seen = False
    for i in range(n_origins):
        for j in range(n_dests):
            var d = frame_metric_distance(
                oxs[i], oys[i], dxs[j], dys[j], frame, metric
            )
            if frame_metric_undefined(
                d, oxs[i], oys[i], dxs[j], dys[j], frame, metric
            ):
                return _no_matrix(
                    GEO_ERR_METRIC_NO_CONVERGENCE, n_origins, n_dests, False
                )
            dist.append(geo_finite_or_zero(d))
            reach.append(True)
            if not seen:
                lo = d
                hi = d
                seen = True
            else:
                if d < lo:
                    lo = d
                if d > hi:
                    hi = d
    return GeoRouteMatrix(
        GEO_OK,
        n_origins,
        n_dests,
        cells,
        0,
        False,
        seen,
        geo_finite_or_zero(lo),
        geo_finite_or_zero(hi),
        dist^,
        reach^,
    )


# Packing is load-bearing — see the note above `join_within_flat`.
fn network_route_matrix_flat(
    node_xs: List[Float64], node_ys: List[Float64], n_nodes: Int,
    edge_src: List[Int], edge_dst: List[Int], n_edges: Int,
    origin_nodes: List[Int], n_origins: Int,
    dest_nodes: List[Int], n_dests: Int, frame: Int, metric: Int,
) -> GeoRouteMatrix:
    """The TRAVEL matrix over a directed road network, in metres.

    Edge weights are not supplied: they are the metric distance between the two endpoint
    coordinates, so the graph and the geometry cannot disagree about how long an edge is. The
    adjacency is the frozen `graph_analytics.adjacency.graph_csr_from_triplets` and each row
    of the matrix is one frozen `graph_csr_dijkstra`.

    An unreachable pair is ABSENT, not large: `reachable` is False and the distance slot is
    0.0. That is inherited from `graph_csr_dijkstra`, which reports `reached` separately —
    and is why it is the kernel called rather than `graph.weighted.shortest_path_dijkstra`,
    which returns `1e18` for an unreachable node and lets a caller add it to a budget.

    A node index outside `[0, n_nodes)` in `origin_nodes` or `dest_nodes` is refused, not
    clamped: an origin the caller did not ask about would produce a full row of plausible
    wrong distances. Out-of-range EDGE endpoints are dropped by the frozen builder and
    reported through its own skip count, which is a different thing — a missing edge changes
    a distance, and `reachable` is what says the path is gone.

    Work is `n_origins * (n_edges + n_nodes log n_nodes)`, so BOTH `n_origins * n_edges` and
    `n_origins * n_nodes` are charged, each by division. Charging only the first leaves a hole
    that `n_edges = 0` walks straight through: an edgeless graph with 2^20 nodes and 2^22
    origins passes an edge-product budget of zero and then runs 2^22 Dijkstra initialisations
    over 2^20 nodes. Bounding the matrix allocation alone would leave the whole per-origin
    Dijkstra uncharged, which is the "bounding memory is not bounding work" defect.

    @capability network_route_matrix_flat
    complexity: O(n_origins * (n_edges + n_nodes log n_nodes))
    counts:
    - n_nodes <= len(node_xs, node_ys) [kernel_validated]
    - n_edges <= len(edge_src, edge_dst) [kernel_validated]
    - n_origins <= len(origin_nodes) [kernel_validated]
    - n_dests <= len(dest_nodes) [kernel_validated]
    @endcapability
    """
    var md = geo_metric_defect(frame, metric)
    if md != GEO_OK:
        return _no_matrix(md, n_origins, n_dests, True)
    var nd = geo_points_defect(node_xs, node_ys, n_nodes, frame, GEO_MAX_POINTS)
    if nd != GEO_OK:
        return _no_matrix(nd, n_origins, n_dests, True)
    if n_edges < 0 or n_edges > len(edge_src) or n_edges > len(edge_dst):
        return _no_matrix(GEO_ERR_COUNT, n_origins, n_dests, True)
    if n_origins < 0 or n_origins > len(origin_nodes):
        return _no_matrix(GEO_ERR_COUNT, n_origins, n_dests, True)
    if n_dests < 0 or n_dests > len(dest_nodes):
        return _no_matrix(GEO_ERR_COUNT, n_origins, n_dests, True)
    if not geo_cells_fit(n_origins, n_dests, GEO_MAX_MATRIX_CELLS):
        return _no_matrix(GEO_ERR_BUDGET, n_origins, n_dests, True)
    if not geo_cells_fit(n_origins, n_edges, GEO_MAX_CANDIDATE_WORK):
        return _no_matrix(GEO_ERR_BUDGET, n_origins, n_dests, True)
    if not geo_cells_fit(n_origins, n_nodes, GEO_MAX_CANDIDATE_WORK):
        return _no_matrix(GEO_ERR_BUDGET, n_origins, n_dests, True)
    for i in range(n_origins):
        if origin_nodes[i] < 0 or origin_nodes[i] >= n_nodes:
            return _no_matrix(GEO_ERR_PARAM, n_origins, n_dests, True)
    for j in range(n_dests):
        if dest_nodes[j] < 0 or dest_nodes[j] >= n_nodes:
            return _no_matrix(GEO_ERR_PARAM, n_origins, n_dests, True)

    var src = List[Int]()
    var dst = List[Int]()
    var w = List[Float64]()
    for k in range(n_edges):
        var a = edge_src[k]
        var b = edge_dst[k]
        src.append(a)
        dst.append(b)
        if a >= 0 and a < n_nodes and b >= 0 and b < n_nodes:
            var ew = frame_metric_distance(
                node_xs[a], node_ys[a], node_xs[b], node_ys[b], frame, metric
            )
            if frame_metric_undefined(
                ew, node_xs[a], node_ys[a], node_xs[b], node_ys[b], frame, metric
            ):
                # A zero-weight edge between two antipodal nodes would make every path
                # through it look free, so the graph is refused rather than built wrong.
                return _no_matrix(
                    GEO_ERR_METRIC_NO_CONVERGENCE, n_origins, n_dests, True
                )
            w.append(geo_finite_or_zero(ew))
        else:
            # The frozen builder drops this edge; the weight slot still has to exist so the
            # three arrays stay parallel, and 0.0 is the representable filler for a weight
            # that will never be read.
            w.append(0.0)
    var g = graph_csr_from_triplets(src, dst, w, n_nodes)

    var dist = List[Float64]()
    var reach = List[Bool]()
    var lo = 0.0
    var hi = 0.0
    var seen = False
    var unreachable = 0
    for i in range(n_origins):
        var sp = graph_csr_dijkstra(g, origin_nodes[i])
        if sp.status != GRAPH_OK:
            return _no_matrix(GEO_ERR_LAYOUT, n_origins, n_dests, True)
        if len(sp.distance) < n_nodes or len(sp.reached) < n_nodes:
            return _no_matrix(GEO_ERR_LAYOUT, n_origins, n_dests, True)
        for j in range(n_dests):
            var t = dest_nodes[j]
            if sp.reached[t]:
                var d = geo_finite_or_zero(sp.distance[t])
                dist.append(d)
                reach.append(True)
                if not seen:
                    lo = d
                    hi = d
                    seen = True
                else:
                    if d < lo:
                        lo = d
                    if d > hi:
                        hi = d
            else:
                dist.append(0.0)
                reach.append(False)
                unreachable += 1
    return GeoRouteMatrix(
        GEO_OK,
        n_origins,
        n_dests,
        n_origins * n_dests,
        unreachable,
        True,
        seen,
        geo_finite_or_zero(lo),
        geo_finite_or_zero(hi),
        dist^,
        reach^,
    )
