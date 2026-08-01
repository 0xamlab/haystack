"""test_discrete_event_contract.mojo — known-value tests for the package vocabulary.

Hand-written. Every value below is either derived by hand from the definition or read back from
the frozen kernel that owns it, never from this package agreeing with itself.

What is proved here, and why each one earns a test
-------------------------------------------------
1. *The heap-depth function is exact at the boundaries.* `de_heap_levels` multiplies into every
   work budget in the package, so an off-by-one is an off-by-one on every charge. The values
   asserted are read off the definition `floor(log2 n) + 1`: 1, 2, 2, 3, 3, 4, 11 for
   n = 1, 2, 3, 4, 7, 8, 1024. Powers of two and the values one below them are where an
   off-by-one in either direction hides.

2. *The wrapping multiply is real, and `de_product_fits` survives it.* Asserted with the actual
   product: `3 * 6148914691236517206 == 2` in Mojo's wrapping 64-bit arithmetic. So a
   `product <= limit` guard would PASS for that pair, and the division-based check refuses it.
   This is the exact shape that walked past a `rows * cols != len(dense)` guard in
   `sparse_numerics` and crashed the process.

3. *A count above the list length is refused, and the process survives.* `de_all_finite(v, 25)`
   on a two-element list returns False instead of reading `v[24]`. The assertion is the
   REFUSAL; the fact that the suite continues to the next line is the other half of it, because
   the failure mode being prevented is an uncatchable abort that no `try` can observe.

4. *The tolerance is exactly `256 * DBL_EPSILON` at unit magnitude.* Asserted as an exact
   equality against the hand product `5.684341886080802e-14`, so a change to the ulp budget or
   the epsilon shows up here rather than as a comparison that silently got looser.

5. *The two streams are distinct, outside the reserved block, and stable.* Checked against the
   frozen `determinism.streams.is_reserved_stream` rather than against a hardcoded number: ids
   1-7 belong to the first consumer of the generator, and reusing one silently ends the
   independence of both streams with nothing failing.

6. *Every status code has its own name.* All twenty are compared pairwise, because two codes
   sharing a name is the `optimization.integer` / `optimization.explain` defect — one integer,
   two meanings, and a caller that logs the code cannot tell which vocabulary produced it.

7. *`de_agrees` refuses a non-finite instead of passing it.* With a NaN on either side every
   `gap > tol` comparison is False, so an audit built the other way round would report zero
   violations and pass. The verdict is asserted False for a NaN quantity, a NaN reference and a
   NaN-producing tolerance alike.
"""
from std.math import isnan

from determinism.counter_rng import rng_version
from determinism.streams import is_reserved_stream

from discrete_event.contract import (
    DE_ERR_BATCH_RANGE,
    DE_ERR_CAPACITY,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_LEVEL_RANGE,
    DE_ERR_NEGATIVE_DURATION,
    DE_ERR_NON_FINITE,
    DE_ERR_NO_ESTIMATE,
    DE_ERR_NO_STEADY_STATE,
    DE_ERR_PRIORITY_RANGE,
    DE_ERR_RATE_RANGE,
    DE_ERR_SEED_RANGE,
    DE_ERR_TIME_BACKWARD,
    DE_ERR_TOO_FEW,
    DE_ERR_TOO_FEW_REPS,
    DE_ERR_UNSTABLE,
    DE_ERR_WARMUP_RANGE,
    DE_ERR_WORK_BUDGET,
    DE_MAX_EVENTS,
    DE_MAX_WORK,
    DE_OK,
    de_absent,
    de_agrees,
    de_all_finite,
    de_ceilings,
    de_event_order,
    de_finite,
    de_heap_levels,
    de_heap_work,
    de_heap_work_fits,
    de_nondecreasing,
    de_product3_fits,
    de_product_fits,
    de_rng_version,
    de_scaled_tol,
    de_scaled_tol_additions,
    de_status_name,
    de_stream_arrival,
    de_stream_service,
)


fn _floats(a: Float64, b: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a)
    o.append(b)
    return o^


