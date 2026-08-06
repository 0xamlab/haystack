"""Tests for Wave 45 — Linear Programming, Time Zones, Checksums."""

from linear_programming import (
    lp_solve_2var,
    is_feasible,
    objective_value,
    dual_value,
    sensitivity_rhs,
    line_intersection_2d,
    enumerate_vertices_2d,
    transportation_cost,
)
from time_zone import (
    utc_offset,
    convert_time,
    is_dst,
    effective_offset,
    time_difference,
    format_offset,
    is_valid_zone,
    local_to_utc,
    utc_to_local,
    overlap_hours,
)
from checksum import (
    adler32,
    fletcher16,
    luhn_check,
    luhn_checksum,
    isbn10_check,
    isbn13_check,
    xor_checksum,
    modular_sum,
    parity_bit,
    internet_checksum,
    verhoeff_check,
)

from std.math import abs as fabs


# ── Helpers ──────────────────────────────────────────────────────────────────


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _make_A2() -> List[List[Float64]]:
    """Helper: build constraint matrix [[1,1],[2,1]]."""
    var r1 = List[Float64]()
    r1.append(1.0); r1.append(1.0)
    var r2 = List[Float64]()
    r2.append(2.0); r2.append(1.0)
    var A = List[List[Float64]]()
    A.append(r1^); A.append(r2^)
    return A^


def _make_A_lp() -> List[List[Float64]]:
    """Helper: build constraint matrix [[1,1],[1,3]]."""
    var r1 = List[Float64]()
    r1.append(1.0); r1.append(1.0)
    var r2 = List[Float64]()
    r2.append(1.0); r2.append(3.0)
    var A = List[List[Float64]]()
    A.append(r1^); A.append(r2^)
    return A^


def _make_A1() -> List[List[Float64]]:
    """Helper: build constraint matrix [[1,1]]."""
    var r = List[Float64]()
    r.append(1.0); r.append(1.0)
    var A = List[List[Float64]]()
    A.append(r^)
    return A^


def _make_costs() -> List[List[Float64]]:
    """Helper: build cost matrix for transportation."""
    var c1 = List[Float64]()
    c1.append(8.0); c1.append(6.0); c1.append(10.0)
    var c2 = List[Float64]()
    c2.append(9.0); c2.append(12.0); c2.append(13.0)
    var costs = List[List[Float64]]()
    costs.append(c1^); costs.append(c2^)
    return costs^


# ── LP Tests ─────────────────────────────────────────────────────────────────


def test_objective_value() raises:
    var c = List[Float64]()
    c.append(3.0); c.append(2.0)
    var x = List[Float64]()
    x.append(1.0); x.append(1.0)
    _assert_close(objective_value(c, x), 5.0, 1e-9, "objective_value([3,2],[1,1])")
    print("  ✓ objective_value")


def test_is_feasible() raises:
    var x1 = List[Float64]()
    x1.append(1.0); x1.append(1.0)
    var A = _make_A2()
    var b = List[Float64]()
    b.append(3.0); b.append(4.0)
    _assert(is_feasible(x1, A, b), "is_feasible([1,1]) should be True")

    var x2 = List[Float64]()
    x2.append(5.0); x2.append(5.0)
    var A2 = _make_A1()
    var b2 = List[Float64]()
    b2.append(3.0)
    _assert(not is_feasible(x2, A2, b2), "is_feasible([5,5]) should be False")

    # Negative x should be infeasible
    var x3 = List[Float64]()
    x3.append(-1.0); x3.append(1.0)
    var A3 = _make_A1()
    _assert(not is_feasible(x3, A3, b2), "is_feasible([-1,1]) should be False")
    print("  ✓ is_feasible")


