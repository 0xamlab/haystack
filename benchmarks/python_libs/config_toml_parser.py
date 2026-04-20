"""Python equivalent of mojo/engine/config.toml_parser.mojo (auto-generated)."""
import math
import random as _rng

_TOML_SCALAR = 0
_TOML_MAP = 1
_TOML_LIST = 2

class TomlNode:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('kind')
        self.kind = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('scalar')
        self.scalar = _v1 if _v1 is not None else ""
        self.map_keys = []
        self.map_vals = []
        self.list_vals = []
    def __repr__(self):
        return f'TomlNode({vars(self)})'

class _TomlPool:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('nodes')
        self.nodes = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'_TomlPool({vars(self)})'
    def add_scalar(self, value):
        idx = len(self.nodes)
        self.nodes.append(TomlNode(_TOML_SCALAR, value))
        return idx
    
    def add_map(self):
        idx = len(self.nodes)
        self.nodes.append(TomlNode(_TOML_MAP, str("")))
        return idx
    
    def add_list(self):
        idx = len(self.nodes)
        self.nodes.append(TomlNode(_TOML_LIST, str("")))
        return idx
    
    def map_set(self, map_idx, key, val_idx):
        for i in range(len(self.nodes[map_idx].map_keys)):
            if self.nodes[map_idx].map_keys[i] == key:
                self.nodes[map_idx].map_vals[i] = val_idx
                return
        self.nodes[map_idx].map_keys.append(key)
        self.nodes[map_idx].map_vals.append(val_idx)
    
    def map_get(self, map_idx, key):
        for i in range(len(self.nodes[map_idx].map_keys)):
            if self.nodes[map_idx].map_keys[i] == key:
                return self.nodes[map_idx].map_vals[i]
        return -1
    
    def ensure_sub_map(self, parent_idx, key):
        existing = self.map_get(parent_idx, key)
        if existing >= 0 and self.nodes[existing].kind == _TOML_MAP:
            return existing
        sub = self.add_map()
        self.map_set(parent_idx, key, sub)
        return sub
    
    

class TomlDoc:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('pool')
        self.pool = _v0 if _v0 is not None else _TomlPool()
        _v1 = args[1] if 1 < len(args) else kwargs.get('root')
        self.root = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'TomlDoc({vars(self)})'

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

def _toml_strip(s):
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



def _toml_substring(s, start, end):
    bs = s.encode('utf-8')
    result = str("")
    e = min(end, len(s))
    for i in range(start, e):
        result += chr(int(bs[i]))
    return result



def _toml_split_lines(content):
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



def _toml_starts_with(s, prefix):
    if len(prefix) > len(s):
        return False
    sbs = s.encode('utf-8')
    pbs = prefix.encode('utf-8')
    for i in range(len(prefix)):
        if sbs[i] != pbs[i]:
            return False
    return True



def _toml_ends_with(s, suffix):
    if len(suffix) > len(s):
        return False
    sbs = s.encode('utf-8')
    sufs = suffix.encode('utf-8')
    offset = len(s) - len(suffix)
    for i in range(len(suffix)):
        if sbs[offset + i] != sufs[i]:
            return False
    return True



def _toml_find_char(s, c):
    bs = s.encode('utf-8')
    for i in range(len(s)):
        if int(bs[i]) == c:
            return i
    return -1



def _toml_split_dot(path):
    parts = []
    bs = path.encode('utf-8')
    n = len(path)
    start = 0
    for i in range(n):
        if int(bs[i]) == 46:
            parts.append(_toml_substring(path, start, i))
            start = i + 1
    parts.append(_toml_substring(path, start, n))
    return parts



def _toml_unquote(s):
    n = len(s)
    if n < 2:
        return s
    bs = s.encode('utf-8')
    first = int(bs[0])
    last = int(bs[n - 1])
    if (first == 34 and last == 34) or (first == 39 and last == 39):
        return _toml_substring(s, 1, n - 1)
    return s



