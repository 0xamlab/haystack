"""Python equivalent of mojo/engine/number_theory.mojo (auto-generated)."""
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

def is_prime(n):
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1

    witnesses = []
    witnesses.append(2)
    witnesses.append(3)
    witnesses.append(5)
    witnesses.append(7)
    for wi in range(len(witnesses)):
        a = witnesses[wi]
        if a >= n:
            continue
        x = mod_pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        composite = True
        for _ in range(r - 1):
            x = mod_pow(x, 2, n)
            if x == n - 1:
                composite = False
                break
        if composite:
            return False
    return True






def gcd(a, b):
    x = a
    y = b
    if x < 0:
        x = -x
    if y < 0:
        y = -y
    while y != 0:
        t = y
        y = x % y
        x = t
    return x



def lcm(a, b):
    if a == 0 or b == 0:
        return 0
    g = gcd(a, b)
    aa = a
    bb = b
    if aa < 0:
        aa = -aa
    if bb < 0:
        bb = -bb
    return (aa // g) * bb






def mod_pow(base, exp, modulus):
    if modulus == 1:
        return 0
    result = 1
    b = base % modulus
    if b < 0:
        b += modulus
    e = exp
    while e > 0:
        if e % 2 == 1:
            result = (result * b) % modulus
        e //= 2
        b = (b * b) % modulus
    return result






def euler_totient(n):
    if n <= 0:
        return 0
    if n == 1:
        return 1
    result = n
    m = n
    p = 2
    while p * p <= m:
        if m % p == 0:
            while m % p == 0:
                m //= p
            result -= result // p
        p += 1
    if m > 1:
        result -= result // m
    return result






def prime_factors(n):
    factors = []
    if n <= 1:
        return factors
    m = n
    while m % 2 == 0:
        factors.append(2)
        m //= 2
    f = 3
    while f * f <= m:
        while m % f == 0:
            factors.append(f)
            m //= f
        f += 2
    if m > 1:
        factors.append(m)
    return factors






def sieve_of_eratosthenes(limit):
    primes = []
    if limit < 2:
        return primes

    is_comp = []
    for _ in range(limit + 1):
        is_comp.append(False)
    p = 2
    while p * p <= limit:
        if not is_comp[p]:
            j = p * p
            while j <= limit:
                is_comp[j] = True
                j += p
        p += 1
    for i in range(2, limit + 1):
        if not is_comp[i]:
            primes.append(i)
    return primes






def is_coprime(a, b):
    return gcd(a, b) == 1






def extended_gcd(a, b):
    old_r = a
    r = b
    old_s = 1
    s = 0
    old_t = 0
    t = 1
    while r != 0:
        q = old_r // r
        tmp_r = r
        r = old_r - q * r
        old_r = tmp_r
        tmp_s = s
        s = old_s - q * s
        old_s = tmp_s
        tmp_t = t
        t = old_t - q * t
        old_t = tmp_t
    result = []
    result.append(old_r)
    result.append(old_s)
    result.append(old_t)
    return result






def mod_inverse(a, m):
    res = extended_gcd(a, m)
    if res[0] != 1:
        return -1
    inv = res[1] % m
    if inv < 0:
        inv += m
    return inv






def fibonacci(n):
    if n <= 0:
        return 0
    if n == 1:
        return 1
    a = 0
    b = 1
    for _ in range(2, n + 1):
        c = a + b
        a = b
        b = c
    return b






def is_perfect_square(n):
    if n < 0:
        return False
    if n == 0:
        return True

    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x * x == n
