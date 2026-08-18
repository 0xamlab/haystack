"""
pbkdf2.mojo — PBKDF2 Key Derivation with HMAC-SHA256. Zero Python imports.

Replaces hashlib.pbkdf2_hmac with a pure Mojo implementation per RFC 2898.
Includes standalone SHA-256 on byte lists and HMAC-SHA256 on byte lists.

Public API:
  sha256_bytes          — SHA-256 of byte list -> 32-byte list
  hmac_sha256_bytes     — HMAC-SHA256 on byte lists
  pbkdf2_hmac_sha256    — PBKDF2 with HMAC-SHA256
  bytes_from_string     — String to byte list
  bytes_to_hex          — Byte list to hex string
  xor_byte_lists        — XOR two byte lists
  int_to_bytes_be       — Int to big-endian byte list
"""


# ── SHA-256 internals (FIPS 180-4) adapted for List[Int] ────────────────────


def _rotr(x: UInt32, n: Int) -> UInt32:
    return (x >> UInt32(n)) | (x << UInt32(32 - n))


def _k_constants() -> List[UInt32]:
    var k = List[UInt32](capacity=64)
    k.append(0x428a2f98); k.append(0x71374491); k.append(0xb5c0fbcf); k.append(0xe9b5dba5)
    k.append(0x3956c25b); k.append(0x59f111f1); k.append(0x923f82a4); k.append(0xab1c5ed5)
    k.append(0xd807aa98); k.append(0x12835b01); k.append(0x243185be); k.append(0x550c7dc3)
    k.append(0x72be5d74); k.append(0x80deb1fe); k.append(0x9bdc06a7); k.append(0xc19bf174)
    k.append(0xe49b69c1); k.append(0xefbe4786); k.append(0x0fc19dc6); k.append(0x240ca1cc)
    k.append(0x2de92c6f); k.append(0x4a7484aa); k.append(0x5cb0a9dc); k.append(0x76f988da)
    k.append(0x983e5152); k.append(0xa831c66d); k.append(0xb00327c8); k.append(0xbf597fc7)
    k.append(0xc6e00bf3); k.append(0xd5a79147); k.append(0x06ca6351); k.append(0x14292967)
    k.append(0x27b70a85); k.append(0x2e1b2138); k.append(0x4d2c6dfc); k.append(0x53380d13)
    k.append(0x650a7354); k.append(0x766a0abb); k.append(0x81c2c92e); k.append(0x92722c85)
    k.append(0xa2bfe8a1); k.append(0xa81a664b); k.append(0xc24b8b70); k.append(0xc76c51a3)
    k.append(0xd192e819); k.append(0xd6990624); k.append(0xf40e3585); k.append(0x106aa070)
    k.append(0x19a4c116); k.append(0x1e376c08); k.append(0x2748774c); k.append(0x34b0bcb5)
    k.append(0x391c0cb3); k.append(0x4ed8aa4a); k.append(0x5b9cca4f); k.append(0x682e6ff3)
    k.append(0x748f82ee); k.append(0x78a5636f); k.append(0x84c87814); k.append(0x8cc70208)
    k.append(0x90befffa); k.append(0xa4506ceb); k.append(0xbef9a3f7); k.append(0xc67178f2)
    return k^


