"""
progexec — exact execution of a FinQA-shaped indexed numeric program.

FinQA (Chen et al., EMNLP 2021) scores an answer by EXECUTING a short program over ten
operations (`add`, `subtract`, `multiply`, `divide`, `exp`, `greater`, `table_max`,
`table_min`, `table_sum`, `table_average`), where a step may reference an earlier step's
own result by index. That execution step is arithmetic — deterministic, and either exact
or not — which is exactly the half of "LLM does language, Algenta does compute" this
package exists to own, additive-only:

  contract   — the op vocabulary, argument-kind tags, and the 1400-1419 status range.
  roundexact — round-half-to-even at a caller-supplied decimal scale, decided from the
      EXACT value of `x * scale` via `exactnum.eft`'s error-free transforms, rather than
      from a single float64 scaling multiply. Matches CPython's `round(x, n)`
      bit-for-bit; a naive port (Mojo's own builtin `round`, and separately this tree's
      own `currency.round_currency`) does not — see that module's docstring for eleven
      real, verified counterexamples across the two (six and five, different sets).
  exec       — `progexec_run_flat`, the flat-list driver over the ten ops. Table
      aggregates call `numeric.reduce.reduce_sum` / `reduce_max` / `reduce_min` directly
      (rule 3); `table_average` is `reduce_sum(row).value / n`, the same plain
      `sum(row) / len(row)` the official evaluator uses, not `reduce_mean`'s
      (numerically better, differently-rounded) Welford mean.

Public functions take and return only flat lists, scalars, and same-file structs — the
row-name-to-table-row lookup and the program-text tokenisation stay at the call site
(Python, in this driver's case), because those are PARSING, not the arithmetic this
package's own scope is limited to. See `exec`'s module docstring for the one case
(a table row selected by back-reference rather than by name) this boundary refuses rather
than silently mishandles, and why that refusal cannot turn any real FinQA gold program's
answer wrong.
"""
