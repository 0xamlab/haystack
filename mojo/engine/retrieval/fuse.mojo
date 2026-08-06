"""
retrieval.fuse — reciprocal-rank fusion across N ranked lists, with attribution.
Zero Python imports.

Why this module exists
---------------------
The frozen `rag_retrieval.rrf_score(rank_dense, rank_sparse, k)` is the definition of an
RRF contribution in this tree, and it takes exactly TWO ranks. A retrieval contract fuses
however many lanes it ran — lexical, dense, a local candidate ranker, a graph walk — and
the lanes disagree about which document is best, which is the entire reason fusion exists.
There is nothing in the tree that takes N ranked lists.

Nothing here computes a score. `_rrf_term` and the pair fold below are the frozen kernel
called once per pair of ranks; the module supplies the grouping, the ordering, the bounds
and the provenance.

*This module contains no index.* No postings list, no HNSW graph, no segment, no WAL. It
consumes ranked lists that a retrieval engine already produced and returns their fusion.
Building the lists is the retrieval engine's job and it is not duplicated here.

How N lanes reach a two-rank kernel, exactly
--------------------------------------------
A document's RRF total is the sum of `1/(k + rank)` over the lanes that ranked it. The
frozen kernel returns the sum of exactly two such terms, so the terms are folded in PAIRS,
in ascending lane order:

    lanes 0,1,2,3 -> rrf_score(r0, r1, k) + rrf_score(r2, r3, k)
    lanes 0,1,2   -> rrf_score(r0, r1, k) + 0.5 * rrf_score(r2, r2, k)

The odd tail uses the frozen kernel's own arithmetic on a repeated rank: `rrf_score(r, r, k)`
is `t + t` for `t = 1/(k+r)`, and adding a float to itself only increments its exponent, so
that sum is EXACT and halving it is exact for the same reason. The tail term is therefore
bit-identical to `1/(k+r)` and still comes from the frozen kernel. The suite pins both
identities.

The fold order is part of the contract, not an implementation detail: floating-point
addition is not associative, so "ascending lane ordinal, folded in pairs" is what makes two
runs on the same lanes produce the same bits. It is stated here and asserted in the suite.

Absence is absence, never a rank
--------------------------------
A lane that did not return a document contributes NO term to it. It is not given a rank of
`n+1`, it is not given `k`, and it does not push the document down — the standard RRF
definition, and the one that keeps a short lane from being punished for being short.
`Fusion.lane_hits[i]` is how many lanes actually ranked document `i`, so "ranked by one lane
only" is visible rather than inferred, and `Fusion.n_empty_lanes` counts the lanes that
ranked nothing at all. A lane that is EMPTY because the engine behind it could not run is
not representable here and must never be passed: the contract's rule is that an unavailable
lane RAISES before this kernel is reached. An empty lane here means "this lane ran and
matched nothing", which is a real retrieval answer and is reported as one.

Fusing zero lanes is `RETR_ERR_NO_LANES` and not a score of 0.0 (rule 4). Fusing lanes that
all matched nothing is `RETR_OK` with an empty ranking, `n_candidates == 0` and
`n_empty_lanes == n_lanes` — the empty ranking is a real answer, and the counts say which
of the two happened.

What is reused rather than rebuilt
----------------------------------
* `rag_retrieval.rrf_score` — every term, per the fold above.
* `columnar.hash_index.HashIndex` — the `Float64 -> slot` open-addressed grouping table,
  with its FNV-1a hash, its single shared probe sequence and its `get_or_assign` contract
  that hands the caller's own slot number back. Grouping N lanes by document needs exactly
  that and rewriting it would be rule 3's duplicated helper. It is keyed by the document
  ordinal widened to `Float64`, which is injective below 2^53 —
  `score.MAX_DOC_ORDINAL` (2^52) is the bound that guarantees it, and it is checked.
* `retrieval.score.retrieval_rank_order` — the package's one ordering (score descending,
  document ordinal ascending), so a fused ranking and a hybrid ranking agree about "first".
* `retrieval.score.retrieval_finite`, `retrieval_truncation`, the status vocabulary and the
  ceilings — imported, never restated, per rule 3 and rule 4e.

A `Dict` was not used for the grouping because there is no `Dict` anywhere in
`mojo/engine/`, and its iteration order would become a silent input to a ranking that has
to be reproducible.
"""
from std.math import abs as fabs

