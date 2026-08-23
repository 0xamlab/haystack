"""
amd_rocm_compile_gate — the AMD ROCm COMPILE gate for algenta's PORTABLE GPU kernel layer.

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, uint8-packed
backend: rocm
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo
benchmark: none
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

WHAT THIS GATES
---------------
The SAME portable kernel layer the CUDA lane compile-gates (`-D ALGENTA_GPU -D ALGENTA_CUDA
--target-accelerator sm_*`, build-runtime.yml's build-linux-cuda job), cross-compiled for AMD
CDNA targets instead:

    mojo build -D ALGENTA_GPU -D ALGENTA_ROCM --target-accelerator gfx942 \
        -I mojo/engine benchmarks/llm_smoke/amd_rocm_compile_gate.mojo \
        -o /tmp/amd_rocm_compile_gate_gfx942
(same with `gfx950` for the MI355X lane)

Instantiated families (every enqueue_function below forces the kernel through codegen —
an unreachable kernel would compile vacuously and prove nothing, packed_int8_phase0.sh's rule):

| family | module | kernels |
|---|---|---|
| f32 decode GEMV baseline | residentk.kernels | `_gemv_accum_kernel` |
| packed3 GEMV arm | residentk.kernels_packed3 | `_packed3_gemv_kernel{,_v2,_v3}`, `_norm_gemv_kernel_p3{,_v2,_v3}` |
| decode flash attention | residentk.kernels_decode_attn_flash | `_splitk_partial_batched_flash_kernel` |
| prefill flash attention | residentk.kernels_prefill_attn_flash | `_pf_attn_flash_kernel` |
| prefill v2 GEMM | residentk.kernels_prefill_f32_v2 | `_pf_gemm_{assign,accum,swiglu}_kernel_v2` |

The resident SESSION (`session_cuda*.mojo`) is deliberately OUT of scope: it is the
CUDA-specific layer. This gate covers the portable kernels only — exactly the surface the
two-tier define scheme (`ALGENTA_GPU` portable + backend selector) was built to carry.

HONESTY LINE — compile-verified, launch-UNVERIFIED
---------------------------------------------------
Mirrors the CUDA lane's status: the pinned Mojo 1.0.0 / MAX 26.5.0 toolchain ships the
AMDGPU LLVM backend + the ROCm/HIP accelerator table (`mojo build
--print-supported-accelerators` lists gfx90a/gfx942/gfx950/RDNA2-4), so these targets need
NO ROCm toolkit and NO AMD GPU to compile — same way NVPTX ships for the CUDA gate.
Launching the result needs real MI300X/MI355X hardware with ROCm >= 6.3.3 (MI355X: ROCm 7),
which the fleet does not have. PART 0 (host pack/unpack round-trip) is target-independent
and runs anywhere; the device section only executes on a host with a usable accelerator.

WAVEFRONT NOTE (for the future launch-verification stage)
---------------------------------------------------------
These kernels were written against the NVIDIA warp: `_LANES = 32` geometry and
`std.gpu.primitives.warp.sum` reductions. On CDNA the wavefront is 64, so a launch stage
must re-verify the reduction geometry before any correctness claim — the COMPILE gate
deliberately makes none. The full per-kernel audit (7 portable / 5 wave64-locked, exact
failure mechanics, fix sketch) is `benchmarks/llm_smoke/amd_launch_readiness.md`; PART 0.5
below prints the target-resolved `std.gpu.WARP_SIZE` advisory on every run.

Build (macOS build host or a linux runner; AMDGPU backend ships in the toolchain):
    mojo build -D ALGENTA_GPU -D ALGENTA_ROCM --target-accelerator gfx942 \
        -I mojo/engine benchmarks/llm_smoke/amd_rocm_compile_gate.mojo -o gate_gfx942
    mojo build -D ALGENTA_GPU -D ALGENTA_ROCM --target-accelerator gfx950 \
        -I mojo/engine benchmarks/llm_smoke/amd_rocm_compile_gate.mojo -o gate_gfx950
"""

