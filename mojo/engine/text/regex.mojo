"""
regex.mojo — Basic pattern matching. Zero Python imports.
Covers: literal match, *, +, ?, ., character classes [abc], [a-z], [0-9],
        ^, $, |, escapes (\\d, \\w, \\s, \\., \\\\, \\*, etc.).
Not a full PCRE engine — optimized for common data validation patterns.
"""


# ── Byte helpers ──────────────────────────────────────────────────────────────

comptime _BACKSLASH = UInt8(92)
comptime _DOT = UInt8(46)
comptime _STAR = UInt8(42)
comptime _PLUS = UInt8(43)
comptime _QMARK = UInt8(63)
comptime _CARET = UInt8(94)
comptime _DOLLAR = UInt8(36)
comptime _PIPE = UInt8(124)
comptime _LBRACK = UInt8(91)
comptime _RBRACK = UInt8(93)
comptime _DASH = UInt8(45)


@always_inline
def _is_digit(c: UInt8) -> Bool:
    return c >= UInt8(48) and c <= UInt8(57)

@always_inline
def _is_alpha(c: UInt8) -> Bool:
    return (c >= UInt8(65) and c <= UInt8(90)) or (c >= UInt8(97) and c <= UInt8(122))

@always_inline
def _is_word(c: UInt8) -> Bool:
    return _is_alpha(c) or _is_digit(c) or c == UInt8(95)

@always_inline
def _is_space(c: UInt8) -> Bool:
    return c == UInt8(32) or c == UInt8(9) or c == UInt8(10) or c == UInt8(13) or c == UInt8(12)


def _span(s: String, start: Int, end: Int) -> String:
    var bs = s.as_bytes()
    var e = min(end, len(s))
    var result = String("")
    for i in range(start, e):
        result += chr(Int(bs[i]))
    return result


# ── Pattern atom types ────────────────────────────────────────────────────────

comptime _AT_LITERAL = 0
comptime _AT_DOT = 1
comptime _AT_CLASS = 2
comptime _AT_DIGIT = 3
comptime _AT_WORD = 4
comptime _AT_SPACE = 5
comptime _AT_NDIGIT = 6
comptime _AT_NWORD = 7
comptime _AT_NSPACE = 8

comptime _QT_NONE = 0
comptime _QT_STAR = 1
comptime _QT_PLUS = 2
comptime _QT_QMARK = 3


struct _Atom(Copyable, Movable):
    var kind: Int
    var literal: UInt8
    var quantifier: Int
    var class_chars: String
    var class_negated: Bool

    def __init__(out self):
        self.kind = _AT_LITERAL
        self.literal = UInt8(0)
        self.quantifier = _QT_NONE
        self.class_chars = String("")
        self.class_negated = False

    def __init__(out self, kind: Int, literal: UInt8 = UInt8(0)):
        self.kind = kind
        self.literal = literal
        self.quantifier = _QT_NONE
        self.class_chars = String("")
        self.class_negated = False

    def __copyinit__(out self, copy: Self):
        self.kind = copy.kind
        self.literal = copy.literal
        self.quantifier = copy.quantifier
        self.class_chars = copy.class_chars
        self.class_negated = copy.class_negated


# ── Pattern bounds result ─────────────────────────────────────────────────────

struct _PBounds(Copyable, Movable):
    var start: Int
    var end: Int
    var anchor_start: Bool
    var anchor_end: Bool

    def __init__(out self, start: Int, end: Int, anchor_start: Bool, anchor_end: Bool):
        self.start = start
        self.end = end
        self.anchor_start = anchor_start
        self.anchor_end = anchor_end

    def __copyinit__(out self, copy: Self):
        self.start = copy.start
        self.end = copy.end
        self.anchor_start = copy.anchor_start
        self.anchor_end = copy.anchor_end


def _atom_matches(atom: _Atom, c: UInt8) -> Bool:
    if atom.kind == _AT_LITERAL:
        return c == atom.literal
    if atom.kind == _AT_DOT:
        return c != UInt8(10)
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


def _class_contains(class_chars: String, negated: Bool, c: UInt8) -> Bool:
    var bs = class_chars.as_bytes()
    var n = len(class_chars)
    var found = False
    var i = 0
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


# ── Pattern compiler ──────────────────────────────────────────────────────────


