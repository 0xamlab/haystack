"""Python equivalent of mojo/engine/engines.join_detector.mojo (auto-generated)."""
import math
import random as _rng

try:
    from field_mapper import to_lower
except Exception:
    pass
try:
    from string_distance import dice_coefficient
except Exception:
    pass
try:
    from set_ops import jaccard_index
except Exception:
    pass
try:
    from set_ops import to_set
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
    from conv import parse_float64
except Exception:
    pass

class ColEntry:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('full_name')
        self.full_name = _v0 if _v0 is not None else ""
        _v1 = args[1] if 1 < len(args) else kwargs.get('source')
        self.source = _v1 if _v1 is not None else ""
        _v2 = args[2] if 2 < len(args) else kwargs.get('field')
        self.field = _v2 if _v2 is not None else ""
        _v3 = args[3] if 3 < len(args) else kwargs.get('values')
        self.values = _v3 if _v3 is not None else []
        _v4 = args[4] if 4 < len(args) else kwargs.get('unique_ratio')
        self.unique_ratio = _v4 if _v4 is not None else 0.0
    def __repr__(self):
        return f'ColEntry({vars(self)})'

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





def _djb2(s):
    h = 5381
    bytes = s.encode('utf-8')
    for i in range(len(s)):
        h = ((h << 5) + h) ^ int(bytes[i])
    if h < 0:
        h = -h
    return h % 1000000007  # keep manageable





def _extract_values(col_json):
    result = []
    vpos = col_json.find('"values"')
    if vpos < 0:
        return result
    after = _substr(col_json, vpos + 8, len(col_json))
    bracket = after.find("[")
    if bracket < 0:
        return result
    arr = _substr(after, bracket, len(after))
    n = len(arr)
    bytes = arr.encode('utf-8')
    i = 1  # skip [

    while i < n:
        while i < n and (bytes[i] == int(32) or bytes[i] == int(44) or bytes[i] == int(10)):
            i += 1
        if i >= n or bytes[i] == int(93):
            break

        if bytes[i] == int(34):
            i += 1
            start = i
            while i < n and bytes[i] != int(34):
                i += 1
            result.append(_substr(arr, start, i))
            i += 1
        elif bytes[i] >= int(48) and bytes[i] <= int(57) or bytes[i] == int(45):

            start = i
            if bytes[i] == int(45):
                i += 1
            while i < n and bytes[i] >= int(48) and bytes[i] <= int(57):
                i += 1
            if i < n and bytes[i] == int(46):
                i += 1
                while i < n and bytes[i] >= int(48) and bytes[i] <= int(57):
                    i += 1
            result.append(_substr(arr, start, i))
        elif bytes[i] == int(110):
            i += 4
        else:
            while i < n and bytes[i] != int(44) and bytes[i] != int(93):
                i += 1
    return result



def _extract_unique_ratio(col_json):
    return json_get_float(col_json, "unique_ratio", 0.5)





def _jaccard_str_lists(a, b):
    if len(a) == 0 or len(b) == 0:
        return 0.0
    limit = 200
    na = len(a) if len(a) <= limit else limit
    nb = len(b) if len(b) <= limit else limit

    h_a = []
    for i in range(na):
        h_a.append(_djb2(a[i]))

    h_b = []
    for i in range(nb):
        h_b.append(_djb2(b[i]))

    set_a = to_set(h_a)
    set_b = to_set(h_b)
    return jaccard_index(set_a, set_b)



def _cardinality(ur_a, ur_b):
    h_a = ur_a > 0.85
    h_b = ur_b > 0.85
    if h_a and h_b:
        return "1:1"
    elif h_a and not h_b:
        return "1:N"
    elif not h_a and h_b:
        return "N:1"
    else:
        return "N:N"



def _name_sim(a, b):
    la = to_lower(a)
    lb = to_lower(b)
    if la == lb:
        return 1.0
    return dice_coefficient(la, lb)





def _split_dot(full):
    dot = full.find(".")
    result = []
    if dot < 0:
        result.append("")
        result.append(full)
    else:
        result.append(_substr(full, 0, dot))
        result.append(_substr(full, dot + 1, len(full)))
    return result





def _parse_columns(raw):
    result = []

    cols_key = '"columns"'
    cols_pos = raw.find(cols_key)
    if cols_pos < 0:
        return result

    after_cols = _substr(raw, cols_pos + len(cols_key), len(raw))
    outer_brace = after_cols.find("{")
    if outer_brace < 0:
        return result

    cols_json = _substr(after_cols, outer_brace, len(after_cols))
    n = len(cols_json)
    bytes = cols_json.encode('utf-8')
    i = 1  # skip {

    while i < n:
        while i < n and (bytes[i] == int(32) or bytes[i] == int(44) or bytes[i] == int(10) or bytes[i] == int(13)):
            i += 1
        if i >= n or bytes[i] == int(125):
            break
        if bytes[i] != int(34):
            break


        i += 1
        name_start = i
        while i < n and bytes[i] != int(34):
            i += 1
        full_name = _substr(cols_json, name_start, i)
        i += 1


        while i < n and bytes[i] != int(58):
            i += 1
        i += 1
        while i < n and bytes[i] == int(32):
            i += 1


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
        col_obj = _substr(cols_json, obj_start, j)
        i = j

        sf = _split_dot(full_name)
        source = sf[0]
        field = sf[1]
        values = _extract_values(col_obj)
        ur = _extract_unique_ratio(col_obj)

        result.append(ColEntry(full_name, source, field, values, ur))

    return result





def run_join_detect(raw):
    min_conf = json_get_float(raw, "min_confidence", 0.5)

    cols = _parse_columns(raw)
    nc = len(cols)

    if nc < 2:
        return '{"join_keys":[],"error":"need at least 2 columns from different sources"}'

    output = str('{"join_keys":[')
    total_found = 0

    for i in range(nc):
        for j in range(i + 1, nc):
            a = cols[i].copy()
            b = cols[j].copy()


            if a.source == b.source and len(a.source) > 0:
                continue


            if len(a.values) == 0 or len(b.values) == 0:
                continue


            overlap = _jaccard_str_lists(a.values, b.values)


            name_sim = _name_sim(a.field, b.field)


            ur_a = a.unique_ratio
            ur_b = b.unique_ratio
            ur_signal = 0.0
            if ur_a > 0.80 or ur_b > 0.80:
                ur_signal = 0.5 + 0.5 * (ur_a + ur_b) / 2.0

            confidence = overlap * 0.50 + name_sim * 0.30 + ur_signal * 0.20
            fk_prob = overlap * 0.6 + ur_signal * 0.4

            if confidence < min_conf:
                continue

            cardinality = _cardinality(ur_a, ur_b)

            if total_found > 0:
                output += ","
            output += '{"field_a":"' + a.field + '",'
            output += '"source_a":"' + a.source + '",'
            output += '"field_b":"' + b.field + '",'
            output += '"source_b":"' + b.source + '",'
            output += '"overlap":' + str(overlap) + ','
            output += '"name_similarity":' + str(name_sim) + ','
            output += '"cardinality":"' + cardinality + '",'
            output += '"fk_probability":' + str(fk_prob) + ','
            output += '"confidence":' + str(confidence) + '}'
            total_found += 1

    output += '],"total_candidates":' + str(total_found) + '}'
    return output
