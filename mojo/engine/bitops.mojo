"""
bitops.mojo — Bit manipulation utilities. Zero Python imports.

Replaces Python's bitwise ops for performance-critical code.

Public API:
  def popcount(x)         — count set bits
  def leading_zeros(x)    — count leading zeros
  def trailing_zeros(x)   — count trailing zeros
  def next_power_of_2(x)  — next power of 2 >= x
  def is_power_of_2(x)    — check if x is a power of 2
  def reverse_bits(x)     — reverse bits of a UInt32
  def rotate_left(x, n)   — rotate bits left
  def rotate_right(x, n)  — rotate bits right
  def bit_set(x, pos)     — set bit at position
  def bit_clear(x, pos)   — clear bit at position
  def bit_test(x, pos)    — test bit at position
  def bit_toggle(x, pos)  — toggle bit at position
  def fnv1a_hash(data)    — FNV-1a hash for strings
"""


# ── popcount ──────────────────────────────────────────────────────────────────


def popcount(x: Int) -> Int:
    """Count the number of set bits (1s) in x."""
    var n = x
    var count = 0
    # Handle negative numbers by working with unsigned representation
    # Process up to 64 bits
    for _ in range(64):
        if n == 0:
            break
        count += n & 1
        # Unsigned right shift via masking
        n = (n >> 1) & 0x7FFFFFFFFFFFFFFF
    return count


# ── leading_zeros ─────────────────────────────────────────────────────────────


def leading_zeros(x: Int) -> Int:
    """Count leading zero bits in a 64-bit integer. Returns 64 for x == 0."""
    if x == 0:
        return 64
    var n = x
    var count = 0
    # Check from the most significant bit down
    # Bit 63 is sign bit
    for i in range(63, -1, -1):
        var bit = (n >> i) & 1
        if bit == 1:
            break
        count += 1
    return count


# ── trailing_zeros ────────────────────────────────────────────────────────────


def trailing_zeros(x: Int) -> Int:
    """Count trailing zero bits. Returns 64 for x == 0."""
    if x == 0:
        return 64
    var n = x
    var count = 0
    while (n & 1) == 0:
        count += 1
        n = (n >> 1) & 0x7FFFFFFFFFFFFFFF
    return count


# ── next_power_of_2 ──────────────────────────────────────────────────────────


def next_power_of_2(x: Int) -> Int:
    """Return the smallest power of 2 >= x. Returns 1 for x <= 1."""
    if x <= 1:
        return 1
    var p = 1
    while p < x:
        p <<= 1
    return p


# ── is_power_of_2 ────────────────────────────────────────────────────────────


def is_power_of_2(x: Int) -> Bool:
    """Return True if x is a positive power of 2."""
    return x > 0 and (x & (x - 1)) == 0


# ── reverse_bits ──────────────────────────────────────────────────────────────


def reverse_bits(x: UInt32) -> UInt32:
    """Reverse the bits of a 32-bit unsigned integer."""
    var n = x
    var result: UInt32 = 0
    for _ in range(32):
        result = (result << 1) | (n & 1)
        n >>= 1
    return result


# ── rotate_left ───────────────────────────────────────────────────────────────


def rotate_left(x: UInt32, n: Int) -> UInt32:
    """Rotate x left by n bits (32-bit)."""
    var shift = n % 32
    if shift == 0:
        return x
    return (x << UInt32(shift)) | (x >> UInt32(32 - shift))


# ── rotate_right ──────────────────────────────────────────────────────────────


def rotate_right(x: UInt32, n: Int) -> UInt32:
    """Rotate x right by n bits (32-bit)."""
    var shift = n % 32
    if shift == 0:
        return x
    return (x >> UInt32(shift)) | (x << UInt32(32 - shift))


# ── bit_set ───────────────────────────────────────────────────────────────────


def bit_set(x: Int, pos: Int) -> Int:
    """Set bit at position pos (0-indexed from LSB)."""
    return x | (1 << pos)


# ── bit_clear ─────────────────────────────────────────────────────────────────


def bit_clear(x: Int, pos: Int) -> Int:
    """Clear bit at position pos."""
    return x & ~(1 << pos)


# ── bit_test ──────────────────────────────────────────────────────────────────


def bit_test(x: Int, pos: Int) -> Bool:
    """Test if bit at position pos is set."""
    return (x >> pos) & 1 == 1


# ── bit_toggle ────────────────────────────────────────────────────────────────


def bit_toggle(x: Int, pos: Int) -> Int:
    """Toggle bit at position pos."""
    return x ^ (1 << pos)


# ── fnv1a_hash ────────────────────────────────────────────────────────────────


def fnv1a_hash(data: String) -> Int:
    """FNV-1a hash for strings. Returns a non-negative Int.

    FNV-1a parameters (64-bit):
      offset_basis = 14695981039346656037
      prime        = 1099511628211
    """
    # FNV-1a 64-bit parameters
    # offset_basis = 14695981039346656037 (0xcbf29ce484222325)
    # prime = 1099511628211 (0x100000001b3)
    # Since Mojo Int is 64-bit signed, we use the signed representation.
    var hash_val: Int = -3750763034362895579  # 0xcbf29ce484222325 as signed Int64
    var prime: Int = 1099511628211

    var bytes = data.as_bytes()
    for i in range(len(bytes)):
        hash_val = hash_val ^ Int(bytes[i])
        hash_val = hash_val * prime

    # Return non-negative by masking off sign bit
    return hash_val & 0x7FFFFFFFFFFFFFFF
