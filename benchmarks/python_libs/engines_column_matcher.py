"""Python equivalent of mojo/engine/engines.column_matcher.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from field_mapper import to_lower
except Exception:
    pass
try:
    from string_distance import dice_coefficient
except Exception:
    pass
try:
    from string_distance import edit_similarity
except Exception:
    pass
try:
    from json.parser import json_get_string
except Exception:
    pass
try:
    from json.parser import json_get_float
except Exception:
    pass
try:
    from json.parser import json_get_int
except Exception:
    pass
try:
    from conv import parse_float64
except Exception:
    pass

class ColProfile:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('name')
        self.name = _v0 if _v0 is not None else ""
        _v1 = args[1] if 1 < len(args) else kwargs.get('semantic_type')
        self.semantic_type = _v1 if _v1 is not None else ""
        _v2 = args[2] if 2 < len(args) else kwargs.get('polarity')
        self.polarity = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('distribution')
        self.distribution = _v3 if _v3 is not None else ""
        _v4 = args[4] if 4 < len(args) else kwargs.get('mean')
        self.mean = _v4 if _v4 is not None else 0.0
        _v5 = args[5] if 5 < len(args) else kwargs.get('std')
        self.std = _v5 if _v5 is not None else 0.0
    def __repr__(self):
        return f'ColProfile({vars(self)})'

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

def _substr(s, start, end):
    result = str("")
    bytes = s.encode('utf-8')
    n = len(s)
    i = start if start >= 0 else 0
    e = end if end <= n else n
    while i < e:
        result += chr(int(bytes[i]))
        i += 1
    return result





def _normalize_name(s):
    lower = to_lower(s)
    result = str("")
    bytes = lower.encode('utf-8')
    for i in range(len(lower)):
        c = bytes[i]
        if c != int(95) and c != int(32) and c != int(45):
            result += chr(int(c))


    if result == "qty":
        return "quantity"
    if result == "amt":
        return "amount"
    if result == "rev":
        return "revenue"
    if result == "cst":
        return "cost"
    if result == "num":
        return "number"
    if result == "dt":
        return "date"
    if result == "cust":
        return "customer"
    if result == "prc":
        return "price"
    return result





def _name_score(a, b):
    la = _normalize_name(a)
    lb = _normalize_name(b)
    if la == lb:
        return 1.0
    dice = dice_coefficient(la, lb)
    edit = edit_similarity(la, lb)
    substr_bonus = 0.0
    if la.find(lb) >= 0 or lb.find(la) >= 0:
        substr_bonus = 0.15
    score = dice * 0.6 + edit * 0.4 + substr_bonus
    if score > 1.0:
        score = 1.0
    return score



def _semantic_type_score(type_a, type_b):
    if type_a == type_b:
        return 1.0
    if type_a == "id" or type_b == "id":
        return 0.0
    if type_a == "date" or type_b == "date":
        return 0.0
    is_num_a = type_a == "currency" or type_a == "metric" or type_a == "count"
    is_num_b = type_b == "currency" or type_b == "metric" or type_b == "count"
    if is_num_a and is_num_b:
        if (type_a == "currency" or type_a == "metric") and (type_b == "currency" or type_b == "metric"):
            return 0.7
        return 0.5
    if (type_a == "category" or type_a == "text") and (type_b == "category" or type_b == "text"):
        return 0.6
    return 0.0



def _polarity_score(pol_a, pol_b):
    if pol_a == pol_b:
        return 1.0
    if pol_a == 0 or pol_b == 0:
        return 0.5
    return 0.2



def _distribution_score(dist_a, dist_b, mean_a, mean_b, std_a, std_b):
    base = 0.0
    if dist_a == dist_b and len(dist_a) > 0:
        base = 0.5
    cv_a = 0.0
    cv_b = 0.0
    if math.fabs(mean_a) > 0.0:
        cv_a = math.fabs(std_a / mean_a)
    if math.fabs(mean_b) > 0.0:
        cv_b = math.fabs(std_b / mean_b)
    cv_sim = 0.0
    if cv_a > 0.0 and cv_b > 0.0:
        ratio = cv_a / cv_b if cv_a >= cv_b else cv_b / cv_a
        if ratio <= 1.5:
            cv_sim = 0.5 * (1.0 - (ratio - 1.0))
            if cv_sim < 0.0:
                cv_sim = 0.0
    return base + cv_sim * 0.5





def _parse_col_profiles(arr_str):
    result = []
    n = len(arr_str)
    bytes = arr_str.encode('utf-8')
    i = 0


    while i < n and bytes[i] != int(91):
        i += 1
    i += 1

    while i < n:
        while i < n and (bytes[i] == int(32) or bytes[i] == int(44) or bytes[i] == int(10) or bytes[i] == int(13)):
            i += 1
        if i >= n or bytes[i] == int(93):
            break
        if bytes[i] != int(123):
            i += 1
            continue


        obj_start = i
        depth = 0
        in_str = False
        j = i
        while j < n:
            c = bytes[j]
            if c == int(34) and (j == 0 or bytes[j - 1] != int(92)):
                in_str = not in_str
            elif not in_str:
                if c == int(123) or c == int(91):
                    depth += 1
                elif c == int(125) or c == int(93):
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
            j += 1
        obj = _substr(arr_str, obj_start, j)
        i = j

        name = json_get_string(obj, "name")
        sem_type = json_get_string(obj, "semantic_type")
        dist = json_get_string(obj, "distribution")
        polarity = json_get_int(obj, "polarity", 0)
        mean_val = json_get_float(obj, "mean", 0.0)
        std_val = json_get_float(obj, "std", 0.0)

        if len(name) > 0:
            result.append(ColProfile(name, sem_type, polarity, dist, mean_val, std_val))

    return result





def run_column_match(raw):
    source_a = json_get_string(raw, "source_a")
    source_b = json_get_string(raw, "source_b")
    min_conf = json_get_float(raw, "min_confidence", 0.5)
    if len(source_a) == 0:
        source_a = "source_a"
    if len(source_b) == 0:
        source_b = "source_b"


    cols_a_key = '"columns_a"'
    cols_b_key = '"columns_b"'
    cols_a_pos = raw.find(cols_a_key)
    cols_b_pos = raw.find(cols_b_key)
    if cols_a_pos < 0 or cols_b_pos < 0:
        return '{"error":"column_match requires columns_a and columns_b arrays"}'

    after_a = _substr(raw, cols_a_pos + len(cols_a_key), len(raw))
    bracket_a = after_a.find("[")
    if bracket_a < 0:
        return '{"error":"columns_a must be a JSON array"}'
    cols_a = _parse_col_profiles(_substr(after_a, bracket_a, len(after_a)))

    after_b = _substr(raw, cols_b_pos + len(cols_b_key), len(raw))
    bracket_b = after_b.find("[")
    if bracket_b < 0:
        return '{"error":"columns_b must be a JSON array"}'
    cols_b = _parse_col_profiles(_substr(after_b, bracket_b, len(after_b)))

    na = len(cols_a)
    nb = len(cols_b)
    if na == 0 or nb == 0:
        return '{"matches":[],"total_pairs":0}'

    output = str('{"source_a":"')
    output += source_a
    output += '","source_b":"'
    output += source_b
    output += '","matches":['

    total_matches = 0
    for i in range(na):
        for j in range(nb):
            a = cols_a[i].copy()
            b = cols_b[j].copy()

            t_score = _semantic_type_score(a.semantic_type, b.semantic_type)

            if t_score == 0.0:
                continue

            n_score = _name_score(a.name, b.name)
            p_score = _polarity_score(a.polarity, b.polarity)
            d_score = _distribution_score(
                a.distribution, b.distribution,
                a.mean, b.mean, a.std, b.std,
            )

            combined = n_score * 0.40 + t_score * 0.25 + p_score * 0.20 + d_score * 0.15
            if combined < min_conf:
                continue

            match_type = str("semantic")
            if n_score >= 0.99:
                match_type = "exact"
            elif n_score >= 0.80:
                match_type = "name_similar"
            elif t_score >= 0.9 and d_score >= 0.5:
                match_type = "statistical"

            if total_matches > 0:
                output += ","
            output += '{"field_a":"' + a.name + '",'
            output += '"field_b":"' + b.name + '",'
            output += '"score":' + str(combined) + ','
            output += '"name_score":' + str(n_score) + ','
            output += '"type_score":' + str(t_score) + ','
            output += '"polarity_score":' + str(p_score) + ','
            output += '"dist_score":' + str(d_score) + ','
            output += '"match_type":"' + match_type + '"}'
            total_matches += 1

    output += '],"total_pairs":' + str(na * nb) + '}'
    return output
