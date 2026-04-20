"""Tests for Wave 46 — Root Finding, Delta Compression, Causal Inference."""

from root_finding import (
    eval_func,
    eval_deriv,
    bisection,
    newton_raphson,
    secant_method,
    fixed_point,
    regula_falsi,
    bracket_root,
    convergence_order,
)
from compression.delta import (
    delta_encode,
    delta_decode,
    delta_encode_float,
    delta_decode_float,
    xor_delta_encode,
    xor_delta_decode,
    zigzag_delta_encode,
    zigzag_delta_decode,
    double_delta_encode,
    double_delta_decode,
    compression_savings,
)
from causal import (
    ate,
    att,
    propensity_score,
    ipw_estimate,
    diff_in_diff,
    regression_discontinuity,
    iv_estimate,
    stratified_ate,
    cohens_d,
    needed_sample_size_ate,
)

from std.math import abs as fabs, sqrt, cos, exp


# ── Helpers ──────────────────────────────────────────────────────────────────


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _li(a: Int, b: Int, c: Int, d: Int, e: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a); r.append(b); r.append(c); r.append(d); r.append(e)
    return r^


fn _li4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a); r.append(b); r.append(c); r.append(d)
    return r^


fn _lf3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c)
    return r^


fn _lf4(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c); r.append(d)
    return r^


fn _lf5(a: Float64, b: Float64, c: Float64, d: Float64, e: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c); r.append(d); r.append(e)
    return r^


fn _lf8(a: Float64, b: Float64, c: Float64, d: Float64,
        e: Float64, f: Float64, g: Float64, h: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c); r.append(d)
    r.append(e); r.append(f); r.append(g); r.append(h)
    return r^


fn _li8(a: Int, b: Int, c: Int, d: Int,
        e: Int, f: Int, g: Int, h: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a); r.append(b); r.append(c); r.append(d)
    r.append(e); r.append(f); r.append(g); r.append(h)
    return r^


fn _lf6(a: Float64, b: Float64, c: Float64,
        d: Float64, e: Float64, f: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c)
    r.append(d); r.append(e); r.append(f)
    return r^


fn _li6(a: Int, b: Int, c: Int, d: Int, e: Int, f: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a); r.append(b); r.append(c)
    r.append(d); r.append(e); r.append(f)
    return r^


fn _lf1(a: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a)
    return r^


fn _lf2(a: Float64, b: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b)
    return r^


# ── Root Finding Tests ───────────────────────────────────────────────────────


fn test_eval_func() raises:
    print("  test_eval_func ...")
    var s2 = sqrt(2.0)
    # 1: eval_func(sqrt(2), 0) ≈ 0
    _assert_close(eval_func(s2, 0), 0.0, 1e-10, "f0(sqrt2)=0")
    # 2: eval_func(0, 0) = -2
    _assert_close(eval_func(0.0, 0), -2.0, 1e-10, "f0(0)=-2")
    # 3: eval_func(2, 0) = 2
    _assert_close(eval_func(2.0, 0), 2.0, 1e-10, "f0(2)=2")
    # 4: func 2: cos(0)-0 = 1
    _assert_close(eval_func(0.0, 2), 1.0, 1e-10, "f2(0)=1")
    # 5: func 3: exp(0)-0 = 1
    _assert_close(eval_func(0.0, 3), 1.0, 1e-10, "f3(0)=1")
    print("    PASS")


fn test_eval_deriv() raises:
    print("  test_eval_deriv ...")
    # 6: deriv of x^2-2 at x=3 is 6
    _assert_close(eval_deriv(3.0, 0), 6.0, 1e-10, "f0'(3)=6")
    # 7: deriv of x^3-x-2 at x=1 is 2
    _assert_close(eval_deriv(1.0, 1), 2.0, 1e-10, "f1'(1)=2")
    print("    PASS")


fn test_bisection() raises:
    print("  test_bisection ...")
    var s2 = sqrt(2.0)
    # 8: bisection on f0 over [1,2] ≈ sqrt(2)
    var r0 = bisection(1.0, 2.0, 0)
    _assert_close(r0, s2, 1e-8, "bisection f0")
    # 9: bisection on f1 over [1,2]
    var r1 = bisection(1.0, 2.0, 1)
    _assert_close(eval_func(r1, 1), 0.0, 1e-6, "bisection f1 root")
    # 10: bisection on f2 over [0,1]
    var r2 = bisection(0.0, 1.0, 2)
    _assert_close(eval_func(r2, 2), 0.0, 1e-6, "bisection f2 root")
    print("    PASS")


