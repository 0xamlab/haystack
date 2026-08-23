"""tc_escape_probe.mojo — the NVIDIA tensor-core escape-hatch probe: can an nvcc-compiled CUDA
object (cuBLAS HMMA GEMM, inline WMMA, packed3->f16 dequant) be LINKED into a Mojo CUDA binary
and DISPATCHED from Mojo — and if so, how fast is it, measured, on H100 + A100?

The pinned Mojo 1.0.0 / MAX 26.5.0 CUDA backend has no tensor-core mma surface and scalarizes
sub-f32 loads (mma_surface_probe.sh), so the prefill GEMMs sit at f32-SIMT efficiency while
llama.cpp's cuBLAS HMMA runs 14.7 ms of TC GEMM over our 297.5 ms f32 SIMT prefill (A100
autopsy). This probe is the NVIDIA analog of the Metal lane's escape hatch (hand-written .metal
shim compiled outside Mojo, linked as a blob, dispatched over a discovery ABI): tc_shim.cu is
compiled with nvcc and linked via -Xlinker, called through std.ffi.external_call.

What it decides (per the campaign brief):
  1. LINK FEASIBILITY — does the link succeed, does the shim run on Mojo-allocated device
     pointers (shared-context proof), correct vs an f64 CPU reference (rel < 1e-2)?
  2. NUMBERS — qkv/o/down-shaped GEMMs, 20-run median + IQR, TC arms vs the in-tree v2 f32
     kernel (residentk.kernels_prefill_f32_v2), TF/s on both GPUs.
  3. ATTENTION — WMMA smoke (16x16x16 f16 tile, the S = Q @ K^T shape): compile+link+run
     feasibility of inline tensor-core PTX in the same shim.
  4. WEIGHT FORMAT — packed3 -> f16 one-time dequant cost at session open (0.6B real layout,
     7B-scale attempt) + the dual-residency VRAM delta.

Build (scripts/build_tc_probe.sh wraps this; GPU 0, solo census):
    # H100 (sm_90):
    nvcc -O3 -arch=sm_90 -Xcompiler -fPIC -c benchmarks/llm_smoke/nvidia_race/tc_shim.cu \\
        -o /tmp/tc_probe/tc_shim.o
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_90 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/tc_escape_probe.mojo \\
        -o /tmp/tc_probe/tc_escape_probe \\
        -Xlinker /tmp/tc_probe/tc_shim.o -Xlinker -lcublas -Xlinker -lcudart \\
        -Xlinker -L/usr/local/cuda/lib64
    # (object + clang link fallback when the plain build refuses the extra objects — the
    #  scripts/build_tc_probe.sh recipe mirrors nvidia_race/setup_vm.sh's build_one_driver.)

Mojo-side sync seam: every shim call runs on the shim's own non-blocking stream and
stream-synchronizes before returning; this probe additionally brackets every timed call with
ctx.synchronize() so both arms (Mojo kernel vs shim call) are timed identically. MAX 26.5's
DeviceStream exposes no raw cudaStream_t accessor (round-3 API map), so stream-ordered
handoff without a host sync is NOT available — documented as the integration-round question.
"""

from max.gpu.host import DeviceBuffer, DeviceContext
from std.gpu import block_idx, thread_idx
from std.time import perf_counter_ns
from std.sys import has_accelerator, is_defined
from std.ffi import external_call
from std.origin import MutAnyOrigin, MutUntrackedOrigin
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM, _G2_BN, _G2_NTHREADS,
    _pf_gemm_assign_kernel_v2,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime WARMUP: Int = 5
comptime SAMPLES: Int = 20
comptime REL_GATE: Float64 = 1.0e-2
"""Campaign brief's correctness gate for f16-TC vs the f64 reference."""

comptime FILL_MULT_A: Int64 = 2654435761
comptime FILL_MULT_W: Int64 = 40503
"""Deterministic LCG-style fills, reproducible bit-exactly by the host f64 reference."""

# ── FFI wrappers: one line per tc_shim.cu entry point, Int64 = device address / status ─────

def _tc_init() -> Int:
    return Int(external_call["tc_shim_init", Int64]())


def _tc_last_error() -> Int:
    return Int(external_call["tc_shim_last_error", Int64]())


def _tc_diag(mut device: Int64, mut context_ptr: Int64, mut driver_ok: Int64) -> Int:
    return Int(
        external_call[
            "tc_shim_diag", Int64,
            UnsafePointer[Int64, origin=MutUntrackedOrigin],
            UnsafePointer[Int64, origin=MutUntrackedOrigin],
            UnsafePointer[Int64, origin=MutUntrackedOrigin],
        ](
            UnsafePointer(to=device).unsafe_origin_cast[MutUntrackedOrigin](),
            UnsafePointer(to=context_ptr).unsafe_origin_cast[MutUntrackedOrigin](),
            UnsafePointer(to=driver_ok).unsafe_origin_cast[MutUntrackedOrigin](),
        )
    )


def _tc_stage_f16(src: Int, dst: Int, n: Int) -> Int:
    return Int(
        external_call["tc_shim_f32_to_f16", Int64, Int64, Int64, Int64](
            Int64(src), Int64(dst), Int64(n))
    )


