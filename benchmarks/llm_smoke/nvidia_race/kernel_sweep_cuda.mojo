"""kernel_sweep_cuda.mojo — the kernel-level NVIDIA sweep: every residentk decode and prefill
kernel measured in isolation at Qwen3-0.6B's real shapes on the campaign session, reported as
achieved throughput vs the GPU's theoretical floor, with a per-kernel verdict:

  * BW-BOUND kernels (the GEMV/weight-streaming family + attention + embed/lmhead):
        achieved GB/s vs the GPU's HBM peak (stated in the header; verdict bands below)
  * COMPUTE-BOUND kernels (the prefill tiled GEMMs at m_rows = 128):
        achieved GFLOP/s vs the FP32 SIMT peak (tensor cores are NOT used by these kernels)

Method (stated): each kernel is dispatched REPS times back-to-back and the context is
synchronized ONCE after the loop — the enqueues race ahead of the device, so the timed window
is device-bound, not host-bound; wall/REPS is the per-dispatch device cost. Shapes are the
resident session's own (Qwen3-0.6B: d_model 1024, h_q 16, h_kv 8, d_head 128, d_ff 3072,
vocab 151936, 28 layers); weights are the real resident f32 weights; layer 0 is swept (all
layers are identically shaped). A prefill runs first so the KV cache and activations hold
realistic contents.

Verdict bands (stated up front, not tuned after): BW kernels ok >= 60% of peak, low-bw
25-60%, very-low-bw < 25% (practical streaming usually lands ~70-85% of HBM peak, so <25%
means the kernel itself — vectorization/tiling/occupancy — is leaving the floor). Compute
kernels ok >= 50% of FP32 peak, low-compute 15-50%, very-low-compute < 15%.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/kernel_sweep_cuda.mojo -o sweep
"""

from max.gpu.host import DeviceContext
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

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
comptime MAX_CTX: Int = 1024
comptime REPS: Int = 200

# Theoretical floors for the raced A100-SXM4-40GB (stated; the output restates them).
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
        raise Error("kernel_sweep_cuda: tensor not found in manifest: " + name)
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


def _report_bw(name: String, us_per: Float64, bytes_per: Float64):
    var gb_s = bytes_per / (us_per * 1.0e-6) / 1.0e9
    var pct = gb_s / HBM_GB_S * 100.0
    var verdict = "ok" if pct >= 60.0 else ("low-bw" if pct >= 25.0 else "very-low-bw")
    print("  BW   ", name, "| us/dispatch =", us_per, "| GB/s =", gb_s,
          "| pct-of-peak =", pct, "% ->", verdict)


def _report_flops(name: String, us_per: Float64, flops_per: Float64):
    var gflops = flops_per / (us_per * 1.0e-6) / 1.0e9
    var pct = gflops / (FP32_TFLOPS * 1000.0) * 100.0
    var verdict = "ok" if pct >= 50.0 else ("low-compute" if pct >= 15.0 else "very-low-compute")
    print("  FLOP ", name, "| us/dispatch =", us_per, "| GFLOP/s =", gflops,
          "| pct-of-peak =", pct, "% ->", verdict)


def _report_fixed(name: String, us_per: Float64):
    var verdict = "dispatch-floor" if us_per < 50.0 else "slow"
    print("  FIXD ", name, "| us/dispatch =", us_per, "->", verdict)


