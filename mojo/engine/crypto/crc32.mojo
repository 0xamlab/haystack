"""
crc32.mojo — CRC-32 checksum for data integrity verification. Zero Python imports.

Replaces Python's zlib.crc32. Table-driven implementation using the
CRC-32 polynomial 0xEDB88320 (reflected form of 0x04C11DB7).

Public API:
  fn crc32(data: String) -> UInt32
  fn crc32_hex(data: String) -> String
  fn crc32_combine(crc1: UInt32, crc2: UInt32, len2: Int) -> UInt32
"""


# ── CRC-32 lookup table ─────────────────────────────────────────────────────
# Pre-computed 256-entry table for the polynomial 0xEDB88320.


fn _make_crc_table() -> List[UInt32]:
    """Build the 256-entry CRC-32 lookup table."""
    var table = List[UInt32]()
    for i in range(256):
        var crc = UInt32(i)
        for _ in range(8):
            if (crc & 1) != 0:
                crc = (crc >> 1) ^ UInt32(0xEDB88320)
            else:
                crc = crc >> 1
        table.append(crc)
    return table^


# ── crc32 ────────────────────────────────────────────────────────────────────


fn crc32(data: String) -> UInt32:
    """Compute the CRC-32 checksum of a string.

    Args:
        data: Input string to checksum.

    Returns:
        CRC-32 checksum as a UInt32.
    """
    var table = _make_crc_table()
    var crc = UInt32(0xFFFFFFFF)
    var bytes = data.as_bytes()

    for i in range(len(bytes)):
        var byte_val = UInt32(Int(bytes[i]))
        var index = Int((crc ^ byte_val) & UInt32(0xFF))
        crc = (crc >> 8) ^ table[index]

    return crc ^ UInt32(0xFFFFFFFF)


# ── crc32_hex ────────────────────────────────────────────────────────────────


fn _nibble_to_hex(n: Int) -> String:
    """Convert a nibble (0-15) to a hex character."""
    if n < 10:
        return chr(ord("0") + n)
    return chr(ord("a") + n - 10)


fn crc32_hex(data: String) -> String:
    """Compute the CRC-32 checksum and return it as an 8-character hex string.

    Args:
        data: Input string to checksum.

    Returns:
        CRC-32 as a lowercase 8-character hexadecimal string.
    """
    var c = crc32(data)
    var result = String("")

    # Convert to 8-char hex, most significant nibble first
    for i in range(7, -1, -1):
        var nibble = Int((c >> UInt32(i * 4)) & UInt32(0xF))
        result += _nibble_to_hex(nibble)

    return result^


# ── crc32_combine ────────────────────────────────────────────────────────────


fn crc32_combine(crc1: UInt32, crc2: UInt32, len2: Int) -> UInt32:
    """Combine two CRC-32 checksums.

    Given crc1 = crc32(A) and crc2 = crc32(B) with len2 = len(B),
    returns crc32(A + B) without re-reading data.

    Uses the GF(2) matrix squaring method.

    Args:
        crc1: CRC-32 of the first data segment.
        crc2: CRC-32 of the second data segment.
        len2: Length of the second data segment in bytes.

    Returns:
        Combined CRC-32 as if the data segments were concatenated.
    """
    if len2 == 0:
        return crc1

    # We use matrix exponentiation in GF(2) to shift crc1 by len2 bytes.
    # The key insight: CRC(A||B) = CRC(A) * x^(8*len2) XOR CRC(B)
    # where multiplication is in GF(2)[x] mod the CRC polynomial.

    # Initialize odd-power matrix with the CRC polynomial
    var odd = List[UInt32]()
    for _ in range(32):
        odd.append(UInt32(0))
    odd[0] = UInt32(0xEDB88320)  # Polynomial
    var row: UInt32 = 1
    for i in range(1, 32):
        odd[i] = row
        row <<= 1

    # Square to get even-power matrix
    var even = List[UInt32]()
    for _ in range(32):
        even.append(UInt32(0))
    _gf2_matrix_square(even, odd)
    _gf2_matrix_square(odd, even)

    var result = crc1
    var remaining = len2

    while remaining > 0:
        # Apply even-power matrix
        _gf2_matrix_square(even, odd)
        if (remaining & 1) != 0:
            result = _gf2_matrix_times(even, result)
        remaining >>= 1
        if remaining == 0:
            break

        # Apply odd-power matrix
        _gf2_matrix_square(odd, even)
        if (remaining & 1) != 0:
            result = _gf2_matrix_times(odd, result)
        remaining >>= 1

    return result ^ crc2


fn _gf2_matrix_times(mat: List[UInt32], vec: UInt32) -> UInt32:
    """Multiply a GF(2) matrix by a vector (CRC value)."""
    var result = UInt32(0)
    var v = vec
    var idx = 0
    while v != 0:
        if (v & 1) != 0:
            result ^= mat[idx]
        v >>= 1
        idx += 1
    return result


fn _gf2_matrix_square(mut square: List[UInt32], mat: List[UInt32]):
    """Square a GF(2) matrix into the output."""
    for n in range(32):
        square[n] = _gf2_matrix_times(mat, mat[n])
