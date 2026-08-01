"""
geospatial.frame — what a batch of coordinates IS, before anything is computed from it.

Zero Python imports. Every distance here comes out of a frozen kernel:

  | quantity                            | frozen kernel called unchanged                |
  | ----------------------------------- | --------------------------------------------- |
  | great-circle distance (sphere)      | `geodesy.haversine_distance`                   |
  | geodesic distance (WGS84)           | `geodesy.vincenty_distance`                    |
  | planar distance                     | `geometry.distance_2d` on `geometry.Point`     |
  | local metre plane, x                | `cartography.equirectangular_x`                |
  | local metre plane, y                | `cartography.equirectangular_y`                |

What is added is the part the frozen family has no place for: the axis order, the unit, the
refusal of a mixed pair, the seam, the poles, and the metre conversion.

Latitude/longitude swapped is the classic geospatial wrong answer
-----------------------------------------------------------------
`geodesy.haversine_distance(lat1, lon1, lat2, lon2)` takes latitude first. A caller holding
GeoJSON coordinates holds longitude first. Nothing in either signature says so, and a
swapped call returns a perfectly plausible number for a different place on Earth — London
to New York becomes 5570 km either way at a glance, but Tokyo to Sydney does not.

Three defences, in strength order, and the third one is the honest admission:

1. `frame_distance_flat` takes TWO frame tags, one per operand, and refuses a mismatch. So
   a metre-plane easting and a longitude cannot combine into a number at all.
2. Every coordinate is range-checked against ITS OWN SLOT (`contract.geo_pair_range_defect`),
   so a longitude of 174.7 sitting in a latitude slot is `GEO_ERR_RANGE`, not a wrapped
   angle. This catches every swap in which |longitude| > 90.
3. When every |x| and every |y| in a batch is <= 90, the batch is consistent with BOTH
   axis orders and NO validator can distinguish them. `frame_census_flat` reports
   `order_ambiguous = True` for exactly that case. That is a fact about the data, not a
   defect, and reporting it is the only truthful option — a silent guess is how the wrong
   answer ships.

Antimeridian and poles are answered, not assumed away
-----------------------------------------------------
A ring stored as raw longitudes cannot say whether the step 179 -> -179 is 2 degrees east
or 358 degrees west. `frame_ring_census_flat` reports:

* `antimeridian_edges` — edges whose RAW longitude difference is 180 degrees or more. Such
  an edge has no unambiguous shortest connection, so every planar operation in this package
  refuses a ring that has one (`GEO_ERR_ANTIMERIDIAN`) instead of picking a side. Splitting
  the ring at the seam is the caller's decision, because which side each part belongs to is
  domain knowledge this kernel does not have.
* `lon_winding_deg` — the sum of the SHORTEST signed longitude steps around the closed ring.
  In exact arithmetic that is 0 for a ring that does not enclose a pole and +-360 for one
  that does, so `|winding| > 180` is a robust test with no tolerance to tune. A ring
  enclosing a pole cannot be represented as a longitude/latitude ring at all — its boundary
  does not separate the plane the way the planar algorithms assume — so it is refused with
  `GEO_ERR_POLE`.
* `touches_pole` — a vertex at exactly +-90 latitude, where a degree of longitude is zero
  metres. Reported rather than refused: a ring with a vertex at the pole is still a valid
  planar ring; the metre SCALE there is what degenerates, and `m_per_deg_lon_lower` says so
  by returning 0.0.

Everything is metres out
------------------------
The frozen geodesy kernels return kilometres. That conversion happens exactly once, here,
so no other module in the package multiplies by 1000 and none of them can disagree about
the unit. `frame_metric_distance` is the package's single definition of "the distance
between two coordinate pairs", and `index`, `join` and `mapmatch` all call it.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_geospatial_frame.mojo
benchmark: benchmarks/mojo_benchmarks/bench_geospatial.mojo
docs: gitbook/engine/geospatial.md
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, cos

from cartography import equirectangular_x, equirectangular_y
from geodesy import haversine_distance, vincenty_distance
from geometry import Point, distance_2d

from geospatial.contract import (
    GEO_EARTH_RADIUS_M,
    GEO_ERR_FRAME,
    GEO_ERR_FRAME_MISMATCH,
    GEO_ERR_METRIC_NO_CONVERGENCE,
    GEO_ERR_PARAM,
    GEO_ERR_RANGE,
    GEO_MAX_LAT_DEG,
    GEO_MAX_LON_DEG,
    GEO_MAX_POINTS,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_VINCENTY,
    GEO_OK,
    GEO_PI,
    geo_finite,
    geo_finite_or_zero,
    geo_frame_defect,
    geo_is_degree_frame,
    geo_lat_of,
    geo_lon_delta,
    geo_lon_of,
    geo_m_per_deg_lon_lower,
    geo_metric_defect,
    geo_pair_range_defect,
    geo_points_defect,
)


# ── returned structs, all declared HERE ───────────────────────────────────────
# A struct owned by another module is silently DROPPED from the contract (the marshalling
# spec is parsed one file at a time), so every public result type in this package is
# declared in the file whose functions return it.


@fieldwise_init
struct FrameCensus(Copyable, Movable):
    """What an unordered batch of coordinates is, in its declared frame.

    `has_extent` is False for an empty batch: the bounding box of nothing does not exist,
    and returning zeros for it would be the "absence is not zero" defect. When it is False
    every extent slot is 0.0 and means nothing.
    """

    var status: Int
    var n_points: Int
    var frame: Int
    var has_extent: Bool
    var min_x: Float64
    var min_y: Float64
    var max_x: Float64
    var max_y: Float64
    var has_span: Bool
    var lon_span_deg: Float64
    var lat_span_deg: Float64
    var order_ambiguous: Bool
    var extent_spans_antimeridian: Bool
    var touches_pole: Bool
    var has_metre_scale: Bool
    var m_per_deg_lon_lower: Float64


@fieldwise_init
struct RingFrameCensus(Copyable, Movable):
    """What an ORDERED ring is, on the sphere: the seam, the poles, and its extent.

    Separate from `FrameCensus` because the two questions are different: a point set has no
    edges, so it can straddle the seam without any edge crossing it, while a ring's edges
    are what make the crossing unambiguous or not.
    """

    var status: Int
    var n_vertices: Int
    var frame: Int
    var explicitly_closed: Bool
    var n_edges: Int
    var antimeridian_edges: Int
    var has_winding: Bool
    var lon_winding_deg: Float64
    var encircles_pole: Bool
    var touches_pole: Bool
    var has_extent: Bool
    var min_x: Float64
    var min_y: Float64
    var max_x: Float64
    var max_y: Float64


@fieldwise_init
struct GeoDistance(Copyable, Movable):
    """One distance in METRES, with the frame and metric that produced it.

    `has_distance` is the answer when it is False: `distance_m` is then 0.0, which is
    representable, and a caller must not read it as "zero metres apart".
    """

    var status: Int
    var has_distance: Bool
    var distance_m: Float64
    var frame: Int
    var metric: Int


@fieldwise_init
struct PathLength(Copyable, Movable):
    """The length of an ordered polyline in metres, plus its per-segment extremes."""

    var status: Int
    var n_segments: Int
    var has_length: Bool
    var length_m: Float64
    var has_extremes: Bool
    var min_segment_m: Float64
    var max_segment_m: Float64
    var frame: Int
    var metric: Int


@fieldwise_init
struct ProjectedPoints(Copyable, Movable):
    """A batch projected to a local equirectangular metre plane about a reference point.

    Both arrays are EMPTY on any refusal — never a padded list of zeros, which a caller
    cannot distinguish from a projection of the origin.
    """

    var status: Int
    var n_points: Int
    var has_result: Bool
    var ref_lat_deg: Float64
    var ref_lon_deg: Float64
    var lon_span_deg: Float64
    var lat_span_deg: Float64
    var xs_m: List[Float64]
    var ys_m: List[Float64]


# ── the package's single definition of "distance" ──────────────────────────────


fn frame_metric_distance(
    x1: Float64, y1: Float64, x2: Float64, y2: Float64, frame: Int, metric: Int
) -> Float64:
    """Distance in METRES between two pairs in one frame under one metric.

    The one place in the package where a metric is chosen and where kilometres become
    metres, so `index`, `join` and `mapmatch` cannot disagree about either. Each branch is
    a call into a frozen kernel and nothing else:

        HAVERSINE  -> geodesy.haversine_distance  (sphere, R = 6371 km)  * 1000
        VINCENTY   -> geodesy.vincenty_distance   (WGS84 ellipsoid)      * 1000
        EUCLIDEAN  -> geometry.distance_2d        (projected plane, metres already)

    Both frozen geodesy kernels take LATITUDE FIRST, so the axis order is resolved by
    `contract.geo_lat_of` / `geo_lon_of` from the frame tag rather than by the caller
    remembering — which is the swap this package exists to make impossible.

    Validation is the CALLER's: this returns 0.0 for a frame/metric pair that is not
    defined (`contract.geo_metric_defect` is the gate) and 0.0 rather than a non-finite for
    a non-finite input, because a distance of "not a number" cannot cross the wire. Public
    entry points call `geo_metric_defect` first and report a status; this is the arithmetic
    behind them, exposed because a caller with already-validated coordinates should not
    have to re-derive the metre conversion.
    
    @capability frame_metric_distance
    complexity: O(1)
    counts: none
    @endcapability
    """
    if geo_metric_defect(frame, metric) != GEO_OK:
        return 0.0
    if not (geo_finite(x1) and geo_finite(y1) and geo_finite(x2) and geo_finite(y2)):
        return 0.0
    if metric == GEO_METRIC_EUCLIDEAN:
        return geo_finite_or_zero(distance_2d(Point(x1, y1), Point(x2, y2)))
    var lat1 = geo_lat_of(x1, y1, frame)
    var lon1 = geo_lon_of(x1, y1, frame)
    var lat2 = geo_lat_of(x2, y2, frame)
    var lon2 = geo_lon_of(x2, y2, frame)
    if metric == GEO_METRIC_VINCENTY:
        return geo_finite_or_zero(vincenty_distance(lat1, lon1, lat2, lon2) * 1000.0)
    return geo_finite_or_zero(haversine_distance(lat1, lon1, lat2, lon2) * 1000.0)


fn frame_metric_undefined(
    distance_m: Float64, x1: Float64, y1: Float64, x2: Float64, y2: Float64,
    frame: Int, metric: Int,
) -> Bool:
    """True when `distance_m` is a value the metric could not actually produce for THIS pair.

    `distance_m` is what `frame_metric_distance` returned for the same pair, frame and metric.
    It is a parameter rather than recomputed because the check is now made for EVERY Vincenty
    pair and recomputing the ellipsoidal solve would double the cost of the metric.

    TWO cases exist, and both belong to `geodesy.vincenty_distance`'s two early exits.

    1. `sin(sigma) < 1e-12` returns 0.0 km labelled "coincident points" — but `sin(sigma)` is
       zero at `sigma = pi` as well as at `sigma = 0`, so the ANTIPODAL pair (0N, 0E) /
       (0N, 180E) is reported as zero metres apart when it is 20 015 km apart. (0N,0E)/
       (0N,179.9E) converges normally, so the failure is a knife-edge.
    2. One hundred iterations without convergence `return haversine_distance(...)` — the
       SPHERICAL value under the ellipsoidal metric's name, for near-antipodal pairs that do
       not hit case 1. Undetected, this is precisely the silent model substitution that
       `GEO_ERR_METRIC_NO_CONVERGENCE` exists to refuse, made by the code that refuses it.

    The kernel is frozen and is not edited. What is added is the DETECTION, and the frozen
    `haversine_distance` is the oracle for both cases:

        distance == 0  and  haversine > 0        =>  case 1, the solver degenerated
        distance == haversine  and  haversine > 0 =>  case 2, the fallback fired

    Neither test carries a tolerance: the fallback returns the spherical number through the
    identical `* 1000.0`, so the equality is bit-exact and deterministic, and a genuinely
    coincident pair has `haversine == 0` and is excluded by the same clause in both.

    Case 2's test is CONSERVATIVE in the one direction that is safe. WGS84 distances cross the
    6371 km sphere's somewhere between the equator and the poles, so a converged pair could in
    principle land bit-exactly on its spherical counterpart and be refused; the answer is then
    a typed refusal rather than a wrong number, which is the direction this package errs in
    everywhere else.

    @capability frame_metric_undefined
    complexity: O(1)
    counts: none
    @endcapability
    """
    if metric != GEO_METRIC_VINCENTY or not geo_is_degree_frame(frame):
        return False
    if geo_pair_range_defect(x1, y1, frame) != GEO_OK:
        return False
    if geo_pair_range_defect(x2, y2, frame) != GEO_OK:
        return False
    var lat1 = geo_lat_of(x1, y1, frame)
    var lon1 = geo_lon_of(x1, y1, frame)
    var lat2 = geo_lat_of(x2, y2, frame)
    var lon2 = geo_lon_of(x2, y2, frame)
    var hav = geo_finite_or_zero(haversine_distance(lat1, lon1, lat2, lon2) * 1000.0)
    if hav <= 0.0:
        return False
    if distance_m == 0.0:
        return True
    return distance_m == hav


# The parameter PACKING below is load-bearing, not style: `mojo_inventory` parses a signature
# inside a TEN-LINE lookahead window and silently drops any function whose signature closes
# later. Do not reflow.
fn frame_distance_flat(
    x1: Float64, y1: Float64, frame_a: Int,
    x2: Float64, y2: Float64, frame_b: Int, metric: Int,
) -> GeoDistance:
    """Distance in metres between two pairs, REFUSING a mixed pair.

    Two frame tags, one per operand, is the whole point: `frame_a != frame_b` is
    `GEO_ERR_FRAME_MISMATCH` and no number comes back. A single-frame signature would make
    the mismatch unrepresentable in the API and therefore undetectable at the call site,
    which is where it happens — one endpoint from a GeoJSON feed, the other from a
    projected shapefile.

    Order of refusal: unknown frame, mismatched frames, metric undefined for the frame,
    then a coordinate outside its slot's range. Each is a different mistake at the caller.
    
    @capability frame_distance_flat
    complexity: O(1)
    counts: none
    @endcapability
    """
    if frame_a != frame_b:
        var fd_a = geo_metric_defect(frame_a, metric)
        if fd_a == GEO_ERR_FRAME:
            return GeoDistance(GEO_ERR_FRAME, False, 0.0, frame_a, metric)
        var fd_b = geo_metric_defect(frame_b, metric)
        if fd_b == GEO_ERR_FRAME:
            return GeoDistance(GEO_ERR_FRAME, False, 0.0, frame_b, metric)
        return GeoDistance(GEO_ERR_FRAME_MISMATCH, False, 0.0, frame_a, metric)
    var md = geo_metric_defect(frame_a, metric)
    if md != GEO_OK:
        return GeoDistance(md, False, 0.0, frame_a, metric)
    var r1 = geo_pair_range_defect(x1, y1, frame_a)
    if r1 != GEO_OK:
        return GeoDistance(r1, False, 0.0, frame_a, metric)
    var r2 = geo_pair_range_defect(x2, y2, frame_a)
    if r2 != GEO_OK:
        return GeoDistance(r2, False, 0.0, frame_a, metric)
    var d = frame_metric_distance(x1, y1, x2, y2, frame_a, metric)
    if not geo_finite(d):
        return GeoDistance(GEO_ERR_RANGE, False, 0.0, frame_a, metric)
    if frame_metric_undefined(d, x1, y1, x2, y2, frame_a, metric):
        return GeoDistance(GEO_ERR_METRIC_NO_CONVERGENCE, False, 0.0, frame_a, metric)
    return GeoDistance(GEO_OK, True, d, frame_a, metric)


# ── census of an unordered batch ───────────────────────────────────────────────


fn frame_census_flat(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int
) -> FrameCensus:
    """What this batch of coordinates is, before anything is computed from it.

    Reports rather than decides, except for the defects that make every downstream answer
    meaningless (a non-finite, an out-of-slot coordinate, a count past the arrays).

    `order_ambiguous` is the field to read before trusting any distance: True means every
    |x| and every |y| is at most 90, so the batch parses identically as lon/lat and as
    lat/lon and this kernel cannot tell which the caller meant. `extent_spans_antimeridian`
    means the raw longitude span exceeds 180 degrees, which for a point set is legal (a
    global dataset) but makes a bounding-box window query near the seam wrong, so the
    window queries in `index` refuse a wrapped window rather than silently returning the
    complement.

    @capability frame_census_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_POINTS)
    if defect != GEO_OK:
        return FrameCensus(
            defect, n, frame, False, 0.0, 0.0, 0.0, 0.0, False, 0.0, 0.0,
            False, False, False, False, 0.0,
        )
    if n == 0:
        # The extent of nothing does not exist. Status is OK — an empty batch is a valid
        # batch — and every absence flag is False.
        return FrameCensus(
            GEO_OK, 0, frame, False, 0.0, 0.0, 0.0, 0.0, False, 0.0, 0.0,
            False, False, False, False, 0.0,
        )
    var min_x = xs[0]
    var max_x = xs[0]
    var min_y = ys[0]
    var max_y = ys[0]
    var max_abs_x = fabs(xs[0])
    var max_abs_y = fabs(ys[0])
    var touches_pole = False
    for i in range(n):
        if xs[i] < min_x:
            min_x = xs[i]
        if xs[i] > max_x:
            max_x = xs[i]
        if ys[i] < min_y:
            min_y = ys[i]
        if ys[i] > max_y:
            max_y = ys[i]
        if fabs(xs[i]) > max_abs_x:
            max_abs_x = fabs(xs[i])
        if fabs(ys[i]) > max_abs_y:
            max_abs_y = fabs(ys[i])
        if geo_is_degree_frame(frame):
            if fabs(geo_lat_of(xs[i], ys[i], frame)) == GEO_MAX_LAT_DEG:
                touches_pole = True

    var degrees = geo_is_degree_frame(frame)
    var lon_span = 0.0
    var lat_span = 0.0
    var has_span = False
    var ambiguous = False
    var wraps = False
    var scale = 0.0
    var has_scale = False
    if degrees:
        has_span = True
        var lo_lat = geo_lat_of(min_x, min_y, frame)
        var hi_lat = geo_lat_of(max_x, max_y, frame)
        var lo_lon = geo_lon_of(min_x, min_y, frame)
        var hi_lon = geo_lon_of(max_x, max_y, frame)
        lat_span = hi_lat - lo_lat
        lon_span = hi_lon - lo_lon
        wraps = lon_span > 180.0
        # Both slots within +-90 => the data reads the same in either axis order.
        ambiguous = max_abs_x <= GEO_MAX_LAT_DEG and max_abs_y <= GEO_MAX_LAT_DEG
        scale = geo_m_per_deg_lon_lower(lo_lat, hi_lat)
        has_scale = scale > 0.0
    return FrameCensus(
        GEO_OK,
        n,
        frame,
        True,
        geo_finite_or_zero(min_x),
        geo_finite_or_zero(min_y),
        geo_finite_or_zero(max_x),
        geo_finite_or_zero(max_y),
        has_span,
        geo_finite_or_zero(lon_span),
        geo_finite_or_zero(lat_span),
        ambiguous,
        wraps,
        touches_pole,
        has_scale,
        geo_finite_or_zero(scale),
    )


