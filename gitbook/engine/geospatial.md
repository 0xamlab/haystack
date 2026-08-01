---
icon: map-location-dot
description: A spatial index with a measured selectivity, a three-valued point-in-polygon with no epsilon, coordinate frames that refuse a swapped latitude, and joins
---

# Geospatial indexing & joins

Six kernel modules for indexing points, deciding what is inside a polygon, joining two
datasets by distance, building route matrices and matching a GPS track to a road network. They
run as compiled kernels inside the runtime that ships with the SDK — there is nothing to start
and nothing to install separately.

The distinguishing property of this package is that it refuses. Geospatial code is unusually
good at returning a plausible number for the wrong place, and every refusal below exists
because the alternative is a wrong answer nobody notices:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Tokyo, written longitude-first (GeoJSON order) but tagged as latitude-first.
# Frame 1 means "x is latitude". A longitude of 139.65 is not a latitude.
out = runtime.execute(
    "geospatial.contract", "geo_pair_range_defect",
    [139.6503, 35.6762, 1],
)["result"]

out    # 709 — coordinate_outside_frame_range
```

No distance came back, because there is no honest distance to return.

## The modules

| Module | What it does |
| --- | --- |
| `geospatial.contract` | the package's one status vocabulary, its three coordinate frames and their axis orders, its three metrics and which frames each is defined for, and the non-wrapping work budget every other module charges against |
| `geospatial.frame` | what a batch of coordinates *is* before anything is computed from it — range per axis, order ambiguity, antimeridian crossing, pole encirclement, extent — plus distance in metres between two frame-tagged points and projection onto a local metre plane |
| `geospatial.polygon` | a three-valued point-in-polygon (inside, outside, or exactly on the boundary), ring orientation and signed area, simplicity and convexity, area in square metres, and convex-clip intersection |
| `geospatial.index` | the spatial index: a uniform cell grid, window queries that report the candidates they examined beside the cost of a full scan, and exact k-nearest neighbours |
| `geospatial.join` | joins within a radius, joins of points into the rings of a multipolygon, crow-flies route matrices and travel matrices over a directed road network |
| `geospatial.mapmatch` | the clamped distance from a point to a road *segment*, and a whole GPS track matched onto a polyline network by dynamic programming |

## Coordinates carry their frame, so a swapped axis cannot be silent

Latitude and longitude reversed is the classic geospatial wrong answer: it returns a
believable distance to a different place. Every function that consumes coordinates takes a
frame tag, and there are three:

| Frame | `x` is | `y` is |
| --- | --- | --- |
| `0` — lonlat degrees | longitude | latitude |
| `1` — latlon degrees | latitude | longitude |
| `2` — plane metres | easting | northing |

Three things follow, in order of strength.

**A distance between two points takes two frame tags and refuses a mismatch.** A longitude and
a projected easting cannot combine into a number at all:

```python
# London Heathrow in lonlat degrees against a projected easting/northing.
d = runtime.execute(
    "geospatial.frame", "frame_distance_flat",
    [-0.4543, 51.47, 0,      # first point, frame 0
     500000.0, 4649776.0, 2, # second point, frame 2
     0],                     # metric 0 = haversine
)["result"]

d["status"]        # 706 — operands_in_different_frames
d["has_distance"]  # False
d["distance_m"]    # 0.0 — a representable placeholder; has_distance is the answer
```

**Every coordinate is range-checked against its own axis.** In a lonlat frame the legal band
for `x` is ±180 and for `y` is ±90, so any swap in which the longitude exceeds 90 degrees in
magnitude is caught — most of the Americas, the Pacific, and all of Asia east of Kabul. The
poles and the antimeridian themselves are legal input, exactly: ±90 and ±180 are accepted and
90.5 is not, with no tolerance widening the band.

**The remaining case is reported, because it cannot be detected.** When every `x` and every
`y` in a batch is within ±90, the data parses identically in either axis order and no
validator can tell which was meant. `frame_census_flat` returns `order_ambiguous = True` for
exactly that case:

```python
lons = [0.0, 1.0, 1.0, 0.0]
lats = [0.0, 0.0, 1.0, 1.0]

census = runtime.execute(
    "geospatial.frame", "frame_census_flat", [lons, lats, 4, 0]
)["result"]

