---
icon: shapes
description: Coordinate-format sparse matrices and paired-array sparse vectors, a dense 1D tensor type, and the standalone scalar index/accumulation formulas an N-D tensor implementation composes.
---

# Sparse structures and tensor primitives

Four modules for two unrelated jobs that happen to share a folder. `sparse` and `sparse_vector`
replace the parts of `scipy.sparse` this codebase actually needs: a coordinate-triplet (COO) matrix
type with matvec, addition, transpose, density and trace, plus a parallel-array sparse vector
representation with dot product, merge-add, cosine similarity, and dense/sparse conversion. `tensor`
is the dense counterpart — a 1D `Tensor1D` array type with the arithmetic, reductions and slicing a
`List[Float64]` needs to stop being a bare list. `tensor_ops` looks like it should be the fourth: the
general N-D tensor engine the other three don't cover. It is not. Every function in `tensor_ops`
takes and returns plain `Float64` scalars — there is no tensor, list, or shape type anywhere in the
file. It is a library of individually-callable formulas for the *steps* an N-D tensor implementation
needs — one accumulation term of a matmul, one flat-index computation, one stable-softmax
probability, one transposed offset — meant to be composed by a caller that already has its own
indexing loop, not a bulk array API in its own right.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 3x3 matrix [[1,0,2],[0,3,0],[4,0,5]] -- 5 of 9 entries are non-zero
dense = [[1.0, 0.0, 2.0], [0.0, 3.0, 0.0], [4.0, 0.0, 5.0]]
mat = runtime.execute("sparse", "sparse_from_dense", [dense, 1e-15])["result"]

runtime.execute("sparse", "sparse_density", [mat])["result"]
# 0.5555555555555556 -- nnz=5 / (3*3)

runtime.execute("sparse", "sparse_matvec", [mat, [1.0, 1.0, 1.0]])["result"]
# [3.0, 3.0, 9.0] -- row 0: 1+2, row 1: 3, row 2: 4+5
```

## The modules

| Module | What it does |
| --- | --- |
| `sparse` | `COOEntry` and `SparseMatrixCOO` — coordinate-format sparse matrices, with `sparse_from_dense`, `sparse_matvec`, `sparse_add`, `sparse_transpose`, `sparse_density`, and `sparse_trace`. |
| `sparse_vector` | Sparse vectors as parallel `(indices, values)` lists — `sv_dot`, `sv_add`, `sv_scale`, `sv_norm`, `sv_cosine`, `sv_to_dense`, `dense_to_sparse`, `sv_nnz`, `sv_sparsity`, `sv_max`. |
| `tensor` | `Tensor1D` — a dense 1D `Float64` array with factories (`zeros`/`ones`/`arange`/`linspace`), element-wise arithmetic, reductions (`sum_t`/`argmax`/`norm`/...), and transforms (`apply_fn`/`slice_t`/`clip`/...). |
| `tensor_ops` | Ten standalone scalar formulas for N-D tensor index and accumulation arithmetic — `flatten_index`, `stride_from_shape`, `transpose_index`, `matmul_element`, `outer_product_element`, `softmax_stable_element`, and others — each computing one step, never a full tensor. |

## `sparse`: COO matrices, and where they feed a bigger engine

`SparseMatrixCOO` stores non-zero entries as an unordered `List[COOEntry]` plus `(nrows, ncols)`; a
`to_dense()` method sums duplicate `(row, col)` entries rather than overwriting, so `sparse_add`
(which concatenates both matrices' entry lists without merging matching coordinates) produces a
`SparseMatrixCOO` that is only correct once rendered through `to_dense` or read through
`sparse_matvec` / `sparse_trace` — the entries themselves may contain the same `(row, col)` twice.
`sparse_from_dense`, `sparse_transpose`, `sparse_density`, and `sparse_trace` are plain, direct
formulas over that entry list; the interesting guard lives in `sparse_matvec`, which validates
`nrows`/`ncols` against a `1 << 26` ceiling (`MAX_COO_DIM`, "keeps one object near the 512 MB
resident-dataset budget," per the module's own comment) and rejects any entry with an out-of-range
row/col or a NaN/Inf value by returning an empty list, rather than indexing past the vector or
letting a non-finite value reach the JSON response.

This module is not a duplicate of the CSR/CSC solvers in
[Sparse systems & graph analytics](sparse-and-graph.md) — it is what feeds them.
`sparse_numerics.csr` imports `COOEntry`, `SparseMatrixCOO`, and `sparse_from_dense` directly to
build its compressed format from triplets, and `sparse_numerics.diagnostics` imports
`sparse_density`/`sparse_trace` for its health-report fields (and `sparse_vector`'s `sv_max`/`sv_nnz`
for the same purpose). `sparse_numerics.spmv` imports `sparse_vector.sv_dot`, `sv_norm`, and
`sv_scale` for its own vector-side arithmetic. The relationship is layered, not redundant: `sparse`
and `sparse_vector` are the coordinate-format and parallel-array primitives; `sparse_numerics` is the
CSR-based solver stack (conjugate gradient, LU, GMRES) built on top of them, documented separately
because it is a much larger family with its own status-code vocabulary and iterative methods.

**Worked example**, verified independently in Python against the same formulas:

```
dense = [[1,0,2],[0,3,0],[4,0,5]]
sparse_from_dense -> entries {(0,0,1),(0,2,2),(1,1,3),(2,0,4),(2,2,5)}, nnz=5
sparse_density      = 5 / 9        = 0.5555555555555556
sparse_trace         = 1 + 3 + 5   = 9.0
sparse_matvec([1,1,1]) = [3.0, 3.0, 9.0]
sparse_transpose -> entries {(0,0,1),(2,0,2),(1,1,3),(0,2,4),(2,2,5)}
                 -> dense [[1,0,4],[0,3,0],[2,0,5]] -- the transpose of the original