def test_line_intersection() raises:
    # x = 3, y = 2
    var pt = line_intersection_2d(1.0, 0.0, 3.0, 0.0, 1.0, 2.0)
    _assert_eq(len(pt), 2, "line_intersection should return 2 values")
    _assert_close(pt[0], 3.0, 1e-9, "intersection x=3")
    _assert_close(pt[1], 2.0, 1e-9, "intersection y=2")

    # Parallel lines: x + y = 1, x + y = 2
    var pt2 = line_intersection_2d(1.0, 1.0, 1.0, 1.0, 1.0, 2.0)
    _assert_eq(len(pt2), 0, "parallel lines should return empty")

    # Another intersection: 2x + 3y = 12, x - y = 1 → x=3, y=2
    var pt3 = line_intersection_2d(2.0, 3.0, 12.0, 1.0, -1.0, 1.0)
    _assert_close(pt3[0], 3.0, 1e-9, "intersection2 x=3")
    _assert_close(pt3[1], 2.0, 1e-9, "intersection2 y=2")
    print("  ✓ line_intersection_2d")


def test_enumerate_vertices() raises:
    var A = _make_A_lp()
    var b = List[Float64]()
    b.append(4.0); b.append(6.0)

    var verts = enumerate_vertices_2d(A, b)
    _assert(len(verts) >= 4, "should have at least 4 vertices")
    # All vertices should be feasible
    var A2 = _make_A_lp()
    for i in range(len(verts)):
        _assert(is_feasible(verts[i], A2, b), "vertex " + String(i) + " should be feasible")
    print("  ✓ enumerate_vertices_2d")


def test_lp_solve() raises:
    # maximize 3x+2y s.t. x+y≤4, x+3y≤6
    var c = List[Float64]()
    c.append(3.0); c.append(2.0)
    var A = _make_A_lp()
    var b = List[Float64]()
    b.append(4.0); b.append(6.0)

    var sol = lp_solve_2var(c, A, b)
    _assert_eq(len(sol), 3, "lp_solve should return 3 values")
    _assert_close(sol[0], 4.0, 1e-6, "optimal x1=4")
    _assert_close(sol[1], 0.0, 1e-6, "optimal x2=0")
    _assert_close(sol[2], 12.0, 1e-6, "optimal obj=12")
    print("  ✓ lp_solve_2var")


def test_dual_value() raises:
    var c = List[Float64]()
    c.append(3.0); c.append(2.0)
    var A = _make_A_lp()
    var b = List[Float64]()
    b.append(4.0); b.append(6.0)

    var dv = dual_value(A, b, c)
    _assert_close(dv, 12.0, 1e-6, "dual_value should equal primal optimal")
    print("  ✓ dual_value")


def test_sensitivity() raises:
    var c = List[Float64]()
    c.append(3.0); c.append(2.0)
    var A = _make_A_lp()
    var b = List[Float64]()
    b.append(4.0); b.append(6.0)

    var s = sensitivity_rhs(c, A, b, 0, 1.0)
    # Increasing b[0] from 4 to 5: now x+y≤5, x+3y≤6
    # Optimal moves to (5,0) → obj=15. Change = 15-12=3
    _assert_close(s, 3.0, 1e-6, "sensitivity_rhs change=3")
    print("  ✓ sensitivity_rhs")


def test_transportation() raises:
    var supply = List[Float64]()
    supply.append(20.0); supply.append(30.0)
    var demand = List[Float64]()
    demand.append(10.0); demand.append(28.0); demand.append(12.0)
    var costs = _make_costs()

    var cost = transportation_cost(supply, demand, costs)
    _assert(cost > 0.0, "transportation cost should be positive")
    # NW corner: 10*8=80, 10*6=60, 18*12=216, 12*13=156 = 512
    _assert_close(cost, 512.0, 1e-6, "transportation cost=512")
    print("  ✓ transportation_cost")


# ── Time Zone Tests ──────────────────────────────────────────────────────────


def test_utc_offset() raises:
    _assert_close(utc_offset("UTC"), 0.0, 1e-9, "UTC offset=0")
    _assert_close(utc_offset("EST"), -5.0, 1e-9, "EST offset=-5")
    _assert_close(utc_offset("IST"), 5.5, 1e-9, "IST offset=5.5")
    _assert_close(utc_offset("JST"), 9.0, 1e-9, "JST offset=9")
    _assert_close(utc_offset("PST"), -8.0, 1e-9, "PST offset=-8")
    _assert_close(utc_offset("AEST"), 10.0, 1e-9, "AEST offset=10")
    _assert_close(utc_offset("GMT"), 0.0, 1e-9, "GMT offset=0")
    print("  ✓ utc_offset")


