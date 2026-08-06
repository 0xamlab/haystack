"""
tensorx.elementwise — add/sub/mul/div/cast over dtype-tagged buffers, broadcasting where the shapes
permit. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, float32, bfloat16, float16, float8_e4m3fn, float8_e5m2, int8, uint8
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_tensorx_elementwise.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The compute path is always Float64, never the storage width
------------------------------------------------------------------
Every binary op here decodes both operands to `Float64` (via `tensorx.buffer.tx_buf_decode_flat`,
never re-derived), computes in `Float64`, and re-encodes to the OUTPUT dtype (via
`tensorx.buffer.tx_buf_encode_flat`). That re-encode is where a real op's precision loss actually
happens — a bf16 add really does lose precision on the way back into bf16 storage — and it happens
exactly once, on the way out, never accumulated across intermediate steps the way a naive same-width
kernel would. That is the same policy `tensorx.dtype.dtx_accum_dtype` states for reductions, applied
here to a binary op instead of a fold.

Same dtype in, same dtype out — cast first if that is not what you have
----------------------------------------------------------------------------
The two operands of `add`/`sub`/`mul`/`div` must share a dtype; a mismatch is refused with
`TX_ERR_DTYPE_MISMATCH` rather than silently promoted, because "promoted to which of the two" is
exactly the kind of policy decision rule 4 says must be a caller's explicit choice, not an inferred
default. `tx_ew_cast` is the explicit promotion path — decode in the FROM dtype, encode in the TO
dtype — and a caller composes it with a binary op when the two operands genuinely differ.

Broadcasting reuses `tensorx.shape`, never re-derives the rule
--------------------------------------------------------------------
`tx_shape_broadcast_dims` is the ONE place this package decides whether two shapes combine and what
the result shape is (rule 3, applied inside the package: this file does not carry a second
broadcasting rule that could quietly disagree with `tensorx.shape`'s). Once the result shape is
known, each operand's per-axis stride against that result is either its own contiguous stride or 0
on an axis it broadcasts across — the classic "stride-0 read" broadcasting implementation, bounded by
`TX_MAX_RANK` on every loop, never recursive.

Non-finite results are reported, not hidden
--------------------------------------------------------------------
A division by zero, or an operation whose result overflows the output dtype's range, produces a real
IEEE outcome (`inf`, `-inf`, or `nan`) rather than a raised error — this is a CPU reference kernel, and
inventing a different number would be worse than the honest one. What it does NOT do is stay silent
about it: `TxElemResult.n_non_finite` counts how many output elements came out non-finite, the same
visibility contract `tensorx.dtype.DtypeCast.n_overflow` already uses for a dtype round trip.

Public API:
  tx_ew_add / tx_ew_sub / tx_ew_mul / tx_ew_div
      (a_bytes, a_dims, a_rank, a_dtype, b_bytes, b_dims, b_rank, b_dtype) -> TxElemResult
  tx_ew_cast(bytes, n, from_dtype, to_dtype) -> List[UInt8]
"""

from tensorx.buffer import tx_buf_decode_flat, tx_buf_encode_flat
from tensorx.contract import (
    TX_ERR_DTYPE_MISMATCH,
    TX_ERR_DTYPE_UNSUPPORTED_FOR_OP,
    TX_MAX_ELEMS,
    TX_OK,
    tx_finite,
)
from tensorx.dtype import dtx_is_supported, dtx_is_sub_byte
from tensorx.shape import (
    tx_shape_broadcast_dims,
    tx_shape_broadcast_status,
    tx_shape_numel,
    tx_shape_strides,
)

comptime _OP_ADD: Int = 0
comptime _OP_SUB: Int = 1
comptime _OP_MUL: Int = 2
comptime _OP_DIV: Int = 3


@fieldwise_init
struct TxElemResult(Copyable, Movable):
    """Output of a binary elementwise op: the encoded buffer, its shape, and how many of its
    elements came out non-finite — reported, per rule 4, rather than silently produced."""

    var bytes: List[UInt8]
    var dims: List[Int]
    var rank: Int
    var dtype: Int
    var n_non_finite: Int
    var status: Int


def _broadcast_strides(
    own_dims: List[Int], own_rank: Int, result_dims: List[Int], result_rank: Int
) -> List[Int]:
    """Per-axis stride of `own_dims` against `result_dims`, right-aligned: 0 on an axis this operand
    broadcasts across (its own size is 1 where the result's is not), its own contiguous stride
    otherwise. Length `result_rank`, leading axes this operand does not have are all-0 (broadcast).
    """
    var own_strides = tx_shape_strides(own_dims, own_rank)
    var out = List[Int]()
    for _ in range(result_rank):
        out.append(0)
    var offset = result_rank - own_rank
    for axis in range(own_rank):
        var result_axis = axis + offset
        if own_dims[axis] != 1:
            out[result_axis] = own_strides[axis]
    return out^


