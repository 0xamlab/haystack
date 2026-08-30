---
icon: compass
description: RAG-specific fusion and quality scores, user-user collaborative filtering, ground-truth ranking metrics, vector-embedding arithmetic, and credit-style scoring formulas — five independent scalar libraries, not one pipeline.
---

# Retrieval, recommendation and ranking kernels

Five modules for five different questions a search-and-recommendation stack asks separately.
`rag_retrieval` scores a single candidate from a RAG-specific signal — reciprocal-rank fusion,
BM25, a hybrid blend, a cross-encoder logit, MMR diversity, chunk overlap, citation coverage,
answer faithfulness. `recommender` predicts a rating nobody has entered yet, from how similar two
users' existing ratings are. `rerank_eval` grades a ranking that already exists against
ground-truth relevance labels — precision, recall, MRR, MAP, NDCG. `embeddings` is the vector
arithmetic everything above quietly assumes: dot product, cosine similarity, Euclidean/Manhattan
distance, k-nearest-neighbors, centroid. `scoring` turns a raw number into something a human reads
as a probability or a credit score — sigmoid, logit, Weight of Evidence, Information Value, Gini,
KS. None of the five imports another, none defines a struct or a status-code range, and every
function takes and returns plain `Float64` / `Int` / `List[Float64]` values — composing them into
an actual pipeline is the caller's job, and (as the sections below show) six of `rag_retrieval`'s
ten formulas are already composed for you, one level up.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# a document ranked 3rd by the dense lane, 1st by the sparse lane, RRF constant 60
runtime.execute("rag_retrieval", "rrf_score", [3.0, 1.0, 60.0])["result"]
# 0.032266458495966696 -- 1/63 + 1/61; the same fold retrieval.fuse.rrf_fuse_flat
# runs, one level up, over a whole ranked list instead of one pair of ranks

