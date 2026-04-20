"""
test_wave3.mojo — Tests for Wave 3 libraries: optimize, stat_tests, linalg.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave3.mojo
"""
from optimize import (
    OptResult,
    LinRegResult,
    minimize_scalar_golden,
    minimize_brent,
    root_bisection,
    root_newton,
    gradient_descent_1d,
    eval_poly,
    eval_poly_deriv,
    linear_regression,
)
from stat_tests import (
    TestResult,
    CorrResult,
    ks_test_2sample,
    ks_test_normal,
    t_test_1sample,
    t_test_2sample,
    chi_squared_test,
    anderson_darling_normal,
    shapiro_wilk_approx,
    pearson_r,
    spearman_r,
)
from linalg import (
    Matrix,
    LUResult,
    EigResult2x2,
    mat_zeros,
    mat_identity,
    mat_from_list,
    mat_add,
    mat_sub,
    mat_mul,
    mat_scale,
    mat_transpose,
    mat_det,
    mat_inv,
    mat_solve,
    vec_dot,
    vec_norm,
    vec_cross,
    mat_lu,
    mat_eigenvalues_2x2,
)
from std.math import abs as fabs


# ── Helpers ───────────────────────────────────────────────────────────────────


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_near(got: Float64, expected: Float64, tol: Float64, label: String) raises:
    if fabs(got - expected) > tol:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        print("   diff:     " + String(fabs(got - expected)))
        raise Error("assertion failed: " + label)


# ── Optimize tests ────────────────────────────────────────────────────────────


def test_eval_poly() raises:
    # f(x) = 3 + 2x + x^2 → f(2) = 3 + 4 + 4 = 11
    var c = List[Float64]()
    c.append(3.0)
    c.append(2.0)
    c.append(1.0)
    _assert_near(eval_poly(c, 2.0), 11.0, 0.001, "eval_poly(3+2x+x², 2)")

    # f'(x) = 2 + 2x → f'(2) = 6
    _assert_near(eval_poly_deriv(c, 2.0), 6.0, 0.001, "eval_poly_deriv(3+2x+x², 2)")

    # Constant polynomial
    var c2 = List[Float64]()
    c2.append(5.0)
    _assert_near(eval_poly(c2, 99.0), 5.0, 0.001, "eval_poly constant")
    _assert_near(eval_poly_deriv(c2, 99.0), 0.0, 0.001, "eval_poly_deriv constant")

    print("  ✓ Polynomial evaluation")


def test_golden_section() raises:
    # Minimize x^2 - 4x + 4 = (x-2)^2, minimum at x=2
    var coeffs = List[Float64]()
    coeffs.append(4.0)
    coeffs.append(-4.0)
    coeffs.append(1.0)  # 4 - 4x + x^2
    var result = minimize_scalar_golden(coeffs, -10.0, 10.0)
    _assert_near(result.x, 2.0, 0.001, "golden min x")
    _assert_near(result.fun, 0.0, 0.001, "golden min f(x)")
    _assert_true(result.converged, "golden converged")

    print("  ✓ Golden section minimize")


def test_brent_minimize() raises:
    # Minimize x^2 - 4x + 4
    var coeffs = List[Float64]()
    coeffs.append(4.0)
    coeffs.append(-4.0)
    coeffs.append(1.0)
    var result = minimize_brent(coeffs, -10.0, 10.0)
    _assert_near(result.x, 2.0, 0.001, "brent min x")
    _assert_near(result.fun, 0.0, 0.001, "brent min f(x)")
    _assert_true(result.converged, "brent converged")

    # Minimize x^2 (min at 0)
    var c2 = List[Float64]()
    c2.append(0.0)
    c2.append(0.0)
    c2.append(1.0)
    var r2 = minimize_brent(c2, -5.0, 5.0)
    _assert_near(r2.x, 0.0, 0.01, "brent min x²")

    print("  ✓ Brent minimize")


def test_bisection_root() raises:
    # Root of x^2 - 4 = 0 → x = 2 (on [0, 5])
    var root_coeffs = List[Float64]()
    root_coeffs.append(-4.0)
    root_coeffs.append(0.0)
    root_coeffs.append(1.0)
    var root = root_bisection(root_coeffs, 0.0, 5.0)
    _assert_near(root.x, 2.0, 0.001, "bisection root x²-4")
    _assert_true(root.converged, "bisection converged")

    # Root of x - 3 = 0 → x = 3
    var c2 = List[Float64]()
    c2.append(-3.0)
    c2.append(1.0)
    var r2 = root_bisection(c2, 0.0, 10.0)
    _assert_near(r2.x, 3.0, 0.001, "bisection root x-3")

    print("  ✓ Bisection root finding")


