"""prefill_gemm_probe.mojo — the prefill GEMM variant gate: first-generation tiled GEMMs
(`residentk.kernels_prefill_f32`) vs the second-generation register-blocked / double-buffered /
float4 family (`residentk.kernels_prefill_f32_v2`), at the campaign session's real Qwen3-0.6B
shapes on the real resident weights.

Two gates, in order:
  1. CORRECTNESS: per role, both generations write into separate device buffers from the SAME
     inputs; the probe reads both back and reports the worst element-wise difference. v2 must
     agree with the first generation (which is itself the oracle-verified session's kernels) to
     fp32-FMA-contraction noise (< 1e-4 relative) BEFORE any timing counts. Ragged-M rows
     (m = 17 and m = 127 — the "any token amount" contract) are checked for the assign role.
  2. PERFORMANCE: each kernel is dispatched REPS times back-to-back with ONE synchronize after
     the loop — the device-bound window the kernel_sweep_cuda entry uses — and reported as
     us/dispatch, GFLOP/s, and % of the A100's 19.5 TFLOP/s FP32 SIMT peak.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/prefill_gemm_probe.mojo -o probe
"""

from max.gpu.host import DeviceBuffer, DeviceContext
from std.math import sqrt
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_OK, residentk_status_name
from residentk.session import _resident_preflight, _ceil_div, _LM_BLOCKS
from residentk.session_cuda import CUDA_SESSION_BUILD, _CudaResidentQwen3
from residentk.kernels import (
    _TG, _SUBS,
    _embed_row_kernel, _norm_gemv_kernel, _gemv_accum_kernel,
    _norm_gemv2_swiglu_kernel, _qk_rope_write_kernel, _sdpa_kernel,
    _lmhead_argmax_kernel, _argmax_reduce_kernel,
    _pf_rmsnorm_rows_kernel, _pf_ropewrt_kernel, _pf_attn_tiled_kernel_simd,
)
from residentk.kernels_prefill_f32 import (
    _GEMM_BM, _GEMM_BN, _GEMM_NTHREADS,
    _pf_gemm_assign_kernel, _pf_gemm_accum_kernel, _pf_gemm_swiglu_kernel,
)
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM, _G2_BN, _G2_NTHREADS,
    _pf_gemm_assign_kernel_v2, _pf_gemm_accum_kernel_v2, _pf_gemm_swiglu_kernel_v2,
)

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
comptime MAX_CTX: Int = 1024
comptime REPS: Int = 100
comptime M: Int = 128

comptime HBM_GB_S: Float64 = 1555.0
comptime FP32_TFLOPS: Float64 = 19.5


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


