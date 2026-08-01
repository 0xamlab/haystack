"""
geospatial.index — the spatial index: a uniform cell grid whose buckets are a frozen CSR.

Zero Python imports.

Why a CELL GRID and not an R-tree
---------------------------------
Both were considered. The grid wins here for four reasons that are properties of this
codebase, not of the literature:

1. **The bucket layout already exists, frozen and tested.** A grid index is exactly a sparse
   matrix whose rows are cells and whose columns are point ids, so
   `sparse_numerics.csr.csr_build_from_triplets` builds it: `cell_start` IS the CSR row
   pointer and `cell_items` IS the (per-row sorted) column index array. An R-tree needs a
   node-splitting heuristic, which is new code with a quality/complexity trade-off and no
   reuse available anywhere in the tree.
2. **Determinism.** The layout is a pure function of (points, side) — the cell of a point is
   arithmetic, and the CSR sorts within each row. An R-tree's shape depends on INSERTION
   ORDER, so the same set of points inserted in a different order gives different node
   bounding boxes, different overlap and different candidate counts. A selectivity claim
   that changes with input order is not a claim.
3. **No recursion.** A query enumerates the cells the window covers by arithmetic and reads
   those buckets. An R-tree query descends, which rule 5 of this repo's kernel rules asks new
   code to avoid, and a malformed node array in a recursive descent is a much larger attack
   surface than an out-of-range bucket pointer.
4. **Bounded work per query, checkable in advance.** Cells touched is
   `(cols spanned) * (rows spanned)`, known before any point is read. An R-tree's examined
   node count is not known until it has been examined.

What the grid gives up is stated rather than hidden: cells are uniform, so a dataset with
extreme clustering puts many points in one bucket, and the selectivity of a query over the
dense region degrades toward a full scan. `max_cell_occupancy` reports exactly that, and
`target_per_cell` is the caller's lever.

H3 and S2 were the third option. Both are hierarchical cell systems over a spherical
subdivision (icosahedral for H3, cube-face plus Hilbert curve for S2), and both are worth
having — for SHARDING, where a globally stable cell id that does not depend on a dataset's
extent is the whole point. Neither is what an in-process window query needs, and
implementing either correctly is a substantial body of new arithmetic (H3's hexagonal
neighbourhood and pentagon distortion; S2's Hilbert curve and cell-boundary containment)
whose value here would be the same candidate set this grid produces. The grid is over the
DATA's own extent, which is why it is not a sharding key and is not offered as one.

Validation is LOCAL to what is read, and that is the difference between fast and pointless
-------------------------------------------------------------------------------------------
The layout arrays arrive over the wire with unknown provenance, and an unchecked
`for k in range(cell_start[c], cell_start[c + 1])` reading `cell_items[k]` and then `xs[id]`
is a three-deep uncatchable process abort. The obvious fix — validate the whole layout on
every query — costs O(n) and would erase the entire benefit of having an index: a
"sublinear" query with a linear guard in front of it is a linear query.

So every read is guarded AT THE POINT OF USE instead:

* `len(cell_start) == side * side + 1` — O(1), and the product is formed by DIVISION
  (`contract.geo_cells_fit`), because `side * side` is a wrapping multiply.
* `n <= len(xs)` and `n <= len(ys)` — O(1), and this is the bound whose absence kills the
  worker.
* for each cell actually touched: `0 <= start <= end <= len(cell_items)`.
* for each candidate actually read: `0 <= id < n`.

A query therefore costs O(cells touched + candidates examined) INCLUDING its validation, and
it cannot abort on any input. What it does not do is certify the parts of the layout it never
looked at: a corrupt pointer in an untouched cell goes unnoticed by that query.
`grid_validate_flat` is the O(n + cells) full certificate for a caller who wants one, and it
is a separate function because its cost is a separate decision.

The selectivity claim
---------------------
Every query returns `candidates_examined` beside `full_scan_cost` (which is `n`), so the
claim is measured on the caller's own data and never asserted. `benchmarks/.../bench_geospatial.mojo`
gates on the RATIO improving as the dataset grows at a fixed query area — which is the only
form of the claim that is scale-free, and the only one that a machine-speed change cannot
flatter.

k-nearest is EXACT, and says what the proof needs
-------------------------------------------------
`grid_knn_flat` expands rings of cells outward and stops when the ring's minimum possible
distance exceeds the current k-th distance. That stopping rule is only sound if a
coordinate-space gap can be converted into a LOWER bound in metres, and the first version of
this file did it the obvious way — gap times metres-per-degree-of-longitude at the worst
latitude in the band — which is NOT a lower bound. A parallel is not a great circle: two
points at latitude 60 separated by 48 degrees of longitude are 2609 km apart, while that
product claims 2669 km. A "lower bound" above the value it bounds ends the search early and
silently drops a nearer neighbour, so the exactness claim would have been false in exactly the
case nobody tests — a wide-extent degree grid at high latitude.

`contract.geo_gap_lower_m` derives the bound from the haversine identity the frozen
`geodesy.haversine_distance` computes, which makes it provable rather than plausible, and it
folds a raw longitude gap through the seam so 350 degrees is treated as 10. Every remaining
approximation is conservative and costs only extra candidates. Because the bound lives on that
sphere it does not carry to the WGS84 ellipsoid: an ellipsoidal request is refused with
`GEO_ERR_METRIC_UNSUPPORTED_HERE` rather than served with an exactness claim that has no
proof. `knn_scan_flat` is the O(n) brute force, and the suite asserts the two agree exactly —
including that the index's distances equal `heap.k_smallest` of the full distance list, which
is a frozen kernel used as the oracle.

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
golden_vectors: mojo/tests/libs/test_geospatial_index.mojo
benchmark: benchmarks/mojo_benchmarks/bench_geospatial.mojo
docs: gitbook/engine/geospatial.md
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, floor

from sparse_numerics.csr import CSR_OK, csr_build_from_triplets

from geospatial.contract import (
    GEO_ERR_ANTIMERIDIAN,
    GEO_ERR_BUDGET,
    GEO_ERR_COUNT,
    GEO_ERR_LAYOUT,
    GEO_ERR_METRIC_NO_CONVERGENCE,
    GEO_ERR_METRIC_UNSUPPORTED_HERE,
    GEO_ERR_PARAM,
    GEO_ERR_WINDOW,
    GEO_MAX_CANDIDATE_WORK,
    GEO_MAX_POINTS,
    GEO_METRIC_VINCENTY,
    GEO_OK,
    geo_cells_fit,
    geo_finite,
    geo_finite_or_zero,
    geo_frame_defect,
    geo_gap_lower_m,
    geo_is_degree_frame,
    geo_lat_of,
    geo_metric_defect,
    geo_pair_range_defect,
    geo_points_defect,
)
from geospatial.frame import frame_metric_distance, frame_metric_undefined

#: The largest grid side. `side * side` cells at `side <= 2^10` keeps the cell pointer array
#: at 2^20 + 1 entries (~8 MB), matched to `GEO_MAX_POINTS` so the index stays O(n) in the
#: point count.
#:
#: Declared HERE and not in `contract` for a mechanical reason: the `dim side <= ...` blocks
#: below name this constant, and the capability-manifest gate resolves such a name only
#: against a same-file `comptime <NAME>: Int = <literal>`. A ceiling declared in one file and
#: tested in another can drift without any gate noticing.
comptime GEO_MAX_GRID_SIDE: Int = 1 << 10

#: The largest cell count a grid may declare: `GEO_MAX_GRID_SIDE` squared, written as a
#: literal shift so it too resolves as a same-file ceiling.
comptime GEO_MAX_GRID_CELLS: Int = 1 << 20

#: The largest `target_per_cell` a caller may ask for. Bounded because `side` is derived from
#: it: an absurd target drives `_side_for` to the maximum side, and a 2^20-cell pointer array
#: for three points is work and memory nobody asked for.
comptime GEO_MAX_TARGET_PER_CELL: Int = 1 << 20


@fieldwise_init
struct GeoGrid(Copyable, Movable):
    """A uniform cell grid over a point set: `cell_start` + `cell_items` are a frozen CSR.

    Cell `c = row * side + col` occupies `cell_items[cell_start[c] : cell_start[c + 1]]`,
    and each entry there is an index into the caller's original coordinate arrays. Both
    arrays are EMPTY on a refusal; `has_extent` is False for an empty point set, where the
    extent does not exist and every extent slot is a meaningless 0.0.

    The struct is returned rather than held: the query functions take these arrays back as
    flat parameters, so nothing in this package keeps state between calls.
    """

    var status: Int
    var n_points: Int
    var frame: Int
    var side: Int
    var n_cells: Int
    var occupied_cells: Int
    var max_cell_occupancy: Int
    var skipped: Int
    var has_extent: Bool
    var min_x: Float64
    var min_y: Float64
    var max_x: Float64
    var max_y: Float64
    var cell_w: Float64
    var cell_h: Float64
    var cell_start: List[Int]
    var cell_items: List[Int]


@fieldwise_init
struct GeoWindow(Copyable, Movable):
    """The point ids inside a closed query box, with the cost of finding them.

    `ids` come back grouped by cell in row-major cell order and ascending within a cell —
    deterministic, and a pure function of the layout. They are NOT globally sorted: sorting
    would cost O(k log k) here or O(n) through a counting sort, and a caller who needs an
    order can impose the one it wants. `full_scan_cost` is `n`, so `candidates_examined`
    against it is the selectivity, measured rather than claimed.
    """

    var status: Int
    var n_found: Int
    var cells_examined: Int
    var candidates_examined: Int
    var full_scan_cost: Int
    var has_selectivity: Bool
    var selectivity: Float64
    var ids: List[Int]


@fieldwise_init
struct GeoKnn(Copyable, Movable):
    """The k nearest points to a query, ascending by distance then by id.

    `exact` is a claim with a proof behind it (see the module docstring) and is False only
    when the entry point could not establish it. `k_returned` may be below `k_requested`
    when the dataset holds fewer points — that is an answer, not a truncation, and
    `has_max_distance` distinguishes "no neighbours at all" from "the nearest is 0 m away".
    """

    var status: Int
    var k_requested: Int
    var k_returned: Int
    var exact: Bool
    var cells_examined: Int
    var candidates_examined: Int
    var rings_expanded: Int
    var has_max_distance: Bool
    var max_distance_m: Float64
    var ids: List[Int]
    var distance_m: List[Float64]


# ── internals ─────────────────────────────────────────────────────────────────


fn _no_grid(status: Int, n: Int, frame: Int) -> GeoGrid:
    var a = List[Int]()
    var b = List[Int]()
    return GeoGrid(
        status, n, frame, 0, 0, 0, 0, 0, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, a^, b^
    )


fn _no_window(status: Int, full_scan_cost: Int) -> GeoWindow:
    var ids = List[Int]()
    return GeoWindow(status, 0, 0, 0, full_scan_cost, False, 0.0, ids^)


fn _no_knn(status: Int, k: Int) -> GeoKnn:
    var ids = List[Int]()
    var ds = List[Float64]()
    return GeoKnn(status, k, 0, False, 0, 0, 0, False, 0.0, ids^, ds^)


fn _cell_axis(value: Float64, lo: Float64, width: Float64, side: Int) -> Int:
    """The cell index along one axis, clamped into `[0, side - 1]`.

    Clamped in BOTH directions, and the comparison is done in floating point BEFORE the
    conversion to `Int`. Both halves matter:

    * a negative index is an uncatchable abort (`a[-1]`), while a too-large one reads past
      the end — so neither may reach a subscript;
    * `Float64(Int(v))` is undefined, not truncated, once `v` leaves the integer grid
      (rule 4c), and `(value - lo) / width` with a denormal `width` is exactly how `v`
      leaves it. Guarding after the conversion would be guarding the poison.
    """
    if side <= 1:
        return 0
    if not (geo_finite(value) and geo_finite(lo) and geo_finite(width)):
        return 0
    if width <= 0.0:
        return 0
    var t = (value - lo) / width
    if not geo_finite(t) or t <= 0.0:
        return 0
    if t >= Float64(side):
        return side - 1
    var idx = Int(floor(t))
    if idx < 0:
        return 0
    if idx > side - 1:
        return side - 1
    return idx


fn _side_for(n: Int, target_per_cell: Int) -> Int:
    """The smallest `side` with `side * side * target_per_cell >= n`, capped at the ceiling.

    An integer loop rather than `ceil(sqrt(n / target))`: `side` is at most 1024, so the loop
    is trivially cheap, and it cannot land one cell off because of a square-root rounding —
    which would change the layout, and therefore every `candidates_examined` this package
    reports, between two machines whose libm differs.

    The condition is tested as `side * side >= ceil(n / target)` and NOT as
    `side * side * target >= n`, because the second form multiplies a caller-supplied integer
    and a 64-bit multiply WRAPS: `3 * 6148914691236517206 == 2`, so at
    `target_per_cell = 2^62` the product turns negative, the test never passes, and a
    three-point dataset silently gets the maximum 2^20-cell grid. In the form used here the
    only product is `side * side`, which is at most 2^20 by construction, and the division is
    exact integer arithmetic. `GEO_MAX_TARGET_PER_CELL` is refused by the caller as well, so
    this is belt to that brace only in the sense that it removes the wrap — the two guards
    answer different questions ("is the request sane" vs "is this arithmetic sound").
    """
    if n <= 0 or target_per_cell <= 0:
        return 1
    var need = (n - 1) // target_per_cell + 1
    var side = 1
    while side < GEO_MAX_GRID_SIDE:
        if side * side >= need:
            return side
        side += 1
    return GEO_MAX_GRID_SIDE


fn _ring_gap_lower_m(
    gap_coord: Float64,
    frame: Int,
    min_x: Float64,
    min_y: Float64,
    max_x: Float64,
    max_y: Float64,
) -> Float64:
    """A lower bound in metres on the distance to anything a `gap_coord` away, in this extent.

    Nothing but a call into `contract.geo_gap_lower_m` with the extent's own latitude band
    resolved through the frame. One line of glue, and it is a function rather than an inline
    expression so the ring-expansion stopping rule has exactly ONE definition of its bound —
    rule 3: a guard enforced in two places is enforced at two strengths.
    """
    var lat_a = geo_lat_of(min_x, min_y, frame)
    var lat_b = geo_lat_of(max_x, max_y, frame)
    return geo_gap_lower_m(gap_coord, frame, lat_a, lat_b)


# ── build ─────────────────────────────────────────────────────────────────────


fn grid_build_flat(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int, target_per_cell: Int
) -> GeoGrid:
    """Build a uniform cell grid over the first `n` points, in their own extent.

    The bucket layout is NOT written here: the cell of each point is computed and the pairs
    are handed to the frozen `sparse_numerics.csr.csr_build_from_triplets`, whose row pointer
    is `cell_start` and whose column indices are `cell_items`. That kernel already sums
    duplicates, drops out-of-range coordinates with a count, and sorts within each row — and
    a point belongs to exactly one cell, so no duplicate can arise and `skipped` must come
    back 0. It is returned anyway, and the suite asserts it, because a non-zero value would
    mean the cell arithmetic produced an id outside the grid it just declared.

    `side` is derived from `n` and `target_per_cell` so the cell COUNT scales with the point
    count: the pointer array is O(n) rather than O(1 / resolution^2), which is what makes an
    equal-angle grid affordable at any zoom. A degenerate extent (every point identical, or
    all collinear on one axis) gives a zero cell width on that axis, and every point then
    lands in column or row 0 — correct, and the reason `_cell_axis` refuses to divide by it.

    The extent is the DATA's own bounding box, not a global one, so `cell_start`/`cell_items`
    are meaningless without the extent fields they came back with. They are passed to the
    query functions together for that reason.

    @capability grid_build_flat
    complexity: O(n log n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    - dim target_per_cell <= GEO_MAX_TARGET_PER_CELL [kernel_validated]
    @endcapability
    """
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_POINTS)
    if defect != GEO_OK:
        return _no_grid(defect, n, frame)
    if target_per_cell <= 0 or target_per_cell > GEO_MAX_TARGET_PER_CELL:
        return _no_grid(GEO_ERR_PARAM, n, frame)
    var side = _side_for(n, target_per_cell)
    if not geo_cells_fit(side, side, GEO_MAX_GRID_CELLS):
        return _no_grid(GEO_ERR_PARAM, n, frame)
    var n_cells = side * side
    if n == 0:
        var start = List[Int]()
        for _ in range(n_cells + 1):
            start.append(0)
        var items = List[Int]()
        return GeoGrid(
            GEO_OK, 0, frame, side, n_cells, 0, 0, 0, False,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, start^, items^,
        )

    var min_x = xs[0]
    var max_x = xs[0]
    var min_y = ys[0]
    var max_y = ys[0]
    for i in range(n):
        if xs[i] < min_x:
            min_x = xs[i]
        if xs[i] > max_x:
            max_x = xs[i]
        if ys[i] < min_y:
            min_y = ys[i]
        if ys[i] > max_y:
            max_y = ys[i]
    var cell_w = (max_x - min_x) / Float64(side)
    var cell_h = (max_y - min_y) / Float64(side)
    if not geo_finite(cell_w):
        cell_w = 0.0
    if not geo_finite(cell_h):
        cell_h = 0.0

    var rows = List[Int]()
    var cols = List[Int]()
    var vals = List[Float64]()
    for i in range(n):
        var col = _cell_axis(xs[i], min_x, cell_w, side)
        var row = _cell_axis(ys[i], min_y, cell_h, side)
        rows.append(row * side + col)
        cols.append(i)
        vals.append(1.0)
    var built = csr_build_from_triplets(rows, cols, vals, n_cells, n)
    if built.status != CSR_OK or len(built.indptr) != n_cells + 1:
        return _no_grid(GEO_ERR_LAYOUT, n, frame)

    var occupied = 0
    var worst = 0
    for c in range(n_cells):
        var count = built.indptr[c + 1] - built.indptr[c]
        if count > 0:
            occupied += 1
        if count > worst:
            worst = count
    return GeoGrid(
        GEO_OK,
        n,
        frame,
        side,
        n_cells,
        occupied,
        worst,
        built.skipped,
        True,
        geo_finite_or_zero(min_x),
        geo_finite_or_zero(min_y),
        geo_finite_or_zero(max_x),
        geo_finite_or_zero(max_y),
        geo_finite_or_zero(cell_w),
        geo_finite_or_zero(cell_h),
        built.indptr.copy(),
        built.indices.copy(),
    )


fn grid_validate_flat(
    cell_start: List[Int], cell_items: List[Int], n: Int, side: Int
) -> Int:
    """The FULL O(n + cells) certificate for a layout, for a caller who wants one.

    Separate from the queries on purpose. The queries validate exactly what they read, which
    is what keeps them sublinear; this checks the whole layout, which is what a caller
    persisting an index across many queries should do once. The four conditions are the same
    ones `sparse_numerics.csr.csr_validate_flat` checks for a CSR, because that is what this
    is: a zero head, monotone pointers, a tail at the item count, and every item id in range.

    Monotonicity plus a zero head plus a tail equal to `len(cell_items)` bounds every pointer
    to `[0, nnz]`, so no separate per-pointer range test is needed.

    @capability grid_validate_flat
    complexity: O(n + side * side)
    counts:
    - dim side <= GEO_MAX_GRID_SIDE [kernel_validated]
    @endcapability
    """
    if n < 0 or side <= 0:
        return GEO_ERR_PARAM
    if side > GEO_MAX_GRID_SIDE:
        return GEO_ERR_PARAM
    if not geo_cells_fit(side, side, GEO_MAX_GRID_CELLS):
        return GEO_ERR_PARAM
    var n_cells = side * side
    if len(cell_start) != n_cells + 1:
        return GEO_ERR_LAYOUT
    if cell_start[0] != 0:
        return GEO_ERR_LAYOUT
    for c in range(1, n_cells + 1):
        if cell_start[c] < cell_start[c - 1]:
            return GEO_ERR_LAYOUT
    if cell_start[n_cells] != len(cell_items):
        return GEO_ERR_LAYOUT
    for k in range(len(cell_items)):
        if cell_items[k] < 0 or cell_items[k] >= n:
            return GEO_ERR_LAYOUT
    return GEO_OK


# ── window query ──────────────────────────────────────────────────────────────


fn _window_defect(
    qminx: Float64, qminy: Float64, qmaxx: Float64, qmaxy: Float64, frame: Int
) -> Int:
    """`GEO_OK` for a usable query box, else why it is not one.

    An inverted longitude range (`qminx > qmaxx`) in a DEGREE frame is how a caller spells a
    window that wraps the antimeridian, so it gets `GEO_ERR_ANTIMERIDIAN` and not a generic
    complaint: the fix is to split it into two windows, and only the caller knows whether
    that is what it meant. Silently returning the complement of the box — which is what a
    naive `x >= qminx and x <= qmaxx` yields for a wrapped window, i.e. nothing — is the
    quiet wrong answer. In a projected frame there is no seam, so an inverted range is just
    an inverted range.
    """
    var fd = geo_frame_defect(frame)
    if fd != GEO_OK:
        return fd
    if not (
        geo_finite(qminx) and geo_finite(qminy) and geo_finite(qmaxx) and geo_finite(qmaxy)
    ):
        return GEO_ERR_WINDOW
    if qminy > qmaxy:
        return GEO_ERR_WINDOW
    if qminx > qmaxx:
        if geo_is_degree_frame(frame):
            return GEO_ERR_ANTIMERIDIAN
        return GEO_ERR_WINDOW
    var lo = geo_pair_range_defect(qminx, qminy, frame)
    if lo != GEO_OK:
        return lo
    return geo_pair_range_defect(qmaxx, qmaxy, frame)


# The parameter PACKING below is load-bearing, not style. `mojo_inventory` parses a
# signature inside a TEN-LINE lookahead window; a signature that closes on the eleventh line
# is dropped from the runtime contract and from the dispatch with no error anywhere, so the
# function simply is not there. Measured on this package: `grid_window_flat` and
# `grid_knn_flat` at one parameter per line closed on line 17 and were both silently absent
# from the contract until they were packed. Do not reflow these.
fn window_scan_flat(
    xs: List[Float64], ys: List[Float64], n: Int,
    qminx: Float64, qminy: Float64, qmaxx: Float64, qmaxy: Float64, frame: Int,
) -> GeoWindow:
    """The FULL SCAN a window query is measured against. Closed box on both axes.

    Present as a first-class function, not only as benchmark scaffolding: the index's answer
    is only trustworthy if something independent produces the same set, and the suite
    asserts exactly that. It is also the right entry point below a few thousand points,
    where building a grid costs more than scanning.

    @capability window_scan_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var wd = _window_defect(qminx, qminy, qmaxx, qmaxy, frame)
    if wd != GEO_OK:
        return _no_window(wd, 0)
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_POINTS)
    if defect != GEO_OK:
        return _no_window(defect, 0)
    var ids = List[Int]()
    for i in range(n):
        if xs[i] >= qminx and xs[i] <= qmaxx and ys[i] >= qminy and ys[i] <= qmaxy:
            ids.append(i)
    var found = len(ids)
    var sel = 1.0 if n > 0 else 0.0
    return GeoWindow(GEO_OK, found, 0, n, n, n > 0, sel, ids^)