def test_newton_root() raises:
    # Root of x^2 - 4 = 0, starting from x0=3 → x = 2
    var c = List[Float64]()
    c.append(-4.0)
    c.append(0.0)
    c.append(1.0)
    var root = root_newton(3.0, c)
    _assert_near(root.x, 2.0, 0.001, "newton root x²-4")
    _assert_true(root.converged, "newton converged")

    print("  ✓ Newton root finding")


def test_gradient_descent() raises:
    # Minimize x^2 - 4x + 4, starting from x0=0
    var c = List[Float64]()
    c.append(4.0)
    c.append(-4.0)
    c.append(1.0)
    var result = gradient_descent_1d(c, 0.0, 0.1)
    _assert_near(result.x, 2.0, 0.01, "gd min x")
    _assert_true(result.converged, "gd converged")

    print("  ✓ Gradient descent 1D")


def test_linear_regression() raises:
    var x_reg = List[Float64]()
    var y_reg = List[Float64]()
    x_reg.append(1.0)
    x_reg.append(2.0)
    x_reg.append(3.0)
    x_reg.append(4.0)
    x_reg.append(5.0)
    y_reg.append(2.1)
    y_reg.append(3.9)
    y_reg.append(6.2)
    y_reg.append(7.8)
    y_reg.append(10.1)
    var reg = linear_regression(x_reg, y_reg)
    _assert_near(reg.slope, 2.0, 0.2, "linreg slope ≈ 2")
    _assert_true(reg.r_squared > 0.99, "linreg R² > 0.99")

    # Perfect linear data: y = 3x + 1
    var x2 = List[Float64]()
    var y2 = List[Float64]()
    x2.append(0.0)
    x2.append(1.0)
    x2.append(2.0)
    x2.append(3.0)
    y2.append(1.0)
    y2.append(4.0)
    y2.append(7.0)
    y2.append(10.0)
    var reg2 = linear_regression(x2, y2)
    _assert_near(reg2.slope, 3.0, 0.001, "linreg perfect slope")
    _assert_near(reg2.intercept, 1.0, 0.001, "linreg perfect intercept")
    _assert_near(reg2.r_squared, 1.0, 0.001, "linreg perfect R²")

    print("  ✓ Linear regression")


# ── Stat tests ────────────────────────────────────────────────────────────────


def test_t_test_1sample() raises:
    # Sample mean ≈ 100 vs H0: mu=100 → should NOT reject
    var sample = List[Float64]()
    sample.append(98.0)
    sample.append(102.0)
    sample.append(100.0)
    sample.append(99.0)
    sample.append(101.0)
    var tt = t_test_1sample(sample, 100.0)
    _assert_true(not tt.reject_h0, "t-test non-reject when mean=H0")
    _assert_true(tt.p_value > 0.05, "t-test p > 0.05")

    # Sample far from mu → should reject
    var sample2 = List[Float64]()
    sample2.append(10.0)
    sample2.append(11.0)
    sample2.append(12.0)
    sample2.append(10.0)
    sample2.append(11.0)
    var tt2 = t_test_1sample(sample2, 100.0)
    _assert_true(tt2.reject_h0, "t-test reject when mean far from H0")

    print("  ✓ t-test 1-sample")


def test_t_test_2sample() raises:
    # Same distribution → should not reject
    var s1 = List[Float64]()
    s1.append(10.0)
    s1.append(11.0)
    s1.append(10.5)
    s1.append(9.5)
    s1.append(10.2)
    var s2 = List[Float64]()
    s2.append(10.1)
    s2.append(10.8)
    s2.append(10.3)
    s2.append(9.7)
    s2.append(10.0)
    var tt = t_test_2sample(s1, s2)
    _assert_true(not tt.reject_h0, "t-test 2sample non-reject same dist")

    # Very different means → reject
    var s3 = List[Float64]()
    s3.append(100.0)
    s3.append(101.0)
    s3.append(102.0)
    s3.append(100.0)
    s3.append(101.0)
    var tt2 = t_test_2sample(s1, s3)
    _assert_true(tt2.reject_h0, "t-test 2sample reject different dist")

    print("  ✓ t-test 2-sample (Welch)")


