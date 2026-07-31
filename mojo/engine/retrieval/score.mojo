"""
retrieval.score — the scoring half of the retrieval contract. Zero Python imports.

Why this module exists
---------------------
`rag_retrieval.mojo` holds ten scoring primitives and every one of them is a scalar
function of scalars: `hybrid_search_score(vector, bm25, alpha)` combines ONE pair of
numbers, `mmr_diversity_score(relevance, max_sim, lambda)` scores ONE candidate against
an already-known maximum similarity, and `retrieval_precision(relevant, retrieved)`
divides two counts. They are correct and they are frozen. What the tree does not have is
the thing a retrieval surface actually needs: a driver that takes a whole candidate list,
applies one of those primitives across it, produces a ranking with a stated tie-break, and
says WHICH lane put each item where.

So every number below comes out of a frozen kernel. This module supplies the loop, the
validation, the ordering and the attribution — that is the composition, and it is the
whole value. Nothing here recomputes a similarity, a BM25 term or a hybrid blend.

What is reused rather than rebuilt
----------------------------------
* `rag_retrieval.hybrid_search_score` — the dense/sparse blend, called once per candidate.
* `rag_retrieval.mmr_diversity_score` — the MMR objective, called once per candidate per
  greedy step. The greedy loop, the running max-similarity and the selection order are
  what this module adds; the score itself is never recomputed here.
* `rag_retrieval.retrieval_precision`, `citation_coverage`, `context_relevance_score` —
  called by `retrieval_quality_flat`, which exists only to say when their answer does not
  exist (all three return `0.0` for a zero denominator; see rule 4 below).
* `sparse_numerics.csr.dims_fit` — the n x n similarity-matrix shape check, written with a
  division precisely because `n * n == len(similarity)` is a wrapping multiply and
  therefore not a bound.
* `sparse_numerics.csr.MAX_CSR_DIM` — the shared outer ceiling, never modified, and never
  used directly as this package's limit (see the allocation arithmetic below).

`vector_kernels/` is NOT called from here, deliberately. Its prefilter and batch ranker are
the local candidate-generation fast path — `Float32`, `VEC_DIM = 64`, `MAX_SHORTLIST = 64`,
struct-typed (`CandidateEntry`, `RankResult`) and therefore not marshalable across a public
signature. It stays exactly where it is and its output is one LANE into the drivers here;
`table.mojo` in particular is a purpose-built ranking index and is untouched.

`optimization.model.model_finite` is the tree's other public finiteness predicate, and it is
NOT imported here: reaching it drags `expr`, `query.ir`, `types` and the LP model container
into a retrieval scoring path, which is the wrong dependency direction for one comparison.
`retrieval_finite` below is this package's single definition, public for exactly the reason
`model_finite` was made public — `fuse.mojo` imports it rather than carrying a copy.

Rule 4: an answer that does not exist is absent, never zero
-----------------------------------------------------------
Three frozen kernels report "there is nothing to divide by" as `0.0`:

    retrieval_precision(r, 0.0)        -> 0.0    # precision of an empty retrieval set
    citation_coverage(c, 0.0)          -> 0.0    # coverage over nothing retrieved
    context_relevance_score(q, 0.0)    -> 0.0    # relevance with no query terms

`0.0` is a real value in all three ranges — it is what a retrieval that returned only
irrelevant chunks scores — so a caller cannot tell a bad retrieval from an absent
measurement. `retrieval_quality_flat` calls those same three kernels and carries a
`_known` flag per figure, which is the entire difference.

The same rule drives the rest of the module: a weight outside [0, 1] is
`RETR_ERR_WEIGHT_RANGE` and never silently clamped, a non-finite score is
`RETR_ERR_NON_FINITE` and never sorted, and `MMRSelection.max_sim_known` is False for the
first selected document because the maximum similarity to an EMPTY selected set does not
exist. (`mmr_diversity_score` is still called for that first pick with a redundancy term
of 0.0 — that is "no penalty", stated by the flag, not an inferred similarity. It cannot
change the pick: the term is identical for every candidate on the first step.)

Status codes: 200-219 belong to the `retrieval` package
-------------------------------------------------------
ONE vocabulary for the whole package, per rule 4e — `fuse.mojo` imports these codes rather
than allocating its own, because `optimization` shipped `81` meaning two different things
in one package and no caller could tell which. 200-213 are assigned below; 214-219 are
reserved for this package. Nothing here reuses optimization's 0-30/40-42/60-63/80-86/
100-105/110-159 ranges.

Determinism
-----------
Every ordering in this package is `score DESCENDING, then document ordinal ASCENDING` —
`retrieval_rank_order` is the single implementation of it and `fuse.mojo` calls it too. Two
lanes that disagree about a document therefore fuse to one reproducible position, and the
tie-break is a property of the ordinal alone, so it does not depend on which lane was
scanned first, on the order candidates were appended, or on the sort's stability.

Allocation arithmetic, per rule 1c
----------------------------------
`MAX_CSR_DIM` (2^26) is justified for ONE array of that length. The drivers here allocate
several arrays per candidate, and `fuse.mojo` allocates five more per (document, lane)
contribution, so the ceiling is scaled down rather than inherited:

    per candidate    : ordinal + score + two decomposition parts + dominant lane
                       + order + merge buffer          ~= 7 * 8 = 56 bytes
    per fused slot   : the above + hits + best_lane + best_rank + pending + last_lane
                       + hash slot/key at 0.7 load     ~= 13 * 8 = 104 bytes
    per contribution : doc + lane + rank + contribution + fused score + position
                                                       ~= 6 * 8 = 48 bytes

At `MAX_RETRIEVAL_CELLS = 2^22` that is 2^22 * 104 = 436 MB of slot state OR 2^22 * 48 =
201 MB of provenance rows, and the two peaks do not coincide (a provenance row exists only
for a returned document, and the slot arrays are sized by unique documents, not by
contributions). The worst single request stays inside the 512 MiB resident-dataset budget
`algenta_runtime.session` already treats as the limit for one object. 2^23 would be ~870 MB,
so 2^22 is the ceiling and `MAX_CSR_DIM` itself is left alone for the packages that depend
on it.

Every dimension is ALSO bounded against what the payload contains, which is the half of
rule 1c a ceiling does not cover: `n` must not exceed `len(relevance)`, the similarity
matrix must be exactly `n * n` cells, `n_lanes` must equal `len(lane_lengths)` and the lane
lengths must sum to exactly `len(doc_ids)`. A count the payload does not back is a rejection,
not a smaller loop.
"""
from std.math import abs as fabs, isinf, isnan

