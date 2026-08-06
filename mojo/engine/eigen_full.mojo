"""
eigen_full.mojo — Full symmetric eigendecomposition via cyclic Jacobi. Zero Python imports.

Replaces numpy.linalg.eigh and numpy.linalg.svd (thin, tall case) with pure
Mojo. Lifts the 2×2 cap of matrix_decomp.eigen_2x2 to symmetric N×N
(n ≤ 200) using the cyclic Jacobi rotation method, and provides thin SVD of
tall matrices through the A^T A eigendecomposition.

Complexity: eigh_symmetric is O(n^3) per sweep (typically 5–10 sweeps);
sub-millisecond up to roughly n ≈ 40, tens of milliseconds at the n = 200
cap — intrinsic to dense eigendecomposition, and the cap prevents accidental
multi-second stalls. svd_via_eigh adds O(rows · cols^2) to form A^T A.

Public API:
  eigh_symmetric  — eigenvalues (sorted desc) + orthonormal eigenvectors of symmetric A
  svd_via_eigh    — thin SVD (U, singular values, V) of tall A via eigh of A^T A
  EighResult      — eigenvalues, eigenvectors (flat row-major), sweeps, converged
  SVDResult       — u, singular_values, v (flat row-major), converged
"""
from std.math import sqrt, abs as fabs


# ── result structs ───────────────────────────────────────────────────────────


struct EighResult(Copyable, Movable):
    """Symmetric eigendecomposition A = V · diag(eigenvalues) · V^T.

    eigenvalues: sorted descending, length n.
    eigenvectors: the n×n orthonormal matrix V stored flat row-major
      (element (i, j) at index i * n + j). Eigenvector k — paired with
      eigenvalues[k] — is the k-th COLUMN of V. Sign convention: the
      largest-magnitude component of each eigenvector is made positive.
    sweeps: Jacobi sweeps performed. converged: off-diagonal norm reached
      tol · ||A||_F within max_sweeps. Empty lists signal invalid input.
    """

    var eigenvalues: List[Float64]
    var eigenvectors: List[Float64]
    var sweeps: Int
    var converged: Bool

    def __init__(out self):
        self.eigenvalues = List[Float64]()
        self.eigenvectors = List[Float64]()
        self.sweeps = 0
        self.converged = False


struct SVDResult(Copyable, Movable):
    """Thin SVD A = U · diag(singular_values) · V^T for tall A (rows ≥ cols).

    u: rows×cols flat row-major; column k is the k-th left singular vector.
    singular_values: length cols, sorted descending, all ≥ 0.
    v: cols×cols flat row-major; column k is the k-th right singular vector.
    Columns of u whose singular value is ≤ max_sv · 1e-12 are left as zeros
    (near-null directions), so u is column-orthonormal only over the
    numerical rank. Empty lists signal invalid input.
    """

    var u: List[Float64]
    var singular_values: List[Float64]
    var v: List[Float64]
    var converged: Bool

    def __init__(out self):
        self.u = List[Float64]()
        self.singular_values = List[Float64]()
        self.v = List[Float64]()
        self.converged = False


# ── helpers ──────────────────────────────────────────────────────────────────


def _fro_norm(S: List[Float64]) -> Float64:
    """Frobenius norm of a flat matrix."""
    var s: Float64 = 0.0
    for i in range(len(S)):
        s += S[i] * S[i]
    return sqrt(s)


def _off_diag_norm(S: List[Float64], n: Int) -> Float64:
    """Frobenius norm of the off-diagonal part of symmetric flat S."""
    var s: Float64 = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            var v = S[i * n + j]
            s += 2.0 * v * v
    return sqrt(s)


# ── eigh_symmetric ───────────────────────────────────────────────────────────


