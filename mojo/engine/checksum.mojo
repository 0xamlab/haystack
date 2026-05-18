"""
checksum.mojo — Checksum algorithms. Zero Python imports.
Replaces various checksum libraries for the decision engine.

Public API:
  adler32, fletcher16, luhn_check, luhn_checksum, isbn10_check,
  isbn13_check, xor_checksum, modular_sum, parity_bit,
  internet_checksum, verhoeff_check
"""


# ── Adler-32 ──────────────────────────────────────────────────────────────────


fn adler32(data: List[Int]) -> Int:
    """Adler-32 checksum. a=1+Σdata mod 65521, b=Σa mod 65521."""
    var a: Int = 1
    var b: Int = 0
    var mod: Int = 65521
    for i in range(len(data)):
        a = (a + (data[i] & 0xFF)) % mod
        b = (b + a) % mod
    return (b << 16) | a


# ── Fletcher-16 ───────────────────────────────────────────────────────────────


fn fletcher16(data: List[Int]) -> Int:
    """Fletcher-16 checksum."""
    var sum1: Int = 0
    var sum2: Int = 0
    for i in range(len(data)):
        sum1 = (sum1 + (data[i] & 0xFF)) % 255
        sum2 = (sum2 + sum1) % 255
    return (sum2 << 8) | sum1


# ── Luhn Check ────────────────────────────────────────────────────────────────


fn luhn_check(digits: List[Int]) -> Bool:
    """Luhn algorithm validity check."""
    var n = len(digits)
    if n == 0:
        return False
    var total: Int = 0
    var alt = False
    var i = n - 1
    while i >= 0:
        var d = digits[i]
        if alt:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
        i -= 1
    return total % 10 == 0


# ── Luhn Checksum ─────────────────────────────────────────────────────────────


fn luhn_checksum(digits: List[Int]) -> Int:
    """Compute Luhn check digit for given digits."""
    var n = len(digits)
    var total: Int = 0
    var alt = True  # Start alternating from rightmost (which will be the check digit)
    var i = n - 1
    while i >= 0:
        var d = digits[i]
        if alt:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
        i -= 1
    return (10 - (total % 10)) % 10


# ── ISBN-10 Check ─────────────────────────────────────────────────────────────


fn isbn10_check(digits: List[Int]) -> Bool:
    """ISBN-10 check: 10 digits, weighted sum mod 11 == 0.
    Weights: 10, 9, 8, ..., 1."""
    if len(digits) != 10:
        return False
    var total: Int = 0
    for i in range(10):
        total += digits[i] * (10 - i)
    return total % 11 == 0


# ── ISBN-13 Check ─────────────────────────────────────────────────────────────


fn isbn13_check(digits: List[Int]) -> Bool:
    """ISBN-13 check: alternating 1,3 weights mod 10 == 0."""
    if len(digits) != 13:
        return False
    var total: Int = 0
    for i in range(13):
        if i % 2 == 0:
            total += digits[i]
        else:
            total += digits[i] * 3
    return total % 10 == 0


# ── XOR Checksum ──────────────────────────────────────────────────────────────


fn xor_checksum(data: List[Int]) -> Int:
    """Simple XOR of all bytes."""
    var result: Int = 0
    for i in range(len(data)):
        result = result ^ (data[i] & 0xFF)
    return result


# ── Modular Sum ───────────────────────────────────────────────────────────────


fn modular_sum(data: List[Int], modulus: Int = 256) -> Int:
    """Sum mod modulus."""
    var total: Int = 0
    for i in range(len(data)):
        total += data[i]
    return total % modulus


# ── Parity Bit ────────────────────────────────────────────────────────────────


fn parity_bit(data: List[Int]) -> Int:
    """Even parity: 0 if even number of 1s, 1 if odd."""
    var count: Int = 0
    for i in range(len(data)):
        if data[i] != 0:
            count += 1
    return count % 2


# ── Internet Checksum ─────────────────────────────────────────────────────────


fn internet_checksum(data: List[Int]) -> Int:
    """Simplified IP checksum: 16-bit ones' complement sum."""
    var total: Int = 0
    var n = len(data)
    var i: Int = 0
    while i < n - 1:
        var word = ((data[i] & 0xFF) << 8) | (data[i + 1] & 0xFF)
        total += word
        i += 2
    if n % 2 == 1:
        total += (data[n - 1] & 0xFF) << 8

    # Fold carry
    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


# ── Verhoeff Check ────────────────────────────────────────────────────────────

