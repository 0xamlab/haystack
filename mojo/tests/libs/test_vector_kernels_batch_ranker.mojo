"""test_vector_kernels_batch_ranker.mojo — hand-written tests for vector_kernels.batch_ranker.

Hand-written because the A-Z generator synthesizes Float64 fixtures only; rank_shortlist
takes Float32-vector structs. Covers the valid single-candidate path and the degenerate
zero-candidate shape from the audit battery.
"""
from vector_kernels.batch_ranker import (
    CandidateEntry,
    QueryForRank,
    RankResult,
    rank_shortlist,
)
from vector_kernels.dot import build_vec64_f32

def main() raises:
    # One candidate column whose vector comes from the same name the query uses, so the
    # cosine path scores it above zero.
    var entries = List[CandidateEntry]()
    var e = CandidateEntry()
    e.column_id = 7
    e.norm_inv = build_vec64_f32("unit_price", e.vec.data)
    entries.append(e^)

    var req = QueryForRank()
    req.top_k = 1
    req.query_norm_inv = build_vec64_f32("unit_price", req.query_vec.data)

    var cand_ids = List[UInt32]()
    cand_ids.append(UInt32(0))
    var tok_hits = List[UInt16]()
    tok_hits.append(UInt16(0))

    var res = rank_shortlist(entries, req, cand_ids, tok_hits, 1)
    if res.count != 1:
        raise Error("rank_shortlist must return the single candidate")
    if res.entries[0].column_id != 7:
        raise Error("rank_shortlist returned the wrong column")

    # Degenerate: zero candidates must return an empty result, not abort.
    var empty_ids = List[UInt32]()
    var empty_hits = List[UInt16]()
    var empty_res = rank_shortlist(entries, req, empty_ids, empty_hits, 0)
    if empty_res.count != 0:
        raise Error("rank_shortlist with zero candidates must be empty")
