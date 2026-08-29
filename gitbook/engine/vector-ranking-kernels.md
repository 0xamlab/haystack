---
icon: ranking-star
description: SIMD Float32 dot-product and cosine-similarity primitives, a resident candidate-vector table, and the JSON-in/JSON-out column-name and repository-file rankers built on top of them.
---

# Vector ranking kernels

Five modules answer one question in two domains: given a name, which of these candidates is
it probably talking about? `vector_kernels.dot` is the SIMD arithmetic underneath everything
else — a 64-lane dot product, an L2 norm inverse, a cosine similarity, and the encoder that
turns an arbitrary string into a 64-bucket bigram-frequency vector. `vector_kernels.table` and
`vector_kernels.ranker` use that encoding to match a raw column name against a schema's
candidate columns (the "which column did the user mean" problem behind spreadsheet/table
resolution). `vector_kernels.repo_ranker` runs the same shape of match against repository file
paths for issue-triage localization. `vector_kernels.batch_ranker` sits on top of the table
with a pre-filtered shortlist scorer, a multi-query batch driver, and the planner-facing helper
that turns a ranking into an accept/ambiguous/fallback decision. None of this is an embeddings
model or an ANN index — it is a fixed-width hashed vector standing in for a name's shape, scored
by cosine similarity and fused with a handful of integer/string boosts.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

a = [1.0] * 64
b = [2.0] * 64
runtime.execute("vector_kernels.dot", "dot64_f32", [a, b])["result"]
# 128.0 — 8 unrolled 8-wide SIMD accumulators, no scalar tail (VEC_DIM=64 is exactly 8x8)

runtime.execute("vector_kernels.table", "source_id_of", ["POS"])["result"]
# 1 — SOURCE_POS; a string that matches none of the known labels maps to 0 (SOURCE_UNKNOWN)
```

## The modules

| Module | What it does |
| --- | --- |
| `vector_kernels.dot` | the four SIMD Float32 primitives everything else here is built from: 64-lane dot product, L2 norm inverse, cosine similarity, and the string→bigram-vector encoder |
| `vector_kernels.table` | a resident `CandidateTable` of pre-encoded columns, plus the typed `RankRequest`/`RankResult` query path that replaced the JSON pipeline for column matching |
| `vector_kernels.ranker` | `run_column_rank_v2` — the JSON-in/JSON-out column-name ranker (cosine + token-Jaccard + role/source boosts); Float32-SIMD successor to `engines.column_ranker` |
| `vector_kernels.repo_ranker` | `run_repo_rank` — the repo-domain sibling: ranks every candidate source file against an issue's query terms in one batched call, for the `/repositories` triage lane |
| `vector_kernels.batch_ranker` | the pre-filtered shortlist scorer, the multi-query batch driver, and `to_planner_resolution`, which turns a `RankResult` into a resolved column, confidence, and fallback flag |

## A name becomes a 64-slot vector, not an embedding

`dot.build_vec64_f32`, `table`'s internal `_build_vec_inplace`, and `ranker`'s internal
`_build_vec` all run the identical algorithm: normalize each byte (`_`, `-`, `.` fold to space;
uppercase folds to lowercase; everything else passes through), then hash every consecutive
normalized byte pair into one of 64 buckets — `h = (prev * 31 + cur) & 63` — incrementing that
bucket. The 64-element result is then L2-normalized by returning `1/‖v‖` as a separate
`norm_inv` scalar (never dividing in place), so `cosine64_f32` computes similarity as a plain
dot product times two pre-computed inverses.

Working the first bigram of `"unit_price"` by hand: normalized bytes `u`(117) and `n`(110) give
`h = (117*31 + 110) & 63 = 3737 & 63 = 25` — bucket 25 gets incremented. This is the exact
formula in `dot.mojo`, `table.mojo`, and `ranker.mojo`; the reference-only ctypes companion
`vector_kernels/ffi_layout.py` (explicitly documented as "not imported at runtime" — a sketch
for a future shared-library export path) asserts the same value as its own self-test. Carrying
the same computation through the full 10-character string of `"unit_price"` lands 9 bigrams in
9 distinct buckets (2, 16, 25, 26, 34, 43, 44, 55, 59), each with count 1, so
`mag_sq = 9` and `norm_inv = 1/3 = 0.3333...`.

`repo_ranker.mojo` uses a different normalizer on purpose: its own `_norm_byte` keeps only
lowercase letters and digits and maps *every other byte* — punctuation, JSON syntax, path
separators — to space, "so bigrams are robust to formatting" (its docstring's words). The
column-name family only folds `_`/`-`/`.`; a literal space or other punctuation in a column
name is not a separator for it. The two families are not interchangeable encoders even though
they share the same hash formula and the same `VEC_DIM=64`.

{% hint style="warning" %}
**64 buckets collide, and the collisions are large enough to matter.** Cosine similarity
between the bigram vectors of `"unit_price"` and the *unrelated* string `"total_amount"` comes
out to `0.5025` — over half — because 5 of `total_amount`'s 11 bigram buckets land on the same
indices as 5 of `unit_price`'s 9 (`{25, 34, 43, 44, 59}`), purely from hash collisions in a
64-slot space. This is exactly why every scoring formula in this family fuses the cosine term
with a token-Jaccard term and integer role/source boosts rather than trusting cosine alone —
a fused score of `0.55 * cosine + 0.25 * jaccard + boosts` cannot be fooled by a lucky hash
collision the way raw cosine can.
{% endhint %}

## The SIMD primitives, worked from the hand-written test

`dot.mojo`'s four functions are covered by a hand-written test, not the corpus's usual
auto-generated one (the generator only synthesizes Float64 fixtures, and these kernels take
Float32 64-lane vectors, so real assertions had to be written by hand):

```python
a = [1.0] * 64
b = [2.0] * 64

