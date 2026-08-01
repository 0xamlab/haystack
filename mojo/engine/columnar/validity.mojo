"""
columnar.validity — one bit per slot saying whether a value is present. Zero Python.

The first validity bitmap in this tree, in either language. Everything else here
encodes "missing" as a value, and every candidate sentinel is also real data: NaN is
a measurement outcome, 0.0 is a revenue, -1 is a temperature. A separate bit makes
presence orthogonal to value, which is the only way `0.0` and "no answer" can both
be representable.

Layout
------
Bit `i` lives in byte `i / 8` at position `i % 8`, least-significant bit first —
Arrow's convention, chosen so a buffer produced here can later be handed to an Arrow
consumer without a re-pack.

Set means present. That polarity matters: a freshly zeroed buffer then reads as
all-null, so a caller who allocates and forgets to populate gets "no data" rather
than "all zeros are real values". Failing toward absence is the safer default.
"""
from std.bit import pop_count

comptime BITS_PER_BYTE: Int = 8


fn bytes_for_bits(n: Int) -> Int:
    """Bytes needed for `n` bits, rounded up."""
    if n <= 0:
        return 0
    return (n + BITS_PER_BYTE - 1) // BITS_PER_BYTE


fn new_all_null(n: Int) -> List[UInt8]:
    """A bitmap of `n` slots, every one absent."""
    var out = List[UInt8]()
    for _ in range(bytes_for_bits(n)):
        out.append(0)
    return out^


fn new_all_valid(n: Int) -> List[UInt8]:
    """A bitmap of `n` slots, every one present.

    Trailing bits past `n` in the final byte are left set; `is_valid` bounds-checks
    against the logical length, so they are never consulted. `count_valid` takes the
    length explicitly for the same reason.
    """
    var out = List[UInt8]()
    for _ in range(bytes_for_bits(n)):
        out.append(0xFF)
    return out^


fn is_valid(bitmap: List[UInt8], index: Int) -> Bool:
    """True when slot `index` holds a value. Out of range reads as absent."""
    if index < 0:
        return False
    var byte = index // BITS_PER_BYTE
    if byte >= len(bitmap):
        return False
    return (bitmap[byte] >> UInt8(index % BITS_PER_BYTE)) & UInt8(1) == UInt8(1)


fn set_valid(mut bitmap: List[UInt8], index: Int):
    if index < 0:
        return
    var byte = index // BITS_PER_BYTE
    if byte >= len(bitmap):
        return
    bitmap[byte] = bitmap[byte] | (UInt8(1) << UInt8(index % BITS_PER_BYTE))


fn set_null(mut bitmap: List[UInt8], index: Int):
    if index < 0:
        return
    var byte = index // BITS_PER_BYTE
    if byte >= len(bitmap):
        return
    bitmap[byte] = bitmap[byte] & ~(UInt8(1) << UInt8(index % BITS_PER_BYTE))


fn count_valid(bitmap: List[UInt8], length: Int) -> Int:
    """Present slots among the first `length`.

    Whole 64-bit words go through the popcount instruction, leftover whole
    bytes through a byte popcount, and only the final partial byte is walked
    bit by bit. Round 3 hoisted "does this column have nulls at all?" to the
    front of every grouped scan, which put this function on the serial prefix
    of 1e7-row questions — the old per-byte bit-loop popcount was costing
    milliseconds per column there, so it became word-wise. Same answer for
    every (bitmap, length), including bitmaps shorter than the length (absent
    bytes count nothing, exactly as before).
    """
    if length <= 0:
        return 0
    var full_bytes = length // BITS_PER_BYTE
    var counted_bytes = full_bytes
    if counted_bytes > len(bitmap):
        counted_bytes = len(bitmap)
    var total = 0
    var words = counted_bytes // 8
    var wp = bitmap.unsafe_ptr().bitcast[UInt64]()
    for i in range(words):
        total += Int(pop_count(wp[i]))
    for i in range(words * 8, counted_bytes):
        total += Int(pop_count(bitmap[i]))
    var remainder = length % BITS_PER_BYTE
    if remainder > 0 and full_bytes < len(bitmap):
        for bit in range(remainder):
            if (bitmap[full_bytes] >> UInt8(bit)) & UInt8(1) == UInt8(1):
                total += 1
    return total


fn count_null(bitmap: List[UInt8], length: Int) -> Int:
    if length <= 0:
        return 0
    return length - count_valid(bitmap, length)


fn all_valid(bitmap: List[UInt8], length: Int) -> Bool:
    """True when nothing is missing — lets callers take a no-null fast path."""
    return count_valid(bitmap, length) == length


fn any_null(bitmap: List[UInt8], length: Int) -> Bool:
    return not all_valid(bitmap, length)


fn slice_bitmap(bitmap: List[UInt8], offset: Int, length: Int) -> List[UInt8]:
    """A bitmap for `length` slots starting at `offset`, re-aligned to bit 0.

    Re-aligning costs a copy, but it means a sliced column needs no offset field and
    cannot be misread by anything that assumes bit 0 is slot 0. Values can be sliced
    zero-copy via offset+len; a bitmap cannot, because bit offsets are not byte
    offsets unless the offset happens to be a multiple of 8.
    """
    var out = new_all_null(length)
    for i in range(length):
        if is_valid(bitmap, offset + i):
            set_valid(out, i)
    return out^


fn bitmap_and(a: List[UInt8], b: List[UInt8], length: Int) -> List[UInt8]:
    """Slots present in both — the validity of a binary operation's result."""
    var out = new_all_null(length)
    for i in range(length):
        if is_valid(a, i) and is_valid(b, i):
            set_valid(out, i)
    return out^


fn bitmap_or(a: List[UInt8], b: List[UInt8], length: Int) -> List[UInt8]:
    var out = new_all_null(length)
    for i in range(length):
        if is_valid(a, i) or is_valid(b, i):
            set_valid(out, i)
    return out^