def test_convert_time() raises:
    var r1 = convert_time(12, 0, "UTC", "EST")
    _assert_eq(r1[0], 7, "12:00 UTC → 7:xx EST")
    _assert_eq(r1[1], 0, "12:00 UTC → x:00 EST")

    var r2 = convert_time(12, 0, "EST", "UTC")
    _assert_eq(r2[0], 17, "12:00 EST → 17:xx UTC")
    _assert_eq(r2[1], 0, "12:00 EST → x:00 UTC")

    # Wrap around midnight
    var r3 = convert_time(2, 0, "UTC", "PST")
    _assert_eq(r3[0], 18, "2:00 UTC → 18:xx PST (prev day)")
    _assert_eq(r3[1], 0, "minute stays 0")
    print("  ✓ convert_time")


def test_time_difference() raises:
    _assert_close(time_difference("UTC", "JST"), 9.0, 1e-9, "UTC→JST=9h")
    _assert_close(time_difference("EST", "PST"), -3.0, 1e-9, "EST→PST=-3h")
    _assert_close(time_difference("PST", "EST"), 3.0, 1e-9, "PST→EST=3h")
    _assert_close(time_difference("UTC", "IST"), 5.5, 1e-9, "UTC→IST=5.5h")
    print("  ✓ time_difference")


def test_is_valid_zone() raises:
    _assert(is_valid_zone("UTC"), "UTC is valid")
    _assert(is_valid_zone("EST"), "EST is valid")
    _assert(is_valid_zone("CET"), "CET is valid")
    _assert(not is_valid_zone("FAKE"), "FAKE is not valid")
    _assert(not is_valid_zone("XYZ"), "XYZ is not valid")
    _assert(is_valid_zone("AEST"), "AEST is valid")
    print("  ✓ is_valid_zone")


def test_is_dst() raises:
    _assert(is_dst(6, "EST"), "EST June is DST")
    _assert(not is_dst(1, "EST"), "EST January is not DST")
    _assert(is_dst(6, "CET"), "CET June is DST")
    _assert(not is_dst(12, "CET"), "CET December is not DST")
    _assert(not is_dst(6, "JST"), "JST has no DST")
    _assert(not is_dst(6, "UTC"), "UTC has no DST")
    print("  ✓ is_dst")


def test_effective_offset() raises:
    _assert_close(effective_offset("EST", 6), -4.0, 1e-9, "EST summer=-4")
    _assert_close(effective_offset("EST", 1), -5.0, 1e-9, "EST winter=-5")
    _assert_close(effective_offset("CET", 7), 2.0, 1e-9, "CET summer=2")
    _assert_close(effective_offset("JST", 6), 9.0, 1e-9, "JST always 9")
    print("  ✓ effective_offset")


def test_format_offset() raises:
    _assert(format_offset(5.5) == "+05:30", "format +5.5 → +05:30")
    _assert(format_offset(-8.0) == "-08:00", "format -8 → -08:00")
    _assert(format_offset(0.0) == "+00:00", "format 0 → +00:00")
    _assert(format_offset(9.0) == "+09:00", "format 9 → +09:00")
    print("  ✓ format_offset")


def test_local_to_utc() raises:
    var r = local_to_utc(12, 0, "CET")
    _assert_eq(r[0], 11, "12:00 CET → 11:xx UTC")
    _assert_eq(r[1], 0, "12:00 CET → x:00 UTC")

    var r2 = local_to_utc(12, 0, "EST")
    _assert_eq(r2[0], 17, "12:00 EST → 17:xx UTC")
    print("  ✓ local_to_utc")


def test_utc_to_local() raises:
    var r = utc_to_local(12, 0, "JST")
    _assert_eq(r[0], 21, "12:00 UTC → 21:xx JST")
    _assert_eq(r[1], 0, "12:00 UTC → x:00 JST")
    print("  ✓ utc_to_local")


