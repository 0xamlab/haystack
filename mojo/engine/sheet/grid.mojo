"""sheet.grid — workbook model + loader for the extracted-workbook text format.

The staged Python extractor (`scripts/sheet_plane/extract_xlsx.py`) turns one
.xlsx into a deterministic tab-separated text stream; this loader is the only
thing that parses it. Refusal-first: a malformed line, an out-of-range sheet
index, a bad A1 ref, a duplicate cell, or the (corpus-absent) 1904 date system
each refuse the whole workbook with a named status — nothing indexes on
unvalidated input.

Format (fields tab-separated; %25/%09/%0A/%0D escapes inside text fields):

    SHEETWB\t1
    D\t<0|1>                          date1904 flag (1 refuses)
    S\t<sheet name>                   declaration order = sheet index
    N\t<scope>\t<name>\t<refers>      defined name; scope -1 = workbook
    C\t<sheet>\t<ref>\t<t>\t<v>       constant cell; t in n,s,b,e
    F\t<sheet>\t<ref>\t<ftype>\t<formula>\t<ct>\t<cv>
                                      ftype: n | a (array master) | m:<si>
                                      (shared master) | d (dataTable)
    G\t<sheet>\t<ref>\t<si>\t<ct>\t<cv>
                                      shared-formula follower: no formula
                                      text is stored in the file (69.5% of
                                      all corpus formula cells) — it shares
                                      the master's tree shifted by
                                      (Δrow, Δcol) on RELATIVE refs only

Memory: allocation is payload-proportional (≈4 bytes per payload byte across
the parallel arrays) and additionally hard-capped at MAX_WB_CELLS cells /
MAX_WB_NODES formula nodes; past either, the load refuses rather than grows.

Status codes 1300-1319 (package range 1300-1349, see __init__.mojo).

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

from sheet.formula import FNode, NK_UNSUP, parse_formula
from sheet.numio import _bs_str, _parse_number
from sheet.refs import MAX_COLS, MAX_ROWS, pack_coord, parse_a1_cell
from sheet.values import (
    VK_BOOL,
    VK_EMPTY,
    VK_ERR,
    VK_NUM,
    VK_TEXT,
    error_code_of,
)

comptime SHEET_OK: Int = 1300
comptime SHEET_ERR_BAD_MAGIC: Int = 1301
comptime SHEET_ERR_BAD_LINE: Int = 1302
comptime SHEET_ERR_SHEET_INDEX: Int = 1303
comptime SHEET_ERR_BAD_REF: Int = 1304
comptime SHEET_ERR_DATE1904: Int = 1305
comptime SHEET_ERR_TOO_LARGE: Int = 1306
comptime SHEET_ERR_DUP_CELL: Int = 1307
comptime SHEET_ERR_EMPTY: Int = 1308

comptime MAX_WB_CELLS: Int = 33554432  # 2^25; ~120 B/cell peak ==> refuse, never balloon
comptime MAX_WB_NODES: Int = 67108864  # 2^26 formula IR nodes
comptime MAX_WB_SHEETS: Int = 1024
comptime MAX_WB_NAMES: Int = 1048576

# Formula-cell kinds (Workbook.c_ftype)
comptime FT_NONE: Int = 0  # constant cell
comptime FT_NORMAL: Int = 1
comptime FT_ARRAY: Int = 2
comptime FT_SHARED_MASTER: Int = 3
comptime FT_SHARED_FOLLOWER: Int = 4
comptime FT_DATATABLE: Int = 5


struct Workbook(Copyable, Movable):
    """Loaded workbook: parallel per-cell arrays plus two sorted permutations
    (row-major and column-major) for range scans and point lookups. Formula
    IR lives in one shared arena (`nodes` + `pool`); a cell keeps its root."""

    var sheet_names: List[String]
    # defined names
    var name_folded: List[String]
    var name_scope: List[Int]
    var name_root: List[Int]
    # per-cell parallel arrays
    var c_sheet: List[Int]
    var c_coord: List[Int]  # row * MAX_COLS + col
    var c_kind: List[Int]  # constant kind (VK_*) or VK_EMPTY for formula cells
    var c_num: List[Float64]
    var c_text: List[String]
    var c_err: List[Int]
    var c_froot: List[Int]  # -1 for constants
    var c_ftype: List[Int]
    var c_fdr: List[Int]  # shared-follower row delta
    var c_fdc: List[Int]
    var c_ftext: List[String]  # formula text for diagnostics ("" on followers)
    # cached (Excel-stored) value for formula cells: kind 0 = none
    var c_ct: List[Int]  # 0 none, else VK_NUM / VK_TEXT / VK_BOOL / VK_ERR
    var c_cnum: List[Float64]
    var c_ctext: List[String]
    var c_cerr: List[Int]
    # formula IR arena
    var nodes: List[FNode]
    var pool: List[Int]
    # sorted permutations + per-sheet slice starts (built by _finish)
    var perm_row: List[Int]  # by (sheet, row, col)
    var perm_col: List[Int]  # by (sheet, col, row)
    var sheet_row_start: List[Int]  # len = sheets + 1
    var sheet_col_start: List[Int]
    var formula_cells: List[Int]  # indices with froot >= 0, load order

    def __init__(out self):
        self.sheet_names = List[String]()
        self.name_folded = List[String]()
        self.name_scope = List[Int]()
        self.name_root = List[Int]()
        self.c_sheet = List[Int]()
        self.c_coord = List[Int]()
        self.c_kind = List[Int]()
        self.c_num = List[Float64]()
        self.c_text = List[String]()
        self.c_err = List[Int]()
        self.c_froot = List[Int]()
        self.c_ftype = List[Int]()
        self.c_fdr = List[Int]()
        self.c_fdc = List[Int]()
        self.c_ftext = List[String]()
        self.c_ct = List[Int]()
        self.c_cnum = List[Float64]()
        self.c_ctext = List[String]()
        self.c_cerr = List[Int]()
        self.nodes = List[FNode]()
        self.pool = List[Int]()
        self.perm_row = List[Int]()
        self.perm_col = List[Int]()
        self.sheet_row_start = List[Int]()
        self.sheet_col_start = List[Int]()
        self.formula_cells = List[Int]()

    def n_cells(self) -> Int:
        return len(self.c_coord)

    def find_cell(self, sheet: Int, row: Int, col: Int) -> Int:
        """Cell index at (sheet, row, col); -1 when nothing is stored there.
        Binary search over the row-major permutation slice of `sheet`."""
        if sheet < 0 or sheet >= len(self.sheet_names):
            return -1
        if row < 0 or row >= MAX_ROWS or col < 0 or col >= MAX_COLS:
            return -1
        var target = pack_coord(row, col)
        var lo = self.sheet_row_start[sheet]
        var hi = self.sheet_row_start[sheet + 1]
        while lo < hi:
            var mid = (lo + hi) // 2
            var c = self.c_coord[self.perm_row[mid]]
            if c < target:
                lo = mid + 1
            elif c > target:
                hi = mid
            else:
                return self.perm_row[mid]
        return -1

    def used_extent(self, sheet: Int, mut max_row: Int, mut max_col: Int) -> Bool:
        """Last stored row and column of a sheet — its USED range. Excel never
        evaluates past it, and neither should array materialisation: without
        this, one `LOOKUP(2,1/(F:F<>""),F:F)` would materialise 1,048,576
        elements per call. The row-major index is sorted, so the last entry of
        the sheet's slice carries the largest row; the column-major index the
        largest column. False when the sheet has no stored cells."""
        if sheet < 0 or sheet >= len(self.sheet_names):
            return False
        var a = self.sheet_row_start[sheet]
        var b = self.sheet_row_start[sheet + 1]
        if b <= a:
            return False
        max_row = self.c_coord[self.perm_row[b - 1]] // MAX_COLS
        var ca = self.sheet_col_start[sheet]
        var cb = self.sheet_col_start[sheet + 1]
        if cb <= ca:
            return False
        max_col = self.c_coord[self.perm_col[cb - 1]] % MAX_COLS
        return True

    def row_slice_bounds(self, sheet: Int, coord_lo: Int, coord_hi: Int, mut lo: Int, mut hi: Int) -> Bool:
        """[lo, hi) into perm_row covering coords in [coord_lo, coord_hi]."""
        if sheet < 0 or sheet >= len(self.sheet_names):
            return False
        var a = self.sheet_row_start[sheet]
        var b = self.sheet_row_start[sheet + 1]
        # lower bound for coord_lo
        var l = a
        var h = b
        while l < h:
            var mid = (l + h) // 2
            if self.c_coord[self.perm_row[mid]] < coord_lo:
                l = mid + 1
            else:
                h = mid
        lo = l
        # upper bound for coord_hi
        l = lo
        h = b
        while l < h:
            var mid = (l + h) // 2
            if self.c_coord[self.perm_row[mid]] <= coord_hi:
                l = mid + 1
            else:
                h = mid
        hi = l
        return True

    def col_slice_bounds(self, sheet: Int, key_lo: Int, key_hi: Int, mut lo: Int, mut hi: Int) -> Bool:
        """[lo, hi) into perm_col covering col-major keys (col*MAX_ROWS+row)
        in [key_lo, key_hi]."""
        if sheet < 0 or sheet >= len(self.sheet_names):
            return False
        var a = self.sheet_col_start[sheet]
        var b = self.sheet_col_start[sheet + 1]
        var l = a
        var h = b
        while l < h:
            var mid = (l + h) // 2
            var idx = self.perm_col[mid]
            var key = (self.c_coord[idx] % MAX_COLS) * MAX_ROWS + self.c_coord[idx] // MAX_COLS
            if key < key_lo:
                l = mid + 1
            else:
                h = mid
        lo = l
        l = lo
        h = b
        while l < h:
            var mid = (l + h) // 2
            var idx = self.perm_col[mid]
            var key = (self.c_coord[idx] % MAX_COLS) * MAX_ROWS + self.c_coord[idx] // MAX_COLS
            if key <= key_hi:
                l = mid + 1
            else:
                h = mid
        hi = l
        return True

    def resolve_name(self, folded: String, sheet: Int) -> Int:
        """Defined-name lookup: sheet scope wins over workbook scope. Returns
        the parsed refers-to root node, or -1 when the name does not exist."""
        var global_hit = -1
        for i in range(len(self.name_folded)):
            if self.name_folded[i] == folded:
                if self.name_scope[i] == sheet:
                    return self.name_root[i]
                if self.name_scope[i] == -1 and global_hit < 0:
                    global_hit = self.name_root[i]
        return global_hit


struct LoadResult(Copyable, Movable):
    var status: Int
    var line_no: Int  # 1-based line of the refusal, 0 when ok
    var wb: Workbook

    def __init__(out self):
        self.status = SHEET_OK
        self.line_no = 0
        self.wb = Workbook()


def _unescape(bs: Span[UInt8, _], start: Int, end: Int) -> String:
    """Decode %XX escapes (the extractor emits %09 %0A %0D %25 only, but any
    hex pair decodes). A malformed escape passes through literally."""
    var buf = List[UInt8]()
    var i = start
    while i < end:
        var b = Int(bs[i])
        if b == 37 and i + 2 < end:
            var h1 = _hex(Int(bs[i + 1]))
            var h2 = _hex(Int(bs[i + 2]))
            if h1 >= 0 and h2 >= 0:
                buf.append(UInt8(h1 * 16 + h2))
                i += 3
                continue
        buf.append(UInt8(b))
        i += 1
    return _bs_str(buf)


def _hex(b: Int) -> Int:
    if b >= 48 and b <= 57:
        return b - 48
    if b >= 97 and b <= 102:
        return b - 87
    if b >= 65 and b <= 70:
        return b - 55
    return -1


def _radix_sort_perm(keys: List[Int]) -> List[Int]:
    """Stable LSD radix sort (3 x 16-bit digits, keys < 2^45) returning the
    permutation. O(n) time, two n-length Int buffers."""
    var n = len(keys)
    var perm = List[Int]()
    for i in range(n):
        perm.append(i)
    var tmp = List[Int]()
    tmp.resize(n, 0)
    var counts = List[Int]()
    for pass_i in range(3):
        var shift = pass_i * 16
        counts.clear()
        counts.resize(65536, 0)
        for i in range(n):
            var d = (keys[perm[i]] >> shift) & 65535
            counts[d] += 1
        var total = 0
        for d in range(65536):
            var c = counts[d]
            counts[d] = total
            total += c
        for i in range(n):
            var d = (keys[perm[i]] >> shift) & 65535
            tmp[counts[d]] = perm[i]
            counts[d] += 1
        for i in range(n):
            perm[i] = tmp[i]
    return perm^


struct _Line(Copyable, Movable):
    """One split line: field byte-ranges into the payload."""

    var starts: List[Int]
    var ends: List[Int]

    def __init__(out self):
        self.starts = List[Int]()
        self.ends = List[Int]()


def _field_eq(bs: Span[UInt8, _], start: Int, end: Int, lit: String) -> Bool:
    var lb = lit.as_bytes()
    if end - start != len(lb):
        return False
    for i in range(len(lb)):
        if bs[start + i] != lb[i]:
            return False
    return True


def _field_int(bs: Span[UInt8, _], start: Int, end: Int, mut val: Int) -> Bool:
    var i = start
    var neg = False
    if i < end and Int(bs[i]) == 45:
        neg = True
        i += 1
    if i >= end or end - i > 10:
        return False
    var acc = 0
    while i < end:
        var b = Int(bs[i])
        if b < 48 or b > 57:
            return False
        acc = acc * 10 + (b - 48)
        i += 1
    val = -acc if neg else acc
    return True


def load_workbook(text: String) -> LoadResult:
    """Parse the extracted-workbook text format into a Workbook. Refuses with
    a named status and the offending 1-based line number; never crashes and
    never returns a half-loaded workbook as OK.

    @capability load_workbook
    complexity: O(len(text)) + O(cells log cells) for index builds
    counts: none
    @endcapability
    """
    var res = LoadResult()
    var bs = text.as_bytes()
    var n = len(bs)
    if n == 0:
        res.status = SHEET_ERR_EMPTY
        return res^
    # shared-formula registry: parallel lists (sheet, si, cell index)
    var sm_sheet = List[Int]()
    var sm_si = List[Int]()
    var sm_cell = List[Int]()
    # follower fixups: (cell index, si) resolved after the full pass
    var fw_cell = List[Int]()
    var fw_si = List[Int]()

    var line_no = 0
    var pos = 0
    var seen_magic = False
    while pos < n:
        var eol = pos
        while eol < n and Int(bs[eol]) != 10:
            eol += 1
        line_no += 1
        var s = pos
        var e = eol
        if e > s and Int(bs[e - 1]) == 13:
            e -= 1
        pos = eol + 1
        if e == s:
            continue  # blank line
        # split fields on \t
        var f_start = List[Int]()
        var f_end = List[Int]()
        var fs = s
        var i = s
        while i <= e:
            if i == e or Int(bs[i]) == 9:
                f_start.append(fs)
                f_end.append(i)
                fs = i + 1
            i += 1
        var nf = len(f_start)
        if not seen_magic:
            if nf == 2 and _field_eq(bs, f_start[0], f_end[0], "SHEETWB") and _field_eq(
                bs, f_start[1], f_end[1], "1"
            ):
                seen_magic = True
                continue
            res.status = SHEET_ERR_BAD_MAGIC
            res.line_no = line_no
            return res^
        var kind0 = f_start[0]
        var kind1 = f_end[0]
        if kind1 - kind0 != 1:
            res.status = SHEET_ERR_BAD_LINE
            res.line_no = line_no
            return res^
        var k = Int(bs[kind0])
        if k == 68:  # D
            if nf != 2:
                res.status = SHEET_ERR_BAD_LINE
                res.line_no = line_no
                return res^
            if not _field_eq(bs, f_start[1], f_end[1], "0"):
                res.status = SHEET_ERR_DATE1904
                res.line_no = line_no
                return res^
            continue
        if k == 83:  # S
            if nf != 2 or len(res.wb.sheet_names) >= MAX_WB_SHEETS:
                res.status = SHEET_ERR_BAD_LINE if nf != 2 else SHEET_ERR_TOO_LARGE
                res.line_no = line_no
                return res^
            res.wb.sheet_names.append(_unescape(bs, f_start[1], f_end[1]))
            continue
        if k == 78:  # N scope name refers
            if nf != 4 or len(res.wb.name_folded) >= MAX_WB_NAMES:
                res.status = SHEET_ERR_BAD_LINE if nf != 4 else SHEET_ERR_TOO_LARGE
                res.line_no = line_no
                return res^
            var scope = 0
            if not _field_int(bs, f_start[1], f_end[1], scope):
                res.status = SHEET_ERR_BAD_LINE
                res.line_no = line_no
                return res^
            if scope < -1 or scope >= len(res.wb.sheet_names):
                res.status = SHEET_ERR_SHEET_INDEX
                res.line_no = line_no
                return res^
            var nm = _fold_name(_unescape(bs, f_start[2], f_end[2]))
            var refers = _unescape(bs, f_start[3], f_end[3])
            var root = parse_formula(refers, res.wb.sheet_names, res.wb.nodes, res.wb.pool)
            res.wb.name_folded.append(nm^)
            res.wb.name_scope.append(scope)
            res.wb.name_root.append(root)
            continue
        if k == 67 or k == 70 or k == 71:  # C / F / G share sheet+ref parsing
            var want = 5
            if k == 70:
                want = 7
            elif k == 71:
                want = 6
            if nf != want:
                res.status = SHEET_ERR_BAD_LINE
                res.line_no = line_no
                return res^
            if res.wb.n_cells() >= MAX_WB_CELLS or len(res.wb.nodes) >= MAX_WB_NODES:
                res.status = SHEET_ERR_TOO_LARGE
                res.line_no = line_no
                return res^
            var sheet = 0
            if not _field_int(bs, f_start[1], f_end[1], sheet) or sheet < 0 or sheet >= len(
                res.wb.sheet_names
            ):
                res.status = SHEET_ERR_SHEET_INDEX
                res.line_no = line_no
                return res^
            var ref_text = _unescape(bs, f_start[2], f_end[2])
            var pa = parse_a1_cell(ref_text)
            if not pa.ok:
                res.status = SHEET_ERR_BAD_REF
                res.line_no = line_no
                return res^
            var ci = res.wb.n_cells()
            res.wb.c_sheet.append(sheet)
            res.wb.c_coord.append(pack_coord(pa.row, pa.col))
            res.wb.c_kind.append(VK_EMPTY)
            res.wb.c_num.append(0.0)
            res.wb.c_text.append(String(""))
            res.wb.c_err.append(0)
            res.wb.c_froot.append(-1)
            res.wb.c_ftype.append(FT_NONE)
            res.wb.c_fdr.append(0)
            res.wb.c_fdc.append(0)
            res.wb.c_ftext.append(String(""))
            res.wb.c_ct.append(0)
            res.wb.c_cnum.append(0.0)
            res.wb.c_ctext.append(String(""))
            res.wb.c_cerr.append(0)
            if k == 67:  # C sheet ref t v
                if not _store_const(res.wb, ci, bs, f_start[3], f_end[3], f_start[4], f_end[4]):
                    res.status = SHEET_ERR_BAD_LINE
                    res.line_no = line_no
                    return res^
                continue
            if k == 70:  # F sheet ref ftype formula ct cv
                var ft_s = f_start[3]
                var ft_e = f_end[3]
                var ftype = FT_NORMAL
                var si = -1
                if _field_eq(bs, ft_s, ft_e, "n"):
                    ftype = FT_NORMAL
                elif _field_eq(bs, ft_s, ft_e, "a"):
                    ftype = FT_ARRAY
                elif _field_eq(bs, ft_s, ft_e, "d"):
                    ftype = FT_DATATABLE
                elif ft_e - ft_s >= 3 and Int(bs[ft_s]) == 109 and Int(bs[ft_s + 1]) == 58:
                    ftype = FT_SHARED_MASTER
                    if not _field_int(bs, ft_s + 2, ft_e, si) or si < 0:
                        res.status = SHEET_ERR_BAD_LINE
                        res.line_no = line_no
                        return res^
                else:
                    res.status = SHEET_ERR_BAD_LINE
                    res.line_no = line_no
                    return res^
                var ftext = _unescape(bs, f_start[4], f_end[4])
                var root = parse_formula(ftext, res.wb.sheet_names, res.wb.nodes, res.wb.pool)
                res.wb.c_froot[ci] = root
                res.wb.c_ftype[ci] = ftype
                res.wb.c_ftext[ci] = ftext^
                if ftype == FT_SHARED_MASTER:
                    sm_sheet.append(sheet)
                    sm_si.append(si)
                    sm_cell.append(ci)
                if not _store_cached(res.wb, ci, bs, f_start[5], f_end[5], f_start[6], f_end[6]):
                    res.status = SHEET_ERR_BAD_LINE
                    res.line_no = line_no
                    return res^
                res.wb.formula_cells.append(ci)
                continue
            # G sheet ref si ct cv
            var si2 = 0
            if not _field_int(bs, f_start[3], f_end[3], si2) or si2 < 0:
                res.status = SHEET_ERR_BAD_LINE
                res.line_no = line_no
                return res^
            res.wb.c_ftype[ci] = FT_SHARED_FOLLOWER
            fw_cell.append(ci)
            fw_si.append(si2)
            if not _store_cached(res.wb, ci, bs, f_start[4], f_end[4], f_start[5], f_end[5]):
                res.status = SHEET_ERR_BAD_LINE
                res.line_no = line_no
                return res^
            res.wb.formula_cells.append(ci)
            continue
        res.status = SHEET_ERR_BAD_LINE
        res.line_no = line_no
        return res^
    if not seen_magic:
        res.status = SHEET_ERR_BAD_MAGIC
        res.line_no = line_no
        return res^
    if len(res.wb.sheet_names) == 0:
        res.status = SHEET_ERR_EMPTY
        return res^
    # resolve shared followers: master's tree + (Δrow, Δcol)
    for i in range(len(fw_cell)):
        var ci = fw_cell[i]
        var sheet = res.wb.c_sheet[ci]
        var si = fw_si[i]
        var master = -1
        for j in range(len(sm_cell)):
            if sm_sheet[j] == sheet and sm_si[j] == si:
                master = sm_cell[j]
                break
        if master < 0:
            # orphan follower: taint the cell, never the workbook (the census
            # found zero of these, but a truncated extract could produce one)
            var nd = FNode(NK_UNSUP)
            nd.text = String("SHARED_ORPHAN")
            res.wb.nodes.append(nd^)
            res.wb.c_froot[ci] = len(res.wb.nodes) - 1
            continue
        res.wb.c_froot[ci] = res.wb.c_froot[master]
        var mc = res.wb.c_coord[master]
        var cc = res.wb.c_coord[ci]
        res.wb.c_fdr[ci] = cc // MAX_COLS - mc // MAX_COLS
        res.wb.c_fdc[ci] = cc % MAX_COLS - mc % MAX_COLS
    # build sorted permutations; refuse duplicates
    var nc = res.wb.n_cells()
    var row_keys = List[Int]()
    var col_keys = List[Int]()
    for i in range(nc):
        var sh = res.wb.c_sheet[i]
        var coord = res.wb.c_coord[i]
        # 3x16-bit radix passes need keys < 2^48; MAX_WB_SHEETS(2^10) *
        # 2^34 coords would overflow, so sheets get their own high bits and
        # we sort per composite key built to fit: sheet(10) + coord(34) = 44.
        row_keys.append(sh * (MAX_ROWS * MAX_COLS) + coord)
        col_keys.append(
            sh * (MAX_ROWS * MAX_COLS) + (coord % MAX_COLS) * MAX_ROWS + coord // MAX_COLS
        )
    res.wb.perm_row = _radix_sort_perm(row_keys)
    res.wb.perm_col = _radix_sort_perm(col_keys)
    for i in range(1, nc):
        if row_keys[res.wb.perm_row[i]] == row_keys[res.wb.perm_row[i - 1]]:
            res.status = SHEET_ERR_DUP_CELL
            return res^
    # per-sheet slice starts
    var n_sheets = len(res.wb.sheet_names)
    res.wb.sheet_row_start.resize(n_sheets + 1, 0)
    res.wb.sheet_col_start.resize(n_sheets + 1, 0)
    var p = 0
    for sh in range(n_sheets):
        res.wb.sheet_row_start[sh] = p
        while p < nc and res.wb.c_sheet[res.wb.perm_row[p]] == sh:
            p += 1
    res.wb.sheet_row_start[n_sheets] = p
    p = 0
    for sh in range(n_sheets):
        res.wb.sheet_col_start[sh] = p
        while p < nc and res.wb.c_sheet[res.wb.perm_col[p]] == sh:
            p += 1
    res.wb.sheet_col_start[n_sheets] = p
    return res^


def _fold_name(s: String) -> String:
    var bsx = s.as_bytes()
    var buf = List[UInt8]()
    for i in range(len(bsx)):
        var b = Int(bsx[i])
        if b >= 65 and b <= 90:
            b += 32
        buf.append(UInt8(b))
    return _bs_str(buf)


def _store_const(
    mut wb: Workbook, ci: Int, bs: Span[UInt8, _], t_s: Int, t_e: Int, v_s: Int, v_e: Int
) -> Bool:
    if t_e - t_s != 1:
        return False
    var t = Int(bs[t_s])
    if t == 110:  # n
        var vtext = _unescape(bs, v_s, v_e)
        var v: Float64 = 0.0
        if not _parse_number(vtext, v):
            return False
        wb.c_kind[ci] = VK_NUM
        wb.c_num[ci] = v
        return True
    if t == 115:  # s
        wb.c_kind[ci] = VK_TEXT
        wb.c_text[ci] = _unescape(bs, v_s, v_e)
        return True
    if t == 98:  # b
        if _field_eq(bs, v_s, v_e, "1"):
            wb.c_kind[ci] = VK_BOOL
            wb.c_num[ci] = 1.0
            return True
        if _field_eq(bs, v_s, v_e, "0"):
            wb.c_kind[ci] = VK_BOOL
            wb.c_num[ci] = 0.0
            return True
        return False
    if t == 101:  # e
        var code = error_code_of(_unescape(bs, v_s, v_e))
        if code == 0:
            return False
        wb.c_kind[ci] = VK_ERR
        wb.c_err[ci] = code
        return True
    return False


def _store_cached(
    mut wb: Workbook, ci: Int, bs: Span[UInt8, _], t_s: Int, t_e: Int, v_s: Int, v_e: Int
) -> Bool:
    if t_e - t_s != 1:
        return False
    var t = Int(bs[t_s])
    if t == 122:  # z: no cached value
        wb.c_ct[ci] = 0
        return True
    if t == 110:
        var vtext = _unescape(bs, v_s, v_e)
        var v: Float64 = 0.0
        if not _parse_number(vtext, v):
            return False
        wb.c_ct[ci] = VK_NUM
        wb.c_cnum[ci] = v
        return True
    if t == 115:
        wb.c_ct[ci] = VK_TEXT
        wb.c_ctext[ci] = _unescape(bs, v_s, v_e)
        return True
    if t == 98:
        if _field_eq(bs, v_s, v_e, "1"):
            wb.c_ct[ci] = VK_BOOL
            wb.c_cnum[ci] = 1.0
            return True
        if _field_eq(bs, v_s, v_e, "0"):
            wb.c_ct[ci] = VK_BOOL
            wb.c_cnum[ci] = 0.0
            return True
        return False
    if t == 101:
        var lit = _unescape(bs, v_s, v_e)
        var code = error_code_of(lit)
        if code == 0:
            # modern cached error (#SPILL!, #CALC!, ...): keep the workbook,
            # mark "cached error we cannot produce" via VK_ERR code 0 — the
            # comparator counts these as unsupported-comparison, named.
            wb.c_ct[ci] = VK_ERR
            wb.c_cerr[ci] = 0
            wb.c_ctext[ci] = lit^
            return True
        wb.c_ct[ci] = VK_ERR
        wb.c_cerr[ci] = code
        return True
    return False