from rag_retrieval import (
    citation_coverage,
    context_relevance_score,
    hybrid_search_score,
    mmr_diversity_score,
    retrieval_precision,
)
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status vocabulary: 200-213 assigned, 214-219 reserved for this package ─────────
comptime RETR_OK: Int = 200
comptime RETR_ERR_NO_LANES: Int = 201
comptime RETR_ERR_LANE_SHAPE: Int = 202
comptime RETR_ERR_LENGTH_MISMATCH: Int = 203
comptime RETR_ERR_DOC_ORDINAL: Int = 204
comptime RETR_ERR_DUPLICATE_IN_LANE: Int = 205
comptime RETR_ERR_DIMENSION_TOO_LARGE: Int = 206
comptime RETR_ERR_WEIGHT_RANGE: Int = 207
comptime RETR_ERR_NON_FINITE: Int = 208
comptime RETR_ERR_K_RANGE: Int = 209
comptime RETR_ERR_SHAPE: Int = 210
comptime RETR_ERR_TOP_K: Int = 211
comptime RETR_ERR_QUALITY_COUNTS: Int = 212
comptime RETR_ERR_ATTRIBUTION: Int = 213

# A residual is a magnitude, so a negative value cannot be one: -1.0 says the certificate
# was never computed, exactly as `optimization.assignment.ASSIGN_DEFECT_ABSENT` does.
comptime RETR_RESIDUAL_ABSENT: Float64 = -1.0

