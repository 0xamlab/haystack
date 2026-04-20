"""Python equivalent of mojo/engine/text.tokenizer.mojo (auto-generated)."""
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

def _is_punct(c):
    if c == ord(",") or c == ord(".") or c == ord("!") or c == ord("?"):
        return True
    if c == ord(";") or c == ord(":") or c == ord("'") or c == ord('"'):
        return True
    if c == ord("(") or c == ord(")") or c == ord("[") or c == ord("]"):
        return True
    if c == ord("{") or c == ord("}") or c == ord("-") or c == ord("/"):
        return True
    if c == ord("@") or c == ord("#") or c == ord("$") or c == ord("%"):
        return True
    if c == ord("&") or c == ord("*") or c == ord("+") or c == ord("="):
        return True
    if c == ord("<") or c == ord(">") or c == ord("\\") or c == ord("`"):
        return True
    if c == ord("~") or c == ord("^") or c == ord("|") or c == ord("_"):
        return True
    return False



def _to_lower(c):
    if c >= ord("A") and c <= ord("Z"):
        return c + 32
    return c



def _is_whitespace(c):
    return c == ord(" ") or c == ord("\t") or c == ord("\n") or c == ord("\r")



def _substr(s, start, end):
    sb = s.encode('utf-8')
    result = str("")
    for i in range(start, end):
        result += chr(int(sb[i]))
    return result



def is_stopword(word):
    if word == "the" or word == "a" or word == "an" or word == "is":
        return True
    if word == "are" or word == "was" or word == "were" or word == "be":
        return True
    if word == "been" or word == "being" or word == "have" or word == "has":
        return True
    if word == "had" or word == "do" or word == "does" or word == "did":
        return True
    if word == "in" or word == "on" or word == "at" or word == "to":
        return True
    if word == "for" or word == "of" or word == "and" or word == "or":
        return True
    if word == "but" or word == "not" or word == "with" or word == "this":
        return True
    if word == "that" or word == "it" or word == "from" or word == "by":
        return True
    if word == "as" or word == "if" or word == "so":
        return True
    return False






def word_tokenize(text):
    b = text.encode('utf-8')
    n = len(b)
    tokens = []
    current = str("")

    for i in range(n):
        c = int(b[i])
        if _is_whitespace(c):
            if len(current) > 0:
                tokens.append(current)
                current = str("")
        elif _is_punct(c):
            if len(current) > 0:
                tokens.append(current)
                current = str("")
        else:
            current += chr(_to_lower(c))

    if len(current) > 0:
        tokens.append(current)

    return tokens






def sentence_tokenize(text):
    b = text.encode('utf-8')
    n = len(b)
    sentences = []
    start = 0

    for i in range(n):
        c = int(b[i])
        if c == ord(".") or c == ord("!") or c == ord("?"):
            is_boundary = False
            if i == n - 1:
                is_boundary = True
            elif _is_whitespace(int(b[i + 1])):
                is_boundary = True

            if is_boundary:

                s_start = start
                while s_start <= i and _is_whitespace(int(b[s_start])):
                    s_start += 1
                if s_start <= i:
                    sentences.append(_substr(text, s_start, i + 1))
                start = i + 1


    if start < n:
        s_start = start
        s_end = n
        while s_start < s_end and _is_whitespace(int(b[s_start])):
            s_start += 1
        while s_end > s_start and _is_whitespace(int(b[s_end - 1])):
            s_end -= 1
        if s_start < s_end:
            sentences.append(_substr(text, s_start, s_end))

    return sentences






def char_ngrams(text, n):
    length = len(text)
    result = []
    if n <= 0 or length < n:
        return result
    for i in range(length - n + 1):
        result.append(_substr(text, i, i + n))
    return result






def word_ngrams(tokens, n):
    result = []
    length = len(tokens)
    if n <= 0 or length < n:
        return result
    for i in range(length - n + 1):
        gram = tokens[i]
        for j in range(1, n):
            gram += "_" + tokens[i + j]
        result.append(gram)
    return result






def remove_stopwords(tokens):
    result = []
    for i in range(len(tokens)):
        if not is_stopword(tokens[i]):
            result.append(tokens[i])
    return result






def stem_simple(word):
    b = word.encode('utf-8')
    n = len(b)


    if n < 4:
        return word


    if n > 3:
        if (
            int(b[n - 3]) == ord("i")
            and int(b[n - 2]) == ord("n")
            and int(b[n - 1]) == ord("g")
        ):
            return _substr(word, 0, n - 3)


    if n > 2:
        if int(b[n - 2]) == ord("e") and int(b[n - 1]) == ord("d"):
            return _substr(word, 0, n - 2)


    if n > 2:
        if int(b[n - 2]) == ord("l") and int(b[n - 1]) == ord("y"):
            return _substr(word, 0, n - 2)


    if n > 1:
        if int(b[n - 1]) == ord("s") and int(b[n - 2]) != ord("s"):
            return _substr(word, 0, n - 1)

    return word






def vocabulary_size(tokens):
    unique = []
    for i in range(len(tokens)):
        found = False
        for j in range(len(unique)):
            if unique[j] == tokens[i]:
                found = True
                break
        if not found:
            unique.append(tokens[i])
    return len(unique)






def token_frequency(tokens):
    unique = []
    counts = []
    for i in range(len(tokens)):
        found = False
        for j in range(len(unique)):
            if unique[j] == tokens[i]:
                counts[j] = counts[j] + 1
                found = True
                break
        if not found:
            unique.append(tokens[i])
            counts.append(1)


    nu = len(unique)
    for i in range(nu):
        for j in range(0, nu - i - 1):
            if counts[j] < counts[j + 1]:
                tmp_c = counts[j]
                counts[j] = counts[j + 1]
                counts[j + 1] = tmp_c
                tmp_t = unique[j]
                unique[j] = unique[j + 1]
                unique[j + 1] = tmp_t

    result = []
    for i in range(nu):
        pair = []
        pair.append(unique[i])
        pair.append(str(counts[i]))
        result.append(pair)
    return result






def pad_sequence(tokens, max_len, pad_token):
    result = []
    n = len(tokens)
    for i in range(max_len):
        if i < n:
            result.append(tokens[i])
        else:
            result.append(pad_token)
    return result