# Verhoeff multiplication table (D5 group)
fn _verhoeff_d(i: Int, j: Int) -> Int:
    # d table (10x10)
    if i == 0:
        if j == 0: return 0
        if j == 1: return 1
        if j == 2: return 2
        if j == 3: return 3
        if j == 4: return 4
        if j == 5: return 5
        if j == 6: return 6
        if j == 7: return 7
        if j == 8: return 8
        return 9
    if i == 1:
        if j == 0: return 1
        if j == 1: return 2
        if j == 2: return 3
        if j == 3: return 4
        if j == 4: return 0
        if j == 5: return 6
        if j == 6: return 7
        if j == 7: return 8
        if j == 8: return 9
        return 5
    if i == 2:
        if j == 0: return 2
        if j == 1: return 3
        if j == 2: return 4
        if j == 3: return 0
        if j == 4: return 1
        if j == 5: return 7
        if j == 6: return 8
        if j == 7: return 9
        if j == 8: return 5
        return 6
    if i == 3:
        if j == 0: return 3
        if j == 1: return 4
        if j == 2: return 0
        if j == 3: return 1
        if j == 4: return 2
        if j == 5: return 8
        if j == 6: return 9
        if j == 7: return 5
        if j == 8: return 6
        return 7
    if i == 4:
        if j == 0: return 4
        if j == 1: return 0
        if j == 2: return 1
        if j == 3: return 2
        if j == 4: return 3
        if j == 5: return 9
        if j == 6: return 5
        if j == 7: return 6
        if j == 8: return 7
        return 8
    if i == 5:
        if j == 0: return 5
        if j == 1: return 9
        if j == 2: return 8
        if j == 3: return 7
        if j == 4: return 6
        if j == 5: return 0
        if j == 6: return 4
        if j == 7: return 3
        if j == 8: return 2
        return 1
    if i == 6:
        if j == 0: return 6
        if j == 1: return 5
        if j == 2: return 9
        if j == 3: return 8
        if j == 4: return 7
        if j == 5: return 1
        if j == 6: return 0
        if j == 7: return 4
        if j == 8: return 3
        return 2
    if i == 7:
        if j == 0: return 7
        if j == 1: return 6
        if j == 2: return 5
        if j == 3: return 9
        if j == 4: return 8
        if j == 5: return 2
        if j == 6: return 1
        if j == 7: return 0
        if j == 8: return 4
        return 3
    if i == 8:
        if j == 0: return 8
        if j == 1: return 7
        if j == 2: return 6
        if j == 3: return 5
        if j == 4: return 9
        if j == 5: return 3
        if j == 6: return 2
        if j == 7: return 1
        if j == 8: return 0
        return 4
    # i == 9
    if j == 0: return 9
    if j == 1: return 8
    if j == 2: return 7
    if j == 3: return 6
    if j == 4: return 5
    if j == 5: return 4
    if j == 6: return 3
    if j == 7: return 2
    if j == 8: return 1
    return 0


fn _verhoeff_p(i: Int, j: Int) -> Int:
    # Permutation table (8x10)
    if i == 0:
        if j == 0: return 0
        if j == 1: return 1
        if j == 2: return 2
        if j == 3: return 3
        if j == 4: return 4
        if j == 5: return 5
        if j == 6: return 6
        if j == 7: return 7
        if j == 8: return 8
        return 9
    if i == 1:
        if j == 0: return 1
        if j == 1: return 5
        if j == 2: return 7
        if j == 3: return 6
        if j == 4: return 2
        if j == 5: return 8
        if j == 6: return 3
        if j == 7: return 0
        if j == 8: return 9
        return 4
    if i == 2:
        if j == 0: return 5
        if j == 1: return 8
        if j == 2: return 0
        if j == 3: return 3
        if j == 4: return 7
        if j == 5: return 9
        if j == 6: return 6
        if j == 7: return 1
        if j == 8: return 4
        return 2
    if i == 3:
        if j == 0: return 8
        if j == 1: return 9
        if j == 2: return 1
        if j == 3: return 6
        if j == 4: return 0
        if j == 5: return 4
        if j == 6: return 3
        if j == 7: return 5
        if j == 8: return 2
        return 7
    if i == 4:
        if j == 0: return 9
        if j == 1: return 4
        if j == 2: return 5
        if j == 3: return 3
        if j == 4: return 1
        if j == 5: return 2
        if j == 6: return 6
        if j == 7: return 8
        if j == 8: return 7
        return 0
    if i == 5:
        if j == 0: return 4
        if j == 1: return 2
        if j == 2: return 8
        if j == 3: return 6
        if j == 4: return 5
        if j == 5: return 7
        if j == 6: return 3
        if j == 7: return 9
        if j == 8: return 0
        return 1
    if i == 6:
        if j == 0: return 2
        if j == 1: return 7
        if j == 2: return 9
        if j == 3: return 3
        if j == 4: return 8
        if j == 5: return 0
        if j == 6: return 6
        if j == 7: return 4
        if j == 8: return 1
        return 5
    # i == 7
    if j == 0: return 7
    if j == 1: return 0
    if j == 2: return 4
    if j == 3: return 6
    if j == 4: return 9
    if j == 5: return 1
    if j == 6: return 3
    if j == 7: return 2
    if j == 8: return 5
    return 8


fn verhoeff_check(digits: List[Int]) -> Bool:
    """Verhoeff algorithm check digit validation.
    Returns True if the full number (including check digit) is valid."""
    var n = len(digits)
    if n == 0:
        return False
    var c: Int = 0
    for i in range(n):
        var idx = n - 1 - i
        var p_idx = (i + 1) % 8
        var p_val = _verhoeff_p(p_idx, digits[idx])
        c = _verhoeff_d(c, p_val)
    return c == 0