# Which lane paid for a hybrid score. TIE is -1 because a tie is not lane 0.
comptime RETR_LANE_DENSE: Int = 0
comptime RETR_LANE_SPARSE: Int = 1
comptime RETR_LANE_TIE: Int = -1

# Candidate counts and lane counts drive allocation, so they get the scaled-down ceiling
# whose arithmetic is stated in the module docstring. `MAX_CSR_DIM` stays the shared outer
# limit and is asserted to dominate this one in the suite.
comptime MAX_RETRIEVAL_CELLS: Int = 1 << 22
comptime MAX_RETRIEVAL_DIM: Int = 1 << 22

# A document ordinal drives NO allocation — `fuse.mojo` keys a hash index by it rather than
# indexing an array with it — so it is not bounded by the allocation ceiling. It is bounded
# by EXACTNESS: the hash key is the ordinal widened to Float64, which is injective only
# below 2^53. 2^52 keeps a decade of headroom under that and still admits a global chunk id
# from a corpus far larger than any candidate list.
comptime MAX_DOC_ORDINAL: Int = 1 << 52


fn retrieval_status_name(code: Int) -> String:
    """Name for a status code, so an error surfaces the defect and not a bare number."""
    if code == RETR_OK:
        return "ok"
    if code == RETR_ERR_NO_LANES:
        return "no_lanes_to_fuse"
    if code == RETR_ERR_LANE_SHAPE:
        return "lane_count_does_not_match_lane_lengths"
    if code == RETR_ERR_LENGTH_MISMATCH:
        return "declared_count_exceeds_payload"
    if code == RETR_ERR_DOC_ORDINAL:
        return "document_ordinal_out_of_range"
    if code == RETR_ERR_DUPLICATE_IN_LANE:
        return "one_lane_ranks_a_document_twice"
    if code == RETR_ERR_DIMENSION_TOO_LARGE:
        return "dimension_exceeds_retrieval_ceiling"
    if code == RETR_ERR_WEIGHT_RANGE:
        return "weight_outside_unit_interval"
    if code == RETR_ERR_NON_FINITE:
        return "non_finite_score"
    if code == RETR_ERR_K_RANGE:
        return "rrf_k_not_positive"
    if code == RETR_ERR_SHAPE:
        return "invalid_shape"
    if code == RETR_ERR_TOP_K:
        return "negative_top_k"
    if code == RETR_ERR_QUALITY_COUNTS:
        return "count_not_a_subset_of_its_total"
    if code == RETR_ERR_ATTRIBUTION:
        return "attribution_does_not_reproduce_fused_score"
    return "unknown"


fn retrieval_finite(v: Float64) -> Bool:
    """True for a real number: neither NaN nor +-inf.

    PUBLIC on purpose, and the SINGLE definition of "finite" for this package —
    `fuse.mojo` imports it. `optimization.model.model_finite` is the same predicate for
    the optimization package and is deliberately not imported (see the module docstring):
    two definitions in one package is the defect rule 3 names, two definitions in two
    packages with no shared dependency is not.
    """
    return not (isnan(v) or isinf(v))


fn _precedes(a_score: Float64, a_ord: Int, b_score: Float64, b_ord: Int) -> Bool:
    """True when `a` must be ranked before `b`: higher score, ascending ordinal on a tie.

    Assumes both scores are finite, which every public driver validates before ordering
    anything — a NaN compares False against everything and would make this comparator
    non-transitive.
    """
    if a_score != b_score:
        return a_score > b_score
    return a_ord < b_ord


