---
icon: toolbox
description: Nine unrelated infrastructure primitives grouped only by being what is left over -- windowed stream aggregates, LLM structured-output scoring, time-zone/date/unit conversion, glob and template string matching, Protocol-Buffers-style binary framing, compiler-theory formulas, and agent/tool-orchestration cost scoring.
---

# Streaming, structured output, and time kernels

Nine modules with no shared subject, documented on one page because each is a small,
self-contained infrastructure primitive rather than part of a larger domain family already
covered elsewhere. Read individually they are: windowed stream aggregates (`streaming.windows`,
which already has its own page and is summarized rather than repeated here), closed-form scoring
formulas for LLM structured-output quality (`structured_output`), a hand-rolled `pytz` stand-in
(`time_zone`), a `pint`-style physical-unit converter (`units`), epoch/civil-calendar arithmetic
replacing Python's `datetime` (`datetime`), glob and template string matching (`pattern`), a
Protocol-Buffers-style binary wire format (`protocol`), closed-form compiler-theory predicates and
metrics (`compiler_theory`), and closed-form scoring formulas for building an LLM agent loop
(`agent_runtime`). They run as compiled kernels inside the runtime that ships with the SDK --
nothing to start, nothing to install separately.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("units", "convert_length", [1.0, "mi", "km"])["result"]
# 1.609344

runtime.execute("time_zone", "utc_to_local", [12, 0, "JST"])["result"]
# [21, 0] -- 12:00 UTC is 21:00 in Tokyo (UTC+9, no DST)
```

## The modules

| Module | What it does |
| --- | --- |
| `streaming.windows` | Rolling minimum, maximum, range, mean, and standard deviation over a sliding window, plus exponentially weighted mean and variance -- already documented in full at [Windowed aggregates](streaming-windows.md); listed here only so this page's own module index is complete |
| `structured_output` | Closed-form scoring formulas for LLM structured-output quality: JSON-FSM next-token validity, SQL clause-ordering validity, XML nesting-depth limits, regex character-class range checks, type-coercion confidence, schema-field confidence and recall, output-repair edit distance, output diversity, and format-compliance rate |
| `time_zone` | A hand-rolled `pytz` stand-in over eleven hardcoded zone abbreviations: UTC-offset lookup, a simplified US/EU daylight-saving calendar, local↔UTC and zone↔zone time conversion, and business-hour overlap |
| `units` | A `pint`-style converter: length, mass, temperature, time, area, volume, speed, and binary (1024-based) data-size conversion, each by a fixed per-unit factor |
| `datetime` | Epoch-second date/time arithmetic replacing Python's `datetime`: Howard Hinnant's civil-calendar algorithm for epoch-to-date and date-to-epoch conversion, ISO-8601 formatting and parsing, leap-year check, day-of-week, day arithmetic, and human-readable duration formatting |
| `pattern` | An `fnmatch`-plus-minimal-`jinja2` stand-in: dynamic-programming glob matching (`*` and `?`), `{{key}}` template substitution, and the split/join/trim/pad/contains/count string toolkit both are built from |
| `protocol` | A hand-rolled Protocol-Buffers wire format: base-128 varint encode/decode, ZigZag signed-integer mapping, and tag-plus-length field/message encode/decode -- not to be confused with `network_protocol` elsewhere in this batch, which is HTTP status text, MIME types, and query-string parsing |
| `compiler_theory` | Closed-form compiler-theory predicates and metrics: LL(1) and LR(1) grammar-conflict checks, binary-AST depth and node count, register pressure, instruction-latency summation, basic-block throughput (IPC), and loop-unroll overhead savings |
| `agent_runtime` | Closed-form scoring formulas for an LLM agent/tool-calling loop: tool-call cost estimate, retry decision, plan-step dependency-bitmask check, RL-style discounted action value, tool-selection score, memory-retrieval relevance, context-window budget, step reward, a schema-hash match check, and remaining cost budget |

## `streaming.windows` already has a dedicated page

`streaming.windows` ships ten functions and two structs (`WindowSeries`, `WindowSummary`) for
rolling min/max/range/mean/std and EWMA/EWM-variance, all built by wrapping frozen kernels
(`timeseries_stats.rolling_mean`, `rolling_std`, `online_learning`'s exponential updates,
`pandas_groupby`'s Welford accumulators) in a result that carries a presence flag, a position
count, and a typed status instead of a bare list. That whole story -- including why `window_std`
is charged as the *product* `n * window` while every other function here is charged as `n`, why a
sliding-window variance is never computed by subtracting a departing observation from a Welford
accumulator, and why `window_summary_std` returns `-1.0` rather than `0.0` for "nothing to
summarize" -- is told in full at **[Windowed aggregates](streaming-windows.md)**. It is repeated
here only as one row in this page's own module table.

`streaming.windows` is a sibling of the four modules documented at
**[Streaming sketches](streaming-sketches.md)** (`streaming.distinct`, `streaming.frequency`,
`streaming.quantiles`, `streaming.drift`): all five share the `streaming.contract` module's status
codes (`STM_OK`, `STM_ERR_WINDOW`, `STM_ERR_NON_FINITE`, and so on) and size ceilings, and
`streaming-windows.md` already cross-links to `streaming-sketches.md` and back. The two page
families answer different questions about the same conceptual stream -- windows over the *last w*
observations versus a summary of *everything seen so far* -- and neither module imports the other.

## Structured-output scoring is metrics, not a constrained decoder

`structured_output` sounds like it should be the grammar-constrained decoding engine that forces
an LLM's next token to stay inside a JSON schema or a regular expression. Reading
`mojo/engine/structured_output.mojo` corrects that: every one of its ten functions is an
independent closed-form `Float64` formula that *scores* one aspect of structured-output quality
from numbers a caller already has -- there is no tokenizer, no grammar compiler, and no FSM that
is actually built anywhere in this module. `json_next_token_valid`, for instance, is documented as
a JSON finite-state machine, but its real body is two `if` statements (object-after-object-open is
invalid, the end state accepts nothing) and a default `1.0` for every other transition -- a coarse
approximation of validity, not a real JSON grammar:

```python
runtime.execute("structured_output", "json_next_token_valid", [1.0, 0.0])["result"]
# 0.0 -- state 1 (inside an object) can't be followed by another '{' without a key first

