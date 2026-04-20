"""Python equivalent of mojo/engine/game_theory.mojo (auto-generated)."""
import math
import random as _rng

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

def nash_2x2(payoff_a, payoff_b):


    b00 = payoff_b[0][0]
    b01 = payoff_b[0][1]
    b10 = payoff_b[1][0]
    b11 = payoff_b[1][1]
    denom_p = (b00 - b01 - b10 + b11)
    p = 0.5
    if math.fabs(denom_p) > 1e-12:
        p = (b11 - b10) / denom_p
    if p < 0.0:
        p = 0.0
    if p > 1.0:
        p = 1.0



    a00 = payoff_a[0][0]
    a01 = payoff_a[0][1]
    a10 = payoff_a[1][0]
    a11 = payoff_a[1][1]
    denom_q = (a00 - a01 - a10 + a11)
    q = 0.5
    if math.fabs(denom_q) > 1e-12:
        q = (a11 - a01) / denom_q
    if q < 0.0:
        q = 0.0
    if q > 1.0:
        q = 1.0

    result = []
    result.append(p)
    result.append(q)
    return result






def minimax_value(payoff):
    rows = len(payoff)
    if rows == 0:
        return 0.0
    best = -1e300
    for i in range(rows):
        row = payoff[i].copy()
        cols = len(row)
        if cols == 0:
            continue
        row_min = row[0]
        for j in range(1, cols):
            if row[j] < row_min:
                row_min = row[j]
        if row_min > best:
            best = row_min
    return best






def dominated_strategy_check(payoff):
    rows = len(payoff)
    result = []
    if rows == 0:
        return result
    cols = len(payoff[0])
    for i in range(rows):
        dominated = False
        for j in range(rows):
            if i == j:
                continue

            all_better = True
            for k in range(cols):
                if payoff[j][k] <= payoff[i][k]:
                    all_better = False
                    break
            if all_better:
                dominated = True
                break
        result.append(dominated)
    return result






def expected_payoff(payoff, p_row, p_col):
    rows = len(payoff)
    total = 0.0
    for i in range(rows):
        row = payoff[i].copy()
        cols = len(row)
        for j in range(cols):
            total += p_row[i] * p_col[j] * row[j]
    return total






def prisoners_dilemma_payoff(p1_cooperate, p2_cooperate):
    result = []
    if p1_cooperate and p2_cooperate:
        result.append(3.0)
        result.append(3.0)
    elif p1_cooperate and not p2_cooperate:
        result.append(0.0)
        result.append(5.0)
    elif not p1_cooperate and p2_cooperate:
        result.append(5.0)
        result.append(0.0)
    else:
        result.append(1.0)
        result.append(1.0)
    return result






def iterated_pd(strategy1, strategy2, rounds):
    total1 = 0.0
    total2 = 0.0
    last_p1 = True  # last move of player 1 (True = cooperate)
    last_p2 = True  # last move of player 2

    for r in range(rounds):
        p1_coop = 0
        p2_coop = 0


        if strategy1 == 0:
            p1_coop = True
        elif strategy1 == 1:
            p1_coop = False
        else:
            if r == 0:
                p1_coop = True
            else:
                p1_coop = last_p2


        if strategy2 == 0:
            p2_coop = True
        elif strategy2 == 1:
            p2_coop = False
        else:
            if r == 0:
                p2_coop = True
            else:
                p2_coop = last_p1

        pay = prisoners_dilemma_payoff(p1_coop, p2_coop)
        total1 += pay[0]
        total2 += pay[1]
        last_p1 = p1_coop
        last_p2 = p2_coop

    result = []
    result.append(total1)
    result.append(total2)
    return result






def shapley_value_3player(v):


    phi = []
    phi.append(0.0)
    phi.append(0.0)
    phi.append(0.0)



    perms = []
    perms.append(0); perms.append(1); perms.append(2)
    perms.append(0); perms.append(2); perms.append(1)
    perms.append(1); perms.append(0); perms.append(2)
    perms.append(1); perms.append(2); perms.append(0)
    perms.append(2); perms.append(0); perms.append(1)
    perms.append(2); perms.append(1); perms.append(0)

    for p in range(6):
        coalition = 0  # bitmask
        for pos in range(3):
            player = perms[p * 3 + pos]
            bit = 1 << player
            new_coalition = coalition | bit
            marginal = v[new_coalition] - v[coalition]
            phi[player] = phi[player] + marginal
            coalition = new_coalition


    phi[0] = phi[0] / 6.0
    phi[1] = phi[1] / 6.0
    phi[2] = phi[2] / 6.0

    return phi






def pareto_optimal_outcomes(payoffs_a, payoffs_b):
    n = len(payoffs_a)
    result = []
    for i in range(n):
        is_optimal = True
        for j in range(n):
            if i == j:
                continue

            if payoffs_a[j] >= payoffs_a[i] and payoffs_b[j] >= payoffs_b[i]:
                if payoffs_a[j] > payoffs_a[i] or payoffs_b[j] > payoffs_b[i]:
                    is_optimal = False
                    break
        result.append(is_optimal)
    return result
