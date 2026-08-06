"""
tensorx.buffer — a `List[UInt8]` tagged with a dtype and a shape: the thing every other tensorx
file operates on. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, float32, bfloat16, float16, float8_e4m3fn, float8_e5m2, int8, uint8
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_tensorx_buffer.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Which dtypes a buffer can hold as VALUES
-------------------------------------------
Eight of `tensorx.dtype`'s ten codes are self-contained: a byte sequence alone, plus the dtype tag,
determines the value — `float64`, `float32`, `bfloat16`, `float16`, `float8_e4m3fn`, `float8_e5m2`,
`int8`, `uint8`. `int4` and `nf4` are NOT: a 4-bit code is only a value together with the per-block
scale that produced it, and that scale lives in a `tensorx.pack.BlockQuant`, not in this buffer. So a
`TxBuffer` of dtype `int4` or `nf4` is refused here with `TX_ERR_DTYPE_UNSUPPORTED_FOR_OP` — reporting
an "elementwise value" for a code with no scale attached would be a confident wrong number, which is
exactly what rule 4 exists to prevent. Quantize and dequantize sub-byte tensors through
`tensorx.pack` and hold the codes and scales as two ordinary `TxBuffer`s (codes as `int8`, scales as
`float32`) if a caller wants them buffer-shaped.

Encoding is the compiler's own bitcast, not a hand-rolled layout
--------------------------------------------------------------------
Every encode/decode here goes through `std.memory.bitcast` between the dtype's native `Scalar` and an
unsigned integer of the same width, then that integer is spread across bytes LITTLE-ENDIAN — the
native byte order on every target this repo builds for (Apple Silicon and x86-64 are both
little-endian). Verified directly against the compiler before this module was written: `bitcast`
round-trips `bfloat16 <-> uint16` and `float8_e4m3fn <-> uint8` exactly, including negative values
(`bf16(-0.75)` survives `bitcast[uint16]` then back). Nothing here re-derives IEEE bit layouts by
hand; the one thing owned locally is the byte ORDER, which is a policy choice, not a hardware fact to
get wrong.

Why the public surface is flat lists, and `TxBuffer` stays local to this file
----------------------------------------------------------------------------------
Per rule 2, a struct returned from a public driver must be declared in the SAME file the driver is in,
or the runtime-contract generator silently drops the function. `tensorx.elementwise` and
`tensorx.reduce` both need to decode and encode buffers, so rather than have them take a `TxBuffer`
across a file boundary — safe in this tree's current dispatch generator by direct test, but the
documented hazard this whole rule exists for — they call the FLAT functions below
(`tx_buf_decode_flat` / `tx_buf_encode_flat` / `tx_buf_required_bytes_flat`) directly, passing
`(bytes, n, dtype)` rather than a `TxBuffer`. `TxBuffer` itself is a same-file convenience for a
caller that wants one value carrying its own shape.

Public API:
  tx_buf_element_width_bytes(dtype)                       — 1/2/4/8, or 0 for a non-value-bearing dtype
  tx_buf_required_bytes_flat(n, dtype)                     — exact bytes for n self-contained elements
  tx_buf_required_bytes(dims, rank, dtype)                 — the shaped version, via tensorx.shape
  tx_buf_encode_flat(values, n, dtype) / tx_buf_decode_flat(data, n, dtype)
  TxBuffer / tx_buf_make(values, n, dims, rank, dtype) / tx_buf_to_values(buf)
"""

from std.memory import bitcast

from tensorx.contract import (
    TX_ERR_DTYPE_UNSUPPORTED_FOR_OP,
    TX_ERR_LENGTH_MISMATCH,
    TX_ERR_NEGATIVE_COUNT,
    TX_ERR_SHAPE_MISMATCH,
    TX_MAX_ELEMS,
    TX_OK,
    tx_finite,
)
from tensorx.dtype import (
    DT_BF16,
    DT_F16,
    DT_F32,
    DT_F64,
    DT_F8E4M3,
    DT_F8E5M2,
    DT_I8,
    DT_U8,
    dtx_is_supported,
    dtx_is_sub_byte,
)
from tensorx.shape import tx_shape_numel, tx_shape_status


@fieldwise_init
struct TxBuffer(Copyable, Movable):
    """Raw bytes plus the dtype and shape that give them meaning.

    `dims` is truncated to `rank` entries and `data` is empty on any failure, matching `TxShape`'s
    convention — a caller that forgets to check `status` reads an empty buffer, never a partial one.
    """

    var data: List[UInt8]
    var dims: List[Int]
    var rank: Int
    var dtype: Int
    var status: Int


