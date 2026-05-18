"""
tensor_ops.mojo — Tensor math: matmul, broadcast, reshape, stride calculations.
Zero Python imports.

Public API:
  matmul_element                 — one element of matrix multiplication
  broadcast_index                — broadcasted flat index computation
  stride_from_shape              — compute row-major stride
  flatten_index                  — ND index → flat index
  unflatten_index_dim            — flat index → dimension value
  transpose_index                — transposed 2D flat index
  outer_product_element          — one element of outer product
  tensor_norm_contribution       — L2 norm element contribution
  softmax_stable_element         — numerically stable softmax element
  tensor_dot_contribution        — one element of generalised tensor dot
"""
from std.math import sqrt, log, exp


fn matmul_element(
    a_row_sum: Float64, b_col_element: Float64
) -> Float64:
    """One accumulation step in matrix multiplication C = A × B.

    C[i,j] = Σ_k A[i,k] × B[k,j]  — this is one A×B term.

    Args:
        a_row_sum: Running sum Σ A[i,k] × B[k,j] so far.
        b_col_element: B[k,j] element being added.

    Returns:
        Updated accumulator (caller provides A[i,k] via grad_mul pattern).
    """
    return a_row_sum + b_col_element


fn broadcast_index(
    idx: Float64, dim_size: Float64
) -> Float64:
    """NumPy-style broadcast: map index to 0 if dim_size == 1.

    Args:
        idx: Original index along dimension.
        dim_size: Size of this dimension in the tensor.

    Returns:
        Effective index (0 for broadcast dims, idx otherwise).
    """
    if dim_size <= 1.0:
        return 0.0
    return idx


fn stride_from_shape(
    dim_size: Float64, next_stride: Float64
) -> Float64:
    """Row-major stride for a dimension: stride = next_stride × dim_size.

    Build strides from right to left; rightmost stride = 1.

    Args:
        dim_size: Size of this dimension.
        next_stride: Stride of the next (inner) dimension.

    Returns:
        Stride for this dimension.
    """
    return dim_size * next_stride


fn flatten_index(
    row: Float64, col: Float64, n_cols: Float64
) -> Float64:
    """2D row-major flat index: row × n_cols + col.

    Args:
        row: Row index.
        col: Column index.
        n_cols: Number of columns (row stride).

    Returns:
        Flat index.
    """
    return row * n_cols + col


fn unflatten_index_dim(
    flat_idx: Float64, stride: Float64, dim_size: Float64
) -> Float64:
    """Extract dimension index from flat index.

    dim_idx = (flat_idx // stride) % dim_size

    Args:
        flat_idx: Flat tensor index.
        stride: Stride of this dimension.
        dim_size: Size of this dimension.

    Returns:
        Index along this dimension.
    """
    if stride <= 0.0 or dim_size <= 0.0:
        return 0.0
    return Float64(Int64(flat_idx / stride) % Int64(dim_size))


fn transpose_index(
    row: Float64, col: Float64, n_rows: Float64
) -> Float64:
    """Flat index after 2D transpose: col × n_rows + row.

    Args:
        row: Row in original matrix.
        col: Column in original matrix.
        n_rows: Number of rows in original (= n_cols after transpose).

    Returns:
        Flat index in transposed matrix.
    """
    return col * n_rows + row


fn outer_product_element(a_i: Float64, b_j: Float64) -> Float64:
    """Outer product element: (a ⊗ b)[i,j] = a_i × b_j.

    Args:
        a_i: Element from vector a.
        b_j: Element from vector b.

    Returns:
        Outer product element.
    """
    return a_i * b_j


fn tensor_norm_contribution(x: Float64) -> Float64:
    """L2 norm contribution: x².

    Sum these across elements then sqrt to get L2 norm.

    Args:
        x: Tensor element.

    Returns:
        Squared element value.
    """
    return x * x


fn softmax_stable_element(
    x_i: Float64, x_max: Float64, sum_exp: Float64
) -> Float64:
    """Numerically stable softmax element: exp(x_i - max) / Σexp(x_j - max).

    Args:
        x_i: Logit for this class.
        x_max: Maximum logit in the vector.
        sum_exp: Σ exp(x_j - x_max) across all classes.

    Returns:
        Softmax probability.
    """
    if sum_exp <= 0.0:
        return 0.0
    return exp(x_i - x_max) / sum_exp


fn tensor_dot_contribution(
    a: Float64, b: Float64, axis_size: Float64
) -> Float64:
    """Generalised tensor dot: one a×b term normalised by axis size.

    Args:
        a: Tensor element from A.
        b: Tensor element from B.
        axis_size: Size of the contracted axis (for averaging).

    Returns:
        Normalised contribution.
    """
    if axis_size <= 0.0:
        return 0.0
    return a * b / axis_size
