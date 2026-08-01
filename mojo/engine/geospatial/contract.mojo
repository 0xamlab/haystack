"""
geospatial.contract — the one status vocabulary, frame vocabulary and guard for the package.

Zero Python imports. Nothing here computes geometry; it decides what a request MEANS and
whether it may proceed.

Why the codes all live in ONE file
----------------------------------
Rule 4e of `new-kernel-package-rules.md` was written because two files in one package
independently claimed codes 80-84, so one integer named two different defects. The cheapest
way to make that impossible is to have exactly one place where a code is minted and exactly
one `geo_status_name`, and to assert in the suite that no two codes share an integer and no
two names repeat. Range 700-729 is this package's; nothing else in the tree owns it.

Coordinates are NOT interchangeable, so the frame travels with them
-------------------------------------------------------------------
There are three frames, and every function that consumes coordinates takes the tag:

    GEO_FRAME_LONLAT_DEG   x = longitude deg, y = latitude deg   (GeoJSON / "x,y" order)
    GEO_FRAME_LATLON_DEG   x = latitude deg,  y = longitude deg  (the order most APIs print)
    GEO_FRAME_PLANE_M      x = easting m,     y = northing m     (already projected)

The classic geospatial wrong answer is lat/lon silently swapped, which yields a plausible
distance to the wrong place. Three things are done about it, in order of strength:

1. *A distance between two operands takes TWO frame tags and refuses a mismatch*
   (`GEO_ERR_FRAME_MISMATCH`). Degrees against metres cannot silently produce a number.
2. *Every coordinate is range-checked against its own slot.* In `LONLAT_DEG` a `y` of 150
   is not a latitude, and the request is refused with `GEO_ERR_RANGE` rather than folded
   into a wrapped angle. This catches every swap in which the longitude exceeds 90 degrees
   in magnitude — most of the Americas, the Pacific, and all of Asia east of Kabul.
3. *The residue is REPORTED, because it is not detectable.* When every |x| and every |y| in
   a batch is at most 90, the data is consistent with BOTH orderings and no validator can
   tell them apart. `frame.frame_census_flat` returns `order_ambiguous = True` for exactly
   that case. Silence there would be the lie; a flag a caller can gate on is the truth.

Distances are returned in METRES, always, whatever the frame. The frozen geodesy kernels
return kilometres; the conversion happens once, at the boundary, in `frame.mojo`.

The count guard, and why it is `[kernel_validated]` everywhere in this package
-----------------------------------------------------------------------------
Reading past a `List` end is an uncatchable process abort: `try`/`except` does not help and
the respawn loses every resident dataset. So no function here trusts a caller's `n`.
`geo_points_defect` is the single gate: it checks `n` against BOTH coordinate lists, against
the declared ceiling, for finiteness and for range, and returns a code. Every public driver
calls it before it indexes anything, and every `counts:` block in this package therefore
says `[kernel_validated]` — the kernel really does check, and the guard must not pre-empt a
typed status with a generic refusal.

A negative `n` is not fatal (`range(-3)` reads nothing) but a negative INDEX is, so `n < 0`
is a hard refusal rather than a silent empty answer, and every parameter used as a subscript
(a ring offset, a cell id, a `k`) is bounded in BOTH directions where it is consumed.

Absence, per rule 4
-------------------
JSON has no NaN or infinity and the dispatch refuses a non-finite rather than serialising
it, so a raw non-finite in any struct field turns the WHOLE response into a typed error.
Every quantity that may not exist is therefore a `has_*` flag plus a slot that is
representable: when the flag is False the slot is `0.0`, and the FLAG is the answer.
`geo_finite_or_zero` is the one-line enforcement of that at every construction site.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_geospatial_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_geospatial.mojo
docs: gitbook/engine/geospatial.md
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, cos, isinf, isnan, sin


# ── status codes: 700-729, this package's whole allocation ─────────────────────
# One integer, one meaning, one namer. `geospatial.contract` is the only file in the
# package that mints a code; the suite asserts the mapping is injective in both
# directions, so a copy-paste collision fails the build rather than a caller's log.

comptime GEO_OK: Int = 700
# A complete answer would have exceeded a declared budget, so what came back is PARTIAL.
# It is a distinct status and not `GEO_OK`, because a truncated join presented as a join is
# the silent-wrong-answer this package exists to refuse.
comptime GEO_OK_TRUNCATED: Int = 701
comptime GEO_ERR_COUNT: Int = 702
comptime GEO_ERR_TOO_LARGE: Int = 703
comptime GEO_ERR_NON_FINITE: Int = 704
comptime GEO_ERR_FRAME: Int = 705
comptime GEO_ERR_FRAME_MISMATCH: Int = 706
comptime GEO_ERR_METRIC: Int = 707
comptime GEO_ERR_UNIT_MISMATCH: Int = 708
comptime GEO_ERR_RANGE: Int = 709
comptime GEO_ERR_PARAM: Int = 710
comptime GEO_ERR_EMPTY: Int = 711
comptime GEO_ERR_ANTIMERIDIAN: Int = 712
comptime GEO_ERR_POLE: Int = 713
comptime GEO_ERR_DEGENERATE_RING: Int = 714
comptime GEO_ERR_SELF_INTERSECTING: Int = 715
comptime GEO_ERR_NOT_CONVEX: Int = 716
comptime GEO_ERR_LAYOUT: Int = 717
comptime GEO_ERR_WINDOW: Int = 718
comptime GEO_ERR_BUDGET: Int = 719
comptime GEO_ERR_NO_CANDIDATE: Int = 720
comptime GEO_ERR_OFFSETS: Int = 721
# Distinct from GEO_ERR_METRIC ("no such metric") and GEO_ERR_UNIT_MISMATCH ("that metric is
# undefined for that frame"). This one means the metric EXISTS and IS defined for the frame,
# but this particular entry point cannot serve it: `index.grid_knn_flat` proves exactness
# with a bound derived on the sphere `geodesy.haversine_distance` uses, and that proof does
# not carry to the WGS84 ellipsoid, so an ellipsoidal request is refused rather than served
# with an unprovable exactness claim. Three different causes, three codes, because a caller
# fixes each one differently.
comptime GEO_ERR_METRIC_UNSUPPORTED_HERE: Int = 722
# The metric exists, is defined for the frame, is supported by this entry point — and still
# could not produce a value for THIS pair of points. There is exactly one such case in the
# tree today and it is remotely triggerable: `geodesy.vincenty_distance` tests `sin(sigma)`
# against 1e-12 and reads the result as "coincident points", returning 0.0 km. But sin(sigma)
# is also zero at sigma = pi, so the two ANTIPODAL points (0N, 0E) and (0N, 180E) come back
# 0.0 km apart when they are 20 015 km apart. Substituting the spherical answer there would
# silently change the model mid-metric; returning the 0.0 would put a wrong number inside a
# radius join. So the pair is reported ABSENT under this code, and the caller switches metric.
comptime GEO_ERR_METRIC_NO_CONVERGENCE: Int = 723


# ── frames ────────────────────────────────────────────────────────────────────

comptime GEO_FRAME_LONLAT_DEG: Int = 0
comptime GEO_FRAME_LATLON_DEG: Int = 1
comptime GEO_FRAME_PLANE_M: Int = 2
comptime GEO_FRAME_COUNT: Int = 3


# ── metrics ───────────────────────────────────────────────────────────────────
# Each names the FROZEN kernel it dispatches to. Nothing here computes a distance.

comptime GEO_METRIC_HAVERSINE: Int = 0  # geodesy.haversine_distance, sphere R = 6371 km
comptime GEO_METRIC_VINCENTY: Int = 1  # geodesy.vincenty_distance, WGS84 ellipsoid
comptime GEO_METRIC_EUCLIDEAN: Int = 2  # geometry.distance_2d, projected plane
comptime GEO_METRIC_COUNT: Int = 3


# ── ceilings: memory AND work, per rule 1c ────────────────────────────────────
# "Bounding memory is not bounding work." Each ceiling below names the loop it charges,
# because a ceiling that bounds one factor of a product is not a budget.

# A point set. The index build holds, at peak: two Int cell/id arrays, a Float64 value
# array and the frozen COO's entry list (2 Int + 1 Float64 each) — about 48 bytes per
# point — plus the cell pointer array. 2^20 points is therefore ~50 MB against the
# 512 MiB single-object budget, with room for the caller's own two coordinate arrays.
comptime GEO_MAX_POINTS: Int = 1 << 20

# A ring, for the O(n) operations: point-in-polygon, area, bounding box, winding.
comptime GEO_MAX_RING_VERTICES: Int = 1 << 16

# Simplicity (self-intersection) is an O(n^2) edge-pair test. 2^11 vertices is ~2.1M pairs,
# which is milliseconds; the ceiling for the O(n) operations is 32x higher. Above this the
# report says `simplicity_checked = False` — absence, not a claim — exactly as the frozen
# `optimization.routing.distance_matrix_check` reports `triangle_checked`.
comptime GEO_MAX_SIMPLICITY_VERTICES: Int = 1 << 11

# The grid side ceiling lives in `index.mojo` and the emitted-pair ceiling in `join.mojo`,
# each in the ONE file whose kernel tests it. Both are named by a `dim ... <= NAME`
# capability declaration, and the manifest gate resolves such a name only against a
# same-file `comptime`: a ceiling declared here and tested there could drift silently, so
# the constant lives with its check. Everything below is used by two or more modules.

# A route matrix is n_o * n_d cells of Float64 AND n_o * n_d distance evaluations, so this
# one ceiling charges both. 2^22 cells is 33 MB and ~4.2M haversine calls.
comptime GEO_MAX_MATRIX_CELLS: Int = 1 << 22

# Candidate TESTS, which is the work a spatial join actually does — distinct from the pair
# ceiling, because a query can examine many candidates and emit none.
comptime GEO_MAX_CANDIDATE_WORK: Int = 1 << 26

# Polylines in a network, and the DP width per track point. The map-matching cost is
# sum over t of |C_t| * |C_{t-1}|, so the per-point candidate cap is what bounds the DP;
# GEO_MAX_CANDIDATE_WORK charges the total.
comptime GEO_MAX_LINES: Int = 1 << 16
comptime GEO_MAX_CANDIDATES_PER_POINT: Int = 32


# ── geodetic constants, kept consistent with the frozen kernels ───────────────
# `geodesy.haversine_distance` uses EARTH_RADIUS_KM = 6371.0. Every metre value this
# package derives from an ANGLE uses the same sphere, so a bound computed here and a
# distance computed by the frozen kernel are on the same model. Using a different radius
# would make a "lower bound" occasionally larger than the value it bounds.

comptime GEO_PI: Float64 = 3.141592653589793
comptime GEO_EARTH_RADIUS_M: Float64 = 6371000.0
#: Metres per degree of LATITUDE on that sphere: pi * R / 180. Also the metres per degree
#: of longitude AT THE EQUATOR, which is why the longitude bound below scales it by cos.
comptime GEO_M_PER_DEG: Float64 = 111194.92664455873
comptime GEO_MAX_LAT_DEG: Float64 = 90.0
comptime GEO_MAX_LON_DEG: Float64 = 180.0

#: Relative slack subtracted from a derived geometric LOWER BOUND, to absorb the error of the
#: `std.math` transcendentals it is built from (which are not correctly rounded here). It is
#: not a modelling tolerance and no comparison of two computed quantities uses it: it makes a
#: bound provably conservative, and being conservative only ever costs extra candidates.
comptime GEO_BOUND_SLACK: Float64 = 1.0e-9


fn geo_status_name(code: Int) -> String:
    """The name of a status code, so a failure surfaces the defect and not a bare number.

    @capability geo_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if code == GEO_OK:
        return "ok"
    if code == GEO_OK_TRUNCATED:
        return "ok_partial_budget_reached"
    if code == GEO_ERR_COUNT:
        return "count_exceeds_coordinate_arrays"
    if code == GEO_ERR_TOO_LARGE:
        return "count_above_declared_ceiling"
    if code == GEO_ERR_NON_FINITE:
        return "non_finite_coordinate"
    if code == GEO_ERR_FRAME:
        return "unknown_coordinate_frame"
    if code == GEO_ERR_FRAME_MISMATCH:
        return "operands_in_different_frames"
    if code == GEO_ERR_METRIC:
        return "unknown_distance_metric"
    if code == GEO_ERR_UNIT_MISMATCH:
        return "metric_undefined_for_that_frame"
    if code == GEO_ERR_RANGE:
        return "coordinate_outside_frame_range"
    if code == GEO_ERR_PARAM:
        return "scalar_parameter_out_of_range"
    if code == GEO_ERR_EMPTY:
        return "no_answer_exists_for_empty_input"
    if code == GEO_ERR_ANTIMERIDIAN:
        return "geometry_crosses_the_antimeridian"
    if code == GEO_ERR_POLE:
        return "geometry_encircles_a_pole"
    if code == GEO_ERR_DEGENERATE_RING:
        return "ring_has_no_interior"
    if code == GEO_ERR_SELF_INTERSECTING:
        return "ring_is_self_intersecting"
    if code == GEO_ERR_NOT_CONVEX:
        return "clip_polygon_is_not_convex"
    if code == GEO_ERR_LAYOUT:
        return "index_layout_unsound"
    if code == GEO_ERR_WINDOW:
        return "query_window_inverted_or_wrapped"
    if code == GEO_ERR_BUDGET:
        return "declared_work_budget_exceeded"
    if code == GEO_ERR_NO_CANDIDATE:
        return "track_point_has_no_candidate_within_radius"
    if code == GEO_ERR_OFFSETS:
        return "offsets_array_unsound"
    if code == GEO_ERR_METRIC_UNSUPPORTED_HERE:
        return "metric_not_supported_by_this_entry_point"
    if code == GEO_ERR_METRIC_NO_CONVERGENCE:
        return "metric_undefined_for_this_pair_of_points"
    return "unknown_status"


