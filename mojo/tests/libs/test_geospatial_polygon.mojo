"""test_geospatial_polygon.mojo — known-value tests for point-in-polygon and ring geometry.

Hand-written. Every polygon here has vertices at exactly representable coordinates and an
answer a reader can verify on paper, because point-in-polygon is decided by the SIGN of an
orientation determinant and a sign is either right or wrong — there is nothing to be
approximately correct about.

The five degeneracies the module docstring enumerates each get an assertion, on shapes chosen
so the expected answer is not a matter of opinion:

1. *Strictly inside / outside.* The unit square (0,0) (1,0) (1,1) (0,1): (0.5, 0.5) is inside
   with exactly 1 crossing, (1.5, 0.5) is outside with 0.
2. *Exactly on an edge interior.* (0.0, 0.5) on the left edge, (1.0, 0.5) on the right.
3. *Exactly on a vertex.* (0,0) and (1,1).
4. *On a HORIZONTAL edge* — the case a crossing rule cannot decide at all, because a
   horizontal edge at the ray's own height has no crossing. (0.5, 0.0) and (0.5, 1.0).
5. *The ray passing exactly through a vertex.* The diamond (1,0) (2,1) (1,2) (0,1) with the
   query at (-1, 1): the ray y = 1 leaves the query and passes exactly through the vertices
   (0,1) AND (2,1). The half-open rule gives 2 crossings, so the parity is unchanged and the
   answer is OUTSIDE. One crossing there would be the classic wrong answer.

And the no-epsilon claim is asserted in both directions: (0.5, +1e-18) is INSIDE and
(0.5, -1e-18) is OUTSIDE, deterministically, because 1e-18 is not zero.

Areas are the FROZEN `geometry.polygon_area`. The unit square is 1.0 and the diamond
(1,0) (2,1) (1,2) (0,1) is 2.0 by the shoelace sum 1 + 3 + 1 - 1 = 4, halved. The 1x1 degree
box at the equator projects to 111 190.69268247242 m by 111 194.92664455873 m =
12 363 840 916.385195 m^2 — the product of two closed forms, evaluated in CPython.

The even-odd / non-zero disagreement is asserted on a square traversed TWICE, where the centre
has winding number 2 and crossing parity 0: "inside" under the winding rule, "outside" under
parity. Returning one of those silently would be picking a convention in the one case where it
matters.
"""
from std.math import abs as fabs, cos, sin

from geospatial.contract import (
    GEO_ERR_ANTIMERIDIAN,
    GEO_ERR_BUDGET,
    GEO_ERR_DEGENERATE_RING,
    GEO_ERR_NOT_CONVEX,
    GEO_ERR_POLE,
    GEO_ERR_RANGE,
    GEO_FRAME_LONLAT_DEG,
    GEO_FRAME_PLANE_M,
    GEO_MAX_SIMPLICITY_VERTICES,
    GEO_OK,
)
from geospatial.polygon import (
    GEO_ORIENT_CCW,
    GEO_ORIENT_CW,
    GEO_ORIENT_DEGENERATE,
    GEO_PIP_BOUNDARY,
    GEO_PIP_INSIDE,
    GEO_PIP_OUTSIDE,
    point_in_ring_flat,
    points_in_ring_flat,
    ring_area_flat,
    ring_intersect_convex_flat,
    ring_planar_defect_flat,
    ring_report_flat,
)

#: 111190.69268247242 * 111194.92664455873 — the metre area of a 1x1 degree box projected
#: about its own centre (0.5 N, 0.5 E). Evaluated in CPython from R*pi/180 and cos(0.5 deg).
comptime REF_DEG_BOX_M2: Float64 = 12363840916.385195


def _square() -> List[Float64]:
    """The unit square, counter-clockwise, as x0,y0,x1,y1,... — split by the caller."""
    var v = List[Float64]()
    v.append(0.0)
    v.append(1.0)
    v.append(1.0)
    v.append(0.0)
    return v^


