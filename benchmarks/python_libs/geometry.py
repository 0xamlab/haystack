"""Python equivalent of mojo/engine/geometry.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass

class Point:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('x')
        self.x = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('y')
        self.y = _v1 if _v1 is not None else 0.0
    def __repr__(self):
        return f'Point({vars(self)})'

def random_float64(lo=0.0, hi=1.0): return _rng.uniform(lo, hi)
def random_si64(): return _rng.randint(-2**31, 2**31)
def random_ui64(): return _rng.randint(0, 2**32)

def json_get_string(raw, key, default=''):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return str(v) if v is not None else default
    except Exception: return default
def json_get_float(raw, key, default=0.0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return float(v) if v is not None else default
    except Exception: return default
def json_get_int(raw, key, default=0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return int(v) if v is not None else default
    except Exception: return default
def json_get_bool(raw, key, default=False):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return bool(v) if v is not None else default
    except Exception: return default
def json_get_object(raw, key, default='{}'):
    try:
        import json as _j; v = _j.loads(raw).get(key, {})
        return _j.dumps(v) if isinstance(v, dict) else default
    except Exception: return default
def json_get_array(raw, key, default='[]'):
    try:
        import json as _j; v = _j.loads(raw).get(key, [])
        return _j.dumps(v) if isinstance(v, list) else default
    except Exception: return default
def json_array_len(arr):
    try:
        import json as _j; return len(_j.loads(arr))
    except Exception: return 0
def json_array_get(arr, index):
    try:
        import json as _j; v = _j.loads(arr)
        return _j.dumps(v[index]) if index < len(v) else ''
    except Exception: return ''
def to_lower(s): return s.lower()
def contains_keyword(text, keyword): return keyword.lower() in text.lower()
def detect_polarity(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','expense','loss','debit','charge','penalty','tax')): return -1
    if any(k in n for k in ('revenue','profit','income','gain','credit','sales')): return 1
    return 0
def detect_unit_hint(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','price','revenue','profit','amount','value','dollar')): return 'currency'
    if any(k in n for k in ('pct','percent','ratio','rate','margin')): return 'percentage'
    if any(k in n for k in ('qty','quantity','count','units','volume')): return 'count'
    return ''
def infer_distribution_from_values(values): return ('normal', '{}')
def map_fields(raw): return []
def build_objective_function(mappings): return ''
def build_variables_json(mappings): return '[]'
class FieldMapping: pass
def dice_coefficient(a, b):
    if not a or not b: return 0.0
    def _bg(s): return set(s[i:i+2] for i in range(len(s)-1))
    ag, bg = _bg(a), _bg(b)
    if not ag or not bg: return 0.0
    return 2.0 * len(ag & bg) / (len(ag) + len(bg))
def edit_similarity(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    m, n = len(a), len(b); dp = list(range(n+1))
    for i in range(1, m+1):
        prev, dp[0] = dp[0], i
        for j in range(1, n+1):
            t = dp[j]; dp[j] = prev if a[i-1]==b[j-1] else 1+min(prev,dp[j],dp[j-1]); prev=t
    return 1.0 - dp[n] / max(m, n)
def jaccard_index(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)
def to_set(lst): return list(set(lst))
def parse_float64(s, default=0.0):
    try: return float(s)
    except Exception: return default
def parse_int(s, default=0):
    try: return int(float(s))
    except Exception: return default
DIM_UNKNOWN = 0; DIM_COUNT = 1; DIM_CURRENCY = 2; DIM_RATE = 3
DIM_RATIO = 4; DIM_IDENTIFIER = 5; DIM_INVALID = -1
def infer_from_samples(values): return DIM_UNKNOWN
def propagate(a, b, op): return DIM_UNKNOWN
def role_for_dimension(dim): return 'metric'
class Python:
    @staticmethod
    def import_module(name):
        import importlib; return importlib.import_module(name)

def _cross_from_list(pts, oi, ai, bi):
    return (pts[ai].x - pts[oi].x) * (pts[bi].y - pts[oi].y) - (
        pts[ai].y - pts[oi].y
    ) * (pts[bi].x - pts[oi].x)






def distance_2d(a, b):
    dx = a.x - b.x
    dy = a.y - b.y
    return math.sqrt(dx * dx + dy * dy)






def cross_product_2d(o, a, b):
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)






def point_in_polygon(p, polygon):
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1
    for i in range(n):
        yi = polygon[i].y
        yj = polygon[j].y
        xi = polygon[i].x
        xj = polygon[j].x

        if ((yi > p.y) != (yj > p.y)) and (
            p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i

    return inside






def polygon_area(polygon):
    n = len(polygon)
    if n < 3:
        return 0.0

    area = 0.0
    j = n - 1
    for i in range(n):
        area += (polygon[j].x + polygon[i].x) * (polygon[j].y - polygon[i].y)
        j = i

    return math.fabs(area) / 2.0






def polygon_perimeter(polygon):
    n = len(polygon)
    if n < 2:
        return 0.0

    perim = 0.0
    for i in range(n):
        j = (i + 1) % n
        dx = polygon[j].x - polygon[i].x
        dy = polygon[j].y - polygon[i].y
        perim += math.sqrt(dx * dx + dy * dy)
    return perim






def convex_hull(points):
    n = len(points)
    if n < 3:
        result = []
        for i in range(n):
            result.append(Point(points[i].x, points[i].y))
        return result


    sorted_pts = []
    for i in range(n):
        sorted_pts.append(Point(points[i].x, points[i].y))

    for i in range(1, n):
        key_x = sorted_pts[i].x
        key_y = sorted_pts[i].y
        j = i - 1
        while j >= 0 and (sorted_pts[j].x > key_x or (sorted_pts[j].x == key_x and sorted_pts[j].y > key_y)):
            sorted_pts[j + 1] = Point(sorted_pts[j].x, sorted_pts[j].y)
            j -= 1
        sorted_pts[j + 1] = Point(key_x, key_y)


    lower = []
    for i in range(n):
        while len(lower) >= 2:
            ll = len(lower)
            ox = lower[ll - 2].x
            oy = lower[ll - 2].y
            ax = lower[ll - 1].x
            ay = lower[ll - 1].y
            bx = sorted_pts[i].x
            by = sorted_pts[i].y
            cross = (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
            if cross <= 0.0:
                _ = lower.pop()
            else:
                break
        lower.append(Point(sorted_pts[i].x, sorted_pts[i].y))


    upper = []
    for i in range(n - 1, -1, -1):
        while len(upper) >= 2:
            ul = len(upper)
            ox = upper[ul - 2].x
            oy = upper[ul - 2].y
            ax = upper[ul - 1].x
            ay = upper[ul - 1].y
            bx = sorted_pts[i].x
            by = sorted_pts[i].y
            cross = (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
            if cross <= 0.0:
                _ = upper.pop()
            else:
                break
        upper.append(Point(sorted_pts[i].x, sorted_pts[i].y))


    _ = lower.pop()
    _ = upper.pop()


    result = []
    for i in range(len(lower)):
        result.append(Point(lower[i].x, lower[i].y))
    for i in range(len(upper)):
        result.append(Point(upper[i].x, upper[i].y))

    return result






def line_intersection(p1, p2, p3, p4):
    x1 = p1.x
    y1 = p1.y
    x2 = p2.x
    y2 = p2.y
    x3 = p3.x
    y3 = p3.y
    x4 = p4.x
    y4 = p4.y

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if math.fabs(denom) < 1e-12:
        raise Error("Lines are parallel or coincident — no unique intersection")

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom

    ix = x1 + t * (x2 - x1)
    iy = y1 + t * (y2 - y1)
    return Point(ix, iy)






def centroid(polygon):
    n = len(polygon)
    if n == 0:
        return Point(0.0, 0.0)
    if n == 1:
        return Point(polygon[0].x, polygon[0].y)
    if n == 2:
        return Point(
            (polygon[0].x + polygon[1].x) / 2.0,
            (polygon[0].y + polygon[1].y) / 2.0,
        )

    signed_area = 0.0
    cx = 0.0
    cy = 0.0

    for i in range(n):
        j = (i + 1) % n
        cross = polygon[i].x * polygon[j].y - polygon[j].x * polygon[i].y
        signed_area += cross
        cx += (polygon[i].x + polygon[j].x) * cross
        cy += (polygon[i].y + polygon[j].y) * cross

    signed_area /= 2.0
    if math.fabs(signed_area) < 1e-15:
        sx = 0.0
        sy = 0.0
        for i in range(n):
            sx += polygon[i].x
            sy += polygon[i].y
        return Point(sx / float(n), sy / float(n))

    cx /= 6.0 * signed_area
    cy /= 6.0 * signed_area
    return Point(cx, cy)






def bounding_box(points):
    n = len(points)
    if n == 0:
        return []

    min_x = points[0].x
    min_y = points[0].y
    max_x = points[0].x
    max_y = points[0].y

    for i in range(1, n):
        if points[i].x < min_x:
            min_x = points[i].x
        if points[i].y < min_y:
            min_y = points[i].y
        if points[i].x > max_x:
            max_x = points[i].x
        if points[i].y > max_y:
            max_y = points[i].y

    result = []
    result.append(min_x)
    result.append(min_y)
    result.append(max_x)
    result.append(max_y)
    return result
