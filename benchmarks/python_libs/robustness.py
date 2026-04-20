"""Python equivalent of mojo/engine/robustness.mojo (auto-generated)."""
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
    from random import random_float64
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

def eval_test_func(x, func_id):
    n = len(x)
    if func_id == 0:
        s = 0.0
        for i in range(n):
            s += x[i]
        return s
    elif func_id == 1:
        if n == 0:
            return 0.0
        p = 1.0
        for i in range(n):
            p *= x[i]
        return p
    else:
        s = 0.0
        for i in range(n):
            s += float(i + 1) * x[i]
        return s






def perturbation_test(values, perturbation):
    n = len(values)
    result = []
    for i in range(n):
        r = random_float64() * 2.0 - 1.0
        result.append(values[i] + r * perturbation)
    return result






def sensitivity_one_at_a_time(baseline, index, delta, func_id):
    f0 = eval_test_func(baseline, func_id)
    perturbed = []
    for i in range(len(baseline)):
        if i == index:
            perturbed.append(baseline[i] + delta)
        else:
            perturbed.append(baseline[i])
    f1 = eval_test_func(perturbed, func_id)
    if math.fabs(delta) < 1e-15:
        return 0.0
    return (f1 - f0) / delta






def morris_screening(n_inputs, func_id, n_trajectories, delta):
    effects = []
    for i in range(n_inputs):
        effects.append(0.0)

    for _t in range(n_trajectories):
        base = []
        for i in range(n_inputs):
            base.append(random_float64())
        f_base = eval_test_func(base, func_id)

        for i in range(n_inputs):
            perturbed = []
            for j in range(n_inputs):
                if j == i:
                    perturbed.append(base[j] + delta)
                else:
                    perturbed.append(base[j])
            f_pert = eval_test_func(perturbed, func_id)
            ee = math.fabs((f_pert - f_base) / delta)
            effects[i] = effects[i] + ee

    if n_trajectories > 0:
        for i in range(n_inputs):
            effects[i] = effects[i] / float(n_trajectories)
    return effects






def sobol_first_order_estimate(n_inputs, func_id, n_samples):
    indices = []
    for i in range(n_inputs):
        indices.append(0.0)

    a_mat = []
    b_mat = []
    f_a = []
    f_b = []

    for s in range(n_samples):
        row_a = []
        row_b = []
        for j in range(n_inputs):
            row_a.append(random_float64())
            row_b.append(random_float64())
        f_a.append(eval_test_func(row_a, func_id))
        f_b.append(eval_test_func(row_b, func_id))
        a_mat.append(row_a)
        b_mat.append(row_b)

    mean_a = 0.0
    for s in range(n_samples):
        mean_a += f_a[s]
    mean_a /= float(n_samples)
    var_total = 0.0
    for s in range(n_samples):
        d = f_a[s] - mean_a
        var_total += d * d
    var_total /= float(n_samples)

    if var_total < 1e-15:
        return indices

    for i in range(n_inputs):
        cov_sum = 0.0
        for s in range(n_samples):
            ab_i = []
            for j in range(n_inputs):
                if j == i:
                    ab_i.append(b_mat[s][j])
                else:
                    ab_i.append(a_mat[s][j])
            f_ab_i = eval_test_func(ab_i, func_id)
            cov_sum += f_b[s] * (f_ab_i - f_a[s])
        si = cov_sum / (float(n_samples) * var_total)
        if si < 0.0:
            si = 0.0
        if si > 1.0:
            si = 1.0
        indices[i] = si
    return indices






def input_range_sweep(baseline, index, lo, hi, n_points, func_id):
    result = []
    if n_points <= 1:
        x = []
        for j in range(len(baseline)):
            if j == index:
                x.append(lo)
            else:
                x.append(baseline[j])
        row = []
        row.append(lo)
        row.append(eval_test_func(x, func_id))
        result.append(row)
        return result
    step = (hi - lo) / float(n_points - 1)
    for i in range(n_points):
        val = lo + float(i) * step
        x = []
        for j in range(len(baseline)):
            if j == index:
                x.append(val)
            else:
                x.append(baseline[j])
        row = []
        row.append(val)
        row.append(eval_test_func(x, func_id))
        result.append(row)
    return result






def tornado_data(baseline, deltas, func_id):
    n = len(baseline)
    result = []
    for i in range(n):
        d = 0.1
        if i < len(deltas):
            d = deltas[i]
        x_low = []
        x_high = []
        for j in range(n):
            if j == i:
                x_low.append(baseline[j] - d)
                x_high.append(baseline[j] + d)
            else:
                x_low.append(baseline[j])
                x_high.append(baseline[j])
        row = []
        row.append(eval_test_func(x_low, func_id))
        row.append(eval_test_func(x_high, func_id))
        result.append(row)
    return result






def robustness_score(results):
    n = len(results)
    if n == 0:
        return 0.0
    mean = 0.0
    for i in range(n):
        mean += results[i]
    mean /= float(n)
    if math.fabs(mean) < 1e-15:
        return 0.0
    var_sum = 0.0
    for i in range(n):
        d = results[i] - mean
        var_sum += d * d
    var_sum /= float(n)
    return math.sqrt(var_sum) / math.fabs(mean)
