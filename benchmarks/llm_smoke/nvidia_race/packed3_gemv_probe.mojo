"""packed3_gemv_probe.mojo — the runtime half of the arithmetic-packed-int8 (packed3) decode
campaign: the compile battery (`packed_int8_phase0.sh`) proved the `std.memory.bitcast` byte
view lowers for sm_80/sm_89 on the pinned Mojo 1.0.0 / MAX 26.5.0 toolchain; this probe
measures what the DECODE KERNEL FAMILY built on it (`residentk.kernels_packed3`) actually does
on the A100/L4 VMs, in three parts:

PART 0 — HOST PACK ROUND-TRIP (runs on any host with the CUDA build, no GPU needed):
    (a) EXACT byte round-trip of the pack/unpack integer math on synthetic patterns — corner
        triples, one-hot bytes, a 256-entry diagonal sweep and 200k LCG-random triples:
        unpack(pack(b0,b1,b2)) == (b0,b1,b2), checked through BOTH unpack paths — the
        device's byte VIEW (the word's bit pattern must BE `[b0, b1, b2, 0]`; the word is a
        32-bit container, never a Float32 value) and the integer-mask inverse;
    (b) pack -> host-unpack-dequant -> compare against the original weights on real-shaped
        pseudo-random rows: max abs error must sit inside the quantization bound scale/2 per
        block — quantization error ONLY, no packing bug.

PART 1 — STREAMING PARITY: a packed3 buffer vs its f32 twin, both streamed through the same
    proven 128-bit `load[width=4]` path (the packed side inserts the 12-quant-byte selection
    the GEMV kernels use), GB/s each. Expect parity — >= 85% of the f32 number — because both
    are Float32 vector loads; anything less means the byte view throttles the load path.

PART 2 — `_packed3_gemv_kernel` on real 0.6B-shaped roles (K=1024,N=4096 and K=3072,N=1024):
    correctness vs a host Float64 dequant oracle, tolerance = quantization error ONLY (the
    kernel-vs-dequantized-oracle gap is reported separately and must be sum-order noise, not
    an unpack/lane/reduction bug), then timed against the f32 `_gemv_accum_kernel` twin,
    GB/s and % of HBM peak for each.

PART 3 — the ledger traffic-model projection: REALRACE_RESULTS.md ("THE SECOND-GPU LANE")
    established f32 decode streams 2.62 GB/token against the A100's 1555 GB/s and the L4's
    300 GB/s; at the packed3 layout (module docstring's layout math) the 0.6B's 2.38 GB of
    f32 weights compress to ~0.87-0.94 GB and the per-token traffic to ~1.11-1.18 GB — the
    projected bandwidth floor this kernel family races against.

INTEGRITY ARMOR, inherited from f16_simd_arith_probe.mojo (measured not assumed): every
timed kernel stores ALL lanes' accumulated result (a `sink[0]`-style store lets DCE kill the
other lanes — ncu caught exactly that), and the stream loads feed the stored accumulator so
neither they nor the byte view can be deleted. The timed windows are REPS back-to-back
dispatches with ONE synchronize — device-bound, the i8_gemv_probe.mojo form.

Build (macOS build host or the VM; plain build first, setup_vm.sh stage 7's object+link
recipe as fallback when the toolchain does not auto-link the MAX CUDA runtime):
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo \
        -o packed3_gemv_probe
(same with `sm_89` for the L4 lane)
"""

