"""Int8_pack_probe.mojo — does an explicit packed-32-bit-word int8 read beat the char4 vector load
`residentk.kernels`'s int8 GEMV kernels already use, or does Metal's compiler already lower `char4`
to the same word-sized instruction?

Hand-written, throwaway measurement (not registered in `generate_mojo_tests.py`; this is a probe for
a design decision, exactly like `decode_metal_probe.mojo` before it, not a golden-vector suite).
REQUIRES the GPU build flag and a shader compiler:

    DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I../mojo/engine int8_pack_probe.mojo

Question being asked, precisely
--------------------------------
`residentk.kernels._VEC_I8`'s own docstring already establishes that `char4` (4 bytes, 4 elements)
is MSL's widest native vector type for `int8` -- there is no `char8`/`char16`. Four `int8` values
also happen to pack exactly into one 32-bit word, which is a DIFFERENT question from vector width:
maybe the compiler already emits a single 32-bit load for `w.load[width=4]` on an `Int8` pointer
(bytes are bytes; a 4-byte-aligned 4-element read is a natural 32-bit load either way it's spelled),
in which case an explicit `UInt32` read + manual shift/mask unpack is pure overhead (extra ALU ops
for the same one load). Or maybe it is not, and the explicit form is faster. This probe measures
both, plus a doubled-width variant (two consecutive 32-bit words, 8 int8 values, unpacked together)
against the SAME char4 loop run for twice as many elements per outer step, to ask whether reading
two words back-to-back (more independent memory ops in flight before the first is consumed) beats
two round trips through the narrower loop. All three kernels are stripped down to ONLY the GEMV
reduction (no rmsnorm stage, no residual add) so the timing isolates the weight-load instruction
choice, which is the one thing this probe varies; every other structural aspect (threadgroup shape,
one SIMD group per output column, the same tree reduction) is copied verbatim from
`residentk.kernels._norm_gemv_kernel_i8` so the measurement reflects that kernel's real access
pattern, not a synthetic one.

Correctness gate, per this phase's Stage 1: all three variants are checked against a scalar Int8
reference (no vectorization at all) on a small, hand-computable shape BEFORE any timing number is
trusted. A kernel that is fast and wrong is not reported.
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
"""Same `-D ALGENTA_GPU` define every other GPU-gated module in this tree keys off (see
`residentk.session`'s module docstring for why a runtime `if` cannot do this job)."""

comptime _TG: Int = 256
comptime _LANES: Int = 32
comptime _SUBS: Int = _TG // _LANES
comptime _VEC4: Int = 4
comptime _VEC_STRIDE4: Int = _LANES * _VEC4
comptime _VEC8: Int = 8
comptime _VEC_STRIDE8: Int = _LANES * _VEC8
comptime _STAGE: Int = RESIDENT_MAX_D_MODEL

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]


def _sbyte(word: UInt32, shift: Int) -> Float32:
    """Unpack ONE signed int8 lane from a packed 32-bit word at byte offset `shift/8`, little-endian
    (byte 0 = the lowest 8 bits) -- the same byte order a `char4` vector load reads from the
    identical bytes, verified by this file's own correctness check rather than assumed."""
    var b = Int32((word >> UInt32(shift)) & UInt32(0xFF))
    if b > 127:
        b -= 256
    return Float32(b)


def _sbyte_bl(word: UInt32, shift: Int) -> Float32:
    """Branchless twin of `_sbyte`: shift the target byte into the sign position and arithmetic-
    shift back, instead of a mask + compare + conditional subtract. Exists to rule out "the branch
    is what's slow" before blaming the load itself -- see `_gemv_i8_word32_bl`."""
    var raw = (word >> UInt32(shift)) & UInt32(0xFF)
    var signed_val = (Int32(raw) << 24) >> 24
    return Float32(signed_val)