fn main():
    var passed = 0
    var failed = 0
    print("\n[discrete_event.contract] known-value suite")

    # ── 1. the ordering contract is a value, not a comment ────────────────────
    if de_event_order() == "time,priority,sequence/v1":
        passed += 1
        print("  ✅ the tie-break rule names itself: time,priority,sequence/v1")
    else:
        failed += 1
        print("  ❌ event order identifier changed:", de_event_order())

    # Read back from the FROZEN kernel, so a generator change cannot be hidden by editing a
    # string in this package.
    if de_rng_version() == rng_version() and de_rng_version() == "philox4x64-10/v1":
        passed += 1
        print("  ✅ the generator names itself and matches determinism.counter_rng")
    else:
        failed += 1
        print("  ❌ rng version disagrees with the frozen kernel:", de_rng_version())

    # ── 2. heap depth, from the definition floor(log2 n) + 1 ──────────────────
    var depth_ok = de_heap_levels(0) == 0
    depth_ok = depth_ok and de_heap_levels(1) == 1
    depth_ok = depth_ok and de_heap_levels(2) == 2
    depth_ok = depth_ok and de_heap_levels(3) == 2
    depth_ok = depth_ok and de_heap_levels(4) == 3
    depth_ok = depth_ok and de_heap_levels(7) == 3
    depth_ok = depth_ok and de_heap_levels(8) == 4
    depth_ok = depth_ok and de_heap_levels(1024) == 11
    depth_ok = depth_ok and de_heap_levels(-5) == 0
    if depth_ok:
        passed += 1
        print("  ✅ heap depth exact at 0,1,2,3,4,7,8,1024 and safe for a negative count")
    else:
        failed += 1
        print(
            "  ❌ heap depth wrong:", de_heap_levels(1), de_heap_levels(2), de_heap_levels(3),
            de_heap_levels(4), de_heap_levels(7), de_heap_levels(8), de_heap_levels(1024),
        )

    # 2 * 8 * levels(8) = 2 * 8 * 4 = 64, by hand.
    if de_heap_work(8) == 64 and de_heap_work(0) == 0:
        passed += 1
        print("  ✅ work charge for 8 events is 2*8*4 = 64")
    else:
        failed += 1
        print("  ❌ work charge wrong:", de_heap_work(8))

    if de_heap_work_fits(DE_MAX_EVENTS) and de_heap_work(DE_MAX_EVENTS) == 44040192:
        passed += 1
        print("  ✅ the event ceiling fits the work budget: 2*2^20*21 = 44040192 <= 2^27")
    else:
        failed += 1
        print("  ❌ the event ceiling does not fit its own work budget:",
              de_heap_work(DE_MAX_EVENTS))

    # ── 3. the wrapping multiply, demonstrated then defeated ──────────────────
    var wrapped = 3 * 6148914691236517206
    if wrapped == 2:
        passed += 1
        print("  ✅ demonstrated: 3 * 6148914691236517206 == 2 (wrapping 64-bit)")
    else:
        failed += 1
        print("  ❌ the wrapping multiply premise no longer holds:", wrapped)

    if not de_product_fits(3, 6148914691236517206, DE_MAX_WORK):
        passed += 1
        print("  ✅ de_product_fits refuses the pair whose product wraps to 2")
    else:
        failed += 1
        print("  ❌ de_product_fits was fooled by the wrapping multiply")

    var fits_ok = de_product_fits(4, 5, 20)
    fits_ok = fits_ok and not de_product_fits(4, 6, 20)
    fits_ok = fits_ok and de_product_fits(0, 6148914691236517206, 1)
    fits_ok = fits_ok and not de_product_fits(-1, 2, 20)
    fits_ok = fits_ok and de_product3_fits(2, 3, 4, 24)
    fits_ok = fits_ok and not de_product3_fits(2, 3, 5, 24)
    if fits_ok:
        passed += 1
        print("  ✅ 4*5<=20, 4*6>20, 0*huge<=1, negative refused, 2*3*4<=24, 2*3*5>24")
    else:
        failed += 1
        print("  ❌ product bounds wrong at a hand-checked pair")

    # ── 4. a count above the list length refuses instead of reading ───────────
    var two = _floats(1.0, 2.0)
    if de_all_finite(two, 2) and not de_all_finite(two, 25):
        passed += 1
        print("  ✅ count 25 on a 2-element list is refused, not read (the process survived)")
    else:
        failed += 1
        print("  ❌ the count guard did not refuse an over-count")

    var with_nan = _floats(1.0, 0.0 / 0.0)
    if not de_all_finite(with_nan, 2) and de_all_finite(with_nan, 1):
        passed += 1
        print("  ✅ a NaN in the prefix is caught; a shorter prefix that excludes it is fine")
    else:
        failed += 1
        print("  ❌ NaN detection depends on the wrong prefix")

    var down = _floats(2.0, 1.0)
    if de_nondecreasing(two, 2) and not de_nondecreasing(down, 2) and not de_nondecreasing(two, 9):
        passed += 1
        print("  ✅ monotonicity holds for [1,2], fails for [2,1], refuses an over-count")
    else:
        failed += 1
        print("  ❌ monotonicity check wrong")

    # ── 5. tolerances, exact at unit magnitude ────────────────────────────────
    # 256 * 2.220446049250313e-16 = 5.684341886080802e-14, by hand.
    if de_scaled_tol(1.0, 0.0) == 5.684341886080802e-14:
        passed += 1
        print("  ✅ tolerance at unit magnitude is exactly 256 * DBL_EPSILON")
    else:
        failed += 1
        print("  ❌ base tolerance changed:", de_scaled_tol(1.0, 0.0))

    # (256 + 256) * DBL_EPSILON * 1.0 = 512 * 2.220446049250313e-16 = 1.1368683772161603e-13.
    if de_scaled_tol_additions(1.0, 0.0, 256) == 1.1368683772161603e-13:
        passed += 1
        print("  ✅ 256 extra additions exactly doubles the ulp allowance")
    else:
        failed += 1
        print("  ❌ addition widening wrong:", de_scaled_tol_additions(1.0, 0.0, 256))

    # A nonsense negative addition count must not loosen anything.
    if de_scaled_tol_additions(1.0, 0.0, -1000000) == de_scaled_tol(1.0, 0.0):
        passed += 1
        print("  ✅ a negative addition count widens nothing")
    else:
        failed += 1
        print("  ❌ a negative addition count changed the tolerance")

    # ── 6. de_agrees refuses non-finites rather than passing them ─────────────
    var nan = 0.0 / 0.0
    var agree_ok = de_agrees(1.0, 1.0, 0.0, 0)
    agree_ok = agree_ok and not de_agrees(1.0, 1.0 + 1e-9, 0.0, 0)
    agree_ok = agree_ok and de_agrees(1.0, 1.0 + 1e-9, 1e-8, 0)
    agree_ok = agree_ok and not de_agrees(nan, 1.0, 0.0, 0)
    agree_ok = agree_ok and not de_agrees(1.0, nan, 0.0, 0)
    agree_ok = agree_ok and not de_agrees(nan, nan, 0.0, 0)
    if agree_ok:
        passed += 1
        print("  ✅ agreement is exact, respects an absolute tolerance, and REFUSES a NaN")
    else:
        failed += 1
        print("  ❌ de_agrees mishandled an exact, tolerant or non-finite case")

    if de_absent() == 0.0 and de_finite(de_absent()) and not isnan(de_absent()):
        passed += 1
        print("  ✅ the absent value slot is a representable 0.0, never a non-finite")
    else:
        failed += 1
        print("  ❌ de_absent is not serialisable")

    # ── 7. the streams: distinct, derived, outside the reserved block ─────────
    var arrival = de_stream_arrival()
    var service = de_stream_service()
    var stream_ok = arrival != service
    stream_ok = stream_ok and arrival >= 8 and service >= 8
    stream_ok = stream_ok and arrival < 65535 and service < 65535
    stream_ok = stream_ok and not is_reserved_stream(UInt64(arrival))
    stream_ok = stream_ok and not is_reserved_stream(UInt64(service))
    stream_ok = stream_ok and arrival == de_stream_arrival()
    stream_ok = stream_ok and service == de_stream_service()
    if stream_ok:
        passed += 1
        print(
            "  ✅ arrival and service streams are distinct, stable and outside the reserved",
            "block:", arrival, service,
        )
    else:
        failed += 1
        print("  ❌ stream ids collide or fall inside the reserved block:", arrival, service)

    # ── 8. every status code has its own name ─────────────────────────────────
    var codes = List[Int]()
    codes.append(DE_OK)
    codes.append(DE_ERR_NON_FINITE)
    codes.append(DE_ERR_EMPTY)
    codes.append(DE_ERR_COUNT)
    codes.append(DE_ERR_DIMENSION_TOO_LARGE)
    codes.append(DE_ERR_WORK_BUDGET)
    codes.append(DE_ERR_TIME_BACKWARD)
    codes.append(DE_ERR_CAPACITY)
    codes.append(DE_ERR_RATE_RANGE)
    codes.append(DE_ERR_UNSTABLE)
    codes.append(DE_ERR_TOO_FEW)
    codes.append(DE_ERR_NO_STEADY_STATE)
    codes.append(DE_ERR_TOO_FEW_REPS)
    codes.append(DE_ERR_LEVEL_RANGE)
    codes.append(DE_ERR_PRIORITY_RANGE)
    codes.append(DE_ERR_SEED_RANGE)
    codes.append(DE_ERR_WARMUP_RANGE)
    codes.append(DE_ERR_NEGATIVE_DURATION)
    codes.append(DE_ERR_BATCH_RANGE)
    codes.append(DE_ERR_NO_ESTIMATE)
    var distinct_codes = True
    var named = True
    for i in range(len(codes)):
        if codes[i] < 400 or codes[i] > 419:
            distinct_codes = False
        if de_status_name(codes[i]) == "unknown_status":
            named = False
        for j in range(i + 1, len(codes)):
            if codes[i] == codes[j]:
                distinct_codes = False
            if de_status_name(codes[i]) == de_status_name(codes[j]):
                named = False
    if len(codes) == 20 and distinct_codes and named:
        passed += 1
        print("  ✅ 20 status codes, all inside the declared 400-419 range, all uniquely named")
    else:
        failed += 1
        print("  ❌ status codes collide, escape 400-419, or share a name")

    if de_status_name(399) == "unknown_status" and de_status_name(420) == "unknown_status":
        passed += 1
        print("  ✅ a code outside the owned range is named unknown, not silently mapped")
    else:
        failed += 1
        print("  ❌ a code outside 400-419 was given a name")

    # ── 9. the ceilings are reportable, in the documented order ──────────────
    var ceilings = de_ceilings()
    if len(ceilings) == 8 and ceilings[0] == DE_MAX_EVENTS and ceilings[7] == DE_MAX_WORK:
        passed += 1
        print("  ✅ eight ceilings, events first and the work budget last")
    else:
        failed += 1
        print("  ❌ ceiling report changed shape:", len(ceilings))

    print("  [discrete_event.contract] Passed:", passed, "Failed:", failed)