from max.gpu.host import DeviceContext
from std.gpu import block_idx, grid_dim, thread_idx
from std.memory import bitcast
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.kernels import _TG, _SUBS, _gemv_accum_kernel
from residentk.kernels_packed3 import (
    _packed3_gemv_kernel,
    _pack_f32_to_packed3, _p3_dequant_host,
    _p3_k_pack, _p3_words_per_row, _p3_blocks_per_row,
    _p3_pack_word, _p3_unpack_word,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime REPS_GEMV: Int = 400
comptime REPS_STREAM: Int = 50
comptime HBM_GB_S: Float64 = 1555.0
"""A100-SXM4-40GB HBM peak, the ledger's number."""
comptime L4_GB_S: Float64 = 300.0
"""L4 (g2-standard-8, the ledger's second-GPU lane) bandwidth."""

# ── the ledger traffic model (REALRACE_RESULTS.md, THE SECOND-GPU LANE) ──────
comptime F32_GB_PER_TOKEN: Float64 = 2.62
comptime WEIGHTS_GB_F32: Float64 = 2.38
comptime NONWEIGHT_GB_PER_TOKEN: Float64 = F32_GB_PER_TOKEN - WEIGHTS_GB_F32

comptime STREAM_NTHREADS: Int = 256
comptime STREAM_NBLOCKS: Int = 432
comptime STREAM_NWORDS: Int = 24 * 1024 * 1024
"""Float32 words per stream buffer (96 MB — larger than the A100's 40 MB L2, so the timed
passes actually stream from HBM instead of measuring the cache)."""


def _stream_f32_kernel(dst: _FP, src: _FP, n_vec_i64: Int64):
    """Reference streamer: grid-strided 128-bit Float32 loads, the proven HBM-speed path."""
    var n_vec = Int(n_vec_i64)
    var gid = Int(block_idx.x) * STREAM_NTHREADS + Int(thread_idx.x)
    var stride = Int(grid_dim.x) * STREAM_NTHREADS
    var acc = Float32(0.0)
    var i = gid
    while i < n_vec:
        var v = src.load[width=4](i * 4)
        acc += v[0] + v[1] + v[2] + v[3]
        i += stride
    # ALL lanes store — the f16_simd_arith_probe armor against dead-lane DCE.
    dst[gid] = acc


def _stream_p3_kernel(dst: _FP, src: _FP, n_vec_i64: Int64):
    """The packed3 twin: the SAME 128-bit Float32 loads, with the GEMV kernels' byte-view
    unpack (12 quant-lane selections per 16 bytes) inserted between load and accumulate."""
    var n_vec = Int(n_vec_i64)
    var gid = Int(block_idx.x) * STREAM_NTHREADS + Int(thread_idx.x)
    var stride = Int(grid_dim.x) * STREAM_NTHREADS
    var acc = Float32(0.0)
    var i = gid
    while i < n_vec:
        var v = src.load[width=4](i * 4)
        var b = bitcast[DType.uint8, 16](v)
        var s = Int32(0)
        # The 12 quant bytes of the 16: lane (e//3)*4 + e%3 for element e — the exact
        # selection `_packed3_gemv_kernel` performs.
        s += Int32(b[0])
        s += Int32(b[1])
        s += Int32(b[2])
        s += Int32(b[4])
        s += Int32(b[5])
        s += Int32(b[6])
        s += Int32(b[8])
        s += Int32(b[9])
        s += Int32(b[10])
        s += Int32(b[12])
        s += Int32(b[13])
        s += Int32(b[14])
        acc += Float32(s)
        i += stride
    dst[gid] = acc


def _lehmer_next(state: Int64) -> Int64:
    """Park-Miller LCG: `state * 48271 mod 2^31-1` — the product stays below 2^63, so this
    is exact Int64 arithmetic, deterministic across hosts (no Float rounding, no wrap)."""
    return (state * 48271) % 2147483647


def _lehmer_f32(state: Int64) -> Float32:
    """Map an LCG state into [-1, 1)."""
    return Float32(Float64(state) * (2.0 / 2147483647.0) - 1.0)


def _check_byte_triple(b0: UInt8, b1: UInt8, b2: UInt8) -> Bool:
    """One synthetic-pattern round-trip, checked through BOTH unpack paths:

    1. the DEVICE's path — the packed word bitcast to its byte view must be exactly
       `[b0, b1, b2, 0]` (the kernel's lane selection reads bytes 0,1,2);
    2. `_p3_unpack_word`'s integer-mask path — must agree.

    Note the word is a BIT-PATTERN container, never a Float32 value: comparing it to
    `Float32(b0 + 256*b1 + 65536*b2)` would be WRONG (that is the integer whose bit
    pattern is stored, not the value the word denotes)."""
    var v = _p3_pack_word(b0, b1, b2)
    var view = bitcast[DType.uint8, 4](SIMD[DType.float32, 1](v))
    if view[0] != b0 or view[1] != b1 or view[2] != b2 or view[3] != UInt8(0):
        return False
    var (u0, u1, u2) = _p3_unpack_word(v)
    return u0 == b0 and u1 == b1 and u2 == b2


def _host_roundtrip_checks() raises -> Bool:
    """PART 0. Returns True iff every host-side round-trip passes."""
    var ok = True

    # (a) exact byte round-trip of the pack/unpack integer math.
    var n_checked = 0
    var n_fail = 0
    # Corners + one-hot bytes.
    for b0 in range(2):
        for b1 in range(2):
            for b2 in range(2):
                var bb0 = UInt8(b0 * 255)
                var bb1 = UInt8(b1 * 255)
                var bb2 = UInt8(b2 * 255)
                n_checked += 1
                if not _check_byte_triple(bb0, bb1, bb2):
                    n_fail += 1
    if not _check_byte_triple(UInt8(1), UInt8(2), UInt8(3)):
        n_fail += 1
    n_checked += 1
    if not _check_byte_triple(UInt8(3), UInt8(2), UInt8(1)):
        n_fail += 1
    n_checked += 1
    if not _check_byte_triple(UInt8(128), UInt8(128), UInt8(128)):
        n_fail += 1
    n_checked += 1
    if not _check_byte_triple(UInt8(255), UInt8(254), UInt8(253)):
        n_fail += 1
    n_checked += 1
    # Diagonal sweep: every byte value once in each position.
    for i in range(256):
        n_checked += 3
        if not _check_byte_triple(UInt8(i), UInt8(255 - i), UInt8((i * 7) % 256)):
            n_fail += 1
        if not _check_byte_triple(UInt8(255 - i), UInt8((i * 7) % 256), UInt8(i)):
            n_fail += 1
        if not _check_byte_triple(UInt8((i * 7) % 256), UInt8(i), UInt8(255 - i)):
            n_fail += 1
    # 200k LCG-random triples.
    var st = Int64(987654321)
    for _ in range(200000):
        st = _lehmer_next(st)
        var b0 = UInt8(Int(st & 255))
        st = _lehmer_next(st)
        var b1 = UInt8(Int(st & 255))
        st = _lehmer_next(st)
        var b2 = UInt8(Int(st & 255))
        n_checked += 1
        if not _check_byte_triple(b0, b1, b2):
            n_fail += 1
    if n_fail > 0:
        ok = False
    print("  byte round-trip:", n_checked, "triples,", n_fail, "mismatches ->",
          "PASS" if n_fail == 0 else "FAIL")

    # (b) pack -> unpack-dequant -> compare: the only allowed error is quantization.
    # k = 1000 exercises BOTH tails at once: not a multiple of 12 (k_pack = 1008) and not a
    # multiple of 32 (32 blocks, the last one part real / part padding).
    var k = 1000
    var n = 16
    var k_pack = _p3_k_pack(k)
    var words_per_row = _p3_words_per_row(k)
    var nblocks = _p3_blocks_per_row(k)
    var w = List[Float32](capacity=n * k)
    st = Int64(123456789)
    for _ in range(n * k):
        st = _lehmer_next(st)
        w.append(_lehmer_f32(st))
    var p = _pack_f32_to_packed3(w, k, n)
    var len_ok = len(p.packed) == n * words_per_row and \
        len(p.scales) == n * nblocks and len(p.zeros) == n * nblocks
    if not len_ok:
        ok = False
    print("  packed list lengths:", len(p.packed), len(p.scales), len(p.zeros),
          "expected", n * words_per_row, n * nblocks, n * nblocks, "->",
          "PASS" if len_ok else "FAIL")

    var deq = _p3_dequant_host(p.packed, p.scales, p.zeros, k, n)
    var max_err = Float32(0.0)
    var max_bound = Float32(0.0)
    var err_fail = 0
    for r in range(n):
        for e in range(k):
            var sc = p.scales[r * nblocks + (e >> 5)]
            var bound = sc * Float32(0.5)
            var err = deq[r * k_pack + e] - w[r * k + e]
            if err < Float32(0.0):
                err = -err
            if err > max_err:
                max_err = err
            if bound > max_bound:
                max_bound = bound
            # 1.001 slack: the bound is real arithmetic, err is Float32 arithmetic.
            if err > bound * Float32(1.001) + Float32(1.0e-7):
                err_fail += 1
    if err_fail > 0:
        ok = False
    print("  quantization round-trip: max abs err", max_err, "vs bound", max_bound,
          "(", err_fail, "elements above bound ) ->",
          "PASS" if err_fail == 0 else "FAIL")
    return ok


def _run_shape(
    ref ctx: DeviceContext, k_comptime: Int, n_comptime: Int, shape_name: String,
) raises -> Bool:
    """PART 2 for one (K, N) role: build, pack, oracle-check `_packed3_gemv_kernel`, then
    time it against the f32 `_gemv_accum_kernel` twin. Returns the correctness verdict."""
    var k = k_comptime
    var n = n_comptime
    var k_pack = _p3_k_pack(k)
    var words_per_row = _p3_words_per_row(k)
    var nblocks = _p3_blocks_per_row(k)

    # ── deterministic pseudo-random weights and activation ──
    var w = List[Float32](capacity=n * k)
    var st = Int64(246801357)
    for _ in range(n * k):
        st = _lehmer_next(st)
        w.append(_lehmer_f32(st))
    var x = List[Float32](capacity=k_pack)
    for _ in range(k):
        st = _lehmer_next(st)
        x.append(_lehmer_f32(st))
    for _ in range(k_pack - k):
        x.append(Float32(0.0))  # the TAIL contract: x zero-padded to k_pack

    # ── host pack + dequant oracle ──
    var p = _pack_f32_to_packed3(w, k, n)
    var deq = _p3_dequant_host(p.packed, p.scales, p.zeros, k, n)
    var y_deq = List[Float64](capacity=n)
    var y_true = List[Float64](capacity=n)
    # Per-row absolute term sums: the robust denominator for relative diffs. Rows whose
    # dot product cancels toward zero would blow up a |y|-denominated relative error even
    # for a perfect kernel; Sigma |x_e * w_e| never cancels and is the row's true scale.
    var abs_deq = List[Float64](capacity=n)
    var abs_true = List[Float64](capacity=n)
    for j in range(n):
        var acc_deq = Float64(0.0)
        var acc_true = Float64(0.0)
        var a_deq = Float64(0.0)
        var a_true = Float64(0.0)
        for e in range(k):
            var xe = Float64(x[e])
            var ax = xe
            if ax < 0.0:
                ax = -ax
            var wde = Float64(deq[j * k_pack + e])
            var awd = wde
            if awd < 0.0:
                awd = -awd
            var wtr = Float64(w[j * k + e])
            var awt = wtr
            if awt < 0.0:
                awt = -awt
            acc_deq += xe * wde
            acc_true += xe * wtr
            a_deq += ax * awd
            a_true += ax * awt
        y_deq.append(acc_deq)
        y_true.append(acc_true)
        abs_deq.append(a_deq)
        abs_true.append(a_true)

    # ── device buffers + upload ──
    var wp_buf = ctx.enqueue_create_buffer[DType.float32](n * words_per_row)
    var sc_buf = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
    var z_buf = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
    var x_buf = ctx.enqueue_create_buffer[DType.float32](k_pack)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var y_f32 = ctx.enqueue_create_buffer[DType.float32](n)
    var wf32_buf = ctx.enqueue_create_buffer[DType.float32](n * k)
    var packed_p = p.packed.unsafe_ptr()
    with wp_buf.map_to_host() as h:
        for i in range(n * words_per_row):
            h[i] = packed_p[i]
    var scales_p = p.scales.unsafe_ptr()
    with sc_buf.map_to_host() as h:
        for i in range(n * nblocks):
            h[i] = scales_p[i]
    var zeros_p = p.zeros.unsafe_ptr()
    with z_buf.map_to_host() as h:
        for i in range(n * nblocks):
            h[i] = zeros_p[i]
    var x_p = x.unsafe_ptr()
    with x_buf.map_to_host() as h:
        for i in range(k_pack):
            h[i] = x_p[i]
    var w_p = w.unsafe_ptr()
    with wf32_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = w_p[i]

    # ── correctness: one launch, read back, compare against BOTH oracles ──
    ctx.enqueue_function[_packed3_gemv_kernel](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), wp_buf.unsafe_ptr(),
        sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(), Int64(k), Int64(n),
        grid_dim=n, block_dim=_TG)
    ctx.synchronize()

    var max_rel_code = Float64(0.0)
    var max_rel_quant = Float64(0.0)
    var max_abs_code = Float64(0.0)
    var max_abs_quant = Float64(0.0)
    with y_buf.map_to_host() as h:
        for j in range(n):
            var yk = Float64(h[j])
            var d_code = yk - y_deq[j]
            if d_code < 0.0:
                d_code = -d_code
            var d_quant = y_deq[j] - y_true[j]
            if d_quant < 0.0:
                d_quant = -d_quant
            if d_code > max_abs_code:
                max_abs_code = d_code
            if d_quant > max_abs_quant:
                max_abs_quant = d_quant
            # Relative diffs denominated by the row's absolute term sum — never cancels.
            var r_code = d_code / abs_deq[j]
            if r_code > max_rel_code:
                max_rel_code = r_code
            var r_quant = d_quant / abs_true[j]
            if r_quant > max_rel_quant:
                max_rel_quant = r_quant
    # Codegen gap: kernel vs dequantized oracle — Float32 summation-order noise only,
    # typically ~1e-6 of the row's term sum; 1e-4 leaves two orders of margin and any
    # unpack/lane/reduction bug would land at O(1e-1).
    var code_ok = max_rel_code <= 1.0e-4
    # Quantization gap: dequantized oracle vs true f32 weights — bounded by the block-32
    # scale/2 per element, expected ~max_scale / (2 * mean|w|) ~ a few 1e-3 of the term sum.
    var quant_ok = max_rel_quant <= 1.0e-2
    print(shape_name, "correctness: kernel-vs-dequant-oracle max rel diff",
          max_rel_code, "( max abs", max_abs_code, ") ->",
          "PASS" if code_ok else "FAIL")
    print(shape_name, "quantization: dequant-vs-true max rel diff",
          max_rel_quant, "( max abs", max_abs_quant, ") ->",
          "PASS" if quant_ok else "FAIL")

    # ── timing: REPS back-to-back dispatches, one synchronize (device-bound windows) ──
    var t0 = perf_counter_ns()
    for _ in range(REPS_GEMV):
        ctx.enqueue_function[_packed3_gemv_kernel](
            y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), wp_buf.unsafe_ptr(),
            sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(), Int64(k), Int64(n),
            grid_dim=n, block_dim=_TG)
    ctx.synchronize()
    var p3_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS_GEMV)
    # Weight stream: packed words + per-block scale/zero. x is L2-resident across the reps.
    var p3_bytes = Float64(n) * (Float64(words_per_row) * 4.0 + Float64(nblocks) * 8.0)

    t0 = perf_counter_ns()
    for _ in range(REPS_GEMV):
        ctx.enqueue_function[_gemv_accum_kernel](
            y_f32.unsafe_ptr(), x_buf.unsafe_ptr(), wf32_buf.unsafe_ptr(),
            Int64(k), Int64(n),
            grid_dim=(n + _SUBS - 1) // _SUBS, block_dim=_TG)
    ctx.synchronize()
    var f32_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS_GEMV)
    var f32_bytes = Float64(n) * Float64(k) * 4.0

    print(shape_name, "packed3:", p3_us, "us ->",
          p3_bytes / (p3_us * 1.0e-6) / 1.0e9, "GB/s (",
          p3_bytes / (p3_us * 1.0e-6) / 1.0e9 / HBM_GB_S * 100.0, "% of HBM )")
    print(shape_name, "f32 twin:", f32_us, "us ->",
          f32_bytes / (f32_us * 1.0e-6) / 1.0e9, "GB/s (",
          f32_bytes / (f32_us * 1.0e-6) / 1.0e9 / HBM_GB_S * 100.0, "% of HBM )")
    return code_ok and quant_ok


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("packed3_gemv_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        # PART 0 is host-only — it runs on a CUDA build even without an accelerator, so the
        # pack/unpack math is verified on the build host before any VM time is spent.
        print("PART 0 — host pack round-trip")
        if not _host_roundtrip_checks():
            print("packed3_gemv_probe: host round-trip FAILED")
            exit(1)

        if not has_accelerator():
            print("packed3_gemv_probe: no accelerator on this host (host checks passed)")
            return

        var ctx = DeviceContext()
        print("packed3_gemv_probe: device:", ctx.name())

        # ── PART 1: streaming parity, packed3 byte view vs f32 twin ──
        print("PART 1 — streaming parity (", STREAM_NWORDS * 4 // (1024 * 1024),
              "MB per buffer )")
        var src = ctx.enqueue_create_buffer[DType.float32](STREAM_NWORDS)
        var sink = ctx.enqueue_create_buffer[DType.float32](
            STREAM_NBLOCKS * STREAM_NTHREADS)
        var n_vec = STREAM_NWORDS // 4
        var stream_bytes = Float64(STREAM_NWORDS) * 4.0

        # Warmup both (clock ramp + first-dispatch cost out of the timed window).
        ctx.enqueue_function[_stream_f32_kernel](
            sink.unsafe_ptr(), src.unsafe_ptr(), Int64(n_vec),
            grid_dim=STREAM_NBLOCKS, block_dim=STREAM_NTHREADS)
        ctx.enqueue_function[_stream_p3_kernel](
            sink.unsafe_ptr(), src.unsafe_ptr(), Int64(n_vec),
            grid_dim=STREAM_NBLOCKS, block_dim=STREAM_NTHREADS)
        ctx.synchronize()

        var t0 = perf_counter_ns()
        for _ in range(REPS_STREAM):
            ctx.enqueue_function[_stream_f32_kernel](
                sink.unsafe_ptr(), src.unsafe_ptr(), Int64(n_vec),
                grid_dim=STREAM_NBLOCKS, block_dim=STREAM_NTHREADS)
        ctx.synchronize()
        var f32_s = Float64(perf_counter_ns() - t0) / 1.0e9 / Float64(REPS_STREAM)

        t0 = perf_counter_ns()
        for _ in range(REPS_STREAM):
            ctx.enqueue_function[_stream_p3_kernel](
                sink.unsafe_ptr(), src.unsafe_ptr(), Int64(n_vec),
                grid_dim=STREAM_NBLOCKS, block_dim=STREAM_NTHREADS)
        ctx.synchronize()
        var p3_s = Float64(perf_counter_ns() - t0) / 1.0e9 / Float64(REPS_STREAM)

        var f32_gbs = stream_bytes / f32_s / 1.0e9
        var p3_gbs = stream_bytes / p3_s / 1.0e9
        var parity = p3_gbs / f32_gbs
        print("  f32 stream:   ", f32_s * 1000.0, "ms/dispatch ->", f32_gbs, "GB/s (",
              f32_gbs / HBM_GB_S * 100.0, "% of HBM )")
        print("  packed3 view: ", p3_s * 1000.0, "ms/dispatch ->", p3_gbs, "GB/s (",
              p3_gbs / HBM_GB_S * 100.0, "% of HBM )")
        print("  parity p3/f32:", parity, "->",
              "PASS" if parity >= 0.85 else "FAIL", "(gate: >= 0.85)")

        # ── PART 2: GEMV correctness + race timing at the 0.6B role shapes ──
        print("PART 2 — _packed3_gemv_kernel, real-shaped roles")
        var ok1 = _run_shape(ctx, 1024, 4096, "  k=1024 n=4096: ")
        var ok2 = _run_shape(ctx, 3072, 1024, "  k=3072 n=1024: ")

        # ── PART 3: ledger traffic-model projection ──
        print("PART 3 — traffic model (ledger: f32 = 2.62 GB/token, weights 2.38 GB )")
        var bw_brief = 4.0 / 3.0 + 4.0 / 32.0    # 1.4583 B/w — the campaign brief's layout
        var bw_impl = 4.0 / 3.0 + 8.0 / 32.0     # 1.5833 B/w — this implementation (f32 scale+zero)
        var tok_brief = WEIGHTS_GB_F32 * bw_brief / 4.0 + NONWEIGHT_GB_PER_TOKEN
        var tok_impl = WEIGHTS_GB_F32 * bw_impl / 4.0 + NONWEIGHT_GB_PER_TOKEN
        print("  bytes/weight: brief", bw_brief, "| as implemented", bw_impl)
        print("  GB/token:     brief", tok_brief, "| as implemented", tok_impl,
              "| f32", F32_GB_PER_TOKEN)
        print("  bandwidth-floor tok/s  A100 (1555 GB/s):  f32",
              HBM_GB_S / F32_GB_PER_TOKEN, "| packed3 brief",
              HBM_GB_S / tok_brief, "| packed3 impl", HBM_GB_S / tok_impl)
        print("  bandwidth-floor tok/s  L4 (300 GB/s):     f32",
              L4_GB_S / F32_GB_PER_TOKEN, "| packed3 brief",
              L4_GB_S / tok_brief, "| packed3 impl", L4_GB_S / tok_impl)

        if ok1 and ok2:
            print("packed3_gemv_probe: done")
        else:
            print("packed3_gemv_probe: correctness FAILED")
            exit(1)