# ── census of an ordered ring ─────────────────────────────────────────────────


fn frame_ring_census_flat(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int
) -> RingFrameCensus:
    """The seam and pole verdict for an ORDERED ring, and its extent.

    The ring is treated as implicitly closed: edge `i` runs from vertex `i` to vertex
    `(i + 1) % n`. A caller who also repeats the first vertex at the end therefore supplies
    one extra ZERO-LENGTH edge, which is inert under every rule in this package — it has a
    zero longitude delta so it adds nothing to the winding and cannot be an antimeridian
    edge, and in `polygon` it is skipped by the half-open crossing rule and can only be hit
    by the boundary test at a vertex the boundary test already covers. `explicitly_closed`
    reports which form arrived.

    Both verdicts are exact-threshold tests with no tolerance to tune:

    * an edge is an ANTIMERIDIAN edge when |raw longitude difference| >= 180, i.e. when the
      shortest connection between its endpoints is ambiguous or crosses the seam;
    * the ring ENCIRCLES a pole when the sum of shortest signed longitude steps around it
      exceeds 180 in magnitude, which in exact arithmetic can only be 0 or +-360.

    @capability frame_ring_census_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_POINTS)
    if defect != GEO_OK:
        return RingFrameCensus(
            defect, n, frame, False, 0, 0, False, 0.0, False, False, False,
            0.0, 0.0, 0.0, 0.0,
        )
    if n == 0:
        return RingFrameCensus(
            GEO_OK, 0, frame, False, 0, 0, False, 0.0, False, False, False,
            0.0, 0.0, 0.0, 0.0,
        )
    var closed = n >= 2 and xs[n - 1] == xs[0] and ys[n - 1] == ys[0]
    var min_x = xs[0]
    var max_x = xs[0]
    var min_y = ys[0]
    var max_y = ys[0]
    var touches_pole = False
    for i in range(n):
        if xs[i] < min_x:
            min_x = xs[i]
        if xs[i] > max_x:
            max_x = xs[i]
        if ys[i] < min_y:
            min_y = ys[i]
        if ys[i] > max_y:
            max_y = ys[i]
        if geo_is_degree_frame(frame):
            if fabs(geo_lat_of(xs[i], ys[i], frame)) == GEO_MAX_LAT_DEG:
                touches_pole = True

    var degrees = geo_is_degree_frame(frame)
    var seam_edges = 0
    var winding = 0.0
    var has_winding = False
    if degrees and n >= 2:
        has_winding = True
        for i in range(n):
            var j = i + 1
            if j == n:
                j = 0
            var lon_i = geo_lon_of(xs[i], ys[i], frame)
            var lon_j = geo_lon_of(xs[j], ys[j], frame)
            if fabs(lon_j - lon_i) >= 180.0:
                seam_edges += 1
            winding += geo_lon_delta(lon_i, lon_j)
    return RingFrameCensus(
        GEO_OK,
        n,
        frame,
        closed,
        n if n >= 2 else 0,
        seam_edges,
        has_winding,
        geo_finite_or_zero(winding),
        has_winding and fabs(winding) > 180.0,
        touches_pole,
        True,
        geo_finite_or_zero(min_x),
        geo_finite_or_zero(min_y),
        geo_finite_or_zero(max_x),
        geo_finite_or_zero(max_y),
    )


# ── path length ───────────────────────────────────────────────────────────────


fn frame_path_length_flat(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int, metric: Int
) -> PathLength:
    """Length of an ordered polyline in metres, plus its shortest and longest segment.

    One point is a valid path with ZERO segments and therefore no length: `has_length` is
    False and `length_m` is 0.0. That is not pedantry — a track reduced to one fix by a
    filter must not report a zero-metre journey, which downstream code reads as "did not
    move" rather than "cannot say".

    @capability frame_path_length_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var md = geo_metric_defect(frame, metric)
    if md != GEO_OK:
        return PathLength(md, 0, False, 0.0, False, 0.0, 0.0, frame, metric)
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_POINTS)
    if defect != GEO_OK:
        return PathLength(defect, 0, False, 0.0, False, 0.0, 0.0, frame, metric)
    if n < 2:
        return PathLength(GEO_OK, 0, False, 0.0, False, 0.0, 0.0, frame, metric)
    var total = 0.0
    var lo = 0.0
    var hi = 0.0
    for i in range(n - 1):
        var d = frame_metric_distance(xs[i], ys[i], xs[i + 1], ys[i + 1], frame, metric)
        if frame_metric_undefined(
            d, xs[i], ys[i], xs[i + 1], ys[i + 1], frame, metric
        ):
            return PathLength(
                GEO_ERR_METRIC_NO_CONVERGENCE, n - 1, False, 0.0, False, 0.0, 0.0,
                frame, metric,
            )
        total += d
        if i == 0:
            lo = d
            hi = d
        else:
            if d < lo:
                lo = d
            if d > hi:
                hi = d
    if not geo_finite(total):
        return PathLength(GEO_ERR_RANGE, n - 1, False, 0.0, False, 0.0, 0.0, frame, metric)
    return PathLength(
        GEO_OK,
        n - 1,
        True,
        geo_finite_or_zero(total),
        True,
        geo_finite_or_zero(lo),
        geo_finite_or_zero(hi),
        frame,
        metric,
    )


