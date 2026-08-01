"""sheet.engine — demand-driven topological recalc with named cycles.

The dependency DAG is traversed demand-first with an EXPLICIT cell stack (a
real corpus chain is O(cells) deep — finch carries million-row shared-formula
columns — so machine recursion is banned at the cell level; expression trees
recurse only to the parser's bounded depth). Discovery pushes a cell's static
dependencies (refs, ranges, names) above it; evaluation then runs with every
static dep black. Dynamic references — OFFSET and INDIRECT return REFERENCES,
rank 1 and rank 10 of the census — surface as PENDING values that push the
blocking cell and retry, so dynamic edges join the same traversal.

A dereference that lands on a cell already on the stack walks the demand
parent chain: found means a true cycle, and the cycle NAMES ITS CELLS
("Sheet1!K3 -> Sheet1!K4 -> Sheet1!K3") — the dag_validate lesson. Cycle
members become typed CYCLE values that taint dependents; live circular
workbooks (sbv2 real-estate models with iterative calc) refuse honestly
instead of crashing or spinning.

Work is charged, not just memory: every node evaluation, scanned cell and
materialised array element decrements one budget; exhaustion stops the recalc
with a partial, honestly-labelled report (status RECALC_BUDGET).

Status codes 1320-1339 (package range 1300-1349).

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_sheet_engine.mojo
benchmark: benchmarks/mojo_benchmarks/bench_sheet_plane.mojo
docs: docs/mojo/sheet-plane.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

from std.math import abs as fabs, floor, pow, sqrt

from sheet.formula import (
    FID_ABS,
    FID_AND,
    FID_CHOOSE,
    FID_COLUMN,
    FID_DATE,
    FID_DAYS,
    FID_EDATE,
    FID_EOMONTH,
    FID_INT,
    FID_ISBLANK,
    FID_ISNUMBER,
    FID_LARGE,
    FID_LEFT,
    FID_LEN,
    FID_LOOKUP,
    FID_OR,
    FID_RIGHT,
    FID_ROUNDDOWN,
    FID_ROUNDUP,
    FID_ROWS,
    FID_SLN,
    FID_SUBSTITUTE,
    FID_SUMIFS,
    FID_SUMPRODUCT,
    FID_VALUE,
    FID_WEEKDAY,
    FID_AVERAGE,
    FID_COUNTIF,
    FID_COUNTIFS,
    FID_IF,
    FID_IFERROR,
    FID_INDEX,
    FID_INDIRECT,
    FID_MATCH,
    FID_MAX,
    FID_MIN,
    FID_MONTH,
    FID_OFFSET,
    FID_RANK,
    FID_ROW,
    FID_STDEV,
    FID_SUM,
    FID_SUMIF,
    FID_TEXTAFTER,
    FID_TIME,
    FID_UNKNOWN,
    FID_VLOOKUP,
    FID_VOLATILE,
    FID_YEAR,
    FNode,
    NK_ARRAYLIT,
    NK_BIN,
    NK_BOOL,
    NK_ERR,
    NK_FUNC,
    NK_MISSING,
    NK_NAME,
    NK_NUM,
    NK_RANGE,
    NK_REF,
    NK_STR,
    NK_UN,
    NK_UNSUP,
    OP_ADD,
    OP_CAT,
    OP_DIV,
    OP_EQ,
    OP_GE,
    OP_GT,
    OP_LE,
    OP_LT,
    OP_MUL,
    OP_NE,
    OP_NEG,
    OP_PCT,
    OP_POW,
    OP_SUB,
)
from sheet.grid import (
    FT_ARRAY,
    FT_DATATABLE,
    FT_SHARED_FOLLOWER,
    Workbook,
)
from sheet.numio import _bs_str, _parse_number_trimmed
from sheet.refs import (
    MAX_COLS,
    MAX_ROWS,
    REL_COL0,
    REL_COL1,
    REL_ROW0,
    REL_ROW1,
    a1_of,
    parse_ref_text,
)
from sheet.values import (
    ERR_DIV0,
    ERR_NA,
    ERR_NAME,
    ERR_NUM,
    ERR_REF,
    ERR_VALUE,
    VK_ARRAY,
    VK_BOOL,
    VK_CYCLE,
    VK_EMPTY,
    VK_ERR,
    VK_NUM,
    VK_PENDING,
    VK_RANGE,
    VK_TEXT,
    VK_UNSUP,
    CellValue,
    cv_bool,
    cv_cycle,
    cv_empty,
    cv_err,
    cv_num,
    cv_pending,
    cv_range,
    cv_text,
    cv_unsup,
    error_code_of,
    fold_ascii,
    has_wildcard,
    num_to_text,
    text_cmp_ci,
    text_equal_ci,
    wildcard_match,
)

comptime RECALC_OK: Int = 1320
comptime RECALC_BUDGET: Int = 1321

comptime DEFAULT_BUDGET: Int = 2147483647  # ~2.1e9 charged ops per workbook
comptime MAX_ARRAY_ELEMS: Int = 2097152  # 2^21 materialised elements per array value
comptime MAX_EVAL_DEPTH: Int = 240
comptime MAX_RETRIES_PER_CELL: Int = 4096
comptime EXCEL_MAX_SERIAL: Int = 2958465  # 9999-12-31

# cell traversal states
comptime _WHITE: Int = 0
comptime _QUEUED: Int = 1
comptime _BLACK: Int = 2


struct _Ctx(Copyable, Movable):
    """Evaluation context: the cell whose formula is running. `dr`/`dc` are
    the shared-formula follower deltas applied to RELATIVE refs; array_mode
    is true inside a legacy array formula (t="array" master)."""

    var cell: Int
    var sheet: Int
    var row: Int
    var col: Int
    var dr: Int
    var dc: Int
    var array_mode: Bool

    fn __init__(out self):
        self.cell = -1
        self.sheet = 0
        self.row = 0
        self.col = 0
        self.dr = 0
        self.dc = 0
        self.array_mode = False


struct _EngineState(Copyable, Movable):
    var values: List[CellValue]  # per cell index (formula cells only)
    var state: List[Int]
    var discovered: List[Bool]
    var parent: List[Int]
    var retries: List[Int]
    var stack: List[Int]
    var arr_pool: List[CellValue]
    var ops: Int
    var budget: Int
    var exhausted: Bool
    var cur_cell: Int
    var max_stack: Int
    var cycle_count: Int
    var cycle_names: List[String]  # first few cycles, cells named
    var cycle_cells: Int

    fn __init__(out self):
        self.values = List[CellValue]()
        self.state = List[Int]()
        self.discovered = List[Bool]()
        self.parent = List[Int]()
        self.retries = List[Int]()
        self.stack = List[Int]()
        self.arr_pool = List[CellValue]()
        self.ops = 0
        self.budget = DEFAULT_BUDGET
        self.exhausted = False
        self.cur_cell = -1
        self.max_stack = 0
        self.cycle_count = 0
        self.cycle_names = List[String]()
        self.cycle_cells = 0

    fn charge(mut self, n: Int) -> Bool:
        """Charge `n` ops; False once the budget is gone."""
        self.ops += n
        if self.ops > self.budget:
            self.exhausted = True
            return False
        return True


fn _cell_name(wb: Workbook, ci: Int) -> String:
    var out = String("")
    var sh = wb.c_sheet[ci]
    if sh >= 0 and sh < len(wb.sheet_names):
        out += wb.sheet_names[sh]
    out += "!"
    out += a1_of(wb.c_coord[ci] // MAX_COLS, wb.c_coord[ci] % MAX_COLS)
    return out^


# ── Deref / cycle detection ──────────────────────────────────────────────────
fn _deref_cell(wb: Workbook, mut st: _EngineState, target: Int) -> CellValue:
    """The value stored at cell index `target`, or PENDING/CYCLE."""
    if wb.c_froot[target] < 0:
        # constant cell
        var k = wb.c_kind[target]
        if k == VK_NUM:
            return cv_num(wb.c_num[target])
        if k == VK_TEXT:
            return cv_text(wb.c_text[target])
        if k == VK_BOOL:
            return cv_bool(wb.c_num[target] != 0.0)
        if k == VK_ERR:
            return cv_err(wb.c_err[target])
        return cv_empty()
    if st.state[target] == _BLACK:
        return st.values[target].copy()
    if st.state[target] == _QUEUED:
        # possible cycle: is `target` an ancestor of the evaluating cell?
        var walker = st.cur_cell
        var steps = 0
        while walker >= 0 and steps <= len(st.stack) + 1:
            if walker == target:
                _record_cycle(wb, st, target)
                return cv_cycle()
            walker = st.parent[walker]
            steps += 1
    return cv_pending(target)


fn _record_cycle(wb: Workbook, mut st: _EngineState, target: Int):
    """Name the cycle target -> ... -> cur_cell -> target and mark every cell
    on it BLACK with a typed CYCLE value."""
    st.cycle_count += 1
    var chain = List[Int]()
    var walker = st.cur_cell
    var steps = 0
    while walker >= 0 and steps <= len(st.stack) + 1:
        chain.append(walker)
        if walker == target:
            break
        walker = st.parent[walker]
        steps += 1
    # chain is cur_cell .. target; present it target-first
    if len(st.cycle_names) < 4:
        var name = String("")
        var i = len(chain) - 1
        var shown = 0
        while i >= 0:
            name += _cell_name(wb, chain[i])
            name += " -> "
            i -= 1
            shown += 1
            if shown >= 32 and i >= 0:
                name += "... -> "
                break
        name += _cell_name(wb, target)
        st.cycle_names.append(name^)
    for i in range(len(chain)):
        var ci = chain[i]
        if st.state[ci] != _BLACK:
            st.state[ci] = _BLACK
            st.values[ci] = cv_cycle()
            st.cycle_cells += 1


# ── Taint combination ────────────────────────────────────────────────────────
fn _taint_rank(v: CellValue) -> Int:
    if v.kind == VK_PENDING:
        return 3
    if v.kind == VK_UNSUP:
        return 2
    if v.kind == VK_CYCLE:
        return 1
    return 0


fn _worse_taint(a: CellValue, b: CellValue) -> CellValue:
    if _taint_rank(a) >= _taint_rank(b):
        return a.copy()
    return b.copy()


# ── Scalarisation / coercion ─────────────────────────────────────────────────
fn _materialize(
    wb: Workbook, mut st: _EngineState, rng: CellValue, mut rows: Int, mut cols: Int
) -> CellValue:
    """RANGE -> ARRAY (elements in st.arr_pool). Bounded by MAX_ARRAY_ELEMS
    and the budget; blanks materialise as EMPTY elements."""
    var r0 = rng.b
    var c0 = rng.c
    var r1 = rng.d
    var c1 = rng.e
    rows = r1 - r0 + 1
    cols = c1 - c0 + 1
    if rows <= 0 or cols <= 0:
        return cv_err(ERR_REF)
    if rows * cols > MAX_ARRAY_ELEMS:
        return cv_unsup(String("ARRAY_TOO_LARGE"))
    if not st.charge(rows * cols):
        return cv_unsup(String("BUDGET"))
    var start = len(st.arr_pool)
    for _ in range(rows * cols):
        st.arr_pool.append(cv_empty())
    # fill from stored cells in the rectangle (row-band walk)
    var lo = 0
    var hi = 0
    if wb.row_slice_bounds(
        rng.a, r0 * MAX_COLS + c0, r1 * MAX_COLS + c1, lo, hi
    ):
        for p in range(lo, hi):
            var ci = wb.perm_row[p]
            var coord = wb.c_coord[ci]
            var col = coord % MAX_COLS
            if col < c0 or col > c1:
                continue
            var row = coord // MAX_COLS
            var v = _deref_cell(wb, st, ci)
            if v.kind == VK_PENDING:
                return v^
            st.arr_pool[start + (row - r0) * cols + (col - c0)] = v^
    var out = CellValue()
    out.kind = VK_ARRAY
    out.a = start
    out.b = rows
    out.c = cols
    return out^


fn _array_elem(st: _EngineState, arr: CellValue, r: Int, c: Int) -> CellValue:
    """Broadcast-aware element access: a 1-wide/1-tall dimension repeats;
    anything else out of shape is #N/A (Excel array semantics)."""
    var rr = r
    var cc = c
    if arr.b == 1:
        rr = 0
    if arr.c == 1:
        cc = 0
    if rr < 0 or rr >= arr.b or cc < 0 or cc >= arr.c:
        return cv_err(ERR_NA)
    var idx = arr.a + rr * arr.c + cc
    if idx < 0 or idx >= len(st.arr_pool):
        return cv_err(ERR_NA)
    return st.arr_pool[idx].copy()


fn _to_scalar(wb: Workbook, mut st: _EngineState, ctx: _Ctx, v: CellValue) -> CellValue:
    """RANGE -> one cell value. In array mode this is the (0,0) element; in
    scalar mode it is Excel's implicit intersection against the formula cell
    (single column spanning the formula's row, single row spanning its
    column, or 1x1) and #VALUE! otherwise. ARRAY -> (0,0) element."""
    if v.kind == VK_RANGE:
        if ctx.array_mode:
            var target = wb.find_cell(v.a, v.b, v.c)
            if target < 0:
                return cv_empty()
            return _deref_cell(wb, st, target)
        var r0 = v.b
        var c0 = v.c
        var r1 = v.d
        var c1 = v.e
        var row = -1
        var col = -1
        if r0 == r1 and c0 == c1:
            row = r0
            col = c0
        elif c0 == c1 and ctx.row >= r0 and ctx.row <= r1:
            row = ctx.row
            col = c0
        elif r0 == r1 and ctx.col >= c0 and ctx.col <= c1:
            row = r0
            col = ctx.col
        else:
            return cv_err(ERR_VALUE)
        var target = wb.find_cell(v.a, row, col)
        if target < 0:
            return cv_empty()
        return _deref_cell(wb, st, target)
    if v.kind == VK_ARRAY:
        return _array_elem(st, v, 0, 0)
    return v.copy()


fn _to_number(v: CellValue, mut out_num: Float64) -> Int:
    """Scalar -> Float64 with Excel coercion. Returns 0 ok, else an error
    code. EMPTY coerces to 0; text must parse as one plain decimal."""
    if v.kind == VK_NUM:
        out_num = v.num
        return 0
    if v.kind == VK_BOOL:
        out_num = v.num
        return 0
    if v.kind == VK_EMPTY:
        out_num = 0.0
        return 0
    if v.kind == VK_TEXT:
        var parsed: Float64 = 0.0
        if _parse_number_trimmed(v.text, parsed):
            out_num = parsed
            return 0
        return ERR_VALUE
    if v.kind == VK_ERR:
        return v.err
    return ERR_VALUE


fn _to_text(v: CellValue) -> String:
    if v.kind == VK_TEXT:
        return v.text
    if v.kind == VK_NUM:
        return num_to_text(v.num)
    if v.kind == VK_BOOL:
        return String("TRUE") if v.num != 0.0 else String("FALSE")
    if v.kind == VK_EMPTY:
        return String("")
    return String("")


fn _to_bool(v: CellValue, mut out_b: Bool) -> Int:
    """Scalar -> logical. Numbers: nonzero. Text: TRUE/FALSE (any case) or a
    number-looking string; anything else #VALUE!. EMPTY -> FALSE."""
    if v.kind == VK_BOOL:
        out_b = v.num != 0.0
        return 0
    if v.kind == VK_NUM:
        out_b = v.num != 0.0
        return 0
    if v.kind == VK_EMPTY:
        out_b = False
        return 0
    if v.kind == VK_TEXT:
        var f = fold_ascii(v.text)
        if f == "true":
            out_b = True
            return 0
        if f == "false":
            out_b = False
            return 0
        var parsed: Float64 = 0.0
        if _parse_number_trimmed(v.text, parsed):
            out_b = parsed != 0.0
            return 0
        return ERR_VALUE
    if v.kind == VK_ERR:
        return v.err
    return ERR_VALUE


