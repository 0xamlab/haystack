"""
sparse_numerics — compressed sparse layouts. Zero Python.

What the tree has today, and why it is not enough
-------------------------------------------------
`sparse.mojo` is the only sparse matrix type in the repo:
`SparseMatrixCOO{entries: List[COOEntry], nrows, ncols}`. It is a triplet *builder*,
and a deliberately permissive one:

* entries keep insertion order — nothing is sorted
* duplicate `(row, col)` pairs are legal and are *summed* at materialisation, because
  `to_dense` accumulates with `+=`
* `nnz()` is `len(entries)`, so it counts duplicates and explicitly stored zeros
* nothing anywhere coalesces or canonicalises

Those are the right invariants for assembly (a finite-element or graph-Laplacian
assembly emits the same coordinate many times on purpose) and the wrong ones for
arithmetic. Every operation on COO is O(nnz) with a scatter, there is no way to ask
for "row i" without scanning every entry, and two matrices that denote the same
linear map can have different entry lists — so no operation on COO can be compared
for equality, deduplicated or cached.

There is no CSR, no CSC, no row-pointer array, no coalesce, no sort-indices and no
sparse factorisation anywhere in the tree. This package adds the compressed layouts
alongside COO; `sparse.mojo` is frozen and unchanged, and stays the assembly front
door. `csr.csr_from_coo` is the bridge, and it is defined to agree with `to_dense`
exactly — duplicates sum — so moving to the compressed layout can never change a
number.

Modules:
  csr  — CSRMatrix / CSCMatrix, construction, validation, transpose, coalesce,
         row and column slicing, and the flat-list drivers
  diagnostics — one health report plus focused predicates: density, extrema, row and
         column norms, diagonal magnitude, symmetry defect, empty rows and columns,
         non-finite positions, and a condition-number estimate that reports its
         failures as statuses instead of as 1e18
  spmv — the products: A^T y without building A^T, a row against a sparse vector,
         A * B, A + B, scale, Frobenius norm, and a compensated A @ x
  iterative — Krylov solvers: CG and preconditioned CG (Jacobi, symmetric
         Gauss-Seidel), CGLS for least squares and the nonsymmetric case, and
         restarted GMRES. Every solver reports a status plus separate `converged` and
         `breakdown` flags, so an iterate that hit the iteration cap, an indefinite
         matrix and a singular system are all distinguishable from a solution — which
         they are not in `linalg.mat_solve`, whose singular answer is a zero vector
  factor — direct solves: LU with the permutation and a real singular flag, guarded
         triangular substitution, an announced dense fallback, least squares, and
         a residual on every answer

Public functions take and return only `List`/`Int`/`Float64`/`Bool`/`String` or a
return-only struct, so the package lands in the runtime library contract without a
new message type. It is therefore *not* in `_SKIP_RUNTIME_DIRS`.
"""
