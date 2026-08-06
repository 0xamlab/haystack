"""Tests for Wave 42 — SVM Kernels, Dependency Resolution, Advanced Rate Limiting."""

from svm_kernel import (
    kernel_linear,
    kernel_rbf,
    kernel_polynomial,
    kernel_sigmoid,
    kernel_matrix,
    kernel_center,
    kernel_alignment,
    frobenius_norm,
    is_positive_semidefinite,
)
from dependency import (
    resolve_order,
    has_cycle,
    transitive_deps,
    dependency_depth,
    is_compatible,
    find_conflicts,
    install_plan,
    reverse_deps,
)
from token_bucket import (
    TokenBucket,
    tb_create,
    tb_consume,
    tb_refill,
    tb_available,
    LeakyBucket,
    lb_create,
    lb_add,
    lb_leak,
    lb_level,
    SlidingWindow,
    sw_create,
    sw_allow,
    sw_count,
)
from std.math import abs as fabs, sqrt


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helpers to build lists concisely ──────────────────────────────────────────


def _f2(a: Float64, b: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a)
    v.append(b)
    return v^


def _f3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a)
    v.append(b)
    v.append(c)
    return v^


def _i2(a: Int, b: Int) -> List[Int]:
    var v = List[Int]()
    v.append(a)
    v.append(b)
    return v^


def _i3(a: Int, b: Int, c: Int) -> List[Int]:
    var v = List[Int]()
    v.append(a)
    v.append(b)
    v.append(c)
    return v^


# ── SVM kernel tests ──────────────────────────────────────────────────────────


def test_kernel_linear() raises:
    # 1: orthogonal vectors
    _assert_close(kernel_linear(_f2(1.0, 0.0), _f2(0.0, 1.0)), 0.0, 1e-12, "linear orthogonal")

    # 2: same vector
    _assert_close(kernel_linear(_f2(1.0, 2.0), _f2(1.0, 2.0)), 5.0, 1e-12, "linear same vec")

    # 3: known dot product
    _assert_close(kernel_linear(_f2(2.0, 3.0), _f2(4.0, 1.0)), 11.0, 1e-12, "linear 2*4+3*1=11")

    # 4: zero vector
    _assert_close(kernel_linear(_f2(0.0, 0.0), _f2(5.0, 3.0)), 0.0, 1e-12, "linear zero vec")

    print("  ✓ kernel_linear (4 assertions)")


def test_kernel_rbf() raises:
    # 5: same point → 1.0
    var x = _f2(1.0, 2.0)
    _assert_close(kernel_rbf(x, x), 1.0, 1e-12, "rbf same point")

    # 6: distant points → ~0
    _assert(kernel_rbf(_f2(0.0, 0.0), _f2(100.0, 100.0)) < 1e-6, "rbf distant points near zero")

    # 7: gamma effect — higher gamma, faster decay
    var a2 = _f2(0.0, 0.0)
    var b2 = _f2(1.0, 0.0)
    var k1 = kernel_rbf(a2, b2, 0.5)
    var k2 = kernel_rbf(a2, b2, 2.0)
    _assert(k1 > k2, "rbf higher gamma → faster decay")

    # 8: symmetric
    var a3 = _f2(1.0, 3.0)
    var b3 = _f2(2.0, 5.0)
    _assert_close(kernel_rbf(a3, b3), kernel_rbf(b3, a3), 1e-12, "rbf symmetric")

    print("  ✓ kernel_rbf (4 assertions)")


def test_kernel_polynomial() raises:
    # 9: (1·1 + 0)^2 = 1.0
    _assert_close(kernel_polynomial(_f2(1.0, 0.0), _f2(1.0, 0.0), 2, 0.0), 1.0, 1e-12, "poly [1,0] deg2")

    # 10: (1+1+1)^2 = 9
    _assert_close(kernel_polynomial(_f2(1.0, 1.0), _f2(1.0, 1.0), 2, 1.0), 9.0, 1e-12, "poly (2+1)^2=9")

    # 11: degree 1 = linear + coef0
    _assert_close(kernel_polynomial(_f2(2.0, 3.0), _f2(4.0, 1.0), 1, 0.0), 11.0, 1e-12, "poly deg1 = linear")

    print("  ✓ kernel_polynomial (3 assertions)")


