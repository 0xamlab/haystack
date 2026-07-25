---
icon: cubes
description: Jacobi symmetric eigendecomposition and thin SVD for full-rank spectral computation.
---

# Symmetric eigendecomposition and thin SVD

`eigen_full` computes full eigendecompositions of symmetric N×N matrices
and thin SVDs of tall matrices in pure Mojo, with zero Python imports —
replacing `numpy.linalg.eigh` and `numpy.linalg.svd` (thin, tall case).
It lifts the 2×2 cap of `matrix_decomp.eigen_2x2` to symmetric n ≤ 200
using the cyclic Jacobi rotation method.

## Functions

| Function | What it does |
|---|---|
| `eigh_symmetric(A, n, max_sweeps, tol)` | Eigenvalues (sorted descending) + orthonormal eigenvectors of a symmetric n×n matrix (flat row-major). Sweeps of Givens rotations run until the off-diagonal Frobenius norm falls to `tol · ‖A‖_F`. Returns `EighResult` (eigenvalues, eigenvectors, sweeps, converged). |
| `svd_via_eigh(A, rows, cols, max_sweeps, tol)` | Thin SVD `A = U · diag(σ) · V^T` of a tall matrix (rows ≥ cols) via eigendecomposition of the Gram matrix `A^T A`. Returns `SVDResult` (u, singular_values, v, converged). |

## Guarantees and conventions

- **Fully deterministic** — no randomness anywhere. Eigenvector sign is
  fixed by making the largest-magnitude component of each vector positive.
- Eigenvalues and singular values are sorted descending; eigenvector /
  singular-vector k is the k-th **column** of the flat row-major matrix.
- Input is symmetrized as `(A + A^T) / 2` before decomposition, mirroring
  `numpy.linalg.eigh` reading one triangle.
- Invalid input (n ≤ 0, n > 200, wrong flat length, or rows < cols for
  the SVD) returns an empty, unconverged result rather than trapping.
- Complexity is O(n³) per Jacobi sweep (typically 5–10 sweeps):
  sub-millisecond up to roughly n ≈ 40, tens of milliseconds at the
  n = 200 cap — the cap is the design envelope and bounds worst-case latency.
- SVD accuracy note: forming `A^T A` squares the condition number, so tiny
  singular values are accurate to about sqrt(machine eps) relative — fine
  for regression/PCA-style use. Columns of U whose σ ≤ max σ · 1e-12 are
  left zero (numerical null space).

## Verification

The test suite pins hand-computed known values rather than snapshots:

- 2×2 `[[2,1],[1,2]]` recovers eigenvalues 3, 1 and eigenvectors
  (1,1)/√2, (1,−1)/√2 to 1e-10.
- A 3×3 constructed as `Q · diag(5, 2, −1) · Q^T` from a hand-chosen
  orthogonal Q recovers the eigenvalues and the exact Q columns to 1e-8,
  with eigenvector Gram deviation and reconstruction `‖A − V D V^T‖`
  both below 1e-8.
- The ill-conditioned 6×6 Hilbert matrix converges with orthonormality
  and reconstruction error below 1e-8.
- SVD: the 3×2 case recovers σ = √3 (1.7320508075688772), 1; the
  rank-deficient `[[1,2],[2,4],[3,6]]` gives σ = √70 (8.366600265340756), 0
  with the null U column exactly zero; reconstruction `‖A − U Σ V^T‖`
  stays below 1e-8 throughout.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