fn test_newton_raphson() raises:
    print("  test_newton_raphson ...")
    var s2 = sqrt(2.0)
    # 11: newton on f0 from x0=1.5 ≈ sqrt(2)
    var r0 = newton_raphson(1.5, 0)
    _assert_close(r0, s2, 1e-10, "newton f0")
    # 12: newton on f1
    var r1 = newton_raphson(1.5, 1)
    _assert_close(eval_func(r1, 1), 0.0, 1e-8, "newton f1 root")
    # 13: newton on f2
    var r2 = newton_raphson(0.5, 2)
    _assert_close(eval_func(r2, 2), 0.0, 1e-8, "newton f2 root")
    # 14: newton on f3
    var r3 = newton_raphson(1.5, 3)
    _assert_close(eval_func(r3, 3), 0.0, 1e-8, "newton f3 root")
    print("    PASS")


fn test_secant_method() raises:
    print("  test_secant_method ...")
    var s2 = sqrt(2.0)
    # 15: secant on f0
    var r0 = secant_method(1.0, 2.0, 0)
    _assert_close(r0, s2, 1e-8, "secant f0")
    # 16: secant on f1
    var r1 = secant_method(1.0, 2.0, 1)
    _assert_close(eval_func(r1, 1), 0.0, 1e-6, "secant f1 root")
    print("    PASS")


fn test_fixed_point() raises:
    print("  test_fixed_point ...")
    var s2 = sqrt(2.0)
    # 17: fixed-point on f0
    var r0 = fixed_point(1.5, 0)
    _assert_close(r0, s2, 1e-8, "fixedpt f0")
    # 18: fixed-point on f2
    var r2 = fixed_point(0.5, 2)
    _assert_close(eval_func(r2, 2), 0.0, 1e-8, "fixedpt f2 root")
    print("    PASS")


fn test_regula_falsi() raises:
    print("  test_regula_falsi ...")
    var s2 = sqrt(2.0)
    # 19: regula_falsi on f0
    var r0 = regula_falsi(1.0, 2.0, 0)
    _assert_close(r0, s2, 1e-8, "regula_falsi f0")
    # 20: regula_falsi on f1
    var r1 = regula_falsi(1.0, 2.0, 1)
    _assert_close(eval_func(r1, 1), 0.0, 1e-6, "regula_falsi f1 root")
    # 21: regula_falsi on f2
    var r2 = regula_falsi(0.0, 1.0, 2)
    _assert_close(eval_func(r2, 2), 0.0, 1e-6, "regula_falsi f2 root")
    print("    PASS")


fn test_methods_agree() raises:
    print("  test_methods_agree ...")
    var rb = bisection(1.0, 2.0, 0)
    var rn = newton_raphson(1.5, 0)
    var rs = secant_method(1.0, 2.0, 0)
    var rf = regula_falsi(1.0, 2.0, 0)
    var rp = fixed_point(1.5, 0)
    # 22–25: all methods agree within 1e-6
    _assert_close(rb, rn, 1e-6, "bisection≈newton")
    _assert_close(rn, rs, 1e-6, "newton≈secant")
    _assert_close(rs, rf, 1e-6, "secant≈regula_falsi")
    _assert_close(rf, rp, 1e-6, "regula_falsi≈fixedpt")
    print("    PASS")


fn test_bracket_root() raises:
    print("  test_bracket_root ...")
    # 26: bracket_root returns valid bracket for f0
    var br = bracket_root(0, start=0.0, step=0.5)
    _assert(len(br) == 2, "bracket len==2")
    # 27: f(a)*f(b) < 0
    var fa = eval_func(br[0], 0)
    var fb = eval_func(br[1], 0)
    _assert(fa * fb < 0.0, "bracket sign change")
    # 28: bracket for f2
    var br2 = bracket_root(2, start=0.0, step=0.25)
    _assert(len(br2) == 2, "bracket2 len==2")
    _assert(eval_func(br2[0], 2) * eval_func(br2[1], 2) < 0.0, "bracket2 sign change")
    print("    PASS")


