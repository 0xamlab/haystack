"""Python equivalent of mojo/engine/vision_gate.mojo (auto-generated)."""
import math
import random as _rng

_BLUR_MIN = 100.0          # Laplacian variance below this ⇒ blurry
_BRIGHT_LOW = 20.0         # mean brightness below this ⇒ under-exposed
_BRIGHT_HIGH = 235.0       # mean brightness above this ⇒ over-exposed
_ENTROPY_MIN = 0.5         # 256-bin entropy below this ⇒ near-blank
_TEXT_EDGE_MIN = 0.10      # edge density above this with text intent ⇒ OCR
_TEXT_ENTROPY_MIN = 3.0    # entropy floor for "text-like"
_CROP_EDGE_MIN = 0.15      # edge density above this ⇒ a region dominates

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

def should_use_cache(is_duplicate_flag):
    return is_duplicate_flag



def needs_clearer_image(blur_score, brightness):
    return (
        blur_score < _BLUR_MIN
        or brightness < _BRIGHT_LOW
        or brightness > _BRIGHT_HIGH
    )



def is_text_heavy(edge_density, entropy):
    return edge_density > _TEXT_EDGE_MIN and entropy > _TEXT_ENTROPY_MIN



def quality_gate_passed(blur_score, brightness, entropy):
    return (
        not needs_clearer_image(blur_score, brightness)
        and entropy >= _ENTROPY_MIN
    )






def route_image_request(blur_score, brightness, entropy, edge_density, is_duplicate_flag, intent_code):

    if is_duplicate_flag:
        return 0

    if intent_code == 2:
        return 1

    if needs_clearer_image(blur_score, brightness):
        return 2

    if entropy < _ENTROPY_MIN:
        return 1

    if intent_code == 1:
        if edge_density > _TEXT_EDGE_MIN:
            return 3
        return 4


    if edge_density > _CROP_EDGE_MIN:
        return 5
    return 4
