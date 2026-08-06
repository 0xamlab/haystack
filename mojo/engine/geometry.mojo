"""
geometry.mojo — Computational geometry. Zero Python imports.

Replaces shapely with pure Mojo implementations for 2D points,
polygon operations, convex hull, line intersection, and bounding boxes.

Public API:
  Point             — 2D point struct (x, y)
  distance_2d       — Euclidean distance between 2D points
  point_in_polygon  — Ray casting algorithm
  polygon_area      — Shoelace formula (absolute value)
  polygon_perimeter — Sum of edge lengths
  convex_hull       — Andrew's monotone chain algorithm (CCW)
  line_intersection — Line segment intersection point
  cross_product_2d  — 2D cross product (OA × OB)
  centroid          — Centroid of a simple polygon
  bounding_box      — Returns [min_x, min_y, max_x, max_y]
"""
from std.math import sqrt, abs as fabs


# ── Point struct ─────────────────────────────────────────────────────────────


struct Point(Copyable, Movable):
    """A 2D point with x, y coordinates."""

    var x: Float64
    var y: Float64

    def __init__(out self, x: Float64, y: Float64):
        self.x = x
        self.y = y


# ── distance_2d ──────────────────────────────────────────────────────────────


def distance_2d(a: Point, b: Point) -> Float64:
    """Euclidean distance between two 2D points."""
    var dx = a.x - b.x
    var dy = a.y - b.y
    return sqrt(dx * dx + dy * dy)


# ── cross_product_2d ─────────────────────────────────────────────────────────


def cross_product_2d(o: Point, a: Point, b: Point) -> Float64:
    """2D cross product of vectors OA and OB.

    Positive if O→A→B is counter-clockwise, negative if clockwise.
    """
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)


# ── _cross_from_list (helper) ────────────────────────────────────────────────


def _cross_from_list(pts: List[Point], oi: Int, ai: Int, bi: Int) -> Float64:
    """Cross product reading points by index — avoids copy issues."""
    return (pts[ai].x - pts[oi].x) * (pts[bi].y - pts[oi].y) - (
        pts[ai].y - pts[oi].y
    ) * (pts[bi].x - pts[oi].x)


# ── point_in_polygon ─────────────────────────────────────────────────────────


