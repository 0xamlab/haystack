"""Python equivalent of mojo/engine/regression_tree.mojo (auto-generated)."""
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

class RegressionTree:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('split_feature')
        self.split_feature = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('split_value')
        self.split_value = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('left_child')
        self.left_child = _v2 if _v2 is not None else []
        _v3 = args[3] if 3 < len(args) else kwargs.get('right_child')
        self.right_child = _v3 if _v3 is not None else []
        _v4 = args[4] if 4 < len(args) else kwargs.get('leaf_value')
        self.leaf_value = _v4 if _v4 is not None else []
        _v5 = args[5] if 5 < len(args) else kwargs.get('n_nodes')
        self.n_nodes = _v5 if _v5 is not None else 0
    def __repr__(self):
        return f'RegressionTree({vars(self)})'

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

def _mean_of(y, indices):
    n = len(indices)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += y[indices[i]]
    return s / float(n)



def _mse_of(y, indices):
    n = len(indices)
    if n == 0:
        return 0.0
    m = _mean_of(y, indices)
    s = 0.0
    for i in range(n):
        d = y[indices[i]] - m
        s += d * d
    return s / float(n)






def _add_node(tree, feat, val, left, right, leaf_val):
    idx = tree.n_nodes
    tree.split_feature.append(feat)
    tree.split_value.append(val)
    tree.left_child.append(left)
    tree.right_child.append(right)
    tree.leaf_value.append(leaf_val)
    tree.n_nodes += 1
    return idx






def _build_recursive(tree, X, y, indices, depth, max_depth, min_samples):
    n = len(indices)
    mean_val = _mean_of(y, indices)

    if n < min_samples or depth >= max_depth:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)

    all_same = True
    y0 = y[indices[0]]
    for i in range(1, n):
        if math.fabs(y[indices[i]] - y0) > 1e-15:
            all_same = False
            break
    if all_same:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)
    split_info = best_split(X, y, indices)
    feat = int(split_info[0])
    val = split_info[1]
    red = split_info[2]
    if feat < 0 or red < 1e-15:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)

    left_idx = []
    right_idx = []
    for i in range(n):
        if X[indices[i]][feat] <= val:
            left_idx.append(indices[i])
        else:
            right_idx.append(indices[i])
    if len(left_idx) == 0 or len(right_idx) == 0:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)

    node_idx = _add_node(tree, feat, val, -1, -1, mean_val)
    left_node = _build_recursive(
        tree, X, y, left_idx, depth + 1, max_depth, min_samples
    )
    right_node = _build_recursive(
        tree, X, y, right_idx, depth + 1, max_depth, min_samples
    )
    tree.left_child[node_idx] = left_node
    tree.right_child[node_idx] = right_node
    return node_idx






def _node_depth(tree, node):
    if node < 0 or node >= tree.n_nodes:
        return 0
    if tree.split_feature[node] == -1:
        return 1
    ld = _node_depth(tree, tree.left_child[node])
    rd = _node_depth(tree, tree.right_child[node])
    if ld > rd:
        return 1 + ld
    return 1 + rd



def mse_reduction(y, left_idx, right_idx):
    n_l = len(left_idx)
    n_r = len(right_idx)
    n = n_l + n_r
    if n == 0:
        return 0.0

    all_idx = []
    for i in range(n_l):
        all_idx.append(left_idx[i])
    for i in range(n_r):
        all_idx.append(right_idx[i])
    mse_parent = _mse_of(y, all_idx)
    mse_left = _mse_of(y, left_idx)
    mse_right = _mse_of(y, right_idx)
    weighted = (float(n_l) * mse_left + float(n_r) * mse_right) / float(n)
    return mse_parent - weighted






def best_split(X, y, indices):
    n = len(indices)
    result = []
    result.append(-1.0)  # feature
    result.append(0.0)   # value
    result.append(0.0)   # reduction
    if n < 2:
        return result
    n_features = len(X[0])
    best_red = 0.0
    best_feat = -1
    best_val = 0.0
    for f in range(n_features):

        vals = []
        for i in range(n):
            vals.append(X[indices[i]][f])

        sorted_idx = []
        for i in range(n):
            sorted_idx.append(i)
        for i in range(1, n):
            kv = vals[i]
            ki = sorted_idx[i]
            j = i - 1
            while j >= 0 and vals[j] > kv:
                vals[j + 1] = vals[j]
                sorted_idx[j + 1] = sorted_idx[j]
                j -= 1
            vals[j + 1] = kv
            sorted_idx[j + 1] = ki

        for s in range(1, n):
            if math.fabs(vals[s] - vals[s - 1]) < 1e-15:
                continue
            split_val = (vals[s - 1] + vals[s]) / 2.0
            left = []
            right = []
            for i in range(s):
                left.append(indices[sorted_idx[i]])
            for i in range(s, n):
                right.append(indices[sorted_idx[i]])
            red = mse_reduction(y, left, right)
            if red > best_red:
                best_red = red
                best_feat = f
                best_val = split_val
    result[0] = float(best_feat)
    result[1] = best_val
    result[2] = best_red
    return result






def build_tree(X, y, max_depth=5, min_samples=2):
    tree = RegressionTree()
    n = len(y)
    if n == 0:
        _ = _add_node(tree, -1, 0.0, -1, -1, 0.0)
        return tree
    indices = []
    for i in range(n):
        indices.append(i)
    _ = _build_recursive(tree, X, y, indices, 0, max_depth, min_samples)
    return tree





