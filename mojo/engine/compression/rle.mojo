"""
rle.mojo — Run-Length Encoding compression. Zero Python imports.

Simple RLE compression useful for data with repeated values
(e.g., compressing simulation output arrays).

Encoding format (byte-level):
  For each run: [count_byte, value_byte]
  count is 1-255. Runs longer than 255 are split into multiple pairs.

Public API:
  rle_encode()             — compress List[UInt8] using RLE
  rle_decode()             — decompress List[UInt8]
  rle_encode_string()      — compress string (e.g., "AAABBC" → "3A2B1C")
  rle_decode_string()      — decompress string
  compression_ratio()      — compute ratio original_size / compressed_size
"""


# ── Byte-level RLE ───────────────────────────────────────────────────────────


fn rle_encode(data: List[UInt8]) -> List[UInt8]:
    """Compress bytes using Run-Length Encoding.

    Format: pairs of (count, value) bytes. Max run length per pair is 255.
    """
    var result = List[UInt8]()
    var n = len(data)
    if n == 0:
        return result^

    var i = 0
    while i < n:
        var current = data[i]
        var count: UInt8 = 1
        while i + Int(count) < n and data[i + Int(count)] == current and count < 255:
            count += 1
        result.append(count)
        result.append(current)
        i += Int(count)

    return result^


fn rle_decode(compressed: List[UInt8]) -> List[UInt8]:
    """Decompress RLE-encoded bytes.

    Expects pairs of (count, value) bytes.
    """
    var result = List[UInt8]()
    var n = len(compressed)
    var i = 0
    while i + 1 < n:
        var count = Int(compressed[i])
        var value = compressed[i + 1]
        for _ in range(count):
            result.append(value)
        i += 2
    return result^


# ── String-level RLE ─────────────────────────────────────────────────────────


fn _int_to_string(val: Int) -> String:
    """Convert a non-negative integer to string."""
    if val == 0:
        return String("0")
    var result = String("")
    var v = val
    while v > 0:
        var digit = v % 10
        result = chr(48 + digit) + result
        v = v // 10
    return result


fn rle_encode_string(data: String) -> String:
    """Compress a string using RLE. E.g., "AAABBC" → "3A2B1C"."""
    var n = len(data)
    if n == 0:
        return String("")

    var bs = data.as_bytes()
    var result = String("")
    var i = 0

    while i < n:
        var current = Int(bs[i])
        var count = 1
        while i + count < n and Int(bs[i + count]) == current:
            count += 1
        result += _int_to_string(count)
        result += chr(current)
        i += count

    return result


fn rle_decode_string(compressed: String) -> String:
    """Decompress an RLE-encoded string. E.g., "3A2B1C" → "AAABBC"."""
    var n = len(compressed)
    if n == 0:
        return String("")

    var bs = compressed.as_bytes()
    var result = String("")
    var i = 0

    while i < n:
        # Read digits for count
        var count = 0
        while i < n and Int(bs[i]) >= 48 and Int(bs[i]) <= 57:
            count = count * 10 + (Int(bs[i]) - 48)
            i += 1
        # Read the character
        if i < n:
            var ch = chr(Int(bs[i]))
            for _ in range(count):
                result += ch
            i += 1

    return result


# ── Utility ──────────────────────────────────────────────────────────────────


fn compression_ratio(original_size: Int, compressed_size: Int) -> Float64:
    """Compute compression ratio = original_size / compressed_size.

    Returns 0.0 if compressed_size is 0.
    """
    if compressed_size == 0:
        return 0.0
    return Float64(original_size) / Float64(compressed_size)