from columnar.hash_index import HashIndex
from rag_retrieval import rrf_score
from retrieval.score import (
    MAX_DOC_ORDINAL,
    MAX_RETRIEVAL_CELLS,
    MAX_RETRIEVAL_DIM,
    RETR_ERR_ATTRIBUTION,
    RETR_ERR_DIMENSION_TOO_LARGE,
    RETR_ERR_DOC_ORDINAL,
    RETR_ERR_DUPLICATE_IN_LANE,
    RETR_ERR_K_RANGE,
    RETR_ERR_LANE_SHAPE,
    RETR_ERR_LENGTH_MISMATCH,
    RETR_ERR_NON_FINITE,
    RETR_ERR_NO_LANES,
    RETR_ERR_TOP_K,
    RETR_OK,
    RETR_RESIDUAL_ABSENT,
    retrieval_finite,
    retrieval_rank_order,
    retrieval_truncation,
)

# Machine epsilon for Float64, spelled out so the attribution tolerance below is auditable.
comptime RETR_EPS: Float64 = 2.220446049250313e-16


def _rrf_term(rank: Int, k: Float64) -> Float64:
    """`1/(k + rank)`, taken from the frozen kernel rather than rewritten.

    `rrf_score(r, r, k)` is `t + t` with `t = 1/(k+r)`; that sum is exact (it only
    increments the exponent) and so is halving it, so this is bit-identical to
    `1.0 / (k + Float64(rank))` while the arithmetic still belongs to `rag_retrieval`.

    Ranks here are 1-based, so `k + rank >= 1` for every admissible `k >= 0` and no term
    can divide by zero or exceed 1.0. That bound is why an accumulated fused score cannot
    overflow: at most `n_lanes <= MAX_RETRIEVAL_DIM` terms, each in (0, 1].
    """
    return 0.5 * rrf_score(Float64(rank), Float64(rank), k)


@fieldwise_init
struct Fusion(Copyable, Movable):
    """A fused ranking across N lanes, with per-document and per-lane attribution.

    `doc_ids[i]` / `scores[i]` are the ranking, best first, ordered by score descending
    with ties broken on ascending document ordinal.

    `lane_hits[i]` is how many lanes ranked that document — 1 means a single lane put it
    here. `best_lane[i]` is the lane that ranked it highest and `best_rank[i]` that rank,
    1-based; on a tie the LOWEST lane ordinal wins, so the attribution is reproducible.
    Together they answer "why is this first" from the result alone: a document with
    `lane_hits == 3` beat one with `lane_hits == 1` on agreement, not on any single score.

    `lane_returned[l]` is how many of the returned documents lane `l` contributed to, so a
    lane that dominated the answer and a lane that changed nothing are distinguishable.
    `n_empty_lanes` counts lanes that ranked nothing at all.

    `n_candidates` is the number of DISTINCT documents seen across every lane, and
    `n_returned` how many survived `top_k`. On any status other than `RETR_OK` every list
    is empty, every count is 0 and `k` is 0.0 as padding rather than as an echo — 0.0 is
    itself an admissible `k`, so it is only meaningful under `RETR_OK`.
    """

    var status: Int
    var n_lanes: Int
    var n_empty_lanes: Int
    var n_candidates: Int
    var n_returned: Int
    var k: Float64
    var doc_ids: List[Int]
    var scores: List[Float64]
    var lane_hits: List[Int]
    var best_lane: List[Int]
    var best_rank: List[Int]
    var lane_returned: List[Int]


def _no_fusion(status: Int) -> Fusion:
    """A rejection: every list empty, every count 0."""
    return Fusion(
        status,
        0,
        0,
        0,
        0,
        0.0,
        List[Int](),
        List[Float64](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Int](),
    )


