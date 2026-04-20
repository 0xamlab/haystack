"""Python equivalent of mojo/engine/network_analysis.mojo (auto-generated)."""
import math
import random as _rng

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

def _has_edge(adj, u, v):
    ncount = len(adj[u])
    for i in range(ncount):
        if adj[u][i] == v:
            return True
    return False






def degree(adj, node):
    return len(adj[node])






def degree_distribution(adj):
    result = []
    for i in range(len(adj)):
        result.append(len(adj[i]))
    return result






def density(adj):
    n = len(adj)
    if n <= 1:
        return 0.0
    edge_count = 0
    for i in range(n):
        edge_count += len(adj[i])

    e = edge_count
    return float(e) / float(n * (n - 1))






def bfs_distances(adj, start):
    n = len(adj)
    dist = []
    for i in range(n):
        dist.append(-1)
    dist[start] = 0
    queue = []
    queue.append(start)
    head = 0
    while head < len(queue):
        cur = queue[head]
        head += 1
        ncount = len(adj[cur])
        for j in range(ncount):
            nb = adj[cur][j]
            if dist[nb] == -1:
                dist[nb] = dist[cur] + 1
                queue.append(nb)
    return dist






def pagerank(adj, damping=0.85, max_iter=100, tol=1e-6):
    n = len(adj)
    if n == 0:
        return []
    rank = []
    new_rank = []
    init_val = 1.0 / float(n)
    for i in range(n):
        rank.append(init_val)
        new_rank.append(0.0)

    for _ in range(max_iter):
        base = (1.0 - damping) / float(n)
        for i in range(n):
            new_rank[i] = base
        for i in range(n):
            deg = len(adj[i])
            if deg > 0:
                share = rank[i] / float(deg)
                for j in range(deg):
                    nb = adj[i][j]
                    new_rank[nb] += damping * share

        diff = 0.0
        for i in range(n):
            diff += math.fabs(new_rank[i] - rank[i])
        for i in range(n):
            rank[i] = new_rank[i]
        if diff < tol:
            break
    return rank






def degree_centrality(adj):
    n = len(adj)
    result = []
    if n <= 1:
        for i in range(n):
            result.append(0.0)
        return result
    denom = float(n - 1)
    for i in range(n):
        result.append(float(len(adj[i])) / denom)
    return result






def closeness_centrality(adj):
    n = len(adj)
    result = []
    if n <= 1:
        for i in range(n):
            result.append(0.0)
        return result
    for i in range(n):
        dist = bfs_distances(adj, i)
        total = 0
        reachable = 0
        for j in range(n):
            if j != i and dist[j] >= 0:
                total += dist[j]
                reachable += 1
        if total > 0 and reachable == n - 1:
            result.append(float(n - 1) / float(total))
        else:
            result.append(0.0)
    return result






def clustering_coefficient(adj, node):
    k = len(adj[node])
    if k < 2:
        return 0.0
    triangles = 0
    for i in range(k):
        for j in range(i + 1, k):
            if _has_edge(adj, adj[node][i], adj[node][j]):
                triangles += 1
    possible = k * (k - 1) // 2
    return float(triangles) / float(possible)






def avg_clustering_coefficient(adj):
    n = len(adj)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        total += clustering_coefficient(adj, i)
    return total / float(n)






def is_connected(adj):
    n = len(adj)
    if n == 0:
        return True
    dist = bfs_distances(adj, 0)
    for i in range(n):
        if dist[i] == -1:
            return False
    return True






def connected_components(adj):
    n = len(adj)
    visited = []
    for i in range(n):
        visited.append(False)
    components = []
    for i in range(n):
        if not visited[i]:
            dist = bfs_distances(adj, i)
            comp = []
            for j in range(n):
                if dist[j] >= 0:
                    visited[j] = True
                    comp.append(j)
            components.append(comp)
    return components