def _compile_branch(pattern: String, start: Int, end: Int) -> List[_Atom]:
    var atoms = List[_Atom]()
    var bs = pattern.as_bytes()
    var i = start

    while i < end:
        var c = bs[i]

        if c == _BACKSLASH and i + 1 < end:
            var nc = bs[i + 1]
            var atom = _Atom()
            if nc == UInt8(100):
                atom.kind = _AT_DIGIT
            elif nc == UInt8(68):
                atom.kind = _AT_NDIGIT
            elif nc == UInt8(119):
                atom.kind = _AT_WORD
            elif nc == UInt8(87):
                atom.kind = _AT_NWORD
            elif nc == UInt8(115):
                atom.kind = _AT_SPACE
            elif nc == UInt8(83):
                atom.kind = _AT_NSPACE
            else:
                atom.kind = _AT_LITERAL
                atom.literal = nc
            i += 2
            if i < end:
                var q = bs[i]
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
            var atom = _Atom(_AT_CLASS)
            i += 1
            if i < end and bs[i] == _CARET:
                atom.class_negated = True
                i += 1
            var class_str = String("")
            while i < end and bs[i] != _RBRACK:
                class_str += chr(Int(bs[i]))
                i += 1
            atom.class_chars = class_str
            if i < end:
                i += 1
            if i < end:
                var q = bs[i]
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
            var atom = _Atom(_AT_DOT)
            i += 1
            if i < end:
                var q = bs[i]
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
            var atom = _Atom(_AT_LITERAL, c)
            i += 1
            if i < end:
                var q = bs[i]
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

    return atoms^


# ── Matching engine ───────────────────────────────────────────────────────────


def _match_atoms(atoms: List[_Atom], atom_idx: Int, text: String, text_pos: Int) -> Int:
    var ai = atom_idx
    var tp = text_pos
    var n_atoms = len(atoms)
    var n_text = len(text)
    var tbs = text.as_bytes()

    while ai < n_atoms:
        var atom = atoms[ai].copy()

        if atom.quantifier == _QT_NONE:
            if tp >= n_text:
                return -1
            if not _atom_matches(atom, tbs[tp]):
                return -1
            tp += 1
            ai += 1

        elif atom.quantifier == _QT_STAR:
            var max_count = 0
            var save = tp
            while save + max_count < n_text and _atom_matches(atom, tbs[save + max_count]):
                max_count += 1
            var count = max_count
            while count >= 0:
                var result = _match_atoms(atoms, ai + 1, text, save + count)
                if result >= 0:
                    return result
                count -= 1
            return -1

        elif atom.quantifier == _QT_PLUS:
            var max_count = 0
            var save = tp
            while save + max_count < n_text and _atom_matches(atom, tbs[save + max_count]):
                max_count += 1
            if max_count == 0:
                return -1
            var count = max_count
            while count >= 1:
                var result = _match_atoms(atoms, ai + 1, text, save + count)
                if result >= 0:
                    return result
                count -= 1
            return -1

        elif atom.quantifier == _QT_QMARK:
            if tp < n_text and _atom_matches(atom, tbs[tp]):
                var result = _match_atoms(atoms, ai + 1, text, tp + 1)
                if result >= 0:
                    return result
            return _match_atoms(atoms, ai + 1, text, tp)

        else:
            ai += 1

    return tp


def _split_alternations(pattern: String, start: Int, end: Int) -> List[Int]:
    var positions = List[Int]()
    var bs = pattern.as_bytes()
    var in_class = False
    var i = start
    while i < end:
        var c = bs[i]
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
    return positions^


def _has_start_anchor(pattern: String) -> Bool:
    if len(pattern) == 0:
        return False
    return pattern.as_bytes()[0] == _CARET


def _has_end_anchor(pattern: String) -> Bool:
    if len(pattern) == 0:
        return False
    var bs = pattern.as_bytes()
    var n = len(pattern)
    if bs[n - 1] != _DOLLAR:
        return False
    if n >= 2 and bs[n - 2] == _BACKSLASH:
        return False
    return True


def _pattern_bounds(pattern: String) -> _PBounds:
    var start = 0
    var end = len(pattern)
    var sa = _has_start_anchor(pattern)
    var ea = _has_end_anchor(pattern)
    if sa:
        start = 1
    if ea:
        end -= 1
    return _PBounds(start, end, sa, ea)


# ── Public API ────────────────────────────────────────────────────────────────


