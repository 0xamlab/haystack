"""
test_sha256.mojo — NIST / FIPS 180-4 test vectors for sha256.mojo.

Validates the pure-Mojo SHA-256 implementation against known digests:
  1. Empty string
  2. "abc"  (NIST one-block example)
  3. 448-bit two-block message (NIST)
  4. Engine-style canonical hash string
  5. "Hello, World!"

Also tests the incremental SHA256 struct (multi-update).

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_sha256.mojo
"""
from sha256 import sha256_hex, SHA256


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_eq(got: String, expected: String, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)
    print("✅ " + label)


# ── Test vectors ──────────────────────────────────────────────────────────────

def test_empty_string() raises:
    """NIST: SHA-256 of the empty message."""
    _assert_eq(
        sha256_hex(""),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "sha256('') == NIST empty-string vector",
    )


def test_abc() raises:
    """NIST: SHA-256('abc') — single 512-bit block."""
    _assert_eq(
        sha256_hex("abc"),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "sha256('abc') == NIST one-block vector",
    )


def test_two_block() raises:
    """NIST: 448-bit message requiring two 512-bit blocks."""
    _assert_eq(
        sha256_hex("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
        "sha256(448-bit msg) == NIST two-block vector",
    )


def test_engine_hash() raises:
    """Engine canonical string — verified against Python hashlib.sha256()."""
    _assert_eq(
        sha256_hex("0.7.0-mojo-parallel|monte_carlo|10000|42500.0|15300.0|0.082|0.72"),
        "17142681a7a6f10ecdba7c3e1c1ebd39ea6adb962299f61956fa30fad006ce13",
        "sha256(engine canonical) == Python hashlib reference",
    )


def test_hello_world() raises:
    """SHA-256('Hello, World!') — common sanity check."""
    _assert_eq(
        sha256_hex("Hello, World!"),
        "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f",
        "sha256('Hello, World!') == known digest",
    )


# ── Incremental (struct) API ──────────────────────────────────────────────────

def test_incremental_single() raises:
    """SHA256 struct: single update produces same result as sha256_hex."""
    var h = SHA256()
    h.update("abc")
    _assert_eq(
        h.hexdigest(),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "SHA256.update('abc').hexdigest() == NIST vector",
    )


def test_incremental_multi() raises:
    """SHA256 struct: multiple updates produce the same digest as single call."""
    var h = SHA256()
    h.update("abcdbcdecdefdefg")
    h.update("efghfghighijhijk")
    h.update("ijkljklmklmnlmno")
    h.update("mnopnopq")
    _assert_eq(
        h.hexdigest(),
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
        "SHA256 multi-update == NIST two-block vector",
    )


def test_hexdigest_idempotent() raises:
    """Calling hexdigest() twice must return identical results."""
    var h = SHA256()
    h.update("abc")
    var d1 = h.hexdigest()
    var d2 = h.hexdigest()
    _assert_eq(d1, d2, "hexdigest() idempotent — two calls match")


# ── Runner ────────────────────────────────────────────────────────────────────

def main() raises:
    print("━━━ SHA-256 NIST / FIPS 180-4 test suite ━━━")
    test_empty_string()
    test_abc()
    test_two_block()
    test_engine_hash()
    test_hello_world()
    test_incremental_single()
    test_incremental_multi()
    test_hexdigest_idempotent()
    print("━━━ All 8 SHA-256 tests passed ━━━")
