"""Python equivalent of mojo/engine/column_rank.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.python import Python
except Exception:
    pass
try:
    from std.python import PythonObject
except Exception:
    pass
try:
    from field_mapper import to_lower
except Exception:
    pass
try:
    from python_bridge import fast_f64
except Exception:
    pass
try:
    from python_bridge import fast_int
except Exception:
    pass
try:
    from python_bridge import py_str
except Exception:
    pass
try:
    from string_distance import dice_coefficient
except Exception:
    pass
try:
    from string_distance import edit_similarity
except Exception:
    pass

class ResidentColumnRankEntry:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('id')
        self.id = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('source')
        self.source = _v1 if _v1 is not None else ""
        _v2 = args[2] if 2 < len(args) else kwargs.get('column')
        self.column = _v2 if _v2 is not None else ""
        _v3 = args[3] if 3 < len(args) else kwargs.get('source_id')
        self.source_id = _v3 if _v3 is not None else 0
        _v4 = args[4] if 4 < len(args) else kwargs.get('role_id')
        self.role_id = _v4 if _v4 is not None else 0
        self.normalized = ""
    def __repr__(self):
        return f'ResidentColumnRankEntry({vars(self)})'
    def copy(self):
        return ResidentColumnRankEntry(self.id, self.source, self.column, self.source_id, self.role_id)
    
    

class RankedEntry:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('id')
        self.id = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('source')
        self.source = _v1 if _v1 is not None else ""
        _v2 = args[2] if 2 < len(args) else kwargs.get('column')
        self.column = _v2 if _v2 is not None else ""
        _v3 = args[3] if 3 < len(args) else kwargs.get('score')
        self.score = _v3 if _v3 is not None else 0.0
        _v4 = args[4] if 4 < len(args) else kwargs.get('name_sim')
        self.name_sim = _v4 if _v4 is not None else 0.0
        _v5 = args[5] if 5 < len(args) else kwargs.get('type_boost')
        self.type_boost = _v5 if _v5 is not None else 0.0
        _v6 = args[6] if 6 < len(args) else kwargs.get('confidence_gap')
        self.confidence_gap = _v6 if _v6 is not None else 0.0
    def __repr__(self):
        return f'RankedEntry({vars(self)})'
    def copy(self):
        return RankedEntry(
            self.id,
            self.source,
            self.column,
            self.score,
            self.name_sim,
            self.type_boost,
            self.confidence_gap,
        )
    
    

class ResidentColumnRankState:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('entries')
        self.entries = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'ResidentColumnRankState({vars(self)})'
    def copy(self):
        out = ResidentColumnRankState()
        out.entries = self.entries.copy()
        return out
    
    def init_from_json(self, raw):
        json_m = Python.import_module("json")
        builtins = Python.import_module("builtins")
        payload = json_m.loads(raw)
        entries_py = payload.get("entries", Python.evaluate("[]"))
        self.entries = []
        for i in range(fast_int(builtins.len(entries_py))):
            entry = entries_py[i]
            self.entries.append(
                ResidentColumnRankEntry(
                    fast_int(entry.get("id", i)),
                    py_str(entry.get("source", "")),
                    py_str(entry.get("column", "")),
                    fast_int(entry.get("source_id", 0)),
                    fast_int(entry.get("role_id", 0)),
                )
            )
        return '{"status":"ok","count":' + str(len(self.entries)) + "}"
    
    def _query_ranked(self, query):
        builtins = Python.import_module("builtins")
        candidate_ids = query.get("candidate_ids", Python.evaluate("[]"))
        top_k = fast_int(query.get("top_k", 5))
        use_all = fast_int(builtins.len(candidate_ids)) == 0
        hint = py_str(query.get("hint", ""))
        query_source_id = fast_int(query.get("source_id", 0))
        query_role_id = fast_int(query.get("role_id", 0))
        ranked = []
        for i in range(len(self.entries)):
            if not use_all:
                include_entry = False
                for j in range(fast_int(builtins.len(candidate_ids))):
                    if fast_int(candidate_ids[j]) == self.entries[i].id:
                        include_entry = True
                        break
                if not include_entry:
                    continue
            ranked.append(_candidate_score(hint, query_source_id, query_role_id, self.entries[i]))
        _sort_ranked(ranked)
        if top_k < len(ranked):
            trimmed = []
            for i in range(top_k):
                trimmed.append(ranked[i].copy())
            return trimmed
        return ranked
    
    def run_query(self, raw):
        json_m = Python.import_module("json")
        payload = json_m.loads(raw)
        ranked = self._query_ranked(payload)
        return '{"ranked":' + _ranked_json(ranked, len(ranked)) + ',"ambiguous":false,"gap":' + str(ranked[0].confidence_gap if len(ranked) > 0 else 0.0) + "}"
    
    def run_batch(self, raw):
        json_m = Python.import_module("json")
        builtins = Python.import_module("builtins")
        payload = json_m.loads(raw)
        requests = payload.get("requests", Python.evaluate("[]"))
        results_json = str("[")
        for i in range(fast_int(builtins.len(requests))):
            ranked = self._query_ranked(requests[i])
            if i > 0:
                results_json += ","
            results_json += '{"ranked":' + _ranked_json(ranked, len(ranked)) + ',"ambiguous":false,"gap":' + str(ranked[0].confidence_gap if len(ranked) > 0 else 0.0) + "}"
        results_json += "]"
        return '{"results":' + results_json + "}"
    
    

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

def _normalize(text):
    lower = to_lower(text)
    out = str("")
    pending_space = False
    bytes = lower.encode('utf-8')
    for i in range(len(lower)):
        c = bytes[i]
        is_alpha = (c >= int(97) and c <= int(122))
        is_digit = c >= int(48) and c <= int(57)
        if is_alpha or is_digit:
            if pending_space and len(out) > 0:
                out += " "
            out += chr(int(c))
            pending_space = False
        else:
            pending_space = True
    return out



def _token_overlap_boost(hint, candidate):
    hint_norm = _normalize(hint)
    if len(hint_norm) == 0:
        return 0.0
    bytes = hint_norm.encode('utf-8')
    token = str("")
    matched = 0
    total = 0
    for i in range(len(hint_norm) + 1):
        if i == len(hint_norm) or bytes[i] == int(32):
            if len(token) > 0:
                total += 1
                if candidate.find(token) >= 0:
                    matched += 1
                token = ""
            continue
        token += chr(int(bytes[i]))
    if total == 0:
        return 0.0
    return 0.08 * float(matched) / float(total)



def _role_boost(query_role_id, candidate_role_id):
    if query_role_id <= 0 or candidate_role_id <= 0:
        return 0.0
    if query_role_id == candidate_role_id:
        return 0.12
    return -0.04



def _source_boost(query_source_id, candidate_source_id):
    if query_source_id <= 0 or candidate_source_id <= 0:
        return 0.0
    if query_source_id == candidate_source_id:
        return 0.08
    return -0.02



def _candidate_score(hint, query_source_id, query_role_id, entry):
    hint_norm = _normalize(hint)
    name_sim = edit_similarity(hint_norm, entry.normalized)
    dice = dice_coefficient(hint_norm, entry.normalized)
    if dice > name_sim:
        name_sim = dice
    type_boost = _role_boost(query_role_id, entry.role_id) + _source_boost(query_source_id, entry.source_id)
    score = 0.78 * name_sim + type_boost + _token_overlap_boost(hint, entry.normalized)
    if score < 0.0:
        score = 0.0
    elif score > 1.0:
        score = 1.0
    return RankedEntry(entry.id, entry.source, entry.column, score, name_sim, type_boost, 0.0)



def _sort_ranked(ranked):
    for i in range(1, len(ranked)):
        key = ranked[i].copy()
        j = i - 1
        while j >= 0 and ranked[j].score < key.score:
            ranked[j + 1] = ranked[j].copy()
            j -= 1
        ranked[j + 1] = key.copy()
    if len(ranked) > 0:
        top_gap = ranked[0].score - (ranked[1].score if len(ranked) > 1 else 0.0)
        ranked[0].confidence_gap = top_gap



def _ranked_json(ranked, top_k):
    json_m = Python.import_module("json")
    rows = Python.evaluate("[]")
    limit = top_k
    if limit > len(ranked):
        limit = len(ranked)
    for i in range(limit):
        row = Python.evaluate("{}")
        row["id"] = ranked[i].id
        row["source"] = ranked[i].source
        row["column"] = ranked[i].column
        row["score"] = ranked[i].score
        row["name_sim"] = ranked[i].name_sim
        row["type_boost"] = ranked[i].type_boost
        row["confidence_gap"] = ranked[i].confidence_gap
        rows.append(row)
    return py_str(json_m.dumps(rows))



def run_column_rank(raw):
    json_m = Python.import_module("json")
    builtins = Python.import_module("builtins")
    payload = json_m.loads(raw)
    hint = py_str(payload.get("hint", ""))
    if len(hint) == 0:
        hint_words = payload.get("hint_words", Python.evaluate("[]"))
        for i in range(fast_int(builtins.len(hint_words))):
            if i > 0:
                hint += " "
            hint += py_str(hint_words[i])
    candidates = payload.get("candidates", Python.evaluate("[]"))
    top_k = fast_int(payload.get("top_k", 5))
    context = payload.get("context", Python.evaluate("{}"))
    query_source_id = 0
    query_role_id = 0
    ranked = []
    for i in range(fast_int(builtins.len(candidates))):
        candidate = candidates[i]
        entry = ResidentColumnRankEntry(
            i,
            py_str(candidate.get("source", "")),
            py_str(candidate.get("column", "")),
            query_source_id,
            query_role_id,
        )
        ranked.append(_candidate_score(hint, query_source_id, query_role_id, entry))
    _sort_ranked(ranked)
    return '{"ranked":' + _ranked_json(ranked, top_k) + ',"ambiguous":false,"gap":' + str(ranked[0].confidence_gap if len(ranked) > 0 else 0.0) + "}"
