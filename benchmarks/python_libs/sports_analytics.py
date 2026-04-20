"""Python equivalent of mojo/engine/sports_analytics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
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

def batting_average(hits, at_bats):
    if at_bats == 0.0:
        return 0.0
    return hits / at_bats






def on_base_percentage(hits, walks, hbp, at_bats, sf):
    denom = at_bats + walks + hbp + sf
    if denom == 0.0:
        return 0.0
    return (hits + walks + hbp) / denom






def slugging_percentage(total_bases, at_bats):
    if at_bats == 0.0:
        return 0.0
    return total_bases / at_bats






def ops(obp, slg):
    return obp + slg






def era(earned_runs, innings_pitched):
    if innings_pitched == 0.0:
        return 0.0
    return (earned_runs / innings_pitched) * 9.0






def whip(walks, hits, innings_pitched):
    if innings_pitched == 0.0:
        return 0.0
    return (walks + hits) / innings_pitched






def passer_rating_nfl(comp, att, yards, td, interceptions):
    if att == 0.0:
        return 0.0
    a = (comp / att - 0.3) * 5.0
    b = (yards / att - 3.0) * 0.25
    c = (td / att) * 20.0
    d = 2.375 - (interceptions / att) * 25.0

    if a < 0.0:
        a = 0.0
    if a > 2.375:
        a = 2.375
    if b < 0.0:
        b = 0.0
    if b > 2.375:
        b = 2.375
    if c < 0.0:
        c = 0.0
    if c > 2.375:
        c = 2.375
    if d < 0.0:
        d = 0.0
    if d > 2.375:
        d = 2.375
    return (a + b + c + d) / 6.0 * 100.0






def pythagorean_wins(runs_scored, runs_allowed, exponent):
    if runs_scored <= 0.0 and runs_allowed <= 0.0:
        return 0.0
    if runs_scored <= 0.0:
        return 0.0
    if runs_allowed <= 0.0:
        return 1.0
    rs_e = math.exp(exponent * math.log(runs_scored))
    ra_e = math.exp(exponent * math.log(runs_allowed))
    denom = rs_e + ra_e
    if denom == 0.0:
        return 0.0
    return rs_e / denom






def elo_expected_score(rating_a, rating_b):
    exponent = (rating_b - rating_a) / 400.0
    return 1.0 / (1.0 + math.exp(exponent * math.log(10.0)))






def elo_new_rating(old_rating, k, actual_score, expected_score):
    return old_rating + k * (actual_score - expected_score)






def true_shooting_percentage(points, fga, fta):
    denom = 2.0 * (fga + 0.44 * fta)
    if denom == 0.0:
        return 0.0
    return points / denom






def player_efficiency_rating_approx(points, rebounds, assists, steals, blocks, turnovers, minutes, pace):
    if minutes == 0.0:
        return 0.0
    raw = points + rebounds + assists + steals + blocks - turnovers
    pace_factor = pace / 100.0
    return (raw / minutes) * pace_factor