def tx_buf_element_width_bytes(dtype: Int) -> Int:
    """Byte width of ONE element for a self-contained dtype. `0` for `int4`/`nf4` (sub-byte, and not
    addressable this way — see the module docstring) and for any unsupported code.
    """
    if dtx_is_sub_byte(dtype) or not dtx_is_supported(dtype):
        return 0
    if dtype == DT_F64:
        return 8
    if dtype == DT_F32:
        return 4
    if dtype == DT_BF16 or dtype == DT_F16:
        return 2
    if dtype == DT_F8E4M3 or dtype == DT_F8E5M2 or dtype == DT_I8 or dtype == DT_U8:
        return 1
    return 0


def tx_buf_required_bytes_flat(n: Int, dtype: Int) -> Int:
    """Exact byte length needed for `n` self-contained elements of `dtype`. `-1` if `n` is negative,
    exceeds the package ceiling, or `dtype` cannot be held this way.
    """
    if n < 0 or n > TX_MAX_ELEMS:
        return -1
    var width = tx_buf_element_width_bytes(dtype)
    if width == 0:
        return -1
    return n * width


def tx_buf_required_bytes(dims: List[Int], rank: Int, dtype: Int) -> Int:
    """The shaped version of `tx_buf_required_bytes_flat`: element count comes from `tensorx.shape`
    rather than being taken on faith from a caller-supplied `n`.

    @capability tx_buf_required_bytes
    complexity: O(rank)
    counts:
    - rank <= len(dims) [enforced]
    @endcapability
    """
    if tx_shape_status(dims, rank) != TX_OK:
        return -1
    var n = tx_shape_numel(dims, rank)
    return tx_buf_required_bytes_flat(n, dtype)


def _encode_one(value: Float64, dtype: Int, mut out: List[UInt8]) -> Bool:
    """Append the little-endian byte encoding of one value to `out`. False (nothing appended) if
    `dtype` is not self-contained.
    """
    if dtype == DT_F64:
        var bits = bitcast[DType.uint64](Float64(value))
        for shift in range(8):
            out.append(UInt8((bits >> UInt64(8 * shift)) & 0xFF))
        return True
    if dtype == DT_F32:
        var bits32 = bitcast[DType.uint32](Float32(value))
        for shift in range(4):
            out.append(UInt8((bits32 >> UInt32(8 * shift)) & 0xFF))
        return True
    if dtype == DT_BF16:
        var b16 = bitcast[DType.uint16](Scalar[DType.bfloat16](Float32(value)))
        out.append(UInt8(b16 & 0xFF))
        out.append(UInt8((b16 >> 8) & 0xFF))
        return True
    if dtype == DT_F16:
        var h16 = bitcast[DType.uint16](Scalar[DType.float16](Float32(value)))
        out.append(UInt8(h16 & 0xFF))
        out.append(UInt8((h16 >> 8) & 0xFF))
        return True
    if dtype == DT_F8E4M3:
        out.append(bitcast[DType.uint8](Scalar[DType.float8_e4m3fn](Float32(value))))
        return True
    if dtype == DT_F8E5M2:
        out.append(bitcast[DType.uint8](Scalar[DType.float8_e5m2](Float32(value))))
        return True
    if dtype == DT_I8:
        # Clamp before converting: Int64(v) for |v| beyond Int8's range is undefined, not
        # saturating (rule 4c). The clamp happens in Float64, then one narrowing cast.
        var clamped = value
        if clamped > 127.0:
            clamped = 127.0
        if clamped < -128.0:
            clamped = -128.0
        out.append(bitcast[DType.uint8](Int8(Int(clamped))))
        return True
    if dtype == DT_U8:
        var clamped_u = value
        if clamped_u > 255.0:
            clamped_u = 255.0
        if clamped_u < 0.0:
            clamped_u = 0.0
        out.append(UInt8(Int(clamped_u)))
        return True
    return False


def _decode_one(data: List[UInt8], offset: Int, dtype: Int) -> Float64:
    """Decode one little-endian element of `dtype` starting at byte `offset`. Caller guarantees
    `offset + width <= len(data)`; this helper only assembles bytes it is handed.
    """
    if dtype == DT_F64:
        var bits: UInt64 = 0
        for shift in range(8):
            bits = bits | (UInt64(data[offset + shift]) << UInt64(8 * shift))
        return Float64(bitcast[DType.float64](bits))
    if dtype == DT_F32:
        var bits32: UInt32 = 0
        for shift in range(4):
            bits32 = bits32 | (UInt32(data[offset + shift]) << UInt32(8 * shift))
        return Float64(bitcast[DType.float32](bits32))
    if dtype == DT_BF16:
        var b16: UInt16 = UInt16(data[offset]) | (UInt16(data[offset + 1]) << 8)
        return Float64(bitcast[DType.bfloat16](b16).cast[DType.float64]())
    if dtype == DT_F16:
        var h16: UInt16 = UInt16(data[offset]) | (UInt16(data[offset + 1]) << 8)
        return Float64(bitcast[DType.float16](h16).cast[DType.float64]())
    if dtype == DT_F8E4M3:
        return Float64(bitcast[DType.float8_e4m3fn](data[offset]).cast[DType.float64]())
    if dtype == DT_F8E5M2:
        return Float64(bitcast[DType.float8_e5m2](data[offset]).cast[DType.float64]())
    if dtype == DT_I8:
        return Float64(bitcast[DType.int8](data[offset]))
    if dtype == DT_U8:
        return Float64(data[offset])
    return 0.0