fn retrieval_rank_order(
    scores: List[Float64], ordinals: List[Int]
) -> List[Int]:
    """Positions of `scores` in ranked order: score DESCENDING, ordinal ASCENDING on a tie.

    The single ordering used by this package, `fuse.mojo` included, so a fused ranking and
    a hybrid ranking cannot disagree about what "first" means. Returns positions into the
    input arrays, not the ordinals themselves.

    Bottom-up (non-recursive) merge sort, per the dialect rule preferring an explicit loop
    over recursion, and O(n log n) because a fused candidate set is the whole retrieval
    result rather than a chunk. The frozen alternatives were both rejected for cause:
    `sorting.mergesort` and `sorting.insertion_sort` sort a bare `List[Float64]` and so
    discard the identity that ranking exists to carry, and `sorting.mergesort` recurses;
    `query.executor.sort_indices` does sort indices, stably, but requires a `RecordBatch`
    and is an O(n^2) insertion pass sized for operator chunks. Neither can express the
    two-key comparator.

    An empty or single-element input needs no comparison. An EMPTY RETURN is a refusal, and
    there are exactly two of them: a length mismatch, which would otherwise index
    `ordinals` past its end (rule 1: that read is an uncatchable abort, and this function is
    exported), and a non-finite score. A NaN compares False against everything, which makes
    the comparator non-transitive and the resulting permutation arbitrary — an arbitrary
    permutation returned as a ranking is precisely the silent wrong answer this package
    exists to remove, so it is refused instead. The finiteness sweep repeats what every
    driver here already did with the same predicate; a guard duplicated at the same strength
    is fine, and the one this protects is a direct SDK call.
    """
    var n = len(scores)
    if len(ordinals) != n:
        return List[Int]()
    for i in range(n):
        if not retrieval_finite(scores[i]):
            return List[Int]()
    var order = List[Int]()
    for i in range(n):
        order.append(i)
    if n < 2:
        return order^

    var buffer = order.copy()
    var width = 1
    while width < n:
        var lo = 0
        while lo < n:
            var mid = lo + width
            if mid > n:
                mid = n
            var hi = lo + width + width
            if hi > n:
                hi = n
            var left = lo
            var right = mid
            var out_pos = lo
            while left < mid and right < hi:
                var a = order[left]
                var b = order[right]
                # Take from the right run only when it STRICTLY precedes the left head,
                # which is what keeps the pass stable. With unique ordinals the order is
                # total anyway, so the result does not depend on that — it is the reason
                # the comparator is asymmetric rather than an inequality on scores alone.
                if _precedes(scores[b], ordinals[b], scores[a], ordinals[a]):
                    buffer[out_pos] = b
                    right += 1
                else:
                    buffer[out_pos] = a
                    left += 1
                out_pos += 1
            while left < mid:
                buffer[out_pos] = order[left]
                left += 1
                out_pos += 1
            while right < hi:
                buffer[out_pos] = order[right]
                right += 1
                out_pos += 1
            lo = hi
        for t in range(n):
            order[t] = buffer[t]
        width = width + width
    return order^


fn retrieval_truncation(n_available: Int, top_k: Int) -> Int:
    """How many items a `top_k` request actually yields.

    `top_k == 0` means no truncation across every driver in this package — one convention,
    stated once. Asking for more items than exist yields what exists, and the result's
    `n_returned` reports that rather than padding.

    A negative `top_k` returns -1, which is not a count: it is never a request, and a
    driver reports it as `RETR_ERR_TOP_K` before calling here. Returning `n_available`
    instead would make this helper accept, as "all", exactly what every driver in the
    package rejects — one invariant at two strengths, which rule 3 names as a bug even
    when the weaker path never fires today.
    """
    if top_k < 0:
        return -1
    if n_available <= 0:
        return 0
    if top_k <= 0 or top_k > n_available:
        return n_available
    return top_k


