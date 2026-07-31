"""test_tensorx_contract.mojo — known-value tests for the tensorx status/shape contract.

Hand-written. The assertions target the failures that return a plausible answer rather than an error:
a count larger than the buffer it indexes, a `rows * cols` product that wraps past its own guard, a
shape that is merely long enough rather than exactly right, and a status code that means two
different things.
"""
from tensorx.contract import (
    TX_ERR_COUNT_EXCEEDS_LENGTH,
    TX_ERR_DIMENSION_TOO_LARGE,
    TX_ERR_EMPTY,
    TX_ERR_NEGATIVE_COUNT,
    TX_ERR_SHAPE_MISMATCH,
    TX_MAX_ELEMS,
    TX_OK,
    tx_all_finite,
    tx_count_ok,
    tx_dims_fit,
    tx_finite,
    tx_shape_ok,
    tx_status_name,
)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── status vocabulary ─────────────────────────────────────────────────────
    # Every code names itself, and an unknown code says so instead of borrowing a neighbour's name.
    var codes = List[Int]()
    codes.append(TX_OK)
    codes.append(TX_ERR_COUNT_EXCEEDS_LENGTH)
    codes.append(TX_ERR_NEGATIVE_COUNT)
    codes.append(TX_ERR_DIMENSION_TOO_LARGE)
    codes.append(TX_ERR_SHAPE_MISMATCH)
    codes.append(TX_ERR_EMPTY)

    var distinct = True
    for i in range(len(codes)):
        for j in range(len(codes)):
            if i != j and tx_status_name(codes[i]) == tx_status_name(codes[j]):
                distinct = False
    if distinct and tx_status_name(999) == String("unknown_status"):
        passed += 1
        print("  ✅ every status names itself distinctly; an unknown code is not guessed at")
    else:
        failed += 1
        print("  ❌ status names collide or an unknown code was mislabelled")

    var in_range = True
    for i in range(len(codes)):
        if codes[i] < 300 or codes[i] > 319:
            in_range = False
    if in_range:
        passed += 1
        print("  ✅ all status codes sit inside the package's 300-319 range (rule 4e)")
    else:
        failed += 1
        print("  ❌ a status code escaped the 300-319 range and may collide with another package")

    # ── finiteness ────────────────────────────────────────────────────────────
    var inf_v = 1.0 / 0.0
    var nan_v = 0.0 / 0.0
    if tx_finite(1.0) and not tx_finite(inf_v) and not tx_finite(-inf_v) and not tx_finite(nan_v):
        passed += 1
        print("  ✅ tx_finite rejects NaN and both infinities")
    else:
        failed += 1
        print("  ❌ tx_finite misclassified a non-finite value")

    # 1e300 is finite. This is the value that defeats a `_finite` guard used as an integer-range
    # check — rule 4c — so it must classify as finite here, not be quietly treated as suspect.
    if tx_finite(1e300):
        passed += 1
        print("  ✅ 1e300 is finite (the value that defeats _finite-as-a-range-check)")
    else:
        failed += 1
        print("  ❌ tx_finite wrongly rejected a large finite value")

    # ── the count relation ────────────────────────────────────────────────────
    if (
        tx_count_ok(5, 5) == TX_OK
        and tx_count_ok(6, 5) == TX_ERR_COUNT_EXCEEDS_LENGTH
        and tx_count_ok(-1, 5) == TX_ERR_NEGATIVE_COUNT
    ):
        passed += 1
        print("  ✅ 'too many' and 'negative' are distinct statuses, not one 'invalid'")
    else:
        failed += 1
        print("  ❌ tx_count_ok conflated two different caller mistakes")

    var v = List[Float64]()
    v.append(1.0)
    v.append(2.0)
    v.append(3.0)
    v.append(4.0)
    v.append(5.0)

    # The A-Z suite's exact shape: a five-element list and n = 5. This is the call that always works,
    # which is why the harness can never find the hole below it.
    if tx_all_finite(v, 5):
        passed += 1
        print("  ✅ the A-Z shape (5 elements, n=5) scans cleanly")
    else:
        failed += 1
        print("  ❌ tx_all_finite failed on the ordinary in-range case")

    # ...and the call the harness never makes.
    if not tx_all_finite(v, 25):
        passed += 1
        print("  ✅ n=25 over a 5-element list returns False instead of aborting the worker")
    else:
        failed += 1
        print("  ❌ tx_all_finite read past the end of its buffer")

    v[2] = nan_v
    if not tx_all_finite(v, 5):
        passed += 1
        print("  ✅ a NaN inside the scanned range is detected")
    else:
        failed += 1
        print("  ❌ tx_all_finite missed a NaN")
    v[2] = 3.0

    # ── the wrapping-multiply trap ────────────────────────────────────────────
    # 3 * 6148914691236517206 == 2 in wrapping 64-bit arithmetic. A guard written as
    # `if rows * cols > ceiling` passes this and the kernel then indexes a two-element buffer as if
    # it were 18 exabytes. This is not hypothetical — it aborted the worker in sparse_numerics.
    if not tx_dims_fit(3, 6148914691236517206, TX_MAX_ELEMS):
        passed += 1
        print("  ✅ the wrapping product 3 x 6148914691236517206 is refused")
    else:
        failed += 1
        print("  ❌ tx_dims_fit formed a wrapping product and accepted it")

    if tx_dims_fit(1024, 1024, TX_MAX_ELEMS) and not tx_dims_fit(TX_MAX_ELEMS, 2, TX_MAX_ELEMS):
        passed += 1
        print("  ✅ an ordinary shape fits and one past the ceiling does not")
    else:
        failed += 1
        print("  ❌ tx_dims_fit misjudged an ordinary or an oversize shape")

    if not tx_dims_fit(0, 5, TX_MAX_ELEMS) and not tx_dims_fit(-1, 5, TX_MAX_ELEMS):
        passed += 1
        print("  ✅ a zero or negative dimension does not 'fit' vacuously")
    else:
        failed += 1
        print("  ❌ tx_dims_fit accepted a non-positive dimension")

    # ── exact shape, not merely sufficient ────────────────────────────────────
    if tx_shape_ok(2, 3, 6) == TX_OK:
        passed += 1
        print("  ✅ an exact row-major shape is accepted")
    else:
        failed += 1
        print("  ❌ tx_shape_ok rejected an exact shape")

    # A longer buffer means the caller and the kernel disagree about what the data is. Using a prefix
    # would produce a confident answer for a different matrix.
    if tx_shape_ok(2, 3, 7) == TX_ERR_SHAPE_MISMATCH and tx_shape_ok(2, 3, 5) == TX_ERR_SHAPE_MISMATCH:
        passed += 1
        print("  ✅ a buffer that is too long is rejected, not silently truncated")
    else:
        failed += 1
        print("  ❌ tx_shape_ok accepted a buffer whose length disagreed with the shape")

    if tx_shape_ok(0, 3, 0) == TX_ERR_EMPTY:
        passed += 1
        print("  ✅ an empty shape reports empty rather than matching a zero-length buffer")
    else:
        failed += 1
        print("  ❌ tx_shape_ok treated an empty shape as valid")

    if TX_MAX_ELEMS == 67108864:
        passed += 1
        print("  ✅ the element ceiling is 2^26 (512 MiB of Float64)")
    else:
        failed += 1
        print("  ❌ TX_MAX_ELEMS drifted from its documented derivation")

    print("  [tensorx.contract] Passed:", passed, "Failed:", failed)
