"""h100_gemm_probe.mojo — the H100 prefill GEMM variant A/B probe: v2 baseline vs the new
v3 WIDE (BM=128, TM=8x4) and v3s SMALL-M NARROW (BM=32, 128 threads) families at Qwen3-0.6B's
real layer shapes, at the real M values the raced drivers run (128 fixture chunks, 256 one-pass
fixture, 1152 serve-admission passes). Layer 0's REAL resident f32 weights; deterministic
activation fill; per role: (1) max-abs difference vs the v2 twin on identical inputs (gate:
<= 1e-5 — same ascending-k order, only codegen-level differences expected), then (2) timing
as REPS back-to-back enqueues + one sync (device-bound, the kernel_sweep_cuda method).

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_90 \
        -I mojo/engine -I attention_forge \
        benchmarks/llm_smoke/nvidia_race/h100_gemm_probe.mojo -o h100_gemm_probe
"""

from max.gpu.host import DeviceBuffer, DeviceContext
from std.gpu import block_idx, thread_idx
from std.math import sqrt
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from std.origin import MutAnyOrigin
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_OK, residentk_status_name
from residentk.session import _resident_preflight, _ceil_div
from residentk.session_cuda import CUDA_SESSION_BUILD, _CudaResidentQwen3
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM, _G2_BN, _G2_NTHREADS,
    _pf_gemm_assign_kernel_v2,
    _pf_gemm_accum_kernel_v2,
    _pf_gemm_swiglu_kernel_v2,
)
from residentk.kernels_prefill_f32_v2n import (
    _G2N_BN, _G2N_NTHREADS,
    _pf_gemm_accum_kernel_v2n,
)
from residentk.kernels_prefill_f32_v3 import (
    _G3_BM, _G3_BN, _G3_NTHREADS,
    _pf_gemm_assign_kernel_v3,
    _pf_gemm_accum_kernel_v3,
    _G3S_BM, _G3S_BN, _G3S_NTHREADS,
    _pf_gemm_accum_kernel_v3s,
)

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
comptime MAX_CTX: Int = 1024
comptime M_MAX: Int = 1152
comptime REPS: Int = 50
comptime DIFF_GATE: Float64 = 1.0e-5
comptime FP32_TFLOPS_H100: Float64 = 66.9


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
        raise Error("h100_gemm_probe: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("h100_gemm_probe: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("h100_gemm_probe: " + ctx + " failed, status=" + String(status))


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
    print("h100_gemm_probe: Qwen3-0.6B | REPS =", REPS, "| M values: 128, 256, 1152",
          "| H100 f32 floor:", FP32_TFLOPS_H100, "TFLOP/s")

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 64, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("h100_gemm_probe: cannot run here:", residentk_status_name(pre))
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        print("h100_gemm_probe: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("h100_gemm_probe: no accelerator on this host")
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
        var pf = s.prefill(prompt_ids)
        _check(pf.status, RESIDENT_OK, "prefill")

        ref lw = s.layers[0]
        var n_q = h_q * d_head
        var n_kv = h_kv * d_head
        var n_qkv = n_q + 2 * n_kv

        # ── probe scratch at M_MAX rows ──
        var x = s.ctx.enqueue_create_buffer[DType.float32](M_MAX * d_model)
        var y_ref = s.ctx.enqueue_create_buffer[DType.float32](M_MAX * n_qkv)
        var y_new = s.ctx.enqueue_create_buffer[DType.float32](M_MAX * n_qkv)
        var attn_in = s.ctx.enqueue_create_buffer[DType.float32](M_MAX * n_q)
        var act_in = s.ctx.enqueue_create_buffer[DType.float32](M_MAX * d_ff)
        s.ctx.synchronize()

        # deterministic fills: x and the ACCUM destinations' base values
        with x.map_to_host() as h:
            var v = 0.0
            for i in range(M_MAX * d_model):
                v = v + 0.6180339887498949
                if v >= 1.0:
                    v = v - 1.0
                h[i] = Float32(v - 0.5)
        with attn_in.map_to_host() as h:
            var v = 0.0
            for i in range(M_MAX * n_q):
                v = v + 0.7548776662466927
                if v >= 1.0:
                    v = v - 1.0
                h[i] = Float32(v - 0.5)
        with act_in.map_to_host() as h:
            var v = 0.0
            for i in range(M_MAX * d_ff):
                v = v + 0.4142135623730951
                if v >= 1.0:
                    v = v - 1.0
                h[i] = Float32(v - 0.5)
        s.ctx.synchronize()

        var ms = [128, 256, 1152]

        # ══════════ ROLE 1: qkv ASSIGN (K=d_model, N=n_qkv) ══════════
        for i in range(3):
            var m = ms[i]
            # correctness
            s.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                y_ref.unsafe_ptr(), x.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                Int64(m), Int64(d_model), Int64(n_qkv),
                grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                block_dim=_G2_NTHREADS)
            s.ctx.enqueue_function[_pf_gemm_assign_kernel_v3](
                y_new.unsafe_ptr(), x.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                Int64(m), Int64(d_model), Int64(n_qkv),
                grid_dim=_ceil_div(m, _G3_BM) * _ceil_div(n_qkv, _G3_BN),
                block_dim=_G3_NTHREADS)
            s.ctx.synchronize()
            var md = _max_abs_diff(y_ref, y_new, m * n_qkv)
            print("qkv assign M =", m, "| v3-vs-v2 max_abs_diff =", md,
                  "|", "PASS" if md <= DIFF_GATE else "FAIL")
            # timing
            var t0 = perf_counter_ns()
            for _ in range(REPS):
                s.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                    y_ref.unsafe_ptr(), x.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                    Int64(m), Int64(d_model), Int64(n_qkv),
                    grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                    block_dim=_G2_NTHREADS)
            s.ctx.synchronize()
            var v2_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
            t0 = perf_counter_ns()
            for _ in range(REPS):
                s.ctx.enqueue_function[_pf_gemm_assign_kernel_v3](
                    y_new.unsafe_ptr(), x.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                    Int64(m), Int64(d_model), Int64(n_qkv),
                    grid_dim=_ceil_div(m, _G3_BM) * _ceil_div(n_qkv, _G3_BN),
                    block_dim=_G3_NTHREADS)
            s.ctx.synchronize()
            var v3_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
            var flops = Float64(2) * Float64(m) * Float64(n_qkv) * Float64(d_model)
            _report("qkv_assign", m, v2_us, v3_us, flops)

        # ══════════ ROLE 2: o_proj ACCUM (K=n_q, N=d_model) — narrow N ══════════
        for i in range(3):
            var m = ms[i]
            _fill_const(y_ref, m * d_model, 0.25, s.ctx)
            _copy_same(y_new, y_ref, m * d_model, s.ctx)
            s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                y_ref.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                Int64(m), Int64(n_q), Int64(d_model),
                grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(d_model, _G2_BN),
                block_dim=_G2_NTHREADS)
            s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3](
                y_new.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                Int64(m), Int64(n_q), Int64(d_model),
                grid_dim=_ceil_div(m, _G3_BM) * _ceil_div(d_model, _G3_BN),
                block_dim=_G3_NTHREADS)
            s.ctx.synchronize()
            var md = _max_abs_diff(y_ref, y_new, m * d_model)
            print("o accum M =", m, "| v3-vs-v2 max_abs_diff =", md,
                  "|", "PASS" if md <= DIFF_GATE else "FAIL")
            var t0 = perf_counter_ns()
            for _ in range(REPS):
                s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                    y_ref.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    Int64(m), Int64(n_q), Int64(d_model),
                    grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(d_model, _G2_BN),
                    block_dim=_G2_NTHREADS)
            s.ctx.synchronize()
            var v2_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
            t0 = perf_counter_ns()
            for _ in range(REPS):
                s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3](
                    y_new.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    Int64(m), Int64(n_q), Int64(d_model),
                    grid_dim=_ceil_div(m, _G3_BM) * _ceil_div(d_model, _G3_BN),
                    block_dim=_G3_NTHREADS)
            s.ctx.synchronize()
            var v3_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
            var flops = Float64(2) * Float64(m) * Float64(d_model) * Float64(n_q)
            _report("o_accum_v3", m, v2_us, v3_us, flops)
            # v3s small-M narrow variant
            if m <= 256:
                _fill_const(y_new, m * d_model, 0.25, s.ctx)
                s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3s](
                    y_new.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    Int64(m), Int64(n_q), Int64(d_model),
                    grid_dim=_ceil_div(m, _G3S_BM) * _ceil_div(d_model, _G3S_BN),
                    block_dim=_G3S_NTHREADS)
                s.ctx.synchronize()
                md = _max_abs_diff(y_ref, y_new, m * d_model)
                print("o accum M =", m, "| v3s-vs-v2 max_abs_diff =", md,
                      "|", "PASS" if md <= DIFF_GATE else "FAIL")
                _dbg_first_vals("o_v3s_dbg", y_ref, y_new, m * d_model, s.ctx)
                t0 = perf_counter_ns()
                for _ in range(REPS):
                    s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3s](
                        y_new.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                        Int64(m), Int64(n_q), Int64(d_model),
                        grid_dim=_ceil_div(m, _G3S_BM) * _ceil_div(d_model, _G3S_BN),
                        block_dim=_G3S_NTHREADS)
                s.ctx.synchronize()
                var v3s_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
                _report("o_accum_v3s", m, v2_us, v3s_us, flops)
                # v2n (BN=32) reference twin
                _fill_const(y_new, m * d_model, 0.25, s.ctx)
                s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2n](
                    y_new.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    Int64(m), Int64(n_q), Int64(d_model),
                    grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(d_model, _G2N_BN),
                    block_dim=_G2N_NTHREADS)
                s.ctx.synchronize()
                md = _max_abs_diff(y_ref, y_new, m * d_model)
                print("o accum M =", m, "| v2n-vs-v2 max_abs_diff =", md,
                      "|", "PASS" if md <= DIFF_GATE else "FAIL")
                t0 = perf_counter_ns()
                for _ in range(REPS):
                    s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2n](
                        y_new.unsafe_ptr(), attn_in.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                        Int64(m), Int64(n_q), Int64(d_model),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(d_model, _G2N_BN),
                        block_dim=_G2N_NTHREADS)
                s.ctx.synchronize()
                var v2n_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
                _report("o_accum_v2n", m, v2_us, v2n_us, flops)

        # ══════════ ROLE 3: down_proj ACCUM (K=d_ff, N=d_model) — narrow N ══════════
        for i in range(3):
            var m = ms[i]
            _fill_const(y_ref, m * d_model, 0.25, s.ctx)
            _copy_same(y_new, y_ref, m * d_model, s.ctx)
            s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                y_ref.unsafe_ptr(), act_in.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                Int64(m), Int64(d_ff), Int64(d_model),
                grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(d_model, _G2_BN),
                block_dim=_G2_NTHREADS)
            s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3](
                y_new.unsafe_ptr(), act_in.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                Int64(m), Int64(d_ff), Int64(d_model),
                grid_dim=_ceil_div(m, _G3_BM) * _ceil_div(d_model, _G3_BN),
                block_dim=_G3_NTHREADS)
            s.ctx.synchronize()
            var md = _max_abs_diff(y_ref, y_new, m * d_model)
            print("down accum M =", m, "| v3-vs-v2 max_abs_diff =", md,
                  "|", "PASS" if md <= DIFF_GATE else "FAIL")
            var t0 = perf_counter_ns()
            for _ in range(REPS):
                s.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                    y_ref.unsafe_ptr(), act_in.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    Int64(m), Int64(d_ff), Int64(d_model),
                    grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(d_model, _G2_BN),
                    block_dim=_G2_NTHREADS)
            s.ctx.synchronize()
            var v2_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
            t0 = perf_counter_ns()
            for _ in range(REPS):
                s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3](
                    y_new.unsafe_ptr(), act_in.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    Int64(m), Int64(d_ff), Int64(d_model),
                    grid_dim=_ceil_div(m, _G3_BM) * _ceil_div(d_model, _G3_BN),
                    block_dim=_G3_NTHREADS)
            s.ctx.synchronize()
            var v3_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
            var flops = Float64(2) * Float64(m) * Float64(d_model) * Float64(d_ff)
            _report("down_accum_v3", m, v2_us, v3_us, flops)
            if m <= 256:
                _fill_const(y_new, m * d_model, 0.25, s.ctx)
                s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3s](
                    y_new.unsafe_ptr(), act_in.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    Int64(m), Int64(d_ff), Int64(d_model),
                    grid_dim=_ceil_div(m, _G3S_BM) * _ceil_div(d_model, _G3S_BN),
                    block_dim=_G3S_NTHREADS)
                s.ctx.synchronize()
                md = _max_abs_diff(y_ref, y_new, m * d_model)
                print("down accum M =", m, "| v3s-vs-v2 max_abs_diff =", md,
                      "|", "PASS" if md <= DIFF_GATE else "FAIL")
                t0 = perf_counter_ns()
                for _ in range(REPS):
                    s.ctx.enqueue_function[_pf_gemm_accum_kernel_v3s](
                        y_new.unsafe_ptr(), act_in.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                        Int64(m), Int64(d_ff), Int64(d_model),
                        grid_dim=_ceil_div(m, _G3S_BM) * _ceil_div(d_model, _G3S_BN),
                        block_dim=_G3S_NTHREADS)
                s.ctx.synchronize()
                var v3s_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
                _report("down_accum_v3s", m, v2_us, v3s_us, flops)

        # ══════════ ROLE 4: gate/up + SwiGLU (K=d_model, N=d_ff) — v2 only (control) ══════════
        for i in range(3):
            var m = ms[i]
            var t0 = perf_counter_ns()
            for _ in range(REPS):
                s.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                    act_in.unsafe_ptr(), x.unsafe_ptr(), lw.w_gu.unsafe_ptr(),
                    Int64(m), Int64(d_model), Int64(d_ff),
                    grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(d_ff, _G2_BN),
                    block_dim=_G2_NTHREADS)
            s.ctx.synchronize()
            var v2_us = _ms(perf_counter_ns() - t0) * 1000.0 / Float64(REPS)
            var flops = Float64(2) * Float64(m) * Float64(2) * Float64(d_ff) * Float64(d_model)
            var tf = flops / (v2_us * 1.0e-6) / 1.0e12
            print("swiglu v2 M =", m, "|", v2_us, "us |", tf, "TF/s =",
                  tf / FP32_TFLOPS_H100 * 100.0, "% of H100 f32 peak")

        print("h100_gemm_probe: done")


alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


comptime _PROBE_FILL_THREADS: Int = 256


def _probe_fill_kernel(buf: _FP, v: Float32, n_i64: Int64):
    var i = Int(block_idx.x) * _PROBE_FILL_THREADS + Int(thread_idx.x)
    if i < Int(n_i64):
        buf[i] = v


def _probe_copy_kernel(dst: _FP, src: _FP, n_i64: Int64):
    var i = Int(block_idx.x) * _PROBE_FILL_THREADS + Int(thread_idx.x)
    if i < Int(n_i64):
        dst[i] = src[i]


def _fill_const(mut buf: DeviceBuffer[DType.float32], n: Int, v: Float32, mut ctx: DeviceContext) raises:
    # DEVICE-SIDE fill: a host-mapped fill raced the following kernel enqueue (measured:
    # vacuous diffs on the accum variants) — the device kernel is stream-ordered, no race.
    ctx.enqueue_function[_probe_fill_kernel](
        buf.unsafe_ptr(), v, Int64(n),
        grid_dim=_ceil_div(n, 256), block_dim=256)
    ctx.synchronize()


def _copy_same(
    mut dst: DeviceBuffer[DType.float32], mut src: DeviceBuffer[DType.float32], n: Int,
    mut ctx: DeviceContext
) raises:
    ctx.enqueue_function[_probe_copy_kernel](
        dst.unsafe_ptr(), src.unsafe_ptr(), Int64(n),
        grid_dim=_ceil_div(n, 256), block_dim=256)
    ctx.synchronize()


def _dbg_first_vals(
    tag: String, mut a: DeviceBuffer[DType.float32], mut b: DeviceBuffer[DType.float32],
    n: Int, mut ctx: DeviceContext
) raises:
    ctx.synchronize()
    with a.map_to_host() as ha:
        print(tag, "a[0..2]:", ha[0], ha[1], ha[2])
    with b.map_to_host() as hb:
        print(tag, "b[0..2]:", hb[0], hb[1], hb[2])


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


def _report(role: String, m: Int, v2_us: Float64, new_us: Float64, flops: Float64):
    var tf2 = flops / (v2_us * 1.0e-6) / 1.0e12
    var tfn = flops / (new_us * 1.0e-6) / 1.0e12
    print("  ", role, "M =", m, "| v2:", v2_us, "us (", tf2, "TF/s ) | new:", new_us,
          "us (", tfn, "TF/s ) | speedup", v2_us / new_us,
          "| new % of H100 f32 peak:", tfn / FP32_TFLOPS_H100 * 100.0)