fn _type_rank(v: CellValue) -> Int:
    # Excel ordering: numbers < text < FALSE < TRUE (bool ranks above text)
    if v.kind == VK_NUM:
        return 0
    if v.kind == VK_TEXT:
        return 1
    if v.kind == VK_BOOL:
        return 2
    return 0


fn _compare_scalars(l: CellValue, r: CellValue, mut ord_out: Int) -> Int:
    """Excel `=`/`<`-family comparison. Returns 0 ok (ord_out -1/0/1), else
    an error code. EMPTY coerces to the other side's zero value."""
    var a = l.copy()
    var b = r.copy()
    if a.kind == VK_ERR:
        return a.err
    if b.kind == VK_ERR:
        return b.err
    if a.kind == VK_EMPTY and b.kind == VK_EMPTY:
        ord_out = 0
        return 0
    if a.kind == VK_EMPTY:
        if b.kind == VK_NUM:
            a = cv_num(0.0)
        elif b.kind == VK_TEXT:
            a = cv_text(String(""))
        elif b.kind == VK_BOOL:
            a = cv_bool(False)
    if b.kind == VK_EMPTY:
        if a.kind == VK_NUM:
            b = cv_num(0.0)
        elif a.kind == VK_TEXT:
            b = cv_text(String(""))
        elif a.kind == VK_BOOL:
            b = cv_bool(False)
    var ra = _type_rank(a)
    var rb = _type_rank(b)
    if ra != rb:
        ord_out = -1 if ra < rb else 1
        return 0
    if a.kind == VK_NUM and b.kind == VK_NUM:
        if a.num < b.num:
            ord_out = -1
        elif a.num > b.num:
            ord_out = 1
        else:
            ord_out = 0
        return 0
    if a.kind == VK_TEXT and b.kind == VK_TEXT:
        ord_out = text_cmp_ci(a.text, b.text)
        return 0
    # bools
    if a.num < b.num:
        ord_out = -1
    elif a.num > b.num:
        ord_out = 1
    else:
        ord_out = 0
    return 0


# ── Aggregation over ranges / arrays / scalars ───────────────────────────────
struct _Agg(Copyable, Movable):
    """Numeric accumulator shared by MIN/MAX/SUM/AVERAGE/STDEV. Collects the
    values so STDEV can run its second pass; count stays exact for AVERAGE."""

    var nums: List[Float64]
    var err: Int
    var taint: CellValue

    fn __init__(out self):
        self.nums = List[Float64]()
        self.err = 0
        self.taint = CellValue()


fn _agg_cell_value(mut agg: _Agg, v: CellValue):
    """RANGE-cell semantics: numbers count, bools/text/blanks are ignored,
    errors and taints propagate."""
    if agg.err != 0:
        return
    if v.kind == VK_NUM:
        agg.nums.append(v.num)
    elif v.kind == VK_ERR:
        agg.err = v.err
    elif v.kind == VK_PENDING or v.kind == VK_UNSUP or v.kind == VK_CYCLE:
        agg.taint = _worse_taint(agg.taint, v)


fn _agg_scalar_value(mut agg: _Agg, v: CellValue):
    """Direct-argument semantics: bools count as 0/1, numeric text counts,
    non-numeric text is #VALUE!."""
    if agg.err != 0:
        return
    if v.kind == VK_PENDING or v.kind == VK_UNSUP or v.kind == VK_CYCLE:
        agg.taint = _worse_taint(agg.taint, v)
        return
    if v.kind == VK_EMPTY:
        agg.nums.append(0.0)
        return
    var x: Float64 = 0.0
    var code = _to_number(v, x)
    if code != 0:
        agg.err = code
        return
    agg.nums.append(x)


fn _agg_range(wb: Workbook, mut st: _EngineState, rng: CellValue, mut agg: _Agg):
    """Walk the STORED cells of a rectangle (blanks contribute nothing to any
    numeric aggregate), charging the walk."""
    var r0 = rng.b
    var c0 = rng.c
    var r1 = rng.d
    var c1 = rng.e
    var narrow = c1 - c0 + 1 <= 4 and r1 - r0 > 4096
    if narrow:
        # tall narrow ranges: per-column walks over the column-major index
        for col in range(c0, c1 + 1):
            var lo = 0
            var hi = 0
            if not wb.col_slice_bounds(
                rng.a, col * MAX_ROWS + r0, col * MAX_ROWS + r1, lo, hi
            ):
                return
            if not st.charge(hi - lo + 1):
                agg.taint = _worse_taint(agg.taint, cv_unsup(String("BUDGET")))
                return
            for p in range(lo, hi):
                var v = _deref_cell(wb, st, wb.perm_col[p])
                _agg_cell_value(agg, v)
                if agg.err != 0 or agg.taint.kind == VK_PENDING:
                    return
        return
    var lo = 0
    var hi = 0
    if not wb.row_slice_bounds(rng.a, r0 * MAX_COLS + c0, r1 * MAX_COLS + c1, lo, hi):
        return
    if not st.charge(hi - lo + 1):
        agg.taint = _worse_taint(agg.taint, cv_unsup(String("BUDGET")))
        return
    for p in range(lo, hi):
        var ci = wb.perm_row[p]
        var col = wb.c_coord[ci] % MAX_COLS
        if col < c0 or col > c1:
            continue
        var v = _deref_cell(wb, st, ci)
        _agg_cell_value(agg, v)
        if agg.err != 0 or agg.taint.kind == VK_PENDING:
            return


fn _agg_value(wb: Workbook, mut st: _EngineState, ctx: _Ctx, v: CellValue, mut agg: _Agg):
    if v.kind == VK_RANGE:
        _agg_range(wb, st, v, agg)
        return
    if v.kind == VK_ARRAY:
        for i in range(v.b * v.c):
            var idx = v.a + i
            if idx >= 0 and idx < len(st.arr_pool):
                _agg_cell_value(agg, st.arr_pool[idx])
        return
    if v.kind == VK_EMPTY:
        return  # an omitted argument contributes nothing
    _agg_scalar_value(agg, v)


# ── Criteria (COUNTIF / COUNTIFS / SUMIF) ────────────────────────────────────
comptime _CEQ: Int = 1
comptime _CNE: Int = 2
comptime _CLT: Int = 3
comptime _CGT: Int = 4
comptime _CLE: Int = 5
comptime _CGE: Int = 6

comptime _CK_NUM: Int = 0
comptime _CK_TEXT: Int = 1
comptime _CK_BOOL: Int = 2
comptime _CK_ERR: Int = 3
comptime _CK_EMPTY: Int = 4


struct _Crit(Copyable, Movable):
    var op: Int
    var kind: Int
    var num: Float64
    var text: String
    var err: Int
    var wild: Bool

    fn __init__(out self):
        self.op = _CEQ
        self.kind = _CK_EMPTY
        self.num = 0.0
        self.text = String("")
        self.err = 0
        self.wild = False


fn _crit_of(v: CellValue) -> _Crit:
    var c = _Crit()
    if v.kind == VK_NUM:
        c.kind = _CK_NUM
        c.num = v.num
        return c^
    if v.kind == VK_BOOL:
        c.kind = _CK_BOOL
        c.num = v.num
        return c^
    if v.kind == VK_ERR:
        c.kind = _CK_ERR
        c.err = v.err
        return c^
    if v.kind == VK_EMPTY:
        # an empty CELL as criterion is numeric 0 (Excel documents this);
        # only the "" TEXT criterion means "match blanks"
        c.kind = _CK_NUM
        c.num = 0.0
        return c^
    # text criterion: optional operator prefix, then value
    var bs = v.text.as_bytes()
    var n = len(bs)
    var i = 0
    if n >= 2 and Int(bs[0]) == 60 and Int(bs[1]) == 62:
        c.op = _CNE
        i = 2
    elif n >= 2 and Int(bs[0]) == 60 and Int(bs[1]) == 61:
        c.op = _CLE
        i = 2
    elif n >= 2 and Int(bs[0]) == 62 and Int(bs[1]) == 61:
        c.op = _CGE
        i = 2
    elif n >= 1 and Int(bs[0]) == 60:
        c.op = _CLT
        i = 1
    elif n >= 1 and Int(bs[0]) == 62:
        c.op = _CGT
        i = 1
    elif n >= 1 and Int(bs[0]) == 61:
        c.op = _CEQ
        i = 1
    var body = String("")
    for j in range(i, n):
        body += chr(Int(bs[j]))
    if len(body) == 0:
        c.kind = _CK_EMPTY
        return c^
    var parsed: Float64 = 0.0
    if _parse_number_trimmed(body, parsed):
        c.kind = _CK_NUM
        c.num = parsed
        return c^
    var f = fold_ascii(body)
    if f == "true":
        c.kind = _CK_BOOL
        c.num = 1.0
        return c^
    if f == "false":
        c.kind = _CK_BOOL
        c.num = 0.0
        return c^
    var ec = _crit_err_code(body)
    if ec != 0:
        c.kind = _CK_ERR
        c.err = ec
        return c^
    c.kind = _CK_TEXT
    c.text = body^
    c.wild = has_wildcard(c.text)
    return c^


fn _crit_err_code(s: String) -> Int:
    return error_code_of(s)


fn _crit_matches_blank(c: _Crit) -> Bool:
    """Does this criterion match a truly-empty cell? `=`/"" do; `<>x` does
    (a blank is not x); bare `<>` means non-blank and does not."""
    if c.kind == _CK_EMPTY:
        return c.op == _CEQ
    return c.op == _CNE


fn _crit_match(c: _Crit, v: CellValue) -> Bool:
    if v.kind == VK_EMPTY:
        return _crit_matches_blank(c)
    if c.kind == _CK_EMPTY:
        # "" matches blank or empty text; "<>" matches non-blank
        if c.op == _CEQ:
            return v.kind == VK_TEXT and len(v.text) == 0
        return not (v.kind == VK_TEXT and len(v.text) == 0)
    if c.kind == _CK_NUM:
        var x: Float64 = 0.0
        if v.kind == VK_NUM:
            x = v.num
        elif v.kind == VK_TEXT:
            var parsed: Float64 = 0.0
            if not _parse_number_trimmed(v.text, parsed):
                return c.op == _CNE
            x = parsed
        else:
            return c.op == _CNE
        return _ord_ok(c.op, _fcmp(x, c.num))
    if c.kind == _CK_TEXT:
        if v.kind != VK_TEXT:
            return c.op == _CNE
        if c.op == _CEQ or c.op == _CNE:
            var hit = wildcard_match(c.text, v.text) if c.wild else text_equal_ci(
                c.text, v.text
            )
            return hit if c.op == _CEQ else not hit
        return _ord_ok(c.op, text_cmp_ci(v.text, c.text))
    if c.kind == _CK_BOOL:
        if v.kind != VK_BOOL:
            return c.op == _CNE
        return _ord_ok(c.op, _fcmp(v.num, c.num))
    # error criterion
    if v.kind != VK_ERR:
        return c.op == _CNE
    if c.op == _CEQ:
        return v.err == c.err
    if c.op == _CNE:
        return v.err != c.err
    return False


fn _fcmp(a: Float64, b: Float64) -> Int:
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


fn _ord_ok(op: Int, ord_v: Int) -> Bool:
    if op == _CEQ:
        return ord_v == 0
    if op == _CNE:
        return ord_v != 0
    if op == _CLT:
        return ord_v < 0
    if op == _CGT:
        return ord_v > 0
    if op == _CLE:
        return ord_v <= 0
    return ord_v >= 0


# ── Excel serial dates (1900 system, leap bug preserved) ─────────────────────
fn _serial_to_ymd(serial: Int, mut y: Int, mut m: Int, mut d: Int) -> Bool:
    """Excel 1900-system serial -> (year, month, day). Serial 60 is the fake
    1900-02-29; 0 is 'January 0, 1900'. False outside [0, 2958465]."""
    if serial < 0 or serial > EXCEL_MAX_SERIAL:
        return False
    if serial == 60:
        y = 1900
        m = 2
        d = 29
        return True
    if serial < 60:
        y = 1900
        if serial <= 31:
            m = 1
            d = serial
        else:
            m = 2
            d = serial - 31
        return True
    # serial > 60: civil algorithm on days since 1970-01-01 (serial 25569)
    var z = serial - 25569
    z += 719468
    var era = z // 146097 if z >= 0 else (z - 146096) // 146097
    var doe = z - era * 146097
    var yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    var yy = yoe + era * 400
    var doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    var mp = (5 * doy + 2) // 153
    var dd = doy - (153 * mp + 2) // 5 + 1
    var mm = mp + 3 if mp < 10 else mp - 9
    y = yy + 1 if mm <= 2 else yy
    m = mm
    d = dd
    return True


# ── Reference resolution (shared-formula deltas applied here) ────────────────
fn _shifted_range_of_node(nd: FNode, ctx: _Ctx) -> CellValue:
    """NK_REF/NK_RANGE -> VK_RANGE with follower deltas applied to RELATIVE
    corners; #REF! when shifted off the grid or the sheet is unknown."""
    var sheet = nd.a
    if sheet == -1:
        sheet = ctx.sheet
    if sheet < 0:
        return cv_err(ERR_REF)
    var r0 = nd.b
    var c0 = nd.c
    var r1 = nd.b
    var c1 = nd.c
    if nd.k == NK_RANGE:
        r1 = nd.d
        c1 = nd.e
    if nd.f & REL_ROW0 != 0:
        r0 += ctx.dr
    if nd.f & REL_COL0 != 0:
        c0 += ctx.dc
    if nd.k == NK_RANGE:
        if nd.f & REL_ROW1 != 0:
            r1 += ctx.dr
        if nd.f & REL_COL1 != 0:
            c1 += ctx.dc
    else:
        r1 = r0
        c1 = c0
    if r0 < 0 or c0 < 0 or r1 >= MAX_ROWS or c1 >= MAX_COLS or r0 > r1 or c0 > c1:
        return cv_err(ERR_REF)
    return cv_range(sheet, r0, c0, r1, c1)


# ── The expression evaluator ─────────────────────────────────────────────────
fn _eval(wb: Workbook, mut st: _EngineState, ctx: _Ctx, ni: Int, depth: Int) -> CellValue:
    if depth > MAX_EVAL_DEPTH:
        return cv_unsup(String("DEEP_EVAL"))
    if ni < 0 or ni >= len(wb.nodes):
        return cv_unsup(String("INTERNAL_NODE"))
    if not st.charge(1):
        return cv_unsup(String("BUDGET"))
    var k = wb.nodes[ni].k
    if k == NK_NUM:
        return cv_num(wb.nodes[ni].num)
    if k == NK_STR:
        return cv_text(wb.nodes[ni].text)
    if k == NK_BOOL:
        return cv_bool(wb.nodes[ni].num != 0.0)
    if k == NK_ERR:
        return cv_err(wb.nodes[ni].a)
    if k == NK_MISSING:
        return cv_empty()
    if k == NK_UNSUP:
        return cv_unsup(wb.nodes[ni].text)
    if k == NK_REF or k == NK_RANGE:
        return _shifted_range_of_node(wb.nodes[ni], ctx)
    if k == NK_NAME:
        var root = wb.resolve_name(wb.nodes[ni].text, ctx.sheet)
        if root < 0:
            return cv_err(ERR_NAME)
        return _eval(wb, st, ctx, root, depth + 1)
    if k == NK_ARRAYLIT:
        var rows = wb.nodes[ni].a
        var cols = wb.nodes[ni].b
        var cnt = wb.nodes[ni].argc
        if rows * cols != cnt or cnt > MAX_ARRAY_ELEMS:
            return cv_err(ERR_VALUE)
        if not st.charge(cnt):
            return cv_unsup(String("BUDGET"))
        var start = len(st.arr_pool)
        for i in range(cnt):
            var child = wb.pool[wb.nodes[ni].arg_start + i]
            st.arr_pool.append(_eval(wb, st, ctx, child, depth + 1))
        var out = CellValue()
        out.kind = VK_ARRAY
        out.a = start
        out.b = rows
        out.c = cols
        return out^
    if k == NK_UN:
        var x = _eval(wb, st, ctx, wb.pool[wb.nodes[ni].arg_start], depth + 1)
        return _apply_unary(wb, st, ctx, wb.nodes[ni].a, x^)
    if k == NK_BIN:
        var l = _eval(wb, st, ctx, wb.pool[wb.nodes[ni].arg_start], depth + 1)
        if l.kind == VK_PENDING:
            return l^
        var r = _eval(wb, st, ctx, wb.pool[wb.nodes[ni].arg_start + 1], depth + 1)
        return _apply_binary(wb, st, ctx, wb.nodes[ni].a, l^, r^)
    if k == NK_FUNC:
        return _call_function(wb, st, ctx, ni, depth)
    return cv_unsup(String("INTERNAL_NODE"))


