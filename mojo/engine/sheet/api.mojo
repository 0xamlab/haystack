"""sheet.api — flat public drivers: recalc a workbook and compare every
formula cell against the value Excel cached for it.

The comparison NEVER hides a wrong answer behind a loose tolerance:

  * numbers match EXACTLY (Float64 equality on the correctly-rounded parse of
    the 17-significant-digit cached <v>), or fall into one of two separately
    counted near buckets that are NEVER merged into exact: `matched_tol`
    (relative 1e-9 — last-ulps divergence in STDEV-class arithmetic) and
    `matched_snap` (cached is EXACTLY 0.0 and the recalc is within 1e-6 —
    Excel's documented cosmetic near-zero snap on +/- chains, measured live
    on bluefin: cached 0.0 vs an exact fp sum of -1.16e-10). A genuinely
    wrong answer fails all three: the anti-vacuity suite proves it;
    everything else is a MISMATCH and the first few are quoted verbatim;
  * text/bool must be byte-identical / equal;
  * a cached error only matches the SAME typed error;
  * an unimplemented function taints its cell (and its dependents) into an
    UNSUPPORTED bucket counted BY NAME — the uncovered tail is a table, never
    a silent skip; TODAY/NOW/RAND/RANDBETWEEN go to a volatile bucket because
    their cached values are irreproducible by construction;
  * cells on (or downstream of) a dependency cycle are counted and the first
    cycles name their cells.

Status codes: reuses grid's 1300-1319 and engine's 1320-1321.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_sheet_functions.mojo
benchmark: benchmarks/mojo_benchmarks/bench_sheet_plane.mojo
docs: docs/mojo/sheet-plane.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

from sheet.engine import RECALC_OK, RecalcOutcome, recalc_workbook
from sheet.grid import SHEET_OK, load_workbook
from sheet.numio import _bs_str
from sheet.refs import MAX_COLS, a1_of, parse_a1_cell
from sheet.values import (
    VK_BOOL,
    VK_CYCLE,
    VK_ERR,
    VK_NUM,
    VK_TEXT,
    VK_UNSUP,
    CellValue,
    error_name,
    fold_ascii,
    value_to_display,
)
from std.math import abs as fabs


comptime REL_TOL: Float64 = 1e-9
comptime ABS_TOL: Float64 = 1e-12
comptime SNAP_TOL: Float64 = 1e-6
comptime MAX_SAMPLES: Int = 8


struct SheetRecalcReport(Copyable, Movable):
    """Corpus-validation report for one workbook. `status` is SHEET_OK/1320
    on success, a 1300-range loader refusal, or 1321 (budget exhausted,
    counts are partial and `not_evaluated` says how partial)."""

    var status: Int
    var load_line: Int
    var sheets: Int
    var cells: Int
    var formula_cells: Int
    var evaluated: Int
    var not_evaluated: Int
    var no_cached: Int
    var matched_exact: Int
    var matched_tol: Int
    var matched_snap: Int
    var error_matched: Int
    var mismatched: Int
    var error_mismatched: Int
    var unsupported: Int
    var volatile_cells: Int
    var cycle_cells: Int
    var cycle_count: Int
    var unsupported_compare: Int
    var ops: Int
    var max_chain: Int
    var cycle_names: String
    var unsupported_names: String
    var mismatch_samples: String

    def __init__(out self):
        self.status = 0
        self.load_line = 0
        self.sheets = 0
        self.cells = 0
        self.formula_cells = 0
        self.evaluated = 0
        self.not_evaluated = 0
        self.no_cached = 0
        self.matched_exact = 0
        self.matched_tol = 0
        self.matched_snap = 0
        self.error_matched = 0
        self.mismatched = 0
        self.error_mismatched = 0
        self.unsupported = 0
        self.volatile_cells = 0
        self.cycle_cells = 0
        self.cycle_count = 0
        self.unsupported_compare = 0
        self.ops = 0
        self.max_chain = 0
        self.cycle_names = String("")
        self.unsupported_names = String("")
        self.mismatch_samples = String("")


def _is_volatile_name(name: String) -> Bool:
    return name == "TODAY" or name == "NOW" or name == "RAND" or name == "RANDBETWEEN"


def _tally(mut names: List[String], mut counts: List[Int], name: String):
    for i in range(len(names)):
        if names[i] == name:
            counts[i] += 1
            return
    if len(names) < 512:
        names.append(name)
        counts.append(1)


def _num_close(a: Float64, b: Float64) -> Bool:
    var d = fabs(a - b)
    if d <= ABS_TOL:
        return True
    var scale = fabs(a)
    if fabs(b) > scale:
        scale = fabs(b)
    return d <= REL_TOL * scale


def _trunc80(s: String) -> String:
    var bs = s.as_bytes()
    if len(bs) <= 80:
        return s
    var cut = 80
    while cut > 0 and Int(bs[cut]) & 192 == 128:
        cut -= 1  # never split a UTF-8 sequence
    var buf = List[UInt8]()
    for i in range(cut):
        buf.append(bs[i])
    var out = _bs_str(buf)
    out += "..."
    return out^


def sheet_recalc_report(workbook_text: String, budget_ops: Int) -> SheetRecalcReport:
    """Load an extracted workbook, recalc every formula cell from the input
    cells, and compare cell-by-cell against Excel's cached values. Refusal
    on malformed input reports the loader status and offending line; junk
    input never crashes.

    @capability sheet_recalc_report
    complexity: O(payload + charged recalc work), budget-bounded
    counts: none
    @endcapability
    """
    var rep = SheetRecalcReport()
    var lr = load_workbook(workbook_text)
    rep.status = lr.status
    rep.load_line = lr.line_no
    if lr.status != SHEET_OK:
        return rep^
    rep.sheets = len(lr.wb.sheet_names)
    rep.cells = lr.wb.n_cells()
    rep.formula_cells = len(lr.wb.formula_cells)
    var out = recalc_workbook(lr.wb, budget_ops)
    rep.status = out.status
    rep.evaluated = out.evaluated
    rep.not_evaluated = out.not_evaluated
    rep.ops = out.ops
    rep.max_chain = out.max_stack
    rep.cycle_count = out.cycle_count
    for i in range(len(out.cycle_names)):
        if i > 0:
            rep.cycle_names += " | "
        rep.cycle_names += out.cycle_names[i]
    var unames = List[String]()
    var ucounts = List[Int]()
    var samples = 0
    for i in range(len(lr.wb.formula_cells)):
        var ci = lr.wb.formula_cells[i]
        var v = out.values[ci].copy()
        # a budget stop leaves cells unevaluated: they are already counted in
        # not_evaluated and must join NO other bucket. A finished cell can
        # never be VK_EMPTY (finalize maps empty to the number 0), so the
        # default-initialised sentinel is unambiguous.
        if v.kind == 0:
            continue
        if v.kind == VK_CYCLE:
            rep.cycle_cells += 1
            continue
        if v.kind == VK_UNSUP:
            if _is_volatile_name(v.text):
                rep.volatile_cells += 1
            else:
                rep.unsupported += 1
                _tally(unames, ucounts, v.text)
            continue
        var ct = lr.wb.c_ct[ci]
        if ct == 0:
            rep.no_cached += 1
            continue
        if ct == VK_ERR and lr.wb.c_cerr[ci] == 0:
            # a modern cached error literal (#SPILL!, ...) we cannot produce
            rep.unsupported_compare += 1
            _tally(unames, ucounts, lr.wb.c_ctext[ci])
            continue
        var ok_exact = False
        var ok_tol = False
        var ok_snap = False
        var err_hit = False
        var err_miss = False
        if ct == VK_NUM:
            if v.kind == VK_NUM and v.num == lr.wb.c_cnum[ci]:
                ok_exact = True
            elif v.kind == VK_NUM and _num_close(v.num, lr.wb.c_cnum[ci]):
                ok_tol = True
            elif v.kind == VK_NUM and lr.wb.c_cnum[ci] == 0.0 and fabs(v.num) <= SNAP_TOL:
                ok_snap = True
        elif ct == VK_TEXT:
            if v.kind == VK_TEXT and v.text == lr.wb.c_ctext[ci]:
                ok_exact = True
        elif ct == VK_BOOL:
            if v.kind == VK_BOOL and (v.num != 0.0) == (lr.wb.c_cnum[ci] != 0.0):
                ok_exact = True
        elif ct == VK_ERR:
            if v.kind == VK_ERR and v.err == lr.wb.c_cerr[ci]:
                err_hit = True
            else:
                err_miss = True
        if ok_exact:
            rep.matched_exact += 1
            continue
        if ok_tol:
            rep.matched_tol += 1
            continue
        if ok_snap:
            rep.matched_snap += 1
            continue
        if err_hit:
            rep.error_matched += 1
            continue
        if err_miss:
            rep.error_mismatched += 1
        else:
            rep.mismatched += 1
        if samples < MAX_SAMPLES:
            samples += 1
            var s = String("")
            var sh = lr.wb.c_sheet[ci]
            if sh >= 0 and sh < len(lr.wb.sheet_names):
                s += lr.wb.sheet_names[sh]
            s += "!"
            s += a1_of(lr.wb.c_coord[ci] // MAX_COLS, lr.wb.c_coord[ci] % MAX_COLS)
            s += " f="
            if lr.wb.c_ftext[ci].byte_length() > 0:
                s += _trunc80(lr.wb.c_ftext[ci])
            else:
                s += "(shared follower)"
            s += " cached="
            if ct == VK_NUM:
                s += String(lr.wb.c_cnum[ci])
            elif ct == VK_TEXT:
                s += _trunc80(lr.wb.c_ctext[ci])
            elif ct == VK_BOOL:
                s += "TRUE" if lr.wb.c_cnum[ci] != 0.0 else "FALSE"
            else:
                s += error_name(lr.wb.c_cerr[ci])
            s += " got="
            s += _trunc80(value_to_display(v))
            if rep.mismatch_samples.byte_length() > 0:
                rep.mismatch_samples += " | "
            rep.mismatch_samples += s
    # uncovered tail, counted by name
    for i in range(len(unames)):
        if i > 0:
            rep.unsupported_names += ","
        rep.unsupported_names += unames[i]
        rep.unsupported_names += ":"
        rep.unsupported_names += String(ucounts[i])
    return rep^


struct SheetCellResult(Copyable, Movable):
    """One recalculated cell for the hand-checkable suites: `kind` is the
    VK_* of the result, with the error name spelled out."""

    var status: Int
    var found: Bool
    var kind: Int
    var num: Float64
    var text: String
    var err_name: String

    def __init__(out self):
        self.status = 0
        self.found = False
        self.kind = 0
        self.num = 0.0
        self.text = String("")
        self.err_name = String("")


def sheet_eval_cell(
    workbook_text: String, sheet_name: String, ref_text: String, budget_ops: Int
) -> SheetCellResult:
    """Recalc the workbook and return the computed value of one cell,
    addressed by sheet name (case-insensitive) and A1 ref. `found` is False
    when the workbook refused to load, the sheet/ref does not parse, or no
    such cell is stored.

    @capability sheet_eval_cell
    complexity: O(payload + charged recalc work), budget-bounded
    counts: none
    @endcapability
    """
    var res = SheetCellResult()
    var lr = load_workbook(workbook_text)
    res.status = lr.status
    if lr.status != SHEET_OK:
        return res^
    var pa = parse_a1_cell(ref_text)
    if not pa.ok:
        return res^
    var sheet = -1
    var folded = fold_ascii(sheet_name)
    for i in range(len(lr.wb.sheet_names)):
        if fold_ascii(lr.wb.sheet_names[i]) == folded:
            sheet = i
            break
    if sheet < 0:
        return res^
    var ci = lr.wb.find_cell(sheet, pa.row, pa.col)
    if ci < 0:
        return res^
    var out = recalc_workbook(lr.wb, budget_ops)
    res.status = out.status
    res.found = True
    var v = CellValue()
    if lr.wb.c_froot[ci] >= 0:
        v = out.values[ci].copy()
    else:
        # constant cell: report the stored value
        v.kind = lr.wb.c_kind[ci]
        v.num = lr.wb.c_num[ci]
        v.text = lr.wb.c_text[ci]
        v.err = lr.wb.c_err[ci]
    res.kind = v.kind
    res.num = v.num
    res.text = v.text
    if v.kind == VK_ERR:
        res.err_name = error_name(v.err)
    elif v.kind == VK_UNSUP:
        res.err_name = v.text
    return res^
