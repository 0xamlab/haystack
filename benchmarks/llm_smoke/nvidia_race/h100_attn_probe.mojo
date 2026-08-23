"""h100_attn_probe.mojo — flash1 vs flash2 prefill-attention A/B at the rag serve admission
shapes (Qwen3-0.6B: h_q 16, h_kv 8, d_head 128): pass windows m=1152 at pos_base
0/1152/2304/3456 (a 4096-token prompt's four _PF_PASS_MAX passes) plus the fixture shape
(m=256, pos_base=0). Gate: max-abs diff flash2-vs-flash1 on identical buffers (same math
order — expect bit-exact or ulps), then timing as REPS back-to-back enqueues + one sync.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_90 \
        -I mojo/engine -I attention_forge \
        benchmarks/llm_smoke/nvidia_race/h100_attn_probe.mojo -o h100_attn_probe
"""

from max.gpu.host import DeviceBuffer, DeviceContext
from std.gpu import block_idx, thread_idx
from std.sys import has_accelerator
from std.time import perf_counter_ns
from std.origin import MutAnyOrigin
from residentk.session import _ceil_div
from residentk.kernels_prefill_attn_flash import (
    _PF_FLASH_NTHREADS,
    _PF_FLASH_ROWS_PER_BLOCK,
    _pf_attn_flash_kernel,
)
from residentk.kernels_prefill_attn_flash2 import (
    _pf_attn_flash2_kernel,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime H_Q: Int = 16
comptime H_KV: Int = 8
comptime D_HEAD: Int = 128
comptime REPS: Int = 30
comptime DIFF_GATE: Float64 = 1.0e-5


def _attn_fill_kernel(buf: _FP, seed_i64: Int64, n_i64: Int64):
    # deterministic bounded pseudo-random fill (LCG over the index), values in [-0.5, 0.5)
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    if i < Int(n_i64):
        var x = UInt64(i) * UInt64(6364136223846793005) + UInt64(seed_i64)
        x = x ^ (x >> UInt64(33))
        x = x * UInt64(0xff51afd7ed558ccd)
        x = x ^ (x >> UInt64(33))
        var u = Float32(Float64(Int64(x & UInt64(0xFFFFFF))) / Float64(16777216.0))
        buf[i] = u - Float32(0.5)


def _fill(mut buf: DeviceBuffer[DType.float32], n: Int, seed: Int, mut ctx: DeviceContext) raises:
    ctx.enqueue_function[_attn_fill_kernel](
        buf.unsafe_ptr(), Int64(seed), Int64(n),
        grid_dim=_ceil_div(n, 256), block_dim=256)
    ctx.synchronize()


def _max_abs_diff(
    mut a: DeviceBuffer[DType.float32], mut b: DeviceBuffer[DType.float32], n: Int
) raises -> Float64:
    var md = Float64(0.0)
    with a.map_to_host() as ha:
        with b.map_to_host() as hb:
            for i in range(n):
                var d = Float64(ha[i]) - Float64(hb[i])
                if d < 0.0:
                    d = -d
                if d > md:
                    md = d
    return md


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    var n_q = H_Q * D_HEAD
    var m_max = 1152
    var kv_rows_max = 4096

    var q_rot = ctx.enqueue_create_buffer[DType.float32](m_max * n_q)
    var ck = ctx.enqueue_create_buffer[DType.float32](kv_rows_max * H_KV * D_HEAD)
    var cv = ctx.enqueue_create_buffer[DType.float32](kv_rows_max * H_KV * D_HEAD)
    var out1 = ctx.enqueue_create_buffer[DType.float32](m_max * n_q)
    var out2 = ctx.enqueue_create_buffer[DType.float32](m_max * n_q)
    ctx.synchronize()

    _fill(q_rot, m_max * n_q, 17, ctx)
    _fill(ck, kv_rows_max * H_KV * D_HEAD, 29, ctx)
    _fill(cv, kv_rows_max * H_KV * D_HEAD, 43, ctx)

    var scale = Float32(0.08838834764831845)  # 1/sqrt(128)

    print("h100_attn_probe: flash1 vs flash2 | REPS =", REPS)
    var shapes = [(256, 0), (1152, 0), (1152, 1152), (1152, 2304), (640, 3456)]
    for s in range(5):
        var m = shapes[s][0]
        var pos_base = shapes[s][1]

        ctx.enqueue_function[_pf_attn_flash_kernel](
            out1.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
            Int64(pos_base), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale, Int64(m),
            grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK) * H_Q,
            block_dim=_PF_FLASH_NTHREADS)
        ctx.enqueue_function[_pf_attn_flash2_kernel](
            out2.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
            Int64(pos_base), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale, Int64(m),
            grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK) * H_Q,
            block_dim=_PF_FLASH_NTHREADS)
        ctx.synchronize()
        var md = _max_abs_diff(out1, out2, m * n_q)
        print("m =", m, "pos_base =", pos_base, "| flash2-vs-flash1 max_abs_diff =", md,
              "|", "PASS" if md <= DIFF_GATE else "FAIL")

        var t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_pf_attn_flash_kernel](
                out1.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
                Int64(pos_base), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale, Int64(m),
                grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK) * H_Q,
                block_dim=_PF_FLASH_NTHREADS)
        ctx.synchronize()
        var t1_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_pf_attn_flash2_kernel](
                out2.unsafe_ptr(), q_rot.unsafe_ptr(), ck.unsafe_ptr(), cv.unsafe_ptr(),
                Int64(pos_base), Int64(H_Q), Int64(H_KV), Int64(D_HEAD), scale, Int64(m),
                grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK) * H_Q,
                block_dim=_PF_FLASH_NTHREADS)
        ctx.synchronize()
        var t2_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
        print("  flash1:", t1_us, "us | flash2:", t2_us, "us | speedup", t1_us / t2_us)
    print("h100_attn_probe: done")


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6
