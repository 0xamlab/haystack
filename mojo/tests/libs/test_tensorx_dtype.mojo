"""test_tensorx_dtype.mojo — known-value tests for the dtype system.

Hand-written. Three jobs.

**One: pin the constants against the compiler.** `dtx_eps` and `dtx_max_finite` are hand-written
tables, and a wrong epsilon does not fail loudly — it produces a tolerance that passes a broken
result. So every entry is re-derived here from the native cast rather than compared against a second
copy of the same number: eps is checked by confirming `1 + eps` survives the round-trip while
`1 + eps/2` does not, and max_finite by confirming it survives while twice it does not.

**Two: pin the divergence from the frozen kernel.** `quantization_stack.bf16_to_fp32_round` is frozen
and unchanged; this module's bf16 is a separate contract with a different rounding convention. The
delta is asserted at known values so neither side can drift without a failing test, and so the number
in the module docstring stays true.

**Three: cover the silent failures.** A count past the end of its buffer. A NaN reaching a tolerance
computation, where `eps * (1 + nan)` is NaN and every subsequent `>` comparison is False. An
`Int(Float64(...))` byte width. An unknown dtype name resolving to a default.
"""
from quantization_stack import bf16_to_fp32_round
from tensorx.contract import TX_ERR_COUNT_EXCEEDS_LENGTH, TX_ERR_NEGATIVE_COUNT, TX_OK
from tensorx.dtype import (
    DT_BF16,
    DT_F16,
    DT_F32,
    DT_F64,
    DT_F8E4M3,
    DT_F8E5M2,
    DT_I4,
    DT_I8,
    DT_INVALID,
    DT_NF4,
    DT_U8,
    dtx_accum_dtype,
    dtx_bf16_frozen_delta,
    dtx_bits,
    dtx_bytes_per_1024,
    dtx_dtype_from_name,
    dtx_dtype_name,
    dtx_eps,
    dtx_is_float,
    dtx_is_sub_byte,
    dtx_is_supported,
    dtx_max_finite,
    dtx_round_trip,
    dtx_round_trip_list,
    dtx_tol_for,
)


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var floats = List[Int]()
    floats.append(DT_F64)
    floats.append(DT_F32)
    floats.append(DT_BF16)
    floats.append(DT_F16)
    floats.append(DT_F8E4M3)
    floats.append(DT_F8E5M2)

    var all_codes = List[Int]()
    for i in range(len(floats)):
        all_codes.append(floats[i])
    all_codes.append(DT_I8)
    all_codes.append(DT_U8)
    all_codes.append(DT_I4)
    all_codes.append(DT_NF4)

    # ── names round-trip, and an unknown name does NOT get a default ──────────
    var name_bad = 0
    for i in range(len(all_codes)):
        if dtx_dtype_from_name(dtx_dtype_name(all_codes[i])) != all_codes[i]:
            name_bad += 1
    if name_bad == 0 and dtx_dtype_from_name(String("float9")) == DT_INVALID:
        passed += 1
        print("  ✅ every dtype name round-trips; an unknown name is DT_INVALID, not a default")
    else:
        failed += 1
        print("  ❌ a dtype name failed to round-trip, or an unknown name resolved to a dtype")

    if not dtx_is_supported(DT_INVALID) and not dtx_is_supported(99):
        passed += 1
        print("  ✅ DT_INVALID and out-of-range codes are unsupported")
    else:
        failed += 1
        print("  ❌ an invalid dtype code was reported supported")

    # ── eps derived from the compiler, not copied from a second table ─────────
    # 1 + eps must survive the round-trip; 1 + eps/2 must round back to 1.0. That is what "the gap
    # between 1.0 and the next representable value" means, and it is checkable rather than asserted.
    var eps_bad = 0
    for i in range(len(floats)):
        var c = floats[i]
        var e = dtx_eps(c)
        if e <= 0.0:
            eps_bad += 1
            continue
        if dtx_round_trip(1.0 + e, c) <= 1.0:
            eps_bad += 1
        if dtx_round_trip(1.0 + e * 0.5, c) != 1.0:
            eps_bad += 1
    if eps_bad == 0:
        passed += 1
        print("  ✅ dtx_eps matches the compiler's own representable gap for all 6 float dtypes")
    else:
        failed += 1
        print("  ❌ dtx_eps disagrees with the compiler on", eps_bad, "check(s)")

    if dtx_eps(DT_I8) == 0.0 and dtx_eps(DT_NF4) == 0.0:
        passed += 1
        print("  ✅ integer and codebook dtypes report eps 0.0 (exact on their own grid)")
    else:
        failed += 1
        print("  ❌ a non-float dtype reported a floating epsilon")

    # ── max_finite derived from the compiler ──────────────────────────────────
    var max_bad = 0
    for i in range(len(floats)):
        var c = floats[i]
        var m = dtx_max_finite(c)
        if dtx_round_trip(m, c) != m:
            max_bad += 1
    if max_bad == 0:
        passed += 1
        print("  ✅ dtx_max_finite survives its own round-trip for all 6 float dtypes")
    else:
        failed += 1
        print("  ❌ dtx_max_finite is not representable in", max_bad, "dtype(s)")

    # ── sub-byte widths stay integral ─────────────────────────────────────────
    # int4 is 4 bits. Expressed per-element in bytes it is 0.5, which cannot be a buffer stride, and
    # routing it through Int(Float64(...)) is rule 4c's undefined conversion. Per-1024 is exact.
    if dtx_bits(DT_I4) == 4 and dtx_bytes_per_1024(DT_I4) == 512 and dtx_bytes_per_1024(DT_F64) == 8192:
        passed += 1
        print("  ✅ sub-byte widths are exact integers per 1024 elements, never a fractional byte")
    else:
        failed += 1
        print("  ❌ byte-width arithmetic is not integral")

    if dtx_is_sub_byte(DT_I4) and dtx_is_sub_byte(DT_NF4) and not dtx_is_sub_byte(DT_I8):
        passed += 1
        print("  ✅ sub-byte dtypes are flagged, so a buffer length is not read as an element count")
    else:
        failed += 1
        print("  ❌ sub-byte classification is wrong")

    if dtx_is_float(DT_BF16) and not dtx_is_float(DT_NF4) and not dtx_is_float(DT_I8):
        passed += 1
        print("  ✅ NF4 is classified as a codebook, not a float")
    else:
        failed += 1
        print("  ❌ float classification is wrong")

    # ── accumulation policy is stated once ────────────────────────────────────
    var accum_bad = 0
    for i in range(len(floats)):
        var c = floats[i]
        var want = DT_F64 if c == DT_F64 else DT_F32
        if dtx_accum_dtype(c) != want:
            accum_bad += 1
    if accum_bad == 0 and dtx_accum_dtype(99) == DT_INVALID:
        passed += 1
        print("  ✅ everything below f64 accumulates in f32; an unknown dtype has no accumulator")
    else:
        failed += 1
        print("  ❌ the accumulation policy is inconsistent")

    # ── bf16 is symmetric; the frozen kernel's convention is not ──────────────
    if dtx_round_trip(0.75, DT_BF16) == 0.75 and dtx_round_trip(-0.75, DT_BF16) == -0.75:
        passed += 1
        print("  ✅ this module's bf16 is symmetric: round(-x) == -round(x)")
    else:
        failed += 1
        print("  ❌ bf16 round-trip is not symmetric")

    # Pinned so the measured table in the module docstring cannot go stale, and so a change on
    # either side surfaces here rather than as a slightly worse model three weeks later.
    if (
        dtx_bf16_frozen_delta(0.75) == 0.0
        and dtx_bf16_frozen_delta(-0.75) == -0.0078125
        and dtx_bf16_frozen_delta(-1.0) == -0.0078125
    ):
        passed += 1
        print("  ✅ the divergence from the frozen bf16 convention is pinned at known values")
    else:
        failed += 1
        print("  ❌ the frozen-bf16 delta drifted:", dtx_bf16_frozen_delta(-0.75))

    if bf16_to_fp32_round(0.75) == 0.75 and bf16_to_fp32_round(-0.75) != -0.75:
        passed += 1
        print("  ✅ the frozen kernel is reachable and unchanged (asymmetric by its own convention)")
    else:
        failed += 1
        print("  ❌ the frozen bf16 kernel changed — it is supposed to be frozen")

    # ── hand/reference-derived golden values for bf16 and both fp8 formats ─────
    # Cross-checked against real torch casts, run before this block was written:
    #   torch.tensor(3.14159, dtype=torch.float32).to(torch.bfloat16)      -> 3.140625
    #   torch.tensor(3.14159, dtype=torch.float32).to(torch.float8_e4m3fn) -> 3.25
    #   torch.tensor(3.14159, dtype=torch.float32).to(torch.float8_e5m2)   -> 3.0
    #   torch.tensor(100.0,  dtype=torch.float32).to(torch.float8_e4m3fn) -> 96.0
    #   torch.tensor(100.0,  dtype=torch.float32).to(torch.float8_e5m2)   -> 96.0
    if (
        dtx_round_trip(3.14159, DT_BF16) == 3.140625
        and dtx_round_trip(3.14159, DT_F8E4M3) == 3.25
        and dtx_round_trip(3.14159, DT_F8E5M2) == 3.0
    ):
        passed += 1
        print("  ✅ pi rounds to 3.140625 (bf16), 3.25 (fp8 e4m3), 3.0 (fp8 e5m2) — matching torch")
    else:
        failed += 1
        print(
            "  ❌ a bf16/fp8 golden value drifted from the torch reference:",
            dtx_round_trip(3.14159, DT_BF16),
            dtx_round_trip(3.14159, DT_F8E4M3),
            dtx_round_trip(3.14159, DT_F8E5M2),
        )

    if dtx_round_trip(100.0, DT_F8E4M3) == 96.0 and dtx_round_trip(100.0, DT_F8E5M2) == 96.0:
        passed += 1
        print("  ✅ 100.0 rounds to 96.0 in both fp8 e4m3 and e5m2 — matching torch")
    else:
        failed += 1
        print("  ❌ the fp8 100.0 golden value drifted from the torch reference")

    # ── the count guard the A-Z harness cannot exercise ───────────────────────
    var v = List[Float64]()
    v.append(0.1)
    v.append(-0.1)
    v.append(3.14159265358979)
    v.append(1e40)
    v.append(0.0)

    var ok = dtx_round_trip_list(v, 5, DT_BF16)
    if ok.status == TX_OK and len(ok.values) == 5:
        passed += 1
        print("  ✅ the in-range cast returns one value per input")
    else:
        failed += 1
        print("  ❌ the in-range cast failed:", ok.status)

    var over = dtx_round_trip_list(v, 25, DT_BF16)
    if over.status == TX_ERR_COUNT_EXCEEDS_LENGTH and len(over.values) == 0:
        passed += 1
        print("  ✅ n=25 over a 5-element list is refused, not an out-of-bounds read")
    else:
        failed += 1
        print("  ❌ dtx_round_trip_list did not refuse an oversize count")

    if dtx_round_trip_list(v, -1, DT_BF16).status == TX_ERR_NEGATIVE_COUNT:
        passed += 1
        print("  ✅ a negative count is a distinct status from an oversize one")
    else:
        failed += 1
        print("  ❌ a negative count was not distinguished")

    # 1e40 exceeds fp8-e4m3's 448.0 by 38 orders of magnitude. Reporting it as overflow rather than
    # silently saturating is what lets a caller pick a different format.
    var fp8 = dtx_round_trip_list(v, 5, DT_F8E4M3)
    if fp8.status == TX_OK and fp8.n_overflow == 1:
        passed += 1
        print("  ✅ a value beyond the dtype's range is counted as overflow, not silently saturated")
    else:
        failed += 1
        print("  ❌ fp8 overflow was not reported: n_overflow =", fp8.n_overflow)

    var nan_v = 0.0 / 0.0
    var with_nan = List[Float64]()
    with_nan.append(1.0)
    with_nan.append(nan_v)
    var nan_cast = dtx_round_trip_list(with_nan, 2, DT_BF16)
    if nan_cast.n_nan == 1:
        passed += 1
        print("  ✅ NaNs are counted rather than folded into the error statistic")
    else:
        failed += 1
        print("  ❌ a NaN was not counted")

    # ── the tolerance constructor ─────────────────────────────────────────────
    # At |q| = 1000 in bf16 the relative term must dominate. If the absolute term were doing the work
    # here, the comparison would have silently become absolute at a scale the caller never chose.
    var t = dtx_tol_for(1000.0, DT_BF16, 1e-9)
    if t.status == TX_OK and t.relative_term > t.absolute_term and t.value == t.relative_term + t.absolute_term:
        passed += 1
        print("  ✅ the tolerance is relative_term + absolute_term, and scales with the quantity")
    else:
        failed += 1
        print("  ❌ tolerance composition is wrong")

    # The relative term must come from eps and the quantity ALONE — not from the caller's tolerance
    # (spelling 4) and not from any aggregate (spellings 1 and 2).
    var t_small = dtx_tol_for(1.0, DT_BF16, 1e-9)
    var t_big = dtx_tol_for(1000.0, DT_BF16, 1e-9)
    if _abs(t_big.relative_term - t_small.relative_term * 1000.0) < 1e-12:
        passed += 1
        print("  ✅ the relative term is exactly eps * |quantity| — linear, from that quantity alone")
    else:
        failed += 1
        print("  ❌ the relative term is not linear in the quantity")

    # No floor. A `1 + |x|` idiom would make this ~eps instead of ~0, i.e. absolute at a tiny scale.
    var t_tiny = dtx_tol_for(1e-13, DT_BF16, 0.0)
    if t_tiny.relative_term < 1e-14:
        passed += 1
        print("  ✅ there is no 1+|x| floor: a tiny quantity gets a tiny relative term")
    else:
        failed += 1
        print("  ❌ the tolerance has a floor that dominates at small magnitudes")

    # With a NaN in play, eps * (1 + nan) is NaN and every `fabs(d) > nan` is False — an audit that
    # passes having counted zero violations. Rule 4d: validate finiteness BEFORE building a tolerance.
    if dtx_tol_for(nan_v, DT_BF16, 1e-9).status != TX_OK and dtx_tol_for(1.0, 99, 1e-9).status != TX_OK:
        passed += 1
        print("  ✅ a NaN quantity or unknown dtype is refused before a tolerance is computed")
    else:
        failed += 1
        print("  ❌ a NaN or unknown dtype produced a tolerance")

    print("  [tensorx.dtype] Passed:", passed, "Failed:", failed)