runtime.execute("vector_kernels.dot", "dot64_f32", [a, b])["result"]
# 128.0  — Σ(1.0 * 2.0) over 64 lanes

runtime.execute("vector_kernels.dot", "l2_norm_inv_f32", [a])["result"]
# 0.125  — 1/sqrt(64), since a is 64 ones

runtime.execute("vector_kernels.dot", "cosine64_f32", [a, b, 0.125, 0.125])["result"]
# 1.0    — parallel constant vectors → cosine 1
```

Every function in `dot.mojo` guards its SIMD loads rather than reading past the end of a short
list: `dot64_f32`/`l2_norm_inv_f32`/`cosine64_f32` return `0.0` (not an out-of-bounds read, not
an abort) whenever an input has fewer than `VEC_DIM=64` elements, and `build_vec64_f32` returns
`0.0` without writing to `out_vec` at all when the caller's buffer is shorter than 64 — the
test file (`test_vector_kernels_dot.mojo`) exercises both an empty list and a single-element
buffer and asserts the untouched buffer keeps its original length.

## Column matching: `vector_kernels.ranker` and `vector_kernels.table`

`run_column_rank_v2` takes one JSON object — a `query` (`name`, `role_hint`, `source`), a
`candidates` array, and a `top_k` — and returns ranked `matches`, each carrying `source`,
`column`, `score`, `name_sim`, `token_sim`, `type_boost`, and `prior_boost`, plus a
`confidence_gap` and an `ambiguous` flag (`gap < 0.08`). Its own docstring calls it "the same
schema as
`column_ranker.mojo`" (the module's non-SIMD predecessor, still present under
`mojo/engine/engines/`) "but using Float32 SIMD 8-wide kernels for ~1000x Python speedup."

No hand-written test exercises `run_column_rank_v2` with a real query — the only test file for
it is auto-generated and calls it once with the literal string `"test"`, checking only that the
call returns without aborting (which it does: `"test"` contains no `"query"` key, so the source
takes its own documented refusal path and returns `{"error":"missing query.name"}`). Working a
real query by hand, mechanically applying `ranker.mojo`'s published formula — `0.55 * name_sim
+ 0.25 * token_sim + type_boost + prior_boost`, clamped to `[0, 1]`, where the JSON field
`type_boost` is whatever the internal `_role_boost()` helper computes — to
`query = {"name": "unit_price", "role_hint": "unit_measure", "source": "POS"}` against two
candidates:

```python
payload = {
    "query": {"name": "unit_price", "role_hint": "unit_measure", "source": "POS"},
    "candidates": [
        {"source": "orders", "name": "unit_price"},
        {"source": "orders", "name": "total_amount"},
    ],
    "top_k": 5,
}
runtime.execute("vector_kernels.ranker", "run_column_rank_v2", [json.dumps(payload)])["result"]
```

`"unit_price"` against itself scores `name_sim=1.0`, `token_sim=1.0` (identical token sets),
`type_boost=0.12` (the role hint `"unit_measure"` itself tokenizes to `["unit","measure"]`,
which contains `"unit"` — this boost depends only on the query's role hint, never on the
candidate's own name or role, so it comes out identical for every candidate in the result),
and `prior_boost=0.10`
(`"POS"` + a name containing both `"unit"` and `"price"`), summing past 1.0 and clamping to
`1.0000`. `"total_amount"` scores `name_sim=0.5025` (the collision above), `token_sim=0.0`,
the same `type_boost=0.12`, and `prior_boost=0.0` (no `"unit"` in the name), for a fused
`0.3964`. `confidence_gap = 1.0 - 0.3964 = 0.6036`, well past the `0.08` ambiguity threshold,
so `ambiguous` is `false`.

`vector_kernels.table` is the typed, JSON-free hot path the same scoring formula was rebuilt
into: `CandidateTable.add_column` pre-encodes each candidate's bigram vector once at build time
and caches its `norm_inv`; `CandidateTable.rank` then does only SIMD dot products and integer
comparisons per query — no string parsing, no JSON, an insertion-sort top-k, and the same
`AMBIG_GAP=0.08` ambiguity rule. The runtime contract exposes four standalone entry points —
`build_query` (encode a name into a `RankRequest`), `build_table_json` (parse a JSON candidates
array into a resident `CandidateTable`), and the string→integer mappers `source_id_of` /
`role_id_of` (`POS`→1, `BACKLOG`→2, `INVOICE`→3, anything else→0=`SOURCE_UNKNOWN`;
`unit_measure`→1, `derived_measure`→2, anything else→0=`ROLE_OTHER` — case-sensitive, and an
unrecognized string returns the "unknown" constant rather than raising). `CandidateTable.rank`
itself is a method reached by calling those two builders first, not a bare dispatchable
function, so it does not appear as its own contract entry. As with `ranker`, the only test
file for this module (`test_vector_kernels_table.mojo`) is an auto-generated smoke test that
calls each of the four contract functions once with a placeholder string and checks only that
nothing aborts.

## Repository triage: `vector_kernels.repo_ranker`

`run_repo_rank` takes `query_terms` (an array of strings), a `candidates` array of
`{"path", "text"}` objects, and `top_k`, and returns `matches` of `{"path", "score"}` sorted
descending — no role/source boosts, just `0.6 * name_sim + 0.4 * token_sim` clamped to
`[0, 1]`. Its docstring names it plainly: "the production 'extend Mojo for repos' kernel for
the `/repositories` triage ranking lane."

The hint that this backs `apps/api_server/services/repository_intelligence_lexical.py` does
not hold up — that file wires a different lane entirely: Telys' `LexicalCodeIndex` from
`memengine.lexical` (a kernel-backed BM25 index over code text), gated by its own
`ALGENTA_REPOSITORIES_LEXICAL_RANKING` flag, with no reference to `vector_kernels` anywhere in
it. The real, current caller is
**`apps/api_server/services/repository_intelligence_sdk_ranking.py`**, gated by
`ALGENTA_REPOSITORIES_SDK_RANKING` (default off). Its module docstring is explicit about the
plan: a per-candidate `text.fuzzy.jaro_winkler_similarity` dispatch is "today's" lane (fixing
camelCase/snake_case recall an exact-substring heuristic misses), while "a batched
`vector_kernels.repo_ranker` Mojo entrypoint can later replace the per-candidate dispatch for
production scale" — its own comments describe `run_repo_rank` as "benchmarked at ~44 us / 50
candidates" and note the fallback exists because the batched kernel may not yet be
dispatchable in every deployment. `_dispatch_repo_ranker` calls
`runtime.execute("vector_kernels.repo_ranker", "run_repo_rank", payload)` first and falls back
to the per-candidate fuzzy lane only if that call fails or is refused; both the module name and
the function name are asserted directly in the test suite's
`test_batched_repo_ranker_dispatch` case — though that test's `0.81`/`0.1` scores come from a
mocked runtime exercising the wiring, not real kernel arithmetic.

For a real number, working `repo_ranker.mojo`'s algorithm by hand for query terms
`["normalize", "status"]` against a candidate whose text is `"src svc normalize_status"`: the
query text is built from the raw `["normalize","status"]` JSON substring (quotes and the comma
fold to spaces under `repo_ranker`'s all-non-alnum-is-a-separator rule, but the tokenizer still
recovers `["normalize", "status"]` cleanly), giving `name_sim=0.7891`. The candidate text
tokenizes to `["src", "svc", "normalize", "status"]` — the underscore in `normalize_status` is
itself a separator under that same rule, so it splits into two tokens, both of which are also
query tokens: `intersect=2`, `union=2+4-2=4`, `token_sim=0.5`. Fused score:
`0.6 * 0.7891 + 0.4 * 0.5 = 0.6735`. A second, unrelated candidate
(text `"docs readme project overview"`) scores `name_sim=0.4178`, `token_sim=0.0`, fused
`0.2507`. As with `ranker`, the shipped test for this module
(`test_vector_kernels_repo_ranker.mojo`) is an auto-generated smoke test that calls
`run_repo_rank("test")` once and checks only for no abort — which matches the source's
documented refusal path (`"test"` has no `"query_terms"` key, so it returns `{"matches":[]}`).

## Batch scoring and the planner decision: `vector_kernels.batch_ranker`

`rank_shortlist` and `rank_batch` are the internal machinery — not standalone contract
entries — that sit on top of `table.mojo`'s `CandidateEntry`/`CandidateTable` shapes. `rank_batch`
walks a token-posting index to build a shortlist per query, falls back to scoring every column
when the shortlist has fewer than 2 hits (setting `FLAG_FALLBACK_USED`), and hands the
shortlist to `rank_shortlist`, which adds a token-overlap bonus (`+0.05` per shared token,
capped at 3 tokens = `+0.15`) on top of the same weighted-cosine fusion as `table.mojo`. These
two are exercised by a hand-written test, not the auto-generated smoke tests: building one
`CandidateEntry(column_id=7)` whose vector comes from `build_vec64_f32("unit_price")` and
querying with the same name, `rank_shortlist(entries, req, [0], [0], 1)` returns `count=1` with
`entries[0].column_id == 7` (a perfect self-match); calling it again with zero candidates
(`rank_shortlist(entries, req, [], [], 0)`) returns `count=0` rather than aborting.

The one function this module exposes through the runtime contract is `to_planner_resolution`,
which takes a `RankResult` and compresses it to the fields a decision planner actually needs:
`resolved_column_id`, `score`, `confidence_gap`, and three booleans — `confident` (best score
`>= MIN_ACCEPT` (`0.72`) **and** gap `>= AMBIG_GAP` (`0.08`), read off `planner_flags` bit 0),
`ambiguous` (gap `< 0.08`, `planner_flags` bit 2), and `fallback_used` (the all-column fallback
fired, `planner_flags` bit 1). Its single parameter is itself a struct produced upstream by
`rank_shortlist` or `CandidateTable.rank`, so in practice it is chained after one of those
rather than called with hand-built literal arguments. The default, never-populated
`PlannerResolution()` is worth noting on its own: `ambiguous` defaults to `True` and
`confident` defaults to `False` — a struct nobody filled in reads as "not resolved," not as an
accepted match.

## Verification notes

`test_vector_kernels_dot.mojo` and `test_vector_kernels_batch_ranker.mojo` are hand-written,
with real numeric assertions (`dot64_f32([1.0]*64, [2.0]*64) == 128.0`; `rank_shortlist`
returning the seeded `column_id=7`) — both files say so directly, because the corpus's
auto-generator only synthesizes `Float64` fixtures and these kernels take Float32 64-lane
vectors and vector-of-structs shapes it cannot produce. `test_vector_kernels_table.mojo`,
`test_vector_kernels_ranker.mojo`, and `test_vector_kernels_repo_ranker.mojo` are
auto-generated: each calls its module's contract functions once with a placeholder string and
checks only that the call completes, so the worked examples above for `run_column_rank_v2` and
`run_repo_rank` are independent hand-computations against the published source, not lifted
from a verified fixture — flagged as such rather than presented as test output.

**Next:** see [Retrieval](retrieval.md) for the SDK's higher-level, embedding/ANN-backed search
surface these hash-based kernels are not — or the [runtime library catalog](runtime-library-catalog.md)
for every module and function in the engine.
