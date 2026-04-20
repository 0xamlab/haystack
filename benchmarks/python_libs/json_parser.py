"""Python equivalent of mojo/engine/json.parser.mojo (auto-generated)."""
import math
import random as _rng

try:
    from conv import parse_float64
except Exception:
    pass
try:
    from conv import parse_int
except Exception:
    pass
try:
    from conv import is_whitespace
except Exception:
    pass

_QUOTE = int(34)       # "
_BACKSLASH = int(92)   # backslash
_LBRACE = int(123)     # {
_RBRACE = int(125)     # }
_LBRACKET = int(91)    # [
_RBRACKET = int(93)    # ]
_COLON = int(58)       # :
_COMMA = int(44)       # ,
_MINUS = int(45)       # -
_DOT = int(46)         # .
_CHAR_T = int(116)     # t
_CHAR_F = int(102)     # f
_CHAR_N = int(110)     # n
_CHAR_E = int(101)     # e (scientific notation)
_CHAR_E_UP = int(69)   # math.e
_CHAR_PLUS = int(43)   # +
_DIGIT_0 = int(48)     # 0
_DIGIT_9 = int(57)     # 9

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

def _extract_number_str(raw, pos):
    bytes = raw.encode('utf-8')
    n = len(raw)
    p = pos
    while p < n:
        c = bytes[p]
        if c == _COMMA or c == _RBRACE or c == _RBRACKET or is_whitespace(c):
            break
        p += 1

    result = str("")
    for i in range(pos, p):
        result += chr(int(bytes[i]))
    return result






def skip_whitespace(data, pos):
    bytes = data.encode('utf-8')
    n = len(data)
    p = pos
    while p < n and is_whitespace(bytes[p]):
        p += 1
    return p






def skip_json_value(data, pos):
    bytes = data.encode('utf-8')
    n = len(data)
    p = skip_whitespace(data, pos)

    if p >= n:
        return p

    ch = bytes[p]


    if ch == _QUOTE:
        p += 1  # skip opening "
        while p < n:
            if bytes[p] == _BACKSLASH:
                p += 2  # skip escaped char
                continue
            if bytes[p] == _QUOTE:
                p += 1  # skip closing "
                return p
            p += 1
        return p  # unterminated string — return end


    if ch == _LBRACE:
        p += 1
        depth = 1
        while p < n and depth > 0:
            c = bytes[p]
            if c == _QUOTE:

                p += 1
                while p < n:
                    if bytes[p] == _BACKSLASH:
                        p += 2
                        continue
                    if bytes[p] == _QUOTE:
                        p += 1
                        break
                    p += 1
                continue
            if c == _LBRACE:
                depth += 1
            elif c == _RBRACE:
                depth -= 1
            p += 1
        return p


    if ch == _LBRACKET:
        p += 1
        depth = 1
        while p < n and depth > 0:
            c = bytes[p]
            if c == _QUOTE:

                p += 1
                while p < n:
                    if bytes[p] == _BACKSLASH:
                        p += 2
                        continue
                    if bytes[p] == _QUOTE:
                        p += 1
                        break
                    p += 1
                continue
            if c == _LBRACKET:
                depth += 1
            elif c == _RBRACKET:
                depth -= 1
            p += 1
        return p


    if ch == _CHAR_T:
        return p + 4  # "true"


    if ch == _CHAR_F:
        return p + 5  # "false"


    if ch == _CHAR_N:
        return p + 4  # "null"


    if ch == _MINUS or (ch >= _DIGIT_0 and ch <= _DIGIT_9):
        p += 1
        while p < n:
            c = bytes[p]
            if (
                (c >= _DIGIT_0 and c <= _DIGIT_9)
                or c == _DOT
                or c == _CHAR_E
                or c == _CHAR_E_UP
                or c == _MINUS
                or c == _CHAR_PLUS
            ):
                p += 1
            else:
                break
        return p


    return p + 1






def find_key(data, key):
    bytes = data.encode('utf-8')
    n = len(data)
    key_bytes = key.encode('utf-8')
    key_len = len(key)


    p = skip_whitespace(data, 0)
    if p >= n or bytes[p] != _LBRACE:
        return -1
    p += 1

    while p < n:
        p = skip_whitespace(data, p)
        if p >= n:
            return -1


        if bytes[p] == _RBRACE:
            return -1


        if bytes[p] == _COMMA:
            p += 1
            p = skip_whitespace(data, p)


        if p >= n or bytes[p] != _QUOTE:
            return -1


        p += 1  # skip opening "
        key_start = p
        while p < n:
            if bytes[p] == _BACKSLASH:
                p += 2
                continue
            if bytes[p] == _QUOTE:
                break
            p += 1
        key_end = p
        p += 1  # skip closing "


        found = (key_end - key_start) == key_len
        if found:
            for i in range(key_len):
                if bytes[key_start + i] != key_bytes[i]:
                    found = False
                    break


        p = skip_whitespace(data, p)
        if p >= n or bytes[p] != _COLON:
            return -1
        p += 1
        p = skip_whitespace(data, p)

        if found:
            return p  # position of the value


        p = skip_json_value(data, p)

    return -1






