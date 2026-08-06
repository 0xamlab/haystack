"""test_tensorx_shape.mojo — known-value tests for N-D shape, strides and broadcasting.

Hand-written. The reference numbers for broadcasting are cross-checked against
`numpy.broadcast_shapes`, run for real rather than guessed:

    numpy.broadcast_shapes((3,), (4, 3))            -> (4, 3)
    numpy.broadcast_shapes((5, 1, 4), (1, 3, 4))     -> (5, 3, 4)
    numpy.broadcast_shapes((), (5,))                -> (5,)
    numpy.broadcast_shapes((2, 3), (3, 2))           -> ValueError (incompatible)

The assertions target the failures that produce a plausible wrong shape rather than an error: a rank
read from an untrusted integer and used to size a loop with no ceiling, trailing-side padding instead
of leading-side (which broadcasts over the wrong axis), and a strides comparison that reads past a
shorter list than the dims it is checked against.
"""
from tensorx.contract import (
    TX_ERR_BROADCAST_INCOMPATIBLE,
    TX_ERR_EMPTY,
    TX_ERR_LENGTH_MISMATCH,
    TX_ERR_RANK_TOO_HIGH,
    TX_ERR_SHAPE_MISMATCH,
    TX_OK,
)
from tensorx.shape import (
    TX_MAX_RANK,
    tx_shape_broadcast_dims,
    tx_shape_broadcastable,
    tx_shape_broadcast_status,
    tx_shape_is_contiguous,
    tx_shape_make,
    tx_shape_numel,
    tx_shape_status,
    tx_shape_strides,
    tx_shape_validate,
)


def _dims(a: Int, b: Int = -1, c: Int = -1, d: Int = -1) -> List[Int]:
    """Small helper: build a dims list from up to four values, stopping at the first -1."""
    var out = List[Int]()
    out.append(a)
    if b != -1:
        out.append(b)
    if c != -1:
        out.append(c)
    if d != -1:
        out.append(d)
    return out^


