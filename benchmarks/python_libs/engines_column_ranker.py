"""Python equivalent of mojo/engine/engines.column_ranker.mojo (auto-generated)."""
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
    from field_mapper import to_lower
except Exception:
    pass
try:
    from json.parser import json_get_float
except Exception:
    pass
try:
    from json.parser import json_get_int
except Exception:
    pass
try:
    from json.parser import json_get_string
except Exception:
    pass
try:
    from json.parser import json_get_array
except Exception:
    pass
try:
    from json.parser import json_array_len
except Exception:
    pass
try:
    from json.parser import json_array_get
except Exception:
    pass
try:
    from json.parser import json_get_object
except Exception:
    pass
try:
    from conv import parse_float64
except Exception:
    pass

VEC_BUCKETS = 64    # bigram hash buckets
MAX_CANDS = 256   # hard cap on candidates per call
AMBIG_GAP = 0.08  # gap below which top-2 are "ambiguous"

class RankResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('source')
        self.source = _v0 if _v0 is not None else ""
        _v1 = args[1] if 1 < len(args) else kwargs.get('column')
        self.column = _v1 if _v1 is not None else ""
        _v2 = args[2] if 2 < len(args) else kwargs.get('score')
        self.score = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('name_sim')
        self.name_sim = _v3 if _v3 is not None else 0.0
        _v4 = args[4] if 4 < len(args) else kwargs.get('token_sim')
        self.token_sim = _v4 if _v4 is not None else 0.0
        _v5 = args[5] if 5 < len(args) else kwargs.get('type_boost')
        self.type_boost = _v5 if _v5 is not None else 0.0
        _v6 = args[6] if 6 < len(args) else kwargs.get('prior_boost')
        self.prior_boost = _v6 if _v6 is not None else 0.0
    def __repr__(self):
        return f'RankResult({vars(self)})'

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

def _substr(s, start, end):
    result = str("")
    bytes = s.encode('utf-8')
    n = len(s)
    i = start if start >= 0 else 0
    e = end if end <= n else n
    while i < e:
        result += chr(int(bytes[i]))
        i += 1
    return result



def _is_sep(c):
    return c == 95 or c == 32 or c == 45 or c == 46



def _normalize(s):
    result = str("")
    bytes = s.encode('utf-8')
    n = len(s)
    for i in range(n):
        c = bytes[i]
        if _is_sep(c):
            result += " "
        elif c >= 65 and c <= 90:
            result += chr(int(c + 32))
        else:
            result += chr(int(c))
    return result



def _tokens(s):
    result = []
    norm = _normalize(s)
    bytes = norm.encode('utf-8')
    n = len(norm)
    cur = str("")
    for i in range(n):
        c = bytes[i]
        if c == 32:
            if len(cur) > 0:
                result.append(cur)
                cur = str("")
        else:
            cur += chr(int(c))
    if len(cur) > 0:
        result.append(cur)
    return result





def _bigram_vec(s):
    vec = []
    for _ in range(VEC_BUCKETS):
        vec.append(0.0)
    norm_s = _normalize(s)
    bytes = norm_s.encode('utf-8')
    n = len(norm_s)
    if n < 2:
        return vec
    for i in range(n - 1):

        h = (int(bytes[i]) * 31 + int(bytes[i + 1])) & (VEC_BUCKETS - 1)
        vec[h] = vec[h] + 1.0

    mag = 0.0
    for i in range(VEC_BUCKETS):
        mag += vec[i] * vec[i]
    if mag > 0.0:
        mag = math.sqrt(mag)
        for i in range(VEC_BUCKETS):
            vec[i] = vec[i] / mag
    return vec



def _cosine(a, b):
    dot = 0.0
    for i in range(VEC_BUCKETS):
        dot += a[i] * b[i]
    if dot < 0.0:
        return 0.0
    if dot > 1.0:
        return 1.0
    return dot





def _token_jaccard(a_toks, b_toks):
    na = len(a_toks)
    nb = len(b_toks)
    if na == 0 and nb == 0:
        return 1.0
    if na == 0 or nb == 0:
        return 0.0
    shared = 0
    for i in range(na):
        for j in range(nb):
            if a_toks[i] == b_toks[j]:
                shared += 1
                break
    union = na + nb - shared
    if union == 0:
        return 0.0
    return float(shared) / float(union)





def _role_boost(role, hint_toks):
    n = len(hint_toks)

    want_unit = False
    want_derived = False
    want_base = False
    want_ratio = False

    for i in range(n):
        t = hint_toks[i]
        if t == "unit" or t == "per" or t == "each" or t == "price":
            want_unit = True
        if t == "ext" or t == "extended" or t == "total" or t == "amount":
            want_derived = True
        if t == "base" or t == "standard" or t == "list" or t == "gross":
            want_base = True
        if t == "ratio" or t == "rate" or t == "pct" or t == "margin" or t == "fill":
            want_ratio = True

    BOOST = 0.12

    if role == "unit_measure" and want_unit:
        return BOOST
    if role == "derived_measure" and want_derived:
        return BOOST
    if role == "base_measure" and want_base:
        return BOOST
    if role == "ratio" and want_ratio:
        return BOOST


    if want_unit and (role == "derived_measure" or role == "base_measure"):
        return -0.08
    if want_derived and (role == "unit_measure"):
        return -0.08

    return 0.0





