"""test_eigen_full.mojo — hand-computed known-value tests for eigen_full."""
from std.math import sqrt, abs as fabs
from eigen_full import eigh_symmetric, svd_via_eigh


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅", name)
    else:
        failed += 1
        print("  ❌", name)


fn approx(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


fn _dot_col(V: List[Float64], n: Int, k: Int, q: List[Float64]) -> Float64:
    """Dot product of column k of flat n×n V with vector q."""
    var s: Float64 = 0.0
    for i in range(n):
        s += V[i * n + k] * q[i]
    return s


fn _gram_max_dev(M: List[Float64], rows: Int, cols: Int) -> Float64:
    """max |M^T M - I| over the cols×cols Gram matrix (column orthonormality)."""
    var worst: Float64 = 0.0
    for a in range(cols):
        for b in range(cols):
            var s: Float64 = 0.0
            for i in range(rows):
                s += M[i * cols + a] * M[i * cols + b]
            var target: Float64 = 1.0 if a == b else 0.0
            var d = fabs(s - target)
            if d > worst:
                worst = d
    return worst


fn _recon_max_dev(
    A: List[Float64], evals: List[Float64], V: List[Float64], n: Int
) -> Float64:
    """max |A - V diag(evals) V^T| elementwise."""
    var worst: Float64 = 0.0
    for i in range(n):
        for j in range(n):
            var s: Float64 = 0.0
            for k in range(n):
                s += V[i * n + k] * evals[k] * V[j * n + k]
            var d = fabs(s - A[i * n + j])
            if d > worst:
                worst = d
    return worst


fn _svd_recon_max_dev(
    A: List[Float64],
    U: List[Float64],
    sv: List[Float64],
    V: List[Float64],
    rows: Int,
    cols: Int,
) -> Float64:
    """max |A - U diag(sv) V^T| elementwise."""
    var worst: Float64 = 0.0
    for i in range(rows):
        for j in range(cols):
            var s: Float64 = 0.0
            for k in range(cols):
                s += U[i * cols + k] * sv[k] * V[j * cols + k]
            var d = fabs(s - A[i * cols + j])
            if d > worst:
                worst = d
    return worst


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── eigh_symmetric: 1x1 ──────────────────────────────────────────────
    var a1 = List[Float64]()
    a1.append(7.0)
    var r1 = eigh_symmetric(a1, 1)
    check(
        len(r1.eigenvalues) == 1
        and approx(r1.eigenvalues[0], 7.0, 1e-12)
        and approx(r1.eigenvectors[0], 1.0, 1e-12)
        and r1.converged,
        "eigen_full::eigh_symmetric 1x1 exact",
        passed,
        failed,
    )

    # ── eigh_symmetric: 2x2 [[2,1],[1,2]] -> eigenvalues 3, 1 ────────────
    # Hand-computed: char poly l^2 - 4l + 3 = 0 -> l = 3, 1;
    # v(3) = (1,1)/sqrt2, v(1) = (1,-1)/sqrt2.
    var a2 = List[Float64]()
    a2.append(2.0)
    a2.append(1.0)
    a2.append(1.0)
    a2.append(2.0)
    var r2 = eigh_symmetric(a2, 2)
    check(
        approx(r2.eigenvalues[0], 3.0, 1e-10)
        and approx(r2.eigenvalues[1], 1.0, 1e-10),
        "eigen_full::eigh_symmetric 2x2 known eigenvalues 3,1",
        passed,
        failed,
    )
    var e2a = List[Float64]()
    e2a.append(0.7071067811865476)
    e2a.append(0.7071067811865476)
    var e2b = List[Float64]()
    e2b.append(0.7071067811865476)
    e2b.append(-0.7071067811865476)
    check(
        approx(fabs(_dot_col(r2.eigenvectors, 2, 0, e2a)), 1.0, 1e-10)
        and approx(fabs(_dot_col(r2.eigenvectors, 2, 1, e2b)), 1.0, 1e-10),
        "eigen_full::eigh_symmetric 2x2 known eigenvectors (1,1)/sqrt2 & (1,-1)/sqrt2",
        passed,
        failed,
    )

    # ── eigh_symmetric: 3x3 constructed as Q D Q^T ───────────────────────
    # Hand-chosen orthogonal Q columns: q1=(2,1,2)/3, q2=(-2,2,1)/3,
    # q3=(1,2,-2)/3; D = diag(5, 2, -1). Hand-multiplied:
    # A = Q D Q^T = [[3,0,2],[0,1,2],[2,2,2]]
    # (check: trace 6 = 5+2-1, det -10 = 5*2*(-1)).
    var a3 = List[Float64]()
    a3.append(3.0)
    a3.append(0.0)
    a3.append(2.0)
    a3.append(0.0)
    a3.append(1.0)
    a3.append(2.0)
    a3.append(2.0)
    a3.append(2.0)
    a3.append(2.0)
    var r3 = eigh_symmetric(a3, 3)
    check(
        r3.converged
        and approx(r3.eigenvalues[0], 5.0, 1e-8)
        and approx(r3.eigenvalues[1], 2.0, 1e-8)
        and approx(r3.eigenvalues[2], -1.0, 1e-8),
        "eigen_full::eigh_symmetric 3x3 QDQ^T eigenvalues 5,2,-1 within 1e-8",
        passed,
        failed,
    )
    var q1 = List[Float64]()
    q1.append(2.0 / 3.0)
    q1.append(1.0 / 3.0)
    q1.append(2.0 / 3.0)
    var q2 = List[Float64]()
    q2.append(-2.0 / 3.0)
    q2.append(2.0 / 3.0)
    q2.append(1.0 / 3.0)
    var q3 = List[Float64]()
    q3.append(1.0 / 3.0)
    q3.append(2.0 / 3.0)
    q3.append(-2.0 / 3.0)
    check(
        approx(fabs(_dot_col(r3.eigenvectors, 3, 0, q1)), 1.0, 1e-8)
        and approx(fabs(_dot_col(r3.eigenvectors, 3, 1, q2)), 1.0, 1e-8)
        and approx(fabs(_dot_col(r3.eigenvectors, 3, 2, q3)), 1.0, 1e-8),
        "eigen_full::eigh_symmetric 3x3 QDQ^T eigenvectors recover Q columns",
        passed,
        failed,
    )
    check(
        _gram_max_dev(r3.eigenvectors, 3, 3) < 1e-8,
        "eigen_full::eigh_symmetric 3x3 eigenvectors orthonormal (Gram ~ I)",
        passed,
        failed,
    )
    check(
        _recon_max_dev(a3, r3.eigenvalues, r3.eigenvectors, 3) < 1e-8,
        "eigen_full::eigh_symmetric 3x3 reconstruction ||A - V D V^T|| < 1e-8",
        passed,
        failed,
    )

    # ── eigh_symmetric: ties (4·I) and zero matrix ───────────────────────
    var a4 = List[Float64]()
    for i in range(3):
        for j in range(3):
            a4.append(4.0 if i == j else 0.0)
    var r4 = eigh_symmetric(a4, 3)
    check(
        r4.converged
        and approx(r4.eigenvalues[0], 4.0, 1e-12)
        and approx(r4.eigenvalues[1], 4.0, 1e-12)
        and approx(r4.eigenvalues[2], 4.0, 1e-12)
        and _gram_max_dev(r4.eigenvectors, 3, 3) < 1e-12
        and _recon_max_dev(a4, r4.eigenvalues, r4.eigenvectors, 3) < 1e-12,
        "eigen_full::eigh_symmetric all-equal eigenvalues (4I) exact",
        passed,
        failed,
    )
    var a5 = List[Float64]()
    for _ in range(9):
        a5.append(0.0)
    var r5 = eigh_symmetric(a5, 3)
    var zero_ok = r5.converged
    for k in range(3):
        if r5.eigenvalues[k] != 0.0:
            zero_ok = False
    for i in range(3):
        for j in range(3):
            var want: Float64 = 1.0 if i == j else 0.0
            if r5.eigenvectors[i * 3 + j] != want:
                zero_ok = False
    check(
        zero_ok,
        "eigen_full::eigh_symmetric zero matrix -> zero eigenvalues, V = I",
        passed,
        failed,
    )

    # ── eigh_symmetric: 6x6 Hilbert matrix (ill-conditioned SPD) ─────────
    var h6 = List[Float64]()
    for i in range(6):
        for j in range(6):
            h6.append(1.0 / Float64(i + j + 1))
    var r6 = eigh_symmetric(h6, 6)
    var sorted_ok = True
    for k in range(5):
        if r6.eigenvalues[k] < r6.eigenvalues[k + 1] - 1e-12:
            sorted_ok = False
    check(
        r6.converged and sorted_ok,
        "eigen_full::eigh_symmetric 6x6 Hilbert converged, eigenvalues sorted desc",
        passed,
        failed,
    )
    check(
        _gram_max_dev(r6.eigenvectors, 6, 6) < 1e-8
        and _recon_max_dev(h6, r6.eigenvalues, r6.eigenvectors, 6) < 1e-8,
        "eigen_full::eigh_symmetric 6x6 Hilbert orthonormal + reconstruction < 1e-8",
        passed,
        failed,
    )

    # ── eigh_symmetric: invalid inputs ───────────────────────────────────
    var empty = List[Float64]()
    var r7 = eigh_symmetric(empty, 0)
    var bad_len = List[Float64]()
    bad_len.append(1.0)
    bad_len.append(2.0)
    bad_len.append(3.0)
    var r8 = eigh_symmetric(bad_len, 2)
    var big = List[Float64]()
    for _ in range(201 * 201):
        big.append(0.0)
    var r9 = eigh_symmetric(big, 201)
    check(
        len(r7.eigenvalues) == 0
        and not r7.converged
        and len(r8.eigenvalues) == 0
        and len(r9.eigenvalues) == 0,
        "eigen_full::eigh_symmetric invalid input (n=0, wrong len, n>200) -> empty",
        passed,
        failed,
    )

    # ── svd_via_eigh: 3x2 with known singular values ─────────────────────
    # A = [[1,1],[0,1],[1,0]]; A^T A = [[2,1],[1,2]] -> eigenvalues 3,1
    # -> singular values sqrt(3), 1 (hand-computed).
    var m1 = List[Float64]()
    m1.append(1.0)
    m1.append(1.0)
    m1.append(0.0)
    m1.append(1.0)
    m1.append(1.0)
    m1.append(0.0)
    var s1 = svd_via_eigh(m1, 3, 2)
    check(
        s1.converged
        and approx(s1.singular_values[0], 1.7320508075688772, 1e-8)
        and approx(s1.singular_values[1], 1.0, 1e-8),
        "eigen_full::svd_via_eigh 3x2 singular values sqrt(3), 1",
        passed,
        failed,
    )
    check(
        _gram_max_dev(s1.u, 3, 2) < 1e-8 and _gram_max_dev(s1.v, 2, 2) < 1e-8,
        "eigen_full::svd_via_eigh 3x2 U and V column-orthonormal",
        passed,
        failed,
    )
    check(
        _svd_recon_max_dev(m1, s1.u, s1.singular_values, s1.v, 3, 2) < 1e-8,
        "eigen_full::svd_via_eigh 3x2 reconstruction ||A - U S V^T|| < 1e-8",
        passed,
        failed,
    )

    # ── svd_via_eigh: rank-deficient 3x2 ─────────────────────────────────
    # A = [[1,2],[2,4],[3,6]] (col2 = 2*col1): A^T A = [[14,28],[28,56]],
    # eigenvalues 70, 0 -> singular values sqrt(70), 0.
    var m2 = List[Float64]()
    m2.append(1.0)
    m2.append(2.0)
    m2.append(2.0)
    m2.append(4.0)
    m2.append(3.0)
    m2.append(6.0)
    var s2 = svd_via_eigh(m2, 3, 2)
    var null_col_zero = True
    for i in range(3):
        if s2.u[i * 2 + 1] != 0.0:
            null_col_zero = False
    check(
        approx(s2.singular_values[0], 8.366600265340756, 1e-8)
        and s2.singular_values[1] <= 1e-7
        and null_col_zero
        and _svd_recon_max_dev(m2, s2.u, s2.singular_values, s2.v, 3, 2) < 1e-8,
        "eigen_full::svd_via_eigh rank-deficient: sigma = sqrt(70), 0; null U column zero",
        passed,
        failed,
    )

    # ── svd_via_eigh: square identity + invalid wide input ───────────────
    var m3 = List[Float64]()
    m3.append(1.0)
    m3.append(0.0)
    m3.append(0.0)
    m3.append(1.0)
    var s3 = svd_via_eigh(m3, 2, 2)
    check(
        approx(s3.singular_values[0], 1.0, 1e-12)
        and approx(s3.singular_values[1], 1.0, 1e-12)
        and _svd_recon_max_dev(m3, s3.u, s3.singular_values, s3.v, 2, 2) < 1e-12,
        "eigen_full::svd_via_eigh 2x2 identity: sigma = 1, 1; exact reconstruction",
        passed,
        failed,
    )
    var m4 = List[Float64]()
    for _ in range(6):
        m4.append(1.0)
    var s4 = svd_via_eigh(m4, 2, 3)
    check(
        len(s4.singular_values) == 0 and not s4.converged,
        "eigen_full::svd_via_eigh wide matrix (rows < cols) -> empty result",
        passed,
        failed,
    )

    print("  [eigen_full] Passed:", passed, "Failed:", failed)