def main() raises:
    var passed = 0
    var failed = 0
    print("[geospatial.polygon]")

    # ── the unit square, counter-clockwise ────────────────────────────────────
    var sx = List[Float64]()
    var sy = List[Float64]()
    sx.append(0.0)
    sy.append(0.0)
    sx.append(1.0)
    sy.append(0.0)
    sx.append(1.0)
    sy.append(1.0)
    sx.append(0.0)
    sy.append(1.0)

    var rep = ring_report_flat(sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        rep.status == GEO_OK
        and rep.has_area
        and rep.area == 1.0
        and rep.signed_area == 1.0
        and rep.orientation == GEO_ORIENT_CCW
        and rep.has_perimeter
        and rep.perimeter == 4.0
        and rep.is_convex
        and rep.simplicity_checked
        and not rep.self_intersecting
        and rep.duplicate_vertices == 0
        and not rep.explicitly_closed
    ):
        passed += 1
        print("  ✅ unit square: area 1.0, perimeter 4.0, counter-clockwise, simple, convex")
    else:
        failed += 1
        print("  ❌ unit square report wrong:", rep.area, rep.perimeter, rep.orientation)

    # The sign is the ONLY thing this module adds to the frozen area, and it says so by
    # reproducing the frozen kernel's magnitude EXACTLY rather than within a tolerance.
    if rep.magnitude_matches_frozen:
        passed += 1
        print("  ✅ |trapezoid sum| / 2 is bit-equal to the frozen geometry.polygon_area")
    else:
        failed += 1
        print("  ❌ the orientation sum does not match the frozen area accumulation")

    # Reversing the ring flips the orientation and the SIGNED area; the magnitude does not
    # move. That is what tells an outer ring from a hole, and no frozen kernel can say it.
    var rx = List[Float64]()
    var ry = List[Float64]()
    for i in range(4):
        rx.append(sx[3 - i])
        ry.append(sy[3 - i])
    var rrep = ring_report_flat(rx, ry, 4, GEO_FRAME_PLANE_M)
    if (
        rrep.orientation == GEO_ORIENT_CW
        and rrep.area == 1.0
        and rrep.signed_area == -1.0
    ):
        passed += 1
        print("  ✅ the reversed square is clockwise with signed area -1.0, magnitude 1.0")
    else:
        failed += 1
        print("  ❌ reversal did not flip the orientation:", rrep.orientation)

    # ── case 1: strictly inside and strictly outside ──────────────────────────
    var inside = point_in_ring_flat(0.5, 0.5, sx, sy, 4, GEO_FRAME_PLANE_M)
    var outside = point_in_ring_flat(1.5, 0.5, sx, sy, 4, GEO_FRAME_PLANE_M)
    var left_out = point_in_ring_flat(-0.5, 0.5, sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        inside.classification == GEO_PIP_INSIDE
        and inside.crossings == 1
        and inside.winding_number == 1
        and inside.inside_even_odd
        and inside.inside_nonzero
        and not inside.on_boundary
        and inside.boundary_edge == -1
        and outside.classification == GEO_PIP_OUTSIDE
        and outside.crossings == 0
        and outside.winding_number == 0
        # A point to the LEFT of the square is outside with TWO crossings, not zero: the
        # +x ray leaves it, enters through the left edge and leaves through the right one.
        # Parity, not a count, is what decides — and the winding cancels to 0.
        and left_out.classification == GEO_PIP_OUTSIDE
        and left_out.crossings == 2
        and left_out.winding_number == 0
    ):
        passed += 1
        print("  ✅ (0.5,0.5) inside, 1 crossing; right of it 0 crossings, left of it 2")
    else:
        failed += 1
        print("  ❌ interior/exterior wrong:", inside.crossings, outside.crossings)

    # ── case 2: exactly on an edge interior (vertical edges) ──────────────────
    var on_left = point_in_ring_flat(0.0, 0.5, sx, sy, 4, GEO_FRAME_PLANE_M)
    var on_right = point_in_ring_flat(1.0, 0.5, sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        on_left.classification == GEO_PIP_BOUNDARY
        and on_left.on_boundary
        and on_left.boundary_edge >= 0
        and on_right.classification == GEO_PIP_BOUNDARY
        and on_right.on_boundary
    ):
        passed += 1
        print("  ✅ (0.0,0.5) and (1.0,0.5) on the vertical edges are BOUNDARY, not a guess")
    else:
        failed += 1
        print("  ❌ an edge-interior point was not BOUNDARY:", on_left.classification)

    # ── case 3: exactly on a vertex ───────────────────────────────────────────
    var v00 = point_in_ring_flat(0.0, 0.0, sx, sy, 4, GEO_FRAME_PLANE_M)
    var v11 = point_in_ring_flat(1.0, 1.0, sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        v00.classification == GEO_PIP_BOUNDARY
        and v11.classification == GEO_PIP_BOUNDARY
        and v00.on_boundary
        and v11.on_boundary
    ):
        passed += 1
        print("  ✅ both corners (0,0) and (1,1) are BOUNDARY, with no vertex special case")
    else:
        failed += 1
        print("  ❌ a vertex was not BOUNDARY:", v00.classification, v11.classification)

    # ── case 4: on a HORIZONTAL edge — the crossing rule cannot decide this ───
    var on_bottom = point_in_ring_flat(0.5, 0.0, sx, sy, 4, GEO_FRAME_PLANE_M)
    var on_top = point_in_ring_flat(0.5, 1.0, sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        on_bottom.classification == GEO_PIP_BOUNDARY
        and on_bottom.boundary_edge == 0
        and on_top.classification == GEO_PIP_BOUNDARY
    ):
        passed += 1
        print("  ✅ (0.5,0.0) on the horizontal bottom edge is BOUNDARY, edge 0")
    else:
        failed += 1
        print("  ❌ a horizontal-edge point was decided by the crossing rule:", on_bottom.classification)

    # ── case 5: the ray passes exactly through TWO vertices ──────────────────
    # Diamond (1,0) (2,1) (1,2) (0,1). The ray y = 1 from (-1,1) hits the vertices (0,1) and
    # (2,1) exactly. Half-open in y => each vertex belongs to exactly one of its two edges,
    # so the count is 2 and the parity is unchanged: OUTSIDE. A naive rule counts 1 and says
    # INSIDE.
    var dx = List[Float64]()
    var dy = List[Float64]()
    dx.append(1.0)
    dy.append(0.0)
    dx.append(2.0)
    dy.append(1.0)
    dx.append(1.0)
    dy.append(2.0)
    dx.append(0.0)
    dy.append(1.0)
    var graze = point_in_ring_flat(-1.0, 1.0, dx, dy, 4, GEO_FRAME_PLANE_M)
    var d_in = point_in_ring_flat(1.0, 1.0, dx, dy, 4, GEO_FRAME_PLANE_M)
    if (
        graze.classification == GEO_PIP_OUTSIDE
        and graze.crossings == 2
        and graze.winding_number == 0
        and d_in.classification == GEO_PIP_INSIDE
        and d_in.crossings == 1
        and d_in.winding_number == 1
    ):
        passed += 1
        print("  ✅ a ray through two vertices counts 2 crossings, so OUTSIDE stays OUTSIDE")
    else:
        failed += 1
        print("  ❌ vertex-grazing ray miscounted:", graze.crossings, graze.classification)

    # The diamond's area is 2.0 by the shoelace 1 + 3 + 1 - 1 = 4, halved.
    var drep = ring_report_flat(dx, dy, 4, GEO_FRAME_PLANE_M)
    if drep.area == 2.0 and drep.orientation == GEO_ORIENT_CCW and drep.is_convex:
        passed += 1
        print("  ✅ the diamond's area is exactly 2.0 and it is convex")
    else:
        failed += 1
        print("  ❌ diamond area wrong:", drep.area)

    # ── no epsilon, in both directions ───────────────────────────────────────
    var just_in = point_in_ring_flat(0.5, 1.0e-18, sx, sy, 4, GEO_FRAME_PLANE_M)
    var just_out = point_in_ring_flat(0.5, -1.0e-18, sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        just_in.classification == GEO_PIP_INSIDE
        and just_out.classification == GEO_PIP_OUTSIDE
    ):
        passed += 1
        print("  ✅ 1e-18 above the edge is INSIDE and 1e-18 below is OUTSIDE — no band")
    else:
        failed += 1
        print("  ❌ an epsilon band crept in:", just_in.classification, just_out.classification)

    # ── even-odd and non-zero disagree, and both are reported ────────────────
    # The unit square traversed TWICE. The centre has winding 2 (inside by the winding rule)
    # and 2 crossings (outside by parity). Neither is "the" answer, so both come back.
    var tx = List[Float64]()
    var ty = List[Float64]()
    for _ in range(2):
        for i in range(4):
            tx.append(sx[i])
            ty.append(sy[i])
    var twice = point_in_ring_flat(0.5, 0.5, tx, ty, 8, GEO_FRAME_PLANE_M)
    if (
        twice.status == GEO_OK
        and twice.winding_number == 2
        and twice.crossings == 2
        and not twice.inside_even_odd
        and twice.inside_nonzero
        and twice.classification == GEO_PIP_OUTSIDE
    ):
        passed += 1
        print("  ✅ a doubly-wound square: parity says outside, winding 2 says inside; both")
    else:
        failed += 1
        print("  ❌ the two membership rules did not disagree:", twice.crossings, twice.winding_number)

    var trep = ring_report_flat(tx, ty, 8, GEO_FRAME_PLANE_M)
    if trep.simplicity_checked and trep.self_intersecting and trep.bad_edge_a >= 0:
        passed += 1
        print("  ✅ and the ring is reported self-intersecting, naming the first bad edge")
    else:
        failed += 1
        print("  ❌ a doubled ring was not flagged self-intersecting")

    # ── "no area" is not "zero area" ─────────────────────────────────────────
    # Two vertices cannot bound anything: has_area False. Three COLLINEAR vertices bound a
    # genuine zero: has_area True with a DEGENERATE orientation. A caller branches differently.
    var two_x = List[Float64]()
    var two_y = List[Float64]()
    two_x.append(0.0)
    two_y.append(0.0)
    two_x.append(1.0)
    two_y.append(1.0)
    var r2 = ring_report_flat(two_x, two_y, 2, GEO_FRAME_PLANE_M)
    var col_x = List[Float64]()
    var col_y = List[Float64]()
    col_x.append(0.0)
    col_y.append(0.0)
    col_x.append(1.0)
    col_y.append(0.0)
    col_x.append(2.0)
    col_y.append(0.0)
    var rc = ring_report_flat(col_x, col_y, 3, GEO_FRAME_PLANE_M)
    if (
        not r2.has_area
        and r2.area == 0.0
        and r2.has_perimeter
        and rc.has_area
        and rc.area == 0.0
        and rc.orientation == GEO_ORIENT_DEGENERATE
    ):
        passed += 1
        print("  ✅ 2 vertices have NO area; 3 collinear ones have an area that IS zero")
    else:
        failed += 1
        print("  ❌ absence and zero were conflated:", r2.has_area, rc.has_area)

    # Three collinear vertices walked monotonically are NOT a spike, so not self-intersecting.
    if rc.simplicity_checked and not rc.self_intersecting:
        passed += 1
        print("  ✅ a monotone collinear triple is simple, not a spike")
    else:
        failed += 1
        print("  ❌ a collinear triple was called self-intersecting")

    # A ring with fewer than 3 vertices has no interior, and says so with its own status
    # rather than answering "outside" as though the question made sense.
    var deg = point_in_ring_flat(5.0, 5.0, two_x, two_y, 2, GEO_FRAME_PLANE_M)
    if deg.status == GEO_ERR_DEGENERATE_RING and deg.classification == GEO_PIP_OUTSIDE:
        passed += 1
        print("  ✅ a 2-vertex ring returns GEO_ERR_DEGENERATE_RING, not a bare 'outside'")
    else:
        failed += 1
        print("  ❌ a degenerate ring answered as if it had an interior:", deg.status)

    # A point ON a 2-vertex ring is still on it — reported BOUNDARY with the degenerate status.
    var on_deg = point_in_ring_flat(0.5, 0.5, two_x, two_y, 2, GEO_FRAME_PLANE_M)
    if on_deg.classification == GEO_PIP_BOUNDARY and on_deg.status == GEO_ERR_DEGENERATE_RING:
        passed += 1
        print("  ✅ a point on a 2-vertex ring is BOUNDARY and the status still says degenerate")
    else:
        failed += 1
        print("  ❌ a point on a segment was lost:", on_deg.classification)

    # ── the count guard, on the ring's own vertices ──────────────────────────
    var over = point_in_ring_flat(0.5, 0.5, sx, sy, 9, GEO_FRAME_PLANE_M)
    var neg = point_in_ring_flat(0.5, 0.5, sx, sy, -1, GEO_FRAME_PLANE_M)
    if over.status != GEO_OK and neg.status != GEO_OK:
        passed += 1
        print("  ✅ n=9 and n=-1 over a 4-vertex ring both refuse; the process is alive")
    else:
        failed += 1
        print("  ❌ the vertex count guard let something through")

    # A query point outside its own slot's range is refused before any geometry runs.
    var bad_q = point_in_ring_flat(0.0, 95.0, sx, sy, 4, GEO_FRAME_LONLAT_DEG)
    if bad_q.status == GEO_ERR_RANGE:
        passed += 1
        print("  ✅ a query point at latitude 95 is refused, not folded")
    else:
        failed += 1
        print("  ❌ an out-of-range query point was accepted:", bad_q.status)

    # ── seam and pole rings are refused, each with its own code ──────────────
    # A box across the antimeridian: 179 -> -179 has no unambiguous shortest connection.
    var ax = List[Float64]()
    var ay = List[Float64]()
    ax.append(179.0)
    ay.append(0.0)
    ax.append(-179.0)
    ay.append(0.0)
    ax.append(-179.0)
    ay.append(1.0)
    ax.append(179.0)
    ay.append(1.0)
    # A ring encircling the north pole. It necessarily ALSO has a seam edge, which is why the
    # pole test runs first: otherwise GEO_ERR_POLE would be unreachable and the caller would
    # be told to split at the seam, which cannot fix a pole encirclement.
    var wx = List[Float64]()
    var wy = List[Float64]()
    wx.append(0.0)
    wy.append(80.0)
    wx.append(90.0)
    wy.append(80.0)
    wx.append(180.0)
    wy.append(80.0)
    wx.append(-90.0)
    wy.append(80.0)
    if (
        ring_planar_defect_flat(ax, ay, 4, GEO_FRAME_LONLAT_DEG) == GEO_ERR_ANTIMERIDIAN
        and ring_planar_defect_flat(wx, wy, 4, GEO_FRAME_LONLAT_DEG) == GEO_ERR_POLE
        and ring_planar_defect_flat(sx, sy, 4, GEO_FRAME_LONLAT_DEG) == GEO_OK
        and ring_planar_defect_flat(ax, ay, 4, GEO_FRAME_PLANE_M) == GEO_OK
    ):
        passed += 1
        print("  ✅ a seam ring is ANTIMERIDIAN, a pole ring is POLE, and neither in a plane")
    else:
        failed += 1
        print("  ❌ the seam/pole verdicts are wrong")

    var seam_area = ring_area_flat(ax, ay, 4, GEO_FRAME_LONLAT_DEG)
    var pole_pip = point_in_ring_flat(0.0, 85.0, wx, wy, 4, GEO_FRAME_LONLAT_DEG)
    if (
        seam_area.status == GEO_ERR_ANTIMERIDIAN
        and not seam_area.has_area
        and seam_area.area_m2 == 0.0
        and pole_pip.status == GEO_ERR_POLE
    ):
        passed += 1
        print("  ✅ area and membership both refuse rather than answer plausibly")
    else:
        failed += 1
        print("  ❌ a seam/pole ring produced an answer:", seam_area.status, pole_pip.status)

    # ── area in square metres, projected and said so ─────────────────────────
    var plane_area = ring_area_flat(sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        plane_area.status == GEO_OK
        and plane_area.has_area
        and plane_area.area_m2 == 1.0
        and not plane_area.projected
        and plane_area.orientation == GEO_ORIENT_CCW
    ):
        passed += 1
        print("  ✅ a metre-frame ring: 1.0 m^2, projected = False")
    else:
        failed += 1
        print("  ❌ planar area wrong:", plane_area.area_m2, plane_area.projected)

    var deg_area = ring_area_flat(sx, sy, 4, GEO_FRAME_LONLAT_DEG)
    if (
        deg_area.status == GEO_OK
        and deg_area.has_area
        and deg_area.projected
        and fabs(deg_area.area_m2 - REF_DEG_BOX_M2) < REF_DEG_BOX_M2 * 1.0e-9
        and deg_area.ref_lat_deg == 0.5
        and deg_area.ref_lon_deg == 0.5
        and deg_area.lon_span_deg == 1.0
        and deg_area.lat_span_deg == 1.0
    ):
        passed += 1
        print("  ✅ a 1x1 degree box at the equator is 12363840916.39 m^2, ref parallel 0.5")
    else:
        failed += 1
        print("  ❌ projected area wrong:", deg_area.area_m2, deg_area.ref_lat_deg)

    # Under 3 vertices there is no area at all, in either frame.
    var no_area = ring_area_flat(two_x, two_y, 2, GEO_FRAME_PLANE_M)
    if no_area.status == GEO_OK and not no_area.has_area and no_area.area_m2 == 0.0:
        passed += 1
        print("  ✅ a 2-vertex ring reports NO area, with status OK")
    else:
        failed += 1
        print("  ❌ a 2-vertex ring claimed an area")

    # ── batch classification ─────────────────────────────────────────────────
    var pxs = List[Float64]()
    var pys = List[Float64]()
    pxs.append(0.5)
    pys.append(0.5)  # inside
    pxs.append(0.25)
    pys.append(0.75)  # inside
    pxs.append(0.5)
    pys.append(0.0)  # boundary (horizontal edge)
    pxs.append(1.0)
    pys.append(1.0)  # boundary (vertex)
    pxs.append(2.0)
    pys.append(2.0)  # outside
    var batch = points_in_ring_flat(pxs, pys, 5, sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        batch.status == GEO_OK
        and batch.n_points == 5
        and batch.n_inside == 2
        and batch.n_boundary == 2
        and batch.n_outside == 1
        and len(batch.codes) == 5
        and batch.codes[0] == GEO_PIP_INSIDE
        and batch.codes[2] == GEO_PIP_BOUNDARY
        and batch.codes[4] == GEO_PIP_OUTSIDE
        and batch.edge_tests == 20
    ):
        passed += 1
        print("  ✅ batch of 5: 2 inside, 2 boundary, 1 outside, 20 edge tests charged")
    else:
        failed += 1
        print("  ❌ batch counts wrong:", batch.n_inside, batch.n_boundary, batch.n_outside)

    # The batch must agree with the single-point entry point EXACTLY — same convention, one
    # implementation, so a caller cannot get one answer from one door and another from the next.
    var agree = True
    for i in range(5):
        var one = point_in_ring_flat(pxs[i], pys[i], sx, sy, 4, GEO_FRAME_PLANE_M)
        if one.classification != batch.codes[i]:
            agree = False
    if agree:
        passed += 1
        print("  ✅ the batch and single-point entry points return identical classifications")
    else:
        failed += 1
        print("  ❌ batch and single-point disagree")

    # On a refusal `codes` is EMPTY, never a list of zeros — GEO_PIP_OUTSIDE is 0, so a
    # zero-filled list would read as "every point is outside".
    var refused = points_in_ring_flat(pxs, pys, 5, two_x, two_y, 2, GEO_FRAME_PLANE_M)
    if (
        refused.status == GEO_ERR_DEGENERATE_RING
        and len(refused.codes) == 0
        and refused.n_points == 0
    ):
        passed += 1
        print("  ✅ a refused batch returns an EMPTY codes list, not 5 zeros")
    else:
        failed += 1
        print("  ❌ a refusal returned codes:", len(refused.codes))

    # ── convex clip ──────────────────────────────────────────────────────────
    # The unit square clipped by [0.5, 1.5] x [0, 1] is [0.5, 1] x [0, 1]: area exactly 0.5.
    var cx = List[Float64]()
    var cy = List[Float64]()
    cx.append(0.5)
    cy.append(0.0)
    cx.append(1.5)
    cy.append(0.0)
    cx.append(1.5)
    cy.append(1.0)
    cx.append(0.5)
    cy.append(1.0)
    var clip = ring_intersect_convex_flat(sx, sy, 4, cx, cy, 4, GEO_FRAME_PLANE_M)
    if (
        clip.status == GEO_OK
        and not clip.is_empty
        and clip.has_area
        and fabs(clip.area - 0.5) < 1.0e-15
        and clip.clip_convex
        and clip.subject_convex
    ):
        passed += 1
        print("  ✅ the unit square clipped to x >= 0.5 has area exactly 0.5")
    else:
        failed += 1
        print("  ❌ clip area wrong:", clip.area, clip.n_vertices)

    # Clipping by a reversed (clockwise) clip ring must give the same answer: which side is
    # "inside" follows the clip's OWN winding, so the caller need not supply a direction.
    var rcx = List[Float64]()
    var rcy = List[Float64]()
    for i in range(4):
        rcx.append(cx[3 - i])
        rcy.append(cy[3 - i])
    var rclip = ring_intersect_convex_flat(sx, sy, 4, rcx, rcy, 4, GEO_FRAME_PLANE_M)
    if rclip.status == GEO_OK and fabs(rclip.area - clip.area) < 1.0e-15:
        passed += 1
        print("  ✅ a clockwise clip ring gives the same intersection as its reversal")
    else:
        failed += 1
        print("  ❌ the clip's winding changed the answer:", rclip.area)

    # Two rings that do not overlap have an EMPTY intersection, and that is a real answer with
    # status OK — distinguished from a refusal by the STATUS, never by len(xs).
    var fx = List[Float64]()
    var fy = List[Float64]()
    fx.append(10.0)
    fy.append(10.0)
    fx.append(11.0)
    fy.append(10.0)
    fx.append(11.0)
    fy.append(11.0)
    fx.append(10.0)
    fy.append(11.0)
    var disjoint = ring_intersect_convex_flat(sx, sy, 4, fx, fy, 4, GEO_FRAME_PLANE_M)
    if (
        disjoint.status == GEO_OK
        and disjoint.is_empty
        and len(disjoint.xs) == 0
        and not disjoint.has_area
    ):
        passed += 1
        print("  ✅ disjoint rings: is_empty True with status OK, both lists empty")
    else:
        failed += 1
        print("  ❌ a disjoint clip did not report an empty intersection:", disjoint.status)

    # A NON-CONVEX clip is refused. Sutherland-Hodgman assumes an intersection of half-planes;
    # on an L-shape it returns a polygon that looks reasonable and is wrong.
    var lx = List[Float64]()
    var ly = List[Float64]()
    lx.append(0.0)
    ly.append(0.0)
    lx.append(2.0)
    ly.append(0.0)
    lx.append(2.0)
    ly.append(1.0)
    lx.append(1.0)
    ly.append(1.0)
    lx.append(1.0)
    ly.append(2.0)
    lx.append(0.0)
    ly.append(2.0)
    var nonconvex = ring_intersect_convex_flat(sx, sy, 4, lx, ly, 6, GEO_FRAME_PLANE_M)
    if (
        nonconvex.status == GEO_ERR_NOT_CONVEX
        and not nonconvex.clip_convex
        and len(nonconvex.xs) == 0
        and not nonconvex.is_empty
    ):
        passed += 1
        print("  ✅ an L-shaped clip is refused with GEO_ERR_NOT_CONVEX, not clipped wrong")
    else:
        failed += 1
        print("  ❌ a non-convex clip was accepted:", nonconvex.status)

    # The L-shape is a legitimate SUBJECT, though: clipping it by the unit square keeps the
    # unit square's worth of it, area 1.0.
    var lsub = ring_intersect_convex_flat(lx, ly, 6, sx, sy, 4, GEO_FRAME_PLANE_M)
    if (
        lsub.status == GEO_OK
        and not lsub.subject_convex
        and lsub.clip_convex
        and fabs(lsub.area - 1.0) < 1.0e-15
    ):
        passed += 1
        print("  ✅ a non-convex SUBJECT is fine: the L clipped to the unit square is 1.0")
    else:
        failed += 1
        print("  ❌ a non-convex subject was mishandled:", lsub.status, lsub.area)

    # ── a PENTAGRAM clip: turn-sign consistent, and not convex ────────────────
    # Five vertices at radius 1, 144 degrees apart. Every turn has the same sign, so a gate
    # made of turn signs alone accepts it — and Sutherland-Hodgman then returns the
    # intersection of the five half-planes, which is the inner pentagon of area
    # 2.5 * r^2 * sin(72 deg) with r = 1/phi^2 = 0.381966, i.e. 0.34687. That is neither the
    # star (1.12257) nor any intersection the caller asked for, and it came back under GEO_OK
    # with `clip_convex = True`. Convexity is turn signs AND simplicity.
    var star_x = List[Float64]()
    var star_y = List[Float64]()
    star_x.append(1.0)
    star_y.append(0.0)
    star_x.append(-0.8090169943749473)
    star_y.append(0.5877852522924732)
    star_x.append(0.30901699437494745)
    star_y.append(-0.9510565162951535)
    star_x.append(0.30901699437494745)
    star_y.append(0.9510565162951535)
    star_x.append(-0.8090169943749473)
    star_y.append(-0.5877852522924732)
    var star_rep = ring_report_flat(star_x, star_y, 5, GEO_FRAME_PLANE_M)
    var star_clip = ring_intersect_convex_flat(
        sx, sy, 4, star_x, star_y, 5, GEO_FRAME_PLANE_M
    )
    if (
        star_rep.simplicity_checked
        and star_rep.self_intersecting
        and star_rep.is_convex
        and star_clip.status == GEO_ERR_NOT_CONVEX
        and not star_clip.clip_convex
        and star_clip.n_vertices == 0
        and len(star_clip.xs) == 0
        and star_clip.area == 0.0
    ):
        passed += 1
        print("  ✅ a pentagram turns consistently, is NOT simple, and is refused as a clip")
    else:
        failed += 1
        print(
            "  ❌ the pentagram clip was accepted:", star_clip.status,
            star_clip.clip_convex, star_clip.n_vertices, star_clip.area,
        )

    # A convex clip of the same vertex count still works, so the new half of the gate refuses
    # the star and nothing else: the regular pentagon inscribed in the same circle, clipped
    # against the 4x4 square that contains it, comes back whole with the pentagon's own area
    # 2.5 * sin(72 deg) = 2.377641290737884.
    var pent_x = List[Float64]()
    var pent_y = List[Float64]()
    pent_x.append(1.0)
    pent_y.append(0.0)
    pent_x.append(0.30901699437494745)
    pent_y.append(0.9510565162951535)
    pent_x.append(-0.8090169943749473)
    pent_y.append(0.5877852522924732)
    pent_x.append(-0.8090169943749473)
    pent_y.append(-0.5877852522924732)
    pent_x.append(0.30901699437494745)
    pent_y.append(-0.9510565162951535)
    var big_x = List[Float64]()
    var big_y = List[Float64]()
    big_x.append(-2.0)
    big_y.append(-2.0)
    big_x.append(2.0)
    big_y.append(-2.0)
    big_x.append(2.0)
    big_y.append(2.0)
    big_x.append(-2.0)
    big_y.append(2.0)
    var pent_clip = ring_intersect_convex_flat(
        big_x, big_y, 4, pent_x, pent_y, 5, GEO_FRAME_PLANE_M
    )
    if (
        pent_clip.status == GEO_OK
        and pent_clip.clip_convex
        and pent_clip.n_vertices == 5
        and fabs(pent_clip.area - 2.377641290737884) < 1.0e-12
    ):
        passed += 1
        print("  ✅ the convex pentagon with the same 5 vertices clips fine: area 2.3776")
    else:
        failed += 1
        print(
            "  ❌ the simplicity gate over-refused a convex clip:", pent_clip.status,
            pent_clip.n_vertices, pent_clip.area,
        )

    # Simplicity is O(n^2) and is only affordable to GEO_MAX_SIMPLICITY_VERTICES. Above that
    # the question is not asked, and "not asked" is not "answered no": the clip is refused with
    # GEO_ERR_BUDGET rather than clipped on an unverified convexity claim. A convex ring of
    # exactly the ceiling is still served, so the boundary is where it is declared to be.
    var ring_at_limit_x = List[Float64]()
    var ring_at_limit_y = List[Float64]()
    var ring_over_x = List[Float64]()
    var ring_over_y = List[Float64]()
    for i in range(GEO_MAX_SIMPLICITY_VERTICES + 1):
        var ang = 2.0 * 3.141592653589793 * Float64(i) / Float64(
            GEO_MAX_SIMPLICITY_VERTICES + 1
        )
        ring_over_x.append(cos(ang))
        ring_over_y.append(sin(ang))
    for i in range(GEO_MAX_SIMPLICITY_VERTICES):
        var ang2 = 2.0 * 3.141592653589793 * Float64(i) / Float64(
            GEO_MAX_SIMPLICITY_VERTICES
        )
        ring_at_limit_x.append(cos(ang2))
        ring_at_limit_y.append(sin(ang2))
    var over_limit = ring_intersect_convex_flat(
        big_x, big_y, 4, ring_over_x, ring_over_y, GEO_MAX_SIMPLICITY_VERTICES + 1,
        GEO_FRAME_PLANE_M,
    )
    var at_limit = ring_intersect_convex_flat(
        big_x, big_y, 4, ring_at_limit_x, ring_at_limit_y, GEO_MAX_SIMPLICITY_VERTICES,
        GEO_FRAME_PLANE_M,
    )
    if (
        over_limit.status == GEO_ERR_BUDGET
        and not over_limit.clip_convex
        and len(over_limit.xs) == 0
        and at_limit.status == GEO_OK
        and at_limit.clip_convex
        and at_limit.n_vertices == GEO_MAX_SIMPLICITY_VERTICES
    ):
        passed += 1
        print("  ✅ a clip ring above the simplicity ceiling refuses; one AT it is served")
    else:
        failed += 1
        print(
            "  ❌ the simplicity ceiling is not the declared boundary:", over_limit.status,
            at_limit.status, at_limit.n_vertices,
        )

    var thin = ring_intersect_convex_flat(sx, sy, 4, two_x, two_y, 2, GEO_FRAME_PLANE_M)
    if thin.status == GEO_ERR_DEGENERATE_RING and len(thin.xs) == 0:
        passed += 1
        print("  ✅ a 2-vertex clip ring is degenerate, not an empty intersection")
    else:
        failed += 1
        print("  ❌ a 2-vertex clip was not refused:", thin.status)

    print("  [geospatial.polygon] Passed:", passed, "Failed:", failed)
