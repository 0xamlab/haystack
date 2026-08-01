"""sheet.values — typed cell values and Excel coercion rules.

The classic error values (#DIV/0!, #REF!, #VALUE!, #N/A, ...) are typed VALUES
that propagate through every operator and function, never crashes. Two extra
internal kinds carry honesty rather than data:

  * UNSUP  — the cell's result passed through something this build does not
             implement (an unimplemented function, a structured reference, an
             external workbook link). The taint carries the reason NAME so the
             uncovered tail is counted per function, never silently skipped.
  * PENDING / CYCLE — engine-internal: a dereferenced formula cell that is not
             computed yet, and a cell on a named dependency cycle.

Number formatting follows Excel's &-conversion (round to 15 significant
digits, plain notation between 1e-4 and 1e21, otherwise scientific) so string
results can be compared byte-for-byte against cached values.

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

from std.math import abs as fabs, floor

from sheet.numio import _bs_str

# ── Value kinds ───────────────────────────────────────────────────────────────
comptime VK_EMPTY: Int = 0
comptime VK_NUM: Int = 1
comptime VK_TEXT: Int = 2
comptime VK_BOOL: Int = 3
comptime VK_ERR: Int = 4
comptime VK_RANGE: Int = 5  # engine-internal: an unresolved reference value
comptime VK_UNSUP: Int = 6  # honesty taint: text holds the reason name
comptime VK_PENDING: Int = 7  # engine-internal: a holds the blocking cell index
comptime VK_CYCLE: Int = 8  # cell participates in (or depends on) a named cycle
comptime VK_ARRAY: Int = 9  # engine-internal: materialized array

# ── Error codes (Excel's classic seven) ───────────────────────────────────────
comptime ERR_NULL: Int = 1  # #NULL!
comptime ERR_DIV0: Int = 2  # #DIV/0!
comptime ERR_VALUE: Int = 3  # #VALUE!
comptime ERR_REF: Int = 4  # #REF!
comptime ERR_NAME: Int = 5  # #NAME?
comptime ERR_NUM: Int = 6  # #NUM!
comptime ERR_NA: Int = 7  # #N/A


fn error_name(code: Int) -> String:
    """The literal Excel spelling for an error code.

    @capability error_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if code == ERR_NULL:
        return String("#NULL!")
    if code == ERR_DIV0:
        return String("#DIV/0!")
    if code == ERR_VALUE:
        return String("#VALUE!")
    if code == ERR_REF:
        return String("#REF!")
    if code == ERR_NAME:
        return String("#NAME?")
    if code == ERR_NUM:
        return String("#NUM!")
    if code == ERR_NA:
        return String("#N/A")
    return String("#UNKNOWN_ERR!")


fn error_code_of(text: String) -> Int:
    """Parse an error literal to its code; 0 when `text` is not an error literal.

    @capability error_code_of
    complexity: O(len(text))
    counts: none
    @endcapability
    """
    if text == "#NULL!":
        return ERR_NULL
    if text == "#DIV/0!":
        return ERR_DIV0
    if text == "#VALUE!":
        return ERR_VALUE
    if text == "#REF!":
        return ERR_REF
    if text == "#NAME?":
        return ERR_NAME
    if text == "#NUM!":
        return ERR_NUM
    if text == "#N/A":
        return ERR_NA
    # Modern error literals we recognise by name but do not produce: they are
    # reported as an UNSUP reason upstream, never silently zero. #SPILL!,
    # #CALC!, #GETTING_DATA are matched by prefix at the call sites that care.
    return 0


# ── The value record ─────────────────────────────────────────────────────────
struct CellValue(Copyable, Movable):
    """One typed spreadsheet value. `kind` selects which fields carry data:

    NUM -> num; TEXT -> text; BOOL -> num (0/1); ERR -> err; UNSUP -> text is
    the reason name; PENDING -> a is the blocking global cell index;
    RANGE -> a=sheet, b=r0, c=c0, d=r1, e=c1. EMPTY/CYCLE carry nothing.
    ARRAY values live only in the evaluator (element pool indices a..b).
    """

    var kind: Int
    var num: Float64
    var text: String
    var err: Int
    var a: Int
    var b: Int
    var c: Int
    var d: Int
    var e: Int

    fn __init__(out self):
        self.kind = VK_EMPTY
        self.num = 0.0
        self.text = String("")
        self.err = 0
        self.a = 0
        self.b = 0
        self.c = 0
        self.d = 0
        self.e = 0


fn cv_empty() -> CellValue:
    return CellValue()


fn cv_num(x: Float64) -> CellValue:
    var v = CellValue()
    v.kind = VK_NUM
    v.num = x
    return v^


fn cv_text(s: String) -> CellValue:
    var v = CellValue()
    v.kind = VK_TEXT
    v.text = s
    return v^


fn cv_bool(b: Bool) -> CellValue:
    var v = CellValue()
    v.kind = VK_BOOL
    v.num = 1.0 if b else 0.0
    return v^