def _compress_block(data: List[Int], offset: Int, mut h: List[UInt32]):
    """Process one 512-bit block from data (as Int bytes) at offset."""
    var k = _k_constants()
    var w = List[UInt32](capacity=64)
    for i in range(16):
        var base = offset + i * 4
        var word = (UInt32(data[base]) << UInt32(24)) | (UInt32(data[base + 1]) << UInt32(16)) | (UInt32(data[base + 2]) << UInt32(8)) | UInt32(data[base + 3])
        w.append(word)
    for i in range(16, 64):
        var s0 = _rotr(w[i-15], 7) ^ _rotr(w[i-15], 18) ^ (w[i-15] >> UInt32(3))
        var s1 = _rotr(w[i-2], 17) ^ _rotr(w[i-2], 19) ^ (w[i-2] >> UInt32(10))
        w.append(w[i-16] + s0 + w[i-7] + s1)

    var a = h[0]; var b = h[1]; var c = h[2]; var d = h[3]
    var e = h[4]; var f = h[5]; var g = h[6]; var hh = h[7]

    for i in range(64):
        var S1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
        var ch = (e & f) ^ (~e & g)
        var t1 = hh + S1 + ch + k[i] + w[i]
        var S0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
        var maj = (a & b) ^ (a & c) ^ (b & c)
        var t2 = S0 + maj
        hh = g; g = f; f = e; e = d + t1
        d = c; c = b; b = a; a = t1 + t2

    h[0] += a; h[1] += b; h[2] += c; h[3] += d
    h[4] += e; h[5] += f; h[6] += g; h[7] += hh


# ── sha256_bytes ─────────────────────────────────────────────────────────────


def sha256_bytes(data: List[Int]) -> List[Int]:
    """SHA-256 hash of byte list, returns 32-byte list.

    FIPS 180-4 implementation operating on List[Int] (0-255 values).

    Args:
        data: Input bytes as List[Int].

    Returns:
        32-byte hash as List[Int].
    """
    var h = List[UInt32](capacity=8)
    h.append(0x6a09e667); h.append(0xbb67ae85)
    h.append(0x3c6ef372); h.append(0xa54ff53a)
    h.append(0x510e527f); h.append(0x9b05688c)
    h.append(0x1f83d9ab); h.append(0x5be0cd19)

    var msg_len = len(data)
    var pos = 0
    while pos + 64 <= msg_len:
        _compress_block(data, pos, h)
        pos += 64

    # Build padded tail
    var buf = List[Int](capacity=128)
    while pos < msg_len:
        buf.append(data[pos])
        pos += 1
    buf.append(0x80)
    while len(buf) % 64 != 56:
        buf.append(0)
    var bit_len = UInt64(msg_len) * 8
    buf.append(Int((bit_len >> 56) & 0xFF))
    buf.append(Int((bit_len >> 48) & 0xFF))
    buf.append(Int((bit_len >> 40) & 0xFF))
    buf.append(Int((bit_len >> 32) & 0xFF))
    buf.append(Int((bit_len >> 24) & 0xFF))
    buf.append(Int((bit_len >> 16) & 0xFF))
    buf.append(Int((bit_len >> 8) & 0xFF))
    buf.append(Int(bit_len & 0xFF))

    var off = 0
    while off < len(buf):
        _compress_block(buf, off, h)
        off += 64

    var result = List[Int](capacity=32)
    for i in range(8):
        var w = h[i]
        result.append(Int((w >> 24) & 0xFF))
        result.append(Int((w >> 16) & 0xFF))
        result.append(Int((w >> 8) & 0xFF))
        result.append(Int(w & 0xFF))
    return result^


# ── Utility functions ────────────────────────────────────────────────────────


def bytes_from_string(s: String) -> List[Int]:
    """Convert string to byte list.

    Args:
        s: Input string.

    Returns:
        List of byte values (0-255).
    """
    var bspan = s.as_bytes()
    var n = s.byte_length()
    var result = List[Int](capacity=n)
    for i in range(n):
        result.append(Int(bspan[i]))
    return result^


def bytes_to_hex(data: List[Int]) -> String:
    """Convert byte list to lowercase hex string.

    Args:
        data: List of byte values (0-255).

    Returns:
        Hex string (2 chars per byte).
    """
    var result = String("")
    for i in range(len(data)):
        var b = data[i]
        var hi = (b >> 4) & 0x0F
        if hi < 10:
            result += chr(48 + hi)
        else:
            result += chr(87 + hi)
        var lo = b & 0x0F
        if lo < 10:
            result += chr(48 + lo)
        else:
            result += chr(87 + lo)
    return result


