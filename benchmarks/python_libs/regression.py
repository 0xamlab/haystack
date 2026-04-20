"""Python equivalent of mojo/engine/regression.mojo (auto-generated)."""
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

class RegressionResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('coefficients')
        self.coefficients = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('intercept')
        self.intercept = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('r_squared')
        self.r_squared = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('residuals')
        self.residuals = _v3 if _v3 is not None else []
    def __repr__(self):
        return f'RegressionResult({vars(self)})'

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

def _solve_normal_equations(XtX, Xty):
    p = len(Xty)


    aug = []
    for i in range(p):
        row = []
        for j in range(p):
            row.append(XtX[i][j])
        row.append(Xty[i])
        aug.append(row)


    for col in range(p):

        max_val = math.fabs(aug[col][col])
        max_row = col
        for row in range(col + 1, p):
            if math.fabs(aug[row][col]) > max_val:
                max_val = math.fabs(aug[row][col])
                max_row = row

        if max_row != col:
            tmp = aug[col].copy()
            aug[col] = aug[max_row].copy()
            aug[max_row] = tmp

        pivot = aug[col][col]
        if math.fabs(pivot) < 1e-15:
            continue


        for row in range(col + 1, p):
            factor = aug[row][col] / pivot
            for j in range(col, p + 1):
                aug[row][j] -= factor * aug[col][j]


    beta = []
    for _ in range(p):
        beta.append(0.0)
    for i in range(p - 1, -1, -1):
        s = aug[i][p]
        for j in range(i + 1, p):
            s -= aug[i][j] * beta[j]
        if math.fabs(aug[i][i]) > 1e-15:
            beta[i] = s / aug[i][i]
    return beta






def r_squared(y_actual, y_predicted):
    n = len(y_actual)
    if n == 0:
        return 0.0
    mean_y = 0.0
    for i in range(n):
        mean_y += y_actual[i]
    mean_y /= float(n)

    ss_tot = 0.0
    ss_res = 0.0
    for i in range(n):
        dt = y_actual[i] - mean_y
        ss_tot += dt * dt
        dr = y_actual[i] - y_predicted[i]
        ss_res += dr * dr
    if ss_tot < 1e-15:
        return 1.0 if ss_res < 1e-15 else 0.0
    return 1.0 - ss_res / ss_tot



def mse(y_actual, y_predicted):
    n = len(y_actual)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        d = y_actual[i] - y_predicted[i]
        total += d * d
    return total / float(n)



def rmse(y_actual, y_predicted):
    return math.sqrt(mse(y_actual, y_predicted))






def predict(X, coefficients, intercept):
    n = len(X)
    result = []
    for i in range(n):
        val = intercept
        p = len(X[i])
        for j in range(p):
            val += X[i][j] * coefficients[j]
        result.append(val)
    return result






def ols_simple(x, y):
    n = len(x)
    if n == 0:
        return RegressionResult([], 0.0, 0.0, [])

    mean_x = 0.0
    mean_y = 0.0
    for i in range(n):
        mean_x += x[i]
        mean_y += y[i]
    mean_x /= float(n)
    mean_y /= float(n)

    ss_xy = 0.0
    ss_xx = 0.0
    for i in range(n):
        dx = x[i] - mean_x
        ss_xy += dx * (y[i] - mean_y)
        ss_xx += dx * dx

    slope = 0.0
    if math.fabs(ss_xx) > 1e-15:
        slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x


    residuals = []
    y_pred = []
    for i in range(n):
        yp = slope * x[i] + intercept
        y_pred.append(yp)
        residuals.append(y[i] - yp)

    r2 = r_squared(y, y_pred)

    coeffs = []
    coeffs.append(slope)
    return RegressionResult(coeffs, intercept, r2, residuals)






def ols_multiple(X, y):
    n = len(X)
    if n == 0:
        return RegressionResult([], 0.0, 0.0, [])
    p_orig = len(X[0])
    p = p_orig + 1  # +1 for intercept column



    XtX = []
    for i in range(p):
        row = []
        for _ in range(p):
            row.append(0.0)
        XtX.append(row)
    Xty = []
    for _ in range(p):
        Xty.append(0.0)

    for i in range(n):

        xi = []
        xi.append(1.0)
        for j in range(p_orig):
            xi.append(X[i][j])
        for a in range(p):
            Xty[a] += xi[a] * y[i]
            for b in range(p):
                XtX[a][b] += xi[a] * xi[b]

    beta = _solve_normal_equations(XtX, Xty)

    intercept = beta[0]
    coeffs = []
    for j in range(1, p):
        coeffs.append(beta[j])


    y_pred = predict(X, coeffs, intercept)
    residuals = []
    for i in range(n):
        residuals.append(y[i] - y_pred[i])
    r2 = r_squared(y, y_pred)

    return RegressionResult(coeffs, intercept, r2, residuals)






def ridge_regression(X, y, alpha=1.0):
    n = len(X)
    if n == 0:
        return RegressionResult([], 0.0, 0.0, [])
    p_orig = len(X[0])
    p = p_orig + 1

    XtX = []
    for i in range(p):
        row = []
        for _ in range(p):
            row.append(0.0)
        XtX.append(row)
    Xty = []
    for _ in range(p):
        Xty.append(0.0)

    for i in range(n):
        xi = []
        xi.append(1.0)
        for j in range(p_orig):
            xi.append(X[i][j])
        for a in range(p):
            Xty[a] += xi[a] * y[i]
            for b in range(p):
                XtX[a][b] += xi[a] * xi[b]


    for j in range(1, p):
        XtX[j][j] += alpha

    beta = _solve_normal_equations(XtX, Xty)

    intercept = beta[0]
    coeffs = []
    for j in range(1, p):
        coeffs.append(beta[j])

    y_pred = predict(X, coeffs, intercept)
    residuals = []
    for i in range(n):
        residuals.append(y[i] - y_pred[i])
    r2 = r_squared(y, y_pred)

    return RegressionResult(coeffs, intercept, r2, residuals)






def polynomial_features(x, degree):
    n = len(x)
    result = []
    for i in range(n):
        row = []
        val = 1.0
        for d in range(degree):
            val *= x[i]
            row.append(val)
        result.append(row)
    return result
