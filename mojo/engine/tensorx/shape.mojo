"""
tensorx.shape — N-dimensional shape, contiguous row-major strides, and broadcasting. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_tensorx_shape.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Why this is a separate file from `contract.mojo`'s `tx_shape_ok`
------------------------------------------------------------------
`tx_shape_ok` is the flat 2-D case: `rows * cols == data_len`, exactly, and every kernel in `gemm/`
already depends on that exact signature staying put (rule 3 — a frozen-in-spirit shape once other
code calls it). A tensor plane needs rank up to a handful of dimensions — batch, sequence, heads,
head_dim is already four — and needs to answer a question 2-D shapes never have to: whether two
shapes of DIFFERENT rank can be combined at all. That is `tx_shape_broadcastable`, and it did not fit
inside a function whose contract is "exactly two dimensions."

The product is still checked by division
-------------------------------------------
Every product here — the shape's own element count, and the two candidate shapes being tested for
broadcast compatibility — is computed by `tensorx.contract.tx_numel_checked`, the N-dimensional
sibling of `tx_dims_fit`. Nothing in this file multiplies dimensions together directly.

Rank is bounded, and the bound is a real ceiling, not decoration
--------------------------------------------------------------------
`TX_MAX_RANK` is 8. A tensor plane's real shapes rarely exceed five axes (batch, sequence, heads,
head_dim, and an occasional expert axis for MoE); eight leaves headroom without leaving the loops in
this file — every one of which is a fixed `range(rank)`, never a recursion — unbounded. A caller
that reports a higher rank is refused with `TX_ERR_RANK_TOO_HIGH` before any dimension is read, which
matters because a rank read from an untrusted integer and then used to size a loop is exactly rule
1c's hazard: a per-call cost that is bounded by a ceiling but not by anything the payload contains.

Broadcasting follows NumPy's rule, right-aligned
---------------------------------------------------
Two shapes are broadcastable when, comparing dimensions from the TRAILING axis backward, each pair
is either equal or one of them is 1. A shape with fewer dimensions is treated as having 1s implicitly
padded on its LEADING side — `(3,)` broadcasts against `(4, 3)` as if it were `(1, 3)`. This is the
rule PyTorch, NumPy and MLX all share, so a caller migrating a real broadcasting op will not encounter
a fourth interpretation. `tx_shape_broadcast_dims` returns the RESULT shape rather than a Bool alone,
so `tensorx.elementwise` calls it once and gets both the answer and the shape to compute against.

An empty `List[Int]` correctly means "scalar," not "invalid"
----------------------------------------------------------------
Rank 0 is a legitimate shape — a scalar — and its element count is 1, the product of zero factors.
`tx_numel_checked(dims, 0, ceiling)` already returns 1 for this case (see its own test), and every
function below inherits that rather than special-casing rank 0 a second time.

Public API:
  tx_shape_numel(dims, rank)                                  — checked product, 0 if invalid
  tx_shape_status(dims, rank)                                 — WHY it is or is not valid
  tx_shape_strides(dims, rank)                                — contiguous row-major strides
  tx_shape_is_contiguous(dims, strides, rank)                 — compares against the row-major answer
  tx_shape_validate(dims, rank, data_len)                     — the N-D `tx_shape_ok`
  tx_shape_broadcastable(dims_a, rank_a, dims_b, rank_b)       — right-aligned NumPy rule
  tx_shape_broadcast_dims(dims_a, rank_a, dims_b, rank_b)      — the result shape, empty if incompatible
  tx_shape_broadcast_status(dims_a, rank_a, dims_b, rank_b)    — WHY broadcasting would fail
  TxShape / tx_shape_make(dims, rank)                          — a one-call constructor bundling all
                                                                   of the above for a single shape
"""

from tensorx.contract import (
    TX_ERR_DIMENSION_TOO_LARGE,
    TX_ERR_EMPTY,
    TX_ERR_LENGTH_MISMATCH,
    TX_ERR_RANK_TOO_HIGH,
    TX_ERR_SHAPE_MISMATCH,
    TX_ERR_BROADCAST_INCOMPATIBLE,
    TX_MAX_ELEMS,
    TX_OK,
    tx_numel_checked,
)

comptime TX_MAX_RANK: Int = 8
"""Highest supported rank. Every loop in this file is `range(rank)` with `rank <= TX_MAX_RANK`
checked first, so no loop here can be driven past a small, fixed bound by a caller-supplied rank."""


@fieldwise_init
struct TxShape(Copyable, Movable):
    """A validated shape: its own dims, contiguous strides, and element count, computed once.

    `dims` and `strides` are truncated to `rank` entries on success and EMPTY on failure — a caller
    checking `status == TX_OK` before reading `numel` cannot be tricked by a stale nonzero count from
    a rejected shape, because there is no leftover data left to read.
    """

    var dims: List[Int]
    var strides: List[Int]
    var rank: Int
    var numel: Int
    var status: Int