runtime.execute("embeddings", "cosine_similarity", [[1.0, 0.0], [-1.0, 0.0]])["result"]
# -1.0 -- exactly opposite vectors
```

## The modules

| Module | What it does |
| --- | --- |
| `rag_retrieval` | Reciprocal rank fusion, BM25 term scoring, hybrid dense/sparse blending, a cross-encoder logit, MMR diversity, chunk-overlap ratio, and four RAG-quality ratios (retrieval precision, citation coverage, context relevance, answer faithfulness). |
| `recommender` | User-user collaborative filtering: cosine similarity between two users' ratings, a k-NN weighted-average rating prediction, popularity ranking, per-item/per-user rating means, top-n item selection, item co-rating overlap, cold-start recommendation, and RMSE. |
| `rerank_eval` | Offline ranking-quality metrics graded against ground-truth relevance labels: precision@k, recall@k, hit rate@k, MRR@k, MAP@k, NDCG@k, pairwise margin accuracy, score separation, and a latency-discounted quality score. |
| `embeddings` | SIMD-vectorized vector arithmetic: dot product, cosine similarity, Euclidean/Manhattan distance, L2 normalization, centroid, nearest-neighbor and k-nearest-neighbors search, an N×N similarity matrix, vector add/scale, plus `_strict` siblings of the lenient originals. |
| `scoring` | Sigmoid/logit, log-odds ↔ credit-score conversion, Weight of Evidence and Information Value, Gini coefficient and KS statistic from a classifier's scores, score banding, linear scoring, and min-max normalization. |

## `rag_retrieval`: the frozen formulas underneath two higher-altitude pages

| Function | What it does |
| --- | --- |
| `rrf_score(rank_dense, rank_sparse, k)` | `1/(k+rank_dense) + 1/(k+rank_sparse)` — Reciprocal Rank Fusion over exactly two ranks. |
| `hybrid_search_score(vector_score, bm25_score, alpha)` | `alpha*vector + (1-alpha)*bm25` — dense/sparse blend. |
| `bm25_term_score(tf, df, n_docs, doc_len, avg_doc_len, k1, b)` | The Okapi BM25 term contribution: IDF times a saturating term-frequency curve normalized by document length. `0.0` if `df <= 0` or `n_docs <= 0`. |
| `cross_encoder_logit(query_repr, doc_repr, bias)` | `query_repr * doc_repr + bias` — one dimension's contribution to a cross-encoder logit; the caller sums across dimensions. |
| `chunk_overlap_ratio(chunk_size, overlap_size)` | `overlap_size / chunk_size`, the fraction of a sliding-window chunk shared with its neighbor; `0.0` if `chunk_size <= 0`. |
| `context_relevance_score(query_terms_in_context, total_query_terms)` | `query_terms_in_context / total_query_terms`; `0.0` if the denominator is `<= 0`. |
| `answer_faithfulness_score(answer_claims_supported, total_answer_claims)` | `supported / total`; **`1.0`**, not `0.0`, if there are no claims to check — an empty claim set is vacuously faithful. |
| `citation_coverage(cited_chunks, total_retrieved)` | `cited / retrieved`; `0.0` if nothing was retrieved. |
| `retrieval_precision(relevant_retrieved, total_retrieved)` | `relevant / retrieved`; `0.0` if nothing was retrieved. Not clamped to `[0, 1]` — feeding it a `relevant_retrieved` larger than `total_retrieved` returns a precision above `1.0`. |
| `mmr_diversity_score(relevance, max_similarity_to_selected, lambda_mmr)` | `lambda*relevance - (1-lambda)*max_sim` — Maximal Marginal Relevance for one candidate against the set already selected. |

Worked by hand from the real formulas: `bm25_term_score(2.0, 10.0, 100.0, 50.0, 100.0, 1.5, 0.75)`
— a term appearing twice in a 50-token document, half the average 100-token length, seen in 10 of
100 documents — computes `idf = ln((100-10+0.5)/(10+0.5) + 1) = ln(9.619048) = 2.263844`,
`norm = 50/100 = 0.5`, `denom = 2 + 1.5*(1 - 0.75 + 0.75*0.5) = 2.9375`, and returns
`2.263844 * 2 * 2.5 / 2.9375 = 3.853183420728139`. A shorter chunking example:
`chunk_overlap_ratio(512.0, 128.0) = 0.25` — a 512-token chunk with 128 tokens of overlap shares a
quarter of its content with its neighbor. `cross_encoder_logit(0.5, 0.8, -0.2) = 0.5*0.8 - 0.2 =
0.2`; `citation_coverage(3.0, 5.0) = 0.6`; `answer_faithfulness_score(8.0, 10.0) = 0.8`.

**This module is the scalar layer two other pages already build on, and four of its ten functions
are not wired to anything yet.** [Retrieval fusion and signal kernels](retrieval-fusion-and-signal-kernels.md)
documents `retrieval.fuse` and `retrieval.score` as frozen compositions "over even-lower-level
scalar kernels in `rag_retrieval.mojo`," and reading that page's own mapping table confirms exactly
which six:

| `rag_retrieval` function | driven, one level up, by |
| --- | --- |
| `rrf_score` | `retrieval.fuse.rrf_fuse_flat` — folds it pairwise across N ranked lanes |
| `hybrid_search_score` | `retrieval.score.hybrid_rank_flat` — runs it once per candidate |
| `mmr_diversity_score` | `retrieval.score.mmr_select_flat` — runs it inside a greedy selection loop |
| `retrieval_precision`, `citation_coverage`, `context_relevance_score` | `retrieval.score.retrieval_quality_flat` — pairs each with a `_known` flag for the zero-denominator case |

Two levels up from that, [Retrieval](retrieval.md)'s Python verbs `hybrid_search(fusion="rrf")`,
`hybrid_search(fusion="linear")` and `rerank` are the same arithmetic again, reached through
`retrieval_execution.py`. The remaining four `rag_retrieval` functions —
`bm25_term_score`, `cross_encoder_logit`, `chunk_overlap_ratio`, and `answer_faithfulness_score` —
have no caller anywhere in `packages/algenta/algenta/` today; they are real, tested, and reachable
only by calling `rag_retrieval` directly, the same way `retrieval_quality_flat` was found to be an
unwired survivor on the fusion page.

## `recommender`: user-user collaborative filtering

| Function | What it does |
| --- | --- |
| `cosine_sim_users(ratings, u1, u2)` | Cosine similarity between two users, computed only over items **both** rated (a `0.0` entry means unrated, not "rated zero"). `0.0` if either user index is out of range. |
| `predict_rating(ratings, user, item, k)` | KNN collaborative filter: gathers every other user who rated `item` and has positive similarity to `user`, keeps the `k` most similar, and returns their ratings weighted by similarity. `0.0` if there is no such neighbor. |
| `popularity_ranking(ratings)` | Item indices ordered by how many users rated them, descending. |
| `mean_rating_per_item(ratings)` / `mean_rating_per_user(ratings)` | Average rating, excluding `0.0` (unrated) entries; `0.0` for an item/user with no ratings at all. |
| `top_n_items(item_scores, n)` | Indices of the `n` highest-scoring items, descending. |
| `item_overlap(ratings, u1, u2)` | Count of items both users rated. |
| `cold_start_recommend(ratings, n)` | The top-`n` items from `popularity_ranking` — a strategy for a user with no history. |
| `rmse_ratings(predicted, actual)` | RMSE over entries where `actual != 0.0`; `0.0` if `predicted` is shorter than `actual`. |

A worked 3-user, 4-item matrix (`0.0` = unrated):

```
        item0  item1  item2  item3
