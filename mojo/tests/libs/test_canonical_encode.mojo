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

    # ── the ASCII encoding is pinned, because it is already shipping ─────────
    # Every hash ever produced depends on these exact bytes, so they are written out
    # rather than compared against the encoder's own opinion.
    if to_hex(transcode('{"a":1,"b":2}')) == "0702" + "050161" + "0302" + "050162" + "0304":
        passed += 1
        print("  ✅ ASCII object bytes unchanged (07 count, sorted key/value pairs)")
    else:
        failed += 1
        print("  ❌ ASCII encoding drifted:", to_hex(transcode('{"a":1,"b":2}')))

    # ── \uXXXX must NOT collapse to the literal text of its own escape ───────
    # Live plan_hash COLLISION, fixed here: the decoder emitted the `u` after the
    # backslash and let the hex digits through as text, so `ñ` and the ASCII string
    # `u00f1` produced identical canonical bytes. Two plans naming DIFFERENT columns
    # ("año" vs "au00f1o") shared one plan_hash and returned different results.
    var escaped_nlike = to_hex(transcode('["a\\u00f1o"]'))
    var literal_ulike = to_hex(transcode('["au00f1o"]'))
    if escaped_nlike != literal_ulike:
        passed += 1
        print("  ✅ 'año' and the ASCII text 'au00f1o' hash differently")
    else:
        failed += 1
        print("  ❌ \\u escape collides with its own literal spelling:", escaped_nlike)

    # Same collision as it reached a join prefix: "café." vs "cafu00e9.".
    if to_hex(transcode('{"prefix":"caf\\u00e9."}')) != to_hex(
        transcode('{"prefix":"cafu00e9."}')
    ):
        passed += 1
        print("  ✅ join prefix 'café.' and 'cafu00e9.' hash differently")
    else:
        failed += 1
        print("  ❌ join prefix collision persists")

    # ── the other side of the coin: escaped and literal SAME value hash same ─
    # This is the actual canonicalisation requirement. Python's json.dumps escapes
    # non-ASCII by default and JavaScript's JSON.stringify does not, so the two
    # producers must agree.
    if (
        to_hex(transcode('["\\u00f1"]')) == to_hex(transcode('["ñ"]'))
        and to_hex(transcode('["\\u00f1"]')) == "0601" + "0502c3b1"
    ):
        passed += 1
        print("  ✅ \\u00f1 and a literal ñ are one value, encoded as UTF-8 c3b1")
    else:
        failed += 1
        print("  ❌ escaped/literal ñ disagree:", to_hex(transcode('["\\u00f1"]')))

    # ── a surrogate pair is ONE code point, not two halves ──────────────────
    # 😀 is U+1F600, whose UTF-8 is the four bytes f0 9f 98 80.
    var pair = to_hex(transcode('["\\ud83d\\ude00"]'))
    if pair == "0601" + "0504f09f9880" and pair == to_hex(transcode('["😀"]')):
        passed += 1
        print("  ✅ \\uD83D\\uDE00 decodes to the one code point U+1F600")
    else:
        failed += 1
        print("  ❌ surrogate pair mishandled:", pair)

    # Case of the hex digits is not part of the value.
    if to_hex(transcode('["\\uD83D\\uDE00"]')) == pair:
        passed += 1
        print("  ✅ \\uXXXX hex digits are case-insensitive")
    else:
        failed += 1
        print("  ❌ hex case changed the value:", to_hex(transcode('["\\uD83D\\uDE00"]')))

    # ── raw UTF-8 survives byte for byte ────────────────────────────────────
    # `chr(Int(byte))` rebuilding turned región (7 bytes) into regiÃ³n (9); these
    # expected byte strings are the UTF-8 of each name and nothing else.
    if (
        to_hex(transcode('["región"]')) == "0601" + "0507" + "72656769c3b36e"
        and to_hex(transcode('["café"]')) == "0601" + "0505" + "636166c3a9"
        and to_hex(transcode('["売上"]')) == "0601" + "0506" + "e5a3b2e4b88a"
    ):
        passed += 1
        print("  ✅ región / café / 売上 encode as their exact UTF-8 bytes")
    else:
        failed += 1
        print(
            "  ❌ non-ASCII bytes corrupted:",
            to_hex(transcode('["región"]')),
            to_hex(transcode('["café"]')),
            to_hex(transcode('["売上"]')),
        )

    # ── the standard escapes, including a NUL byte ─────
    if (
        to_hex(transcode('["\\u0041"]')) == to_hex(transcode('["A"]'))
        and to_hex(transcode('["\\/"]')) == to_hex(transcode('["/"]'))
        and to_hex(transcode('["\\u0000"]')) == "0601" + "050100"
        and to_hex(transcode('["\\t"]')) == "0601" + "050109"
        and to_hex(transcode('["\\""]')) == "0601" + "050122"
    ):
        passed += 1
        print("  ✅ \\u0041/\\/ match their literals; \\u0000 and \\t are single bytes")
    else:
        failed += 1
        print("  ❌ standard escape decoding wrong:", to_hex(transcode('["\\u0000"]')))

    # ── malformed input is refused, never given a canonical form ────────────
    # `[t]` did not merely mis-encode: `skip_json_value` returns pos+4 for any token
    # starting with `t`, so the slice read past the end of the document and CRASHED
    # the process — uncatchable, taking the worker with it. Reaching the print below
    # at all is the regression test.
    var rejected = 0
    var malformed = List[String]()
    malformed.append("[t]")  # truncated literal, formerly an out-of-bounds read
    malformed.append("[tr]")
    malformed.append("[nul]")
    malformed.append('["ab')  # unterminated string
    malformed.append('["ab\\')  # ends in a backslash
    malformed.append("{a:1}")  # unquoted key
    malformed.append('["\\q"]')  # not a JSON escape
    malformed.append('["\\u00f"]')  # \u with three hex digits
    malformed.append('["\\uzzzz"]')  # \u with no hex digits
    for i in range(len(malformed)):
        try:
            _ = transcode(malformed[i])
        except:
            rejected += 1
    if rejected == len(malformed):
        passed += 1
        print("  ✅ malformed documents are refused, not canonicalised (no crash)")
    else:
        failed += 1
        print("  ❌ malformed documents accepted:", rejected, "of", len(malformed))

    # A valid literal still encodes, so the check above did not just refuse everything.
    if to_hex(transcode("[true,false,null]")) == "0603" + "02" + "01" + "00":
        passed += 1
        print("  ✅ true/false/null still encode as 02/01/00")
    else:
        failed += 1
        print("  ❌ literal encoding broken:", to_hex(transcode("[true,false,null]")))

    print("  [canonical.encode] Passed:", passed, "Failed:", failed)


fn _nan_bytes() -> List[UInt8]:
    """The canonical NaN pattern as 8 big-endian bytes."""
    var out = List[UInt8]()
    for shift in range(7, -1, -1):
        out.append(UInt8((CANONICAL_NAN_BITS >> (shift * 8)) & 0xFF))
    return out^