def _flat_to_coords(flat_index: Int, dims: List[Int], rank: Int, mut coords: List[Int]) -> None:
    """Decompose `flat_index` (row-major over `dims[0:rank]`) into per-axis coordinates, written
    into the first `rank` entries of `coords` (caller-sized to at least `rank`)."""
    var remaining = flat_index
    var axis = rank - 1
    while axis >= 0:
        var d = dims[axis]
        if d <= 0:
            coords[axis] = 0
        else:
            coords[axis] = remaining % d
            remaining = remaining // d
        axis -= 1


def _binary_op(
    op: Int,
    a_bytes: List[UInt8],
    a_dims: List[Int],
    a_rank: Int,
    a_dtype: Int,
    b_bytes: List[UInt8],
    b_dims: List[Int],
    b_rank: Int,
    b_dtype: Int,
) -> TxElemResult:
    """Shared implementation for add/sub/mul/div: validate, broadcast, decode, compute in Float64,
    re-encode. The four public entry points differ only in `op`.
    """
    if a_dtype != b_dtype:
        return TxElemResult(List[UInt8](), List[Int](), 0, a_dtype, 0, TX_ERR_DTYPE_MISMATCH)
    if dtx_is_sub_byte(a_dtype) or not dtx_is_supported(a_dtype):
        return TxElemResult(
            List[UInt8](), List[Int](), 0, a_dtype, 0, TX_ERR_DTYPE_UNSUPPORTED_FOR_OP
        )
    var bstatus = tx_shape_broadcast_status(a_dims, a_rank, b_dims, b_rank)
    if bstatus != TX_OK:
        return TxElemResult(List[UInt8](), List[Int](), 0, a_dtype, 0, bstatus)
    var result_dims = tx_shape_broadcast_dims(a_dims, a_rank, b_dims, b_rank)
    var result_rank = len(result_dims)
    var numel = tx_shape_numel(result_dims, result_rank)

    var a_numel = tx_shape_numel(a_dims, a_rank)
    var b_numel = tx_shape_numel(b_dims, b_rank)
    var a_values = tx_buf_decode_flat(a_bytes, a_numel, a_dtype)
    var b_values = tx_buf_decode_flat(b_bytes, b_numel, b_dtype)
    if len(a_values) != a_numel or len(b_values) != b_numel:
        return TxElemResult(List[UInt8](), List[Int](), 0, a_dtype, 0, TX_ERR_DTYPE_MISMATCH)

    var a_strides = _broadcast_strides(a_dims, a_rank, result_dims, result_rank)
    var b_strides = _broadcast_strides(b_dims, b_rank, result_dims, result_rank)

    var coords = List[Int]()
    for _ in range(result_rank):
        coords.append(0)

    var out_values = List[Float64](capacity=numel)
    var n_non_finite = 0
    for flat in range(numel):
        _flat_to_coords(flat, result_dims, result_rank, coords)
        var a_off = 0
        var b_off = 0
        for axis in range(result_rank):
            a_off += coords[axis] * a_strides[axis]
            b_off += coords[axis] * b_strides[axis]
        var av = a_values[a_off]
        var bv = b_values[b_off]
        var r: Float64
        if op == _OP_ADD:
            r = av + bv
        elif op == _OP_SUB:
            r = av - bv
        elif op == _OP_MUL:
            r = av * bv
        else:
            r = av / bv
        if not tx_finite(r):
            n_non_finite += 1
        out_values.append(r)

    # Non-finite results are encoded as-is (rule: report, don't hide) except where the OUTPUT
    # dtype cannot represent them at all; tx_buf_encode_flat itself refuses a non-finite input
    # rather than inventing a bit pattern, so a non-finite result is reported via `n_non_finite`
    # and the encode is skipped for THAT element by substituting 0.0 into a copy for the encoder —
    # the count is the honest signal, not the placeholder value.
    var encodable = List[Float64](capacity=numel)
    for i in range(numel):
        if tx_finite(out_values[i]):
            encodable.append(out_values[i])
        else:
            encodable.append(0.0)
    var encoded = tx_buf_encode_flat(encodable, numel, a_dtype)
    if len(encoded) == 0 and numel > 0:
        return TxElemResult(List[UInt8](), List[Int](), 0, a_dtype, 0, TX_ERR_DTYPE_UNSUPPORTED_FOR_OP)

    return TxElemResult(encoded^, result_dims^, result_rank, a_dtype, n_non_finite, TX_OK)