@fieldwise_init
struct HybridRanking(Copyable, Movable):
    """A dense/sparse hybrid ranking, with the blend decomposed into its two lanes.

    `scores[i]` is `hybrid_search_score(dense[d], sparse[d], alpha)` for `d = doc_ids[i]`,
    straight from the frozen kernel. `dense_part[i]` and `sparse_part[i]` are the two
    terms that kernel adds — `alpha * dense` and `(1 - alpha) * sparse` — so "why did this
    rank first" is answerable from the result alone, and `dominant_lane[i]` names the term
    that was larger (`RETR_LANE_TIE` when they are exactly equal, because a tie is not
    lane 0).

    `max_attribution_residual` is the certificate that the decomposition really explains
    the score: the largest per-item `|score - (dense_part + sparse_part)|` divided by THAT
    ITEM's own `|dense_part| + |sparse_part|`. Per item, never over the whole ranking —
    rule 4b: an aggregate scale lets one item's magnitude pay for another item's
    inconsistency. It is `RETR_RESIDUAL_ABSENT` when nothing was ranked, since the maximum
    over an empty set does not exist. A nonzero value is expected only from
    floating-point contraction, and the suite pins it at exactly 0.0.

    `dense_ranks_nothing` / `sparse_ranks_nothing` are True when that lane gave every
    candidate an identical score over at least two candidates. Such a lane contributes no
    ordering at all, which is what a placeholder lane filled with zeros looks like from
    inside the kernel. They are reported, not rejected: with `alpha == 1.0` an
    order-free sparse lane is harmless, and the kernel cannot know whether a flat lane
    means "unavailable" — that distinction belongs to the caller, which must RAISE for a
    lane it could not run instead of passing zeros.

    On any status other than `RETR_OK` every list is empty and every count is 0, and
    `alpha` is 0.0 as padding rather than as an echo: a partially validated ranking is not
    a partial answer.
    """

    var status: Int
    var n_candidates: Int
    var n_returned: Int
    var alpha: Float64
    var dense_ranks_nothing: Bool
    var sparse_ranks_nothing: Bool
    var max_attribution_residual: Float64
    var doc_ids: List[Int]
    var scores: List[Float64]
    var dense_part: List[Float64]
    var sparse_part: List[Float64]
    var dominant_lane: List[Int]


fn _no_hybrid(status: Int) -> HybridRanking:
    """A rejection: every list empty, every number flagged absent."""
    return HybridRanking(
        status,
        0,
        0,
        0.0,
        False,
        False,
        RETR_RESIDUAL_ABSENT,
        List[Int](),
        List[Float64](),
        List[Float64](),
        List[Float64](),
        List[Int](),
    )


fn _flat_lane(values: List[Float64], n: Int) -> Bool:
    """True when every one of the first `n` values is identical and `n >= 2`.

    Caller has already bounded `n` against `len(values)`.
    """
    if n < 2:
        return False
    var first = values[0]
    for i in range(1, n):
        if values[i] != first:
            return False
    return True