# Packing is load-bearing — see the note above `window_scan_flat`.
fn grid_window_flat(
    cell_start: List[Int], cell_items: List[Int],
    xs: List[Float64], ys: List[Float64], n: Int, side: Int,
    min_x: Float64, min_y: Float64, cell_w: Float64, cell_h: Float64,
    qminx: Float64, qminy: Float64, qmaxx: Float64, qmaxy: Float64, frame: Int,
) -> GeoWindow:
    """Point ids inside a closed query box, reading only the cells the box covers.

    Cost is O(cells covered + candidates examined) INCLUDING validation, because every read
    is guarded where it happens rather than by an O(n) pre-scan that would erase the point of
    having an index. A malformed layout is `GEO_ERR_LAYOUT` at the first bad pointer or id,
    never an abort. Two O(1) checks carry most of the weight: `len(cell_start)` against
    `side * side + 1` (formed by division, since the product wraps) and `n` against both
    coordinate array lengths.

    A box entirely outside the grid's extent returns `GEO_OK` with zero found — an answer, not
    a refusal. A caller may ask about empty space. It is not free: `_cell_axis` clamps such a
    box onto the boundary cells and those cells are read and reported in `cells_examined`.

    There is deliberately NO "box outside the extent, skip everything" early-out, and the
    reason is worth stating because the early-out looks obviously correct. The extent MAXIMUM
    is not a parameter here, and reconstructing it as `min_x + cell_w * side` is a rounding
    error away from the truth: for the 10x10 unit lattice with `min_x = 0`, `max_x = 0.9`,
    `cell_w = 0.09`, the product is 0.8999999999999999, so a query box on the grid's own right
    edge tested as "entirely outside" and every point on that edge — 19 of 100, the top row and
    the right column — vanished from the result under a status of OK. Clamping is exact where
    reconstruction is not: a box on the extent maximum lands in the last cell, which is where
    the points on the extent maximum are, and the per-candidate box test then decides.

    The extent parameters must be the ones `grid_build_flat` returned with these arrays. They
    are not recoverable from the arrays, so passing a different extent yields a wrong answer
    with no way for this function to know; that is why they travel together in `GeoGrid`.

    @capability grid_window_flat
    complexity: O(cells_covered + candidates_examined)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    - dim side <= GEO_MAX_GRID_SIDE [kernel_validated]
    @endcapability
    """
    var wd = _window_defect(qminx, qminy, qmaxx, qmaxy, frame)
    if wd != GEO_OK:
        return _no_window(wd, n)
    if side <= 0 or side > GEO_MAX_GRID_SIDE:
        return _no_window(GEO_ERR_PARAM, n)
    if n < 0 or n > GEO_MAX_POINTS:
        return _no_window(GEO_ERR_COUNT, n)
    if n > len(xs) or n > len(ys):
        return _no_window(GEO_ERR_COUNT, n)
    if not geo_cells_fit(side, side, GEO_MAX_GRID_CELLS):
        return _no_window(GEO_ERR_PARAM, n)
    var n_cells = side * side
    if len(cell_start) != n_cells + 1:
        return _no_window(GEO_ERR_LAYOUT, n)
    if not (geo_finite(min_x) and geo_finite(min_y)):
        return _no_window(GEO_ERR_LAYOUT, n)
    if not (geo_finite(cell_w) and geo_finite(cell_h)) or cell_w < 0.0 or cell_h < 0.0:
        return _no_window(GEO_ERR_LAYOUT, n)

    var col_lo = _cell_axis(qminx, min_x, cell_w, side)
    var col_hi = _cell_axis(qmaxx, min_x, cell_w, side)
    var row_lo = _cell_axis(qminy, min_y, cell_h, side)
    var row_hi = _cell_axis(qmaxy, min_y, cell_h, side)
    var ids = List[Int]()
    var cells = 0
    var candidates = 0
    for row in range(row_lo, row_hi + 1):
        for col in range(col_lo, col_hi + 1):
            var c = row * side + col
            cells += 1
            var s = cell_start[c]
            var e = cell_start[c + 1]
            if s < 0 or e < s or e > len(cell_items):
                return _no_window(GEO_ERR_LAYOUT, n)
            for k in range(s, e):
                var pid = cell_items[k]
                if pid < 0 or pid >= n:
                    return _no_window(GEO_ERR_LAYOUT, n)
                candidates += 1
                if (
                    xs[pid] >= qminx
                    and xs[pid] <= qmaxx
                    and ys[pid] >= qminy
                    and ys[pid] <= qmaxy
                ):
                    ids.append(pid)
    var sel = 0.0
    var has_sel = n > 0
    if has_sel:
        sel = Float64(candidates) / Float64(n)
    return GeoWindow(
        GEO_OK, len(ids), cells, candidates, n, has_sel, geo_finite_or_zero(sel), ids^
    )


