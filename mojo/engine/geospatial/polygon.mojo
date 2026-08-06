"""
geospatial.polygon — point-in-polygon as a NUMERICAL problem, plus area and intersection.

Zero Python imports. The arithmetic that already exists is called, not rewritten:

  | quantity                       | frozen kernel called unchanged            |
  | ------------------------------ | ----------------------------------------- |
  | area MAGNITUDE of a ring       | `geometry.polygon_area` (shoelace, abs)    |
  | perimeter                      | `geometry.polygon_perimeter`               |
  | turn direction at a vertex     | `geometry.cross_product_2d`                |
  | segment-segment intersection   | `geometry.line_intersection`               |
  | projection to a metre plane    | `frame.frame_project_flat` -> `cartography` |
  | seam / pole verdict on a ring  | `frame.frame_ring_census_flat`             |

`geometry.point_in_polygon` already exists and is the standard crossing-number ray cast. It
is not called here, and the reason is the whole point of this module rather than a
preference — see the next section. It stays reachable and unchanged.

Point-in-polygon is a robustness problem, not a geometry problem
---------------------------------------------------------------
The frozen `geometry.point_in_polygon` returns `Bool`. That signature cannot express the
answer for a point ON the boundary, so it returns whatever the arithmetic happens to
produce, and it divides:

    if ((yi > p.y) != (yj > p.y)) and (p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi)

The guard makes `yj - yi` non-zero so the division is safe, but the QUOTIENT is a rounded
value compared against `p.x`, so a point exactly on a slanted edge lands on whichever side
the rounding falls. This module answers three-valued instead, and compares without dividing.

The five cases that break naive implementations, and this module's decision for each:

1. **Point strictly inside or outside.** Crossing number with a half-open y-range. Decided
   by the SIGN of an orientation determinant, never by a quotient:
   `isLeft = (x1-x0)*(py-y0) - (px-x0)*(y1-y0)`. Two multiplies and a subtract — no
   division, so no rounded intermediate is compared against a coordinate.

2. **Point exactly on an edge's interior.** `isLeft == 0.0` EXACTLY, and the point inside
   the edge's closed bounding box => `GEO_PIP_BOUNDARY`. Detected in its own pass, BEFORE
   any crossing is counted, so the answer never depends on how the crossing rule happens to
   treat it.

3. **Point exactly on a vertex.** Falls out of case 2: a vertex is in the closed bounding
   box of both its edges and gives `isLeft == 0.0` for both. No special case is needed, and
   a special case would be a second place for the convention to differ.

4. **Point on a HORIZONTAL edge.** Also case 2, and this is the case the crossing rule
   cannot decide at all: a horizontal edge at the ray's own height has no crossing. Because
   the boundary pass runs first, `(0.5, 0.0)` on the unit square's bottom edge is BOUNDARY,
   not the coin-flip that an epsilon-free crossing test alone would give.

5. **The ray passes exactly through a vertex.** The crossing rule is HALF-OPEN in y: an
   edge is considered only when `y0 <= py < y1` (upward) or `y1 <= py < y0` (downward). So
   each vertex belongs to exactly one of its two edges' ranges, a horizontal edge belongs to
   neither, and a vertex the ray grazes contributes either 0 or 2 crossings — never 1.
   Verified in the suite on an arrow polygon whose notch vertex sits exactly at the ray's
   height, where the two edges meeting there contribute +1 and -1 winding (net 0) and 2
   crossings (parity unchanged).

**There is no epsilon anywhere in the classification.** A point 1e-18 from an edge but not
exactly on it is classified inside or outside, deterministically, by the sign of the
determinant. That is a decision, not an oversight: the width of a tolerance band is a
number the caller never chose, it makes the predicate non-transitive (a point can be "on"
two edges that do not meet), and it makes the answer depend on the ring's coordinate
magnitude. Callers who need a band should buffer the ring, which is a modelling choice with
a unit.

**Two membership rules, both reported, because they disagree and the difference is real.**
`inside_even_odd` is crossing parity; `inside_nonzero` is a non-zero winding number. They
agree on every simple ring and differ exactly on self-intersecting ones — a figure-eight's
crossed lobe is "in" under the winding rule and "out" under parity. Returning one and
calling it "inside" would be picking a convention silently for the case where it matters, so
both come back and `ring_report_flat` says whether the ring is simple at all.

Area: the frozen magnitude, and only the SIGN is added
------------------------------------------------------
`geometry.polygon_area` returns `|A|`, discarding the sign, so ring ORIENTATION — which is
what tells an outer ring from a hole — is not obtainable from any frozen kernel. The sign is
therefore computed here, using the frozen kernel's OWN trapezoid form and OWN accumulation
order (`(x_j + x_i) * (y_j - y_i)` starting from `j = n - 1`), so `|sum| / 2` is
bit-identical to what `polygon_area` returns rather than merely close. `RingReport` carries
`magnitude_matches_frozen`, the module asserting its own consistency, and the returned
magnitude is the FROZEN kernel's value — this module contributes one integer, `+1`, `-1` or
`0`. Note the frozen accumulation is the NEGATED shoelace: a counter-clockwise ring gives a
negative sum, which is why the orientation is `-sign(sum)`.

Geodetic area is projected, and says so
---------------------------------------
An area in square degrees is not an area. `ring_area_flat` on a degree frame projects the
ring to a local equirectangular metre plane about the centre of its own extent (frozen
`cartography.equirectangular_*` via `frame.frame_project_flat`) and takes the frozen
shoelace there, returning m². East-west scale is exact only at the reference parallel, so
the latitude span is returned with the answer for the caller to bound the distortion. A
spherical-excess area is a DIFFERENT quantity computed by a different formula; it is not
offered here rather than offered approximately under the same name.

Intersection is convex-clip, and a non-convex clip is REFUSED
-------------------------------------------------------------
`ring_intersect_convex_flat` is Sutherland-Hodgman: the subject ring is clipped
half-plane by half-plane against the clip ring's edges, with each crossing point coming from
the frozen `geometry.line_intersection`. That algorithm is only correct when the CLIP ring
is convex, so convexity is verified and a non-convex clip is refused with
`GEO_ERR_NOT_CONVEX`. A general polygon-polygon boolean (Greiner-Hormann or Vatti) is a
different algorithm with its own degeneracy handling, and returning a Sutherland-Hodgman
result for a non-convex clip would be a plausible wrong polygon. The SUBJECT may be
non-convex; the result may then carry collinear degenerate edges along the clip boundary,
which change no area and are reported through `n_vertices`.

"Verified" means BOTH halves of the definition, because turn-sign consistency is not
convexity. A pentagram turns the same way at all five vertices, so a turn-sign gate alone
accepts it and returns the intersection of its five half-planes — the inner pentagon, a
plausible polygon that is not the intersection of anything the caller named. Convexity is
turn-sign consistency AND simplicity, and simplicity is the O(n^2) `_ring_simplicity` that
`ring_report_flat` reports; the clip gate calls the same one. That is also why a clip ring
above `contract.GEO_MAX_SIMPLICITY_VERTICES` is refused with `GEO_ERR_BUDGET` instead of
clipped: at that size the question is unaffordable, and "not asked" is not "answered no".

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
golden_vectors: mojo/tests/libs/test_geospatial_polygon.mojo
benchmark: benchmarks/mojo_benchmarks/bench_geospatial.mojo
docs: gitbook/engine/geospatial.md
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from geometry import (
    Point,
    cross_product_2d,
    line_intersection,
    polygon_area,
    polygon_perimeter,
)

from geospatial.contract import (
    GEO_ERR_ANTIMERIDIAN,
    GEO_ERR_BUDGET,
    GEO_ERR_DEGENERATE_RING,
    GEO_ERR_NOT_CONVEX,
    GEO_ERR_POLE,
    GEO_FRAME_LONLAT_DEG,
    GEO_MAX_CANDIDATE_WORK,
    GEO_MAX_POINTS,
    GEO_MAX_RING_VERTICES,
    GEO_MAX_SIMPLICITY_VERTICES,
    GEO_OK,
    geo_cells_fit,
    geo_finite_or_zero,
    geo_is_degree_frame,
    geo_pair_range_defect,
    geo_points_defect,
)
from geospatial.frame import frame_project_flat, frame_ring_census_flat

# ── classification values (not statuses; statuses all live in contract) ────────

comptime GEO_PIP_OUTSIDE: Int = 0
comptime GEO_PIP_INSIDE: Int = 1
comptime GEO_PIP_BOUNDARY: Int = 2

comptime GEO_ORIENT_CW: Int = -1
comptime GEO_ORIENT_DEGENERATE: Int = 0
comptime GEO_ORIENT_CCW: Int = 1


@fieldwise_init
struct RingReport(Copyable, Movable):
    """Everything structural about one ring, with every absent quantity flagged.

    `simplicity_checked` is False above `GEO_MAX_SIMPLICITY_VERTICES`, where the O(n^2)
    edge-pair test is not spent. `self_intersecting` is then False because nothing was
    checked, NOT because the ring is simple — read the flag first. This mirrors
    `optimization.routing.distance_matrix_check`'s `triangle_checked`.
    """

    var status: Int
    var n_vertices: Int
    var frame: Int
    var explicitly_closed: Bool
    var has_area: Bool
    var area: Float64
    var signed_area: Float64
    var orientation: Int
    var magnitude_matches_frozen: Bool
    var has_perimeter: Bool
    var perimeter: Float64
    var simplicity_checked: Bool
    var self_intersecting: Bool
    var bad_edge_a: Int
    var bad_edge_b: Int
    var duplicate_vertices: Int
    var is_convex: Bool
    var has_extent: Bool
    var min_x: Float64
    var min_y: Float64
    var max_x: Float64
    var max_y: Float64


@fieldwise_init
struct PipResult(Copyable, Movable):
    """Where one point lies relative to one ring: inside, outside, or ON the boundary.

    `classification` is the three-valued answer and is the field to branch on.
    `inside_even_odd` and `inside_nonzero` are the two membership rules, both reported
    because they disagree on a self-intersecting ring. `boundary_edge` is the index of the
    first edge the point lies on, or -1.
    """

    var status: Int
    var classification: Int
    var on_boundary: Bool
    var inside_even_odd: Bool
    var inside_nonzero: Bool
    var crossings: Int
    var winding_number: Int
    var boundary_edge: Int


@fieldwise_init
struct RingClassification(Copyable, Movable):
    """A batch of points classified against one ring. `codes` is EMPTY on any refusal."""

    var status: Int
    var n_points: Int
    var n_inside: Int
    var n_boundary: Int
    var n_outside: Int
    var edge_tests: Int
    var codes: List[Int]


@fieldwise_init
struct RingArea(Copyable, Movable):
    """The area of a ring in SQUARE METRES, and how it was obtained.

    `projected` True means the ring was in degrees and was carried onto a local metre plane
    about (`ref_lat_deg`, `ref_lon_deg`); the spans are there so the caller can bound the
    projection's distortion. False means the ring was already in metres and the answer is
    the frozen shoelace of it.
    """

    var status: Int
    var has_area: Bool
    var area_m2: Float64
    var signed_area_m2: Float64
    var orientation: Int
    var projected: Bool
    var ref_lat_deg: Float64
    var ref_lon_deg: Float64
    var lon_span_deg: Float64
    var lat_span_deg: Float64


@fieldwise_init
struct ClipResult(Copyable, Movable):
    """The intersection of a subject ring with a CONVEX clip ring.

    `is_empty` True with status `GEO_OK` is a real answer: two rings that do not overlap
    have an empty intersection. `xs`/`ys` are then empty, and so they are on a refusal —
    which is why `status` and not `len(xs)` is what distinguishes the two.
    """

    var status: Int
    var n_vertices: Int
    var is_empty: Bool
    var has_area: Bool
    var area: Float64
    var subject_convex: Bool
    var clip_convex: Bool
    var xs: List[Float64]
    var ys: List[Float64]


# ── shared internals ──────────────────────────────────────────────────────────


def _is_left(x0: Float64, y0: Float64, x1: Float64, y1: Float64, px: Float64, py: Float64) -> Float64:
    """`> 0` when (px, py) is strictly left of the directed segment (x0,y0) -> (x1,y1).

    The orientation determinant itself is the frozen `geometry.cross_product_2d` and is NOT
    re-spelled here — this is only the flat-scalar adapter onto it, so the whole module has
    one definition of "which side", the one already used by the convexity loops. An earlier
    version inlined the two multiplies; they were bit-for-bit the frozen kernel's, which is a
    duplicate definition of one quantity inside one file and exactly what this package argues
    against elsewhere.

    What it does NOT use is a division: the frozen `point_in_polygon` compares a QUOTIENT
    against `px`, which rounds, so a point exactly on a slanted edge lands on whichever side
    the rounding falls. Exactly `0.0` here means exactly collinear, which is what makes the
    boundary case decidable without an epsilon.
    """
    return cross_product_2d(Point(x0, y0), Point(x1, y1), Point(px, py))


def _in_closed_box(
    px: Float64, py: Float64, x0: Float64, y0: Float64, x1: Float64, y1: Float64
) -> Bool:
    """Whether (px, py) is inside the CLOSED bounding box of the segment's two endpoints.

    Paired with `_is_left(...) == 0.0` this is the exact on-segment test, including a
    zero-length segment (where it reduces to point equality) and a horizontal one.
    """
    var lo_x = x0
    var hi_x = x1
    if x1 < x0:
        lo_x = x1
        hi_x = x0
    var lo_y = y0
    var hi_y = y1
    if y1 < y0:
        lo_y = y1
        hi_y = y0
    return px >= lo_x and px <= hi_x and py >= lo_y and py <= hi_y


def _point_on_segment(
    px: Float64, py: Float64, x0: Float64, y0: Float64, x1: Float64, y1: Float64
) -> Bool:
    """Whether (px, py) lies EXACTLY on the closed segment. Collinear plus in the box.

    The single definition of "on an edge" for this whole module — the boundary pass of
    point-in-polygon, the spike test in the simplicity check and the touching branches of
    `_segments_cross` all call it, so the convention cannot be enforced at two strengths.
    """
    if _is_left(x0, y0, x1, y1, px, py) != 0.0:
        return False
    return _in_closed_box(px, py, x0, y0, x1, y1)


def _points_of(xs: List[Float64], ys: List[Float64], n: Int) -> List[Point]:
    """The first `n` pairs as frozen `geometry.Point`s, so the frozen kernels can be called.

    This glue is the missing driver: every polygon kernel in the frozen tree takes
    `List[Point]`, which cannot cross a JSON frame, so nothing reached them from a flat
    request. The caller must have validated `n` against both lists first — every public
    entry point here does, via `contract.geo_points_defect`.
    """
    var out = List[Point]()
    for i in range(n):
        out.append(Point(xs[i], ys[i]))
    return out^


def _frozen_trapezoid_sum(xs: List[Float64], ys: List[Float64], n: Int) -> Float64:
    """The frozen shoelace accumulation, WITHOUT the `fabs` — the sign is all that is taken.

    Byte-for-byte the loop inside `geometry.polygon_area`: the same `(x_j + x_i) *
    (y_j - y_i)` term, the same `j = n - 1` start, the same left-to-right order. That is
    deliberate and it is the reason `magnitude_matches_frozen` can be an `==` rather than a
    tolerance: any other equivalent formula would differ in the last bit and turn a
    self-check into a tolerance choice.

    The magnitude is NOT returned from here. `polygon_area` remains the definition of the
    area; this contributes the one integer the frozen kernel throws away.
    """
    if n < 3:
        return 0.0
    var total: Float64 = 0.0
    var j = n - 1
    for i in range(n):
        total += (xs[j] + xs[i]) * (ys[j] - ys[i])
        j = i
    return total


def _orientation_of_sum(total: Float64) -> Int:
    """`GEO_ORIENT_CCW` / `_CW` / `_DEGENERATE` from the frozen trapezoid sum.

    The frozen accumulation runs `(x_j + x_i) * (y_j - y_i)` from `j = n - 1`, which is the
    NEGATED shoelace: the counter-clockwise unit square (0,0) (1,0) (1,1) (0,1) sums to
    -2.0. So counter-clockwise is a negative sum, and the sign is inverted here rather than
    the loop being "fixed" — the loop must stay identical to the frozen one.
    """
    if total < 0.0:
        return GEO_ORIENT_CCW
    if total > 0.0:
        return GEO_ORIENT_CW
    return GEO_ORIENT_DEGENERATE


def ring_planar_defect_flat(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int
) -> Int:
    """`GEO_OK` when this ring may be treated as a planar ring in its own frame.

    A degree ring is refused when it encircles a pole (its longitude winding is +-360, and its
    boundary does not separate the longitude/latitude plane the way every algorithm below
    assumes) or when an edge crosses the antimeridian (its shortest connection is ambiguous,
    so no planar algorithm can know which way the edge goes). Both are explicit refusals with
    their own codes — never a silently wrong area or membership.

    The POLE test runs first, and the order is not arbitrary. A ring that encircles a pole
    ALWAYS contains a seam edge — its shortest longitude steps sum to +-360 while its raw
    differences sum to 0, so some edge must differ from its raw difference by a full turn,
    which means a raw difference of at least 180 — so testing the seam first would make
    `GEO_ERR_POLE` unreachable and report the less useful of the two facts. The distinction is
    actionable: a seam-crossing ring is fixed by splitting it at +-180, and a pole-encircling
    ring is not fixable that way at all, because no longitude/latitude ring can enclose a pole.

    Public because `join` applies the same admissibility test to every ring of a multipolygon
    before it joins anything to it, and rule 3 says a check that appears twice at two
    strengths is a bug even if it never fires: one definition, one behaviour.

    @capability ring_planar_defect_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var census = frame_ring_census_flat(xs, ys, n, frame)
    if census.status != GEO_OK:
        return census.status
    if not geo_is_degree_frame(frame):
        return GEO_OK
    if census.encircles_pole:
        return GEO_ERR_POLE
    if census.antimeridian_edges > 0:
        return GEO_ERR_ANTIMERIDIAN
    return GEO_OK