fn tx_shape_status(dims: List[Int], rank: Int) -> Int:
    """Why `dims[0:rank]` is or is not a valid shape. `TX_OK` means every other function in this
    file will accept it.

    @capability tx_shape_status
    complexity: O(rank)
    counts:
    - rank <= len(dims) [enforced]
    @endcapability
    """
    if rank < 0:
        return TX_ERR_EMPTY
    if rank > TX_MAX_RANK:
        return TX_ERR_RANK_TOO_HIGH
    if rank > len(dims):
        return TX_ERR_LENGTH_MISMATCH
    # Checked ahead of tx_numel_checked so a non-positive dimension is named EMPTY, matching
    # tx_shape_ok's convention, rather than folded into the generic "would exceed the ceiling"
    # code a division-based overflow guard also returns for the same -1 sentinel.
    for i in range(rank):
        if dims[i] <= 0:
            return TX_ERR_EMPTY
    if tx_numel_checked(dims, rank, TX_MAX_ELEMS) < 0:
        return TX_ERR_DIMENSION_TOO_LARGE
    return TX_OK


fn tx_shape_numel(dims: List[Int], rank: Int) -> Int:
    """Element count of `dims[0:rank]`. `0` if the shape is invalid.

    `0` rather than `-1` here, unlike `tx_numel_checked`: every valid shape in THIS package has
    `numel >= 1` (rank 0 is a scalar, numel 1), so `0` is unambiguous at this layer even though the
    lower-level helper needs `-1` to distinguish "invalid" from a genuine empty product. Callers that
    need to distinguish "invalid" from "numel happens to be small" should call `tx_shape_status`
    first, the same way `tx_shape_ok` is checked before trusting a 2-D product.

    @capability tx_shape_numel
    complexity: O(rank)
    counts:
    - rank <= len(dims) [kernel_validated]
    @endcapability
    """
    if tx_shape_status(dims, rank) != TX_OK:
        return 0
    var n = tx_numel_checked(dims, rank, TX_MAX_ELEMS)
    return n if n > 0 else 0


fn tx_shape_strides(dims: List[Int], rank: Int) -> List[Int]:
    """Contiguous row-major strides for `dims[0:rank]`. Empty list if the shape is invalid.

    The last axis has stride 1; each axis moving left multiplies by the dimension to its right. This
    is the same convention `tx_shape_ok` and every 2-D kernel in `gemm/` already assume for a flat
    row-major buffer — rank 2 here reproduces exactly `[cols, 1]`.

    @capability tx_shape_strides
    complexity: O(rank)
    counts:
    - rank <= len(dims) [enforced]
    @endcapability
    """
    var out = List[Int]()
    if tx_shape_status(dims, rank) != TX_OK:
        return out^
    for _ in range(rank):
        out.append(0)
    var running = 1
    var i = rank - 1
    while i >= 0:
        out[i] = running
        running = running * dims[i]
        i -= 1
    return out^


fn tx_shape_is_contiguous(dims: List[Int], strides: List[Int], rank: Int) -> Bool:
    """True when `strides[0:rank]` is EXACTLY the row-major contiguous layout for `dims[0:rank]`.

    Bounds `rank` against both `dims` and `strides` before reading either — a caller passing a
    shorter `strides` list than `dims` claims must not read past the end of the shorter one.

    @capability tx_shape_is_contiguous
    complexity: O(rank)
    counts:
    - rank <= len(dims) [enforced]
    - rank <= len(strides) [enforced]
    @endcapability
    """
    if rank < 0 or rank > len(strides):
        return False
    var expected = tx_shape_strides(dims, rank)
    if len(expected) != rank:
        return False
    for i in range(rank):
        if strides[i] != expected[i]:
            return False
    return True


fn tx_shape_validate(dims: List[Int], rank: Int, data_len: Int) -> Int:
    """The N-dimensional `tx_shape_ok`: `dims[0:rank]`'s element count must equal `data_len` EXACTLY.

    A buffer longer than its declared shape means the caller and the kernel disagree about what the
    data is; a longer buffer is rejected the same way `tx_shape_ok` rejects one, not treated as a
    shape with trailing padding.

    @capability tx_shape_validate
    complexity: O(rank)
    counts:
    - rank <= len(dims) [enforced]
    @endcapability
    """
    var status = tx_shape_status(dims, rank)
    if status != TX_OK:
        return status
    var n = tx_numel_checked(dims, rank, TX_MAX_ELEMS)
    if n != data_len:
        return TX_ERR_SHAPE_MISMATCH
    return TX_OK


