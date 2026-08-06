"""test_serialization_io.mojo — known-value tests for serialization_io.

Hand-computed exact tokens:
  0.5   = 1 * 2^-1              -> "1p-1"
  -2.75 = -(11 * 2^-2)          -> "-11p-2"
  0.25  = 1 * 2^-2              -> "1p-2"
  0.1 (nearest double) = 0x1.999999999999ap-4
      = 7205759403792794 * 2^-56 = 3602879701896397 * 2^-55
                                -> "3602879701896397p-55"
  max finite = (2^53 - 1) * 2^971 -> "9007199254740991p971"
  min subnormal = 2^-1074       -> "1p-1074"
  2^1023 = 1 * 2^1023           -> "1p1023" (odd m => e can exceed 971;
      domain is e >= -1074 and e + bitlen(m) <= 1024, i.e. value <= max finite)
  2^53 = 9007199254740992 (integer, plain digits)
  2^61 = 2305843009213693952 (integer, plain digits)
  2^62 -> "1p62" (plain-integer form capped below 2^62)
FNV-1a 64 test vectors (Noll): "" -> 0xCBF29CE484222325,
  "a" -> 0xAF63DC4C8601EC8C, "foobar" -> 0x85944171F73967E8.
"""
from serialization_io import (
    WeightsBundle,
    weights_to_string,
    weights_from_string,
    string_checksum,
)


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ serialization_io::" + name)
    else:
        failed += 1
        print("  ❌ serialization_io::" + name)


def _names1(a: String) -> List[String]:
    var out = List[String]()
    out.append(a)
    return out^


def _fold(h: UInt64) -> Float64:
    return Float64(Int((h >> 32) ^ (h & UInt64(0xFFFFFFFF))))


def _pos_inf() -> Float64:
    var big: Float64 = 1.0e308
    return big * 10.0


def _quiet_nan() -> Float64:
    var z: Float64 = 0.0
    return z / z


def _is_neg_zero(v: Float64) -> Bool:
    if v != 0.0:
        return False
    var one: Float64 = 1.0
    return one / v < 0.0


def _make_val(m: Int, e: Int) -> Float64:
    """m * 2^e via single exact power-of-two steps (independent of kernel)."""
    var v = Float64(m)
    if e > 0:
        for _ in range(e):
            v *= 2.0
    else:
        for _ in range(-e):
            v /= 2.0
    return v