def _segments_cross(
    ax0: Float64, ay0: Float64, ax1: Float64, ay1: Float64,
    bx0: Float64, by0: Float64, bx1: Float64, by1: Float64,
) -> Bool:
    """Whether two closed segments share at least one point. Exact signs, no epsilon.

    Four orientation determinants: a proper crossing is opposite signs on both pairs; the
    collinear and endpoint-touching cases are the four `== 0.0` branches, each confirmed by
    the closed-box test. Touching counts as intersecting, because a ring whose non-adjacent
    edges touch is not simple and the algorithms below assume simplicity.
    """
    var d1 = _is_left(bx0, by0, bx1, by1, ax0, ay0)
    var d2 = _is_left(bx0, by0, bx1, by1, ax1, ay1)
    var d3 = _is_left(ax0, ay0, ax1, ay1, bx0, by0)
    var d4 = _is_left(ax0, ay0, ax1, ay1, bx1, by1)
    var opposite_a = (d1 > 0.0 and d2 < 0.0) or (d1 < 0.0 and d2 > 0.0)
    var opposite_b = (d3 > 0.0 and d4 < 0.0) or (d3 < 0.0 and d4 > 0.0)
    if opposite_a and opposite_b:
        return True
    if _point_on_segment(ax0, ay0, bx0, by0, bx1, by1):
        return True
    if _point_on_segment(ax1, ay1, bx0, by0, bx1, by1):
        return True
    if _point_on_segment(bx0, by0, ax0, ay0, ax1, ay1):
        return True
    if _point_on_segment(bx1, by1, ax0, ay0, ax1, ay1):
        return True
    return False


