"""Python equivalent of mojo/engine/pension.mojo (auto-generated)."""
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

def _pow(base, n):
    if n == 0:
        return 1.0
    result = 1.0
    b = base
    exp = n
    if exp < 0:
        b = 1.0 / b
        exp = -exp
    for _ in range(exp):
        result *= b
    return result






def replacement_ratio(pension_income, final_salary):
    if math.fabs(final_salary) < 1e-30:
        return 0.0
    return pension_income / final_salary * 100.0






def defined_benefit_pension(years, salary, accrual_rate):
    return years * salary * accrual_rate






def defined_contribution_value(contributions, return_rate, years):
    if math.fabs(return_rate) < 1e-30:
        return contributions * float(years)
    growth = (1.0 + return_rate) ** (years) - 1.0
    return contributions * growth / return_rate






def annuity_factor(rate, years):
    if math.fabs(rate) < 1e-30:
        return float(years)
    pv = 1.0 - (1.0 + rate) ** (-years)
    return pv / rate






def pension_lump_sum_from_annuity(annual_pension, annuity_factor_val):
    return annual_pension * annuity_factor_val






def funding_ratio(plan_assets, plan_liabilities):
    if math.fabs(plan_liabilities) < 1e-30:
        return 0.0
    return plan_assets / plan_liabilities * 100.0






def contribution_rate_required(target_fund, years, salary, return_rate):
    if math.fabs(salary) < 1e-30:
        return 0.0
    if math.fabs(return_rate) < 1e-30:
        denom = salary * float(years)
        if math.fabs(denom) < 1e-30:
            return 0.0
        return target_fund / denom * 100.0
    fv_factor = ((1.0 + return_rate) ** (years) - 1.0) / return_rate
    denom = salary * fv_factor
    if math.fabs(denom) < 1e-30:
        return 0.0
    return target_fund / denom * 100.0






def inflation_adjusted_pension(nominal, inflation_rate, years):
    divisor = (1.0 + inflation_rate) ** (years)
    if math.fabs(divisor) < 1e-30:
        return 0.0
    return nominal / divisor






def pension_gap(required_income, expected_pension):
    return required_income - expected_pension






def social_security_bend_points(aime, bp1, bp2):
    part1 = aime
    if part1 > bp1:
        part1 = bp1
    mid = aime
    if mid > bp2:
        mid = bp2
    part2 = mid - bp1
    if part2 < 0.0:
        part2 = 0.0
    part3 = aime - bp2
    if part3 < 0.0:
        part3 = 0.0
    return 0.9 * part1 + 0.32 * part2 + 0.15 * part3






def years_to_full_vesting(service_years, vesting_schedule):
    if math.fabs(vesting_schedule) < 1e-30:
        return 100.0
    pct = service_years / vesting_schedule * 100.0
    if pct > 100.0:
        pct = 100.0
    if pct < 0.0:
        pct = 0.0
    return pct






def withdrawal_rate(annual_withdrawal, portfolio_value):
    if math.fabs(portfolio_value) < 1e-30:
        return 0.0
    return annual_withdrawal / portfolio_value * 100.0