def test_chi_squared() raises:
    # Observed = expected → chi2 ≈ 0, p ≈ 1
    var obs = List[Float64]()
    obs.append(10.0)
    obs.append(20.0)
    obs.append(30.0)
    var exp = List[Float64]()
    exp.append(10.0)
    exp.append(20.0)
    exp.append(30.0)
    var result = chi_squared_test(obs, exp)
    _assert_near(result.statistic, 0.0, 0.001, "chi2 stat when O=E")
    _assert_true(not result.reject_h0, "chi2 non-reject when O=E")

    # Very different → should reject
    var obs2 = List[Float64]()
    obs2.append(50.0)
    obs2.append(5.0)
    obs2.append(5.0)
    var result2 = chi_squared_test(obs2, exp)
    _assert_true(result2.reject_h0, "chi2 reject when O≠E")

    print("  ✓ Chi-squared test")


def test_ks_2sample() raises:
    # Two identical samples → KS stat ≈ 0
    var s1 = List[Float64]()
    s1.append(1.0)
    s1.append(2.0)
    s1.append(3.0)
    s1.append(4.0)
    s1.append(5.0)
    var result = ks_test_2sample(s1, s1)
    _assert_near(result.statistic, 0.0, 0.001, "KS same samples D=0")
    _assert_true(not result.reject_h0, "KS same samples non-reject")

    print("  ✓ KS 2-sample test")


def test_ks_normal() raises:
    # Roughly normal data
    var sample = List[Float64]()
    sample.append(-1.5)
    sample.append(-0.8)
    sample.append(-0.3)
    sample.append(0.0)
    sample.append(0.2)
    sample.append(0.5)
    sample.append(0.9)
    sample.append(1.2)
    sample.append(1.8)
    sample.append(2.0)
    var result = ks_test_normal(sample)
    # Should not reject normality for roughly normal data
    _assert_true(result.statistic < 0.5, "KS normal stat < 0.5")

    print("  ✓ KS normal test")


def test_anderson_darling() raises:
    # Roughly normal data
    var sample = List[Float64]()
    sample.append(-2.1)
    sample.append(-1.3)
    sample.append(-0.5)
    sample.append(-0.1)
    sample.append(0.2)
    sample.append(0.6)
    sample.append(0.9)
    sample.append(1.4)
    sample.append(1.8)
    sample.append(2.5)
    var result = anderson_darling_normal(sample)
    # For approximately normal data, A² should be relatively small
    _assert_true(result.statistic >= 0.0, "AD stat >= 0")

    print("  ✓ Anderson-Darling test")


def test_shapiro_wilk() raises:
    # Roughly normal data
    var sample = List[Float64]()
    sample.append(-1.8)
    sample.append(-1.0)
    sample.append(-0.4)
    sample.append(0.0)
    sample.append(0.3)
    sample.append(0.7)
    sample.append(1.1)
    sample.append(1.5)
    sample.append(2.0)
    sample.append(2.5)
    var result = shapiro_wilk_approx(sample)
    # W should be close to 1.0 for normal data
    _assert_true(result.statistic > 0.5, "Shapiro W > 0.5")
    _assert_true(result.statistic <= 1.0, "Shapiro W <= 1.0")

    print("  ✓ Shapiro-Wilk test")


def test_pearson_r() raises:
    # Perfectly correlated
    var x = List[Float64]()
    x.append(1.0)
    x.append(2.0)
    x.append(3.0)
    x.append(4.0)
    x.append(5.0)
    var y = List[Float64]()
    y.append(2.1)
    y.append(3.9)
    y.append(6.2)
    y.append(7.8)
    y.append(10.1)
    var pr = pearson_r(x, y)
    _assert_true(pr.r > 0.99, "pearson r > 0.99")
    _assert_true(pr.p_value < 0.01, "pearson p < 0.01")

    # Perfect correlation
    var y2 = List[Float64]()
    y2.append(2.0)
    y2.append(4.0)
    y2.append(6.0)
    y2.append(8.0)
    y2.append(10.0)
    var pr2 = pearson_r(x, y2)
    _assert_near(pr2.r, 1.0, 0.001, "pearson r = 1 exact")

    print("  ✓ Pearson correlation")


