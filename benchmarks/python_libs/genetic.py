"""Python equivalent of mojo/engine/genetic.mojo (auto-generated)."""
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
    from std.math import log
except Exception:
    pass
try:
    from std.random import random_float64
except Exception:
    pass

PI = 3.141592653589793

class Individual:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('genes')
        self.genes = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('fitness')
        self.fitness = _v1 if _v1 is not None else 0.0
    def __repr__(self):
        return f'Individual({vars(self)})'

class GAConfig:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('population_size')
        self.population_size = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('n_genes')
        self.n_genes = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('mutation_rate')
        self.mutation_rate = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('crossover_rate')
        self.crossover_rate = _v3 if _v3 is not None else 0.0
        _v4 = args[4] if 4 < len(args) else kwargs.get('elitism')
        self.elitism = _v4 if _v4 is not None else 0
        _v5 = args[5] if 5 < len(args) else kwargs.get('gene_min')
        self.gene_min = _v5 if _v5 is not None else 0.0
        _v6 = args[6] if 6 < len(args) else kwargs.get('gene_max')
        self.gene_max = _v6 if _v6 is not None else 0.0
    def __repr__(self):
        return f'GAConfig({vars(self)})'

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

def _randn():
    u1 = random_float64()
    u2 = random_float64()
    if u1 < 1e-15:
        u1 = 1e-15
    r = math.sqrt(-2.0 * math.log(u1))
    theta = 2.0 * math.pi * u2

    v = theta
    while v > math.pi:
        v -= 2.0 * math.pi
    while v < -math.pi:
        v += 2.0 * math.pi
    x2 = v * v
    x4 = x2 * x2
    x6 = x4 * x2
    x8 = x6 * x2
    x10 = x8 * x2
    cosv = 1.0 - x2 / 2.0 + x4 / 24.0 - x6 / 720.0 + x8 / 40320.0 - x10 / 3628800.0
    return r * cosv






def _evaluate(ind, eval_fn_id):
    if eval_fn_id == 0:
        s = 0.0
        for i in range(len(ind.genes)):
            diff = ind.genes[i] - float(i)
            s += diff * diff
        return -s
    return 0.0






def _sort_by_fitness(pop):
    n = len(pop)
    for i in range(1, n):
        key_fit = pop[i].fitness
        key_genes = []
        for g in range(len(pop[i].genes)):
            key_genes.append(pop[i].genes[g])
        j = i - 1
        while j >= 0 and pop[j].fitness < key_fit:

            sg = []
            for g in range(len(pop[j].genes)):
                sg.append(pop[j].genes[g])
            pop[j + 1] = Individual(sg, pop[j].fitness)
            j -= 1
        pop[j + 1] = Individual(key_genes, key_fit)





