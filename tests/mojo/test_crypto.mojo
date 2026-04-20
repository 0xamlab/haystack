"""
test_crypto.mojo — Tests for the pure-Mojo crypto package: base64, hmac, uuid.

Validates:
  - Base64 encoding/decoding (standard + URL-safe)
  - HMAC-SHA256 against known test vectors
  - UUID v4 format, version/variant bits, uniqueness

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_crypto.mojo
"""
from crypto.base64 import b64_encode, b64_decode, b64_url_encode, b64_url_decode
from crypto.hmac import hmac_sha256, hmac_sha256_verify
from crypto.uuid import uuid4, uuid4_hex


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_eq(got: String, expected: String, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


@always_inline
fn _char_at(s: String, idx: Int) -> String:
    """Get the character at a given byte index as a String."""
    return chr(Int(s.as_bytes()[idx]))


# ── Base64 tests ─────────────────────────────────────────────────────────────

def test_base64() raises:
    # Standard encode/decode
    _assert_eq(b64_encode("Hello"), "SGVsbG8=", "b64_encode('Hello')")
    _assert_eq(b64_decode("SGVsbG8="), "Hello", "b64_decode('SGVsbG8=')")

    # Empty string
    _assert_eq(b64_encode(""), "", "b64_encode('')")
    _assert_eq(b64_decode(""), "", "b64_decode('')")

    # Padding variants: 1 byte, 2 bytes, 3 bytes (no pad)
    _assert_eq(b64_encode("a"), "YQ==", "b64_encode('a')")
    _assert_eq(b64_encode("ab"), "YWI=", "b64_encode('ab')")
    _assert_eq(b64_encode("abc"), "YWJj", "b64_encode('abc')")

    # Round-trip
    _assert_eq(b64_decode(b64_encode("Hello, World!")), "Hello, World!", "round-trip 'Hello, World!'")
    _assert_eq(b64_decode(b64_encode("Mojo is fast!")), "Mojo is fast!", "round-trip 'Mojo is fast!'")
    _assert_eq(b64_decode(b64_encode("1234567890")), "1234567890", "round-trip '1234567890'")

    # URL-safe: no padding, + → -, / → _
    _assert_eq(b64_url_encode("Hello"), "SGVsbG8", "b64_url_encode('Hello') — no padding")

    # URL-safe round-trip
    _assert_eq(b64_url_decode(b64_url_encode("Hello")), "Hello", "url-safe round-trip 'Hello'")
    _assert_eq(b64_url_decode(b64_url_encode("Hello, World!")), "Hello, World!", "url-safe round-trip 'Hello, World!'")

    print("✅ Base64 encode/decode")


# ── HMAC-SHA256 tests ────────────────────────────────────────────────────────

def test_hmac_sha256() raises:
    # Known test vector: HMAC-SHA256("key", "The quick brown fox jumps over the lazy dog")
    var hmac1 = hmac_sha256("key", "The quick brown fox jumps over the lazy dog")
    _assert_true(len(hmac1) == 64, "HMAC output is 64 hex chars")
    _assert_eq(
        hmac1,
        "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8",
        "HMAC-SHA256('key', 'The quick brown fox...')",
    )

    # Verify: correct
    _assert_true(
        hmac_sha256_verify("key", "The quick brown fox jumps over the lazy dog", hmac1),
        "hmac_sha256_verify correct message",
    )

    # Verify: tampered message
    _assert_true(
        not hmac_sha256_verify("key", "tampered message", hmac1),
        "hmac_sha256_verify tampered message",
    )

    # Verify: wrong key
    _assert_true(
        not hmac_sha256_verify("wrong_key", "The quick brown fox jumps over the lazy dog", hmac1),
        "hmac_sha256_verify wrong key",
    )

    # Empty message
    var hmac_empty = hmac_sha256("key", "")
    _assert_true(len(hmac_empty) == 64, "HMAC empty message is 64 hex chars")
    _assert_eq(
        hmac_empty,
        "5d5d139563c95b5967b9bd9a8c9b233a9dedb45072794cd232dc1b74832607d0",
        "HMAC-SHA256('key', '')",
    )

    print("✅ HMAC-SHA256")


# ── UUID v4 tests ────────────────────────────────────────────────────────────

def test_uuid4() raises:
    var id1 = uuid4()

    # Length: 8-4-4-4-12 = 36 chars
    _assert_true(len(id1) == 36, "UUID v4 length is 36")

    # Dash positions (using byte access)
    _assert_true(_char_at(id1, 8) == "-", "UUID dash at position 8")
    _assert_true(_char_at(id1, 13) == "-", "UUID dash at position 13")
    _assert_true(_char_at(id1, 18) == "-", "UUID dash at position 18")
    _assert_true(_char_at(id1, 23) == "-", "UUID dash at position 23")

    # Version: character at position 14 must be '4'
    _assert_true(_char_at(id1, 14) == "4", "UUID version 4 at position 14")

    # Variant: character at position 19 must be 8, 9, a, or b
    var vc = _char_at(id1, 19)
    _assert_true(
        vc == "8" or vc == "9" or vc == "a" or vc == "b",
        "UUID variant char at position 19 is 8/9/a/b (got: " + vc + ")",
    )

    # Two UUIDs should be different
    var id2 = uuid4()
    _assert_true(id1 != id2, "Two uuid4() calls produce different values")

    # Hex version: 32 chars, no dashes
    var hex_id = uuid4_hex()
    _assert_true(len(hex_id) == 32, "uuid4_hex() length is 32")

    # Version in hex: char at position 12 must be '4'
    _assert_true(_char_at(hex_id, 12) == "4", "uuid4_hex() version 4 at position 12")

    # Variant in hex: char at position 16 must be 8/9/a/b
    var hvc = _char_at(hex_id, 16)
    _assert_true(
        hvc == "8" or hvc == "9" or hvc == "a" or hvc == "b",
        "uuid4_hex() variant char at position 16 is 8/9/a/b (got: " + hvc + ")",
    )

    print("✅ UUID v4")


# ── Runner ────────────────────────────────────────────────────────────────────

def main() raises:
    print("━━━ Crypto test suite (base64, hmac, uuid) ━━━")
    test_base64()
    test_hmac_sha256()
    test_uuid4()
    print("━━━ All crypto tests passed ━━━")