def point_in_polygon(p: Point, polygon: List[Point]) -> Bool:
    """Test whether a point lies inside a polygon using the ray casting algorithm."""
    var n = len(polygon)
    if n < 3:
        return False

    var inside = False
    var j = n - 1
    for i in range(n):
        var yi = polygon[i].y
        var yj = polygon[j].y
        var xi = polygon[i].x
        var xj = polygon[j].x

        if ((yi > p.y) != (yj > p.y)) and (
            p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i

    return inside


# ── polygon_area ─────────────────────────────────────────────────────────────


def polygon_area(polygon: List[Point]) -> Float64:
    """Area of a simple polygon using the Shoelace formula."""
    var n = len(polygon)
    if n < 3:
        return 0.0

    var area: Float64 = 0.0
    var j = n - 1
    for i in range(n):
        area += (polygon[j].x + polygon[i].x) * (polygon[j].y - polygon[i].y)
        j = i

    return fabs(area) / 2.0


# ── polygon_perimeter ────────────────────────────────────────────────────────


def polygon_perimeter(polygon: List[Point]) -> Float64:
    """Perimeter of a polygon (sum of edge lengths)."""
    var n = len(polygon)
    if n < 2:
        return 0.0

    var perim: Float64 = 0.0
    for i in range(n):
        var j = (i + 1) % n
        var dx = polygon[j].x - polygon[i].x
        var dy = polygon[j].y - polygon[i].y
        perim += sqrt(dx * dx + dy * dy)
    return perim


# ── convex_hull ──────────────────────────────────────────────────────────────


def convex_hull(points: List[Point]) -> List[Point]:
    """Convex hull using Andrew's monotone chain algorithm.

    Returns hull vertices in counter-clockwise order.
    """
    var n = len(points)
    if n < 3:
        var result = List[Point]()
        for i in range(n):
            result.append(Point(points[i].x, points[i].y))
        return result^

    # Sort by x, then by y (insertion sort — copy via x,y)
    var sorted_pts = List[Point]()
    for i in range(n):
        sorted_pts.append(Point(points[i].x, points[i].y))

    for i in range(1, n):
        var key_x = sorted_pts[i].x
        var key_y = sorted_pts[i].y
        var j = i - 1
        while j >= 0 and (sorted_pts[j].x > key_x or (sorted_pts[j].x == key_x and sorted_pts[j].y > key_y)):
            sorted_pts[j + 1] = Point(sorted_pts[j].x, sorted_pts[j].y)
            j -= 1
        sorted_pts[j + 1] = Point(key_x, key_y)

    # Build lower hull
    var lower = List[Point]()
    for i in range(n):
        while len(lower) >= 2:
            var ll = len(lower)
            var ox = lower[ll - 2].x
            var oy = lower[ll - 2].y
            var ax = lower[ll - 1].x
            var ay = lower[ll - 1].y
            var bx = sorted_pts[i].x
            var by = sorted_pts[i].y
            var cross = (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
            if cross <= 0.0:
                _ = lower.pop()
            else:
                break
        lower.append(Point(sorted_pts[i].x, sorted_pts[i].y))

    # Build upper hull
    var upper = List[Point]()
    for i in range(n - 1, -1, -1):
        while len(upper) >= 2:
            var ul = len(upper)
            var ox = upper[ul - 2].x
            var oy = upper[ul - 2].y
            var ax = upper[ul - 1].x
            var ay = upper[ul - 1].y
            var bx = sorted_pts[i].x
            var by = sorted_pts[i].y
            var cross = (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
            if cross <= 0.0:
                _ = upper.pop()
            else:
                break
        upper.append(Point(sorted_pts[i].x, sorted_pts[i].y))

    # Remove last point of each half because it's repeated
    _ = lower.pop()
    _ = upper.pop()

    # Concatenate
    var result = List[Point]()
    for i in range(len(lower)):
        result.append(Point(lower[i].x, lower[i].y))
    for i in range(len(upper)):
        result.append(Point(upper[i].x, upper[i].y))

    return result^


# ── line_intersection ────────────────────────────────────────────────────────


def line_intersection(p1: Point, p2: Point, p3: Point, p4: Point) raises -> Point:
    """Intersection point of two lines through (p1-p2) and (p3-p4)."""
    var x1 = p1.x
    var y1 = p1.y
    var x2 = p2.x
    var y2 = p2.y
    var x3 = p3.x
    var y3 = p3.y
    var x4 = p4.x
    var y4 = p4.y

    var denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if fabs(denom) < 1e-12:
        raise Error("Lines are parallel or coincident — no unique intersection")

    var t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom

    var ix = x1 + t * (x2 - x1)
    var iy = y1 + t * (y2 - y1)
    return Point(ix, iy)


# ── centroid ─────────────────────────────────────────────────────────────────


def centroid(polygon: List[Point]) -> Point:
    """Centroid of a simple polygon."""
    var n = len(polygon)
    if n == 0:
        return Point(0.0, 0.0)
    if n == 1:
        return Point(polygon[0].x, polygon[0].y)
    if n == 2:
        return Point(
            (polygon[0].x + polygon[1].x) / 2.0,
            (polygon[0].y + polygon[1].y) / 2.0,
        )

    var signed_area: Float64 = 0.0
    var cx: Float64 = 0.0
    var cy: Float64 = 0.0

    for i in range(n):
        var j = (i + 1) % n
        var cross = polygon[i].x * polygon[j].y - polygon[j].x * polygon[i].y
        signed_area += cross
        cx += (polygon[i].x + polygon[j].x) * cross
        cy += (polygon[i].y + polygon[j].y) * cross

    signed_area /= 2.0
    if fabs(signed_area) < 1e-15:
        var sx: Float64 = 0.0
        var sy: Float64 = 0.0
        for i in range(n):
            sx += polygon[i].x
            sy += polygon[i].y
        return Point(sx / Float64(n), sy / Float64(n))

    cx /= 6.0 * signed_area
    cy /= 6.0 * signed_area
    return Point(cx, cy)


# ── bounding_box ─────────────────────────────────────────────────────────────


def bounding_box(points: List[Point]) -> List[Float64]:
    """Axis-aligned bounding box. Returns [min_x, min_y, max_x, max_y]."""
    var n = len(points)
    if n == 0:
        return List[Float64]()

    var min_x = points[0].x
    var min_y = points[0].y
    var max_x = points[0].x
    var max_y = points[0].y

    for i in range(1, n):
        if points[i].x < min_x:
            min_x = points[i].x
        if points[i].y < min_y:
            min_y = points[i].y
        if points[i].x > max_x:
            max_x = points[i].x
        if points[i].y > max_y:
            max_y = points[i].y

    var result = List[Float64]()
    result.append(min_x)
    result.append(min_y)
    result.append(max_x)
    result.append(max_y)
    return result^
