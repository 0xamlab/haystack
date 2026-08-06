"""
geospatial.mapmatch — a GPS track matched onto a polyline network.

Zero Python imports. Every geodetic quantity comes out of a frozen kernel:

  | quantity                               | frozen kernel called unchanged          |
  | -------------------------------------- | --------------------------------------- |
  | distance to the great circle of a leg  | `geodesy.cross_track_distance`           |
  | distance along that leg to the foot    | `geodesy.along_track_distance`           |
  | the foot's own coordinates             | `geodesy.destination_point` + `initial_bearing` |
  | leg length and point-to-point distance | `geodesy.haversine_distance` via `frame` |
  | planar projection and distance         | `geometry.distance_2d`                   |
  | candidate pruning                      | `index.grid_build_flat` / `grid_window_flat` |

`cross_track_distance` and `along_track_distance` have existed in this tree unused: they are
exactly the two numbers a map matcher needs, and nothing composed them. This is the missing
driver, and the three things it adds are the clamp, the sequence, and the refusal.

The clamp is the part the frozen kernels cannot do
-------------------------------------------------
`cross_track_distance` measures the distance to the great CIRCLE through the leg's endpoints
— an infinite line, not the segment. Using it directly on a road segment reports a vehicle
20 km past the end of a street as being 3 m from it, which is how a matcher snaps a track to
a road it never touched. The segment case is decided by the SIGN of the along-track direction
at each endpoint, taken from the frozen `initial_bearing`:

    before a  <=>  cos( bearing(a->p) - bearing(a->b) )  <  0
    past b    <=>  cos( bearing(b->p) - bearing(b->a) )  <  0
    inside    <=>  neither

That is spherical trigonometry's own statement of the case, because the signed along-track
angle satisfies `cos(along) * cos(cross) = cos(dist(a, p))` and `sign(cos(along))` is the sign
of that bearing dot product — so the test is a comparison against ZERO with no tolerance at
all, not a length inequality with a rounding allowance. Outside, the distance is to the nearer
endpoint, exactly.

The obvious alternative is a length test, `along_from_a + along_from_b <= leg`, and it is
WRONG for a long leg. `along_track_distance` ends in `asin`, so an along-track angle of 150
degrees comes back as 30: the two folded numbers sum to `180 - leg` for a point past the end,
the test degenerates into `180 - leg <= leg`, and every leg of a quarter of the globe or more
is called "inside" no matter how far past the end the point is — which is the exact failure
the clamp exists to remove, wearing a status of OK. The same fold is corrected where the
along-track distance is REPORTED: `dist(a, p)` past a quarter circle means the true along-track
angle is obtuse, so the foot and the leg fraction come from `half_circumference - folded`.

`along_track_distance` returns a non-negative number and therefore cannot say which SIDE of
the endpoint the foot fell on. The bearings can, which is why the decision is theirs.

An EXACTLY antipodal leg is refused with `GEO_ERR_PARAM`. Two antipodal endpoints lie on
infinitely many great circles, so they do not name an arc, and every answer about "the"
distance to it would be a choice this package made silently. The test is an exact equality
(`lat_b == -lat_a` and `|lon_b - lon_a| == 180`), not a tolerance: a leg of 179.999 degrees
does determine an arc and is served.

The sequence is a Viterbi over per-observation candidates, not an HMM over fixed states
---------------------------------------------------------------------------------------
`hmm.hmm_viterbi` exists and is not called, for a structural reason rather than a preference:
it takes a transition matrix over a FIXED state set shared by every observation, and a map
matcher's states are the candidate segments near THIS fix — a different, small set at every
step. Expressing that as a fixed state space means a |segments| x |segments| transition
matrix, which for a city network is millions of rows of which a handful are ever consulted.
So the dynamic program is written over the per-observation candidate lists.

The cost is the Newson-Krumm shape with one stated substitution:

    emission(t, c)      = clamped point-to-segment distance in metres
    transition(t, c, c')= | great-circle step between the two fixes
                           - great-circle step between the two feet |
    total               = sum of emissions + beta * sum of transitions

The substitution is that the second term of the transition uses the STRAIGHT-LINE distance
between the two projected feet, where the published measure uses the route distance through
the network. A route distance means a shortest path per candidate pair per step, which is a
different order of cost and needs a connectivity model this signature does not carry; the
straight line is a lower bound on it. Saying so is the point —
`join.network_route_matrix_flat` is where route distances live.

`beta` is the caller's lever, in metres per metre. `beta = 0` is nearest-segment matching per
fix with no continuity at all; large `beta` prefers a self-consistent path even when
individual fixes are then matched further from their nearest road.

A gap is a refusal, not a partial match
---------------------------------------
A track point with NO candidate segment within `search_radius_m` refuses the whole match with
`GEO_ERR_NO_CANDIDATE` and `first_unmatched` naming the fix. The alternative — matching the
fixes that had candidates and leaving a hole — returns a path the vehicle did not take, with
no field distinguishing it from one it did. Widening the radius or splitting the track at the
gap is the caller's decision.

Candidates per fix are capped at `contract.GEO_MAX_CANDIDATES_PER_POINT` (the nearest ones,
ties broken by segment index so the result does not depend on the index layout), and `pruned`
says when that bit. The DP cost is `sum over t of |C_t| * |C_(t-1)|`, so the cap is what
bounds it: charging only the candidate SEARCH would leave the quadratic step uncharged, which
is the "bounding memory is not bounding work" defect.

The candidate SEARCH is charged separately, and it has to be, because the DP cap says nothing
about it. Two things make it unbounded otherwise. First, the network's segment count is
`len(nxs)`-shaped, not `n_lines`-shaped — one polyline may carry millions of vertices — so
`GEO_MAX_SEGMENTS` bounds it directly. Second, a fix whose search box is rejected by the index
(a box clipped by the seam) falls back to testing EVERY segment, which is correct but costs
`n_segments`, and `n_track` such fixes cost their product. Segment tests are therefore
accumulated across fixes and stopped at `contract.GEO_MAX_CANDIDATE_WORK` with
`GEO_ERR_BUDGET`, so no admitted request can run away.

The third thing that has to be charged is the CELLS a probe reads, and it is charged for the
same reason: an index probe costs O(cells covered + candidates examined), the box here is
widened by the network's longest half-segment on each axis, and over a sparse network the
widened box covers thousands of empty cells per fix while examining no candidate at all. A
ceiling that counted candidates alone priced that box at zero and a valid request could spend
minutes at a declared cost of nothing. `cells_examined` reports the quantity, beside
`candidates_examined`, and their SUM is what the ceiling bounds.

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
golden_vectors: mojo/tests/libs/test_geospatial_mapmatch.mojo
benchmark: benchmarks/mojo_benchmarks/bench_geospatial.mojo
docs: gitbook/engine/geospatial.md
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, cos as mcos

from geodesy import (
    along_track_distance,
    cross_track_distance,
    destination_point,
    initial_bearing,
)

from geospatial.contract import (
    GEO_EARTH_RADIUS_M,
    GEO_ERR_BUDGET,
    GEO_ERR_COUNT,
    GEO_ERR_METRIC_UNSUPPORTED_HERE,
    GEO_ERR_NO_CANDIDATE,
    GEO_ERR_PARAM,
    GEO_M_PER_DEG,
    GEO_PI,
    GEO_MAX_CANDIDATE_WORK,
    GEO_MAX_CANDIDATES_PER_POINT,
    GEO_MAX_LINES,
    GEO_MAX_POINTS,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_HAVERSINE,
    GEO_METRIC_VINCENTY,
    GEO_OK,
    geo_cells_fit,
    geo_degree_box_half,
    geo_finite,
    geo_finite_or_zero,
    geo_is_degree_frame,
    geo_lat_of,
    geo_lon_of,
    geo_metric_defect,
    geo_offsets_defect,
    geo_pair_range_defect,
    geo_points_defect,
)
from geospatial.frame import frame_metric_distance
from geospatial.index import grid_build_flat, grid_window_flat

#: Half of the great circle, in metres, on the sphere `geodesy.haversine_distance` uses
#: (R = 6371 km). Two facts about a degree leg are read off it and nothing else:
#: `dist(a, p)` above HALF of it means the along-track angle is obtuse and the frozen
#: `asin`-folded along-track distance must be unfolded, and a leg equal to it is a pair of
#: antipodes that names no arc. It is a property of the frozen metric, not a tolerance.
comptime GEO_HALF_CIRCUMFERENCE_M: Float64 = GEO_PI * GEO_EARTH_RADIUS_M

#: The most segments a network may hold. Distinct from `contract.GEO_MAX_LINES`, which bounds
#: the number of POLYLINES: a single polyline can carry as many vertices as the coordinate
#: arrays hold, so a line ceiling is not a segment ceiling. Every per-fix candidate scan is
#: O(n_segments) in the worst case, which is why this one exists.
comptime GEO_MAX_SEGMENTS: Int = 1 << 20

#: Where the foot of the perpendicular fell.
comptime GEO_FOOT_INTERIOR: Int = 0
comptime GEO_FOOT_START: Int = 1
comptime GEO_FOOT_END: Int = 2


@fieldwise_init
struct SegmentDistance(Copyable, Movable):
    """The clamped distance from a point to ONE segment, and where the foot landed.

    `foot_x`/`foot_y` are in the same frame as the inputs. `where` is `GEO_FOOT_INTERIOR`,
    `GEO_FOOT_START` or `GEO_FOOT_END`, which is the distinction a segment has and a great
    circle does not — and the one the frozen cross-track kernel cannot make on its own.
    `t_fraction` is meaningful only for a projected frame, where the segment is a straight
    line; on a degree frame it is the along-track distance as a fraction of the leg length,
    which is the same quantity for a great-circle leg and is flagged by `has_fraction`.
    """

    var status: Int
    var has_distance: Bool
    var distance_m: Float64
    var where: Int
    var has_foot: Bool
    var foot_x: Float64
    var foot_y: Float64
    var has_fraction: Bool
    var t_fraction: Float64
    var has_leg_length: Bool
    var leg_length_m: Float64


@fieldwise_init
struct GeoMatch(Copyable, Movable):
    """A whole track matched to the network, or a refusal with the fix that caused it.

    Every list is EMPTY on a refusal. `segment_of_point[t]` is a GLOBAL segment index; the
    mapping back to a polyline is `line_of_point[t]`. `offset_m[t]` is the emission distance
    for the chosen segment — how far the fix was from the road it was matched to, which is the
    number an operator inspects when a match looks wrong.

    `candidates_examined` and `cells_examined` are reported separately because they are
    separate costs and BOTH are charged against the work ceiling: a search box over a sparse
    network can cover tens of thousands of empty index cells and examine no candidate at all,
    so a budget that counted candidates alone would price that box at zero.
    """

    var status: Int
    var n_track: Int
    var n_lines: Int
    var n_segments: Int
    var pruned: Bool
    var first_unmatched: Int
    var candidates_examined: Int
    var cells_examined: Int
    var dp_transitions: Int
    var has_cost: Bool
    var total_cost: Float64
    var has_offsets: Bool
    var max_offset_m: Float64
    var segment_of_point: List[Int]
    var line_of_point: List[Int]
    var offset_m: List[Float64]
    var matched_xs: List[Float64]
    var matched_ys: List[Float64]


# ── refusals ──────────────────────────────────────────────────────────────────


def _no_segment(status: Int) -> SegmentDistance:
    return SegmentDistance(status, False, 0.0, GEO_FOOT_INTERIOR, False, 0.0, 0.0, False, 0.0, False, 0.0)


def _no_match(status: Int, n_track: Int, n_lines: Int, first_unmatched: Int) -> GeoMatch:
    var a = List[Int]()
    var b = List[Int]()
    var c = List[Float64]()
    var d = List[Float64]()
    var e = List[Float64]()
    return GeoMatch(
        status, n_track, n_lines, 0, False, first_unmatched, 0, 0, 0, False, 0.0,
        False, 0.0, a^, b^, c^, d^, e^,
    )


def _metric_defect_here(frame: Int, metric: Int) -> Int:
    """`GEO_OK` for a metric this module can clamp a segment under.

    `GEO_METRIC_VINCENTY` is refused with `GEO_ERR_METRIC_UNSUPPORTED_HERE`: the clamp is
    built from `geodesy.cross_track_distance` and `along_track_distance`, which are SPHERICAL
    (they divide a haversine distance by the same 6371 km radius), so an ellipsoidal endpoint
    distance would be compared against a spherical along-track quantity — two models in one
    answer, and the quarter-circle fold correction below is stated on that sphere and on no
    other. `frame.frame_path_length_flat` serves Vincenty where no clamp is involved.
    """
    var md = geo_metric_defect(frame, metric)
    if md != GEO_OK:
        return md
    if metric == GEO_METRIC_VINCENTY:
        return GEO_ERR_METRIC_UNSUPPORTED_HERE
    return GEO_OK


# ── point to segment ──────────────────────────────────────────────────────────


# The parameter PACKING below is load-bearing, not style. `mojo_inventory` parses a
# signature inside a TEN-LINE lookahead window and silently drops a function whose signature
# closes later — no error, the function simply is not in the contract. Do not reflow.
def point_to_segment_flat(
    px: Float64, py: Float64,
    ax: Float64, ay: Float64, bx: Float64, by: Float64,
    frame: Int, metric: Int,
) -> SegmentDistance:
    """The distance from a point to a SEGMENT — clamped — plus the foot's coordinates.

    For `GEO_FRAME_PLANE_M` this is the textbook projection with `t` clamped to `[0, 1]`, and
    the distance is the frozen `geometry.distance_2d` from the point to the foot.

    For a degree frame the SIGN of the along-track direction at each endpoint decides the case,
    and it is read off the frozen `initial_bearing`: the foot is before `a` when
    `cos(bearing(a->p) - bearing(a->b)) < 0`, past `b` when
    `cos(bearing(b->p) - bearing(b->a)) < 0`, and interior otherwise. A comparison against
    zero, with no tolerance. Interior gives `|cross_track_distance|` and a foot at
    `destination_point(a, bearing(a->b), along)` — all frozen. Outside gives the nearer
    endpoint, exactly.

    The along-track distance the interior branch reports is UNFOLDED first. The frozen
    `along_track_distance` ends in `asin`, so it cannot exceed a quarter of the globe and
    returns `180 - along` for an obtuse along-track angle; the angle is obtuse exactly when
    `dist(a, p)` exceeds a quarter circle, and then the true value is
    `GEO_HALF_CIRCUMFERENCE_M - folded`. Without that correction a point 100 degrees along a
    150-degree leg reports a foot at 80 degrees and a leg fraction of 0.53 instead of 0.67 —
    the distance would be right and the position wrong.

    A superficially cheaper test — `along(p, a->b) + along(p, b->a) <= leg` — is rejected
    because the same fold breaks it: for a point past the end of a leg of length L the folded
    sum is `180 - L`, so the test reduces to `180 - L <= L` and calls EVERY point "interior"
    on any leg of 90 degrees or more, however far past the end it is. That is the clamp
    inverted on exactly the inputs the clamp exists for.

    A degenerate leg (`a == b`) has no direction: the distance is the point-to-point distance,
    the foot is that shared endpoint, and `has_fraction` is False because there is no
    fraction of a zero-length leg. An exactly antipodal leg has infinitely many directions and
    is refused with `GEO_ERR_PARAM` rather than answered about an arc the caller never named.

    @capability point_to_segment_flat
    complexity: O(1)
    counts: none
    @endcapability
    """
    var md = _metric_defect_here(frame, metric)
    if md != GEO_OK:
        return _no_segment(md)
    var pd = geo_pair_range_defect(px, py, frame)
    if pd != GEO_OK:
        return _no_segment(pd)
    var ad = geo_pair_range_defect(ax, ay, frame)
    if ad != GEO_OK:
        return _no_segment(ad)
    var bd = geo_pair_range_defect(bx, by, frame)
    if bd != GEO_OK:
        return _no_segment(bd)

    var leg = frame_metric_distance(ax, ay, bx, by, frame, metric)
    var d_pa = frame_metric_distance(px, py, ax, ay, frame, metric)
    var d_pb = frame_metric_distance(px, py, bx, by, frame, metric)
    if leg == 0.0:
        return SegmentDistance(
            GEO_OK, True, geo_finite_or_zero(d_pa), GEO_FOOT_START, True,
            geo_finite_or_zero(ax), geo_finite_or_zero(ay), False, 0.0, True, 0.0,
        )

    if not geo_is_degree_frame(frame):
        var vx = bx - ax
        var vy = by - ay
        var denom = vx * vx + vy * vy
        var t = ((px - ax) * vx + (py - ay) * vy) / denom
        if not geo_finite(t):
            t = 0.0
        var where = GEO_FOOT_INTERIOR
        if t <= 0.0:
            t = 0.0
            where = GEO_FOOT_START
        elif t >= 1.0:
            t = 1.0
            where = GEO_FOOT_END
        var fx = ax + t * vx
        var fy = ay + t * vy
        var d = frame_metric_distance(px, py, fx, fy, frame, metric)
        return SegmentDistance(
            GEO_OK, True, geo_finite_or_zero(d), where, True,
            geo_finite_or_zero(fx), geo_finite_or_zero(fy), True,
            geo_finite_or_zero(t), True, geo_finite_or_zero(leg),
        )

    var p_lat = geo_lat_of(px, py, frame)
    var p_lon = geo_lon_of(px, py, frame)
    var a_lat = geo_lat_of(ax, ay, frame)
    var a_lon = geo_lon_of(ax, ay, frame)
    var b_lat = geo_lat_of(bx, by, frame)
    var b_lon = geo_lon_of(bx, by, frame)
    # Antipodal endpoints name no arc: refuse rather than answer about one of the infinitely
    # many great circles through them. Exact equalities, so 179.999 degrees is still served.
    if a_lat == -b_lat and fabs(a_lon - b_lon) == 180.0:
        return _no_segment(GEO_ERR_PARAM)

    # WHICH SIDE, from the bearings. `cos(bearing(a->p) - bearing(a->b))` carries the sign of
    # the signed along-track angle at `a`, because `cos(along) * cos(cross) = cos(dist(a, p))`
    # and `cos(cross) >= 0` always. A comparison against zero; no tolerance is involved, and
    # the two flags are computed independently at the two endpoints so a long leg is decided
    # by the same rule as a short one.
    var deg_to_rad = GEO_PI / 180.0
    var brg_ab = initial_bearing(a_lat, a_lon, b_lat, b_lon)
    var brg_ap = initial_bearing(a_lat, a_lon, p_lat, p_lon)
    var brg_ba = initial_bearing(b_lat, b_lon, a_lat, a_lon)
    var brg_bp = initial_bearing(b_lat, b_lon, p_lat, p_lon)
    var before_a = mcos((brg_ap - brg_ab) * deg_to_rad) < 0.0
    var past_b = mcos((brg_bp - brg_ba) * deg_to_rad) < 0.0

    var along_a = along_track_distance(p_lat, p_lon, a_lat, a_lon, b_lat, b_lon) * 1000.0
    if not geo_finite(along_a):
        along_a = 0.0
    # UNFOLD it. `along_track_distance` ends in `asin`, so it returns
    # `half circumference - along` whenever the along-track angle is obtuse, and that happens
    # exactly when `p` is more than a quarter circle from `a` — at which point `cos(dist(a,p))`
    # is negative and so is `cos(along)`. Only the reported foot and fraction depend on this;
    # the distance itself comes from the cross-track kernel.
    if d_pa > GEO_HALF_CIRCUMFERENCE_M / 2.0:
        along_a = GEO_HALF_CIRCUMFERENCE_M - along_a
    if not (before_a or past_b):
        var cross = fabs(
            cross_track_distance(p_lat, p_lon, a_lat, a_lon, b_lat, b_lon) * 1000.0
        )
        if not geo_finite(cross):
            cross = d_pa
        var best = cross
        if d_pa < best:
            best = d_pa
        if d_pb < best:
            best = d_pb
        var brg = initial_bearing(a_lat, a_lon, b_lat, b_lon)
        var foot = destination_point(a_lat, a_lon, brg, along_a / 1000.0)
        var f_lat = 0.0
        var f_lon = 0.0
        if len(foot) == 2:
            f_lat = geo_finite_or_zero(foot[0])
            f_lon = geo_finite_or_zero(foot[1])
        var fx = f_lon
        var fy = f_lat
        if geo_lat_of(1.0, 0.0, frame) == 1.0:
            fx = f_lat
            fy = f_lon
        return SegmentDistance(
            GEO_OK, True, geo_finite_or_zero(best), GEO_FOOT_INTERIOR, True,
            geo_finite_or_zero(fx), geo_finite_or_zero(fy), True,
            geo_finite_or_zero(along_a / leg), True, geo_finite_or_zero(leg),
        )
    if d_pa <= d_pb:
        return SegmentDistance(
            GEO_OK, True, geo_finite_or_zero(d_pa), GEO_FOOT_START, True,
            geo_finite_or_zero(ax), geo_finite_or_zero(ay), True, 0.0, True,
            geo_finite_or_zero(leg),
        )
    return SegmentDistance(
        GEO_OK, True, geo_finite_or_zero(d_pb), GEO_FOOT_END, True,
        geo_finite_or_zero(bx), geo_finite_or_zero(by), True, 1.0, True,
        geo_finite_or_zero(leg),
    )


# ── map matching ──────────────────────────────────────────────────────────────


def _cand_insert(
    mut seg: List[Int],
    mut cost: List[Float64],
    mut fx: List[Float64],
    mut fy: List[Float64],
    cap: Int,
    sid: Int,
    d: Float64,
    x: Float64,
    y: Float64,
):
    """Keep the `cap` nearest candidates, ordered by `(distance, segment index)`.

    The segment-index tiebreak is what makes the match a function of the DATA rather than of
    the grid layout: two segments at the same distance from a fix are common (a divided road,
    a duplicated way) and without the tiebreak the chosen one would depend on which cell the
    query happened to read first.
    """
    var m = len(cost)
    if cap <= 0:
        return
    if m >= cap:
        if d > cost[m - 1]:
            return
        if d == cost[m - 1] and sid > seg[m - 1]:
            return
    var pos = m
    for i in range(m):
        if d < cost[i] or (d == cost[i] and sid < seg[i]):
            pos = i
            break
    seg.insert(pos, sid)
    cost.insert(pos, d)
    fx.insert(pos, x)
    fy.insert(pos, y)
    while len(cost) > cap:
        _ = seg.pop()
        _ = cost.pop()
        _ = fx.pop()
        _ = fy.pop()


# Packing is load-bearing — see the note above `point_to_segment_flat`.
def map_match_flat(
    txs: List[Float64], tys: List[Float64], n_track: Int,
    nxs: List[Float64], nys: List[Float64],
    line_offsets: List[Int], n_lines: Int,
    search_radius_m: Float64, beta: Float64, frame: Int, metric: Int,
) -> GeoMatch:
    """Match an ordered track onto a polyline network by dynamic programming.

    The network arrives CSR-style: polyline `g` occupies
    `[line_offsets[g], line_offsets[g + 1])` in `nxs`/`nys`, validated by
    `contract.geo_offsets_defect`. A polyline of one vertex contributes no segment; that is a
    valid input (a network can carry a stub) and is simply skipped.

    Candidates per fix are found through the cell index over segment MIDPOINTS, with the query
    box widened by the longest half-segment in the network so the box is a superset of the
    true search disc — a shorter box would silently drop a long segment whose midpoint is far
    from the fix but whose body passes right through it. That widening is also why the CELLS a
    probe covers are charged against `contract.GEO_MAX_CANDIDATE_WORK` alongside the candidates
    it examines: over a sparse network the widened box is thousands of empty cells and no
    candidates, and a ceiling counting candidates alone would price the whole scan at zero.

    `beta` weights continuity against per-fix accuracy and must be finite and non-negative.
    `search_radius_m` must be finite and positive: a zero radius admits only a fix lying
    exactly on a road, which is a legitimate but almost certainly unintended request, so it is
    refused rather than silently returning `GEO_ERR_NO_CANDIDATE` for every real track.

    @capability map_match_flat
    complexity: O(n_track * candidates_per_fix^2 + n_track * (cells_per_box + candidates_per_box))
    counts:
    - n_track <= len(txs, tys) [kernel_validated]
    - n_lines + 1 == len(line_offsets) [kernel_validated]
    @endcapability
    """
    var md = _metric_defect_here(frame, metric)
    if md != GEO_OK:
        return _no_match(md, n_track, n_lines, -1)
    if not geo_finite(search_radius_m) or search_radius_m <= 0.0:
        return _no_match(GEO_ERR_PARAM, n_track, n_lines, -1)
    if not geo_finite(beta) or beta < 0.0:
        return _no_match(GEO_ERR_PARAM, n_track, n_lines, -1)
    var td = geo_points_defect(txs, tys, n_track, frame, GEO_MAX_POINTS)
    if td != GEO_OK:
        return _no_match(td, n_track, n_lines, -1)
    var n_vertices = len(nxs)
    if len(nys) < n_vertices:
        n_vertices = len(nys)
    var od = geo_offsets_defect(line_offsets, n_lines, n_vertices, GEO_MAX_LINES)
    if od != GEO_OK:
        return _no_match(od, n_track, n_lines, -1)
    if not geo_cells_fit(
        n_track, GEO_MAX_CANDIDATES_PER_POINT * GEO_MAX_CANDIDATES_PER_POINT,
        GEO_MAX_CANDIDATE_WORK,
    ):
        return _no_match(GEO_ERR_BUDGET, n_track, n_lines, -1)

    # ── segments, and their midpoints, from the polylines ──────────────────────
    var seg_a = List[Int]()
    var seg_b = List[Int]()
    var seg_line = List[Int]()
    var mid_x = List[Float64]()
    var mid_y = List[Float64]()
    var half_max_x = 0.0
    var half_max_y = 0.0
    for g in range(n_lines):
        var s = line_offsets[g]
        var e = line_offsets[g + 1]
        for v in range(s, e - 1):
            if geo_pair_range_defect(nxs[v], nys[v], frame) != GEO_OK:
                return _no_match(GEO_ERR_COUNT, n_track, n_lines, -1)
            if geo_pair_range_defect(nxs[v + 1], nys[v + 1], frame) != GEO_OK:
                return _no_match(GEO_ERR_COUNT, n_track, n_lines, -1)
            seg_a.append(v)
            seg_b.append(v + 1)
            seg_line.append(g)
            mid_x.append((nxs[v] + nxs[v + 1]) / 2.0)
            mid_y.append((nys[v] + nys[v + 1]) / 2.0)
            var half_x = fabs(nxs[v + 1] - nxs[v]) / 2.0
            var half_y = fabs(nys[v + 1] - nys[v]) / 2.0
            if half_x > half_max_x:
                half_max_x = half_x
            if half_y > half_max_y:
                half_max_y = half_y
    var n_segments = len(seg_a)
    if n_segments > GEO_MAX_SEGMENTS:
        return _no_match(GEO_ERR_BUDGET, n_track, n_lines, -1)
    if n_segments == 0:
        return _no_match(GEO_ERR_NO_CANDIDATE, n_track, n_lines, 0)
    if n_track == 0:
        var e0 = List[Int]()
        var e1 = List[Int]()
        var e2 = List[Float64]()
        var e3 = List[Float64]()
        var e4 = List[Float64]()
        return GeoMatch(
            GEO_OK, 0, n_lines, n_segments, False, -1, 0, 0, 0, False, 0.0, False, 0.0,
            e0^, e1^, e2^, e3^, e4^,
        )

    var grid = grid_build_flat(mid_x, mid_y, n_segments, frame, 4)
    if grid.status != GEO_OK:
        return _no_match(grid.status, n_track, n_lines, -1)

    # The radius in COORDINATE units, per axis. A metre radius is a different number of
    # degrees along each axis and at each latitude, so the longitude half-width comes from
    # `contract.geo_degree_box_half` at the FIX's own latitude — the same definition `join`
    # uses. Widened by the longest half-segment on that axis, because a long segment whose
    # MIDPOINT is outside the box can still pass through the fix, and the index holds
    # midpoints.
    var degrees = geo_is_degree_frame(frame)
    var x_is_lat = not degrees or geo_lat_of(1.0, 0.0, frame) == 1.0
    var lat_half = search_radius_m / GEO_M_PER_DEG

    # ── candidates per fix ────────────────────────────────────────────────────
    var cand_seg = List[List[Int]]()
    var cand_cost = List[List[Float64]]()
    var cand_fx = List[List[Float64]]()
    var cand_fy = List[List[Float64]]()
    var candidates = 0
    #: Index cells read across all fixes, and the sum of BOTH costs, which is what the ceiling
    #: bounds. `grid_window_flat`'s own declared cost is O(cells + candidates) and a widened
    #: box over a sparse network is nearly all cells: charging candidates alone priced a
    #: 205 x 205-cell probe at zero and let a valid request run for minutes.
    var cells = 0
    var work = 0
    var pruned = False
    for t in range(n_track):
        var half_x = search_radius_m
        var half_y = search_radius_m
        if degrees:
            var lon_half = geo_degree_box_half(
                search_radius_m, geo_lat_of(txs[t], tys[t], frame)
            )
            if x_is_lat:
                half_x = lat_half
                half_y = lon_half
            else:
                half_x = lon_half
                half_y = lat_half
        half_x += half_max_x
        half_y += half_max_y
        var win = grid_window_flat(
            grid.cell_start, grid.cell_items, mid_x, mid_y, n_segments, grid.side,
            grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
            txs[t] - half_x, tys[t] - half_y, txs[t] + half_x, tys[t] + half_y,
            frame,
        )
        var ids = List[Int]()
        if win.status != GEO_OK:
            # A box clipped by the seam or by a pole is not a reason to give up: fall back to
            # every segment for THIS fix. Slower, never wrong, and the count says it happened.
            # It is also the expensive branch — O(n_segments) for one fix — so it is charged at
            # its true cost below rather than at the cost of an indexed probe.
            if work > GEO_MAX_CANDIDATE_WORK - n_segments:
                return _no_match(GEO_ERR_BUDGET, n_track, n_lines, t)
            candidates += n_segments
            work += n_segments
            for s in range(n_segments):
                ids.append(s)
        else:
            var probe = win.cells_examined + win.candidates_examined
            if work > GEO_MAX_CANDIDATE_WORK - probe:
                return _no_match(GEO_ERR_BUDGET, n_track, n_lines, t)
            candidates += win.candidates_examined
            cells += win.cells_examined
            work += probe
            for c in range(len(win.ids)):
                ids.append(win.ids[c])
        var segs = List[Int]()
        var costs = List[Float64]()
        var fxs = List[Float64]()
        var fys = List[Float64]()
        for c in range(len(ids)):
            var sid = ids[c]
            var ia = seg_a[sid]
            var ib = seg_b[sid]
            var sd = point_to_segment_flat(
                txs[t], tys[t], nxs[ia], nys[ia], nxs[ib], nys[ib], frame, metric
            )
            if sd.status != GEO_OK or not sd.has_distance:
                continue
            if sd.distance_m > search_radius_m:
                continue
            _cand_insert(
                segs, costs, fxs, fys, GEO_MAX_CANDIDATES_PER_POINT,
                sid, sd.distance_m, sd.foot_x, sd.foot_y,
            )
        if len(segs) == 0:
            return _no_match(GEO_ERR_NO_CANDIDATE, n_track, n_lines, t)
        if len(segs) == GEO_MAX_CANDIDATES_PER_POINT:
            pruned = True
        cand_seg.append(segs^)
        cand_cost.append(costs^)
        cand_fx.append(fxs^)
        cand_fy.append(fys^)

    # ── Viterbi over the candidate lists ──────────────────────────────────────
    var best = List[List[Float64]]()
    var back = List[List[Int]]()
    var transitions = 0
    for t in range(n_track):
        var row = List[Float64]()
        var brow = List[Int]()
        ref here = cand_cost[t]
        if t == 0:
            for c in range(len(here)):
                row.append(here[c])
                brow.append(-1)
        else:
            ref prev = best[t - 1]
            var step = frame_metric_distance(
                txs[t - 1], tys[t - 1], txs[t], tys[t], frame, metric
            )
            for c in range(len(here)):
                var best_cost = 0.0
                var best_from = -1
                for q in range(len(prev)):
                    transitions += 1
                    var foot_step = frame_metric_distance(
                        cand_fx[t - 1][q], cand_fy[t - 1][q],
                        cand_fx[t][c], cand_fy[t][c], frame, metric,
                    )
                    var total = prev[q] + beta * fabs(step - foot_step)
                    if best_from < 0 or total < best_cost:
                        best_cost = total
                        best_from = q
                row.append(best_cost + here[c])
                brow.append(best_from)
        best.append(row^)
        back.append(brow^)

    ref last = best[n_track - 1]
    var pick = 0
    for c in range(1, len(last)):
        if last[c] < last[pick]:
            pick = c
    var total_cost = last[pick]

    var seg_of = List[Int]()
    var line_of = List[Int]()
    var offs = List[Float64]()
    var mxs = List[Float64]()
    var mys = List[Float64]()
    for _ in range(n_track):
        seg_of.append(-1)
        line_of.append(-1)
        offs.append(0.0)
        mxs.append(0.0)
        mys.append(0.0)
    var cur = pick
    var max_off = 0.0
    for t in range(n_track - 1, -1, -1):
        var sid = cand_seg[t][cur]
        seg_of[t] = sid
        line_of[t] = seg_line[sid]
        offs[t] = geo_finite_or_zero(cand_cost[t][cur])
        mxs[t] = geo_finite_or_zero(cand_fx[t][cur])
        mys[t] = geo_finite_or_zero(cand_fy[t][cur])
        if offs[t] > max_off:
            max_off = offs[t]
        if t > 0:
            var prev_index = back[t][cur]
            if prev_index < 0:
                prev_index = 0
            cur = prev_index
    return GeoMatch(
        GEO_OK,
        n_track,
        n_lines,
        n_segments,
        pruned,
        -1,
        candidates,
        cells,
        transitions,
        True,
        geo_finite_or_zero(total_cost),
        True,
        geo_finite_or_zero(max_off),
        seg_of^,
        line_of^,
        offs^,
        mxs^,
        mys^,
    )