fn test_convergence_order() raises:
    print("  test_convergence_order ...")
    # Newton method convergence: collect errors for f0, starting from x=2
    var s2 = sqrt(2.0)
    var errors = List[Float64]()
    var x = 2.0
    for _ in range(10):
        errors.append(fabs(x - s2))
        var fx = eval_func(x, 0)
        var dfx = eval_deriv(x, 0)
        x = x - fx / dfx
    # 29: convergence order for Newton ≈ 2
    var order = convergence_order(errors)
    _assert(order > 1.5, "Newton order > 1.5, got " + String(order))
    # 30: convergence order for Newton < 3
    _assert(order < 3.0, "Newton order < 3.0, got " + String(order))
    print("    PASS")


# ── Delta Compression Tests ─────────────────────────────────────────────────


fn test_delta_encode_decode() raises:
    print("  test_delta_encode_decode ...")
    var data = _li(1, 3, 6, 10, 15)
    var encoded = delta_encode(data)
    # 31: delta_encode first = 1
    _assert_eq(encoded[0], 1, "delta[0]=1")
    # 32: delta_encode second = 2
    _assert_eq(encoded[1], 2, "delta[1]=2")
    # 33: delta_encode third = 3
    _assert_eq(encoded[2], 3, "delta[2]=3")
    # 34: delta_encode fourth = 4
    _assert_eq(encoded[3], 4, "delta[3]=4")
    # 35: delta_encode fifth = 5
    _assert_eq(encoded[4], 5, "delta[4]=5")
    # 36: roundtrip
    var decoded = delta_decode(encoded)
    for i in range(len(data)):
        _assert_eq(decoded[i], data[i], "delta roundtrip [" + String(i) + "]")
    print("    PASS")


fn test_delta_encode_specific() raises:
    print("  test_delta_encode_specific ...")
    var data = _li4(1, 3, 6, 10)
    var encoded = delta_encode(data)
    # 37: [1,2,3,4]
    _assert_eq(encoded[0], 1, "spec[0]")
    _assert_eq(encoded[1], 2, "spec[1]")
    _assert_eq(encoded[2], 3, "spec[2]")
    _assert_eq(encoded[3], 4, "spec[3]")
    print("    PASS")


fn test_xor_delta() raises:
    print("  test_xor_delta ...")
    var data = _li(10, 12, 15, 8, 20)
    var encoded = xor_delta_encode(data)
    var decoded = xor_delta_decode(encoded)
    # 38–42: xor roundtrip
    for i in range(len(data)):
        _assert_eq(decoded[i], data[i], "xor roundtrip [" + String(i) + "]")
    print("    PASS")


fn test_zigzag_delta() raises:
    print("  test_zigzag_delta ...")
    var data = _li(100, 98, 102, 97, 105)
    var encoded = zigzag_delta_encode(data)
    var decoded = zigzag_delta_decode(encoded)
    # 43–47: zigzag roundtrip
    for i in range(len(data)):
        _assert_eq(decoded[i], data[i], "zigzag roundtrip [" + String(i) + "]")
    print("    PASS")


fn test_double_delta() raises:
    print("  test_double_delta ...")
    # Linear sequence: 10, 20, 30, 40, 50
    var data = _li(10, 20, 30, 40, 50)
    var encoded = double_delta_encode(data)
    # 48: double delta of linear → mostly zeros after first two
    _assert_eq(encoded[2], 0, "double_delta linear [2]=0")
    _assert_eq(encoded[3], 0, "double_delta linear [3]=0")
    _assert_eq(encoded[4], 0, "double_delta linear [4]=0")
    # 49: roundtrip
    var decoded = double_delta_decode(encoded)
    for i in range(len(data)):
        _assert_eq(decoded[i], data[i], "double_delta roundtrip [" + String(i) + "]")
    print("    PASS")


fn test_delta_float() raises:
    print("  test_delta_float ...")
    var data = _lf4(1.5, 2.3, 3.7, 4.1)
    var encoded = delta_encode_float(data, precision=1000)
    var decoded = delta_decode_float(encoded, precision=1000)
    # 50–53: float roundtrip within quantization error
    for i in range(len(data)):
        _assert_close(decoded[i], data[i], 0.002, "float roundtrip [" + String(i) + "]")
    print("    PASS")