def test_overlap_hours() raises:
    var ov = overlap_hours("EST", "CET")
    _assert(ov >= 0 and ov <= 8, "EST/CET overlap in [0,8]")
    _assert_eq(ov, 2, "EST/CET overlap=2h")

    var ov2 = overlap_hours("UTC", "UTC")
    _assert_eq(ov2, 8, "same zone overlap=8h")
    print("  ✓ overlap_hours")


# ── Checksum Tests ───────────────────────────────────────────────────────────


def test_adler32() raises:
    var d0 = List[Int]()
    d0.append(0)
    _assert_eq(adler32(d0), 65537, "adler32([0])=65537")

    # adler32 of [1]: a=2, b=2 → (2<<16)|2 = 131074
    var d1 = List[Int]()
    d1.append(1)
    _assert_eq(adler32(d1), 131074, "adler32([1])=131074")

    # Empty
    var de = List[Int]()
    _assert_eq(adler32(de), 1, "adler32([])=1")
    print("  ✓ adler32")


def test_fletcher16() raises:
    var d = List[Int]()
    d.append(1); d.append(2)
    # sum1: 0+1=1, 1+2=3. sum2: 0+1=1, 1+3=4. Result=(4<<8)|3=1027
    _assert_eq(fletcher16(d), 1027, "fletcher16([1,2])=1027")

    var d2 = List[Int]()
    d2.append(0)
    # sum1=0, sum2=0 → 0
    _assert_eq(fletcher16(d2), 0, "fletcher16([0])=0")
    print("  ✓ fletcher16")


def test_luhn_check() raises:
    # 79927398713 is a well-known valid Luhn number
    var valid = List[Int]()
    valid.append(7); valid.append(9); valid.append(9); valid.append(2)
    valid.append(7); valid.append(3); valid.append(9); valid.append(8)
    valid.append(7); valid.append(1); valid.append(3)
    _assert(luhn_check(valid), "79927398713 is Luhn valid")

    # Alter one digit → invalid
    var invalid = List[Int]()
    invalid.append(7); invalid.append(9); invalid.append(9); invalid.append(2)
    invalid.append(7); invalid.append(3); invalid.append(9); invalid.append(8)
    invalid.append(7); invalid.append(1); invalid.append(4)
    _assert(not luhn_check(invalid), "79927398714 is Luhn invalid")
    print("  ✓ luhn_check")


def test_luhn_checksum() raises:
    # For 7992739871, check digit should be 3
    var d = List[Int]()
    d.append(7); d.append(9); d.append(9); d.append(2)
    d.append(7); d.append(3); d.append(9); d.append(8)
    d.append(7); d.append(1)
    _assert_eq(luhn_checksum(d), 3, "luhn_checksum for 7992739871 → 3")
    print("  ✓ luhn_checksum")


def test_isbn10() raises:
    # 0306406152 is a valid ISBN-10
    var d = List[Int]()
    d.append(0); d.append(3); d.append(0); d.append(6); d.append(4)
    d.append(0); d.append(6); d.append(1); d.append(5); d.append(2)
    _assert(isbn10_check(d), "0306406152 is valid ISBN-10")

    # Wrong check digit
    var d2 = List[Int]()
    d2.append(0); d2.append(3); d2.append(0); d2.append(6); d2.append(4)
    d2.append(0); d2.append(6); d2.append(1); d2.append(5); d2.append(3)
    _assert(not isbn10_check(d2), "0306406153 is invalid ISBN-10")

    # Wrong length
    var d3 = List[Int]()
    d3.append(1); d3.append(2); d3.append(3)
    _assert(not isbn10_check(d3), "length 3 is invalid ISBN-10")
    print("  ✓ isbn10_check")


