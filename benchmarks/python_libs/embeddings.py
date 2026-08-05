"""Python equivalent of mojo/engine/embeddings.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.sys.info import simd_width_of
except Exception:
    pass

W = 1

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

def _min_len(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    return n



def _cosine_similarity_with_query_mag(query, candidate, query_mag):
    if query_mag <= 0.0:
        return 0.0
    dot = 0.0
    cand_sq = 0.0
    n = _min_len(query, candidate)
    for i in range(n):
        q = query[i]
        c = candidate[i]
        dot += q * c
        cand_sq += c * c
    if cand_sq <= 0.0:
        return 0.0
    return dot / (query_mag * math.sqrt(cand_sq))



def _insert_topk(best_scores, best_indices, candidate_score, candidate_index, max_count):
    if max_count <= 0:
        return

    if len(best_scores) < max_count:
        best_scores.append(candidate_score)
        best_indices.append(candidate_index)
        pos = len(best_scores) - 1
        while pos > 0 and best_scores[pos] > best_scores[pos - 1]:
            tmp_score = best_scores[pos - 1]
            best_scores[pos - 1] = best_scores[pos]
            best_scores[pos] = tmp_score
            tmp_idx = best_indices[pos - 1]
            best_indices[pos - 1] = best_indices[pos]
            best_indices[pos] = tmp_idx
            pos -= 1
        return

    tail = len(best_scores) - 1
    if candidate_score <= best_scores[tail]:
        return

    best_scores[tail] = candidate_score
    best_indices[tail] = candidate_index

    pos = tail
    while pos > 0 and best_scores[pos] > best_scores[pos - 1]:
        tmp_score = best_scores[pos - 1]
        best_scores[pos - 1] = best_scores[pos]
        best_scores[pos] = tmp_score
        tmp_idx = best_indices[pos - 1]
        best_indices[pos - 1] = best_indices[pos]
        best_indices[pos] = tmp_idx
        pos -= 1






def dot_product(a, b):
    n = _min_len(a, b)
    ap = a
    bp = b
    acc = (0.0)
    i = 0
    while i + W <= n:
        acc += ap[i] * bp[i]
        i += W
    s = acc
    while i < n:
        s += ap[i] * bp[i]
        i += 1
    return s



def dot_product_strict(a, b):
    if len(a) != len(b):
        raise Exception(
            "dot_product_strict: a has "
            + str(len(a))
            + " dimensions but b has "
            + str(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return dot_product(a, b)






def vector_magnitude(v):
    n = len(v)
    vp = v
    acc = (0.0)
    i = 0
    while i + W <= n:
        chunk = vp[i]
        acc += chunk * chunk
        i += W
    s = acc
    while i < n:
        s += vp[i] * vp[i]
        i += 1
    return math.sqrt(s)






def cosine_similarity(a, b):
    n = _min_len(a, b)
    ap = a
    bp = b
    dot_acc = (0.0)
    sqa_acc = (0.0)
    sqb_acc = (0.0)
    i = 0
    while i + W <= n:
        av = ap[i]
        bv = bp[i]
        dot_acc += av * bv
        sqa_acc += av * av
        sqb_acc += bv * bv
        i += W
    dot = dot_acc
    sq_a = sqa_acc
    sq_b = sqb_acc
    while i < n:
        av = ap[i]
        bv = bp[i]
        dot += av * bv
        sq_a += av * av
        sq_b += bv * bv
        i += 1
    if sq_a <= 0.0 or sq_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(sq_a) * math.sqrt(sq_b))



def cosine_similarity_strict(a, b):
    if len(a) != len(b):
        raise Exception(
            "cosine_similarity_strict: a has "
            + str(len(a))
            + " dimensions but b has "
            + str(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return cosine_similarity(a, b)






def euclidean_distance(a, b):
    n = _min_len(a, b)
    ap = a
    bp = b
    acc = (0.0)
    i = 0
    while i + W <= n:
        d = ap[i] - bp[i]
        acc += d * d
        i += W
    s = acc
    while i < n:
        d = ap[i] - bp[i]
        s += d * d
        i += 1
    return math.sqrt(s)



def euclidean_distance_strict(a, b):
    if len(a) != len(b):
        raise Exception(
            "euclidean_distance_strict: a has "
            + str(len(a))
            + " dimensions but b has "
            + str(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return euclidean_distance(a, b)






def manhattan_distance(a, b):
    n = _min_len(a, b)
    ap = a
    bp = b
    acc = (0.0)
    i = 0
    while i + W <= n:
        acc += abs(ap[i] - bp[i])
        i += W
    s = acc
    while i < n:
        d = ap[i] - bp[i]
        if d < 0.0:
            d = -d
        s += d
        i += 1
    return s



def manhattan_distance_strict(a, b):
    if len(a) != len(b):
        raise Exception(
            "manhattan_distance_strict: a has "
            + str(len(a))
            + " dimensions but b has "
            + str(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return manhattan_distance(a, b)






def normalize_vector(v):
    n = len(v)
    mag = vector_magnitude(v)
    result = []
    if mag == 0.0:
        for i in range(n):
            result.append(0.0)
        return result
    inv_mag = 1.0 / mag
    for i in range(n):
        result.append(v[i] * inv_mag)
    return result






def centroid(vectors):
    n = len(vectors)
    if n == 0:
        return []
    dim = len(vectors[0])
    for i in range(1, n):
        if len(vectors[i]) != dim:
            raise Exception(
                "centroid: vectors[0] has "
                + str(dim)
                + " dimensions but vectors["
                + str(i)
                + "] has "
                + str(len(vectors[i]))
                + "; all vectors must share the same dimensionality"
            )
    result = vectors[0].copy()
    for i in range(1, n):
        for d in range(dim):
            result[d] += vectors[i][d]
    inv_n = 1.0 / float(n)
    for d in range(dim):
        result[d] *= inv_n
    return result






def nearest_neighbor(query, candidates):
    n_candidates = len(candidates)
    if n_candidates == 0:
        return 0
    query_mag = vector_magnitude(query)
    best_idx = 0
    best_sim = _cosine_similarity_with_query_mag(query, candidates[0], query_mag)
    for i in range(1, n_candidates):
        sim = _cosine_similarity_with_query_mag(query, candidates[i], query_mag)
        if sim > best_sim:
            best_sim = sim
            best_idx = i
    return best_idx



def nearest_neighbor_strict(query, candidates):
    qlen = len(query)
    for i in range(len(candidates)):
        if len(candidates[i]) != qlen:
            raise Exception(
                "nearest_neighbor_strict: query has "
                + str(qlen)
                + " dimensions but candidates["
                + str(i)
                + "] has "
                + str(len(candidates[i]))
                + " dimensions; every candidate must share the query's"
                " dimensionality"
            )
    return nearest_neighbor(query, candidates)






def k_nearest_neighbors(query, candidates, k):
    count = k
    n_candidates = len(candidates)
    if count <= 0 or n_candidates == 0:
        return []
    if count > n_candidates:
        count = n_candidates
    query_mag = vector_magnitude(query)

    if count == n_candidates:
        all_scores = []
        all_indices = []
        for i in range(n_candidates):
            all_scores.append(
                _cosine_similarity_with_query_mag(query, candidates[i], query_mag)
            )
            all_indices.append(i)
        for i in range(1, count):
            key_score = all_scores[i]
            key_idx = all_indices[i]
            j = i - 1
            while j >= 0 and all_scores[j] < key_score:
                all_scores[j + 1] = all_scores[j]
                all_indices[j + 1] = all_indices[j]
                j -= 1
            all_scores[j + 1] = key_score
            all_indices[j + 1] = key_idx
        return all_indices

    best_scores = []
    best_indices = []
    for i in range(n_candidates):
        sim = _cosine_similarity_with_query_mag(query, candidates[i], query_mag)
        _insert_topk(best_scores, best_indices, sim, i, count)
    return best_indices



def k_nearest_neighbors_strict(query, candidates, k):
    qlen = len(query)
    for i in range(len(candidates)):
        if len(candidates[i]) != qlen:
            raise Exception(
                "k_nearest_neighbors_strict: query has "
                + str(qlen)
                + " dimensions but candidates["
                + str(i)
                + "] has "
                + str(len(candidates[i]))
                + " dimensions; every candidate must share the query's"
                " dimensionality"
            )
    return k_nearest_neighbors(query, candidates, k)






def cosine_similarity_matrix(vectors):
    n = len(vectors)
    norms = []
    for i in range(n):
        norms.append(vector_magnitude(vectors[i]))

    zero_row = []
    for _ in range(n):
        zero_row.append(0.0)

    matrix = []
    for _ in range(n):
        matrix.append(zero_row.copy())

    for i in range(n):
        norm_i = norms[i]
        if norm_i <= 0.0:
            continue
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            norm_j = norms[j]
            if norm_j <= 0.0:
                continue
            dot = 0.0
            limit = _min_len(vectors[i], vectors[j])
            for k in range(limit):
                dot += vectors[i][k] * vectors[j][k]
            sim = dot / (norm_i * norm_j)
            matrix[i][j] = sim
            matrix[j][i] = sim
    return matrix



def cosine_similarity_matrix_strict(vectors):
    n = len(vectors)
    if n > 0:
        dim = len(vectors[0])
        for i in range(1, n):
            if len(vectors[i]) != dim:
                raise Exception(
                    "cosine_similarity_matrix_strict: vectors[0] has "
                    + str(dim)
                    + " dimensions but vectors["
                    + str(i)
                    + "] has "
                    + str(len(vectors[i]))
                    + " dimensions; all vectors must share the same"
                    " dimensionality"
                )
    return cosine_similarity_matrix(vectors)






def vector_add(a, b):
    n = _min_len(a, b)
    result = []
    for i in range(n):
        result.append(a[i] + b[i])
    return result



def vector_add_strict(a, b):
    if len(a) != len(b):
        raise Exception(
            "vector_add_strict: a has "
            + str(len(a))
            + " dimensions but b has "
            + str(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return vector_add(a, b)






def vector_scale(v, s):
    n = len(v)
    result = []
    for i in range(n):
        result.append(v[i] * s)
    return result