def _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("prefill_gemm_probe: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _us(ns: Int, reps: Int) -> Float64:
    return Float64(ns) / 1.0e3 / Float64(reps)


def _check(status: Int, ok: Int, ctx_name: String) raises:
    if status != ok:
        raise Error("prefill_gemm_probe: " + ctx_name + " failed, status=" + String(status))


@fieldwise_init
struct DiffReport(Copyable, Movable):
    var max_abs: Float64
    var max_rel: Float64
    var n_diff: Int


def _diff_buffers(
    mut ctx: DeviceContext, yb: DeviceBuffer[DType.float32],
    yv: DeviceBuffer[DType.float32], n_elems: Int,
) raises -> DiffReport:
    """Copy both device buffers to pinned host buffers and report the worst element-wise
    difference. The buffers are passed borrowed; enqueue_copy only reads them."""
    var max_abs = Float64(0.0)
    var max_rel = Float64(0.0)
    var n_diff = 0
    var hb_a = ctx.enqueue_create_host_buffer[DType.float32](n_elems)
    var hb_b = ctx.enqueue_create_host_buffer[DType.float32](n_elems)
    ctx.enqueue_copy(hb_a, yb)
    ctx.enqueue_copy(hb_b, yv)
    ctx.synchronize()
    var host_a = hb_a.unsafe_ptr()
    var host_b = hb_b.unsafe_ptr()
    for i in range(n_elems):
        var va = Float64(host_a[i])
        var vb = Float64(host_b[i])
        var d = va - vb
        if d < 0.0:
            d = -d
        var denom = va if va >= 0.0 else -va
        var vb_abs = vb if vb >= 0.0 else -vb
        if vb_abs > denom:
            denom = vb_abs
        if denom < 1.0:
            denom = 1.0
        if d > 0.0:
            n_diff += 1
        if d > max_abs:
            max_abs = d
        var rel = d / denom
        if rel > max_rel:
            max_rel = rel
    return DiffReport(max_abs, max_rel, n_diff)


def main() raises:
    var manifest = _read_text_file(MANIFEST_PATH)
    var config = json_get_object(manifest, "config")
    var d_model = json_get_int(config, "hidden_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var vocab_size = json_get_int(config, "vocab_size", -1)
    var theta = json_get_float(config, "rope_theta", -1.0)
    var eps = json_get_float(config, "rms_norm_eps", -1.0)
    var n_prompt = json_get_int(config, "n_tokens", -1)

    var scale = 1.0 / sqrt(Float64(d_head))
    print("prefill_gemm_probe: Qwen3-0.6B shapes | m =", M, "| REPS =", REPS,
          "| floors: FP32", FP32_TFLOPS, "TFLOP/s")

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 64, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("prefill_gemm_probe: cannot run here:", residentk_status_name(pre))
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        print("prefill_gemm_probe: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("prefill_gemm_probe: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))

        var tensors_obj = json_get_object(manifest, "tensors")
        var s = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("  device:", s.device_name())
        var rt = rope_table(d_head, MAX_CTX, theta)
        _check(rt.status, ATTN_OK, "rope_table")
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check(s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
               RESIDENT_OK, "upload_globals")
        for layer in range(n_layers):
            var pfx = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(BLOB_PATH, tensors_obj, pfx + "input_layernorm.weight")
            var ln2 = _load_tensor(BLOB_PATH, tensors_obj, pfx + "post_attention_layernorm.weight")
            var qn = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.q_norm.weight")
            var kn = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.k_norm.weight")
            var wq = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.q_proj.weight")
            var wk = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.k_proj.weight")
            var wv = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.v_proj.weight")
            var wo = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.o_proj.weight")
            var wg = _load_tensor(BLOB_PATH, tensors_obj, pfx + "mlp.gate_proj.weight")
            var wu = _load_tensor(BLOB_PATH, tensors_obj, pfx + "mlp.up_proj.weight")
            var wd = _load_tensor(BLOB_PATH, tensors_obj, pfx + "mlp.down_proj.weight")
            _check(s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                   RESIDENT_OK, "upload_layer " + String(layer))
        _check(s.seal(), RESIDENT_OK, "seal")

        # One prefill so the activation scratch holds realistic contents.
        var pf = s.prefill(prompt_ids)
        _check(pf.status, RESIDENT_OK, "prefill")

        ref lw = s.layers[0]
        var n_q = h_q * d_head
        var n_kv = h_kv * d_head
        var n_qkv = n_q + 2 * n_kv

        print("== CORRECTNESS GATE — v2 vs first generation, same inputs ==")

        # ── assign(qkv) at m = M ──
        var yb = s.ctx.enqueue_create_buffer[DType.float32](M * n_qkv)
        var yv = s.ctx.enqueue_create_buffer[DType.float32](M * n_qkv)
        s.ctx.enqueue_function[_pf_gemm_assign_kernel](
            yb.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
            Int64(M), Int64(d_model), Int64(n_qkv),
            grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(n_qkv, _GEMM_BN),
            block_dim=_GEMM_NTHREADS)
        s.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
            yv.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
            Int64(M), Int64(d_model), Int64(n_qkv),
            grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
            block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var d1 = _diff_buffers(s.ctx, yb, yv, M * n_qkv)
        print("  assign(qkv) m =", M, ": max_abs =", d1.max_abs, "| max_rel =", d1.max_rel,
              "| n_diff =", d1.n_diff, "of", M * n_qkv)

        # ── ragged-M rows: the any-token-amount contract ──
        var ragged_ms = List[Int]()
        ragged_ms.append(17)
        ragged_ms.append(127)
        for rm in ragged_ms:
            var ybr = s.ctx.enqueue_create_buffer[DType.float32](rm * n_qkv)
            var yvr = s.ctx.enqueue_create_buffer[DType.float32](rm * n_qkv)
            s.ctx.enqueue_function[_pf_gemm_assign_kernel](
                ybr.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                Int64(rm), Int64(d_model), Int64(n_qkv),
                grid_dim=_ceil_div(rm, _GEMM_BM) * _ceil_div(n_qkv, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
            s.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                yvr.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                Int64(rm), Int64(d_model), Int64(n_qkv),
                grid_dim=_ceil_div(rm, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                block_dim=_G2_NTHREADS)
            s.ctx.synchronize()
            var dr = _diff_buffers(s.ctx, ybr, yvr, rm * n_qkv)
            print("  assign(qkv) m =", rm, ": max_abs =", dr.max_abs, "| max_rel =", dr.max_rel,
                  "| n_diff =", dr.n_diff, "of", rm * n_qkv)
            if dr.max_rel > 1e-4:
                print("RESULT: FAIL (ragged-m correctness gate)")
                return

        # ── accum(o_proj) over zeroed outputs ──
        var ob = s.ctx.enqueue_create_buffer[DType.float32](M * d_model)
        var ov = s.ctx.enqueue_create_buffer[DType.float32](M * d_model)
        with ob.map_to_host() as h:
            for i in range(M * d_model):
                h[i] = Float32(0.0)
        with ov.map_to_host() as h:
            for i in range(M * d_model):
                h[i] = Float32(0.0)
        s.ctx.synchronize()
        s.ctx.enqueue_function[_pf_gemm_accum_kernel](
            ob.unsafe_ptr(), s.pf_attn.unsafe_ptr(), lw.w_o.unsafe_ptr(),
            Int64(M), Int64(n_q), Int64(d_model),
            grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(d_model, _GEMM_BN),
            block_dim=_GEMM_NTHREADS)
        s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
            ov.unsafe_ptr(), s.pf_attn.unsafe_ptr(), lw.w_o.unsafe_ptr(),
            Int64(M), Int64(n_q), Int64(d_model),
            grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(d_model, _G2_BN),
            block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var d2 = _diff_buffers(s.ctx, ob, ov, M * d_model)
        print("  accum(o) m =", M, ": max_abs =", d2.max_abs, "| max_rel =", d2.max_rel,
              "| n_diff =", d2.n_diff, "of", M * d_model)

        # ── swiglu(gate/up) ──
        var ab = s.ctx.enqueue_create_buffer[DType.float32](M * d_ff)
        var av = s.ctx.enqueue_create_buffer[DType.float32](M * d_ff)
        s.ctx.enqueue_function[_pf_gemm_swiglu_kernel](
            ab.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_gu.unsafe_ptr(),
            Int64(M), Int64(d_model), Int64(d_ff),
            grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(d_ff, _GEMM_BN),
            block_dim=_GEMM_NTHREADS)
        s.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
            av.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_gu.unsafe_ptr(),
            Int64(M), Int64(d_model), Int64(d_ff),
            grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(d_ff, _G2_BN),
            block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var d3 = _diff_buffers(s.ctx, ab, av, M * d_ff)
        print("  swiglu(gu) m =", M, ": max_abs =", d3.max_abs, "| max_rel =", d3.max_rel,
              "| n_diff =", d3.n_diff, "of", M * d_ff)

        # ── accum(down_proj) over zeroed outputs ──
        var db = s.ctx.enqueue_create_buffer[DType.float32](M * d_model)
        var dv = s.ctx.enqueue_create_buffer[DType.float32](M * d_model)
        with db.map_to_host() as h:
            for i in range(M * d_model):
                h[i] = Float32(0.0)
        with dv.map_to_host() as h:
            for i in range(M * d_model):
                h[i] = Float32(0.0)
        s.ctx.synchronize()
        s.ctx.enqueue_function[_pf_gemm_accum_kernel](
            db.unsafe_ptr(), s.pf_act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
            Int64(M), Int64(d_ff), Int64(d_model),
            grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(d_model, _GEMM_BN),
            block_dim=_GEMM_NTHREADS)
        s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
            dv.unsafe_ptr(), s.pf_act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
            Int64(M), Int64(d_ff), Int64(d_model),
            grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(d_model, _G2_BN),
            block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var d4 = _diff_buffers(s.ctx, db, dv, M * d_model)
        print("  accum(down) m =", M, ": max_abs =", d4.max_abs, "| max_rel =", d4.max_rel,
              "| n_diff =", d4.n_diff, "of", M * d_model)

        var worst_rel = d1.max_rel
        if d2.max_rel > worst_rel:
            worst_rel = d2.max_rel
        if d3.max_rel > worst_rel:
            worst_rel = d3.max_rel
        if d4.max_rel > worst_rel:
            worst_rel = d4.max_rel
        if worst_rel > 1e-4:
            print("RESULT: FAIL (correctness gate, worst rel diff", worst_rel, ")")
            return
        print("  correctness gate PASS (worst rel diff", worst_rel, "< 1e-4)")

        print("== PERFORMANCE — REPS dispatches back-to-back, one synchronize ==")

        var t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_assign_kernel](
                yb.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                Int64(M), Int64(d_model), Int64(n_qkv),
                grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(n_qkv, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        var base_qkv = _us(perf_counter_ns() - t0, REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                yv.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                Int64(M), Int64(d_model), Int64(n_qkv),
                grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var v2_qkv = _us(perf_counter_ns() - t0, REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_accum_kernel](
                ob.unsafe_ptr(), s.pf_attn.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                Int64(M), Int64(n_q), Int64(d_model),
                grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(d_model, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        var base_o = _us(perf_counter_ns() - t0, REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                ov.unsafe_ptr(), s.pf_attn.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                Int64(M), Int64(n_q), Int64(d_model),
                grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(d_model, _G2_BN),
                block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var v2_o = _us(perf_counter_ns() - t0, REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_swiglu_kernel](
                ab.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_gu.unsafe_ptr(),
                Int64(M), Int64(d_model), Int64(d_ff),
                grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(d_ff, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        var base_gu = _us(perf_counter_ns() - t0, REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                av.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_gu.unsafe_ptr(),
                Int64(M), Int64(d_model), Int64(d_ff),
                grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(d_ff, _G2_BN),
                block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var v2_gu = _us(perf_counter_ns() - t0, REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_accum_kernel](
                db.unsafe_ptr(), s.pf_act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                Int64(M), Int64(d_ff), Int64(d_model),
                grid_dim=_ceil_div(M, _GEMM_BM) * _ceil_div(d_model, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        var base_down = _us(perf_counter_ns() - t0, REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                dv.unsafe_ptr(), s.pf_act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                Int64(M), Int64(d_ff), Int64(d_model),
                grid_dim=_ceil_div(M, _G2_BM) * _ceil_div(d_model, _G2_BN),
                block_dim=_G2_NTHREADS)
        s.ctx.synchronize()
        var v2_down = _us(perf_counter_ns() - t0, REPS)

        var flops_qkv = Float64(2) * Float64(M) * Float64(n_qkv) * Float64(d_model)
        var flops_o = Float64(2) * Float64(M) * Float64(d_model) * Float64(n_q)
        var flops_gu = Float64(2) * Float64(M) * Float64(2) * Float64(d_ff) * Float64(d_model)
        var flops_down = Float64(2) * Float64(M) * Float64(d_model) * Float64(d_ff)
        var peak_gf = FP32_TFLOPS * 1000.0

        print("  assign(qkv): base", base_qkv, "us (",
              flops_qkv / (base_qkv * 1e-6) / 1e9, "GF/s,",
              flops_qkv / (base_qkv * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) | v2", v2_qkv,
              "us (", flops_qkv / (v2_qkv * 1e-6) / 1e9, "GF/s,",
              flops_qkv / (v2_qkv * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) |",
              base_qkv / v2_qkv, "x")
        print("  accum(o):    base", base_o, "us (",
              flops_o / (base_o * 1e-6) / 1e9, "GF/s,",
              flops_o / (base_o * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) | v2", v2_o,
              "us (", flops_o / (v2_o * 1e-6) / 1e9, "GF/s,",
              flops_o / (v2_o * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) |",
              base_o / v2_o, "x")
        print("  swiglu(gu):  base", base_gu, "us (",
              flops_gu / (base_gu * 1e-6) / 1e9, "GF/s,",
              flops_gu / (base_gu * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) | v2", v2_gu,
              "us (", flops_gu / (v2_gu * 1e-6) / 1e9, "GF/s,",
              flops_gu / (v2_gu * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) |",
              base_gu / v2_gu, "x")
        print("  accum(down): base", base_down, "us (",
              flops_down / (base_down * 1e-6) / 1e9, "GF/s,",
              flops_down / (base_down * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) | v2", v2_down,
              "us (", flops_down / (v2_down * 1e-6) / 1e9, "GF/s,",
              flops_down / (v2_down * 1e-6) / 1e9 / peak_gf * 100.0, "% peak) |",
              base_down / v2_down, "x")

        var base_sum = base_qkv + base_o + base_gu + base_down
        var v2_sum = v2_qkv + v2_o + v2_gu + v2_down
        print("  LAYER GEMM SUM: base", base_sum, "us | v2", v2_sum, "us |",
              base_sum / v2_sum, "x | projected per-layer saving",
              (base_sum - v2_sum) / 1000.0, "ms x", n_layers, "layers =",
              (base_sum - v2_sum) / 1000.0 * Float64(n_layers), "ms per prefill chunk")
        print("RESULT: PASS")
