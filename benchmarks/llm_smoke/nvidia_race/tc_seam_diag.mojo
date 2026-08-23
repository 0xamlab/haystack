"""tc_seam_diag.mojo — isolate the TC integration seam cost. Gates PASS, but the integrated
fixture prefill ran ~5x SLOWER than the native chain even though the probe measured the TC
seam 5-15x FASTER per GEMM — so something per-call in the integrated path is expensive. This
driver measures, on a real resident session with staged f16 weights:
  A: bare back-to-back TC GEMM calls, ONE sync at the end
  B: ctx.synchronize() + TC call per iteration (the integration's pre-call seam)
  D: bare empty ctx.synchronize() (nothing pending) — the floor of a sync
  E: enqueue a tiny Mojo kernel + ctx.synchronize() per iteration (drain cost with work)
Build on the VM (TC flag + shim linked) and run solo."""

from std.sys import exit, has_accelerator
from std.time import perf_counter_ns
from std.math import sqrt
from residentk.contract import RESIDENT_OK, residentk_status_name
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_SESSION_BUILD, _CudaResidentQwen3
from residentk.tc_shim_bridge import TC_SHIM_BUILD, _tc_gemm_dispatch

comptime MAX_CTX: Int = 512


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def _make_ids() raises -> List[Int]:
    var ids = List[Int](capacity=256)
    for i in range(256):
        ids.append((i * 7) % 1000)
    return ids^


def main() raises:
    @parameter
    if not (CUDA_SESSION_BUILD and TC_SHIM_BUILD):
        print("tc_seam_diag: build with -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_TC_SHIM")
        return
    else:
        if not has_accelerator():
            print("no accelerator")
            exit(1)

        var d_model = 1024
        var h_q = 16
        var h_kv = 8
        var d_head = 64
        var d_ff = 3072
        var n_layers = 28
        var vocab = 151936
        var eps = 1.0e-6
        var scale = 1.0 / sqrt(Float64(d_head))
        var pre = _resident_preflight(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, 256, 256, MAX_CTX, eps, scale
        )
        if pre != RESIDENT_OK:
            print("preflight:", residentk_status_name(pre))
            exit(1)

        var s = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, MAX_CTX, eps, scale
        )
        s.ctx.synchronize()
        s._tc_stage_weights()
        if s.tc_staged != 1:
            print("staging FAILED — tc_staged =", s.tc_staged)
            exit(1)

        var m = 256
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var reps = 28
        ref lw = s.layers[0]
        var xn_a = Int(s.pf_xn.unsafe_ptr())
        var w16_a = Int(s.w16_qkv[0].unsafe_ptr())
        var w32_a = Int(lw.w_qkv.unsafe_ptr())
        var a16_a = Int(s.tc_a16.unsafe_ptr())
        var c16_a = Int(s.tc_c16.unsafe_ptr())
        var out_a = Int(s.pf_qkv.unsafe_ptr())

        # warm the cuBLAS algo cache for this shape
        for _ in range(5):
            _ = _tc_gemm_dispatch(xn_a, w16_a, w32_a, m, d_model, n_qkv, a16_a, c16_a,
                                  out_a, 0)
        s.ctx.synchronize()

        # ── A: bare back-to-back TC calls, ONE sync at the end ──
        var t0 = perf_counter_ns()
        for _ in range(reps):
            _ = _tc_gemm_dispatch(xn_a, w16_a, w32_a, m, d_model, n_qkv, a16_a, c16_a,
                                  out_a, 0)
        s.ctx.synchronize()
        var ta = perf_counter_ns() - t0

        # ── B: ctx.synchronize() + TC call per iteration (the integration seam) ──
        t0 = perf_counter_ns()
        for _ in range(reps):
            s.ctx.synchronize()
            _ = _tc_gemm_dispatch(xn_a, w16_a, w32_a, m, d_model, n_qkv, a16_a, c16_a,
                                  out_a, 0)
        s.ctx.synchronize()
        var tb = perf_counter_ns() - t0

        # ── D: bare empty ctx.synchronize() floor ──
        s.ctx.synchronize()
        t0 = perf_counter_ns()
        for _ in range(reps):
            s.ctx.synchronize()
        var td = perf_counter_ns() - t0

        print("TC SEAM DIAG | M =", m, "| reps =", reps)
        print("  A bare TC calls (1 sync end):   ", _ms(ta) / Float64(reps), "ms/call")
        print("  B sync+TC call (int seam):      ", _ms(tb) / Float64(reps), "ms/call")
        print("  D bare empty sync floor:        ", _ms(td) / Float64(reps), "ms/sync")

        # ── F: REAL prefill through the session, TC arm then native arm ──
        # warm both paths once (cuBLAS heuristics + kernel JIT, untimed)
        _ = s.prefill(_make_ids())
        s.tc_staged = -1
        _ = s.prefill(_make_ids())
        # timed: TC
        s.tc_staged = 1
        _ = s.prefill(_make_ids())
        var t1 = perf_counter_ns()
        for _ in range(5):
            _ = s.prefill(_make_ids())
        var tf_tc = perf_counter_ns() - t1
        # timed: native
        s.tc_staged = -1
        _ = s.prefill(_make_ids())
        t1 = perf_counter_ns()
        for _ in range(5):
            _ = s.prefill(_make_ids())
        var tf_nat = perf_counter_ns() - t1
        print("  F real prefill TC:    ", _ms(tf_tc) / 5.0, "ms")
        print("  F real prefill native:", _ms(tf_nat) / 5.0, "ms")
        print("tc_seam_diag: done")