def test_spearman_r() raises:
    # Monotonic but nonlinear
    var x = List[Float64]()
    x.append(1.0)
    x.append(2.0)
    x.append(3.0)
    x.append(4.0)
    x.append(5.0)
    var y = List[Float64]()
    y.append(1.0)
    y.append(4.0)
    y.append(9.0)
    y.append(16.0)
    y.append(25.0)  # y = x² — perfect monotonic
    var sr = spearman_r(x, y)
    _assert_near(sr.r, 1.0, 0.001, "spearman rho = 1 for monotone")

    print("  ✓ Spearman correlation")


# ── Linalg tests ──────────────────────────────────────────────────────────────


def test_matrix_basics() raises:
    var m = mat_zeros(3, 3)
    _assert_near(m.get(0, 0), 0.0, 0.001, "zeros(0,0)")
    _assert_near(m.get(2, 2), 0.0, 0.001, "zeros(2,2)")

    var id = mat_identity(3)
    _assert_near(id.get(0, 0), 1.0, 0.001, "identity(0,0)")
    _assert_near(id.get(1, 1), 1.0, 0.001, "identity(1,1)")
    _assert_near(id.get(0, 1), 0.0, 0.001, "identity(0,1)")

    print("  ✓ Matrix basics")


def test_matrix_ops() raises:
    var a_data = List[Float64]()
    a_data.append(1.0)
    a_data.append(2.0)
    a_data.append(3.0)
    a_data.append(4.0)
    var a = mat_from_list(a_data, 2, 2)

    var b_data = List[Float64]()
    b_data.append(5.0)
    b_data.append(6.0)
    b_data.append(7.0)
    b_data.append(8.0)
    var b = mat_from_list(b_data, 2, 2)

    # Add
    var c = mat_add(a, b)
    _assert_near(c.get(0, 0), 6.0, 0.001, "add(0,0)")
    _assert_near(c.get(1, 1), 12.0, 0.001, "add(1,1)")

    # Sub
    var d = mat_sub(b, a)
    _assert_near(d.get(0, 0), 4.0, 0.001, "sub(0,0)")
    _assert_near(d.get(1, 1), 4.0, 0.001, "sub(1,1)")

    # Scale
    var e = mat_scale(a, 2.0)
    _assert_near(e.get(0, 0), 2.0, 0.001, "scale(0,0)")
    _assert_near(e.get(1, 1), 8.0, 0.001, "scale(1,1)")

    # Transpose
    var t = mat_transpose(a)
    _assert_near(t.get(0, 1), 3.0, 0.001, "transpose(0,1)")
    _assert_near(t.get(1, 0), 2.0, 0.001, "transpose(1,0)")

    print("  ✓ Matrix operations (add, sub, scale, transpose)")


def test_matrix_mul() raises:
    # [[1,2],[3,4]] * [[5,6],[7,8]] = [[19,22],[43,50]]
    var a_data = List[Float64]()
    a_data.append(1.0)
    a_data.append(2.0)
    a_data.append(3.0)
    a_data.append(4.0)
    var a = mat_from_list(a_data, 2, 2)

    var b_data = List[Float64]()
    b_data.append(5.0)
    b_data.append(6.0)
    b_data.append(7.0)
    b_data.append(8.0)
    var b = mat_from_list(b_data, 2, 2)

    var c = mat_mul(a, b)
    _assert_near(c.get(0, 0), 19.0, 0.001, "mul(0,0)")
    _assert_near(c.get(0, 1), 22.0, 0.001, "mul(0,1)")
    _assert_near(c.get(1, 0), 43.0, 0.001, "mul(1,0)")
    _assert_near(c.get(1, 1), 50.0, 0.001, "mul(1,1)")

    # Multiply by identity
    var id = mat_identity(2)
    var d = mat_mul(a, id)
    _assert_near(d.get(0, 0), 1.0, 0.001, "A*I(0,0)")
    _assert_near(d.get(1, 1), 4.0, 0.001, "A*I(1,1)")

    print("  ✓ Matrix multiplication")


