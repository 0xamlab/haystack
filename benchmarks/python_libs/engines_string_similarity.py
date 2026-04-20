"""Python equivalent of mojo/engine/engines.string_similarity.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from string_distance import dice_coefficient
except Exception:
    pass
try:
    from field_mapper import to_lower
except Exception:
    pass
try:
    from json.parser import json_get_float
except Exception:
    pass
try:
    from json.parser import json_get_array
except Exception:
    pass
try:
    from json.parser import json_array_len
except Exception:
    pass
try:
    from json.parser import json_array_get
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

def _to_lower_byte(c):
    if c >= int(65) and c <= int(90):
        return c + int(32)
    return c


def _is_alnum_lower(c):
    return (c >= int(97) and c <= int(122)) or (c >= int(48) and c <= int(57))


def _is_alnum_any(c):
    return ((c >= int(65) and c <= int(90)) or
            (c >= int(97) and c <= int(122)) or
            (c >= int(48) and c <= int(57)))


def _is_upper_alpha(c):
    return c >= int(65) and c <= int(90)


def _is_lower_alpha(c):
    return c >= int(97) and c <= int(122)


def _is_stop_word(w):
    return (w == "of" or w == "the" or w == "a" or w == "an" or
            w == "and" or w == "or" or w == "by" or w == "in" or
            w == "at" or w == "for" or w == "per")





def _unquote(s):
    n = len(s)
    if n < 2:
        return s
    bytes = s.encode('utf-8')
    if bytes[0] != int(34) or bytes[n - 1] != int(34):
        return s
    result = str("")
    i = 1
    while i < n - 1:
        if bytes[i] == int(92) and i + 1 < n - 1:
            nxt = bytes[i + 1]
            if nxt == int(34):
                result += '"'
            elif nxt == int(92):
                result += "\\"
            elif nxt == int(110):
                result += "\n"
            elif nxt == int(116):
                result += "\t"
            elif nxt == int(114):
                result += "\r"
            elif nxt == int(47):
                result += "/"
            else:
                result += chr(int(nxt))
            i += 2
            continue
        result += chr(int(bytes[i]))
        i += 1
    return result





def _expand_column(col):
    n = len(col)
    bytes = col.encode('utf-8')
    result = str("")
    for i in range(n):
        c = bytes[i]
        if c == int(37):
            result += " percent "
        elif c == int(36):
            result += " dollar "
        elif c == int(35):
            result += " number "
        elif _is_upper_alpha(c) and i > 0 and _is_lower_alpha(bytes[i - 1]):

            result += " "
            result += chr(int(c + int(32)))  # lowercase
        else:
            result += chr(int(_to_lower_byte(c)))
    return result



def _tokenize(s):
    result = []
    bytes = s.encode('utf-8')
    n = len(s)
    i = 0
    while i < n:
        if _is_alnum_lower(bytes[i]):
            start = i
            while i < n and _is_alnum_lower(bytes[i]):
                i += 1
            tok = str("")
            for k in range(start, i):
                tok += chr(int(bytes[k]))
            if len(tok) > 0:
                result.append(tok)
        else:
            i += 1
    return result



def _col_raw_parts(col):
    result = []
    bytes = col.encode('utf-8')
    n = len(col)
    i = 0
    while i < n:
        if _is_alnum_any(bytes[i]):
            start = i
            while i < n and _is_alnum_any(bytes[i]):
                i += 1
            tok = str("")
            for k in range(start, i):
                tok += chr(int(bytes[k]))
            if len(tok) > 0:
                result.append(tok)
        else:
            i += 1
    return result





def _fuzzy_token_sim(a, b):
    if len(a) == 0 or len(b) == 0:
        return 0.0
    if a == b:
        return 1.0
    la = len(a)
    lb = len(b)

    short_s = a
    long_s = b
    sl = la
    ll = lb
    if la > lb:
        short_s = b; long_s = a
        sl = lb; ll = la

    sb = short_s.encode('utf-8')
    lb2 = long_s.encode('utf-8')
    is_prefix = True
    for k in range(sl):
        if sb[k] != lb2[k]:
            is_prefix = False
            break
    if is_prefix:
        return float(sl) / float(ll)

    return dice_coefficient(a, b)



def _fuzzy_name_sim(hint_toks, col_toks):
    n_hint = len(hint_toks)
    n_col = len(col_toks)
    if n_hint == 0 or n_col == 0:
        return 0.0
    log_sum = 0.0
    for hi in range(n_hint):
        best = 1e-6   # floor to avoid math.log(0)
        for ci in range(n_col):
            sim = _fuzzy_token_sim(hint_toks[hi], col_toks[ci])
            if sim > best:
                best = sim
        log_sum += math.log(best)
    return math.exp(log_sum / float(n_hint))



def _acronym_score(hint_toks, col_parts):

    initials = str("")
    for i in range(len(hint_toks)):
        hw = hint_toks[i]
        if _is_stop_word(hw) or len(hw) == 0:
            continue
        wb = hw.encode('utf-8')
        first = wb[0]

        if _is_lower_alpha(first):
            initials += chr(int(first - int(32)))
        else:
            initials += chr(int(first))

    if len(initials) == 0:
        return 0.0

    init_bytes = initials.encode('utf-8')
    init_len = len(initials)
    best = 0.0

    for pi in range(len(col_parts)):
        part = col_parts[pi]
        plen = len(part)
        if plen < 2 or plen > 6:
            continue

        pb = part.encode('utf-8')
        all_upper = True
        for k in range(plen):
            if not _is_upper_alpha(pb[k]):
                all_upper = False
                break
        if not all_upper:
            continue

        if part == initials:
            return 1.0

        min_len = plen if plen < init_len else init_len
        max_len = plen if plen > init_len else init_len
        matches = 0
        for k in range(min_len):
            if pb[k] == init_bytes[k]:
                matches += 1
        partial = float(matches) / float(max_len)
        if partial > best:
            best = partial

    return best





def run_string_similarity(raw):

    hint_arr = json_get_array(raw, "hint_words")
    n_hints = json_array_len(hint_arr)
    threshold = json_get_float(raw, "threshold", 0.0)


    hint_toks = []
    for i in range(n_hints):
        raw_hw = _unquote(json_array_get(hint_arr, i))
        hw = to_lower(raw_hw)

        hb = hw.encode('utf-8')
        hn = len(hw)
        hs = 0
        he = hn
        while hs < hn and hb[hs] == int(32):
            hs += 1
        while he > hs and hb[he - 1] == int(32):
            he -= 1
        if he > hs:
            htok = str("")
            for k in range(hs, he):
                htok += chr(int(hb[k]))
            if len(htok) > 0:
                hint_toks.append(htok)


    cols_arr = json_get_array(raw, "columns")
    n_cols = json_array_len(cols_arr)

    if len(hint_toks) == 0 or n_cols == 0:
        return '{"matches":[]}'

    output = str('{"matches":[')
    match_count = 0

    for ci in range(n_cols):
        col = _unquote(json_array_get(cols_arr, ci))
        if len(col) == 0:
            continue


        col_exp = _expand_column(col)
        col_toks = _tokenize(col_exp)


        col_parts = _col_raw_parts(col)

        fuzzy = _fuzzy_name_sim(hint_toks, col_toks)
        acro = _acronym_score(hint_toks, col_parts)

        score = fuzzy
        if acro > score:
            score = acro

        if score < threshold:
            continue

        method = str("fuzzy")
        if acro >= fuzzy and acro > 0.0:
            method = "acronym"

        if match_count > 0:
            output += ","
        output += '{"column":"' + col + '",'
        output += '"score":'   + str(score) + ','
        output += '"fuzzy":'   + str(fuzzy) + ','
        output += '"acronym":' + str(acro)  + ','
        output += '"method":"' + method + '"}'
        match_count += 1

    output += ']}'
    return output
