"""sheet.refs — A1-style cell and range references.

Excel's grid is rows 1..1048576 and columns A..XFD (1..16384). Internally both
are 0-based. A coordinate packs as `row * 16384 + col`, which tops out below
2^34 and is therefore exact in an Int and in a Float64.

Refusal-first: every parser returns a success flag; nothing indexes on a
malformed reference. Absoluteness ($) is preserved as flag bits because
shared-formula followers shift only the RELATIVE parts.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_sheet_refs.mojo
benchmark: benchmarks/mojo_benchmarks/bench_sheet_plane.mojo
docs: docs/mojo/sheet-plane.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

from sheet.numio import _bs_str

comptime MAX_ROWS: Int = 1048576
comptime MAX_COLS: Int = 16384

# Flag bits for relative/absolute parts (set bit = RELATIVE, shiftable).
comptime REL_ROW0: Int = 1
comptime REL_COL0: Int = 2
comptime REL_ROW1: Int = 4
comptime REL_COL1: Int = 8
# Whole-column (A:A) / whole-row (3:7) markers.
comptime WHOLE_COL: Int = 16
comptime WHOLE_ROW: Int = 32


def pack_coord(row: Int, col: Int) -> Int:
    return row * MAX_COLS + col


def coord_row(coord: Int) -> Int:
    return coord // MAX_COLS


def coord_col(coord: Int) -> Int:
    return coord % MAX_COLS


def col_name(col: Int) -> String:
    """0-based column index -> letters (0 -> A, 16383 -> XFD)."""
    if col < 0 or col >= MAX_COLS:
        return String("?")
    var c = col
    var tmp = List[Int]()
    while True:
        tmp.append(c % 26)
        c = c // 26 - 1
        if c < 0:
            break
    var out = String("")
    var i = len(tmp) - 1
    while i >= 0:
        out += chr(65 + tmp[i])
        i -= 1
    return out^


def a1_of(row: Int, col: Int) -> String:
    """0-based (row, col) -> "A1" text."""
    var out = col_name(col)
    out += String(row + 1)
    return out^


def parse_col_letters(bs: Span[UInt8, _], start: Int, end: Int, mut col: Int) -> Bool:
    """[start, end) uppercase-folded letters -> 0-based column. False when the
    run is empty, too long, or out of the A..XFD grid."""
    var n = end - start
    if n <= 0 or n > 3:
        return False
    var acc = 0
    for i in range(start, end):
        var b = Int(bs[i])
        if b >= 97 and b <= 122:
            b -= 32
        if b < 65 or b > 90:
            return False
        acc = acc * 26 + (b - 64)
    if acc < 1 or acc > MAX_COLS:
        return False
    col = acc - 1
    return True


def parse_row_digits(bs: Span[UInt8, _], start: Int, end: Int, mut row: Int) -> Bool:
    """[start, end) digits -> 0-based row. False on empty/overflow/zero."""
    var n = end - start
    if n <= 0 or n > 7:
        return False
    var acc = 0
    for i in range(start, end):
        var b = Int(bs[i])
        if b < 48 or b > 57:
            return False
        acc = acc * 10 + (b - 48)
    if acc < 1 or acc > MAX_ROWS:
        return False
    row = acc - 1
    return True


struct A1Parse(Copyable, Movable):
    """Result of parsing one A1 cell token like `$B$7` (no sheet, no range)."""

    var ok: Bool
    var row: Int
    var col: Int
    var row_rel: Bool
    var col_rel: Bool

    def __init__(out self):
        self.ok = False
        self.row = 0
        self.col = 0
        self.row_rel = True
        self.col_rel = True


def parse_a1_cell(text: String) -> A1Parse:
    """Parse a single-cell A1 reference with optional $ marks. Refuses
    anything with leftover bytes, so "A1B", "A0", "XFE1" all fail.

    @capability parse_a1_cell
    complexity: O(len(text))
    counts: none
    @endcapability
    """
    var out = A1Parse()
    var bs = text.as_bytes()
    var n = len(bs)
    var i = 0
    if i < n and Int(bs[i]) == 36:  # $
        out.col_rel = False
        i += 1
    var col_start = i
    while i < n:
        var b = Int(bs[i])
        if (b >= 65 and b <= 90) or (b >= 97 and b <= 122):
            i += 1
        else:
            break
    var col = 0
    if not parse_col_letters(bs, col_start, i, col):
        return out^
    if i < n and Int(bs[i]) == 36:
        out.row_rel = False
        i += 1
    var row_start = i
    while i < n:
        var b = Int(bs[i])
        if b >= 48 and b <= 57:
            i += 1
        else:
            break
    var row = 0
    if not parse_row_digits(bs, row_start, i, row):
        return out^
    if i != n:
        return out^
    out.ok = True
    out.row = row
    out.col = col
    return out^


struct RefParse(Copyable, Movable):
    """Result of parsing a full reference `[['Sheet Name'|Sheet]!]A1[:B2]`,
    including whole-column `A:A` and whole-row `3:7` forms. `sheet_name` is
    empty when no sheet qualifier was present. `flags` uses REL_*/WHOLE_*."""

    var ok: Bool
    var has_sheet: Bool
    var sheet_name: String
    var is_range: Bool
    var r0: Int
    var c0: Int
    var r1: Int
    var c1: Int
    var flags: Int

    def __init__(out self):
        self.ok = False
        self.has_sheet = False
        self.sheet_name = String("")
        self.is_range = False
        self.r0 = 0
        self.c0 = 0
        self.r1 = 0
        self.c1 = 0
        self.flags = 0


def _find_bang(bs: Span[UInt8, _], n: Int) -> Int:
    """Index of the `!` separating a sheet qualifier, honouring '...' quoting
    with '' escapes. -1 when there is none."""
    var i = 0
    if i < n and Int(bs[i]) == 39:  # opening quote
        i += 1
        while i < n:
            if Int(bs[i]) == 39:
                if i + 1 < n and Int(bs[i + 1]) == 39:
                    i += 2
                    continue
                i += 1
                break
            i += 1
        if i < n and Int(bs[i]) == 33:
            return i
        return -1
    while i < n:
        if Int(bs[i]) == 33:
            return i
        i += 1
    return -1


def _unquote_sheet(bs: Span[UInt8, _], end: Int) -> String:
    """The sheet-name text before the `!` at `end`, with quoting removed."""
    var i = 0
    var n = end
    var buf = List[UInt8]()
    if n > 0 and Int(bs[0]) == 39:
        i = 1
        while i < n:
            if Int(bs[i]) == 39:
                if i + 1 < n and Int(bs[i + 1]) == 39:
                    buf.append(UInt8(39))
                    i += 2
                    continue
                break
            buf.append(bs[i])
            i += 1
        return _bs_str(buf)
    while i < n:
        buf.append(bs[i])
        i += 1
    return _bs_str(buf)


def parse_ref_text(text: String) -> RefParse:
    """Parse a (possibly sheet-qualified, possibly rectangular) reference.
    This is the INDIRECT("...") grammar and the loader's grammar for defined
    names; the formula tokenizer uses the piece parsers directly. Sheet-BANG
    forms it refuses (3-D `S1:S2!A1`, external `[1]S!A1`) come back not-ok;
    the caller decides between #REF! and an UNSUP taint.

    @capability parse_ref_text
    complexity: O(len(text))
    counts: none
    @endcapability
    """
    var out = RefParse()
    var bs = text.as_bytes()
    var n = len(bs)
    if n == 0 or n > 256:
        return out^
    if Int(bs[0]) == 91:  # [  external workbook
        return out^
    var bang = _find_bang(bs, n)
    var body_start = 0
    if bang >= 0:
        out.has_sheet = True
        out.sheet_name = _unquote_sheet(bs, bang)
        if len(out.sheet_name) == 0 or len(out.sheet_name) > 64:
            out.ok = False
            return out^
        body_start = bang + 1
    # split body on ':' (at most one)
    var colon = -1
    var j = body_start
    while j < n:
        if Int(bs[j]) == 58:
            if colon >= 0:
                return out^
            colon = j
        j += 1
    if colon < 0:
        var one = _sub(bs, body_start, n)
        var p = parse_a1_cell(one)
        if not p.ok:
            return out^
        out.ok = True
        out.r0 = p.row
        out.c0 = p.col
        out.r1 = p.row
        out.c1 = p.col
        var fl = 0
        if p.row_rel:
            fl |= REL_ROW0 | REL_ROW1
        if p.col_rel:
            fl |= REL_COL0 | REL_COL1
        out.flags = fl
        return out^
    var left = _sub(bs, body_start, colon)
    var right = _sub(bs, colon + 1, n)
    # whole-column A:C or whole-row 3:7 first
    var wc = _parse_col_only(left)
    var wc2 = _parse_col_only(right)
    if wc.ok and wc2.ok:
        out.ok = True
        out.is_range = True
        out.r0 = 0
        out.r1 = MAX_ROWS - 1
        out.c0 = min(wc.col, wc2.col)
        out.c1 = max(wc.col, wc2.col)
        var fl = WHOLE_COL
        if wc.rel:
            fl |= REL_COL0
        if wc2.rel:
            fl |= REL_COL1
        out.flags = fl
        return out^
    var wr = _parse_row_only(left)
    var wr2 = _parse_row_only(right)
    if wr.ok and wr2.ok:
        out.ok = True
        out.is_range = True
        out.c0 = 0
        out.c1 = MAX_COLS - 1
        out.r0 = min(wr.row, wr2.row)
        out.r1 = max(wr.row, wr2.row)
        var fl = WHOLE_ROW
        if wr.rel:
            fl |= REL_ROW0
        if wr2.rel:
            fl |= REL_ROW1
        out.flags = fl
        return out^
    var pl = parse_a1_cell(left)
    var pr = parse_a1_cell(right)
    if not pl.ok or not pr.ok:
        return out^
    out.ok = True
    out.is_range = True
    out.r0 = min(pl.row, pr.row)
    out.r1 = max(pl.row, pr.row)
    out.c0 = min(pl.col, pr.col)
    out.c1 = max(pl.col, pr.col)
    var fl = 0
    if pl.row_rel:
        fl |= REL_ROW0
    if pl.col_rel:
        fl |= REL_COL0
    if pr.row_rel:
        fl |= REL_ROW1
    if pr.col_rel:
        fl |= REL_COL1
    out.flags = fl
    return out^


struct _ColOnly(Copyable, Movable):
    var ok: Bool
    var col: Int
    var rel: Bool

    def __init__(out self):
        self.ok = False
        self.col = 0
        self.rel = True


struct _RowOnly(Copyable, Movable):
    var ok: Bool
    var row: Int
    var rel: Bool

    def __init__(out self):
        self.ok = False
        self.row = 0
        self.rel = True


def _parse_col_only(text: String) -> _ColOnly:
    var out = _ColOnly()
    var bs = text.as_bytes()
    var n = len(bs)
    var i = 0
    if i < n and Int(bs[i]) == 36:
        out.rel = False
        i += 1
    var col = 0
    if parse_col_letters(bs, i, n, col):
        out.ok = True
        out.col = col
    return out^


def _parse_row_only(text: String) -> _RowOnly:
    var out = _RowOnly()
    var bs = text.as_bytes()
    var n = len(bs)
    var i = 0
    if i < n and Int(bs[i]) == 36:
        out.rel = False
        i += 1
    var row = 0
    if parse_row_digits(bs, i, n, row):
        out.ok = True
        out.row = row
    return out^


def _sub(bs: Span[UInt8, _], start: Int, end: Int) -> String:
    var buf = List[UInt8]()
    var e = min(end, len(bs))
    var i = max(0, start)
    while i < e:
        buf.append(bs[i])
        i += 1
    return _bs_str(buf)
