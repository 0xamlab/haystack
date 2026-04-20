"""Python equivalent of mojo/engine/blockchain.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log as _log
except Exception:
    pass
try:
    from std.math import pow as _pow
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

def _log2(x):
    if x <= 0.0:
        return 0.0
    return math.math.log(x) / math.math.log(2.0)



def _ceil_int(x):
    i = int(x)
    if float(i) < x:
        return i + 1
    return i






def block_reward_halving(initial_reward, halvings):
    if halvings < 0:
        return initial_reward
    return initial_reward / (2.0) ** (float(halvings))



def hash_rate_to_difficulty(hash_rate, block_time_sec):
    return hash_rate * block_time_sec / (2.0) ** (32.0)



def transaction_fee_priority(base_fee, tip):
    return base_fee + tip



def gas_cost(gas_used, gas_price_gwei):
    return gas_used * gas_price_gwei / 1e9



def confirmations_security(confirmations, attack_hashrate_pct):
    if confirmations <= 0:
        return 1.0
    return (attack_hashrate_pct / 100.0) ** (float(confirmations))



def merkle_tree_depth(n_transactions):
    if n_transactions <= 1:
        return 0
    return _ceil_int(math.math.log2(float(n_transactions)))



def tps_throughput(transactions, time_seconds):
    if time_seconds == 0.0:
        return 0.0
    return float(transactions) / time_seconds



def block_size_utilization(used_bytes, max_bytes):
    if max_bytes == 0.0:
        return 0.0
    return used_bytes / max_bytes * 100.0



def staking_apy(rewards_per_year, staked_amount):
    if staked_amount == 0.0:
        return 0.0
    return rewards_per_year / staked_amount * 100.0



def validator_uptime(online_slots, total_slots):
    if total_slots == 0.0:
        return 0.0
    return online_slots / total_slots * 100.0



def finality_time_pbft(n_validators, round_time):
    return 3.0 * round_time



def token_inflation_rate(new_supply, total_supply):
    if total_supply == 0.0:
        return 0.0
    return new_supply / total_supply * 100.0
