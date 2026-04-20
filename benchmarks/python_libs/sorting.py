"""Python equivalent of mojo/engine/sorting.mojo (auto-generated)."""
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

def _swap(data, i, j):
    tmp = data[i]
    data[i] = data[j]
    data[j] = tmp






def _lomuto_partition(data, lo, hi):
    pivot = data[hi]
    i = lo
    for j in range(lo, hi):
        if data[j] <= pivot:
            _swap(data, i, j)
            i += 1
    _swap(data, i, hi)
    return i



def _quicksort_impl(data, lo, hi):
    if lo < hi:
        p = _lomuto_partition(data, lo, hi)
        _quicksort_impl(data, lo, p - 1)
        _quicksort_impl(data, p + 1, hi)



def _merge(a, b):
    result = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    while i < len(a):
        result.append(a[i])
        i += 1
    while j < len(b):
        result.append(b[j])
        j += 1
    return result



def _mergesort_impl(data):
    if len(data) <= 1:
        copy = []
        for i in range(len(data)):
            copy.append(data[i])
        return copy
    mid = len(data) // 2
    left = []
    right = []
    for i in range(mid):
        left.append(data[i])
    for i in range(mid, len(data)):
        right.append(data[i])
    sorted_left = _mergesort_impl(left)
    sorted_right = _mergesort_impl(right)
    return _merge(sorted_left, sorted_right)



def _sift_down(data, start, end):
    root = start
    while root * 2 + 1 <= end:
        child = root * 2 + 1
        swap_idx = root
        if data[swap_idx] < data[child]:
            swap_idx = child
        if child + 1 <= end and data[swap_idx] < data[child + 1]:
            swap_idx = child + 1
        if swap_idx == root:
            return
        _swap(data, root, swap_idx)
        root = swap_idx



def quicksort(data):
    result = []
    for i in range(len(data)):
        result.append(data[i])
    if len(result) > 1:
        _quicksort_impl(result, 0, len(result) - 1)
    return result






def mergesort(data):
    return _mergesort_impl(data)






def heapsort(data):
    result = []
    for i in range(len(data)):
        result.append(data[i])
    n = len(result)
    if n <= 1:
        return result

    start = (n - 2) // 2
    while start >= 0:
        _sift_down(result, start, n - 1)
        start -= 1

    end = n - 1
    while end > 0:
        _swap(result, 0, end)
        end -= 1
        _sift_down(result, 0, end)
    return result






def insertion_sort(data):
    result = []
    for i in range(len(data)):
        result.append(data[i])
    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result






def selection_sort(data):
    result = []
    for i in range(len(data)):
        result.append(data[i])
    n = len(result)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if result[j] < result[min_idx]:
                min_idx = j
        if min_idx != i:
            _swap(result, i, min_idx)
    return result






def bubble_sort(data):
    result = []
    for i in range(len(data)):
        result.append(data[i])
    n = len(result)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if result[j] > result[j + 1]:
                _swap(result, j, j + 1)
                swapped = True
        if not swapped:
            break
    return result






def counting_sort_int(data):
    if len(data) == 0:
        return []

    max_val = data[0]
    for i in range(1, len(data)):
        if data[i] > max_val:
            max_val = data[i]

    counts = []
    for i in range(max_val + 1):
        counts.append(0)
    for i in range(len(data)):
        counts[data[i]] += 1

    result = []
    for i in range(len(counts)):
        for _ in range(counts[i]):
            result.append(i)
    return result






def is_sorted(data):
    for i in range(1, len(data)):
        if data[i] < data[i - 1]:
            return False
    return True






def reverse_list(data):
    result = []
    i = len(data) - 1
    while i >= 0:
        result.append(data[i])
        i -= 1
    return result






def nth_smallest(data, n):
    sorted_data = quicksort(data)
    return sorted_data[n]