def tx_buf_encode_flat(values: List[Float64], n: Int, dtype: Int) -> List[UInt8]:
    """Encode the first `n` entries of `values` into raw little-endian bytes of `dtype`.

    Empty on a negative or out-of-range `n`, on a dtype this buffer cannot hold as values (`int4`,
    `nf4`, or anything unsupported), or on a non-finite input — a NaN or infinity bit-pattern is not
    invented here; the caller sees an empty result rather than a silently poisoned buffer.

    @capability tx_buf_encode_flat
    complexity: O(n)
    counts:
    - n <= len(values) [enforced]
    @endcapability
    """
    var out = List[UInt8]()
    if n < 0 or n > len(values) or n > TX_MAX_ELEMS:
        return out^
    if tx_buf_element_width_bytes(dtype) == 0:
        return out^
    for i in range(n):
        if not tx_finite(values[i]):
            return List[UInt8]()
        if not _encode_one(values[i], dtype, out):
            return List[UInt8]()
    return out^


def tx_buf_decode_flat(data: List[UInt8], n: Int, dtype: Int) -> List[Float64]:
    """Decode `n` elements of `dtype` from `data`, starting at byte 0.

    Empty if `n` is negative or out of range, if `dtype` cannot be held as values, or if `data` is
    too short to hold `n` elements — the last of which is the guard that keeps this an O(n) bounded
    read rather than the uncatchable abort a raw `data[offset]` would give past the buffer's end.

    @capability tx_buf_decode_flat
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    var need = tx_buf_required_bytes_flat(n, dtype)
    if need < 0 or need > len(data):
        return out^
    var width = tx_buf_element_width_bytes(dtype)
    for i in range(n):
        out.append(_decode_one(data, i * width, dtype))
    return out^


def tx_buf_make(
    values: List[Float64], n: Int, dims: List[Int], rank: Int, dtype: Int
) -> TxBuffer:
    """Build a `TxBuffer` from `n` flat values reshaped to `dims[0:rank]`.

    `n` must equal the shape's own element count EXACTLY — the same "no silent prefix, no silent
    pad" rule `tx_shape_validate` and `tx_shape_ok` both enforce, applied here before any byte is
    written rather than after.

    @capability tx_buf_make
    complexity: O(n)
    counts:
    - n <= len(values) [enforced]
    @endcapability
    """
    if n < 0:
        return TxBuffer(List[UInt8](), List[Int](), 0, dtype, TX_ERR_NEGATIVE_COUNT)
    if tx_shape_status(dims, rank) != TX_OK:
        return TxBuffer(List[UInt8](), List[Int](), 0, dtype, tx_shape_status(dims, rank))
    var numel = tx_shape_numel(dims, rank)
    if numel != n:
        return TxBuffer(List[UInt8](), List[Int](), 0, dtype, TX_ERR_SHAPE_MISMATCH)
    if n > len(values):
        return TxBuffer(List[UInt8](), List[Int](), 0, dtype, TX_ERR_LENGTH_MISMATCH)
    if tx_buf_element_width_bytes(dtype) == 0:
        return TxBuffer(List[UInt8](), List[Int](), 0, dtype, TX_ERR_DTYPE_UNSUPPORTED_FOR_OP)
    var encoded = tx_buf_encode_flat(values, n, dtype)
    if len(encoded) != tx_buf_required_bytes_flat(n, dtype):
        return TxBuffer(List[UInt8](), List[Int](), 0, dtype, TX_ERR_LENGTH_MISMATCH)
    var out_dims = List[Int]()
    for i in range(rank):
        out_dims.append(dims[i])
    return TxBuffer(encoded^, out_dims^, rank, dtype, TX_OK)


def tx_buf_to_values(buf: TxBuffer) -> List[Float64]:
    """Decode a whole `TxBuffer` back to a flat `List[Float64]`, in the buffer's own row-major order.

    Same-file struct parameter, per rule 2 — this function and `TxBuffer` are both declared here.
    """
    if buf.status != TX_OK:
        return List[Float64]()
    var numel = tx_shape_numel(buf.dims, buf.rank)
    return tx_buf_decode_flat(buf.data, numel, buf.dtype)
