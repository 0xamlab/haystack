"""
sparse_vector.mojo — Sparse vector operations. Zero Python imports.

Replaces scipy.sparse vector ops with pure Mojo implementations using
parallel index/value lists.

Public API:
  sv_dot            — Sparse dot product
  sv_add            — Sparse addition (merged)
  sv_scale          — Scale all values
  sv_norm           — L2 norm
  sv_cosine         — Cosine similarity
  sv_to_dense       — Convert to dense vector
  dense_to_sparse   — Convert dense to sparse
  sv_nnz            — Count non-zeros
  sv_sparsity       — Sparsity ratio
  sv_max            — Max value in sparse vector
"""
from std.math import sqrt, abs as fabs


def _same_indices(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _is_identity_indices(indices: List[Int], size: Int) -> Bool:
    if len(indices) != size:
        return False
    for i in range(size):
        if indices[i] != i:
            return False
    return True


def _all_above_tol(values: List[Float64], tol: Float64) -> Bool:
    for i in range(len(values)):
        if fabs(values[i]) <= tol:
            return False
    return True


# ── sv_dot ─────────────────────────────────────────────────────────────────────


def sv_dot(
    idx_a: List[Int], val_a: List[Float64],
    idx_b: List[Int], val_b: List[Float64],
) -> Float64:
    """Sparse dot product. Two-pointer merge on sorted indices."""
    if len(idx_a) != len(val_a) or len(idx_b) != len(val_b):
        return 0.0
    var result: Float64 = 0.0
    var i = 0
    var j = 0
    var na = len(idx_a)
    var nb = len(idx_b)
    while i < na and j < nb:
        if idx_a[i] == idx_b[j]:
            result += val_a[i] * val_b[j]
            i += 1
            j += 1
        elif idx_a[i] < idx_b[j]:
            i += 1
        else:
            j += 1
    return result


# ── sv_add ─────────────────────────────────────────────────────────────────────


def sv_add(
    idx_a: List[Int], val_a: List[Float64],
    idx_b: List[Int], val_b: List[Float64],
) -> List[List[Float64]]:
    """Sparse addition. Returns [[merged_indices_as_float], [merged_values]]."""
    if len(idx_a) != len(val_a) or len(idx_b) != len(val_b):
        return List[List[Float64]]()
    var na = len(idx_a)
    var nb = len(idx_b)
    if _same_indices(idx_a, idx_b):
        var same_idx = List[Float64](capacity=na)
        var same_val = List[Float64](capacity=na)
        for i in range(na):
            var s = val_a[i] + val_b[i]
            if fabs(s) > 1e-15:
                same_idx.append(Float64(idx_a[i]))
                same_val.append(s)
        var same_result = List[List[Float64]](capacity=2)
        same_result.append(same_idx^)
        same_result.append(same_val^)
        return same_result^

    var merged_idx = List[Float64](capacity=na + nb)
    var merged_val = List[Float64](capacity=na + nb)
    var i = 0
    var j = 0
    while i < na and j < nb:
        if idx_a[i] == idx_b[j]:
            var s = val_a[i] + val_b[j]
            if fabs(s) > 1e-15:
                merged_idx.append(Float64(idx_a[i]))
                merged_val.append(s)
            i += 1
            j += 1
        elif idx_a[i] < idx_b[j]:
            merged_idx.append(Float64(idx_a[i]))
            merged_val.append(val_a[i])
            i += 1
        else:
            merged_idx.append(Float64(idx_b[j]))
            merged_val.append(val_b[j])
            j += 1
    while i < na:
        merged_idx.append(Float64(idx_a[i]))
        merged_val.append(val_a[i])
        i += 1
    while j < nb:
        merged_idx.append(Float64(idx_b[j]))
        merged_val.append(val_b[j])
        j += 1
    var result = List[List[Float64]](capacity=2)
    result.append(merged_idx^)
    result.append(merged_val^)
    return result^


# ── sv_scale ───────────────────────────────────────────────────────────────────


def sv_scale(values: List[Float64], scalar: Float64) -> List[Float64]:
    """Scale all values by a scalar."""
    var out = values.copy()
    var n = len(out)
    for i in range(n):
        out[i] = out[i] * scalar
    return out^


# ── sv_norm ────────────────────────────────────────────────────────────────────


def sv_norm(values: List[Float64]) -> Float64:
    """L2 norm of sparse vector values."""
    var s: Float64 = 0.0
    for i in range(len(values)):
        s += values[i] * values[i]
    return sqrt(s)


# ── sv_cosine ──────────────────────────────────────────────────────────────────


def sv_cosine(
    idx_a: List[Int], val_a: List[Float64],
    idx_b: List[Int], val_b: List[Float64],
) -> Float64:
    """Cosine similarity between two sparse vectors."""
    if len(idx_a) != len(val_a) or len(idx_b) != len(val_b):
        return 0.0
    var dot = sv_dot(idx_a, val_a, idx_b, val_b)
    var na = sv_norm(val_a)
    var nb = sv_norm(val_b)
    if na < 1e-30 or nb < 1e-30:
        return 0.0
    return dot / (na * nb)


# ── sv_to_dense ────────────────────────────────────────────────────────────────


def sv_to_dense(indices: List[Int], values: List[Float64], size: Int) -> List[Float64]:
    """Convert sparse representation to dense vector."""
    if size <= 0:
        return List[Float64]()
    if len(indices) != len(values):
        return List[Float64]()
    if len(values) == size and _is_identity_indices(indices, size):
        return values.copy()

    var out = List[Float64](capacity=size)
    for i in range(size):
        out.append(0.0)
    for i in range(len(indices)):
        if indices[i] >= 0 and indices[i] < size:
            out[indices[i]] = values[i]
    return out^


# ── dense_to_sparse ────────────────────────────────────────────────────────────


def dense_to_sparse(dense: List[Float64], tol: Float64 = 1e-15) -> List[List[Float64]]:
    """Convert dense vector to sparse. Returns [[indices_as_float], [values]]."""
    var n = len(dense)
    if _all_above_tol(dense, tol):
        var dense_idx = List[Float64](capacity=n)
        for i in range(n):
            dense_idx.append(Float64(i))
        var dense_result = List[List[Float64]](capacity=2)
        dense_result.append(dense_idx^)
        dense_result.append(dense.copy())
        return dense_result^
    var idx = List[Float64](capacity=n)
    var vals = List[Float64](capacity=n)
    for i in range(n):
        if fabs(dense[i]) > tol:
            idx.append(Float64(i))
            vals.append(dense[i])
    var result = List[List[Float64]](capacity=2)
    result.append(idx^)
    result.append(vals^)
    return result^


# ── sv_nnz ─────────────────────────────────────────────────────────────────────


def sv_nnz(values: List[Float64]) -> Int:
    """Count non-zero entries."""
    var count = 0
    for i in range(len(values)):
        if fabs(values[i]) > 1e-30:
            count += 1
    return count


# ── sv_sparsity ────────────────────────────────────────────────────────────────


def sv_sparsity(nnz: Int, size: Int) -> Float64:
    """Sparsity ratio: 1 - nnz/size."""
    if size <= 0:
        return 1.0
    return 1.0 - Float64(nnz) / Float64(size)


# ── sv_max ─────────────────────────────────────────────────────────────────────


def sv_max(values: List[Float64]) -> Float64:
    """Max value in sparse vector values list."""
    if len(values) == 0:
        return 0.0
    var m = values[0]
    for i in range(1, len(values)):
        if values[i] > m:
            m = values[i]
    return m