fn hybrid_rank_flat(
    dense: List[Float64], sparse: List[Float64],
    n: Int, alpha: Float64, top_k: Int,
) -> HybridRanking:
    """Rank `n` candidates by the frozen `hybrid_search_score`, decomposition included.

    `dense[d]` and `sparse[d]` are candidate `d`'s score from each lane; the returned
    `doc_ids` are ordinals into those arrays. `alpha` is the DENSE weight, matching the
    frozen kernel's own argument, and it is validated rather than clamped: outside
    [0, 1] the blend is an extrapolation past both lanes, so it is `RETR_ERR_WEIGHT_RANGE`.
    `top_k == 0` returns the whole ranking; negative is `RETR_ERR_TOP_K`.

    The endpoints are exact, which is what makes this composition testable:
    `alpha == 0.0` returns the sparse score bit-for-bit and `alpha == 1.0` the dense one,
    because the frozen kernel computes `alpha * v + (1 - alpha) * b` and both `0.0 * x`
    and `x + 0.0` are exact for finite `x`.

    Every score is checked finite BEFORE anything is ordered: a NaN wins no comparison, so
    it does not poison a maximum, it silently sinks — and a ranking that quietly dropped a
    candidate to last is the failure mode this whole package exists to remove.
    """
    if n < 0:
        return _no_hybrid(RETR_ERR_SHAPE)
    if top_k < 0:
        return _no_hybrid(RETR_ERR_TOP_K)
    if n > MAX_RETRIEVAL_DIM:
        return _no_hybrid(RETR_ERR_DIMENSION_TOO_LARGE)
    if n > len(dense) or n > len(sparse):
        return _no_hybrid(RETR_ERR_LENGTH_MISMATCH)
    if not retrieval_finite(alpha):
        return _no_hybrid(RETR_ERR_NON_FINITE)
    if alpha < 0.0 or alpha > 1.0:
        return _no_hybrid(RETR_ERR_WEIGHT_RANGE)
    for i in range(n):
        if not retrieval_finite(dense[i]) or not retrieval_finite(sparse[i]):
            return _no_hybrid(RETR_ERR_NON_FINITE)

    var all_scores = List[Float64]()
    var all_dense = List[Float64]()
    var all_sparse = List[Float64]()
    var ordinals = List[Int]()
    for i in range(n):
        all_scores.append(hybrid_search_score(dense[i], sparse[i], alpha))
        all_dense.append(alpha * dense[i])
        all_sparse.append((1.0 - alpha) * sparse[i])
        ordinals.append(i)

    var order = retrieval_rank_order(all_scores, ordinals)
    var keep = retrieval_truncation(len(order), top_k)

    var doc_ids = List[Int]()
    var scores = List[Float64]()
    var dense_part = List[Float64]()
    var sparse_part = List[Float64]()
    var dominant = List[Int]()
    var worst = RETR_RESIDUAL_ABSENT
    for position in range(keep):
        var d = order[position]
        var part_dense = all_dense[d]
        var part_sparse = all_sparse[d]
        doc_ids.append(d)
        scores.append(all_scores[d])
        dense_part.append(part_dense)
        sparse_part.append(part_sparse)
        if part_dense > part_sparse:
            dominant.append(RETR_LANE_DENSE)
        elif part_sparse > part_dense:
            dominant.append(RETR_LANE_SPARSE)
        else:
            dominant.append(RETR_LANE_TIE)
        # Per-item relative residual: the scale is THIS item's two parts and nothing else.
        var magnitude = fabs(part_dense) + fabs(part_sparse)
        var gap = fabs(all_scores[d] - (part_dense + part_sparse))
        var relative = 0.0 if magnitude == 0.0 else gap / magnitude
        if worst == RETR_RESIDUAL_ABSENT or relative > worst:
            worst = relative

    return HybridRanking(
        RETR_OK,
        n,
        keep,
        alpha,
        _flat_lane(dense, n),
        _flat_lane(sparse, n),
        worst,
        doc_ids^,
        scores^,
        dense_part^,
        sparse_part^,
        dominant^,
    )


@fieldwise_init
struct MMRSelection(Copyable, Movable):
    """A greedy MMR selection, in the order the documents were selected.

    `mmr_scores[step]` is the frozen `mmr_diversity_score`'s value for the document chosen
    at that step, AT THE MOMENT it was chosen — an MMR score is a function of the selected
    set, so it is not recomputable afterwards, and storing it is the only way the choice
    can be explained.

    `max_sim[step]` is the redundancy term that entered that score, and
    `max_sim_known[step]` is False exactly once, for the first pick, because the maximum
    similarity to an empty selected set does not exist (rule 4). The value carried there
    is 0.0 and it is padding, not a measurement: the flag is the answer. It cannot change
    the first pick, since the term is identical for every candidate on step 0.

    `relevance[step]` echoes the query relevance that entered the score, so a row explains
    itself without the caller re-indexing its own input.

    On any status other than `RETR_OK` every list is empty.
    """

    var status: Int
    var n_candidates: Int
    var n_selected: Int
    var lambda_mmr: Float64
    var doc_ids: List[Int]
    var mmr_scores: List[Float64]
    var relevance: List[Float64]
    var max_sim: List[Float64]
    var max_sim_known: List[Bool]


fn _no_mmr(status: Int) -> MMRSelection:
    """A rejection: every list empty, every number flagged absent."""
    return MMRSelection(
        status,
        0,
        0,
        0.0,
        List[Int](),
        List[Float64](),
        List[Float64](),
        List[Float64](),
        List[Bool](),
    )