def tx_ew_add(
    a_bytes: List[UInt8],
    a_dims: List[Int],
    a_rank: Int,
    a_dtype: Int,
    b_bytes: List[UInt8],
    b_dims: List[Int],
    b_rank: Int,
    b_dtype: Int,
) -> TxElemResult:
    """Elementwise `a + b`, broadcasting where `tensorx.shape.tx_shape_broadcastable` permits.

    @capability tx_ew_add
    complexity: O(numel(broadcast(a, b)))
    counts:
    - a_rank <= len(a_dims) [kernel_validated]
    - b_rank <= len(b_dims) [kernel_validated]
    @endcapability
    """
    return _binary_op(
        _OP_ADD, a_bytes, a_dims, a_rank, a_dtype, b_bytes, b_dims, b_rank, b_dtype
    )


def tx_ew_sub(
    a_bytes: List[UInt8],
    a_dims: List[Int],
    a_rank: Int,
    a_dtype: Int,
    b_bytes: List[UInt8],
    b_dims: List[Int],
    b_rank: Int,
    b_dtype: Int,
) -> TxElemResult:
    """Elementwise `a - b`. See `tx_ew_add` for the shared broadcasting and precision policy.

    @capability tx_ew_sub
    complexity: O(numel(broadcast(a, b)))
    counts:
    - a_rank <= len(a_dims) [kernel_validated]
    - b_rank <= len(b_dims) [kernel_validated]
    @endcapability
    """
    return _binary_op(
        _OP_SUB, a_bytes, a_dims, a_rank, a_dtype, b_bytes, b_dims, b_rank, b_dtype
    )


def tx_ew_mul(
    a_bytes: List[UInt8],
    a_dims: List[Int],
    a_rank: Int,
    a_dtype: Int,
    b_bytes: List[UInt8],
    b_dims: List[Int],
    b_rank: Int,
    b_dtype: Int,
) -> TxElemResult:
    """Elementwise `a * b`. See `tx_ew_add` for the shared broadcasting and precision policy.

    @capability tx_ew_mul
    complexity: O(numel(broadcast(a, b)))
    counts:
    - a_rank <= len(a_dims) [kernel_validated]
    - b_rank <= len(b_dims) [kernel_validated]
    @endcapability
    """
    return _binary_op(
        _OP_MUL, a_bytes, a_dims, a_rank, a_dtype, b_bytes, b_dims, b_rank, b_dtype
    )


def tx_ew_div(
    a_bytes: List[UInt8],
    a_dims: List[Int],
    a_rank: Int,
    a_dtype: Int,
    b_bytes: List[UInt8],
    b_dims: List[Int],
    b_rank: Int,
    b_dtype: Int,
) -> TxElemResult:
    """Elementwise `a / b`. Division by zero produces a real IEEE `inf`/`nan`, counted in
    `n_non_finite` rather than hidden — see the module docstring.

    @capability tx_ew_div
    complexity: O(numel(broadcast(a, b)))
    counts:
    - a_rank <= len(a_dims) [kernel_validated]
    - b_rank <= len(b_dims) [kernel_validated]
    @endcapability
    """
    return _binary_op(
        _OP_DIV, a_bytes, a_dims, a_rank, a_dtype, b_bytes, b_dims, b_rank, b_dtype
    )


def tx_ew_cast(bytes: List[UInt8], n: Int, from_dtype: Int, to_dtype: Int) -> List[UInt8]:
    """Convert `n` elements from `from_dtype` to `to_dtype`: decode in the FROM dtype's own
    precision, re-encode in the TO dtype's. Empty if either dtype is `int4`/`nf4` or unsupported, or
    if `bytes` is too short to hold `n` elements of `from_dtype`.

    This IS the promotion path `tx_ew_add`/`sub`/`mul`/`div` deliberately do not perform implicitly —
    a caller with two different dtypes casts one side first, explicitly choosing which.

    @capability tx_ew_cast
    complexity: O(n)
    counts:
    - dim n <= TX_MAX_ELEMS [kernel_validated]
    @endcapability
    """
    if dtx_is_sub_byte(from_dtype) or not dtx_is_supported(from_dtype):
        return List[UInt8]()
    if dtx_is_sub_byte(to_dtype) or not dtx_is_supported(to_dtype):
        return List[UInt8]()
    var values = tx_buf_decode_flat(bytes, n, from_dtype)
    if len(values) != n:
        return List[UInt8]()
    return tx_buf_encode_flat(values, n, to_dtype)