fn cv_err(code: Int) -> CellValue:
    var v = CellValue()
    v.kind = VK_ERR
    v.err = code
    return v^


fn cv_unsup(reason: String) -> CellValue:
    var v = CellValue()
    v.kind = VK_UNSUP
    v.text = reason
    return v^


fn cv_pending(cell_index: Int) -> CellValue:
    var v = CellValue()
    v.kind = VK_PENDING
    v.a = cell_index
    return v^


fn cv_cycle() -> CellValue:
    var v = CellValue()
    v.kind = VK_CYCLE
    return v^


fn cv_range(sheet: Int, r0: Int, c0: Int, r1: Int, c1: Int) -> CellValue:
    var v = CellValue()
    v.kind = VK_RANGE
    v.a = sheet
    v.b = r0
    v.c = c0
    v.d = r1
    v.e = c1
    return v^


fn is_taint(v: CellValue) -> Bool:
    """True when `v` must dominate any computation it touches (in priority
    order PENDING > UNSUP > CYCLE; plain errors are NOT taints — they are
    answers)."""
    return v.kind == VK_PENDING or v.kind == VK_UNSUP or v.kind == VK_CYCLE


# ── ASCII case folding (Excel text comparisons are case-insensitive) ─────────
fn fold_ascii(s: String) -> String:
    """Lower-case ASCII letters; other bytes pass through untouched."""
    var bs = s.as_bytes()
    var buf = List[UInt8]()
    for i in range(len(bs)):
        var b = Int(bs[i])
        if b >= 65 and b <= 90:
            b += 32
        buf.append(UInt8(b))
    return _bs_str(buf)


fn text_equal_ci(a: String, b: String) -> Bool:
    """Case-insensitive (ASCII) equality, Excel's `=` on text."""
    var ab = a.as_bytes()
    var bb = b.as_bytes()
    if len(ab) != len(bb):
        return False
    for i in range(len(ab)):
        var x = Int(ab[i])
        var y = Int(bb[i])
        if x >= 65 and x <= 90:
            x += 32
        if y >= 65 and y <= 90:
            y += 32
        if x != y:
            return False
    return True


fn text_cmp_ci(a: String, b: String) -> Int:
    """Case-insensitive (ASCII) ordering: -1, 0, 1."""
    var ab = a.as_bytes()
    var bb = b.as_bytes()
    var n = min(len(ab), len(bb))
    for i in range(n):
        var x = Int(ab[i])
        var y = Int(bb[i])
        if x >= 65 and x <= 90:
            x += 32
        if y >= 65 and y <= 90:
            y += 32
        if x < y:
            return -1
        if x > y:
            return 1
    if len(ab) < len(bb):
        return -1
    if len(ab) > len(bb):
        return 1
    return 0


# ── Wildcard match (COUNTIF/VLOOKUP-exact/MATCH text criteria) ────────────────
fn wildcard_match(pattern: String, candidate: String) -> Bool:
    """Excel wildcard semantics: `*` any run, `?` one char, `~` escapes the
    next wildcard. Case-insensitive. Iterative two-pointer algorithm with
    backtracking on the last `*` — no recursion, O(len(p)*len(c)) worst case.
    """
    var p = fold_ascii(pattern).as_bytes()
    var c = fold_ascii(candidate).as_bytes()
    var np = len(p)
    var nc = len(c)
    var pi = 0
    var ci = 0
    var star_p = -1
    var star_c = -1
    while ci < nc:
        var lit_ok = False
        if pi < np:
            var pb = Int(p[pi])
            if pb == 126 and pi + 1 < np:  # ~ escape
                if Int(p[pi + 1]) == Int(c[ci]):
                    pi += 2
                    ci += 1
                    lit_ok = True
            elif pb == 42:  # *
                star_p = pi
                star_c = ci
                pi += 1
                lit_ok = True
            elif pb == 63 or pb == Int(c[ci]):  # ? or exact byte
                pi += 1
                ci += 1
                lit_ok = True
        if not lit_ok:
            if star_p >= 0:
                star_c += 1
                ci = star_c
                pi = star_p + 1
            else:
                return False
    while pi < np and Int(p[pi]) == 42:
        pi += 1
    return pi == np


fn has_wildcard(s: String) -> Bool:
    var bs = s.as_bytes()
    for i in range(len(bs)):
        var b = Int(bs[i])
        if b == 42 or b == 63:
            return True
    return False


# ── Number → text, Excel &-conversion ─────────────────────────────────────────
fn _round_digits_15(mut digits: List[Int], mut exp10: Int):
    """Round a decimal digit string (value = 0.d0 d1 ... * 10^exp10) to 15
    significant digits in place, string-level, propagating carries."""
    if len(digits) <= 15:
        return
    var keep = 15
    var round_up = digits[keep] >= 5
    var out = List[Int]()
    for i in range(keep):
        out.append(digits[i])
    if round_up:
        var i = keep - 1
        while i >= 0:
            out[i] += 1
            if out[i] < 10:
                break
            out[i] = 0
            i -= 1
        if i < 0:
            # 999... rolled over to 1000...: one more magnitude
            var out2 = List[Int]()
            out2.append(1)
            for _ in range(keep - 1):
                out2.append(0)
            digits = out2^
            exp10 += 1
            return
    digits = out^


