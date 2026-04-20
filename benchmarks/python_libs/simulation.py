"""Python equivalent of mojo/engine/simulation.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass

class Event:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('time')
        self.time = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('event_type')
        self.event_type = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('entity_id')
        self.entity_id = _v2 if _v2 is not None else 0
    def __repr__(self):
        return f'Event({vars(self)})'

class SimState:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('clock')
        self.clock = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('ev_time')
        self.ev_time = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('ev_type')
        self.ev_type = _v2 if _v2 is not None else []
        _v3 = args[3] if 3 < len(args) else kwargs.get('ev_id')
        self.ev_id = _v3 if _v3 is not None else []
        _v4 = args[4] if 4 < len(args) else kwargs.get('comp_time')
        self.comp_time = _v4 if _v4 is not None else []
        _v5 = args[5] if 5 < len(args) else kwargs.get('comp_type')
        self.comp_type = _v5 if _v5 is not None else []
        _v6 = args[6] if 6 < len(args) else kwargs.get('comp_id')
        self.comp_id = _v6 if _v6 is not None else []
        _v7 = args[7] if 7 < len(args) else kwargs.get('next_id')
        self.next_id = _v7 if _v7 is not None else 0
    def __repr__(self):
        return f'SimState({vars(self)})'

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

def _remove_event_at(state, idx):
    n = len(state.ev_time)
    new_t = []
    new_ty = []
    new_id = []
    for i in range(n):
        if i != idx:
            new_t.append(state.ev_time[i])
            new_ty.append(state.ev_type[i])
            new_id.append(state.ev_id[i])
    state.ev_time = new_t
    state.ev_type = new_ty
    state.ev_id = new_id






def _lcg_next(seed):
    return (1103515245 * seed + 12345) & 0x7FFFFFFF



def _lcg_float(seed):
    v = float(seed) / float(0x7FFFFFFF)
    if v <= 0.0:
        v = 1e-10
    if v >= 1.0:
        v = 1.0 - 1e-10
    return v






def create_sim():
    return SimState()






def mm1_simulate(arrival_rate, service_rate, n_customers):
    seed = 42
    total_wait = 0.0
    total_system = 0.0
    total_service = 0.0
    clock = 0.0
    server_free_at = 0.0

    for _ in range(n_customers):

        seed = _lcg_next(seed)
        u1 = _lcg_float(seed)
        inter_arrival = -math.log(u1) / arrival_rate
        clock += inter_arrival


        seed = _lcg_next(seed)
        u2 = _lcg_float(seed)
        service_time = -math.log(u2) / service_rate


        start_service = 0.0
        if clock >= server_free_at:
            start_service = clock
        else:
            start_service = server_free_at
        wait_time = start_service - clock
        system_time = wait_time + service_time
        server_free_at = start_service + service_time

        total_wait += wait_time
        total_system += system_time
        total_service += service_time

    n = float(n_customers)
    avg_wait = total_wait / n
    avg_system = total_system / n
    utilization = 0.0
    if server_free_at > 0.0:
        utilization = total_service / server_free_at
    else:
        utilization = 0.0

    result = []
    result.append(avg_wait)
    result.append(avg_system)
    result.append(utilization)
    return result