def _tc_gemm_f16(a: Int, w16: Int, m: Int, k: Int, n: Int, a16: Int, c16: Int, c32: Int,
                 f16_accum: Int) -> Int:
    return Int(
        external_call[
            "tc_shim_gemm_f16", Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            Int64,
        ](Int64(a), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(a16), Int64(c16),
          Int64(c32), Int64(f16_accum))
    )


def _tc_gemm_f16_pre(a16: Int, w16: Int, m: Int, k: Int, n: Int, c16: Int, c32: Int,
                     f16_accum: Int) -> Int:
    return Int(
        external_call[
            "tc_shim_gemm_f16_pre", Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            Int64,
        ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c16), Int64(c32),
          Int64(f16_accum))
    )


def _tc_gemmex_only(a16: Int, w16: Int, m: Int, k: Int, n: Int, c16: Int, f16_accum: Int) -> Int:
    return Int(
        external_call[
            "tc_shim_gemmex_only", Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
        ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c16), Int64(f16_accum))
    )


def _tc_gemm_tf32(a: Int, w: Int, m: Int, k: Int, n: Int, c: Int) -> Int:
    return Int(
        external_call["tc_shim_gemm_tf32", Int64, Int64, Int64, Int64, Int64, Int64, Int64](
            Int64(a), Int64(w), Int64(m), Int64(k), Int64(n), Int64(c))
    )


def _tc_dequant(words: Int, scales: Int, zeros: Int, out16: Int, rows: Int, k: Int, k_pad: Int,
                words_per_row: Int, blocks_per_row: Int) -> Int:
    return Int(
        external_call[
            "tc_shim_dequant_packed3_f16", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            Int64, Int64, Int64,
        ](Int64(words), Int64(scales), Int64(zeros), Int64(out16), Int64(rows), Int64(k),
          Int64(k_pad), Int64(words_per_row), Int64(blocks_per_row))
    )


def _tc_wmma(a16: Int, b16: Int, d32: Int) -> Int:
    return Int(
        external_call["tc_shim_wmma_smoke", Int64, Int64, Int64, Int64](
            Int64(a16), Int64(b16), Int64(d32))
    )


# ── angle 1 + 2 wrappers: runtime PTX load + hand-written mma.sync dispatch ───────────────

def _tc_rt_init() -> Int:
    return Int(external_call["tc_shim_rt_init", Int64]())


def _tc_rt_vadd(a: Int, b: Int, c: Int, n: Int) -> Int:
    return Int(
        external_call["tc_shim_rt_vadd", Int64, Int64, Int64, Int64, Int64](
            Int64(a), Int64(b), Int64(c), Int64(n))
    )


def _tc_rt_mma_gemm(a16: Int, w16: Int, c32: Int, m: Int, k: Int, n: Int) -> Int:
    return Int(
        external_call["tc_shim_rt_mma_gemm", Int64, Int64, Int64, Int64, Int64, Int64, Int64](
            Int64(a16), Int64(w16), Int64(c32), Int64(m), Int64(k), Int64(n))
    )


def _tc_ptr_context(addr: Int, mut out_ctx: Int64) -> Int:
    return Int(
        external_call[
            "tc_shim_ptr_context", Int64, Int64, UnsafePointer[Int64, origin=MutUntrackedOrigin],
        ](Int64(addr), UnsafePointer(to=out_ctx).unsafe_origin_cast[MutUntrackedOrigin]())
    )


# ── deterministic fills (DEVICE-side: host-mapped fills race the next enqueue — the H100
#    autopsy probe battery paid for that lesson; device kernels are stream-ordered) ────────

def _fill_lcg_kernel(buf: _FP, mult: Int64, n_i64: Int64):
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var n = Int(n_i64)
    if i < n:
        var h = Int64(i) * mult
        var r = h % Int64(1000000)
        var v = Float64(r) / 1000000.0 - 0.5
        buf[i] = Float32(v)


def _fill_seq_kernel(buf: _FP, n_i64: Int64):
    """words buffer fill for dequant timing: byte pattern (w % 251) so quants are non-zero."""
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var n = Int(n_i64)
    if i < n:
        var b = UInt32(UInt64(i) % UInt64(251))
        var word = b + (b << 8) + (b << 16)
        buf[i] = UnsafePointer(to=word).bitcast[Float32]()[unsafe_offset=0]


