"""sheet.formula — tokenizer + parser for Excel formula text.

Mirrors the flat-node IR pattern of `expr.parse_expr`: typed records appended
to a `List[FNode]`, children as Int indices into a shared `List[Int]` argument
pool — no pointers, no recursion in the data. The parser is recursive descent
with Excel's documented precedence, including the two traps:

  * unary minus binds TIGHTER than `^`  (=-2^2 is 4, not -4)
  * `^` is LEFT-associative              (=2^3^2 is 64, not 512)

Refusal-first: the parser never raises and never returns a half-built tree.
Anything outside the supported grammar (structured Table[Col] references,
external [1]Sheet!A1 links, union/intersection range operators, R1C1) becomes
a single NK_UNSUP root carrying the reason NAME, so the evaluator taints the
cell and the report counts it — never a crash, never a silent zero.

Function names are resolved to ids here; unknown names keep their text so the
uncovered-function table is produced by the engine itself, per function name.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_sheet_formula.mojo
benchmark: benchmarks/mojo_benchmarks/bench_sheet_plane.mojo
docs: docs/mojo/sheet-plane.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

from sheet.numio import _bs_str, _parse_number

from sheet.refs import (
    MAX_COLS,
    MAX_ROWS,
    REL_COL0,
    REL_COL1,
    REL_ROW0,
    REL_ROW1,
    WHOLE_COL,
    WHOLE_ROW,
    A1Parse,
    parse_a1_cell,
    _parse_col_only,
    _parse_row_only,
)
from sheet.values import ERR_NA, ERR_REF, error_code_of

# ── Node kinds ────────────────────────────────────────────────────────────────
comptime NK_NUM: Int = 1
comptime NK_STR: Int = 2
comptime NK_BOOL: Int = 3
comptime NK_ERR: Int = 4  # a = error code
comptime NK_REF: Int = 5  # a = sheet (-1 current), b = row, c = col, f = REL_* flags
comptime NK_RANGE: Int = 6  # a = sheet, b = r0, c = c0, d = r1, e = c1, f = flags
comptime NK_NAME: Int = 7  # text = defined name (folded), a = sheet scope or -1
comptime NK_FUNC: Int = 8  # text = name, b = fid, args in pool
comptime NK_BIN: Int = 9  # a = op, two args in pool
comptime NK_UN: Int = 10  # a = op (OP_NEG/OP_PCT), one arg in pool
comptime NK_MISSING: Int = 11  # an omitted argument slot
comptime NK_ARRAYLIT: Int = 12  # a = rows, b = cols, elements in pool row-major
comptime NK_UNSUP: Int = 13  # text = reason name

# ── Operator codes (NK_BIN.a / NK_UN.a) ──────────────────────────────────────
comptime OP_ADD: Int = 1
comptime OP_SUB: Int = 2
comptime OP_MUL: Int = 3
comptime OP_DIV: Int = 4
comptime OP_POW: Int = 5
comptime OP_CAT: Int = 6
comptime OP_EQ: Int = 7
comptime OP_NE: Int = 8
comptime OP_LT: Int = 9
comptime OP_GT: Int = 10
comptime OP_LE: Int = 11
comptime OP_GE: Int = 12
comptime OP_NEG: Int = 20
comptime OP_PCT: Int = 21

# ── Function ids, in strict census order ─────────────────────────────────────
comptime FID_UNKNOWN: Int = -1
comptime FID_VOLATILE: Int = -2  # TODAY/NOW/RAND/RANDBETWEEN: cached value is irreproducible
comptime FID_OFFSET: Int = 1
comptime FID_ROW: Int = 2
comptime FID_MIN: Int = 3
comptime FID_IF: Int = 4
comptime FID_SUM: Int = 5
comptime FID_VLOOKUP: Int = 6
comptime FID_IFERROR: Int = 7
comptime FID_COUNTIFS: Int = 8
comptime FID_TIME: Int = 9
comptime FID_INDIRECT: Int = 10
comptime FID_AND: Int = 11
comptime FID_MAX: Int = 12
comptime FID_AVERAGE: Int = 13
comptime FID_TEXTAFTER: Int = 14
comptime FID_ABS: Int = 15
comptime FID_STDEV: Int = 16
comptime FID_YEAR: Int = 17
comptime FID_COUNTIF: Int = 18
comptime FID_INDEX: Int = 19
comptime FID_MATCH: Int = 20
comptime FID_MONTH: Int = 21
comptime FID_SUMIF: Int = 22
comptime FID_RANK: Int = 23
# COLUMN is Phase-1 core (ROW's sibling: a position, not a value); after it
# the ids continue in strict census order 24..48. TEXT (rank 31) is the one
# deliberate skip — it needs a number-format engine and stays in the counted
# tail. TODAY (rank 25) is volatile by construction.
comptime FID_COLUMN: Int = 24
comptime FID_WEEKDAY: Int = 25
comptime FID_INT: Int = 26
comptime FID_LEFT: Int = 27
comptime FID_EDATE: Int = 28
comptime FID_SUBSTITUTE: Int = 29
comptime FID_EOMONTH: Int = 30
comptime FID_SLN: Int = 31
comptime FID_ROUNDUP: Int = 32
comptime FID_VALUE: Int = 33
comptime FID_SUMPRODUCT: Int = 34
comptime FID_SUMIFS: Int = 35
comptime FID_DAYS: Int = 36
comptime FID_LOOKUP: Int = 37
comptime FID_LARGE: Int = 38
comptime FID_RIGHT: Int = 39
comptime FID_LEN: Int = 40
comptime FID_OR: Int = 41
comptime FID_ROWS: Int = 42
comptime FID_ISNUMBER: Int = 43
comptime FID_CHOOSE: Int = 44
comptime FID_ROUNDDOWN: Int = 45
comptime FID_ISBLANK: Int = 46
comptime FID_DATE: Int = 47

comptime MAX_FORMULA_BYTES: Int = 32768
comptime MAX_NODES_PER_FORMULA: Int = 65536
comptime MAX_PARSE_DEPTH: Int = 200


fn function_id_of(name_upper: String) -> Int:
    """Resolve a (prefix-stripped, uppercased) function name to its id.

    @capability function_id_of
    complexity: O(len(name))
    counts: none
    @endcapability
    """
    if name_upper == "OFFSET":
        return FID_OFFSET
    if name_upper == "ROW":
        return FID_ROW
    if name_upper == "MIN":
        return FID_MIN
    if name_upper == "IF":
        return FID_IF
    if name_upper == "SUM":
        return FID_SUM
    if name_upper == "VLOOKUP":
        return FID_VLOOKUP
    if name_upper == "IFERROR":
        return FID_IFERROR
    if name_upper == "COUNTIFS":
        return FID_COUNTIFS
    if name_upper == "TIME":
        return FID_TIME
    if name_upper == "INDIRECT":
        return FID_INDIRECT
    if name_upper == "AND":
        return FID_AND
    if name_upper == "MAX":
        return FID_MAX
    if name_upper == "AVERAGE":
        return FID_AVERAGE
    if name_upper == "TEXTAFTER":
        return FID_TEXTAFTER
    if name_upper == "ABS":
        return FID_ABS
    if name_upper == "STDEV":
        return FID_STDEV
    if name_upper == "YEAR":
        return FID_YEAR
    if name_upper == "COUNTIF":
        return FID_COUNTIF
    if name_upper == "INDEX":
        return FID_INDEX
    if name_upper == "MATCH":
        return FID_MATCH
    if name_upper == "MONTH":
        return FID_MONTH
    if name_upper == "SUMIF":
        return FID_SUMIF
    if name_upper == "RANK":
        return FID_RANK
    if name_upper == "COLUMN":
        return FID_COLUMN
    if name_upper == "WEEKDAY":
        return FID_WEEKDAY
    if name_upper == "INT":
        return FID_INT
    if name_upper == "LEFT":
        return FID_LEFT
    if name_upper == "EDATE":
        return FID_EDATE
    if name_upper == "SUBSTITUTE":
        return FID_SUBSTITUTE
    if name_upper == "EOMONTH":
        return FID_EOMONTH
    if name_upper == "SLN":
        return FID_SLN
    if name_upper == "ROUNDUP":
        return FID_ROUNDUP
    if name_upper == "VALUE":
        return FID_VALUE
    if name_upper == "SUMPRODUCT":
        return FID_SUMPRODUCT
    if name_upper == "SUMIFS":
        return FID_SUMIFS
    if name_upper == "DAYS":
        return FID_DAYS
    if name_upper == "LOOKUP":
        return FID_LOOKUP
    if name_upper == "LARGE":
        return FID_LARGE
    if name_upper == "RIGHT":
        return FID_RIGHT
    if name_upper == "LEN":
        return FID_LEN
    if name_upper == "OR":
        return FID_OR
    if name_upper == "ROWS":
        return FID_ROWS
    if name_upper == "ISNUMBER":
        return FID_ISNUMBER
    if name_upper == "CHOOSE":
        return FID_CHOOSE
    if name_upper == "ROUNDDOWN":
        return FID_ROUNDDOWN
    if name_upper == "ISBLANK":
        return FID_ISBLANK
    if name_upper == "DATE":
        return FID_DATE
    if (
        name_upper == "TODAY"
        or name_upper == "NOW"
        or name_upper == "RAND"
        or name_upper == "RANDBETWEEN"
    ):
        return FID_VOLATILE
    return FID_UNKNOWN


# ── FNode ─────────────────────────────────────────────────────────────────────
struct FNode(Copyable, Movable):
    """One flat IR node. Children (for BIN/UN/FUNC/ARRAYLIT) are indices into
    the shared argument pool: pool[arg_start .. arg_start+argc)."""

    var k: Int
    var num: Float64
    var text: String
    var a: Int
    var b: Int
    var c: Int
    var d: Int
    var e: Int
    var f: Int
    var arg_start: Int
    var argc: Int

    fn __init__(out self, k: Int):
        self.k = k
        self.num = 0.0
        self.text = String("")
        self.a = 0
        self.b = 0
        self.c = 0
        self.d = 0
        self.e = 0
        self.f = 0
        self.arg_start = 0
        self.argc = 0


# ── Tokens ────────────────────────────────────────────────────────────────────
comptime TK_END: Int = 0
comptime TK_NUM: Int = 1
comptime TK_STR: Int = 2
comptime TK_ERR: Int = 3
comptime TK_IDENT: Int = 4  # letters/digits/_/./$/\ and bytes >= 128
comptime TK_QUOTED: Int = 5  # 'sheet name'
comptime TK_BANG: Int = 6
comptime TK_LP: Int = 7
comptime TK_RP: Int = 8
comptime TK_COMMA: Int = 9
comptime TK_COLON: Int = 10
comptime TK_SEMI: Int = 11
comptime TK_LB: Int = 12  # {
comptime TK_RB: Int = 13  # }
comptime TK_LSQ: Int = 14  # [
comptime TK_PLUS: Int = 15
comptime TK_MINUS: Int = 16
comptime TK_MUL: Int = 17
comptime TK_DIV: Int = 18
comptime TK_POW: Int = 19
comptime TK_AMP: Int = 20
comptime TK_PCT: Int = 21
comptime TK_EQ: Int = 22
comptime TK_NE: Int = 23
comptime TK_LT: Int = 24
comptime TK_GT: Int = 25
comptime TK_LE: Int = 26
comptime TK_GE: Int = 27
comptime TK_BAD: Int = 28


struct Token(Copyable, Movable):
    var kind: Int
    var num: Float64
    var text: String

    fn __init__(out self, kind: Int):
        self.kind = kind
        self.num = 0.0
        self.text = String("")


fn _is_ident_byte(b: Int) -> Bool:
    if b >= 48 and b <= 57:
        return True
    if b >= 65 and b <= 90:
        return True
    if b >= 97 and b <= 122:
        return True
    if b == 95 or b == 46 or b == 36 or b == 92 or b == 63:
        return True  # _ . $ \ ?  (? appears in some defined names)
    if b >= 128:
        return True  # UTF-8 continuation/lead bytes: sheet & defined names
    return False


fn _upper(s: String) -> String:
    var bs = s.as_bytes()
    var buf = List[UInt8]()
    for i in range(len(bs)):
        var b = Int(bs[i])
        if b >= 97 and b <= 122:
            b -= 32
        buf.append(UInt8(b))
    return _bs_str(buf)


fn tokenize(formula: String, mut toks: List[Token]) -> Bool:
    """Formula text (without the leading '=') -> token list. False only on a
    hard refusal (over-long input, unterminated string); anything merely odd
    becomes TK_BAD for the parser to refuse with a reason."""
    toks.clear()
    var bs = formula.as_bytes()
    var n = len(bs)
    if n > MAX_FORMULA_BYTES:
        return False
    var i = 0
    while i < n:
        var b = Int(bs[i])
        # whitespace (Excel intersection operator is NOT supported: documented)
        if b == 32 or b == 9 or b == 10 or b == 13:
            i += 1
            continue
        if b == 34:  # " string literal, "" escapes
            var t = Token(TK_STR)
            var sbuf = List[UInt8]()
            i += 1
            var closed = False
            while i < n:
                if Int(bs[i]) == 34:
                    if i + 1 < n and Int(bs[i + 1]) == 34:
                        sbuf.append(UInt8(34))
                        i += 2
                        continue
                    closed = True
                    i += 1
                    break
                sbuf.append(bs[i])
                i += 1
            if not closed:
                return False
            t.text = _bs_str(sbuf)
            toks.append(t^)
            continue
        if b == 39:  # ' quoted sheet name, '' escapes
            var t = Token(TK_QUOTED)
            var qbuf = List[UInt8]()
            i += 1
            var closed = False
            while i < n:
                if Int(bs[i]) == 39:
                    if i + 1 < n and Int(bs[i + 1]) == 39:
                        qbuf.append(UInt8(39))
                        i += 2
                        continue
                    closed = True
                    i += 1
                    break
                qbuf.append(bs[i])
                i += 1
            if not closed:
                return False
            t.text = _bs_str(qbuf)
            toks.append(t^)
            continue
        if b == 35:  # # error literal
            var t = Token(TK_ERR)
            var text = String("#")
            i += 1
            while i < n:
                var c = Int(bs[i])
                var is_body = (c >= 48 and c <= 57) or (c >= 65 and c <= 90) or (
                    c >= 97 and c <= 122
                ) or c == 47 or c == 95
                if is_body:
                    text += chr(c)
                    i += 1
                elif c == 33 or c == 63:  # ! or ? terminates most literals
                    text += chr(c)
                    i += 1
                    break
                else:
                    break
            t.text = _upper(text)
            toks.append(t^)
            continue
        if (b >= 48 and b <= 57) or b == 46:
            # number literal: digits [. digits] [E [+-] digits]
            var start = i
            var seen_dot = b == 46
            var seen_digit = b != 46
            i += 1
            while i < n:
                var c = Int(bs[i])
                if c >= 48 and c <= 57:
                    seen_digit = True
                    i += 1
                elif c == 46 and not seen_dot:
                    seen_dot = True
                    i += 1
                else:
                    break
            # exponent only when directly followed by digits/sign+digits
            if i < n and (Int(bs[i]) == 101 or Int(bs[i]) == 69) and seen_digit:
                var j = i + 1
                if j < n and (Int(bs[j]) == 43 or Int(bs[j]) == 45):
                    j += 1
                if j < n and Int(bs[j]) >= 48 and Int(bs[j]) <= 57:
                    i = j
                    while i < n and Int(bs[i]) >= 48 and Int(bs[i]) <= 57:
                        i += 1
            if not seen_digit:
                toks.append(Token(TK_BAD))
                continue
            var nbuf = List[UInt8]()
            for k2 in range(start, i):
                nbuf.append(bs[k2])
            var text = _bs_str(nbuf)
            var t = Token(TK_NUM)
            var v: Float64 = 0.0
            if not _parse_number(text, v):
                toks.append(Token(TK_BAD))
                continue
            t.num = v
            t.text = text^
            toks.append(t^)
            continue
        if _is_ident_byte(b) and not (b >= 48 and b <= 57):
            var t = Token(TK_IDENT)
            var ibuf = List[UInt8]()
            while i < n and _is_ident_byte(Int(bs[i])):
                ibuf.append(bs[i])
                i += 1
            t.text = _bs_str(ibuf)
            toks.append(t^)
            continue
        if b == 33:
            toks.append(Token(TK_BANG))
            i += 1
            continue
        if b == 40:
            toks.append(Token(TK_LP))
            i += 1
            continue
        if b == 41:
            toks.append(Token(TK_RP))
            i += 1
            continue
        if b == 44:
            toks.append(Token(TK_COMMA))
            i += 1
            continue
        if b == 58:
            toks.append(Token(TK_COLON))
            i += 1
            continue
        if b == 59:
            toks.append(Token(TK_SEMI))
            i += 1
            continue
        if b == 123:
            toks.append(Token(TK_LB))
            i += 1
            continue
        if b == 125:
            toks.append(Token(TK_RB))
            i += 1
            continue
        if b == 91:
            toks.append(Token(TK_LSQ))
            i += 1
            continue
        if b == 93:
            toks.append(Token(TK_BAD))
            i += 1
            continue
        if b == 43:
            toks.append(Token(TK_PLUS))
            i += 1
            continue
        if b == 45:
            toks.append(Token(TK_MINUS))
            i += 1
            continue
        if b == 42:
            toks.append(Token(TK_MUL))
            i += 1
            continue
        if b == 47:
            toks.append(Token(TK_DIV))
            i += 1
            continue
        if b == 94:
            toks.append(Token(TK_POW))
            i += 1
            continue
        if b == 38:
            toks.append(Token(TK_AMP))
            i += 1
            continue
        if b == 37:
            toks.append(Token(TK_PCT))
            i += 1
            continue
        if b == 61:
            toks.append(Token(TK_EQ))
            i += 1
            continue
        if b == 60:
            if i + 1 < n and Int(bs[i + 1]) == 62:
                toks.append(Token(TK_NE))
                i += 2
            elif i + 1 < n and Int(bs[i + 1]) == 61:
                toks.append(Token(TK_LE))
                i += 2
            else:
                toks.append(Token(TK_LT))
                i += 1
            continue
        if b == 62:
            if i + 1 < n and Int(bs[i + 1]) == 61:
                toks.append(Token(TK_GE))
                i += 2
            else:
                toks.append(Token(TK_GT))
                i += 1
            continue
        toks.append(Token(TK_BAD))
        i += 1
    toks.append(Token(TK_END))
    return True


# ── Parser ────────────────────────────────────────────────────────────────────
struct Parser(Copyable, Movable):
    """Recursive-descent state. `fail_reason` is set once and sticks; the
    public entry point converts it into a single NK_UNSUP root."""

    var toks: List[Token]
    var pos: Int
    var failed: Bool
    var fail_reason: String
    var sheet_names_folded: List[String]

    fn __init__(out self):
        self.toks = List[Token]()
        self.pos = 0
        self.failed = False
        self.fail_reason = String("")
        self.sheet_names_folded = List[String]()

    fn peek_kind(self) -> Int:
        if self.pos < len(self.toks):
            return self.toks[self.pos].kind
        return TK_END

    fn peek_kind_at(self, ahead: Int) -> Int:
        var p = self.pos + ahead
        if p < len(self.toks):
            return self.toks[p].kind
        return TK_END

    fn fail(mut self, reason: String):
        if not self.failed:
            self.failed = True
            self.fail_reason = reason

    fn resolve_sheet(self, name: String) -> Int:
        """Case-insensitive sheet lookup; -2 when unknown (eval -> #REF!)."""
        var folded = _fold(name)
        for i in range(len(self.sheet_names_folded)):
            if self.sheet_names_folded[i] == folded:
                return i
        return -2


fn _fold(s: String) -> String:
    var bs = s.as_bytes()
    var buf = List[UInt8]()
    for i in range(len(bs)):
        var b = Int(bs[i])
        if b >= 65 and b <= 90:
            b += 32
        buf.append(UInt8(b))
    return _bs_str(buf)


fn _strip_fn_prefix(name_upper: String) -> String:
    """Strip the storage prefixes modern functions carry: _XLFN.XLWS.,
    _XLFN., _XLWS., _XLPM.  (verified against corpus XML)."""
    var s = name_upper
    if _starts_with(s, "_XLFN.XLWS."):
        return _drop(s, 11)
    if _starts_with(s, "_XLFN."):
        return _drop(s, 6)
    if _starts_with(s, "_XLWS."):
        return _drop(s, 6)
    if _starts_with(s, "_XLPM."):
        return _drop(s, 6)
    return s


fn _starts_with(s: String, prefix: String) -> Bool:
    var sb = s.as_bytes()
    var pb = prefix.as_bytes()
    if len(sb) < len(pb):
        return False
    for i in range(len(pb)):
        if sb[i] != pb[i]:
            return False
    return True


fn _drop(s: String, n: Int) -> String:
    var bs = s.as_bytes()
    var buf = List[UInt8]()
    for i in range(n, len(bs)):
        buf.append(bs[i])
    return _bs_str(buf)


fn _new_node(mut nodes: List[FNode], var nd: FNode) -> Int:
    nodes.append(nd^)
    return len(nodes) - 1


fn parse_formula(
    formula: String, sheet_names: List[String], mut nodes: List[FNode], mut pool: List[Int]
) -> Int:
    """Parse one formula (text WITHOUT the leading '='). Appends nodes to the
    shared arena and returns the root index. Never raises and never fails the
    workbook: any refusal becomes an NK_UNSUP root whose text names the reason
    (STRUCTURED_REF, EXTERNAL_REF, RANGE_UNION, PARSE, DEEP_EXPR, ...), which
    the evaluator turns into an honestly-counted taint.

    @capability parse_formula
    complexity: O(len(formula))
    counts: none
    @endcapability
    """
    var base_nodes = len(nodes)
    var p = Parser()
    for i in range(len(sheet_names)):
        p.sheet_names_folded.append(_fold(sheet_names[i]))
    if not tokenize(formula, p.toks):
        var nd = FNode(NK_UNSUP)
        nd.text = String("PARSE")
        return _new_node(nodes, nd^)
    var root = _parse_cmp(p, nodes, pool, 0)
    if not p.failed and p.peek_kind() != TK_END:
        p.fail(String("PARSE"))
    if p.failed or root < 0 or len(nodes) - base_nodes > MAX_NODES_PER_FORMULA:
        var reason = p.fail_reason
        if len(reason) == 0:
            reason = String("PARSE")
        # roll back partial nodes so the arena carries no orphans
        while len(nodes) > base_nodes:
            _ = nodes.pop()
        var nd = FNode(NK_UNSUP)
        nd.text = reason
        return _new_node(nodes, nd^)
    return root


fn _parse_cmp(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    if depth > MAX_PARSE_DEPTH:
        p.fail(String("DEEP_EXPR"))
        return -1
    var left = _parse_concat(p, nodes, pool, depth + 1)
    while not p.failed:
        var k = p.peek_kind()
        var op = 0
        if k == TK_EQ:
            op = OP_EQ
        elif k == TK_NE:
            op = OP_NE
        elif k == TK_LT:
            op = OP_LT
        elif k == TK_GT:
            op = OP_GT
        elif k == TK_LE:
            op = OP_LE
        elif k == TK_GE:
            op = OP_GE
        else:
            break
        p.pos += 1
        var right = _parse_concat(p, nodes, pool, depth + 1)
        left = _bin(nodes, pool, op, left, right)
    return left


fn _parse_concat(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    if depth > MAX_PARSE_DEPTH:
        p.fail(String("DEEP_EXPR"))
        return -1
    var left = _parse_addsub(p, nodes, pool, depth + 1)
    while not p.failed and p.peek_kind() == TK_AMP:
        p.pos += 1
        var right = _parse_addsub(p, nodes, pool, depth + 1)
        left = _bin(nodes, pool, OP_CAT, left, right)
    return left


fn _parse_addsub(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    if depth > MAX_PARSE_DEPTH:
        p.fail(String("DEEP_EXPR"))
        return -1
    var left = _parse_muldiv(p, nodes, pool, depth + 1)
    while not p.failed:
        var k = p.peek_kind()
        if k == TK_PLUS:
            p.pos += 1
            var right = _parse_muldiv(p, nodes, pool, depth + 1)
            left = _bin(nodes, pool, OP_ADD, left, right)
        elif k == TK_MINUS:
            p.pos += 1
            var right = _parse_muldiv(p, nodes, pool, depth + 1)
            left = _bin(nodes, pool, OP_SUB, left, right)
        else:
            break
    return left


fn _parse_muldiv(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    if depth > MAX_PARSE_DEPTH:
        p.fail(String("DEEP_EXPR"))
        return -1
    var left = _parse_pow(p, nodes, pool, depth + 1)
    while not p.failed:
        var k = p.peek_kind()
        if k == TK_MUL:
            p.pos += 1
            var right = _parse_pow(p, nodes, pool, depth + 1)
            left = _bin(nodes, pool, OP_MUL, left, right)
        elif k == TK_DIV:
            p.pos += 1
            var right = _parse_pow(p, nodes, pool, depth + 1)
            left = _bin(nodes, pool, OP_DIV, left, right)
        else:
            break
    return left


fn _parse_pow(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    if depth > MAX_PARSE_DEPTH:
        p.fail(String("DEEP_EXPR"))
        return -1
    var left = _parse_unary(p, nodes, pool, depth + 1)
    while not p.failed and p.peek_kind() == TK_POW:
        p.pos += 1
        var right = _parse_unary(p, nodes, pool, depth + 1)
        left = _bin(nodes, pool, OP_POW, left, right)  # left-assoc: 2^3^2 = 64
    return left


fn _parse_unary(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    if depth > MAX_PARSE_DEPTH:
        p.fail(String("DEEP_EXPR"))
        return -1
    var k = p.peek_kind()
    if k == TK_MINUS:
        p.pos += 1
        var inner = _parse_unary(p, nodes, pool, depth + 1)
        return _un(nodes, pool, OP_NEG, inner)
    if k == TK_PLUS:
        p.pos += 1
        return _parse_unary(p, nodes, pool, depth + 1)
    return _parse_postfix(p, nodes, pool, depth + 1)


fn _parse_postfix(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    var e = _parse_primary(p, nodes, pool, depth + 1)
    while not p.failed and p.peek_kind() == TK_PCT:
        p.pos += 1
        e = _un(nodes, pool, OP_PCT, e)
    return e


fn _bin(mut nodes: List[FNode], mut pool: List[Int], op: Int, l: Int, r: Int) -> Int:
    if l < 0 or r < 0:
        return -1
    var nd = FNode(NK_BIN)
    nd.a = op
    nd.arg_start = len(pool)
    nd.argc = 2
    pool.append(l)
    pool.append(r)
    return _new_node(nodes, nd^)


fn _un(mut nodes: List[FNode], mut pool: List[Int], op: Int, x: Int) -> Int:
    if x < 0:
        return -1
    var nd = FNode(NK_UN)
    nd.a = op
    nd.arg_start = len(pool)
    nd.argc = 1
    pool.append(x)
    return _new_node(nodes, nd^)


fn _parse_primary(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], depth: Int) -> Int:
    if depth > MAX_PARSE_DEPTH:
        p.fail(String("DEEP_EXPR"))
        return -1
    var k = p.peek_kind()
    if k == TK_NUM:
        # possible whole-row range 3:7 (row-only ':' row-only)
        if p.peek_kind_at(1) == TK_COLON and p.peek_kind_at(2) == TK_NUM:
            var lrow = _row_only_of_num(p.toks[p.pos])
            var rrow = _row_only_of_num(p.toks[p.pos + 2])
            if lrow >= 0 and rrow >= 0:
                p.pos += 3
                var nd = FNode(NK_RANGE)
                nd.a = -1
                nd.b = min(lrow, rrow)
                nd.c = 0
                nd.d = max(lrow, rrow)
                nd.e = MAX_COLS - 1
                nd.f = WHOLE_ROW | REL_ROW0 | REL_ROW1
                return _new_node(nodes, nd^)
        var nd = FNode(NK_NUM)
        nd.num = p.toks[p.pos].num
        p.pos += 1
        return _new_node(nodes, nd^)
    if k == TK_STR:
        var nd = FNode(NK_STR)
        nd.text = p.toks[p.pos].text
        p.pos += 1
        return _new_node(nodes, nd^)
    if k == TK_ERR:
        var code = error_code_of(p.toks[p.pos].text)
        if code == 0:
            # modern error literal (#SPILL!, #CALC!, ...) we do not produce
            p.fail(String("MODERN_ERROR_LITERAL"))
            return -1
        var nd = FNode(NK_ERR)
        nd.a = code
        p.pos += 1
        return _new_node(nodes, nd^)
    if k == TK_LP:
        p.pos += 1
        var inner = _parse_cmp(p, nodes, pool, depth + 1)
        if p.peek_kind() == TK_COMMA:
            p.fail(String("RANGE_UNION"))
            return -1
        if p.peek_kind() != TK_RP:
            p.fail(String("PARSE"))
            return -1
        p.pos += 1
        return inner
    if k == TK_LB:
        return _parse_array_literal(p, nodes, pool)
    if k == TK_LSQ:
        p.fail(String("EXTERNAL_REF"))
        return -1
    if k == TK_QUOTED:
        # 'Sheet Name'!ref — a leading [N] marks an EXTERNAL workbook link,
        # which is unresolvable by construction (701 external-reference parts
        # corpus-wide): named taint, never a fake #REF! mismatch
        if p.peek_kind_at(1) != TK_BANG:
            p.fail(String("PARSE"))
            return -1
        var sheet_name = p.toks[p.pos].text
        var snb = sheet_name.as_bytes()
        if len(snb) > 0 and Int(snb[0]) == 91:
            p.fail(String("EXTERNAL_REF"))
            return -1
        p.pos += 2
        return _parse_ref_body(p, nodes, pool, sheet_name, True)
    if k == TK_IDENT:
        var text = p.toks[p.pos].text
        var next_k = p.peek_kind_at(1)
        if next_k == TK_LP:
            # function call
            p.pos += 2
            return _parse_call(p, nodes, pool, text, depth)
        if next_k == TK_BANG:
            # unquoted sheet qualifier — or a 3-D Sheet1:Sheet2!A1 we refuse
            p.pos += 2
            return _parse_ref_body(p, nodes, pool, text, True)
        if next_k == TK_LSQ:
            p.fail(String("STRUCTURED_REF"))
            return -1
        if next_k == TK_COLON:
            # A1:B2, A:A, $A:$C, A1:'x'!B2(refused), Sheet ranges handled above
            p.pos += 2  # consume IDENT and ':'
            return _parse_range_tail(p, nodes, pool, text, -1)
        p.pos += 1
        return _parse_single_token_ref_or_name(p, nodes, pool, text)
    p.fail(String("PARSE"))
    return -1


fn _row_only_of_num(t: Token) -> Int:
    """A TK_NUM token that is a plain integer row (digits only) -> 0-based
    row; -1 otherwise."""
    var bs = t.text.as_bytes()
    var n = len(bs)
    if n == 0 or n > 7:
        return -1
    var acc = 0
    for i in range(n):
        var b = Int(bs[i])
        if b < 48 or b > 57:
            return -1
        acc = acc * 10 + (b - 48)
    if acc < 1 or acc > MAX_ROWS:
        return -1
    return acc - 1


fn _parse_call(
    mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], raw_name: String, depth: Int
) -> Int:
    var name = _strip_fn_prefix(_upper(raw_name))
    var args = List[Int]()
    if p.peek_kind() == TK_RP:
        p.pos += 1
    else:
        while True:
            if p.peek_kind() == TK_COMMA or p.peek_kind() == TK_RP:
                # omitted argument slot
                var m = FNode(NK_MISSING)
                args.append(_new_node(nodes, m^))
            else:
                var a = _parse_cmp(p, nodes, pool, depth + 1)
                if p.failed or a < 0:
                    return -1
                args.append(a)
            if p.peek_kind() == TK_COMMA:
                p.pos += 1
                continue
            if p.peek_kind() == TK_RP:
                p.pos += 1
                break
            p.fail(String("PARSE"))
            return -1
    var nd = FNode(NK_FUNC)
    nd.text = name
    nd.b = function_id_of(name)
    nd.arg_start = len(pool)
    nd.argc = len(args)
    for i in range(len(args)):
        pool.append(args[i])
    return _new_node(nodes, nd^)


fn _parse_ref_body(
    mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], sheet_name: String, had_sheet: Bool
) -> Int:
    """After `Sheet!` — parse the A1/range body. The sheet resolves now; an
    unknown sheet becomes a #REF! constant (Excel's behaviour for a deleted
    sheet is #REF!; a NAMED but never-declared sheet in a stored formula is
    effectively that)."""
    var sheet_idx = p.resolve_sheet(sheet_name)
    var k = p.peek_kind()
    if k == TK_IDENT:
        var text = p.toks[p.pos].text
        if p.peek_kind_at(1) == TK_COLON:
            p.pos += 2
            return _parse_range_tail(p, nodes, pool, text, sheet_idx)
        p.pos += 1
        var pa = parse_a1_cell(text)
        if pa.ok:
            return _mk_ref(nodes, sheet_idx, pa)
        p.fail(String("PARSE"))
        return -1
    if k == TK_NUM:
        # whole-row with sheet: Sheet1!3:7
        if p.peek_kind_at(1) == TK_COLON and p.peek_kind_at(2) == TK_NUM:
            var lrow = _row_only_of_num(p.toks[p.pos])
            var rrow = _row_only_of_num(p.toks[p.pos + 2])
            if lrow >= 0 and rrow >= 0:
                p.pos += 3
                var nd = FNode(NK_RANGE)
                nd.a = sheet_idx
                nd.b = min(lrow, rrow)
                nd.c = 0
                nd.d = max(lrow, rrow)
                nd.e = MAX_COLS - 1
                nd.f = WHOLE_ROW | REL_ROW0 | REL_ROW1
                return _new_node(nodes, nd^)
        p.fail(String("PARSE"))
        return -1
    if k == TK_ERR:
        # Sheet1!#REF! — a stored broken reference
        p.pos += 1
        var nd = FNode(NK_ERR)
        nd.a = ERR_REF
        return _new_node(nodes, nd^)
    p.fail(String("PARSE"))
    return -1


fn _parse_range_tail(
    mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], left_text: String, sheet_idx: Int
) -> Int:
    """`left_text` came right before a consumed ':'. Parse the right side and
    build a RANGE node. Handles A1:B2, A:C, $A:$C; the row-only 3:7 form never
    reaches here (numbers are handled in primary)."""
    if p.peek_kind() != TK_IDENT and p.peek_kind() != TK_NUM:
        p.fail(String("PARSE"))
        return -1
    var right_text = p.toks[p.pos].text
    p.pos += 1
    var nd = FNode(NK_RANGE)
    nd.a = sheet_idx
    # cell:cell
    var pl = parse_a1_cell(left_text)
    var pr = parse_a1_cell(right_text)
    if pl.ok and pr.ok:
        nd.b = min(pl.row, pr.row)
        nd.c = min(pl.col, pr.col)
        nd.d = max(pl.row, pr.row)
        nd.e = max(pl.col, pr.col)
        # flags follow the NORMALISED corners, so a shared-formula shift moves
        # the same physical corner the $ was written on even for "B2:A1"
        var top_rel = pl.row_rel if pl.row <= pr.row else pr.row_rel
        var bot_rel = pr.row_rel if pl.row <= pr.row else pl.row_rel
        var left_rel = pl.col_rel if pl.col <= pr.col else pr.col_rel
        var right_rel = pr.col_rel if pl.col <= pr.col else pl.col_rel
        var fl = 0
        if top_rel:
            fl |= REL_ROW0
        if bot_rel:
            fl |= REL_ROW1
        if left_rel:
            fl |= REL_COL0
        if right_rel:
            fl |= REL_COL1
        nd.f = fl
        return _new_node(nodes, nd^)
    # col-only:col-only  (A:A, $B:D)
    var cl = _parse_col_only(left_text)
    var cr = _parse_col_only(right_text)
    if cl.ok and cr.ok:
        nd.b = 0
        nd.c = min(cl.col, cr.col)
        nd.d = MAX_ROWS - 1
        nd.e = max(cl.col, cr.col)
        var fl = WHOLE_COL
        if cl.rel:
            fl |= REL_COL0
        if cr.rel:
            fl |= REL_COL1
        nd.f = fl
        return _new_node(nodes, nd^)
    # row-only:row-only with $ ($3:$9 tokenizes as IDENT)
    var rl = _parse_row_only(left_text)
    var rr = _parse_row_only(right_text)
    if rl.ok and rr.ok:
        nd.b = min(rl.row, rr.row)
        nd.c = 0
        nd.d = max(rl.row, rr.row)
        nd.e = MAX_COLS - 1
        var fl = WHOLE_ROW
        if rl.rel:
            fl |= REL_ROW0
        if rr.rel:
            fl |= REL_ROW1
        nd.f = fl
        return _new_node(nodes, nd^)
    p.fail(String("DYNAMIC_RANGE_OP"))
    return -1


fn _mk_ref(mut nodes: List[FNode], sheet_idx: Int, pa: A1Parse) -> Int:
    var nd = FNode(NK_REF)
    nd.a = sheet_idx
    nd.b = pa.row
    nd.c = pa.col
    var fl = 0
    if pa.row_rel:
        fl |= REL_ROW0
    if pa.col_rel:
        fl |= REL_COL0
    nd.f = fl
    return _new_node(nodes, nd^)


fn _parse_single_token_ref_or_name(
    mut p: Parser, mut nodes: List[FNode], mut pool: List[Int], text: String
) -> Int:
    """A bare identifier: A1 cell, TRUE/FALSE, or a defined name."""
    var up = _upper(text)
    if up == "TRUE":
        var nd = FNode(NK_BOOL)
        nd.num = 1.0
        return _new_node(nodes, nd^)
    if up == "FALSE":
        var nd = FNode(NK_BOOL)
        nd.num = 0.0
        return _new_node(nodes, nd^)
    var pa = parse_a1_cell(text)
    if pa.ok:
        return _mk_ref(nodes, -1, pa)
    var nd = FNode(NK_NAME)
    nd.text = _fold(text)
    nd.a = -1
    return _new_node(nodes, nd^)


fn _parse_array_literal(mut p: Parser, mut nodes: List[FNode], mut pool: List[Int]) -> Int:
    """{1,2;3,4} — constants only (numbers with optional sign, strings, bools,
    error literals). Must be rectangular."""
    p.pos += 1  # consume {
    var elems = List[Int]()
    var cols = -1
    var row_cols = 0
    var rows = 1
    while True:
        var k = p.peek_kind()
        var neg = False
        if k == TK_MINUS:
            neg = True
            p.pos += 1
            k = p.peek_kind()
        if k == TK_NUM:
            var nd = FNode(NK_NUM)
            nd.num = -p.toks[p.pos].num if neg else p.toks[p.pos].num
            elems.append(_new_node(nodes, nd^))
            p.pos += 1
        elif k == TK_STR and not neg:
            var nd = FNode(NK_STR)
            nd.text = p.toks[p.pos].text
            elems.append(_new_node(nodes, nd^))
            p.pos += 1
        elif k == TK_IDENT and not neg:
            var up = _upper(p.toks[p.pos].text)
            if up == "TRUE" or up == "FALSE":
                var nd = FNode(NK_BOOL)
                nd.num = 1.0 if up == "TRUE" else 0.0
                elems.append(_new_node(nodes, nd^))
                p.pos += 1
            else:
                p.fail(String("PARSE"))
                return -1
        elif k == TK_ERR and not neg:
            var code = error_code_of(p.toks[p.pos].text)
            if code == 0:
                p.fail(String("MODERN_ERROR_LITERAL"))
                return -1
            var nd = FNode(NK_ERR)
            nd.a = code
            elems.append(_new_node(nodes, nd^))
            p.pos += 1
        else:
            p.fail(String("PARSE"))
            return -1
        row_cols += 1
        var nk = p.peek_kind()
        if nk == TK_COMMA:
            p.pos += 1
            continue
        if nk == TK_SEMI:
            if cols < 0:
                cols = row_cols
            elif row_cols != cols:
                p.fail(String("PARSE"))
                return -1
            row_cols = 0
            rows += 1
            p.pos += 1
            continue
        if nk == TK_RB:
            if cols < 0:
                cols = row_cols
            elif row_cols != cols:
                p.fail(String("PARSE"))
                return -1
            p.pos += 1
            break
        p.fail(String("PARSE"))
        return -1
    var nd = FNode(NK_ARRAYLIT)
    nd.a = rows
    nd.b = cols
    nd.arg_start = len(pool)
    nd.argc = len(elems)
    for i in range(len(elems)):
        pool.append(elems[i])
    return _new_node(nodes, nd^)