census["order_ambiguous"]  # True — both readings are consistent with this data
census["lon_span_deg"]     # 1.0
census["lat_span_deg"]     # 1.0
census["has_extent"]       # True
```

A silent guess there is how the wrong answer ships. A flag you can gate on is the truth.

Distances come back in **metres**, from every frame and every metric, so nothing downstream
has to remember a unit. Mixing a metric and a frame that do not belong together — a Euclidean
distance over degrees, or a great-circle distance over projected metres — is refused with
`metric_undefined_for_that_frame` rather than producing a number in units of degrees that
looks like a distance.

## Point-in-polygon is a numerical problem

A point strictly inside a polygon is easy. The cases that break implementations are the ones
on the boundary, and a function returning `True`/`False` cannot express them at all. This
package answers three-valued — **inside**, **outside**, or **exactly on the boundary** — and
decides by the sign of an orientation determinant rather than by comparing a division's result
against a coordinate:

```python
# The unit square, counter-clockwise.
xs = [0.0, 1.0, 1.0, 0.0]
ys = [0.0, 0.0, 1.0, 1.0]

# (0.5, 0.0) sits exactly on the horizontal bottom edge.
r = runtime.execute(
    "geospatial.polygon", "point_in_ring_flat",
    [0.5, 0.0, xs, ys, 4, 2],
)["result"]

r["classification"]  # 2 — on the boundary (0 outside, 1 inside)
r["on_boundary"]     # True
r["boundary_edge"]   # 0 — the edge it lies on
```

Five degeneracies, and the decision for each:

| Case | Answer |
| --- | --- |
| strictly inside or outside | crossing parity, from determinant signs, with no division anywhere |
| exactly on an edge's interior | on the boundary — detected in its own pass, before any crossing is counted |
| exactly on a vertex | on the boundary, by the same rule, with no special case |
| on a **horizontal** edge — which a crossing rule cannot decide at all | on the boundary |
| the ray passing exactly **through a vertex** | the crossing rule is half-open in `y`, so each vertex belongs to exactly one of its two edges and a grazed vertex contributes 0 or 2 crossings, never 1 |

**There is no epsilon.** A point 1e-18 from an edge but not exactly on it is classified inside
or outside, deterministically. That is a decision, not an oversight: the width of a tolerance
band is a number you never chose, it makes the predicate non-transitive, and it makes the
answer depend on how far your coordinates are from the origin. If you need a band, buffer the
ring — that is a modelling choice, and it has a unit.

Two membership rules come back, because they disagree and the difference is real.
`inside_even_odd` is crossing parity and `inside_nonzero` is a non-zero winding number. They
agree on every simple ring and differ exactly on self-intersecting ones, where a crossed lobe
is "in" under one rule and "out" under the other. `ring_report_flat` tells you whether the
ring is simple at all, so you know which case you are in.

## The antimeridian and the poles are answered or refused, never guessed

A ring stored as raw longitudes cannot say whether the step 179 → −179 is two degrees east or
358 degrees west. So:

* An edge whose raw longitude difference is 180 degrees or more has no unambiguous shortest
  connection. Every planar operation refuses such a ring with
  `geometry_crosses_the_antimeridian`. Splitting it at ±180 is your decision, because which
  side each part belongs to is knowledge the kernel does not have.
* A ring whose shortest longitude steps sum to ±360 encircles a pole, and its boundary does
  not separate the longitude/latitude plane the way the planar algorithms need. That is
  `geometry_encircles_a_pole`, and it is reported ahead of the seam because splitting at ±180
  cannot fix it.
* A vertex *at* a pole is reported and not refused. The ring is still a valid planar ring; it
  is the metre scale that degenerates there, and the census says so.

A window query whose longitude range is inverted is how you spell a window that wraps the
seam, so it is refused with the antimeridian status rather than quietly returning the box's
complement — which is nothing.

## Area in square metres, and it says how it got there

An area in square degrees is not an area. For a degree frame, `ring_area_flat` carries the ring
onto a local metre plane about the centre of its own extent and returns m², with the reference
parallel and both spans so you can bound the projection's distortion:

```python
# A one-degree box with corners at (0, 0) and (1, 1).
area = runtime.execute(
    "geospatial.polygon", "ring_area_flat", [lons, lats, 4, 0]
)["result"]

