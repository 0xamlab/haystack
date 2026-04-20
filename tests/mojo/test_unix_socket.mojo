"""
test_unix_socket.mojo — Frame encoding/decoding tests for net/unix_socket.mojo.

Validates the pure-Mojo length-prefixed frame helpers that replace Python's
struct.pack('>I') / struct.unpack('>I') in the IPC wire protocol.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_unix_socket.mojo
"""
from net.unix_socket import encode_frame, decode_frame_length, encode_u32_be, decode_u32_be


# ── Helpers ───────────────────────────────────────────────────────────────────

fn _make_header(a: UInt8, b: UInt8, c: UInt8, d: UInt8) -> List[UInt8]:
    """Build a 4-byte List[UInt8] from individual bytes."""
    var h = List[UInt8](capacity=4)
    h.append(a)
    h.append(b)
    h.append(c)
    h.append(d)
    return h^


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)
    print("✅ " + label)


def _assert_eq(got: Int, expected: Int, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)
    print("✅ " + label)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_encode_u32_be_zero() raises:
    """Encode zero as big-endian bytes."""
    var enc = encode_u32_be(0)
    _assert_eq(len(enc), 4, "encode_u32_be(0) length == 4")
    _assert_true(
        enc[0] == 0 and enc[1] == 0 and enc[2] == 0 and enc[3] == 0,
        "encode_u32_be(0) == [0,0,0,0]",
    )


def test_encode_u32_be_256() raises:
    """Encode 256 (0x00000100) as big-endian bytes."""
    var enc = encode_u32_be(256)
    _assert_true(
        enc[0] == 0 and enc[1] == 0 and enc[2] == 1 and enc[3] == 0,
        "encode_u32_be(256) == [0,0,1,0]",
    )


def test_encode_u32_be_16777216() raises:
    """Encode 16777216 (0x01000000) as big-endian bytes."""
    var enc = encode_u32_be(16777216)
    _assert_true(
        enc[0] == 1 and enc[1] == 0 and enc[2] == 0 and enc[3] == 0,
        "encode_u32_be(16777216) == [1,0,0,0]",
    )


def test_roundtrip_42() raises:
    """Round-trip encode/decode for value 42."""
    _assert_eq(decode_u32_be(encode_u32_be(42)), 42, "roundtrip(42)")


def test_roundtrip_10000() raises:
    """Round-trip encode/decode for value 10000."""
    _assert_eq(decode_u32_be(encode_u32_be(10000)), 10000, "roundtrip(10000)")


def test_roundtrip_zero() raises:
    """Round-trip encode/decode for value 0."""
    _assert_eq(decode_u32_be(encode_u32_be(0)), 0, "roundtrip(0)")


def test_roundtrip_0x00FFFFFF() raises:
    """Round-trip encode/decode for 0x00FFFFFF."""
    _assert_eq(
        decode_u32_be(encode_u32_be(16777215)), 16777215, "roundtrip(0x00FFFFFF)"
    )


def test_encode_frame_hello() raises:
    """Frame for 'hello' is 9 bytes with correct header."""
    var frame = encode_frame("hello")
    _assert_eq(len(frame), 9, "encode_frame('hello') length == 9")
    var hdr = _make_header(frame[0], frame[1], frame[2], frame[3])
    _assert_eq(decode_frame_length(hdr), 5, "frame header decodes to 5")


def test_encode_frame_json() raises:
    """Frame header for JSON status payload decodes to 18."""
    var frame = encode_frame('{"status":"ready"}')
    var hdr = _make_header(frame[0], frame[1], frame[2], frame[3])
    var payload_len = decode_frame_length(hdr)
    _assert_eq(payload_len, 18, "json frame header decodes to 18")


def test_encode_frame_empty() raises:
    """Frame for empty string is 4 bytes with zero-length header."""
    var frame = encode_frame("")
    _assert_eq(len(frame), 4, "encode_frame('') length == 4")
    var hdr = _make_header(frame[0], frame[1], frame[2], frame[3])
    _assert_eq(decode_frame_length(hdr), 0, "empty frame header decodes to 0")


def test_roundtrip_large_value() raises:
    """Round-trip encode/decode for max uint32 (0xFFFFFFFF)."""
    var val = 4294967295  # 0xFFFFFFFF
    _assert_eq(decode_u32_be(encode_u32_be(val)), val, "roundtrip(0xFFFFFFFF)")


def test_encode_u32_be_known_pattern() raises:
    """Encode 0xDEADBEEF produces expected byte pattern."""
    var enc = encode_u32_be(0xDEADBEEF)
    _assert_true(
        enc[0] == 0xDE and enc[1] == 0xAD and enc[2] == 0xBE and enc[3] == 0xEF,
        "encode_u32_be(0xDEADBEEF) == [DE,AD,BE,EF]",
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def main() raises:
    print("━━━ Unix socket frame encoding test suite ━━━")
    test_encode_u32_be_zero()
    test_encode_u32_be_256()
    test_encode_u32_be_16777216()
    test_roundtrip_42()
    test_roundtrip_10000()
    test_roundtrip_zero()
    test_roundtrip_0x00FFFFFF()
    test_encode_frame_hello()
    test_encode_frame_json()
    test_encode_frame_empty()
    test_roundtrip_large_value()
    test_encode_u32_be_known_pattern()
    print("━━━ All 12 unix socket tests passed ━━━")
    print("✅ All Unix socket tests passed")
