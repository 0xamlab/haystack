"""
delta.mojo — Delta encoding/compression. Zero Python imports.
Replaces: custom delta compression utilities

Provides delta, XOR-delta, zigzag-delta, and double-delta encoding
for integer and float sequences.

Public API:
  delta_encode, delta_decode,
  delta_encode_float, delta_decode_float,
  xor_delta_encode, xor_delta_decode,
  zigzag_delta_encode, zigzag_delta_decode,
  double_delta_encode, double_delta_decode,
  compression_savings
"""


# ── Basic delta encoding ─────────────────────────────────────────────────────


def delta_encode(data: List[Int]) -> List[Int]:
    """Delta encoding: first value as-is, then differences."""
    var result = List[Int]()
    var n = len(data)
    if n == 0:
        return result^
    result.append(data[0])
    for i in range(1, n):
        result.append(data[i] - data[i - 1])
    return result^


def delta_decode(deltas: List[Int]) -> List[Int]:
    """Delta decoding: cumulative sum reconstruction."""
    var result = List[Int]()
    var n = len(deltas)
    if n == 0:
        return result^
    result.append(deltas[0])
    for i in range(1, n):
        result.append(result[i - 1] + deltas[i])
    return result^


# ── Float delta encoding ─────────────────────────────────────────────────────


def delta_encode_float(
    data: List[Float64], precision: Int = 1000
) -> List[Int]:
    """Quantize floats to int (multiply by precision) then delta encode."""
    var quantized = List[Int]()
    for i in range(len(data)):
        quantized.append(Int(data[i] * Float64(precision)))
    return delta_encode(quantized^)


def delta_decode_float(
    deltas: List[Int], precision: Int = 1000
) -> List[Float64]:
    """Delta decode then dequantize (divide by precision)."""
    var decoded = delta_decode(deltas)
    var result = List[Float64]()
    for i in range(len(decoded)):
        result.append(Float64(decoded[i]) / Float64(precision))
    return result^


# ── XOR delta encoding ──────────────────────────────────────────────────────


def xor_delta_encode(data: List[Int]) -> List[Int]:
    """XOR-based delta: first value, then XOR with previous."""
    var result = List[Int]()
    var n = len(data)
    if n == 0:
        return result^
    result.append(data[0])
    for i in range(1, n):
        result.append(data[i] ^ data[i - 1])
    return result^


def xor_delta_decode(encoded: List[Int]) -> List[Int]:
    """XOR delta decode: cumulative XOR reconstruction."""
    var result = List[Int]()
    var n = len(encoded)
    if n == 0:
        return result^
    result.append(encoded[0])
    for i in range(1, n):
        result.append(result[i - 1] ^ encoded[i])
    return result^


# ── Zigzag delta encoding ───────────────────────────────────────────────────


def _zigzag_encode_val(v: Int) -> Int:
    """Zigzag encode a signed int: maps negatives to odds, positives to evens."""
    if v >= 0:
        return v * 2
    return (-v) * 2 - 1


def _zigzag_decode_val(v: Int) -> Int:
    """Zigzag decode: inverse of zigzag encode."""
    if v % 2 == 0:
        return v // 2
    return -((v + 1) // 2)


def zigzag_delta_encode(data: List[Int]) -> List[Int]:
    """Delta + zigzag encoding for signed deltas.

    First delta-encodes, then zigzag-encodes each delta value.
    Good for sequences with small signed deltas.
    """
    var deltas = delta_encode(data)
    var result = List[Int]()
    for i in range(len(deltas)):
        result.append(_zigzag_encode_val(deltas[i]))
    return result^


def zigzag_delta_decode(encoded: List[Int]) -> List[Int]:
    """Zigzag delta decode: undo zigzag then delta decode."""
    var deltas = List[Int]()
    for i in range(len(encoded)):
        deltas.append(_zigzag_decode_val(encoded[i]))
    return delta_decode(deltas^)


# ── Double delta encoding ───────────────────────────────────────────────────


def double_delta_encode(data: List[Int]) -> List[Int]:
    """Double delta: delta of deltas. Excellent for linear sequences.

    For a perfectly linear sequence, double deltas are all zero (after first two).
    """
    var first_deltas = delta_encode(data)
    return delta_encode(first_deltas^)


def double_delta_decode(encoded: List[Int]) -> List[Int]:
    """Double delta decode: decode twice."""
    var first_decoded = delta_decode(encoded)
    return delta_decode(first_decoded^)


# ── Compression savings ─────────────────────────────────────────────────────


def compression_savings(original_bits: Int, compressed_bits: Int) -> Float64:
    """Compute compression savings: 1 - compressed/original.

    Returns value in [0, 1] where 1 = perfect compression, 0 = no savings.
    Returns 0.0 if original_bits is 0.
    """
    if original_bits <= 0:
        return 0.0
    var ratio = Float64(compressed_bits) / Float64(original_bits)
    if ratio > 1.0:
        return 0.0
    return 1.0 - ratio
