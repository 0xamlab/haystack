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
from std.math import sqrt, abs as fabs


# ── dot_product ──────────────────────────────────────────────────────────────


fn dot_product(a: List[Float64], b: List[Float64]) -> Float64:
    """Dot product of two vectors."""
    var s: Float64 = 0.0
    var n = len(a)
    if len(b) < n:
        n = len(b)
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
    var d = dot_product(a, b)
    var ma = vector_magnitude(a)
    var mb = vector_magnitude(b)
    if ma == 0.0 or mb == 0.0:
        return 0.0
    return d / (ma * mb)


# ── euclidean_distance ───────────────────────────────────────────────────────


fn euclidean_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """L2 (Euclidean) distance between two vectors."""
    var s: Float64 = 0.0
    var n = len(a)
    if len(b) < n:
        n = len(b)
    for i in range(n):
        var d = a[i] - b[i]
        s += d * d
    return sqrt(s)


# ── manhattan_distance ───────────────────────────────────────────────────────


fn manhattan_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """L1 (Manhattan) distance between two vectors."""
    var s: Float64 = 0.0
    var n = len(a)
    if len(b) < n:
        n = len(b)
    for i in range(n):
        var d = a[i] - b[i]
        if d < 0.0:
            d = -d
        s += d
    return s


# ── normalize_vector ─────────────────────────────────────────────────────────


fn normalize_vector(v: List[Float64]) -> List[Float64]:
    """L2 normalize to unit vector."""
    var mag = vector_magnitude(v)
    var result = List[Float64]()
    if mag == 0.0:
        for i in range(len(v)):
            result.append(0.0)
        return result^
    for i in range(len(v)):
        result.append(v[i] / mag)
    return result^


# ── centroid ─────────────────────────────────────────────────────────────────


fn centroid(vectors: List[List[Float64]]) -> List[Float64]:
    """Mean of vectors (centroid)."""
    var n = len(vectors)
    if n == 0:
        return List[Float64]()
    var dim = len(vectors[0])
    var result = List[Float64]()
    for d in range(dim):
        result.append(0.0)
    for i in range(n):
        for d in range(dim):
            result[d] += vectors[i][d]
    for d in range(dim):
        result[d] /= Float64(n)
    return result^


# ── nearest_neighbor ─────────────────────────────────────────────────────────


fn nearest_neighbor(query: List[Float64], candidates: List[List[Float64]]) -> Int:
    """Index of nearest candidate by cosine similarity (highest)."""
    var best_idx = 0
    var best_sim: Float64 = -2.0
    for i in range(len(candidates)):
        var sim = cosine_similarity(query, candidates[i])
        if sim > best_sim:
            best_sim = sim
            best_idx = i
    return best_idx


# ── k_nearest_neighbors ─────────────────────────────────────────────────────


fn k_nearest_neighbors(
    query: List[Float64], candidates: List[List[Float64]], k: Int
) -> List[Int]:
    """Indices of k nearest candidates by cosine similarity."""
    # Compute all similarities
    var sims = List[Float64]()
    for i in range(len(candidates)):
        sims.append(cosine_similarity(query, candidates[i]))
    # Track which indices are already selected
    var selected = List[Bool]()
    for i in range(len(candidates)):
        selected.append(False)
    var result = List[Int]()
    var count = k
    if count > len(candidates):
        count = len(candidates)
    for _ in range(count):
        var best_idx = -1
        var best_sim: Float64 = -2.0
        for j in range(len(candidates)):
            if not selected[j] and sims[j] > best_sim:
                best_sim = sims[j]
                best_idx = j
        if best_idx >= 0:
            result.append(best_idx)
            selected[best_idx] = True
    return result^


# ── cosine_similarity_matrix ─────────────────────────────────────────────────


fn cosine_similarity_matrix(vectors: List[List[Float64]]) -> List[List[Float64]]:
    """NxN cosine similarity matrix."""
    var n = len(vectors)
    var matrix = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(cosine_similarity(vectors[i], vectors[j]))
        matrix.append(row^)
    return matrix^


# ── vector_add ───────────────────────────────────────────────────────────────


fn vector_add(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Element-wise addition of two vectors."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var result = List[Float64]()
    for i in range(n):
        result.append(a[i] + b[i])
    return result^


# ── vector_scale ─────────────────────────────────────────────────────────────


fn vector_scale(v: List[Float64], s: Float64) -> List[Float64]:
    """Scalar multiplication of a vector."""
    var result = List[Float64]()
    for i in range(len(v)):
        result.append(v[i] * s)
    return result^
