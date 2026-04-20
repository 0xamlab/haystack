"""Python equivalent of mojo/engine/engines.relation_detector.mojo (auto-generated)."""
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
try:
    from dimensions import infer_from_samples
except Exception:
    pass
try:
    from dimensions import propagate
except Exception:
    pass
try:
    from dimensions import role_for_dimension
except Exception:
    pass
try:
    from dimensions import DIM_UNKNOWN
except Exception:
    pass
try:
    from dimensions import DIM_COUNT
except Exception:
    pass
try:
    from dimensions import DIM_CURRENCY
except Exception:
    pass
try:
    from dimensions import DIM_RATE
except Exception:
    pass
try:
    from dimensions import DIM_RATIO
except Exception:
    pass
try:
    from dimensions import DIM_IDENTIFIER
except Exception:
    pass
try:
    from dimensions import DIM_INVALID
except Exception:
    pass

class ColVector:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('name')
        self.name = _v0 if _v0 is not None else ""
        _v1 = args[1] if 1 < len(args) else kwargs.get('values')
        self.values = _v1 if _v1 is not None else []
    def __repr__(self):
        return f'ColVector({vars(self)})'

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





def _parse_float_array(arr_str):
    result = []
    n = len(arr_str)
    bytes = arr_str.encode('utf-8')
    i = 0


    while i < n and bytes[i] != int(91):
        i += 1
    i += 1  # skip [

    while i < n:

        while i < n and (bytes[i] == int(32) or bytes[i] == int(44)
                         or bytes[i] == int(10) or bytes[i] == int(13)):
            i += 1
        if i >= n or bytes[i] == int(93):
            break


        if bytes[i] == int(110) or bytes[i] == int(116) or bytes[i] == int(102):
            while i < n and bytes[i] != int(44) and bytes[i] != int(93):
                i += 1
            continue


        start = i
        if bytes[i] == int(45):
            i += 1
        while i < n and bytes[i] >= int(48) and bytes[i] <= int(57):
            i += 1
        if i < n and bytes[i] == int(46):
            i += 1
            while i < n and bytes[i] >= int(48) and bytes[i] <= int(57):
                i += 1
        if i < n and (bytes[i] == int(101) or bytes[i] == int(69)):
            i += 1
            if i < n and (bytes[i] == int(43) or bytes[i] == int(45)):
                i += 1
            while i < n and bytes[i] >= int(48) and bytes[i] <= int(57):
                i += 1

        num_str = _substr(arr_str, start, i)
        if len(num_str) > 0:
            result.append(parse_float64(num_str))

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
        while i < n and (bytes[i] == int(32) or bytes[i] == int(44)
                         or bytes[i] == int(10) or bytes[i] == int(13)):
            i += 1
        if i >= n or bytes[i] == int(125):
            break
        if bytes[i] != int(34):
            break


        i += 1
        name_start = i
        while i < n and bytes[i] != int(34):
            i += 1
        field_name = _substr(cols_json, name_start, i)
        i += 1


        while i < n and bytes[i] != int(58):
            i += 1
        i += 1
        while i < n and bytes[i] == int(32):
            i += 1


        if i >= n or bytes[i] != int(91):
            while i < n and bytes[i] != int(44) and bytes[i] != int(125):
                i += 1
            continue


        arr_start = i
        depth = 0
        j = i
        while j < n:
            c = bytes[j]
            if c == int(91):
                depth += 1
            elif c == int(93):
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1

        arr_str = _substr(cols_json, arr_start, j)
        i = j

        values = _parse_float_array(arr_str)
        if len(field_name) > 0 and len(values) > 0:
            result.append(ColVector(field_name, values))

    return result





def _pearson_r(a, b, n):
    mean_a = 0.0
    mean_b = 0.0
    for i in range(n):
        mean_a += a[i]
        mean_b += b[i]
    mean_a /= float(n)
    mean_b /= float(n)

    num = 0.0
    sq_a = 0.0
    sq_b = 0.0
    for i in range(n):
        da = a[i] - mean_a
        db = b[i] - mean_b
        num += da * db
        sq_a += da * da
        sq_b += db * db

    den = math.sqrt(sq_a * sq_b)
    if den < 1e-10:
        return 0.0
    return num / den



def _check_approx(predicted, actual, n):
    valid = 0
    matches = 0
    for i in range(n):
        av = actual[i]
        if math.fabs(av) < 1e-9:
            continue
        valid += 1
        if math.fabs(predicted[i] - av) / math.fabs(av) <= 0.05:
            matches += 1
    if valid < 3:
        return False
    return float(matches) / float(valid) >= 0.85





def _mean(v, n):
    s = 0.0
    for i in range(n):
        s += v[i]
    return s / float(n)