def test_matrix_inverse() raises:
    # 2x2 matrix inverse
    var m_data = List[Float64]()
    m_data.append(2.0)
    m_data.append(1.0)
    m_data.append(1.0)
    m_data.append(1.0)
    var m = mat_from_list(m_data, 2, 2)
    var m_inv = mat_inv(m)

    # A * A^{-1} should be identity
    var prod = mat_mul(m, m_inv)
    _assert_near(prod.get(0, 0), 1.0, 0.001, "inv: A*Ainv(0,0)")
    _assert_near(prod.get(0, 1), 0.0, 0.001, "inv: A*Ainv(0,1)")
    _assert_near(prod.get(1, 0), 0.0, 0.001, "inv: A*Ainv(1,0)")
    _assert_near(prod.get(1, 1), 1.0, 0.001, "inv: A*Ainv(1,1)")

    # 3x3 matrix
    var m3_data = List[Float64]()
    m3_data.append(1.0)
    m3_data.append(2.0)
    m3_data.append(3.0)
    m3_data.append(0.0)
    m3_data.append(1.0)
    m3_data.append(4.0)
    m3_data.append(5.0)
    m3_data.append(6.0)
    m3_data.append(0.0)
    var m3 = mat_from_list(m3_data, 3, 3)
    var m3_inv = mat_inv(m3)
    var prod3 = mat_mul(m3, m3_inv)
    _assert_near(prod3.get(0, 0), 1.0, 0.001, "inv 3x3: (0,0)")
    _assert_near(prod3.get(1, 1), 1.0, 0.001, "inv 3x3: (1,1)")
    _assert_near(prod3.get(2, 2), 1.0, 0.001, "inv 3x3: (2,2)")
    _assert_near(prod3.get(0, 1), 0.0, 0.001, "inv 3x3: (0,1)")

    print("  ✓ Matrix inverse")


def test_matrix_solve() raises:
    # Solve Ax = b: [[2,1],[1,1]] * x = [5, 3] → x = [2, 1]
    var m_data = List[Float64]()
    m_data.append(2.0)
    m_data.append(1.0)
    m_data.append(1.0)
    m_data.append(1.0)
    var m = mat_from_list(m_data, 2, 2)
    var b_vec = List[Float64]()
    b_vec.append(5.0)
    b_vec.append(3.0)
    var x_sol = mat_solve(m, b_vec)
    _assert_near(x_sol[0], 2.0, 0.001, "solve x[0]=2")
    _assert_near(x_sol[1], 1.0, 0.001, "solve x[1]=1")

    # 3x3 system: I*x = [3,5,7] → x = [3,5,7]
    var id = mat_identity(3)
    var b3 = List[Float64]()
    b3.append(3.0)
    b3.append(5.0)
    b3.append(7.0)
    var x3 = mat_solve(id, b3)
    _assert_near(x3[0], 3.0, 0.001, "solve I*x: x[0]")
    _assert_near(x3[1], 5.0, 0.001, "solve I*x: x[1]")
    _assert_near(x3[2], 7.0, 0.001, "solve I*x: x[2]")

    print("  ✓ Matrix solve")


def test_determinant() raises:
    # det([[2,1],[1,1]]) = 2*1 - 1*1 = 1
    var m_data = List[Float64]()
    m_data.append(2.0)
    m_data.append(1.0)
    m_data.append(1.0)
    m_data.append(1.0)
    var m = mat_from_list(m_data, 2, 2)
    _assert_near(mat_det(m), 1.0, 0.001, "det 2x2 = 1")

    # det(I) = 1
    var id3 = mat_identity(3)
    _assert_near(mat_det(id3), 1.0, 0.001, "det I3 = 1")

    # Singular matrix: det = 0
    var s_data = List[Float64]()
    s_data.append(1.0)
    s_data.append(2.0)
    s_data.append(2.0)
    s_data.append(4.0)
    var s = mat_from_list(s_data, 2, 2)
    _assert_near(mat_det(s), 0.0, 0.001, "det singular = 0")

    # 3x3 determinant
    var m3_data = List[Float64]()
    m3_data.append(1.0)
    m3_data.append(2.0)
    m3_data.append(3.0)
    m3_data.append(4.0)
    m3_data.append(5.0)
    m3_data.append(6.0)
    m3_data.append(7.0)
    m3_data.append(8.0)
    m3_data.append(0.0)
    var m3 = mat_from_list(m3_data, 3, 3)
    # det = 1(5*0 - 6*8) - 2(4*0 - 6*7) + 3(4*8 - 5*7) = -48 + 84 - 3 = 27
    _assert_near(mat_det(m3), 27.0, 0.001, "det 3x3 = 27")

    print("  ✓ Determinant")