fn _apply_unary(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, op: Int, var x: CellValue
) -> CellValue:
    if x.kind == VK_RANGE or x.kind == VK_ARRAY:
        # elementwise over an array operand (legacy intersection first)
        if x.kind == VK_RANGE and not ctx.array_mode:
            var s = _to_scalar(wb, st, ctx, x)
            if not (s.kind == VK_ERR and s.err == ERR_VALUE):
                return _apply_unary(wb, st, ctx, op, s^)
        var rows = 0
        var cols = 0
        var arr = x.copy()
        if x.kind == VK_RANGE:
            arr = _materialize(wb, st, x, rows, cols)
            if arr.kind != VK_ARRAY:
                return arr^
        var start = len(st.arr_pool)
        var cnt = arr.b * arr.c
        if not st.charge(cnt):
            return cv_unsup(String("BUDGET"))
        for i in range(cnt):
            var e = st.arr_pool[arr.a + i].copy()
            st.arr_pool.append(_apply_unary_scalar(op, e))
        var out = CellValue()
        out.kind = VK_ARRAY
        out.a = start
        out.b = arr.b
        out.c = arr.c
        return out^
    return _apply_unary_scalar(op, x)


fn _apply_unary_scalar(op: Int, v: CellValue) -> CellValue:
    if _taint_rank(v) > 0:
        return v.copy()
    var x: Float64 = 0.0
    var code = _to_number(v, x)
    if code != 0:
        return cv_err(code)
    if op == OP_NEG:
        return cv_num(-x)
    # OP_PCT
    return cv_num(x / 100.0)


fn _apply_binary(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, op: Int, var l: CellValue, var r: CellValue
) -> CellValue:
    if l.kind == VK_PENDING:
        return l^
    if r.kind == VK_PENDING:
        return r^
    var l_arr = l.kind == VK_RANGE or l.kind == VK_ARRAY
    var r_arr = r.kind == VK_RANGE or r.kind == VK_ARRAY
    if l_arr or r_arr:
        # legacy implicit intersection first (scalar context only)
        if not ctx.array_mode:
            var ls = l.copy()
            var rs = r.copy()
            var ok = True
            if l.kind == VK_RANGE:
                ls = _to_scalar(wb, st, ctx, l)
                if ls.kind == VK_ERR and ls.err == ERR_VALUE:
                    ok = False
            if ok and r.kind == VK_RANGE:
                rs = _to_scalar(wb, st, ctx, r)
                if rs.kind == VK_ERR and rs.err == ERR_VALUE:
                    ok = False
            if ok and not (ls.kind == VK_ARRAY or rs.kind == VK_ARRAY):
                return _apply_binary_scalar(op, ls, rs)
        # broadcast elementwise
        var rows_l = 1
        var cols_l = 1
        var la = l.copy()
        if l.kind == VK_RANGE:
            la = _materialize(wb, st, l, rows_l, cols_l)
            if la.kind != VK_ARRAY:
                return la^
        var rows_r = 1
        var cols_r = 1
        var ra = r.copy()
        if r.kind == VK_RANGE:
            ra = _materialize(wb, st, r, rows_r, cols_r)
            if ra.kind != VK_ARRAY:
                return ra^
        var out_rows = 1
        var out_cols = 1
        if la.kind == VK_ARRAY:
            out_rows = max(out_rows, la.b)
            out_cols = max(out_cols, la.c)
        if ra.kind == VK_ARRAY:
            out_rows = max(out_rows, ra.b)
            out_cols = max(out_cols, ra.c)
        if out_rows * out_cols > MAX_ARRAY_ELEMS:
            return cv_unsup(String("ARRAY_TOO_LARGE"))
        if not st.charge(out_rows * out_cols):
            return cv_unsup(String("BUDGET"))
        var start = len(st.arr_pool)
        for i in range(out_rows * out_cols):
            var rr = i // out_cols
            var cc = i % out_cols
            var le = la.copy() if la.kind != VK_ARRAY else _array_elem(st, la, rr, cc)
            var re = ra.copy() if ra.kind != VK_ARRAY else _array_elem(st, ra, rr, cc)
            st.arr_pool.append(_apply_binary_scalar(op, le, re))
        var out = CellValue()
        out.kind = VK_ARRAY
        out.a = start
        out.b = out_rows
        out.c = out_cols
        return out^
    return _apply_binary_scalar(op, l, r)


fn _apply_binary_scalar(op: Int, l: CellValue, r: CellValue) -> CellValue:
    if _taint_rank(l) > 0 or _taint_rank(r) > 0:
        return _worse_taint(l, r)
    if op == OP_CAT:
        if l.kind == VK_ERR:
            return cv_err(l.err)
        if r.kind == VK_ERR:
            return cv_err(r.err)
        var out = _to_text(l)
        out += _to_text(r)
        return cv_text(out^)
    if op >= OP_EQ and op <= OP_GE:
        var ord_v = 0
        var code = _compare_scalars(l, r, ord_v)
        if code != 0:
            return cv_err(code)
        if op == OP_EQ:
            return cv_bool(ord_v == 0)
        if op == OP_NE:
            return cv_bool(ord_v != 0)
        if op == OP_LT:
            return cv_bool(ord_v < 0)
        if op == OP_GT:
            return cv_bool(ord_v > 0)
        if op == OP_LE:
            return cv_bool(ord_v <= 0)
        return cv_bool(ord_v >= 0)
    var a: Float64 = 0.0
    var code_a = _to_number(l, a)
    if code_a != 0:
        return cv_err(code_a)
    var b: Float64 = 0.0
    var code_b = _to_number(r, b)
    if code_b != 0:
        return cv_err(code_b)
    var out: Float64 = 0.0
    if op == OP_ADD:
        out = a + b
    elif op == OP_SUB:
        out = a - b
    elif op == OP_MUL:
        out = a * b
    elif op == OP_DIV:
        if b == 0.0:
            return cv_err(ERR_DIV0)
        out = a / b
    elif op == OP_POW:
        if a == 0.0 and b == 0.0:
            return cv_err(ERR_NUM)
        out = pow(a, b)
    else:
        return cv_err(ERR_VALUE)
    if out != out:  # nan (e.g. (-8)^0.5)
        return cv_err(ERR_NUM)
    if out > 1.7976931348623157e308 or out < -1.7976931348623157e308:
        return cv_err(ERR_NUM)
    return cv_num(out)


