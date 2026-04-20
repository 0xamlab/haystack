"""Python equivalent of mojo/engine/structs.containers.mojo (auto-generated)."""
import math
import random as _rng

class MinHeap:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('_data')
        self._data = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'MinHeap({vars(self)})'
    def size(self):
        return len(self._data)
    
    def peek(self):
        if len(self._data) == 0:
            return 0.0
        return self._data[0]
    
    def push(self, value):
        self._data.append(value)
        self._sift_up(len(self._data) - 1)
    
    def pop(self):
        n = len(self._data)
        if n == 0:
            return 0.0
        if n == 1:
            val = self._data[0]
            self._data = []
            return val
        result = self._data[0]
    
        self._data[0] = self._data[n - 1]
    
        new_data = []
        for i in range(n - 1):
            new_data.append(self._data[i])
        self._data = new_data
        self._sift_down(0)
        return result
    
    def _sift_up(self, idx):
        i = idx
        while i > 0:
            parent = (i - 1) // 2
            if self._data[i] < self._data[parent]:
                tmp = self._data[i]
                self._data[i] = self._data[parent]
                self._data[parent] = tmp
                i = parent
            else:
                break
    
    def _sift_down(self, idx):
        n = len(self._data)
        i = idx
        while True:
            left = 2 * i + 1
            right = 2 * i + 2
            smallest = i
            if left < n and self._data[left] < self._data[smallest]:
                smallest = left
            if right < n and self._data[right] < self._data[smallest]:
                smallest = right
            if smallest != i:
                tmp = self._data[i]
                self._data[i] = self._data[smallest]
                self._data[smallest] = tmp
                i = smallest
            else:
                break
    
    

class RingBuffer:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('capacity')
        self.capacity = _v0 if _v0 is not None else 0
        self._data = []
        self._capacity = 0
        self._head = None
        self._count = None
    def __repr__(self):
        return f'RingBuffer({vars(self)})'
    def push(self, value):
        self._data[self._head] = value
        self._head = (self._head + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1
    
    def get(self, index):
        if index < 0 or index >= self._count:
            return 0.0
    
        start = (self._head - self._count + self._capacity) % self._capacity
        actual = (start + index) % self._capacity
        return self._data[actual]
    
    def mean(self):
        if self._count == 0:
            return 0.0
        total = 0.0
        start = (self._head - self._count + self._capacity) % self._capacity
        for i in range(self._count):
            idx = (start + i) % self._capacity
            total += self._data[idx]
        return total / float(self._count)
    
    def is_full(self):
        return self._count == self._capacity
    
    def size(self):
        return self._count
    
    

class SortedList:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('_data')
        self._data = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'SortedList({vars(self)})'
    def insert(self, value):
        n = len(self._data)
    
        lo = 0
        hi = n
        while lo < hi:
            mid = (lo + hi) // 2
            if self._data[mid] < value:
                lo = mid + 1
            else:
                hi = mid
    
    
        new_data = []
        for i in range(lo):
            new_data.append(self._data[i])
        new_data.append(value)
        for i in range(lo, n):
            new_data.append(self._data[i])
        self._data = new_data
    
    def get(self, index):
        if index < 0 or index >= len(self._data):
            return 0.0
        return self._data[index]
    
    def median(self):
        n = len(self._data)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return self._data[n // 2]
        return (self._data[n // 2 - 1] + self._data[n // 2]) / 2.0
    
    def remove(self, index):
        n = len(self._data)
        if index < 0 or index >= n:
            return
        new_data = []
        for i in range(n):
            if i != index:
                new_data.append(self._data[i])
        self._data = new_data
    
    def size(self):
        return len(self._data)
    
    

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

def counter(data, bins):
    n = len(data)
    result = []
    if n == 0 or bins <= 0:
        for _ in range(bins):
            result.append(0)
        return result


    lo = data[0]
    hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]

    for _ in range(bins):
        result.append(0)

    span = hi - lo
    if span == 0.0:

        result[0] = n
        return result

    for i in range(n):
        bin_idx = int((data[i] - lo) / span * float(bins))
        if bin_idx >= bins:
            bin_idx = bins - 1
        if bin_idx < 0:
            bin_idx = 0
        result[bin_idx] = result[bin_idx] + 1

    return result






def unique(data):
    n = len(data)
    if n == 0:
        return []


    sorted_data = []
    for i in range(n):
        sorted_data.append(data[i])


    for i in range(1, n):
        key = sorted_data[i]
        j = i - 1
        while j >= 0 and sorted_data[j] > key:
            sorted_data[j + 1] = sorted_data[j]
            j -= 1
        sorted_data[j + 1] = key


    result = []
    result.append(sorted_data[0])
    for i in range(1, n):
        if sorted_data[i] != result[len(result) - 1]:
            result.append(sorted_data[i])

    return result
