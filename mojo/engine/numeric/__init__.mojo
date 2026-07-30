"""
numeric — one aggregation contract, for NEW surfaces only.

The existing aggregation paths are frozen and keep working exactly as they do. This
package does not change them and nothing reroutes them through it; it exists so new
surfaces have a single definition to build on instead of adding a fifth.

Why a contract is needed at all
-------------------------------
There are currently four aggregation implementations across the SDKs and server, and
they disagree in ways that are silent rather than loud:

* two canonical tokens — `"avg"` in `/v1/query` and the TS SDK, `"mean"` in the
  Python `algenta` map-query path
* feeding one side the other's token returns SUM, silently, in both directions
  (`.get(aggregation, sum)` on one side, a `default:` case on the other)
* three different means: `statistics.mean`, `sum(v)/len(v)`, and a JS `reduce`
* Python rounds every aggregate to 4 decimals; TypeScript does not round at all
* Python aggregates NaN and ±Inf and treats bool as 1/0; TypeScript requires
  `Number.isFinite` and coerces numeric strings
* an empty group yields 0.0 on one side — a real-looking answer to a question with
  no answer

Every one of those produces a plausible number rather than an error, which is the
worst failure mode for an analytics surface.

Frozen decisions here
---------------------
* canonical token is `"avg"`; `"mean"` is an accepted alias. `"avg"` is what the
  public wire already uses, so choosing `"mean"` would be a breaking change bought
  for internal tidiness.
* an unknown token is a hard error naming the accepted set — never a fallback to sum
* empty reduction: count 0, sum 0, and avg/min/max **null**, not 0.0
* mean is Welford, one implementation
* NaN and ±Inf are rejected at ingest, never aggregated
* no rounding: that is presentation, and belongs to the caller
* nulls are skipped by value aggregates and counted only by `count_all`

Modules:
  contract — aggregation opcodes, token parsing, and the null/empty policy
  reduce   — the reductions themselves, over values plus a validity mask

Invoked directly, not through `library_execute`, so this package is excluded from
the runtime-library inventory.
"""