# ── k nearest ─────────────────────────────────────────────────────────────────


fn _knn_insert(
    mut ids: List[Int],
    mut dists: List[Float64],
    k: Int,
    pid: Int,
    d: Float64,
) -> Bool:
    """Insert one candidate into a distance-ordered buffer of at most `k`. True if kept.

    Ordering is lexicographic on `(distance, id)`, so the result is a function of the SET of
    candidates and not of the order they were visited. Without the id tiebreak, two points at
    the same distance would come back in whichever order the cell layout produced, and the
    index and the brute-force scan would disagree on a tie while both being "correct".
    """
    var m = len(dists)
    if k <= 0:
        return False
    if m >= k:
        var worst = dists[m - 1]
        if d > worst:
            return False
        if d == worst and pid > ids[m - 1]:
            return False
    var pos = m
    for i in range(m):
        if d < dists[i] or (d == dists[i] and pid < ids[i]):
            pos = i
            break
    ids.insert(pos, pid)
    dists.insert(pos, d)
    while len(dists) > k:
        _ = ids.pop()
        _ = dists.pop()
    return True


# Packing is load-bearing — see the note above `window_scan_flat`.
fn knn_scan_flat(
    xs: List[Float64], ys: List[Float64], n: Int,
    qx: Float64, qy: Float64, k: Int, frame: Int, metric: Int,
) -> GeoKnn:
    """The O(n) brute-force k-nearest, which the indexed answer must reproduce exactly.

    `k` above `n` returns `n` neighbours with `k_returned < k_requested` — an answer, since
    a dataset of three points has three nearest neighbours. `k == 0` returns nothing with
    status `GEO_OK`; `k < 0` is `GEO_ERR_PARAM`, because a negative count that reaches
    subscript arithmetic anywhere downstream is fatal and silently treating it as zero hides
    a caller bug.

    The WORK is `n * min(k, n)`, not `n + k`, because `_knn_insert` walks a buffer of up to
    `k` entries per candidate. That product is what is charged against
    `GEO_MAX_CANDIDATE_WORK`, by division, and a request above it is `GEO_ERR_BUDGET`. The
    distinction is the one rule 1c names: at `k = 2^62` and `n = 2^20` the allocation is a
    harmless 8 MB while the loop is 5.5e11 comparisons, so a ceiling on the buffer alone
    would let a "valid" request run for hours. `k` is first reduced to `min(k, n)` — an answer
    can hold at most `n` neighbours, so that changes no result — and only then charged.

    @capability knn_scan_flat
    complexity: O(n * min(k, n))
    counts:
    - n <= len(xs, ys) [kernel_validated]
    - dim k [kernel_validated]
    @endcapability
    """
    var md = geo_metric_defect(frame, metric)
    if md != GEO_OK:
        return _no_knn(md, k)
    if k < 0:
        return _no_knn(GEO_ERR_PARAM, k)
    var qd = geo_pair_range_defect(qx, qy, frame)
    if qd != GEO_OK:
        return _no_knn(qd, k)
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_POINTS)
    if defect != GEO_OK:
        return _no_knn(defect, k)
    var k_eff = k
    if k_eff > n:
        k_eff = n
    if not geo_cells_fit(n, k_eff, GEO_MAX_CANDIDATE_WORK):
        return _no_knn(GEO_ERR_BUDGET, k)
    var ids = List[Int]()
    var dists = List[Float64]()
    for i in range(n):
        var d = frame_metric_distance(qx, qy, xs[i], ys[i], frame, metric)
        if frame_metric_undefined(d, qx, qy, xs[i], ys[i], frame, metric):
            # 0.0 from a metric that could not measure the pair would make an antipodal
            # point the nearest neighbour there is.
            return _no_knn(GEO_ERR_METRIC_NO_CONVERGENCE, k)
        _ = _knn_insert(ids, dists, k_eff, i, d)
    var got = len(ids)
    var worst = 0.0
    if got > 0:
        worst = dists[got - 1]
    return GeoKnn(
        GEO_OK, k, got, True, 0, n, 0, got > 0, geo_finite_or_zero(worst), ids^, dists^
    )


