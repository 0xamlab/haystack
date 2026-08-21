---
icon: table
description: The spreadsheet formula plane — recalculates real .xlsx workbooks in pure Mojo and compares every formula cell against Excel's cached value; substrate under the finance-benchmark tier.
---

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

```text title="recalc pipeline"
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
* **The tolerance is not a hiding place** — proven by mutation at corpus
  scale, not by assertion. Three mutants of the shipped engine were run over
  a whole corpus: SUM off by 1e-8 relative (10x the tolerance), every scalar
  ADD off by 1e-8, and — the decisive one — every ADD off by **2e-10, five
  times SMALLER than the 1e-9 tolerance**. All three are caught: the
  sub-tolerance mutant still fails 56,451 cells and collapses `matched_exact`
  from 182,105 to 106,813, because a near-tolerance error amplifies through
  dependency chains and because the EXACT bucket is the load-bearing number.

## A mismatch is a lead, not a statistic

Corpus self-validation is only worth the compute if the mismatches get
opened. Four defects in this engine were found that way and none was
reachable from a hand-written test, because each needed a real workbook to
express it:

| symptom in the corpus | root cause |
|---|---|
| `SUMIFS(...,"JESUS MAGAÑA")` summed 0 | the criteria parser rebuilt its body with `chr()`, re-encoding every byte >= 0x80 |
| `MATCH(1,INDEX((A=x)*(B=y),0),0)` → #VALUE! | INDEX rejected a COMPUTED array; only ranges were indexable |
| `INDEX(#REF!,MATCH(..))` → #VALUE! (cached #REF!) | INDEX turned an error argument into #VALUE! instead of propagating it |
| `LOOKUP(2,1/($A$3:$A$7<>""),$A$3:$A$7)` answered a different row per copy | implicit intersection collapsed the search vector — the answer depended on the formula's own row |

The rest of the mismatch mass is diagnosed, not merely counted: cells that
disagree because the FILE disagrees with itself (SpreadsheetBench-2's
Debugging tasks inject a bug into the formula text and keep the pre-injection
cached value — `SUM(F4,F6,F4)` cached as `F4+F6`), cells whose inputs Excel
serialized at fewer digits than it computed with, and named unimplemented
functions.

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

**Vector slots take no implicit intersection.** LOOKUP's search/result vectors,
INDEX's array and MATCH's lookup vector are REFERENCE slots: a computed
operand inside them stays an array. Without that rule the corpus's
last-non-blank idiom `LOOKUP(2,1/($A$3:$A$7<>""),$A$3:$A$7)` collapses to the
formula's OWN row and silently answers a different cell — the kind of bug
only corpus-scale self-validation finds, because it is invisible in any
workbook whose formula happens to sit outside the range. Whole-column (`F:F`)
and whole-row operands materialise clamped to the sheet's USED range, which
is also what Excel evaluates; explicit ranges keep their blank tail.

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
  named-cycle case, #DIV/0! chains, 72 function cells with hand-derived
  cached values — including the two corpus-found regressions: non-ASCII
  criteria bytes and INDEX(computed_array, 0)). Registered in
  `HANDWRITTEN_TESTS`; mutation-tested (ADD→SUB,
  swallowed cycles, STDEV divisor, SUM dropping an operand — each caught by
  exactly the assertion that owns it).
* `benchmarks/mojo_benchmarks/bench_sheet_plane.mojo` — BENCH_GATE on
  properties (correctness sentinel, bit-identical determinism, 8x scaling,
  charged work), demonstrated to fail on a mutated SUM.
* Status codes: the package owns 1300-1349 (grid 1300-1319, engine 1320-1339).

## Related

* [new-kernel-package-rules.md](new-kernel-package-rules.md) — the rules a new Mojo kernel package (like `sheet/`) must follow.