runtime.execute("structured_output", "json_next_token_valid", [5.0, 7.0])["result"]
# 0.0 -- state 5 is "end"; nothing is valid after it

runtime.execute("structured_output", "json_next_token_valid", [2.0, 3.0])["result"]
# 1.0 -- every other (state, token) pair is allowed by this simplified check
```

The rest score things a serving stack measures after the fact:

```python
import math

runtime.execute("structured_output", "schema_field_confidence",
                [math.log(0.8), 0.9])["result"]
# 0.72 -- exp(log_prob) * schema_match = 0.8 * 0.9

runtime.execute("structured_output", "sql_clause_transition", [3.0, 3.0])["result"]
# 0.5 -- WHERE(3) -> WHERE(3): same-clause continuation, not a forward move

runtime.execute("structured_output", "output_repair_edit_distance", [100.0, 15.0])["result"]
# 0.15 -- 15 character edits over a 100-character malformed output

runtime.execute("structured_output", "type_coercion_score", [3.5, 0.0])["result"]
# 0.5 -- target type is int (0) but 3.5 has a fractional part, so it's a partial match
```

This is the same species of module as `inference_cost_latency` and `inference_security` from
[Multimodal and inference operations kernels](multimodal-and-inference-operations-kernels.md): a
library of scalar heuristics a serving stack plugs its own signals into, never a buffer or a
grammar object, and its own docstring says so directly ("Zero Python imports").

**A naming trap worth flagging.** `agent_runtime` (documented below) declares its own function
called `structured_output_match(output_schema_hash, actual_output_hash)` -- a bare hash-equality
check (`1.0` if the two hashes match, `0.0` otherwise) that has nothing to do with the
`structured_output` module beyond sharing a name fragment. A caller reaching for "the
structured-output match function" by name alone could land in either module and get a
completely different kind of answer; the two are documented separately in this page precisely so
that collision is visible rather than silently assumed away.

## Time zones, units, and dates: three small, explicitly simplified stdlib replacements

`time_zone`, `units`, and `datetime` each replace one Python standard-library or common
third-party module with a pure-Mojo implementation, and each says so in its own docstring. None
claims to be a complete replacement, and each has a real, documented limitation worth knowing
before reaching for it.

**A second naming trap: two `convert_time` functions, in two different modules, with two
different signatures.** `time_zone.convert_time(hour, minute, from_zone, to_zone)` shifts a
wall-clock time between named zones and returns `[hour, minute]`. `units.convert_time(value,
from_unit, to_unit)` is a pure scalar unit conversion -- `convert_time(1.0, "hr", "min")` gives
`60.0` -- with no notion of a zone or a wall clock at all. The runtime contract lists both under
their own module name (`time_zone.convert_time` and `units.convert_time` are never ambiguous to
`runtime.execute`, which always takes the module name first), but a reader skimming for "the
`convert_time` function" by name alone, independent of module, will find two answers to two
different questions.

**`time_zone` covers eleven hardcoded abbreviations, not the IANA database.** `utc_offset` and
`is_valid_zone` recognize exactly `UTC`, `GMT`, `EST`, `CST`, `MST`, `PST`, `CET`, `EET`, `JST`,
`IST`, and `AEST` -- every other name falls through `utc_offset`'s chain to a silent `0.0` (treated
as UTC) while `is_valid_zone` correctly reports it invalid, so a caller who checks validity first
is protected and one who skips that check is not. `is_dst` is a fixed calendar rule, not a real
transition table: US-style zones (`EST`/`CST`/`MST`/`PST`) are "DST" for the *entire* March-through-November
span with no specific transition date or year-dependence, `CET`/`EET` for March-through-October, and
every other zone (`JST`, `UTC`, `AEST`, ...) never observes DST at all -- which is directionally
right for real Japan and wrong in the direction of the calendar for the Southern Hemisphere's
`AEST`, whose real DST months are the opposite half of the year. These are simplifications this
module's own docstring calls out ("Replaces pytz basics"), not silent gaps:

```python
runtime.execute("time_zone", "utc_offset", ["IST"])["result"]
# 5.5 -- India Standard Time, the one non-integer offset in the table

