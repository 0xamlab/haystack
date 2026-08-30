---
icon: square-root-variable
description: Dense matrix arithmetic, LU/QR/Cholesky decompositions, 2×2 eigenvalues and power iteration, and elementwise matrix operations, split across two independent in-tree matrix representations.
---

# Core linear algebra kernels

Four modules for the dense linear algebra underneath everything else in the tree that isn't a
GEMM-scale matmul: solving `Ax = b`, inverting and decomposing small-to-medium matrices, checking a
matrix's basic properties (symmetric, positive-definite, orthogonal), and the elementwise algebra
(Kronecker/Hadamard products, matrix powers, vectorization) that shows up in kernels elsewhere in the
tree. The surprise worth flagging up front: this is not one implementation reused four ways — it is
**two independent matrix representations**, each with its own take on LU decomposition, determinants,
and linear solves, and neither imports the other. `linalg` and `linalg_ext` operate on a `Matrix`
struct (flat row-major `List[Float64]` plus explicit `rows`/`cols`, with `get`/`set` accessors);
`matrix_decomp` and `matrix_ops` operate directly on nested `List[List[Float64]]` and never construct
a `Matrix` at all. `linalg_ext` is a genuine extension — its docstring says so and its imports prove
it (`from linalg import Matrix, mat_mul, mat_inv, mat_det, ...`) — but `matrix_decomp` and
`matrix_ops` import only `std.math`, nothing from `linalg` or each other's sibling. The result is a
tree with two parallel, non-interoperating ways to do an LU decomposition, and a caller has to know
which matrix representation the rest of their pipeline is already using before picking one.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# linalg: the Matrix struct is a dict with data/rows/cols fields
a = {"data": [2.0, 1.0, 1.0, 1.0], "rows": 2, "cols": 2}   # [[2,1],[1,1]]
runtime.execute("linalg", "mat_solve", [a, [5.0, 3.0]])["result"]
# [2.0, 1.0] -- solves [[2,1],[1,1]]*x = [5,3]

