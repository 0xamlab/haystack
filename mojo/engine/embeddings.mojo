"""
embeddings.mojo — Vector embeddings utilities. Zero Python imports.

Replaces sentence-transformers/sklearn vector utilities with pure Mojo
implementations for dot product, cosine similarity, distance metrics,
normalization, centroid, nearest-neighbor search, and similarity matrices.

Public API:
  dot_product              — Dot product of two vectors
  cosine_similarity        — Cosine similarity
  euclidean_distance       — L2 distance
  manhattan_distance       — L1 distance
  normalize_vector         — L2 normalize to unit vector
  centroid                 — Mean of vectors (centroid)
  nearest_neighbor         — Index of nearest candidate by cosine similarity
  k_nearest_neighbors      — Indices of k nearest by cosine similarity
  cosine_similarity_matrix — NxN similarity matrix
  vector_add               — Element-wise addition
  vector_scale             — Scalar multiplication
  vector_magnitude         — L2 norm
"""
from std.math import sqrt


fn _min_len(a: List[Float64], b: List[Float64]) -> Int:
    var n = len(a)
    if len(b) < n:
        n = len(b)
    return n


fn _cosine_similarity_with_query_mag(
    query: List[Float64], candidate: List[Float64], query_mag: Float64
) -> Float64:
    if query_mag <= 0.0:
        return 0.0
    var dot: Float64 = 0.0
    var cand_sq: Float64 = 0.0
    var n = _min_len(query, candidate)
    for i in range(n):
        var q = query[i]
        var c = candidate[i]
        dot += q * c
        cand_sq += c * c
    if cand_sq <= 0.0:
        return 0.0
    return dot / (query_mag * sqrt(cand_sq))


fn _insert_topk(
    mut best_scores: List[Float64],
    mut best_indices: List[Int],
    candidate_score: Float64,
    candidate_index: Int,
    max_count: Int,
):
    if max_count <= 0:
        return

    if len(best_scores) < max_count:
        best_scores.append(candidate_score)
        best_indices.append(candidate_index)
        var pos = len(best_scores) - 1
        while pos > 0 and best_scores[pos] > best_scores[pos - 1]:
            var tmp_score = best_scores[pos - 1]
            best_scores[pos - 1] = best_scores[pos]
            best_scores[pos] = tmp_score
            var tmp_idx = best_indices[pos - 1]
            best_indices[pos - 1] = best_indices[pos]
            best_indices[pos] = tmp_idx
            pos -= 1
        return

    var tail = len(best_scores) - 1
    if candidate_score <= best_scores[tail]:
        return

    best_scores[tail] = candidate_score
    best_indices[tail] = candidate_index

    var pos = tail
    while pos > 0 and best_scores[pos] > best_scores[pos - 1]:
        var tmp_score = best_scores[pos - 1]
        best_scores[pos - 1] = best_scores[pos]
        best_scores[pos] = tmp_score
        var tmp_idx = best_indices[pos - 1]
        best_indices[pos - 1] = best_indices[pos]
        best_indices[pos] = tmp_idx
        pos -= 1


# ── dot_product ──────────────────────────────────────────────────────────────


fn dot_product(a: List[Float64], b: List[Float64]) -> Float64:
    """Dot product of two vectors."""
    var s: Float64 = 0.0
    var n = _min_len(a, b)
    for i in range(n):
        s += a[i] * b[i]
    return s


# ── vector_magnitude ─────────────────────────────────────────────────────────


fn vector_magnitude(v: List[Float64]) -> Float64:
    """L2 norm (magnitude) of a vector."""
    var s: Float64 = 0.0
    for i in range(len(v)):
        s += v[i] * v[i]
    return sqrt(s)


# ── cosine_similarity ────────────────────────────────────────────────────────


fn cosine_similarity(a: List[Float64], b: List[Float64]) -> Float64:
    """Cosine similarity between two vectors."""
    var dot: Float64 = 0.0
    var sq_a: Float64 = 0.0
    var sq_b: Float64 = 0.0
    var n = _min_len(a, b)
    for i in range(n):
        var av = a[i]
        var bv = b[i]
        dot += av * bv
        sq_a += av * av
        sq_b += bv * bv
    if sq_a <= 0.0 or sq_b <= 0.0:
        return 0.0
    return dot / (sqrt(sq_a) * sqrt(sq_b))


# ── euclidean_distance ───────────────────────────────────────────────────────


fn euclidean_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """L2 (Euclidean) distance between two vectors."""
    var s: Float64 = 0.0
    var n = _min_len(a, b)
    for i in range(n):
        var d = a[i] - b[i]
        s += d * d
    return sqrt(s)


# ── manhattan_distance ───────────────────────────────────────────────────────


fn manhattan_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """L1 (Manhattan) distance between two vectors."""
    var s: Float64 = 0.0
    var n = _min_len(a, b)
    for i in range(n):
        var d = a[i] - b[i]
        if d < 0.0:
            d = -d
        s += d
    return s