runtime.execute("time_zone", "effective_offset", ["EST", 6])["result"]
# -4.0 -- EST is -5.0 in January and -4.0 in June under the simplified US DST window

runtime.execute("time_zone", "convert_time", [2, 0, "UTC", "PST"])["result"]
# [18, 0] -- 02:00 UTC lands on 18:00 the *previous* day in PST; the result never
# reports a day offset, only wrapped hour:minute

runtime.execute("time_zone", "overlap_hours", ["EST", "CET"])["result"]
# 2 -- of the default 09:00-17:00 workday, EST and CET share 2 hours in UTC
```

**`units` is genuine physical-unit conversion -- and it is not `dimensions`.**
[Dimensionality, information theory, and complex-systems kernels](dimensionality-information-theory-and-complex-systems-kernels.md)
already flags that the batch-6 module named `dimensions` is *not* physical-unit tracking despite
its name -- it is a business-semantics classifier for spreadsheet columns (Count/Currency/Rate/Ratio/Identifier).
`units`, documented here, is the module that actually does what `dimensions`'s name suggests:
eight converters (length, mass, temperature, time, area, volume, speed, data) that multiply by a
fixed per-unit factor, or run the affine Celsius round-trip for temperature. It performs no
dimensional-consistency checking of its own -- there is no function here that rejects converting a
length into a mass -- it trusts the caller to pass compatible units to the right function:

```python
runtime.execute("units", "convert_temperature", [212.0, "F", "K"])["result"]
# 373.15 -- boiling water in Fahrenheit, converted through Celsius to Kelvin

runtime.execute("units", "convert_data", [1.0, "TB", "GB"])["result"]
# 1024.0 -- binary (1024-based), not decimal (1000-based)

runtime.execute("units", "convert_speed", [1.0, "knot", "km/h"])["result"]
# 1.852
```

**`datetime` implements Howard Hinnant's civil-calendar algorithm, and one function quietly breaks
its own "zero Python imports" claim.** `epoch_to_iso`/`iso_to_epoch` and the `year`/`month`/`day`/
`hour`/`minute`/`second` accessors are all built on the same `civil_from_days` /
`days_from_civil` pair (https://howardhinnant.github.io/date_algorithms.html), a well-known
branch-free proleptic-Gregorian algorithm, so they handle negative epochs and leap years correctly
without a lookup table per year. But `now_epoch()` -- despite the module's own header claiming
"Zero Python imports" -- imports `std.python.Python` and calls into CPython's `time.time()` to get
the wall clock, the one function in this module that is not pure Mojo:

```python
runtime.execute("datetime", "epoch_to_iso", [1767225600])["result"]
# "2026-01-01T00:00:00Z"

runtime.execute("datetime", "day_of_week", [1767225600])["result"]
# 3 -- Thursday (0=Monday); 1970-01-01 (epoch 0) is also a Thursday