@fieldwise_init
struct _Simplicity(Copyable, Movable):
    """Whether a ring is simple — or that the question was not asked, which is not "yes"."""

    var checked: Bool
    var self_intersecting: Bool
    var edge_a: Int
    var edge_b: Int


def _ring_simplicity(xs: List[Float64], ys: List[Float64], n: Int) -> _Simplicity:
    """The O(n^2) simplicity test: does any pair of the ring's edges share a point?

    ONE definition, called by `ring_report_flat` (which reports it) and by
    `ring_intersect_convex_flat` (which refuses on it). It used to be inlined in the report
    only, and the clip gate therefore tested turn-sign consistency alone — which equals
    convexity only for SIMPLE rings, so a pentagram passed it and Sutherland-Hodgman returned
    the intersection of five half-planes (the inner pentagon) as if it were the intersection
    the caller asked for. Rule 3: a guard needed in two places is defined once, or the two
    places enforce it at two strengths.

    `checked` is False above `GEO_MAX_SIMPLICITY_VERTICES`, and then `self_intersecting` means
    nothing and must not be read as False. Bounding the allocation instead of the work is the
    defect rule 1c names: n^2 edge pairs at n = 2^16 is 4.3e9 tests.
    """
    var checked = n <= GEO_MAX_SIMPLICITY_VERTICES
    var self_int = False
    var bad_a = -1
    var bad_b = -1
    if checked and n >= 4:
        for i in range(n):
            var i2 = i + 1
            if i2 == n:
                i2 = 0
            for k in range(i + 1, n):
                var k2 = k + 1
                if k2 == n:
                    k2 = 0
                var hit = False
                if k == i2 or k2 == i:
                    # ADJACENT edges. They share a vertex by construction, so meeting there
                    # is not a defect and `_segments_cross` would flag every ring ever
                    # written. The real defect is a SPIKE: the ring doubling back so that one
                    # edge's far endpoint lands ON the other edge. Three collinear vertices
                    # walked monotonically are NOT a spike — the third vertex is collinear
                    # with the first edge but lies beyond it, so the closed-box test rejects
                    # it — which is why this is the right test rather than a collinearity
                    # test.
                    if k == i2:
                        hit = _point_on_segment(
                            xs[k2], ys[k2], xs[i], ys[i], xs[i2], ys[i2]
                        ) or _point_on_segment(xs[i], ys[i], xs[k], ys[k], xs[k2], ys[k2])
                    else:
                        hit = _point_on_segment(
                            xs[k], ys[k], xs[i], ys[i], xs[i2], ys[i2]
                        ) or _point_on_segment(xs[i2], ys[i2], xs[k], ys[k], xs[k2], ys[k2])
                else:
                    hit = _segments_cross(
                        xs[i], ys[i], xs[i2], ys[i2], xs[k], ys[k], xs[k2], ys[k2]
                    )
                if hit:
                    self_int = True
                    bad_a = i
                    bad_b = k
                    break
            if self_int:
                break
    return _Simplicity(checked, self_int, bad_a, bad_b)


