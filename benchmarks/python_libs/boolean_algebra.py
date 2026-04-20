"""Python equivalent of mojo/engine/boolean_algebra.mojo (auto-generated)."""
import math
import random as _rng

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

def _apply_op_2(a, b, op):
    if op == 0:
        return bool_and(a, b)
    elif op == 1:
        return bool_or(a, b)
    elif op == 2:
        return bool_xor(a, b)
    elif op == 3:
        return bool_implies(a, b)
    elif op == 4:
        return bool_iff(a, b)
    return False






def bool_and(a, b):
    return a and b






def bool_or(a, b):
    return a or b






def bool_not(a):
    return not a






def bool_xor(a, b):
    return a != b






def bool_implies(a, b):
    return (not a) or b






def bool_iff(a, b):
    return a == b






def truth_table_2(op):
    table = []

    vals = []
    vals.append(False)
    vals.append(True)
    for i in range(2):
        for j in range(2):
            a = vals[i]
            b = vals[j]
            result = _apply_op_2(a, b, op)
            row = []
            row.append(a)
            row.append(b)
            row.append(result)
            table.append(row)
    return table






def eval_dnf(values, clauses):
    for ci in range(len(clauses)):
        clause_true = True
        for li in range(len(clauses[ci])):
            lit = clauses[ci][li]
            idx = 0
            negated = 0
            if lit < 0:
                idx = -lit - 1
                negated = True
            else:
                idx = lit - 1
                negated = False
            if idx < 0 or idx >= len(values):
                clause_true = False
                break
            val = values[idx]
            if negated:
                val = not val
            if not val:
                clause_true = False
                break
        if clause_true:
            return True
    return False






def eval_cnf(values, clauses):
    for ci in range(len(clauses)):
        clause_true = False
        for li in range(len(clauses[ci])):
            lit = clauses[ci][li]
            idx = 0
            negated = 0
            if lit < 0:
                idx = -lit - 1
                negated = True
            else:
                idx = lit - 1
                negated = False
            if idx < 0 or idx >= len(values):
                continue
            val = values[idx]
            if negated:
                val = not val
            if val:
                clause_true = True
                break
        if not clause_true:
            return False
    return True






def is_tautology_2var(op):
    table = truth_table_2(op)
    for i in range(len(table)):
        if not table[i][2]:
            return False
    return True






def count_satisfying_2var(op):
    table = truth_table_2(op)
    count = 0
    for i in range(len(table)):
        if table[i][2]:
            count += 1
    return count






def majority_vote(values):
    count = 0
    n = len(values)
    for i in range(n):
        if values[i]:
            count += 1
    return count * 2 > n






def parity(values):
    result = False
    for i in range(len(values)):
        if values[i]:
            result = not result
    return result
