"""Python equivalent of mojo/engine/combinatorial.mojo (auto-generated)."""
import math
import random as _rng

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

def knapsack_01(weights, values, capacity):
    n = len(weights)
    if n == 0 or capacity <= 0:
        return []


    dp = []
    for _ in range((n + 1) * (capacity + 1)):
        dp.append(0)

    for i in range(1, n + 1):
        for w in range(capacity + 1):

            dp[i * (capacity + 1) + w] = dp[(i - 1) * (capacity + 1) + w]

            if weights[i - 1] <= w:
                with_item = dp[(i - 1) * (capacity + 1) + (w - weights[i - 1])] + values[i - 1]
                if with_item > dp[i * (capacity + 1) + w]:
                    dp[i * (capacity + 1) + w] = with_item


    selected = []
    w = capacity
    i = n
    while i > 0 and w > 0:
        if dp[i * (capacity + 1) + w] != dp[(i - 1) * (capacity + 1) + w]:
            selected.append(i - 1)
            w -= weights[i - 1]
        i -= 1


    rev = []
    k = len(selected) - 1
    while k >= 0:
        rev.append(selected[k])
        k -= 1
    return rev






def knapsack_01_value(weights, values, capacity):
    n = len(weights)
    if n == 0 or capacity <= 0:
        return 0

    dp = []
    for _ in range(capacity + 1):
        dp.append(0)

    for i in range(n):
        w = capacity
        while w >= weights[i]:
            with_item = dp[w - weights[i]] + values[i]
            if with_item > dp[w]:
                dp[w] = with_item
            w -= 1

    return dp[capacity]






def tsp_greedy(distances):
    n = len(distances)
    if n == 0:
        return []
    if n == 1:
        tour = []
        tour.append(0)
        tour.append(0)
        return tour

    visited = []
    for _ in range(n):
        visited.append(False)

    tour = []
    tour.append(0)
    visited[0] = True
    current = 0

    for _ in range(n - 1):
        best_next = -1
        best_dist = 1e308
        for j in range(n):
            if not visited[j] and distances[current][j] < best_dist:
                best_dist = distances[current][j]
                best_next = j
        tour.append(best_next)
        visited[best_next] = True
        current = best_next

    tour.append(0)  # Return to start
    return tour






def tsp_tour_length(distances, tour):
    total = 0.0
    n = len(tour)
    for i in range(n - 1):
        total += distances[tour[i]][tour[i + 1]]
    return total






def bin_packing_first_fit(items, bin_capacity):
    n = len(items)
    if n == 0:
        return 0
    bins = []  # remaining capacity per bin
    for i in range(n):
        placed = False
        for b in range(len(bins)):
            if bins[b] >= items[i]:
                bins[b] -= items[i]
                placed = True
                break
        if not placed:
            bins.append(bin_capacity - items[i])
    return len(bins)






def bin_packing_first_fit_decreasing(items, bin_capacity):
    n = len(items)
    if n == 0:
        return 0

    sorted_items = []
    for i in range(n):
        sorted_items.append(items[i])
    for i in range(1, n):
        key = sorted_items[i]
        j = i - 1
        while j >= 0 and sorted_items[j] < key:
            sorted_items[j + 1] = sorted_items[j]
            j -= 1
        sorted_items[j + 1] = key
    return bin_packing_first_fit(sorted_items, bin_capacity)






def assignment_greedy(cost_matrix):
    n = len(cost_matrix)
    if n == 0:
        return []

    m = len(cost_matrix[0])
    col_used = []
    for _ in range(m):
        col_used.append(False)

    assignment = []
    for i in range(n):
        best_col = -1
        best_cost = 1e308
        for j in range(m):
            if not col_used[j] and cost_matrix[i][j] < best_cost:
                best_cost = cost_matrix[i][j]
                best_col = j
        assignment.append(best_col)
        if best_col >= 0:
            col_used[best_col] = True
    return assignment






def max_subarray_sum(data):
    n = len(data)
    if n == 0:
        return 0.0
    best = data[0]
    current = data[0]
    for i in range(1, n):
        if current + data[i] > data[i]:
            current = current + data[i]
        else:
            current = data[i]
        if current > best:
            best = current
    return best






def longest_increasing_subsequence(data):
    n = len(data)
    if n == 0:
        return 0

    tails = []
    for i in range(n):
        x = data[i]

        lo = 0
        hi = len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if tails[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        if lo == len(tails):
            tails.append(x)
        else:
            tails[lo] = x
    return len(tails)






def coin_change(coins, amount):
    if amount == 0:
        return 0
    if amount < 0 or len(coins) == 0:
        return -1

    inf = amount + 1
    dp = []
    for _ in range(amount + 1):
        dp.append(inf)
    dp[0] = 0

    for i in range(1, amount + 1):
        for j in range(len(coins)):
            if coins[j] <= i:
                prev = dp[i - coins[j]]
                if prev + 1 < dp[i]:
                    dp[i] = prev + 1

    if dp[amount] > amount:
        return -1
    return dp[amount]
