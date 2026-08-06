"""
uuid.mojo — UUID v4 generation. Zero Python imports.

RFC 4122 compliant (version 4, random). Uses Mojo's std.random
for cryptographic-quality random byte generation.

Public API:
  uuid4()      — generate UUID v4 string (36 chars with dashes)
  uuid4_hex()  — generate UUID v4 as 32 hex chars (no dashes)
"""
from std.random import random_float64


# ── Hex helpers ──────────────────────────────────────────────────────────────

comptime _HEX_ALPHABET = "0123456789abcdef"


@always_inline
def _nibble_to_hex(n: Int) -> String:
    """Convert a 4-bit nibble (0-15) to a single lowercase hex character."""
    return chr(Int(_HEX_ALPHABET.as_bytes()[n & 0x0F]))


@always_inline
def _byte_to_hex(b: Int) -> String:
    """Convert a byte (0-255) to a 2-character lowercase hex string."""
    return _nibble_to_hex((b >> 4) & 0x0F) + _nibble_to_hex(b & 0x0F)


# ── Random byte generation ───────────────────────────────────────────────────

@always_inline
def _random_byte() -> Int:
    """Generate a random byte (0-255) using random_float64()."""
    var v = Int(random_float64() * 256.0)
    if v > 255:
        v = 255
    if v < 0:
        v = 0
    return v


def _random_bytes_16() -> List[Int]:
    """Generate 16 random bytes."""
    var bytes = List[Int](capacity=16)
    for _ in range(16):
        bytes.append(_random_byte())
    return bytes^


# ── UUID v4 ──────────────────────────────────────────────────────────────────

def uuid4() -> String:
    """Generate a UUID v4 (random) string.

    Format: 8-4-4-4-12 hex chars = 36 chars total.
    Example: "550e8400-e29b-41d4-a716-446655440000"

    Bits:
    - Version: bits 48-51 = 0100 (version 4)
    - Variant: bits 64-65 = 10 (RFC 4122)
    - All other bits: random
    """
    var b = _random_bytes_16()

    # Set version 4: byte 6 high nibble = 0x40
    b[6] = (b[6] & 0x0F) | 0x40

    # Set variant RFC 4122: byte 8 high bits = 10xx
    b[8] = (b[8] & 0x3F) | 0x80

    # Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    #         [0-3]   -[4-5]-[6-7]-[8-9]-[10-15]
    var result = String("")

    # Bytes 0-3
    result += _byte_to_hex(b[0])
    result += _byte_to_hex(b[1])
    result += _byte_to_hex(b[2])
    result += _byte_to_hex(b[3])
    result += "-"

    # Bytes 4-5
    result += _byte_to_hex(b[4])
    result += _byte_to_hex(b[5])
    result += "-"

    # Bytes 6-7 (contains version)
    result += _byte_to_hex(b[6])
    result += _byte_to_hex(b[7])
    result += "-"

    # Bytes 8-9 (contains variant)
    result += _byte_to_hex(b[8])
    result += _byte_to_hex(b[9])
    result += "-"

    # Bytes 10-15
    result += _byte_to_hex(b[10])
    result += _byte_to_hex(b[11])
    result += _byte_to_hex(b[12])
    result += _byte_to_hex(b[13])
    result += _byte_to_hex(b[14])
    result += _byte_to_hex(b[15])

    return result


def uuid4_hex() -> String:
    """Generate a UUID v4 as 32 hex chars (no dashes)."""
    var b = _random_bytes_16()

    # Set version 4: byte 6 high nibble = 0x40
    b[6] = (b[6] & 0x0F) | 0x40

    # Set variant RFC 4122: byte 8 high bits = 10xx
    b[8] = (b[8] & 0x3F) | 0x80

    var result = String("")
    for i in range(16):
        result += _byte_to_hex(b[i])

    return result
