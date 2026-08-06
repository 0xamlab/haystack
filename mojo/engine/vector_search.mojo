"""
vector_search.mojo — ANN / vector search index math (HNSW, IVF, PQ).
Zero Python imports.

Public API:
  hnsw_layer_probability         — HNSW random level probability
  hnsw_search_ef_scale           — ef parameter heuristic
  ivf_coarse_quantizer_dist      — IVF coarse centroid distance
  pq_quantization_error          — product quantization error estimate
  lsh_hash_bit                   — locality-sensitive hash bit
  recall_at_k                    — recall@k metric
  mrr_score                      — mean reciprocal rank contribution
  beam_search_score              — beam search candidate score
  faiss_nprobe_coverage          — IVF nprobe coverage estimate
  ann_distance_bound             — triangle inequality distance bound
"""
from std.math import sqrt, log, exp


def hnsw_layer_probability(
    level: Float64, m_l: Float64
) -> Float64:
    """HNSW probability that a node exists at given level.

    P(level ≥ l) = exp(-l / m_L)

    Args:
        level: Layer level l (0 = base).
        m_l: Level multiplier (1/ln(M) typical, M=16).

    Returns:
        Probability of node existing at this level.
    """
    if m_l <= 0.0:
        return 0.0
    return exp(-level / m_l)


def hnsw_search_ef_scale(
    k: Float64, ef_construction: Float64
) -> Float64:
    """Recommended ef search parameter: max(ef_construction, k).

    Args:
        k: Number of neighbours requested.
        ef_construction: ef_construction parameter used at index build.

    Returns:
        Recommended ef for search.
    """
    if k > ef_construction:
        return k
    return ef_construction


def ivf_coarse_quantizer_dist(
    x: Float64, centroid: Float64
) -> Float64:
    """Squared distance contribution for IVF coarse quantizer assignment.

    d² += (x_i - c_i)²  — one dimension contribution.

    Args:
        x: Query vector element.
        centroid: Centroid element.

    Returns:
        Squared difference contribution.
    """
    var diff = x - centroid
    return diff * diff


def pq_quantization_error(
    x: Float64, pq_centroid: Float64, n_subspaces: Float64
) -> Float64:
    """Product quantization per-subspace distortion estimate.

    PQ error = Σ ||x_s - c_s||² / n_subspaces

    This returns one subspace squared distance term.

    Args:
        x: Subspace vector element.
        pq_centroid: Assigned PQ centroid element.
        n_subspaces: Number of PQ subspaces M.

    Returns:
        Normalised squared distortion contribution.
    """
    if n_subspaces <= 0.0:
        return 0.0
    var diff = x - pq_centroid
    return diff * diff / n_subspaces


def lsh_hash_bit(
    x_dot_random: Float64, bias: Float64, bucket_width: Float64
) -> Float64:
    """Random projection LSH hash bucket index.

    h(x) = floor((x·r + b) / w)

    Args:
        x_dot_random: Dot product of x with random vector r.
        bias: Random bias b ~ Uniform(0, w).
        bucket_width: Bucket width w.

    Returns:
        Hash bucket index (as Float64).
    """
    if bucket_width <= 0.0:
        return 0.0
    return Float64(Int64((x_dot_random + bias) / bucket_width))


def recall_at_k(
    relevant_retrieved: Float64, k: Float64, total_relevant: Float64
) -> Float64:
    """Recall@k: relevant items in top-k / total relevant.

    Args:
        relevant_retrieved: Count of relevant items in top-k results.
        k: Number of results retrieved.
        total_relevant: Total relevant items in collection.

    Returns:
        Recall@k (0–1).
    """
    if total_relevant <= 0.0:
        return 0.0
    return relevant_retrieved / total_relevant


def mrr_score(rank: Float64) -> Float64:
    """Mean Reciprocal Rank contribution: 1/rank.

    Args:
        rank: Rank of first relevant result (1-indexed).

    Returns:
        Reciprocal rank (0 if no relevant result found; pass 0 for rank).
    """
    if rank <= 0.0:
        return 0.0
    return 1.0 / rank


def beam_search_score(
    log_prob: Float64, length: Float64, alpha: Float64
) -> Float64:
    """Length-normalised beam search score.

    score = log_prob / length^alpha

    Args:
        log_prob: Accumulated log probability.
        length: Sequence length so far.
        alpha: Length penalty (0.6–0.7 typical).

    Returns:
        Normalised score.
    """
    if length <= 0.0:
        return log_prob
    return log_prob / exp(alpha * log(length))


def faiss_nprobe_coverage(
    nprobe: Float64, n_lists: Float64
) -> Float64:
    """Approximate fraction of index covered by nprobe lists.

    coverage ≈ nprobe / n_lists

    Args:
        nprobe: Number of inverted lists searched.
        n_lists: Total inverted lists in IVF index.

    Returns:
        Coverage fraction (0–1).
    """
    if n_lists <= 0.0:
        return 1.0
    var cov = nprobe / n_lists
    if cov > 1.0:
        return 1.0
    return cov


def ann_distance_bound(
    dist_query_centroid: Float64, centroid_radius: Float64
) -> Float64:
    """Triangle inequality lower bound on query-to-point distance.

    d(q, x) ≥ d(q, c) - radius(c)

    Used to prune clusters in ANN search.

    Args:
        dist_query_centroid: Distance from query to cluster centroid.
        centroid_radius: Maximum radius of cluster.

    Returns:
        Lower bound on distance to any point in cluster.
    """
    var bound = dist_query_centroid - centroid_radius
    if bound < 0.0:
        return 0.0
    return bound
