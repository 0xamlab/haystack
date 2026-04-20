"""Python equivalent of mojo/engine/sentiment.mojo (auto-generated)."""
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

def _is_alpha_byte(c):
    return (c >= 97 and c <= 122) or (c >= 65 and c <= 90)



def _to_lower_byte(c):
    if c >= 65 and c <= 90:
        return c + 32
    return c






def _lexicon_words():
    w = []

    w.append("good")       # 0.7
    w.append("great")      # 0.9
    w.append("excellent")  # 0.95
    w.append("amazing")    # 0.9
    w.append("love")       # 0.8
    w.append("happy")      # 0.7
    w.append("wonderful")  # 0.85
    w.append("fantastic")  # 0.9
    w.append("best")       # 0.8
    w.append("perfect")    # 0.95
    w.append("beautiful")  # 0.8
    w.append("awesome")    # 0.85
    w.append("nice")       # 0.5
    w.append("fine")       # 0.3
    w.append("ok")         # 0.1
    w.append("brilliant")  # 0.9
    w.append("superb")     # 0.9
    w.append("outstanding")# 0.9
    w.append("lovely")     # 0.75
    w.append("pleasant")   # 0.6
    w.append("enjoy")      # 0.7
    w.append("delight")    # 0.8
    w.append("cheerful")   # 0.7
    w.append("positive")   # 0.6
    w.append("like")       # 0.4
    w.append("glad")       # 0.6
    w.append("joy")        # 0.8
    w.append("pleased")    # 0.6
    w.append("exciting")   # 0.75
    w.append("impressive") # 0.7

    w.append("bad")        # -0.7
    w.append("terrible")   # -0.9
    w.append("awful")      # -0.9
    w.append("horrible")   # -0.95
    w.append("hate")       # -0.8
    w.append("sad")        # -0.7
    w.append("worst")      # -0.9
    w.append("ugly")       # -0.8
    w.append("poor")       # -0.6
    w.append("boring")     # -0.5
    w.append("angry")      # -0.7
    w.append("disappointing") # -0.6
    w.append("weak")       # -0.4
    w.append("fail")       # -0.7
    w.append("wrong")      # -0.5
    w.append("not")        # -0.3
    w.append("never")      # -0.3
    w.append("horrible")   # duplicate, skip in scores
    w.append("disgusting") # -0.85
    w.append("dreadful")   # -0.8
    w.append("miserable")  # -0.8
    w.append("annoying")   # -0.6
    w.append("frustrating")# -0.6
    w.append("painful")    # -0.7
    w.append("useless")    # -0.7
    w.append("disaster")   # -0.85
    w.append("trash")      # -0.7
    w.append("broken")     # -0.5
    w.append("fear")       # -0.6
    w.append("sick")       # -0.5
    return w



def _lexicon_scores():
    s = []

    s.append(0.7)   # good
    s.append(0.9)   # great
    s.append(0.95)  # excellent
    s.append(0.9)   # amazing
    s.append(0.8)   # love
    s.append(0.7)   # happy
    s.append(0.85)  # wonderful
    s.append(0.9)   # fantastic
    s.append(0.8)   # best
    s.append(0.95)  # perfect
    s.append(0.8)   # beautiful
    s.append(0.85)  # awesome
    s.append(0.5)   # nice
    s.append(0.3)   # fine
    s.append(0.1)   # ok
    s.append(0.9)   # brilliant
    s.append(0.9)   # superb
    s.append(0.9)   # outstanding
    s.append(0.75)  # lovely
    s.append(0.6)   # pleasant
    s.append(0.7)   # enjoy
    s.append(0.8)   # delight
    s.append(0.7)   # cheerful
    s.append(0.6)   # positive
    s.append(0.4)   # like
    s.append(0.6)   # glad
    s.append(0.8)   # joy
    s.append(0.6)   # pleased
    s.append(0.75)  # exciting
    s.append(0.7)   # impressive

    s.append(-0.7)  # bad
    s.append(-0.9)  # terrible
    s.append(-0.9)  # awful
    s.append(-0.95) # horrible
    s.append(-0.8)  # hate
    s.append(-0.7)  # sad
    s.append(-0.9)  # worst
    s.append(-0.8)  # ugly
    s.append(-0.6)  # poor
    s.append(-0.5)  # boring
    s.append(-0.7)  # angry
    s.append(-0.6)  # disappointing
    s.append(-0.4)  # weak
    s.append(-0.7)  # fail
    s.append(-0.5)  # wrong
    s.append(-0.3)  # not
    s.append(-0.3)  # never
    s.append(-0.95) # horrible (dup)
    s.append(-0.85) # disgusting
    s.append(-0.8)  # dreadful
    s.append(-0.8)  # miserable
    s.append(-0.6)  # annoying
    s.append(-0.6)  # frustrating
    s.append(-0.7)  # painful
    s.append(-0.7)  # useless
    s.append(-0.85) # disaster
    s.append(-0.7)  # trash
    s.append(-0.5)  # broken
    s.append(-0.6)  # fear
    s.append(-0.5)  # sick
    return s