fn mmr_select_flat(
    relevance: List[Float64], similarity: List[Float64],
    n: Int, k: Int, lambda_mmr: Float64,
) -> MMRSelection:
    """Greedy Maximal Marginal Relevance over `n` candidates, via the frozen kernel.

    `relevance[d]` is candidate `d`'s similarity to the query. `similarity` is the flat
    row-major `n x n` candidate-candidate matrix: `similarity[i * n + j]` is
    `sim(candidate i, candidate j)`. Only the `[candidate][selected]` direction is ever
    read, so an asymmetric matrix is used exactly as given and never symmetrised behind
    the caller's back, and the diagonal is never read at all (a selected candidate is
    excluded before its column is consulted).

    `lambda_mmr` is the frozen kernel's own relevance/diversity weight and is validated,
    not clamped: `lambda > 1` inverts the sign of the diversity term and `lambda < 0`
    inverts relevance, so either one is `RETR_ERR_WEIGHT_RANGE`. `k == 0` selects every
    candidate, `k > n` selects the `n` that exist and says so in `n_selected`, and `k < 0`
    is `RETR_ERR_TOP_K`.

    Selection is `max` by MMR score with ties broken on ascending candidate ordinal — the
    same comparator `retrieval_rank_order` uses, so the whole package orders one way. That
    matters most at `lambda == 0.0`, where every score on step 0 is exactly 0.0 and the
    tie-break IS the answer.

    The running maximum starts ABSENT rather than at 0.0, tracked per candidate: a cosine
    similarity may be negative, and seeding the maximum at zero would floor it and
    understate the redundancy penalty for a candidate that is only negatively similar to
    everything selected.
    """
    if n < 0:
        return _no_mmr(RETR_ERR_SHAPE)
    if k < 0:
        return _no_mmr(RETR_ERR_TOP_K)
    if n > MAX_RETRIEVAL_DIM:
        return _no_mmr(RETR_ERR_DIMENSION_TOO_LARGE)
    if n > len(relevance):
        return _no_mmr(RETR_ERR_LENGTH_MISMATCH)
    # `dims_fit` rather than `n * n == len(similarity)`: that product is a wrapping
    # multiply, so it is not a bound and the indexing below would run off the end.
    if not dims_fit(n, n, len(similarity)):
        return _no_mmr(RETR_ERR_SHAPE)
    if not retrieval_finite(lambda_mmr):
        return _no_mmr(RETR_ERR_NON_FINITE)
    if lambda_mmr < 0.0 or lambda_mmr > 1.0:
        return _no_mmr(RETR_ERR_WEIGHT_RANGE)
    for i in range(n):
        if not retrieval_finite(relevance[i]):
            return _no_mmr(RETR_ERR_NON_FINITE)
    for c in range(n * n):
        if not retrieval_finite(similarity[c]):
            return _no_mmr(RETR_ERR_NON_FINITE)

    var selected = List[Bool]()
    var best_sim = List[Float64]()
    var has_sim = List[Bool]()
    for _ in range(n):
        selected.append(False)
        best_sim.append(0.0)
        has_sim.append(False)

    var target = retrieval_truncation(n, k)
    var doc_ids = List[Int]()
    var mmr_scores = List[Float64]()
    var chosen_relevance = List[Float64]()
    var chosen_max_sim = List[Float64]()
    var chosen_known = List[Bool]()

    for _ in range(target):
        var best = -1
        var best_score = 0.0
        for i in range(n):
            if selected[i]:
                continue
            var redundancy = best_sim[i] if has_sim[i] else 0.0
            var score = mmr_diversity_score(relevance[i], redundancy, lambda_mmr)
            if best < 0 or _precedes(score, i, best_score, best):
                best = i
                best_score = score
        if best < 0:
            break
        selected[best] = True
        doc_ids.append(best)
        mmr_scores.append(best_score)
        chosen_relevance.append(relevance[best])
        chosen_max_sim.append(best_sim[best] if has_sim[best] else 0.0)
        chosen_known.append(has_sim[best])
        for i in range(n):
            if selected[i]:
                continue
            var pair = similarity[i * n + best]
            if not has_sim[i] or pair > best_sim[i]:
                best_sim[i] = pair
                has_sim[i] = True

    return MMRSelection(
        RETR_OK,
        n,
        len(doc_ids),
        lambda_mmr,
        doc_ids^,
        mmr_scores^,
        chosen_relevance^,
        chosen_max_sim^,
        chosen_known^,
    )


