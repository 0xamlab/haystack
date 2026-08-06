"""Tests for Wave 41 — Trie, Protocol Buffers, Special Functions."""

from trie import (
    Trie,
    trie_create,
    trie_insert,
    trie_search,
    trie_starts_with,
    trie_count_words,
    trie_count_nodes,
    trie_word_list,
    trie_prefix_count,
)
from protocol import (
    encode_varint,
    decode_varint,
    zigzag_encode,
    zigzag_decode,
    encode_field,
    decode_field,
    encode_string_field,
    decode_string_field,
    encode_message,
    decode_message,
)
from special_functions import (
    gamma_function,
    log_gamma,
    beta_function,
    digamma,
    incomplete_gamma_lower,
    regularized_gamma,
    erf,
    erfc,
    bessel_j0,
    factorial_float,
    double_factorial,
    binomial_coefficient,
)
from std.math import abs as fabs, sqrt, exp


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Trie tests ────────────────────────────────────────────────────────────────


def test_trie() raises:
    print("── Trie tests ──")
    var n_pass: Int = 0

    # 1: Empty trie has 1 node (root)
    var t = trie_create()
    _assert_eq(trie_count_nodes(t), 1, "empty trie has 1 node")
    n_pass += 1

    # 2: Empty trie has 0 words
    _assert_eq(trie_count_words(t), 0, "empty trie has 0 words")
    n_pass += 1

    # 3: Insert and search "hello"
    trie_insert(t, "hello")
    _assert(trie_search(t, "hello"), "search finds 'hello'")
    n_pass += 1

    # 4: Search for non-inserted word → False
    _assert(not trie_search(t, "world"), "search 'world' → False")
    n_pass += 1

    # 5: Partial word not found
    _assert(not trie_search(t, "hell"), "search partial 'hell' → False")
    n_pass += 1

    # 6: starts_with "hel"
    _assert(trie_starts_with(t, "hel"), "starts_with 'hel' → True")
    n_pass += 1

    # 7: starts_with "hello"
    _assert(trie_starts_with(t, "hello"), "starts_with 'hello' → True")
    n_pass += 1

    # 8: starts_with "xyz" → False
    _assert(not trie_starts_with(t, "xyz"), "starts_with 'xyz' → False")
    n_pass += 1

    # 9: Count words after 1 insert
    _assert_eq(trie_count_words(t), 1, "count_words == 1")
    n_pass += 1

    # 10: Insert more words
    trie_insert(t, "help")
    trie_insert(t, "heap")
    _assert_eq(trie_count_words(t), 3, "count_words == 3 after 3 inserts")
    n_pass += 1

    # 11: Search each word
    _assert(trie_search(t, "help"), "search 'help'")
    n_pass += 1

    # 12:
    _assert(trie_search(t, "heap"), "search 'heap'")
    n_pass += 1

    # 13: prefix_count "hel" → 2 (hello, help)
    _assert_eq(trie_prefix_count(t, "hel"), 2, "prefix_count 'hel' == 2")
    n_pass += 1

    # 14: prefix_count "he" → 3 (hello, help, heap)
    _assert_eq(trie_prefix_count(t, "he"), 3, "prefix_count 'he' == 3")
    n_pass += 1

    # 15: prefix_count "z" → 0
    _assert_eq(trie_prefix_count(t, "z"), 0, "prefix_count 'z' == 0")
    n_pass += 1

    # 16: word_list returns all words
    var words = trie_word_list(t)
    _assert_eq(len(words), 3, "word_list has 3 words")
    n_pass += 1

    # 17: Nodes count > 1
    _assert(trie_count_nodes(t) > 1, "multiple nodes after inserts")
    n_pass += 1

    # 18: Insert duplicate doesn't add extra word
    trie_insert(t, "hello")
    _assert_eq(trie_count_words(t), 3, "duplicate insert doesn't add word")
    n_pass += 1

    # 19: Empty string prefix counts all
    _assert_eq(trie_prefix_count(t, ""), 3, "empty prefix counts all words")
    n_pass += 1

    print("  ✓ " + String(n_pass) + " trie assertions passed")


