"""Python equivalent of mojo/engine/survival.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass

class SurvivalPoint:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('time')
        self.time = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('survival')
        self.survival = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('at_risk')
        self.at_risk = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('events')
        self.events = _v3 if _v3 is not None else 0
    def __repr__(self):
        return f'SurvivalPoint({vars(self)})'

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

def _sort_indices(times):
    n = len(times)
    idx = []
    for i in range(n):
        idx.append(i)

    for i in range(1, n):
        key = idx[i]
        key_val = times[key]
        j = i - 1
        while j >= 0 and times[idx[j]] > key_val:
            idx[j + 1] = idx[j]
            j -= 1
        idx[j + 1] = key
    return idx






def kaplan_meier(times, events):
    n = len(times)
    result = []
    result.append(SurvivalPoint(0.0, 1.0, n, 0))
    if n == 0:
        return result

    idx = _sort_indices(times)
    surv = 1.0
    at_risk = n
    i = 0

    while i < n:
        t = times[idx[i]]
        d = 0
        c = 0

        while i < n and times[idx[i]] == t:
            if events[idx[i]]:
                d += 1
            else:
                c += 1
            i += 1
        if d > 0:
            surv *= (1.0 - float(d) / float(at_risk))
            result.append(SurvivalPoint(t, surv, at_risk, d))
        at_risk -= (d + c)
    return result






def nelson_aalen(times, events):
    n = len(times)
    result = []
    row0 = []
    row0.append(0.0); row0.append(0.0)
    result.append(row0)
    if n == 0:
        return result

    idx = _sort_indices(times)
    cum_h = 0.0
    at_risk = n
    i = 0

    while i < n:
        t = times[idx[i]]
        d = 0
        c = 0
        while i < n and times[idx[i]] == t:
            if events[idx[i]]:
                d += 1
            else:
                c += 1
            i += 1
        if d > 0:
            cum_h += float(d) / float(at_risk)
            row = []
            row.append(t); row.append(cum_h)
            result.append(row)
        at_risk -= (d + c)
    return result






def log_rank_statistic(times1, events1, times2, events2):

    all_times = []
    for i in range(len(times1)):
        if events1[i]:
            t = times1[i]
            found = False
            for j in range(len(all_times)):
                if all_times[j] == t:
                    found = True
                    break
            if not found:
                all_times.append(t)
    for i in range(len(times2)):
        if events2[i]:
            t = times2[i]
            found = False
            for j in range(len(all_times)):
                if all_times[j] == t:
                    found = True
                    break
            if not found:
                all_times.append(t)


    for i in range(1, len(all_times)):
        key = all_times[i]
        j = i - 1
        while j >= 0 and all_times[j] > key:
            all_times[j + 1] = all_times[j]
            j -= 1
        all_times[j + 1] = key

    obs_minus_exp = 0.0
    variance = 0.0

    for ti in range(len(all_times)):
        t = all_times[ti]

        n1 = 0
        d1 = 0
        for j in range(len(times1)):
            if times1[j] >= t:
                n1 += 1
            if times1[j] == t and events1[j]:
                d1 += 1
        n2 = 0
        d2 = 0
        for j in range(len(times2)):
            if times2[j] >= t:
                n2 += 1
            if times2[j] == t and events2[j]:
                d2 += 1

        n_total = n1 + n2
        d_total = d1 + d2
        if n_total == 0:
            continue
        e1 = float(n1) * float(d_total) / float(n_total)
        obs_minus_exp += float(d1) - e1

        if n_total > 1:
            num = float(n1) * float(n2) * float(d_total) * float(n_total - d_total)
            den = float(n_total) * float(n_total) * float(n_total - 1)
            variance += num / den

    if variance <= 0.0:
        return 0.0
    return (obs_minus_exp * obs_minus_exp) / variance






def hazard_rate(times, events, bandwidth):
    n = len(times)
    idx = _sort_indices(times)

    utimes = []
    for i in range(n):
        if events[idx[i]]:
            t = times[idx[i]]
            found = False
            for j in range(len(utimes)):
                if utimes[j] == t:
                    found = True
                    break
            if not found:
                utimes.append(t)

    result = []
    for ti in range(len(utimes)):
        t = utimes[ti]
        num = 0.0
        den = 0.0
        for j in range(n):
            u = (t - times[j]) / bandwidth
            if math.fabs(u) <= 1.0:
                k = 0.75 * (1.0 - u * u)
                if events[j]:
                    num += k
                den += k
        h = 0.0
        if den > 0.0:
            h = num / (den * bandwidth)
        row = []
        row.append(t); row.append(h)
        result.append(row)
    return result






def life_table(times, events, intervals):
    n_int = len(intervals)
    result = []
    surv = 1.0
    n_total = len(times)

    for k in range(n_int):
        lo = intervals[k]
        hi = 1e30
        if k + 1 < n_int:
            hi = intervals[k + 1]

        n_risk = 0
        n_event = 0
        for j in range(n_total):
            if times[j] >= lo:
                n_risk += 1
        for j in range(n_total):
            if times[j] >= lo and times[j] < hi and events[j]:
                n_event += 1

        if n_risk > 0 and n_event > 0:
            surv *= (1.0 - float(n_event) / float(n_risk))

        row = []
        row.append(lo)
        row.append(float(n_risk))
        row.append(float(n_event))
        row.append(surv)
        result.append(row)
    return result