def regex_match(pattern: String, text: String) -> Bool:
    """Check if the entire text matches the pattern."""
    var pb = _pattern_bounds(pattern)

    var alts = _split_alternations(pattern, pb.start, pb.end)

    if len(alts) == 0:
        var atoms = _compile_branch(pattern, pb.start, pb.end)
        var result = _match_atoms(atoms, 0, text, 0)
        return result == len(text)
    else:
        var prev = pb.start
        for a in range(len(alts)):
            var atoms = _compile_branch(pattern, prev, alts[a])
            var result = _match_atoms(atoms, 0, text, 0)
            if result == len(text):
                return True
            prev = alts[a] + 1
        var atoms = _compile_branch(pattern, prev, pb.end)
        var result = _match_atoms(atoms, 0, text, 0)
        return result == len(text)


def regex_search(pattern: String, text: String) -> Int:
    """Find first occurrence of pattern in text. Returns start index or -1."""
    var pb = _pattern_bounds(pattern)
    var n = len(text)

    var alts = _split_alternations(pattern, pb.start, pb.end)

    var end_range = n
    if pb.anchor_start:
        end_range = 1

    for pos in range(0, end_range):
        if len(alts) == 0:
            var atoms = _compile_branch(pattern, pb.start, pb.end)
            var result = _match_atoms(atoms, 0, text, pos)
            if result >= 0:
                if pb.anchor_end and result != n:
                    continue
                return pos
        else:
            var prev = pb.start
            for a in range(len(alts)):
                var atoms = _compile_branch(pattern, prev, alts[a])
                var result = _match_atoms(atoms, 0, text, pos)
                if result >= 0:
                    if pb.anchor_end and result != n:
                        prev = alts[a] + 1
                        continue
                    return pos
                prev = alts[a] + 1
            var atoms = _compile_branch(pattern, prev, pb.end)
            var result = _match_atoms(atoms, 0, text, pos)
            if result >= 0:
                if not (pb.anchor_end and result != n):
                    return pos

    return -1


def _match_at(pattern: String, p_start: Int, p_end: Int, text: String, pos: Int) -> Int:
    var alts = _split_alternations(pattern, p_start, p_end)

    if len(alts) == 0:
        var atoms = _compile_branch(pattern, p_start, p_end)
        return _match_atoms(atoms, 0, text, pos)
    else:
        var prev = p_start
        for a in range(len(alts)):
            var atoms = _compile_branch(pattern, prev, alts[a])
            var result = _match_atoms(atoms, 0, text, pos)
            if result >= 0:
                return result
            prev = alts[a] + 1
        var atoms = _compile_branch(pattern, prev, p_end)
        return _match_atoms(atoms, 0, text, pos)


def regex_find_all(pattern: String, text: String) -> List[String]:
    """Find all non-overlapping matches of pattern in text."""
    var results = List[String]()
    var pb = _pattern_bounds(pattern)
    var n = len(text)
    var pos = 0

    while pos <= n:
        var end_pos = _match_at(pattern, pb.start, pb.end, text, pos)
        if end_pos >= 0 and end_pos >= pos:
            results.append(_span(text, pos, end_pos))
            if end_pos == pos:
                pos += 1
            else:
                pos = end_pos
        else:
            pos += 1

    return results^


def regex_replace(pattern: String, text: String, replacement: String) -> String:
    """Replace all occurrences of pattern in text with replacement."""
    var pb = _pattern_bounds(pattern)
    var n = len(text)
    var result = String("")
    var pos = 0
    var tbs = text.as_bytes()

    while pos <= n:
        var end_pos = _match_at(pattern, pb.start, pb.end, text, pos)
        if end_pos >= 0 and end_pos >= pos:
            result += replacement
            if end_pos == pos:
                if pos < n:
                    result += chr(Int(tbs[pos]))
                pos += 1
            else:
                pos = end_pos
        else:
            if pos < n:
                result += chr(Int(tbs[pos]))
            pos += 1

    return result


def regex_split(pattern: String, text: String) -> List[String]:
    """Split text by pattern matches."""
    var parts = List[String]()
    var pb = _pattern_bounds(pattern)
    var n = len(text)
    var last_end = 0
    var pos = 0

    while pos <= n:
        var end_pos = _match_at(pattern, pb.start, pb.end, text, pos)
        if end_pos >= 0 and end_pos > pos:
            parts.append(_span(text, last_end, pos))
            last_end = end_pos
            pos = end_pos
        else:
            pos += 1

    parts.append(_span(text, last_end, n))
    return parts^


def is_match_literal(pattern: String, text: String) -> Bool:
    """Fast path: literal string matching (no regex metacharacters)."""
    return pattern == text


def is_match_simple(pattern: String, text: String) -> Bool:
    """Match with only . * + ? support (no character classes)."""
    var atoms = _compile_branch(pattern, 0, len(pattern))
    var result = _match_atoms(atoms, 0, text, 0)
    return result == len(text)