def _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── exact token formatting: hand-computed strings ────────────────────────
    var a0 = List[Float64]()
    a0.append(0.5); a0.append(-2.75); a0.append(3.0)
    var arr0 = List[List[Float64]]()
    arr0.append(a0^)
    var s0 = weights_to_string(_names1("w"), arr0)
    check(
        s0 == String("v1|w|3|1p-1,-11p-2,3\n"),
        "weights_to_string exact tokens 0.5,-2.75,3.0",
        passed,
        failed,
    )

    var a1 = List[Float64]()
    a1.append(42.0); a1.append(1.0); a1.append(-1.0)
    var arr1 = List[List[Float64]]()
    arr1.append(a1^)
    check(
        weights_to_string(_names1("a"), arr1) == String("v1|a|3|42,1,-1\n"),
        "integers render as plain digits",
        passed,
        failed,
    )

    var a2 = List[Float64]()
    a2.append(0.1)
    var arr2 = List[List[Float64]]()
    arr2.append(a2^)
    check(
        weights_to_string(_names1("x"), arr2)
        == String("v1|x|1|3602879701896397p-55\n"),
        "0.1 exact significand token (hand-derived)",
        passed,
        failed,
    )

    var a3 = List[Float64]()
    a3.append(1.7976931348623157e308)
    var arr3 = List[List[Float64]]()
    arr3.append(a3^)
    check(
        weights_to_string(_names1("x"), arr3)
        == String("v1|x|1|9007199254740991p971\n"),
        "max finite double token (2^53-1)*2^971",
        passed,
        failed,
    )

    var tiny: Float64 = 1.0  # 2^-1074, built by exact halving
    for _ in range(1074):
        tiny /= 2.0
    var a4 = List[Float64]()
    a4.append(tiny)
    var arr4 = List[List[Float64]]()
    arr4.append(a4^)
    check(
        weights_to_string(_names1("x"), arr4) == String("v1|x|1|1p-1074\n"),
        "min subnormal 2^-1074 -> 1p-1074",
        passed,
        failed,
    )

    var a5 = List[Float64]()
    a5.append(0.0)
    var neg_zero: Float64 = 0.0
    neg_zero = -neg_zero
    a5.append(neg_zero)
    var arr5 = List[List[Float64]]()
    arr5.append(a5^)
    var s5 = weights_to_string(_names1("z"), arr5)
    check(
        s5 == String("v1|z|2|0,-0\n"),
        "signed zeros -> 0 and -0",
        passed,
        failed,
    )

    var a6 = List[Float64]()
    a6.append(_pos_inf()); a6.append(-_pos_inf()); a6.append(_quiet_nan())
    var arr6 = List[List[Float64]]()
    arr6.append(a6^)
    var s6 = weights_to_string(_names1("s"), arr6)
    check(
        s6 == String("v1|s|3|inf,-inf,nan\n"),
        "inf/-inf/nan tokens",
        passed,
        failed,
    )

    # Plain-integer boundary: 2^53 and 2^61 plain, 2^62 falls back to p-form.
    var a7 = List[Float64]()
    a7.append(9007199254740992.0)       # 2^53
    a7.append(2305843009213693952.0)    # 2^61
    a7.append(4611686018427387904.0)    # 2^62
    var arr7 = List[List[Float64]]()
    arr7.append(a7^)
    check(
        weights_to_string(_names1("p"), arr7)
        == String("v1|p|3|9007199254740992,2305843009213693952,1p62\n"),
        "plain-integer boundary at 2^62",
        passed,
        failed,
    )

    # ── round trip: exact bit-for-bit equality ───────────────────────────────
    var gnarly = List[Float64]()
    gnarly.append(0.1)
    gnarly.append(-0.1)
    gnarly.append(1.0 / 3.0)
    gnarly.append(3.141592653589793)
    gnarly.append(2.718281828459045e-10)
    gnarly.append(1.0e300)
    gnarly.append(-1.0e300)
    gnarly.append(1.0e-300)
    gnarly.append(123456.789)
    gnarly.append(6.02214076e23)
    gnarly.append(1.7976931348623157e308)
    gnarly.append(2.2250738585072014e-308)  # min normal
    gnarly.append(tiny)
    gnarly.append(-tiny)
    var garr = List[List[Float64]]()
    garr.append(gnarly.copy())
    var gs = weights_to_string(_names1("g"), garr)
    var gb = weights_from_string(gs)
    var rt_ok = gb.ok and len(gb.arrays) == 1 and len(gb.arrays[0]) == len(gnarly)
    if rt_ok:
        for i in range(len(gnarly)):
            if gb.arrays[0][i] != gnarly[i]:
                rt_ok = False
    check(
        rt_ok,
        "round trip exact: negatives, exponents, subnormals",
        passed,
        failed,
    )

    # Signed zero and specials survive the round trip.
    var zb = weights_from_string(s5)
    check(
        zb.ok
        and len(zb.arrays[0]) == 2
        and zb.arrays[0][0] == 0.0
        and not _is_neg_zero(zb.arrays[0][0])
        and _is_neg_zero(zb.arrays[0][1]),
        "round trip preserves +0 vs -0",
        passed,
        failed,
    )
    var sb = weights_from_string(s6)
    check(
        sb.ok
        and sb.arrays[0][0] == _pos_inf()
        and sb.arrays[0][1] == -_pos_inf()
        and sb.arrays[0][2] != sb.arrays[0][2],
        "round trip preserves inf/-inf/nan",
        passed,
        failed,
    )

    # ── multi-array payload, names/order, empty + all-equal arrays ──────────
    var names_m = List[String]()
    names_m.append(String("layer0"))
    names_m.append(String("bias"))
    names_m.append(String("ties"))
    var arr_m = List[List[Float64]]()
    var m0 = List[Float64]()
    m0.append(0.5); m0.append(0.25)
    arr_m.append(m0^)
    arr_m.append(List[Float64]())  # empty array
    var m2 = List[Float64]()
    m2.append(7.5); m2.append(7.5); m2.append(7.5)  # all-equal / ties
    arr_m.append(m2^)
    var sm = weights_to_string(names_m, arr_m)
    check(
        sm == String("v1|layer0|2|1p-1,1p-2\nv1|bias|0|\nv1|ties|3|15p-1,15p-1,15p-1\n"),
        "multi-line payload exact (incl empty + all-equal arrays)",
        passed,
        failed,
    )
    var bm = weights_from_string(sm)
    check(
        bm.ok
        and len(bm.names) == 3
        and bm.names[0] == String("layer0")
        and bm.names[1] == String("bias")
        and bm.names[2] == String("ties")
        and len(bm.arrays[0]) == 2
        and len(bm.arrays[1]) == 0
        and len(bm.arrays[2]) == 3
        and bm.arrays[0][0] == 0.5
        and bm.arrays[0][1] == 0.25
        and bm.arrays[2][0] == 7.5
        and bm.arrays[2][2] == 7.5,
        "multi-line parse: names, order, lengths, values",
        passed,
        failed,
    )

    # ── edge cases: empty inputs, mismatch, name sanitization, CRLF ─────────
    var be = weights_from_string(String(""))
    check(
        be.ok and len(be.names) == 0 and len(be.arrays) == 0,
        "empty string -> ok empty bundle",
        passed,
        failed,
    )
    var empty_names = List[String]()
    var empty_arrays = List[List[Float64]]()
    check(
        weights_to_string(empty_names, empty_arrays) == String(""),
        "no arrays -> empty string",
        passed,
        failed,
    )
    var one_name = _names1("a")
    check(
        weights_to_string(one_name, empty_arrays) == String(""),
        "names/arrays length mismatch -> empty string",
        passed,
        failed,
    )
    var abad = List[Float64]()
    abad.append(1.0)
    var arr_bad = List[List[Float64]]()
    arr_bad.append(abad^)
    var sbad = weights_to_string(_names1("a|b\nc"), arr_bad)
    var bbad = weights_from_string(sbad)
    check(
        sbad == String("v1|a_b_c|1|1\n")
        and bbad.ok
        and bbad.names[0] == String("a_b_c"),
        "name sanitization: '|' and newline -> '_'",
        passed,
        failed,
    )
    var bcrlf = weights_from_string(String("\nv1|w|1|5\r\n\n"))
    check(
        bcrlf.ok and len(bcrlf.arrays) == 1 and bcrlf.arrays[0][0] == 5.0,
        "CRLF + blank lines tolerated",
        passed,
        failed,
    )

    # ── strict rejection of corrupt payloads ─────────────────────────────────
    check(
        not weights_from_string(String("v2|w|1|1\n")).ok,
        "reject unknown version tag",
        passed,
        failed,
    )
    check(
        not weights_from_string(String("v1|w|2|1p-1\n")).ok
        and not weights_from_string(String("v1|w|1|1,2\n")).ok,
        "reject declared-length mismatch (both directions)",
        passed,
        failed,
    )
    check(
        not weights_from_string(String("v1|w|1|\n")).ok
        and not weights_from_string(String("v1|w|1|1,\n")).ok,
        "reject empty value token / trailing comma",
        passed,
        failed,
    )
    check(
        not weights_from_string(String("v1|w\n")).ok
        and not weights_from_string(String("junk\n")).ok
        and not weights_from_string(String("v1|w|x|1\n")).ok,
        "reject missing fields / junk / non-numeric length",
        passed,
        failed,
    )
    check(
        not weights_from_string(String("v1|w|1|1q3\n")).ok
        and not weights_from_string(String("v1|w|1|--5\n")).ok
        and not weights_from_string(String("v1|w|1|1p\n")).ok,
        "reject malformed tokens",
        passed,
        failed,
    )
    check(
        not weights_from_string(String("v1|w|1|1p1024\n")).ok  # 2^1024 overflows
        and not weights_from_string(String("v1|w|1|3p1023\n")).ok  # 1.5*2^1024
        and not weights_from_string(String("v1|w|1|9007199254740991p972\n")).ok
        and not weights_from_string(String("v1|w|1|1p-1075\n")).ok
        and not weights_from_string(String("v1|w|1|9007199254740992p0\n")).ok,
        "reject out-of-domain exponent / significand >= 2^53",
        passed,
        failed,
    )

    # High binade, short odd significand: e legitimately exceeds 971.
    # 2^972, 2^1000, 2^1023, 3*2^1022 are finite doubles; tokens 1p972,
    # 1p1000, 1p1023, 3p1022 must be emitted AND re-parsed bit-exactly.
    var hb = List[Float64]()
    hb.append(_make_val(1, 972))
    hb.append(_make_val(1, 1000))
    hb.append(_make_val(1, 1023))
    hb.append(_make_val(3, 1022))
    var hb_arr = List[List[Float64]]()
    hb_arr.append(hb.copy())
    var hs = weights_to_string(_names1("h"), hb_arr)
    var hbnd = weights_from_string(hs)
    var hb_ok = (
        hs == String("v1|h|4|1p972,1p1000,1p1023,3p1022\n")
        and hbnd.ok
        and len(hbnd.arrays) == 1
        and len(hbnd.arrays[0]) == 4
    )
    if hb_ok:
        for i in range(4):
            if hbnd.arrays[0][i] != hb[i]:
                hb_ok = False
    check(
        hb_ok,
        "e>971 with short odd significand: 2^1023 et al round-trip",
        passed,
        failed,
    )
    # Domain boundary from raw tokens: 1p1023 and max-finite accepted exactly.
    var bd = weights_from_string(String("v1|w|2|1p1023,9007199254740991p971\n"))
    check(
        bd.ok
        and bd.arrays[0][0] == _make_val(1, 1023)
        and bd.arrays[0][1] == 1.7976931348623157e308,
        "accept boundary tokens 1p1023 and 9007199254740991p971",
        passed,
        failed,
    )
    # A bad line poisons the whole bundle (no partial loads).
    var bpart = weights_from_string(String("v1|good|1|1\nv1|bad|1|zzz\n"))
    check(
        not bpart.ok and len(bpart.names) == 0 and len(bpart.arrays) == 0,
        "corrupt line -> ok=False and no partial data",
        passed,
        failed,
    )

    # ── string_checksum: FNV-1a 64 known vectors, folded ─────────────────────
    check(
        string_checksum(String("")) == _fold(UInt64(0xCBF29CE484222325)),
        "checksum('') == folded FNV offset basis",
        passed,
        failed,
    )
    check(
        string_checksum(String("a")) == _fold(UInt64(0xAF63DC4C8601EC8C)),
        "checksum('a') matches published FNV-1a vector",
        passed,
        failed,
    )
    check(
        string_checksum(String("foobar")) == _fold(UInt64(0x85944171F73967E8)),
        "checksum('foobar') matches published FNV-1a vector",
        passed,
        failed,
    )
    var c1 = string_checksum(gs)
    var c2 = string_checksum(gs)
    var c3 = string_checksum(gs + String(" "))
    check(
        c1 == c2 and c1 != c3,
        "checksum deterministic and tamper-sensitive",
        passed,
        failed,
    )
    check(
        c1 >= 0.0 and c1 < 4294967296.0 and c1 == Float64(Int(c1)),
        "checksum integer-valued in [0, 2^32)",
        passed,
        failed,
    )

    # ── seeded stress: 200 random doubles round-trip bit-exactly ─────────────
    var rng = UInt64(0x9E3779B97F4A7C15)
    var stress = List[Float64]()
    for t in range(200):
        rng = _xorshift64(rng)
        var b = Int(rng % UInt64(53)) + 1  # significand bit length in [1, 53]
        rng = _xorshift64(rng)
        var half = 1 << (b - 1)
        var m = Int(rng % UInt64(half)) + half  # b-bit significand
        m = m | 1  # odd; bit length unchanged (only bit 0 set)
        rng = _xorshift64(rng)
        var e = Int(rng % UInt64(2099 - b)) - 1074  # [-1074, 1024-b]: full domain
        var v = _make_val(m, e)
        if t % 2 == 1:
            v = -v
        stress.append(v)
    var sarr = List[List[Float64]]()
    sarr.append(stress.copy())
    var ss = weights_to_string(_names1("stress"), sarr)
    var sbnd = weights_from_string(ss)
    var n_exact = 0
    if sbnd.ok and len(sbnd.arrays) == 1 and len(sbnd.arrays[0]) == 200:
        for t in range(200):
            if sbnd.arrays[0][t] == stress[t]:
                n_exact += 1
    check(
        n_exact == 200,
        "200 seeded random doubles (full m/e domain) round-trip exact",
        passed,
        failed,
    )

    print("  [serialization_io] Passed:", passed, "Failed:", failed)
