"""sdpa_simd_nvidia_probe.mojo — the NVIDIA correctness gate for adopting the warp-shuffle
attention twin `_sdpa_kernel_simd` on CUDA, REQUIRED before the dispatch swap: that kernel's
own docstring records a real codegen bug on Metal/1.0.0b2 (lanes 0/1 lose their `cv`
contribution — ~1% of dispatches at production shapes, 100% deterministic at the minimal
d_head=32 / n_keys=1 shape). This probe answers: does the bug exist on NVIDIA / mojo 1.0.0?

Method:
  1. MINIMAL REPRO SHAPE: d_head=32, n_keys=1 — 100% deterministic on Metal. Any output
     mismatch vs the barrier-tree kernel here = the bug is present on this target.
  2. PRODUCTION SHAPE STRESS: Qwen3-0.6B's decode attention (h_q=16, h_kv=8, d_head=128),
     n_keys in {257, 512}, 2000 dispatches each of BOTH kernels on identical pseudo-random
     inputs, outputs compared element-wise against the F32 agreement bound. Any mismatch
     beyond the bound = the bug (or a real numerics divergence — either blocks adoption).
  3. SPEED SANITY: wall time for 500 dispatches of each kernel at the production shape, so
     the adoption decision carries the measured gain, not just the hope.

Inputs are LCG pseudo-random (the residentk_cuda_smoke.mojo generator), identical for both
kernels per case. The barrier-tree `_sdpa_kernel` is the reference — it has produced the
campaign's exact oracle continuation on all three NVIDIA GPUs.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/sdpa_simd_nvidia_probe.mojo -o probe
"""

from max.gpu.host import DeviceContext
from std.math import sqrt
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.kernels import _sdpa_kernel, _sdpa_kernel_simd

comptime H_Q: Int = 16
comptime H_KV: Int = 8
comptime D_HEAD: Int = 128
comptime STRESS_REPS: Int = 2000
comptime SPEED_REPS: Int = 500


def _lcg(seed: Int) -> Float64:
    var s = (seed * 6364136223846793005 + 1442695040888963407) & 0x7FFFFFFFFFFFFFFF
    return Float64(s % 1000003) / 1000003.0


def _fill_rand(h: UnsafePointer[Float32, origin=MutUntrackedOrigin], n: Int, seed: Int, mag: Float64):
    for i in range(n):
        h[i] = Float32((_lcg(seed + i) * 2.0 - 1.0) * mag)


