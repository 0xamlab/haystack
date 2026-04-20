"""Python equivalent of mojo/engine/music_theory.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass

LN2 = 0.6931471805599453

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

def _log2(x):
    return math.log(x) / LN2



def _pow2(x):


    val = x * LN2
    result = 1.0
    term = 1.0
    for i in range(1, 30):
        term *= val / float(i)
        result += term
    return result






def frequency_from_midi(midi_note):
    exponent = float(midi_note - 69) / 12.0
    return 440.0 * _pow2(exponent)






def midi_from_frequency(freq):
    if freq <= 0.0:
        return 0
    val = 69.0 + 12.0 * math.math.log2(freq / 440.0)

    if val >= 0.0:
        return int(val + 0.5)
    else:
        return int(val - 0.5)






def cents_between(freq1, freq2):
    if freq1 <= 0.0 or freq2 <= 0.0:
        return 0.0
    return 1200.0 * math.math.log2(freq2 / freq1)






def semitones_between(midi1, midi2):
    diff = midi1 - midi2
    if diff < 0:
        return -diff
    return diff






def note_in_scale(note_class, scale_root, scale_pattern_idx):
    offset = (note_class - scale_root + 12) % 12
    if scale_pattern_idx == 0:

        return (offset == 0 or offset == 2 or offset == 4 or offset == 5
                or offset == 7 or offset == 9 or offset == 11)
    else:

        return (offset == 0 or offset == 2 or offset == 3 or offset == 5
                or offset == 7 or offset == 8 or offset == 10)






def interval_ratio_just(semitones):

    if semitones == 0:
        return 1.0          # unison
    elif semitones == 1:
        return 16.0 / 15.0  # minor second
    elif semitones == 2:
        return 9.0 / 8.0    # major second
    elif semitones == 3:
        return 6.0 / 5.0    # minor third
    elif semitones == 4:
        return 5.0 / 4.0    # major third
    elif semitones == 5:
        return 4.0 / 3.0    # perfect fourth
    elif semitones == 6:
        return 45.0 / 32.0  # tritone (augmented fourth)
    elif semitones == 7:
        return 3.0 / 2.0    # perfect fifth
    elif semitones == 8:
        return 8.0 / 5.0    # minor sixth
    elif semitones == 9:
        return 5.0 / 3.0    # major sixth
    elif semitones == 10:
        return 9.0 / 5.0    # minor seventh
    elif semitones == 11:
        return 15.0 / 8.0   # major seventh
    elif semitones == 12:
        return 2.0           # octave

    return _pow2(float(semitones) / 12.0)






def beat_frequency(freq1, freq2):
    return math.fabs(freq1 - freq2)






def tempo_to_beat_duration(bpm):
    if bpm <= 0.0:
        return 0.0
    return 60.0 / bpm






def measures_duration(bpm, beats_per_measure, num_measures):
    if bpm <= 0.0:
        return 0.0
    beat_dur = 60.0 / bpm
    return beat_dur * float(beats_per_measure) * float(num_measures)






def transpose_midi(midi_note, semitones):
    return midi_note + semitones






def octave_from_midi(midi_note):
    return (midi_note // 12) - 1






def is_enharmonic(midi1, midi2):
    return (midi1 % 12) == (midi2 % 12)