# ── projection to a local metre plane ─────────────────────────────────────────


# Packing is load-bearing — see the note above `frame_distance_flat`.
fn frame_project_flat(
    xs: List[Float64], ys: List[Float64], n: Int,
    frame: Int, ref_lat_deg: Float64, ref_lon_deg: Float64,
) -> ProjectedPoints:
    """Project a degree batch onto a local equirectangular METRE plane about a reference.

    The projection itself is the frozen `cartography.equirectangular_x` and
    `equirectangular_y`; what is added is the reference point, the metre scaling by the
    sphere radius that keeps it consistent with `geodesy.haversine_distance`, and the
    validation.

        x_m = R * equirectangular_x(lon_rad, ref_lon_rad, cos(ref_lat_rad))
        y_m = R * (equirectangular_y(lat_rad) - equirectangular_y(ref_lat_rad))

    This exists because the planar algorithms in `polygon` need metres, and because area in
    square degrees is not an area. The distortion is real and stated rather than hidden:
    east-west scale is exact only at `ref_lat_deg` and shrinks as cos(lat)/cos(ref_lat)
    away from it, so the caller is told the latitude span it asked for. A frame that is
    already `PLANE_M` is refused (`GEO_ERR_FRAME`) rather than passed through, because
    "project the projected" is a request whose meaning the caller and this kernel would be
    guessing at differently.

    @capability frame_project_flat
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var empty_x = List[Float64]()
    var empty_y = List[Float64]()
    if not geo_is_degree_frame(frame):
        return ProjectedPoints(
            GEO_ERR_FRAME, 0, False, 0.0, 0.0, 0.0, 0.0, empty_x^, empty_y^
        )
    if not geo_finite(ref_lat_deg) or not geo_finite(ref_lon_deg):
        return ProjectedPoints(
            GEO_ERR_PARAM, 0, False, 0.0, 0.0, 0.0, 0.0, empty_x^, empty_y^
        )
    if fabs(ref_lat_deg) > GEO_MAX_LAT_DEG or fabs(ref_lon_deg) > GEO_MAX_LON_DEG:
        return ProjectedPoints(
            GEO_ERR_PARAM, 0, False, 0.0, 0.0, 0.0, 0.0, empty_x^, empty_y^
        )
    var defect = geo_points_defect(xs, ys, n, frame, GEO_MAX_POINTS)
    if defect != GEO_OK:
        return ProjectedPoints(
            defect, 0, False, 0.0, 0.0, 0.0, 0.0, empty_x^, empty_y^
        )
    var ref_lat_rad = ref_lat_deg * GEO_PI / 180.0
    var ref_lon_rad = ref_lon_deg * GEO_PI / 180.0
    var cos_ref = cos(ref_lat_rad)
    var out_x = List[Float64]()
    var out_y = List[Float64]()
    var lon_lo = 0.0
    var lon_hi = 0.0
    var lat_lo = 0.0
    var lat_hi = 0.0
    for i in range(n):
        var lat = geo_lat_of(xs[i], ys[i], frame)
        var lon = geo_lon_of(xs[i], ys[i], frame)
        if i == 0:
            lon_lo = lon
            lon_hi = lon
            lat_lo = lat
            lat_hi = lat
        else:
            if lon < lon_lo:
                lon_lo = lon
            if lon > lon_hi:
                lon_hi = lon
            if lat < lat_lo:
                lat_lo = lat
            if lat > lat_hi:
                lat_hi = lat
        var lat_rad = lat * GEO_PI / 180.0
        var lon_rad = lon * GEO_PI / 180.0
        var px = GEO_EARTH_RADIUS_M * equirectangular_x(lon_rad, ref_lon_rad, cos_ref)
        var py = GEO_EARTH_RADIUS_M * (
            equirectangular_y(lat_rad) - equirectangular_y(ref_lat_rad)
        )
        out_x.append(geo_finite_or_zero(px))
        out_y.append(geo_finite_or_zero(py))
    return ProjectedPoints(
        GEO_OK,
        n,
        True,
        geo_finite_or_zero(ref_lat_deg),
        geo_finite_or_zero(ref_lon_deg),
        geo_finite_or_zero(lon_hi - lon_lo),
        geo_finite_or_zero(lat_hi - lat_lo),
        out_x^,
        out_y^,
    )


fn frame_pair_defect(frame_a: Int, frame_b: Int) -> Int:
    """`GEO_OK` when two operands may be combined; the reason they may not otherwise.

    Exposed separately so a caller composing several calls can ask the question once,
    instead of discovering the mismatch as a surprising `GEO_ERR_FRAME_MISMATCH` from the
    third call in a chain. Also the single definition the rest of the package uses, so a
    mismatch is never enforced at two different strengths.
    
    @capability frame_pair_defect
    complexity: O(1)
    counts: none
    @endcapability
    """
    if geo_frame_defect(frame_a) != GEO_OK:
        return GEO_ERR_FRAME
    if geo_frame_defect(frame_b) != GEO_OK:
        return GEO_ERR_FRAME
    if frame_a != frame_b:
        return GEO_ERR_FRAME_MISMATCH
    return GEO_OK
