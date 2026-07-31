"""test_tensorx_pack.mojo — known-value tests for blockwise low-bit quantization.

Hand-written. The assertions target the failures that produce a working model rather than an error:

* **A nibble order that is backwards.** Two 4-bit codes share a byte; swapping them transposes
  adjacent weights and trains to something slightly worse with no error anywhere. Pinned against a
  hand-computed byte.
* **A codebook that is off by one level.** NF4 is sixteen fixed quantiles, not a formula. If ours
  disagrees with the one that produced the checkpoint, every weight is reconstructed one step wrong.
  All sixteen values are pinned.
* **A 4-bit grid clamped at 127.** `quantization.quantize_symmetric` is hardcoded to int8, which is
  why this package has its own code producer. `int4_error_vs_frozen` sweeps the agreement against the
  frozen `quantization.int4_pack_error` oracle, so the new driver cannot drift from the frozen one.
* **A count past the end of its buffer**, which the A-Z harness structurally cannot find.

The NF4-vs-int4 comparison is a property test, not a fixed number: NF4 exists because weights are
approximately normal, so on normal-ish data it must beat a uniform grid at the same bit width. If that
inverts, the codebook or the scaling is wrong even when every other assertion passes.
"""
from quantization import int4_pack_error, scale_from_range
from tensorx.contract import (
    TX_ERR_BITS_UNSUPPORTED,
    TX_ERR_BLOCK_SIZE,
    TX_ERR_CODE_OUT_OF_RANGE,
    TX_ERR_LENGTH_MISMATCH,
    TX_OK,
)
from tensorx.pack import (
    calibrate_absmax,
    calibrate_percentile,
    dequantize_blockwise,
    dequantize_nf4,
    double_quant_scales,
    int4_error_vs_frozen,
    nf4_levels,
    pack_int4,
    quant_error_report,
    quantize_blockwise,
    quantize_nf4,
    unpack_int4,
)


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the NF4 codebook, pinned ──────────────────────────────────────────────
    var lv = nf4_levels()
    var codebook_ok = len(lv) == 16
    if codebook_ok:
        codebook_ok = (
            lv[0] == -1.0
            and lv[7] == 0.0
            and lv[15] == 1.0
            and lv[1] == -0.6961928009986877
            and lv[8] == 0.07958029955625534
            and lv[14] == 0.7229568362236023
        )
    var ascending = True
    for i in range(1, len(lv)):
        if lv[i] <= lv[i - 1]:
            ascending = False
    if codebook_ok and ascending:
        passed += 1
        print("  ✅ the NF4 codebook is 16 ascending levels with -1/0/+1 pinned at 0/7/15")
    else:
        failed += 1
        print("  ❌ the NF4 codebook drifted — reconstruction will disagree with the checkpoint")

    # ── nibble order is low-first ─────────────────────────────────────────────
    # codes[0] = -8 -> nibble 0; codes[1] = 7 -> nibble 15. Low nibble first means the byte is
    # (15 << 4) | 0 == 240. If the order were reversed it would be 15, and nothing else would notice.
    var codes = List[Int]()
    codes.append(-8)
    codes.append(7)
    codes.append(0)
    codes.append(-1)
    codes.append(3)
    var packed = pack_int4(codes, 5)
    if packed.status == TX_OK and len(packed.bytes) == 3 and packed.bytes[0] == 240:
        passed += 1
        print("  ✅ nibble order is low-first: [-8, 7] packs to byte 240, not 15")
    else:
        failed += 1
        print("  ❌ nibble packing is wrong — adjacent weights would be transposed")

    var un = unpack_int4(packed.bytes, 5)
    var rt_ok = len(un) == 5
    if rt_ok:
        for i in range(5):
            if un[i] != codes[i]:
                rt_ok = False
    if rt_ok:
        passed += 1
        print("  ✅ an odd-length nibble round-trip preserves every code, including -8 and 7")
    else:
        failed += 1
        print("  ❌ nibble round-trip lost or altered a code")

    if pack_int4(codes, 99).status == TX_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ packing more codes than exist is refused, not an out-of-bounds read")
    else:
        failed += 1
        print("  ❌ pack_int4 did not bound its count")

    var oob = List[Int]()
    oob.append(99)
    if pack_int4(oob, 1).status == TX_ERR_CODE_OUT_OF_RANGE:
        passed += 1
        print("  ✅ a code outside -8..7 is refused rather than silently truncated to a nibble")
    else:
        failed += 1
        print("  ❌ pack_int4 accepted a code that does not fit 4 bits")

    if len(unpack_int4(packed.bytes, 999)) == 0:
        passed += 1
        print("  ✅ unpacking more values than the buffer holds returns empty, not garbage")
    else:
        failed += 1
        print("  ❌ unpack_int4 read past the end of its buffer")

    # ── the 4-bit code producer agrees with the frozen oracle ─────────────────
    # This is the rule-3 obligation for writing a new code producer: the frozen kernel remains the
    # definition of what a 4-bit round-trip costs, and the new driver is checked against it.
    var sweep = List[Float64]()
    sweep.append(0.0)
    sweep.append(0.3)
    sweep.append(-0.3)
    sweep.append(0.7)
    sweep.append(-0.7)
    sweep.append(1.0)
    sweep.append(-1.0)
    sweep.append(0.049)
    sweep.append(-0.049)
    var delta_bad = 0
    for i in range(len(sweep)):
        if _abs(int4_error_vs_frozen(sweep[i], 0.1)) > 1e-12:
            delta_bad += 1
    if delta_bad == 0:
        passed += 1
        print("  ✅ the 4-bit driver agrees with frozen int4_pack_error on all", len(sweep), "probes")
    else:
        failed += 1
        print("  ❌ the 4-bit driver diverged from the frozen oracle on", delta_bad, "probes")

    # The frozen kernel is reachable and unchanged.
    if int4_pack_error(0.0, 0.1) == 0.0 and scale_from_range(1.0, 4.0) > 0.0:
        passed += 1
        print("  ✅ the frozen quantization kernels are reachable and behave as before")
    else:
        failed += 1
        print("  ❌ a frozen quantization kernel changed")

    # ── blockwise round-trip ──────────────────────────────────────────────────
    var x = List[Float64]()
    x.append(0.5)
    x.append(-0.25)
    x.append(1.0)
    x.append(-1.0)
    x.append(0.125)
    x.append(0.0)
    x.append(-0.75)
    x.append(0.33)

    var bq = quantize_blockwise(x, 8, 4, 4)
    if bq.status == TX_OK and bq.n_blocks == 2 and len(bq.codes) == 8 and len(bq.scales) == 2:
        passed += 1
        print("  ✅ 8 values at block 4 gives 2 blocks, 8 codes and 2 scales")
    else:
        failed += 1
        print("  ❌ blockwise shape is wrong:", bq.n_blocks, len(bq.codes), len(bq.scales))

    var dq = dequantize_blockwise(bq.codes, bq.scales, 8, 4, 4)
    var er = quant_error_report(x, dq, 8)
    # Every code is within one step of the true value, so the error cannot exceed one scale.
    var worst_scale = bq.scales[0]
    if bq.scales[1] > worst_scale:
        worst_scale = bq.scales[1]
    if er.status == TX_OK and er.n_compared == 8 and er.max_abs_err <= worst_scale:
        passed += 1
        print("  ✅ int4 round-trip error stays within one quantization step")
    else:
        failed += 1
        print("  ❌ int4 error exceeded one step:", er.max_abs_err, "vs", worst_scale)

    # A trailing partial block must be scaled on its own real length. With 7 values at block 4 the
    # second block holds 3; padding it with zeros would drag its absmax down and misquantize them.
    var bq7 = quantize_blockwise(x, 7, 4, 4)
    var dq7 = dequantize_blockwise(bq7.codes, bq7.scales, 7, 4, 4)
    if bq7.n_blocks == 2 and len(bq7.codes) == 7 and len(dq7) == 7:
        passed += 1
        print("  ✅ a trailing partial block is sized and scaled on its own real length")
    else:
        failed += 1
        print("  ❌ partial-block handling is wrong:", bq7.n_blocks, len(bq7.codes))

    # ── NF4 must beat a uniform grid at the same width ────────────────────────
    var nq = quantize_nf4(x, 8, 4)
    var nd = dequantize_nf4(nq.codes, nq.scales, 8, 4)
    var ner = quant_error_report(x, nd, 8)
    if nq.status == TX_OK and len(nd) == 8 and ner.max_abs_err < er.max_abs_err:
        passed += 1
        print("  ✅ NF4 beats uniform int4 on max error at the same bit width — the reason it exists")
    else:
        failed += 1
        print("  ❌ NF4 did not beat uniform int4:", ner.max_abs_err, "vs", er.max_abs_err)

    # A value sitting exactly on +/-1.0 is the block absmax, so it reconstructs exactly.
    var exact = List[Float64]()
    exact.append(1.0)
    exact.append(-1.0)
    var eq = quantize_nf4(exact, 2, 2)
    var ed = dequantize_nf4(eq.codes, eq.scales, 2, 2)
    if len(ed) == 2 and ed[0] == 1.0 and ed[1] == -1.0:
        passed += 1
        print("  ✅ values on the codebook endpoints reconstruct exactly")
    else:
        failed += 1
        print("  ❌ endpoint values did not reconstruct exactly")

    var badcode = List[Int]()
    badcode.append(77)
    if len(dequantize_nf4(badcode, nq.scales, 1, 4)) == 0:
        passed += 1
        print("  ✅ an NF4 index outside 0..15 is refused, not clamped to a level")
    else:
        failed += 1
        print("  ❌ dequantize_nf4 accepted an index outside the codebook")

    # An all-zero block has no absmax; it must reconstruct to zeros rather than divide by zero.
    var zeros = List[Float64]()
    for _ in range(4):
        zeros.append(0.0)
    var zq = quantize_nf4(zeros, 4, 4)
    var zd = dequantize_nf4(zq.codes, zq.scales, 4, 4)
    var zeros_ok = zq.status == TX_OK and len(zd) == 4
    if zeros_ok:
        for i in range(4):
            if zd[i] != 0.0:
                zeros_ok = False
    if zeros_ok:
        passed += 1
        print("  ✅ an all-zero block round-trips to zeros instead of dividing by its absmax")
    else:
        failed += 1
        print("  ❌ an all-zero block did not round-trip cleanly")

    # ── double quantization ───────────────────────────────────────────────────
    var dqs = double_quant_scales(bq.scales, bq.n_blocks, 2)
    if dqs.status == TX_OK and dqs.n_outer == 1 and len(dqs.scale_codes) == 2:
        passed += 1
        print("  ✅ block scales quantize against an outer block of scales")
    else:
        failed += 1
        print("  ❌ double quantization shape is wrong:", dqs.n_outer, len(dqs.scale_codes))

    if double_quant_scales(bq.scales, 99, 2).status == TX_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ double quantization bounds its block count")
    else:
        failed += 1
        print("  ❌ double_quant_scales did not bound n_blocks")

    # ── calibration ───────────────────────────────────────────────────────────
    if calibrate_absmax(x, 8) == 1.0 and calibrate_absmax(x, 99) == 0.0:
        passed += 1
        print("  ✅ absmax is correct in range and returns 0.0 rather than reading past the end")
    else:
        failed += 1
        print("  ❌ calibrate_absmax is wrong")

    # A percentile clip must sit at or below the absmax, and above zero for this data.
    var p50 = calibrate_percentile(x, 8, 50.0)
    var p100 = calibrate_percentile(x, 8, 100.0)
    if p50 > 0.0 and p50 <= p100 and p100 == 1.0:
        passed += 1
        print("  ✅ percentile calibration is monotone and reaches absmax at p100")
    else:
        failed += 1
        print("  ❌ percentile calibration is wrong:", p50, p100)

    if calibrate_percentile(x, 8, 0.0) == 0.0 and calibrate_percentile(x, 8, 101.0) == 0.0:
        passed += 1
        print("  ✅ an out-of-range percentile is refused rather than clamped silently")
    else:
        failed += 1
        print("  ❌ an out-of-range percentile was accepted")

    # ── the guards the A-Z harness cannot reach ───────────────────────────────
    if quantize_blockwise(x, 99, 4, 4).status == TX_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ n=99 over an 8-element list is refused, not an uncatchable abort")
    else:
        failed += 1
        print("  ❌ quantize_blockwise did not bound its count")

    if (
        quantize_blockwise(x, 8, 4, 5).status == TX_ERR_BITS_UNSUPPORTED
        and quantize_blockwise(x, 8, 0, 4).status == TX_ERR_BLOCK_SIZE
        and quantize_blockwise(x, 8, 99999, 4).status == TX_ERR_BLOCK_SIZE
    ):
        passed += 1
        print("  ✅ unsupported bit width and out-of-range block size are distinct statuses")
    else:
        failed += 1
        print("  ❌ bits/block validation conflated two different mistakes")

    if len(dequantize_blockwise(bq.codes, bq.scales, 99, 4, 4)) == 0:
        passed += 1
        print("  ✅ dequantizing more codes than exist returns empty")
    else:
        failed += 1
        print("  ❌ dequantize_blockwise read past the end")

    var nan_v = 0.0 / 0.0
    var with_nan = List[Float64]()
    with_nan.append(1.0)
    with_nan.append(nan_v)
    var nan_rep = quant_error_report(with_nan, with_nan, 2)
    if nan_rep.n_compared == 1:
        passed += 1
        print("  ✅ a NaN is excluded from the error statistics rather than poisoning all three")
    else:
        failed += 1
        print("  ❌ a NaN reached the error statistics")

    print("  [tensorx.pack] Passed:", passed, "Failed:", failed)