fn test_compression_savings() raises:
    print("  test_compression_savings ...")
    # 54: 50% savings
    _assert_close(compression_savings(100, 50), 0.5, 1e-10, "savings 50%")
    # 55: 0% savings (no compression)
    _assert_close(compression_savings(100, 100), 0.0, 1e-10, "savings 0%")
    # 56: savings between 0 and 1
    var s = compression_savings(1000, 250)
    _assert(s > 0.0 and s < 1.0, "savings in (0,1)")
    # 57: savings = 0.75
    _assert_close(s, 0.75, 1e-10, "savings 75%")
    print("    PASS")


fn test_delta_empty() raises:
    print("  test_delta_empty ...")
    var empty = List[Int]()
    # 58: empty encode
    var enc = delta_encode(empty)
    _assert_eq(len(enc), 0, "empty encode len=0")
    # 59: empty decode
    var dec = delta_decode(empty)
    _assert_eq(len(dec), 0, "empty decode len=0")
    print("    PASS")


# ── Causal Inference Tests ───────────────────────────────────────────────────


fn test_ate_basic() raises:
    print("  test_ate_basic ...")
    var treated = _lf3(10.0, 12.0, 11.0)
    var control = _lf3(5.0, 6.0, 7.0)
    # 60: ATE = 11 - 6 = 5
    _assert_close(ate(treated, control), 5.0, 1e-10, "ate=5")
    print("    PASS")


fn test_att_basic() raises:
    print("  test_att_basic ...")
    var treated = _lf3(10.0, 12.0, 14.0)
    var counter = _lf3(8.0, 9.0, 10.0)
    # 61: ATT = 12 - 9 = 3
    _assert_close(att(treated, counter), 3.0, 1e-10, "att=3")
    print("    PASS")


fn test_diff_in_diff() raises:
    print("  test_diff_in_diff ...")
    var pre_t = _lf3(10.0, 11.0, 12.0)
    var post_t = _lf3(15.0, 16.0, 17.0)
    var pre_c = _lf3(10.0, 11.0, 12.0)
    var post_c = _lf3(12.0, 13.0, 14.0)
    # 62: DiD = (16-11) - (13-11) = 5 - 2 = 3
    _assert_close(diff_in_diff(pre_t, post_t, pre_c, post_c), 3.0, 1e-10, "did=3")
    print("    PASS")


fn test_cohens_d_identical() raises:
    print("  test_cohens_d_identical ...")
    var g1 = _lf5(5.0, 5.0, 5.0, 5.0, 5.0)
    var g2 = _lf5(5.0, 5.0, 5.0, 5.0, 5.0)
    # 63: identical groups → d = 0
    _assert_close(cohens_d(g1, g2), 0.0, 1e-10, "cohens_d identical=0")
    print("    PASS")


fn test_cohens_d_separated() raises:
    print("  test_cohens_d_separated ...")
    var g1 = _lf5(10.0, 10.1, 9.9, 10.2, 9.8)
    var g2 = _lf5(5.0, 5.1, 4.9, 5.2, 4.8)
    # 64: well-separated → d > 0.8 (large effect)
    var d = cohens_d(g1, g2)
    _assert(d > 0.8, "cohens_d separated > 0.8, got " + String(d))
    # 65: should be very large since groups are 5 apart with small std
    _assert(d > 20.0, "cohens_d very large, got " + String(d))
    print("    PASS")


fn test_propensity_score() raises:
    print("  test_propensity_score ...")
    var features = _lf5(1.0, 2.0, 3.0, 4.0, 5.0)
    var treatment = _li(0, 0, 1, 1, 1)
    var ps = propensity_score(features, treatment)
    # 66: all scores in (0,1)
    for i in range(len(ps)):
        _assert(ps[i] > 0.0, "ps[" + String(i) + "] > 0")
        _assert(ps[i] < 1.0, "ps[" + String(i) + "] < 1")
    # 67: higher features should have higher propensity
    _assert(ps[4] > ps[0], "ps monotonic")
    print("    PASS")


fn test_ipw_estimate() raises:
    print("  test_ipw_estimate ...")
    var outcomes = _lf4(10.0, 12.0, 5.0, 6.0)
    var treatment = _li4(1, 1, 0, 0)
    var propensity = _lf4(0.6, 0.7, 0.3, 0.4)
    # 68: IPW should produce a finite value
    var est = ipw_estimate(outcomes, treatment, propensity)
    _assert(est == est, "ipw finite (not NaN)")
    # 69: IPW result reasonable (positive since treated > control)
    _assert(est > 0.0, "ipw positive")
    print("    PASS")