def xor_byte_lists(a: List[Int], b: List[Int]) -> List[Int]:
    """XOR two byte lists element-wise.

    Args:
        a: First byte list.
        b: Second byte list (same length as a).

    Returns:
        XOR result.
    """
    var n = len(a)
    if len(b) != n:
        return List[Int]()
    var result = List[Int](capacity=n)
    for i in range(n):
        result.append(a[i] ^ b[i])
    return result^


def int_to_bytes_be(value: Int, length: Int) -> List[Int]:
    """Convert integer to big-endian byte list.

    Args:
        value: Non-negative integer.
        length: Number of output bytes.

    Returns:
        Big-endian byte representation.
    """
    var result = List[Int](capacity=length)
    for i in range(length):
        result.append(0)
    var v = value
    for i in range(length):
        result[length - 1 - i] = v & 0xFF
        v >>= 8
    return result^


# ── hmac_sha256_bytes ────────────────────────────────────────────────────────


def hmac_sha256_bytes(key: List[Int], message: List[Int]) -> List[Int]:
    """HMAC-SHA256 operating on byte lists (0-255).

    Uses the standard HMAC construction (RFC 2104) with SHA-256.

    Args:
        key: Key as byte list.
        message: Message as byte list.

    Returns:
        32-byte HMAC as List[Int].
    """
    var block_size = 64

    # Step 1: Normalize key
    var k = List[Int](capacity=block_size)
    if len(key) > block_size:
        var hashed = sha256_bytes(key)
        for i in range(len(hashed)):
            k.append(hashed[i])
    else:
        for i in range(len(key)):
            k.append(key[i])

    # Pad to block_size
    while len(k) < block_size:
        k.append(0)

    # Step 2: Inner hash = SHA256((k XOR ipad) || message)
    var inner = List[Int](capacity=block_size + len(message))
    for i in range(block_size):
        inner.append(k[i] ^ 0x36)
    for i in range(len(message)):
        inner.append(message[i])
    var inner_hash = sha256_bytes(inner)

    # Step 3: Outer hash = SHA256((k XOR opad) || inner_hash)
    var outer = List[Int](capacity=block_size + 32)
    for i in range(block_size):
        outer.append(k[i] ^ 0x5C)
    for i in range(len(inner_hash)):
        outer.append(inner_hash[i])

    return sha256_bytes(outer)


# ── pbkdf2_hmac_sha256 ──────────────────────────────────────────────────────


def pbkdf2_hmac_sha256(password: List[Int], salt: List[Int],
                      iterations: Int, dk_len: Int) -> List[Int]:
    """PBKDF2 with HMAC-SHA256 per RFC 2898.

    Args:
        password: Password as byte list.
        salt: Salt as byte list.
        iterations: Number of iterations (>= 1).
        dk_len: Desired key length in bytes.

    Returns:
        Derived key as byte list of length dk_len.
    """
    if dk_len <= 0 or dk_len > 1000000:
        return List[Int]()  # negative dk_len breaks List capacity; huge blows it up
    var hash_len = 32  # SHA-256 output
    # Number of blocks needed
    var blocks = (dk_len + hash_len - 1) // hash_len

    var dk = List[Int](capacity=dk_len)

    for block_idx in range(1, blocks + 1):
        # U_1 = HMAC(password, salt || INT_32_BE(block_idx))
        var salt_block = List[Int](capacity=len(salt) + 4)
        for i in range(len(salt)):
            salt_block.append(salt[i])
        var be = int_to_bytes_be(block_idx, 4)
        for i in range(4):
            salt_block.append(be[i])

        var u = hmac_sha256_bytes(password, salt_block)
        # T = U_1
        var t = List[Int](capacity=hash_len)
        for i in range(hash_len):
            t.append(u[i])

        # U_2 .. U_c
        for iter_idx in range(1, iterations):
            u = hmac_sha256_bytes(password, u)
            for i in range(hash_len):
                t[i] = t[i] ^ u[i]

        # Append T to derived key
        for i in range(hash_len):
            if len(dk) < dk_len:
                dk.append(t[i])

    return dk^
