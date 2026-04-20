"""Python equivalent of mojo/engine/engines.column_profiler.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from field_mapper import contains_keyword
except Exception:
    pass
try:
    from field_mapper import to_lower
except Exception:
    pass
try:
    from field_mapper import detect_polarity
except Exception:
    pass
try:
    from field_mapper import detect_unit_hint
except Exception:
    pass
try:
    from field_mapper import infer_distribution_from_values
except Exception:
    pass
try:
    from json.parser import json_get_string
except Exception:
    pass
try:
    from conv import parse_float64
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

def _substr(s, start, end):
    result = str("")
    bytes = s.encode('utf-8')
    n = len(s)
    i = start
    e = end
    if i < 0:
        i = 0
    if e > n:
        e = n
    while i < e:
        result += chr(int(bytes[i]))
        i += 1
    return result





def _djb2_str(s):
    h = 5381
    bytes = s.encode('utf-8')
    for i in range(len(s)):
        h = ((h << 5) + h) ^ int(bytes[i])
    if h < 0:
        h = -h
    return h % 1000000007





def _approx_entropy(values):
    n = len(values)
    if n <= 1:
        return 0.0
    mn = values[0]
    mx = values[0]
    for i in range(1, n):
        if values[i] < mn:
            mn = values[i]
        if values[i] > mx:
            mx = values[i]
    span = mx - mn
    if span <= 0.0:
        return 0.0
    bins = 32
    counts = []
    for _ in range(bins):
        counts.append(0)
    for i in range(n):
        idx = int((values[i] - mn) / span * float(bins - 1))
        if idx < 0:
            idx = 0
        if idx >= bins:
            idx = bins - 1
        counts[idx] = counts[idx] + 1
    ent = 0.0
    nf = float(n)
    for i in range(bins):
        if counts[i] > 0:
            p = float(counts[i]) / nf
            ent -= p * math.log(p) / math.log(2.0)
    return ent





def _is_date_string(s):
    n = len(s)
    if n < 6 or n > 32:
        return False
    bytes = s.encode('utf-8')
    has_sep = False
    has_digit = False
    for i in range(n):
        c = bytes[i]
        if c == int(45) or c == int(47) or c == int(58):
            has_sep = True
        if c >= int(48) and c <= int(57):
            has_digit = True
    return has_sep and has_digit



def _is_alphanumeric_id(s):
    n = len(s)
    if n < 2 or n > 30:
        return False
    bytes = s.encode('utf-8')
    has_digit = False
    has_alpha = False
    all_valid = True
    for i in range(n):
        c = bytes[i]
        if c >= int(48) and c <= int(57):
            has_digit = True
        elif (c >= int(65) and c <= int(90)) or (c >= int(97) and c <= int(122)):
            has_alpha = True
        elif c == int(45) or c == int(95):
            pass
        else:
            all_valid = False
            break
    return all_valid and has_digit and has_alpha



def _count_distinct_float(values):
    n = len(values)
    if n == 0:
        return 0
    sorted = values.copy()
    for i in range(1, n):
        key = sorted[i]
        j = i - 1
        while j >= 0 and sorted[j] > key:
            sorted[j + 1] = sorted[j]
            j -= 1
        sorted[j + 1] = key
    distinct = 1
    for i in range(1, n):
        if sorted[i] != sorted[i - 1]:
            distinct += 1
    return distinct





def _classify_semantic_type(field_name, values, strings, polarity, unit_hint, unique_ratio):
    has_numeric = len(values) > 0
    has_strings = len(strings) > 0


    name_signals_id = (
        contains_keyword(field_name, "id") or
        contains_keyword(field_name, "_no") or
        contains_keyword(field_name, "number") or
        contains_keyword(field_name, "code") or
        contains_keyword(field_name, "ref") or
        contains_keyword(field_name, "key")
    )

    if unique_ratio > 0.85:
        if name_signals_id:
            return "id"
        if has_strings and len(strings) > 0:
            id_count = 0
            check_n = len(strings)
            if check_n > 10:
                check_n = 10
            for i in range(check_n):
                if _is_alphanumeric_id(strings[i]):
                    id_count += 1
            if id_count > check_n / 2:
                return "id"


    if has_strings and len(strings) > 0:
        date_count = 0
        check_n = len(strings)
        if check_n > 5:
            check_n = 5
        for i in range(check_n):
            if _is_date_string(strings[i]):
                date_count += 1
        if date_count > check_n / 2:
            return "date"


    if has_strings and unique_ratio < 0.10:
        return "category"

    if not has_numeric:
        return "text"


    if unit_hint == "currency":
        return "currency"
    if unit_hint == "percentage":
        return "percentage"


    mn = values[0]
    mx = values[0]
    for i in range(1, len(values)):
        if values[i] < mn:
            mn = values[i]
        if values[i] > mx:
            mx = values[i]



    name_signals_pct = (
        contains_keyword(field_name, "pct") or
        contains_keyword(field_name, "percent") or
        contains_keyword(field_name, "ratio") or
        contains_keyword(field_name, "rate") or
        contains_keyword(field_name, "margin") or
        contains_keyword(field_name, "fill") or
        contains_keyword(field_name, "utiliz")
    )
    if mn >= 0.0 and mx <= 1.05 and (name_signals_pct or unit_hint == "percentage"):
        return "percentage"


    all_int = True
    for i in range(len(values)):
        if values[i] != float(int(values[i])):
            all_int = False
            break
    if all_int and mn >= 0.0 and mx < 1000000.0 and not name_signals_id:
        if contains_keyword(field_name, "qty") or contains_keyword(field_name, "quantity") or contains_keyword(field_name, "count") or contains_keyword(field_name, "units"):
            return "count"


    if polarity != 0 and (mx > 10.0 or mn < -10.0):
        return "currency"

    if polarity != 0:
        return "metric"

    return "metric"





def _extract_float_array(arr_json):
    result = []
    n = len(arr_json)
    bytes = arr_json.encode('utf-8')
    i = 0
    while i < n and bytes[i] != int(91):
        i += 1
    i += 1

    while i < n:

        while i < n and (bytes[i] == int(32) or bytes[i] == int(44) or bytes[i] == int(10) or bytes[i] == int(13)):
            i += 1
        if i >= n or bytes[i] == int(93):
            break


        if bytes[i] == int(110) or bytes[i] == int(116) or bytes[i] == int(102):
            while i < n and bytes[i] != int(44) and bytes[i] != int(93):
                i += 1
            continue




        if bytes[i] == int(34):
            i += 1
            str_start = i
            while i < n and bytes[i] != int(34):
                i += 1
            num_str = _substr(arr_json, str_start, i)
            if i < n:
                i += 1  # skip closing "

            if len(num_str) > 0:
                first = num_str.encode('utf-8')[0]
                looks_numeric = (
                    (first >= int(48) and first <= int(57)) or  # 0-9
                    first == int(45) or  # -
                    first == int(46)     # .
                )
                if looks_numeric:
                    result.append(parse_float64(num_str))
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
        if i > start:
            result.append(parse_float64(_substr(arr_json, start, i)))
        else:
            i += 1  # unrecognised token — always advance to prevent infinite loop

    return result



def _extract_string_array(arr_json):
    result = []
    n = len(arr_json)
    bytes = arr_json.encode('utf-8')
    i = 0
    while i < n and bytes[i] != int(91):
        i += 1
    i += 1
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
            result.append(_substr(arr_json, start, i))
            i += 1
        else:
            while i < n and bytes[i] != int(44) and bytes[i] != int(93):
                i += 1
    return result





def _find_bracket_value(s, key):
    key_quoted = '"' + key + '"'
    pos = s.find(key_quoted)
    if pos < 0:
        return ""
    after = _substr(s, pos + len(key_quoted), len(s))
    bracket = after.find("[")
    if bracket < 0:
        return ""
    return _substr(after, bracket, len(after))





def run_column_profile(raw):

    cols_key = '"columns"'
    cols_pos = raw.find(cols_key)
    if cols_pos < 0:
        return '{"error":"column_profile requires a columns object"}'


    after_cols = _substr(raw, cols_pos + len(cols_key), len(raw))
    outer_brace = after_cols.find("{")
    if outer_brace < 0:
        return '{"error":"columns must be a JSON object"}'

    cols_json = _substr(after_cols, outer_brace, len(after_cols))
    n = len(cols_json)
    bytes = cols_json.encode('utf-8')
    i = 1  # skip opening {

    result = str('{"profiles":{')
    first_col = True

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
        col_name = _substr(cols_json, name_start, i)
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


        values_arr_str = _find_bracket_value(col_obj, "values")
        strings_arr_str = _find_bracket_value(col_obj, "strings")

        values = []
        if len(values_arr_str) > 0:
            values = _extract_float_array(values_arr_str)

        strings = []
        if len(strings_arr_str) > 0:
            strings = _extract_string_array(strings_arr_str)


        polarity = detect_polarity(col_name)
        unit = detect_unit_hint(col_name)

        num_count = len(values)
        str_count = len(strings)
        total = num_count + str_count
        if total == 0:
            total = 1


        distinct_num = _count_distinct_float(values)
        str_hashes = []
        distinct_str = 0
        for k in range(str_count):
            h = _djb2_str(strings[k])
            found = False
            for m in range(len(str_hashes)):
                if str_hashes[m] == h:
                    found = True
                    break
            if not found:
                str_hashes.append(h)
                distinct_str += 1
        unique_ratio = float(distinct_num + distinct_str) / float(total)


        mean_val = 0.0
        std_val = 0.0
        min_val = 0.0
        max_val = 0.0
        entropy_val = 0.0
        dist_name = str("categorical")
        dist_params = str("{}")

        if num_count > 0:
            mean_val = values[0]
            min_val = values[0]
            max_val = values[0]
            for k in range(1, num_count):
                mean_val += values[k]
                if values[k] < min_val:
                    min_val = values[k]
                if values[k] > max_val:
                    max_val = values[k]
            mean_val /= float(num_count)

            if num_count > 1:
                sq_sum = 0.0
                for k in range(num_count):
                    diff = values[k] - mean_val
                    sq_sum += diff * diff
                std_val = math.sqrt(sq_sum / float(num_count - 1))

            entropy_val = _approx_entropy(values)
            infer_result = infer_distribution_from_values(values)
            dist_name = infer_result[0]
            dist_params = infer_result[1]

        sem_type = _classify_semantic_type(
            col_name, values, strings, polarity, unit, unique_ratio
        )


        confidence = 0.7
        if sem_type == "id" and unique_ratio > 0.95:
            confidence = 0.95
        elif sem_type == "currency" and unit == "currency" and polarity != 0:
            confidence = 0.92
        elif sem_type == "date" and str_count > 0:
            confidence = 0.90
        elif sem_type == "category" and str_count > 0 and unique_ratio < 0.05:
            confidence = 0.88


        if not first_col:
            result += ","
        first_col = False

        result += '"' + col_name + '":{'
        result += '"semantic_type":"' + sem_type + '",'
        result += '"polarity":' + str(polarity) + ','
        result += '"unique_ratio":' + str(unique_ratio) + ','
        result += '"sample_count":' + str(num_count + str_count) + ','
        result += '"confidence":' + str(confidence)

        if num_count > 0:
            result += ',"mean":' + str(mean_val)
            result += ',"std":' + str(std_val)
            result += ',"min":' + str(min_val)
            result += ',"max":' + str(max_val)
            result += ',"entropy":' + str(entropy_val)
            result += ',"distribution":"' + dist_name + '"'
            result += ',"dist_params":' + dist_params

        if len(unit) > 0:
            result += ',"unit":"' + unit + '"'

        result += "}"

    result += "}}"
    return result