fn geo_frame_name(frame: Int) -> String:
    """The name of a frame tag, including its axis order — the order IS the meaning.

    @capability geo_frame_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if frame == GEO_FRAME_LONLAT_DEG:
        return "lonlat_deg_x_is_longitude"
    if frame == GEO_FRAME_LATLON_DEG:
        return "latlon_deg_x_is_latitude"
    if frame == GEO_FRAME_PLANE_M:
        return "plane_m_x_is_easting"
    return "unknown_frame"


fn geo_metric_name(metric: Int) -> String:
    """The name of a metric tag, and therefore of the frozen kernel it dispatches to.

    @capability geo_metric_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if metric == GEO_METRIC_HAVERSINE:
        return "haversine_sphere_6371km"
    if metric == GEO_METRIC_VINCENTY:
        return "vincenty_wgs84"
    if metric == GEO_METRIC_EUCLIDEAN:
        return "euclidean_projected_plane"
    return "unknown_metric"


fn geo_finite(v: Float64) -> Bool:
    """True for a value the dispatch can serialise. NaN and both infinities are not.

    @capability geo_finite
    complexity: O(1)
    counts: none
    @endcapability
    """
    return not (isnan(v) or isinf(v))


fn geo_finite_or_zero(v: Float64) -> Float64:
    """`v` when representable, else `0.0`.

    Called at EVERY struct construction site in this package. The dispatch refuses a
    non-finite rather than serialising it, so one raw NaN in one field turns an otherwise
    complete answer into a typed transport error for the whole response. The paired
    `has_*` flag is what says whether the slot means anything; this only guarantees the
    slot is representable.
    
    @capability geo_finite_or_zero
    complexity: O(1)
    counts: none
    @endcapability
    """
    if geo_finite(v):
        return v
    return 0.0