```

There is no `test_sparse.mojo` at all in `mojo/tests/libs/` — unlike every other module in this
family, `sparse.mojo` has no dedicated test file. Three of its six functions do get real, pinned
assertions from inside `sparse_numerics`'s own test suites, though: `test_sparse_numerics_csr.mojo`
calls `sparse_matvec` directly as a "frozen oracle" cross-check against CSR's own matvec — both
compute `A @ [1,2,3] = [7,6]` for the same matrix — and `test_sparse_numerics_diagnostics.mojo` calls
`sparse_add` and `sparse_density` directly to build a deliberately-unmerged duplicate: two entries of
`2.0` stored at the same `(0,0)` coordinate make `sparse_density` return `2.0` — density *exceeding*
`1.0` — because `sparse_add` concatenates entry lists without coalescing matching coordinates, a case
the test uses specifically to contrast against CSR's own coalesced density of `1.0` for the identical
data. `sparse_transpose`, and the bare `sparse_trace` function itself (as opposed to
`sparse_numerics.diagnostics`'s own `sparse_trace_checked`/`sparse_trace_driver` wrappers around it),
are never called anywhere in the test tree.

## `sparse_vector`: paired-array sparse vectors

Every function here operates on two parallel `List`s — `indices: List[Int]` and
`values: List[Float64]` — with no struct wrapping them; the merge-based functions (`sv_dot`, `sv_add`,
`sv_cosine`) assume both inputs' indices are sorted ascending and use a two-pointer merge rather than
a nested loop, so they are `O(na + nb)`, not `O(na * nb)`. `sv_add` special-cases identical index
arrays (`_same_indices`) to skip the merge entirely, and both the identical-index and general-merge
paths drop any summed entry whose magnitude falls to `≤ 1e-15` — genuine fill-in cancellation is
pruned from the result rather than carried as an explicit zero. `sv_to_dense` has its own fast path:
if the sparse representation is already dense and in identity order (`len(values) == size` and
`indices == [0, 1, ..., size-1]`), it returns a copy of `values` directly rather than scattering
element by element.

**Worked example**, hand-verified in Python against the two-pointer merge formulas:

```
a: indices=[0,2,4], values=[3,4,12]      (‖a‖ = sqrt(9+16+144) = 13.0)
b: indices=[2,3,4], values=[5,1,4]       (‖b‖ = sqrt(25+1+16)  = 6.480740698...)

