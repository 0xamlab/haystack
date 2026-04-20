"""Python equivalent of mojo/engine/time_zone.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
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

def _normalize_time(total_minutes):
    m = total_minutes % 1440
    if m < 0:
        m += 1440
    result = []
    result.append(m // 60)
    result.append(m % 60)
    return result






def utc_offset(zone_name):
    if zone_name == "UTC" or zone_name == "GMT":
        return 0.0
    if zone_name == "EST":
        return -5.0
    if zone_name == "CST":
        return -6.0
    if zone_name == "MST":
        return -7.0
    if zone_name == "PST":
        return -8.0
    if zone_name == "CET":
        return 1.0
    if zone_name == "EET":
        return 2.0
    if zone_name == "JST":
        return 9.0
    if zone_name == "IST":
        return 5.5
    if zone_name == "AEST":
        return 10.0
    return 0.0






def is_valid_zone(name):
    if name == "UTC":
        return True
    if name == "GMT":
        return True
    if name == "EST":
        return True
    if name == "CST":
        return True
    if name == "MST":
        return True
    if name == "PST":
        return True
    if name == "CET":
        return True
    if name == "EET":
        return True
    if name == "JST":
        return True
    if name == "IST":
        return True
    if name == "AEST":
        return True
    return False






def is_dst(month, zone_name):
    if zone_name == "EST" or zone_name == "CST" or zone_name == "MST" or zone_name == "PST":
        return month >= 3 and month <= 11
    if zone_name == "CET" or zone_name == "EET":
        return month >= 3 and month <= 10
    return False






def effective_offset(zone_name, month):
    base = utc_offset(zone_name)
    if is_dst(month, zone_name):
        return base + 1.0
    return base






def time_difference(zone1, zone2):
    return utc_offset(zone2) - utc_offset(zone1)






def format_offset(offset_hours):
    sign = "+"
    h = offset_hours
    if h < 0.0:
        sign = "-"
        h = -h
    hours_int = int(h)
    frac = h - float(hours_int)
    minutes_int = int(frac * 60.0 + 0.5)

    h_str = ""
    if hours_int < 10:
        h_str = "0" + str(hours_int)
    else:
        h_str = str(hours_int)

    m_str = ""
    if minutes_int < 10:
        m_str = "0" + str(minutes_int)
    else:
        m_str = str(minutes_int)

    return sign + h_str + ":" + m_str






def convert_time(hour, minute, from_zone, to_zone):
    from_off = utc_offset(from_zone)
    to_off = utc_offset(to_zone)
    diff = to_off - from_off
    total_minutes = hour * 60 + minute + int(diff * 60.0)
    return _normalize_time(total_minutes)






def local_to_utc(hour, minute, zone):
    return convert_time(hour, minute, zone, "UTC")






def utc_to_local(hour, minute, zone):
    return convert_time(hour, minute, "UTC", zone)






def overlap_hours(zone1, zone2, work_start=9, work_end=17):
    off1 = utc_offset(zone1)
    off2 = utc_offset(zone2)


    start1_utc = work_start - int(off1)
    end1_utc = work_end - int(off1)
    start2_utc = work_start - int(off2)
    end2_utc = work_end - int(off2)


    start1_utc = start1_utc % 24
    if start1_utc < 0:
        start1_utc += 24
    end1_utc = end1_utc % 24
    if end1_utc < 0:
        end1_utc += 24
    start2_utc = start2_utc % 24
    if start2_utc < 0:
        start2_utc += 24
    end2_utc = end2_utc % 24
    if end2_utc < 0:
        end2_utc += 24


    s1 = start1_utc
    e1 = end1_utc
    s2 = start2_utc
    e2 = end2_utc


    if e1 <= s1:
        e1 += 24
    if e2 <= s2:
        e2 += 24

    overlap_start = s1
    if s2 > overlap_start:
        overlap_start = s2
    overlap_end = e1
    if e2 < overlap_end:
        overlap_end = e2

    result = overlap_end - overlap_start
    if result < 0:
        result = 0
    return result
