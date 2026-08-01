"""sheet — the spreadsheet formula plane (additive namespace, 2026-08).

Recalculates real .xlsx workbooks from their input cells and compares every
formula cell against the value Excel cached for it, so a whole benchmark corpus
is its own ground truth. The xlsx container (zip/XML) is read by a staged
Python extractor (`scripts/sheet_plane/extract_xlsx.py`) because the frozen
`compression/` package has no RFC-1951 inflate; everything from formula text
onward — tokenizer, parser, reference resolution, dependency traversal, cycle
naming, typed error propagation, function evaluation, cached-value comparison —
is this package, pure Mojo, zero Python imports.

Modules:
  values   — typed cell values (number/text/bool/error/empty) and coercions;
             errors are VALUES that propagate, never crashes.
  refs     — A1/absolute/whole-row/whole-column references, sheet resolution.
  formula  — tokenizer + parser to a flat-node IR (mirrors `expr.parse_expr`:
             typed records in a List, children as Int indices, no pointers).
  grid     — workbook model + loader for the extractor's tab-separated text
             format; refusal-first on anything malformed.
  engine   — demand-driven topological recalc over the dependency DAG with an
             explicit stack (a 1M-cell chain must not touch machine recursion),
             cycles NAMED cell by cell, dynamic edges (OFFSET/INDIRECT), the
             function library in census order, and the cached-value comparator.
  api      — flat public drivers (String in, typed report struct out).

Status codes: this package owns the 1300-1349 range (see rule 4e in
docs/mojo/new-kernel-package-rules.md). grid claims 1300-1319, engine
1320-1339, api reuses both.
"""