fn geo_is_degree_frame(frame: Int) -> Bool:
    """True for the two angular frames. `PLANE_M` is metric and shares no comparison.

    @capability geo_is_degree_frame
    complexity: O(1)
    counts: none
    @endcapability
    """
    return frame == GEO_FRAME_LONLAT_DEG or frame == GEO_FRAME_LATLON_DEG


fn geo_frame_defect(frame: Int) -> Int:
    """`GEO_OK` for a known frame tag, else `GEO_ERR_FRAME`.

    A frame tag is not defaulted anywhere in this package. Defaulting it would mean
    guessing an axis order, which is the exact wrong answer the tag exists to prevent.
    
    @capability geo_frame_defect
    complexity: O(1)
    counts: none
    @endcapability
    """
    if frame < 0 or frame >= GEO_FRAME_COUNT:
        return GEO_ERR_FRAME
    return GEO_OK


fn geo_metric_defect(frame: Int, metric: Int) -> Int:
    """Whether `metric` is defined for coordinates in `frame`.

    This is where "refuse mixed units" is actually enforced. Handing degrees to a
    Euclidean metric yields a number in units of degrees that LOOKS like a distance, and
    handing projected metres to haversine treats an easting of 500000 as 500000 degrees of
    longitude. Both are refused with `GEO_ERR_UNIT_MISMATCH`; neither returns a plausible
    wrong distance.
    
    @capability geo_metric_defect
    complexity: O(1)
    counts: none
    @endcapability
    """
    var fd = geo_frame_defect(frame)
    if fd != GEO_OK:
        return fd
    if metric < 0 or metric >= GEO_METRIC_COUNT:
        return GEO_ERR_METRIC
    if geo_is_degree_frame(frame):
        if metric == GEO_METRIC_EUCLIDEAN:
            return GEO_ERR_UNIT_MISMATCH
        return GEO_OK
    if metric != GEO_METRIC_EUCLIDEAN:
        return GEO_ERR_UNIT_MISMATCH
    return GEO_OK