def test_isbn13() raises:
    # 9780306406157 is a valid ISBN-13
    var d = List[Int]()
    d.append(9); d.append(7); d.append(8); d.append(0); d.append(3)
    d.append(0); d.append(6); d.append(4); d.append(0); d.append(6)
    d.append(1); d.append(5); d.append(7)
    _assert(isbn13_check(d), "9780306406157 is valid ISBN-13")

    # Wrong check digit
    var d2 = List[Int]()
    d2.append(9); d2.append(7); d2.append(8); d2.append(0); d2.append(3)
    d2.append(0); d2.append(6); d2.append(4); d2.append(0); d2.append(6)
    d2.append(1); d2.append(5); d2.append(8)
    _assert(not isbn13_check(d2), "9780306406158 is invalid ISBN-13")
    print("  ✓ isbn13_check")


def test_xor_checksum() raises:
    var d = List[Int]()
    d.append(0xFF); d.append(0xFF)
    _assert_eq(xor_checksum(d), 0, "xor([0xFF,0xFF])=0")

    var d2 = List[Int]()
    d2.append(0xAA); d2.append(0x55)
    _assert_eq(xor_checksum(d2), 0xFF, "xor([0xAA,0x55])=0xFF")

    var d3 = List[Int]()
    d3.append(0x12)
    _assert_eq(xor_checksum(d3), 0x12, "xor([0x12])=0x12")
    print("  ✓ xor_checksum")


def test_modular_sum() raises:
    var d = List[Int]()
    d.append(1); d.append(2); d.append(3)
    _assert_eq(modular_sum(d, 256), 6, "mod_sum([1,2,3],256)=6")

    var d2 = List[Int]()
    d2.append(200); d2.append(100)
    _assert_eq(modular_sum(d2, 256), 44, "mod_sum([200,100],256)=44")
    print("  ✓ modular_sum")


def test_parity_bit() raises:
    var d = List[Int]()
    d.append(1); d.append(0); d.append(1); d.append(1)
    _assert_eq(parity_bit(d), 1, "parity([1,0,1,1])=1")

    var d2 = List[Int]()
    d2.append(1); d2.append(0); d2.append(1); d2.append(0)
    _assert_eq(parity_bit(d2), 0, "parity([1,0,1,0])=0")

    var d3 = List[Int]()
    d3.append(0); d3.append(0)
    _assert_eq(parity_bit(d3), 0, "parity([0,0])=0")
    print("  ✓ parity_bit")


def test_internet_checksum() raises:
    var d = List[Int]()
    d.append(0x00); d.append(0x01); d.append(0x00); d.append(0x02)
    var ic = internet_checksum(d)
    # word1=1, word2=2, total=3, ~3 & 0xFFFF = 65532
    _assert_eq(ic, 65532, "internet_checksum([0,1,0,2])=65532")
    _assert(ic <= 65535, "internet_checksum fits in 16 bits")
    print("  ✓ internet_checksum")


def test_verhoeff() raises:
    # [0, 1] is a valid Verhoeff pair
    var v1 = List[Int]()
    v1.append(0); v1.append(1)
    _assert(verhoeff_check(v1), "verhoeff [0,1] valid")

    # [0, 2] is invalid
    var v2 = List[Int]()
    v2.append(0); v2.append(2)
    _assert(not verhoeff_check(v2), "verhoeff [0,2] invalid")

    # Empty is not valid
    var v3 = List[Int]()
    _assert(not verhoeff_check(v3), "verhoeff empty invalid")
    print("  ✓ verhoeff_check")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 45 Tests ===")

    print("\n── Linear Programming ──")
    test_objective_value()
    test_is_feasible()
    test_line_intersection()
    test_enumerate_vertices()
    test_lp_solve()
    test_dual_value()
    test_sensitivity()
    test_transportation()

    print("\n── Time Zones ──")
    test_utc_offset()
    test_convert_time()
    test_time_difference()
    test_is_valid_zone()
    test_is_dst()
    test_effective_offset()
    test_format_offset()
    test_local_to_utc()
    test_utc_to_local()
    test_overlap_hours()

    print("\n── Checksums ──")
    test_adler32()
    test_fletcher16()
    test_luhn_check()
    test_luhn_checksum()
    test_isbn10()
    test_isbn13()
    test_xor_checksum()
    test_modular_sum()
    test_parity_bit()
    test_internet_checksum()
    test_verhoeff()

    print("\n✅ All Wave 45 tests passed!")
