"""Python equivalent of mojo/engine/wavelet.mojo (auto-generated)."""
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

def haar_forward(data):
    n = len(data)
    half = n // 2
    out = []
    s2 = math.sqrt(2.0)

    for i in range(half):
        out.append((data[2 * i] + data[2 * i + 1]) / s2)

    for i in range(half):
        out.append((data[2 * i] - data[2 * i + 1]) / s2)
    return out






def haar_inverse(coeffs):
    n = len(coeffs)
    half = n // 2
    out = []
    s2 = math.sqrt(2.0)
    for i in range(half):
        a = coeffs[i]
        d = coeffs[half + i]
        out.append((a + d) / s2)
        out.append((a - d) / s2)
    return out






def haar_multilevel(data, levels):
    current = data.copy()
    n = len(current)
    result = []

    for i in range(n):
        result.append(0.0)
    length = n
    for lev in range(levels):
        if length < 2:
            break
        half = length // 2
        s2 = math.sqrt(2.0)
        approx = []
        detail = []
        for i in range(half):
            approx.append((current[2 * i] + current[2 * i + 1]) / s2)
            detail.append((current[2 * i] - current[2 * i + 1]) / s2)

        for i in range(half):
            result[half + i] = detail[i]

        current = []
        for i in range(half):
            current.append(approx[i])
        length = half

    for i in range(length):
        result[i] = current[i]
    return result






def haar_multilevel_inverse(coeffs, levels):
    n = len(coeffs)

    length = n
    for lev in range(levels):
        length = length // 2

    current = []
    for i in range(length):
        current.append(coeffs[i])
    s2 = math.sqrt(2.0)
    for lev in range(levels):
        half = len(current)
        detail_start = half  # detail coefficients start at this offset in coeffs
        reconstructed = []
        for i in range(half):
            a = current[i]
            d = coeffs[detail_start + i]
            reconstructed.append((a + d) / s2)
            reconstructed.append((a - d) / s2)
        current = reconstructed
    return current






def threshold_hard(coeffs, threshold):
    out = []
    for i in range(len(coeffs)):
        if math.fabs(coeffs[i]) < threshold:
            out.append(0.0)
        else:
            out.append(coeffs[i])
    return out






def threshold_soft(coeffs, threshold):
    out = []
    for i in range(len(coeffs)):
        val = math.fabs(coeffs[i])
        if val <= threshold:
            out.append(0.0)
        else:
            sign = 1.0
            if coeffs[i] < 0.0:
                sign = -1.0
            out.append(sign * (val - threshold))
    return out






def denoise_haar(data, threshold, levels=1):
    coeffs = haar_multilevel(data, levels)
    thresholded = threshold_soft(coeffs, threshold)
    return haar_multilevel_inverse(thresholded, levels)






def energy_ratio(coeffs):
    n = len(coeffs)
    if n == 0:
        return 0.0
    half = n // 2
    total_energy = 0.0
    detail_energy = 0.0
    for i in range(n):
        total_energy += coeffs[i] * coeffs[i]
    for i in range(half, n):
        detail_energy += coeffs[i] * coeffs[i]
    if total_energy < 1e-15:
        return 0.0
    return detail_energy / total_energy






def detail_coefficients(coeffs):
    n = len(coeffs)
    half = n // 2
    out = []
    for i in range(half, n):
        out.append(coeffs[i])
    return out






def approx_coefficients(coeffs):
    n = len(coeffs)
    half = n // 2
    out = []
    for i in range(half):
        out.append(coeffs[i])
    return out