from max.gpu.host import DeviceContext
from std.gpu import WARP_SIZE
from std.memory import bitcast
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from residentk.kernels import _TG, _gemv_accum_kernel
from residentk.kernels_packed3 import (
    _packed3_gemv_kernel,
    _packed3_gemv_kernel_v2,
    _packed3_gemv_kernel_v3,
    _norm_gemv_kernel_p3,
    _norm_gemv_kernel_p3_v2,
    _norm_gemv_kernel_p3_v3,
    _pack_f32_to_packed3, _p3_dequant_host,
    _p3_k_pack, _p3_words_per_row, _p3_blocks_per_row,
    _p3_pack_word, _p3_unpack_word,
)
from residentk.kernels_decode_attn_flash import _splitk_partial_batched_flash_kernel
from residentk.kernels_prefill_attn_flash import _pf_attn_flash_kernel
from residentk.kernels_prefill_f32_v2 import (
    _pf_gemm_assign_kernel_v2,
    _pf_gemm_accum_kernel_v2,
    _pf_gemm_swiglu_kernel_v2,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

# ── gate shapes (runtime-only; compile gate never launches them) ───────────────
comptime GEMV_K: Int = 1024
comptime GEMV_N: Int = 1024
comptime FLASH_B: Int = 2
comptime FLASH_HQ: Int = 8
comptime FLASH_HKV: Int = 2
comptime FLASH_DHEAD: Int = 128
comptime FLASH_KEYS: Int = 512
comptime FLASH_SPLITS: Int = 4
comptime PF_M: Int = 64
comptime G2_K: Int = 1024
comptime G2_N: Int = 1024
comptime G2_NFF: Int = 1024


def _lehmer_next(state: Int64) -> Int64:
    """Park-Miller LCG — verbatim from packed3_gemv_probe.mojo."""
    return (state * 48271) % 2147483647


def _lehmer_f32(state: Int64) -> Float32:
    return Float32(Float64(state) * (2.0 / 2147483647.0) - 1.0)


def _check_byte_triple(b0: UInt8, b1: UInt8, b2: UInt8) -> Bool:
    """One pack/unpack round-trip through BOTH views — verbatim from the CUDA probe."""
    var v = _p3_pack_word(b0, b1, b2)
    var view = bitcast[DType.uint8, 4](SIMD[DType.float32, 1](v))
    if view[0] != b0 or view[1] != b1 or view[2] != b2 or view[3] != UInt8(0):
        return False
    var (u0, u1, u2) = _p3_unpack_word(v)
    return u0 == b0 and u1 == b1 and u2 == b2


def _host_roundtrip_checks() raises -> Bool:
    """PART 0 — target-independent: the packed3 pack/unpack math. Runs on the build host
    (any OS, any accelerator tier) before any device time would be spent."""
    var ok = True
    var n_checked = 0
    var n_fail = 0
    for i in range(256):
        n_checked += 3
        if not _check_byte_triple(UInt8(i), UInt8(255 - i), UInt8((i * 7) % 256)):
            n_fail += 1
        if not _check_byte_triple(UInt8(255 - i), UInt8((i * 7) % 256), UInt8(i)):
            n_fail += 1
        if not _check_byte_triple(UInt8((i * 7) % 256), UInt8(i), UInt8(255 - i)):
            n_fail += 1
    var st = Int64(987654321)
    for _ in range(20000):
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

    # quantization round-trip at k=1000 (both tails exercised — the probe's shape)
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
    var err_fail = 0
    for r in range(n):
        for e in range(k):
            var bound = p.scales[r * nblocks + (e >> 5)] * Float32(0.5)
            var err = deq[r * k_pack + e] - w[r * k + e]
            if err < Float32(0.0):
                err = -err
            if err > bound * Float32(1.001) + Float32(1.0e-7):
                err_fail += 1
    if err_fail > 0:
        ok = False
    print("  quantization round-trip:", err_fail, "elements above bound ->",
          "PASS" if err_fail == 0 else "FAIL")
    return ok


def _instantiate_kernels(ref ctx: DeviceContext) raises:
    """PART 1 — one enqueue per gated kernel. The enqueues are what force each kernel
    through the TARGET codegen (the compile gate's whole point); on a host without AMD
    hardware this path is never executed — the gate is decided at `mojo build` time."""

    # ── packed3 GEMV arm (k=1024, n=1024) ──
    var k = GEMV_K
    var n = GEMV_N
    var k_pack = _p3_k_pack(k)
    var words_per_row = _p3_words_per_row(k)
    var nblocks = _p3_blocks_per_row(k)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var x_buf = ctx.enqueue_create_buffer[DType.float32](k_pack)
    var wp_buf = ctx.enqueue_create_buffer[DType.float32](n * words_per_row)
    var sc_buf = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
    var z_buf = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
    var gamma_buf = ctx.enqueue_create_buffer[DType.float32](k_pack)
    var wf32_buf = ctx.enqueue_create_buffer[DType.float32](n * k)

    ctx.enqueue_function[_packed3_gemv_kernel](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), wp_buf.unsafe_ptr(),
        sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(), Int64(k), Int64(n),
        grid_dim=n, block_dim=_TG)
    ctx.enqueue_function[_packed3_gemv_kernel_v2](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), wp_buf.unsafe_ptr(),
        sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(), Int64(k), Int64(n),
        grid_dim=n, block_dim=_TG)
    ctx.enqueue_function[_packed3_gemv_kernel_v3](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), wp_buf.unsafe_ptr(),
        sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(), Int64(k), Int64(n),
        grid_dim=n, block_dim=_TG)
    ctx.enqueue_function[_norm_gemv_kernel_p3](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
        wp_buf.unsafe_ptr(), sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(),
        Int64(k), Int64(n), Float32(1.0e-6),
        grid_dim=(n + 7) // 8, block_dim=_TG)
    ctx.enqueue_function[_norm_gemv_kernel_p3_v2](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
        wp_buf.unsafe_ptr(), sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(),
        Int64(k), Int64(n), Float32(1.0e-6),
        grid_dim=(n + 7) // 8, block_dim=_TG)
    ctx.enqueue_function[_norm_gemv_kernel_p3_v3](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
        wp_buf.unsafe_ptr(), sc_buf.unsafe_ptr(), z_buf.unsafe_ptr(),
        Int64(k), Int64(n), Float32(1.0e-6),
        grid_dim=(n + 7) // 8, block_dim=_TG)
    # f32 decode baseline
    ctx.enqueue_function[_gemv_accum_kernel](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), wf32_buf.unsafe_ptr(),
        Int64(k), Int64(n),
        grid_dim=(n + 7) // 8, block_dim=_TG)

    # ── decode flash attention (B=2, h_q=8, h_kv=2, d_head=128, splits=4) ──
    var b = FLASH_B
    var h_q = FLASH_HQ
    var h_kv = FLASH_HKV
    var d_head = FLASH_DHEAD
    var nkeys = FLASH_KEYS
    var n_splits = FLASH_SPLITS
    var per_seq = h_q * n_splits
    var units = b * per_seq
    var m_buf = ctx.enqueue_create_buffer[DType.float32](units)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](units)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](units * d_head)
    var q_buf = ctx.enqueue_create_buffer[DType.float32](b * h_q * d_head)
    var ck_buf = ctx.enqueue_create_buffer[DType.float32](b * nkeys * d_head)
    var cv_buf = ctx.enqueue_create_buffer[DType.float32](b * nkeys * d_head)
    var nk_buf = ctx.enqueue_create_buffer[DType.int64](b)
    ctx.enqueue_function[_splitk_partial_batched_flash_kernel](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        nk_buf.unsafe_ptr(), Int64(b), Int64(nkeys * d_head),
        Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
        Float32(0.08838834764831845),
        grid_dim=(units + 7) // 8, block_dim=256)

    # ── prefill flash attention (m=64 rows, h_q=8, h_kv=2, d_head=128) ──
    var m_rows = PF_M
    var attn_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * h_q * d_head)
    var pq_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * h_q * d_head)
    var pck_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * h_kv * d_head)
    var pcv_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * h_kv * d_head)
    ctx.enqueue_function[_pf_attn_flash_kernel](
        attn_buf.unsafe_ptr(), pq_buf.unsafe_ptr(), pck_buf.unsafe_ptr(),
        pcv_buf.unsafe_ptr(), Int64(0), Int64(h_q), Int64(h_kv), Int64(d_head),
        Float32(0.08838834764831845), Int64(m_rows),
        grid_dim=((m_rows + 31) // 32) * h_q, block_dim=256)

    # ── prefill v2 GEMM family (m=64, k=1024, n=1024; n_ff=1024) ──
    var m = PF_M
    var gk = G2_K
    var gn = G2_N
    var n_ff = G2_NFF
    var gy_buf = ctx.enqueue_create_buffer[DType.float32](m * gn)
    var gxn_buf = ctx.enqueue_create_buffer[DType.float32](m * gk)
    var gw_buf = ctx.enqueue_create_buffer[DType.float32](gn * gk)
    var gact_buf = ctx.enqueue_create_buffer[DType.float32](m * n_ff)
    var gw_ff_buf = ctx.enqueue_create_buffer[DType.float32](2 * n_ff * gk)
    ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
        gy_buf.unsafe_ptr(), gxn_buf.unsafe_ptr(), gw_buf.unsafe_ptr(),
        Int64(m), Int64(gk), Int64(gn),
        grid_dim=((m + 63) // 64) * ((gn + 63) // 64), block_dim=256)
    ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
        gy_buf.unsafe_ptr(), gxn_buf.unsafe_ptr(), gw_buf.unsafe_ptr(),
        Int64(m), Int64(gk), Int64(gn),
        grid_dim=((m + 63) // 64) * ((gn + 63) // 64), block_dim=256)
    ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
        gact_buf.unsafe_ptr(), gxn_buf.unsafe_ptr(), gw_ff_buf.unsafe_ptr(),
        Int64(m), Int64(gk), Int64(n_ff),
        grid_dim=((m + 63) // 64) * ((n_ff + 63) // 64), block_dim=256)
    ctx.synchronize()


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_ROCM"]()):
        print("amd_rocm_compile_gate: needs -D ALGENTA_GPU -D ALGENTA_ROCM")
        return
    else:
        print("PART 0 — host pack round-trip (target-independent)")
        if not _host_roundtrip_checks():
            print("amd_rocm_compile_gate: host round-trip FAILED")
            exit(1)

        # PART 0.5 — WAVEFRONT GEOMETRY ADVISORY (audit 2026-08-23). `std.gpu.WARP_SIZE`
        # resolves AT COMPILE TIME per target accelerator (32 NVIDIA / 32 RDNA / 64 CDNA),
        # so a gfx build prints the 64-lane caveat below and an sm build would print 32.
        # Advisory only — the gate's verdict stays "compiles for this target"; the
        # correctness caveat for the 5 wave64-locked kernels is the launch stage's job
        # (benchmarks/llm_smoke/amd_launch_readiness.md §1, full per-kernel mechanics).
        print("PART 0.5 — wavefront geometry advisory (WARP_SIZE target-resolved at compile time)")
        print("  std.gpu.WARP_SIZE on this build target =", WARP_SIZE)
        @parameter
        if WARP_SIZE == 64:
            print("  CDNA wavefront = 64 lanes; 5 of the 12 gated kernels assume 32-lane warps:")
            print("    _packed3_gemv_kernel{,_v2,_v3} — warp.sum spans two 32-lane groups (silent 2x)")
            print("    _splitk_partial_batched_flash_kernel — warp_id()/lane*4 maps (silent corruption)")
            print("    _pf_attn_flash_kernel — warp_id()/lane*4 maps (silent corruption)")
            print("  see benchmarks/llm_smoke/amd_launch_readiness.md before ANY launch")

        if not has_accelerator():
            print("amd_rocm_compile_gate: no accelerator on this host",
                  "(host checks passed; gate verdict is decided at compile time)")
            return

        var ctx = DeviceContext()
        print("amd_rocm_compile_gate: device:", ctx.name())
        print("PART 1 — kernel instantiation (launch-UNVERIFIED on AMD: needs MI300X/",
              "MI355X + ROCm >= 6.3.3)")
        _instantiate_kernels(ctx)
        print("amd_rocm_compile_gate: done")
