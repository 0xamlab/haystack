"""Python equivalent of mojo/engine/ml.metrics.mojo (auto-generated)."""
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

class PRF1Result:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('precision')
        self.precision = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('recall')
        self.recall = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('f1')
        self.f1 = _v2 if _v2 is not None else 0.0
    def __repr__(self):
        return f'PRF1Result({vars(self)})'

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

def accuracy(predicted, actual):
    n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)

    correct = 0
    for i in range(n):
        if int(predicted[i] + 0.5) == int(actual[i] + 0.5):
            correct += 1
    return float(correct) / float(n)






def mse(predicted, actual):
    n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)

    s = 0.0
    for i in range(n):
        d = predicted[i] - actual[i]
        s += d * d
    return s / float(n)






def rmse(predicted, actual):
    return math.sqrt(mse(predicted, actual))






def mae(predicted, actual):
    n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)

    s = 0.0
    for i in range(n):
        s += math.fabs(predicted[i] - actual[i])
    return s / float(n)






def r2_score(predicted, actual):
    n = len(predicted)
    if n == 0:
        return 0.0
    if len(actual) < n:
        n = len(actual)


    mean_actual = 0.0
    for i in range(n):
        mean_actual += actual[i]
    mean_actual /= float(n)

    ss_res = 0.0
    ss_tot = 0.0
    for i in range(n):
        d_res = actual[i] - predicted[i]
        ss_res += d_res * d_res
        d_tot = actual[i] - mean_actual
        ss_tot += d_tot * d_tot

    if ss_tot == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot






def confusion_matrix(predicted, actual, n_classes):

    mat = []
    for _ in range(n_classes):
        row = []
        for _ in range(n_classes):
            row.append(0)
        mat.append(row)

    n = len(predicted)
    if len(actual) < n:
        n = len(actual)

    for i in range(n):
        a = actual[i]
        p = predicted[i]
        if a >= 0 and a < n_classes and p >= 0 and p < n_classes:
            mat[a][p] = mat[a][p] + 1

    return mat






def precision_recall_f1(predicted, actual):
    tp = 0
    fp = 0
    fn_count = 0

    n = len(predicted)
    if len(actual) < n:
        n = len(actual)

    for i in range(n):
        if predicted[i] == 1 and actual[i] == 1:
            tp += 1
        elif predicted[i] == 1 and actual[i] == 0:
            fp += 1
        elif predicted[i] == 0 and actual[i] == 1:
            fn_count += 1

    precision = 0.0
    if tp + fp > 0:
        precision = float(tp) / float(tp + fp)

    recall = 0.0
    if tp + fn_count > 0:
        recall = float(tp) / float(tp + fn_count)

    f1 = 0.0
    if precision + recall > 0.0:
        f1 = 2.0 * precision * recall / (precision + recall)

    return PRF1Result(precision, recall, f1)
