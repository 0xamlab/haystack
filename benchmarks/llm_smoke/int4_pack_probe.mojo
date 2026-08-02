"""int4_pack_probe.mojo — Stage (a) of the int4-weight-quantization task: an isolated, host-only
quantization-error measurement (int4 vs int8 vs the Float64 source, no GPU required) FOLLOWED by a
GPU correctness+vector-width probe for the packed-nibble GEMV, in the same convention
`int8_pack_probe.mojo` established: hand-written, throwaway, NOT registered in
`generate_mojo_tests.py` (a design probe, not a golden-vector suite).

    DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I../mojo/engine int4_pack_probe.mojo

Part 1 (host-only, no GPU, always runs): does int4's per-element quantization error measure at
"roughly 2x int8's", as a naive "half the levels" intuition would guess, or is that intuition wrong?
------------------------------------------------------------------------------------------------------
Per-output-row symmetric quantization maps `[-maxabs, maxabs]` onto `LEVELS` signed integer steps
per side: int8 uses 127 (`scale = maxabs/127`), int4 uses 7 (`scale = maxabs/7`) — see
`residentk.session._quantize_row_i8`'s docstring for the int8 scheme this int4 scheme mirrors
exactly, one bit width down. The quantization step (one LSB) is `scale` itself, and for a
source whose values are not concentrated at the rare extreme, per-element rounding error is
governed by that step, not by the *bit width* directly: halving the bit width (8 -> 4) does NOT
halve the level count (127 -> 7 is a ~18x drop, not 2x), so a "half the bits -> 2x the error" guess
is checked here against a real measurement and is expected to be wrong by roughly an order of
magnitude — reported honestly either way, not adjusted to match the guess.

Part 2 (GPU, needs -D ALGENTA_GPU + a device): does a packed-nibble GEMV kernel, unpacked in-register
with mask+shift (no manual word-level bit tricks — `int8_pack_probe.mojo`'s own measurement already
found manual word-unpack variants LOSE to a native vector load, so this probe does not re-litigate
that question), agree with an independent scalar Int4 reference? And which packed-BYTE vector width
— `uchar2` (4 elements/lane/step) or `uchar4` (8 elements/lane/step) — is actually faster on this
hardware, since a packed int4 byte holds TWO elements and so does not inherit int8's `char4` choice
by the same byte-width arithmetic that carried over cleanly from Float32's `float4` to int8's
`char4` (`_VEC_I8`'s own docstring: matching Float32's BYTE width, not element count, was the correct
generalization for int8; for int4 the byte-to-element ratio has itself changed, so this is a new
question, not a repeat of an old answer).
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu.host import DeviceContext, DeviceBuffer
from std.gpu import barrier, thread_idx, block_idx
from std.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.sys import has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.contract import RESIDENT_MAX_D_MODEL

comptime PROBE_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()

comptime _TG: Int = 256
comptime _LANES: Int = 32
comptime _SUBS: Int = _TG // _LANES
comptime _STAGE: Int = RESIDENT_MAX_D_MODEL

comptime _VEC_B2: Int = 2
"""Packed bytes/lane/step for the `uchar2` variant -- 4 int4 elements/lane/step."""
comptime _VEC_STRIDE_B2: Int = _LANES * _VEC_B2 * 2
"""ELEMENT stride/step for the `uchar2` variant: 32 lanes x 2 bytes x 2 elements/byte = 128."""

comptime _VEC_B4: Int = 4
"""Packed bytes/lane/step for the `uchar4` variant -- 8 int4 elements/lane/step."""
comptime _VEC_STRIDE_B4: Int = _LANES * _VEC_B4 * 2
"""ELEMENT stride/step for the `uchar4` variant: 32 lanes x 4 bytes x 2 elements/byte = 256."""

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I4P = UnsafePointer[UInt8, origin=MutAnyOrigin]

comptime _I8_MAX: Float64 = 127.0
comptime _I4_MAX: Float64 = 7.0


# ── Part 1: host-only quantization-error measurement ──────────────────────────────────────────


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


fn _round_half_away(q: Float64) -> Int:
    return Int(q + 0.5) if q >= 0.0 else Int(q - 0.5)


fn _quantize_row_generic(
    v: List[Float64], row: Int, k: Int, levels: Float64
) -> Tuple[List[Int64], Float64]:
    """Per-row symmetric quantize at an arbitrary level count -- the SAME scheme
    `residentk.session._quantize_row_i8`/`_quantize_row_i4` use, parameterized on `levels` (127 for
    int8, 7 for int4) so this one function measures both without duplicating the rounding rule."""
    var maxabs = 0.0
    for i in range(k):
        var av = v[row * k + i]
        if av < 0.0:
            av = -av
        if av > maxabs:
            maxabs = av
    var scale = (maxabs / levels) if maxabs > 0.0 else 1.0
    var inv = 1.0 / scale
    var out = List[Int64](capacity=k)
    var lv = Int64(levels)
    for i in range(k):
        var q = v[row * k + i] * inv
        var r = Int64(_round_half_away(q))
        if r > lv:
            r = lv
        if r < -lv:
            r = -lv
        out.append(r)
    return (out^, scale)


fn _measure_quant_error(n_rows: Int, k: Int) -> None:
    """Quantize a moderate pseudo-random matrix (some rows with tiny/zero max, to exercise the
    forced-scale=1.0 edge case both schemes share) to int8 and int4, dequantize each back to
    Float64, and report mean/max absolute error against the Float64 source for both, plus their
    ratio -- the number this probe exists to report honestly rather than assume."""
    var w = List[Float64](capacity=n_rows * k)
    for i in range(n_rows * k):
        w.append(_pseudo(1, i)[0])
    # Force a few literal all-zero rows, exactly the edge case `_quantize_row_i4`'s docstring (to be
    # written) inherits from `_quantize_row_i8`'s "never a zero divisor" discipline.
    var zero_row = n_rows // 3
    for i in range(k):
        w[zero_row * k + i] = 0.0

    var sum_abs_err_8 = 0.0
    var sum_abs_err_4 = 0.0
    var max_abs_err_8 = 0.0
    var max_abs_err_4 = 0.0
    var n_total = 0

    for row in range(n_rows):
        var q8_scale = _quantize_row_generic(w, row, k, _I8_MAX)
        var q4_scale = _quantize_row_generic(w, row, k, _I4_MAX)
        var q8 = q8_scale[0].copy()
        var s8 = q8_scale[1]
        var q4 = q4_scale[0].copy()
        var s4 = q4_scale[1]
        for i in range(k):
            var orig = w[row * k + i]
            var deq8 = Float64(q8[i]) * s8
            var deq4 = Float64(q4[i]) * s4
            var e8 = deq8 - orig
            if e8 < 0.0:
                e8 = -e8
            var e4 = deq4 - orig
            if e4 < 0.0:
                e4 = -e4
            sum_abs_err_8 += e8
            sum_abs_err_4 += e4
            if e8 > max_abs_err_8:
                max_abs_err_8 = e8
            if e4 > max_abs_err_4:
                max_abs_err_4 = e4
            n_total += 1

    var mean8 = sum_abs_err_8 / Float64(n_total)
    var mean4 = sum_abs_err_4 / Float64(n_total)
    print("  rows=", n_rows, " k=", k, " total elements=", n_total,
          " (row", zero_row, "forced all-zero -> scale=1.0 for both schemes)")
    print("  int8: mean |error| =", mean8, "   max |error| =", max_abs_err_8)
    print("  int4: mean |error| =", mean4, "   max |error| =", max_abs_err_4)
    print("  int4/int8 ratio: mean =", mean4 / mean8, "   max =", max_abs_err_4 / max_abs_err_8)
    print("  level-count ratio (127/7) for comparison:", _I8_MAX / _I4_MAX)
    print("  naive \"half the bits -> 2x the error\" guess would predict ratio ~= 2.0")


# ── Part 2: GPU correctness + vector-width probe ───────────────────────────────────────────────


@fieldwise_init
struct _QRow4(Copyable, Movable):
    var packed: List[UInt8]
    var scale: Float64


fn _quantize_row_i4_pack(v: List[Float64], row: Int, k: Int) -> _QRow4:
    """Per-row symmetric int4 quantize AND pack two nibbles per byte, host reference. `scale =
    max(|row|) / 7`, values clamped to `[-7, 7]`, byte = `(hi << 4) | (lo & 0xF)` -- low nibble is
    the EVEN k-index, high nibble the ODD one, matching the unpack convention the GPU kernels below
    use (mask+shift for the low nibble via a left-shift-then-arithmetic-right-shift, shift alone for
    the high nibble via a mask-then-arithmetic-right-shift)."""
    var maxabs = 0.0
    for i in range(k):
        var av = v[row * k + i]
        if av < 0.0:
            av = -av
        if av > maxabs:
            maxabs = av
    var scale = (maxabs / _I4_MAX) if maxabs > 0.0 else 1.0
    var inv = 1.0 / scale
    var n_bytes = (k + 1) // 2
    var out = List[UInt8](capacity=n_bytes)
    var i = 0
    while i < k:
        var qlo = v[row * k + i] * inv
        var rlo = _round_half_away(qlo)
        if rlo > 7:
            rlo = 7
        if rlo < -7:
            rlo = -7
        var hi_val = 0
        if i + 1 < k:
            var qhi = v[row * k + i + 1] * inv
            var rhi = _round_half_away(qhi)
            if rhi > 7:
                rhi = 7
            if rhi < -7:
                rhi = -7
            hi_val = rhi
        var lo_bits = UInt8(rlo & 0xF)
        var hi_bits = UInt8(hi_val & 0xF)
        out.append((hi_bits << 4) | lo_bits)
        i += 2
    return _QRow4(out^, scale)


fn _gemv_i4_scalar_ref(
    x: List[Float64], packed: List[UInt8], scale: List[Float64], k: Int, n: Int
) -> List[Float64]:
    """Pure-host, no-vectorization Int4 GEMV reference: unpack each byte's two nibbles with plain
    integer arithmetic (no shift trick, so this is independent of the GPU kernels' unpack method),
    dequantize, multiply-accumulate. This is what variants below are checked against."""
    var n_bytes_per_row = (k + 1) // 2
    var out = List[Float64](capacity=n)
    for j in range(n):
        var acc = 0.0
        var s = scale[j]
        var base = j * n_bytes_per_row
        for bidx in range(n_bytes_per_row):
            var b = Int(packed[base + bidx])
            var lo = b & 0xF
            if lo >= 8:
                lo -= 16
            var hi = (b >> 4) & 0xF
            if hi >= 8:
                hi -= 16
            var i0 = bidx * 2
            acc += x[i0] * (Float64(lo) * s)
            if i0 + 1 < k:
                acc += x[i0 + 1] * (Float64(hi) * s)
        out.append(acc)
    return out^


fn _gemv_i4_uchar2(y: _FP, x: _FP, w: _I4P, wscale: _FP, k: Int, n: Int):
    """Variant `uchar2`: native `w.load[width=2]` (2 packed bytes = 4 int4 elements) per lane per
    step, unpacked with mask+shift into two Float32x2 halves, dequantized, multiplied against two
    Float32x2 slices of the staged activation, accumulated."""
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var s = tid
    while s < k:
        xs[s] = x[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var n_bytes = (k + 1) // 2
        var base = j * n_bytes
        var srow = wscale[j]
        var k_vec = (k // _VEC_STRIDE_B2) * _VEC_STRIDE_B2
        var t = lane * _VEC_B2
        while t < k_vec // 2:
            var bv = w.load[width=_VEC_B2](base + t)
            var lo = ((bv << 4).cast[DType.int8]() >> 4).cast[DType.float32]() * srow
            var hi = ((bv & UInt8(0xF0)).cast[DType.int8]() >> 4).cast[DType.float32]() * srow
            var elem_off = t * 2
            var xv0 = xs.load[width=2](elem_off)
            var xv1 = xs.load[width=2](elem_off + 2)
            acc += xv0[0] * lo[0] + xv0[1] * hi[0] + xv1[0] * lo[1] + xv1[1] * hi[1]
            t += _LANES * _VEC_B2
        var tt = k_vec + lane
        while tt < k:
            var bidx = tt // 2
            var b = w[base + bidx]
            var val: Int8
            if tt % 2 == 0:
                val = (b << 4).cast[DType.int8]() >> 4
            else:
                val = (b & UInt8(0xF0)).cast[DType.int8]() >> 4
            acc += xs[tt] * (Float32(val) * srow)
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


fn _gemv_i4_uchar4(y: _FP, x: _FP, w: _I4P, wscale: _FP, k: Int, n: Int):
    """Variant `uchar4`: native `w.load[width=4]` (4 packed bytes = 8 int4 elements) per lane per
    step -- twice `uchar2`'s elements/step, same mask+shift unpack, four Float32x2 unpack pairs
    combined into the accumulator."""
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var s = tid
    while s < k:
        xs[s] = x[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var n_bytes = (k + 1) // 2
        var base = j * n_bytes
        var srow = wscale[j]
        var k_vec = (k // _VEC_STRIDE_B4) * _VEC_STRIDE_B4
        var t = lane * _VEC_B4
        while t < k_vec // 2:
            var bv = w.load[width=_VEC_B4](base + t)
            var lo = ((bv << 4).cast[DType.int8]() >> 4).cast[DType.float32]() * srow
            var hi = ((bv & UInt8(0xF0)).cast[DType.int8]() >> 4).cast[DType.float32]() * srow
            var elem_off = t * 2
            for e in range(4):
                var xv = xs.load[width=2](elem_off + e * 2)
                acc += xv[0] * lo[e] + xv[1] * hi[e]
            t += _LANES * _VEC_B4
        var tt = k_vec + lane
        while tt < k:
            var bidx = tt // 2
            var b = w[base + bidx]
            var val: Int8
            if tt % 2 == 0:
                val = (b << 4).cast[DType.int8]() >> 4
            else:
                val = (b & UInt8(0xF0)).cast[DType.int8]() >> 4
            acc += xs[tt] * (Float32(val) * srow)
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


fn _ceil_div(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


fn _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


fn _worst_delta(ybuf: DeviceBuffer[DType.float32], refv: List[Float64], n: Int) raises -> Float64:
    var worst = 0.0
    with ybuf.map_to_host() as h:
        for j in range(n):
            var d = Float64(h[j]) - refv[j]
            if d < 0.0:
                d = -d
            if d > worst:
                worst = d
    return worst


fn _build_case(k: Int, n: Int) -> Tuple[List[Float64], List[UInt8], List[Float64], List[Float64]]:
    """Returns (x, packed_weights, per_row_scales, scalar_reference_output)."""
    var x64 = _pseudo(k, 3)
    var wf = _pseudo(n * k, 11)
    var n_bytes_per_row = (k + 1) // 2
    var packed = List[UInt8](capacity=n * n_bytes_per_row)
    var scales = List[Float64](capacity=n)
    for row in range(n):
        var qr = _quantize_row_i4_pack(wf, row, k)
        for b in qr.packed:
            packed.append(b)
        scales.append(qr.scale)
    var refv = _gemv_i4_scalar_ref(x64, packed, scales, k, n)
    return (x64^, packed^, scales^, refv^)


fn _run_correctness(ctx: DeviceContext) raises -> Bool:
    """Stage 1 (GPU): small, hand-computable, deliberately-misaligned shape (`k=136`, not a
    multiple of either variant's element stride), checked against the independent pure-host scalar
    Int4 reference."""
    var k = 136
    var n = 24
    var built = _build_case(k, n)
    var x64 = built[0].copy()
    var packed = built[1].copy()
    var scales = built[2].copy()
    var refv = built[3].copy()
    var n_bytes_per_row = (k + 1) // 2

    var xbuf = ctx.enqueue_create_buffer[DType.float32](k)
    var wbuf = ctx.enqueue_create_buffer[DType.uint8](n * n_bytes_per_row)
    var sbuf = ctx.enqueue_create_buffer[DType.float32](n)
    var ybuf = ctx.enqueue_create_buffer[DType.float32](n)
    with xbuf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(x64[i])
    with wbuf.map_to_host() as h:
        for i in range(n * n_bytes_per_row):
            h[i] = packed[i]
    with sbuf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(scales[i])
    ctx.synchronize()

    var f_b2 = ctx.compile_function_unchecked[_gemv_i4_uchar2]()
    var f_b4 = ctx.compile_function_unchecked[_gemv_i4_uchar4]()
    var grid = _ceil_div(n, _SUBS)
    var all_ok = True

    ctx.enqueue_function_unchecked(
        f_b2, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
        grid_dim=grid, block_dim=_TG,
    )
    ctx.synchronize()
    var worst_b2 = _worst_delta(ybuf, refv, n)
    var ok_b2 = worst_b2 < 1e-3
    all_ok = all_ok and ok_b2
    print("  correctness[ uchar2 ]: worst |delta| vs scalar host reference =", worst_b2, "  ",
          "OK" if ok_b2 else "MISMATCH")

    ctx.enqueue_function_unchecked(
        f_b4, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
        grid_dim=grid, block_dim=_TG,
    )
    ctx.synchronize()
    var worst_b4 = _worst_delta(ybuf, refv, n)
    var ok_b4 = worst_b4 < 1e-3
    all_ok = all_ok and ok_b4
    print("  correctness[ uchar4 ]: worst |delta| vs scalar host reference =", worst_b4, "  ",
          "OK" if ok_b4 else "MISMATCH")

    return all_ok


fn _time_shape(ctx: DeviceContext, k: Int, n: Int, reps: Int) raises:
    var built = _build_case(k, n)
    var x64 = built[0].copy()
    var packed = built[1].copy()
    var scales = built[2].copy()
    var n_bytes_per_row = (k + 1) // 2

    var xbuf = ctx.enqueue_create_buffer[DType.float32](k)
    var wbuf = ctx.enqueue_create_buffer[DType.uint8](n * n_bytes_per_row)
    var sbuf = ctx.enqueue_create_buffer[DType.float32](n)
    var ybuf = ctx.enqueue_create_buffer[DType.float32](n)
    with xbuf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(x64[i])
    with wbuf.map_to_host() as h:
        for i in range(n * n_bytes_per_row):
            h[i] = packed[i]
    with sbuf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(scales[i])
    ctx.synchronize()

    var f_b2 = ctx.compile_function_unchecked[_gemv_i4_uchar2]()
    var f_b4 = ctx.compile_function_unchecked[_gemv_i4_uchar4]()
    var grid = _ceil_div(n, _SUBS)

    print("   k=", k, " n=", n)

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_b2, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_b2 = List[Float64]()
    for _ in range(reps):
        var t0 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_b2, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
        ctx.synchronize()
        samples_b2.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var med_b2 = _median(samples_b2)
    print("   uchar2 (4 elem/lane/step) : median of", reps, "=", med_b2, "us")

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_b4, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_b4 = List[Float64]()
    for _ in range(reps):
        var t0b = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_b4, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
        ctx.synchronize()
        samples_b4.append(Float64(Int(perf_counter_ns() - t0b)) / 1e3)
    var med_b4 = _median(samples_b4)
    print("   uchar4 (8 elem/lane/step) : median of", reps, "=", med_b4, "us   (",
          (med_b4 - med_b2) / med_b2 * 100.0, "% vs uchar2)")


def main() raises:
    print("=== int4 quantization probe: Part 1 (host-only error measurement) ===")
    print("")
    _measure_quant_error(256, 512)
    print("")

    print("=== int4 quantization probe: Part 2 (GPU correctness + vector-width) ===")
    print("")
    if not PROBE_GPU_BUILD:
        print("Built WITHOUT -D ALGENTA_GPU: refusing to report GPU timings (kernels compiled out).")
        return
    if not has_accelerator():
        print("No usable accelerator. Refusing to report GPU timings.")
        return

    var ctx = DeviceContext()

    print("--- Stage 1 correctness: small (k=136, n=24) shape vs a pure-host scalar reference ---")
    var ok = _run_correctness(ctx)
    if not ok:
        print("CORRECTNESS FAILURE: refusing to report any timing number.")
        return
    print("")

    print("--- Decode-shaped timing: gate/up-like (k=1024, n=3072) ---")
    _time_shape(ctx, 1024, 3072, 200)
    print("")
    print("--- Decode-shaped timing: down-proj-like (k=3072, n=1024) ---")
    _time_shape(ctx, 3072, 1024, 200)
    print("")
    print("--- Decode-shaped timing: o_proj-like (k=2048, n=1024) ---")
    _time_shape(ctx, 2048, 1024, 200)
