"""
geospatial — spatial indexing and joins over the frozen cartography/geodesy/geometry family.

Zero Python imports. Nothing here recomputes a distance, a bearing, a projection or a
polygon area: those exist and are called. What is added is the four things the frozen
family does not have — a declared coordinate frame, a robust boundary convention, an index,
and end-to-end drivers.

What was already there, and what each module therefore does
-----------------------------------------------------------
`geodesy.mojo` has haversine and Vincenty distance, initial bearing, destination point,
midpoint, cross-track and along-track distance, geodetic <-> ECEF and rhumb distance.
`cartography.mojo` has Mercator and equirectangular projection, UTM zone, scale factors and
great-circle distance. `geometry.mojo` has a 2D `Point`, Euclidean distance, the 2D cross
product, ray-cast point-in-polygon, the shoelace area, perimeter, monotone-chain convex
hull, line intersection, centroid and bounding box. `topology.distance_matrix` has an
all-pairs Euclidean matrix and `optimization.routing.distance_matrix_check` censuses one.

So:

  contract — the status vocabulary (700-729, minted in ONE file), the three coordinate
             frames and their axis orders, the three metrics and which frames they are
             defined for, the count/offset/product guards, and the absence policy.
  frame    — what a batch of coordinates IS: range per slot, order ambiguity, antimeridian
             crossing, pole encirclement, extent. Plus the two drivers the frozen kernels
             lack: a frame-checked distance in metres, and an array projected to a local
             metre plane.
  polygon  — a ring report (orientation, signed area, simplicity, extent) and a THREE-valued
             point-in-polygon: inside, outside, or exactly on the boundary. Convex clipping
             for intersection and area.
  index    — the spatial index: a uniform equal-angle cell grid whose bucket layout is a
             frozen CSR, window queries with measured selectivity, and exact k-nearest with
             a stated lower bound.
  join     — spatial joins (radius, and point-in-ring) driven by that index, plus route
             matrices over the frozen metrics.
  mapmatch — a GPS track matched to a polyline network by dynamic programming over
             per-observation candidates, with the emission distance built from the frozen
             cross-track and along-track kernels.

Every public function takes and returns only `List[Float64]` / `List[Int]` / `Float64` /
`Int` / `Bool` / `String` or a struct declared in its own file, so the package lands in the
runtime library contract with no new message type and is not in `_SKIP_RUNTIME_DIRS`.
"""
