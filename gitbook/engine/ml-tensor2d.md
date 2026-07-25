---
icon: table-cells
description: Dense 2-D matrix type with matmul, matvec and outer products backing the trainable-model kernels.
---

# Dense 2D matrices (Matrix2D)

`tensor2d` is the minimal dense 2D matrix type the ML kernels build on —
zero Python imports. It replaces the numpy 2D essentials (`np.zeros`, 2D
`np.array`, `A @ B`, `A @ x`, `A.T`, `A + B`, `c * A`, row/column
slicing) with a row-major `List[Float64]` store plus the core products,
and complements `tensor.mojo` (1D `Tensor1D`) and `linalg.mojo`
(solvers/decompositions).

## Functions

| Function | What it does |
|---|---|
| `Matrix2D(rows, cols)` | Dense row-major matrix; element (i, j) lives at `data[i * cols + j]`; negative dims clamp to 0. |
| `m2_zeros(rows, cols)` | rows x cols matrix of zeros. |
| `m2_from_list(data, rows, cols)` | Build from a row-major flat list; short input is zero-padded, extra values ignored. |
| `m2_get(m, i, j)` | Element at (i, j); returns 0.0 when out of range. |
| `m2_set(m, i, j, val)` | Write val at (i, j); silent no-op when out of range. |
| `m2_matmul(a, b)` | Matrix product A(m x p) @ B(p x n) -> (m x n); i-k-j loop order keeps the inner loop contiguous in both B and C. |
| `m2_matvec(a, x)` | Matrix-vector product A(m x n) @ x(n) -> list of m values. |
| `m2_transpose(a)` | A^T: (m x n) -> (n x m). |
| `m2_add(a, b)` | Element-wise A + B (same shape). |
| `m2_scale(a, c)` | Scalar multiple c * A. |
| `m2_row(a, i)` | Copy of row i as `List[Float64]`; empty when out of range. |
| `m2_col(a, j)` | Copy of column j as `List[Float64]`; empty when out of range. |

## Shape-mismatch policy: deterministic, never traps

Binary ops on incompatible shapes return an empty 0x0 `Matrix2D` (or an
empty `List` for `m2_matvec`); out-of-range `m2_get` returns 0.0 and
out-of-range `m2_set` is a no-op. Callers gate on `rows/cols > 0`
instead of catching exceptions. All loops are plain O(m·n) / O(m·p·n)
passes — sub-millisecond for typical ML-kernel shapes (a 100x100x100
product is ~1e6 mul-adds); a full 10k x 10k dense product is inherently
much slower and out of scope for this minimal type.

## Verification

The test suite pins hand-computed values at 1e-12 absolute tolerance:
`[[1,2,3],[4,5,6]] @ [[7,8],[9,10],[11,12]] = [[58,64],[139,154]]` and
`[[1,2,3],[4,5,6]] @ [2,1,3] = [13,31]`, plus the algebraic identities
`A @ I == A`, `(A^T)^T == A`, `(AB)^T == B^T A^T`, and
`A + (-A) == zeros`. Edge shapes are covered explicitly: 1x1 products,
row-vector @ column-vector = `[[32]]`, 3x1 @ 1x3 outer products, and
0x0 / negative-dimension inputs.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