# ── ring report ───────────────────────────────────────────────────────────────


def ring_report_flat(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int
) -> RingReport:
    """Everything structural about a ring: orientation, area, simplicity, convexity, extent.

    Area MAGNITUDE and perimeter are the frozen `geometry.polygon_area` and
    `polygon_perimeter` of the same vertices; the orientation is the sign the frozen area
    discards, derived from the frozen kernel's own accumulation so
    `magnitude_matches_frozen` is an exact equality and not a tolerance.

    A ring with fewer than three vertices has NO area — `has_area` is False and `area` is
    0.0, distinct from a genuinely zero-area collinear triple, which has `has_area` True and
    `orientation == GEO_ORIENT_DEGENERATE`. "Could not be computed" and "computed to be
    zero" are different facts and a caller branches on them differently.

    Simplicity costs O(n^2) and is spent only up to `GEO_MAX_SIMPLICITY_VERTICES`; above it
    `simplicity_checked` is False and `self_intersecting` means nothing. Bounding the
    ALLOCATION here would not bound the work, which is the defect rule 1c names.

    @capability ring_report_flat
    complexity: O(n^2) up to GEO_MAX_SIMPLICITY_VERTICES, else O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_RING_VERTICES)
    if defect != GEO_OK:
        return RingReport(
            defect, n, frame, False, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False,
            False, 0.0, False, False, -1, -1, 0, False, False, 0.0, 0.0, 0.0, 0.0,
        )
    var planar = ring_planar_defect_flat(xs, ys, n, frame)
    if planar != GEO_OK:
        return RingReport(
            planar, n, frame, False, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False,
            False, 0.0, False, False, -1, -1, 0, False, False, 0.0, 0.0, 0.0, 0.0,
        )
    var closed = n >= 2 and xs[n - 1] == xs[0] and ys[n - 1] == ys[0]
    if n == 0:
        return RingReport(
            GEO_OK, 0, frame, False, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False,
            False, 0.0, False, False, -1, -1, 0, False, False, 0.0, 0.0, 0.0, 0.0,
        )

    var min_x = xs[0]
    var max_x = xs[0]
    var min_y = ys[0]
    var max_y = ys[0]
    var duplicates = 0
    for i in range(n):
        if xs[i] < min_x:
            min_x = xs[i]
        if xs[i] > max_x:
            max_x = xs[i]
        if ys[i] < min_y:
            min_y = ys[i]
        if ys[i] > max_y:
            max_y = ys[i]
        var j = i + 1
        if j == n:
            j = 0
        if xs[i] == xs[j] and ys[i] == ys[j]:
            duplicates += 1

    var pts = _points_of(xs, ys, n)
    var has_area = n >= 3
    var area = 0.0
    var trapezoid = 0.0
    var orientation = GEO_ORIENT_DEGENERATE
    var matches = False
    if has_area:
        area = polygon_area(pts)
        trapezoid = _frozen_trapezoid_sum(xs, ys, n)
        orientation = _orientation_of_sum(trapezoid)
        matches = fabs(trapezoid) / 2.0 == area
    var has_perimeter = n >= 2
    var perimeter = 0.0
    if has_perimeter:
        perimeter = polygon_perimeter(pts)

    # Convexity: every turn must have the same sign, with collinear turns permitted. A ring
    # that is self-intersecting can pass a turn-sign test (a pentagram turns consistently),
    # so convexity is reported ALONGSIDE simplicity and neither implies the other here.
    var convex = n >= 3
    if convex:
        var seen_positive = False
        var seen_negative = False
        for i in range(n):
            var b = i + 1
            if b >= n:
                b -= n
            var c = i + 2
            while c >= n:
                c -= n
            var turn = cross_product_2d(pts[i], pts[b], pts[c])
            if turn > 0.0:
                seen_positive = True
            elif turn < 0.0:
                seen_negative = True
        convex = not (seen_positive and seen_negative)

    var simple = _ring_simplicity(xs, ys, n)
    var simplicity_checked = simple.checked
    var self_int = simple.self_intersecting
    var bad_a = simple.edge_a
    var bad_b = simple.edge_b

    return RingReport(
        GEO_OK,
        n,
        frame,
        closed,
        has_area,
        geo_finite_or_zero(area),
        geo_finite_or_zero(Float64(orientation) * area),
        orientation,
        matches,
        has_perimeter,
        geo_finite_or_zero(perimeter),
        simplicity_checked,
        self_int,
        bad_a,
        bad_b,
        duplicates,
        convex,
        True,
        geo_finite_or_zero(min_x),
        geo_finite_or_zero(min_y),
        geo_finite_or_zero(max_x),
        geo_finite_or_zero(max_y),
    )


# ── point in ring ─────────────────────────────────────────────────────────────


def _classify_point(
    px: Float64, py: Float64, xs: List[Float64], ys: List[Float64], n: Int
) -> PipResult:
    """The classification itself, with validation already done by the caller.

    Factored out so `points_in_ring_flat` validates the ring ONCE instead of once per
    point: routing a batch through the public single-point entry would re-run an O(n)
    validation and an O(n) seam census per point, tripling the real cost of a declared
    `O(n_points * n_vertices)`.

    Two passes, and the ORDER is the convention:

    1. *Boundary.* `_point_on_segment` for every edge — collinear exactly, and inside the
       edge's closed bounding box. One rule covers an edge interior, a vertex, a horizontal
       edge and a zero-length edge, and it returns immediately, so the crossing rule never
       has to decide a boundary point.
    2. *Crossing number and winding number*, half-open in y: an edge counts only when
       `y0 <= py < y1` (upward) or `y1 <= py < y0` (downward). Each vertex therefore belongs
       to exactly one of its two edges, a horizontal edge belongs to neither, and a vertex
       the ray merely grazes contributes 0 or 2 crossings — never 1.
    """
    for i in range(n):
        var j = i + 1
        if j == n:
            j = 0
        if _point_on_segment(px, py, xs[i], ys[i], xs[j], ys[j]):
            var st = GEO_OK if n >= 3 else GEO_ERR_DEGENERATE_RING
            return PipResult(st, GEO_PIP_BOUNDARY, True, False, False, 0, 0, i)
    if n < 3:
        return PipResult(
            GEO_ERR_DEGENERATE_RING, GEO_PIP_OUTSIDE, False, False, False, 0, 0, -1
        )

    var crossings = 0
    var winding = 0
    for i in range(n):
        var j = i + 1
        if j == n:
            j = 0
        var y0 = ys[i]
        var y1 = ys[j]
        var side = _is_left(xs[i], ys[i], xs[j], ys[j], px, py)
        if y0 <= py and y1 > py:
            # Upward edge. The point is strictly left of it exactly when the edge lies to
            # the point's right, i.e. when the +x ray crosses it.
            if side > 0.0:
                crossings += 1
                winding += 1
        elif y1 <= py and y0 > py:
            # Downward edge, so the sense is reversed.
            if side < 0.0:
                crossings += 1
                winding -= 1
    var even_odd = (crossings % 2) == 1
    var nonzero = winding != 0
    var classification = GEO_PIP_INSIDE if even_odd else GEO_PIP_OUTSIDE
    return PipResult(
        GEO_OK, classification, False, even_odd, nonzero, crossings, winding, -1
    )


def point_in_ring_flat(
    px: Float64, py: Float64, xs: List[Float64], ys: List[Float64], n: Int, frame: Int
) -> PipResult:
    """Where one point lies relative to one ring: INSIDE, OUTSIDE or exactly ON the boundary.

    Two passes, in this order, and the order is load-bearing:

    1. *Boundary.* For every edge, `_is_left == 0.0` exactly AND the point inside that
       edge's closed bounding box. Catches an edge interior, a vertex, a horizontal edge and
       a zero-length edge with one rule and no special cases. Returns immediately, so no
       crossing rule ever has to decide a boundary point.
    2. *Crossing number and winding number*, half-open in y so a vertex belongs to exactly
       one of its edges and a horizontal edge belongs to neither.

    A ring of fewer than 3 vertices has no interior: the answer is OUTSIDE for every point
    not on it, with status `GEO_ERR_DEGENERATE_RING` so a caller cannot mistake "there is no
    inside" for "your point is outside my polygon".

    @capability point_in_ring_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_RING_VERTICES)
    if defect != GEO_OK:
        return PipResult(defect, GEO_PIP_OUTSIDE, False, False, False, 0, 0, -1)
    var pd = geo_pair_range_defect(px, py, frame)
    if pd != GEO_OK:
        return PipResult(pd, GEO_PIP_OUTSIDE, False, False, False, 0, 0, -1)
    var planar = ring_planar_defect_flat(xs, ys, n, frame)
    if planar != GEO_OK:
        return PipResult(planar, GEO_PIP_OUTSIDE, False, False, False, 0, 0, -1)
    return _classify_point(px, py, xs, ys, n)