fn _padded_dim(dims: List[Int], rank: Int, result_rank: Int, axis_from_right: Int) -> Int:
    """Dimension `axis_from_right` (0 = last axis) of a shape right-aligned into `result_rank` axes.

    Implements the implicit leading-1 padding NumPy's broadcasting rule uses for a shorter shape:
    an axis beyond `rank` (i.e. further left than this shape actually has dimensions) is 1.
    """
    var offset = result_rank - rank
    if axis_from_right >= result_rank - offset:
        return 1
    var idx = rank - 1 - axis_from_right
    if idx < 0 or idx >= rank:
        return 1
    return dims[idx]


fn tx_shape_broadcast_status(
    dims_a: List[Int], rank_a: Int, dims_b: List[Int], rank_b: Int
) -> Int:
    """Why `dims_a[0:rank_a]` and `dims_b[0:rank_b]` do or do not broadcast together.

    Right-aligned NumPy rule: walking from the trailing axis backward, each pair of dimensions must
    be equal or one of them must be 1. A shape with fewer axes is padded with implicit leading 1s,
    never trailing ones — trailing padding would silently broadcast over the WRONG axis (batch
    against sequence, say) rather than refusing.

    @capability tx_shape_broadcast_status
    complexity: O(max(rank_a, rank_b))
    counts:
    - rank_a <= len(dims_a) [enforced]
    - rank_b <= len(dims_b) [enforced]
    @endcapability
    """
    var status_a = tx_shape_status(dims_a, rank_a)
    if status_a != TX_OK:
        return status_a
    var status_b = tx_shape_status(dims_b, rank_b)
    if status_b != TX_OK:
        return status_b
    var result_rank = rank_a if rank_a > rank_b else rank_b
    for axis in range(result_rank):
        var da = _padded_dim(dims_a, rank_a, result_rank, axis)
        var db = _padded_dim(dims_b, rank_b, result_rank, axis)
        if da != db and da != 1 and db != 1:
            return TX_ERR_BROADCAST_INCOMPATIBLE
    return TX_OK


fn tx_shape_broadcastable(
    dims_a: List[Int], rank_a: Int, dims_b: List[Int], rank_b: Int
) -> Bool:
    """True when the two shapes can be combined by broadcasting. See `tx_shape_broadcast_status`
    for WHY, when the answer is False.

    @capability tx_shape_broadcastable
    complexity: O(max(rank_a, rank_b))
    counts:
    - rank_a <= len(dims_a) [kernel_validated]
    - rank_b <= len(dims_b) [kernel_validated]
    @endcapability
    """
    return tx_shape_broadcast_status(dims_a, rank_a, dims_b, rank_b) == TX_OK


fn tx_shape_broadcast_dims(
    dims_a: List[Int], rank_a: Int, dims_b: List[Int], rank_b: Int
) -> List[Int]:
    """The broadcast result shape, right-aligned, or an EMPTY list if the two shapes are not
    broadcast-compatible.

    Each result axis is the larger of the two padded dimensions (equivalently, whichever side is not
    1, or either if both are 1) — never re-derived by a separate rule from
    `tx_shape_broadcast_status`, so the two functions cannot silently disagree about which shapes are
    valid.

    @capability tx_shape_broadcast_dims
    complexity: O(max(rank_a, rank_b))
    counts:
    - rank_a <= len(dims_a) [enforced]
    - rank_b <= len(dims_b) [enforced]
    @endcapability
    """
    var out = List[Int]()
    if tx_shape_broadcast_status(dims_a, rank_a, dims_b, rank_b) != TX_OK:
        return out^
    var result_rank = rank_a if rank_a > rank_b else rank_b
    for axis_from_right in range(result_rank):
        var da = _padded_dim(dims_a, rank_a, result_rank, axis_from_right)
        var db = _padded_dim(dims_b, rank_b, result_rank, axis_from_right)
        out.append(da if da > db else db)
    # `out` was built trailing-axis-first; reverse it into the natural leading-to-trailing order.
    var reversed_out = List[Int]()
    var i = len(out) - 1
    while i >= 0:
        reversed_out.append(out[i])
        i -= 1
    return reversed_out^


fn tx_shape_make(dims: List[Int], rank: Int) -> TxShape:
    """Build a `TxShape`: validated dims, contiguous strides, and element count, in one call.

    On any failure every field carrying data is empty and `numel` is 0 — a caller that forgets to
    check `status` reads zeroes and an empty shape, never a stale or partial one.

    @capability tx_shape_make
    complexity: O(rank)
    counts:
    - rank <= len(dims) [enforced]
    @endcapability
    """
    var status = tx_shape_status(dims, rank)
    if status != TX_OK:
        return TxShape(List[Int](), List[Int](), 0, 0, status)
    var out_dims = List[Int]()
    for i in range(rank):
        out_dims.append(dims[i])
    var strides = tx_shape_strides(dims, rank)
    var numel = tx_numel_checked(dims, rank, TX_MAX_ELEMS)
    return TxShape(out_dims^, strides^, rank, numel, TX_OK)