fn geo_lat_of(x: Float64, y: Float64, frame: Int) -> Float64:
    """The LATITUDE of a pair, given the frame. Returns 0.0 for a projected pair.

    Every latitude read in this package goes through here rather than through a local
    `if frame == ...`, so an axis order is decided in one place. A projected pair has no
    latitude and the caller must not be reading one; 0.0 is the representable slot and
    `geo_is_degree_frame` is the flag.
    
    @capability geo_lat_of
    complexity: O(1)
    counts: none
    @endcapability
    """
    if frame == GEO_FRAME_LONLAT_DEG:
        return y
    if frame == GEO_FRAME_LATLON_DEG:
        return x
    return 0.0


fn geo_lon_of(x: Float64, y: Float64, frame: Int) -> Float64:
    """The LONGITUDE of a pair, given the frame. Returns 0.0 for a projected pair.

    @capability geo_lon_of
    complexity: O(1)
    counts: none
    @endcapability
    """
    if frame == GEO_FRAME_LONLAT_DEG:
        return x
    if frame == GEO_FRAME_LATLON_DEG:
        return y
    return 0.0


fn geo_pair_range_defect(x: Float64, y: Float64, frame: Int) -> Int:
    """`GEO_OK` when both components are finite and inside their own slot's range.

    The range test is per-SLOT, not per-value: in `LONLAT_DEG` the legal band for `x` is
    +-180 and for `y` is +-90, and swapping them is what makes a swapped pair detectable.
    A projected pair has no angular band, so only finiteness is required — an easting is
    just a number.

    No tolerance is applied. +-90 and +-180 are exactly representable and a pole or the
    antimeridian itself is legal input; widening the band would admit a latitude of 90.5,
    which is not a latitude.
    
    @capability geo_pair_range_defect
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not geo_finite(x) or not geo_finite(y):
        return GEO_ERR_NON_FINITE
    if frame == GEO_FRAME_PLANE_M:
        return GEO_OK
    if frame == GEO_FRAME_LONLAT_DEG:
        if fabs(x) > GEO_MAX_LON_DEG or fabs(y) > GEO_MAX_LAT_DEG:
            return GEO_ERR_RANGE
        return GEO_OK
    if frame == GEO_FRAME_LATLON_DEG:
        if fabs(x) > GEO_MAX_LAT_DEG or fabs(y) > GEO_MAX_LON_DEG:
            return GEO_ERR_RANGE
        return GEO_OK
    return GEO_ERR_FRAME


fn geo_points_defect(
    xs: List[Float64], ys: List[Float64], n: Int, frame: Int, ceiling: Int
) -> Int:
    """The single gate every driver in this package calls before it indexes anything.

    Returns `GEO_OK` or the FIRST defect, checked in an order where each test only reads
    what its predecessors proved exists:

      1. the frame tag is known — otherwise the range test below has no meaning;
      2. `n >= 0` — a negative count reads nothing from `range`, but the same integer
         reaches subscript arithmetic downstream, and `a[-1]` is an uncatchable abort;
      3. `n <= ceiling` — the per-entry-point resource bound, tighter than the array
         lengths and independent of them;
      4. `n <= len(xs)` AND `n <= len(ys)` — the bound whose absence kills the worker;
      5. every one of the first `n` pairs is finite and in range.

    Step 4 is why every `counts:` block in this package is `[kernel_validated]` rather
    than `[enforced]`: the check really is here, so the pre-call guard must not replace a
    typed `GEO_ERR_COUNT` with a generic refusal. Declaring `[kernel_validated]` and NOT
    writing the check would tell the guard to stand down over a hole, which is strictly
    worse than declaring nothing.

    @capability geo_points_defect
    complexity: O(n)
    counts:
    - n <= len(xs, ys) [kernel_validated]
    @endcapability
    """
    var fd = geo_frame_defect(frame)
    if fd != GEO_OK:
        return fd
    if n < 0:
        return GEO_ERR_COUNT
    if ceiling < 0:
        return GEO_ERR_PARAM
    if n > ceiling:
        return GEO_ERR_TOO_LARGE
    if n > len(xs) or n > len(ys):
        return GEO_ERR_COUNT
    for i in range(n):
        var d = geo_pair_range_defect(xs[i], ys[i], frame)
        if d != GEO_OK:
            return d
    return GEO_OK


fn geo_normalise_lon(lon: Float64) -> Float64:
    """A longitude folded into [-180, 180]. Non-finite in, `0.0` out.

    Written as a bounded loop rather than `lon - 360 * floor((lon + 180) / 360)` because
    the closed form routes through `floor` of a quotient and returns exactly 180.0 or
    -180.0 depending on rounding at the seam, and the seam is where every antimeridian
    bug lives. The loop is exact for any finite input a validated coordinate can hold
    (at most a couple of turns) and the cap makes it total for the rest.
    
    @capability geo_normalise_lon
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not geo_finite(lon):
        return 0.0
    var out = lon
    var guard = 0
    while out > 180.0 and guard < 64:
        out -= 360.0
        guard += 1
    while out < -180.0 and guard < 64:
        out += 360.0
        guard += 1
    return out


