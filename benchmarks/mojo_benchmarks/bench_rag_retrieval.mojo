"""bench_rag_retrieval.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from rag_retrieval import rrf_score, hybrid_search_score, bm25_term_score, cross_encoder_logit, chunk_overlap_ratio, context_relevance_score, answer_faithfulness_score, citation_coverage, retrieval_precision, mmr_diversity_score
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_rrf_score: Float64 = 0.0
    var _t0_rrf_score = perf_counter_ns()
    for _ in range(N):
        _acc_rrf_score += rrf_score(0.5, 0.5, 0.5)
    var _t1_rrf_score = perf_counter_ns()
    var _ns_rrf_score = Float64(_t1_rrf_score - _t0_rrf_score) / Float64(N)
    print("MOJO_TIMING rag_retrieval::rrf_score", _ns_rrf_score, _acc_rrf_score)
    var _acc_hybrid_search_score: Float64 = 0.0
    var _t0_hybrid_search_score = perf_counter_ns()
    for _ in range(N):
        _acc_hybrid_search_score += hybrid_search_score(0.5, 0.5, 0.5)
    var _t1_hybrid_search_score = perf_counter_ns()
    var _ns_hybrid_search_score = Float64(_t1_hybrid_search_score - _t0_hybrid_search_score) / Float64(N)
    print("MOJO_TIMING rag_retrieval::hybrid_search_score", _ns_hybrid_search_score, _acc_hybrid_search_score)
    var _acc_bm25_term_score: Float64 = 0.0
    var _t0_bm25_term_score = perf_counter_ns()
    for _ in range(N):
        _acc_bm25_term_score += bm25_term_score(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bm25_term_score = perf_counter_ns()
    var _ns_bm25_term_score = Float64(_t1_bm25_term_score - _t0_bm25_term_score) / Float64(N)
    print("MOJO_TIMING rag_retrieval::bm25_term_score", _ns_bm25_term_score, _acc_bm25_term_score)
    var _acc_cross_encoder_logit: Float64 = 0.0
    var _t0_cross_encoder_logit = perf_counter_ns()
    for _ in range(N):
        _acc_cross_encoder_logit += cross_encoder_logit(0.5, 0.5, 0.5)
    var _t1_cross_encoder_logit = perf_counter_ns()
    var _ns_cross_encoder_logit = Float64(_t1_cross_encoder_logit - _t0_cross_encoder_logit) / Float64(N)
    print("MOJO_TIMING rag_retrieval::cross_encoder_logit", _ns_cross_encoder_logit, _acc_cross_encoder_logit)
    var _acc_chunk_overlap_ratio: Float64 = 0.0
    var _t0_chunk_overlap_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_chunk_overlap_ratio += chunk_overlap_ratio(0.5, 0.5)
    var _t1_chunk_overlap_ratio = perf_counter_ns()
    var _ns_chunk_overlap_ratio = Float64(_t1_chunk_overlap_ratio - _t0_chunk_overlap_ratio) / Float64(N)
    print("MOJO_TIMING rag_retrieval::chunk_overlap_ratio", _ns_chunk_overlap_ratio, _acc_chunk_overlap_ratio)
    var _acc_context_relevance_score: Float64 = 0.0
    var _t0_context_relevance_score = perf_counter_ns()
    for _ in range(N):
        _acc_context_relevance_score += context_relevance_score(0.5, 0.5)
    var _t1_context_relevance_score = perf_counter_ns()
    var _ns_context_relevance_score = Float64(_t1_context_relevance_score - _t0_context_relevance_score) / Float64(N)
    print("MOJO_TIMING rag_retrieval::context_relevance_score", _ns_context_relevance_score, _acc_context_relevance_score)
    var _acc_answer_faithfulness_score: Float64 = 0.0
    var _t0_answer_faithfulness_score = perf_counter_ns()
    for _ in range(N):
        _acc_answer_faithfulness_score += answer_faithfulness_score(0.5, 0.5)
    var _t1_answer_faithfulness_score = perf_counter_ns()
    var _ns_answer_faithfulness_score = Float64(_t1_answer_faithfulness_score - _t0_answer_faithfulness_score) / Float64(N)
    print("MOJO_TIMING rag_retrieval::answer_faithfulness_score", _ns_answer_faithfulness_score, _acc_answer_faithfulness_score)
    var _acc_citation_coverage: Float64 = 0.0
    var _t0_citation_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_citation_coverage += citation_coverage(0.5, 0.5)
    var _t1_citation_coverage = perf_counter_ns()
    var _ns_citation_coverage = Float64(_t1_citation_coverage - _t0_citation_coverage) / Float64(N)
    print("MOJO_TIMING rag_retrieval::citation_coverage", _ns_citation_coverage, _acc_citation_coverage)
    var _acc_retrieval_precision: Float64 = 0.0
    var _t0_retrieval_precision = perf_counter_ns()
    for _ in range(N):
        _acc_retrieval_precision += retrieval_precision(0.5, 0.5)
    var _t1_retrieval_precision = perf_counter_ns()
    var _ns_retrieval_precision = Float64(_t1_retrieval_precision - _t0_retrieval_precision) / Float64(N)
    print("MOJO_TIMING rag_retrieval::retrieval_precision", _ns_retrieval_precision, _acc_retrieval_precision)
    var _acc_mmr_diversity_score: Float64 = 0.0
    var _t0_mmr_diversity_score = perf_counter_ns()
    for _ in range(N):
        _acc_mmr_diversity_score += mmr_diversity_score(0.5, 0.5, 0.5)
    var _t1_mmr_diversity_score = perf_counter_ns()
    var _ns_mmr_diversity_score = Float64(_t1_mmr_diversity_score - _t0_mmr_diversity_score) / Float64(N)
    print("MOJO_TIMING rag_retrieval::mmr_diversity_score", _ns_mmr_diversity_score, _acc_mmr_diversity_score)
