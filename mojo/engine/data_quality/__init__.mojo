"""
data_quality — expectations, profiling, duplicates and leakage. Zero Python imports.

What the tree already has, and what it does not
----------------------------------------------
Every number this package reports comes out of a frozen kernel. The value added is the
composition and the refusals.

EXISTING-FROZEN, called rather than reimplemented:

Every name below is IMPORTED and CALLED. The list is the actual import list, checked
against `grep`, not a reading list: two entries in an earlier draft of this paragraph
(`columnar.validity` and `numeric.reduce.first_non_finite`) named files the package never
imports, which is the same class of false claim as reimplementing a frozen kernel and is
recorded here so the correction is visible rather than quietly applied.

  * `numeric.reduce` — the ONLY null-aware reduction family in the tree. Every reduction
    returns `(value, present)` and nulls travel in a parallel `List[Bool]` mask rather than
    as a sentinel. `reduce_mean` (Welford), `reduce_stddev`, `reduce_min`, `reduce_max`,
    `all_valid` and `is_finite_value` are the six names imported. `profile` computes no
    mean, spread or extremum of its own; it builds the live-and-finite mask and calls
    these. The MEDIAN comes from `stats.median`, not from here — `reduce_median` sorts with
    insertion sort and is deliberately not imported.
  * `query.ir` — the typed expression IR. `types.ExprNode` plus comparison (100-105),
    three-valued logical (110-112), null (120-122), column-reference (130) and cast
    (140-141) opcodes, with `validation_error` rejecting a malformed plan whole and
    `first_unsupported_op` naming a node the columnar evaluator cannot run.
  * `query.eval` — the columnar evaluator, with SQL null semantics already decided:
    arithmetic and comparison propagate null, `AND`/`OR` are three-valued and
    deliberately not strict. An expectation engine needs exactly this and nothing here
    re-decides it.
  * `columnar.array` / `columnar.batch` — `float64_with_nulls`, `Float64Array`,
    `RecordBatch` and `Schema` build the nullable columns `query.eval` reads, so `0.0` no
    longer has to mean "missing". `columnar.validity` is NOT imported and is not claimed:
    presence in this package is a `List[Bool]`, one entry per row, because that is what a
    flat SDK signature can carry — a validity BITMAP is the representation those frozen
    columns use internally, and it is `float64_with_nulls` that converts.
  * `columnar.hash_index` — `HashIndex` and `CompositeKeyIndex`, keyed on the IEEE-754
    bit pattern with `-0.0` collapsed to `+0.0` and every NaN collapsed to one quiet NaN.
    That is a STATED notion of equality, and it is what duplicate detection needs;
    `abs(a - b) < tol` is not an equivalence relation and cannot key a hash table.
  * `stat_tests.pearson_r`, `stats.median`, `sparse_numerics.csr.dims_fit` and
    `validate.check_monotonic` — correlation, the median, wrapping-safe shape validation
    by DIVISION, and run-direction detection. All four are imported and called.

  NOT called, deliberately, and named here so the classification cannot be read as a
  claim of reuse it does not make:

  * `regression.ols_simple` — a least-squares fit answers "what is the best affine map",
    not "is this exactly affine". Its coefficients accumulate error over all `n` rows, so
    checking an exact relation against them needs a tolerance that grows with the number
    of OTHER rows, which is the tolerance-scaling defect. `leakage` derives the candidate
    map from two rows and verifies every row against ITS OWN magnitude instead; the
    reasoning is in that module's docstring. `ols_simple` stays frozen and reachable for
    callers who want the fit itself.
  * `ml.preprocessing`, `feature_engineering`, `feature_selection`,
    `engines.column_profiler` — READ and classified in the module docstrings that use
    them as prior art, not imported. `feature_selection.f_test_scores` and
    `information_gain` score a feature against a target, and a score is not a verdict;
    `engines.column_profiler` has no concept of a null. Each is discussed where it is
    relevant. None is modified and none is reimplemented — the drivers here answer a
    different question, and say so.
  * `currency.round_currency` — the tree's existing decimal rounder, and the prior art for
    `contract.dq_quantize`, which is written new anyway because the ANSWER differs:
    `round_currency` rounds half toward `+inf` (`round_currency(-0.5, 0) == 0.0`) while a
    grid used as a hash KEY must be sign-symmetric (`dq_quantize(-0.5, 0) == -1.0`), and
    `round_currency` has neither a `decimals` range guard nor a representability guard. The
    citation belongs here: a "genuinely-missing" classification that does not name the
    nearest existing kernel is an unexamined claim even when the decision is right.
  * `columnar.validity` and `numeric.reduce.first_non_finite` — named ONLY to withdraw two
    reuse claims an earlier draft made for them. Neither is imported anywhere in the
    package. A grep of the package for either name finds it in this paragraph and nowhere
    else.

MISSING-DRIVER — the primitives exist and nothing composes them end to end:

  * an EXPECTATION over a table. `query.eval` evaluates a predicate and
    `query.executor` filters with it, but a filter answers "which rows survive", not
    "which rows failed, in which column, against which bound, with which observed
    value". `expect` builds the plan with the frozen `query.ir` constructors, runs the
    frozen evaluator, and returns the per-row addresses.
  * a COLUMN PROFILE that separates NULL from NaN from zero. `engines.column_profiler`
    is the only profiler in the tree; it has no concept of a null at all (its inputs are
    JSON arrays and `_extract_float_array` simply skips a `null` token), and its
    `mean`/`std` are computed inline over whatever survived parsing. `profile` keeps the
    three facts apart and reports every statistic through `numeric.reduce`.
  * DUPLICATE detection on a stated key. `columnar.hash_index` provides the index and
    `query.aggregate` groups with it, but nothing reports duplicate ROWS, group sizes or
    the first row of each group.
  * a LEAKAGE report. `feature_selection.f_test_scores` and `information_gain` score a
    feature against a target and `stat_tests.pearson_r` correlates two vectors, but a
    score is not a verdict and none of them separates "suspicious" from "proven".

SURFACE-GAP — reachable in the tree, not reachable from the SDK:

  * `engines.column_profiler.run_column_profile` is a JSON-in/JSON-out engine under
    `engines/`, which is in `_SKIP_RUNTIME_DIRS`. `columnar/`, `query/` and `numeric/`
    are excluded too, because their entry points take `RecordBatch`, `List[ExprNode]`
    and `Reduction`. This package's public surface is flat lists in, a return-only
    struct out, so all four become reachable THROUGH it without a new message type.

GENUINELY-MISSING, written new here: the expectation opcode vocabulary, the
null/NaN/zero census, the group/duplicate accounting, the leakage verdict ladder, and
the work budget that bounds all of them.

The four things this family gets wrong when it is done badly
------------------------------------------------------------
1. *A failed expectation must name the ROW and the COLUMN.* "3 rows failed" is not
   actionable. `ExpectationReport` carries `fail_rows`, `fail_columns`, `fail_ops`,
   `fail_expected` and `fail_observed` as parallel lists, and `expect_failure_line`
   renders one as `row 47, column 2, expected gt 0.0, got -12.0`.

2. *Null and NaN are different facts, and both differ from zero.* `ColumnProfile`
   counts `n_null`, `n_nan`, `n_pos_inf`, `n_neg_inf`, `n_zero`, `n_negative` and
   `n_positive` separately. A column of 100 nulls and a column of 100 zeros produce
   different profiles, and so do a NaN and a null.

3. *A correlation is suspicious; a timestamp is proof.* `leakage` says which of the two
   it found. `proven_target_copy` and `proven_affine` are deterministic-function facts
   about the data. `abs_pearson` is a number and `suspicious_correlation` is a flag, and
   the docstring states outright that neither is evidence of leakage. Future information
   is provable ONLY from timestamps the caller supplies, so it lives in a separate
   function with a separate struct and `temporal_checked` says whether it ran.

4. *A duplicate needs a stated key and a stated equality.* The key is `key_cols`, and
   nothing is a duplicate of anything under any other key. Equality is the frozen
   `columnar.hash_index.normalize_bits` bit pattern, or — when the caller declares a
   decimal grid — that pattern after rounding to the grid. Never `abs(a - b) < tol`.

Bounded work, and what was not checked
--------------------------------------
`contract.DQ_MAX_WORK` bounds every product that drives cost: `n_rows * n_cols` for a
table, `n_nodes * rows` for an evaluation, `n_expectations * rows` for a suite,
`n_rows * n_key_cols` for a duplicate scan. When a request exceeds it, an expectation
report checks a PREFIX and says how many rows it did not check
(`n_rows_not_checked`, `work_truncated`) — it does not sample, because a sampled pass
that reports a clean table is a wrong answer rather than a partial one.

A budget only bounds the work it is actually charged over, and the truncated drivers
therefore extract COLUMN PREFIXES (`contract.dq_column_prefix`) rather than whole columns.
Extracting the whole column per expectation made `n_expectations * rows` a declaration and
`n_expectations * n_rows` the reality: measured at the ceiling, a 256-expectation suite
examining 5,461 of 4,194,304 rows ran 29x slower than a one-expectation request examining
1,398,101 rows at the same declared cost. Bounding memory is not bounding work, and a
declared cost that understates the real loop by a factor is the same defect wearing a
budget.

Status codes
------------
This package owns 400-449 and uses no other range (rule 4e). One vocabulary,
`contract.dq_status_name`, with per-module sub-ranges recorded beside each block:
contract 400-409, profile 410-419, expect 420-429, leakage 430-439,
duplicates 440-449.

Modules
-------
  contract   — status codes, ceilings, the work budget, the ONE tolerance builder, the
               ONE float-equality notion, the guarded column extractor
  profile    — the null/NaN/zero census and every statistic through `numeric.reduce`
  expect     — expectations over the frozen typed IR, with row-and-column addresses
  duplicates — grouping on a stated key with a stated equality
  leakage    — target-copy, affine-image, correlation, missingness and timing checks

Public functions take and return only `List`/`Int`/`Float64`/`Bool`/`String` or a
return-only struct declared in the same file, so the package lands in the runtime
library contract without a new message type. It is therefore NOT in
`_SKIP_RUNTIME_DIRS`.
"""