def _gemv_i8_char4(y: _FP, x: _FP, w: _I8P, wscale: _FP, k: Int, n: Int):
    """Variant A (baseline): `w.load[width=4]` char4 vector load, dequant, accumulate -- byte-for-
    byte the same inner loop `residentk.kernels._norm_gemv_kernel_i8` uses, with the rmsnorm stage
    removed (`xs` is a verbatim copy of `x`, not a normalized one) so this probe measures only the
    weight-load choice."""
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
        var base = j * k
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC4](srow)
        var k_vec = (k // _VEC_STRIDE4) * _VEC_STRIDE4
        var t = lane * _VEC4
        while t < k_vec:
            var xv = xs.load[width=_VEC4](t)
            var wv = w.load[width=_VEC4](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE4
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
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


def _gemv_i8_word32(y: _FP, x: _FP, w: _I8P, wscale: _FP, k: Int, n: Int):
    """Variant B: ONE explicit `UInt32` read (via `w.bitcast[UInt32]()`) fetching the same 4 bytes
    `_gemv_i8_char4` reads with `load[width=4]`, then a manual shift/mask unpack to 4 signed lanes.
    Same 4-elements-per-step throughput as variant A -- the only difference is the load
    instruction's spelling, which is exactly what this probe exists to measure."""
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
        var base = j * k
        var srow = wscale[j]
        var wu = w.bitcast[UInt32]()
        var k_vec = (k // _VEC_STRIDE4) * _VEC_STRIDE4
        var t = lane * _VEC4
        while t < k_vec:
            var xv = xs.load[width=_VEC4](t)
            var word = wu[(base + t) // 4]
            var wv = SIMD[DType.float32, _VEC4](
                _sbyte(word, 0), _sbyte(word, 8), _sbyte(word, 16), _sbyte(word, 24)
            ) * srow
            var pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE4
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
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


def _gemv_i8_word32_bl(y: _FP, x: _FP, w: _I8P, wscale: _FP, k: Int, n: Int):
    """Variant B2: identical to `_gemv_i8_word32` except the unpack uses `_sbyte_bl` (branchless
    shift-based sign extension) instead of `_sbyte` (mask + compare + conditional subtract). Exists
    to separate "the extra unpack arithmetic is inherently costly" from "the branch specifically is
    costly" before reporting variant B's result as the answer to the packed-load question."""
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
        var base = j * k
        var srow = wscale[j]
        var wu = w.bitcast[UInt32]()
        var k_vec = (k // _VEC_STRIDE4) * _VEC_STRIDE4
        var t = lane * _VEC4
        while t < k_vec:
            var xv = xs.load[width=_VEC4](t)
            var word = wu[(base + t) // 4]
            var wv = SIMD[DType.float32, _VEC4](
                _sbyte_bl(word, 0), _sbyte_bl(word, 8), _sbyte_bl(word, 16), _sbyte_bl(word, 24)
            ) * srow
            var pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE4
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
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


def _gemv_i8_word32x2(y: _FP, x: _FP, w: _I8P, wscale: _FP, k: Int, n: Int):
    """Variant C: TWO consecutive `UInt32` reads (8 bytes, 8 elements) issued back-to-back before
    either is unpacked, then two 4-wide `Float32` sub-vectors combined -- 8 elements/step instead of
    4, half as many outer-loop iterations for the same `k`. Tests whether more independent memory
    ops in flight per step beats twice as many trips through the narrower loop, independent of
    whether variant B alone wins or loses."""
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
        var base = j * k
        var srow = wscale[j]
        var wu = w.bitcast[UInt32]()
        var k_vec = (k // _VEC_STRIDE8) * _VEC_STRIDE8
        var t = lane * _VEC8
        while t < k_vec:
            var word0 = wu[(base + t) // 4]
            var word1 = wu[(base + t) // 4 + 1]
            var xv0 = xs.load[width=_VEC4](t)
            var xv1 = xs.load[width=_VEC4](t + _VEC4)
            var wv0 = SIMD[DType.float32, _VEC4](
                _sbyte(word0, 0), _sbyte(word0, 8), _sbyte(word0, 16), _sbyte(word0, 24)
            ) * srow
            var wv1 = SIMD[DType.float32, _VEC4](
                _sbyte(word1, 0), _sbyte(word1, 8), _sbyte(word1, 16), _sbyte(word1, 24)
            ) * srow
            var pv0 = xv0 * wv0
            var pv1 = xv1 * wv1
            acc += pv0[0] + pv0[1] + pv0[2] + pv0[3] + pv1[0] + pv1[1] + pv1[2] + pv1[3]
            t += _VEC_STRIDE8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
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


def _gemv_i8_scalar_ref(y: List[Float64], x: List[Float64], w: List[Int8], wscale: List[Float64], k: Int, n: Int) -> List[Float64]:
    """Pure-host, no-vectorization Int8 GEMV reference -- one multiply-add at a time, no `char4`, no
    packed word, nothing this probe is trying to measure. Used only to check that variants A/B/C
    agree with EACH OTHER and with this independent scalar path, on a small shape, before any timing
    number from this file is trusted."""
    var out = List[Float64](capacity=n)
    for j in range(n):
        var acc = 0.0
        var base = j * k
        var s = wscale[j]
        for i in range(k):
            acc += x[i] * (Float64(w[base + i]) * s)
        out.append(acc)
    return out^


def _ceil_div(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


def _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


@fieldwise_init
struct _QRow(Copyable, Movable):
    var q: List[Int8]
    var scale: Float64


def _quantize_row(v: List[Float64], row: Int, k: Int) -> _QRow:
    """Per-row symmetric int8 quantize, matching `residentk.session._quantize_row_i8`'s scheme
    exactly (scale = max(|row|)/127, never zero)."""
    var maxabs = 0.0
    for i in range(k):
        var av = v[row * k + i]
        if av < 0.0:
            av = -av
        if av > maxabs:
            maxabs = av
    var scale = (maxabs / 127.0) if maxabs > 0.0 else 1.0
    var inv = 1.0 / scale
    var out = List[Int8](capacity=k)
    for i in range(k):
        var q = v[row * k + i] * inv
        var r = Int(q + 0.5) if q >= 0.0 else Int(q - 0.5)
        if r > 127:
            r = 127
        if r < -127:
            r = -127
        out.append(Int8(r))
    return _QRow(out^, scale)


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


def _run_correctness(ctx: DeviceContext) raises -> Bool:
    """Stage 1: small, hand-computable shape (k=136, n=24 -- not a multiple of 256 either, so the
    scalar-tail path in every variant is exercised too), checked against the pure-host scalar
    reference AND against each other. `k=136` deliberately includes the `_VEC_STRIDE8`-misaligned
    remainder every variant's tail loop must handle."""
    var k = 136
    var n = 24
    var x64 = _pseudo(k, 3)
    var wf = _pseudo(n * k, 11)
    var w_i8 = List[Int8](capacity=n * k)
    var scales = List[Float64](capacity=n)
    for row in range(n):
        var qr = _quantize_row(wf, row, k)
        for v in qr.q:
            w_i8.append(v)
        scales.append(qr.scale)

    var refv = _gemv_i8_scalar_ref(x64, x64, w_i8, scales, k, n)

    var xbuf = ctx.enqueue_create_buffer[DType.float32](k)
    var wbuf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var sbuf = ctx.enqueue_create_buffer[DType.float32](n)
    var ybuf = ctx.enqueue_create_buffer[DType.float32](n)
    with xbuf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(x64[i])
    with wbuf.map_to_host() as h:
        for i in range(n * k):
            h[i] = w_i8[i]
    with sbuf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(scales[i])
    ctx.synchronize()

    var f_a = ctx.compile_function_unchecked[_gemv_i8_char4]()
    var f_b = ctx.compile_function_unchecked[_gemv_i8_word32]()
    var f_bl = ctx.compile_function_unchecked[_gemv_i8_word32_bl]()
    var f_c = ctx.compile_function_unchecked[_gemv_i8_word32x2]()
    var grid = _ceil_div(n, _SUBS)

    var all_ok = True

    ctx.enqueue_function_unchecked(
        f_a, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
        grid_dim=grid, block_dim=_TG,
    )
    ctx.synchronize()
    var worst_a = _worst_delta(ybuf, refv, n)
    var ok_a = worst_a < 1e-3
    all_ok = all_ok and ok_a
    print("  correctness[ char4 ]: worst |delta| vs scalar host reference =", worst_a, "  ", "OK" if ok_a else "MISMATCH")

    ctx.enqueue_function_unchecked(
        f_b, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
        grid_dim=grid, block_dim=_TG,
    )
    ctx.synchronize()
    var worst_b = _worst_delta(ybuf, refv, n)
    var ok_b = worst_b < 1e-3
    all_ok = all_ok and ok_b
    print("  correctness[ word32 ]: worst |delta| vs scalar host reference =", worst_b, "  ", "OK" if ok_b else "MISMATCH")

    ctx.enqueue_function_unchecked(
        f_bl, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
        grid_dim=grid, block_dim=_TG,
    )
    ctx.synchronize()
    var worst_bl = _worst_delta(ybuf, refv, n)
    var ok_bl = worst_bl < 1e-3
    all_ok = all_ok and ok_bl
    print("  correctness[ word32_bl ]: worst |delta| vs scalar host reference =", worst_bl, "  ", "OK" if ok_bl else "MISMATCH")

    ctx.enqueue_function_unchecked(
        f_c, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
        grid_dim=grid, block_dim=_TG,
    )
    ctx.synchronize()
    var worst_c = _worst_delta(ybuf, refv, n)
    var ok_c = worst_c < 1e-3
    all_ok = all_ok and ok_c
    print("  correctness[ word32x2 ]: worst |delta| vs scalar host reference =", worst_c, "  ", "OK" if ok_c else "MISMATCH")

    return all_ok


def _worst_delta(ybuf: DeviceBuffer[DType.float32], refv: List[Float64], n: Int) raises -> Float64:
    var worst = 0.0
    with ybuf.map_to_host() as h:
        for j in range(n):
            var d = Float64(h[j]) - refv[j]
            if d < 0.0:
                d = -d
            if d > worst:
                worst = d
    return worst


def main() raises:
    print("=== int8 packed-load probe: char4 vs explicit-word-unpack, at real decode GEMV shapes ===")
    print("")

    if not PROBE_GPU_BUILD:
        print("Built WITHOUT -D ALGENTA_GPU: refusing to report timings (kernels compiled out).")
        return
    if not has_accelerator():
        print("No usable accelerator. Refusing to report timings.")
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
    print("--- Decode-shaped timing: lm_head-column-block-like (k=1024, n=2048) ---")
    _time_shape(ctx, 1024, 2048, 200)


def _time_shape(ctx: DeviceContext, k: Int, n: Int, reps: Int) raises:
    var x64 = _pseudo(k, 3)
    var wf = _pseudo(n * k, 11)
    var w_i8 = List[Int8](capacity=n * k)
    var scales = List[Float64](capacity=n)
    for row in range(n):
        var qr = _quantize_row(wf, row, k)
        for v in qr.q:
            w_i8.append(v)
        scales.append(qr.scale)

    var xbuf = ctx.enqueue_create_buffer[DType.float32](k)
    var wbuf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var sbuf = ctx.enqueue_create_buffer[DType.float32](n)
    var ybuf = ctx.enqueue_create_buffer[DType.float32](n)
    with xbuf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(x64[i])
    with wbuf.map_to_host() as h:
        for i in range(n * k):
            h[i] = w_i8[i]
    with sbuf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(scales[i])
    ctx.synchronize()

    var f_a = ctx.compile_function_unchecked[_gemv_i8_char4]()
    var f_b = ctx.compile_function_unchecked[_gemv_i8_word32]()
    var f_bl = ctx.compile_function_unchecked[_gemv_i8_word32_bl]()
    var f_c = ctx.compile_function_unchecked[_gemv_i8_word32x2]()
    var grid = _ceil_div(n, _SUBS)

    print("   k=", k, " n=", n)

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_a, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_a = List[Float64]()
    for _ in range(reps):
        var t0 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_a, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
        ctx.synchronize()
        samples_a.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var med_a = _median(samples_a)
    print("   char4    (baseline) : median of", reps, "=", med_a, "us")

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_b, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_b = List[Float64]()
    for _ in range(reps):
        var t0b = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_b, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
        ctx.synchronize()
        samples_b.append(Float64(Int(perf_counter_ns() - t0b)) / 1e3)
    var med_b = _median(samples_b)
    print("   word32   (packed-4) : median of", reps, "=", med_b, "us   (", (med_b - med_a) / med_a * 100.0, "% vs char4)")

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_bl, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_bl = List[Float64]()
    for _ in range(reps):
        var t0bl = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_bl, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
        ctx.synchronize()
        samples_bl.append(Float64(Int(perf_counter_ns() - t0bl)) / 1e3)
    var med_bl = _median(samples_bl)
    print("   word32_bl(branchless): median of", reps, "=", med_bl, "us   (", (med_bl - med_a) / med_a * 100.0, "% vs char4)")

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_c, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_c = List[Float64]()
    for _ in range(reps):
        var t0c = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_c, ybuf.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), sbuf.unsafe_ptr(), k, n,
            grid_dim=grid, block_dim=_TG,
        )
        ctx.synchronize()
        samples_c.append(Float64(Int(perf_counter_ns() - t0c)) / 1e3)
    var med_c = _median(samples_c)
    print("   word32x2 (packed-8) : median of", reps, "=", med_c, "us   (", (med_c - med_a) / med_a * 100.0, "% vs char4)")