fn geo_lon_delta(from_lon: Float64, to_lon: Float64) -> Float64:
    """The SHORTEST signed longitude step from one meridian to another, in (-180, 180].

    A ring stored as raw longitudes cannot say whether 179 -> -179 is a 2-degree step east
    or a 358-degree step west. This package's convention is the shortest step, which is
    what makes the pole test below a total function; the ANTIMERIDIAN test in
    `frame.frame_ring_census_flat` is the separate question of whether that shortest step
    crosses the seam, and it is answered from the raw values.
    
    @capability geo_lon_delta
    complexity: O(1)
    counts: none
    @endcapability
    """
    return geo_normalise_lon(to_lon - from_lon)


fn geo_m_per_deg_lon_lower(lat_a_deg: Float64, lat_b_deg: Float64) -> Float64:
    """A LOWER bound on metres per degree of longitude anywhere in [lat_a, lat_b].

    Metres per degree of longitude is `GEO_M_PER_DEG * cos(lat)`, which is largest at the
    equator and falls to zero at a pole. A search that expands outward in DEGREES needs a
    lower bound to convert a degree gap into a metre gap it can compare against a metre
    radius, so the bound uses the LARGEST |latitude| in the band.

    This is a bound, not a tolerance, and the distinction matters: rule 4b forbids sizing
    a per-item comparison by an aggregate over other items, and this is not one — it is
    a conservative floor over an interval, and being conservative can only cause MORE
    candidates to be examined, never a neighbour to be missed. A band that reaches a pole
    gives 0.0, which correctly degrades an expanding search to a full scan.
    
    @capability geo_m_per_deg_lon_lower
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not geo_finite(lat_a_deg) or not geo_finite(lat_b_deg):
        return 0.0
    var worst = fabs(lat_a_deg)
    if fabs(lat_b_deg) > worst:
        worst = fabs(lat_b_deg)
    if worst >= GEO_MAX_LAT_DEG:
        return 0.0
    var c = cos(worst * GEO_PI / 180.0)
    if c < 0.0:
        return 0.0
    return GEO_M_PER_DEG * c


fn geo_gap_lower_m(
    gap_coord: Float64, frame: Int, lat_a_deg: Float64, lat_b_deg: Float64
) -> Float64:
    """A RIGOROUS lower bound, in metres, on the distance between two points whose
    coordinates differ by at least `gap_coord` on at least one axis, both inside the
    latitude band [`lat_a_deg`, `lat_b_deg`].

    This is the stopping rule behind `index.grid_knn_flat`'s exactness claim, so "rigorous"
    has to mean provable and not merely plausible. `PLANE_M` is trivial: a Chebyshev gap of
    `g` metres IS at least `g` metres of Euclidean distance.

    The degree case is the one that needs care, and the OBVIOUS bound is wrong. Scaling the
    gap by `GEO_M_PER_DEG * cos(latmax)` — metres per degree of longitude at the worst
    latitude in the band — over-estimates, because a parallel is not a great circle: two
    points at latitude 60 with a longitude gap of 48 degrees are 0.4095 R apart, while
    `48 deg * cos(60)` is 0.4189 R. A "lower bound" larger than the value it bounds stops the
    search early and DROPS a nearer neighbour, which is the exactness claim silently failing.

    The bound used instead comes straight out of the haversine identity the frozen
    `geodesy.haversine_distance` computes,

        sin^2(sigma/2) = sin^2(dlat/2) + cos(lat1) cos(lat2) sin^2(dlon/2)

    by keeping only the term the gap is realised in:

      * realised in LATITUDE: sigma >= |dlat| (drop the non-negative longitude term);
      * realised in LONGITUDE: sin(sigma/2) >= cos(latmax) sin(|dlon|/2) because
        cos(lat) >= cos(latmax) >= 0 throughout the band, and sigma >= 2 sin(sigma/2)
        because sin(t) <= t. So sigma >= 2 cos(latmax) sin(|dlon|/2).

    The longitude form is never larger than the latitude form (`2 sin(a/2) <= a`), so it is
    the bound for both cases and no case analysis survives into the code.

    `gap_coord` is a RAW coordinate difference, and a raw longitude difference of 350 degrees
    is a real separation of 10, so the gap is folded to `min(gap, 360 - gap)` first.
    Forgetting that would over-estimate by a factor of 35 near the seam.

    Zero for a non-finite or non-positive gap, and zero when the band reaches a pole — which
    turns an expanding search into a full scan and stays exact, because a bound of zero never
    stops anything.
    
    @capability geo_gap_lower_m
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not geo_finite(gap_coord) or gap_coord <= 0.0:
        return 0.0
    if frame == GEO_FRAME_PLANE_M:
        return gap_coord
    if not geo_is_degree_frame(frame):
        return 0.0
    if not geo_finite(lat_a_deg) or not geo_finite(lat_b_deg):
        return 0.0
    var worst = fabs(lat_a_deg)
    if fabs(lat_b_deg) > worst:
        worst = fabs(lat_b_deg)
    if worst >= GEO_MAX_LAT_DEG:
        return 0.0
    var gap = gap_coord
    if gap > 360.0:
        return 0.0
    if gap > 180.0:
        gap = 360.0 - gap
    var c = cos(worst * GEO_PI / 180.0)
    if c <= 0.0:
        return 0.0
    var half = sin(gap * GEO_PI / 360.0)
    if half <= 0.0:
        return 0.0
    # The identity above is exact in real arithmetic; `sin` and `cos` are not. `std.math`'s
    # transcendentals are not correctly rounded in this toolchain, so the product carries a
    # small relative error of unknown sign, and a bound that is too LARGE by even one ulp is
    # a bound that can stop a search early. `GEO_BOUND_SLACK` is relative to the bound's own
    # magnitude — not to a sum, a maximum, or a caller's tolerance — and shrinking a
    # conservative bound can only cost candidates.
    var out = 2.0 * GEO_EARTH_RADIUS_M * c * half * (1.0 - GEO_BOUND_SLACK)
    if not geo_finite(out) or out < 0.0:
        return 0.0
    return out