def run_relation_detect(raw):
    source = json_get_string(raw, "source")
    min_conf = json_get_float(raw, "min_confidence", 0.70)

    cols = _parse_columns(raw)
    nc = len(cols)

    if nc < 3:
        return ('{"source":"' + source
                + '","relationships":[],"columns_scanned":' + str(nc)
                + ',"triples_tested":0,"triples_evaluated":0}')


    means = []
    for k in range(nc):
        cv = cols[k].copy()
        n = len(cv.values)
        means.append(_mean(cv.values, n) if n > 0 else 0.0)




    stds = []
    cvs = []
    for k in range(nc):
        cv_col = cols[k].copy()
        n_c = len(cv_col.values)
        mk = means[k]
        sq = 0.0
        for idx in range(n_c):
            d = cv_col.values[idx] - mk
            sq += d * d
        sd = math.sqrt(sq / float(n_c)) if n_c > 1 else 0.0
        stds.append(sd)
        cv_ratio = sd / math.fabs(mk) if math.fabs(mk) > 1e-9 else 0.0
        cvs.append(cv_ratio)



    corr = []
    for _ in range(nc * nc):
        corr.append(0.0)

    for i in range(nc):
        ci = cols[i].copy()
        ni = len(ci.values)
        for j in range(i + 1, nc):
            cj = cols[j].copy()
            nj = len(cj.values)
            n_ij = ni if ni <= nj else nj
            if n_ij < 3:
                continue
            r = _pearson_r(ci.values, cj.values, n_ij)
            corr[i * nc + j] = r
            corr[j * nc + i] = r



    CV_THRESH = 0.05
    CORR_THRESH = 0.25

    output = str('{"source":"')
    output += source
    output += '","relationships":['

    total_triples = 0
    triples_evaluated = 0
    found = 0


    for k in range(nc):
        cv = cols[k].copy()
        n = len(cv.values)
        if n < 3:
            continue

        mk = means[k]
        abs_mk = math.fabs(mk)
        if abs_mk < 1e-9:
            continue  # all-zero result column — skip

        for i in range(nc):
            if i == k:
                continue
            av = cols[i].copy()
            if len(av.values) < n:
                continue

            mi = means[i]
            r_ik = math.fabs(corr[i * nc + k])

            for j in range(i + 1, nc):
                if j == k:
                    continue
                bv = cols[j].copy()
                if len(bv.values) < n:
                    continue

                total_triples += 1



                r_jk = math.fabs(corr[j * nc + k])
                if r_ik < CORR_THRESH and r_jk < CORR_THRESH:
                    continue




                if cvs[i] < CV_THRESH or cvs[j] < CV_THRESH:
                    continue


                mj = means[j]
                do_multiply = True
                do_add = True

                mul_scale = math.fabs(mi * mj) / abs_mk
                if mul_scale < 0.04 or mul_scale > 25.0:
                    do_multiply = False

                add_scale = math.fabs(mi + mj) / abs_mk
                if add_scale < 0.15 or add_scale > 7.0:
                    do_add = False

                if not do_multiply and not do_add:
                    continue


                triples_evaluated += 1

                products = []
                sums = []
                if do_multiply:
                    for m in range(n):
                        products.append(av.values[m] * bv.values[m])
                if do_add:
                    for m in range(n):
                        sums.append(av.values[m] + bv.values[m])

                if do_multiply and _check_approx(products, cv.values, n):
                    conf = _pearson_r(products, cv.values, n)
                    if conf < 0.0:
                        conf = -conf
                    if conf >= min_conf:

                        _da_m = infer_from_samples(av.values)
                        _db_m = infer_from_samples(bv.values)
                        dim_a_m = 0
                        dim_b_m = 0
                        if _da_m == DIM_COUNT and _db_m != DIM_COUNT:
                            dim_a_m = DIM_COUNT
                            dim_b_m = DIM_RATE
                        elif _db_m == DIM_COUNT and _da_m != DIM_COUNT:
                            dim_a_m = DIM_RATE
                            dim_b_m = DIM_COUNT
                        elif mi <= mj:
                            dim_a_m = DIM_COUNT
                            dim_b_m = DIM_RATE
                        else:
                            dim_a_m = DIM_RATE
                            dim_b_m = DIM_COUNT
                        dim_r_m = propagate("multiply", dim_a_m, dim_b_m)
                        role_m = role_for_dimension(dim_r_m)

                        if found > 0:
                            output += ","
                        output += '{"formula":"' + cv.name + ' = ' + av.name + ' x ' + bv.name + '",'
                        output += '"field_result":"' + cv.name + '",'
                        output += '"field_a":"' + av.name + '",'
                        output += '"field_b":"' + bv.name + '",'
                        output += '"operation":"multiply",'
                        output += '"dim_a":' + str(dim_a_m) + ','
                        output += '"dim_b":' + str(dim_b_m) + ','
                        output += '"dim_result":' + str(dim_r_m) + ','
                        output += '"role_result":"' + role_m + '",'
                        output += '"confidence":' + str(conf) + '}'
                        found += 1

                if do_add and _check_approx(sums, cv.values, n):
                    conf = _pearson_r(sums, cv.values, n)
                    if conf < 0.0:
                        conf = -conf
                    if conf >= min_conf:

                        dim_a_a = infer_from_samples(av.values)
                        dim_b_a = infer_from_samples(bv.values)
                        dim_r_a = propagate("add", dim_a_a, dim_b_a)


                        if dim_r_a == DIM_UNKNOWN and dim_a_a == DIM_UNKNOWN and dim_b_a == DIM_UNKNOWN:
                            dim_r_a = DIM_RATE
                        role_a = role_for_dimension(dim_r_a)

                        if found > 0:
                            output += ","
                        output += '{"formula":"' + cv.name + ' = ' + av.name + ' + ' + bv.name + '",'
                        output += '"field_result":"' + cv.name + '",'
                        output += '"field_a":"' + av.name + '",'
                        output += '"field_b":"' + bv.name + '",'
                        output += '"operation":"add",'
                        output += '"dim_a":' + str(dim_a_a) + ','
                        output += '"dim_b":' + str(dim_b_a) + ','
                        output += '"dim_result":' + str(dim_r_a) + ','
                        output += '"role_result":"' + role_a + '",'
                        output += '"confidence":' + str(conf) + '}'
                        found += 1

    output += '],"columns_scanned":' + str(nc)
    output += ',"triples_tested":' + str(total_triples)
    output += ',"triples_evaluated":' + str(triples_evaluated) + '}'
    return output