user0:   5.0    4.0    —      1.0
user1:   5.0    4.0    5.0    1.0
user2:   1.0    5.0    3.0    5.0
```

`cosine_sim_users(ratings, 0, 1) = 1.0` — user1 agrees with user0 on every item they share
(items 0, 1, 3), so the similarity is exact. `cosine_sim_users(ratings, 0, 2) = 0.6482037235521643`
— user2 shares the same three items but rates them very differently (`1.0` vs `5.0` on item 0).
Predicting user0's missing item 2 (`predict_rating(ratings, 0, 2, 2)`) blends both neighbors'
ratings for that item, weighted by their similarity to user0:
`(1.0*5.0 + 0.6482*3.0) / (1.0 + 0.6482) = 4.213442228907027` — closer to user1's `5.0` than
user2's `3.0`, in proportion to how much more user1 agrees with user0 elsewhere.
`item_overlap(ratings, 0, 1) = 3` (items 0, 1, 3). `popularity_ranking(ratings) = [0, 1, 3, 2]`
(items 0, 1, 3 were all rated by all three users; item 2 by only two — ties among the count-3 items
keep their original order, since the insertion sort's `<` comparison only moves a strictly
higher count ahead). `mean_rating_per_item(ratings) = [3.6667, 4.3333, 4.0, 2.3333]`.

**`item_overlap` skips the bounds check its sibling functions perform.** `cosine_sim_users` and
`predict_rating` both check `u1`/`u2` (or `user`) against `len(ratings)` before indexing and return
`0.0` on an out-of-range index — their comments call these "untrusted user indices" explicitly.
`item_overlap` has no such check: it indexes `ratings[u1]` and `ratings[u2]` directly, so an
out-of-range user index reaches an out-of-bounds `List` read rather than a graceful `0.0` — the
same uncatchable, worker-killing abort this corpus has flagged elsewhere for unguarded index
arguments, not a return value a caller can branch on.

## `rerank_eval`: grading a ranking against ground truth, not producing one

| Function | What it does |
| --- | --- |
| `precision_at_k(relevance, k)` | Fraction of the top-`k` that are relevant (`relevance[i] > 0`). |
| `recall_at_k(relevance, total_relevant, k)` | Relevant hits in the top-`k`, divided by `total_relevant` (not by `k`). |
| `hit_rate_at_k(relevance, k)` | `1.0` if any of the top-`k` is relevant, else `0.0`. |
| `mrr_at_k(relevance, k)` | `1 / rank` of the first relevant item in the top-`k`; `0.0` if none. |
| `map_at_k(relevance, k)` | Mean of the precision values measured at each relevant hit's own rank, within the top-`k`. |
| `ndcg_at_k(gains, ideal_gains, k)` | DCG over `gains` divided by DCG over `ideal_gains`, both discounted by `ln(rank+2)`; negative gains are clamped to `0.0` first. |
| `pairwise_margin_accuracy(positive_scores, negative_scores, margin)` | Fraction of paired (positive, negative) scores where `positive >= negative + margin`. |
| `score_separation(positive_scores, negative_scores)` | Mean positive score minus mean negative score. |
| `latency_weighted_quality(quality_score, latency_ms, target_latency_ms)` | `quality / (1 + latency/target)` — a quality score discounted for exceeding a latency budget. |

Worked on `relevance = [1, 0, 1, 0, 1]` (5 candidates, 3 of them relevant, `total_relevant = 3`,
`k = 5`): `precision_at_k = 3/5 = 0.6`, `recall_at_k = 3/3 = 1.0`, `mrr_at_k = 1/1 = 1.0` (the first
relevant item is already at rank 1), and `map_at_k` averages precision at each hit's own rank —
`(1/1 + 2/3 + 3/5) / 3 = 0.7555555555555555`. For `ndcg_at_k`, on
`gains = [3, 2, 3, 0, 1]` against `ideal_gains = [3, 3, 2, 1, 0]` (the same multiset, optimally
ordered), `dcg = 8.8707...`, `ideal_dcg = 9.1229...`, giving
`ndcg_at_k = 0.9723642841729144` — this ranking recovers 97.2% of the gain the ideal ordering
would have delivered.

**Distinct from `rag_retrieval`, and distinct from what `retrieval.score` already wraps.**
`rag_retrieval`'s precision-shaped functions (`retrieval_precision`, `citation_coverage`,
`context_relevance_score`) take two raw counts and divide — they never see a ranked list or a
position, so they cannot express "relevant, but ranked 40th." `rerank_eval`'s functions all take a
`relevance` list indexed by rank (or, for MRR/MAP/NDCG, care about *where* in that list a hit
lands), which is the one thing the `rag_retrieval` ratios cannot represent. The two families are
complementary, not overlapping — one answers "how much of what came back is relevant," the other
answers "how well ordered was it." Confirming there is no third answer to check against:
`retrieval.score.retrieval_quality_flat` (documented on the fusion page above) drives exactly the
three `rag_retrieval` ratio functions, not `rerank_eval`'s NDCG/MRR/MAP — and grepping `gitbook/`
for `rerank_eval`'s own function names (`ndcg_at_k`, `mrr_at_k`, `precision_at_k`, and the rest)
turns up nothing outside this page.

## `embeddings`: SIMD vector arithmetic, and the lenient/strict split

| Function | What it does |
| --- | --- |
| `dot_product(a, b)` / `dot_product_strict(a, b)` | Dot product, SIMD-accumulated over `min(len(a), len(b))` lanes at a time; the `_strict` sibling raises on a length mismatch instead of silently truncating. |
| `cosine_similarity(a, b)` / `_strict` | Cosine similarity; `0.0` if either vector has zero magnitude. |
| `euclidean_distance(a, b)` / `_strict` | L2 distance. |
| `manhattan_distance(a, b)` / `_strict` | L1 distance. |
| `vector_magnitude(v)` | L2 norm. |
| `normalize_vector(v)` | Rescales to a unit vector; an all-zero input stays all-zero rather than dividing by `0.0`. |
| `centroid(vectors)` | Mean of a list of vectors; raises (naming the offending index and length) if any vector after the first has a different dimensionality. |
| `nearest_neighbor(query, candidates)` / `_strict` | Index of the candidate with highest cosine similarity to `query`. |
| `k_nearest_neighbors(query, candidates, k)` / `_strict` | Indices of the `k` best candidates by cosine similarity, descending; `k` is clamped to the candidate count rather than indexed directly. |
| `cosine_similarity_matrix(vectors)` / `_strict` | Symmetric N×N similarity matrix; a zero-magnitude vector gets a `0.0` diagonal entry, not a `1.0` shortcut. |
| `vector_add(a, b)` / `_strict` | Element-wise sum. |
| `vector_scale(v, s)` | Element-wise scalar multiply. |

Every dot-product-shaped reduction (`dot_product`, `cosine_similarity`, `euclidean_distance`,
`manhattan_distance`, `vector_magnitude`) is SIMD-vectorized — a `SIMD[DType.float64, W]` load off
each `List`'s own backing buffer, `W` lanes per step (2 on this host's NEON, 8 on AVX-512), with a
scalar tail loop for any remainder. Hand-verified against `tests/mojo/test_wave33.mojo`'s pinned
suite: `vector_magnitude([3.0, 4.0]) = 5.0`, `normalize_vector([3.0, 4.0]) = [0.6, 0.8]`,
`centroid([[1.0, 0.0], [0.0, 1.0]]) = [0.5, 0.5]`, and `cosine_similarity([1.0, 0.0], [-1.0, 0.0])
= -1.0`.

**The lenient originals and their `_strict` siblings are a deliberate, permanent split, not an
in-progress migration.** `dot_product`, `cosine_similarity`, `euclidean_distance`,
`manhattan_distance`, `vector_add`, `cosine_similarity_matrix`, `nearest_neighbor`, and
`k_nearest_neighbors` all silently truncate to the shorter of two mismatched-length vectors — a
real hazard if two embeddings from different models, with different output widths, get batched
together by mistake. The module's own docstring is explicit that these stay frozen ("some caller
may genuinely rely on the lenient behavior"), and adds a `_strict` sibling for each instead of
changing the original. `centroid`, by contrast, was patched **in place** rather than given a
`_strict` twin — `tests/mojo/test_embeddings_centroid_crash_probe.mojo` documents why: a ragged
input used to be an out-of-bounds `List` index (an uncatchable, worker-killing abort) rather than a
catchable error, and a crash is never acceptable behavior for any caller, unlike a silent
truncation some caller might actually want.

**Distinct from two other modules with adjacent names.** `embeddings` is plain
`List[Float64]` vector math with no model behind it — [Tensor buffer primitives](tensorx-kernels.md)
(`tensorx.*`) is a completely separate concern, a dtype-tagged byte-buffer substrate for
quantized/low-bit tensors that `attnk`, `mlpk`, `gemm` and others decode through; nothing in
`tensorx` computes a cosine similarity or a nearest neighbor, and nothing in `embeddings` touches a
dtype code. [Vector ranking kernels](vector-ranking-kernels.md) (`vector_kernels.*`) says so about
itself directly: "None of this is an embeddings model... it is a fixed-width hashed vector standing
in for a name's shape" — a 64-bucket bigram hash of a *string*, built for column-name and
file-path matching, never touching a `List[Float64]` embedding at all.

**`embeddings.cosine_similarity` is a literal model id in the hosted LLM API, not just a
similarity concept.** [Generate embeddings](../llm/embeddings.md) documents `POST
/v1/embeddings/similarity` and `POST /v1/rerank`, and both routes take their scoring `model` as
one of `embeddings.cosine_similarity`, `embeddings.euclidean_distance`, or
`embeddings.manhattan_distance` — the exact three function names in this module. That page
documents the REST contract (request/response shapes, error codes); this page documents what those
three names actually compute.

## `scoring`: sigmoid/logit, WoE/IV, and classifier separation metrics

| Function | What it does |
| --- | --- |
| `sigmoid(x)` | `1 / (1 + exp(-x))`. |
| `logit(p)` | `log(p / (1-p))`; `p` clamped to `[1e-15, 1-1e-15]` first. |
| `log_odds_to_score(log_odds, base_score=600, pdo=20)` / `score_to_log_odds(score, base_score=600, pdo=20)` | Exact inverses — the standard credit-scoring "points to double the odds" transform. |
| `woe(events, non_events, total_events, total_non_events)` | Weight of Evidence for one bin: `ln(dist_non_events / dist_events)`. |
| `iv(woe_values, dist_events, dist_non_events)` | Information Value: `Σ(dist_non_events_i - dist_events_i) * woe_i` across bins; `0.0` if the three lists' lengths disagree. |
| `gini_coefficient(actual, predicted)` | `2*AUC - 1`, AUC computed by the trapezoidal rule over predictions sorted descending. |
| `ks_statistic(actual, predicted)` | Max separation between the cumulative positive and negative rate, over predictions sorted ascending. |
| `score_band(score, boundaries, labels)` | The first label whose boundary the score falls at or under; the last label if none do. |
| `linear_score(features, weights, intercept)` | `Σ(feature_i * weight_i) + intercept`. |
| `normalize_score(score, min_score, max_score)` | `(score - min) / (max - min)`, clamped to `[0, 1]`; `0.0` if `min == max`. |

`sigmoid(0.0) = 0.5` and `logit(0.5) = 0.0` are each other's fixed point, as they must be for
inverse functions. A two-bin Information Value example: with `total_events = 100`,
`total_non_events = 900` overall, a low-risk bin (`events=10`, `non_events=200`) has
`woe = ln((200/900) / (10/100)) = ln(2.2222) = 0.7985076962177714`, and a high-risk bin
(`events=90`, `non_events=700`) has `woe = ln((700/900) / (90/100)) = -0.14595391262307983`.
Summing `(dist_non_events - dist_events) * woe` across both bins —
`(0.2222-0.10)*0.79851 + (0.7778-0.90)*(-0.14595)` — gives `iv = 0.11543419663610402`, in the range
conventionally read as "medium" predictive power. `log_odds_to_score(0.79851) = 576.96` and
`score_to_log_odds(576.96) = 0.79851` round-trip back exactly, confirming the two are inverses
under the same `base_score`/`pdo` pair. `normalize_score(650.0, 300.0, 850.0) = 0.6363636363636364`.

**`gini_coefficient` shares a name with a completely different function.**
[Macroeconomic indicators and currency kernels](macroeconomic-indicators-and-currency-kernels.md)'s
`economic_indicators.gini_coefficient` takes one list — a distribution of incomes — and measures
income inequality via the Lorenz curve. `scoring.gini_coefficient` takes two parallel lists —
`actual` binary labels and `predicted` scores — and measures a classifier's ranking ability via
`2*AUC - 1`. Same name, same "0 is equal/no-skill, higher is more unequal/more discriminating"
shape, but different signature, different domain, and no shared code: reading both `.mojo` files
confirms neither imports the other, and the two never appear together in this codebase outside
this cross-reference.

**`scoring` is not `forecast-scoring` or `progexec`.**
[Forecast scoring & the Murphy decomposition](forecast-scoring.md)'s `forecast_metrics` grades
probabilistic forecasts (Brier score, calibration, reliability/resolution) — a different question
from converting a score into a credit band. [Program execution & scoring](program-execution-scoring.md)'s
`progexec` executes a resolved FinQA arithmetic program bit-for-bit against an evaluator's rounding
spec — arithmetic replay, not scoring in any sense this module uses the word. All three modules
happen to have "scoring" somewhere in their name or docstring; none of the three imports or is
imported by another.

## Verification

All five `mojo/tests/libs/test_*.mojo` files behind this page (`test_rag_retrieval.mojo`,
`test_recommender.mojo`, `test_rerank_eval.mojo`, `test_embeddings.mojo`, `test_scoring.mojo`) are
auto-generated coverage smoke tests — each calls every function once with a literal `0.5`-style
argument (or a small fixed list) and checks only that the result is finite (or, for a `List`
return, non-negative length); none pin a specific numeric output, and `test_recommender.mojo`
covers only 2 of `recommender`'s 9 functions this way (`top_n_items`, `rmse_ratings`) — the rest
have no auto-generated coverage at all. `test_embeddings.mojo` is the same shape, but
`embeddings` is the one module of the five with real hand-written coverage sitting one directory
over: `tests/mojo/test_wave33.mojo` pins `dot_product`, `cosine_similarity`, `euclidean_distance`,
`manhattan_distance`, `normalize_vector`, `centroid`, `nearest_neighbor`, `k_nearest_neighbors`,
`cosine_similarity_matrix`, `vector_magnitude`, `vector_add`, and `vector_scale` against worked
values (the `[3, 4]`-vector numbers above are pinned there), and three further hand-written probes
— `test_embeddings_dimension_mismatch_probe.mojo`, `test_embeddings_centroid_crash_probe.mojo`, and
`test_embeddings_simd_tail_probe.mojo` — exercise the `_strict` siblings against real ragged input,
the `centroid` crash fix, and the SIMD accumulation order, respectively. `rag_retrieval`,
`recommender`, `rerank_eval`, and `scoring` have no equivalent pinned suite anywhere in
`tests/mojo/`; every worked number for those four modules above was independently computed from the
real formulas in `mojo/engine/rag_retrieval.mojo`, `recommender.mojo`, `rerank_eval.mojo`, and
`scoring.mojo` and can be reproduced by re-running the same arithmetic.

**Next:** [Retrieval fusion and signal kernels](retrieval-fusion-and-signal-kernels.md) for the
`retrieval.fuse`/`retrieval.score` compositions built on `rag_retrieval`'s formulas, or the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