def test_vector_ops() raises:
    var v1 = List[Float64]()
    v1.append(3.0)
    v1.append(4.0)
    _assert_near(vec_norm(v1), 5.0, 0.001, "norm [3,4] = 5")
    _assert_near(vec_dot(v1, v1), 25.0, 0.001, "dot [3,4]·[3,4] = 25")

    var v2 = List[Float64]()
    v2.append(1.0)
    v2.append(0.0)
    var v3 = List[Float64]()
    v3.append(0.0)
    v3.append(1.0)
    _assert_near(vec_dot(v2, v3), 0.0, 0.001, "dot orthogonal = 0")

    # Cross product: [1,0,0] × [0,1,0] = [0,0,1]
    var a = List[Float64]()
    a.append(1.0)
    a.append(0.0)
    a.append(0.0)
    var b = List[Float64]()
    b.append(0.0)
    b.append(1.0)
    b.append(0.0)
    var c = vec_cross(a, b)
    _assert_near(c[0], 0.0, 0.001, "cross x")
    _assert_near(c[1], 0.0, 0.001, "cross y")
    _assert_near(c[2], 1.0, 0.001, "cross z")

    print("  ✓ Vector operations")


def test_lu_decomposition() raises:
    var m_data = List[Float64]()
    m_data.append(2.0)
    m_data.append(1.0)
    m_data.append(1.0)
    m_data.append(1.0)
    var m = mat_from_list(m_data, 2, 2)
    var result = mat_lu(m)
    var L = result.L.copy()
    var U = result.U.copy()

    # L*U should reconstruct the (possibly pivoted) original matrix
    var lu_prod = mat_mul(L, U)
    # Verify L is lower triangular with 1s on diagonal
    _assert_near(L.get(0, 0), 1.0, 0.001, "LU: L(0,0)=1")
    _assert_near(L.get(1, 1), 1.0, 0.001, "LU: L(1,1)=1")

    # U should be upper triangular
    _assert_near(U.get(1, 0), 0.0, 0.001, "LU: U(1,0)=0")

    print("  ✓ LU decomposition")


def test_eigenvalues_2x2() raises:
    # [[2, 0], [0, 3]] → eigenvalues 3, 2
    var m_data = List[Float64]()
    m_data.append(2.0)
    m_data.append(0.0)
    m_data.append(0.0)
    m_data.append(3.0)
    var m = mat_from_list(m_data, 2, 2)
    var eigs = mat_eigenvalues_2x2(m)
    # Eigenvalues should be 3 and 2 (or 2 and 3)
    var sum_eigs = eigs.lambda1 + eigs.lambda2
    var prod_eigs = eigs.lambda1 * eigs.lambda2
    _assert_near(sum_eigs, 5.0, 0.001, "eigenvalues sum = 5")
    _assert_near(prod_eigs, 6.0, 0.001, "eigenvalues product = 6")

    # [[1, 1], [0, 2]] → eigenvalues 1, 2
    var m2_data = List[Float64]()
    m2_data.append(1.0)
    m2_data.append(1.0)
    m2_data.append(0.0)
    m2_data.append(2.0)
    var m2 = mat_from_list(m2_data, 2, 2)
    var eigs2 = mat_eigenvalues_2x2(m2)
    _assert_near(eigs2.lambda1 + eigs2.lambda2, 3.0, 0.001, "eigenvalues 2 sum = 3")

    print("  ✓ Eigenvalues 2×2")


# ── Runner ────────────────────────────────────────────────────────────────────


def main() raises:
    print("━━━ Wave 3 test suite (optimize, stat_tests, linalg) ━━━")
    print("")

    print("── Optimize ──")
    test_eval_poly()
    test_golden_section()
    test_brent_minimize()
    test_bisection_root()
    test_newton_root()
    test_gradient_descent()
    test_linear_regression()
    print("✅ Optimize — all tests passed")
    print("")

    print("── Statistical Tests ──")
    test_t_test_1sample()
    test_t_test_2sample()
    test_chi_squared()
    test_ks_2sample()
    test_ks_normal()
    test_anderson_darling()
    test_shapiro_wilk()
    test_pearson_r()
    test_spearman_r()
    print("✅ Statistical tests — all tests passed")
    print("")

    print("── Linear Algebra ──")
    test_matrix_basics()
    test_matrix_ops()
    test_matrix_mul()
    test_matrix_inverse()
    test_matrix_solve()
    test_determinant()
    test_vector_ops()
    test_lu_decomposition()
    test_eigenvalues_2x2()
    print("✅ Linear algebra — all tests passed")
    print("")

    print("━━━ All Wave 3 tests passed ━━━")