def _dims_eq(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── basic validity ──────────────────────────────────────────────────────────
    var d234 = _dims(2, 3, 4)
    if tx_shape_status(d234, 3) == TX_OK and tx_shape_numel(d234, 3) == 24:
        passed += 1
        print("  ✅ a 3-D shape (2,3,4) is valid with numel 24")
    else:
        failed += 1
        print("  ❌ a 3-D shape was misjudged:", tx_shape_status(d234, 3), tx_shape_numel(d234, 3))

    # rank 0 is a scalar, not an error.
    var empty_dims = List[Int]()
    if tx_shape_status(empty_dims, 0) == TX_OK and tx_shape_numel(empty_dims, 0) == 1:
        passed += 1
        print("  ✅ rank 0 is a valid scalar shape with numel 1")
    else:
        failed += 1
        print("  ❌ rank 0 was not treated as a scalar")

    # A zero or negative dimension is EMPTY, not a generic 'too large'.
    var d_zero = _dims(3, 0)
    if tx_shape_status(d_zero, 2) == TX_ERR_EMPTY and tx_shape_numel(d_zero, 2) == 0:
        passed += 1
        print("  ✅ a zero dimension reports empty, distinct from 'too large'")
    else:
        failed += 1
        print("  ❌ a zero dimension was not reported as empty")

    # rank cannot exceed TX_MAX_RANK, and TX_MAX_RANK is what the docstring says it is.
    var rank_ok = TX_MAX_RANK == 8
    var d9 = List[Int]()
    for _ in range(TX_MAX_RANK + 1):
        d9.append(2)
    if tx_shape_status(d9, TX_MAX_RANK + 1) != TX_ERR_RANK_TOO_HIGH:
        rank_ok = False
    if rank_ok:
        passed += 1
        print("  ✅ a rank past TX_MAX_RANK (8) is refused before any dimension is read")
    else:
        failed += 1
        print("  ❌ an over-rank shape was not refused, or TX_MAX_RANK drifted from 8")

    # rank cannot exceed the dims list actually supplied, even when it is still within
    # TX_MAX_RANK — this is the case the A-Z harness's fixed 5-element/`n=5` shape could hit for
    # a 3-element dims list with rank=5.
    if tx_shape_status(d234, 5) == TX_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ rank=5 over a 3-element dims list is refused, not an uncatchable abort")
    else:
        failed += 1
        print("  ❌ tx_shape_status read past the end of its dims list")

    # ── contiguous row-major strides ─────────────────────────────────────────────
    var strides234 = tx_shape_strides(d234, 3)
    var expected234 = _dims(12, 4, 1)
    if _dims_eq(strides234, expected234):
        passed += 1
        print("  ✅ (2,3,4) has row-major strides (12,4,1)")
    else:
        failed += 1
        print("  ❌ tx_shape_strides drifted from the hand-computed row-major strides")

    if tx_shape_is_contiguous(d234, strides234, 3):
        passed += 1
        print("  ✅ the strides tx_shape_strides itself produced are recognised as contiguous")
    else:
        failed += 1
        print("  ❌ tx_shape_is_contiguous rejected its own sibling's output")

    var bad_strides = _dims(1, 4, 1)
    if not tx_shape_is_contiguous(d234, bad_strides, 3):
        passed += 1
        print("  ✅ a permuted (non-contiguous) stride pattern is rejected")
    else:
        failed += 1
        print("  ❌ tx_shape_is_contiguous accepted a permuted stride pattern")

    # A strides list shorter than the rank being checked must not be read past its end.
    var short_strides = _dims(12, 4)
    if not tx_shape_is_contiguous(d234, short_strides, 3):
        passed += 1
        print("  ✅ a strides list shorter than rank is refused, not read past its end")
    else:
        failed += 1
        print("  ❌ tx_shape_is_contiguous read past a short strides list")

    # ── exact validation against a data length ───────────────────────────────────
    if tx_shape_validate(d234, 3, 24) == TX_OK:
        passed += 1
        print("  ✅ tx_shape_validate accepts a buffer whose length matches exactly")
    else:
        failed += 1
        print("  ❌ tx_shape_validate rejected an exact match")

    if (
        tx_shape_validate(d234, 3, 25) == TX_ERR_SHAPE_MISMATCH
        and tx_shape_validate(d234, 3, 23) == TX_ERR_SHAPE_MISMATCH
    ):
        passed += 1
        print("  ✅ a buffer too long or too short is rejected, not silently truncated or padded")
    else:
        failed += 1
        print("  ❌ tx_shape_validate accepted a buffer whose length disagreed with the shape")

    # ── broadcasting, cross-checked against numpy.broadcast_shapes ──────────────
    # numpy.broadcast_shapes((3,), (4, 3)) -> (4, 3)
    var d3 = _dims(3)
    var d43 = _dims(4, 3)
    var bshape1 = tx_shape_broadcast_dims(d3, 1, d43, 2)
    if _dims_eq(bshape1, d43) and tx_shape_broadcastable(d3, 1, d43, 2):
        passed += 1
        print("  ✅ (3,) broadcasts against (4,3) to (4,3), matching numpy.broadcast_shapes")
    else:
        failed += 1
        print("  ❌ (3,) vs (4,3) broadcast result drifted from numpy")

    # numpy.broadcast_shapes((5,1,4), (1,3,4)) -> (5,3,4)
    var d514 = _dims(5, 1, 4)
    var d134 = _dims(1, 3, 4)
    var bshape2 = tx_shape_broadcast_dims(d514, 3, d134, 3)
    var expected2 = _dims(5, 3, 4)
    if _dims_eq(bshape2, expected2):
        passed += 1
        print("  ✅ (5,1,4) broadcasts against (1,3,4) to (5,3,4), matching numpy")
    else:
        failed += 1
        print("  ❌ (5,1,4) vs (1,3,4) broadcast result drifted from numpy")

    # numpy.broadcast_shapes((), (5,)) -> (5,) — a scalar broadcasts against anything.
    var d5 = _dims(5)
    var bshape3 = tx_shape_broadcast_dims(empty_dims, 0, d5, 1)
    if _dims_eq(bshape3, d5):
        passed += 1
        print("  ✅ a scalar (rank 0) broadcasts against (5,) to (5,), matching numpy")
    else:
        failed += 1
        print("  ❌ scalar broadcasting drifted from numpy")

    # numpy.broadcast_shapes((2,3), (3,2)) -> ValueError: incompatible.
    var d23 = _dims(2, 3)
    var d32 = _dims(3, 2)
    if (
        tx_shape_broadcast_status(d23, 2, d32, 2) == TX_ERR_BROADCAST_INCOMPATIBLE
        and not tx_shape_broadcastable(d23, 2, d32, 2)
        and len(tx_shape_broadcast_dims(d23, 2, d32, 2)) == 0
    ):
        passed += 1
        print("  ✅ (2,3) vs (3,2) is refused as incompatible, matching numpy's ValueError")
    else:
        failed += 1
        print("  ❌ an incompatible shape pair was not refused")

    # Padding must be on the LEADING side. A caller migrating a real op must broadcast (3,) against
    # (4,3) as (1,3), never as (3,1) — the latter would silently broadcast over the wrong axis.
    # (3,) padded on the leading side is (1,3); against (3,1) that gives (3,3) — both axes have a
    # 1 on one side, so this is compatible, and numpy.broadcast_shapes((3,), (3,1)) agrees.
    var d31 = _dims(3, 1)
    var np_agrees = tx_shape_broadcastable(d3, 1, d31, 2) and _dims_eq(
        tx_shape_broadcast_dims(d3, 1, d31, 2), _dims(3, 3)
    )
    if np_agrees:
        passed += 1
        print("  ✅ (3,) vs (3,1) broadcasts to (3,3) via leading-side padding, matching numpy")
    else:
        failed += 1
        print("  ❌ leading-side padding drifted from numpy's broadcasting rule")

    # rank past TX_MAX_RANK must be refused before any per-axis comparison.
    if tx_shape_broadcast_status(d9, TX_MAX_RANK + 1, d5, 1) == TX_ERR_RANK_TOO_HIGH:
        passed += 1
        print("  ✅ broadcasting refuses an over-rank shape before comparing any axis")
    else:
        failed += 1
        print("  ❌ broadcasting did not check rank before comparing axes")

    # ── the one-call constructor ─────────────────────────────────────────────────
    var shp = tx_shape_make(d234, 3)
    if (
        shp.status == TX_OK
        and shp.numel == 24
        and shp.rank == 3
        and _dims_eq(shp.strides, expected234)
    ):
        passed += 1
        print("  ✅ tx_shape_make bundles dims, strides and numel consistently")
    else:
        failed += 1
        print("  ❌ tx_shape_make produced an inconsistent TxShape")

    var bad_shp = tx_shape_make(d_zero, 2)
    if bad_shp.status == TX_ERR_EMPTY and len(bad_shp.dims) == 0 and bad_shp.numel == 0:
        passed += 1
        print("  ✅ a rejected shape carries no stale dims or numel")
    else:
        failed += 1
        print("  ❌ a rejected TxShape leaked partial data")

    print()
    print("[tensorx.shape] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("tensorx.shape known-value suite failed")