@fieldwise_init
struct Provenance(Copyable, Movable):
    """One row per (document, lane) contribution to a fused ranking.

    Long form on purpose: a fused score with no attribution cannot be explained, and the
    per-document summary in `Fusion` cannot say what a lane that was NOT the best lane
    contributed. Row `r` says lane `lanes[r]` ranked document `doc_ids[r]` at 1-based rank
    `ranks[r]`, adding `contributions[r] = 1/(k + rank)` to that document's total
    `fused_scores[r]`, and the document sits at `fused_positions[r]` in the returned
    ranking.

    Rows are ordered by fused position, then by ascending lane ordinal within a document,
    so the table reads as the ranking it explains.

    `max_attribution_residual` is the certificate that the rows really add up to the
    scores: the largest per-document `|sum(contributions) - fused_score|` divided by THAT
    DOCUMENT's own `sum(|contributions|)`. Per document, never over the whole table —
    rule 4b. It is not identically zero, and the reason is stated rather than hidden: the
    fused score is folded in PAIRS while this sum is accumulated left to right, and
    floating-point addition is not associative, so a document ranked by three or more
    lanes can differ in the last bits. It IS exactly 0.0 for one or two lanes, and the
    suite asserts that. A residual larger than the per-document rounding bound
    (`8 * hits * eps`) is `RETR_ERR_ATTRIBUTION` with every list empty — an explanation
    that does not reproduce the score is worse than none, because a caller stops looking.

    The certificate covers exactly that: the rows sum to the score. It does not claim the
    lanes were correctly ranked, that the ranks are dense, or that the scores are
    calibrated.
    """

    var status: Int
    var n_rows: Int
    var n_candidates: Int
    var n_returned: Int
    var max_attribution_residual: Float64
    var doc_ids: List[Int]
    var lanes: List[Int]
    var ranks: List[Int]
    var contributions: List[Float64]
    var fused_scores: List[Float64]
    var fused_positions: List[Int]


def _no_provenance(status: Int) -> Provenance:
    """A rejection: every list empty, the certificate flagged absent."""
    return Provenance(
        status,
        0,
        0,
        0,
        RETR_RESIDUAL_ABSENT,
        List[Int](),
        List[Int](),
        List[Int](),
        List[Float64](),
        List[Float64](),
        List[Int](),
    )


def _validate_lanes(
    doc_ids: List[Int], lane_lengths: List[Int],
    n_lanes: Int, k: Float64, top_k: Int,
) -> Int:
    """Everything that must hold before a single document ordinal is read.

    Shape validation and resource bounding are separate checks (rule 1c), and both are
    here: `n_lanes` is bounded by the ceiling AND pinned to `len(lane_lengths)`, and the
    lane lengths are bounded by the ceiling AND required to sum to exactly `len(doc_ids)`.
    A declared count the payload does not back is a rejection, never a shorter loop.

    The running total is compared against the ceiling INSIDE the loop, so it cannot wrap:
    each length is already at most `MAX_RETRIEVAL_CELLS` (2^22) and the accumulator is
    checked before the next addition, so it never leaves 64-bit range.
    """
    if n_lanes < 0:
        return RETR_ERR_LANE_SHAPE
    if n_lanes == 0:
        return RETR_ERR_NO_LANES
    if n_lanes != len(lane_lengths):
        return RETR_ERR_LANE_SHAPE
    if n_lanes > MAX_RETRIEVAL_DIM:
        return RETR_ERR_DIMENSION_TOO_LARGE
    if top_k < 0:
        return RETR_ERR_TOP_K
    if not retrieval_finite(k):
        return RETR_ERR_K_RANGE
    # k == 0.0 is admissible: ranks are 1-based, so `k + rank >= 1`. k < 0 is not — at
    # k == -1 the rank-1 term divides by zero, and no clamp can make that a score.
    if k < 0.0:
        return RETR_ERR_K_RANGE

    var total = 0
    for lane in range(n_lanes):
        var length = lane_lengths[lane]
        if length < 0:
            return RETR_ERR_LANE_SHAPE
        if length > MAX_RETRIEVAL_CELLS:
            return RETR_ERR_DIMENSION_TOO_LARGE
        total += length
        if total > MAX_RETRIEVAL_CELLS:
            return RETR_ERR_DIMENSION_TOO_LARGE
    if total != len(doc_ids):
        return RETR_ERR_LENGTH_MISMATCH
    for i in range(total):
        if doc_ids[i] < 0 or doc_ids[i] > MAX_DOC_ORDINAL:
            return RETR_ERR_DOC_ORDINAL
    return RETR_OK


