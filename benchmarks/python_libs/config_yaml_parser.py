"""Python equivalent of mojo/engine/config.yaml_parser.mojo (auto-generated)."""
import math
import random as _rng

_YAML_SCALAR = 0
_YAML_MAP = 1
_YAML_LIST = 2

class YamlNode:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('kind')
        self.kind = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('scalar')
        self.scalar = _v1 if _v1 is not None else ""
        self.map_keys = []
        self.map_vals = []
        self.list_vals = []
    def __repr__(self):
        return f'YamlNode({vars(self)})'

class _YamlPool:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('nodes')
        self.nodes = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'_YamlPool({vars(self)})'
    def add_scalar(self, value):
        idx = len(self.nodes)
        self.nodes.append(YamlNode(_YAML_SCALAR, value))
        return idx
    
    def add_map(self):
        idx = len(self.nodes)
        self.nodes.append(YamlNode(_YAML_MAP, str("")))
        return idx
    
    def add_list(self):
        idx = len(self.nodes)
        self.nodes.append(YamlNode(_YAML_LIST, str("")))
        return idx
    
    

class _ParseState:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('lines')
        self.lines = _v0 if _v0 is not None else []
        self.pos = 0
        self.pool = _YamlPool()
    def __repr__(self):
        return f'_ParseState({vars(self)})'

class YamlDoc:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('pool')
        self.pool = _v0 if _v0 is not None else _YamlPool()
        _v1 = args[1] if 1 < len(args) else kwargs.get('root')
        self.root = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'YamlDoc({vars(self)})'

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

def _count_indent(line):
    bs = line.encode('utf-8')
    n = len(line)
    count = 0
    while count < n and int(bs[count]) == 32:  # space
        count += 1
    return count



def _strip(s):
    bs = s.encode('utf-8')
    n = len(s)
    start = 0
    while start < n:
        c = int(bs[start])
        if c != 32 and c != 9 and c != 10 and c != 13:
            break
        start += 1
    end = n
    while end > start:
        c = int(bs[end - 1])
        if c != 32 and c != 9 and c != 10 and c != 13:
            break
        end -= 1
    result = str("")
    for i in range(start, end):
        result += chr(int(bs[i]))
    return result



def _starts_with(s, prefix):
    sbs = s.encode('utf-8')
    pbs = prefix.encode('utf-8')
    if len(prefix) > len(s):
        return False
    for i in range(len(prefix)):
        if sbs[i] != pbs[i]:
            return False
    return True



def _split_lines(content):
    lines = []
    bs = content.encode('utf-8')
    n = len(content)
    start = 0
    for i in range(n):
        if int(bs[i]) == 10:
            line = str("")
            for j in range(start, i):
                line += chr(int(bs[j]))
            lines.append(line)
            start = i + 1

    if start <= n:
        line = str("")
        for j in range(start, n):
            line += chr(int(bs[j]))
        lines.append(line)
    return lines



def _find_colon(line):
    bs = line.encode('utf-8')
    n = len(line)
    for i in range(n):
        if int(bs[i]) == 58:
            if i + 1 >= n or int(bs[i + 1]) == 32:
                return i
    return -1



def _substring(s, start, end):
    bs = s.encode('utf-8')
    result = str("")
    e = min(end, len(s))
    for i in range(start, e):
        result += chr(int(bs[i]))
    return result



def _unquote(s):
    n = len(s)
    if n < 2:
        return s
    bs = s.encode('utf-8')
    first = int(bs[0])
    last = int(bs[n - 1])
    if (first == 34 and last == 34) or (first == 39 and last == 39):
        return _substring(s, 1, n - 1)
    return s






def _parse_block(state, base_indent):
    n_lines = len(state.lines)

    if state.pos >= n_lines:
        return state.pool.add_scalar(str(""))

    first_line = state.lines[state.pos]
    first_stripped = _strip(first_line)


    if _starts_with(first_stripped, "- "):
        list_idx = state.pool.add_list()
        while state.pos < n_lines:
            line = state.lines[state.pos]
            li = _count_indent(line)
            ls = _strip(line)
            if len(ls) == 0:
                state.pos += 1
                continue
            if li < base_indent:
                break
            if li != base_indent or not _starts_with(ls, "- "):
                break
            item_val = _strip(_substring(ls, 2, len(ls)))
            item_idx = state.pool.add_scalar(item_val)
            state.pool.nodes[list_idx].list_vals.append(item_idx)
            state.pos += 1
        return list_idx


    map_idx = state.pool.add_map()
    while state.pos < n_lines:
        line = state.lines[state.pos]
        li = _count_indent(line)
        ls = _strip(line)

        if len(ls) == 0:
            state.pos += 1
            continue

        if li < base_indent:
            break

        if li > base_indent:
            state.pos += 1
            continue

        colon_pos = _find_colon(ls)
        if colon_pos < 0:
            state.pos += 1
            continue

        key = _strip(_substring(ls, 0, colon_pos))
        val_part = str("")
        if colon_pos + 1 < len(ls):
            val_part = _strip(_substring(ls, colon_pos + 1, len(ls)))

        state.pos += 1

        if len(val_part) > 0:
            val_idx = state.pool.add_scalar(_unquote(val_part))
            state.pool.nodes[map_idx].map_keys.append(key)
            state.pool.nodes[map_idx].map_vals.append(val_idx)
        else:
            if state.pos < n_lines:
                next_line = state.lines[state.pos]
                next_stripped = _strip(next_line)
                if len(next_stripped) > 0:
                    next_indent = _count_indent(next_line)
                    if next_indent > base_indent:
                        child_idx = _parse_block(state, next_indent)
                        state.pool.nodes[map_idx].map_keys.append(key)
                        state.pool.nodes[map_idx].map_vals.append(child_idx)
                    else:
                        empty_idx = state.pool.add_scalar(str(""))
                        state.pool.nodes[map_idx].map_keys.append(key)
                        state.pool.nodes[map_idx].map_vals.append(empty_idx)
                else:
                    empty_idx = state.pool.add_scalar(str(""))
                    state.pool.nodes[map_idx].map_keys.append(key)
                    state.pool.nodes[map_idx].map_vals.append(empty_idx)
            else:
                empty_idx = state.pool.add_scalar(str(""))
                state.pool.nodes[map_idx].map_keys.append(key)
                state.pool.nodes[map_idx].map_vals.append(empty_idx)

    return map_idx






def _split_path(path):
    parts = []
    bs = path.encode('utf-8')
    n = len(path)
    start = 0
    for i in range(n):
        if int(bs[i]) == 46:
            seg = str("")
            for j in range(start, i):
                seg += chr(int(bs[j]))
            parts.append(seg)
            start = i + 1
    last = str("")
    for j in range(start, n):
        last += chr(int(bs[j]))
    parts.append(last)
    return parts



def _resolve_path(doc, path):
    parts = _split_path(path)
    current = doc.root
    for pi in range(len(parts)):
        seg = parts[pi]
        if doc.pool.nodes[current].kind != _YAML_MAP:
            return -1
        found = False
        for ki in range(len(doc.pool.nodes[current].map_keys)):
            if doc.pool.nodes[current].map_keys[ki] == seg:
                current = doc.pool.nodes[current].map_vals[ki]
                found = True
                break
        if not found:
            return -1
    return current



def yaml_parse(content):
    lines = _split_lines(content)
    state = _ParseState(lines)
    root = _parse_block(state, 0)
    return YamlDoc(state.pool, root)





