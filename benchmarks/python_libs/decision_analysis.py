"""Python equivalent of mojo/engine/decision_analysis.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
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

def _pow_pos(base, exp):
    if base <= 0.0:
        return 0.0
    ln_base = math.log(base)
    return _exp_approx(exp * ln_base)



def _exp_approx(x):
    clamped = x
    if clamped > 20.0:
        clamped = 20.0
    if clamped < -20.0:
        clamped = -20.0
    result = 1.0
    term = 1.0
    for i in range(1, 30):
        term *= clamped / float(i)
        result += term
    return result






def _row_ev(payoffs, row, probs):
    n_states = len(probs)
    ev = 0.0
    for j in range(n_states):
        ev += payoffs[row][j] * probs[j]
    return ev






def expected_value(outcomes, probabilities):
    n = len(outcomes)
    result = 0.0
    for i in range(n):
        result += outcomes[i] * probabilities[i]
    return result






def expected_utility(outcomes, probabilities, risk_aversion):
    n = len(outcomes)
    result = 0.0
    gamma = risk_aversion
    if math.fabs(gamma - 1.0) < 1e-12:

        for i in range(n):
            x = outcomes[i]
            if x <= 0.0:
                x = 1e-15
            result += probabilities[i] * math.log(x)
    else:
        exp = 1.0 - gamma
        for i in range(n):
            x = outcomes[i]
            if x <= 0.0:
                x = 1e-15

            util = _pow_pos(x, exp) / exp
            result += probabilities[i] * util
    return result



def decision_matrix_best(payoffs, probabilities):
    n_alts = len(payoffs)
    best_idx = 0
    best_ev = _row_ev(payoffs, 0, probabilities)
    for i in range(1, n_alts):
        ev = _row_ev(payoffs, i, probabilities)
        if ev > best_ev:
            best_ev = ev
            best_idx = i
    return best_idx






def minimax_regret(payoffs):
    n_alts = len(payoffs)
    n_states = len(payoffs[0])

    best_per_state = []
    for j in range(n_states):
        best = payoffs[0][j]
        for i in range(1, n_alts):
            if payoffs[i][j] > best:
                best = payoffs[i][j]
        best_per_state.append(best)

    best_idx = 0
    best_max_regret = 1e300
    for i in range(n_alts):
        max_regret = 0.0
        for j in range(n_states):
            regret = best_per_state[j] - payoffs[i][j]
            if regret > max_regret:
                max_regret = regret
        if max_regret < best_max_regret:
            best_max_regret = max_regret
            best_idx = i
    return best_idx






def hurwicz_criterion(payoffs, alpha):
    n_alts = len(payoffs)
    best_idx = 0
    best_val = -1e300
    for i in range(n_alts):
        n_states = len(payoffs[i])
        row_min = payoffs[i][0]
        row_max = payoffs[i][0]
        for j in range(1, n_states):
            if payoffs[i][j] < row_min:
                row_min = payoffs[i][j]
            if payoffs[i][j] > row_max:
                row_max = payoffs[i][j]
        val = alpha * row_max + (1.0 - alpha) * row_min
        if val > best_val:
            best_val = val
            best_idx = i
    return best_idx






def value_of_perfect_info(payoffs, probabilities):
    n_alts = len(payoffs)
    n_states = len(probabilities)

    best_ev = _row_ev(payoffs, 0, probabilities)
    for i in range(1, n_alts):
        ev = _row_ev(payoffs, i, probabilities)
        if ev > best_ev:
            best_ev = ev

    ev_pi = 0.0
    for j in range(n_states):
        best = payoffs[0][j]
        for i in range(1, n_alts):
            if payoffs[i][j] > best:
                best = payoffs[i][j]
        ev_pi += probabilities[j] * best
    return ev_pi - best_ev






def sensitivity_range(payoffs, state_idx, n_steps=100):
    n_states = len(payoffs[0])
    result = []
    for s in range(n_steps):
        p = float(s) / float(n_steps - 1) if n_steps > 1 else 0.5
        probs = []
        remaining = 1.0 - p
        for j in range(n_states):
            if j == state_idx:
                probs.append(p)
            else:
                probs.append(remaining / float(n_states - 1))
        best = decision_matrix_best(payoffs, probs)
        row = []
        row.append(p)
        row.append(float(best))
        result.append(row)
    return result






def maximin(payoffs):
    n_alts = len(payoffs)
    best_idx = 0
    best_min = -1e300
    for i in range(n_alts):
        n_states = len(payoffs[i])
        row_min = payoffs[i][0]
        for j in range(1, n_states):
            if payoffs[i][j] < row_min:
                row_min = payoffs[i][j]
        if row_min > best_min:
            best_min = row_min
            best_idx = i
    return best_idx






def maximax(payoffs):
    n_alts = len(payoffs)
    best_idx = 0
    best_max = -1e300
    for i in range(n_alts):
        n_states = len(payoffs[i])
        row_max = payoffs[i][0]
        for j in range(1, n_states):
            if payoffs[i][j] > row_max:
                row_max = payoffs[i][j]
        if row_max > best_max:
            best_max = row_max
            best_idx = i
    return best_idx






def laplace_criterion(payoffs):
    n_alts = len(payoffs)
    best_idx = 0
    best_avg = -1e300
    for i in range(n_alts):
        n_states = len(payoffs[i])
        total = 0.0
        for j in range(n_states):
            total += payoffs[i][j]
        avg = total / float(n_states)
        if avg > best_avg:
            best_avg = avg
            best_idx = i
    return best_idx