runtime.execute("datetime", "format_duration_ms", [3661000])["result"]
# "1h 1m 1s"

runtime.execute("datetime", "is_leap_year", [2000])["result"]
# True -- divisible by 400; is_leap_year(1900) is False (divisible by 100, not 400)
```

## Pattern matching is glob and templates, not regex

`pattern`'s docstring is explicit about scope: it replaces `fnmatch` and a minimal slice of
`jinja2`, plus the split/join/trim/pad/contains/count string operations both are built from.
There is no regular-expression engine here -- `glob_match`'s only two special characters are `*`
(any sequence) and `?` (exactly one character), matched with a textbook dynamic-programming table
rather than backtracking:

```python
runtime.execute("pattern", "glob_match", ["*.txt", "file.txt"])["result"]
# True

runtime.execute("pattern", "glob_match", ["test?", "test12"])["result"]
# False -- '?' matches exactly one character, and "12" is two

runtime.execute("pattern", "template_substitute",
                ["{{a}}+{{b}}", ["a", "b"], ["1", "2"]])["result"]
# "1+2"

runtime.execute("pattern", "pad_left", ["hi", 5])["result"]
# "   hi"
```

`regex_constraint_match` in the `structured_output` module (above) is a plain numeric-range check
over a single Unicode code point, not a regular-expression matcher either -- neither of these two
modules implements regex, despite both having functions whose names invoke it.

## Protocol is Protocol Buffers, and it is not `network_protocol`

`protocol`'s docstring states its scope directly: "Protocol Buffer-like serialization primitives."
It implements base-128 varint encoding (7 data bits per byte, the high bit a continuation flag),
ZigZag mapping for signed integers, and protobuf-style tag-plus-value field and message
encode/decode -- a binary wire format, with no HTTP, MIME, or text-protocol concept anywhere in it.
This batch also contains `network_protocol.mojo`, whose own docstring covers a completely
different, non-overlapping surface: HTTP status-code reason phrases, MIME-type lookup by file
extension, `Content-Type` header parsing, and query-string build/parse. The two share the word
"protocol" and nothing else -- neither imports the other, and no function name appears in both.

```python
runtime.execute("protocol", "encode_varint", [300])["result"]
# [172, 2] -- 300 = 0b100101100; low 7 bits (0b0101100=44) with continuation bit
# set (44|128=172), then the remaining 0b10=2 in the second byte

runtime.execute("protocol", "zigzag_encode", [-2])["result"]
# 3 -- ZigZag maps 0,-1,1,-2,2,... to 0,1,2,3,4,...

fields = [[1, 42], [2, 100]]
encoded = runtime.execute("protocol", "encode_message", [fields])["result"]
decoded = runtime.execute("protocol", "decode_message", [encoded])["result"]
# decoded == [[1, 0, 42], [2, 0, 100]]  -- [field_number, wire_type, value] per field
```

## Compiler theory is closed-form predicates, not a lexer, parser, or optimizer

`compiler_theory` is twelve small functions -- boolean conflict checks, arithmetic metrics, one
plain summation -- not a working lexer, parser, or code generator. There is no grammar object, no
token stream, and no instruction-selection pass anywhere in `mojo/engine/compiler_theory.mojo`;
each function takes the numbers a real compiler pass would have already computed (does the FIRST
set contain epsilon, can this LR state both shift and reduce, how many registers are live) and
applies the one-line textbook formula:

```python
runtime.execute("compiler_theory", "grammar_is_ambiguous", [True, False])["result"]
# True -- a shift/reduce conflict alone is enough to call the grammar ambiguous

runtime.execute("compiler_theory", "ast_depth", [3, 5])["result"]
# 6 -- 1 + max(3, 5)

lats = [3, 1, 4, 1, 5]
runtime.execute("compiler_theory", "instruction_latency_sum", [lats, 5])["result"]
# 14 -- sum of all five latencies