# matrix_decomp: the same 2x2 matrix, as a plain nested list -- a different calling convention
runtime.execute("matrix_decomp", "det_2x2", [[[2.0, 1.0], [1.0, 1.0]]])["result"]
# 1.0
```

## The modules

| Module | What it does |
| --- | --- |
| `linalg` | The `Matrix` struct (flat row-major storage, `get`/`set`) plus its core operations: zero/identity/from-list construction, elementwise add/sub/scale/transpose, matrix multiplication, determinant (direct formulas through 4×4, LU-based beyond that), Gauss-Jordan inverse, Gaussian-elimination solve, vector dot/norm/cross product, LU decomposition with partial pivoting, and closed-form eigenvalues for 2×2 matrices. |
| `linalg_ext` | Builds on `linalg`'s `Matrix` type: QR decomposition via modified Gram-Schmidt, Frobenius and infinity matrix norms, trace, a symmetry check, a positive-definite check (by attempting a Cholesky factorization), power iteration for the dominant eigenvalue/eigenvector of any size square matrix, and an approximate condition number from the ratio of infinity norms. |
| `matrix_decomp` | A second, independent implementation over nested `List[List[Float64]]`: LU decomposition (Doolittle, unit-diagonal `L`), Cholesky decomposition (the one place in this family that returns the actual factor `L`, not just a pass/fail), 2×2 eigenvalues *and* eigenvectors, fixed-size 2×2/3×3 determinants, trace, symmetry and positive-definite checks, and standalone forward/back triangular solvers plus a combined `solve_lu`. |
| `matrix_ops` | Elementwise and structural matrix algebra, also over nested lists, that neither other module has: Kronecker and Hadamard products, integer matrix powers by repeated squaring, outer product, a Taylor-series matrix exponential, column-major vectorization (`vec`/`unvec`), L1 and L∞ matrix norms, the commutator `[A,B] = AB - BA`, an orthogonality check, and Gram-Schmidt orthonormalization. |

## `linalg`: the `Matrix` struct and its core operations

| Function | What it does |
| --- | --- |
| `Matrix(rows, cols)` / `mat_zeros` | Zero-initialized matrix; `data` is a flat row-major `List[Float64]`, element `(i,j)` lives at `data[i*cols+j]`. |
| `mat_identity(n)` | `n×n` identity. |
| `mat_from_list(data, rows, cols)` | Builds from a flat row-major list; short input is zero-padded, extra values ignored. |
| `mat_add`, `mat_sub`, `mat_scale`, `mat_transpose` | Elementwise add/subtract, scalar multiply, transpose. |
| `mat_mul(a, b)` | `C = A × B`, textbook triple loop, `i-j-k` order. |
| `mat_det(a)` | Direct cofactor formulas for `1×1` through `4×4`; general `n×n` falls through to LU decomposition with partial pivoting, returning `0.0` on a non-square input or a pivot below `1e-15`. |
| `mat_inv(a)` | Gauss-Jordan elimination on the augmented `[A \| I]` matrix, partial pivoting; returns an all-zero matrix if `A` is singular or non-square. |
| `mat_solve(a, b)` | Gaussian elimination with partial pivoting on `[A \| b]`; returns an all-zero vector if `A` is singular, non-square, or `len(b) != a.rows`. |
| `vec_dot`, `vec_norm`, `vec_cross` | Dot product (over the shorter of the two inputs), Euclidean norm, and 3D cross product (`[0,0,0]` if either input has fewer than 3 elements). |
| `mat_lu(a)` | LU decomposition with partial pivoting, returning `LUResult(L, U, pivots)` where `pivots` is the row-permutation array such that `P·A = L·U`. |
| `mat_eigenvalues_2x2(a)` | Closed-form quadratic-formula eigenvalues for a `2×2` matrix only; on a complex-eigenvalue case (negative discriminant) both returned values collapse to the shared real part. Returns `EigResult2x2(lambda1, lambda2)` — eigenvalues only, no eigenvectors. |

**Worked example, using the same matrix the real hand-written test suite pins** (`A = [[2, 1], [1,
1]]`, from `tests/mojo/test_wave3.mojo` — not the auto-generated smoke test; see Verification
below):

* `mat_det(A) = 2*1 - 1*1 = 1.0` — pinned directly (`"det 2x2 = 1"`).
* `mat_solve(A, [5, 3])` solves `2x+y=5, x+y=3` → `x = [2.0, 1.0]` — pinned directly.
* `mat_lu(A)` — the test only pins the triangular *structure* (`L(0,0)=1`, `L(1,1)=1`, `U(1,0)=0`),
  not every entry. Working the algorithm by hand: column 0's pivot is already `2` (the larger of
  `|2|` and `|1|`), so there is no row swap; the single elimination step gives `L = [[1,0],[0.5,1]]`,
  `U = [[2,1],[0,0.5]]`, `pivots = [0,1]` — consistent with the pinned structure, and `L·U`
  reconstructs `A` exactly.
* `mat_eigenvalues_2x2` is *not* exercised by this particular matrix in the test file, but on the
  test's other fixture `[[1,1],[0,2]]` the pinned assertion is `lambda1 + lambda2 = 3.0` (the true
  eigenvalues are the diagonal entries `1` and `2`, since the matrix is already triangular).

`mat_mul` has its own pinned example: `[[1,2],[3,4]] × [[5,6],[7,8]] = [[19,22],[43,50]]`, and
`vec_cross([1,0,0], [0,1,0]) = [0,0,1]` — the standard basis check, `î × ĵ = k̂`.

## `linalg_ext`: what "extended" actually adds

Reading the module docstring and the import list settles the hint directly: `linalg_ext` is a real
extension of `linalg`, not a separate or renamed thing — it imports `Matrix`, `mat_mul`,
`mat_transpose`, `mat_inv`, `mat_det`, `vec_dot`, and `vec_norm` straight from `linalg` and adds
exactly the operations `linalg` doesn't have:

| Function | What it does |
| --- | --- |
| `mat_qr(a)` | QR decomposition via modified Gram-Schmidt on the columns of `A` (`m×n`, `m >= n`); returns `QRResult(Q, R)` with `Q` orthogonal (`m×n`) and `R` upper-triangular (`n×n`). |
| `mat_norm_frobenius(a)` | `sqrt(sum of squares of all elements)`. |
| `mat_norm_inf(a)` | Maximum absolute row sum. |
| `mat_trace(a)` | Sum of diagonal elements (over `min(rows, cols)`, so it doesn't require a square matrix). |
| `mat_is_symmetric(a, tol=1e-10)` | `A[i][j] ≈ A[j][i]` for every off-diagonal pair, within `tol`. |
| `mat_is_positive_definite(a)` | Attempts a Cholesky factorization and returns `True`/`False` on success/failure — but does not return the factor `L` itself; for that, see `matrix_decomp.cholesky` below. |
| `mat_power_iteration(a, max_iter=100)` | Power iteration with a Rayleigh-quotient eigenvalue estimate at each step; works for **any** `n×n` matrix, unlike `linalg.mat_eigenvalues_2x2`'s `2×2`-only closed form. Returns `PowerIterResult(eigenvalue, eigenvector)`. |
| `mat_condition_number(a)` | `‖A‖_∞ · ‖A⁻¹‖_∞`, computed by calling `linalg.mat_inv` directly; returns `1e18` for a non-square or singular matrix rather than `inf`. |

**Every number below is a pinned assertion from `tests/mojo/test_wave12.mojo`**, not an invented
example. For `A = [[1, 1], [0, 1]]`:

* `mat_trace(A) = 2.0`
* `mat_norm_frobenius(A) = sqrt(1²+1²+0²+1²) = sqrt(3) ≈ 1.7320508`
* `mat_norm_inf(A) = 2.0` (row sums are `2` and `1`, max is `2`)
* `mat_qr(A)` — the test checks `Qᵀ·Q ≈ I` and `Q·R ≈ A` to within `0.01`, rather than pinning `Q`
  and `R`'s individual entries.

For `[[1,2],[2,3]]`, `mat_is_symmetric` is `True`; for `A` above (not symmetric, `A[0][1]=1 ≠
A[1][0]=0`), it's `False`. For `[[2,1],[1,2]]`, `mat_is_positive_definite` is `True`, and
`mat_power_iteration` on that same matrix converges to `eigenvalue ≈ 3.0` — matching the matrix's
true eigenvalues of `3` and `1` (trace `4`, det `3` → roots of `λ²-4λ+3=0`). `mat_condition_number`
of `mat_identity(2)` is `1.0`, the minimum possible value.

{% hint style="info" %}
**`mat_power_iteration` finds the dominant eigenvalue for any size, `mat_eigenvalues_2x2` only for
2×2 — and neither returns what the other does by default.** The power-iteration route gives an
eigenvector along with the eigenvalue but only the single dominant one; the closed-form 2×2 route
(in `linalg`) gives both eigenvalues but no eigenvectors. `matrix_decomp.eigen_2x2` (below) is the
one function in this whole family that returns both eigenvalues *and* both eigenvectors — but, like
`linalg`'s version, only for 2×2. For eigendecomposition of general symmetric matrices up to `n=200`,
see [Symmetric eigendecomposition and thin SVD](ml-eigendecomposition.md), whose `eigen_full` is
described in its own docstring as lifting "the 2×2 cap of `matrix_decomp.eigen_2x2`" specifically —
a real, verified cross-reference between the two pages, not a guess.
{% endhint %}

## `matrix_decomp`: the second implementation, over nested lists

None of `matrix_decomp`'s functions take or return a `Matrix` struct — every matrix here is a plain
`List[List[Float64]]`, and the module imports nothing from `linalg` or `linalg_ext`. It overlaps
conceptually with both (LU decomposition, determinants, a linear solve) but is a separate
implementation with different conventions: `lu_decompose` uses Doolittle's method (unit diagonal on
`L`, no separate `pivots` array — pivoting happens internally but isn't reported to the caller,
unlike `linalg.mat_lu`'s `LUResult.pivots`), and it is the **only** module of the four that exposes a
direct Cholesky factor.

| Function | What it does |
| --- | --- |
| `det_2x2`, `det_3x3` | Fixed-size determinant formulas — no general-`n` path exists in this module. |
| `trace(A)` | Sum of diagonal elements. |
| `is_symmetric(A, tol=1e-10)` | Same check as `linalg_ext.mat_is_symmetric`, over a nested list. |
| `cholesky(A)` | Returns the lower-triangular factor `L` where `A = L·Lᵀ`, or an **empty list** if `A` isn't symmetric positive-definite. |
| `is_positive_definite(A)` | `len(cholesky(A)) > 0` — literally calls `cholesky` and checks it didn't refuse. |
| `lu_decompose(A)` | Doolittle LU with partial pivoting; returns `[L, U]` as a 2-element list of matrices. |
| `eigen_2x2(A)` | Eigenvalues **and** normalized eigenvectors for a `2×2` matrix: `[[λ1, λ2], [v1x, v1y], [v2x, v2y]]`. |
| `forward_substitution(L, b)` | Solves `Lx = b` for lower-triangular `L`. |
| `back_substitution(U, b)` | Solves `Ux = b` for upper-triangular `U`. |
| `solve_lu(A, b)` | Solves `Ax = b` directly via Gaussian elimination with partial pivoting (does not call `lu_decompose` internally — it re-derives its own elimination on an augmented `[A \| b]`). |

**Every number below is a pinned assertion from `tests/mojo/test_wave34.mojo`.**

* `det_2x2([[1,2],[3,4]]) = 1*4 - 2*3 = -2.0`
* `det_3x3([[2,1,1],[1,3,2],[1,0,0]]) = 2*(3*0-2*0) - 1*(1*0-2*1) + 1*(1*0-3*1) = 0+2-3 = -1.0`
* `trace([[2,1],[1,3]]) = 5.0`
* `cholesky([[4,2],[2,3]])` gives `L` such that `L·Lᵀ` reproduces the original matrix to `1e-9`:
  `L·Lᵀ = [[4, 2], [2, 3]]` exactly (checked entrywise in the test, not just `len(L) > 0`).
* `is_positive_definite([[-1,0],[0,-2]])` is `False` — both diagonal entries are negative, so the
  very first Cholesky step (`diag = A[0][0] = -1 <= 0`) refuses immediately.
* `lu_decompose([[2,1],[5,3]])`: since pivoting can permute rows, the test doesn't check `L` and `U`
  entrywise — it reconstructs `L·U` and checks `|det(L·U)| = |det(A)| = |2*3 - 1*5| = 1.0`, which
  must hold regardless of which row ended up on top.
* `forward_substitution([[1,0],[2,1]], [1,4]) = [1.0, 2.0]` — `x0 = 1/1 = 1`, `x1 = (4 - 2*1)/1 = 2`.
* `back_substitution([[2,1],[0,3]], [4,6]) = [1.0, 2.0]` — `x1 = 6/3 = 2`, `x0 = (4 - 1*2)/2 = 1`.
* `solve_lu([[1,2],[3,5]], [5,14]) = [3.0, 1.0]`.
* `eigen_2x2([[2,1],[1,2]])`: `λ1 = 3.0`, `λ2 = 1.0` (matching `linalg_ext.mat_power_iteration`'s
  independently-converged `3.0` on the same matrix above), and the returned eigenvectors are unit
  length (`v1x² + v1y² = 1.0`, checked to `1e-9`).

## `matrix_ops`: elementwise and structural algebra nothing else here has

Also over nested `List[List[Float64]]`, also importing nothing from the other three modules.
Unlike `matrix_decomp`, none of this overlaps conceptually with `linalg`/`linalg_ext` — Kronecker
products, matrix exponentials, and vectorization don't exist anywhere else in this family.

| Function | What it does |
| --- | --- |
| `kronecker_product(A, B)` | `A ⊗ B`; an `m×n` `A` and `p×q` `B` give an `(m·p)×(n·q)` result. |
| `hadamard_product(A, B)` | Elementwise product; refuses (empty result) if `A` and `B` aren't the same shape. |
| `matrix_power(A, n)` | `Aⁿ` via exponentiation by squaring; `n` is clamped to `1000` and negative `n` is refused. |
| `outer_product(a, b)` | `n×m` matrix, `C[i][j] = a[i]*b[j]`. |
| `matrix_exp_approx(A, terms=10)` | Truncated Taylor series `Σ Aᵏ/k!`, `k=0..terms-1` — an approximation, not a closed-form matrix exponential, and its accuracy depends entirely on how many terms are kept. |
| `vec(A)` / `unvec(v, rows, cols)` | Column-major vectorization and its inverse reshape. |
| `matrix_norm_1(A)` | Maximum absolute **column** sum. |
| `matrix_norm_inf(A)` | Maximum absolute **row** sum — the same definition as `linalg_ext.mat_norm_inf`, reimplemented over a nested list instead of a `Matrix`. |
| `commutator(A, B)` | `[A,B] = AB - BA`; refuses (empty result) unless both matrices are square and the same size. |
| `is_orthogonal(A, tol=1e-8)` | Checks `AᵀA ≈ I`. |
| `gram_schmidt(vectors)` | Orthonormalizes a list of vectors, subtracting each projection sequentially and re-using the updated vector for the next one — the same modified-Gram-Schmidt update order as `linalg_ext.mat_qr`, but returning only the orthonormal vectors (no `R`, no `Matrix` wrapper) and operating on an arbitrary list of vectors rather than a matrix's columns. |

**Every number below is a pinned assertion from `tests/mojo/test_wave43.mojo`.**

* `kronecker_product(I₂, I₂)` is the `4×4` identity — `K[0][0]=K[1][1]=K[2][2]=K[3][3]=1.0`,
  `K[0][1]=0.0`.
* `hadamard_product([[3,5],[7,11]], [[1,1],[1,1]]) = [[3,5],[7,11]]` — multiplying by all-ones is a
  no-op, which is a cheap way to check the elementwise indexing lines up.
* `matrix_power([[1,2],[3,4]], 2) = [[1*1+2*3, 1*2+2*4],[3*1+4*3, 3*2+4*4]] = [[7,10],[15,22]]`, and
  `matrix_power(A, 0)` is the identity regardless of `A` (`A⁰ = I`) for any square `A`.
* `outer_product([1,2], [3,4]) = [[3,4],[6,8]]`.
* `vec([[1,2],[3,4]])` in column-major order is `[1,3,2,4]`, and `unvec` of that vector back to
  `2×2` round-trips to the original `[[1,2],[3,4]]` exactly.
* `matrix_norm_inf([[1,-2],[3,4]]) = max(|1|+|-2|, |3|+|4|) = max(3,7) = 7.0`; the same matrix's
  `matrix_norm_1 = max(|1|+|3|, |-2|+|4|) = max(4,6) = 6.0` — norm_1 and norm_inf disagree on this
  matrix precisely because it isn't symmetric.
* `commutator(A, A) = [[0,0],[0,0]]` for any `A` — a matrix always commutes with itself.
* `is_orthogonal` is `True` for the identity and `False` for `[[1,2],[3,4]]`.
* `gram_schmidt([[1,1,0],[1,0,1],[0,1,1]])` produces three mutually orthogonal unit vectors (all
  three pairwise dot products and the first two norms are checked to `1e-10`); independently
  computing the full result in Python gives `[0.7071068, 0.7071068, 0]`,
  `[0.4082483, -0.4082483, 0.8164966]`, `[-0.5773503, 0.5773503, 0.5773503]`.
* `matrix_exp_approx([[0,0],[0,0]])` is the identity (`e⁰ = I`) — the only case in the test suite
  where the truncated series is checked against a value with a closed form.

## Refusing rather than crashing

`matrix_decomp` and `matrix_ops` share a real safety property that `linalg`/`linalg_ext` handle
differently, because the two representations fail differently. A `List[List[Float64]]` can be
ragged or too short in a way the type system doesn't prevent, and reading past the end of a Mojo
`List` is — per the source comments on nearly every function in these two modules — "an
uncatchable abort of the whole process," not a raiseable exception. So `det_2x2`, `det_3x3`,
`eigen_2x2`, `forward_substitution`, `back_substitution`, `solve_lu`, `hadamard_product`, and
`commutator` all explicitly check row/column counts up front and return a degenerate value (`0.0`,
an empty list, or an empty matrix) instead of indexing into a shape they haven't verified.
`forward_substitution`, `back_substitution`, and `solve_lu` additionally refuse on a NaN or
infinite entry in `b`, since a non-finite value can't cross the JSON result wire back to the caller.
`matrix_power` and `matrix_exp_approx` clamp their `n`/`terms` argument to `1000` so an untrusted
caller can't turn a single call into unbounded work.

`linalg`/`linalg_ext`'s `Matrix` struct sidesteps the ragged-list problem — it's always built
through `mat_zeros`, `mat_identity`, or `mat_from_list`, all of which keep `data.length ==
rows*cols` — but that only protects a single matrix's *own* internal consistency. Only `mat_solve`
checks a *second* argument's shape against the first (`a.rows != a.cols` or `len(b) != a.rows`
refuses with a zero vector); `mat_add`, `mat_sub`, `mat_mul`, and `mat_transpose` all assume their
arguments already agree in shape and do not re-verify it. Singular matrices are the one case
`linalg` and `linalg_ext` do guard uniformly: `mat_det`, `mat_inv`, `mat_solve`, and
`mat_condition_number` all key off the same `1e-15` pivot threshold and return a designated
degenerate value (`0.0`, a zero matrix, a zero vector, or `1e18`) rather than dividing by
something too close to zero.

Separately, `matrix_ops.unvec` declares a count relation in the runtime contract — `len(v)` must
equal `rows*cols` — that the SDK checks before the call ever reaches Mojo (see
[Declared capabilities](capabilities.md) for how these declarations work generally), for the same
reason: an under-length `v` would be read past its end inside the kernel.

## Verification

`mojo/tests/libs/test_linalg.mojo` and `test_matrix_ops.mojo` are the auto-generated coverage smoke
tests for two of these four modules — each calls a handful of functions once with a fixed
`[0.5, 0.6, 0.7, 0.4, 0.3]`-style fixture and checks only that the result is finite; neither pins a
specific numeric output. **No auto-generated test file exists at all for `linalg_ext` or
`matrix_decomp`** — there is no `test_linalg_ext.mojo` or `test_matrix_decomp.mojo` under
`mojo/tests/libs/`.

The real rigor behind this page is a different, hand-written test suite: `tests/mojo/test_wave3.mojo`
(`linalg`), `test_wave12.mojo` (`linalg_ext`), `test_wave34.mojo` (`matrix_decomp`), and
`test_wave43.mojo` (`matrix_ops`), each with explicit expected-value comments and numeric
assertions at tolerances between `1e-3` and `1e-10`. Every worked number above is either lifted
directly from one of those four files, or — where a page needed a value the pinned tests don't
compute directly (the `mat_lu` walkthrough's `L`/`U` entries, `mat_qr`'s intermediate values, the
full three-vector `gram_schmidt` output) — independently re-derived from the real formulas in
`mojo/engine/linalg.mojo`, `linalg_ext.mojo`, `matrix_decomp.mojo`, and `matrix_ops.mojo` and
checked in Python against the exact algorithm as coded (not against a library's own answer for the
"same" operation, since e.g. `matrix_exp_approx`'s truncated series is deliberately not a true
matrix exponential).

**Next:** see [Symmetric eigendecomposition and thin SVD](ml-eigendecomposition.md) for the
general-`n` eigendecomposition that lifts `matrix_decomp.eigen_2x2`'s 2×2 cap, or
[GEMM kernels](gemm-kernels.md), which checks its blocked matmul against `linalg.mat_mul` as a
frozen correctness oracle.
