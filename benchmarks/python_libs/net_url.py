"""Python equivalent of mojo/engine/net.url.mojo (auto-generated)."""
import math
import random as _rng

class URL:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('scheme')
        self.scheme = _v0 if _v0 is not None else None
        _v1 = args[1] if 1 < len(args) else kwargs.get('host')
        self.host = _v1 if _v1 is not None else None
        _v2 = args[2] if 2 < len(args) else kwargs.get('port')
        self.port = _v2 if _v2 is not None else None
        _v3 = args[3] if 3 < len(args) else kwargs.get('path')
        self.path = _v3 if _v3 is not None else None
        _v4 = args[4] if 4 < len(args) else kwargs.get('query')
        self.query = _v4 if _v4 is not None else None
        _v5 = args[5] if 5 < len(args) else kwargs.get('fragment')
        self.fragment = _v5 if _v5 is not None else None
    def __repr__(self):
        return f'URL({vars(self)})'

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

def _is_alpha(c):
    return (c >= 65 and c <= 90) or (c >= 97 and c <= 122)



def _is_digit(c):
    return c >= 48 and c <= 57



def _is_alnum(c):
    return _is_alpha(c) or _is_digit(c)



def _is_unreserved(c):
    return _is_alnum(c) or c == 45 or c == 46 or c == 95 or c == 126



def _hex_digit(val):
    if val < 10:
        return chr(48 + val)
    return chr(65 + val - 10)



def _hex_val(c):
    ci = int(c)
    if ci >= 48 and ci <= 57:
        return ci - 48
    if ci >= 65 and ci <= 70:
        return ci - 65 + 10
    if ci >= 97 and ci <= 102:
        return ci - 97 + 10
    return -1



def _int_to_string(val):
    if val == 0:
        return str("0")
    result = str("")
    v = val
    while v > 0:
        result = chr(48 + v % 10) + result
        v = v // 10
    return result



def _string_to_int(s):
    bs = s.encode('utf-8')
    n = len(s)
    result = 0
    for i in range(n):
        c = int(bs[i])
        if c >= 48 and c <= 57:
            result = result * 10 + (c - 48)
        else:
            break
    return result



def _substr(s, start, end):
    bs = s.encode('utf-8')
    n = len(s)
    e = end
    if e > n:
        e = n
    st = start
    if st < 0:
        st = 0
    result = str("")
    for i in range(st, e):
        result += chr(int(bs[i]))
    return result



def _find(s, needle, start):
    s_len = len(s)
    n_len = len(needle)
    if n_len == 0:
        return start
    if start + n_len > s_len:
        return -1
    s_bytes = s.encode('utf-8')
    n_bytes = needle.encode('utf-8')
    for i in range(start, s_len - n_len + 1):
        found = True
        for j in range(n_len):
            if s_bytes[i + j] != n_bytes[j]:
                found = False
                break
        if found:
            return i
    return -1



def _find_char(s, ch, start):
    bs = s.encode('utf-8')
    n = len(s)
    for i in range(start, n):
        if bs[i] == ch:
            return i
    return -1






def url_parse(raw):
    u = URL()
    s = raw
    total = len(s)


    pos = 0
    colon_slash = _find(s, "://", 0)
    if colon_slash >= 0:
        u.scheme = _substr(s, 0, colon_slash)
        pos = colon_slash + 3


    hash_pos = _find_char(s, int(35), pos)  # '#'
    working_end = total
    if hash_pos >= 0:
        u.fragment = _substr(s, hash_pos + 1, total)
        working_end = hash_pos


    q_pos = _find_char(s, int(63), pos)  # '?'
    if q_pos >= 0 and q_pos < working_end:
        u.query = _substr(s, q_pos + 1, working_end)
        working_end = q_pos


    slash_pos = _find_char(s, int(47), pos)  # '/'
    if slash_pos >= 0 and slash_pos < working_end:
        u.path = _substr(s, slash_pos, working_end)
        working_end = slash_pos
    else:
        u.path = str("")


    authority = _substr(s, pos, working_end)
    auth_len = len(authority)

    if auth_len > 0:

        auth_bs = authority.encode('utf-8')
        colon_pos = -1
        for i in range(auth_len):
            if auth_bs[i] == int(58):
                colon_pos = i
        if colon_pos >= 0:
            u.host = _substr(authority, 0, colon_pos)
            port_str = _substr(authority, colon_pos + 1, auth_len)
            u.port = _string_to_int(port_str)
        else:
            u.host = authority

    return u






def url_encode(s):
    bs = s.encode('utf-8')
    n = len(s)
    result = str("")
    for i in range(n):
        c = bs[i]
        if _is_unreserved(c):
            result += chr(int(c))
        else:
            result += "%"
            result += _hex_digit(int(c) >> 4)
            result += _hex_digit(int(c) & 0x0F)
    return result






def url_decode(s):
    bs = s.encode('utf-8')
    n = len(s)
    result = str("")
    i = 0
    while i < n:
        if bs[i] == int(37) and i + 2 < n:
            hi = _hex_val(bs[i + 1])
            lo = _hex_val(bs[i + 2])
            if hi >= 0 and lo >= 0:
                result += chr(hi * 16 + lo)
                i += 3
                continue
        if bs[i] == int(43):
            result += " "
        else:
            result += chr(int(bs[i]))
        i += 1
    return result






def query_parse(query):
    result = []
    q_len = len(query)
    if q_len == 0:
        return result

    start = 0

    while start < q_len:

        amp_pos = _find_char(query, int(38), start)  # '&'
        end = amp_pos
        if end < 0:
            end = q_len

        pair_str = _substr(query, start, end)
        eq_pos = _find_char(pair_str, int(61), 0)  # '='

        pair = []
        if eq_pos >= 0:
            pair.append(_substr(pair_str, 0, eq_pos))
            pair.append(_substr(pair_str, eq_pos + 1, len(pair_str)))
        else:
            pair.append(pair_str)
            pair.append(str(""))
        result.append(pair)

        if amp_pos < 0:
            break
        start = amp_pos + 1

    return result






def query_get(query, key):
    pairs = query_parse(query)
    n = len(pairs)
    for i in range(n):
        if len(pairs[i]) >= 2 and pairs[i][0] == key:
            return pairs[i][1]
    return str("")