# ── Protocol tests ────────────────────────────────────────────────────────────


def test_protocol() raises:
    print("── Protocol Buffer tests ──")
    var n_pass: Int = 0

    # 20: encode_varint(0) == [0]
    var v0 = encode_varint(0)
    _assert_eq(len(v0), 1, "varint(0) len == 1")
    n_pass += 1

    # 21:
    _assert_eq(v0[0], 0, "varint(0)[0] == 0")
    n_pass += 1

    # 22: encode_varint(1) == [1]
    var v1 = encode_varint(1)
    _assert_eq(v1[0], 1, "varint(1)[0] == 1")
    n_pass += 1

    # 23: encode_varint(127) == [127]
    var v127 = encode_varint(127)
    _assert_eq(len(v127), 1, "varint(127) is 1 byte")
    n_pass += 1

    # 24: encode_varint(128) == [128, 1]
    var v128 = encode_varint(128)
    _assert_eq(len(v128), 2, "varint(128) is 2 bytes")
    n_pass += 1

    # 25:
    _assert_eq(v128[0], 128, "varint(128)[0] == 128")
    n_pass += 1

    # 26:
    _assert_eq(v128[1], 1, "varint(128)[1] == 1")
    n_pass += 1

    # 27: encode_varint(300) == [172, 2]
    var v300 = encode_varint(300)
    _assert_eq(v300[0], 172, "varint(300)[0] == 172")
    n_pass += 1

    # 28:
    _assert_eq(v300[1], 2, "varint(300)[1] == 2")
    n_pass += 1

    # 29: decode_varint roundtrip
    var dec = decode_varint(v300, 0)
    _assert_eq(dec[0], 300, "decode_varint(encode_varint(300)) == 300")
    n_pass += 1

    # 30: decode consumed 2 bytes
    _assert_eq(dec[1], 2, "decode_varint consumed 2 bytes")
    n_pass += 1

    # 31: Roundtrip for large value
    var v10000 = encode_varint(10000)
    var dec10k = decode_varint(v10000, 0)
    _assert_eq(dec10k[0], 10000, "varint roundtrip 10000")
    n_pass += 1

    # 32: zigzag_encode(0) == 0
    _assert_eq(zigzag_encode(0), 0, "zigzag(0) == 0")
    n_pass += 1

    # 33: zigzag_encode(-1) == 1
    _assert_eq(zigzag_encode(-1), 1, "zigzag(-1) == 1")
    n_pass += 1

    # 34: zigzag_encode(1) == 2
    _assert_eq(zigzag_encode(1), 2, "zigzag(1) == 2")
    n_pass += 1

    # 35: zigzag_encode(-2) == 3
    _assert_eq(zigzag_encode(-2), 3, "zigzag(-2) == 3")
    n_pass += 1

    # 36: zigzag_decode(zigzag_encode(42)) == 42
    _assert_eq(zigzag_decode(zigzag_encode(42)), 42, "zigzag roundtrip 42")
    n_pass += 1

    # 37: zigzag_decode(zigzag_encode(-99)) == -99
    _assert_eq(zigzag_decode(zigzag_encode(-99)), -99, "zigzag roundtrip -99")
    n_pass += 1

    # 38: encode_field then decode_field roundtrip
    var field_enc = encode_field(1, 0, 150)
    var field_dec = decode_field(field_enc, 0)
    _assert_eq(field_dec[0], 1, "field decode: field_number == 1")
    n_pass += 1

    # 39:
    _assert_eq(field_dec[1], 0, "field decode: wire_type == 0")
    n_pass += 1

    # 40:
    _assert_eq(field_dec[2], 150, "field decode: value == 150")
    n_pass += 1

    # 41: encode_message then decode_message roundtrip
    var fields = List[List[Int]]()
    var f1 = List[Int]()
    f1.append(1)
    f1.append(100)
    fields.append(f1^)
    var f2 = List[Int]()
    f2.append(2)
    f2.append(200)
    fields.append(f2^)
    var msg_enc = encode_message(fields)
    var msg_dec = decode_message(msg_enc)
    _assert_eq(len(msg_dec), 2, "decode_message returns 2 fields")
    n_pass += 1

    # 42:
    _assert_eq(msg_dec[0][0], 1, "msg field 1 number == 1")
    n_pass += 1

    # 43:
    _assert_eq(msg_dec[0][2], 100, "msg field 1 value == 100")
    n_pass += 1

    # 44:
    _assert_eq(msg_dec[1][0], 2, "msg field 2 number == 2")
    n_pass += 1

    # 45:
    _assert_eq(msg_dec[1][2], 200, "msg field 2 value == 200")
    n_pass += 1

    # 46: encode_string_field + decode_string_field
    var str_enc = encode_string_field(3, "hi")
    var str_dec = decode_string_field(str_enc, 0)
    _assert_eq(str_dec[0], 3, "string field number == 3")
    n_pass += 1

    # 47:
    _assert_eq(str_dec[2], 2, "string length == 2")
    n_pass += 1

    print("  ✓ " + String(n_pass) + " protocol assertions passed")