def _max_abs_diff(
    a: UnsafePointer[Float32, origin=MutUntrackedOrigin],
    b: UnsafePointer[Float32, origin=MutUntrackedOrigin],
    n: Int,
) -> Float64:
    var m = Float64(0)
    for i in range(n):
        var d = Float64(a[i] - b[i])
        if d < 0.0:
            d = -d
        if d > m:
            m = d
    return m


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("sdpa_simd_nvidia_probe: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("sdpa_simd_nvidia_probe: no accelerator on this host")
            return

        var ctx = DeviceContext()
        print("sdpa_simd_nvidia_probe: device:", ctx.name())

        # ═══ CASE 1: the minimal repro shape — d_head=32, n_keys=1 (100% on Metal) ═══
        var dh1 = 32
        var nk1 = 1
        var h_q1 = 4
        var h_kv1 = 2
        var n_out1 = h_q1 * dh1
        var q_rot1 = ctx.enqueue_create_buffer[DType.float32](n_out1)
        var ck1 = ctx.enqueue_create_buffer[DType.float32](nk1 * h_kv1 * dh1)
        var cv1 = ctx.enqueue_create_buffer[DType.float32](nk1 * h_kv1 * dh1)
        var out_tree1 = ctx.enqueue_create_buffer[DType.float32](n_out1)
        var out_simd1 = ctx.enqueue_create_buffer[DType.float32](n_out1)
        var hq1 = ctx.enqueue_create_host_buffer[DType.float32](n_out1)
        var hck1 = ctx.enqueue_create_host_buffer[DType.float32](nk1 * h_kv1 * dh1)
        var hcv1 = ctx.enqueue_create_host_buffer[DType.float32](nk1 * h_kv1 * dh1)
        var ho_tree1 = ctx.enqueue_create_host_buffer[DType.float32](n_out1)
        var ho_simd1 = ctx.enqueue_create_host_buffer[DType.float32](n_out1)

        _fill_rand(hq1.unsafe_ptr(), n_out1, 11, 1.0)
        _fill_rand(hck1.unsafe_ptr(), nk1 * h_kv1 * dh1, 22, 1.0)
        _fill_rand(hcv1.unsafe_ptr(), nk1 * h_kv1 * dh1, 33, 1.0)
        ctx.enqueue_copy(q_rot1, hq1)
        ctx.enqueue_copy(ck1, hck1)
        ctx.enqueue_copy(cv1, hcv1)

        # repeat the minimal dispatch many times: the Metal bug was deterministic per-dispatch
        var mismatches1 = 0
        for rep in range(100):
            ctx.enqueue_function[_sdpa_kernel](
                out_tree1.unsafe_ptr(), q_rot1.unsafe_ptr(), ck1.unsafe_ptr(), cv1.unsafe_ptr(),
                Int64(nk1), Int64(h_q1), Int64(h_kv1), Int64(dh1), Float32(0.1767766952966369),
                grid_dim=h_q1, block_dim=dh1)
            ctx.enqueue_function[_sdpa_kernel_simd](
                out_simd1.unsafe_ptr(), q_rot1.unsafe_ptr(), ck1.unsafe_ptr(), cv1.unsafe_ptr(),
                Int64(nk1), Int64(h_q1), Int64(h_kv1), Int64(dh1), Float32(0.1767766952966369),
                grid_dim=h_q1, block_dim=dh1)
            ctx.synchronize()
            ctx.enqueue_copy(ho_tree1, out_tree1)
            ctx.enqueue_copy(ho_simd1, out_simd1)
            ctx.synchronize()
            var d = _max_abs_diff(ho_tree1.unsafe_ptr(), ho_simd1.unsafe_ptr(), n_out1)
            if d > 1.0e-5:
                mismatches1 += 1
        print("CASE1 minimal repro (d_head=32, n_keys=1) x100: mismatches =", mismatches1,
              "->", "FAIL (bug present on NVIDIA)" if mismatches1 > 0 else "PASS")

        # ═══ CASE 2: production shape stress — d_head=128, n_keys in {257, 512} ═══
        var n_out = H_Q * D_HEAD
        var scale = Float32(1.0 / sqrt(Float64(D_HEAD)))
        var q_rot = ctx.enqueue_create_buffer[DType.float32](n_out)
        var ck = ctx.enqueue_create_buffer[DType.float32](1024 * H_KV * D_HEAD)
        var cv = ctx.enqueue_create_buffer[DType.float32](1024 * H_KV * D_HEAD)
        var out_tree = ctx.enqueue_create_buffer[DType.float32](n_out)
        var out_simd = ctx.enqueue_create_buffer[DType.float32](n_out)
        var hq = ctx.enqueue_create_host_buffer[DType.float32](n_out)
        var hck = ctx.enqueue_create_host_buffer[DType.float32](1024 * H_KV * D_HEAD)
        var hcv = ctx.enqueue_create_host_buffer[DType.float32](1024 * H_KV * D_HEAD)
        var ho_tree = ctx.enqueue_create_host_buffer[DType.float32](n_out)
        var ho_simd = ctx.enqueue_create_host_buffer[DType.float32](n_out)

        _fill_rand(hq.unsafe_ptr(), n_out, 111, 1.0)
        _fill_rand(hck.unsafe_ptr(), 1024 * H_KV * D_HEAD, 222, 1.0)
        _fill_rand(hcv.unsafe_ptr(), 1024 * H_KV * D_HEAD, 333, 1.0)
        ctx.enqueue_copy(q_rot, hq)
        ctx.enqueue_copy(ck, hck)
        ctx.enqueue_copy(cv, hcv)
        ctx.synchronize()

        for case_i in range(2):
            var nk = 257 if case_i == 0 else 512
            var worst = Float64(0)
            var mismatches = 0
            for rep in range(STRESS_REPS):
                ctx.enqueue_function[_sdpa_kernel](
                    out_tree.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
                    Int64(nk), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale,
                    grid_dim=H_Q, block_dim=D_HEAD)
                ctx.enqueue_function[_sdpa_kernel_simd](
                    out_simd.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
                    Int64(nk), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale,
                    grid_dim=H_Q, block_dim=D_HEAD)
                ctx.synchronize()
                ctx.enqueue_copy(ho_tree, out_tree)
                ctx.enqueue_copy(ho_simd, out_simd)
                ctx.synchronize()
                var d = _max_abs_diff(ho_tree.unsafe_ptr(), ho_simd.unsafe_ptr(), n_out)
                if d > worst:
                    worst = d
                # F32 agreement bound family for n_keys-wide accumulation
                var bound = Float64(1.19e-7) * Float64(nk) * 8.0
                if d > bound:
                    mismatches += 1
            print("CASE2 production stress (n_keys=", nk, ") x", STRESS_REPS,
                  ": worst_abs_diff =", worst, "mismatches =", mismatches,
                  "->", "FAIL (bug present on NVIDIA)" if mismatches > 0 else "PASS")

            # ═══ CASE 3: speed sanity — 500 dispatches each ═══
            var t0 = perf_counter_ns()
            for rep in range(SPEED_REPS):
                ctx.enqueue_function[_sdpa_kernel](
                    out_tree.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
                    Int64(nk), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale,
                    grid_dim=H_Q, block_dim=D_HEAD)
            ctx.synchronize()
            var tree_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(SPEED_REPS)
            t0 = perf_counter_ns()
            for rep in range(SPEED_REPS):
                ctx.enqueue_function[_sdpa_kernel_simd](
                    out_simd.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
                    Int64(nk), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale,
                    grid_dim=H_Q, block_dim=D_HEAD)
            ctx.synchronize()
            var simd_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(SPEED_REPS)
            print("CASE3 speed (n_keys=", nk, "): barrier-tree =", tree_us,
                  "us/dispatch | warp-shuffle =", simd_us, "us/dispatch | speedup =",
                  tree_us / simd_us, "x")

        print("sdpa_simd_nvidia_probe: done")
