"""test_tensor2d.mojo — known-value tests for tensor2d (Matrix2D)."""
from tensor2d import (
    Matrix2D,
    m2_zeros,
    m2_from_list,
    m2_get,
    m2_set,
    m2_matmul,
    m2_matvec,
    m2_transpose,
    m2_add,
    m2_scale,
    m2_row,
    m2_col,
)


def _close(a: Float64, b: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d < 1e-12


def _vec_close(a: List[Float64], b: List[Float64]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not _close(a[i], b[i]):
            return False
    return True


def _m2_close(a: Matrix2D, b: Matrix2D) -> Bool:
    if a.rows != b.rows or a.cols != b.cols:
        return False
    return _vec_close(a.data, b.data)


def _flat(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ tensor2d::" + name)
    else:
        failed += 1
        print("  ❌ tensor2d::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── m2_zeros ─────────────────────────────────────────────────────────────
    var z = m2_zeros(2, 3)
    var z_ok = z.rows == 2 and z.cols == 3 and len(z.data) == 6
    for i in range(len(z.data)):
        if z.data[i] != 0.0:
            z_ok = False
    check(z_ok, "m2_zeros 2x3 shape + all zeros", passed, failed)

    var z0 = m2_zeros(0, 5)
    var zn = m2_zeros(-2, 3)
    check(
        z0.rows == 0 and z0.cols == 5 and len(z0.data) == 0
        and zn.rows == 0 and zn.cols == 3 and len(zn.data) == 0,
        "m2_zeros empty + negative dims clamp",
        passed,
        failed,
    )

    # ── m2_from_list / m2_get ────────────────────────────────────────────────
    # A = [[1,2,3],[4,5,6]] row-major
    var a = m2_from_list(_flat(1.0, 2.0, 3.0, 4.0, 5.0, 6.0), 2, 3)
    check(
        a.rows == 2 and a.cols == 3
        and _close(m2_get(a, 0, 0), 1.0)
        and _close(m2_get(a, 0, 2), 3.0)
        and _close(m2_get(a, 1, 0), 4.0)
        and _close(m2_get(a, 1, 2), 6.0),
        "m2_from_list row-major layout via m2_get",
        passed,
        failed,
    )

    # short input zero-pads; extra input ignored
    var short = m2_from_list(_flat(9.0), 2, 2)
    var extra = m2_from_list(_flat(1.0, 2.0, 3.0, 4.0, 99.0), 2, 2)
    check(
        _close(m2_get(short, 0, 0), 9.0) and _close(m2_get(short, 1, 1), 0.0)
        and extra.rows == 2 and extra.cols == 2 and len(extra.data) == 4
        and _close(m2_get(extra, 1, 1), 4.0),
        "m2_from_list short input pads, extra ignored",
        passed,
        failed,
    )

    # out-of-range get -> 0.0
    check(
        _close(m2_get(a, 2, 0), 0.0) and _close(m2_get(a, 0, 3), 0.0)
        and _close(m2_get(a, -1, 0), 0.0) and _close(m2_get(a, 0, -1), 0.0),
        "m2_get out of range -> 0.0",
        passed,
        failed,
    )

    # ── m2_set ───────────────────────────────────────────────────────────────
    var s = m2_zeros(2, 2)
    m2_set(s, 0, 1, 7.5)
    m2_set(s, 1, 0, -2.0)
    m2_set(s, 5, 5, 100.0)   # no-op
    m2_set(s, -1, 0, 100.0)  # no-op
    check(
        _close(m2_get(s, 0, 1), 7.5) and _close(m2_get(s, 1, 0), -2.0)
        and _close(m2_get(s, 0, 0), 0.0) and _close(m2_get(s, 1, 1), 0.0)
        and len(s.data) == 4,
        "m2_set writes in range, no-op out of range",
        passed,
        failed,
    )

    # ── m2_matmul: hand-computed 2x3 @ 3x2 ──────────────────────────────────
    # A = [[1,2,3],[4,5,6]], B = [[7,8],[9,10],[11,12]]
    # AB = [[1*7+2*9+3*11, 1*8+2*10+3*12],
    #       [4*7+5*9+6*11, 4*8+5*10+6*12]] = [[58,64],[139,154]]
    var b = m2_from_list(_flat(7.0, 8.0, 9.0, 10.0, 11.0, 12.0), 3, 2)
    var ab = m2_matmul(a, b)
    check(
        ab.rows == 2 and ab.cols == 2
        and _close(m2_get(ab, 0, 0), 58.0) and _close(m2_get(ab, 0, 1), 64.0)
        and _close(m2_get(ab, 1, 0), 139.0) and _close(m2_get(ab, 1, 1), 154.0),
        "m2_matmul 2x3 @ 3x2 = [[58,64],[139,154]]",
        passed,
        failed,
    )

    # B @ A is 3x3 — spot-check corners:
    # (0,0)=7*1+8*4=39  (0,2)=7*3+8*6=69  (2,0)=11*1+12*4=59  (2,2)=11*3+12*6=105
    var ba = m2_matmul(b, a)
    check(
        ba.rows == 3 and ba.cols == 3
        and _close(m2_get(ba, 0, 0), 39.0) and _close(m2_get(ba, 0, 2), 69.0)
        and _close(m2_get(ba, 2, 0), 59.0) and _close(m2_get(ba, 2, 2), 105.0),
        "m2_matmul 3x2 @ 2x3 corners",
        passed,
        failed,
    )

    # identity: A @ I3 == A
    var i3 = m2_zeros(3, 3)
    m2_set(i3, 0, 0, 1.0)
    m2_set(i3, 1, 1, 1.0)
    m2_set(i3, 2, 2, 1.0)
    check(_m2_close(m2_matmul(a, i3), a), "m2_matmul A @ I == A", passed, failed)

    # 1x1: [3] @ [4] = [12]
    var one_a = m2_from_list(_flat(3.0), 1, 1)
    var one_b = m2_from_list(_flat(4.0), 1, 1)
    var one_ab = m2_matmul(one_a, one_b)
    check(
        one_ab.rows == 1 and one_ab.cols == 1 and _close(m2_get(one_ab, 0, 0), 12.0),
        "m2_matmul 1x1",
        passed,
        failed,
    )

    # all-equal: ones(2,2) @ ones(2,2) = [[2,2],[2,2]]
    var ones = m2_from_list(_flat(1.0, 1.0, 1.0, 1.0), 2, 2)
    var ones2 = m2_matmul(ones, ones)
    check(
        _close(m2_get(ones2, 0, 0), 2.0) and _close(m2_get(ones2, 1, 1), 2.0)
        and _close(m2_get(ones2, 0, 1), 2.0) and _close(m2_get(ones2, 1, 0), 2.0),
        "m2_matmul all-ones 2x2 -> all 2.0",
        passed,
        failed,
    )

    # mismatch (2x3 @ 2x3) and empty operand -> 0x0
    var mm = m2_matmul(a, a)
    var me = m2_matmul(m2_zeros(0, 0), a)
    check(
        mm.rows == 0 and mm.cols == 0 and len(mm.data) == 0
        and me.rows == 0 and me.cols == 0,
        "m2_matmul shape mismatch / empty -> 0x0",
        passed,
        failed,
    )

    # ── m2_matvec ────────────────────────────────────────────────────────────
    # A @ [2,1,3] = [1*2+2*1+3*3, 4*2+5*1+6*3] = [13, 31]
    var mv = m2_matvec(a, _flat(2.0, 1.0, 3.0))
    check(
        len(mv) == 2 and _close(mv[0], 13.0) and _close(mv[1], 31.0),
        "m2_matvec [[1,2,3],[4,5,6]] @ [2,1,3] = [13,31]",
        passed,
        failed,
    )
    # signed: A @ [1,0,-1] = [-2,-2]
    var mv2 = m2_matvec(a, _flat(1.0, 0.0, -1.0))
    check(
        len(mv2) == 2 and _close(mv2[0], -2.0) and _close(mv2[1], -2.0),
        "m2_matvec signed vector",
        passed,
        failed,
    )
    # length mismatch -> empty
    check(
        len(m2_matvec(a, _flat(1.0, 2.0))) == 0
        and len(m2_matvec(m2_zeros(0, 0), List[Float64]())) == 0,
        "m2_matvec length mismatch -> empty (0x0 @ [] -> empty)",
        passed,
        failed,
    )

    # ── m2_transpose ─────────────────────────────────────────────────────────
    # A^T = [[1,4],[2,5],[3,6]]
    var at = m2_transpose(a)
    check(
        at.rows == 3 and at.cols == 2
        and _close(m2_get(at, 0, 0), 1.0) and _close(m2_get(at, 0, 1), 4.0)
        and _close(m2_get(at, 1, 0), 2.0) and _close(m2_get(at, 1, 1), 5.0)
        and _close(m2_get(at, 2, 0), 3.0) and _close(m2_get(at, 2, 1), 6.0),
        "m2_transpose 2x3 -> exact 3x2",
        passed,
        failed,
    )
    check(_m2_close(m2_transpose(at), a), "m2_transpose involution (A^T)^T == A", passed, failed)
    var te = m2_transpose(m2_zeros(0, 0))
    check(te.rows == 0 and te.cols == 0, "m2_transpose empty -> empty", passed, failed)
    # (AB)^T == B^T A^T
    check(
        _m2_close(m2_transpose(ab), m2_matmul(m2_transpose(b), m2_transpose(a))),
        "m2_transpose (AB)^T == B^T A^T",
        passed,
        failed,
    )

    # ── m2_add ───────────────────────────────────────────────────────────────
    # [[1,2],[3,4]] + [[10,20],[30,40]] = [[11,22],[33,44]]
    var c1 = m2_from_list(_flat(1.0, 2.0, 3.0, 4.0), 2, 2)
    var c2 = m2_from_list(_flat(10.0, 20.0, 30.0, 40.0), 2, 2)
    var csum = m2_add(c1, c2)
    check(
        _close(m2_get(csum, 0, 0), 11.0) and _close(m2_get(csum, 0, 1), 22.0)
        and _close(m2_get(csum, 1, 0), 33.0) and _close(m2_get(csum, 1, 1), 44.0),
        "m2_add exact [[11,22],[33,44]]",
        passed,
        failed,
    )
    var bad = m2_add(c1, a)
    check(bad.rows == 0 and bad.cols == 0, "m2_add shape mismatch -> 0x0", passed, failed)
    check(
        _m2_close(m2_add(c1, m2_scale(c1, -1.0)), m2_zeros(2, 2)),
        "m2_add A + (-A) == zeros",
        passed,
        failed,
    )

    # ── m2_scale ─────────────────────────────────────────────────────────────
    # 2.5 * [[1,2],[3,4]] = [[2.5,5],[7.5,10]]
    var sc = m2_scale(c1, 2.5)
    check(
        _close(m2_get(sc, 0, 0), 2.5) and _close(m2_get(sc, 0, 1), 5.0)
        and _close(m2_get(sc, 1, 0), 7.5) and _close(m2_get(sc, 1, 1), 10.0),
        "m2_scale 2.5x exact",
        passed,
        failed,
    )
    check(
        _m2_close(m2_scale(a, 0.0), m2_zeros(2, 3))
        and _m2_close(m2_scale(a, 1.0), a),
        "m2_scale by 0 -> zeros, by 1 -> identity op",
        passed,
        failed,
    )

    # ── m2_row / m2_col ──────────────────────────────────────────────────────
    var r1 = m2_row(a, 1)
    var col2 = m2_col(a, 2)
    check(
        _vec_close(r1, _flat(4.0, 5.0, 6.0)),
        "m2_row(A,1) = [4,5,6]",
        passed,
        failed,
    )
    check(
        _vec_close(col2, _flat(3.0, 6.0)),
        "m2_col(A,2) = [3,6]",
        passed,
        failed,
    )
    check(
        len(m2_row(a, 2)) == 0 and len(m2_row(a, -1)) == 0
        and len(m2_col(a, 3)) == 0 and len(m2_col(a, -1)) == 0,
        "m2_row/m2_col out of range -> empty",
        passed,
        failed,
    )
    # row of transpose == col of original
    check(
        _vec_close(m2_row(at, 2), m2_col(a, 2).copy()),
        "m2_row(A^T, j) == m2_col(A, j)",
        passed,
        failed,
    )

    # ── single-element and 1xN edge shapes ───────────────────────────────────
    var rvec = m2_from_list(_flat(1.0, 2.0, 3.0), 1, 3)   # 1x3
    var cvec = m2_from_list(_flat(4.0, 5.0, 6.0), 3, 1)   # 3x1
    # (1x3)@(3x1) = [[1*4+2*5+3*6]] = [[32]]
    var dot = m2_matmul(rvec, cvec)
    check(
        dot.rows == 1 and dot.cols == 1 and _close(m2_get(dot, 0, 0), 32.0),
        "m2_matmul row-vec @ col-vec = [[32]]",
        passed,
        failed,
    )
    # (3x1)@(1x3) = outer product, (2,1) entry = 6*2 = 12
    var outer = m2_matmul(cvec, rvec)
    check(
        outer.rows == 3 and outer.cols == 3
        and _close(m2_get(outer, 2, 1), 12.0) and _close(m2_get(outer, 0, 0), 4.0),
        "m2_matmul outer product 3x1 @ 1x3",
        passed,
        failed,
    )

    print("  [tensor2d] Passed:", passed, "Failed:", failed)
