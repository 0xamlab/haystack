"""Python equivalent of mojo/engine/topology.mojo (auto-generated)."""
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

def _uf_find(parent, x):
    cur = x
    while parent[cur] != cur:
        cur = parent[cur]
    return cur



def _uf_union(parent, rank, a, b):
    ra = _uf_find(parent, a)
    rb = _uf_find(parent, b)
    if ra == rb:
        return False
    if rank[ra] < rank[rb]:
        parent[ra] = rb
    elif rank[ra] > rank[rb]:
        parent[rb] = ra
    else:
        parent[rb] = ra
        rank[ra] += 1
    return True






def distance_matrix(points):
    n = len(points)
    result = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(0.0)
            else:
                s = 0.0
                dim = len(points[i])
                if len(points[j]) < dim:
                    dim = len(points[j])
                for k in range(dim):
                    d = points[i][k] - points[j][k]
                    s += d * d
                row.append(math.sqrt(s))
        result.append(row)
    return result






def vietoris_rips_edges(distances, epsilon):
    n = len(distances)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if distances[i][j] <= epsilon:
                edge = []
                edge.append(i)
                edge.append(j)
                edges.append(edge)
    return edges






def connected_components_from_edges(n, edges):
    parent = []
    rank = []
    for i in range(n):
        parent.append(i)
        rank.append(0)
    for idx in range(len(edges)):
        _ = _uf_union(parent, rank, edges[idx][0], edges[idx][1])
    count = 0
    for i in range(n):
        if _uf_find(parent, i) == i:
            count += 1
    return count






def betti_0(n, edges):
    return connected_components_from_edges(n, edges)






def filtration_values(distances):
    vals = []
    n = len(distances)
    for i in range(n):
        for j in range(i + 1, n):
            d = distances[i][j]

            found = False
            for k in range(len(vals)):
                if math.fabs(vals[k] - d) < 1e-12:
                    found = True
                    break
            if not found:
                vals.append(d)

    for i in range(1, len(vals)):
        key = vals[i]
        j = i - 1
        while j >= 0 and vals[j] > key:
            vals[j + 1] = vals[j]
            j -= 1
        vals[j + 1] = key
    return vals






def persistence_diagram_0(distances):
    n = len(distances)

    edge_w = []
    edge_i = []
    edge_j = []
    for i in range(n):
        for j in range(i + 1, n):
            edge_w.append(distances[i][j])
            edge_i.append(i)
            edge_j.append(j)

    for ii in range(1, len(edge_w)):
        kw = edge_w[ii]
        ki = edge_i[ii]
        kj = edge_j[ii]
        jj = ii - 1
        while jj >= 0 and edge_w[jj] > kw:
            edge_w[jj + 1] = edge_w[jj]
            edge_i[jj + 1] = edge_i[jj]
            edge_j[jj + 1] = edge_j[jj]
            jj -= 1
        edge_w[jj + 1] = kw
        edge_i[jj + 1] = ki
        edge_j[jj + 1] = kj

    parent = []
    rank = []
    for i in range(n):
        parent.append(i)
        rank.append(0)
    diagram = []
    for idx in range(len(edge_w)):
        merged = _uf_union(parent, rank, edge_i[idx], edge_j[idx])
        if merged:
            pair = []
            pair.append(0.0)
            pair.append(edge_w[idx])
            diagram.append(pair)

    last = []
    last.append(0.0)
    last.append(1e18)
    diagram.append(last)
    return diagram






def total_persistence(diagram):
    s = 0.0
    for i in range(len(diagram)):
        if diagram[i][1] < 1e18:
            s += diagram[i][1] - diagram[i][0]
    return s






def bottleneck_distance(d1, d2):
    max_dist = 0.0

    for i in range(len(d1)):
        min_d = 1e18
        for j in range(len(d2)):
            db = math.fabs(d1[i][0] - d2[j][0])
            dd = math.fabs(d1[i][1] - d2[j][1])
            dist = db
            if dd > dist:
                dist = dd
            if dist < min_d:
                min_d = dist
        if min_d > max_dist:
            max_dist = min_d

    for i in range(len(d2)):
        min_d = 1e18
        for j in range(len(d1)):
            db = math.fabs(d2[i][0] - d1[j][0])
            dd = math.fabs(d2[i][1] - d1[j][1])
            dist = db
            if dd > dist:
                dist = dd
            if dist < min_d:
                min_d = dist
        if min_d > max_dist:
            max_dist = min_d
    return max_dist






def euler_characteristic(n_vertices, n_edges, n_triangles):
    return n_vertices - n_edges + n_triangles






def rips_triangle_count(n, edges):

    adj = []
    for _ in range(n):
        row = []
        for _ in range(n):
            row.append(False)
        adj.append(row)
    for idx in range(len(edges)):
        a = edges[idx][0]
        b = edges[idx][1]
        adj[a][b] = True
        adj[b][a] = True
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i][j]:
                for k in range(j + 1, n):
                    if adj[i][k] and adj[j][k]:
                        count += 1
    return count
