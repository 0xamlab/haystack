"""Python equivalent of mojo/engine/text.regex.mojo (auto-generated)."""
import math
import random as _rng

_BACKSLASH = int(92)
_DOT = int(46)
_STAR = int(42)
_PLUS = int(43)
_QMARK = int(63)
_CARET = int(94)
_DOLLAR = int(36)
_PIPE = int(124)
_LBRACK = int(91)
_RBRACK = int(93)
_DASH = int(45)

class _Atom:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('kind')
        self.kind = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('literal')
        self.literal = _v1 if _v1 is not None else 0
        self.quantifier = 0
        self.class_chars = ""
        self.class_negated = False
    def __repr__(self):
        return f'_Atom({vars(self)})'

class _PBounds:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('start')
        self.start = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('end')
        self.end = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('anchor_start')
        self.anchor_start = _v2 if _v2 is not None else False
        _v3 = args[3] if 3 < len(args) else kwargs.get('anchor_end')
        self.anchor_end = _v3 if _v3 is not None else False
    def __repr__(self):
        return f'_PBounds({vars(self)})'

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

def _is_digit(c):
    return c >= int(48) and c <= int(57)


def _is_alpha(c):
    return (c >= int(65) and c <= int(90)) or (c >= int(97) and c <= int(122))


def _is_word(c):
    return _is_alpha(c) or _is_digit(c) or c == int(95)


def _is_space(c):
    return c == int(32) or c == int(9) or c == int(10) or c == int(13) or c == int(12)



def _span(s, start, end):
    bs = s.encode('utf-8')
    e = min(end, len(s))
    result = str("")
    for i in range(start, e):
        result += chr(int(bs[i]))
    return result




_AT_LITERAL = 0
_AT_DOT = 1
_AT_CLASS = 2
_AT_DIGIT = 3
_AT_WORD = 4
_AT_SPACE = 5
_AT_NDIGIT = 6
_AT_NWORD = 7
_AT_NSPACE = 8

_QT_NONE = 0
_QT_STAR = 1
_QT_PLUS = 2
_QT_QMARK = 3



def _atom_matches(atom, c):
    if atom.kind == _AT_LITERAL:
        return c == atom.literal
    if atom.kind == _AT_DOT:
        return c != int(10)
    if atom.kind == _AT_DIGIT:
        return _is_digit(c)
    if atom.kind == _AT_WORD:
        return _is_word(c)
    if atom.kind == _AT_SPACE:
        return _is_space(c)
    if atom.kind == _AT_NDIGIT:
        return not _is_digit(c)
    if atom.kind == _AT_NWORD:
        return not _is_word(c)
    if atom.kind == _AT_NSPACE:
        return not _is_space(c)
    if atom.kind == _AT_CLASS:
        return _class_contains(atom.class_chars, atom.class_negated, c)
    return False



def _class_contains(class_chars, negated, c):
    bs = class_chars.encode('utf-8')
    n = len(class_chars)
    found = False
    i = 0
    while i < n:
        if i + 2 < n and bs[i + 1] == _DASH:
            if c >= bs[i] and c <= bs[i + 2]:
                found = True
                break
            i += 3
        else:
            if c == bs[i]:
                found = True
                break
            i += 1
    if negated:
        return not found
    return found






