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

`dot_product`, `cosine_similarity`, `euclidean_distance`, `manhattan_distance`,
`vector_add`, `cosine_similarity_matrix`, `nearest_neighbor`, and
`k_nearest_neighbors` all silently compare/aggregate over only the shorter of
two mismatched-length vectors (via `_min_len` / `_cosine_similarity_with_query_mag`)
rather than raising -- correct for a caller who already aligned dimensions, a
silent-wrong-answer trap for one who didn't (e.g. accidentally batching
embeddings from two different models with different output dimensionality).
Those EXISTING functions are left unchanged (frozen; some caller may
genuinely rely on the lenient behavior -- same reasoning as `pearson_r` /
`spearman_r` in stat_tests.mojo). `dot_product_strict`, `cosine_similarity_strict`,
`euclidean_distance_strict`, `manhattan_distance_strict`, `vector_add_strict`,
`cosine_similarity_matrix_strict`, `nearest_neighbor_strict`, and
`k_nearest_neighbors_strict` are additive siblings that raise instead, naming
the offending list and its real length -- the same shape as
`pearson_r_strict`/`spearman_r_strict` in stat_tests.mojo.

SIMD, over the vector's own dimension
--------------------------------------
`dot_product`, `cosine_similarity`, `euclidean_distance`, `manhattan_distance`
and `vector_magnitude` accumulate `W` (`simd_width_of[DType.float64]()`) lanes
per step: a `SIMD[DType.float64, W]` load straight off each `List`'s backing
buffer (`gemm.blocked.gemv_flat`'s real, working idiom -- `(ptr + i).load[width=W]()`),
one vector arithmetic op, and a `reduce_add()` at the end to fold the lanes
down to one scalar. Any `n % W` remainder runs a plain scalar tail loop, same
shape as `gemv_flat`'s. Their `_strict` siblings take this for free: each one
is a dimension check followed by a call to the vectorized function, not a
second copy of the loop.

`reduce_add()` folds the SIMD lanes in a DIFFERENT order than the scalar
loop's `i = 0, 1, 2, ...` did, and float addition is not associative, so a
sum here CAN differ from the old scalar sum by a few ULP -- measured, not
just theoretical: `tests/mojo/test_embeddings_simd_tail_probe.mojo` sweeps
many lengths with realistic (non-integer) values and finds ULP-level
differences starting at n as small as 2. Every EXISTING hand-written golden
vector in this module's suites (`mojo/tests/libs/test_embeddings.mojo`,
`tests/mojo/test_wave33.mojo`, `tests/mojo/test_embeddings_dimension_mismatch_probe.mojo`)
happens to use small integer-valued inputs, and every one of those stays
EXACTLY bit-identical to its pre-SIMD value (verified) -- but that is a
property of those specific inputs, not a general guarantee, so the tail
probe's broader length sweep compares against a magnitude-scaled tolerance
(`tensorx.dtype.dtx_tol_for`, the same primitive and the same
length-scaled-relative-term shape `gemm.blocked.gemm_reference_delta_flat`
already uses for its own blocked-vs-reference comparison) rather than `==`.
No function's raised-error behavior, signature, or return type changed.
"""
from std.math import sqrt
from std.sys.info import simd_width_of

comptime W: Int = simd_width_of[DType.float64]()
"""SIMD lanes for Float64 on the build target -- `gemm.blocked.W`'s same
alias, re-declared here rather than imported so this module has no
dependency on `gemm`. 2 on 128-bit NEON (this host), 8 on AVX-512."""


def _min_len(a: List[Float64], b: List[Float64]) -> Int:
    var n = len(a)
    if len(b) < n:
        n = len(b)
    return n


def _cosine_similarity_with_query_mag(
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


def _insert_topk(
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


def dot_product(a: List[Float64], b: List[Float64]) -> Float64:
    """Dot product of two vectors. SIMD-vectorized; see the module docstring."""
    var n = _min_len(a, b)
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    var acc = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + W <= n:
        acc += (ap + i).load[width=W]() * (bp + i).load[width=W]()
        i += W
    var s = acc.reduce_add()
    while i < n:
        s += ap[i] * bp[i]
        i += 1
    return s


def dot_product_strict(a: List[Float64], b: List[Float64]) raises -> Float64:
    """`dot_product`, but raises on a dimension mismatch instead of silently
    summing only over `min(len(a), len(b))`. See the module docstring.
    """
    if len(a) != len(b):
        raise Error(
            "dot_product_strict: a has "
            + String(len(a))
            + " dimensions but b has "
            + String(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return dot_product(a, b)


# ── vector_magnitude ─────────────────────────────────────────────────────────


def vector_magnitude(v: List[Float64]) -> Float64:
    """L2 norm (magnitude) of a vector. SIMD-vectorized; see the module
    docstring."""
    var n = len(v)
    var vp = v.unsafe_ptr()
    var acc = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + W <= n:
        var chunk = (vp + i).load[width=W]()
        acc += chunk * chunk
        i += W
    var s = acc.reduce_add()
    while i < n:
        s += vp[i] * vp[i]
        i += 1
    return sqrt(s)


# ── cosine_similarity ────────────────────────────────────────────────────────


def cosine_similarity(a: List[Float64], b: List[Float64]) -> Float64:
    """Cosine similarity between two vectors. SIMD-vectorized; see the module
    docstring."""
    var n = _min_len(a, b)
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    var dot_acc = SIMD[DType.float64, W](0.0)
    var sqa_acc = SIMD[DType.float64, W](0.0)
    var sqb_acc = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + W <= n:
        var av = (ap + i).load[width=W]()
        var bv = (bp + i).load[width=W]()
        dot_acc += av * bv
        sqa_acc += av * av
        sqb_acc += bv * bv
        i += W
    var dot = dot_acc.reduce_add()
    var sq_a = sqa_acc.reduce_add()
    var sq_b = sqb_acc.reduce_add()
    while i < n:
        var av = ap[i]
        var bv = bp[i]
        dot += av * bv
        sq_a += av * av
        sq_b += bv * bv
        i += 1
    if sq_a <= 0.0 or sq_b <= 0.0:
        return 0.0
    return dot / (sqrt(sq_a) * sqrt(sq_b))


def cosine_similarity_strict(a: List[Float64], b: List[Float64]) raises -> Float64:
    """`cosine_similarity`, but raises on a dimension mismatch instead of
    silently comparing only over `min(len(a), len(b))`. See the module
    docstring.
    """
    if len(a) != len(b):
        raise Error(
            "cosine_similarity_strict: a has "
            + String(len(a))
            + " dimensions but b has "
            + String(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return cosine_similarity(a, b)


# ── euclidean_distance ───────────────────────────────────────────────────────


def euclidean_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """L2 (Euclidean) distance between two vectors. SIMD-vectorized; see the
    module docstring."""
    var n = _min_len(a, b)
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    var acc = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + W <= n:
        var d = (ap + i).load[width=W]() - (bp + i).load[width=W]()
        acc += d * d
        i += W
    var s = acc.reduce_add()
    while i < n:
        var d = ap[i] - bp[i]
        s += d * d
        i += 1
    return sqrt(s)


def euclidean_distance_strict(a: List[Float64], b: List[Float64]) raises -> Float64:
    """`euclidean_distance`, but raises on a dimension mismatch instead of
    silently measuring only over `min(len(a), len(b))`. See the module
    docstring.
    """
    if len(a) != len(b):
        raise Error(
            "euclidean_distance_strict: a has "
            + String(len(a))
            + " dimensions but b has "
            + String(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return euclidean_distance(a, b)


# ── manhattan_distance ───────────────────────────────────────────────────────


def manhattan_distance(a: List[Float64], b: List[Float64]) -> Float64:
    """L1 (Manhattan) distance between two vectors. SIMD-vectorized; see the
    module docstring."""
    var n = _min_len(a, b)
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    var acc = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + W <= n:
        acc += abs((ap + i).load[width=W]() - (bp + i).load[width=W]())
        i += W
    var s = acc.reduce_add()
    while i < n:
        var d = ap[i] - bp[i]
        if d < 0.0:
            d = -d
        s += d
        i += 1
    return s


def manhattan_distance_strict(a: List[Float64], b: List[Float64]) raises -> Float64:
    """`manhattan_distance`, but raises on a dimension mismatch instead of
    silently measuring only over `min(len(a), len(b))`. See the module
    docstring.
    """
    if len(a) != len(b):
        raise Error(
            "manhattan_distance_strict: a has "
            + String(len(a))
            + " dimensions but b has "
            + String(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return manhattan_distance(a, b)


# ── normalize_vector ─────────────────────────────────────────────────────────


def normalize_vector(v: List[Float64]) -> List[Float64]:
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


def centroid(vectors: List[List[Float64]]) raises -> List[Float64]:
    """Mean of vectors (centroid).

    Raises if any vector after the first has a different length than
    `vectors[0]`. The averaging loop below reads every vector at indices
    `0 .. dim-1` (`dim` taken from `vectors[0]`) -- indexing a shorter vector
    at those positions is an out-of-bounds `List` access, which is an
    uncatchable, worker-killing bounds assertion in this runtime rather than
    a normal exception (see the kernel-count-abort precedent). A raise here,
    before any such index is touched, is the only correct behavior for a
    length mismatch; unlike a lenient-truncation choice elsewhere in this
    module, no caller can ever have a legitimate reason to want a crash.
    """
    var n = len(vectors)
    if n == 0:
        return List[Float64]()
    var dim = len(vectors[0])
    for i in range(1, n):
        if len(vectors[i]) != dim:
            raise Error(
                "centroid: vectors[0] has "
                + String(dim)
                + " dimensions but vectors["
                + String(i)
                + "] has "
                + String(len(vectors[i]))
                + "; all vectors must share the same dimensionality"
            )
    var result = vectors[0].copy()
    for i in range(1, n):
        for d in range(dim):
            result[d] += vectors[i][d]
    var inv_n = 1.0 / Float64(n)
    for d in range(dim):
        result[d] *= inv_n
    return result^


# ── nearest_neighbor ─────────────────────────────────────────────────────────


def nearest_neighbor(query: List[Float64], candidates: List[List[Float64]]) -> Int:
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


def nearest_neighbor_strict(
    query: List[Float64], candidates: List[List[Float64]]
) raises -> Int:
    """`nearest_neighbor`, but raises if any candidate's dimensionality
    differs from `query`'s instead of silently comparing over
    `min(len(query), len(candidate))` per candidate (via
    `_cosine_similarity_with_query_mag`). See the module docstring.
    """
    var qlen = len(query)
    for i in range(len(candidates)):
        if len(candidates[i]) != qlen:
            raise Error(
                "nearest_neighbor_strict: query has "
                + String(qlen)
                + " dimensions but candidates["
                + String(i)
                + "] has "
                + String(len(candidates[i]))
                + " dimensions; every candidate must share the query's"
                " dimensionality"
            )
    return nearest_neighbor(query, candidates)


# ── k_nearest_neighbors ─────────────────────────────────────────────────────


def k_nearest_neighbors(
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


def k_nearest_neighbors_strict(
    query: List[Float64], candidates: List[List[Float64]], k: Int
) raises -> List[Int]:
    """`k_nearest_neighbors`, but raises if any candidate's dimensionality
    differs from `query`'s instead of silently comparing over
    `min(len(query), len(candidate))` per candidate. See the module
    docstring.

    `k` is CLAMPED to `len(candidates)` inside `k_nearest_neighbors` itself
    (`if count > n_candidates: count = n_candidates`) rather than used to
    index anything directly, so an oversized `k` is answered with "all
    candidates, ranked" instead of an out-of-bounds read.

    @capability k_nearest_neighbors_strict
    complexity: O(n log k)
    counts:
    - k <= len(candidates) [clamped]
    @endcapability
    """
    var qlen = len(query)
    for i in range(len(candidates)):
        if len(candidates[i]) != qlen:
            raise Error(
                "k_nearest_neighbors_strict: query has "
                + String(qlen)
                + " dimensions but candidates["
                + String(i)
                + "] has "
                + String(len(candidates[i]))
                + " dimensions; every candidate must share the query's"
                " dimensionality"
            )
    return k_nearest_neighbors(query, candidates, k)


# ── cosine_similarity_matrix ─────────────────────────────────────────────────


def cosine_similarity_matrix(vectors: List[List[Float64]]) -> List[List[Float64]]:
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


def cosine_similarity_matrix_strict(
    vectors: List[List[Float64]],
) raises -> List[List[Float64]]:
    """`cosine_similarity_matrix`, but raises if any vector's dimensionality
    differs from `vectors[0]`'s instead of silently comparing each pair over
    `min(len(vectors[i]), len(vectors[j]))` (via `_min_len`). See the module
    docstring.
    """
    var n = len(vectors)
    if n > 0:
        var dim = len(vectors[0])
        for i in range(1, n):
            if len(vectors[i]) != dim:
                raise Error(
                    "cosine_similarity_matrix_strict: vectors[0] has "
                    + String(dim)
                    + " dimensions but vectors["
                    + String(i)
                    + "] has "
                    + String(len(vectors[i]))
                    + " dimensions; all vectors must share the same"
                    " dimensionality"
                )
    return cosine_similarity_matrix(vectors)


# ── vector_add ───────────────────────────────────────────────────────────────


def vector_add(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Element-wise addition of two vectors."""
    var n = _min_len(a, b)
    var result = List[Float64](capacity=n)
    for i in range(n):
        result.append(a[i] + b[i])
    return result^


def vector_add_strict(a: List[Float64], b: List[Float64]) raises -> List[Float64]:
    """`vector_add`, but raises on a dimension mismatch instead of silently
    adding only over `min(len(a), len(b))`. See the module docstring.
    """
    if len(a) != len(b):
        raise Error(
            "vector_add_strict: a has "
            + String(len(a))
            + " dimensions but b has "
            + String(len(b))
            + " dimensions; both vectors must share the same dimensionality"
        )
    return vector_add(a, b)


# ── vector_scale ─────────────────────────────────────────────────────────────


def vector_scale(v: List[Float64], s: Float64) -> List[Float64]:
    """Scalar multiplication of a vector."""
    var n = len(v)
    var result = List[Float64](capacity=n)
    for i in range(n):
        result.append(v[i] * s)
    return result^