area["area_m2"]      # 12363840916.385 — about 12 364 km2
area["projected"]    # True
area["ref_lat_deg"]  # 0.5 — east-west scale is exact only here
area["lat_span_deg"] # 1.0
area["orientation"]  # 1 — counter-clockwise
```

East-west scale is exact only at the reference parallel and shrinks away from it, which is why
the parallel and the spans travel with the answer. A ring already in metres is measured as
given, with `projected = False`.

Ring **orientation** is the other thing here that no plain area gives you: `+1` for
counter-clockwise, `−1` for clockwise, `0` for a degenerate ring. That sign is what
distinguishes an outer ring from a hole.

## Clipping is convex-clip only, and "convex" is checked properly

`ring_intersect_convex_flat` intersects any subject ring with a **convex** clip ring. The
algorithm is only correct for a convex clip, so a clip that is not convex is refused with
`clip_polygon_is_not_convex` instead of being clipped into a polygon that looks reasonable and
is wrong. Your subject ring may be any shape.

Convexity is checked as two things, because either one alone is not convexity. Every corner must
turn the same way, **and** the ring must not cross itself. A five-pointed star turns the same way
at all five points and is obviously not convex: under a corner-only test it would be accepted and
you would get back the intersection of the star's five edge lines — the small pentagon in its
middle — with a success status and no hint that it is not what you asked for. That input is
refused.

Checking that a ring does not cross itself costs work proportional to the square of its vertex
count, so it is affordable up to 2 048 vertices for the clip ring. A larger clip ring is refused
with `declared_work_budget_exceeded`: at that size the question cannot be answered inside the
budget, and "not checked" is not the same as "checked and fine". Simplify the clip, or clip in
pieces.

## The index reports its own selectivity

An index is only worth having if it examines less than everything, so every query returns the
number of candidates it examined beside the cost of a full scan. You do not have to take the
claim on trust — you measure it on your own data:

```python
lons = [...]   # your points
lats = [...]

grid = runtime.execute(
    "geospatial.index", "grid_build_flat",
    [lons, lats, len(lons), 2, 4],   # frame 2 = plane metres, ~4 points per cell
)["result"]

win = runtime.execute(
    "geospatial.index", "grid_window_flat",
    [grid["cell_start"], grid["cell_items"], lons, lats, len(lons), grid["side"],
     grid["min_x"], grid["min_y"], grid["cell_w"], grid["cell_h"],
     495.0, 495.0, 505.0, 505.0, 2],
)["result"]

win["n_found"]              # the points in the box
win["candidates_examined"]  # what it actually looked at
win["cells_examined"]       # the index cells the box covered
win["full_scan_cost"]       # what looking at everything would have cost
win["selectivity"]          # the ratio
```

The set is the one a full scan would return — including points lying exactly on the edge of your
data's own bounding box, which is the boundary case a grid is easiest to get wrong on. You do
not have to take that on trust either: `window_scan_flat` is a first-class function, not
benchmark scaffolding, so you can put the same box through both and compare on your own data.

Both costs come back because both are real. A box covering many cells that hold nothing still
costs the cells it read, so a wide radius over clustered data can be almost entirely cell cost
with no candidates at all — `cells_examined` is that number, and the kernel charges it against
its own work ceiling rather than treating an empty cell as free.

The index is a uniform cell grid whose resolution scales with the point count, and the
consequence that matters is that its advantage **grows** with your data: at a fixed query area
over a fixed extent, the fraction of the dataset examined falls as the dataset gets denser. On
a 1000 × 1000 m extent with a 10 × 10 m window, that fraction goes from 1.6% at 1 024 points
to 0.025% at 65 536 — a 64× improvement in the ratio while the data grew 64× — and the work
per query stays at 16 candidates across 4 cells throughout.

What the grid gives up is stated rather than hidden. Cells are uniform, so extreme clustering
puts many points in one bucket and a query over the dense region degrades towards a full scan.
`max_cell_occupancy` reports exactly that, and the points-per-cell target is your lever.

**k-nearest neighbours are exact**, not approximate. The search expands rings of cells outward
and stops only when the nearest possible point in the next ring is provably farther than the
k-th neighbour already found. The candidate count is set by `k` and the local density rather
than by your dataset size: at `k = 8` it stays near 38 candidates per query whether the dataset
holds 1 024 points or 65 536. Where that stopping proof does not hold — a request for
ellipsoidal geodesic distances, whose bound cannot be derived on the sphere the proof uses —
the indexed entry point refuses with `metric_not_supported_by_this_entry_point` rather than
returning an answer labelled exact. The linear scan serves that metric instead, and says so.

An index over **zero** points is a legitimate thing to query — filters produce empty sets — and
asking it for a neighbour answers "there are none": status `ok`, `k_returned` of 0, and
`has_max_distance` False so the zero in the distance slot cannot be read as "zero metres away".

## Joins, and a truncated join is never labelled complete

`join_within_flat` indexes one side once and probes it with each point on the other side, so it
never forms the full cross product. Pairs come back ordered by left id then right id — a total
order, so the result does not depend on the index's internal resolution:

```python
j = runtime.execute(
    "geospatial.join", "join_within_flat",
    [left_x, left_y, len(left_x),
     right_x, right_y, len(right_x),
     100.0,      # radius in metres
     2, 2,       # frame 2 (plane metres), metric 2 (euclidean)
     100000],    # the most pairs you will accept
)["result"]