def _compile_branch(pattern, start, end):
    atoms = []
    bs = pattern.encode('utf-8')
    i = start

    while i < end:
        c = bs[i]

        if c == _BACKSLASH and i + 1 < end:
            nc = bs[i + 1]
            atom = _Atom()
            if nc == int(100):
                atom.kind = _AT_DIGIT
            elif nc == int(68):
                atom.kind = _AT_NDIGIT
            elif nc == int(119):
                atom.kind = _AT_WORD
            elif nc == int(87):
                atom.kind = _AT_NWORD
            elif nc == int(115):
                atom.kind = _AT_SPACE
            elif nc == int(83):
                atom.kind = _AT_NSPACE
            else:
                atom.kind = _AT_LITERAL
                atom.literal = nc
            i += 2
            if i < end:
                q = bs[i]
                if q == _STAR:
                    atom.quantifier = _QT_STAR
                    i += 1
                elif q == _PLUS:
                    atom.quantifier = _QT_PLUS
                    i += 1
                elif q == _QMARK:
                    atom.quantifier = _QT_QMARK
                    i += 1
            atoms.append(atom.copy())

        elif c == _LBRACK:
            atom = _Atom(_AT_CLASS)
            i += 1
            if i < end and bs[i] == _CARET:
                atom.class_negated = True
                i += 1
            class_str = str("")
            while i < end and bs[i] != _RBRACK:
                class_str += chr(int(bs[i]))
                i += 1
            atom.class_chars = class_str
            if i < end:
                i += 1
            if i < end:
                q = bs[i]
                if q == _STAR:
                    atom.quantifier = _QT_STAR
                    i += 1
                elif q == _PLUS:
                    atom.quantifier = _QT_PLUS
                    i += 1
                elif q == _QMARK:
                    atom.quantifier = _QT_QMARK
                    i += 1
            atoms.append(atom.copy())

        elif c == _DOT:
            atom = _Atom(_AT_DOT)
            i += 1
            if i < end:
                q = bs[i]
                if q == _STAR:
                    atom.quantifier = _QT_STAR
                    i += 1
                elif q == _PLUS:
                    atom.quantifier = _QT_PLUS
                    i += 1
                elif q == _QMARK:
                    atom.quantifier = _QT_QMARK
                    i += 1
            atoms.append(atom.copy())

        elif c == _CARET or c == _DOLLAR:
            i += 1

        else:
            atom = _Atom(_AT_LITERAL, c)
            i += 1
            if i < end:
                q = bs[i]
                if q == _STAR:
                    atom.quantifier = _QT_STAR
                    i += 1
                elif q == _PLUS:
                    atom.quantifier = _QT_PLUS
                    i += 1
                elif q == _QMARK:
                    atom.quantifier = _QT_QMARK
                    i += 1
            atoms.append(atom.copy())

    return atoms






def _match_atoms(atoms, atom_idx, text, text_pos):
    ai = atom_idx
    tp = text_pos
    n_atoms = len(atoms)
    n_text = len(text)
    tbs = text.encode('utf-8')

    while ai < n_atoms:
        atom = atoms[ai].copy()

        if atom.quantifier == _QT_NONE:
            if tp >= n_text:
                return -1
            if not _atom_matches(atom, tbs[tp]):
                return -1
            tp += 1
            ai += 1

        elif atom.quantifier == _QT_STAR:
            max_count = 0
            save = tp
            while save + max_count < n_text and _atom_matches(atom, tbs[save + max_count]):
                max_count += 1
            count = max_count
            while count >= 0:
                result = _match_atoms(atoms, ai + 1, text, save + count)
                if result >= 0:
                    return result
                count -= 1
            return -1

        elif atom.quantifier == _QT_PLUS:
            max_count = 0
            save = tp
            while save + max_count < n_text and _atom_matches(atom, tbs[save + max_count]):
                max_count += 1
            if max_count == 0:
                return -1
            count = max_count
            while count >= 1:
                result = _match_atoms(atoms, ai + 1, text, save + count)
                if result >= 0:
                    return result
                count -= 1
            return -1

        elif atom.quantifier == _QT_QMARK:
            if tp < n_text and _atom_matches(atom, tbs[tp]):
                result = _match_atoms(atoms, ai + 1, text, tp + 1)
                if result >= 0:
                    return result
            return _match_atoms(atoms, ai + 1, text, tp)

        else:
            ai += 1

    return tp



def _split_alternations(pattern, start, end):
    positions = []
    bs = pattern.encode('utf-8')
    in_class = False
    i = start
    while i < end:
        c = bs[i]
        if c == _BACKSLASH:
            i += 2
            continue
        if c == _LBRACK:
            in_class = True
        elif c == _RBRACK:
            in_class = False
        elif c == _PIPE and not in_class:
            positions.append(i)
        i += 1
    return positions



def _has_start_anchor(pattern):
    if len(pattern) == 0:
        return False
    return pattern.encode('utf-8')[0] == _CARET



def _has_end_anchor(pattern):
    if len(pattern) == 0:
        return False
    bs = pattern.encode('utf-8')
    n = len(pattern)
    if bs[n - 1] != _DOLLAR:
        return False
    if n >= 2 and bs[n - 2] == _BACKSLASH:
        return False
    return True



def _pattern_bounds(pattern):
    start = 0
    end = len(pattern)
    sa = _has_start_anchor(pattern)
    ea = _has_end_anchor(pattern)
    if sa:
        start = 1
    if ea:
        end -= 1
    return _PBounds(start, end, sa, ea)