fn _digits_of_shortest(x: Float64, mut digits: List[Int], mut exp10: Int) -> Bool:
    """Extract the decimal digits of String(x) — Mojo's shortest round-trip
    formatting (verified exact in hostio/wire_json.mojo) — normalised so that
    value = 0.digits * 10^exp10 with digits[0] != 0. False on any byte the
    grammar `[+-]?DIGITS[.DIGITS][(e|E)[+-]DIGITS]` does not cover (nan/inf).
    """
    var s = String(x)
    var bs = s.as_bytes()
    var n = len(bs)
    var i = 0
    if i < n and (Int(bs[i]) == 45 or Int(bs[i]) == 43):
        i += 1
    var all_digits = List[Int]()
    var int_len = 0
    var seen_point = False
    while i < n:
        var b = Int(bs[i])
        if b >= 48 and b <= 57:
            all_digits.append(b - 48)
            if not seen_point:
                int_len += 1
            i += 1
        elif b == 46 and not seen_point:
            seen_point = True
            i += 1
        elif b == 101 or b == 69:
            break
        else:
            return False
    var sci_exp = 0
    if i < n:
        # must be e/E here
        i += 1
        var neg = False
        if i < n and (Int(bs[i]) == 45 or Int(bs[i]) == 43):
            neg = Int(bs[i]) == 45
            i += 1
        if i >= n:
            return False
        var acc = 0
        while i < n:
            var b2 = Int(bs[i])
            if b2 < 48 or b2 > 57:
                return False
            acc = acc * 10 + (b2 - 48)
            i += 1
        sci_exp = -acc if neg else acc
    if len(all_digits) == 0:
        return False
    # value = 0.all_digits * 10^(int_len + sci_exp); normalise leading zeros.
    var e = int_len + sci_exp
    var start = 0
    while start < len(all_digits) and all_digits[start] == 0:
        start += 1
        e -= 1
    var mant = List[Int]()
    for j in range(start, len(all_digits)):
        mant.append(all_digits[j])
    if len(mant) == 0:
        mant.append(0)
        e = 1
    digits = mant^
    exp10 = e
    return True


fn num_to_text(x: Float64) -> String:
    """Excel's number-to-text conversion (the `&` operator, General-style):
    round to 15 significant digits, plain notation for 1e-4 <= |x| < 1e21,
    otherwise scientific `mE+NN`. -0.0 renders as "0".

    @capability num_to_text
    complexity: O(digits)
    counts: none
    @endcapability
    """
    if x != x:
        return String("#NUM!")  # nan never appears as a stored Excel number
    if x == 0.0:
        return String("0")
    var neg = x < 0.0
    var ax = fabs(x)
    var digits = List[Int]()
    var exp10 = 0
    if not _digits_of_shortest(ax, digits, exp10):
        return String("#NUM!")
    _round_digits_15(digits, exp10)
    var dg = digits.copy()
    var e10 = exp10
    # strip trailing zeros
    var last = len(dg) - 1
    while last > 0 and dg[last] == 0:
        last -= 1
    var out = String("")
    if neg:
        out += "-"
    if e10 >= -3 and e10 <= 21:
        if e10 <= 0:
            out += "0."
            for _ in range(-e10):
                out += "0"
            for i in range(last + 1):
                out += chr(48 + dg[i])
        elif e10 >= last + 1:
            for i in range(last + 1):
                out += chr(48 + dg[i])
            for _ in range(e10 - (last + 1)):
                out += "0"
        else:
            for i in range(last + 1):
                if i == e10:
                    out += "."
                out += chr(48 + dg[i])
    else:
        # scientific: d.dddE+NN
        out += chr(48 + dg[0])
        if last >= 1:
            out += "."
            for i in range(1, last + 1):
                out += chr(48 + dg[i])
        var se = e10 - 1
        out += "E"
        if se >= 0:
            out += "+"
        else:
            out += "-"
            se = -se
        if se < 10:
            out += "0"
        out += String(se)
    return out^


fn value_to_display(v: CellValue) -> String:
    """Human-readable form for reports and cycle/mismatch messages."""
    if v.kind == VK_EMPTY:
        return String("<empty>")
    if v.kind == VK_NUM:
        return String(v.num)
    if v.kind == VK_TEXT:
        return v.text
    if v.kind == VK_BOOL:
        return String("TRUE") if v.num != 0.0 else String("FALSE")
    if v.kind == VK_ERR:
        return error_name(v.err)
    if v.kind == VK_UNSUP:
        var s = String("<unsupported:")
        s += v.text
        s += ">"
        return s^
    if v.kind == VK_CYCLE:
        return String("<cycle>")
    if v.kind == VK_RANGE:
        return String("<range>")
    if v.kind == VK_ARRAY:
        return String("<array>")
    return String("<pending>")