@fieldwise_init
struct _Grouped(Copyable, Movable):
    """Internal: one document per slot, with its folded score and its best rank.

    Private and never in a public signature, so it is exempt from the same-file marshalling
    rule that governs `Fusion` and `Provenance`.
    """

    var status: Int
    var index: HashIndex
    var doc: List[Int]
    var score: List[Float64]
    var hits: List[Int]
    var best_lane: List[Int]
    var best_rank: List[Int]


def _group_lanes(
    doc_ids: List[Int], lane_lengths: List[Int], n_lanes: Int, k: Float64
) -> _Grouped:
    """Fold every lane's contributions onto one slot per distinct document.

    Caller has already run `_validate_lanes`, so every index below is inside its payload.

    One streaming pass. A pending unpaired rank per slot is what lets the frozen two-rank
    kernel see two DIFFERENT ranks whenever a document appears in two or more lanes — the
    case it was written for — instead of being called with a repeated rank every time.
    """
    var index = HashIndex(64)
    var doc = List[Int]()
    var score = List[Float64]()
    var hits = List[Int]()
    var best_lane = List[Int]()
    var best_rank = List[Int]()
    var pending = List[Int]()
    var last_lane = List[Int]()

    var cursor = 0
    for lane in range(n_lanes):
        var length = lane_lengths[lane]
        for position in range(length):
            var ordinal = doc_ids[cursor + position]
            var rank = position + 1
            var slot = index.get_or_assign(Float64(ordinal), len(doc))
            if slot == len(doc):
                doc.append(ordinal)
                score.append(0.0)
                hits.append(0)
                best_lane.append(lane)
                best_rank.append(rank)
                pending.append(-1)
                last_lane.append(-1)
            if last_lane[slot] == lane:
                # One lane ranking a document twice gives it two ranks from one lane, so
                # its RRF total double-counts that lane. A ranking with a repeat is not a
                # ranking, and silently keeping the better rank would invent an input.
                return _Grouped(
                    RETR_ERR_DUPLICATE_IN_LANE,
                    HashIndex(4),
                    List[Int](),
                    List[Float64](),
                    List[Int](),
                    List[Int](),
                    List[Int](),
                )
            last_lane[slot] = lane
            hits[slot] += 1
            if rank < best_rank[slot]:
                best_rank[slot] = rank
                best_lane[slot] = lane
            if pending[slot] < 0:
                pending[slot] = rank
            else:
                score[slot] += rrf_score(
                    Float64(pending[slot]), Float64(rank), k
                )
                pending[slot] = -1
        cursor += length

    for slot in range(len(doc)):
        if pending[slot] >= 0:
            score[slot] += _rrf_term(pending[slot], k)
        # Unreachable given the bound argued in `_rrf_term` (at most MAX_RETRIEVAL_DIM
        # terms, each in (0, 1]), and checked anyway: a score that is not a number must
        # never reach the comparator, which treats a NaN as equal to everything.
        if not retrieval_finite(score[slot]):
            return _Grouped(
                RETR_ERR_NON_FINITE,
                HashIndex(4),
                List[Int](),
                List[Float64](),
                List[Int](),
                List[Int](),
                List[Int](),
            )

    return _Grouped(
        RETR_OK, index^, doc^, score^, hits^, best_lane^, best_rank^
    )


def _empty_lane_count(lane_lengths: List[Int], n_lanes: Int) -> Int:
    """Lanes that ranked nothing. Caller has pinned `n_lanes` to `len(lane_lengths)`."""
    var empty = 0
    for lane in range(n_lanes):
        if lane_lengths[lane] == 0:
            empty += 1
    return empty