runtime.execute("compiler_theory", "loop_unroll_benefit", [100, 2, 4])["result"]
# 150 -- original overhead 100*2=200, unrolled ceil(100/4)*2=50, benefit=150
```

**`instruction_latency_sum`'s count is guarded outside the kernel, not inside it.** The runtime
contract declares a count relation for this function (`n` must not exceed `len(latencies)`), and
reading `mojo/engine/compiler_theory.mojo` shows the kernel itself has no such check --
`for i in range(n): total += latencies[i]` indexes straight past the end of a short `latencies`
list if `n` is too large, which is an unrecoverable abort inside Mojo, not a catchable exception.
The guard lives one layer up: `apps/runtime/mojo_count_relations.py` declares the relation and
`packages/algenta/algenta/runtime_count_guard.py` enforces it in the SDK transport, before the call
ever reaches this kernel, refusing an oversized `n` with a typed `count_exceeds_list_length` error
instead of letting the request through. This is the same pattern documented in the `streaming.windows`
module for `window_summary_prefix`'s `n` parameter, just enforced at a different layer.

## Agent runtime is scoring formulas for building an agent, not Algenta's own agent loop

`agent_runtime`'s name invites the reading that this is the internal scaffolding running
Algenta's own agentic behavior. It is not: `mojo/engine/runtime_library_dispatch_generated.mojo`
wires it through the exact same generic `library_execute` dispatch mechanism as every other
domain kernel in this corpus (`_dispatch_agent_runtime`, registered next to `_dispatch_units` and
`_dispatch_pattern`), with no special-cased internal call path anywhere. It is ten closed-form
`Float64` formulas a *caller* would use to build their own LLM agent/tool-calling system --
the same style and granularity as `structured_output` above, and a sibling in spirit to
`inference_cost_latency` and `inference_security` from
[Multimodal and inference operations kernels](multimodal-and-inference-operations-kernels.md):

```python
runtime.execute("agent_runtime", "tool_call_cost_estimate",
                [200.0, 500.0, 150.0, 0.002])["result"]
# 0.0015 -- (500+150) tokens * $0.002/1k = $0.0013, plus 200ms latency
# weighted at 0.001x = $0.0002

runtime.execute("agent_runtime", "action_value_estimate",
                [1.0, 10.0, 0.9, 2.0])["result"]
# 9.1 -- immediate_reward + discount^steps_remaining * future_value = 1 + 0.9^2 * 10

runtime.execute("agent_runtime", "context_window_budget",
                [128000.0, 100000.0, 4096.0])["result"]
# 23904.0 -- max minus used minus reserved-for-output

runtime.execute("agent_runtime", "agent_cost_budget_remaining",
                [50.0, 100000.0, 20.0, 0.0002, 0.01])["result"]
# 29.8 -- $50 budget minus (100000 tokens * $0.0002 + 20 tool calls * $0.01) = $50 - $20.20
```

`retry_should_attempt` refuses a retry once `attempt >= max_attempts` regardless of error type, and
separately refuses it whenever `last_error_type >= 2.0` ("permanent") regardless of how many
attempts remain -- both conditions are checked, and either one alone is enough to stop. See the
naming-collision note in the structured-output section above for this module's own
`structured_output_match` function, which is unrelated to the `structured_output` module beyond
the shared name fragment.

## Verification notes

Six of these nine modules have real, hand-computed pinned test suites, not just coverage smoke
tests, and every worked example above was cross-checked against one of them or against the plain
arithmetic in the cited source file:

| Kernel | Real pinned test | Smoke-only? |
| --- | --- | --- |
| `time_zone` | `tests/mojo/test_wave45.mojo` | no |
| `units` | `tests/mojo/test_wave22.mojo` | no |
| `datetime` | `tests/mojo/test_wave5.mojo` | no |
| `pattern` | `tests/mojo/test_wave36.mojo` | no |
| `protocol` | `tests/mojo/test_wave41.mojo` | no |
| `compiler_theory` | `tests/mojo/test_wave65.mojo` | no |
| `structured_output` | -- | yes (`mojo/tests/libs/test_structured_output.mojo` only checks each result is finite) |
| `agent_runtime` | -- | yes (`mojo/tests/libs/test_agent_runtime.mojo` only checks each result is finite) |
| `streaming.windows` | `mojo/tests/libs/test_streaming_windows.mojo` | no -- a hand-written known-value suite, not the auto-generated kind, per its own header comment |

For `structured_output` and `agent_runtime`, every number quoted in this page's examples was
computed independently from the plain closed-form arithmetic in
`mojo/engine/structured_output.mojo` and `mojo/engine/agent_runtime.mojo` (`exp(log_prob) *
match`, `discount ** steps_remaining`, and so on) rather than read off any test file, since no
hand-verified suite exists for either module to check against.

**Next:** [Windowed aggregates](streaming-windows.md) for the full `streaming.windows` story,
[Multimodal and inference operations kernels](multimodal-and-inference-operations-kernels.md) for
the closed-form-formula siblings of `structured_output` and `agent_runtime`, or the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
