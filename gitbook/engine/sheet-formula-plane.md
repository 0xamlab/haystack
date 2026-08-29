---
icon: table-cells
description: Recalculate real spreadsheet formulas — a tokenizer, dependency graph, cycle detection and 48 census-ranked functions, run as compiled kernels inside the runtime that ships with the SDK.
---

# Spreadsheet formula plane

Recalculates a workbook's formula cells from its input cells: tokenize, parse to a flat
formula tree, walk the dependency graph in topological order, evaluate, and — where the
workbook carries a value Excel itself cached for that formula — compare against it. All of
it runs as compiled kernels inside the runtime that ships with the SDK; there is nothing to
start and nothing to install separately.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# a two-cell input and one formula, in the plane's tab-separated workbook format
# (see "The workbook text format" below)
workbook = (
    "SHEETWB\t1\nD\t0\nS\tSheet1\n"
    "C\t0\tA1\tn\t2\n"
    "C\t0\tA2\tn\t3\n"
    "F\t0\tA3\tn\tSUM(A1:A2)\tn\t5\n"     # formula, plus the value Excel cached for it
)

cell = runtime.execute("sheet.api", "sheet_eval_cell",
                       [workbook, "Sheet1", "A3", 100000])["result"]

cell["found"]    # True
cell["kind"]     # 1 — VK_NUM
cell["num"]      # 5.0
cell["status"]   # 1320 — RECALC_OK; the loader's own 1300 (SHEET_OK) is overwritten by
                 # the recalc status once loading succeeds ("Every refusal names itself" below)
```

`sheet_eval_cell` recalculates the whole workbook and returns one cell's value, addressed by
sheet name and A1 reference. It is the entry point for "what does this formula actually
evaluate to" on a workbook you already have in hand.

## Recalculating and comparing at once

The plane's other entry point, `sheet_recalc_report`, recalculates every formula cell and — for
every cell an `.xlsx` file also carries Excel's own last-computed value for — compares against
it. An `.xlsx` stores both the formula AND the value Excel cached for it, so a real workbook is
its own ground truth: correctness validation runs at corpus scale, with no LLM, no judge, and
no hand-written expected value.

{% tabs %}
{% tab title="Python" %}
```python
report = runtime.execute("sheet.api", "sheet_recalc_report", [workbook, 100000])["result"]

report["status"]          # 1320 — RECALC_OK
report["formula_cells"]   # 1
report["matched_exact"]   # 1 — the recalculated A3 equals the cached 5 exactly
report["mismatched"]      # 0
```
{% endtab %}

{% tab title="TypeScript" %}
```ts
import { MojoRuntime } from "algenta-sdk";

const runtime = new MojoRuntime();

const workbook =
  "SHEETWB\t1\nD\t0\nS\tSheet1\n" +
  "C\t0\tA1\tn\t2\n" +
  "C\t0\tA2\tn\t3\n" +
  "F\t0\tA3\tn\tSUM(A1:A2)\tn\t5\n";

const { result: cell } = await runtime.execute("sheet.api", "sheet_eval_cell", [
  workbook, "Sheet1", "A3", 100000,
]) as { result: { found: boolean; kind: number; num: number; status: number } };

cell.found;    // true
cell.kind;     // 1 — VK_NUM
cell.num;      // 5.0

const { result: report } = await runtime.execute("sheet.api", "sheet_recalc_report", [
  workbook, 100000,
]) as { result: { status: number; formula_cells: number; matched_exact: number; mismatched: number } };

report.status;          // 1320 — RECALC_OK
report.formula_cells;   // 1
report.matched_exact;   // 1
report.mismatched;      // 0
```
{% endtab %}
{% endtabs %}

The comparator never hides a wrong answer behind a loose tolerance. Numbers must match
EXACTLY — float64 equality on the correctly-rounded parse of the cached, 17-significant-digit
value — or fall into one of two SEPARATELY counted near buckets that are never merged into
`matched_exact`: `matched_tol` (relative 1e-9, for last-ulp divergence in STDEV-class
arithmetic) and `matched_snap` (the cached value is exactly `0.0` and the recalculation is
within 1e-6 — Excel's own documented cosmetic near-zero snap on plus/minus chains). Everything
else is `mismatched`, and a report's buckets are proven to sum to the formula-cell count, so a
cell cannot silently vanish from every one of them.

{% hint style="info" %}
**A planted wrong answer is caught, not swallowed by a bucket.** A cached value of `31` against
a real answer of `30` lands as one `mismatched` cell — not `matched_tol`, and a cached `0` next
to a genuinely computed `0.5` is `mismatched`, not `matched_snap`. The tolerance and snap
buckets exist for two specific, real numerical effects, not as a general amnesty.
{% endhint %}

## Errors propagate as typed values

`#DIV/0!`, `#REF!`, `#VALUE!`, `#N/A`, `#NAME?`, `#NUM!` and `#NULL!` are typed values that flow
through a formula chain exactly the way Excel's own error propagation does, and `IFERROR` can
catch them:

```python
workbook_err = (
    "SHEETWB\t1\nD\t0\nS\tS\n"
    "C\t0\tA1\tn\t1\n"
    "F\t0\tB1\tn\tA1/0\te\t#DIV/0!\n"
    "F\t0\tB2\tn\tB1+1\te\t#DIV/0!\n"
    "F\t0\tB3\tn\tSUM(B1:B2)\te\t#DIV/0!\n"
    "F\t0\tB4\tn\tIFERROR(B3,\"caught\")\ts\tcaught\n"
)
r = runtime.execute("sheet.api", "sheet_recalc_report", [workbook_err, 100000])["result"]
r["error_matched"]   # 3 — B1, B2 and B3 all cached #DIV/0!, and all three reproduce it
r["matched_exact"]   # 1 — B4's IFERROR catches it and returns "caught"
r["mismatched"]      # 0
```

`IF`, `IFERROR` and `CHOOSE` are lazy: `IF(TRUE,1,1/0)` evaluates to `1` without ever
evaluating the untaken `1/0` branch.

## Cycles name their cells

A circular reference is refused rather than crashing or spinning, and the refusal names the
cycle rather than reporting a bare count:

```python
workbook_cycle = (
    "SHEETWB\t1\nD\t0\nS\tModel\n"
    "F\t0\tA1\tn\tB1+1\tn\t0\n"
    "F\t0\tB1\tn\tA1*2\tn\t0\n"
    "F\t0\tK3\tn\tK4-$K$3\tn\t5\n"
    "C\t0\tK4\tn\t7\n"
)
r = runtime.execute("sheet.api", "sheet_recalc_report", [workbook_cycle, 100000])["result"]
r["cycle_count"]   # 2 — the mutual A1<->B1 cycle, and K3's self-cycle
r["cycle_cells"]   # 3
r["cycle_names"]   # "Model!A1 -> Model!B1 -> Model!A1 | Model!K3 -> Model!K3"
```

Live iterative-calculation financial models do carry real circular references on purpose;
this plane reports the cycle by name instead of guessing an answer for it.

## An unimplemented function taints its cell, by name

A function the plane does not implement does not stop the recalculation or fabricate a
plausible-looking number: it taints its own cell — and every cell that depends on it — into an
`UNSUPPORTED` bucket, counted by the function's name:

```python
workbook_unsup = "SHEETWB\t1\nD\t0\nS\tS\nF\t0\tA1\tn\tTEXT(1,\"0.00\")\tn\t1\n"
r = runtime.execute("sheet.api", "sheet_recalc_report", [workbook_unsup, 100000])["result"]
r["unsupported"]         # 1
r["unsupported_names"]   # "TEXT:1"
```

`TODAY`, `NOW`, `RAND` and `RANDBETWEEN` land in a separate `volatile_cells` bucket instead —
their cached values are irreproducible by construction, which is a different fact from "not
implemented."

## What is implemented

48 functions, added in strict census-frequency order across four benchmark corpora
(9,848,617 formula cells): `OFFSET`, `ROW`, `MIN`, `IF`, `SUM`, `VLOOKUP`, `IFERROR`,
`COUNTIFS`, `TIME`, `INDIRECT`, `AND`, `MAX`, `AVERAGE`, `TEXTAFTER` — the top 14 already cover
90% of real formula cells — then `ABS`, `STDEV`, `YEAR`, `COUNTIF`, `INDEX`, `MATCH`, `MONTH`,
`SUMIF`, `RANK` (the 95% point), `COLUMN`, and census ranks 24-48: `WEEKDAY`, `INT`, `LEFT`,
`EDATE`, `SUBSTITUTE`, `EOMONTH`, `SLN`, `ROUNDUP`, `VALUE`, `SUMPRODUCT`, `SUMIFS`, `DAYS`,
`LOOKUP`, `LARGE`, `RIGHT`, `LEN`, `OR`, `ROWS`, `ISNUMBER`, `CHOOSE`, `ROUNDDOWN`, `ISBLANK`,
`DATE`. `TEXT` (census rank 31) is a deliberate skip — it needs a number-format engine — and
stays in the counted `unsupported` tail rather than a silent gap.

