"""test_retrieval_score.mojo — known-value tests for the retrieval ranking package.

Hand-written. Every expected value below was computed on paper first and is stated in the
comment beside the assertion, because the point of this suite is that the composition
matches arithmetic done independently of it.

Three kinds of assertion do the real work:

1. *Endpoints.* `hybrid_search_score` with `alpha = 0.0` must return the sparse score
   BIT-FOR-BIT and with `alpha = 1.0` the dense score bit-for-bit. That pair pins the
   composition against both of its limits at once, and no tolerance can hide a swapped
   argument, an inverted weight or a lane read from the wrong array.

2. *Differential against the frozen kernels.* `rrf_score`, `hybrid_search_score`,
   `mmr_diversity_score`, `retrieval_precision`, `citation_coverage` and
   `context_relevance_score` are called DIRECTLY here and compared against what the drivers
   return, which is how this suite proves the drivers are a loop over the frozen kernels and
   not a second implementation of them. The two exactness identities the N-lane fold depends
   on — `rrf_score(r, r, k)` is `2/(k+r)` exactly, and half of it is `1/(k+r)` exactly — are
   asserted rather than assumed. The frozen defects the wrappers exist to fix are also
   asserted in their raw form: `retrieval_precision(0, 0) == 0.0` and
   `retrieval_precision(7, 5) == 1.4` are both checked here, next to the driver refusing
   them.

3. *Absence and determinism.* Fusing zero lanes has no answer. A single lane's rank is not a
   pair. Two lanes that rank two documents in exactly opposite orders produce two exactly
   equal scores, so the tie-break IS the answer and it must be the ascending document
   ordinal. A candidate whose only similarity to the selected set is NEGATIVE must keep that
   negative value rather than have it floored at zero — the defect a max seeded at 0.0
   would produce, and the reason `has_sim` exists.

The MMR case is the canonical demonstration and its order was traced by hand: three
documents where the second is highly relevant (0.8) but 0.95-similar to the first, and the
third is barely relevant (0.2) but unrelated. Greedy MMR at lambda = 0.5 must return
0, 2, 1 — relevance alone would return 0, 1, 2.
"""
from rag_retrieval import (
    citation_coverage,
    context_relevance_score,
    hybrid_search_score,
    mmr_diversity_score,
    retrieval_precision,
    rrf_score,
)
from retrieval.fuse import (
    Fusion,
    Provenance,
    rrf_fuse_flat,
    rrf_provenance_flat,
)
from retrieval.score import (
    MAX_DOC_ORDINAL,
    MAX_RETRIEVAL_CELLS,
    MAX_RETRIEVAL_DIM,
    RETR_ERR_DIMENSION_TOO_LARGE,
    RETR_ERR_DOC_ORDINAL,
    RETR_ERR_DUPLICATE_IN_LANE,
    RETR_ERR_K_RANGE,
    RETR_ERR_LANE_SHAPE,
    RETR_ERR_LENGTH_MISMATCH,
    RETR_ERR_NON_FINITE,
    RETR_ERR_NO_LANES,
    RETR_ERR_QUALITY_COUNTS,
    RETR_ERR_SHAPE,
    RETR_ERR_TOP_K,
    RETR_ERR_WEIGHT_RANGE,
    RETR_LANE_DENSE,
    RETR_LANE_SPARSE,
    RETR_LANE_TIE,
    RETR_OK,
    RETR_RESIDUAL_ABSENT,
    hybrid_rank_flat,
    mmr_select_flat,
    retrieval_ceiling_report,
    retrieval_finite,
    retrieval_quality_flat,
    retrieval_rank_order,
    retrieval_status_name,
    retrieval_truncation,
)
from sparse_numerics.csr import MAX_CSR_DIM


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality — every comparison in this suite is against a value produced by the
    same frozen kernel, so a tolerance would hide a real mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _near(a: Float64, b: Float64) -> Bool:
    """Relative closeness against THIS pair's own magnitude, never a global scale."""
    var scale = 1.0 if (a == 0.0 and b == 0.0) else (
        (a if a > 0.0 else -a) + (b if b > 0.0 else -b)
    )
    var gap = a - b
    if gap < 0.0:
        gap = -gap
    return gap <= 1.0e-12 * scale


fn _lf5() -> List[Float64]:
    return _floats(0.5, 0.6, 0.7, 0.4, 0.3)


fn _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


fn _fusion_rejected(f: Fusion) -> Bool:
    """A rejection carries no ranking at all: no partial answer, no padded counts."""
    return (
        f.status != RETR_OK
        and len(f.doc_ids) == 0
        and len(f.scores) == 0
        and len(f.lane_hits) == 0
        and len(f.best_lane) == 0
        and len(f.best_rank) == 0
        and len(f.lane_returned) == 0
        and f.n_candidates == 0
        and f.n_returned == 0
    )


