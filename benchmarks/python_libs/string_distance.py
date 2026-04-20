"""Python equivalent of mojo/engine/string_distance.mojo (auto-generated)."""
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

def _sx_code(c):
    ch = c
    if ch >= 97 and ch <= 122:
        ch = ch - 32

    if ch == 66 or ch == 70 or ch == 80 or ch == 86:
        return 49  # '1'

    if ch == 67 or ch == 71 or ch == 74 or ch == 75 or ch == 81 or ch == 83 or ch == 88 or ch == 90:
        return 50  # '2'

    if ch == 68 or ch == 84:
        return 51  # '3'

    if ch == 76:
        return 52  # '4'

    if ch == 77 or ch == 78:
        return 53  # '5'

    if ch == 82:
        return 54  # '6'
    return 48  # '0' for vowels, H, W, Y



def _levenshtein(a, b):
    m = len(a)
    n = len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')
    prev = []
    curr = []
    for j in range(n + 1):
        prev.append(j)
        curr.append(0)
    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            cost = 0
            if a_bytes[i - 1] != b_bytes[j - 1]:
                cost = 1
            d = prev[j] + 1
            ins = curr[j - 1] + 1
            sub = prev[j - 1] + cost
            best = d
            if ins < best:
                best = ins
            if sub < best:
                best = sub
            curr[j] = best
        for j in range(n + 1):
            tmp = prev[j]
            prev[j] = curr[j]
            curr[j] = tmp
    return prev[n]



def damerau_levenshtein(a, b):
    m = len(a)
    n = len(b)
    if m == 0:
        return n
    if n == 0:
        return m

    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')


    dp = []
    for _ in range((m + 1) * (n + 1)):
        dp.append(0)



    for i in range(m + 1):
        dp[i * (n + 1)] = i
    for j in range(n + 1):
        dp[j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0
            if a_bytes[i - 1] != b_bytes[j - 1]:
                cost = 1
            del_cost = dp[(i - 1) * (n + 1) + j] + 1
            ins_cost = dp[i * (n + 1) + (j - 1)] + 1
            sub_cost = dp[(i - 1) * (n + 1) + (j - 1)] + cost
            best = del_cost
            if ins_cost < best:
                best = ins_cost
            if sub_cost < best:
                best = sub_cost

            if i > 1 and j > 1 and a_bytes[i - 1] == b_bytes[j - 2] and a_bytes[i - 2] == b_bytes[j - 1]:
                trans_cost = dp[(i - 2) * (n + 1) + (j - 2)] + cost
                if trans_cost < best:
                    best = trans_cost
            dp[i * (n + 1) + j] = best

    return dp[m * (n + 1) + n]






def soundex(word):
    if len(word) == 0:
        return "0000"

    w_bytes = word.encode('utf-8')


    first = int(w_bytes[0])
    if first >= 97 and first <= 122:
        first = first - 32

    result = chr(first)

    last_code = _sx_code(w_bytes[0])
    count = 1

    for i in range(1, len(word)):
        if count >= 4:
            break
        ch = w_bytes[i]

        uch = ch
        if uch >= 97 and uch <= 122:
            uch = uch - 32

        if uch == 72 or uch == 87:
            continue
        code = _sx_code(ch)
        if code != 48 and code != last_code:
            result += chr(int(code))
            count += 1


        last_code = code

    while count < 4:
        result += "0"
        count += 1

    return result






def edit_similarity(a, b):
    la = len(a)
    lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    mx = la
    if lb > mx:
        mx = lb
    dist = _levenshtein(a, b)
    return 1.0 - float(dist) / float(mx)






def common_prefix_length(a, b):
    la = len(a)
    lb = len(b)
    n = la if la < lb else lb
    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')
    count = 0
    for i in range(n):
        if a_bytes[i] == b_bytes[i]:
            count += 1
        else:
            break
    return count






def common_suffix_length(a, b):
    la = len(a)
    lb = len(b)
    n = la if la < lb else lb
    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')
    count = 0
    for i in range(n):
        if a_bytes[la - 1 - i] == b_bytes[lb - 1 - i]:
            count += 1
        else:
            break
    return count






def bigrams(s):
    result = []
    n = len(s)
    if n < 2:
        return result
    s_bytes = s.encode('utf-8')
    for i in range(n - 1):
        bg = chr(int(s_bytes[i])) + chr(int(s_bytes[i + 1]))
        result.append(bg)
    return result






def dice_coefficient(a, b):
    bg_a = bigrams(a)
    bg_b = bigrams(b)
    na = len(bg_a)
    nb = len(bg_b)
    if na == 0 and nb == 0:
        return 1.0 if a == b else 0.0
    if na == 0 or nb == 0:
        return 0.0


    used = []
    for _ in range(nb):
        used.append(False)
    matches = 0
    for i in range(na):
        for j in range(nb):
            if not used[j] and bg_a[i] == bg_b[j]:
                used[j] = True
                matches += 1
                break
    return 2.0 * float(matches) / float(na + nb)






def overlap_coefficient(a, b):
    bg_a = bigrams(a)
    bg_b = bigrams(b)
    na = len(bg_a)
    nb = len(bg_b)
    if na == 0 and nb == 0:
        return 1.0 if a == b else 0.0
    if na == 0 or nb == 0:
        return 0.0
    mn = na if na < nb else nb
    used = []
    for _ in range(nb):
        used.append(False)
    matches = 0
    for i in range(na):
        for j in range(nb):
            if not used[j] and bg_a[i] == bg_b[j]:
                used[j] = True
                matches += 1
                break
    return float(matches) / float(mn)






def string_reverse(s):
    n = len(s)
    if n == 0:
        return str("")
    s_bytes = s.encode('utf-8')
    result = str("")
    i = n - 1
    while i >= 0:
        result += chr(int(s_bytes[i]))
        i -= 1
    return result






def is_palindrome(s):

    s_bytes = s.encode('utf-8')
    cleaned = []
    for i in range(len(s)):
        c = s_bytes[i]
        if c == 32:
            continue
        if c >= 65 and c <= 90:
            c = c + 32
        cleaned.append(c)
    n = len(cleaned)
    if n <= 1:
        return True
    left = 0
    right = n - 1
    while left < right:
        if cleaned[left] != cleaned[right]:
            return False
        left += 1
        right -= 1
    return True