# Packing is load-bearing — see the note above `window_scan_flat`.
fn grid_knn_flat(
    cell_start: List[Int], cell_items: List[Int],
    xs: List[Float64], ys: List[Float64], n: Int, side: Int,
    min_x: Float64, min_y: Float64, cell_w: Float64, cell_h: Float64,
    qx: Float64, qy: Float64, k: Int, frame: Int, metric: Int,
) -> GeoKnn:
    """Exact k-nearest by expanding rings of cells, with the stopping rule stated.

    Ring `r` is the set of cells at Chebyshev distance `r` from the query's own cell. After
    the buffer holds `k` candidates, expansion stops once the ring's minimum possible
    distance exceeds the current k-th distance. The coordinate-space gap to anything in ring
    `r` or beyond is at least `(r - 1) * min(cell_w, cell_h)` — `r - 1` rather than `r`
    because the query may sit anywhere inside its own cell, and the smaller cell side because
    the gap may be realised on either axis — and `contract.geo_gap_lower_m` turns that gap
    into a lower bound in METRES.

    That conversion is where the exactness actually lives, and the obvious version of it is
    wrong: scaling a degree gap by `metres per degree of longitude at the worst latitude`
    OVER-estimates, because a parallel is not a great circle, and an over-estimated "lower
    bound" stops the search early and drops a nearer neighbour. `geo_gap_lower_m` derives the
    bound from the haversine identity itself. Every remaining approximation is conservative,
    so it can only cost extra candidates: a band reaching a pole gives a bound of zero, which
    degrades the search to a full scan and stays exact, and `rings_expanded` reports it.

    `GEO_METRIC_VINCENTY` is REFUSED here with `GEO_ERR_METRIC_UNSUPPORTED_HERE`. The bound is
    derived on the same sphere `geodesy.haversine_distance` uses; a WGS84 geodesic can be
    shorter than its spherical counterpart, so the bound would not be a bound and
    `exact = True` would be an unproven claim. `knn_scan_flat` serves Vincenty in O(n) with
    no bound to prove.

    Work, per rule 1c, is `(candidates examined) * min(k, n)` because the insert walks the
    buffer; the a-priori worst case is `n * min(k, n)` and that is what is charged against
    `GEO_MAX_CANDIDATE_WORK`. A ceiling on the buffer alone would leave the insert uncharged.

    @capability grid_knn_flat
    complexity: O((cells_examined + candidates_examined) * min(k, n))
    counts:
    - n <= len(xs, ys) [kernel_validated]
    - dim side <= GEO_MAX_GRID_SIDE [kernel_validated]
    - dim k [kernel_validated]
    @endcapability
    """
    var md = geo_metric_defect(frame, metric)
    if md != GEO_OK:
        return _no_knn(md, k)
    if metric == GEO_METRIC_VINCENTY:
        return _no_knn(GEO_ERR_METRIC_UNSUPPORTED_HERE, k)
    if k < 0:
        return _no_knn(GEO_ERR_PARAM, k)
    var qd = geo_pair_range_defect(qx, qy, frame)
    if qd != GEO_OK:
        return _no_knn(qd, k)
    if side <= 0 or side > GEO_MAX_GRID_SIDE:
        return _no_knn(GEO_ERR_PARAM, k)
    if n < 0 or n > GEO_MAX_POINTS:
        return _no_knn(GEO_ERR_COUNT, k)
    if n > len(xs) or n > len(ys):
        return _no_knn(GEO_ERR_COUNT, k)
    if not geo_cells_fit(side, side, GEO_MAX_GRID_CELLS):
        return _no_knn(GEO_ERR_PARAM, k)
    var n_cells = side * side
    if len(cell_start) != n_cells + 1:
        return _no_knn(GEO_ERR_LAYOUT, k)
    if not (geo_finite(min_x) and geo_finite(min_y)):
        return _no_knn(GEO_ERR_LAYOUT, k)
    if not (geo_finite(cell_w) and geo_finite(cell_h)) or cell_w < 0.0 or cell_h < 0.0:
        return _no_knn(GEO_ERR_LAYOUT, k)
    if k == 0:
        return GeoKnn(GEO_OK, 0, 0, True, 0, 0, 0, False, 0.0, List[Int](), List[Float64]())
    var k_eff = k
    if k_eff > n:
        k_eff = n
    if k_eff == 0:
        # An EMPTY index (n == 0) with k >= 1. There are no neighbours, which is an answer and
        # not a refusal — `knn_scan_flat` returns the same one. It has to be taken HERE: the
        # ring loop's stopping test is `len(dists) >= k_eff`, which is `0 >= 0` on the first
        # ring, and the next line reads `dists[len(dists) - 1]` — `dists[-1]` on an empty
        # List, an uncatchable bounds abort that kills the worker process and every dataset
        # resident in it. `grid_build_flat` over zero points returns exactly this state with
        # `GEO_OK`, so nothing about the input is malformed.
        return GeoKnn(GEO_OK, k, 0, True, 0, 0, 0, False, 0.0, List[Int](), List[Float64]())
    if not geo_cells_fit(n, k_eff, GEO_MAX_CANDIDATE_WORK):
        return _no_knn(GEO_ERR_BUDGET, k)

    # The latitude band the ring bound is derived in, widened OUTWARD by one cell on each
    # axis. The extent maximum is not a parameter and `min + cell * side` reconstructs it a
    # rounding error short of the truth; a band a rounding error too NARROW can exclude the
    # very point whose latitude sets the worst case, and a lower bound derived in the wrong
    # band is not a lower bound. Widening can only lower the bound, which costs extra
    # candidates and keeps `exact` true — the one direction of error that is safe here.
    var min_x_band = min_x - cell_w
    var min_y_band = min_y - cell_h
    var max_x = min_x + cell_w * Float64(side + 1)
    var max_y = min_y + cell_h * Float64(side + 1)
    var cell_min = cell_w
    if cell_h < cell_min:
        cell_min = cell_h
    var col0 = _cell_axis(qx, min_x, cell_w, side)
    var row0 = _cell_axis(qy, min_y, cell_h, side)

    var ids = List[Int]()
    var dists = List[Float64]()
    var cells = 0
    var candidates = 0
    var rings = 0
    for r in range(side + 1):
        rings = r
        if len(dists) > 0 and len(dists) >= k_eff and r >= 1:
            var bound = _ring_gap_lower_m(
                Float64(r - 1) * cell_min, frame, min_x_band, min_y_band, max_x, max_y
            )
            if bound > dists[len(dists) - 1]:
                break
        var row_lo = row0 - r
        var row_hi = row0 + r
        var col_lo = col0 - r
        var col_hi = col0 + r
        var any_cell = False
        for row in range(row_lo, row_hi + 1):
            if row < 0 or row >= side:
                continue
            for col in range(col_lo, col_hi + 1):
                if col < 0 or col >= side:
                    continue
                # Only the ring, not the filled square: the interior was visited at a
                # smaller `r` and re-reading it would make the cost quadratic in `r`.
                var on_ring = (
                    row == row_lo or row == row_hi or col == col_lo or col == col_hi
                )
                if r > 0 and not on_ring:
                    continue
                any_cell = True
                var c = row * side + col
                cells += 1
                var s = cell_start[c]
                var e = cell_start[c + 1]
                if s < 0 or e < s or e > len(cell_items):
                    return _no_knn(GEO_ERR_LAYOUT, k)
                for kk in range(s, e):
                    var pid = cell_items[kk]
                    if pid < 0 or pid >= n:
                        return _no_knn(GEO_ERR_LAYOUT, k)
                    candidates += 1
                    var d = frame_metric_distance(
                        qx, qy, xs[pid], ys[pid], frame, metric
                    )
                    _ = _knn_insert(ids, dists, k_eff, pid, d)
        if not any_cell and r > 0 and row_lo < 0 and row_hi >= side and col_lo < 0 and col_hi >= side:
            break
    var got = len(ids)
    var worst = 0.0
    if got > 0:
        worst = dists[got - 1]
    return GeoKnn(
        GEO_OK,
        k,
        got,
        True,
        cells,
        candidates,
        rings,
        got > 0,
        geo_finite_or_zero(worst),
        ids^,
        dists^,
    )