def _check(status: Int, ok: Int, ctx_name: String) raises:
    if status != ok:
        raise Error("kernel_sweep_cuda: " + ctx_name + " failed, status=" + String(status))


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
    print("kernel_sweep_cuda: Qwen3-0.6B shapes | REPS =", REPS,
          "| floors: HBM", HBM_GB_S, "GB/s, FP32", FP32_TFLOPS, "TFLOP/s")

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 64, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("kernel_sweep_cuda: cannot run here:", residentk_status_name(pre))
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        print("kernel_sweep_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("kernel_sweep_cuda: no accelerator on this host")
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

        # ── one prefill so the KV cache + activations hold realistic contents ──
        var pf = s.prefill(prompt_ids)
        _check(pf.status, RESIDENT_OK, "prefill")

        ref lw = s.layers[0]
        var n_q = h_q * d_head
        var n_kv = h_kv * d_head
        var n_qkv = n_q + 2 * n_kv

        print("== DECODE family (one token, layer-0 shapes, f32 weights) ==")

        var t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_embed_row_kernel](
                s.hidden.unsafe_ptr(), s.embed.unsafe_ptr(),
                Int64(374), Int64(d_model),
                grid_dim=_ceil_div(d_model, _TG), block_dim=_TG)
        s.ctx.synchronize()
        _report_bw("embed_row", _us(perf_counter_ns() - t0, REPS),
                   Float64(d_model) * 4.0 * 2.0)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_norm_gemv_kernel](
                s.qkv.unsafe_ptr(), s.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                lw.w_qkv.unsafe_ptr(), Int64(d_model), Int64(n_qkv), s.eps,
                grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG)
        s.ctx.synchronize()
        _report_bw("norm_gemv(qkv)", _us(perf_counter_ns() - t0, REPS),
                   Float64(n_qkv) * Float64(d_model) * 4.0)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_qk_rope_write_kernel](
                s.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                s.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                s.cos_t.unsafe_ptr(), s.sin_t.unsafe_ptr(),
                Int64(300), Int64(h_q), Int64(h_kv), Int64(d_head), s.eps, Int64(1),
                grid_dim=h_q + h_kv, block_dim=d_head)
        s.ctx.synchronize()
        _report_fixed("qk_rope_write", _us(perf_counter_ns() - t0, REPS))

        var nk = 256
        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_sdpa_kernel](
                s.attn_out.unsafe_ptr(), s.q_rot.unsafe_ptr(),
                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                Int64(nk), Int64(h_q), Int64(h_kv), Int64(d_head), s.scale,
                grid_dim=h_q, block_dim=d_head)
        s.ctx.synchronize()
        _report_bw("sdpa n_keys=256", _us(perf_counter_ns() - t0, REPS),
                   Float64(2) * Float64(nk) * Float64(h_kv) * Float64(d_head) * 4.0)

        nk = 512
        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_sdpa_kernel](
                s.attn_out.unsafe_ptr(), s.q_rot.unsafe_ptr(),
                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                Int64(nk), Int64(h_q), Int64(h_kv), Int64(d_head), s.scale,
                grid_dim=h_q, block_dim=d_head)
        s.ctx.synchronize()
        _report_bw("sdpa n_keys=512", _us(perf_counter_ns() - t0, REPS),
                   Float64(2) * Float64(nk) * Float64(h_kv) * Float64(d_head) * 4.0)

        nk = 1024
        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_sdpa_kernel](
                s.attn_out.unsafe_ptr(), s.q_rot.unsafe_ptr(),
                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                Int64(nk), Int64(h_q), Int64(h_kv), Int64(d_head), s.scale,
                grid_dim=h_q, block_dim=d_head)
        s.ctx.synchronize()
        _report_bw("sdpa n_keys=1024", _us(perf_counter_ns() - t0, REPS),
                   Float64(2) * Float64(nk) * Float64(h_kv) * Float64(d_head) * 4.0)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_gemv_accum_kernel](
                s.hidden.unsafe_ptr(), s.attn_out.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                Int64(n_q), Int64(d_model),
                grid_dim=_ceil_div(d_model, _SUBS), block_dim=_TG)
        s.ctx.synchronize()
        _report_bw("gemv_accum(o_proj)", _us(perf_counter_ns() - t0, REPS),
                   Float64(n_q) * Float64(d_model) * 4.0)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_norm_gemv2_swiglu_kernel](
                s.act.unsafe_ptr(), s.hidden.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                lw.w_gu.unsafe_ptr(), Int64(d_model), Int64(d_ff), s.eps,
                grid_dim=_ceil_div(d_ff, _SUBS), block_dim=_TG)
        s.ctx.synchronize()
        _report_bw("norm_gemv2_swiglu(gu)", _us(perf_counter_ns() - t0, REPS),
                   Float64(2) * Float64(d_ff) * Float64(d_model) * 4.0)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_gemv_accum_kernel](
                s.hidden.unsafe_ptr(), s.act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                Int64(d_ff), Int64(d_model),
                grid_dim=_ceil_div(d_model, _SUBS), block_dim=_TG)
        s.ctx.synchronize()
        _report_bw("gemv_accum(down)", _us(perf_counter_ns() - t0, REPS),
                   Float64(d_ff) * Float64(d_model) * 4.0)

        var n_iters = _ceil_div(vocab_size, _LM_BLOCKS * _SUBS)
        t0 = perf_counter_ns()
        for _ in range(REPS // 4):
            s.ctx.enqueue_function[_lmhead_argmax_kernel](
                s.blk_val.unsafe_ptr(), s.blk_idx.unsafe_ptr(), s.hidden.unsafe_ptr(),
                s.final_norm.unsafe_ptr(), s.embed.unsafe_ptr(),
                Int64(d_model), Int64(vocab_size), s.eps, Int64(n_iters),
                grid_dim=_LM_BLOCKS, block_dim=_TG)
        s.ctx.synchronize()
        _report_bw("lmhead_argmax", _us(perf_counter_ns() - t0, REPS // 4),
                   Float64(vocab_size) * Float64(d_model) * 4.0)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            s.ctx.enqueue_function[_argmax_reduce_kernel](
                s.out_val.unsafe_ptr(), s.out_idx.unsafe_ptr(),
                s.blk_val.unsafe_ptr(), s.blk_idx.unsafe_ptr(), Int64(_LM_BLOCKS),
                grid_dim=1, block_dim=_TG)
        s.ctx.synchronize()
        _report_fixed("argmax_reduce", _us(perf_counter_ns() - t0, REPS))

        print("== PREFILL family (m_rows=128, layer-0 shapes, f32, tiled GEMMs) ==")
        var m = 128

        t0 = perf_counter_ns()
        for _ in range(REPS // 4):
            s.ctx.enqueue_function[_pf_gemm_assign_kernel](
                s.pf_qkv.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                Int64(m), Int64(d_model), Int64(n_qkv),
                grid_dim=_ceil_div(m, _GEMM_BM) * _ceil_div(n_qkv, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        _report_flops("pf_gemm_assign(qkv)", _us(perf_counter_ns() - t0, REPS // 4),
                      Float64(2) * Float64(m) * Float64(n_qkv) * Float64(d_model))

        t0 = perf_counter_ns()
        for _ in range(REPS // 4):
            s.ctx.enqueue_function[_pf_gemm_accum_kernel](
                s.pf_hidden.unsafe_ptr(), s.pf_attn.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                Int64(m), Int64(n_q), Int64(d_model),
                grid_dim=_ceil_div(m, _GEMM_BM) * _ceil_div(d_model, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        _report_flops("pf_gemm_accum(o)", _us(perf_counter_ns() - t0, REPS // 4),
                      Float64(2) * Float64(m) * Float64(d_model) * Float64(n_q))

        t0 = perf_counter_ns()
        for _ in range(REPS // 4):
            s.ctx.enqueue_function[_pf_gemm_swiglu_kernel](
                s.pf_act.unsafe_ptr(), s.pf_xn.unsafe_ptr(), lw.w_gu.unsafe_ptr(),
                Int64(m), Int64(d_model), Int64(d_ff),
                grid_dim=_ceil_div(m, _GEMM_BM) * _ceil_div(d_ff, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        _report_flops("pf_gemm_swiglu(gu)", _us(perf_counter_ns() - t0, REPS // 4),
                      Float64(2) * Float64(m) * Float64(2) * Float64(d_ff) * Float64(d_model))

        t0 = perf_counter_ns()
        for _ in range(REPS // 4):
            s.ctx.enqueue_function[_pf_gemm_accum_kernel](
                s.pf_hidden.unsafe_ptr(), s.pf_act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                Int64(m), Int64(d_ff), Int64(d_model),
                grid_dim=_ceil_div(m, _GEMM_BM) * _ceil_div(d_model, _GEMM_BN),
                block_dim=_GEMM_NTHREADS)
        s.ctx.synchronize()
        _report_flops("pf_gemm_accum(down)", _us(perf_counter_ns() - t0, REPS // 4),
                      Float64(2) * Float64(m) * Float64(d_model) * Float64(d_ff))

        t0 = perf_counter_ns()
        for _ in range(REPS // 4):
            s.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                s.pf_attn.unsafe_ptr(), s.pf_q_rot.unsafe_ptr(),
                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                Int64(0), Int64(h_q), Int64(h_kv), Int64(d_head), s.scale, Int64(m),
                grid_dim=h_q * m, block_dim=d_head)
        s.ctx.synchronize()
        var pf_attn_flops = Float64(4) * Float64(m) * Float64(m) / 2.0 \
            * Float64(d_head) * Float64(h_q)
        _report_flops("pf_attn_tiled(causal)", _us(perf_counter_ns() - t0, REPS // 4),
                      pf_attn_flops)

        t0 = perf_counter_ns()
        for _ in range(REPS // 4):
            s.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                s.pf_xn.unsafe_ptr(), s.pf_hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                Int64(d_model), s.eps, Int64(m),
                grid_dim=m, block_dim=_TG)
        s.ctx.synchronize()
        _report_bw("pf_rmsnorm_rows", _us(perf_counter_ns() - t0, REPS // 4),
                   Float64(2) * Float64(m) * Float64(d_model) * 4.0)

        print("kernel_sweep_cuda: done")
