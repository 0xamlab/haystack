---
icon: calculator
description: Executes a resolved FinQA-style arithmetic program — ten operations, steps that reference earlier results by index — to the official evaluator's own rounding spec, bit-for-bit.
---

# Program execution & scoring

FinQA (Chen et al., EMNLP 2021) scores a predicted answer by EXECUTING a short program drawn
from a financial filing's text and tables: up to a handful of chained steps over ten
operations (`add`, `subtract`, `multiply`, `divide`, `exp`, `greater`, `table_max`,
`table_min`, `table_sum`, `table_average`), where a step may reference an earlier step's own
result by index (`#i`). Getting the operations and table cells right is a language-understanding
problem; executing the resolved program once that decision is made is pure arithmetic — and the
official evaluator's own spec for that arithmetic (`code/evaluate/evaluate.py`) has two real
sharp edges: every intermediate result stays an **unrounded** Python float, and `round(x, 5)` —
Python's round-half-to-even, decided from the exact value — is called exactly **once**, on the
final step only. `progexec` is the driver that reproduces that spec exactly, so scoring a
program is a call into this family rather than a re-embedded copy of the evaluator's own float
loop.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# ADI/2009/page_49.pdf-1: divide(100, 100), divide(3.8, #0) -> gold exe_ans 3.8
OP_DIVIDE = 3
ARG_LITERAL, ARG_REF = 0, 1

result = runtime.execute("progexec.exec", "progexec_run_flat", [
    [OP_DIVIDE, OP_DIVIDE],           # ops
    [ARG_LITERAL, ARG_LITERAL],       # arg1_kind
    [100.0, 3.8],                     # arg1_num
    [ARG_LITERAL, ARG_REF],           # arg2_kind
    [100.0, 0.0],                     # arg2_num: step 1's arg2 is a reference to step #0
    [], [0, 0], [0, 0],                # table_values, table_offset, table_len (unused here)
    2,                                 # n_steps
])["result"]

result["status"]    # 1400 — "ok"
result["present"]   # True
result["value"]     # 3.8 — exactly the dataset's own exe_ans
```

## The modules

| Module | What it does |
| --- | --- |
| `progexec.contract` | the ten op codes, the three argument-kind tags, the 1400-1419 status range, and `progexec_status_name` for turning a status code back into a readable string |
| `progexec.exec` | `progexec_run_flat`, the flat-list driver that walks a program's steps and returns a typed `ProgExecResult` |
| `progexec.roundexact` | `round_half_even_scaled`, a round-half-to-even at a caller-supplied power-of-ten scale, decided from the exact value of `x * scale` rather than a single rounding multiply |

## The op vocabulary and argument tags

`progexec.contract` fixes the op codes in the official evaluator's own `all_ops` order:

| Code | Op | Code | Op |
| --- | --- | --- | --- |
| 0 | `add` | 5 | `greater` |
| 1 | `subtract` | 6 | `table_max` |
| 2 | `multiply` | 7 | `table_min` |
| 3 | `divide` | 8 | `table_sum` |
| 4 | `exp` | 9 | `table_average` |

Every step supplies two tagged operands (`arg2` is ignored for the four `table_*` ops, which are
unary):

| Code | Kind | Meaning |
| --- | --- | --- |
| 0 | `ARG_LITERAL` | the value is `arg*_num[i]` directly |
| 1 | `ARG_REF` | `arg*_num[i]` is `Float64(j)`, a back-reference to an earlier step `j < i` whose own result was numeric, not boolean |
| 2 | `ARG_TABLE_ROW` | valid only for `arg1` on a `table_*` op — the row lives in `table_values[table_offset[i], table_offset[i] + table_len[i])`, already extracted and numeric-parsed by the caller |

Deciding *which* table row a `table_*` step reads is a string-keyed lookup against the report's
own table, done by the caller before this boundary — `progexec.exec`'s own module docstring notes
that replaying the official evaluator against all 8,281 real gold programs shows its
`table_*`-by-back-reference branch is dead code: no gold program ever selects a table row by
`#i` rather than by name. `progexec` requires `ARG_TABLE_ROW` for that slot and returns a typed
refusal (`bad_arg_kind`) rather than silently accepting the case that never occurs.

## A chained program, worked from a real gold answer

`IPG/2009/page_89.pdf-3` is `subtract(34.8,1.2), divide(#0,34.8), multiply(#1,const_100)` —
three steps, two of them back-references, gold `exe_ans` **96.55172**:

```python
step0 = 34.8 - 1.2            # 33.6, kept unrounded
step1 = step0 / 34.8           # 0.9655172413793104, kept unrounded
step2 = step1 * 100.0          # 96.55172413793103
round(step2, 5)                # 96.55172 — rounded exactly once, at the end
```

`progexec_run_flat` reproduces this: `ops=[1, 3, 2]` (subtract, divide, multiply), step 1's
`arg1` is `ARG_REF` to step 0, step 2's `arg1` is `ARG_REF` to step 1, and the returned `value`
is `96.55172`. This is one of the 130 real gold programs (of 8,281) that a naive
re-implementation gets wrong if it rounds `step0` or `step1` to 5 places before reuse — a
one-keystroke mistake the official evaluator's own source invites, since its table branch
carries a commented-out `# this_res = round(this_res, 5)` that reads like a step someone forgot
to delete rather than a step that was never meant to run. Rounding `step1` to `0.96552` before
the final multiply produces `96.552`, not `96.55172`. See
[FinQA exact execution](../benchmarks/finqa-exact-execution.md) for the other five real programs
this exact trap catches.

## Table aggregates call the real reducers, not a re-summed copy

The four `table_*` ops resolve against `numeric.reduce.reduce_max` / `reduce_min` / `reduce_sum`
directly — `progexec` does not carry its own copy of sum/max/min. `table_average` is computed as
`reduce_sum(row).value / len(row)`, the same plain `sum(row) / len(row)` the official evaluator
itself uses, deliberately **not** `numeric.reduce.reduce_mean`'s Welford algorithm: Welford is
numerically better but differs from plain `sum/n` in the last bit, which would occasionally
disagree with `exe_ans` for the same reason `roundexact` exists — a different, if superior,
arithmetic path is still a different bit pattern before the final rounding.

Four real gold answers, each a single-step table program:

| Question id | Op | Table row | Gold `exe_ans` |
| --- | --- | --- | --- |
| `ORLY/2009/page_77.pdf-3` | `table_average` | `[13053.0, 18874.0]` | 15963.5 |
| `MKTX/2005/page_40.pdf-2` | `table_max` | `[13.14, 10.64]` | 13.14 |
| `GS/2012/page_95.pdf-2` | `table_min` | `[208.0, 212.0]` | 208.0 |
| `ORLY/2009/page_77.pdf-2` | `table_sum` | `[13053.0, 18874.0]` | 31927.0 |

## `round(x, 5)`, ported without double-rounding

The official evaluator's final rounding is CPython's `round(x, 5)`: round-half-to-even, decided
from the exact value of `x`. The "obvious" way to port that to a language without CPython's
arbitrary-precision decimal path — multiply by `100000.0` in float64, round to the nearest
integer, divide back — silently double-rounds whenever the true value of `x * 100000` sits
within about half an ULP of an integer-plus-one-half, because the multiply itself introduces a
rounding step before the "real" rounding ever happens. Six real FinQA gold programs land exactly
on that boundary, measured by running Mojo's own builtin `round(x, 5)` against them:

| Question id | Raw value | Naive port | Gold `exe_ans` |
| --- | --- | --- | --- |
| `HII/2011/page_100.pdf-3` | 3.268485 | 3.26848 | **3.26849** |
| `RE/2010/page_42.pdf-4` | 1.276875 | 1.27688 | **1.27687** |
| `CAT/2017/page_69.pdf-2` | -0.771875 | -0.77188 | **-0.77187** |
| `IP/2012/page_84.pdf-2` | 0.115625 | 0.11562 | **0.11563** |
| `ETR/2017/page_143.pdf-2` | 0.128525 | 0.12852 | **0.12853** |
| `HIG/2011/page_53.pdf-1` | 0.178125 | 0.17812 | **0.17813** |

`progexec.roundexact.round_half_even_scaled(x, scale)` avoids this by never forming `x * scale`
as a single rounded float: `exactnum.eft.eft_two_product` produces the exact `(hi, lo)`
double-double for `x * scale`, `hi` alone is rounded to the nearest integer (no scaling step, so
no double-rounding exposure), and the residual `(hi - round(hi)) + lo` — combined via
`exactnum.eft.eft_two_sum` into a clean fractional pair — decides whether the true value actually
crossed the boundary and which way a genuine tie breaks. `scale` is required to be a literal,
exactly-representable power of ten (`PROGEXEC_ROUND_SCALE = 100000.0` for FinQA's five decimal
places) supplied by the caller, never computed via `pow`, which is a transcendental and not
guaranteed exact even for an integer exponent.