j["status"]              # 700 ok, or 701 if the budget was reached
j["truncated"]           # the same fact as a flag
j["n_pairs"]
j["candidates_examined"] # against j["full_scan_cost"]
j["cells_examined"]      # the index cells the search boxes covered
```

Reaching either budget — yours or the kernel's — returns
`ok_partial_budget_reached` and never plain `ok`. A partial join reported as a success is
indistinguishable from a complete one, and the caller who stops looking is the failure this
package exists to prevent.

The kernel's budget counts **both** costs, the candidates compared and the index cells read.
That matters for one shape in particular: a large radius over data clustered in part of its
extent gives every search box thousands of cells that hold nothing, so the join can be almost
pure cell cost with `candidates_examined` at zero. Counting only candidates would price such a
request at nothing and let it run for minutes; counting both stops it at the ceiling and says so
with `ok_partial_budget_reached`. A radius of zero is a legitimate request too — it matches
exactly coincident points, so a zero-radius self-join pairs every point with itself.

`join_point_in_rings_flat` assigns points to the rings of a multipolygon, with two decisions
you should know about. A point on an edge **shared** by two adjacent rings — which every tiling
has — goes to the lower-indexed ring and is reported as on the boundary rather than promoted to
interior, and `n_multi` counts the points more than one ring claimed so overlaps stay visible.
A ring that is not admissible as a planar ring is skipped and counted in `rings_refused`, so
one broken ring out of a thousand does not make the useful answer unreachable, and you can
still tell that something was dropped.

## Two kinds of route matrix, kept apart

`route_matrix_flat` is the crow-flies matrix — a lower bound on travel distance. It is not a
travel matrix and is not named as if it were.

`network_route_matrix_flat` is the travel matrix: node coordinates plus a directed edge list,
where each edge's length is the distance between its own endpoints, so the graph and the
geometry cannot disagree. A pair with no path is reported **absent** — `reachable` is `False`
and the distance slot is `0.0` — rather than as a very large number that no caller can tell
from a real distance and that will happily be added to a budget:

```python
# Nodes 0(0,0) 1(3,0) 2(3,4) 3(100,100); edges 0->1 and 1->2. Node 3 is isolated.
net = runtime.execute(
    "geospatial.join", "network_route_matrix_flat",
    [[0.0, 3.0, 3.0, 100.0], [0.0, 0.0, 4.0, 100.0], 4,
     [0, 1], [1, 2], 2,
     [0], 1, [1, 2, 3], 3, 2, 2],
)["result"]

net["distance_m"]     # [3.0, 7.0, 0.0]
net["reachable"]      # [True, True, False]
net["n_unreachable"]  # 1
```

`0 -> 2` is 7 metres, the sum of the two legs, and not the 5-metre straight line. The `0.0` in
the third slot means nothing at all; `reachable[2] = False` is the answer.

## Map matching clamps to the segment, which is the whole difficulty

The distance from a point to the infinite line through a road segment's endpoints is not the
distance to the road. Used unclamped it reports a vehicle 20 km past the end of a street as
being three metres from it, which is how a matcher snaps a track to a road it never touched:

```python
# The segment (0,0) -> (10,0) and a query 10 m past its end, 3 m off the line.
seg = runtime.execute(
    "geospatial.mapmatch", "point_to_segment_flat",
    [20.0, 3.0, 0.0, 0.0, 10.0, 0.0, 2, 2],
)["result"]

seg["distance_m"]  # 10.4403065089 — to the endpoint, not the 3.0 to the line
seg["where"]       # 2 — the foot fell past the end (0 interior, 1 start)
seg["foot_x"]      # 10.0
```

The clamp holds at every leg length, which is worth saying because the interesting case is not
the short one. On the sphere, a leg 120° of longitude long and a fix 40° past its end is
4 448 953 m from that road, and that is what comes back — not the 111 195 m to the infinite
great circle the leg lies on:

```python
# Leg (0°N, 0°E) -> (0°N, 120°E) on the equator; the fix is at (1°N, 160°E).
far = runtime.execute(
    "geospatial.mapmatch", "point_to_segment_flat",
    [160.0, 1.0, 0.0, 0.0, 120.0, 0.0, 0, 0],   # frame 0 = lon/lat degrees, metric 0 = sphere
)["result"]

