"""Python equivalent of mojo/engine/graph_algorithms.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log
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

def dijkstra_relax(dist_u, edge_weight, dist_v):
    candidate = dist_u + edge_weight
    if candidate < dist_v:
        return candidate
    return dist_v



def bellman_ford_relax(dist_u, edge_weight, dist_v):
    candidate = dist_u + edge_weight
    if candidate < dist_v:
        return candidate
    return dist_v



def pagerank_update(in_neighbor_pr, out_degree, damping, n_nodes):
    teleport = (1.0 - damping) / n_nodes
    if out_degree <= 0.0:
        return teleport
    return teleport + damping * in_neighbor_pr / out_degree



def betweenness_centrality_norm(raw_betweenness, n_nodes, directed):
    if n_nodes <= 2.0:
        return 0.0
    norm = (n_nodes - 1.0) * (n_nodes - 2.0)
    if directed < 0.5:
        norm = norm / 2.0
    if norm <= 0.0:
        return 0.0
    return raw_betweenness / norm



def clustering_coefficient(triangles, degree):
    if degree <= 1.0:
        return 0.0
    return 2.0 * triangles / (degree * (degree - 1.0))



def degree_centrality(degree, n_nodes):
    if n_nodes <= 1.0:
        return 0.0
    return degree / (n_nodes - 1.0)



def closeness_centrality(sum_shortest_paths, n_nodes):
    if sum_shortest_paths <= 0.0:
        return 0.0
    return (n_nodes - 1.0) / sum_shortest_paths



def eigenvector_centrality_update(neighbor_scores_sum, lambda_max):
    if lambda_max <= 0.0:
        return neighbor_scores_sum
    return neighbor_scores_sum / lambda_max



def modularity_contribution(edge_in_community, degree_u, degree_v, total_edges):
    if total_edges <= 0.0:
        return 0.0
    return edge_in_community - degree_u * degree_v / (2.0 * total_edges)



def graph_density(n_edges, n_nodes, directed):
    if n_nodes <= 1.0:
        return 0.0
    max_edges = n_nodes * (n_nodes - 1.0)
    if directed < 0.5:
        max_edges = max_edges / 2.0
    if max_edges <= 0.0:
        return 0.0
    return n_edges / max_edges
