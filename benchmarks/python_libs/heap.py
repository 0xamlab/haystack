"""Python equivalent of mojo/engine/heap.mojo (auto-generated)."""
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



def _sift_down_min(data, start, end):
    root = start
    while True:
        child = 2 * root + 1
        if child > end:
            break
        swap_idx = root
        if data[child] < data[swap_idx]:
            swap_idx = child
        if child + 1 <= end and data[child + 1] < data[swap_idx]:
            swap_idx = child + 1
        if swap_idx == root:
            break
        _swap(data, root, swap_idx)
        root = swap_idx



def _sift_up_min(data, pos):
    child = pos
    while child > 0:
        parent = (child - 1) // 2
        if data[child] < data[parent]:
            _swap(data, child, parent)
            child = parent
        else:
            break



def _sift_down_max(data, start, end):
    root = start
    while True:
        child = 2 * root + 1
        if child > end:
            break
        swap_idx = root
        if data[child] > data[swap_idx]:
            swap_idx = child
        if child + 1 <= end and data[child + 1] > data[swap_idx]:
            swap_idx = child + 1
        if swap_idx == root:
            break
        _swap(data, root, swap_idx)
        root = swap_idx



def _sift_up_max(data, pos):
    child = pos
    while child > 0:
        parent = (child - 1) // 2
        if data[child] > data[parent]:
            _swap(data, child, parent)
            child = parent
        else:
            break






def _simple_sort(data):
    n = len(data)
    for i in range(1, n):
        key = data[i]
        j = i - 1
        while j >= 0 and data[j] > key:
            data[j + 1] = data[j]
            j -= 1
        data[j + 1] = key






def heapify_min(data):
    n = len(data)
    start = (n - 2) // 2
    while start >= 0:
        _sift_down_min(data, start, n - 1)
        start -= 1






def heapify_max(data):
    n = len(data)
    start = (n - 2) // 2
    while start >= 0:
        _sift_down_max(data, start, n - 1)
        start -= 1






def heap_push_min(heap, value):
    heap.append(value)
    _sift_up_min(heap, len(heap) - 1)






def heap_pop_min(heap):
    n = len(heap)
    if n == 0:
        return 0.0
    if n == 1:
        return heap.pop()
    result = heap[0]
    heap[0] = heap[n - 1]
    _ = heap.pop()
    if len(heap) > 0:
        _sift_down_min(heap, 0, len(heap) - 1)
    return result






def heap_push_max(heap, value):
    heap.append(value)
    _sift_up_max(heap, len(heap) - 1)






def heap_pop_max(heap):
    n = len(heap)
    if n == 0:
        return 0.0
    if n == 1:
        return heap.pop()
    result = heap[0]
    heap[0] = heap[n - 1]
    _ = heap.pop()
    if len(heap) > 0:
        _sift_down_max(heap, 0, len(heap) - 1)
    return result






def heap_peek_min(heap):
    if len(heap) == 0:
        return 0.0
    return heap[0]






def heap_peek_max(heap):
    if len(heap) == 0:
        return 0.0
    return heap[0]






def k_smallest(data, k):
    n = len(data)
    kk = min(k, n)
    if kk <= 0:
        return []


    heap = []
    for i in range(kk):
        heap.append(data[i])
    heapify_max(heap)


    for i in range(kk, n):
        if data[i] < heap[0]:
            heap[0] = data[i]
            _sift_down_max(heap, 0, kk - 1)


    _simple_sort(heap)
    return heap






def k_largest(data, k):
    n = len(data)
    kk = min(k, n)
    if kk <= 0:
        return []


    heap = []
    for i in range(kk):
        heap.append(data[i])
    heapify_min(heap)


    for i in range(kk, n):
        if data[i] > heap[0]:
            heap[0] = data[i]
            _sift_down_min(heap, 0, kk - 1)


    _simple_sort(heap)
    return heap



def merge_sorted_lists(lists):
    k = len(lists)
    if k == 0:
        return []


    indices = []
    for i in range(k):
        indices.append(0)

    result = []
    total = 0
    for i in range(k):
        total += len(lists[i])

    for _ in range(total):
        best_val = 1e308
        best_list = -1
        for j in range(k):
            if indices[j] < len(lists[j]):
                if lists[j][indices[j]] < best_val:
                    best_val = lists[j][indices[j]]
                    best_list = j
        if best_list == -1:
            break
        result.append(best_val)
        indices[best_list] = indices[best_list] + 1

    return result






def running_median(data):
    result = []
    n = len(data)
    if n == 0:
        return result

    for i in range(n):

        prefix = []
        for j in range(i + 1):
            prefix.append(data[j])
        _simple_sort(prefix)

        plen = len(prefix)
        if plen % 2 == 1:
            result.append(prefix[plen // 2])
        else:
            result.append((prefix[plen // 2 - 1] + prefix[plen // 2]) / 2.0)

    return result






def is_min_heap(data):
    n = len(data)
    for i in range(n):
        left = 2 * i + 1
        right = 2 * i + 2
        if left < n and data[i] > data[left]:
            return False
        if right < n and data[i] > data[right]:
            return False
    return True