def test_kernel_sigmoid() raises:
    # 12: tanh(0) = 0
    _assert_close(kernel_sigmoid(_f2(0.0, 0.0), _f2(5.0, 3.0), 1.0, 0.0), 0.0, 1e-12, "sigmoid zero dot")

    # 13: sigmoid bounded [-1, 1]
    var ks = kernel_sigmoid(_f2(10.0, 10.0), _f2(10.0, 10.0), 1.0, 0.0)
    _assert(ks >= -1.0 and ks <= 1.0, "sigmoid bounded")

    print("  ✓ kernel_sigmoid (2 assertions)")


def test_kernel_matrix() raises:
    # Build a small dataset
    var data = List[List[Float64]]()
    data.append(_f2(1.0, 0.0))
    data.append(_f2(0.0, 1.0))
    data.append(_f2(1.0, 1.0))

    # 14: RBF diagonal = 1.0
    var K = kernel_matrix(data, 1, 1.0, 3, 0.0)
    _assert_close(K[0][0], 1.0, 1e-12, "gram rbf diag[0]=1")
    # 15
    _assert_close(K[1][1], 1.0, 1e-12, "gram rbf diag[1]=1")
    # 16
    _assert_close(K[2][2], 1.0, 1e-12, "gram rbf diag[2]=1")

    # 17: symmetric
    _assert_close(K[0][1], K[1][0], 1e-12, "gram symmetric [0][1]=[1][0]")
    # 18
    _assert_close(K[0][2], K[2][0], 1e-12, "gram symmetric [0][2]=[2][0]")
    # 19
    _assert_close(K[1][2], K[2][1], 1e-12, "gram symmetric [1][2]=[2][1]")

    # 20: linear kernel matrix
    var Kl = kernel_matrix(data, 0)
    _assert_close(Kl[0][1], 0.0, 1e-12, "gram linear orthog=0")

    print("  ✓ kernel_matrix (7 assertions)")


def test_frobenius_norm() raises:
    # 21: identity 2x2 → sqrt(2)
    var I2 = List[List[Float64]]()
    I2.append(_f2(1.0, 0.0))
    I2.append(_f2(0.0, 1.0))
    _assert_close(frobenius_norm(I2), sqrt(2.0), 1e-12, "frob identity 2x2")

    # 22: identity 3x3 → sqrt(3)
    var I3 = List[List[Float64]]()
    I3.append(_f3(1.0, 0.0, 0.0))
    I3.append(_f3(0.0, 1.0, 0.0))
    I3.append(_f3(0.0, 0.0, 1.0))
    _assert_close(frobenius_norm(I3), sqrt(3.0), 1e-12, "frob identity 3x3")

    # 23: all-ones 2x2 → sqrt(4) = 2
    var A = List[List[Float64]]()
    A.append(_f2(1.0, 1.0))
    A.append(_f2(1.0, 1.0))
    _assert_close(frobenius_norm(A), 2.0, 1e-12, "frob all-ones 2x2")

    print("  ✓ frobenius_norm (3 assertions)")


def test_kernel_alignment() raises:
    # 24: alignment of K with itself ≈ 1.0
    var data = List[List[Float64]]()
    data.append(_f2(1.0, 0.0))
    data.append(_f2(0.0, 1.0))
    var K = kernel_matrix(data, 1, 1.0)
    _assert_close(kernel_alignment(K, K), 1.0, 1e-10, "alignment K with K ≈ 1")

    # 25: alignment is symmetric
    var K2 = kernel_matrix(data, 0)
    var a1 = kernel_alignment(K, K2)
    var a2 = kernel_alignment(K2, K)
    _assert_close(a1, a2, 1e-12, "alignment symmetric")

    print("  ✓ kernel_alignment (2 assertions)")