def eigh_symmetric(
    A: List[Float64], n: Int, max_sweeps: Int = 50, tol: Float64 = 1e-12
) -> EighResult:
    """Full eigendecomposition of a symmetric n×n matrix via cyclic Jacobi.

    A is flat row-major (length n * n) and is symmetrized as (A + A^T) / 2
    before decomposition (exact for symmetric input; mirrors numpy.linalg.eigh
    reading one triangle). Sweeps of Givens rotations annihilate each
    off-diagonal (p, q) pair until the off-diagonal Frobenius norm falls to
    tol · ||A||_F or max_sweeps is exhausted (non-positive max_sweeps/tol fall
    back to 50 / 1e-12). Eigenvalues are returned sorted descending with
    eigenvector columns permuted to match. Invalid input (n ≤ 0, n > 200, or
    len(A) != n * n) returns an empty, unconverged result; the n ≤ 200 cap is
    the design envelope and keeps worst-case latency bounded.
    """
    var out = EighResult()
    if n <= 0 or n > 200 or len(A) != n * n:
        return out^

    # Symmetrized working copy.
    var S = List[Float64](capacity=n * n)
    for i in range(n):
        for j in range(n):
            S.append(0.5 * (A[i * n + j] + A[j * n + i]))

    # Accumulated rotations: V starts as identity.
    var V = List[Float64](capacity=n * n)
    for i in range(n):
        for j in range(n):
            V.append(1.0 if i == j else 0.0)

    var eff_tol = tol
    if eff_tol <= 0.0:
        eff_tol = 1e-12
    var sweeps_cap = max_sweeps
    if sweeps_cap <= 0:
        sweeps_cap = 50

    var fro = _fro_norm(S)
    var target = eff_tol * fro
    var converged = fro == 0.0 or _off_diag_norm(S, n) <= target
    var sweeps_used = 0
    while not converged and sweeps_used < sweeps_cap:
        for p in range(n - 1):
            for q in range(p + 1, n):
                var apq = S[p * n + q]
                if apq == 0.0:
                    continue
                var app = S[p * n + p]
                var aqq = S[q * n + q]
                var tau = (aqq - app) / (2.0 * apq)
                # Stable smaller-root tangent; if tau overflows, t -> 0 and
                # the rotation degenerates to zeroing a negligible a_pq.
                var t: Float64
                if tau >= 0.0:
                    t = 1.0 / (tau + sqrt(1.0 + tau * tau))
                else:
                    t = -1.0 / (-tau + sqrt(1.0 + tau * tau))
                var c = 1.0 / sqrt(1.0 + t * t)
                var s = t * c
                S[p * n + p] = app - t * apq
                S[q * n + q] = aqq + t * apq
                S[p * n + q] = 0.0
                S[q * n + p] = 0.0
                for i in range(n):
                    if i == p or i == q:
                        continue
                    var aip = S[i * n + p]
                    var aiq = S[i * n + q]
                    S[i * n + p] = c * aip - s * aiq
                    S[p * n + i] = S[i * n + p]
                    S[i * n + q] = s * aip + c * aiq
                    S[q * n + i] = S[i * n + q]
                for i in range(n):
                    var vip = V[i * n + p]
                    var viq = V[i * n + q]
                    V[i * n + p] = c * vip - s * viq
                    V[i * n + q] = s * vip + c * viq
        sweeps_used += 1
        converged = _off_diag_norm(S, n) <= target

    # Sort eigenvalues descending (selection sort on an index permutation;
    # n <= 200 so O(n^2) is negligible) and carry eigenvector columns along.
    var order = List[Int](capacity=n)
    for i in range(n):
        order.append(i)
    for a in range(n - 1):
        var best = a
        for b in range(a + 1, n):
            if S[order[b] * n + order[b]] > S[order[best] * n + order[best]]:
                best = b
        if best != a:
            var tmp = order[a]
            order[a] = order[best]
            order[best] = tmp

    var evals = List[Float64](capacity=n)
    for k in range(n):
        evals.append(S[order[k] * n + order[k]])

    var evecs = List[Float64](capacity=n * n)
    for _ in range(n * n):
        evecs.append(0.0)
    for k in range(n):
        var src = order[k]
        # Deterministic sign: first largest-|component| entry made positive.
        var imax = 0
        var vmax = fabs(V[src])
        for i in range(1, n):
            var av = fabs(V[i * n + src])
            if av > vmax:
                vmax = av
                imax = i
        var flip = V[imax * n + src] < 0.0
        for i in range(n):
            var val = V[i * n + src]
            if flip:
                val = -val
            evecs[i * n + k] = val

    out.eigenvalues = evals^
    out.eigenvectors = evecs^
    out.sweeps = sweeps_used
    out.converged = converged
    return out^


# ── svd_via_eigh ─────────────────────────────────────────────────────────────


def svd_via_eigh(
    A: List[Float64],
    rows: Int,
    cols: Int,
    max_sweeps: Int = 50,
    tol: Float64 = 1e-12,
) -> SVDResult:
    """Thin SVD of a tall matrix A (rows ≥ cols) via eigh of A^T A.

    A is flat row-major (length rows * cols). Forms the symmetric PSD
    cols×cols Gram matrix B = A^T A, eigendecomposes it (eigenvalues are
    squared singular values, eigenvectors are right singular vectors V),
    then recovers left singular vectors as u_k = A v_k / sigma_k. Singular
    values are sorted descending; sigma_k ≤ max_sigma · 1e-12 leaves u
    column k as zeros (numerical null space). Note: squaring the condition
    number in A^T A limits accuracy of tiny singular values to about
    sqrt(machine eps) relative — fine for regression/PCA-style use.
    Invalid input (rows < cols, non-positive dims, cols > 200, or
    len(A) != rows * cols) returns an empty, unconverged result.
    """
    var out = SVDResult()
    if rows <= 0 or cols <= 0 or rows < cols or cols > 200:
        return out^
    if len(A) != rows * cols:
        return out^

    # B = A^T A (symmetric — compute upper triangle, mirror).
    var B = List[Float64](capacity=cols * cols)
    for _ in range(cols * cols):
        B.append(0.0)
    for j in range(cols):
        for k in range(j, cols):
            var s: Float64 = 0.0
            for i in range(rows):
                s += A[i * cols + j] * A[i * cols + k]
            B[j * cols + k] = s
            B[k * cols + j] = s

    var eig = eigh_symmetric(B, cols, max_sweeps, tol)
    if len(eig.eigenvalues) == 0:
        return out^

    var sv = List[Float64](capacity=cols)
    for k in range(cols):
        var lam = eig.eigenvalues[k]
        if lam < 0.0:
            lam = 0.0
        sv.append(sqrt(lam))

    var rank_tol = sv[0] * 1e-12  # sv is descending, so sv[0] is max.
    var U = List[Float64](capacity=rows * cols)
    for _ in range(rows * cols):
        U.append(0.0)
    for k in range(cols):
        if sv[k] <= rank_tol or sv[k] == 0.0:
            continue  # near-null direction: column stays zero
        for i in range(rows):
            var s: Float64 = 0.0
            for j in range(cols):
                s += A[i * cols + j] * eig.eigenvectors[j * cols + k]
            U[i * cols + k] = s / sv[k]

    out.u = U^
    out.singular_values = sv^
    out.v = eig.eigenvectors.copy()
    out.converged = eig.converged
    return out^
