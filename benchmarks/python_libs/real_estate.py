"""Python equivalent of mojo/engine/real_estate.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
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

def cap_rate(noi, property_value):
    if math.fabs(property_value) < 1e-30:
        return 0.0
    return noi / property_value * 100.0






def gross_rent_multiplier(price, annual_rent):
    if math.fabs(annual_rent) < 1e-30:
        return 0.0
    return price / annual_rent






def cash_on_cash_return(annual_cashflow, total_invested):
    if math.fabs(total_invested) < 1e-30:
        return 0.0
    return annual_cashflow / total_invested * 100.0






def debt_service_coverage(noi, annual_debt_service):
    if math.fabs(annual_debt_service) < 1e-30:
        return 0.0
    return noi / annual_debt_service






def loan_to_value(loan_amount, property_value):
    if math.fabs(property_value) < 1e-30:
        return 0.0
    return loan_amount / property_value * 100.0






def net_operating_income(gross_income, vacancy_rate, operating_expenses):
    return gross_income * (1.0 - vacancy_rate) - operating_expenses






def mortgage_payment(principal, monthly_rate, n_months):
    if monthly_rate <= 0.0 or n_months <= 0:
        if n_months > 0:
            return principal / float(n_months)
        return 0.0
    rn = math.exp(float(n_months) * math.log(1.0 + monthly_rate))
    return principal * monthly_rate * rn / (rn - 1.0)






def price_per_sqft(price, sqft):
    if math.fabs(sqft) < 1e-30:
        return 0.0
    return price / sqft






def break_even_ratio(operating_expenses, debt_service, gross_income):
    if math.fabs(gross_income) < 1e-30:
        return 0.0
    return (operating_expenses + debt_service) / gross_income * 100.0






def internal_rate_of_return_approx(initial, cashflow, years):
    if math.fabs(initial) < 1e-30 or years <= 0:
        return 0.0
    ratio = cashflow / initial
    if ratio <= 0.0:
        return 0.0
    return math.exp((1.0 / float(years)) * math.log(ratio)) - 1.0






def equity_buildup(original_loan, remaining_loan):
    return original_loan - remaining_loan






def appreciation_value(initial_value, annual_rate, years):
    if years <= 0:
        return initial_value
    return initial_value * math.exp(float(years) * math.log(1.0 + annual_rate))