def _fill_lcg_host(n: Int, mult: Int64) -> List[Float64]:
    """The host twin of _fill_lcg_kernel: bit-identical Float32 inputs, widened to f64 for the
    reference GEMM. Returns Float64(Float32(v)) — the EXACT values the GPU kernels consumed."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        var h = Int64(i) * mult
        var r = h % Int64(1000000)
        var v = Float64(r) / 1000000.0 - 0.5
        out.append(Float64(Float32(v)))
    return out^


def _ceil_div_local(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


def _sort_f64(mut v: List[Float64]):
    for i in range(1, len(v)):
        var x = v[i]
        var j = i - 1
        while j >= 0 and v[j] > x:
            v[j + 1] = v[j]
            j -= 1
        v[j + 1] = x


def _stats_line(name: String, samples: List[Float64], flops: Float64):
    """Median + IQR (hinges) of a PRE-SORTED sample list (the caller runs `_sort_f64` — List
    is move-only and a borrowed parameter cannot be copied or transferred, so the sort lives
    at the call site on the caller's own var). Prints us and TF/s."""
    var med = (samples[SAMPLES // 2 - 1] + samples[SAMPLES // 2]) / 2.0
    var q1 = (samples[SAMPLES // 4 - 1] + samples[SAMPLES // 4]) / 2.0
    var q3 = (samples[3 * SAMPLES // 4 - 1] + samples[3 * SAMPLES // 4]) / 2.0
    var tf = flops / (med * 1.0e-9) / 1.0e12
    print("  ", name, "| median", med / 1000.0, "us [IQR", q1 / 1000.0, "-", q3 / 1000.0,
          "] |", tf, "TF/s")


# ── timed arms. ONE dispatch function so the timing loop is arm-symmetric: every arm runs
#    exactly `call + ctx.synchronize()` inside the clock. ───────────────────────────────────
# arm ids: 0 = v2 f32 SIMT (in-tree), 1 = tc_full f32-accum, 2 = tc_full f16-accum,
#          3 = tc_pre f32-accum (pre-staged A16), 4 = gemmex_only f32-accum (no C convert),
#          5 = tf32 direct f32, 6 = rt_mma_hand (runtime-loaded hand mma.sync, angle 2)

def _run_arm(
    arm: Int, mut ctx: DeviceContext,
    mut A: DeviceBuffer[DType.float32], mut W: DeviceBuffer[DType.float32],
    mut A16: DeviceBuffer[DType.float16], mut W16: DeviceBuffer[DType.float16],
    mut C16: DeviceBuffer[DType.float16], mut C: DeviceBuffer[DType.float32],
    m: Int, k: Int, n: Int,
) raises:
    if arm == 0:
        ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
            C.unsafe_ptr(), A.unsafe_ptr(), W.unsafe_ptr(),
            Int64(m), Int64(k), Int64(n),
            grid_dim=_ceil_div_local(m, _G2_BM) * _ceil_div_local(n, _G2_BN),
            block_dim=_G2_NTHREADS)
    elif arm == 1:
        var r = _tc_gemm_f16(Int(A.unsafe_ptr()), Int(W16.unsafe_ptr()), m, k, n,
                             Int(A16.unsafe_ptr()), Int(C16.unsafe_ptr()), Int(C.unsafe_ptr()), 0)
        if r != 0:
            raise Error("tc_shim_gemm_f16(32acc) failed: " + String(r))
    elif arm == 2:
        var r = _tc_gemm_f16(Int(A.unsafe_ptr()), Int(W16.unsafe_ptr()), m, k, n,
                             Int(A16.unsafe_ptr()), Int(C16.unsafe_ptr()), Int(C.unsafe_ptr()), 1)
        if r != 0:
            raise Error("tc_shim_gemm_f16(16acc) failed: " + String(r))
    elif arm == 3:
        var r = _tc_gemm_f16_pre(Int(A16.unsafe_ptr()), Int(W16.unsafe_ptr()), m, k, n,
                                 Int(C16.unsafe_ptr()), Int(C.unsafe_ptr()), 0)
        if r != 0:
            raise Error("tc_shim_gemm_f16_pre failed: " + String(r))
    elif arm == 4:
        var r = _tc_gemmex_only(Int(A16.unsafe_ptr()), Int(W16.unsafe_ptr()), m, k, n,
                                Int(C16.unsafe_ptr()), 0)
        if r != 0:
            raise Error("tc_shim_gemmex_only failed: " + String(r))
    elif arm == 5:
        var r = _tc_gemm_tf32(Int(A.unsafe_ptr()), Int(W.unsafe_ptr()), m, k, n,
                              Int(C.unsafe_ptr()))
        if r != 0:
            raise Error("tc_shim_gemm_tf32 failed: " + String(r))
    elif arm == 6:
        var r = _tc_rt_mma_gemm(Int(A16.unsafe_ptr()), Int(W16.unsafe_ptr()),
                                Int(C.unsafe_ptr()), m, k, n)
        if r != 0:
            raise Error("tc_shim_rt_mma_gemm failed: " + String(r))
    ctx.synchronize()


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("tc_escape_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("tc_escape_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("tc_escape_probe: device:", ctx.name())

        # ══ PART 1 — link feasibility + shared-context proof ══
        # The binary EXISTS and started => the nvcc object linked into the Mojo CUDA binary.
        # The shim must also see Mojo's context as current (cudaFree(0) inside tc_shim_init
        # binds the runtime to whatever context is current on this thread).
        var st = _tc_init()
        if st != 0:
            print("tc_escape_probe: tc_shim_init FAILED:", st, "last_error:", _tc_last_error())
            return
        print("LINK FEASIBILITY: PASS — nvcc object linked + tc_shim_init = 0")

        var dev = Int64(-1)
        var cptr = Int64(0)
        var dok = Int64(0)
        var dst = _tc_diag(dev, cptr, dok)
        print("  diag: status", dst, "| cuda device", Int(dev),
              "| current CUcontext (shim thread):",
              UnsafePointer(to=cptr).bitcast[UInt64]()[unsafe_offset=0], "| driver-api ok:", Int(dok))

        # ══ scratch buffers at the max probed shape (M=1024, K=4096, N=4096) ══
        var M_MAX = 1024
        var K_MAX = 4096
        var N_MAX = 4096
        var A = ctx.enqueue_create_buffer[DType.float32](M_MAX * K_MAX)
        var W = ctx.enqueue_create_buffer[DType.float32](N_MAX * K_MAX)
        var A16 = ctx.enqueue_create_buffer[DType.float16](M_MAX * K_MAX)
        var W16 = ctx.enqueue_create_buffer[DType.float16](N_MAX * K_MAX)
        var C16 = ctx.enqueue_create_buffer[DType.float16](M_MAX * N_MAX)
        var C = ctx.enqueue_create_buffer[DType.float32](M_MAX * N_MAX)
        var C_v2 = ctx.enqueue_create_buffer[DType.float32](M_MAX * N_MAX)
        ctx.synchronize()

        # ══ PART 1b — correctness vs f64 CPU reference, small shape ══
        var CM = 64
        var CK = 128
        var CN = 256
        ctx.enqueue_function[_fill_lcg_kernel](
            A.unsafe_ptr(), FILL_MULT_A, Int64(CM * CK),
            grid_dim=_ceil_div_local(CM * CK, 256), block_dim=256)
        ctx.enqueue_function[_fill_lcg_kernel](
            W.unsafe_ptr(), FILL_MULT_W, Int64(CN * CK),
            grid_dim=_ceil_div_local(CN * CK, 256), block_dim=256)
        ctx.synchronize()
        var r0 = _tc_stage_f16(Int(W.unsafe_ptr()), Int(W16.unsafe_ptr()), CN * CK)
        if r0 != 0:
            print("tc_escape_probe: W staging FAILED:", r0)
            return
        r0 = _tc_stage_f16(Int(A.unsafe_ptr()), Int(A16.unsafe_ptr()), CM * CK)
        if r0 != 0:
            print("tc_escape_probe: A staging FAILED:", r0)
            return
        ctx.synchronize()

        # f16 arms (both accum modes) + tf32 + in-tree v2, identical inputs
        var st16 = _tc_gemm_f16(Int(A.unsafe_ptr()), Int(W16.unsafe_ptr()), CM, CK, CN,
                                Int(A16.unsafe_ptr()), Int(C16.unsafe_ptr()),
                                Int(C.unsafe_ptr()), 1)
        var hC_tc16 = ctx.enqueue_create_host_buffer[DType.float32](CM * CN)
        ctx.enqueue_copy(hC_tc16, C)
        ctx.synchronize()

        var st32 = _tc_gemm_f16(Int(A.unsafe_ptr()), Int(W16.unsafe_ptr()), CM, CK, CN,
                                Int(A16.unsafe_ptr()), Int(C16.unsafe_ptr()),
                                Int(C.unsafe_ptr()), 0)
        var hC_tc32 = ctx.enqueue_create_host_buffer[DType.float32](CM * CN)
        ctx.enqueue_copy(hC_tc32, C)
        ctx.synchronize()

        var stt = _tc_gemm_tf32(Int(A.unsafe_ptr()), Int(W.unsafe_ptr()), CM, CK, CN,
                                Int(C.unsafe_ptr()))
        var hC_tf32 = ctx.enqueue_create_host_buffer[DType.float32](CM * CN)
        ctx.enqueue_copy(hC_tf32, C)
        ctx.synchronize()

        ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
            C_v2.unsafe_ptr(), A.unsafe_ptr(), W.unsafe_ptr(),
            Int64(CM), Int64(CK), Int64(CN),
            grid_dim=_ceil_div_local(CM, _G2_BM) * _ceil_div_local(CN, _G2_BN),
            block_dim=_G2_NTHREADS)
        ctx.synchronize()
        var hC_v2 = ctx.enqueue_create_host_buffer[DType.float32](CM * CN)
        ctx.enqueue_copy(hC_v2, C_v2)
        ctx.synchronize()

        if st16 != 0 or st32 != 0 or stt != 0:
            print("tc_escape_probe: GEMM call FAILED — st16:", st16, "st32:", st32,
                  "tf32:", stt, "last_error:", _tc_last_error())
            return

        # f64 reference over the EXACT f32-rounded inputs the GPU consumed
        var a_h = _fill_lcg_host(CM * CK, FILL_MULT_A)
        var w_h = _fill_lcg_host(CN * CK, FILL_MULT_W)
        var rel16 = Float64(0.0)
        var rel32 = Float64(0.0)
        var reltf = Float64(0.0)
        var relv2 = Float64(0.0)
        for mrow in range(CM):
            for ncol in range(CN):
                var acc = Float64(0.0)
                for kk in range(CK):
                    acc += a_h[mrow * CK + kk] * w_h[ncol * CK + kk]
                var refv = acc
                var denom = Float64(1.0)
                var ar = refv
                if ar < 0.0:
                    ar = -ar
                if ar > denom:
                    denom = ar
                var d16 = Float64(hC_tc16[mrow * CN + ncol]) - refv
                if d16 < 0.0:
                    d16 = -d16
                if d16 / denom > rel16:
                    rel16 = d16 / denom
                var d32 = Float64(hC_tc32[mrow * CN + ncol]) - refv
                if d32 < 0.0:
                    d32 = -d32
                if d32 / denom > rel32:
                    rel32 = d32 / denom
                var dtf = Float64(hC_tf32[mrow * CN + ncol]) - refv
                if dtf < 0.0:
                    dtf = -dtf
                if dtf / denom > reltf:
                    reltf = dtf / denom
                var dv2 = Float64(hC_v2[mrow * CN + ncol]) - refv
                if dv2 < 0.0:
                    dv2 = -dv2
                if dv2 / denom > relv2:
                    relv2 = dv2 / denom
        print("CORRECTNESS (", CM, "x", CN, "x", CK, "vs f64 CPU reference):")
        print("  tc f16-accum  max_rel:", rel16, "|", "PASS" if rel16 <= REL_GATE else "FAIL")
        print("  tc f32-accum  max_rel:", rel32, "|", "PASS" if rel32 <= REL_GATE else "FAIL")
        print("  tf32          max_rel:", reltf, "|", "PASS" if reltf <= REL_GATE else "FAIL")
        print("  v2 f32 (ctl)  max_rel:", relv2, "|", "PASS" if relv2 <= REL_GATE else "FAIL")

        # ══ PART 1c — ANGLE 1: runtime PTX load + launch on Mojo pointers ══
        # tc_shim_rt_init dlopens libcuda.so.1, cuModuleLoadData's the EMBEDDED PTX (driver
        # JITs it to this GPU's SASS) and resolves the two kernels — zero link-time coupling.
        var rst = _tc_rt_init()
        if rst != 0:
            print("RUNTIME PTX LOAD: FAILED — status", rst, "last_error:", _tc_last_error())
        else:
            print("RUNTIME PTX LOAD: PASS — embedded PTX JIT'd + kernels resolved")
            # vadd smoke: runtime-loaded kernel on Mojo-allocated buffers, oracle = a_h + w_h
            var vst = _tc_rt_vadd(Int(A.unsafe_ptr()), Int(W.unsafe_ptr()),
                                  Int(C_v2.unsafe_ptr()), CM * CK)
            if vst != 0:
                print("  RT VADD: FAILED — status", vst, "last_error:", _tc_last_error())
            else:
                var hV = ctx.enqueue_create_host_buffer[DType.float32](CM * CK)
                ctx.enqueue_copy(hV, C_v2)
                ctx.synchronize()
                var vbad = 0
                for i in range(CM * CK):
                    var want = Float32(Float64(a_h[i]) + Float64(w_h[i]))
                    if hV[i] != want:
                        vbad += 1
                if vbad == 0:
                    print("  RT VADD on Mojo buffers:", CM * CK, "elems bit-exact — INTEROP PASS")
                else:
                    print("  RT VADD: FAIL —", vbad, "mismatches")
            # pointer-level interop evidence: CU_POINTER_ATTRIBUTE_CONTEXT of a Mojo buffer
            # vs the context CURRENT on the shim thread (tc_shim_diag above)
            var pctx = Int64(0)
            var pst = _tc_ptr_context(Int(A.unsafe_ptr()), pctx)
            print("  ptr-context of Mojo buffer A:",
                  UnsafePointer(to=pctx).bitcast[UInt64]()[unsafe_offset=0],
                  "| current ctx:", UnsafePointer(to=cptr).bitcast[UInt64]()[unsafe_offset=0],
                  "| status", pst,
                  "| SAME CONTEXT" if pctx == cptr and pst == 0 else "| (see note)")
            # ANGLE 2 correctness: the hand-written mma.sync GEMM vs the f64 oracle
            # (f16-rounded inputs, f32 accum — the same oracle the WMMA smoke uses)
            var mst = _tc_rt_mma_gemm(Int(A16.unsafe_ptr()), Int(W16.unsafe_ptr()),
                                      Int(C.unsafe_ptr()), CM, CK, CN)
            if mst != 0:
                print("  RT MMA GEMM: FAILED — status", mst, "last_error:", _tc_last_error())
            else:
                var hM = ctx.enqueue_create_host_buffer[DType.float32](CM * CN)
                ctx.enqueue_copy(hM, C)
                ctx.synchronize()
                var mrel = Float64(0.0)
                for mrow in range(CM):
                    for ncol in range(CN):
                        var acc = Float64(0.0)
                        for kk in range(CK):
                            acc += Float64(Float16(a_h[mrow * CK + kk])) *
                                   Float64(Float16(w_h[ncol * CK + kk]))
                        var refv = acc
                        var denom = Float64(1.0)
                        var ar = refv
                        if ar < 0.0:
                            ar = -ar
                        if ar > denom:
                            denom = ar
                        var dd = Float64(hM[mrow * CN + ncol]) - refv
                        if dd < 0.0:
                            dd = -dd
                        if dd / denom > mrel:
                            mrel = dd / denom
                print("  RT MMA GEMM (hand mma.sync, 64x256x128) max_rel:", mrel, "|",
                      "PASS" if mrel <= REL_GATE else "FAIL")

        # ══ PART 3 — WMMA smoke: inline tensor-core tile feasibility ══
        # A16[16,16] / B16[16,16 as n,k] are cut from the staged fills above (their first 256
        # elements ARE those fills); reference recomputes with f16-rounded inputs, f32 accum.
        var wst = _tc_wmma(Int(A16.unsafe_ptr()), Int(W16.unsafe_ptr()), Int(C.unsafe_ptr()))
        if wst != 0:
            print("WMMA SMOKE: FAILED — status", wst, "last_error:", _tc_last_error())
        else:
            var hD = ctx.enqueue_create_host_buffer[DType.float32](256)
            ctx.enqueue_copy(hD, C)
            ctx.synchronize()
            var wrel = Float64(0.0)
            for mrow in range(16):
                for ncol in range(16):
                    var acc = Float64(0.0)
                    for kk in range(16):
                        acc += Float64(Float16(a_h[mrow * 16 + kk])) *
                               Float64(Float16(w_h[ncol * 16 + kk]))
                    var refv = acc
                    var denom = Float64(1.0)
                    var ar = refv
                    if ar < 0.0:
                        ar = -ar
                    if ar > denom:
                        denom = ar
                    var dd = Float64(hD[mrow * 16 + ncol]) - refv
                    if dd < 0.0:
                        dd = -dd
                    if dd / denom > wrel:
                        wrel = dd / denom
            print("WMMA SMOKE (16x16x16 f16 tile, the Q@K^T shape): max_rel", wrel, "|",
                  "PASS — inline TC PTX feasible in-shim" if wrel <= REL_GATE else "FAIL")

        # ══ PART 4a — packed3 -> f16 dequant CORRECTNESS on a known tiny layout ══
        var DN_ROWS = 2
        var DK = 96
        var DK_PAD = 96
        var D_WORDS_PER_ROW = DK_PAD // 3
        var D_BLOCKS_PER_ROW = 3
        var n_words = DN_ROWS * D_WORDS_PER_ROW
        var n_blocks = DN_ROWS * D_BLOCKS_PER_ROW
        var hw = ctx.enqueue_create_host_buffer[DType.int32](n_words)
        var hs = ctx.enqueue_create_host_buffer[DType.float32](n_blocks)
        var hz = ctx.enqueue_create_host_buffer[DType.float32](n_blocks)
        for row in range(DN_ROWS):
            for wi in range(D_WORDS_PER_ROW):
                var word = UInt32(0)
                for lane in range(3):
                    var kk = wi * 3 + lane
                    var q = UInt32((row * 131 + kk * 7) % 256)
                    word = word | (q << UInt32(8 * lane))
                hw[row * D_WORDS_PER_ROW + wi] = UnsafePointer(to=word).bitcast[Int32]()[unsafe_offset=0]
        for b in range(n_blocks):
            hs[b] = Float32(0.01 * Float64(b + 1))
            hz[b] = Float32(128.0 - 3.0 * Float64(b))
        var dw = ctx.enqueue_create_buffer[DType.int32](n_words)
        var ds = ctx.enqueue_create_buffer[DType.float32](n_blocks)
        var dz = ctx.enqueue_create_buffer[DType.float32](n_blocks)
        var do16 = ctx.enqueue_create_buffer[DType.float16](DN_ROWS * DK_PAD)
        ctx.enqueue_copy(dw, hw)
        ctx.enqueue_copy(ds, hs)
        ctx.enqueue_copy(dz, hz)
        ctx.synchronize()
        var dqst = _tc_dequant(Int(dw.unsafe_ptr()), Int(ds.unsafe_ptr()), Int(dz.unsafe_ptr()),
                               Int(do16.unsafe_ptr()), DN_ROWS, DK, DK_PAD, D_WORDS_PER_ROW,
                               D_BLOCKS_PER_ROW)
        var hdq = ctx.enqueue_create_host_buffer[DType.float16](DN_ROWS * DK_PAD)
        ctx.enqueue_copy(hdq, do16)
        ctx.synchronize()
        if dqst != 0:
            print("DEQUANT CORRECTNESS: FAILED — status", dqst)
        else:
            var dq_bad = 0
            var dq_max = Float64(0.0)
            for row in range(DN_ROWS):
                for kk in range(DK):
                    var q = Float64((row * 131 + kk * 7) % 256)
                    var blk = row * D_BLOCKS_PER_ROW + kk // 32
                    var want = (q - Float64(hz[blk])) * Float64(hs[blk])
                    var got = Float64(hdq[row * DK_PAD + kk])
                    var dd = got - want
                    if dd < 0.0:
                        dd = -dd
                    if dd > dq_max:
                        dq_max = dd
                    if dd > 4.0e-3:
                        dq_bad += 1
            if dq_bad == 0:
                print("DEQUANT CORRECTNESS (packed3 layout, 2x96): PASS — max_abs", dq_max)
            else:
                print("DEQUANT CORRECTNESS (packed3 layout, 2x96): FAIL —", dq_bad,
                      "bad elems, max_abs", dq_max)

        # ══ PART 2 — NUMBERS: GEMM shapes, 20-run median + IQR per arm ══
        var shapes_m = [1024, 1024, 1024, 256, 256, 256]
        var shapes_k = [1024, 4096, 4096, 1024, 4096, 4096]
        var shapes_n = [4096, 1024, 3072, 4096, 1024, 3072]
        var shape_names = ["qkv", "o_proj", "down/gate", "qkv(M=256)", "o_proj(M=256)",
                           "down/gate(M=256)"]
        var arm_names = ["v2_f32_simt", "tc_full_32acc", "tc_full_16acc", "tc_pre_32acc",
                         "gemmex_only_32acc", "tf32_direct", "rt_mma_hand"]

        for si in range(6):
            var m = shapes_m[si]
            var k = shapes_k[si]
            var n = shapes_n[si]
            var flops = Float64(2) * Float64(m) * Float64(k) * Float64(n)
            print("GEMM shape", shape_names[si], "M =", m, "K =", k, "N =", n, "|",
                  flops / 1.0e9, "GFLOP")
            ctx.enqueue_function[_fill_lcg_kernel](
                A.unsafe_ptr(), FILL_MULT_A, Int64(m * k),
                grid_dim=_ceil_div_local(m * k, 256), block_dim=256)
            ctx.enqueue_function[_fill_lcg_kernel](
                W.unsafe_ptr(), FILL_MULT_W, Int64(n * k),
                grid_dim=_ceil_div_local(n * k, 256), block_dim=256)
            ctx.synchronize()
            var rs = _tc_stage_f16(Int(W.unsafe_ptr()), Int(W16.unsafe_ptr()), n * k)
            if rs != 0:
                print("  W staging FAILED:", rs)
                return
            rs = _tc_stage_f16(Int(A.unsafe_ptr()), Int(A16.unsafe_ptr()), m * k)
            if rs != 0:
                print("  A staging FAILED:", rs)
                return
            ctx.synchronize()
            for arm in range(7):
                # the hand mma arm (6) is the slow probe kernel — run it on the two qkv shapes
                # only (M=1024 and M=256), the campaign brief's named comparison points
                if arm == 6 and si != 0 and si != 3:
                    continue
                for _ in range(WARMUP):
                    _run_arm(arm, ctx, A, W, A16, W16, C16, C, m, k, n)
                var samps = List[Float64](capacity=SAMPLES)
                for _ in range(SAMPLES):
                    var t0 = perf_counter_ns()
                    _run_arm(arm, ctx, A, W, A16, W16, C16, C, m, k, n)
                    samps.append(Float64(perf_counter_ns() - t0))
                _sort_f64(samps)
                _stats_line(arm_names[arm], samps, flops)

        # ══ PART 4b — packed3 -> f16 dequant COST at session open ══
        _dequant_measure(ctx)

        print("tc_escape_probe: done")


# ── PART 4b: the one-time session-open dequant, real Qwen3-0.6B layout + 7B-scale attempt ──

struct _WFamily(Copyable, Movable):
    var name: String
    var rows: Int
    var k: Int

    def __init__(out self, name: String, rows: Int, k: Int):
        self.name = name
        self.rows = rows
        self.k = k


def _kp(k: Int) -> Int:
    """packed3 k_pad: round to a multiple of 12 elements (4-word rows), spec-faithful."""
    return _ceil_div_local(k, 12) * 12


def _family_words(rows: Int, k: Int) -> Int:
    return rows * (_kp(k) // 3)


def _family_blocks(rows: Int, k: Int) -> Int:
    return rows * _ceil_div_local(_kp(k), 32)


def _run_dequant_battery(
    mut ctx: DeviceContext, fams: List[_WFamily], tag: String,
) raises:
    """Allocate the full packed3 footprint + f16 output for a model, time the full dequant
    battery (one shim call per weight family), report GB/s + ms + VRAM delta."""
    var total_words = 0
    var total_blocks = 0
    var total_elems = 0
    var total_f16_elems = 0
    for i in range(len(fams)):
        total_words += _family_words(fams[i].rows, fams[i].k)
        total_blocks += _family_blocks(fams[i].rows, fams[i].k)
        total_elems += fams[i].rows * fams[i].k
        total_f16_elems += fams[i].rows * _kp(fams[i].k)
    var packed_bytes = Float64(total_words) * 4.0
    var meta_bytes = Float64(total_blocks) * 8.0
    var f16_bytes = Float64(total_f16_elems) * 2.0

    var words = ctx.enqueue_create_buffer[DType.float32](total_words)
    var scales = ctx.enqueue_create_buffer[DType.float32](total_blocks)
    var zeros = ctx.enqueue_create_buffer[DType.float32](total_blocks)
    var out16 = ctx.enqueue_create_buffer[DType.float16](total_f16_elems)
    ctx.enqueue_function[_fill_seq_kernel](
        words.unsafe_ptr(), Int64(total_words),
        grid_dim=_ceil_div_local(total_words, 256), block_dim=256)
    ctx.enqueue_function[_fill_lcg_kernel](
        scales.unsafe_ptr(), FILL_MULT_W, Int64(total_blocks),
        grid_dim=_ceil_div_local(total_blocks, 256), block_dim=256)
    ctx.enqueue_function[_fill_lcg_kernel](
        zeros.unsafe_ptr(), FILL_MULT_A, Int64(total_blocks),
        grid_dim=_ceil_div_local(total_blocks, 256), block_dim=256)
    ctx.synchronize()

    # one warmup battery, then SAMPLES timed batteries (each = every family dequantized once)
    for i in range(len(fams)):
        var r = _tc_dequant(Int(words.unsafe_ptr()), Int(scales.unsafe_ptr()),
                            Int(zeros.unsafe_ptr()), Int(out16.unsafe_ptr()),
                            fams[i].rows, fams[i].k, _kp(fams[i].k),
                            _kp(fams[i].k) // 3, _ceil_div_local(_kp(fams[i].k), 32))
        if r != 0:
            print("DEQUANT", tag, "FAILED on family", fams[i].name, "status", r)
            return
    var samps = List[Float64](capacity=SAMPLES)
    for _ in range(SAMPLES):
        var t0 = perf_counter_ns()
        for i in range(len(fams)):
            _ = _tc_dequant(Int(words.unsafe_ptr()), Int(scales.unsafe_ptr()),
                            Int(zeros.unsafe_ptr()), Int(out16.unsafe_ptr()),
                            fams[i].rows, fams[i].k, _kp(fams[i].k),
                            _kp(fams[i].k) // 3, _ceil_div_local(_kp(fams[i].k), 32))
        ctx.synchronize()
        samps.append(Float64(perf_counter_ns() - t0))
    _sort_f64(samps)
    var med = (samps[SAMPLES // 2 - 1] + samps[SAMPLES // 2]) / 2.0
    var traffic = packed_bytes + meta_bytes + f16_bytes
    var gbs = traffic / (med * 1.0e-9) / 1.0e9
    print("DEQUANT", tag, "| weights:", Float64(total_elems) / 1.0e9, "B params |",
          med / 1.0e6, "ms one-time |", gbs, "GB/s (r+w)")
    print("  VRAM: packed3", (packed_bytes + meta_bytes) / 1.0e9, "GB -> f16",
          f16_bytes / 1.0e9, "GB | dual-residency delta:", f16_bytes / 1.0e9, "GB")


def _dequant_measure(mut ctx: DeviceContext) raises:
    # Qwen3-0.6B (real config: hidden 1024, heads 16 / kv 8 / d_head 64, d_ff 3072, 28 layers,
    # vocab 151936, tied lm_head -> embed only). Norms are excluded (f32, negligible bytes).
    var fams06 = List[_WFamily]()
    fams06.append(_WFamily("embed", 151936, 1024))
    for layer in range(28):
        fams06.append(_WFamily("q", 1024, 1024))
        fams06.append(_WFamily("k", 512, 1024))
        fams06.append(_WFamily("v", 512, 1024))
        fams06.append(_WFamily("o", 1024, 1024))
        fams06.append(_WFamily("g", 3072, 1024))
        fams06.append(_WFamily("u", 3072, 1024))
        fams06.append(_WFamily("d", 1024, 3072))
    _run_dequant_battery(ctx, fams06, "qwen3-0.6b")

    # Qwen2.5-7B-Instruct scale (hidden 3584, heads 28 / kv 4 / d_head 128, d_ff 18944,
    # 28 layers, vocab 152064, UNTIED lm_head): ~7.6B params, ~12 GB packed3 + ~15 GB f16.
    # Attempted on both GPUs; the A100's 40 GB makes it tight, so a failure here is recorded
    # as evidence, and the 0.6B GB/s number above is the bandwidth-faithful projection.
    try:
        var fams7 = List[_WFamily]()
        fams7.append(_WFamily("embed", 152064, 3584))
        fams7.append(_WFamily("lm_head", 152064, 3584))
        for layer in range(28):
            fams7.append(_WFamily("q", 3584, 3584))
            fams7.append(_WFamily("k", 512, 3584))
            fams7.append(_WFamily("v", 512, 3584))
            fams7.append(_WFamily("o", 3584, 3584))
            fams7.append(_WFamily("g", 18944, 3584))
            fams7.append(_WFamily("u", 18944, 3584))
            fams7.append(_WFamily("d", 3584, 18944))
        _run_dequant_battery(ctx, fams7, "qwen2.5-7b")
    except e:
        print("DEQUANT qwen2.5-7b: allocation/run FAILED (recorded):", e)
        print("  -> 7B projection uses the 0.6B-measured GB/s above (bandwidth-bound kernel)")