@fieldwise_init
struct RetrievalQuality(Copyable, Movable):
    """The three frozen rank-quality ratios, each with whether it exists.

    Every value comes from its frozen kernel unchanged. The `_known` flags are the whole
    contribution: `retrieval_precision`, `citation_coverage` and `context_relevance_score`
    each return `0.0` when their denominator is zero, and `0.0` is a real score in all
    three ranges, so without a flag "nothing was retrieved" and "everything retrieved was
    irrelevant" are the same number.

    A value under a False flag is 0.0 and that is padding, not a claim.
    """

    var status: Int
    var precision: Float64
    var precision_known: Bool
    var coverage: Float64
    var coverage_known: Bool
    var relevance: Float64
    var relevance_known: Bool
    var n_retrieved: Int
    var n_query_terms: Int


fn retrieval_quality_flat(
    relevant_retrieved: Int, cited_chunks: Int, total_retrieved: Int,
    query_terms_in_context: Int, total_query_terms: Int,
) -> RetrievalQuality:
    """Precision, citation coverage and context relevance, with absence reported.

    Counts rather than floats, because each of these three is a subset count over a total
    and an integer is what a caller has. A count that is not a subset of its total is
    `RETR_ERR_QUALITY_COUNTS`: `retrieval_precision(7, 5)` is happily `1.4`, and a
    precision above 1 is not a precision. A negative count is refused for the same reason.

    `Int -> Float64` here is always exact and never the rule-4c hazard, which is the
    opposite direction (`Float64 -> Int` past the integer grid).
    """
    if relevant_retrieved < 0 or cited_chunks < 0 or total_retrieved < 0:
        return RetrievalQuality(
            RETR_ERR_QUALITY_COUNTS, 0.0, False, 0.0, False, 0.0, False, 0, 0
        )
    if query_terms_in_context < 0 or total_query_terms < 0:
        return RetrievalQuality(
            RETR_ERR_QUALITY_COUNTS, 0.0, False, 0.0, False, 0.0, False, 0, 0
        )
    if relevant_retrieved > total_retrieved or cited_chunks > total_retrieved:
        return RetrievalQuality(
            RETR_ERR_QUALITY_COUNTS, 0.0, False, 0.0, False, 0.0, False, 0, 0
        )
    if query_terms_in_context > total_query_terms:
        return RetrievalQuality(
            RETR_ERR_QUALITY_COUNTS, 0.0, False, 0.0, False, 0.0, False, 0, 0
        )

    var retrieved = Float64(total_retrieved)
    var terms = Float64(total_query_terms)
    var has_retrieved = total_retrieved > 0
    var has_terms = total_query_terms > 0
    var precision = retrieval_precision(Float64(relevant_retrieved), retrieved)
    var coverage = citation_coverage(Float64(cited_chunks), retrieved)
    var relevance = context_relevance_score(Float64(query_terms_in_context), terms)
    return RetrievalQuality(
        RETR_OK,
        precision if has_retrieved else 0.0,
        has_retrieved,
        coverage if has_retrieved else 0.0,
        has_retrieved,
        relevance if has_terms else 0.0,
        has_terms,
        total_retrieved,
        total_query_terms,
    )


fn retrieval_ceiling_report() -> List[Int]:
    """The ceilings this package enforces, so a caller can size a request before sending it.

    `[MAX_RETRIEVAL_CELLS, MAX_RETRIEVAL_DIM, MAX_DOC_ORDINAL, MAX_CSR_DIM]`. Reading them
    from the kernel rather than restating them in the adapter is the point: a limit copied
    into Python drifts, and rule 3's within-package duplication argument applies across the
    language boundary too.
    """
    var out = List[Int]()
    out.append(MAX_RETRIEVAL_CELLS)
    out.append(MAX_RETRIEVAL_DIM)
    out.append(MAX_DOC_ORDINAL)
    out.append(MAX_CSR_DIM)
    return out^