def tokenize_lower(text):
    bs = text.encode('utf-8')
    n = len(text)
    tokens = []
    start = -1
    for i in range(n):
        c = bs[i]
        if c == 32 or c == 9 or c == 10:
            if start >= 0:
                tok = str("")
                for j in range(start, i):
                    b = bs[j]
                    if _is_alpha_byte(b) or b == 39 or b == 45:
                        tok += chr(int(_to_lower_byte(b)))
                if len(tok) > 0:
                    tokens.append(tok)
                start = -1
        else:
            if start < 0:
                start = i
    if start >= 0:
        tok = str("")
        for j in range(start, n):
            b = bs[j]
            if _is_alpha_byte(b) or b == 39 or b == 45:
                tok += chr(int(_to_lower_byte(b)))
        if len(tok) > 0:
            tokens.append(tok)
    return tokens








def word_sentiment(word):
    lower = word.lower()
    words = _lexicon_words()
    scores = _lexicon_scores()
    for i in range(len(words)):
        if words[i] == lower:
            return scores[i]
    return 0.0






def sentiment_score(text):
    tokens = tokenize_lower(text)
    total = 0.0
    count = 0
    for i in range(len(tokens)):
        s = word_sentiment(tokens[i])
        if s != 0.0:
            total += s
            count += 1
    if count == 0:
        return 0.0
    return total / float(count)






def polarity(text):
    return sentiment_score(text)






def sentiment_label(score):
    if score > 0.05:
        return "positive"
    if score < -0.05:
        return "negative"
    return "neutral"






def subjectivity(text):
    tokens = tokenize_lower(text)
    total = len(tokens)
    if total == 0:
        return 0.0
    found = 0
    for i in range(total):
        if word_sentiment(tokens[i]) != 0.0:
            found += 1
    return float(found) / float(total)






def count_positive_words(text):
    tokens = tokenize_lower(text)
    count = 0
    for i in range(len(tokens)):
        if word_sentiment(tokens[i]) > 0.0:
            count += 1
    return count






def count_negative_words(text):
    tokens = tokenize_lower(text)
    count = 0
    for i in range(len(tokens)):
        if word_sentiment(tokens[i]) < 0.0:
            count += 1
    return count






def most_positive_word(text):
    tokens = tokenize_lower(text)
    best_word = str("")
    best_score = -2.0
    for i in range(len(tokens)):
        s = word_sentiment(tokens[i])
        if s > best_score:
            best_score = s
            best_word = tokens[i]
    return best_word






def most_negative_word(text):
    tokens = tokenize_lower(text)
    worst_word = str("")
    worst_score = 2.0
    for i in range(len(tokens)):
        s = word_sentiment(tokens[i])
        if s < worst_score:
            worst_score = s
            worst_word = tokens[i]
    return worst_word
