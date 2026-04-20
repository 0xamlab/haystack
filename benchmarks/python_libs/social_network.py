"""Python equivalent of mojo/engine/social_network.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.random import random_float64
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

def _has_edge(adj, src, dst):
    for i in range(len(adj[src])):
        if adj[src][i] == dst:
            return True
    return False






def in_degree(adj, node):
    count = 0
    for i in range(len(adj)):
        for j in range(len(adj[i])):
            if adj[i][j] == node:
                count += 1
    return count






def out_degree(adj, node):
    return len(adj[node])






def reciprocity(adj):
    n = len(adj)
    total_edges = 0
    recip_edges = 0
    for i in range(n):
        for j in range(len(adj[i])):
            total_edges += 1
            target = adj[i][j]

            for k in range(len(adj[target])):
                if adj[target][k] == i:
                    recip_edges += 1
                    break
    if total_edges == 0:
        return 0.0
    return float(recip_edges) / float(total_edges)






def influence_spread_ic(adj, seeds, p, n_simulations):
    n = len(adj)
    total_activated = 0.0

    for _sim in range(n_simulations):

        active = []
        for _i in range(n):
            active.append(False)

        queue = []
        for s in range(len(seeds)):
            seed = seeds[s]
            if seed >= 0 and seed < n:
                active[seed] = True
                queue.append(seed)

        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            for j in range(len(adj[node])):
                neighbor = adj[node][j]
                if not active[neighbor]:
                    r = random_float64()
                    if r < p:
                        active[neighbor] = True
                        queue.append(neighbor)

        count = 0
        for i in range(n):
            if active[i]:
                count += 1
        total_activated += float(count)

    return total_activated / float(n_simulations)






def local_clustering_directed(adj, node):
    n = len(adj)

    is_neighbor = []
    for _i in range(n):
        is_neighbor.append(False)

    for j in range(len(adj[node])):
        nb = adj[node][j]
        if nb != node:
            is_neighbor[nb] = True

    for i in range(n):
        for j in range(len(adj[i])):
            if adj[i][j] == node and i != node:
                is_neighbor[i] = True

    neighbors = []
    for i in range(n):
        if is_neighbor[i]:
            neighbors.append(i)

    k = len(neighbors)
    if k <= 1:
        return 0.0


    edges_among = 0
    for i in range(k):
        for j in range(k):
            if i != j:
                if _has_edge(adj, neighbors[i], neighbors[j]):
                    edges_among += 1

    return float(edges_among) / float(k * (k - 1))






def strongly_connected_check(adj):
    n = len(adj)
    if n == 0:
        return True


    visited = []
    for _i in range(n):
        visited.append(False)
    queue = []
    visited[0] = True
    queue.append(0)
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        for j in range(len(adj[node])):
            nb = adj[node][j]
            if not visited[nb]:
                visited[nb] = True
                queue.append(nb)

    for i in range(n):
        if not visited[i]:
            return False


    rev = []
    for _i in range(n):
        rev.append([])
    for i in range(n):
        for j in range(len(adj[i])):
            rev[adj[i][j]].append(i)


    visited2 = []
    for _i in range(n):
        visited2.append(False)
    queue2 = []
    visited2[0] = True
    queue2.append(0)
    head = 0
    while head < len(queue2):
        node = queue2[head]
        head += 1
        for j in range(len(rev[node])):
            nb = rev[node][j]
            if not visited2[nb]:
                visited2[nb] = True
                queue2.append(nb)

    for i in range(n):
        if not visited2[i]:
            return False

    return True






def community_label_propagation(adj, max_iter):
    n = len(adj)
    labels = []
    for i in range(n):
        labels.append(i)

    for _it in range(max_iter):
        changed = False
        for i in range(n):

            neighbor_labels = []
            for j in range(len(adj[i])):
                neighbor_labels.append(labels[adj[i][j]])

            for j in range(n):
                for k in range(len(adj[j])):
                    if adj[j][k] == i:
                        neighbor_labels.append(labels[j])
                        break

            if len(neighbor_labels) == 0:
                continue


            best_label = neighbor_labels[0]
            best_count = 0
            for a in range(len(neighbor_labels)):
                lbl = neighbor_labels[a]
                cnt = 0
                for b in range(len(neighbor_labels)):
                    if neighbor_labels[b] == lbl:
                        cnt += 1
                if cnt > best_count:
                    best_count = cnt
                    best_label = lbl

            if labels[i] != best_label:
                labels[i] = best_label
                changed = True

        if not changed:
            break

    return labels






def network_density(adj):
    n = len(adj)
    if n <= 1:
        return 0.0
    total_edges = 0
    for i in range(n):
        total_edges += len(adj[i])
    return float(total_edges) / float(n * (n - 1))






def average_path_length_estimate(adj, n_samples):
    n = len(adj)
    if n <= 1:
        return 0.0

    total_dist = 0.0
    total_pairs = 0
    actual_samples = n_samples
    if actual_samples > n:
        actual_samples = n

    for s in range(actual_samples):

        source = s % n


        dist = []
        for _i in range(n):
            dist.append(-1)
        dist[source] = 0
        queue = []
        queue.append(source)
        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            for j in range(len(adj[node])):
                nb = adj[node][j]
                if dist[nb] == -1:
                    dist[nb] = dist[node] + 1
                    queue.append(nb)

        for i in range(n):
            if dist[i] > 0:
                total_dist += float(dist[i])
                total_pairs += 1

    if total_pairs == 0:
        return 0.0
    return total_dist / float(total_pairs)