def test_kernel_center() raises:
    # 26: centered kernel row sums ≈ 0
    var data = List[List[Float64]]()
    data.append(_f2(1.0, 2.0))
    data.append(_f2(3.0, 4.0))
    data.append(_f2(5.0, 6.0))
    var K = kernel_matrix(data, 0)
    var Kc = kernel_center(K)
    var row_sum: Float64 = 0.0
    for j in range(3):
        row_sum += Kc[0][j]
    _assert_close(row_sum, 0.0, 1e-10, "centered kernel row sum ≈ 0")

    # 27: col sum ≈ 0
    var col_sum: Float64 = 0.0
    for i in range(3):
        col_sum += Kc[i][1]
    _assert_close(col_sum, 0.0, 1e-10, "centered kernel col sum ≈ 0")

    print("  ✓ kernel_center (2 assertions)")


def test_is_psd() raises:
    # 28: identity is PSD
    var I2 = List[List[Float64]]()
    I2.append(_f2(1.0, 0.0))
    I2.append(_f2(0.0, 1.0))
    _assert(is_positive_semidefinite(I2), "identity is PSD")

    # 29: RBF Gram matrix is PSD (diag dominant for same-point)
    var data = List[List[Float64]]()
    data.append(_f2(1.0, 0.0))
    data.append(_f2(0.0, 1.0))
    var K = kernel_matrix(data, 1, 1.0)
    _assert(is_positive_semidefinite(K), "RBF gram is PSD")

    print("  ✓ is_positive_semidefinite (2 assertions)")


# ── Dependency tests ──────────────────────────────────────────────────────────


def test_resolve_order() raises:
    # Chain: A(0) → B(1) → C(2)  means 0 depends on 1, 1 depends on 2
    var deps = List[List[Int]]()
    deps.append(_i2(0, 1))  # 0 depends on 1
    deps.append(_i2(1, 2))  # 1 depends on 2
    var order = resolve_order(3, deps)
    # 30: correct length
    _assert_eq(len(order), 3, "resolve_order length=3")
    # 31: C(2) before B(1)
    var pos2 = -1
    var pos1 = -1
    var pos0 = -1
    for i in range(len(order)):
        if order[i] == 2:
            pos2 = i
        if order[i] == 1:
            pos1 = i
        if order[i] == 0:
            pos0 = i
    _assert(pos2 < pos1, "resolve_order C before B")
    # 32: B before A
    _assert(pos1 < pos0, "resolve_order B before A")

    print("  ✓ resolve_order (3 assertions)")


def test_has_cycle() raises:
    # 33: cycle A→B→A
    var cycled = List[List[Int]]()
    cycled.append(_i2(0, 1))
    cycled.append(_i2(1, 0))
    _assert(has_cycle(2, cycled), "has_cycle detects cycle")

    # 34: acyclic
    var acyclic = List[List[Int]]()
    acyclic.append(_i2(0, 1))
    _assert(not has_cycle(2, acyclic), "has_cycle no cycle")

    # 35: 3-node cycle
    var cycle3 = List[List[Int]]()
    cycle3.append(_i2(0, 1))
    cycle3.append(_i2(1, 2))
    cycle3.append(_i2(2, 0))
    _assert(has_cycle(3, cycle3), "has_cycle 3-node cycle")

    print("  ✓ has_cycle (3 assertions)")


def test_transitive_deps() raises:
    # 0→1→2→3
    var deps = List[List[Int]]()
    deps.append(_i2(0, 1))
    deps.append(_i2(1, 2))
    deps.append(_i2(2, 3))

    var td = transitive_deps(0, deps)
    # 36: should have 3 transitive deps
    _assert_eq(len(td), 3, "transitive_deps count=3")

    # 37: contains 1
    var has1 = False
    for i in range(len(td)):
        if td[i] == 1:
            has1 = True
    _assert(has1, "transitive_deps contains 1")

    # 38: contains 3
    var has3 = False
    for i in range(len(td)):
        if td[i] == 3:
            has3 = True
    _assert(has3, "transitive_deps contains 3")

    print("  ✓ transitive_deps (3 assertions)")


