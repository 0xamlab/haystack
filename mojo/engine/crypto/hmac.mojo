"""
hmac.mojo — HMAC-SHA256 using native sha256.mojo. Zero Python imports.

RFC 2104 compliant. Works at the byte level to avoid UTF-8 encoding
issues when passing raw hash bytes between inner and outer hashes.

Public API:
  hmac_sha256(key, message)                    — compute HMAC-SHA256, returns 64-char hex
  hmac_sha256_verify(key, message, expected)   — constant-time verification
"""
from sha256 import _compress


# ── Constants ────────────────────────────────────────────────────────────────

comptime _BLOCK_SIZE = 64   # SHA-256 block size in bytes
comptime _HASH_SIZE = 32    # SHA-256 output size in bytes
comptime _IPAD_BYTE = 0x36
comptime _OPAD_BYTE = 0x5C


# ── Byte-level SHA-256 helper ────────────────────────────────────────────────

def _sha256_of_bytes(data: List[UInt8]) -> List[UInt8]:
    """Compute SHA-256 of raw bytes. Returns 32-byte hash as List[UInt8].

    This avoids String/UTF-8 encoding issues when hashing arbitrary bytes.
    Implements the full SHA-256 padding and compression directly on byte data.
    """
    # Initialize hash state (FIPS 180-4 initial values)
    var h = List[UInt32](capacity=8)
    h.append(0x6a09e667); h.append(0xbb67ae85)
    h.append(0x3c6ef372); h.append(0xa54ff53a)
    h.append(0x510e527f); h.append(0x9b05688c)
    h.append(0x1f83d9ab); h.append(0x5be0cd19)

    var msg_len = len(data)

    # Process complete 64-byte blocks
    var pos = 0
    while pos + 64 <= msg_len:
        _compress(data, pos, h)
        pos += 64

    # Build final padded block(s)
    var buf = List[UInt8](capacity=128)
    # Copy remaining bytes
    while pos < msg_len:
        buf.append(data[pos])
        pos += 1

    # Append 0x80 byte
    buf.append(0x80)
    # Pad with zeros until length ≡ 56 (mod 64)
    while len(buf) % 64 != 56:
        buf.append(0)
    # Append original message length in bits as 64-bit big-endian
    var bit_len = UInt64(msg_len) * 8
    buf.append(UInt8(Int((bit_len >> 56) & 0xFF)))
    buf.append(UInt8(Int((bit_len >> 48) & 0xFF)))
    buf.append(UInt8(Int((bit_len >> 40) & 0xFF)))
    buf.append(UInt8(Int((bit_len >> 32) & 0xFF)))
    buf.append(UInt8(Int((bit_len >> 24) & 0xFF)))
    buf.append(UInt8(Int((bit_len >> 16) & 0xFF)))
    buf.append(UInt8(Int((bit_len >> 8) & 0xFF)))
    buf.append(UInt8(Int(bit_len & 0xFF)))

    # Process remaining padded blocks
    var off = 0
    while off < len(buf):
        _compress(buf, off, h)
        off += 64

    # Convert hash state to 32-byte result
    var result = List[UInt8](capacity=32)
    for i in range(8):
        var w = h[i]
        result.append(UInt8(Int((w >> 24) & 0xFF)))
        result.append(UInt8(Int((w >> 16) & 0xFF)))
        result.append(UInt8(Int((w >> 8) & 0xFF)))
        result.append(UInt8(Int(w & 0xFF)))
    return result^


def _bytes_to_hex(data: List[UInt8]) -> String:
    """Convert a list of bytes to a lowercase hex string."""
    var result = String("")
    for i in range(len(data)):
        var b = Int(data[i])
        # High nibble
        var hi = (b >> 4) & 0x0F
        if hi < 10:
            result += chr(48 + hi)
        else:
            result += chr(87 + hi)
        # Low nibble
        var lo = b & 0x0F
        if lo < 10:
            result += chr(48 + lo)
        else:
            result += chr(87 + lo)
    return result


# ── HMAC-SHA256 ──────────────────────────────────────────────────────────────

def hmac_sha256(key: String, message: String) -> String:
    """Compute HMAC-SHA256(key, message). Returns 64-char hex digest.

    Algorithm (RFC 2104):
    1. If key > 64 bytes, key = SHA256(key)
    2. Pad key to 64 bytes with zeros
    3. inner = SHA256((key XOR 0x36) || message)
    4. outer = SHA256((key XOR 0x5C) || inner_bytes)
    5. Return hex(outer)
    """
    # ── Step 1: Normalize key to bytes ──
    var key_bytes = List[UInt8](capacity=_BLOCK_SIZE)
    var raw_key = key.as_bytes()
    var key_len = key.byte_length()

    if key_len > _BLOCK_SIZE:
        # Hash the key if it's longer than the block size
        var hashed = List[UInt8](capacity=key_len)
        for i in range(key_len):
            hashed.append(raw_key[i])
        var hk = _sha256_of_bytes(hashed)
        for i in range(len(hk)):
            key_bytes.append(hk[i])
    else:
        for i in range(key_len):
            key_bytes.append(raw_key[i])

    # ── Step 2: Pad key to block size with zeros ──
    while len(key_bytes) < _BLOCK_SIZE:
        key_bytes.append(0)

    # ── Step 3: Compute inner hash ──
    # Build inner data: (key XOR 0x36) || message
    var msg_bytes = message.as_bytes()
    var msg_len = message.byte_length()
    var inner_data = List[UInt8](capacity=_BLOCK_SIZE + msg_len)

    for i in range(_BLOCK_SIZE):
        inner_data.append(key_bytes[i] ^ UInt8(_IPAD_BYTE))
    for i in range(msg_len):
        inner_data.append(msg_bytes[i])

    var inner_hash = _sha256_of_bytes(inner_data)  # 32 raw bytes

    # ── Step 4: Compute outer hash ──
    # Build outer data: (key XOR 0x5C) || inner_hash_bytes
    var outer_data = List[UInt8](capacity=_BLOCK_SIZE + _HASH_SIZE)

    for i in range(_BLOCK_SIZE):
        outer_data.append(key_bytes[i] ^ UInt8(_OPAD_BYTE))
    for i in range(len(inner_hash)):
        outer_data.append(inner_hash[i])

    var outer_hash = _sha256_of_bytes(outer_data)  # 32 raw bytes

    # ── Step 5: Return hex digest ──
    return _bytes_to_hex(outer_hash)


def hmac_sha256_verify(key: String, message: String, expected_hex: String) -> Bool:
    """Constant-time HMAC verification.

    Computes HMAC-SHA256(key, message) and compares with expected_hex
    using constant-time comparison to prevent timing attacks.
    """
    var computed = hmac_sha256(key, message)
    if computed.byte_length() != expected_hex.byte_length():
        return False

    # Constant-time comparison: always check every character
    var cb = computed.as_bytes()
    var eb = expected_hex.as_bytes()
    var diff = 0
    for i in range(computed.byte_length()):
        diff |= Int(cb[i]) ^ Int(eb[i])
    return diff == 0