# ── Function dispatch ────────────────────────────────────────────────────────
fn _call_function(wb: Workbook, mut st: _EngineState, ctx: _Ctx, ni: Int, depth: Int) -> CellValue:
    var fid = wb.nodes[ni].b
    var argc = wb.nodes[ni].argc
    var arg0 = wb.nodes[ni].arg_start
    if fid == FID_UNKNOWN or fid == FID_VOLATILE:
        return cv_unsup(wb.nodes[ni].text)
    # special forms: lazy evaluation is semantics, not an optimisation —
    # IF(TRUE, 1, 1/0) is 1, never #DIV/0!
    if fid == FID_IF:
        if argc < 2 or argc > 3:
            return cv_err(ERR_VALUE)
        var cond = _eval(wb, st, ctx, wb.pool[arg0], depth + 1)
        if cond.kind == VK_RANGE and not ctx.array_mode:
            var s = _to_scalar(wb, st, ctx, cond)
            if not (s.kind == VK_ERR and s.err == ERR_VALUE):
                cond = s^
        if cond.kind == VK_RANGE or cond.kind == VK_ARRAY:
            return _if_array(wb, st, ctx, ni, cond^, depth)
        if _taint_rank(cond) > 0:
            return cond^
        if cond.kind == VK_ERR:
            return cond^
        var b = False
        var code = _to_bool(cond, b)
        if code != 0:
            return cv_err(code)
        if b:
            var t = _eval(wb, st, ctx, wb.pool[arg0 + 1], depth + 1)
            if t.kind == VK_EMPTY and wb.nodes[wb.pool[arg0 + 1]].k == NK_MISSING:
                return cv_num(0.0)
            return t^
        if argc == 3:
            var e = _eval(wb, st, ctx, wb.pool[arg0 + 2], depth + 1)
            if e.kind == VK_EMPTY and wb.nodes[wb.pool[arg0 + 2]].k == NK_MISSING:
                return cv_num(0.0)
            return e^
        return cv_bool(False)
    if fid == FID_IFERROR:
        if argc != 2:
            return cv_err(ERR_VALUE)
        var v = _eval(wb, st, ctx, wb.pool[arg0], depth + 1)
        if _taint_rank(v) > 0:
            return v^
        # array-aware: IFERROR(--$B$7:C$7, 0) inside SUM must map elementwise
        # (measured live on spreadsheetbench_912 answer files)
        if v.kind == VK_ARRAY or (v.kind == VK_RANGE and (v.b != v.d or v.c != v.e)):
            var rows = 1
            var cols = 1
            var va = v.copy()
            if v.kind == VK_RANGE:
                va = _materialize(wb, st, v, rows, cols)
                if va.kind != VK_ARRAY:
                    return va^
            var fb = _eval(wb, st, ctx, wb.pool[arg0 + 1], depth + 1)
            if fb.kind == VK_PENDING:
                return fb^
            var rf = 1
            var cf = 1
            if fb.kind == VK_RANGE:
                fb = _materialize(wb, st, fb, rf, cf)
                if fb.kind != VK_ARRAY and _taint_rank(fb) > 0:
                    return fb^
            var cnt = va.b * va.c
            if not st.charge(cnt):
                return cv_unsup(String("BUDGET"))
            var start = len(st.arr_pool)
            for i in range(cnt):
                var e = _array_elem(st, va, i // va.c, i % va.c)
                if _taint_rank(e) > 0:
                    st.arr_pool.append(e^)
                elif e.kind == VK_ERR:
                    st.arr_pool.append(
                        fb.copy() if fb.kind != VK_ARRAY else _array_elem(st, fb, i // va.c, i % va.c)
                    )
                else:
                    st.arr_pool.append(e^)
            var outv = CellValue()
            outv.kind = VK_ARRAY
            outv.a = start
            outv.b = va.b
            outv.c = va.c
            return outv^
        var vs = _to_scalar(wb, st, ctx, v)
        if _taint_rank(vs) > 0:
            return vs^
        if vs.kind == VK_ERR:
            var fb = _eval(wb, st, ctx, wb.pool[arg0 + 1], depth + 1)
            if fb.kind == VK_EMPTY and wb.nodes[wb.pool[arg0 + 1]].k == NK_MISSING:
                return cv_text(String(""))
            return fb^
        return vs^
    if fid == FID_CHOOSE:
        if argc < 2:
            return cv_err(ERR_VALUE)
        var kv = _eval(wb, st, ctx, wb.pool[arg0], depth + 1)
        if _taint_rank(kv) > 0:
            return kv^
        var ks = _to_scalar(wb, st, ctx, kv)
        if _taint_rank(ks) > 0:
            return ks^
        var kf: Float64 = 0.0
        var kcode = _to_number(ks, kf)
        if kcode != 0:
            return cv_err(kcode)
        var kidx = 0
        if not _trunc_int(kf, kidx) or kidx < 1 or kidx > argc - 1:
            return cv_err(ERR_VALUE)
        # only the chosen value is evaluated: CHOOSE(1, 5, 1/0) is 5
        return _eval(wb, st, ctx, wb.pool[arg0 + kidx], depth + 1)
    # eager functions: evaluate every argument (ranges stay ranges).
    # SUMPRODUCT defines an ARRAY context for its arguments — that is the
    # function's whole meaning — so its operands never implicit-intersect.
    var actx = ctx.copy()
    if fid == FID_SUMPRODUCT:
        actx.array_mode = True
    var args = List[CellValue]()
    for i in range(argc):
        var v = _eval(wb, st, actx, wb.pool[arg0 + i], depth + 1)
        if v.kind == VK_PENDING:
            return v^
        args.append(v^)
    # array lifting: a scalar-slot argument that is an array (or a range no
    # implicit intersection can resolve) broadcasts the WHOLE call
    # elementwise — modern/CSE semantics, measured on 912 (LEN over a column
    # inside SUMPRODUCT; a range criterion under 1/COUNTIFS)
    var lifted = _maybe_lift(wb, st, actx, fid, args)
    if lifted.kind != VK_EMPTY:
        return lifted^
    return _dispatch_eager(wb, st, actx, fid, args)


fn _dispatch_eager(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    if fid == FID_SUM or fid == FID_MIN or fid == FID_MAX or fid == FID_AVERAGE or fid == FID_STDEV:
        return _fn_numeric_agg(wb, st, ctx, fid, args)
    if fid == FID_ROW:
        return _fn_row(wb, st, ctx, args)
    if fid == FID_OFFSET:
        return _fn_offset(wb, st, ctx, args)
    if fid == FID_VLOOKUP:
        return _fn_vlookup(wb, st, ctx, args)
    if fid == FID_COUNTIFS:
        return _fn_countifs(wb, st, ctx, args)
    if fid == FID_TIME:
        return _fn_time(wb, st, ctx, args)
    if fid == FID_INDIRECT:
        return _fn_indirect(wb, st, ctx, args)
    if fid == FID_AND:
        return _fn_and(wb, st, ctx, args)
    if fid == FID_TEXTAFTER:
        return _fn_textafter(wb, st, ctx, args)
    if fid == FID_ABS:
        return _fn_abs(wb, st, ctx, args)
    if fid == FID_YEAR or fid == FID_MONTH:
        return _fn_year_month(wb, st, ctx, fid, args)
    if fid == FID_COUNTIF:
        return _fn_countif(wb, st, ctx, args)
    if fid == FID_INDEX:
        return _fn_index(wb, st, ctx, args)
    if fid == FID_MATCH:
        return _fn_match(wb, st, ctx, args)
    if fid == FID_SUMIF:
        return _fn_sumif(wb, st, ctx, args)
    if fid == FID_RANK:
        return _fn_rank(wb, st, ctx, args)
    if fid == FID_COLUMN:
        return _fn_column(wb, st, ctx, args)
    if fid == FID_WEEKDAY:
        return _fn_weekday(wb, st, ctx, args)
    if fid == FID_INT or fid == FID_VALUE or fid == FID_SLN or fid == FID_DAYS:
        return _fn_simple_numeric(wb, st, ctx, fid, args)
    if fid == FID_LEFT or fid == FID_RIGHT or fid == FID_LEN:
        return _fn_text_slice(wb, st, ctx, fid, args)
    if fid == FID_EDATE or fid == FID_EOMONTH:
        return _fn_edate_eomonth(wb, st, ctx, fid, args)
    if fid == FID_SUBSTITUTE:
        return _fn_substitute(wb, st, ctx, args)
    if fid == FID_ROUNDUP or fid == FID_ROUNDDOWN:
        return _fn_round_directed(wb, st, ctx, fid, args)
    if fid == FID_SUMPRODUCT:
        return _fn_sumproduct(wb, st, ctx, args)
    if fid == FID_SUMIFS:
        return _fn_sumifs(wb, st, ctx, args)
    if fid == FID_LOOKUP:
        return _fn_lookup(wb, st, ctx, args)
    if fid == FID_LARGE:
        return _fn_large(wb, st, ctx, args)
    if fid == FID_OR:
        return _fn_or(wb, st, ctx, args)
    if fid == FID_ROWS:
        return _fn_rows(wb, st, ctx, args)
    if fid == FID_ISNUMBER or fid == FID_ISBLANK:
        return _fn_is_kind(wb, st, ctx, fid, args)
    if fid == FID_DATE:
        return _fn_date(wb, st, ctx, args)
    return cv_unsup(String("INTERNAL_FID"))


fn _if_array(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, ni: Int, var cond: CellValue, depth: Int
) -> CellValue:
    """Array-context IF: elementwise condition, both branches evaluated once,
    element selection per position (an error in an unselected element does
    not leak)."""
    var argc = wb.nodes[ni].argc
    var arg0 = wb.nodes[ni].arg_start
    var rows = 1
    var cols = 1
    var ca = cond.copy()
    if cond.kind == VK_RANGE:
        ca = _materialize(wb, st, cond, rows, cols)
        if ca.kind != VK_ARRAY:
            return ca^
    var t = _eval(wb, st, ctx, wb.pool[arg0 + 1], depth + 1)
    if t.kind == VK_PENDING:
        return t^
    var e = cv_bool(False)
    if argc == 3:
        e = _eval(wb, st, ctx, wb.pool[arg0 + 2], depth + 1)
        if e.kind == VK_PENDING:
            return e^
    var rt = 1
    var ct2 = 1
    if t.kind == VK_RANGE:
        t = _materialize(wb, st, t, rt, ct2)
        if t.kind != VK_ARRAY and _taint_rank(t) > 0:
            return t^
    var re2 = 1
    var ce2 = 1
    if e.kind == VK_RANGE:
        e = _materialize(wb, st, e, re2, ce2)
        if e.kind != VK_ARRAY and _taint_rank(e) > 0:
            return e^
    # output dims broadcast across ALL three parts: AVERAGE(IF(A2:A19=x,
    # B2:E19)) has an 18x1 condition and an 18x4 value array (measured on 912)
    var out_rows = ca.b
    var out_cols = ca.c
    if t.kind == VK_ARRAY:
        out_rows = max(out_rows, t.b)
        out_cols = max(out_cols, t.c)
    if e.kind == VK_ARRAY:
        out_rows = max(out_rows, e.b)
        out_cols = max(out_cols, e.c)
    if out_rows * out_cols > MAX_ARRAY_ELEMS:
        return cv_unsup(String("ARRAY_TOO_LARGE"))
    if not st.charge(out_rows * out_cols):
        return cv_unsup(String("BUDGET"))
    var start = len(st.arr_pool)
    for i in range(out_rows * out_cols):
        var rr = i // out_cols
        var cc = i % out_cols
        var cel = _array_elem(st, ca, rr, cc)
        if _taint_rank(cel) > 0 or cel.kind == VK_ERR:
            st.arr_pool.append(cel^)
            continue
        var b = False
        var code = _to_bool(cel, b)
        if code != 0:
            st.arr_pool.append(cv_err(code))
            continue
        if b:
            st.arr_pool.append(t.copy() if t.kind != VK_ARRAY else _array_elem(st, t, rr, cc))
        elif argc == 3:
            st.arr_pool.append(e.copy() if e.kind != VK_ARRAY else _array_elem(st, e, rr, cc))
        else:
            st.arr_pool.append(cv_bool(False))
    var out = CellValue()
    out.kind = VK_ARRAY
    out.a = start
    out.b = out_rows
    out.c = out_cols
    return out^


# ── Individual functions ─────────────────────────────────────────────────────
fn _fn_numeric_agg(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    var agg = _Agg()
    for i in range(len(args)):
        _agg_value(wb, st, ctx, args[i], agg)
        if agg.err != 0:
            return cv_err(agg.err)
        if agg.taint.kind == VK_PENDING:
            return agg.taint.copy()
    if _taint_rank(agg.taint) > 0:
        return agg.taint.copy()
    var n = len(agg.nums)
    if fid == FID_SUM:
        var s: Float64 = 0.0
        for i in range(n):
            s += agg.nums[i]
        return cv_num(s)
    if fid == FID_MIN or fid == FID_MAX:
        if n == 0:
            return cv_num(0.0)
        var best = agg.nums[0]
        for i in range(1, n):
            var x = agg.nums[i]
            if fid == FID_MIN:
                if x < best:
                    best = x
            elif x > best:
                best = x
        return cv_num(best)
    if fid == FID_AVERAGE:
        if n == 0:
            return cv_err(ERR_DIV0)
        var s: Float64 = 0.0
        for i in range(n):
            s += agg.nums[i]
        return cv_num(s / Float64(n))
    # STDEV (sample): two-pass for stability
    if n < 2:
        return cv_err(ERR_DIV0)
    var s: Float64 = 0.0
    for i in range(n):
        s += agg.nums[i]
    var mean = s / Float64(n)
    var ss: Float64 = 0.0
    for i in range(n):
        var d = agg.nums[i] - mean
        ss += d * d
    return cv_num(sqrt(ss / Float64(n - 1)))


fn _fn_row(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) == 0:
        return cv_num(Float64(ctx.row + 1))
    if len(args) != 1:
        return cv_err(ERR_VALUE)
    var a = args[0].copy()
    if _taint_rank(a) > 0:
        return a^
    if a.kind == VK_EMPTY:
        return cv_num(Float64(ctx.row + 1))
    if a.kind != VK_RANGE:
        if a.kind == VK_ERR:
            return a^
        return cv_err(ERR_VALUE)
    if ctx.array_mode and a.d > a.b:
        # column vector of row numbers
        var rows = a.d - a.b + 1
        if rows > MAX_ARRAY_ELEMS or not st.charge(rows):
            return cv_unsup(String("ARRAY_TOO_LARGE"))
        var start = len(st.arr_pool)
        for r in range(a.b, a.d + 1):
            st.arr_pool.append(cv_num(Float64(r + 1)))
        var out = CellValue()
        out.kind = VK_ARRAY
        out.a = start
        out.b = rows
        out.c = 1
        return out^
    return cv_num(Float64(a.b + 1))


fn _trunc_int(x: Float64, mut out_i: Int) -> Bool:
    """Truncate toward zero; refuses past the exact-integer grid (rule 4c:
    Float64(Int(v)) outside range is poison, not truncation)."""
    if x != x or x >= 2147483648.0 or x <= -2147483648.0:
        return False
    out_i = Int(x)
    return True


fn _fn_offset(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 3 or len(args) > 5:
        return cv_err(ERR_VALUE)
    var base = args[0].copy()
    if _taint_rank(base) > 0:
        return base^
    if base.kind == VK_ERR:
        return base^
    if base.kind != VK_RANGE:
        return cv_err(ERR_VALUE)
    var dr_v = _to_scalar(wb, st, ctx, args[1])
    var dc_v = _to_scalar(wb, st, ctx, args[2])
    if _taint_rank(dr_v) > 0:
        return dr_v^
    if _taint_rank(dc_v) > 0:
        return dc_v^
    var drf: Float64 = 0.0
    var code = _to_number(dr_v, drf)
    if code != 0:
        return cv_err(code)
    var dcf: Float64 = 0.0
    code = _to_number(dc_v, dcf)
    if code != 0:
        return cv_err(code)
    var dr = 0
    var dc = 0
    if not _trunc_int(drf, dr) or not _trunc_int(dcf, dc):
        return cv_err(ERR_REF)
    var height = base.d - base.b + 1
    var width = base.e - base.c + 1
    if len(args) >= 4 and args[3].kind != VK_EMPTY:
        var hv = _to_scalar(wb, st, ctx, args[3])
        if _taint_rank(hv) > 0:
            return hv^
        var hf: Float64 = 0.0
        code = _to_number(hv, hf)
        if code != 0:
            return cv_err(code)
        if not _trunc_int(hf, height):
            return cv_err(ERR_REF)
    if len(args) == 5 and args[4].kind != VK_EMPTY:
        var wv = _to_scalar(wb, st, ctx, args[4])
        if _taint_rank(wv) > 0:
            return wv^
        var wf: Float64 = 0.0
        code = _to_number(wv, wf)
        if code != 0:
            return cv_err(code)
        if not _trunc_int(wf, width):
            return cv_err(ERR_REF)
    if height == 0 or width == 0:
        return cv_err(ERR_REF)
    var r0 = base.b + dr
    var c0 = base.c + dc
    var r1 = r0 + height - 1
    var c1 = c0 + width - 1
    # negative height/width extend UPWARD/LEFTWARD from the anchor (measured
    # live on finch: OFFSET(D14,0,0,MAX(...,-$B$9),1) with a negative MAX)
    if height < 0:
        r1 = r0
        r0 = r0 + height + 1
    if width < 0:
        c1 = c0
        c0 = c0 + width + 1
    if r0 < 0 or c0 < 0 or r1 >= MAX_ROWS or c1 >= MAX_COLS:
        return cv_err(ERR_REF)
    return cv_range(base.a, r0, c0, r1, c1)


fn _fn_indirect(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 1 or len(args) > 2:
        return cv_err(ERR_VALUE)
    if len(args) == 2 and args[1].kind != VK_EMPTY:
        var a1v = _to_scalar(wb, st, ctx, args[1])
        if _taint_rank(a1v) > 0:
            return a1v^
        var b = False
        var code = _to_bool(a1v, b)
        if code != 0:
            return cv_err(code)
        if not b:
            return cv_unsup(String("INDIRECT_R1C1"))
    var tv = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(tv) > 0:
        return tv^
    if tv.kind == VK_ERR:
        return tv^
    if tv.kind != VK_TEXT:
        return cv_err(ERR_REF)
    var rp = parse_ref_text(tv.text)
    if not rp.ok:
        return cv_err(ERR_REF)
    var sheet = ctx.sheet
    if rp.has_sheet:
        sheet = -1
        var folded = fold_ascii(rp.sheet_name)
        for i in range(len(wb.sheet_names)):
            if fold_ascii(wb.sheet_names[i]) == folded:
                sheet = i
                break
        if sheet < 0:
            return cv_err(ERR_REF)
    return cv_range(sheet, rp.r0, rp.c0, rp.r1, rp.c1)


fn _fn_and(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    var seen = False
    var all_true = True
    for i in range(len(args)):
        var a = args[i].copy()
        if _taint_rank(a) > 0:
            return a^
        if a.kind == VK_ERR:
            return a^
        if a.kind == VK_EMPTY:
            continue
        if a.kind == VK_RANGE or a.kind == VK_ARRAY:
            var agg_err = 0
            var found = False
            var truth = True
            var taint = CellValue()
            _and_over_array_or_range(wb, st, a, found, truth, agg_err, taint)
            if _taint_rank(taint) > 0:
                return taint^
            if agg_err != 0:
                return cv_err(agg_err)
            if found:
                seen = True
                all_true = all_true and truth
            continue
        var b = False
        var code = _to_bool(a, b)
        if code != 0:
            return cv_err(code)
        seen = True
        all_true = all_true and b
    if not seen:
        return cv_err(ERR_VALUE)
    return cv_bool(all_true)


fn _and_over_array_or_range(
    wb: Workbook,
    mut st: _EngineState,
    v: CellValue,
    mut found: Bool,
    mut truth: Bool,
    mut err: Int,
    mut taint: CellValue,
):
    """AND over a reference/array: logicals and numbers participate, text and
    blanks are skipped, errors propagate."""
    if v.kind == VK_ARRAY:
        for i in range(v.b * v.c):
            var idx = v.a + i
            if idx < 0 or idx >= len(st.arr_pool):
                continue
            var e = st.arr_pool[idx].copy()
            if _taint_rank(e) > 0:
                taint = _worse_taint(taint, e)
                return
            if e.kind == VK_ERR:
                err = e.err
                return
            if e.kind == VK_NUM or e.kind == VK_BOOL:
                found = True
                truth = truth and e.num != 0.0
        return
    var lo = 0
    var hi = 0
    if not wb.row_slice_bounds(
        v.a, v.b * MAX_COLS + v.c, v.d * MAX_COLS + v.e, lo, hi
    ):
        return
    if not st.charge(hi - lo + 1):
        taint = _worse_taint(taint, cv_unsup(String("BUDGET")))
        return
    for p in range(lo, hi):
        var ci = wb.perm_row[p]
        var col = wb.c_coord[ci] % MAX_COLS
        if col < v.c or col > v.e:
            continue
        var e = _deref_cell(wb, st, ci)
        if _taint_rank(e) > 0:
            taint = _worse_taint(taint, e)
            return
        if e.kind == VK_ERR:
            err = e.err
            return
        if e.kind == VK_NUM or e.kind == VK_BOOL:
            found = True
            truth = truth and e.num != 0.0


fn _fn_time(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) != 3:
        return cv_err(ERR_VALUE)
    var parts = List[Int]()
    for i in range(3):
        var v = _to_scalar(wb, st, ctx, args[i])
        if _taint_rank(v) > 0:
            return v^
        var x: Float64 = 0.0
        var code = _to_number(v, x)
        if code != 0:
            return cv_err(code)
        var t = 0
        if not _trunc_int(x, t):
            return cv_err(ERR_NUM)
        if t < 0 or t > 32767:
            return cv_err(ERR_NUM)
        parts.append(t)
    var total = parts[0] * 3600 + parts[1] * 60 + parts[2]
    total = total % 86400
    return cv_num(Float64(total) / 86400.0)


fn _fn_abs(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) != 1:
        return cv_err(ERR_VALUE)
    var v = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(v) > 0:
        return v^
    var x: Float64 = 0.0
    var code = _to_number(v, x)
    if code != 0:
        return cv_err(code)
    return cv_num(fabs(x))


fn _fn_year_month(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    if len(args) != 1:
        return cv_err(ERR_VALUE)
    var v = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(v) > 0:
        return v^
    var x: Float64 = 0.0
    var code = _to_number(v, x)
    if code != 0:
        if v.kind == VK_TEXT:
            # Excel parses date TEXT ("July1", "2021-07-01") here; this build
            # does not — a named taint, never a wrong #VALUE! (measured: 912
            # MONTH(D2&1) over month names)
            return cv_unsup(String("DATE_TEXT_COERCION"))
        return cv_err(code)
    if x < 0.0 or x > Float64(EXCEL_MAX_SERIAL) + 1.0:
        return cv_err(ERR_NUM)
    var serial = Int(floor(x))
    var y = 0
    var m = 0
    var d = 0
    if not _serial_to_ymd(serial, y, m, d):
        return cv_err(ERR_NUM)
    if fid == FID_YEAR:
        return cv_num(Float64(y))
    return cv_num(Float64(m))


fn _fn_textafter(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 2 or len(args) > 6:
        return cv_err(ERR_VALUE)
    var tv = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(tv) > 0:
        return tv^
    if tv.kind == VK_ERR:
        return cv_err(tv.err)
    var dv = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(dv) > 0:
        return dv^
    if dv.kind == VK_ERR:
        return cv_err(dv.err)
    var text = _to_text(tv)
    var delim = _to_text(dv)
    var instance = 1
    if len(args) >= 3 and args[2].kind != VK_EMPTY:
        var iv = _to_scalar(wb, st, ctx, args[2])
        if _taint_rank(iv) > 0:
            return iv^
        var xf: Float64 = 0.0
        var code = _to_number(iv, xf)
        if code != 0:
            return cv_err(code)
        if not _trunc_int(xf, instance) or instance == 0:
            return cv_err(ERR_VALUE)
    var match_ci = False
    if len(args) >= 4 and args[3].kind != VK_EMPTY:
        var mv = _to_scalar(wb, st, ctx, args[3])
        if _taint_rank(mv) > 0:
            return mv^
        var b = False
        var code = _to_bool(mv, b)
        if code != 0:
            return cv_err(code)
        match_ci = b
    var match_end = False
    if len(args) >= 5 and args[4].kind != VK_EMPTY:
        var ev = _to_scalar(wb, st, ctx, args[4])
        if _taint_rank(ev) > 0:
            return ev^
        var b = False
        var code = _to_bool(ev, b)
        if code != 0:
            return cv_err(code)
        match_end = b
    var hay = fold_ascii(text) if match_ci else text
    var needle = fold_ascii(delim) if match_ci else delim
    var hb = hay.as_bytes()
    var nb = needle.as_bytes()
    var nh = len(hb)
    var nn = len(nb)
    if nn == 0:
        # empty delimiter matches at the very start (instance 1) / end (-1)
        if instance == 1:
            return cv_text(text)
        if instance == -1:
            return cv_text(String(""))
        return cv_err(ERR_VALUE)
    # collect match positions
    var positions = List[Int]()
    var i = 0
    while i + nn <= nh:
        var hit = True
        for j in range(nn):
            if hb[i + j] != nb[j]:
                hit = False
                break
        if hit:
            positions.append(i)
            i += 1
        else:
            i += 1
    if match_end:
        positions.append(nh)
    var count = len(positions)
    var pick = instance - 1 if instance > 0 else count + instance
    if pick < 0 or pick >= count:
        if len(args) == 6 and args[5].kind != VK_EMPTY:
            return _to_scalar(wb, st, ctx, args[5])
        return cv_err(ERR_NA)
    var after = positions[pick] + nn
    if positions[pick] == nh:  # matched the appended end
        after = nh
    # slice ORIGINAL text (case preserved) from `after`
    var ob = text.as_bytes()
    var obuf = List[UInt8]()
    for k2 in range(after, len(ob)):
        obuf.append(ob[k2])
    return cv_text(_bs_str(obuf))


fn _range_dims_equal(a: CellValue, b: CellValue) -> Bool:
    return a.d - a.b == b.d - b.b and a.e - a.c == b.e - b.c


fn _fn_countif(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) != 2:
        return cv_err(ERR_VALUE)
    var rng = args[0].copy()
    if rng.kind != VK_RANGE:
        if _taint_rank(rng) > 0:
            return rng^
        if rng.kind == VK_ERR:
            return rng^
        return cv_err(ERR_VALUE)
    var cs = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(cs) > 0:
        return cs^
    if cs.kind == VK_ERR:
        return cs^
    var crit = _crit_of(cs)
    var stored = 0
    var matched = 0
    var taint = CellValue()
    _countif_walk(wb, st, rng, crit, stored, matched, taint)
    if _taint_rank(taint) > 0:
        return taint^
    var total = matched
    if _crit_matches_blank(crit):
        var rect = (rng.d - rng.b + 1) * (rng.e - rng.c + 1)
        total += rect - stored
    return cv_num(Float64(total))


fn _countif_walk(
    wb: Workbook,
    mut st: _EngineState,
    rng: CellValue,
    crit: _Crit,
    mut stored: Int,
    mut matched: Int,
    mut taint: CellValue,
):
    var narrow = rng.e - rng.c + 1 <= 4 and rng.d - rng.b > 4096
    if narrow:
        for col in range(rng.c, rng.e + 1):
            var lo = 0
            var hi = 0
            if not wb.col_slice_bounds(
                rng.a, col * MAX_ROWS + rng.b, col * MAX_ROWS + rng.d, lo, hi
            ):
                return
            if not st.charge(hi - lo + 1):
                taint = _worse_taint(taint, cv_unsup(String("BUDGET")))
                return
            for p in range(lo, hi):
                var v = _deref_cell(wb, st, wb.perm_col[p])
                if _taint_rank(v) > 0:
                    taint = _worse_taint(taint, v)
                    return
                stored += 1
                if _crit_match(crit, v):
                    matched += 1
        return
    var lo = 0
    var hi = 0
    if not wb.row_slice_bounds(
        rng.a, rng.b * MAX_COLS + rng.c, rng.d * MAX_COLS + rng.e, lo, hi
    ):
        return
    if not st.charge(hi - lo + 1):
        taint = _worse_taint(taint, cv_unsup(String("BUDGET")))
        return
    for p in range(lo, hi):
        var ci = wb.perm_row[p]
        var col = wb.c_coord[ci] % MAX_COLS
        if col < rng.c or col > rng.e:
            continue
        var v = _deref_cell(wb, st, ci)
        if _taint_rank(v) > 0:
            taint = _worse_taint(taint, v)
            return
        stored += 1
        if _crit_match(crit, v):
            matched += 1


fn _fn_countifs(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    var n = len(args)
    if n < 2 or n % 2 != 0:
        return cv_err(ERR_VALUE)
    var pairs = n // 2
    var rngs = List[CellValue]()
    var crits = List[_Crit]()
    var blankish = List[Bool]()
    for i in range(pairs):
        var r = args[2 * i].copy()
        if r.kind != VK_RANGE:
            if _taint_rank(r) > 0:
                return r^
            return cv_err(ERR_VALUE)
        var cs = _to_scalar(wb, st, ctx, args[2 * i + 1])
        if _taint_rank(cs) > 0:
            return cs^
        if cs.kind == VK_ERR:
            return cs^
        var c = _crit_of(cs)
        blankish.append(_crit_matches_blank(c))
        rngs.append(r^)
        crits.append(c^)
    for i in range(1, pairs):
        if not _range_dims_equal(rngs[0], rngs[i]):
            return cv_err(ERR_VALUE)
    # drive from a criteria range whose criterion cannot match blanks
    var drive = -1
    for i in range(pairs):
        if not blankish[i]:
            drive = i
            break
    var count = 0
    if drive >= 0:
        var d = rngs[drive].copy()
        var lo = 0
        var hi = 0
        if not wb.row_slice_bounds(d.a, d.b * MAX_COLS + d.c, d.d * MAX_COLS + d.e, lo, hi):
            return cv_num(0.0)
        if not st.charge((hi - lo + 1) * pairs):
            return cv_unsup(String("BUDGET"))
        for p in range(lo, hi):
            var ci = wb.perm_row[p]
            var col = wb.c_coord[ci] % MAX_COLS
            if col < d.c or col > d.e:
                continue
            var rr = wb.c_coord[ci] // MAX_COLS - d.b
            var cc = col - d.c
            var all_ok = True
            for q in range(pairs):
                var v = CellValue()
                if q == drive:
                    v = _deref_cell(wb, st, ci)
                else:
                    var target = wb.find_cell(rngs[q].a, rngs[q].b + rr, rngs[q].c + cc)
                    if target >= 0:
                        v = _deref_cell(wb, st, target)
                if _taint_rank(v) > 0:
                    return _worse_taint(v, CellValue())
                if not _crit_match(crits[q], v):
                    all_ok = False
                    break
            if all_ok:
                count += 1
        return cv_num(Float64(count))
    # every criterion matches blanks: iterate the full rectangle, charged
    var d = rngs[0].copy()
    var rect_rows = d.d - d.b + 1
    var rect_cols = d.e - d.c + 1
    if not st.charge(rect_rows * rect_cols * pairs):
        return cv_unsup(String("BUDGET"))
    for rr in range(rect_rows):
        for cc in range(rect_cols):
            var all_ok = True
            for q in range(pairs):
                var v = CellValue()
                var target = wb.find_cell(rngs[q].a, rngs[q].b + rr, rngs[q].c + cc)
                if target >= 0:
                    v = _deref_cell(wb, st, target)
                if _taint_rank(v) > 0:
                    return _worse_taint(v, CellValue())
                if not _crit_match(crits[q], v):
                    all_ok = False
                    break
            if all_ok:
                count += 1
    return cv_num(Float64(count))


fn _fn_sumif(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 2 or len(args) > 3:
        return cv_err(ERR_VALUE)
    var rng = args[0].copy()
    if rng.kind != VK_RANGE:
        if _taint_rank(rng) > 0:
            return rng^
        return cv_err(ERR_VALUE)
    var cs = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(cs) > 0:
        return cs^
    if cs.kind == VK_ERR:
        return cs^
    var crit = _crit_of(cs)
    var sum_rng = rng.copy()
    if len(args) == 3 and args[2].kind != VK_EMPTY:
        var s = args[2].copy()
        if s.kind != VK_RANGE:
            if _taint_rank(s) > 0:
                return s^
            return cv_err(ERR_VALUE)
        # Excel resizes sum_range to the criteria range's shape from its
        # top-left corner
        sum_rng = cv_range(
            s.a, s.b, s.c, s.b + (rng.d - rng.b), s.c + (rng.e - rng.c)
        )
        if sum_rng.d >= MAX_ROWS or sum_rng.e >= MAX_COLS:
            return cv_err(ERR_REF)
    var total: Float64 = 0.0
    if not _crit_matches_blank(crit):
        var lo = 0
        var hi = 0
        if not wb.row_slice_bounds(
            rng.a, rng.b * MAX_COLS + rng.c, rng.d * MAX_COLS + rng.e, lo, hi
        ):
            return cv_num(0.0)
        if not st.charge((hi - lo + 1) * 2):
            return cv_unsup(String("BUDGET"))
        for p in range(lo, hi):
            var ci = wb.perm_row[p]
            var col = wb.c_coord[ci] % MAX_COLS
            if col < rng.c or col > rng.e:
                continue
            var v = _deref_cell(wb, st, ci)
            if _taint_rank(v) > 0:
                return _worse_taint(v, CellValue())
            if not _crit_match(crit, v):
                continue
            var rr = wb.c_coord[ci] // MAX_COLS - rng.b
            var cc = col - rng.c
            var target = wb.find_cell(sum_rng.a, sum_rng.b + rr, sum_rng.c + cc)
            if target < 0:
                continue
            var sv = _deref_cell(wb, st, target)
            if _taint_rank(sv) > 0:
                return _worse_taint(sv, CellValue())
            if sv.kind == VK_ERR:
                return cv_err(sv.err)
            if sv.kind == VK_NUM:
                total += sv.num
        return cv_num(total)
    # blank-matching criterion: full rectangle, charged
    var rect_rows = rng.d - rng.b + 1
    var rect_cols = rng.e - rng.c + 1
    if not st.charge(rect_rows * rect_cols * 2):
        return cv_unsup(String("BUDGET"))
    for rr in range(rect_rows):
        for cc in range(rect_cols):
            var v = CellValue()
            var target = wb.find_cell(rng.a, rng.b + rr, rng.c + cc)
            if target >= 0:
                v = _deref_cell(wb, st, target)
            if _taint_rank(v) > 0:
                return _worse_taint(v, CellValue())
            if not _crit_match(crit, v):
                continue
            var starget = wb.find_cell(sum_rng.a, sum_rng.b + rr, sum_rng.c + cc)
            if starget < 0:
                continue
            var sv = _deref_cell(wb, st, starget)
            if _taint_rank(sv) > 0:
                return _worse_taint(sv, CellValue())
            if sv.kind == VK_ERR:
                return cv_err(sv.err)
            if sv.kind == VK_NUM:
                total += sv.num
    return cv_num(total)


fn _lookup_compatible(lookup: CellValue, cand: CellValue) -> Bool:
    """Same-type comparability for lookup scans (Excel's binary search only
    ever compares like types)."""
    if lookup.kind == VK_NUM and cand.kind == VK_NUM:
        return True
    if lookup.kind == VK_TEXT and cand.kind == VK_TEXT:
        return True
    if lookup.kind == VK_BOOL and cand.kind == VK_BOOL:
        return True
    return False


fn _lookup_cmp(lookup: CellValue, cand: CellValue) -> Int:
    """cand vs lookup: -1 below, 0 equal, 1 above. Only called on
    _lookup_compatible pairs."""
    if lookup.kind == VK_TEXT:
        return text_cmp_ci(cand.text, lookup.text)
    return _fcmp(cand.num, lookup.num)


fn _fn_vlookup(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 3 or len(args) > 4:
        return cv_err(ERR_VALUE)
    var lookup = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(lookup) > 0:
        return lookup^
    if lookup.kind == VK_ERR:
        return lookup^
    var table = args[1].copy()
    if table.kind != VK_RANGE:
        if _taint_rank(table) > 0:
            return table^
        if table.kind == VK_ERR:
            return table^  # VLOOKUP(x, #REF!, ...) is #REF!, measured on 912
        return cv_err(ERR_VALUE)
    var civ = _to_scalar(wb, st, ctx, args[2])
    if _taint_rank(civ) > 0:
        return civ^
    var cf: Float64 = 0.0
    var code = _to_number(civ, cf)
    if code != 0:
        return cv_err(code)
    var col_idx = 0
    if not _trunc_int(cf, col_idx):
        return cv_err(ERR_VALUE)
    if col_idx < 1:
        return cv_err(ERR_VALUE)
    if col_idx > table.e - table.c + 1:
        return cv_err(ERR_REF)
    var approx = True
    if len(args) == 4:
        # VLOOKUP(x, r, 2,) is EXACT: a present-but-empty argument is 0,
        # never the omitted-argument default (measured live on finch)
        var av = _to_scalar(wb, st, ctx, args[3])
        if _taint_rank(av) > 0:
            return av^
        var b = False
        code = _to_bool(av, b)
        if code != 0:
            return cv_err(code)
        approx = b
    var wild = lookup.kind == VK_TEXT and has_wildcard(lookup.text) and not approx
    # walk the stored cells of the FIRST column, ascending row order
    var lo = 0
    var hi = 0
    if not wb.col_slice_bounds(
        table.a, table.c * MAX_ROWS + table.b, table.c * MAX_ROWS + table.d, lo, hi
    ):
        return cv_err(ERR_NA)
    if not st.charge(hi - lo + 1):
        return cv_unsup(String("BUDGET"))
    var best_row = -1
    for p in range(lo, hi):
        var ci = wb.perm_col[p]
        var cand = _deref_cell(wb, st, ci)
        if _taint_rank(cand) > 0:
            return _worse_taint(cand, CellValue())
        var row = wb.c_coord[ci] // MAX_COLS
        if wild:
            if cand.kind == VK_TEXT and wildcard_match(lookup.text, cand.text):
                best_row = row
                break
            continue
        if not _lookup_compatible(lookup, cand):
            continue
        var c = _lookup_cmp(lookup, cand)
        if approx:
            if c <= 0:
                best_row = row  # last candidate <= lookup wins (sorted data)
            else:
                break
        else:
            if c == 0:
                best_row = row
                break
    if best_row < 0:
        return cv_err(ERR_NA)
    var target = wb.find_cell(table.a, best_row, table.c + col_idx - 1)
    if target < 0:
        return cv_empty()
    return _deref_cell(wb, st, target)


fn _fn_match(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 2 or len(args) > 3:
        return cv_err(ERR_VALUE)
    var lookup = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(lookup) > 0:
        return lookup^
    if lookup.kind == VK_ERR:
        return lookup^
    var vec = args[1].copy()
    if vec.kind == VK_ARRAY:
        return _match_over_array(wb, st, ctx, lookup, vec, args)
    if vec.kind != VK_RANGE:
        if _taint_rank(vec) > 0:
            return vec^
        if vec.kind == VK_ERR:
            return vec^
        return cv_err(ERR_NA)
    var vertical = vec.e == vec.c
    var horizontal = vec.d == vec.b
    if not vertical and not horizontal:
        return cv_err(ERR_NA)
    var mtype = 1
    if len(args) == 3 and args[2].kind == VK_EMPTY:
        mtype = 0  # present-but-empty argument is 0: exact match
    if len(args) == 3 and args[2].kind != VK_EMPTY:
        var tv = _to_scalar(wb, st, ctx, args[2])
        if _taint_rank(tv) > 0:
            return tv^
        var tf: Float64 = 0.0
        var code = _to_number(tv, tf)
        if code != 0:
            return cv_err(code)
        if tf > 0.0:
            mtype = 1
        elif tf < 0.0:
            mtype = -1
        else:
            mtype = 0
    var wild = lookup.kind == VK_TEXT and has_wildcard(lookup.text) and mtype == 0
    var lo = 0
    var hi = 0
    if vertical:
        if not wb.col_slice_bounds(
            vec.a, vec.c * MAX_ROWS + vec.b, vec.c * MAX_ROWS + vec.d, lo, hi
        ):
            return cv_err(ERR_NA)
    else:
        if not wb.row_slice_bounds(
            vec.a, vec.b * MAX_COLS + vec.c, vec.b * MAX_COLS + vec.e, lo, hi
        ):
            return cv_err(ERR_NA)
    if not st.charge(hi - lo + 1):
        return cv_unsup(String("BUDGET"))
    var best_pos = -1
    for p in range(lo, hi):
        var ci = wb.perm_col[p] if vertical else wb.perm_row[p]
        var cand = _deref_cell(wb, st, ci)
        if _taint_rank(cand) > 0:
            return _worse_taint(cand, CellValue())
        var pos = 0
        if vertical:
            pos = wb.c_coord[ci] // MAX_COLS - vec.b + 1
        else:
            pos = wb.c_coord[ci] % MAX_COLS - vec.c + 1
        if wild:
            if cand.kind == VK_TEXT and wildcard_match(lookup.text, cand.text):
                best_pos = pos
                break
            continue
        if not _lookup_compatible(lookup, cand):
            continue
        var c = _lookup_cmp(lookup, cand)
        if mtype == 0:
            if c == 0:
                best_pos = pos
                break
        elif mtype == 1:
            if c <= 0:
                best_pos = pos
            else:
                break
        else:  # -1: data descending; last candidate >= lookup
            if c >= 0:
                best_pos = pos
            else:
                break
    if best_pos < 0:
        return cv_err(ERR_NA)
    return cv_num(Float64(best_pos))


fn _fn_index(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 2 or len(args) > 3:
        return cv_err(ERR_VALUE)
    var rng = args[0].copy()
    if rng.kind != VK_RANGE:
        if _taint_rank(rng) > 0:
            return rng^
        return cv_err(ERR_VALUE)
    var rows = rng.d - rng.b + 1
    var cols = rng.e - rng.c + 1
    var rv = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(rv) > 0:
        return rv^
    var rf: Float64 = 0.0
    var code = _to_number(rv, rf)
    if code != 0:
        return cv_err(code)
    var rn = 0
    if not _trunc_int(rf, rn):
        return cv_err(ERR_VALUE)
    var cn = -1
    if len(args) == 3:
        if args[2].kind == VK_EMPTY:
            cn = 0  # INDEX(r, n,) — explicit empty column selects the row
        else:
            var cv2 = _to_scalar(wb, st, ctx, args[2])
            if _taint_rank(cv2) > 0:
                return cv2^
            var cf: Float64 = 0.0
            code = _to_number(cv2, cf)
            if code != 0:
                return cv_err(code)
            if not _trunc_int(cf, cn):
                return cv_err(ERR_VALUE)
    if cn < 0:
        # two-argument form: the argument indexes the vector direction
        if rows == 1 and cols > 1:
            cn = rn
            rn = 1
        else:
            cn = 1
    if rn < 0 or cn < 0:
        return cv_err(ERR_VALUE)
    if rn > rows or cn > cols:
        return cv_err(ERR_REF)
    var r0 = rng.b + (rn - 1 if rn > 0 else 0)
    var c0 = rng.c + (cn - 1 if cn > 0 else 0)
    var r1 = r0 if rn > 0 else rng.d
    var c1 = c0 if cn > 0 else rng.e
    if rn == 0:
        r0 = rng.b
        r1 = rng.d
    if cn == 0:
        c0 = rng.c
        c1 = rng.e
    return cv_range(rng.a, r0, c0, r1, c1)


fn _fn_rank(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 2 or len(args) > 3:
        return cv_err(ERR_VALUE)
    var xv = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(xv) > 0:
        return xv^
    var x: Float64 = 0.0
    var code = _to_number(xv, x)
    if code != 0:
        return cv_err(code)
    var rng = args[1].copy()
    if rng.kind != VK_RANGE:
        if _taint_rank(rng) > 0:
            return rng^
        return cv_err(ERR_VALUE)
    var ascending = False
    if len(args) == 3 and args[2].kind != VK_EMPTY:
        var ov = _to_scalar(wb, st, ctx, args[2])
        if _taint_rank(ov) > 0:
            return ov^
        var of: Float64 = 0.0
        code = _to_number(ov, of)
        if code != 0:
            return cv_err(code)
        ascending = of != 0.0
    var agg = _Agg()
    _agg_range(wb, st, rng, agg)
    if agg.err != 0:
        return cv_err(agg.err)
    if _taint_rank(agg.taint) > 0:
        return agg.taint.copy()
    var found = False
    var above = 0
    for i in range(len(agg.nums)):
        var v = agg.nums[i]
        if v == x:
            found = True
        elif ascending:
            if v < x:
                above += 1
        elif v > x:
            above += 1
    if not found:
        return cv_err(ERR_NA)
    return cv_num(Float64(above + 1))


# ── Discovery: push a cell's static dependencies ─────────────────────────────
fn _push_cell(mut st: _EngineState, ci: Int, parent: Int):
    if st.state[ci] == _WHITE:
        st.state[ci] = _QUEUED
        st.parent[ci] = parent
        st.stack.append(ci)
        if len(st.stack) > st.max_stack:
            st.max_stack = len(st.stack)
    elif st.state[ci] == _QUEUED and parent >= 0:
        # dynamic re-demand: refresh the demand parent for cycle naming and
        # push a duplicate entry so the blocked cell runs before the demander
        st.parent[ci] = parent
        st.stack.append(ci)
        if len(st.stack) > st.max_stack:
            st.max_stack = len(st.stack)


fn _discover_range_deps(
    wb: Workbook, mut st: _EngineState, sheet: Int, r0: Int, c0: Int, r1: Int, c1: Int, owner: Int
):
    """Queue every stored FORMULA cell inside the rectangle."""
    if sheet < 0 or sheet >= len(wb.sheet_names):
        return
    var narrow = c1 - c0 + 1 <= 4 and r1 - r0 > 4096
    if narrow:
        for col in range(c0, c1 + 1):
            var lo = 0
            var hi = 0
            if not wb.col_slice_bounds(sheet, col * MAX_ROWS + r0, col * MAX_ROWS + r1, lo, hi):
                return
            if not st.charge(hi - lo + 1):
                return
            for p in range(lo, hi):
                var ci = wb.perm_col[p]
                if wb.c_froot[ci] >= 0 and st.state[ci] == _WHITE:
                    _push_cell(st, ci, owner)
        return
    var lo = 0
    var hi = 0
    if not wb.row_slice_bounds(sheet, r0 * MAX_COLS + c0, r1 * MAX_COLS + c1, lo, hi):
        return
    if not st.charge(hi - lo + 1):
        return
    for p in range(lo, hi):
        var ci = wb.perm_row[p]
        var col = wb.c_coord[ci] % MAX_COLS
        if col < c0 or col > c1:
            continue
        if wb.c_froot[ci] >= 0 and st.state[ci] == _WHITE:
            _push_cell(st, ci, owner)


fn _discover_cell(wb: Workbook, mut st: _EngineState, owner: Int):
    """Walk the formula tree of `owner` (iteratively — a node stack, never
    machine recursion) and queue its static dependencies. Dynamic targets
    (whatever OFFSET/INDIRECT resolve to at eval time) join later via
    PENDING."""
    var root = wb.c_froot[owner]
    if root < 0:
        return
    var ctx = _ctx_of(wb, owner)
    var todo = List[Int]()
    todo.append(root)
    var names_seen = 0
    while len(todo) > 0:
        var ni = todo.pop()
        if ni < 0 or ni >= len(wb.nodes):
            continue
        if not st.charge(1):
            return
        var k = wb.nodes[ni].k
        if k == NK_REF or k == NK_RANGE:
            var rng = _shifted_range_of_node(wb.nodes[ni], ctx)
            if rng.kind == VK_RANGE:
                if rng.b == rng.d and rng.c == rng.e:
                    var target = wb.find_cell(rng.a, rng.b, rng.c)
                    if target >= 0 and wb.c_froot[target] >= 0 and st.state[target] == _WHITE:
                        _push_cell(st, target, owner)
                else:
                    _discover_range_deps(wb, st, rng.a, rng.b, rng.c, rng.d, rng.e, owner)
            continue
        if k == NK_NAME:
            var nroot = wb.resolve_name(wb.nodes[ni].text, ctx.sheet)
            if nroot >= 0 and names_seen < 64:
                names_seen += 1
                todo.append(nroot)
            continue
        if k == NK_BIN or k == NK_UN or k == NK_FUNC or k == NK_ARRAYLIT:
            for i in range(wb.nodes[ni].argc):
                todo.append(wb.pool[wb.nodes[ni].arg_start + i])


fn _ctx_of(wb: Workbook, ci: Int) -> _Ctx:
    var ctx = _Ctx()
    ctx.cell = ci
    ctx.sheet = wb.c_sheet[ci]
    ctx.row = wb.c_coord[ci] // MAX_COLS
    ctx.col = wb.c_coord[ci] % MAX_COLS
    ctx.dr = wb.c_fdr[ci]
    ctx.dc = wb.c_fdc[ci]
    ctx.array_mode = wb.c_ftype[ci] == FT_ARRAY
    return ctx^


fn _finalize(wb: Workbook, mut st: _EngineState, ctx: _Ctx, var v: CellValue) -> CellValue:
    """Turn an evaluation result into the stored cell value: references
    dereference (array masters take their (0,0) element), arrays take (0,0),
    and a final EMPTY displays as 0 — exactly Excel."""
    if v.kind == VK_RANGE:
        var s = CellValue()
        if ctx.array_mode:
            var target = wb.find_cell(v.a, v.b, v.c)
            if target >= 0:
                s = _deref_cell(wb, st, target)
        else:
            s = _to_scalar(wb, st, ctx, v)
        v = s^
    if v.kind == VK_ARRAY:
        v = _array_elem(st, v, 0, 0)
    if v.kind == VK_EMPTY:
        return cv_num(0.0)
    return v^


struct RecalcOutcome(Copyable, Movable):
    """Everything the comparator needs, still typed (api.mojo flattens it)."""

    var status: Int
    var evaluated: Int
    var not_evaluated: Int
    var ops: Int
    var max_stack: Int
    var cycle_count: Int
    var cycle_cells: Int
    var cycle_names: List[String]
    var values: List[CellValue]

    fn __init__(out self):
        self.status = RECALC_OK
        self.evaluated = 0
        self.not_evaluated = 0
        self.ops = 0
        self.max_stack = 0
        self.cycle_count = 0
        self.cycle_cells = 0
        self.cycle_names = List[String]()
        self.values = List[CellValue]()


fn _run_cell(wb: Workbook, mut st: _EngineState, root_cell: Int):
    _push_cell(st, root_cell, -1)
    while len(st.stack) > 0:
        if st.exhausted:
            return
        var top = st.stack[len(st.stack) - 1]
        if st.state[top] == _BLACK:
            _ = st.stack.pop()
            continue
        if not st.discovered[top]:
            st.discovered[top] = True
            _discover_cell(wb, st, top)
            continue
        st.cur_cell = top
        var ctx = _ctx_of(wb, top)
        var res = CellValue()
        if wb.c_ftype[top] == FT_DATATABLE:
            res = cv_unsup(String("__DATATABLE__"))
        else:
            res = _eval(wb, st, ctx, wb.c_froot[top], 0)
        if res.kind != VK_PENDING:
            res = _finalize(wb, st, ctx, res^)
        if res.kind == VK_PENDING:
            st.retries[top] += 1
            if st.retries[top] > MAX_RETRIES_PER_CELL:
                st.values[top] = cv_unsup(String("RETRY_LIMIT"))
                st.state[top] = _BLACK
                _ = st.stack.pop()
                continue
            var target = res.a
            if target >= 0 and target < len(st.state) and st.state[target] != _BLACK:
                _push_cell(st, target, top)
            continue
        # cycle marking may have blackened this cell mid-evaluation; the
        # named CYCLE value it received then is the answer of record
        if st.state[top] != _BLACK:
            st.values[top] = res^
            st.state[top] = _BLACK
        _ = st.stack.pop()
        st.arr_pool.clear()


fn recalc_workbook(wb: Workbook, budget_ops: Int) -> RecalcOutcome:
    """Demand-driven topological recalculation of every formula cell.
    `budget_ops <= 0` selects DEFAULT_BUDGET. Never raises; budget
    exhaustion returns status RECALC_BUDGET with everything evaluated so far.

    @capability recalc_workbook
    complexity: O(cells + formula nodes + range-scan work), all charged
    counts: none
    @endcapability
    """
    var st = _EngineState()
    st.budget = budget_ops if budget_ops > 0 else DEFAULT_BUDGET
    var n = wb.n_cells()
    st.values.resize(n, CellValue())
    st.state.resize(n, _WHITE)
    st.discovered.resize(n, False)
    st.parent.resize(n, -1)
    st.retries.resize(n, 0)
    var out = RecalcOutcome()
    for i in range(len(wb.formula_cells)):
        if st.exhausted:
            break
        var fc = wb.formula_cells[i]
        if st.state[fc] != _BLACK:
            _run_cell(wb, st, fc)
    for i in range(len(wb.formula_cells)):
        var fc = wb.formula_cells[i]
        if st.state[fc] == _BLACK:
            out.evaluated += 1
        else:
            out.not_evaluated += 1
    out.status = RECALC_BUDGET if st.exhausted else RECALC_OK
    out.ops = st.ops
    out.max_stack = st.max_stack
    out.cycle_count = st.cycle_count
    out.cycle_cells = st.cycle_cells
    out.cycle_names = st.cycle_names.copy()
    out.values = st.values.copy()
    return out^


# ── Census functions 24-48 (see formula.mojo for the ordering note) ──────────
fn _fn_column(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) == 0:
        return cv_num(Float64(ctx.col + 1))
    if len(args) != 1:
        return cv_err(ERR_VALUE)
    var a = args[0].copy()
    if _taint_rank(a) > 0:
        return a^
    if a.kind == VK_EMPTY:
        return cv_num(Float64(ctx.col + 1))
    if a.kind != VK_RANGE:
        if a.kind == VK_ERR:
            return a^
        return cv_err(ERR_VALUE)
    if ctx.array_mode and a.e > a.c:
        var cols = a.e - a.c + 1
        if cols > MAX_ARRAY_ELEMS or not st.charge(cols):
            return cv_unsup(String("ARRAY_TOO_LARGE"))
        var start = len(st.arr_pool)
        for c in range(a.c, a.e + 1):
            st.arr_pool.append(cv_num(Float64(c + 1)))
        var out = CellValue()
        out.kind = VK_ARRAY
        out.a = start
        out.b = 1
        out.c = cols
        return out^
    return cv_num(Float64(a.c + 1))


fn _fn_weekday(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 1 or len(args) > 2:
        return cv_err(ERR_VALUE)
    var v = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(v) > 0:
        return v^
    var x: Float64 = 0.0
    var code = _to_number(v, x)
    if code != 0:
        return cv_err(code)
    if x < 0.0 or x > Float64(EXCEL_MAX_SERIAL) + 1.0:
        return cv_err(ERR_NUM)
    var serial = Int(floor(x))
    var rtype = 1
    if len(args) == 2 and args[1].kind != VK_EMPTY:
        var tv = _to_scalar(wb, st, ctx, args[1])
        if _taint_rank(tv) > 0:
            return tv^
        var tf: Float64 = 0.0
        code = _to_number(tv, tf)
        if code != 0:
            return cv_err(code)
        if not _trunc_int(tf, rtype):
            return cv_err(ERR_NUM)
    # Excel's own week: serial 1 (1900-01-01) is "Sunday" (the 1900 legend)
    if rtype == 1:
        return cv_num(Float64((serial - 1) % 7 + 1))  # Sun=1..Sat=7
    if rtype == 2:
        return cv_num(Float64((serial - 2 % 7 + 7) % 7 + 1))  # Mon=1..Sun=7
    if rtype == 3:
        return cv_num(Float64((serial - 2 % 7 + 7) % 7))  # Mon=0..Sun=6
    if rtype >= 11 and rtype <= 17:
        # 11 starts Monday, 12 Tuesday, ... 17 Sunday
        var start_shift = rtype - 9  # 11 -> 2 (Monday), matching type 2
        return cv_num(Float64((serial - start_shift % 7 + 7) % 7 + 1))
    return cv_err(ERR_NUM)


fn _fn_simple_numeric(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    if fid == FID_INT:
        if len(args) != 1:
            return cv_err(ERR_VALUE)
        var v = _to_scalar(wb, st, ctx, args[0])
        if _taint_rank(v) > 0:
            return v^
        var x: Float64 = 0.0
        var code = _to_number(v, x)
        if code != 0:
            return cv_err(code)
        return cv_num(floor(x))
    if fid == FID_VALUE:
        if len(args) != 1:
            return cv_err(ERR_VALUE)
        var v = _to_scalar(wb, st, ctx, args[0])
        if _taint_rank(v) > 0:
            return v^
        if v.kind == VK_ERR:
            return v^
        if v.kind == VK_NUM:
            return v^
        var x: Float64 = 0.0
        var code = _to_number(v, x)
        if code != 0:
            return cv_err(code)
        return cv_num(x)
    if fid == FID_SLN:
        if len(args) != 3:
            return cv_err(ERR_VALUE)
        var nums = List[Float64]()
        for i in range(3):
            var v = _to_scalar(wb, st, ctx, args[i])
            if _taint_rank(v) > 0:
                return v^
            var x: Float64 = 0.0
            var code = _to_number(v, x)
            if code != 0:
                return cv_err(code)
            nums.append(x)
        if nums[2] == 0.0:
            return cv_err(ERR_DIV0)
        return cv_num((nums[0] - nums[1]) / nums[2])
    # FID_DAYS(end_date, start_date)
    if len(args) != 2:
        return cv_err(ERR_VALUE)
    var e = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(e) > 0:
        return e^
    var s2 = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(s2) > 0:
        return s2^
    var xe: Float64 = 0.0
    var code_e = _to_number(e, xe)
    if code_e != 0:
        return cv_err(code_e)
    var xs: Float64 = 0.0
    var code_s = _to_number(s2, xs)
    if code_s != 0:
        return cv_err(code_s)
    return cv_num(floor(xe) - floor(xs))


fn _utf8_len(s: String) -> Int:
    """Character count (codepoints) — Excel's LEN counts characters, and the
    corpus is UTF-8; continuation bytes (10xxxxxx) do not count."""
    var bs = s.as_bytes()
    var n = 0
    for i in range(len(bs)):
        if Int(bs[i]) & 192 != 128:
            n += 1
    return n


fn _utf8_slice(s: String, from_start: Bool, n_chars: Int) -> String:
    var bs = s.as_bytes()
    var nb = len(bs)
    # character start offsets
    var starts = List[Int]()
    for i in range(nb):
        if Int(bs[i]) & 192 != 128:
            starts.append(i)
    var total = len(starts)
    var take = min(n_chars, total)
    var a = 0
    var b = nb
    if from_start:
        b = starts[take] if take < total else nb
    else:
        a = starts[total - take] if take > 0 else nb
        if take == 0:
            a = nb
    var buf = List[UInt8]()
    for i in range(a, b):
        buf.append(bs[i])
    return _bs_str(buf)


fn _fn_text_slice(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    if len(args) < 1 or len(args) > 2:
        return cv_err(ERR_VALUE)
    var v = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(v) > 0:
        return v^
    if v.kind == VK_ERR:
        return v^
    var text = _to_text(v)
    if fid == FID_LEN:
        if len(args) != 1:
            return cv_err(ERR_VALUE)
        return cv_num(Float64(_utf8_len(text)))
    var n = 1
    if len(args) == 2:
        var nv = _to_scalar(wb, st, ctx, args[1])
        if _taint_rank(nv) > 0:
            return nv^
        var nf: Float64 = 0.0
        var code = _to_number(nv, nf)
        if code != 0:
            return cv_err(code)
        if not _trunc_int(nf, n) or n < 0:
            return cv_err(ERR_VALUE)
    return cv_text(_utf8_slice(text, fid == FID_LEFT, n))


fn _ymd_to_serial(y: Int, m: Int, d: Int) -> Int:
    """Civil (y, m, d) -> Excel 1900 serial, preserving the leap bug. Months
    outside 1..12 and days outside the month ROLL (Excel semantics). Returns
    -1 below serial 0."""
    # normalise month
    var yy = y
    var mm = m
    while mm > 12:
        mm -= 12
        yy += 1
    while mm < 1:
        mm += 12
        yy -= 1
    # days-from-civil (Hinnant), days since 1970-01-01
    var yr = yy - 1 if mm <= 2 else yy
    var era = yr // 400 if yr >= 0 else (yr - 399) // 400
    var yoe = yr - era * 400
    var mp = mm - 3 if mm >= 3 else mm + 9
    var doy = (153 * mp + 2) // 5 + d - 1
    var doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    var days70 = era * 146097 + doe - 719468
    var serial = days70 + 25569
    # the fake 1900-02-29 shifts everything before 1900-03-01 down by one
    if serial < 61:
        serial -= 1
    if serial < 0:
        return -1
    return serial


fn _fn_edate_eomonth(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    if len(args) != 2:
        return cv_err(ERR_VALUE)
    var sv = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(sv) > 0:
        return sv^
    var sx: Float64 = 0.0
    var code = _to_number(sv, sx)
    if code != 0:
        return cv_err(code)
    if sx < 0.0 or sx > Float64(EXCEL_MAX_SERIAL) + 1.0:
        return cv_err(ERR_NUM)
    var mv = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(mv) > 0:
        return mv^
    var mx: Float64 = 0.0
    code = _to_number(mv, mx)
    if code != 0:
        return cv_err(code)
    var months = 0
    if not _trunc_int(mx, months):
        return cv_err(ERR_NUM)
    var y = 0
    var m = 0
    var d = 0
    if not _serial_to_ymd(Int(floor(sx)), y, m, d):
        return cv_err(ERR_NUM)
    var tm = (y * 12 + (m - 1)) + months
    var ny = tm // 12
    var nm = tm % 12 + 1
    var serial = 0
    if fid == FID_EOMONTH:
        serial = _ymd_to_serial(ny, nm + 1, 0)  # day 0 of next month = last day
    else:
        # EDATE clamps the day to the target month's length
        var eom = _ymd_to_serial(ny, nm + 1, 0)
        var som = _ymd_to_serial(ny, nm, 1)
        if eom < 0 or som < 0:
            return cv_err(ERR_NUM)
        var max_d = eom - som + 1
        var dd = min(d, max_d)
        if dd < 1:
            dd = 1
        serial = _ymd_to_serial(ny, nm, dd)
    if serial < 0 or serial > EXCEL_MAX_SERIAL:
        return cv_err(ERR_NUM)
    return cv_num(Float64(serial))


fn _fn_substitute(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) < 3 or len(args) > 4:
        return cv_err(ERR_VALUE)
    var tv = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(tv) > 0:
        return tv^
    if tv.kind == VK_ERR:
        return tv^
    var ov = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(ov) > 0:
        return ov^
    if ov.kind == VK_ERR:
        return ov^
    var nv = _to_scalar(wb, st, ctx, args[2])
    if _taint_rank(nv) > 0:
        return nv^
    if nv.kind == VK_ERR:
        return nv^
    var text = _to_text(tv)
    var old = _to_text(ov)
    var new = _to_text(nv)
    var which = 0  # 0 = all occurrences
    if len(args) == 4:
        var wv = _to_scalar(wb, st, ctx, args[3])
        if _taint_rank(wv) > 0:
            return wv^
        var wf: Float64 = 0.0
        var code = _to_number(wv, wf)
        if code != 0:
            return cv_err(code)
        if not _trunc_int(wf, which) or which < 1:
            return cv_err(ERR_VALUE)
    var tb = text.as_bytes()
    var ob = old.as_bytes()
    var nt = len(tb)
    var no = len(ob)
    if no == 0:
        return cv_text(text)
    var nb2 = new.as_bytes()
    var obuf = List[UInt8]()
    var i = 0
    var seen = 0
    while i < nt:
        var hit = False
        if i + no <= nt:
            hit = True
            for j in range(no):
                if tb[i + j] != ob[j]:
                    hit = False
                    break
        if hit:
            seen += 1
            if which == 0 or seen == which:
                for j in range(len(nb2)):
                    obuf.append(nb2[j])
                i += no
                continue
        obuf.append(tb[i])
        i += 1
    return cv_text(_bs_str(obuf))


fn _pow10_int(n: Int) -> Float64:
    var p: Float64 = 1.0
    var k = n if n >= 0 else -n
    if k > 308:
        k = 308
    for _ in range(k):
        p *= 10.0
    return 1.0 / p if n < 0 else p


fn _fn_round_directed(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    if len(args) < 1 or len(args) > 2:
        return cv_err(ERR_VALUE)
    var v = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(v) > 0:
        return v^
    var x: Float64 = 0.0
    var code = _to_number(v, x)
    if code != 0:
        return cv_err(code)
    var digits = 0
    if len(args) == 2:
        var dv = _to_scalar(wb, st, ctx, args[1])
        if _taint_rank(dv) > 0:
            return dv^
        var df: Float64 = 0.0
        code = _to_number(dv, df)
        if code != 0:
            return cv_err(code)
        if not _trunc_int(df, digits):
            return cv_err(ERR_NUM)
    if digits > 300 or digits < -300:
        return cv_err(ERR_NUM)
    var scale = _pow10_int(digits)
    var scaled = x * scale
    if scaled != scaled or fabs(scaled) >= 9.007199254740992e15:
        return cv_num(x)  # beyond the integer grid the value IS its rounding
    var neg = x < 0.0
    var mag = fabs(scaled)
    var r: Float64 = 0.0
    if fid == FID_ROUNDUP:
        r = floor(mag)
        if r != mag:
            r += 1.0
    else:
        r = floor(mag)
    var out = (-r if neg else r) / scale
    return cv_num(out)


fn _fn_sumproduct(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) == 0:
        return cv_err(ERR_VALUE)
    var arrays = List[CellValue]()
    var rows = -1
    var cols = -1
    for i in range(len(args)):
        var a = args[i].copy()
        if _taint_rank(a) > 0:
            return a^
        if a.kind == VK_ERR:
            return a^
        if a.kind == VK_RANGE:
            var r = 0
            var c = 0
            a = _materialize(wb, st, a, r, c)
            if a.kind != VK_ARRAY:
                return a^
        if a.kind == VK_ARRAY:
            if rows < 0:
                rows = a.b
                cols = a.c
            elif a.b != rows or a.c != cols:
                return cv_err(ERR_VALUE)
            arrays.append(a^)
        else:
            # a scalar factor multiplies everything (1x1)
            if rows < 0:
                rows = 1
                cols = 1
            elif rows != 1 or cols != 1:
                return cv_err(ERR_VALUE)
            arrays.append(a^)
    var total: Float64 = 0.0
    if not st.charge(rows * cols * len(arrays)):
        return cv_unsup(String("BUDGET"))
    for i in range(rows * cols):
        var prod: Float64 = 1.0
        for q in range(len(arrays)):
            ref a = arrays[q]
            var e = a.copy() if a.kind != VK_ARRAY else _array_elem(st, a, i // cols, i % cols)
            if _taint_rank(e) > 0:
                return _worse_taint(e, CellValue())
            if e.kind == VK_ERR:
                return cv_err(e.err)
            if e.kind == VK_NUM:
                prod *= e.num
            elif e.kind == VK_BOOL and len(arrays) == 1:
                prod *= 0.0  # bools are non-numeric to SUMPRODUCT
            else:
                prod *= 0.0
        total += prod
    return cv_num(total)


fn _fn_sumifs(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    var n = len(args)
    if n < 3 or (n - 1) % 2 != 0:
        return cv_err(ERR_VALUE)
    var sum_rng = args[0].copy()
    if sum_rng.kind != VK_RANGE:
        if _taint_rank(sum_rng) > 0:
            return sum_rng^
        return cv_err(ERR_VALUE)
    var pairs = (n - 1) // 2
    var rngs = List[CellValue]()
    var crits = List[_Crit]()
    for i in range(pairs):
        var r = args[1 + 2 * i].copy()
        if r.kind != VK_RANGE:
            if _taint_rank(r) > 0:
                return r^
            return cv_err(ERR_VALUE)
        if not _range_dims_equal(sum_rng, r):
            return cv_err(ERR_VALUE)
        var cs = _to_scalar(wb, st, ctx, args[2 + 2 * i])
        if _taint_rank(cs) > 0:
            return cs^
        if cs.kind == VK_ERR:
            return cs^
        rngs.append(r^)
        crits.append(_crit_of(cs))
    var any_blankish = False
    for i in range(pairs):
        if _crit_matches_blank(crits[i]):
            any_blankish = True
    var total: Float64 = 0.0
    if not any_blankish:
        # drive from the first criteria range's stored cells
        var d = rngs[0].copy()
        var lo = 0
        var hi = 0
        if not wb.row_slice_bounds(d.a, d.b * MAX_COLS + d.c, d.d * MAX_COLS + d.e, lo, hi):
            return cv_num(0.0)
        if not st.charge((hi - lo + 1) * (pairs + 1)):
            return cv_unsup(String("BUDGET"))
        for p in range(lo, hi):
            var ci = wb.perm_row[p]
            var col = wb.c_coord[ci] % MAX_COLS
            if col < d.c or col > d.e:
                continue
            var rr = wb.c_coord[ci] // MAX_COLS - d.b
            var cc = col - d.c
            var all_ok = True
            for q in range(pairs):
                var v = CellValue()
                if q == 0:
                    v = _deref_cell(wb, st, ci)
                else:
                    var target = wb.find_cell(rngs[q].a, rngs[q].b + rr, rngs[q].c + cc)
                    if target >= 0:
                        v = _deref_cell(wb, st, target)
                if _taint_rank(v) > 0:
                    return _worse_taint(v, CellValue())
                if not _crit_match(crits[q], v):
                    all_ok = False
                    break
            if not all_ok:
                continue
            var starget = wb.find_cell(sum_rng.a, sum_rng.b + rr, sum_rng.c + cc)
            if starget < 0:
                continue
            var sv = _deref_cell(wb, st, starget)
            if _taint_rank(sv) > 0:
                return _worse_taint(sv, CellValue())
            if sv.kind == VK_ERR:
                return cv_err(sv.err)
            if sv.kind == VK_NUM:
                total += sv.num
        return cv_num(total)
    # blank-matching criteria: full rectangle, charged
    var rect_rows = sum_rng.d - sum_rng.b + 1
    var rect_cols = sum_rng.e - sum_rng.c + 1
    if not st.charge(rect_rows * rect_cols * (pairs + 1)):
        return cv_unsup(String("BUDGET"))
    for rr in range(rect_rows):
        for cc in range(rect_cols):
            var all_ok = True
            for q in range(pairs):
                var v = CellValue()
                var target = wb.find_cell(rngs[q].a, rngs[q].b + rr, rngs[q].c + cc)
                if target >= 0:
                    v = _deref_cell(wb, st, target)
                if _taint_rank(v) > 0:
                    return _worse_taint(v, CellValue())
                if not _crit_match(crits[q], v):
                    all_ok = False
                    break
            if not all_ok:
                continue
            var starget = wb.find_cell(sum_rng.a, sum_rng.b + rr, sum_rng.c + cc)
            if starget < 0:
                continue
            var sv = _deref_cell(wb, st, starget)
            if _taint_rank(sv) > 0:
                return _worse_taint(sv, CellValue())
            if sv.kind == VK_ERR:
                return cv_err(sv.err)
            if sv.kind == VK_NUM:
                total += sv.num
    return cv_num(total)


fn _fn_lookup(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    """Vector-form LOOKUP: last value <= lookup in the (assumed sorted)
    lookup vector, result from the result vector (or the lookup vector). The
    2-argument ARRAY form searches the first column and answers from the last
    when the range is taller than wide, and row-wise otherwise."""
    if len(args) < 2 or len(args) > 3:
        return cv_err(ERR_VALUE)
    var lookup = _to_scalar(wb, st, ctx, args[0])
    if _taint_rank(lookup) > 0:
        return lookup^
    if lookup.kind == VK_ERR:
        return lookup^
    var vec = args[1].copy()
    if vec.kind != VK_RANGE:
        if _taint_rank(vec) > 0:
            return vec^
        return cv_err(ERR_NA)
    var s_r0 = vec.b
    var s_c0 = vec.c
    var s_r1 = vec.d
    var s_c1 = vec.e
    var out_r0 = s_r0
    var out_c0 = s_c0
    var vertical = True
    if len(args) == 2:
        var rows = vec.d - vec.b + 1
        var cols = vec.e - vec.c + 1
        if rows >= cols:
            s_c1 = s_c0
            out_c0 = vec.e  # answer from the LAST column
        else:
            vertical = False
            s_r1 = s_r0
            out_r0 = vec.d  # answer from the LAST row
    else:
        var res = args[2].copy()
        if res.kind != VK_RANGE:
            if _taint_rank(res) > 0:
                return res^
            return cv_err(ERR_NA)
        vertical = vec.e == vec.c
        if not vertical and vec.d != vec.b:
            return cv_err(ERR_NA)
        s_r1 = vec.d if vertical else vec.b
        s_c1 = vec.c if vertical else vec.e
        out_r0 = res.b
        out_c0 = res.c
        # result vector may be a row or column; align by position below
        if res.e > res.c and res.d == res.b:
            # horizontal result vector
            pass
    var lo = 0
    var hi = 0
    var best_pos = -1
    if vertical:
        if not wb.col_slice_bounds(vec.a, s_c0 * MAX_ROWS + s_r0, s_c0 * MAX_ROWS + s_r1, lo, hi):
            return cv_err(ERR_NA)
    else:
        if not wb.row_slice_bounds(vec.a, s_r0 * MAX_COLS + s_c0, s_r0 * MAX_COLS + s_c1, lo, hi):
            return cv_err(ERR_NA)
    if not st.charge(hi - lo + 1):
        return cv_unsup(String("BUDGET"))
    for p in range(lo, hi):
        var ci = wb.perm_col[p] if vertical else wb.perm_row[p]
        var cand = _deref_cell(wb, st, ci)
        if _taint_rank(cand) > 0:
            return _worse_taint(cand, CellValue())
        if not _lookup_compatible(lookup, cand):
            continue
        var pos = 0
        if vertical:
            pos = wb.c_coord[ci] // MAX_COLS - s_r0
        else:
            pos = wb.c_coord[ci] % MAX_COLS - s_c0
        if _lookup_cmp(lookup, cand) <= 0:
            best_pos = pos
        else:
            break
    if best_pos < 0:
        return cv_err(ERR_NA)
    var target = -1
    if len(args) == 2:
        if vertical:
            target = wb.find_cell(vec.a, s_r0 + best_pos, out_c0)
        else:
            target = wb.find_cell(vec.a, out_r0, s_c0 + best_pos)
    else:
        var res = args[2].copy()
        if res.e > res.c and res.d == res.b:
            target = wb.find_cell(res.a, res.b, res.c + best_pos)
        else:
            target = wb.find_cell(res.a, res.b + best_pos, res.c)
    if target < 0:
        return cv_empty()
    return _deref_cell(wb, st, target)


fn _heap_sort_desc(mut a: List[Float64]):
    """In-place iterative heapsort, descending. New code in the new namespace
    because the frozen insertion_sort is O(n^2) and LARGE ranges reach 10^5
    cells; no recursion, O(n log n)."""
    var n = len(a)
    # build a MIN-heap then extract to the back -> descending order
    var i = n // 2 - 1
    while i >= 0:
        _sift_down_min(a, i, n)
        i -= 1
    var end = n - 1
    while end > 0:
        var t = a[0]
        a[0] = a[end]
        a[end] = t
        _sift_down_min(a, 0, end)
        end -= 1


fn _sift_down_min(mut a: List[Float64], start: Int, end: Int):
    var root = start
    while True:
        var child = 2 * root + 1
        if child >= end:
            return
        if child + 1 < end and a[child + 1] < a[child]:
            child += 1
        if a[child] < a[root]:
            var t = a[root]
            a[root] = a[child]
            a[child] = t
            root = child
        else:
            return


fn _fn_large(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) != 2:
        return cv_err(ERR_VALUE)
    var agg = _Agg()
    _agg_value(wb, st, ctx, args[0], agg)
    if agg.err != 0:
        return cv_err(agg.err)
    if _taint_rank(agg.taint) > 0:
        return agg.taint.copy()
    var kv = _to_scalar(wb, st, ctx, args[1])
    if _taint_rank(kv) > 0:
        return kv^
    var kf: Float64 = 0.0
    var code = _to_number(kv, kf)
    if code != 0:
        return cv_err(code)
    var k = 0
    if not _trunc_int(kf, k) or k < 1 or k > len(agg.nums):
        return cv_err(ERR_NUM)
    var nums = agg.nums.copy()
    if not st.charge(len(nums) * 16):
        return cv_unsup(String("BUDGET"))
    _heap_sort_desc(nums)
    return cv_num(nums[k - 1])


fn _fn_or(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    var seen = False
    var any_true = False
    for i in range(len(args)):
        var a = args[i].copy()
        if _taint_rank(a) > 0:
            return a^
        if a.kind == VK_ERR:
            return a^
        if a.kind == VK_EMPTY:
            continue
        if a.kind == VK_RANGE or a.kind == VK_ARRAY:
            var agg_err = 0
            var found = False
            var truth = True
            var taint = CellValue()
            _and_over_array_or_range(wb, st, a, found, truth, agg_err, taint)
            if _taint_rank(taint) > 0:
                return taint^
            if agg_err != 0:
                return cv_err(agg_err)
            if found:
                seen = True
                # `truth` is AND-accumulated; OR needs its own pass — reuse
                # the walker but detect "any true" as NOT(all false)
                var all_false = True
                var f2 = False
                var t2 = True
                var e2 = 0
                var tt = CellValue()
                _or_probe(wb, st, a, f2, all_false, e2, tt)
                if _taint_rank(tt) > 0:
                    return tt^
                if e2 != 0:
                    return cv_err(e2)
                any_true = any_true or not all_false
            continue
        var b = False
        var code = _to_bool(a, b)
        if code != 0:
            return cv_err(code)
        seen = True
        any_true = any_true or b
    if not seen:
        return cv_err(ERR_VALUE)
    return cv_bool(any_true)


fn _or_probe(
    wb: Workbook,
    mut st: _EngineState,
    v: CellValue,
    mut found: Bool,
    mut all_false: Bool,
    mut err: Int,
    mut taint: CellValue,
):
    if v.kind == VK_ARRAY:
        for i in range(v.b * v.c):
            var idx = v.a + i
            if idx < 0 or idx >= len(st.arr_pool):
                continue
            var e = st.arr_pool[idx].copy()
            if _taint_rank(e) > 0:
                taint = _worse_taint(taint, e)
                return
            if e.kind == VK_ERR:
                err = e.err
                return
            if e.kind == VK_NUM or e.kind == VK_BOOL:
                found = True
                if e.num != 0.0:
                    all_false = False
        return
    var lo = 0
    var hi = 0
    if not wb.row_slice_bounds(v.a, v.b * MAX_COLS + v.c, v.d * MAX_COLS + v.e, lo, hi):
        return
    if not st.charge(hi - lo + 1):
        taint = _worse_taint(taint, cv_unsup(String("BUDGET")))
        return
    for p in range(lo, hi):
        var ci = wb.perm_row[p]
        var col = wb.c_coord[ci] % MAX_COLS
        if col < v.c or col > v.e:
            continue
        var e = _deref_cell(wb, st, ci)
        if _taint_rank(e) > 0:
            taint = _worse_taint(taint, e)
            return
        if e.kind == VK_ERR:
            err = e.err
            return
        if e.kind == VK_NUM or e.kind == VK_BOOL:
            found = True
            if e.num != 0.0:
                all_false = False


fn _fn_rows(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) != 1:
        return cv_err(ERR_VALUE)
    var a = args[0].copy()
    if _taint_rank(a) > 0:
        return a^
    if a.kind == VK_RANGE:
        return cv_num(Float64(a.d - a.b + 1))
    if a.kind == VK_ARRAY:
        return cv_num(Float64(a.b))
    if a.kind == VK_ERR:
        return a^
    return cv_err(ERR_VALUE)


fn _fn_is_kind(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    if len(args) != 1:
        return cv_err(ERR_VALUE)
    var a = args[0].copy()
    if _taint_rank(a) > 0:
        return a^
    if fid == FID_ISBLANK:
        # only a REFERENCE to a truly empty cell is blank
        if a.kind == VK_RANGE:
            var s = _to_scalar(wb, st, ctx, a)
            if _taint_rank(s) > 0:
                return s^
            return cv_bool(s.kind == VK_EMPTY)
        return cv_bool(False)
    # ISNUMBER
    var s = _to_scalar(wb, st, ctx, a)
    if _taint_rank(s) > 0:
        return s^
    return cv_bool(s.kind == VK_NUM)


fn _fn_date(wb: Workbook, mut st: _EngineState, ctx: _Ctx, args: List[CellValue]) -> CellValue:
    if len(args) != 3:
        return cv_err(ERR_VALUE)
    var parts = List[Int]()
    for i in range(3):
        var v = _to_scalar(wb, st, ctx, args[i])
        if _taint_rank(v) > 0:
            return v^
        var x: Float64 = 0.0
        var code = _to_number(v, x)
        if code != 0:
            return cv_err(code)
        var t = 0
        if not _trunc_int(x, t):
            return cv_err(ERR_NUM)
        parts.append(t)
    var y = parts[0]
    if y < 0 or y > 9999:
        return cv_err(ERR_NUM)
    if y <= 1899:
        y += 1900  # Excel's two-digit-era year rule
    var serial = _ymd_to_serial(y, parts[1], parts[2])
    if serial < 0 or serial > EXCEL_MAX_SERIAL:
        return cv_err(ERR_NUM)
    return cv_num(Float64(serial))


# ── Array lifting of scalar-slot arguments ────────────────────────────────────
fn _lift_slot(fid: Int, i: Int, argc: Int) -> Bool:
    """True when argument slot `i` of `fid` is a SCALAR slot that broadcasts
    when given an array. Range-consuming slots (lookup tables, criteria
    ranges, aggregate ranges) never lift."""
    if fid == FID_ABS or fid == FID_INT or fid == FID_VALUE or fid == FID_LEN:
        return i == 0
    if fid == FID_YEAR or fid == FID_MONTH or fid == FID_ISNUMBER:
        return i == 0
    if fid == FID_LEFT or fid == FID_RIGHT:
        return True
    if fid == FID_WEEKDAY or fid == FID_ROUNDUP or fid == FID_ROUNDDOWN or fid == FID_DAYS:
        return True
    if fid == FID_TIME or fid == FID_DATE or fid == FID_SLN or fid == FID_SUBSTITUTE:
        return True
    if fid == FID_TEXTAFTER:
        return True
    if fid == FID_VLOOKUP or fid == FID_MATCH:
        return i == 0
    if fid == FID_COUNTIF or fid == FID_SUMIF:
        return i == 1
    if fid == FID_COUNTIFS:
        return i % 2 == 1
    if fid == FID_SUMIFS:
        return i >= 1 and i % 2 == 0
    return False


fn _maybe_lift(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, fid: Int, args: List[CellValue]
) -> CellValue:
    """When any liftable slot holds an array (or a >1-cell range that scalar
    context cannot intersect), evaluate the whole call once per element and
    return the ARRAY of results. Returns EMPTY when no lifting applies."""
    var need = False
    for i in range(len(args)):
        if not _lift_slot(fid, i, len(args)):
            continue
        ref a = args[i]
        if a.kind == VK_ARRAY and a.b * a.c > 1:
            need = True
        elif a.kind == VK_RANGE and (a.b != a.d or a.c != a.e):
            if ctx.array_mode:
                need = True
            else:
                # scalar mode: lift only when implicit intersection fails
                var probe = _to_scalar(wb, st, ctx, a)
                if probe.kind == VK_PENDING:
                    return probe^
                if probe.kind == VK_ERR and probe.err == ERR_VALUE:
                    need = True
    if not need:
        return cv_empty()
    # materialize lifted slots, compute broadcast dims
    var mat = List[CellValue]()
    var out_rows = 1
    var out_cols = 1
    for i in range(len(args)):
        var a = args[i].copy()
        var take = _lift_slot(fid, i, len(args)) and (
            a.kind == VK_ARRAY or (a.kind == VK_RANGE and (a.b != a.d or a.c != a.e))
        )
        if take and a.kind == VK_RANGE:
            var r = 1
            var c = 1
            a = _materialize(wb, st, a, r, c)
            if a.kind != VK_ARRAY:
                return a^
        if take and a.kind == VK_ARRAY:
            out_rows = max(out_rows, a.b)
            out_cols = max(out_cols, a.c)
        mat.append(a^)
    if out_rows * out_cols > MAX_ARRAY_ELEMS:
        return cv_unsup(String("ARRAY_TOO_LARGE"))
    if not st.charge(out_rows * out_cols):
        return cv_unsup(String("BUDGET"))
    var start = len(st.arr_pool)
    # pre-size: inner calls may grow arr_pool; collect into a local list first
    var results = List[CellValue]()
    for e in range(out_rows * out_cols):
        var rr = e // out_cols
        var cc = e % out_cols
        var eargs = List[CellValue]()
        for i in range(len(mat)):
            ref a = mat[i]
            var lifted_slot = _lift_slot(fid, i, len(mat)) and a.kind == VK_ARRAY
            if lifted_slot:
                eargs.append(_array_elem(st, a, rr, cc))
            else:
                eargs.append(a.copy())
        results.append(_dispatch_eager(wb, st, ctx, fid, eargs))
    start = len(st.arr_pool)
    for i in range(len(results)):
        if results[i].kind == VK_PENDING:
            return results[i].copy()
        st.arr_pool.append(results[i].copy())
    var outv = CellValue()
    outv.kind = VK_ARRAY
    outv.a = start
    outv.b = out_rows
    outv.c = out_cols
    return outv^


fn _match_over_array(
    wb: Workbook, mut st: _EngineState, ctx: _Ctx, lookup: CellValue, vec: CellValue,
    args: List[CellValue],
) -> CellValue:
    """MATCH over a COMPUTED array — MATCH(1, (a=x)*(b>=y)*...) is the classic
    multi-criteria lookup idiom (measured on 912). Positions count every
    element, 1-based, row-major over the vector."""
    if vec.b != 1 and vec.c != 1:
        return cv_err(ERR_NA)
    var mtype = 1
    if len(args) == 3 and args[2].kind == VK_EMPTY:
        mtype = 0
    elif len(args) == 3:
        var tv = _to_scalar(wb, st, ctx, args[2])
        if _taint_rank(tv) > 0:
            return tv^
        var tf: Float64 = 0.0
        var code = _to_number(tv, tf)
        if code != 0:
            return cv_err(code)
        if tf > 0.0:
            mtype = 1
        elif tf < 0.0:
            mtype = -1
        else:
            mtype = 0
    var wild = lookup.kind == VK_TEXT and has_wildcard(lookup.text) and mtype == 0
    var n = vec.b * vec.c
    if not st.charge(n):
        return cv_unsup(String("BUDGET"))
    var best_pos = -1
    for i in range(n):
        var idx = vec.a + i
        if idx < 0 or idx >= len(st.arr_pool):
            continue
        var cand = st.arr_pool[idx].copy()
        if _taint_rank(cand) > 0:
            return _worse_taint(cand, CellValue())
        if wild:
            if cand.kind == VK_TEXT and wildcard_match(lookup.text, cand.text):
                best_pos = i + 1
                break
            continue
        if not _lookup_compatible(lookup, cand):
            continue
        var c = _lookup_cmp(lookup, cand)
        if mtype == 0:
            if c == 0:
                best_pos = i + 1
                break
        elif mtype == 1:
            if c <= 0:
                best_pos = i + 1
            else:
                break
        else:
            if c >= 0:
                best_pos = i + 1
            else:
                break
    if best_pos < 0:
        return cv_err(ERR_NA)
    return cv_num(Float64(best_pos))