def test_dependency_depth() raises:
    # 0→1→2→3 chain: depth=3
    var deps = List[List[Int]]()
    deps.append(_i2(0, 1))
    deps.append(_i2(1, 2))
    deps.append(_i2(2, 3))

    # 39
    _assert_eq(dependency_depth(0, deps), 3, "depth chain=3")
    # 40: leaf has depth 0
    _assert_eq(dependency_depth(3, deps), 0, "depth leaf=0")
    # 41: mid node
    _assert_eq(dependency_depth(1, deps), 2, "depth mid=2")

    print("  ✓ dependency_depth (3 assertions)")


def test_is_compatible() raises:
    # 42
    _assert(is_compatible(5, 3, 7), "5 in [3,7]")
    # 43
    _assert(not is_compatible(2, 3, 7), "2 not in [3,7]")
    # 44
    _assert(is_compatible(3, 3, 7), "3 in [3,7] boundary")
    # 45
    _assert(is_compatible(7, 3, 7), "7 in [3,7] boundary")
    # 46
    _assert(not is_compatible(8, 3, 7), "8 not in [3,7]")

    print("  ✓ is_compatible (5 assertions)")


def test_find_conflicts() raises:
    var reqs = List[List[Int]]()
    reqs.append(_i3(0, 1, 3))   # pkg 0 needs v1-3
    reqs.append(_i3(0, 5, 7))   # pkg 0 needs v5-7 → conflict!
    reqs.append(_i3(1, 2, 4))   # pkg 1 needs v2-4
    var conflicts = find_conflicts(reqs)
    # 47: one conflict pair
    _assert_eq(len(conflicts), 1, "find_conflicts 1 pair")
    # 48: conflict between indices 0 and 1
    _assert_eq(conflicts[0][0], 0, "conflict idx 0")
    # 49
    _assert_eq(conflicts[0][1], 1, "conflict idx 1")

    print("  ✓ find_conflicts (3 assertions)")


def test_install_plan() raises:
    # 0→1→2, 0→3
    var deps = List[List[Int]]()
    deps.append(_i2(0, 1))
    deps.append(_i2(1, 2))
    deps.append(_i2(0, 3))
    var plan = install_plan(4, deps, 0)
    # 50: includes target
    var has0 = False
    for i in range(len(plan)):
        if plan[i] == 0:
            has0 = True
    _assert(has0, "install_plan includes target")
    # 51: includes dep 2
    var has2 = False
    for i in range(len(plan)):
        if plan[i] == 2:
            has2 = True
    _assert(has2, "install_plan includes dep 2")
    # 52: includes dep 3
    var has3 = False
    for i in range(len(plan)):
        if plan[i] == 3:
            has3 = True
    _assert(has3, "install_plan includes dep 3")

    print("  ✓ install_plan (3 assertions)")


def test_reverse_deps() raises:
    # 0→1, 2→1  → reverse_deps(1) = [0, 2]
    var deps = List[List[Int]]()
    deps.append(_i2(0, 1))
    deps.append(_i2(2, 1))
    var rd = reverse_deps(1, deps)
    # 53
    _assert_eq(len(rd), 2, "reverse_deps count=2")
    # 54: contains 0
    var has0 = False
    for i in range(len(rd)):
        if rd[i] == 0:
            has0 = True
    _assert(has0, "reverse_deps contains 0")
    # 55: contains 2
    var has2 = False
    for i in range(len(rd)):
        if rd[i] == 2:
            has2 = True
    _assert(has2, "reverse_deps contains 2")

    print("  ✓ reverse_deps (3 assertions)")


# ── Token bucket tests ────────────────────────────────────────────────────────