`LOOKUP`'s search/result vectors, `INDEX`'s array and `MATCH`'s lookup vector take **no
implicit intersection**: a computed operand inside one of those slots stays an array rather
than collapsing to the calling formula's own row, which is the failure mode that makes the
common "last non-blank" idiom (`LOOKUP(2,1/($A$3:$A$7<>""),$A$3:$A$7)`) answer a different cell
per copy if it is not handled.

## The workbook text format

`sheet_eval_cell` and `sheet_recalc_report` both take a workbook as one tab-separated text
block, not raw `.xlsx` bytes. The lines that matter for hand-built input:

| Line | Fields | Meaning |
| --- | --- | --- |
| `SHEETWB` | `1` | required first line (a version marker) |
| `D` | `0` or `1` | the 1904 date system flag — `1` refuses the whole workbook (no corpus workbook uses it) |
| `S` | `<sheet name>` | declares one sheet; declaration order is its sheet index |
| `C` | `<sheet> <ref> <t> <v>` | a constant cell; `t` is `n` (number), `s` (text), `b` (bool) or `e` (error) |
| `F` | `<sheet> <ref> n <formula> <ct> <cv>` | a formula cell — formula text with no leading `=`, plus the cached type/value Excel stored for it (omit by using status codes instead if you have none) |

This repository's own corpus validation reads real `.xlsx` files with a staged Python
extractor (`scripts/sheet_plane/extract_xlsx.py`) that turns the zip/XML container into this
exact text format — that extraction step is a source-tree tool for the corpus harness, not
part of the runtime library surface itself. Everything from this text format onward —
tokenizing, parsing, dependency resolution, cycle naming, typed error propagation, function
evaluation and cached-value comparison — is what `sheet_eval_cell` / `sheet_recalc_report`
run, in pure Mojo.

## Every refusal names itself

Loading a workbook and recalculating it are two separate status ranges, and a caller sees
both: `sheet_eval_cell`'s and `sheet_recalc_report`'s `status` field is the loader's status
(1300-1308) if the workbook itself did not load, or the recalculation's status (1320-1321) if
it did.

| Code | Name | Meaning |
| --- | --- | --- |
| 1300 | `SHEET_OK` | the workbook loaded |
| 1301 | `SHEET_ERR_BAD_MAGIC` | missing or wrong `SHEETWB` header line |
| 1302 | `SHEET_ERR_BAD_LINE` | a line does not parse as any known record type |
| 1303 | `SHEET_ERR_SHEET_INDEX` | a cell or name references a sheet index that does not exist |
| 1304 | `SHEET_ERR_BAD_REF` | an A1 reference does not parse |
| 1305 | `SHEET_ERR_DATE1904` | the 1904 date system flag is set — refused, not silently reinterpreted |
| 1306 | `SHEET_ERR_TOO_LARGE` | the workbook exceeds the cell/node ceiling |
| 1307 | `SHEET_ERR_DUP_CELL` | the same cell address appears twice |
| 1308 | `SHEET_ERR_EMPTY` | the workbook has no content |
| 1320 | `RECALC_OK` | recalculation finished |
| 1321 | `RECALC_BUDGET` | the `budget_ops` charge ran out before every cell finished — `evaluated` / `not_evaluated` on the report say how much of the workbook that covers |

A malformed workbook never crashes the worker — it returns one of the codes above with
`found = False` (for `sheet_eval_cell`) or a report whose counts are all zero except `status`
(for `sheet_recalc_report`):

```python
bad = "this is not a workbook\n"
r = runtime.execute("sheet.api", "sheet_recalc_report", [bad, 1000])["result"]
r["status"]   # 1301 — SHEET_ERR_BAD_MAGIC
```

## What is not claimed