far["distance_m"]  # 4448953.339962056 — the distance to the endpoint
far["where"]       # 2 — past the end
far["foot_x"]      # 120.0
```

Two limits are worth knowing. A leg whose endpoints are **exactly antipodal** lies on infinitely
many great circles, so it does not name a road at all and is refused rather than answered about
an arc you never chose. And for a leg on the sphere the reported leg *fraction* and foot are
resolved on the same sphere as the distance, so an interior fix two thirds of the way along a
150° leg reports `t_fraction` ≈ 0.667 rather than a folded 0.53.

`map_match_flat` matches a whole track by dynamic programming over the candidate segments near
each fix, balancing per-fix accuracy against continuity with a `beta` you choose in metres per
metre. `beta = 0` is nearest-segment matching per fix with no continuity at all; a larger
`beta` prefers a self-consistent path even when individual fixes then match further from their
nearest road.

A fix with **no** candidate road inside the search radius refuses the whole match with
`track_point_has_no_candidate_within_radius` and the index of the fix that caused it. Matching
the fixes that had candidates and leaving a hole would return a path the vehicle did not take,
with nothing in the result to say so. Widening the radius or splitting the track at the gap is
your call, and you are given the information to make it.

The transition term compares the straight-line step between two matched positions against the
step between the two fixes. The published measure uses the route distance through the network
instead, which needs a shortest path per candidate pair per step; the straight line is a lower
bound on it, and `network_route_matrix_flat` is where route distances live.

## Absence is never zero

Every quantity that might not exist is a flag plus a value slot, and when the flag is `False`
the slot is a representable `0.0` that means nothing:

* a one-fix track has **no** length — not a zero-metre journey, which downstream code reads as
  "did not move" rather than "cannot say";
* an empty batch has **no** bounding box, rather than a box at the origin;
* a ring with fewer than three vertices has **no** area, which is a different fact from three
  collinear vertices whose area genuinely is zero;
* a ring whose vertex count is above the self-intersection ceiling reports
  `simplicity_checked = False`, and `self_intersecting = False` then means "nothing was
  checked", not "the ring is simple".

Read the flag first. That is the whole convention, and it is why nothing here returns a number
it cannot stand behind.

## Statuses

Every function returns a status. The ones you are most likely to see:

| Status | Meaning |
| --- | --- |
| `ok` | complete answer |
| `ok_partial_budget_reached` | a real but **partial** answer; results are missing |
| `count_exceeds_coordinate_arrays` | a declared count is longer than the arrays supplied |
| `count_above_declared_ceiling` | the request is above the entry point's resource bound |
| `unknown_coordinate_frame` / `operands_in_different_frames` | the frame tag is unknown, or two operands are in different frames |
| `metric_undefined_for_that_frame` | degrees against a planar metric, or metres against a spherical one |
| `metric_not_supported_by_this_entry_point` | the metric is fine, but this entry point cannot serve it with the guarantee it advertises |
| `metric_undefined_for_this_pair_of_points` | the metric could not measure these two particular points; a different metric will |
| `coordinate_outside_frame_range` | a coordinate is outside its own axis's legal band |
| `geometry_crosses_the_antimeridian` / `geometry_encircles_a_pole` | the geometry cannot be treated as planar; split it or reproject |
| `ring_has_no_interior` | fewer than three vertices, so there is no inside |
| `clip_polygon_is_not_convex` | the clip region must be convex; the subject need not be |
| `query_window_inverted_or_wrapped` | the query box is inverted on an axis |
| `declared_work_budget_exceeded` | the request would cost more work than the kernel will spend |
| `track_point_has_no_candidate_within_radius` | a track fix has no road inside the search radius |
| `index_layout_unsound` / `offsets_array_unsound` | the index or grouping arrays supplied are not self-consistent |

## See also

* [Data Quality](data-quality.md) — validating coordinates before they reach an index
* [Sparse And Graph](sparse-and-graph.md) — shortest paths and centrality over a road network
* [Runtime Library Catalog](runtime-library-catalog.md) — every module and function