sv_dot(a, b)    = 4*5 + 12*4 = 68.0        -- only indices 2 and 4 overlap
sv_cosine(a, b) = 68.0 / (13.0 * 6.480740698...) = 0.807125215186327
sv_add(a, b)    = indices [0, 2, 3, 4], values [3.0, 9.0, 1.0, 16.0]
```

`sv_norm` and `sv_max` take only a `values` list (no indices) — they are defined purely on the
non-zero magnitudes, indifferent to which coordinates they came from, which is why `sv_sparsity`
(`1.0 - nnz/size`, `1.0` if `size <= 0`) needs the count and the dense size passed in separately
rather than deriving them from a single sparse-vector argument.

## `tensor`: the dense 1D companion to `tensor2d`'s matrices

`tensor.mojo`'s own docstring and `tensor2d.mojo`'s both name this relationship directly:
[`tensor2d`](ml-tensor2d.md)'s `Matrix2D` "complements `tensor.mojo` (1D `Tensor1D`)" — `tensor` is
the 1D vector type, `tensor2d` is the 2D dense matrix type, and neither file imports the other; they
share a design (row-major `List[Float64]` storage, deterministic never-trap shape handling) rather
than code. `Tensor1D` is not used by `tensorx` either: `tensorx/__init__.mojo`'s own docstring lists
`tensor.Tensor1D` as one of the things "the kernel tree already has" that motivated building
`tensorx` in the first place — `Tensor1D` is a bare `List[Float64]` with no dtype tag, and `tensorx`
exists specifically to add the ten-code dtype system (`float64` down to 4-bit `nf4`) that `Tensor1D`
and `Matrix2D` both lack. None of `add`, `sub`, `dot`, `apply_fn`, or any other `tensor` function
takes or returns a `tensorx.buffer.TxBuffer` — the two families are related by lineage, not by call.

Element-wise binary ops (`add`, `sub`, `mul`, `div_t`, `dot`) silently truncate to the shorter
operand's length rather than refusing a size mismatch (`n = min(a.size, b.size)`); `div_t` returns
`0.0` for any element where the divisor is exactly `0.0` rather than propagating `inf`/`nan`.
`slice_t(a, start, end)` clamps `start` up to `0` and `end` down to `a.size`, returning an empty
tensor if the clamped range is degenerate — negative indexing (Python's `a[-1]` style) is explicitly
not supported. `apply_fn`'s `"log"` branch on `x <= 0.0` returns a fixed `-1e300` sentinel rather than
a real `-inf`, and its `"sigmoid"` branch swaps between `1/(1+e^-x)` and `e^x/(1+e^x)` depending on
the sign of `x`, the standard trick to avoid overflowing `exp` on a large negative input.

**Worked example**, hand-verified in Python against the real arithmetic (no numbers below are
invented — every one reproduces the source formula exactly):

```
a = [3, -1, 4, 1, 5]        b = [2, 7, 1, 8, 2]

add(a, b)  = [5, 6, 5, 9, 7]         dot(a, b)  = 6 - 7 + 4 + 8 + 10 = 21
norm(a)    = sqrt(9+1+16+1+25) = sqrt(52) = 7.211102550927978
mean_t(a)  = 12 / 5 = 2.4            argmax(a) = 4  (value 5)
prod_t(a)  = 3*-1*4*1*5 = -60
apply_fn(a, "sigmoid")[0] = 1/(1+e^-3) = 0.9525741268224334
clip(a, 0, 4)   = [3, 0, 4, 1, 4]
where_gt(a, 2)  = [0, 2, 4]           -- indices of 3, 4, 5
linspace(0, 1, 5) = [0.0, 0.25, 0.5, 0.75, 1.0]
```

## `tensor_ops`: index and accumulation formulas, not a tensor engine

None of `tensor_ops`'s ten functions is imported by any other `.mojo` file in this tree — the
generated dispatch table (`runtime_library_dispatch_generated.mojo`) is the only caller found in
source, meaning every function here is reached exclusively through `runtime.execute("tensor_ops",
...)` directly rather than composed internally by some larger kernel. Read individually, each is the
one-line formula behind a step of building an N-D tensor operation from indices: `flatten_index(row,
col, n_cols) = row*n_cols + col` is a 2D row-major offset; `transpose_index(row, col, n_rows) =
col*n_rows + row` is the same offset after a 2D transpose; `broadcast_index(idx, dim_size)` maps an
index to `0` when `dim_size <= 1` (NumPy-style broadcast) and passes it through otherwise;
`outer_product_element(a_i, b_j) = a_i * b_j`; `tensor_norm_contribution(x) = x*x` (sum these, then
`sqrt`, for an L2 norm); `softmax_stable_element(x_i, x_max, sum_exp) = exp(x_i - x_max) / sum_exp`
(`0.0` if `sum_exp <= 0`); `tensor_dot_contribution(a, b, axis_size) = a*b / axis_size` (`0.0` if
`axis_size <= 0`); and `matmul_element(a_row_sum, b_col_element) = a_row_sum + b_col_element` — this
last one does not multiply anything itself, matching its own docstring's note that "caller provides
A[i,k] via grad_mul pattern": the caller is expected to compute the `A[i,k] * B[k,j]` product before
calling this function, which then only performs the running-sum step.

**Worked and independently verified** (softmax over logits `[2.0, 1.0, 0.1]`, `x_max = 2.0`,
`sum_exp = e^0 + e^-1 + e^-1.9 = 1.5174480603940774`):

```
softmax_stable_element(2.0, 2.0, 1.5174480603940774) = 0.6590011388859679
softmax_stable_element(1.0, 2.0, 1.5174480603940774) = 0.24243297070471392
softmax_stable_element(0.1, 2.0, 1.5174480603940774) = 0.09856589040931818
-- sums to 1.0, matching a real softmax over the same three logits