def _match_at(pattern, p_start, p_end, text, pos):
    alts = _split_alternations(pattern, p_start, p_end)

    if len(alts) == 0:
        atoms = _compile_branch(pattern, p_start, p_end)
        return _match_atoms(atoms, 0, text, pos)
    else:
        prev = p_start
        for a in range(len(alts)):
            atoms = _compile_branch(pattern, prev, alts[a])
            result = _match_atoms(atoms, 0, text, pos)
            if result >= 0:
                return result
            prev = alts[a] + 1
        atoms = _compile_branch(pattern, prev, p_end)
        return _match_atoms(atoms, 0, text, pos)



def regex_match(pattern, text):
    pb = _pattern_bounds(pattern)

    alts = _split_alternations(pattern, pb.start, pb.end)

    if len(alts) == 0:
        atoms = _compile_branch(pattern, pb.start, pb.end)
        result = _match_atoms(atoms, 0, text, 0)
        return result == len(text)
    else:
        prev = pb.start
        for a in range(len(alts)):
            atoms = _compile_branch(pattern, prev, alts[a])
            result = _match_atoms(atoms, 0, text, 0)
            if result == len(text):
                return True
            prev = alts[a] + 1
        atoms = _compile_branch(pattern, prev, pb.end)
        result = _match_atoms(atoms, 0, text, 0)
        return result == len(text)



def regex_search(pattern, text):
    pb = _pattern_bounds(pattern)
    n = len(text)

    alts = _split_alternations(pattern, pb.start, pb.end)

    end_range = n
    if pb.anchor_start:
        end_range = 1

    for pos in range(0, end_range):
        if len(alts) == 0:
            atoms = _compile_branch(pattern, pb.start, pb.end)
            result = _match_atoms(atoms, 0, text, pos)
            if result >= 0:
                if pb.anchor_end and result != n:
                    continue
                return pos
        else:
            prev = pb.start
            for a in range(len(alts)):
                atoms = _compile_branch(pattern, prev, alts[a])
                result = _match_atoms(atoms, 0, text, pos)
                if result >= 0:
                    if pb.anchor_end and result != n:
                        prev = alts[a] + 1
                        continue
                    return pos
                prev = alts[a] + 1
            atoms = _compile_branch(pattern, prev, pb.end)
            result = _match_atoms(atoms, 0, text, pos)
            if result >= 0:
                if not (pb.anchor_end and result != n):
                    return pos

    return -1



def regex_find_all(pattern, text):
    results = []
    pb = _pattern_bounds(pattern)
    n = len(text)
    pos = 0

    while pos <= n:
        end_pos = _match_at(pattern, pb.start, pb.end, text, pos)
        if end_pos >= 0 and end_pos >= pos:
            results.append(_span(text, pos, end_pos))
            if end_pos == pos:
                pos += 1
            else:
                pos = end_pos
        else:
            pos += 1

    return results



def regex_replace(pattern, text, replacement):
    pb = _pattern_bounds(pattern)
    n = len(text)
    result = str("")
    pos = 0
    tbs = text.encode('utf-8')

    while pos <= n:
        end_pos = _match_at(pattern, pb.start, pb.end, text, pos)
        if end_pos >= 0 and end_pos >= pos:
            result += replacement
            if end_pos == pos:
                if pos < n:
                    result += chr(int(tbs[pos]))
                pos += 1
            else:
                pos = end_pos
        else:
            if pos < n:
                result += chr(int(tbs[pos]))
            pos += 1

    return result



def regex_split(pattern, text):
    parts = []
    pb = _pattern_bounds(pattern)
    n = len(text)
    last_end = 0
    pos = 0

    while pos <= n:
        end_pos = _match_at(pattern, pb.start, pb.end, text, pos)
        if end_pos >= 0 and end_pos > pos:
            parts.append(_span(text, last_end, pos))
            last_end = end_pos
            pos = end_pos
        else:
            pos += 1

    parts.append(_span(text, last_end, n))
    return parts



def is_match_literal(pattern, text):
    return pattern == text



def is_match_simple(pattern, text):
    atoms = _compile_branch(pattern, 0, len(pattern))
    result = _match_atoms(atoms, 0, text, 0)
    return result == len(text)