# ── normalize_vector ─────────────────────────────────────────────────────────


fn normalize_vector(v: List[Float64]) -> List[Float64]:
    """L2 normalize to unit vector."""
    var n = len(v)
    var mag = vector_magnitude(v)
    var result = List[Float64](capacity=n)
    if mag == 0.0:
        for i in range(n):
            result.append(0.0)
        return result^
    var inv_mag = 1.0 / mag
    for i in range(n):
        result.append(v[i] * inv_mag)
    return result^


# ── centroid ─────────────────────────────────────────────────────────────────


fn centroid(vectors: List[List[Float64]]) -> List[Float64]:
    """Mean of vectors (centroid)."""
    var n = len(vectors)
    if n == 0:
        return List[Float64]()
    var result = vectors[0].copy()
    var dim = len(result)
    for i in range(1, n):
        for d in range(dim):
            result[d] += vectors[i][d]
    var inv_n = 1.0 / Float64(n)
    for d in range(dim):
        result[d] *= inv_n
    return result^


# ── nearest_neighbor ─────────────────────────────────────────────────────────


fn nearest_neighbor(query: List[Float64], candidates: List[List[Float64]]) -> Int:
    """Index of nearest candidate by cosine similarity (highest)."""
    var n_candidates = len(candidates)
    if n_candidates == 0:
        return 0
    var query_mag = vector_magnitude(query)
    var best_idx = 0
    var best_sim = _cosine_similarity_with_query_mag(query, candidates[0], query_mag)
    for i in range(1, n_candidates):
        var sim = _cosine_similarity_with_query_mag(query, candidates[i], query_mag)
        if sim > best_sim:
            best_sim = sim
            best_idx = i
    return best_idx


# ── k_nearest_neighbors ─────────────────────────────────────────────────────


fn k_nearest_neighbors(
    query: List[Float64], candidates: List[List[Float64]], k: Int
) -> List[Int]:
    """Indices of k nearest candidates by cosine similarity."""
    var count = k
    var n_candidates = len(candidates)
    if count <= 0 or n_candidates == 0:
        return List[Int]()
    if count > n_candidates:
        count = n_candidates
    var query_mag = vector_magnitude(query)

    if count == n_candidates:
        var all_scores = List[Float64](capacity=count)
        var all_indices = List[Int](capacity=count)
        for i in range(n_candidates):
            all_scores.append(
                _cosine_similarity_with_query_mag(query, candidates[i], query_mag)
            )
            all_indices.append(i)
        for i in range(1, count):
            var key_score = all_scores[i]
            var key_idx = all_indices[i]
            var j = i - 1
            while j >= 0 and all_scores[j] < key_score:
                all_scores[j + 1] = all_scores[j]
                all_indices[j + 1] = all_indices[j]
                j -= 1
            all_scores[j + 1] = key_score
            all_indices[j + 1] = key_idx
        return all_indices^

    var best_scores = List[Float64](capacity=count)
    var best_indices = List[Int](capacity=count)
    for i in range(n_candidates):
        var sim = _cosine_similarity_with_query_mag(query, candidates[i], query_mag)
        _insert_topk(best_scores, best_indices, sim, i, count)
    return best_indices^


# ── cosine_similarity_matrix ─────────────────────────────────────────────────


fn cosine_similarity_matrix(vectors: List[List[Float64]]) -> List[List[Float64]]:
    """NxN cosine similarity matrix."""
    var n = len(vectors)
    var norms = List[Float64](capacity=n)
    for i in range(n):
        norms.append(vector_magnitude(vectors[i]))

    var zero_row = List[Float64](capacity=n)
    for _ in range(n):
        zero_row.append(0.0)

    var matrix = List[List[Float64]](capacity=n)
    for _ in range(n):
        matrix.append(zero_row.copy())

    for i in range(n):
        var norm_i = norms[i]
        if norm_i <= 0.0:
            continue
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            var norm_j = norms[j]
            if norm_j <= 0.0:
                continue
            var dot: Float64 = 0.0
            var limit = _min_len(vectors[i], vectors[j])
            for k in range(limit):
                dot += vectors[i][k] * vectors[j][k]
            var sim = dot / (norm_i * norm_j)
            matrix[i][j] = sim
            matrix[j][i] = sim
    return matrix^


# ── vector_add ───────────────────────────────────────────────────────────────


fn vector_add(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Element-wise addition of two vectors."""
    var n = _min_len(a, b)
    var result = List[Float64](capacity=n)
    for i in range(n):
        result.append(a[i] + b[i])
    return result^


# ── vector_scale ─────────────────────────────────────────────────────────────


fn vector_scale(v: List[Float64], s: Float64) -> List[Float64]:
    """Scalar multiplication of a vector."""
    var n = len(v)
    var result = List[Float64](capacity=n)
    for i in range(n):
        result.append(v[i] * s)
    return result^
