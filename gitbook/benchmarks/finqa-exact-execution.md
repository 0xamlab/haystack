---
icon: calculator
description: Execution accuracy on all 8,281 gold programs in the real FinQA dataset — Algenta's exact-arithmetic driver against three real naive-reimplementation baselines, on the dataset's own exe_ans, at the dataset's own exact-match rule.
---

# FinQA exact execution

FinQA (Chen et al., EMNLP 2021, [github.com/czyssrs/FinQA](https://github.com/czyssrs/FinQA))
scores a financial question-answering system by EXECUTING a short program — up to six chained
steps over ten operations (`add`, `subtract`, `multiply`, `divide`, `exp`, `greater`,
`table_max`, `table_min`, `table_sum`, `table_average`) drawn from a real SEC filing's text and
tables — against the dataset's own precomputed numeric answer, `exe_ans`. Deciding WHICH
operations and WHICH table cells is the language half of the task. Executing the program once
that decision is made is pure arithmetic, and this page measures that half only: given the
dataset's own gold program, does the execution reproduce `exe_ans` exactly?

This is not the "FinQA OpenEnv" agentic-tool-use benchmark published by Snorkel AI and UC
Berkeley's rLLM team in 2026 (a different dataset built from SEC 10-K tables via SQL and
calculator tools, scored by an LLM judge) — that benchmark's bottleneck is agentic tool-use
discipline, not arithmetic, and this page does not address it. It measures the classic,
execution-accuracy FinQA dataset directly.

## Results

All 8,281 programs with a gold program and a gold `exe_ans` across FinQA's train, dev and test
splits — every one of them, none excluded for being hard, and 0 excluded for any reason (see
[Scope](#scope)). Exact match is the dataset's own rule: `round(final_step, 5) == exe_ans`,
plain equality, nothing fuzzy.

| Arm | Exact match | Wrong |
| --- | --- | --- |
| naive: steps-annotation substitution | 94.07076% | 491 |
| naive: round every intermediate step | 98.43014% | 130 |
| naive: single-multiply final round | 99.92754% | 6 |
| **Algenta (`progexec`)** | **100.00000%** | **0** |

Algenta is the exact ceiling this metric admits, and every naive re-implementation — including
the one that gets 8,275 of 8,281 right — is strictly behind it. Zero of the divergences below
are constructed for this page; every one is a real gold program, replayed and checked against
the dataset's own `exe_ans`.

## Where the divergences come from

Three independent, real ways to reproduce the official evaluator's spec and get it wrong,
verified by running each of them over the full dataset rather than assumed from reading the
spec.

### 1. Rounding every intermediate step, not only the final one

The official evaluator (`code/evaluate/evaluate.py`) keeps every intermediate result as an
unrounded Python float and calls `round(x, 5)` exactly once, on the last step. Its own source
carries a commented-out `# this_res = round(this_res, 5)` inside the table-aggregate branch —
someone re-implementing the spec from that file is one keystroke from uncommenting it, and from
applying the same instinct to the arithmetic branch, which has no such line at all. Six real
examples, gold vs. this naive arm:

| Question id | Program | Gold `exe_ans` | Round-every-step |
| --- | --- | --- | --- |
| `IPG/2009/page_89.pdf-3` | `subtract(34.8,1.2), divide(#0,34.8), multiply(#1,const_100)` | 96.55172 | 96.552 |
| `PNC/2014/page_94.pdf-1` | `divide(34.7,17), multiply(#0,const_100)` | 204.11765 | 204.118 |
| `DRE/2008/page_29.pdf-3` | `subtract(85936,83000), divide(#0,83000), multiply(#1,const_100)` | 3.53735 | 3.537 |
| `HWM/2015/page_95.pdf-2` | `divide(13,167), multiply(#0,const_100)` | 7.78443 | 7.784 |
| `JPM/2009/page_132.pdf-2` | `divide(39,37), subtract(#0,const_1), multiply(#1,const_100)` | 5.40541 | 5.405 |
| `DVN/2015/page_117.pdf-1` | `divide(const_100,17), multiply(376,#0)` | 2211.76471 | 2211.7636 |

130 of the 8,281 programs diverge this way — 3.8% of the 3,378 programs with at least one
back-reference, which is the population where rounding an intermediate can even reach the
final answer.

### 2. The "obvious" final round, ported to a non-Python host

Rounding the final result the way almost any non-Python language's obvious tool rounds a
decimal — multiply by 100000.0 in float64, round to the nearest integer, divide back —
double-rounds whenever the true value of `x * 100000` sits within about half an ULP of an
integer-plus-one-half, because the multiply's own single rounding step can silently corrupt a
value that is genuinely close to, but not exactly at, that boundary. Measured directly: Mojo's
own builtin `round(x, 5)` does exactly this and gets six real gold programs wrong.

| Question id | Program | Gold `exe_ans` | Naive final round |
| --- | --- | --- | --- |
| `HII/2011/page_100.pdf-3` | `multiply(83.7,7.81%), divide(#0,const_2)` | 3.26849 | 3.26848 |
| `RE/2010/page_42.pdf-4` | `subtract(364.3,160.0), divide(#0,160.0)` | 1.27687 | 1.27688 |
| `CAT/2017/page_69.pdf-2` | `multiply(const_1000,1.6), subtract(365,#0), divide(#1,#0)` | -0.77187 | -0.77188 |
| `IP/2012/page_84.pdf-2` | `divide(3.7,32)` | 0.11563 | 0.11562 |
| `ETR/2017/page_143.pdf-2` | `subtract(857679,760000), divide(#0,760000)` | 0.12853 | 0.12852 |
| `HIG/2011/page_53.pdf-1` | `divide(57,320)` | 0.17813 | 0.17812 |

This is not hypothetical inside this tree either. `mojo/engine/currency.round_currency` — a
frozen kernel already shipping, docstring-labelled "banker's rounding" — shares the same
single-multiply mechanism and is separately round-half-up rather than round-half-to-even
(`round_currency(2.5, 0)` returns `3.0`; true round-half-to-even returns `2.0`). Measured
directly against all six cases above, `round_currency` gets five right — round-half-up happens
to land on the correct side of the corrupted value for those five — and `RE/2010/page_42.pdf-4`
wrong, the same as the builtin. Measured separately against the full 8,127 numeric gold
programs, its round-half-up bias produces five of ITS OWN wrong answers — ties that
round-half-to-even correctly leaves alone but round-half-up rounds up on principle:
`INTC/2016/page_33.pdf-3`,
`RE/2010/page_42.pdf-4`, `ZBH/2008/page_70.pdf-2`, `CMCSA/2008/page_59.pdf-4`,
`AMT/2012/page_118.pdf-2`.

### 3. Trusting the dataset's own human-readable step annotations

FinQA ships a `steps` field per question — a natural-language trace like `"divide(100, 100) =
1%"` — alongside the machine `program`. A step that references an earlier one by index (`#0`)
means "the raw float that step computed"; substituting the DISPLAYED value instead (re-parsed
with the same percent-aware parser the official evaluator uses for literal operands) is the
natural mistake for any pipeline that treats the annotation trace as ground truth for what a
prior step "is". 491 of the 3,378 programs with at least one back-reference (14.5%) diverge
this way — including the dataset's own first training record:

| Question id | Program | Gold `exe_ans` | Steps-substitution |
| --- | --- | --- | --- |
| `ADI/2009/page_49.pdf-1` | `divide(100,100), divide(3.8,#0)` | 3.8 | 380.0 |
| `C/2010/page_272.pdf-1` | `divide(2.5,1.6), divide(#0,1.6)` | 0.97656 | 0.5625 |
| `ANSS/2012/page_92.pdf-1` | `add(100000,92500), add(#0,#0), add(#1,const_3), divide(#2,const_2)` | 192501.5 | 91000.0 |
| `HWM/2016/page_52.pdf-2` | `divide(970,100), multiply(#0,100), subtract(#1,100)` | 870.0 | -90.3 |

## Cost

Not published as a claim: this page is about exactness, not throughput. For scale, executing
all 8,281 programs — reading the flat spec, walking every step, calling `numeric.reduce` for
table aggregates, and the double-double round-half-even finalizer — takes 0.27s single-threaded
in the compiled `-O3` binary and 3.5s under the JIT, on the hardware below. Neither number is
offered as a ratio against anything; there is no reference execution engine at the same
exactness to compare it to.

## Method

* **Dataset.** The real FinQA dataset (MIT licensed), all three public splits — `train.json`
  (6,251 records), `dev.json` (883), `test.json` (1,147) — for a population of 8,281 programs,
  every one with both a gold program and a gold `exe_ans`. `private_test.json` (919 records) has
  no published program or answer and is not part of this population.
* **Metric.** The official evaluator's own rule, read from `code/evaluate/evaluate.py` rather
  than assumed: every intermediate arithmetic result stays an unrounded Python `float`;
  `round(x, 5)` — Python's round-half-to-even, decided from the exact value, not from a
  single-multiply approximation of it — is called exactly once, on the final step. A predicted
  result is correct iff it equals `exe_ans` by plain `==`.
* **Same program, three drivers.** All three arms and Algenta's `progexec` execute the
  IDENTICAL resolved operand sequence per program — same operator, same literals, same
  back-references, same table cells (already extracted by a Python lookup, since selecting a
  table row by name is parsing, not arithmetic; see Scope). Only the arithmetic driver differs.
* **Cross-checked before scoring.** Every program's resolved operand sequence is replayed
  through a direct, byte-for-byte port of the official evaluator before being handed to any
  arm, and excluded (not scored) if that replay does not reproduce `exe_ans` — 0 programs were
  excluded this way, so every one of the 8,281 in the results table is a program this page's own
  resolution is independently confirmed correct on.
* **Bit-exact input.** Every float crosses into the Mojo binary as a 16-hex-digit IEEE-754 bit
  pattern (no ASCII decimal round trip), the same convention
  [Least-squares accuracy](least-squares-accuracy.md) uses.
* **Two code-generation paths, asserted identical.** `progexec`'s results are produced under
  both the JIT (`mojo run`) and a compiled `-O3` binary; every one of the 8,281 results is
  byte-identical between the two.
* **Hardware.** Apple M4 Max, 16 cores, 128 GiB. Exactness claims on this page are
  machine-independent (IEEE-754 float64 arithmetic and CPython's round are both fully
  specified); hardware is disclosed for the cost figures only.

## Scope

* **The three naive arms are execution strategies, not products.** There is no competing
  published tool that claims exact FinQA program execution to measure against; the comparison
  this page makes is the one the task requires — the SAME resolved program, run through
  Algenta's driver and through three independently-motivated, real ways a competent
  implementation could get the final number wrong. Each is anchored in something real: the
  official evaluator's own commented-out line, this tree's own frozen `currency.round_currency`
  kernel and Mojo's own builtin `round`, and the dataset's own shipped `steps` annotation field
  — none is a constructed strawman.
* **Table-cell selection is a lookup, done once, outside the timed/scored arithmetic.** Given a
  `table_*` operation's row name, extracting that row's numeric cells from the report's table is
  a string-keyed lookup — decided once, identically, for every arm — not arithmetic. Deciding
  WHICH row to look up is program generation (the LLM's job in a real pipeline) and is outside
  this page's scope entirely: every program here is the dataset's own gold program.
* **One dead branch in the official evaluator is refused, not silently mishandled.** The
  official evaluator's `table_*` branch has an unreachable back-reference case (a table row
  selected by `#i` rather than by name); replaying all 8,281 gold programs against a
  byte-for-byte port of the official evaluator confirms zero of them exercise it.
  `progexec.exec` requires a table row to be a literal name and returns a typed refusal rather
  than accepting the case that never occurs in the real data.
* **This is the classic FinQA dataset, not "FinQA OpenEnv."** A 2026 Snorkel AI / UC Berkeley
  rLLM benchmark on Meta's OpenEnv framework also uses the name "FinQA" for an unrelated,
  SQL-and-calculator-tool agentic dataset, scored by an LLM judge on 10-K SQLite tables. That
  benchmark's own published numbers (`rLLM/rLLM-FinQA-4B` model card) show an RL-trained 4B
  model beating a frozen 235B model — the opposite pairing from a frozen-small-model-plus-tool
  narrative — and reproducing it end-to-end would require paid third-party LLM API calls this
  page does not make. This page is unrelated to that benchmark and makes no claim about it.

## Reproduce

Clone the real dataset (not vendored in this repository; MIT licensed, ~104MB across the three
splits):

```text title="dataset"
git clone https://github.com/czyssrs/FinQA /tmp/FinQA
```

Build the flat input spec and the naive-baseline reference values from the real dataset:

```text title="prepare"
python3 benchmarks/external_baselines/finqa_exec/emit_specs.py /tmp/FinQA/dataset /tmp/finqa_out
```

Run Algenta's driver over every program (JIT shown; `mojo build --optimization-level 3` for the
compiled comparison):

```text title="benchmark"
mojo run -I mojo/engine benchmarks/mojo_benchmarks/measure_progexec_finqa.mojo /tmp/finqa_out/finqa_progexec.spec
```

Score `progexec` and all three naive arms against `exe_ans`, in one process, at the dataset's
own exact-match rule:

```text title="score"
python3 benchmarks/external_baselines/finqa_exec/score.py /tmp/finqa_out
```

## See also

* [Benchmarks](overview.md)
* [Least-squares accuracy](least-squares-accuracy.md)
* [Runtime library catalog](../engine/runtime-library-catalog.md)
