"""
test_wave12.mojo — Tests for Wave 12 libraries: Integration, QR Decomposition, Validation.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave12.mojo
"""
from integrate import (
    trapezoid,
    simpson,
    romberg,
    cumulative_trapezoid,
    integrate_poly,
    quad_gauss_legendre,
)
from linalg import (
    Matrix,
    mat_from_list,
    mat_mul,
    mat_transpose,
    mat_zeros,
    mat_identity,
)
from linalg_ext import (
    QRResult,
    PowerIterResult,
    mat_qr,
    mat_norm_frobenius,
    mat_norm_inf,
    mat_trace,
    mat_is_symmetric,
    mat_is_positive_definite,
    mat_power_iteration,
    mat_condition_number,
)
from validate import (
    is_valid_email,
    is_valid_ip4,
    is_valid_number,
    is_valid_json,
    is_in_range,
    is_positive,
    is_finite,
    clamp,
    sanitize_string,
    validate_array_bounds,
    check_monotonic,
)
from std.math import abs as fabs
from testing import assert_true


def main() raises:
    print("━━━ Wave 12 test suite (Integration, QR, Validation) ━━━")
    print("")

    # ── Integration ──────────────────────────────────────────────────────
    # Integral of y=x^2 from 0 to 1 = 1/3
    var y = List[Float64]()
    for i in range(101):
        var x = Float64(i) / 100.0
        y.append(x * x)
    var trap = trapezoid(y, 0.01)
    assert_true(
        fabs(trap - 1.0 / 3.0) < 0.001,
        "trapezoid(x^2, 0..1) should be ~1/3, got " + String(trap),
    )
    var simp = simpson(y, 0.01)
    assert_true(
        fabs(simp - 1.0 / 3.0) < 0.0001,
        "simpson(x^2, 0..1) should be ~1/3 (more accurate), got " + String(simp),
    )

    # Cumulative trapezoid
    var cum = cumulative_trapezoid(y, 0.01)
    assert_true(
        len(cum) == 100,
        "cumulative_trapezoid should return 100 values, got " + String(len(cum)),
    )
    # Last cumulative value should be close to 1/3
    assert_true(
        fabs(cum[99] - 1.0 / 3.0) < 0.001,
        "cumulative_trapezoid last value should be ~1/3, got " + String(cum[99]),
    )

    # Polynomial integral: x^2 from 0 to 1 exactly
    var coeffs = List[Float64]()
    coeffs.append(0.0)
    coeffs.append(0.0)
    coeffs.append(1.0)
    var poly_int = integrate_poly(coeffs, 0.0, 1.0)
    assert_true(
        fabs(poly_int - 1.0 / 3.0) < 0.0001,
        "integrate_poly(x^2, 0..1) should be 1/3, got " + String(poly_int),
    )

    # Gauss-Legendre on equally-spaced data
    var gl = quad_gauss_legendre(y, 0.0, 1.0)
    assert_true(
        fabs(gl - 1.0 / 3.0) < 0.01,
        "quad_gauss_legendre(x^2, 0..1) should be ~1/3, got " + String(gl),
    )

    print("✅ Numerical integration")

    # ── QR Decomposition ─────────────────────────────────────────────────
    # Q should be orthogonal, R upper triangular, Q*R = A
    var a_data = List[Float64]()
    a_data.append(1.0)
    a_data.append(1.0)
    a_data.append(0.0)
    a_data.append(1.0)
    var a = mat_from_list(a_data, 2, 2)
    var qr = mat_qr(a)
    var q = qr.Q.copy()
    var r = qr.R.copy()

    # Q^T * Q should be identity
    var qtq = mat_mul(mat_transpose(q), q)
    assert_true(
        fabs(qtq.get(0, 0) - 1.0) < 0.01,
        "Q^T*Q (0,0) should be 1, got " + String(qtq.get(0, 0)),
    )
    assert_true(
        fabs(qtq.get(1, 1) - 1.0) < 0.01,
        "Q^T*Q (1,1) should be 1, got " + String(qtq.get(1, 1)),
    )
    assert_true(
        fabs(qtq.get(0, 1)) < 0.01,
        "Q^T*Q (0,1) should be 0, got " + String(qtq.get(0, 1)),
    )

    # Q*R should reconstruct A
    var qr_product = mat_mul(q, r)
    assert_true(
        fabs(qr_product.get(0, 0) - 1.0) < 0.01,
        "Q*R (0,0) should be 1, got " + String(qr_product.get(0, 0)),
    )
    assert_true(
        fabs(qr_product.get(0, 1) - 1.0) < 0.01,
        "Q*R (0,1) should be 1, got " + String(qr_product.get(0, 1)),
    )
    assert_true(
        fabs(qr_product.get(1, 0)) < 0.01,
        "Q*R (1,0) should be 0, got " + String(qr_product.get(1, 0)),
    )
    assert_true(
        fabs(qr_product.get(1, 1) - 1.0) < 0.01,
        "Q*R (1,1) should be 1, got " + String(qr_product.get(1, 1)),
    )

    # Trace
    assert_true(
        fabs(mat_trace(a) - 2.0) < 0.001,
        "trace([[1,1],[0,1]]) should be 2, got " + String(mat_trace(a)),
    )

    # Frobenius norm
    var frob = mat_norm_frobenius(a)
    assert_true(frob > 0, "Frobenius norm should be positive, got " + String(frob))
    # sqrt(1^2 + 1^2 + 0^2 + 1^2) = sqrt(3)
    assert_true(
        fabs(frob - 1.7320508) < 0.01,
        "Frobenius norm of [[1,1],[0,1]] should be sqrt(3), got " + String(frob),
    )

    # Infinity norm
    var inf_norm = mat_norm_inf(a)
    assert_true(
        fabs(inf_norm - 2.0) < 0.001,
        "inf norm of [[1,1],[0,1]] should be 2, got " + String(inf_norm),
    )

    # Symmetry check
    var sym_data = List[Float64]()
    sym_data.append(1.0)
    sym_data.append(2.0)
    sym_data.append(2.0)
    sym_data.append(3.0)
    var sym_mat = mat_from_list(sym_data, 2, 2)
    assert_true(mat_is_symmetric(sym_mat), "[[1,2],[2,3]] should be symmetric")
    assert_true(not mat_is_symmetric(a), "[[1,1],[0,1]] should not be symmetric")

    # Positive definite check
    var pd_data = List[Float64]()
    pd_data.append(2.0)
    pd_data.append(1.0)
    pd_data.append(1.0)
    pd_data.append(2.0)
    var pd_mat = mat_from_list(pd_data, 2, 2)
    assert_true(mat_is_positive_definite(pd_mat), "[[2,1],[1,2]] should be positive definite")

    # Power iteration
    var pi_data = List[Float64]()
    pi_data.append(2.0)
    pi_data.append(1.0)
    pi_data.append(1.0)
    pi_data.append(2.0)
    var pi_mat = mat_from_list(pi_data, 2, 2)
    var pi_result = mat_power_iteration(pi_mat)
    var eigenval = pi_result.eigenvalue
    assert_true(
        fabs(eigenval - 3.0) < 0.01,
        "dominant eigenvalue of [[2,1],[1,2]] should be 3, got " + String(eigenval),
    )

    # Condition number
    var cond = mat_condition_number(mat_identity(2))
    assert_true(
        fabs(cond - 1.0) < 0.01,
        "condition number of identity should be 1, got " + String(cond),
    )

    print("✅ QR decomposition & linalg extensions")

    # ── Validation ───────────────────────────────────────────────────────
    assert_true(is_valid_email("user@example.com"), "user@example.com should be valid email")
    assert_true(not is_valid_email("invalid"), "'invalid' should not be valid email")
    assert_true(not is_valid_email("@no.com"), "@no.com should not be valid email")
    assert_true(not is_valid_email("a@b"), "a@b should not be valid (no dot in domain)")

    assert_true(is_valid_ip4("192.168.1.1"), "192.168.1.1 should be valid IPv4")
    assert_true(is_valid_ip4("0.0.0.0"), "0.0.0.0 should be valid IPv4")
    assert_true(is_valid_ip4("255.255.255.255"), "255.255.255.255 should be valid IPv4")
    assert_true(not is_valid_ip4("999.999.999.999"), "999.999.999.999 should not be valid IPv4")
    assert_true(not is_valid_ip4("1.2.3"), "1.2.3 should not be valid IPv4 (3 octets)")
    assert_true(not is_valid_ip4("1.2.3.4.5"), "1.2.3.4.5 should not be valid IPv4 (5 octets)")

    assert_true(is_valid_number("3.14"), "3.14 should be valid number")
    assert_true(is_valid_number("-42"), "-42 should be valid number")
    assert_true(is_valid_number("1e10"), "1e10 should be valid number")
    assert_true(is_valid_number("+0.5"), "+0.5 should be valid number")
    assert_true(not is_valid_number("abc"), "'abc' should not be valid number")
    assert_true(not is_valid_number(""), "empty string should not be valid number")

    assert_true(is_in_range(5.0, 0.0, 10.0), "5 should be in range [0, 10]")
    assert_true(not is_in_range(15.0, 0.0, 10.0), "15 should not be in range [0, 10]")
    assert_true(is_in_range(0.0, 0.0, 10.0), "0 should be in range [0, 10] (boundary)")
    assert_true(is_in_range(10.0, 0.0, 10.0), "10 should be in range [0, 10] (boundary)")

    assert_true(clamp(15.0, 0.0, 10.0) == 10.0, "clamp(15, 0, 10) should be 10")
    assert_true(clamp(-5.0, 0.0, 10.0) == 0.0, "clamp(-5, 0, 10) should be 0")
    assert_true(clamp(5.0, 0.0, 10.0) == 5.0, "clamp(5, 0, 10) should be 5")

    assert_true(is_positive(1.0), "1.0 should be positive")
    assert_true(not is_positive(-1.0), "-1.0 should not be positive")
    assert_true(not is_positive(0.0), "0.0 should not be positive")

    assert_true(is_finite(1.0), "1.0 should be finite")
    assert_true(is_finite(0.0), "0.0 should be finite")

    var mono = List[Float64]()
    mono.append(1.0)
    mono.append(2.0)
    mono.append(3.0)
    assert_true(
        check_monotonic(mono) == 1,
        "[1,2,3] should be increasing (1), got " + String(check_monotonic(mono)),
    )

    var mono_dec = List[Float64]()
    mono_dec.append(3.0)
    mono_dec.append(2.0)
    mono_dec.append(1.0)
    assert_true(
        check_monotonic(mono_dec) == -1,
        "[3,2,1] should be decreasing (-1), got " + String(check_monotonic(mono_dec)),
    )

    var mono_neither = List[Float64]()
    mono_neither.append(1.0)
    mono_neither.append(3.0)
    mono_neither.append(2.0)
    assert_true(
        check_monotonic(mono_neither) == 0,
        "[1,3,2] should be neither (0), got " + String(check_monotonic(mono_neither)),
    )

    # Array bounds
    var arr = List[Float64]()
    arr.append(1.0)
    arr.append(5.0)
    arr.append(9.0)
    assert_true(validate_array_bounds(arr, 0.0, 10.0), "[1,5,9] should be in [0,10]")
    assert_true(not validate_array_bounds(arr, 2.0, 8.0), "[1,5,9] should not be in [2,8]")

    # JSON validation
    assert_true(is_valid_json('{"key": "value"}'), '{"key": "value"} should be valid JSON')
    assert_true(is_valid_json("[1, 2, 3]"), "[1, 2, 3] should be valid JSON")
    assert_true(not is_valid_json("{unclosed"), "{unclosed should not be valid JSON")

    print("✅ Validation")

    print("")
    print("✅ All Wave 12 tests passed")
