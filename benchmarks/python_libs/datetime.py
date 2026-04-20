"""Python equivalent of mojo/engine/datetime.mojo (auto-generated)."""
import math
import random as _rng

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_SECONDS_PER_DAY = 86400

class Timestamp:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('epoch_sec')
        self.epoch_sec = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('nano')
        self.nano = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'Timestamp({vars(self)})'
    def total_ms(self):
        return self.epoch_sec * 1000 + self.nano // 1_000_000
    
    def total_us(self):
        return self.epoch_sec * 1_000_000 + self.nano // 1000
    
    

class DateComponents:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('yr')
        self.yr = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('mo')
        self.mo = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('dy')
        self.dy = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('hr')
        self.hr = _v3 if _v3 is not None else 0
        _v4 = args[4] if 4 < len(args) else kwargs.get('mn')
        self.mn = _v4 if _v4 is not None else 0
        _v5 = args[5] if 5 < len(args) else kwargs.get('sc')
        self.sc = _v5 if _v5 is not None else 0
    def __repr__(self):
        return f'DateComponents({vars(self)})'

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

def _days_in_month(y, m):
    if m == 2:
        if is_leap_year(y):
            return 29
        return 28
    if m == 4 or m == 6 or m == 9 or m == 11:
        return 30
    return 31








def _civil_from_epoch(epoch):
    s = epoch
    sign = 1
    if s < 0:
        sign = -1
        s = -s

    day_seconds = 0
    z = 0
    if sign < 0:

        z = -((s + _SECONDS_PER_DAY - 1) // _SECONDS_PER_DAY)
        remainder = s % _SECONDS_PER_DAY
        if remainder == 0:
            day_seconds = 0
            z = -(s // _SECONDS_PER_DAY)
        else:
            day_seconds = _SECONDS_PER_DAY - remainder
    else:
        z = s // _SECONDS_PER_DAY
        day_seconds = s % _SECONDS_PER_DAY

    h = day_seconds // _SECONDS_PER_HOUR
    m = (day_seconds % _SECONDS_PER_HOUR) // _SECONDS_PER_MINUTE
    sec = day_seconds % _SECONDS_PER_MINUTE



    z = z + 719468  # shift epoch from 1970-01-01 to 0000-03-01
    era = 0
    if z >= 0:
        era = z // 146097
    else:
        era = (z - 146096) // 146097
    doe = z - era * 146097  # day of era [0, 146096]
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365  # year of era
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)  # day of year [0, 365]
    mp = (5 * doy + 2) // 153  # month index [0, 11]
    d = doy - (153 * mp + 2) // 5 + 1  # day [1, 31]
    mn = 0
    if mp < 10:
        mn = mp + 3
    else:
        mn = mp - 9
    if mn <= 2:
        y = y + 1

    return DateComponents(y, mn, d, h, m, sec)






def _pad2(v):
    if v < 10:
        return "0" + str(v)
    return str(v)



def _pad4(v):
    if v < 10:
        return "000" + str(v)
    if v < 100:
        return "00" + str(v)
    if v < 1000:
        return "0" + str(v)
    return str(v)



def _days_from_civil(y_in, m, d):
    y = y_in
    if m <= 2:
        y = y - 1
    era = 0
    if y >= 0:
        era = y // 400
    else:
        era = (y - 399) // 400
    yoe = y - era * 400  # year of era [0, 399]
    doy = 0
    if m > 2:
        doy = (153 * (m - 3) + 2) // 5 + d - 1
    else:
        doy = (153 * (m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468



def _parse_int_at(s, start, length):
    bs = s.encode('utf-8')
    result = 0
    for i in range(length):
        idx = start + i
        if idx < len(s):
            c = int(bs[idx])
            if c >= 48 and c <= 57:
                result = result * 10 + (c - 48)
    return result



def _ms_frac(ms):
    d1 = ms // 100
    d2 = (ms // 10) % 10
    d3 = ms % 10
    if d3 != 0:
        return str(d1) + str(d2) + str(d3)
    if d2 != 0:
        return str(d1) + str(d2)
    return str(d1)






def now_epoch():
    from std.python import Python
    time_mod = Python.import_module("time")
    return int(py=time_mod.time())






def is_leap_year(y):
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)






def year(epoch):
    result = _civil_from_epoch(epoch)
    return result.yr



def month(epoch):
    result = _civil_from_epoch(epoch)
    return result.mo



def day(epoch):
    result = _civil_from_epoch(epoch)
    return result.dy



def hour(epoch):
    result = _civil_from_epoch(epoch)
    return result.hr



def minute(epoch):
    result = _civil_from_epoch(epoch)
    return result.mn



def second(epoch):
    result = _civil_from_epoch(epoch)
    return result.sc






def epoch_to_iso(epoch):
    parts = _civil_from_epoch(epoch)
    return (
        _pad4(parts.yr) + "-" + _pad2(parts.mo) + "-" + _pad2(parts.dy)
        + "T"
        + _pad2(parts.hr) + ":" + _pad2(parts.mn) + ":" + _pad2(parts.sc)
        + "Z"
    )







def iso_to_epoch(iso):
    n = len(iso)

    if n < 20:
        return 0

    y = _parse_int_at(iso, 0, 4)
    m = _parse_int_at(iso, 5, 2)
    d = _parse_int_at(iso, 8, 2)
    hh = _parse_int_at(iso, 11, 2)
    mm = _parse_int_at(iso, 14, 2)
    ss = _parse_int_at(iso, 17, 2)

    days = _days_from_civil(y, m, d)
    return days * _SECONDS_PER_DAY + hh * _SECONDS_PER_HOUR + mm * _SECONDS_PER_MINUTE + ss






def format_duration_ms(ms):
    if ms < 0:
        return "-" + format_duration_ms(-ms)
    if ms == 0:
        return "0ms"

    total_sec = ms // 1000
    rem_ms = ms % 1000

    if total_sec == 0:
        return str(ms) + "ms"

    hours = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60

    result = str("")

    if hours > 0:
        result += str(hours) + "h"
        if mins > 0 or secs > 0:
            result += " " + str(mins) + "m"
        if secs > 0:
            result += " " + str(secs) + "s"
        return result

    if mins > 0:
        result += str(mins) + "m"
        if secs > 0:
            result += " " + str(secs) + "s"
        elif rem_ms > 0:
            result += " 0." + _ms_frac(rem_ms) + "s"
        return result


    if rem_ms > 0:
        frac = _ms_frac(rem_ms)
        return str(secs) + "." + frac + "s"
    else:
        return str(secs) + "s"



def days_between(epoch1, epoch2):
    diff = epoch2 - epoch1
    if diff < 0:
        diff = -diff
    return diff // _SECONDS_PER_DAY



def add_days(epoch, days):
    return epoch + days * _SECONDS_PER_DAY






def day_of_week(epoch):
    days = epoch // _SECONDS_PER_DAY

    dow = (days + 3) % 7
    if dow < 0:
        dow += 7
    return dow