* **This is not a spreadsheet UI, an `.xlsx` writer, or a live-editing surface.** It reads an
  already-extracted workbook and computes formula values; it does not open, render or save
  a spreadsheet file.
* **No number-format engine.** `TEXT()` is a deliberate, counted skip (see
  [What is implemented](#what-is-implemented)) — formatting a number as a display string is a
  different capability from evaluating a formula.
* **Turning a real `.xlsx` into the text format above is a repository build tool, not a
  runtime-library call.** `scripts/sheet_plane/extract_xlsx.py` runs the zip/XML read with
  Python's standard library once, offline; everything the SDK calls above is the pure-Mojo
  half that starts from its output.
* **No claim about which functions any particular real-world workbook needs.** The 48
  functions above are the ones the four benchmark corpora this plane validates against
  actually use, in the frequency they actually occur at — not an exhaustive implementation of
  Excel's function library.
* **No externally-published comparison number is made on this page.** What is reported here is
  what the functions return and how a workbook's own cached values are used to check them —
  not a benchmark result against another tool. [Benchmarks](../benchmarks/overview.md) covers
  this repository's rules for pages that do make that kind of claim.

## The modules

`sheet.api` is the only module the two examples above ever call directly. The other five sit
underneath it, in the order a workbook actually passes through them: load, parse each formula,
recalculate, and along the way address cells and coerce values.

| Module | What it does |
| --- | --- |
| `sheet.api` | the two public entry points, `sheet_eval_cell` and `sheet_recalc_report` — everything else in this family runs underneath one of those two calls |
| `sheet.grid` | `load_workbook`: parses the tab-separated text format into a `Workbook` (parallel arrays of cell state), refusing a malformed line, an out-of-range sheet index or a duplicate cell by name instead of indexing on it |
| `sheet.formula` | `tokenize` and `parse_formula`: turns one formula's text into a flat `FNode` tree, resolving function names to ids and refusing unsupported grammar (structured references, external links, range unions) as a named `NK_UNSUP` node rather than a guess |
| `sheet.engine` | `recalc_workbook`: the demand-driven topological walk over that tree, cell by cell, with an explicit stack instead of machine recursion, named cycle detection, and a charged operation budget |
| `sheet.refs` | A1-style reference arithmetic — `parse_a1_cell`, `parse_ref_text`, `a1_of`, `pack_coord` — the row/column addressing every other module above calls into |
| `sheet.values` | the typed `CellValue` (numbers, text, bools, the seven classic Excel errors, plus the engine-internal PENDING/CYCLE/UNSUP/ARRAY kinds) and its coercion, comparison and number-formatting rules |

**`sheet.formula`** tokenizes and parses one formula's text — the same parser that produces the
`SUM(A1:A2)` tree in this page's first example. It gets Excel's two documented precedence traps
right: unary minus binds tighter than `^` (`-2^2` parses as `(-2)^2` = 4, not `-4`), and `^` is
left-associative (`2^3^2` parses as `(2^3)^2` = 64, not `2^(3^2)` = 512) — both verified against
real Excel behavior in `test_sheet_formula.mojo`. A formula the parser cannot represent — a
structured `Table[Column]` reference, an external `[1]Sheet1!A1` workbook link, a
parenthesized range union `(A1:A5,B1:B5)` — never crashes and never produces a half-built tree:
it becomes a single `NK_UNSUP` node carrying the reason (`STRUCTURED_REF`, `EXTERNAL_REF`,
`RANGE_UNION`), which is exactly what surfaces the recalculated cell into this page's
`unsupported` bucket.

**`sheet.engine`** is what `sheet_recalc_report` actually runs. It walks the dependency graph
demand-first — a cell's evaluation pushes its own unresolved dependencies onto an explicit
`List[Int]` stack rather than recursing, because a real corpus formula chain can run hundreds of
cells deep (`test_sheet_engine.mojo` builds a 398-cell chain by hand and checks the engine
reports `max_chain >= 398`). Every node evaluated, cell scanned or array element materialized
decrements a caller-supplied `budget_ops`; a workbook too large to finish inside its budget stops
with status `1321` (`RECALC_BUDGET`) and an honest `not_evaluated` count instead of running past
what the caller charged for — the same test drives a 398-cell chain with a budget of only 50 and
confirms it stops partway, then reruns with the default budget and gets all 398 cells exactly
right. A shared formula (Excel's "fill down" optimization, one stored tree serving many cells) is
re-run per follower cell with only its RELATIVE reference parts shifted: a master at `C1` storing
`A1+$B$1` produces followers at `C2`/`C3` that evaluate to `A2+$B$1` and `A3+$B$1` — `$B$1` never
moves because it is absolute — which is exactly the 101/102/103 result
`test_sheet_engine.mojo` checks by hand.

**`sheet.grid`** owns the `Workbook` model `sheet.engine` and `sheet.refs` both read: sheet
names, and one set of parallel arrays per cell (`c_sheet`, `c_coord`, `c_kind`, `c_num`,
`c_text`, `c_err`, plus the formula-tree fields `c_froot`/`c_ftype`/`c_ftext`) rather than one
struct per cell. `load_workbook` is the only thing that parses the tab-separated text format this
page's "workbook text format" section documents, including the `G` line for shared-formula
followers — 69.5% of all formula cells across this plane's benchmark corpora carry no stored
formula text of their own and are recalculated purely from their master's shifted tree. Loading
is refusal-first and allocation is capped (`MAX_WB_CELLS` cells, `MAX_WB_NODES` formula nodes):
past either limit, or on a malformed line, an out-of-range sheet index, a bad A1 reference or a
duplicate cell address, the load refuses with one of the `SHEET_ERR_*` status codes in the table
above rather than building a partially-indexed workbook.

**`sheet.refs`** is the reference arithmetic every other module addresses cells through. Excel's
grid is 1,048,576 rows by 16,384 columns (`A` through `XFD`); internally both are 0-based and pack
into one `Int` as `row * 16384 + col`, which stays exact in a `Float64` too. `parse_a1_cell`
handles the single-cell form, preserving each `$` as a separate relative/absolute flag bit —
`test_sheet_refs.mojo` checks `$B$7` parses to row 6, column 1, both parts absolute — and
`col_name` round-trips the documented edges exactly: column 0 is `A`, 25 is `Z`, 26 is `AA`, and
16383 is `XFD`. `parse_ref_text` handles the fuller grammar `INDIRECT` needs — quoted sheet names,
ranges, whole columns — the same test file confirms `'P&L 2024'!$A$1:B10` parses to sheet `P&L
2024`, rows 0-9, columns 0-1. An off-grid or malformed reference (`A0`, `XFE1`, `A1048577`,
`$$A1`) fails rather than wrapping onto the grid.

**`sheet.values`** defines the `CellValue` every formula ultimately evaluates to, and the
coercion rules that convert between kinds the way Excel does. Beyond the four visible kinds
(number, text, bool, and the seven classic errors — `#NULL!`, `#DIV/0!`, `#VALUE!`, `#REF!`,
`#NAME?`, `#NUM!`, `#N/A`) it defines four engine-internal ones — `RANGE`, `ARRAY`,
`PENDING` and `CYCLE` — that never reach a caller directly but are how `sheet.engine` tracks an
unresolved reference, a materialized range, a cell still being computed, and a cell on a named
cycle. Its `num_to_text` implements Excel's own display conversion (round to 15 significant
digits, plain notation between 1e-4 and 1e21, scientific outside it) so a recalculated number can
be compared byte-for-byte against a cached string: `test_sheet_refs.mojo` checks
`num_to_text(1.0/3.0)` is exactly `"0.333333333333333"` and `num_to_text(1e21)` is `"1E+21"`, and
separately asserts the 15-digit rounding is *not* one ulp off in the other direction — a mutation
guard on the formatter itself. It also holds the wildcard matching (`*`, `?`, `~`-escaped
literals) that `COUNTIF`/`SUMIF`-family criteria parse through `sheet.engine`.

## See also

* [Runtime library catalog](runtime-library-catalog.md) — every module and function, including `sheet.api`, `sheet.engine`, `sheet.formula`, `sheet.grid`, `sheet.refs` and `sheet.values` above.
* [Declared capabilities](capabilities.md) — what each kernel says about determinism, seeds and cost.
* [Statistical inference](statistical-inference.md) — `STDEV` and friends, at full statistical-package depth.
* [Forecasting and backtesting](forecasting.md) — for time-series work a spreadsheet formula was never going to do well.
