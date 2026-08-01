# The spreadsheet formula plane (`mojo/engine/sheet/`)

Recalculates real .xlsx workbooks from their input cells and compares every
formula cell against the value Excel cached for it. An .xlsx stores, for every
formula cell, BOTH the formula and the last value Excel computed — so every
real workbook is its own ground truth, and correctness validation runs at
corpus scale: exact, free, no LLM, no judge.

This is the substrate under the finance-benchmark tier (SpreadsheetBench 2,
BlueFin, Finch, FinSheet-Bench): deterministic compute outside the prompt.
It is NOT a benchmark result; the task harnesses and LLM integration those
benchmarks additionally need are separate, owner-gated work.

## Architecture

```
xlsx ──(staged Python reader)──▶ .swt text ──▶ grid loader ──▶ recalc ──▶ compare
      scripts/sheet_plane/          │            sheet/grid     sheet/engine  sheet/api
      extract_xlsx.py               │            refusal-first  pure Mojo     typed report
```

* The **zip/XML container** is read by `scripts/sheet_plane/extract_xlsx.py`
  (Python stdlib) because the frozen `compression/` package has no RFC-1951
  inflate. Everything from formula text onward — tokenizer, parser, reference
  resolution, dependency traversal, cycle naming, typed error propagation,
  function evaluation, cached-value comparison — is pure Mojo, zero Python
  imports. A Mojo-native reader needs an additive inflate later.
* **Formula IR** mirrors `expr.parse_expr`: flat typed records in a
  `List[FNode]`, children as Int indices in a shared pool. Excel's precedence
  traps are encoded and tested (`-2^2 = 4`; `2^3^2 = 64`).
* **Recalc** is demand-driven topological traversal with an EXPLICIT cell
  stack (corpus chains are O(cells) deep — finch has million-row columns —
  so machine recursion at the cell level is banned). Discovery queues a
  cell's static dependencies; OFFSET/INDIRECT (census ranks 1 and 10) return
  REFERENCES, so dynamic edges surface as PENDING values that push the
  blocking cell and retry.
* **Cycles NAME their cells**: `Model!A1 -> Model!B1 -> Model!A1`. Live
  circular workbooks exist in the corpora (iterative-calc financial models);
  they refuse honestly instead of crashing or spinning.
* **Errors are typed values** (#DIV/0!, #REF!, #VALUE!, #N/A, #NAME?, #NUM!,
  #NULL!) that PROPAGATE; ~292k cached error cells validate this for free.
* **Work is charged, not just memory**: every node eval, scanned cell and
  materialised array element decrements one budget; exhaustion is an honest
  partial status (1321), never a hang.
* **Shared formulas** (69.5% of corpus formula cells are followers with no
  stored text) share the master's tree shifted by (Δrow, Δcol) on RELATIVE
  refs only.

## Honesty machinery

* An unimplemented function taints its cell AND its dependents into an
  UNSUPPORTED bucket counted BY NAME — the uncovered tail is a table, never
  a silent skip. TODAY/NOW/RAND/RANDBETWEEN are a separate volatile bucket
  (their cached values are irreproducible by construction).
* The comparator never hides a wrong answer: numbers match EXACTLY (correctly
  rounded strtod on the 17-significant-digit cached `<v>`), or land in one of
  two separately counted near buckets — `matched_tol` (relative 1e-9) and
  `matched_snap` (cached exactly 0.0, recalc within 1e-6: Excel's cosmetic
  near-zero snap, measured live) — and everything else is a MISMATCH quoted
  verbatim. The suites prove a planted wrong value fails.
* The harness (`scripts/sheet_plane/validate_corpus.py`) asserts per workbook
  that the buckets sum exactly to the formula-cell count: a cell that
  vanishes from every bucket fails the workbook.

## Functions

Implemented in strict census frequency order over the four benchmark corpora
(9,848,617 formula cells): OFFSET, ROW, MIN, IF, SUM, VLOOKUP, IFERROR,
COUNTIFS, TIME, INDIRECT, AND, MAX, AVERAGE, TEXTAFTER (top-14 = the 90%
coverage point), then ABS, STDEV, YEAR, COUNTIF, INDEX, MATCH, MONTH, SUMIF,
RANK (95% point), then COLUMN (Phase-1 core: ROW's sibling) and census ranks
24-48: WEEKDAY, INT, LEFT, EDATE, SUBSTITUTE, EOMONTH, SLN, ROUNDUP, VALUE,
SUMPRODUCT, SUMIFS, DAYS, LOOKUP, LARGE, RIGHT, LEN, OR, ROWS, ISNUMBER,
CHOOSE, ROUNDDOWN, ISBLANK, DATE. TEXT (rank 31) is the one deliberate skip —
it needs a number-format engine and stays in the counted tail.

IF / IFERROR / CHOOSE are special forms: laziness is semantics
(`IF(TRUE,1,1/0)` is 1). The 1900 date system keeps Excel's leap-year legend
(serial 60 is the fake 1900-02-29; DATE(1900,3,1) is 61); the 1904 system is
refused (zero corpus workbooks use it).

## Validation numbers

See the PR description / `scripts/sheet_plane/validate_corpus.py --out`
report for the current corpus numbers (per corpus and overall: matched
exact/tol/snap/error against cached values, with the uncovered tail by
function name). Regenerate any time:

```bash
cd mojo_env && pixi run mojo build -I../mojo/engine \
    ../scripts/sheet_plane/validate_main.mojo -o ../build/sheet_validate
python3 -P scripts/sheet_plane/validate_corpus.py \
    --binary build/sheet_validate --jobs 10 --budget 60000000000 \
    --corpus name=/path/to/xlsx/tree --out report.json
```

## Tests and gates

* `mojo/tests/libs/test_sheet_{refs,formula,engine,functions}.mojo` —
  hand-checkable known values (a five-cell workbook computed by hand, the
  named-cycle case, #DIV/0! chains, 68 function cells with hand-derived
  cached values). Registered in `HANDWRITTEN_TESTS`; mutation-tested (ADD→SUB,
  swallowed cycles, STDEV divisor, SUM dropping an operand — each caught by
  exactly the assertion that owns it).
* `benchmarks/mojo_benchmarks/bench_sheet_plane.mojo` — BENCH_GATE on
  properties (correctness sentinel, bit-identical determinism, 8x scaling,
  charged work), demonstrated to fail on a mutated SUM.
* Status codes: the package owns 1300-1349 (grid 1300-1319, engine 1320-1339).