def _prior_boost(source_type, col_norm):
    col = col_norm  # already lower + space-separated from _normalize
    src = source_type  # raw, may be uppercase


    src_bytes = src.encode('utf-8')
    src_len = len(src)
    s_lower = str("")
    for i in range(src_len):
        c = src_bytes[i]
        if c >= 65 and c <= 90:
            s_lower += chr(int(c + 32))
        else:
            s_lower += chr(int(c))


    has_unit = col.find("unit") >= 0
    has_ext = col.find("ext") >= 0
    has_price = col.find("price") >= 0
    has_cost = col.find("cost") >= 0
    has_amount = col.find("amount") >= 0 or col.find("amt") >= 0
    has_total = col.find("total") >= 0

    is_pos = s_lower.find("pos") >= 0 or s_lower.find("point") >= 0 or s_lower.find("sale") >= 0
    is_backlog = s_lower.find("backlog") >= 0 or s_lower.find("order") >= 0
    is_invoice = s_lower.find("invoice") >= 0 or s_lower.find("ap") >= 0 or s_lower.find("ar") >= 0

    if is_pos:
        if has_unit and (has_cost or has_price):
            return 0.10
        if has_ext and (has_cost or has_price):
            return 0.05
    if is_backlog:
        if has_ext and (has_price or has_cost):
            return 0.10
        if has_unit and has_price:
            return 0.05
    if is_invoice:
        if has_amount or has_total:
            return 0.10

    return 0.0





def _insertion_sort(results):
    n = len(results)
    sorted = []
    for i in range(n):
        sorted.append(results[i].copy())
    for i in range(1, n):
        j = i - 1
        while j >= 0 and sorted[j].score < sorted[j + 1].score:
            tmp = sorted[j].copy()
            sorted[j]     = sorted[j + 1].copy()
            sorted[j + 1] = tmp.copy()
            j -= 1
    return sorted





def _fmt_float(v):
    rounded = float(int(v * 10000.0 + 0.5)) / 10000.0
    return str(rounded)



def _build_output(sorted, top_k):
    n = len(sorted)
    k = top_k if top_k > 0 and top_k < n else n
    gap = 0.0
    ambig = False
    if n >= 2:
        gap = sorted[0].score - sorted[1].score
        ambig = gap < AMBIG_GAP

    out = str('{"ranked":[')
    for i in range(k):
        if i > 0:
            out += ","
        out += '{"source":"' + sorted[i].source + '",'
        out += '"column":"'  + sorted[i].column + '",'
        out += '"score":'    + _fmt_float(sorted[i].score)       + ','
        out += '"name_sim":' + _fmt_float(sorted[i].name_sim)    + ','
        out += '"token_sim":' + _fmt_float(sorted[i].token_sim)  + ','
        out += '"type_boost":' + _fmt_float(sorted[i].type_boost) + ','
        out += '"prior_boost":' + _fmt_float(sorted[i].prior_boost) + ','
        out += '"confidence_gap":' + _fmt_float(gap if i == 0 else 0.0) + '}'
    out += '],'
    out += '"ambiguous":' + ("true" if ambig else "false") + ','
    out += '"gap":' + _fmt_float(gap) + '}'
    return out





def run_column_rank(raw):


    hint_arr = json_get_array(raw, "hint_words")
    n_hints = json_array_len(hint_arr)
    if n_hints == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0,"error":"no hint_words"}'


    hint_joined = str("")
    hint_toks = []
    for i in range(n_hints):
        hw = to_lower(json_array_get(hint_arr, i))

        hw_bytes = hw.encode('utf-8')
        hw_n = len(hw)
        hs = 0
        he = hw_n
        if hw_n >= 2 and hw_bytes[0] == 34 and hw_bytes[hw_n - 1] == 34:
            hs = 1; he = hw_n - 1
        clean = _substr(hw, hs, he)
        toks = _tokens(clean)
        for j in range(len(toks)):
            hint_toks.append(toks[j])
        if i > 0:
            hint_joined += " "
        hint_joined += clean

    if len(hint_toks) == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0,"error":"empty hint"}'


    hint_vec = _bigram_vec(hint_joined)


    ctx_json = json_get_object(raw, "context")
    source_type = json_get_string(ctx_json, "source_type")


    cands_arr = json_get_array(raw, "candidates")
    n_cands = json_array_len(cands_arr)
    if n_cands == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0,"error":"no candidates"}'


    n = n_cands if n_cands <= MAX_CANDS else MAX_CANDS

    top_k = json_get_int(raw, "top_k", 5)


    results = []

    for ci in range(n):
        cand_json = json_array_get(cands_arr, ci)
        col_raw = json_get_string(cand_json, "column")
        source = json_get_string(cand_json, "source")
        role = json_get_string(cand_json, "role")
        fill_rate = json_get_float(cand_json, "fill_rate", 1.0)


        if fill_rate < 0.02:
            continue


        col_vec = _bigram_vec(col_raw)
        name_sim = _cosine(hint_vec, col_vec)

        col_toks = _tokens(col_raw)
        token_sim = _token_jaccard(hint_toks, col_toks)

        tb = _role_boost(role, hint_toks)
        pb = _prior_boost(source_type, _normalize(col_raw))


        base = 0.55 * name_sim + 0.25 * token_sim
        score = base + tb + pb
        if score > 1.0:
            score = 1.0
        if score < 0.0:
            score = 0.0

        results.append(RankResult(
            source = source,
            column = col_raw,
            score = score,
            name_sim = name_sim,
            token_sim = token_sim,
            type_boost = tb,
            prior_boost = pb,
        ))

    if len(results) == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0}'

    sorted = _insertion_sort(results)
    return _build_output(sorted, top_k)