flatten_index(2, 3, 4)     = 11    -- row 2, col 3 of a row-major (5, 4) matrix
transpose_index(2, 3, 5)   = 17    -- same element's offset after transposing to (4, 5)
```

### A docstring/usage mismatch found in `stride_from_shape`

`stride_from_shape(dim_size, next_stride)` returns `dim_size * next_stride`, and its own docstring
labels the first argument `dim_size: Size of this dimension` — meaning the dimension whose stride is
being computed. That labeling does not match the arithmetic needed to actually build correct
row-major strides. For shape `(2, 3, 4)`, the real strides are `(12, 4, 1)` (rightmost = `1`, then
each stride to the left = the size of the dimension *to its right* times that dimension's own
stride: `stride[1] = 4 * stride[2] = 4*1 = 4`, `stride[0] = 3 * stride[1] = 3*4 = 12`). Reproducing
that in Python by calling `stride_from_shape(dim_size, next_stride)` right-to-left and feeding
`dim_size` = the size of the dimension to the *right* (the inner one already processed) gives exactly
`[12, 4, 1]` — correct. Feeding `dim_size` = the size of "this" dimension instead, following the
docstring's literal wording, gives `[6, 3, 1]` for the same shape — silently wrong strides that would
misindex every dimension but the last. The function's arithmetic (a single multiply) is not the
defect; the `Args` description of which dimension's size to pass is inconsistent with the formula it
sits above, and a caller who trusts that wording over the worked derivation would build the wrong
stride table. `unflatten_index_dim`, checked independently against a flat index of `17` in a `(2, 3,
4)` tensor using the *correct* strides `(12, 4, 1)`, decodes back to multi-index `(1, 1, 1)` exactly —
so the rest of this module's index arithmetic is internally consistent; the mislabeling is confined to
`stride_from_shape`'s own docstring.

## Verification

`test_sparse_vector.mojo`, `test_tensor.mojo`, and `test_tensor_ops.mojo` are auto-generated coverage
smoke tests: each calls every function once with fixed fixtures (`0.5`-style scalars, or a five-element
`[0.5, 0.6, 0.7, 0.4, 0.3]` / `[1,2,3,4,5]` fixture pair) and checks only that the result is finite (or,
for list-returning functions, that a result was produced at all) — none pins a specific numeric output,
and `test_tensor.mojo` only exercises the five factory functions (`zeros`/`ones`/`full`/`arange`/
`linspace`), never the arithmetic, reduction, or transform functions. `sparse.mojo` has no test file at
all. Every worked number in this page was hand-derived from the real function bodies in
`mojo/engine/sparse.mojo`, `sparse_vector.mojo`, `tensor.mojo`, and `tensor_ops.mojo`, and independently
re-computed in Python before being presented here — including the `stride_from_shape` trace above, run
both the documented way and the working way to confirm the two diverge.

**Next:** see the CSR-based solver stack these coordinate and sparse-vector primitives feed in
[Sparse systems & graph analytics](sparse-and-graph.md), or the dtype-tagged buffer substrate
`tensor`'s `Tensor1D` predates in [Tensor buffer primitives](tensorx-kernels.md).