def rrf_fuse_flat(
    doc_ids: List[Int], lane_lengths: List[Int],
    n_lanes: Int, k: Float64, top_k: Int,
) -> Fusion:
    """Reciprocal-rank fusion of `n_lanes` ranked lists, via the frozen `rrf_score`.

    `doc_ids` is every lane's ranking CONCATENATED, best first within each lane, and
    `lane_lengths[l]` is how many documents lane `l` contributed; lane `l` therefore
    occupies the slice starting at `sum(lane_lengths[0:l])`. Ranks are derived from
    position — rank `p + 1` for the `p`-th entry — rather than taken as a separate array,
    because a caller-supplied rank that disagrees with the list order is a wrong answer no
    validation could catch.

    `k` is the frozen kernel's own smoothing constant (60 typical). `top_k == 0` returns
    the whole fused ranking; negative is `RETR_ERR_TOP_K`.

    Two lanes that rank the same document differently fuse deterministically: the terms
    are folded in ascending lane order and the ranking breaks ties on ascending document
    ordinal, so the same lanes always produce the same bits and the same order.
    """
    var defect = _validate_lanes(doc_ids, lane_lengths, n_lanes, k, top_k)
    if defect != RETR_OK:
        return _no_fusion(defect)

    var grouped = _group_lanes(doc_ids, lane_lengths, n_lanes, k)
    if grouped.status != RETR_OK:
        return _no_fusion(grouped.status)

    var order = retrieval_rank_order(grouped.score, grouped.doc)
    var keep = retrieval_truncation(len(order), top_k)

    var out_docs = List[Int]()
    var out_scores = List[Float64]()
    var out_hits = List[Int]()
    var out_best_lane = List[Int]()
    var out_best_rank = List[Int]()
    var returned = List[Bool]()
    for _ in range(len(grouped.doc)):
        returned.append(False)
    for position in range(keep):
        var slot = order[position]
        returned[slot] = True
        out_docs.append(grouped.doc[slot])
        out_scores.append(grouped.score[slot])
        out_hits.append(grouped.hits[slot])
        out_best_lane.append(grouped.best_lane[slot])
        out_best_rank.append(grouped.best_rank[slot])

    # Per-lane attribution needs one more pass over the payload, because which lanes
    # touched a RETURNED document is not knowable until truncation has happened.
    var lane_returned = List[Int]()
    for _ in range(n_lanes):
        lane_returned.append(0)
    var cursor = 0
    for lane in range(n_lanes):
        var length = lane_lengths[lane]
        for position in range(length):
            var slot = grouped.index.find(Float64(doc_ids[cursor + position]))
            # Every ordinal was inserted in `_group_lanes`, so `slot` is in range; the
            # guard is here because a missed lookup would otherwise index `returned[-1]`.
            if slot >= 0 and slot < len(returned) and returned[slot]:
                lane_returned[lane] += 1
        cursor += length

    return Fusion(
        RETR_OK,
        n_lanes,
        _empty_lane_count(lane_lengths, n_lanes),
        len(grouped.doc),
        keep,
        k,
        out_docs^,
        out_scores^,
        out_hits^,
        out_best_lane^,
        out_best_rank^,
        lane_returned^,
    )