def json_get_string(raw, key):
    pos = find_key(raw, key)
    if pos < 0:
        return str("")

    bytes = raw.encode('utf-8')
    n = len(raw)

    if pos >= n or bytes[pos] != _QUOTE:
        return str("")

    pos += 1  # skip opening "
    result = str("")
    while pos < n:
        if bytes[pos] == _BACKSLASH and pos + 1 < n:

            next_ch = bytes[pos + 1]
            if next_ch == _QUOTE:
                result += '"'
            elif next_ch == _BACKSLASH:
                result += "\\"
            elif next_ch == int(110):
                result += "\n"
            elif next_ch == int(116):
                result += "\t"
            elif next_ch == int(114):
                result += "\r"
            elif next_ch == int(47):
                result += "/"
            else:
                result += chr(int(next_ch))
            pos += 2
            continue
        if bytes[pos] == _QUOTE:
            break
        result += chr(int(bytes[pos]))
        pos += 1

    return result






def json_get_float(raw, key, default):
    pos = find_key(raw, key)
    if pos < 0:
        return default

    bytes = raw.encode('utf-8')
    n = len(raw)
    if pos >= n:
        return default


    if bytes[pos] == _CHAR_N:
        return default

    num_str = _extract_number_str(raw, pos)
    if len(num_str) == 0:
        return default
    return parse_float64(num_str)






def json_get_int(raw, key, default):
    pos = find_key(raw, key)
    if pos < 0:
        return default

    bytes = raw.encode('utf-8')
    n = len(raw)
    if pos >= n:
        return default


    if bytes[pos] == _CHAR_N:
        return default

    num_str = _extract_number_str(raw, pos)
    if len(num_str) == 0:
        return default
    return parse_int(num_str)






def json_get_bool(raw, key, default):
    pos = find_key(raw, key)
    if pos < 0:
        return default

    bytes = raw.encode('utf-8')
    n = len(raw)
    if pos >= n:
        return default

    if bytes[pos] == _CHAR_T:
        return True
    if bytes[pos] == _CHAR_F:
        return False
    return default






def json_is_null(raw, key):
    pos = find_key(raw, key)
    if pos < 0:
        return True  # key absent → treat as null

    bytes = raw.encode('utf-8')
    n = len(raw)
    if pos >= n:
        return True

    return bytes[pos] == _CHAR_N  # starts with 'n' → null






def json_get_object(raw, key):
    pos = find_key(raw, key)
    if pos < 0:
        return str("")

    bytes = raw.encode('utf-8')
    n = len(raw)
    if pos >= n or bytes[pos] != _LBRACE:
        return str("")

    end = skip_json_value(raw, pos)


    result = str("")
    for i in range(pos, end):
        result += chr(int(bytes[i]))
    return result






def json_get_array(raw, key):
    pos = find_key(raw, key)
    if pos < 0:
        return str("")

    bytes = raw.encode('utf-8')
    n = len(raw)
    if pos >= n or bytes[pos] != _LBRACKET:
        return str("")

    end = skip_json_value(raw, pos)


    result = str("")
    for i in range(pos, end):
        result += chr(int(bytes[i]))
    return result






def json_array_len(arr):
    bytes = arr.encode('utf-8')
    n = len(arr)

    p = skip_whitespace(arr, 0)
    if p >= n or bytes[p] != _LBRACKET:
        return 0
    p += 1
    p = skip_whitespace(arr, p)


    if p < n and bytes[p] == _RBRACKET:
        return 0

    count = 0
    while p < n:
        p = skip_whitespace(arr, p)
        if p >= n or bytes[p] == _RBRACKET:
            break

        count += 1
        p = skip_json_value(arr, p)
        p = skip_whitespace(arr, p)

        if p < n and bytes[p] == _COMMA:
            p += 1

    return count






def json_array_get(arr, index):
    bytes = arr.encode('utf-8')
    n = len(arr)

    p = skip_whitespace(arr, 0)
    if p >= n or bytes[p] != _LBRACKET:
        return str("")
    p += 1

    current = 0
    while p < n:
        p = skip_whitespace(arr, p)
        if p >= n or bytes[p] == _RBRACKET:
            break

        if current == index:

            start = p
            end = skip_json_value(arr, p)
            result = str("")
            for i in range(start, end):
                result += chr(int(bytes[i]))
            return result


        p = skip_json_value(arr, p)
        p = skip_whitespace(arr, p)

        if p < n and bytes[p] == _COMMA:
            p += 1

        current += 1

    return str("")
