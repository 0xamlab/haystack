"""test_canonical_encode.mojo — known-value tests for canonical encoding.

Hand-written. Every assertion here pins a decision that, if it drifted, would make
two semantically equal values hash differently — the failure this encoding exists to
prevent. Expected byte strings are written out explicitly rather than computed, so a
change to the encoder shows up as a diff instead of quietly agreeing with itself.
"""
from canonical.encode import (
    CANONICAL_NAN_BITS,
    byte_order_less,
    encoding_version,
    sort_keys,
    to_hex,
    write_array_header,
    write_bool,
    write_float,
    write_float_list,
    write_int,
    write_null,
    write_object_header,
    write_string,
    write_varint,
    zigzag,
)
from canonical.from_json import transcode
from canonical.hash import (
    digest_encoding_version,
    digest_matches_encoding,
    hash_canonical_bytes,
    versioned_digest,
)


fn _hex_of_float(value: Float64) -> String:
    var out = List[UInt8]()
    write_float(out, value)
    return to_hex(out)


fn _hex_of_int(value: Int) -> String:
    var out = List[UInt8]()
    write_int(out, value)
    return to_hex(out)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── zigzag gives one short encoding per signed value ─────────────────────
    if zigzag(0) == 0 and zigzag(-1) == 1 and zigzag(1) == 2 and zigzag(-2) == 3:
        passed += 1
        print("  ✅ zigzag maps 0,-1,1,-2 -> 0,1,2,3")
    else:
        failed += 1
        print("  ❌ zigzag wrong:", zigzag(0), zigzag(-1), zigzag(1), zigzag(-2))

    # ── varint is LEB128, one encoding per value ─────────────────────────────
    var v = List[UInt8]()
    write_varint(v, 0)
    write_varint(v, 127)
    write_varint(v, 128)
    write_varint(v, 300)
    if to_hex(v) == "007f8001ac02":
        passed += 1
        print("  ✅ varint 0/127/128/300 -> 00 7f 8001 ac02")
    else:
        failed += 1
        print("  ❌ varint wrong:", to_hex(v))

    # ── scalars carry their tag ─────────────────────────────────────────────
    var scalars = List[UInt8]()
    write_null(scalars)
    write_bool(scalars, False)
    write_bool(scalars, True)
    if to_hex(scalars) == "000102":
        passed += 1
        print("  ✅ null/false/true tags are 00/01/02")
    else:
        failed += 1
        print("  ❌ scalar tags wrong:", to_hex(scalars))

    # ── ints: tag 03 then zigzag varint ─────────────────────────────────────
    if _hex_of_int(0) == "0300" and _hex_of_int(-1) == "0301" and _hex_of_int(1) == "0302":
        passed += 1
        print("  ✅ int encoding is tag 03 + zigzag varint")
    else:
        failed += 1
        print("  ❌ int wrong:", _hex_of_int(0), _hex_of_int(-1), _hex_of_int(1))

    # ── floats are IEEE-754 big-endian, so 1.0 is not "1" ───────────────────
    # 1.0 = 0x3FF0000000000000. This is the exact case where JSON diverges between
    # Python ("1.0") and JavaScript ("1").
    if _hex_of_float(1.0) == "043ff0000000000000":
        passed += 1
        print("  ✅ 1.0 encodes as its IEEE-754 bits, not as text")
    else:
        failed += 1
        print("  ❌ float encoding wrong:", _hex_of_float(1.0))

    # ── -0.0 and +0.0 encode identically ────────────────────────────────────
    if _hex_of_float(-0.0) == _hex_of_float(0.0) and _hex_of_float(0.0) == (
        "040000000000000000"
    ):
        passed += 1
        print("  ✅ -0.0 normalises to +0.0 (equal values must hash equal)")
    else:
        failed += 1
        print("  ❌ negative zero not normalised:", _hex_of_float(-0.0))

    # ── every NaN collapses to one pattern ──────────────────────────────────
    var nan_a = Float64(0.0) / Float64(0.0)
    var nan_b = Float64("inf") - Float64("inf")
    var expected_nan = String("04") + to_hex(_nan_bytes())
    if _hex_of_float(nan_a) == expected_nan and _hex_of_float(nan_b) == expected_nan:
        passed += 1
        print("  ✅ all NaNs collapse to the one canonical pattern")
    else:
        failed += 1
        print("  ❌ NaN not canonicalised:", _hex_of_float(nan_a), _hex_of_float(nan_b))

    # ── strings are length-prefixed, so no delimiter escaping is involved ────
    var s = List[UInt8]()
    write_string(s, "ab")
    if to_hex(s) == "05026162":
        passed += 1
        print("  ✅ string is tag 05 + length + UTF-8 bytes")
    else:
        failed += 1
        print("  ❌ string wrong:", to_hex(s))

    # ── containers carry explicit counts ────────────────────────────────────
    var arr = List[UInt8]()
    write_array_header(arr, 2)
    write_int(arr, 7)
    write_int(arr, 8)
    if to_hex(arr) == "060203" + "0e" + "03" + "10":
        passed += 1
        print("  ✅ array is tag 06 + count + values")
    else:
        failed += 1
        print("  ❌ array wrong:", to_hex(arr))

    var obj = List[UInt8]()
    write_object_header(obj, 1)
    write_string(obj, "k")
    write_int(obj, 1)
    if to_hex(obj) == "0701" + "05016b" + "0302":
        passed += 1
        print("  ✅ object is tag 07 + pair count + sorted pairs")
    else:
        failed += 1
        print("  ❌ object wrong:", to_hex(obj))

    # ── key ordering is by UTF-8 bytes, not locale or insertion ─────────────
    if (
        byte_order_less("a", "b")
        and not byte_order_less("b", "a")
        and byte_order_less("a", "aa")
        and not byte_order_less("a", "a")
        and byte_order_less("Z", "a")  # uppercase sorts first by byte value
    ):
        passed += 1
        print("  ✅ byte-order comparison, including 'Z' < 'a'")
    else:
        failed += 1
        print("  ❌ byte ordering wrong")

    var unsorted = List[String]()
    unsorted.append("beta")
    unsorted.append("Alpha")
    unsorted.append("alpha")
    var ordered = sort_keys(unsorted)
    if ordered[0] == "Alpha" and ordered[1] == "alpha" and ordered[2] == "beta":
        passed += 1
        print("  ✅ sort_keys puts keys in canonical byte order")
    else:
        failed += 1
        print("  ❌ sort wrong:", ordered[0], ordered[1], ordered[2])

    # ── the same logical value always produces the same bytes ───────────────
    var first = List[Float64]()
    first.append(1.5)
    first.append(-2.5)
    var second = List[Float64]()
    second.append(1.5)
    second.append(-2.5)
    var enc_a = List[UInt8]()
    var enc_b = List[UInt8]()
    write_float_list(enc_a, first)
    write_float_list(enc_b, second)
    if to_hex(enc_a) == to_hex(enc_b) and len(enc_a) > 0:
        passed += 1
        print("  ✅ equal float lists encode to identical bytes")
    else:
        failed += 1
        print("  ❌ encoding not deterministic")

    # ── a different value produces different bytes ──────────────────────────
    var third = List[Float64]()
    third.append(1.5)
    third.append(-2.6)
    var enc_c = List[UInt8]()
    write_float_list(enc_c, third)
    if to_hex(enc_a) != to_hex(enc_c):
        passed += 1
        print("  ✅ a changed value changes the encoding")
    else:
        failed += 1
        print("  ❌ distinct values collided")

    # ── hashing is stable, and distinct inputs differ ───────────────────────
    var h1 = hash_canonical_bytes(enc_a)
    var h2 = hash_canonical_bytes(enc_b)
    var h3 = hash_canonical_bytes(enc_c)
    if len(h1) == 64 and h1 == h2 and h1 != h3:
        passed += 1
        print("  ✅ digest stable for equal input, different for changed input")
    else:
        failed += 1
        print("  ❌ hashing wrong:", h1, h3)

    # ── versioned digests carry their encoding rules ────────────────────────
    var vd = versioned_digest(enc_a)
    if (
        digest_encoding_version(vd) == encoding_version()
        and digest_matches_encoding(vd)
        and not digest_matches_encoding("algenta-canonical/v0:" + h1)
        and digest_encoding_version(h1) == ""
    ):
        passed += 1
        print("  ✅ versioned digest identifies its encoding; a stale one is detectable")
    else:
        failed += 1
        print("  ❌ digest versioning wrong:", vd)

    # ── transcoding: JSON text stops mattering ───────────────────────────────
    # The whole reason this exists: two producers serialising the same value must
    # agree, and they do not agree on text.
    var t_plain = transcode('{"a":1,"b":2}')
    var t_reordered = transcode('{"b":2,"a":1}')
    var t_spaced = transcode('{ "a" : 1 , "b" : 2 }')
    if to_hex(t_plain) == to_hex(t_reordered) and to_hex(t_plain) == to_hex(t_spaced):
        passed += 1
        print("  ✅ key order and whitespace do not change the canonical bytes")
    else:
        failed += 1
        print("  ❌ transcode not canonical:", to_hex(t_plain), to_hex(t_reordered))

    # ── a changed value still changes the bytes ──────────────────────────────
    if to_hex(transcode('{"a":1}')) != to_hex(transcode('{"a":2}')):
        passed += 1
        print("  ✅ a changed value changes the canonical bytes")
    else:
        failed += 1
        print("  ❌ distinct documents collided")

    # ── number formatting is normalised, but int vs float is preserved ───────
    if (
        to_hex(transcode("[1.0]")) == to_hex(transcode("[1.00]"))
        and to_hex(transcode("[1]")) != to_hex(transcode("[1.0]"))
    ):
        passed += 1
        print("  ✅ 1.0 == 1.00, and 1 stays distinct from 1.0")
    else:
        failed += 1
        print("  ❌ number normalisation wrong")

    # ── nesting, and mixed types, round-trip deterministically ──────────────
    var nested = '{"outer":{"inner":[1,2.5,"x",true,null]},"z":[]}'
    if to_hex(transcode(nested)) == to_hex(transcode(nested)) and len(
        transcode(nested)
    ) > 0:
        passed += 1
        print("  ✅ nested mixed-type documents transcode deterministically")
    else:
        failed += 1
        print("  ❌ nested transcode unstable")

    # ── invalid tokens are refused, not silently read as 0 ──────────────────
    # Regression: `[a]` and `[b]` both parsed as `[0]`, so two different malformed
    # documents hashed identically — a canonical encoder must not agree on garbage.
    var refused = 0
    try:
        _ = transcode("[a]")
    except:
        refused += 1
    try:
        _ = transcode("[b]")
    except:
        refused += 1
    if refused == 2:
        passed += 1
        print("  ✅ non-numeric tokens are refused rather than read as 0")
    else:
        failed += 1
        print("  ❌ invalid tokens accepted")

    # ── escaped strings decode before encoding, so form does not leak ────────
    if to_hex(transcode('["a\\nb"]')) != to_hex(transcode('["a\\\\nb"]')):
        passed += 1
        print("  ✅ an escape and its literal spelling stay distinct")
    else:
        failed += 1
        print("  ❌ escape handling collapsed distinct strings")

    print("  [canonical.encode] Passed:", passed, "Failed:", failed)


fn _nan_bytes() -> List[UInt8]:
    """The canonical NaN pattern as 8 big-endian bytes."""
    var out = List[UInt8]()
    for shift in range(7, -1, -1):
        out.append(UInt8((CANONICAL_NAN_BITS >> (shift * 8)) & 0xFF))
    return out^