fn test_iv_estimate() raises:
    print("  test_iv_estimate ...")
    # Simple IV: z perfectly predicts x, effect of x on y is 2
    var z = _lf6(0.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    var x = _lf6(1.0, 1.0, 3.0, 3.0, 1.0, 3.0)
    var y = _lf6(2.0, 2.0, 6.0, 6.0, 2.0, 6.0)
    # 70: IV estimate should be ≈ 2 (y = 2*x)
    var est = iv_estimate(z, x, y)
    _assert_close(est, 2.0, 1e-8, "iv=2")
    print("    PASS")


fn test_regression_discontinuity() raises:
    print("  test_regression_discontinuity ...")
    var x = _lf8(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    var y = _lf8(2.0, 3.0, 4.0, 5.0, 12.0, 13.0, 14.0, 15.0)
    # 71: RD at cutoff=4.5 should detect jump
    var rd = regression_discontinuity(x, y, cutoff=4.5)
    _assert(rd > 5.0, "RD detects jump > 5")
    # 72: RD at cutoff=4.5 ≈ 13.5 - 3.5 = 10
    _assert_close(rd, 10.0, 1e-8, "RD=10")
    print("    PASS")


fn test_stratified_ate() raises:
    print("  test_stratified_ate ...")
    var outcomes = _lf8(10.0, 5.0, 12.0, 6.0, 20.0, 15.0, 22.0, 16.0)
    var treatment = _li8(1, 0, 1, 0, 1, 0, 1, 0)
    var strata = _li8(0, 0, 0, 0, 1, 1, 1, 1)
    # 73: stratum 0: (10+12)/2 - (5+6)/2 = 11 - 5.5 = 5.5
    # stratum 1: (20+22)/2 - (15+16)/2 = 21 - 15.5 = 5.5
    # weighted: 5.5 * 4/8 + 5.5 * 4/8 = 5.5
    var sa = stratified_ate(outcomes, treatment, strata, 2)
    _assert_close(sa, 5.5, 1e-8, "stratified_ate=5.5")
    print("    PASS")


fn test_needed_sample_size() raises:
    print("  test_needed_sample_size ...")
    # 74: sample size should be positive
    var n = needed_sample_size_ate(0.5, 1.0)
    _assert(n > 0, "sample_size > 0")
    # 75: larger effect → smaller sample
    var n2 = needed_sample_size_ate(1.0, 1.0)
    _assert(n2 < n, "larger effect → smaller n")
    # 76: known formula check: effect=0.5, std=1, alpha=0.05, power=0.8
    # n = 2*(1.96+0.842)^2*1^2/0.25 = 2*7.849/0.25 ≈ 62.8 → 63
    _assert(n >= 50 and n <= 80, "sample_size in [50,80], got " + String(n))
    print("    PASS")


fn test_causal_edge_cases() raises:
    print("  test_causal_edge_cases ...")
    # 77: ATE with single elements
    var t1 = _lf1(10.0)
    var c1 = _lf1(5.0)
    _assert_close(ate(t1, c1), 5.0, 1e-10, "ate single=5")
    # 78: DiD with equal pre/post
    var eq = _lf2(10.0, 10.0)
    _assert_close(diff_in_diff(eq, eq, eq, eq), 0.0, 1e-10, "did equal=0")
    print("    PASS")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 46 Tests ===")

    print("\n── Root Finding ──")
    test_eval_func()
    test_eval_deriv()
    test_bisection()
    test_newton_raphson()
    test_secant_method()
    test_fixed_point()
    test_regula_falsi()
    test_methods_agree()
    test_bracket_root()
    test_convergence_order()

    print("\n── Delta Compression ──")
    test_delta_encode_decode()
    test_delta_encode_specific()
    test_xor_delta()
    test_zigzag_delta()
    test_double_delta()
    test_delta_float()
    test_compression_savings()
    test_delta_empty()

    print("\n── Causal Inference ──")
    test_ate_basic()
    test_att_basic()
    test_diff_in_diff()
    test_cohens_d_identical()
    test_cohens_d_separated()
    test_propensity_score()
    test_ipw_estimate()
    test_iv_estimate()
    test_regression_discontinuity()
    test_stratified_ate()
    test_needed_sample_size()
    test_causal_edge_cases()

    print("\n✅ All Wave 46 tests passed!")