def rrf_provenance_flat(
    doc_ids: List[Int], lane_lengths: List[Int],
    n_lanes: Int, k: Float64, top_k: Int,
) -> Provenance:
    """The (document, lane, rank, contribution) table behind `rrf_fuse_flat`'s ranking.

    Same arguments, same fold, same ordering — the fused scores here are produced by the
    identical code path, so the table and the ranking cannot drift. Rows exist only for
    documents that survived `top_k`, ordered by fused position and then by ascending lane.

    A row is the answer to "why did this rank first": which lane found it, where that lane
    put it, and how much that placement was worth.
    """
    var defect = _validate_lanes(doc_ids, lane_lengths, n_lanes, k, top_k)
    if defect != RETR_OK:
        return _no_provenance(defect)

    var grouped = _group_lanes(doc_ids, lane_lengths, n_lanes, k)
    if grouped.status != RETR_OK:
        return _no_provenance(grouped.status)

    var order = retrieval_rank_order(grouped.score, grouped.doc)
    var keep = retrieval_truncation(len(order), top_k)

    var slot_position = List[Int]()
    for _ in range(len(grouped.doc)):
        slot_position.append(-1)
    var fused_of_position = List[Float64]()
    for position in range(keep):
        slot_position[order[position]] = position
        fused_of_position.append(grouped.score[order[position]])

    # Counting sort by fused position: one pass to size each document's block, one to fill
    # it. The second pass walks the lanes in ascending order, so rows land lane-ascending
    # inside a block for free. `sorting.counting_sort_int` sorts values with no payload and
    # so cannot carry the rank and contribution that make a row a row.
    var block_count = List[Int]()
    for _ in range(keep):
        block_count.append(0)
    var cursor = 0
    for lane in range(n_lanes):
        var length = lane_lengths[lane]
        for position in range(length):
            var slot = grouped.index.find(Float64(doc_ids[cursor + position]))
            if slot >= 0 and slot < len(slot_position):
                var at = slot_position[slot]
                if at >= 0:
                    block_count[at] += 1
        cursor += length

    var block_start = List[Int]()
    var running = 0
    for position in range(keep):
        block_start.append(running)
        running += block_count[position]
    var n_rows = running

    var row_docs = List[Int]()
    var row_lanes = List[Int]()
    var row_ranks = List[Int]()
    var row_contrib = List[Float64]()
    var row_fused = List[Float64]()
    var row_position = List[Int]()
    for _ in range(n_rows):
        row_docs.append(0)
        row_lanes.append(0)
        row_ranks.append(0)
        row_contrib.append(0.0)
        row_fused.append(0.0)
        row_position.append(0)

    var written = List[Int]()
    for _ in range(keep):
        written.append(0)
    cursor = 0
    for lane in range(n_lanes):
        var length = lane_lengths[lane]
        for position in range(length):
            var ordinal = doc_ids[cursor + position]
            var slot = grouped.index.find(Float64(ordinal))
            if slot < 0 or slot >= len(slot_position):
                continue
            var at = slot_position[slot]
            if at < 0:
                continue
            # `written[at] < block_count[at]` holds because both passes iterate the payload
            # identically, so `row` is inside the row arrays.
            var row = block_start[at] + written[at]
            written[at] += 1
            row_docs[row] = ordinal
            row_lanes[row] = lane
            row_ranks[row] = position + 1
            row_contrib[row] = _rrf_term(position + 1, k)
            row_fused[row] = grouped.score[slot]
            row_position[row] = at
        cursor += length

    # The certificate: the rows of a document must add up to its fused score, judged
    # against that document's OWN accumulated magnitude and its OWN term count.
    var sum_contrib = List[Float64]()
    var abs_contrib = List[Float64]()
    for _ in range(keep):
        sum_contrib.append(0.0)
        abs_contrib.append(0.0)
    for row in range(n_rows):
        var at = row_position[row]
        sum_contrib[at] += row_contrib[row]
        abs_contrib[at] += fabs(row_contrib[row])
    var worst = RETR_RESIDUAL_ABSENT
    for position in range(keep):
        var scale = abs_contrib[position]
        var gap = fabs(sum_contrib[position] - fused_of_position[position])
        var relative = 0.0 if scale == 0.0 else gap / scale
        # 8 * m * eps is the standard bound for a left-to-right sum of m terms; the fused
        # score folds the same terms in pairs, so only rounding can separate them. The
        # tolerance scales with THIS document's term count, not with the table's size.
        var tolerance = 8.0 * Float64(block_count[position]) * RETR_EPS
        if relative > tolerance:
            return _no_provenance(RETR_ERR_ATTRIBUTION)
        if worst == RETR_RESIDUAL_ABSENT or relative > worst:
            worst = relative

    return Provenance(
        RETR_OK,
        n_rows,
        len(grouped.doc),
        keep,
        worst,
        row_docs^,
        row_lanes^,
        row_ranks^,
        row_contrib^,
        row_fused^,
        row_position^,
    )
