"""Python equivalent of mojo/engine/compression.huffman.mojo (auto-generated)."""
import math
import random as _rng

class HuffmanNode:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('symbol')
        self.symbol = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('freq')
        self.freq = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('left')
        self.left = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('right')
        self.right = _v3 if _v3 is not None else 0
    def __repr__(self):
        return f'HuffmanNode({vars(self)})'

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

def _build_code_table(tree):
    result = []
    n = len(tree)
    if n == 0:
        return result


    stack_idx = []
    stack_code_len = []

    code_store = []

    stack_idx.append(n - 1)
    empty_code = []
    code_store.append(empty_code)
    stack_code_len.append(0)  # index into code_store

    while len(stack_idx) > 0:
        pos = len(stack_idx) - 1
        idx = stack_idx[pos]
        code_idx = stack_code_len[pos]
        _ = stack_idx.pop()
        _ = stack_code_len.pop()

        if idx < 0 or idx >= n:
            continue

        current_code = code_store[code_idx].copy()

        if tree[idx].symbol >= 0:

            entry = []
            entry.append(tree[idx].symbol)
            if len(current_code) == 0:
                entry.append(0)  # single symbol gets code "0"
            else:
                for b in range(len(current_code)):
                    entry.append(current_code[b])
            result.append(entry)
        else:

            if tree[idx].left >= 0:
                left_code = []
                for b in range(len(current_code)):
                    left_code.append(current_code[b])
                left_code.append(0)
                stack_idx.append(tree[idx].left)
                stack_code_len.append(len(code_store))
                code_store.append(left_code)

            if tree[idx].right >= 0:
                right_code = []
                for b in range(len(current_code)):
                    right_code.append(current_code[b])
                right_code.append(1)
                stack_idx.append(tree[idx].right)
                stack_code_len.append(len(code_store))
                code_store.append(right_code)

    return result






def frequency_count(data):

    symbols = []
    counts = []
    n = len(data)

    for i in range(n):
        val = data[i]
        found = False
        for j in range(len(symbols)):
            if symbols[j] == val:
                counts[j] = counts[j] + 1
                found = True
                break
        if not found:
            symbols.append(val)
            counts.append(1)


    m = len(symbols)
    for i in range(1, m):
        key_sym = symbols[i]
        key_cnt = counts[i]
        j = i - 1
        while j >= 0 and counts[j] > key_cnt:
            symbols[j + 1] = symbols[j]
            counts[j + 1] = counts[j]
            j -= 1
        symbols[j + 1] = key_sym
        counts[j + 1] = key_cnt

    result = []
    for i in range(m):
        pair = []
        pair.append(symbols[i])
        pair.append(counts[i])
        result.append(pair)
    return result






def build_huffman_tree(freqs):
    nodes = []
    num_leaves = len(freqs)
    if num_leaves == 0:
        return nodes

    if num_leaves == 1:

        nodes.append(HuffmanNode(freqs[0][0], freqs[0][1], -1, -1))
        nodes.append(HuffmanNode(-1, freqs[0][1], 0, -1))
        return nodes


    for i in range(num_leaves):
        nodes.append(HuffmanNode(freqs[i][0], freqs[i][1], -1, -1))


    available = []
    for i in range(num_leaves):
        available.append(True)


    for _ in range(num_leaves - 1):

        min1_idx = -1
        min2_idx = -1
        min1_freq = 2147483647  # large int
        min2_freq = 2147483647

        total = len(nodes)
        for i in range(total):
            if i < len(available) and available[i]:
                if nodes[i].freq < min1_freq:
                    min2_freq = min1_freq
                    min2_idx = min1_idx
                    min1_freq = nodes[i].freq
                    min1_idx = i
                elif nodes[i].freq < min2_freq:
                    min2_freq = nodes[i].freq
                    min2_idx = i

        if min1_idx == -1 or min2_idx == -1:
            break


        available[min1_idx] = False
        available[min2_idx] = False


        new_freq = nodes[min1_idx].freq + nodes[min2_idx].freq
        nodes.append(HuffmanNode(-1, new_freq, min1_idx, min2_idx))
        available.append(True)

    return nodes






def huffman_encode(data):
    freqs = frequency_count(data)
    tree = build_huffman_tree(freqs)
    codes = _build_code_table(tree)

    result = []
    n = len(data)
    for i in range(n):
        sym = data[i]

        for c in range(len(codes)):
            if codes[c][0] == sym:
                for b in range(1, len(codes[c])):
                    result.append(codes[c][b])
                break
    return result






def compression_ratio_huffman(original_size, encoded_bits):
    if encoded_bits == 0:
        return 0.0
    return float(original_size * 8) / float(encoded_bits)






def avg_code_length(freqs, codes):
    total_freq = 0
    for i in range(len(freqs)):
        total_freq += freqs[i][1]
    if total_freq == 0:
        return 0.0

    weighted_sum = 0.0
    for i in range(len(codes)):
        sym = codes[i][0]
        code_len = codes[i][1]

        for j in range(len(freqs)):
            if freqs[j][0] == sym:
                weighted_sum += float(code_len) * float(freqs[j][1])
                break
    return weighted_sum / float(total_freq)