def _toml_is_digit(c):
    return c >= 48 and c <= 57



def _toml_parse_value(pool, raw):
    val = _toml_strip(raw)
    vlen = len(val)

    if vlen == 0:
        return pool.add_scalar(str(""))

    vbs = val.encode('utf-8')
    first = int(vbs[0])


    if first == 34 or first == 39:
        return pool.add_scalar(_toml_unquote(val))


    if val == "true" or val == "True":
        return pool.add_scalar(str("true"))
    if val == "false" or val == "False":
        return pool.add_scalar(str("false"))


    if first == 91:
        return _toml_parse_array(pool, val)


    return pool.add_scalar(val)



def _toml_parse_array(pool, raw):
    list_idx = pool.add_list()

    inner = _toml_strip(_toml_substring(raw, 1, len(raw) - 1))
    if len(inner) == 0:
        return list_idx


    bs = inner.encode('utf-8')
    n = len(inner)
    start = 0
    in_string = False
    quote_char = 0
    for i in range(n):
        c = int(bs[i])
        if in_string:
            if c == quote_char:
                in_string = False
        else:
            if c == 34 or c == 39:
                in_string = True
                quote_char = c
            elif c == 44:
                element = _toml_strip(_toml_substring(inner, start, i))
                if len(element) > 0:
                    el_idx = _toml_parse_value(pool, element)
                    pool.nodes[list_idx].list_vals.append(el_idx)
                start = i + 1

    last = _toml_strip(_toml_substring(inner, start, n))
    if len(last) > 0:
        el_idx = _toml_parse_value(pool, last)
        pool.nodes[list_idx].list_vals.append(el_idx)

    return list_idx






def _toml_resolve(doc, path):
    parts = _toml_split_dot(path)
    current = doc.root
    for pi in range(len(parts)):
        seg = _toml_strip(parts[pi])
        if doc.pool.nodes[current].kind != _TOML_MAP:
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



def toml_parse(content):
    pool = _TomlPool()
    root = pool.add_map()
    lines = _toml_split_lines(content)
    current_section = root  # current section node index

    for li in range(len(lines)):
        raw_line = lines[li]
        line = _toml_strip(raw_line)


        if len(line) == 0:
            continue
        lbs = line.encode('utf-8')
        if int(lbs[0]) == 35:
            continue


        effective = line
        in_str = False
        str_char = 0
        ebs = effective.encode('utf-8')
        for ci in range(len(effective)):
            cc = int(ebs[ci])
            if in_str:
                if cc == str_char:
                    in_str = False
            else:
                if cc == 34 or cc == 39:
                    in_str = True
                    str_char = cc
                elif cc == 35:
                    effective = _toml_strip(_toml_substring(effective, 0, ci))
                    break

        if len(effective) == 0:
            continue

        ebs2 = effective.encode('utf-8')


        if int(ebs2[0]) == 91 and int(ebs2[len(effective) - 1]) == 93:
            header = _toml_strip(_toml_substring(effective, 1, len(effective) - 1))
            parts = _toml_split_dot(header)

            current_section = root
            for pi in range(len(parts)):
                part = _toml_strip(parts[pi])
                current_section = pool.ensure_sub_map(current_section, part)
            continue


        eq_pos = -1
        in_s2 = False
        sc2 = 0
        for ki in range(len(effective)):
            kc = int(ebs2[ki])
            if in_s2:
                if kc == sc2:
                    in_s2 = False
            else:
                if kc == 34 or kc == 39:
                    in_s2 = True
                    sc2 = kc
                elif kc == 61:
                    eq_pos = ki
                    break

        if eq_pos > 0:
            key = _toml_strip(_toml_substring(effective, 0, eq_pos))
            val_str = _toml_strip(_toml_substring(effective, eq_pos + 1, len(effective)))
            val_idx = _toml_parse_value(pool, val_str)
            pool.map_set(current_section, key, val_idx)

    return TomlDoc(pool, root)