def _no_codes(status: Int) -> RingClassification:
    """A refusal with an EMPTY `codes` list. `GEO_PIP_OUTSIDE` is 0, so a zero-filled list
    would read as "every point is outside" — the exact absence-is-not-zero defect."""
    var empty = List[Int]()
    return RingClassification(status, 0, 0, 0, 0, 0, empty^)


# The parameter PACKING below is load-bearing, not style: `mojo_inventory` parses a signature
# inside a TEN-LINE lookahead window and silently drops any function whose signature closes
# later. Do not reflow.
def points_in_ring_flat(
    pxs: List[Float64], pys: List[Float64], n_points: Int,
    xs: List[Float64], ys: List[Float64], n_vertices: Int, frame: Int,
) -> RingClassification:
    """Classify a batch of points against one ring. `codes` holds one `GEO_PIP_*` per point.

    The cost is `n_points * n_vertices` edge tests, and that PRODUCT is what is charged
    against `GEO_MAX_CANDIDATE_WORK` — through `contract.geo_cells_fit`, which divides
    rather than multiplying, because `n_points * n_vertices` is a wrapping 64-bit multiply
    and therefore not a bound. Charging only `n_points + n_vertices` would let a valid
    request burn minutes at a declared cost of nothing, which is the defect rule 1c names.

    On any refusal `codes` is EMPTY, never a list of zeros: `GEO_PIP_OUTSIDE` is 0, so a
    zero-filled list would read as "every point is outside".

    @capability points_in_ring_flat
    complexity: O(n_points * n_vertices)
    counts:
    - n_points <= len(pxs, pys) [kernel_validated]
    - n_vertices <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var pd = geo_points_defect(pxs, pys, n_points, frame, GEO_MAX_POINTS)
    if pd != GEO_OK:
        return _no_codes(pd)
    var vd = geo_points_defect(xs, ys, n_vertices, frame, GEO_MAX_RING_VERTICES)
    if vd != GEO_OK:
        return _no_codes(vd)
    if not geo_cells_fit(n_points, n_vertices, GEO_MAX_CANDIDATE_WORK):
        return _no_codes(GEO_ERR_BUDGET)
    var planar = ring_planar_defect_flat(xs, ys, n_vertices, frame)
    if planar != GEO_OK:
        return _no_codes(planar)
    if n_vertices < 3:
        return _no_codes(GEO_ERR_DEGENERATE_RING)

    var codes = List[Int]()
    var n_in = 0
    var n_bound = 0
    var n_out = 0
    for p in range(n_points):
        var r = _classify_point(pxs[p], pys[p], xs, ys, n_vertices)
        codes.append(r.classification)
        if r.classification == GEO_PIP_INSIDE:
            n_in += 1
        elif r.classification == GEO_PIP_BOUNDARY:
            n_bound += 1
        else:
            n_out += 1
    return RingClassification(
        GEO_OK, n_points, n_in, n_bound, n_out, n_points * n_vertices, codes^
    )


# ── area ──────────────────────────────────────────────────────────────────────


def ring_area_flat(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int
) -> RingArea:
    """Area of a ring in SQUARE METRES, projecting a degree ring first and saying so.

    For `GEO_FRAME_PLANE_M` the answer is the frozen `geometry.polygon_area` of the ring as
    given, in m^2, and `projected` is False.

    For a degree frame the ring is carried onto a local equirectangular metre plane about
    the centre of its OWN extent (frozen `cartography.equirectangular_*`) and the frozen
    shoelace is taken there. `projected` is True and the reference parallel and the two
    spans come back with the answer, because east-west scale is exact only at that parallel
    and the caller is the only one who knows whether that error matters. An antimeridian
    edge or a pole-encircling ring is refused, not projected.

    A ring of fewer than three vertices has no area: `has_area` False, `area_m2` 0.0.

    @capability ring_area_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_RING_VERTICES)
    if defect != GEO_OK:
        return RingArea(
            defect, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False, 0.0, 0.0, 0.0, 0.0
        )
    var planar = ring_planar_defect_flat(xs, ys, n, frame)
    if planar != GEO_OK:
        return RingArea(
            planar, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False, 0.0, 0.0, 0.0, 0.0
        )
    if n < 3:
        return RingArea(
            GEO_OK, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False, 0.0, 0.0, 0.0, 0.0
        )
    if not geo_is_degree_frame(frame):
        var pts = _points_of(xs, ys, n)
        var a = polygon_area(pts)
        var o = _orientation_of_sum(_frozen_trapezoid_sum(xs, ys, n))
        return RingArea(
            GEO_OK,
            True,
            geo_finite_or_zero(a),
            geo_finite_or_zero(Float64(o) * a),
            o,
            False,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    var census = frame_ring_census_flat(xs, ys, n, frame)
    if census.status != GEO_OK:
        return RingArea(
            census.status, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False, 0.0, 0.0, 0.0, 0.0
        )
    # The reference is the centre of the ring's own extent, so the projection's error is
    # symmetric about the data rather than about an arbitrary origin.
    var lonlat = frame == GEO_FRAME_LONLAT_DEG
    var lat_lo = census.min_y if lonlat else census.min_x
    var lat_hi = census.max_y if lonlat else census.max_x
    var lon_lo = census.min_x if lonlat else census.min_y
    var lon_hi = census.max_x if lonlat else census.max_y
    var ref_lat = (lat_lo + lat_hi) / 2.0
    var ref_lon = (lon_lo + lon_hi) / 2.0
    var proj = frame_project_flat(xs, ys, n, frame, ref_lat, ref_lon)
    if proj.status != GEO_OK or not proj.has_result:
        return RingArea(
            proj.status, False, 0.0, 0.0, GEO_ORIENT_DEGENERATE, False, 0.0, 0.0, 0.0, 0.0
        )
    var pts_m = _points_of(proj.xs_m, proj.ys_m, n)
    var area_m = polygon_area(pts_m)
    var orient = _orientation_of_sum(_frozen_trapezoid_sum(proj.xs_m, proj.ys_m, n))
    return RingArea(
        GEO_OK,
        True,
        geo_finite_or_zero(area_m),
        geo_finite_or_zero(Float64(orient) * area_m),
        orient,
        True,
        geo_finite_or_zero(ref_lat),
        geo_finite_or_zero(ref_lon),
        geo_finite_or_zero(lon_hi - lon_lo),
        geo_finite_or_zero(lat_hi - lat_lo),
    )


# ── intersection ──────────────────────────────────────────────────────────────


def _turn_signs_consistent(xs: List[Float64], ys: List[Float64], n: Int) -> Bool:
    """Whether every turn around the ring has the same sign (collinear turns allowed).

    NOT a convexity test on its own. A pentagram turns consistently and is not convex, so
    every caller pairs this with `_ring_simplicity`; turn-sign consistency plus simplicity IS
    convexity, and either half alone is not.
    """
    if n < 3:
        return False
    var pts = _points_of(xs, ys, n)
    var positive = False
    var negative = False
    for i in range(n):
        var b = i + 1
        if b >= n:
            b -= n
        var c = i + 2
        while c >= n:
            c -= n
        var turn = cross_product_2d(pts[i], pts[b], pts[c])
        if turn > 0.0:
            positive = True
        elif turn < 0.0:
            negative = True
    return not (positive and negative)


def _no_clip(status: Int, subject_convex: Bool, clip_convex: Bool) -> ClipResult:
    """A clip refusal: both coordinate lists empty, `is_empty` False because no intersection
    was computed at all. `is_empty` True with `GEO_OK` is the real "they do not overlap"."""
    var ex = List[Float64]()
    var ey = List[Float64]()
    return ClipResult(
        status, 0, False, False, 0.0, subject_convex, clip_convex, ex^, ey^
    )


# Packing is load-bearing — see the note above `points_in_ring_flat`.
def ring_intersect_convex_flat(
    sxs: List[Float64], sys: List[Float64], n_subject: Int,
    cxs: List[Float64], cys: List[Float64], n_clip: Int, frame: Int,
) -> ClipResult:
    """Intersect a subject ring with a CONVEX clip ring (Sutherland-Hodgman).

    Each output vertex is either an input vertex or a crossing point from the frozen
    `geometry.line_intersection`; nothing here solves a line pair. The inside test per clip
    edge is the sign of an orientation determinant, consistent with the clip ring's own
    winding, so the caller does not have to supply the clip in a particular direction.

    A non-convex clip is REFUSED (`GEO_ERR_NOT_CONVEX`). Sutherland-Hodgman assumes the clip
    region is an intersection of half-planes; on a non-convex clip it returns a polygon that
    looks reasonable and is wrong, which is the failure mode this package exists to remove.
    The subject may be non-convex — the result may then contain collinear degenerate edges
    that run along the clip boundary, which add no area.

    Convexity of the clip is TWO tests, and it takes both. Turn-sign consistency alone is not
    convexity: a pentagram — five vertices at 144-degree steps — turns consistently at every
    vertex, and under a turn-sign gate alone it was accepted and the returned polygon was the
    intersection of its five half-planes, the inner pentagon of area `2.5 r^2 sin 72` with
    `r = 1/phi^2`, under a status of OK. That is neither the star region nor any intersection
    a caller asked for. Turn-sign consistency plus SIMPLICITY is convexity, and simplicity is
    `_ring_simplicity`, the same O(n^2) test `ring_report_flat` reports — which had already
    called the pentagram self-intersecting while this gate was not asking.

    Simplicity costs O(n_clip^2) and is only affordable up to
    `contract.GEO_MAX_SIMPLICITY_VERTICES`. A clip ring above that is refused with
    `GEO_ERR_BUDGET` rather than clipped on an unverified convexity claim: "too expensive to
    check" is not "checked and fine". The subject ring has no such limit, because nothing here
    assumes anything about it.

    An empty intersection is a real answer with status `GEO_OK`, `is_empty` True and both
    coordinate lists empty. So is a refusal, which is why `status` is what distinguishes
    them and `len(xs)` is not.

    @capability ring_intersect_convex_flat
    complexity: O(n_subject * n_clip + n_clip^2)
    counts:
    - n_subject <= len(sxs, sys) [kernel_validated]
    - n_clip <= len(cxs, cys) [kernel_validated]
    @endcapability
    """
    var sd = geo_points_defect(sxs, sys, n_subject, frame, GEO_MAX_RING_VERTICES)
    if sd != GEO_OK:
        return _no_clip(sd, False, False)
    var cd = geo_points_defect(cxs, cys, n_clip, frame, GEO_MAX_RING_VERTICES)
    if cd != GEO_OK:
        return _no_clip(cd, False, False)
    if not geo_cells_fit(n_subject, n_clip, GEO_MAX_CANDIDATE_WORK):
        return _no_clip(GEO_ERR_BUDGET, False, False)
    if n_subject < 3 or n_clip < 3:
        return _no_clip(GEO_ERR_DEGENERATE_RING, False, False)
    var sp = ring_planar_defect_flat(sxs, sys, n_subject, frame)
    if sp != GEO_OK:
        return _no_clip(sp, False, False)
    var cp = ring_planar_defect_flat(cxs, cys, n_clip, frame)
    if cp != GEO_OK:
        return _no_clip(cp, False, False)
    var subject_convex = _turn_signs_consistent(sxs, sys, n_subject)
    # Turn signs FIRST, because it is O(n) and rejects most non-convex clips; then simplicity,
    # which is O(n_clip^2) and is what separates a convex ring from a star. `clip_convex` in
    # the result means both held — a caller reading that flag is reading "safe to clip with",
    # so it must not be True for a ring only half of the test was run on.
    var clip_turns = _turn_signs_consistent(cxs, cys, n_clip)
    if not clip_turns:
        return _no_clip(GEO_ERR_NOT_CONVEX, subject_convex, False)
    var clip_simple = _ring_simplicity(cxs, cys, n_clip)
    if not clip_simple.checked:
        return _no_clip(GEO_ERR_BUDGET, subject_convex, False)
    if clip_simple.self_intersecting:
        return _no_clip(GEO_ERR_NOT_CONVEX, subject_convex, False)
    # Past this point the clip is certified convex, which is why every `ClipResult` below
    # carries `clip_convex = True` as a literal: there is no path here that has not passed
    # both halves of the test.

    # Which side of a clip edge is "inside" follows the clip ring's own orientation, so a
    # clockwise clip and its counter-clockwise reversal give the same answer.
    var clip_sign = -1.0
    if _orientation_of_sum(_frozen_trapezoid_sum(cxs, cys, n_clip)) == GEO_ORIENT_CCW:
        clip_sign = 1.0

    var cur_x = List[Float64]()
    var cur_y = List[Float64]()
    for i in range(n_subject):
        cur_x.append(sxs[i])
        cur_y.append(sys[i])

    for e in range(n_clip):
        var e2 = e + 1
        if e2 == n_clip:
            e2 = 0
        var ax = cxs[e]
        var ay = cys[e]
        var bx = cxs[e2]
        var by = cys[e2]
        if ax == bx and ay == by:
            continue  # a repeated clip vertex defines no half-plane
        var next_x = List[Float64]()
        var next_y = List[Float64]()
        var m = len(cur_x)
        if m == 0:
            cur_x = next_x^
            cur_y = next_y^
            break
        for i in range(m):
            var j = i + 1
            if j == m:
                j = 0
            var px = cur_x[i]
            var py = cur_y[i]
            var qx = cur_x[j]
            var qy = cur_y[j]
            var sp_i = clip_sign * _is_left(ax, ay, bx, by, px, py)
            var sp_j = clip_sign * _is_left(ax, ay, bx, by, qx, qy)
            if sp_i >= 0.0:
                next_x.append(px)
                next_y.append(py)
            if (sp_i > 0.0 and sp_j < 0.0) or (sp_i < 0.0 and sp_j > 0.0):
                # Strictly opposite sides, so the two lines are not parallel and the frozen
                # solver has a unique answer. The `except` cannot fire for that input and
                # exists so a future edit cannot turn a raise into a process abort.
                try:
                    var hit = line_intersection(
                        Point(px, py), Point(qx, qy), Point(ax, ay), Point(bx, by)
                    )
                    next_x.append(hit.x)
                    next_y.append(hit.y)
                except:
                    pass
        cur_x = next_x^
        cur_y = next_y^

    var out_n = len(cur_x)
    if out_n == 0:
        var zx = List[Float64]()
        var zy = List[Float64]()
        return ClipResult(
            GEO_OK, 0, True, False, 0.0, subject_convex, True, zx^, zy^
        )
    var has_area = out_n >= 3
    var area = 0.0
    if has_area:
        area = polygon_area(_points_of(cur_x, cur_y, out_n))
    return ClipResult(
        GEO_OK,
        out_n,
        False,
        has_area,
        geo_finite_or_zero(area),
        subject_convex,
        True,
        cur_x^,
        cur_y^,
    )