def test_token_bucket() raises:
    # 56: create with full capacity
    var tb = tb_create(10.0, 1.0)
    _assert_close(tb_available(tb), 10.0, 1e-12, "tb_create 10 tokens")

    # 57: consume 5 → True, available = 5
    var ok = tb_consume(tb, 5.0, 0.0)
    _assert(ok, "tb_consume 5 ok")
    # 58
    _assert_close(tb_available(tb), 5.0, 1e-12, "tb after consume 5 = 5")

    # 59: consume 6 → False (not enough)
    var fail = tb_consume(tb, 6.0, 0.0)
    _assert(not fail, "tb_consume 6 fails")
    # 60: tokens unchanged
    _assert_close(tb_available(tb), 5.0, 1e-12, "tb still 5 after failed consume")

    # 61: after 3 seconds, refill 3 tokens → 8
    tb_refill(tb, 3.0)
    _assert_close(tb_available(tb), 8.0, 1e-12, "tb refill 3s → 8")

    # 62: refill capped at capacity
    tb_refill(tb, 100.0)
    _assert_close(tb_available(tb), 10.0, 1e-12, "tb refill capped at capacity")

    print("  ✓ token_bucket (7 assertions)")


def test_leaky_bucket() raises:
    # 63: create empty
    var lb = lb_create(10.0, 2.0)
    _assert_close(lb_level(lb), 0.0, 1e-12, "lb_create level=0")

    # 64: add 5 → True, level 5
    var ok = lb_add(lb, 5.0, 0.0)
    _assert(ok, "lb_add 5 ok")
    # 65
    _assert_close(lb_level(lb), 5.0, 1e-12, "lb level after add 5")

    # 66: add 6 → False (would overflow: 5+6=11 > 10)
    var fail = lb_add(lb, 6.0, 0.0)
    _assert(not fail, "lb_add 6 overflow")

    # 67: add 5 → True (5+5=10 = capacity)
    var ok2 = lb_add(lb, 5.0, 0.0)
    _assert(ok2, "lb_add 5 fills to capacity")
    _assert_close(lb_level(lb), 10.0, 1e-12, "lb at capacity")

    # 68: after 2 seconds, leak 4 (rate=2, elapsed=2) → 6
    lb_leak(lb, 2.0)
    _assert_close(lb_level(lb), 6.0, 1e-12, "lb after leak 2s → 6")

    # 69: leak doesn't go below 0
    lb_leak(lb, 100.0)
    _assert_close(lb_level(lb), 0.0, 1e-12, "lb leak floor at 0")

    print("  ✓ leaky_bucket (7 assertions)")


def test_sliding_window() raises:
    # max 3 requests per 10s window
    var sw = sw_create(10.0, 3)

    # 70: first request allowed
    _assert(sw_allow(sw, 1.0), "sw allow 1st")
    # 71
    _assert(sw_allow(sw, 2.0), "sw allow 2nd")
    # 72
    _assert(sw_allow(sw, 3.0), "sw allow 3rd")
    # 73: 4th denied
    _assert(not sw_allow(sw, 4.0), "sw deny 4th")

    # 74: count = 3
    _assert_eq(sw_count(sw, 5.0), 3, "sw count=3")

    # 75: after window passes, new requests allowed
    _assert(sw_allow(sw, 12.0), "sw allow after window")

    # 76: count after window shift
    _assert_eq(sw_count(sw, 12.0), 2, "sw count after window=2")

    print("  ✓ sliding_window (7 assertions)")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 42 tests — SVM Kernels, Dependency Resolution, Rate Limiting")
    print("=" * 70)

    # SVM kernel tests
    test_kernel_linear()
    test_kernel_rbf()
    test_kernel_polynomial()
    test_kernel_sigmoid()
    test_kernel_matrix()
    test_frobenius_norm()
    test_kernel_alignment()
    test_kernel_center()
    test_is_psd()

    # Dependency tests
    test_resolve_order()
    test_has_cycle()
    test_transitive_deps()
    test_dependency_depth()
    test_is_compatible()
    test_find_conflicts()
    test_install_plan()
    test_reverse_deps()

    # Rate limiting tests
    test_token_bucket()
    test_leaky_bucket()
    test_sliding_window()

    print("=" * 70)
    print("All 76 assertions passed! ✓")