fn geo_degree_box_half(radius_m: Float64, lat_deg: Float64) -> Float64:
    """Half-width in DEGREES OF LONGITUDE that certainly covers `radius_m` at this latitude.

    The one definition in the package, called by `join` and by `mapmatch`, because a search
    box computed two ways at two strengths is rule 3's duplicated guard: it reads as
    defence-in-depth and provides one arbitrary behaviour per call site.

    Metres per degree of longitude shrinks as cos(latitude), so converting a metre radius into
    degrees means DIVIDING by the SMALLEST factor the disc can reach — which yields the
    largest, and therefore safe, half-width. The band used is the disc's own latitude reach,
    `|lat| + radius / GEO_M_PER_DEG`, not an aggregate over the dataset: rule 4b's per-item
    requirement applies to a bound as much as to a tolerance, and a dataset-wide cosine would
    size one point's box from another point's latitude.

    A disc that reaches a pole returns the full 180 degrees, which degrades an indexed search
    to a full scan and stays correct. Conservative in the only safe direction: a box that is
    too LARGE costs candidates, a box that is too small silently drops pairs.
    
    @capability geo_degree_box_half
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not geo_finite(radius_m) or radius_m < 0.0 or not geo_finite(lat_deg):
        return GEO_MAX_LON_DEG
    var lat_reach = fabs(lat_deg) + radius_m / GEO_M_PER_DEG
    if lat_reach >= GEO_MAX_LAT_DEG:
        return GEO_MAX_LON_DEG
    var factor = geo_m_per_deg_lon_lower(lat_reach, lat_reach)
    if factor <= 0.0:
        return GEO_MAX_LON_DEG
    var half = radius_m / factor
    if not geo_finite(half) or half > GEO_MAX_LON_DEG:
        return GEO_MAX_LON_DEG
    return half


fn geo_offsets_defect(offsets: List[Int], n_groups: Int, n_items: Int, ceiling: Int) -> Int:
    """Whether a CSR-style group-offsets array is sound: `n_groups + 1` monotone entries.

    Rings in a multipolygon and polylines in a network both arrive as one flat coordinate
    pair of arrays plus an offsets array, exactly as a CSR row pointer: group `g` occupies
    `[offsets[g], offsets[g+1])`. That layout is only safe if the array is the right
    length, starts at zero, never decreases and ends inside the coordinate arrays — the
    same four conditions `sparse_numerics.csr.csr_validate_flat` checks, for the same
    reason: an unchecked `for k in range(offsets[g], offsets[g+1])` reads past the end and
    kills the process.

    Monotonicity plus a zero head plus a tail at most `n_items` bounds EVERY entry to
    `[0, n_items]`, so no separate per-entry range check is needed.

    @capability geo_offsets_defect
    complexity: O(n_groups)
    counts:
    - n_groups + 1 == len(offsets) [kernel_validated]
    @endcapability
    """
    if n_groups < 0 or n_items < 0:
        return GEO_ERR_PARAM
    if ceiling < 0:
        return GEO_ERR_PARAM
    if n_groups > ceiling:
        return GEO_ERR_TOO_LARGE
    if len(offsets) != n_groups + 1:
        return GEO_ERR_OFFSETS
    if offsets[0] != 0:
        return GEO_ERR_OFFSETS
    for g in range(1, n_groups + 1):
        if offsets[g] < offsets[g - 1]:
            return GEO_ERR_OFFSETS
    if offsets[n_groups] > n_items:
        return GEO_ERR_OFFSETS
    return GEO_OK


fn geo_cells_fit(rows: Int, cols: Int, ceiling: Int) -> Bool:
    """True when `rows * cols` is a sane cell count at or below `ceiling`.

    Written with a DIVISION, following `sparse_numerics.csr.dims_fit`, because
    `rows * cols` is a WRAPPING 64-bit multiply and therefore not a bound at all:

        3 * 6148914691236517206  ==  2

    so a `rows * cols <= ceiling` test passes for a request that then allocates and
    indexes as if it had 6.1e18 columns. Every product this package forms — route-matrix
    cells, grid cells, DP width — is admitted through here first.
    
    @capability geo_cells_fit
    complexity: O(1)
    counts: none
    @endcapability
    """
    if rows < 0 or cols < 0 or ceiling < 0:
        return False
    if rows == 0 or cols == 0:
        return True
    if rows > ceiling // cols:
        return False
    return rows * cols <= ceiling