# ── Special functions tests ───────────────────────────────────────────────────


def test_special_functions() raises:
    print("── Special Functions tests ──")
    var n_pass: Int = 0

    # 48: gamma(1) == 1.0  (0! = 1)
    _assert_close(gamma_function(1.0), 1.0, 1e-8, "gamma(1) == 1")
    n_pass += 1

    # 49: gamma(5) == 24.0  (4! = 24)
    _assert_close(gamma_function(5.0), 24.0, 1e-6, "gamma(5) == 24")
    n_pass += 1

    # 50: gamma(0.5) ≈ √π ≈ 1.7724538509
    _assert_close(gamma_function(0.5), 1.7724538509, 1e-6, "gamma(0.5) ≈ √π")
    n_pass += 1

    # 51: gamma(2) == 1.0  (1! = 1)
    _assert_close(gamma_function(2.0), 1.0, 1e-8, "gamma(2) == 1")
    n_pass += 1

    # 52: gamma(3) == 2.0  (2! = 2)
    _assert_close(gamma_function(3.0), 2.0, 1e-8, "gamma(3) == 2")
    n_pass += 1

    # 53: beta(1, 1) == 1.0
    _assert_close(beta_function(1.0, 1.0), 1.0, 1e-8, "beta(1,1) == 1")
    n_pass += 1

    # 54: beta(2, 3) == 1/12 ≈ 0.08333
    _assert_close(beta_function(2.0, 3.0), 1.0 / 12.0, 1e-8, "beta(2,3) == 1/12")
    n_pass += 1

    # 55: beta(0.5, 0.5) == π
    _assert_close(beta_function(0.5, 0.5), 3.14159265359, 1e-5, "beta(0.5,0.5) ≈ π")
    n_pass += 1

    # 56: log_gamma(1) == 0.0
    _assert_close(log_gamma(1.0), 0.0, 1e-8, "log_gamma(1) == 0")
    n_pass += 1

    # 57: log_gamma(5) ≈ ln(24) ≈ 3.17805
    _assert_close(log_gamma(5.0), 3.17805383035, 1e-6, "log_gamma(5) ≈ ln(24)")
    n_pass += 1

    # 58: erf(0) == 0.0
    _assert_close(erf(0.0), 0.0, 1e-8, "erf(0) == 0")
    n_pass += 1

    # 59: erf(large) ≈ 1.0
    _assert_close(erf(5.0), 1.0, 1e-6, "erf(5) ≈ 1.0")
    n_pass += 1

    # 60: erf(-large) ≈ -1.0
    _assert_close(erf(-5.0), -1.0, 1e-6, "erf(-5) ≈ -1.0")
    n_pass += 1

    # 61: erfc(0) == 1.0
    _assert_close(erfc(0.0), 1.0, 1e-8, "erfc(0) == 1")
    n_pass += 1

    # 62: erfc(large) ≈ 0.0
    _assert_close(erfc(5.0), 0.0, 1e-6, "erfc(5) ≈ 0")
    n_pass += 1

    # 63: erf(1) ≈ 0.8427
    _assert_close(erf(1.0), 0.8427, 1e-3, "erf(1) ≈ 0.8427")
    n_pass += 1

    # 64: bessel_j0(0) == 1.0
    _assert_close(bessel_j0(0.0), 1.0, 1e-8, "bessel_j0(0) == 1")
    n_pass += 1

    # 65: bessel_j0(2.4048) ≈ 0 (first zero)
    _assert_close(bessel_j0(2.4048), 0.0, 1e-3, "bessel_j0(2.4048) ≈ 0")
    n_pass += 1

    # 66: factorial_float(0) == 1.0
    _assert_close(factorial_float(0), 1.0, 1e-8, "0! == 1")
    n_pass += 1

    # 67: factorial_float(1) == 1.0
    _assert_close(factorial_float(1), 1.0, 1e-8, "1! == 1")
    n_pass += 1

    # 68: factorial_float(5) == 120.0
    _assert_close(factorial_float(5), 120.0, 1e-8, "5! == 120")
    n_pass += 1

    # 69: factorial_float(10) == 3628800.0
    _assert_close(factorial_float(10), 3628800.0, 1e-5, "10! == 3628800")
    n_pass += 1

    # 70: double_factorial(5) == 15  (5*3*1)
    _assert_close(double_factorial(5), 15.0, 1e-8, "5!! == 15")
    n_pass += 1

    # 71: double_factorial(6) == 48  (6*4*2)
    _assert_close(double_factorial(6), 48.0, 1e-8, "6!! == 48")
    n_pass += 1

    # 72: double_factorial(0) == 1
    _assert_close(double_factorial(0), 1.0, 1e-8, "0!! == 1")
    n_pass += 1

    # 73: binomial_coefficient(10, 5) == 252
    _assert_close(binomial_coefficient(10, 5), 252.0, 1e-6, "C(10,5) == 252")
    n_pass += 1

    # 74: binomial_coefficient(10, 0) == 1
    _assert_close(binomial_coefficient(10, 0), 1.0, 1e-8, "C(10,0) == 1")
    n_pass += 1

    # 75: binomial_coefficient(10, 10) == 1
    _assert_close(binomial_coefficient(10, 10), 1.0, 1e-8, "C(10,10) == 1")
    n_pass += 1

    # 76: binomial_coefficient(6, 2) == 15
    _assert_close(binomial_coefficient(6, 2), 15.0, 1e-6, "C(6,2) == 15")
    n_pass += 1

    # 77: digamma(1) ≈ -0.5772 (Euler-Mascheroni)
    _assert_close(digamma(1.0), -0.5772156649, 1e-4, "digamma(1) ≈ -γ")
    n_pass += 1

    # 78: digamma(2) ≈ 0.4228 (1 - γ)
    _assert_close(digamma(2.0), 0.4227843351, 1e-4, "digamma(2) ≈ 1 - γ")
    n_pass += 1

    # 79: regularized_gamma(1, 1) ≈ 1 - e^(-1) ≈ 0.6321
    _assert_close(regularized_gamma(1.0, 1.0), 0.6321, 1e-3, "P(1,1) ≈ 0.6321")
    n_pass += 1

    # 80: regularized_gamma(1, 0) == 0
    _assert_close(regularized_gamma(1.0, 0.0), 0.0, 1e-8, "P(1,0) == 0")
    n_pass += 1

    # 81: incomplete_gamma_lower(1, 1) ≈ 1 - e^(-1)
    _assert_close(incomplete_gamma_lower(1.0, 1.0), 0.6321, 1e-3, "γ(1,1) ≈ 0.6321")
    n_pass += 1

    # 82: erf + erfc == 1 for any x
    var x_test: Float64 = 1.5
    _assert_close(erf(x_test) + erfc(x_test), 1.0, 1e-8, "erf(x) + erfc(x) == 1")
    n_pass += 1

    print("  ✓ " + String(n_pass) + " special functions assertions passed")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 41 Tests ===")
    test_trie()
    test_protocol()
    test_special_functions()
    print("=== All Wave 41 tests passed ===")
