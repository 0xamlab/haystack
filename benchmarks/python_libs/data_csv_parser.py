"""Python equivalent of mojo/engine/data.csv_parser.mojo (auto-generated)."""
import math
import random as _rng

class CSVRow:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('fields')
        self.fields = _v0 if _v0 is not None else []
        self.n_fields = 0
    def __repr__(self):
        return f'CSVRow({vars(self)})'

class CSVResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('headers')
        self.headers = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('rows')
        self.rows = _v1 if _v1 is not None else []
    def __repr__(self):
        return f'CSVResult({vars(self)})'

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

def _try_parse_float(s):
    try:
        return atof(s)
    except:
        return 0.0



def _can_parse_float(s):
    if len(s) == 0:
        return False
    bs = s.encode('utf-8')
    start = 0
    while start < len(s) and (bs[start] == _SPACE or bs[start] == _TAB):
        start += 1
    if start >= len(s):
        return False
    if bs[start] == int(45) or bs[start] == int(43):
        start += 1
    if start >= len(s):
        return False
    has_digit = False
    has_dot = False
    i = start
    while i < len(s):
        c = bs[i]
        if c >= int(48) and c <= int(57):
            has_digit = True
        elif c == int(46) and not has_dot:
            has_dot = True
        elif c == int(101) or c == int(69):
            i += 1
            if i < len(s) and (bs[i] == int(45) or bs[i] == int(43)):
                i += 1
            if i >= len(s) or not (bs[i] >= int(48) and bs[i] <= int(57)):
                return False
            while i < len(s) and bs[i] >= int(48) and bs[i] <= int(57):
                i += 1
            while i < len(s) and (bs[i] == _SPACE or bs[i] == _TAB):
                i += 1
            return i == len(s) and has_digit
        elif c == _SPACE or c == _TAB:
            break
        else:
            return False
        i += 1
    while i < len(s) and (bs[i] == _SPACE or bs[i] == _TAB):
        i += 1
    return has_digit and i == len(s)



def _try_parse_int(s):
    try:
        return atol(s)
    except:
        return 0



def _can_parse_int(s):
    if len(s) == 0:
        return False
    bs = s.encode('utf-8')
    start = 0
    while start < len(s) and (bs[start] == _SPACE or bs[start] == _TAB):
        start += 1
    if start >= len(s):
        return False
    if bs[start] == int(45) or bs[start] == int(43):
        start += 1
    if start >= len(s):
        return False
    has_digit = False
    i = start
    while i < len(s):
        c = bs[i]
        if c >= int(48) and c <= int(57):
            has_digit = True
        elif c == _SPACE or c == _TAB:
            break
        else:
            return False
        i += 1
    while i < len(s) and (bs[i] == _SPACE or bs[i] == _TAB):
        i += 1
    return has_digit and i == len(s)






def _parse_fields(line, delim_byte):
    fields = []
    bs = line.encode('utf-8')
    n = len(line)
    current = str("")
    state = 0  # 0=field_start, 1=unquoted, 2=quoted, 3=after_quote
    i = 0

    while i < n:
        c = bs[i]

        if state == 0:
            if c == _DQUOTE:
                state = 2
            elif c == delim_byte:
                fields.append(current)
                current = str("")
            elif c == _CR:
                pass
            elif c == _LF:
                break
            else:
                current += chr(int(c))
                state = 1
        elif state == 1:
            if c == delim_byte:
                fields.append(current)
                current = str("")
                state = 0
            elif c == _CR:
                pass
            elif c == _LF:
                break
            else:
                current += chr(int(c))
        elif state == 2:
            if c == _DQUOTE:
                state = 3
            else:
                current += chr(int(c))
        elif state == 3:
            if c == _DQUOTE:
                current += chr(int(_DQUOTE))
                state = 2
            elif c == delim_byte:
                fields.append(current)
                current = str("")
                state = 0
            elif c == _CR:
                pass
            elif c == _LF:
                break
            else:
                current += chr(int(c))
                state = 1

        i += 1

    fields.append(current)
    return fields



def _split_csv_records(content):
    records = []
    bs = content.encode('utf-8')
    n = len(content)
    current = str("")
    in_quotes = False
    i = 0

    while i < n:
        c = bs[i]

        if c == _DQUOTE:
            in_quotes = not in_quotes
            current += chr(int(c))
        elif c == _LF and not in_quotes:
            if len(current) > 0:
                records.append(current)
            current = str("")
        elif c == _CR and not in_quotes:
            pass
        else:
            current += chr(int(c))

        i += 1

    if len(current) > 0:
        records.append(current)

    return records






def _escape_json_string(s):
    result = str("")
    bs = s.encode('utf-8')
    for i in range(len(s)):
        c = bs[i]
        if c == int(34):
            result += "\\\""
        elif c == int(92):
            result += "\\\\"
        elif c == int(10):
            result += "\\n"
        elif c == int(13):
            result += "\\r"
        elif c == int(9):
            result += "\\t"
        else:
            result += chr(int(c))
    return result