fn main() raises:
    var passed = 0
    var failed = 0
    print("\n[retrieval.score / retrieval.fuse] known-value suite")

    # ══ the two exactness identities the N-lane fold rests on ═════════════════════
    # rrf_score(r, r, k) is t + t for t = 1/(k+r); adding a float to itself only
    # increments the exponent, so it is exact, and halving it is exact for the same
    # reason. If either identity failed, the odd-tail term would not be 1/(k+r) and every
    # single-lane score in this file would be wrong in its last bits.
    var t61 = 1.0 / 61.0
    if rrf_score(1.0, 1.0, 60.0) == t61 + t61 and 0.5 * rrf_score(1.0, 1.0, 60.0) == t61:
        passed += 1
        print("  ✅ rrf_score(r,r,k)/2 is exactly 1/(k+r) — the odd-tail identity holds")
    else:
        failed += 1
        print("  ❌ the frozen rrf_score halving identity does not hold")

    # ══ RRF across two lanes, every number computed on paper ══════════════════════
    # lane 0 ranks 10, 20, 30   (ranks 1, 2, 3)
    # lane 1 ranks 30, 10, 40   (ranks 1, 2, 3)
    #   doc 10: lanes 0,1 -> 1/61 + 1/62 = 0.0325224748810153...
    #   doc 30: lanes 0,1 -> 1/63 + 1/61 = 0.0322664584959667...
    #   doc 20: lane 0 only, rank 2 -> 1/62 = 0.0161290322580645...
    #   doc 40: lane 1 only, rank 3 -> 1/63 = 0.0158730158730159...
    # so the ranking is 10, 30, 20, 40.
    var two_lane_docs = _ints(10, 20, 30, 30, 10, 40)
    var two_lane_lengths = _ints(3, 3)
    var fused = rrf_fuse_flat(two_lane_docs, two_lane_lengths, 2, 60.0, 0)
    if (
        fused.status == RETR_OK
        and _same_ints(fused.doc_ids, _ints(10, 30, 20, 40))
        and fused.n_candidates == 4
        and fused.n_returned == 4
        and fused.n_empty_lanes == 0
    ):
        passed += 1
        print("  ✅ two lanes fuse to 10, 30, 20, 40 — the hand-computed order")
    else:
        failed += 1
        print("  ❌ fused order wrong:", fused.status, len(fused.doc_ids))

    if (
        _same_floats(
            fused.scores,
            _floats(
                rrf_score(1.0, 2.0, 60.0),
                rrf_score(3.0, 1.0, 60.0),
                1.0 / 62.0,
                1.0 / 63.0,
            ),
        )
        and _near(fused.scores[0], 0.032522474881015336)
        and _near(fused.scores[1], 0.032266458495966693)
    ):
        passed += 1
        print("  ✅ every fused score is the frozen rrf_score, bit for bit")
    else:
        failed += 1
        print("  ❌ fused scores are not the frozen kernel's:", fused.scores[0])

    # Attribution: doc 10 and doc 30 were ranked by both lanes; 20 and 40 by one each.
    # doc 30's best rank is 1, and lane 1 is where it got it.
    if (
        _same_ints(fused.lane_hits, _ints(2, 2, 1, 1))
        and _same_ints(fused.best_lane, _ints(0, 1, 0, 1))
        and _same_ints(fused.best_rank, _ints(1, 1, 2, 3))
        and _same_ints(fused.lane_returned, _ints(3, 3))
    ):
        passed += 1
        print("  ✅ provenance: lane hits, best lane, best rank, per-lane counts")
    else:
        failed += 1
        print("  ❌ per-document attribution wrong")

    # ══ the tie-break is the answer, and it is the ascending ordinal ══════════════
    # lane 0 ranks 7 then 3; lane 1 ranks 3 then 7. Both documents score
    # 1/61 + 1/62 — commuted, so exactly equal — and the ranking is decided ONLY by the
    # stated tie-break. Ascending document ordinal puts 3 first.
    var tie_docs = _ints(7, 3, 3, 7)
    var tie_fused = rrf_fuse_flat(tie_docs, _ints(2, 2), 2, 60.0, 0)
    if (
        tie_fused.status == RETR_OK
        and tie_fused.scores[0] == tie_fused.scores[1]
        and _same_ints(tie_fused.doc_ids, _ints(3, 7))
    ):
        passed += 1
        print("  ✅ opposite rankings tie exactly and break on ascending ordinal")
    else:
        failed += 1
        print("  ❌ tie-break not deterministic:", len(tie_fused.doc_ids))

    # ══ one lane is not a pair, and three lanes are a pair plus a tail ════════════
    var solo = rrf_fuse_flat(_ints(5), _ints(1), 1, 60.0, 0)
    if (
        solo.status == RETR_OK
        and solo.scores[0] == 1.0 / 61.0
        and solo.lane_hits[0] == 1
        and solo.n_candidates == 1
    ):
        passed += 1
        print("  ✅ a single lane contributes exactly 1/(k+rank), not a doubled pair")
    else:
        failed += 1
        print("  ❌ single-lane score wrong:", solo.scores[0])

    # doc 9 ranked first by all three lanes: pair(1,1) folded, then the tail.
    # score = rrf_score(1,1,60) + 1/61 = 2/61 + 1/61, in THAT order — the fold order is
    # part of the contract because floating-point addition is not associative.
    var triple = rrf_fuse_flat(_ints(9, 9, 9), _ints(1, 1, 1), 3, 60.0, 0)
    if (
        triple.status == RETR_OK
        and triple.scores[0] == rrf_score(1.0, 1.0, 60.0) + 1.0 / 61.0
        and triple.lane_hits[0] == 3
        and triple.best_lane[0] == 0
        and triple.best_rank[0] == 1
    ):
        passed += 1
        print("  ✅ three lanes fold as a pair plus the exact tail; best lane ties low")
    else:
        failed += 1
        print("  ❌ three-lane fold wrong:", triple.scores[0])

    # ══ an empty lane ranked nothing; it does not rank everything last ════════════
    # lane 1 returned nothing at all. doc 10's score must be identical to what it scores
    # with lane 1 absent entirely — no phantom rank, no penalty for a short lane.
    var with_empty = rrf_fuse_flat(_ints(10, 20), _ints(2, 0), 2, 60.0, 0)
    var without = rrf_fuse_flat(_ints(10, 20), _ints(2), 1, 60.0, 0)
    if (
        with_empty.status == RETR_OK
        and with_empty.n_empty_lanes == 1
        and _same_floats(with_empty.scores, without.scores)
        and _same_ints(with_empty.lane_returned, _ints(2, 0))
    ):
        passed += 1
        print("  ✅ an empty lane contributes nothing and is counted, not imputed")
    else:
        failed += 1
        print("  ❌ empty lane mishandled:", with_empty.n_empty_lanes)

    # Every lane empty: the fused ranking of nothing IS the empty ranking — a real answer,
    # distinguished from "there were no lanes" by n_lanes and n_empty_lanes.
    var all_empty = rrf_fuse_flat(List[Int](), _ints(0, 0), 2, 60.0, 0)
    if (
        all_empty.status == RETR_OK
        and all_empty.n_candidates == 0
        and all_empty.n_returned == 0
        and all_empty.n_lanes == 2
        and all_empty.n_empty_lanes == 2
    ):
        passed += 1
        print("  ✅ two lanes that matched nothing return the empty ranking, status ok")
    else:
        failed += 1
        print("  ❌ all-empty lanes not reported:", all_empty.status)

    # ══ fusing ZERO lanes has no answer (rule 4) ══════════════════════════════════
    var no_lanes = rrf_fuse_flat(List[Int](), List[Int](), 0, 60.0, 0)
    if no_lanes.status == RETR_ERR_NO_LANES and _fusion_rejected(no_lanes):
        passed += 1
        print("  ✅ fusing zero lanes is an error, not a score of 0.0")
    else:
        failed += 1
        print("  ❌ zero lanes not refused:", no_lanes.status)

    # ══ truncation reports the truth, and per-lane counts follow it ═══════════════
    var topped = rrf_fuse_flat(two_lane_docs, two_lane_lengths, 2, 60.0, 2)
    if (
        topped.status == RETR_OK
        and topped.n_candidates == 4
        and topped.n_returned == 2
        and _same_ints(topped.doc_ids, _ints(10, 30))
        # of the two returned, lane 0 contributed to both (10 at rank 1, 30 at rank 3) and
        # so did lane 1 (30 at rank 1, 10 at rank 2)
        and _same_ints(topped.lane_returned, _ints(2, 2))
    ):
        passed += 1
        print("  ✅ top_k truncates the ranking and n_candidates still tells the truth")
    else:
        failed += 1
        print("  ❌ truncation wrong:", topped.n_returned)

    # A negative top_k is not a count, so the exported helper returns -1 rather than
    # accepting as "all" exactly what every driver in the package refuses.
    if retrieval_truncation(0, 5) == 0 and retrieval_truncation(5, 0) == 5 and (
        retrieval_truncation(5, 3) == 3 and retrieval_truncation(3, 9) == 3
    ) and retrieval_truncation(5, -1) == -1:
        passed += 1
        print("  ✅ top_k == 0 means all, more than exists yields what does, -1 refuses")
    else:
        failed += 1
        print("  ❌ truncation convention wrong")

    # ══ shape and resource defects are separate checks ════════════════════════════
    var bad_lane_count = rrf_fuse_flat(_ints(1, 2), _ints(2), 2, 60.0, 0)
    var bad_sum = rrf_fuse_flat(_ints(1, 2), _ints(3), 1, 60.0, 0)
    var dup = rrf_fuse_flat(_ints(5, 5), _ints(2), 1, 60.0, 0)
    var negative_ordinal = rrf_fuse_flat(_ints(-1), _ints(1), 1, 60.0, 0)
    var huge_ordinal = rrf_fuse_flat(_ints(MAX_DOC_ORDINAL + 1), _ints(1), 1, 60.0, 0)
    var negative_k = rrf_fuse_flat(_ints(1), _ints(1), 1, -1.0, 0)
    var negative_top = rrf_fuse_flat(_ints(1), _ints(1), 1, 60.0, -1)
    if (
        bad_lane_count.status == RETR_ERR_LANE_SHAPE
        and bad_sum.status == RETR_ERR_LENGTH_MISMATCH
        and dup.status == RETR_ERR_DUPLICATE_IN_LANE
        and negative_ordinal.status == RETR_ERR_DOC_ORDINAL
        and huge_ordinal.status == RETR_ERR_DOC_ORDINAL
        and negative_k.status == RETR_ERR_K_RANGE
        and negative_top.status == RETR_ERR_TOP_K
        and _fusion_rejected(dup)
    ):
        passed += 1
        print("  ✅ lane shape, lane sum, in-lane duplicate, ordinal, k and top_k refused")
    else:
        failed += 1
        print(
            "  ❌ a defect was accepted:",
            bad_lane_count.status,
            bad_sum.status,
            dup.status,
            negative_ordinal.status,
            huge_ordinal.status,
            negative_k.status,
            negative_top.status,
        )

    # The SAME document in two different lanes is legal and is the whole point; only a
    # repeat inside ONE lane is a defect, because that lane would pay twice.
    var cross_lane = rrf_fuse_flat(_ints(5, 5), _ints(1, 1), 2, 60.0, 0)
    if (
        cross_lane.status == RETR_OK
        and cross_lane.n_candidates == 1
        and cross_lane.lane_hits[0] == 2
        and cross_lane.scores[0] == rrf_score(1.0, 1.0, 60.0)
    ):
        passed += 1
        print("  ✅ one document in two lanes fuses; only an in-lane repeat is refused")
    else:
        failed += 1
        print("  ❌ cross-lane duplicate mishandled:", cross_lane.status)

    # A lane length beyond the package ceiling is a rejection, not an allocation. The
    # payload is two integers.
    var bomb = rrf_fuse_flat(_ints(1, 2), _ints(MAX_RETRIEVAL_CELLS + 1), 1, 60.0, 0)
    if bomb.status == RETR_ERR_DIMENSION_TOO_LARGE and _fusion_rejected(bomb):
        passed += 1
        print("  ✅ a lane length past the ceiling is refused before anything is sized")
    else:
        failed += 1
        print("  ❌ ceiling not enforced on lane length:", bomb.status)

    # k == 0 is admissible: ranks are 1-based, so k + rank >= 1 and the rank-1 term is 1.0.
    var k_zero = rrf_fuse_flat(_ints(4), _ints(1), 1, 0.0, 0)
    if k_zero.status == RETR_OK and k_zero.scores[0] == 1.0:
        passed += 1
        print("  ✅ k == 0 is pure reciprocal rank, and rank 1 scores exactly 1.0")
    else:
        failed += 1
        print("  ❌ k == 0 mishandled:", k_zero.status, k_zero.scores[0])

    # ══ the generated A-Z argument pattern must not crash any driver ══════════════
    # Every List[Int] becomes [1,2,3,4,5] and every Int becomes 5, so lane_lengths sums to
    # 15 against a 5-element doc list. Rule 1: this is the call that breaks a whole run.
    var az_fuse = rrf_fuse_flat(_li5(), _li5(), 5, 0.5, 5)
    var az_prov = rrf_provenance_flat(_li5(), _li5(), 5, 0.5, 5)
    var az_mmr = mmr_select_flat(_lf5(), _lf5(), 5, 5, 0.5)
    if (
        az_fuse.status == RETR_ERR_LENGTH_MISMATCH
        and az_prov.status == RETR_ERR_LENGTH_MISMATCH
        and az_mmr.status == RETR_ERR_SHAPE
    ):
        passed += 1
        print("  ✅ the five-element/five-integer A-Z pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ A-Z pattern not refused:", az_fuse.status, az_mmr.status)

    # ══ provenance: the long-form table, and its certificate ══════════════════════
    # Same two lanes. Rows come out in fused-rank order, ascending lane inside a document:
    #   doc 10 @ pos 0: lane 0 rank 1 (1/61), lane 1 rank 2 (1/62)
    #   doc 30 @ pos 1: lane 0 rank 3 (1/63), lane 1 rank 1 (1/61)
    #   doc 20 @ pos 2: lane 0 rank 2 (1/62)
    #   doc 40 @ pos 3: lane 1 rank 3 (1/63)
    var prov = rrf_provenance_flat(two_lane_docs, two_lane_lengths, 2, 60.0, 0)
    if (
        prov.status == RETR_OK
        and prov.n_rows == 6
        and _same_ints(prov.doc_ids, _ints(10, 10, 30, 30, 20, 40))
        and _same_ints(prov.lanes, _ints(0, 1, 0, 1, 0, 1))
        and _same_ints(prov.ranks, _ints(1, 2, 3, 1, 2, 3))
        and _same_ints(prov.fused_positions, _ints(0, 0, 1, 1, 2, 3))
    ):
        passed += 1
        print("  ✅ provenance rows are (doc, lane, rank) in fused order, lane ascending")
    else:
        failed += 1
        print("  ❌ provenance table wrong:", prov.status, prov.n_rows)

    if (
        _same_floats(
            prov.contributions,
            _floats(
                1.0 / 61.0, 1.0 / 62.0, 1.0 / 63.0, 1.0 / 61.0, 1.0 / 62.0, 1.0 / 63.0
            ),
        )
        and prov.fused_scores[0] == fused.scores[0]
        and prov.fused_scores[4] == fused.scores[2]
        # every document here was ranked by at most two lanes, so the left-to-right sum of
        # the contributions and the pair fold are the same two additions: exactly equal.
        and prov.max_attribution_residual == 0.0
    ):
        passed += 1
        print("  ✅ each row's contribution is 1/(k+rank) and the rows sum exactly")
    else:
        failed += 1
        print(
            "  ❌ attribution wrong:",
            prov.contributions[0],
            prov.max_attribution_residual,
        )

    # Truncated provenance explains only what was returned.
    var prov_top = rrf_provenance_flat(two_lane_docs, two_lane_lengths, 2, 60.0, 1)
    if (
        prov_top.status == RETR_OK
        and prov_top.n_rows == 2
        and prov_top.n_returned == 1
        and prov_top.n_candidates == 4
        and _same_ints(prov_top.doc_ids, _ints(10, 10))
    ):
        passed += 1
        print("  ✅ truncated provenance covers the returned document only")
    else:
        failed += 1
        print("  ❌ truncated provenance wrong:", prov_top.n_rows)

    var prov_none = rrf_provenance_flat(List[Int](), List[Int](), 0, 60.0, 0)
    if (
        prov_none.status == RETR_ERR_NO_LANES
        and len(prov_none.doc_ids) == 0
        and prov_none.max_attribution_residual == RETR_RESIDUAL_ABSENT
    ):
        passed += 1
        print("  ✅ a rejected provenance has no rows and no certificate, not a zero one")
    else:
        failed += 1
        print("  ❌ provenance rejection wrong:", prov_none.status)

    # ══ hybrid: the endpoints are exact ═══════════════════════════════════════════
    # dense  = 0.9, 0.1, 0.5
    # sparse = 0.2, 0.8, 0.5
    var dense = _floats(0.9, 0.1, 0.5)
    var sparse = _floats(0.2, 0.8, 0.5)

    # alpha = 0 is the sparse lane and nothing else: 0.2, 0.8, 0.5 -> order 1, 2, 0.
    var only_sparse = hybrid_rank_flat(dense, sparse, 3, 0.0, 0)
    if (
        only_sparse.status == RETR_OK
        and _same_ints(only_sparse.doc_ids, _ints(1, 2, 0))
        and _same_floats(only_sparse.scores, _floats(0.8, 0.5, 0.2))
        and only_sparse.dominant_lane[0] == RETR_LANE_SPARSE
    ):
        passed += 1
        print("  ✅ alpha = 0 returns the sparse score bit for bit")
    else:
        failed += 1
        print("  ❌ alpha = 0 endpoint wrong:", only_sparse.status)

    # alpha = 1 is the dense lane and nothing else: 0.9, 0.1, 0.5 -> order 0, 2, 1.
    var only_dense = hybrid_rank_flat(dense, sparse, 3, 1.0, 0)
    if (
        only_dense.status == RETR_OK
        and _same_ints(only_dense.doc_ids, _ints(0, 2, 1))
        and _same_floats(only_dense.scores, _floats(0.9, 0.5, 0.1))
        and only_dense.dominant_lane[0] == RETR_LANE_DENSE
    ):
        passed += 1
        print("  ✅ alpha = 1 returns the dense score bit for bit")
    else:
        failed += 1
        print("  ❌ alpha = 1 endpoint wrong:", only_dense.status)

    # alpha = 0.5:  doc 0 -> 0.45 + 0.10 = 0.55   (dense dominates)
    #               doc 2 -> 0.25 + 0.25 = 0.50   (a tie, and a tie is not lane 0)
    #               doc 1 -> 0.05 + 0.40 = 0.45   (sparse dominates)
    var blend = hybrid_rank_flat(dense, sparse, 3, 0.5, 0)
    if (
        blend.status == RETR_OK
        and _same_ints(blend.doc_ids, _ints(0, 2, 1))
        and _same_floats(
            blend.scores,
            _floats(
                hybrid_search_score(0.9, 0.2, 0.5),
                hybrid_search_score(0.5, 0.5, 0.5),
                hybrid_search_score(0.1, 0.8, 0.5),
            ),
        )
        and _near(blend.scores[0], 0.55)
        and _same_ints(
            blend.dominant_lane,
            _ints(RETR_LANE_DENSE, RETR_LANE_TIE, RETR_LANE_SPARSE),
        )
    ):
        passed += 1
        print("  ✅ alpha = 0.5 blends via the frozen kernel; dominance names the lane")
    else:
        failed += 1
        print("  ❌ blended hybrid wrong:", blend.status, blend.scores[0])

    if (
        _same_floats(blend.dense_part, _floats(0.45, 0.25, 0.05))
        and _same_floats(blend.sparse_part, _floats(0.1, 0.25, 0.4))
        and blend.max_attribution_residual == 0.0
        and blend.alpha == 0.5
    ):
        passed += 1
        print("  ✅ the decomposition reproduces the blend exactly (residual 0.0)")
    else:
        failed += 1
        print("  ❌ decomposition does not sum:", blend.max_attribution_residual)

    # A lane that scores every candidate identically supplied no ordering. Reported, not
    # rejected: the kernel cannot know whether that means "unavailable", and the contract
    # requires the caller to RAISE for a lane it could not run rather than pass zeros.
    var flat_dense = hybrid_rank_flat(_floats(0.0, 0.0, 0.0), sparse, 3, 0.5, 0)
    if (
        flat_dense.status == RETR_OK
        and flat_dense.dense_ranks_nothing
        and not flat_dense.sparse_ranks_nothing
    ):
        passed += 1
        print("  ✅ a zero-filled lane is flagged as ranking nothing, and still fuses")
    else:
        failed += 1
        print("  ❌ flat-lane flag wrong")

    var top_hybrid = hybrid_rank_flat(dense, sparse, 3, 0.5, 2)
    var empty_hybrid = hybrid_rank_flat(dense, sparse, 0, 0.5, 0)
    if (
        top_hybrid.n_returned == 2
        and top_hybrid.n_candidates == 3
        and empty_hybrid.status == RETR_OK
        and empty_hybrid.n_candidates == 0
        and empty_hybrid.max_attribution_residual == RETR_RESIDUAL_ABSENT
    ):
        passed += 1
        print("  ✅ hybrid truncation counts honestly; an empty ranking has no residual")
    else:
        failed += 1
        print("  ❌ hybrid truncation/empty wrong:", top_hybrid.n_returned)

    # ══ a weight outside its range is an error, never a clamp ═════════════════════
    var over = hybrid_rank_flat(dense, sparse, 3, 1.5, 0)
    var under = hybrid_rank_flat(dense, sparse, 3, -0.25, 0)
    var short = hybrid_rank_flat(dense, sparse, 4, 0.5, 0)
    var infinite = hybrid_rank_flat(_floats(1.0 / 0.0, 0.1, 0.5), sparse, 3, 0.5, 0)
    var nan_alpha = hybrid_rank_flat(dense, sparse, 3, 0.0 / 0.0, 0)
    var too_big = hybrid_rank_flat(dense, sparse, MAX_RETRIEVAL_DIM + 1, 0.5, 0)
    if (
        over.status == RETR_ERR_WEIGHT_RANGE
        and under.status == RETR_ERR_WEIGHT_RANGE
        and short.status == RETR_ERR_LENGTH_MISMATCH
        and infinite.status == RETR_ERR_NON_FINITE
        and nan_alpha.status == RETR_ERR_NON_FINITE
        and too_big.status == RETR_ERR_DIMENSION_TOO_LARGE
        and len(over.scores) == 0
        and len(infinite.doc_ids) == 0
    ):
        passed += 1
        print("  ✅ weight range, short payload, non-finite score and ceiling all refused")
    else:
        failed += 1
        print(
            "  ❌ hybrid validation gap:",
            over.status,
            under.status,
            short.status,
            infinite.status,
            nan_alpha.status,
            too_big.status,
        )

    # ══ MMR: the canonical diversity case, traced by hand ═════════════════════════
    # relevance   = 0.9, 0.8, 0.2
    # similarity  = [1.00 0.95 0.10
    #                0.95 1.00 0.10
    #                0.10 0.10 1.00]
    # lambda = 0.5:
    #   step 0: 0.45, 0.40, 0.10 (no redundancy term exists yet) -> pick 0
    #   step 1: doc 1 -> 0.5*0.8 - 0.5*0.95 = -0.075
    #           doc 2 -> 0.5*0.2 - 0.5*0.10 = +0.05      -> pick 2
    #   step 2: doc 1 -> -0.075                          -> pick 1
    # Relevance alone would have returned 0, 1, 2. Diversity demotes the redundant 0.8.
    var relevance = _floats(0.9, 0.8, 0.2)
    var similarity = _floats(
        1.0, 0.95, 0.1,
        0.95, 1.0, 0.1,
        0.1, 0.1, 1.0,
    )
    var mmr = mmr_select_flat(relevance, similarity, 3, 3, 0.5)
    if (
        mmr.status == RETR_OK
        and _same_ints(mmr.doc_ids, _ints(0, 2, 1))
        and mmr.n_selected == 3
        and _same_floats(
            mmr.mmr_scores,
            _floats(
                mmr_diversity_score(0.9, 0.0, 0.5),
                mmr_diversity_score(0.2, 0.1, 0.5),
                mmr_diversity_score(0.8, 0.95, 0.5),
            ),
        )
        and _near(mmr.mmr_scores[0], 0.45)
        and _near(mmr.mmr_scores[1], 0.05)
        and _near(mmr.mmr_scores[2], -0.075)
    ):
        passed += 1
        print("  ✅ MMR returns 0, 2, 1 — the redundant 0.8 is demoted, as traced")
    else:
        failed += 1
        print("  ❌ MMR order wrong:", mmr.status, len(mmr.doc_ids))

    # The first pick's redundancy term does not exist, and the flag is the answer.
    if (
        not mmr.max_sim_known[0]
        and mmr.max_sim[0] == 0.0
        and mmr.max_sim_known[1]
        and mmr.max_sim[1] == 0.1
        and mmr.max_sim_known[2]
        and mmr.max_sim[2] == 0.95
        and _same_floats(mmr.relevance, _floats(0.9, 0.2, 0.8))
    ):
        passed += 1
        print("  ✅ the first pick's max-similarity is ABSENT, not zero")
    else:
        failed += 1
        print("  ❌ max_sim_known wrong")

    # lambda = 1 is pure relevance: 0.9, 0.8, 0.2 -> 0, 1, 2.
    var pure_relevance = mmr_select_flat(relevance, similarity, 3, 0, 1.0)
    # lambda = 0 is pure diversity: every step-0 score is exactly 0.0, so the tie-break IS
    # the answer and it must be the ascending ordinal -> 0, then 2 (-0.1 beats -0.95), then 1.
    var pure_diversity = mmr_select_flat(relevance, similarity, 3, 0, 0.0)
    if (
        _same_ints(pure_relevance.doc_ids, _ints(0, 1, 2))
        and _same_floats(pure_relevance.mmr_scores, _floats(0.9, 0.8, 0.2))
        and _same_ints(pure_diversity.doc_ids, _ints(0, 2, 1))
        and pure_diversity.mmr_scores[0] == 0.0
    ):
        passed += 1
        print("  ✅ lambda endpoints: 1.0 is relevance order, 0.0 breaks a total tie low")
    else:
        failed += 1
        print("  ❌ lambda endpoints wrong")

    # A NEGATIVE similarity must survive as the running maximum. Seeding the maximum at 0.0
    # would floor it, understate the penalty and change the score.
    var pair_relevance = _floats(0.5, 0.5)
    var negative_sim = _floats(1.0, -0.8, -0.8, 1.0)
    var negative = mmr_select_flat(pair_relevance, negative_sim, 2, 2, 0.5)
    if (
        negative.status == RETR_OK
        and _same_ints(negative.doc_ids, _ints(0, 1))
        and negative.max_sim[1] == -0.8
        and negative.max_sim_known[1]
        and negative.mmr_scores[1] == mmr_diversity_score(0.5, -0.8, 0.5)
        and _near(negative.mmr_scores[1], 0.65)
    ):
        passed += 1
        print("  ✅ a negative similarity is kept, not floored at zero (0.65, not 0.25)")
    else:
        failed += 1
        print("  ❌ negative similarity floored:", negative.max_sim[1])

    var one_only = mmr_select_flat(relevance, similarity, 3, 1, 0.5)
    var more_than_exists = mmr_select_flat(relevance, similarity, 3, 9, 0.5)
    if (
        one_only.n_selected == 1
        and one_only.n_candidates == 3
        and more_than_exists.n_selected == 3
    ):
        passed += 1
        print("  ✅ k = 1 selects one; k beyond n selects n and says so")
    else:
        failed += 1
        print("  ❌ MMR k handling wrong:", one_only.n_selected)

    var bad_lambda = mmr_select_flat(relevance, similarity, 3, 3, 1.5)
    var bad_k = mmr_select_flat(relevance, similarity, 3, -1, 0.5)
    var bad_shape = mmr_select_flat(relevance, _floats(1.0, 0.5), 3, 3, 0.5)
    var short_relevance = mmr_select_flat(_floats(0.5), similarity, 3, 3, 0.5)
    var nan_sim = mmr_select_flat(
        pair_relevance, _floats(1.0, 0.0 / 0.0, 0.0, 1.0), 2, 2, 0.5
    )
    if (
        bad_lambda.status == RETR_ERR_WEIGHT_RANGE
        and bad_k.status == RETR_ERR_TOP_K
        and bad_shape.status == RETR_ERR_SHAPE
        and short_relevance.status == RETR_ERR_LENGTH_MISMATCH
        and nan_sim.status == RETR_ERR_NON_FINITE
        and len(bad_lambda.doc_ids) == 0
    ):
        passed += 1
        print("  ✅ MMR refuses a bad lambda, a bad k, a bad shape and a NaN similarity")
    else:
        failed += 1
        print(
            "  ❌ MMR validation gap:",
            bad_lambda.status,
            bad_k.status,
            bad_shape.status,
            short_relevance.status,
            nan_sim.status,
        )

    # ══ the wrapping multiply that dims_fit exists to catch ═══════════════════════
    # 3 * 6148914691236517206 == 2 in wrapping 64-bit arithmetic, so an `n*n == len` guard
    # would pass and the similarity read would run off the end — an uncatchable abort.
    var wrap = mmr_select_flat(_floats(0.5, 0.5), _floats(1.0, 1.0), 6148914691236517206, 2, 0.5)
    if wrap.status == RETR_ERR_DIMENSION_TOO_LARGE or wrap.status == RETR_ERR_SHAPE:
        passed += 1
        print("  ✅ a wrapping-multiply dimension is refused before any indexing")
    else:
        failed += 1
        print("  ❌ wrapping multiply not caught:", wrap.status)

    # ══ rank-quality: the frozen zero-denominator answers, made honest ════════════
    # 3 relevant of 5 retrieved -> 0.6;  2 cited of 5 -> 0.4;  4 of 6 query terms -> 0.666...
    var quality = retrieval_quality_flat(3, 2, 5, 4, 6)
    if (
        quality.status == RETR_OK
        and quality.precision == retrieval_precision(3.0, 5.0)
        and quality.coverage == citation_coverage(2.0, 5.0)
        and quality.relevance == context_relevance_score(4.0, 6.0)
        and _near(quality.precision, 0.6)
        and _near(quality.coverage, 0.4)
        and quality.precision_known
        and quality.coverage_known
        and quality.relevance_known
    ):
        passed += 1
        print("  ✅ the three quality ratios are the frozen kernels, unchanged")
    else:
        failed += 1
        print("  ❌ quality ratios wrong:", quality.status, quality.precision)

    # This is the defect the wrapper exists for: the frozen kernels return 0.0 for a zero
    # denominator, and 0.0 is a real score in all three ranges.
    var nothing = retrieval_quality_flat(0, 0, 0, 0, 0)
    if (
        retrieval_precision(0.0, 0.0) == 0.0
        and citation_coverage(0.0, 0.0) == 0.0
        and context_relevance_score(0.0, 0.0) == 0.0
        and nothing.status == RETR_OK
        and not nothing.precision_known
        and not nothing.coverage_known
        and not nothing.relevance_known
    ):
        passed += 1
        print("  ✅ precision of an empty retrieval is ABSENT where the frozen kernel says 0.0")
    else:
        failed += 1
        print("  ❌ zero-denominator absence not reported")

    # And this is the other frozen hazard: 7 relevant of 5 retrieved is happily 1.4.
    var not_a_subset = retrieval_quality_flat(7, 2, 5, 4, 6)
    var over_cited = retrieval_quality_flat(3, 9, 5, 4, 6)
    var over_terms = retrieval_quality_flat(3, 2, 5, 7, 6)
    var negative_count = retrieval_quality_flat(-1, 2, 5, 4, 6)
    if (
        retrieval_precision(7.0, 5.0) == 1.4
        and not_a_subset.status == RETR_ERR_QUALITY_COUNTS
        and over_cited.status == RETR_ERR_QUALITY_COUNTS
        and over_terms.status == RETR_ERR_QUALITY_COUNTS
        and negative_count.status == RETR_ERR_QUALITY_COUNTS
        and not not_a_subset.precision_known
    ):
        passed += 1
        print("  ✅ a count that is not a subset of its total is refused, not divided")
    else:
        failed += 1
        print("  ❌ subset validation gap:", not_a_subset.status, over_terms.status)

    # ══ the one ordering, used by the whole package ═══════════════════════════════
    # scores 0.1, 0.5, 0.5, 0.2 with ordinals 3, 1, 0, 2:
    # the two 0.5s tie, ordinal 0 (position 2) precedes ordinal 1 (position 1), then 0.2
    # (position 3), then 0.1 (position 0) -> [2, 1, 3, 0].
    var order = retrieval_rank_order(_floats(0.1, 0.5, 0.5, 0.2), _ints(3, 1, 0, 2))
    # eight strictly increasing scores exercise merge widths 1, 2, 4 and 8
    var wide = retrieval_rank_order(
        _floats(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0), _ints(0, 1, 2, 3, 4, 5, 6, 7)
    )
    var mismatched = retrieval_rank_order(_floats(0.1, 0.2), _ints(0))
    # A NaN compares False against everything, so ordering it would return an arbitrary
    # permutation dressed as a ranking. This exported entry point refuses instead.
    var nan_order = retrieval_rank_order(_floats(0.1, 0.0 / 0.0, 0.3), _ints(0, 1, 2))
    if (
        _same_ints(order, _ints(2, 1, 3, 0))
        and _same_ints(wide, _ints(7, 6, 5, 4, 3, 2, 1, 0))
        and len(mismatched) == 0
        and len(nan_order) == 0
        and len(retrieval_rank_order(List[Float64](), List[Int]())) == 0
    ):
        passed += 1
        print("  ✅ one ordering: descending, ordinal tie-break, mismatch and NaN refused")
    else:
        failed += 1
        print("  ❌ rank order wrong:", len(order), len(wide), len(nan_order))

    # Provenance over lanes that all matched nothing: no rows, and NO certificate — the
    # maximum residual over an empty table does not exist and must not read as 0.0.
    var prov_empty = rrf_provenance_flat(List[Int](), _ints(0, 0), 2, 60.0, 0)
    if (
        prov_empty.status == RETR_OK
        and prov_empty.n_rows == 0
        and prov_empty.n_candidates == 0
        and prov_empty.max_attribution_residual == RETR_RESIDUAL_ABSENT
    ):
        passed += 1
        print("  ✅ an empty provenance table has no certificate, not a perfect one")
    else:
        failed += 1
        print("  ❌ empty provenance wrong:", prov_empty.max_attribution_residual)

    # ══ ceilings and vocabulary ══════════════════════════════════════════════════
    var ceilings = retrieval_ceiling_report()
    # 2^53 through a runtime binding: the comparison is a real check on the reported value,
    # and a comptime-vs-comptime compare of two literals does not survive the simplifier.
    var float64_exact_int_limit = 9007199254740992
    if (
        len(ceilings) == 4
        and ceilings[0] == MAX_RETRIEVAL_CELLS
        and ceilings[1] == MAX_RETRIEVAL_DIM
        and ceilings[2] == MAX_DOC_ORDINAL
        and ceilings[3] == MAX_CSR_DIM
        and ceilings[0] == 4194304
        and ceilings[0] < ceilings[3]
        and ceilings[2] < float64_exact_int_limit
    ):
        passed += 1
        print("  ✅ the ceilings are reported, scaled below MAX_CSR_DIM, exact as keys")
    else:
        failed += 1
        print("  ❌ ceiling report wrong:", len(ceilings))

    if (
        retrieval_status_name(RETR_OK) == "ok"
        and retrieval_status_name(RETR_ERR_NO_LANES) == "no_lanes_to_fuse"
        and retrieval_status_name(5) == "unknown"
        and retrieval_finite(1.0)
        and not retrieval_finite(1.0 / 0.0)
        and not retrieval_finite(0.0 / 0.0)
        and RETR_OK == 200
        and RETR_LANE_TIE == -1
    ):
        passed += 1
        print("  ✅ one status vocabulary for the package, 200-based, with names")
    else:
        failed += 1
        print("  ❌ status vocabulary wrong:", retrieval_status_name(RETR_OK))

    print("  [retrieval] Passed:", passed, "Failed:", failed)
