"""
rag_retrieval.mojo — RAG retrieval: hybrid search, reranking, chunking.
Zero Python imports.

Public API:
  rrf_score                      — Reciprocal Rank Fusion score
  hybrid_search_score            — BM25 + vector combined score
  bm25_term_score                — BM25 term contribution
  cross_encoder_logit            — cross-encoder reranking logit
  chunk_overlap_ratio            — sliding window chunk overlap
  context_relevance_score        — RAG context relevance estimate
  answer_faithfulness_score      — answer grounded in context
  citation_coverage              — fraction of answer citing sources
  retrieval_precision            — precision of retrieved chunks
  mmr_diversity_score            — Maximal Marginal Relevance score
"""
from std.math import sqrt, log, exp


def rrf_score(
    rank_dense: Float64, rank_sparse: Float64, k: Float64
) -> Float64:
    """Reciprocal Rank Fusion: 1/(k+rank_dense) + 1/(k+rank_sparse).

    Args:
        rank_dense: Rank from dense (vector) retriever.
        rank_sparse: Rank from sparse (BM25) retriever.
        k: RRF constant (60 typical).

    Returns:
        Combined RRF score (higher = more relevant).
    """
    var dense_contrib = 1.0 / (k + rank_dense)
    var sparse_contrib = 1.0 / (k + rank_sparse)
    return dense_contrib + sparse_contrib


def hybrid_search_score(
    vector_score: Float64, bm25_score: Float64, alpha: Float64
) -> Float64:
    """Hybrid search: α × vector + (1-α) × BM25.

    Args:
        vector_score: Cosine similarity from dense retrieval.
        bm25_score: Normalised BM25 score.
        alpha: Weight for vector score (0.5 typical).

    Returns:
        Combined hybrid score.
    """
    return alpha * vector_score + (1.0 - alpha) * bm25_score


def bm25_term_score(
    tf: Float64, df: Float64, n_docs: Float64,
    doc_len: Float64, avg_doc_len: Float64,
    k1: Float64, b: Float64
) -> Float64:
    """BM25 term score contribution.

    score = IDF × tf(k1+1) / (tf + k1(1 - b + b×dl/avgdl))

    Args:
        tf: Term frequency in document.
        df: Document frequency (docs containing term).
        n_docs: Total documents.
        doc_len: Document length (tokens).
        avg_doc_len: Average document length.
        k1: BM25 k1 (1.5 typical).
        b: BM25 b (0.75 typical).

    Returns:
        BM25 term score.
    """
    if df <= 0.0 or n_docs <= 0.0:
        return 0.0
    var idf = log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
    var norm = doc_len / avg_doc_len if avg_doc_len > 0.0 else 1.0
    var denom = tf + k1 * (1.0 - b + b * norm)
    if denom <= 0.0:
        return 0.0
    return idf * tf * (k1 + 1.0) / denom


def cross_encoder_logit(
    query_repr: Float64, doc_repr: Float64, bias: Float64
) -> Float64:
    """Cross-encoder reranker logit: query × doc + bias.

    Args:
        query_repr: Query representation element.
        doc_repr: Document representation element.
        bias: Bias term.

    Returns:
        Logit contribution (sum across dimensions for final score).
    """
    return query_repr * doc_repr + bias


def chunk_overlap_ratio(
    chunk_size: Float64, overlap_size: Float64
) -> Float64:
    """Sliding window chunk overlap ratio.

    Args:
        chunk_size: Tokens per chunk.
        overlap_size: Tokens of overlap between adjacent chunks.

    Returns:
        Overlap ratio (0–1).
    """
    if chunk_size <= 0.0:
        return 0.0
    return overlap_size / chunk_size


def context_relevance_score(
    query_terms_in_context: Float64, total_query_terms: Float64
) -> Float64:
    """Context relevance: fraction of query terms covered by retrieved context.

    Args:
        query_terms_in_context: Query terms found in retrieved chunks.
        total_query_terms: Total unique query terms.

    Returns:
        Relevance score (0–1).
    """
    if total_query_terms <= 0.0:
        return 0.0
    return query_terms_in_context / total_query_terms


def answer_faithfulness_score(
    answer_claims_supported: Float64, total_answer_claims: Float64
) -> Float64:
    """RAG faithfulness: fraction of answer claims grounded in context.

    Args:
        answer_claims_supported: Claims verified in retrieved context.
        total_answer_claims: Total claims in generated answer.

    Returns:
        Faithfulness score (0–1).
    """
    if total_answer_claims <= 0.0:
        return 1.0
    return answer_claims_supported / total_answer_claims


def citation_coverage(
    cited_chunks: Float64, total_retrieved: Float64
) -> Float64:
    """Fraction of retrieved chunks cited in the answer.

    Args:
        cited_chunks: Number of chunks actually cited.
        total_retrieved: Total chunks retrieved.

    Returns:
        Citation coverage (0–1).
    """
    if total_retrieved <= 0.0:
        return 0.0
    return cited_chunks / total_retrieved


def retrieval_precision(
    relevant_retrieved: Float64, total_retrieved: Float64
) -> Float64:
    """Precision of retrieved chunks: relevant / retrieved.

    Args:
        relevant_retrieved: Relevant chunks in retrieval set.
        total_retrieved: Total chunks retrieved.

    Returns:
        Retrieval precision (0–1).
    """
    if total_retrieved <= 0.0:
        return 0.0
    return relevant_retrieved / total_retrieved


def mmr_diversity_score(
    relevance: Float64, max_similarity_to_selected: Float64,
    lambda_mmr: Float64
) -> Float64:
    """Maximal Marginal Relevance score for diverse retrieval.

    MMR = λ × relevance - (1-λ) × max_sim(doc, selected)

    Args:
        relevance: Similarity to query.
        max_similarity_to_selected: Max similarity to already-selected docs.
        lambda_mmr: Diversity-relevance tradeoff (0.5 typical).

    Returns:
        MMR score (higher = retrieve this doc next).
    """
    return lambda_mmr * relevance - (1.0 - lambda_mmr) * max_similarity_to_selected