This tree's own `currency.round_currency` — a frozen kernel already shipping elsewhere,
docstring-labelled "banker's rounding" — is the closest existing candidate and is independently
wrong two ways: it forms the same single-multiply `amount * mult`, and its tie-break is
round-half-**up**, not round-to-even (`round_currency(2.5, 0)` returns `3.0`; true
round-half-to-even returns `2.0`).
It happens to get five of the six cases above right, by getting the corrupted tie's direction
right for the wrong reason, but produces five of its **own** real divergences from `exe_ans` —
a different set, not a superset of the six above (only `RE/2010/page_42.pdf-4` is shared). Both
lists are in `progexec.roundexact`'s module docstring and in
[FinQA exact execution](../benchmarks/finqa-exact-execution.md). `roundexact` exists because the
frozen tool that looks like the obvious fit is provably the wrong shape for this external spec,
not because the tree lacked a rounder.

Genuine ties resolve to the even neighbor, sign-symmetrically, and a value the naive multiply
would *corrupt into* an apparent tie is told apart from a real one:

```python
runtime.execute("progexec.roundexact", "round_half_even_scaled", [0.125, 100.0])["result"]
# 0.12 — an exact tie; 2 is the even neighbor, not round_currency's 0.13

runtime.execute("progexec.roundexact", "round_half_even_scaled", [-0.125, 100.0])["result"]
# -0.12 — ties-to-even is sign-symmetric

runtime.execute("progexec.roundexact", "round_half_even_scaled", [1.5, 1.0])["result"]
# 2.0
runtime.execute("progexec.roundexact", "round_half_even_scaled", [2.5, 1.0])["result"]
# 2.0 — both integer ties resolve to the even neighbor

runtime.execute("progexec.roundexact", "round_half_even_scaled", [2.675, 100.0])["result"]
# 2.67 — NOT a real tie: the true value of 2.675 in float64 is 2.67499999999999982...,
# which a single-multiply rounder can misread as landing exactly on the 2.675 boundary
```

## Refusal is an absence, never a fabricated number

`ProgExecResult.present` is `False` for anything the official evaluator would also refuse to
answer, and the caller always gets a typed `status` rather than a plausible-looking wrong value:
a program with `n_steps <= 0`; a caller-declared `n_steps` that exceeds the real length of any
of the seven parallel `List` arguments (validated before anything is indexed, per rule 1 — a
five-step claim against one-element lists is refused, not read past the end); a forward or
self-reference (`#0` used as an operand at step 0); a reference to a step whose own result was
boolean; a `table_offset`/`table_len` pair that reaches past the real `table_values` buffer; an
empty table row; `divide` by zero (refused, never returned as `inf`); and an unrecognized op
code. A `greater` step at the final position sets `is_bool` and answers via `bool_value` — FinQA's
own `exe_ans` is either a float or the literal string `"yes"`/`"no"`, and collapsing that
distinction into one `Float64` would either lose it or invent a fractional value for a question
that never had one.

## Verification

`mojo/tests/libs/test_progexec_exec.mojo` pins seven real FinQA gold programs — the two-step
`ADI/2009/page_49.pdf-1` divide chain (3.8), the three-step `IPG/2009/page_89.pdf-3` chain
(96.55172), a `greater`-final boolean program (`ABMD/2012/page_75.pdf-1`, "yes"), and the four
table-aggregate examples above — plus six adversarial guard cases (a zero-step program, an
`n_steps` claim past the real list lengths, a self-reference, a table row past the real buffer,
divide-by-zero, and an unknown op code), all against the dataset's own `exe_ans`, not a value
`progexec` computed and checked against itself. `mojo/tests/libs/test_progexec_roundexact.mojo`
pins the six real double-rounding cases above, two genuine ties (`0.125`, `-0.125`), the two
integer ties (`1.5`, `2.5`), the `2.675`-is-not-a-tie case, and zero/negative round-tripping.
The full 8,281-program cross-check against the live dataset — not a sample — runs in
`benchmarks/external_baselines/finqa_exec/score.py`; see
[FinQA exact execution](../benchmarks/finqa-exact-execution.md) for those results.

**Next:** see the full accuracy measurement against all 8,281 real gold programs in
[FinQA exact execution](../benchmarks/finqa-exact-execution.md), or how a kernel like this
declares its own determinism and cost in [Declared capabilities](capabilities.md).
