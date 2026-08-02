"""qwen3_forward.mojo — a real Qwen3-0.6B-Base forward pass through the real Mojo kernels.

Hand-written driver, not a runtime-contract module (it lives under `benchmarks/`, not
`mojo/engine/`, and is not reachable via `execute(module, function, args)` — it is a thin
orchestration script in the same idiom as `bench_attnk.mojo` and friends, just reading real weights
instead of synthetic ones).

What this is
------------
Smoke test / conformance probe for the Algenta Enterprise LLM Kernel Plane's phase-1 question: do
attnk/normk/mlpk/gemm, called through their REAL published signatures with REAL Qwen3-0.6B-Base
weights, reproduce the reference model's forward pass? Every matrix multiply is `gemm.blocked.sgemm_flat`.
Every RMSNorm (including Qwen3's QK-Norm) is `normk.rmsnorm.rmsnorm_fwd_flat`. Every rotary embedding
is `attnk.rope.rope_table` / `rope_apply_flat`. Every attention is `attnk.sdpa.sdpa_forward_flat`
with `attnk.mask.mask_causal_flat`'s bias. Every gated-FFN activation is
`mlpk.activation.gated_ffn_fwd_flat`. Every embedding gather is `mlpk.embedding.embedding_fwd_flat`.
The one new kernel, `llmk.residual.residual_add_flat`, is documented in `mojo/engine/llmk/__init__.mojo`.
Nothing here is a second implementation of anything the plane already had (rule 3).

Weight layout, decided by the Python loading glue (`generate_manifest.py`), not by this file
-----------------------------------------------------------------------------------------------
Every 2D projection weight except `model.embed_tokens.weight` is pre-transposed from HF's
`[out_features, in_features]` to `[in_features, out_features]` at dump time, so every `sgemm_flat`
call below runs `trans_a=False, trans_b=False` (the fast SIMD path) except the final tied
lm_head projection, which reads slices of the UNtransposed embedding table with `trans_b=True`
(gemm's own `GEMM_MAX_DIM_ELEMS` ceiling refuses one call across the whole 151,936-row vocabulary,
so it is chunked — see the loop at the bottom).

Manifest format
---------------
`manifest.json`: `{"config": {...}, "input_ids": [...], "tensors": {name: {"offset": <float64
element index into weights.blob>, "n_elements": ..., "shape": [...]}}}`. `weights.blob` is one flat
Float64 file (native byte order), BF16 already upcast to Float64 by the loader — exact zero-extension,
not a lossy re-round.

I/O paths are hardcoded on purpose: this is a smoke-test driver invoked directly with `mojo run`, not
a runtime-contract function reachable over the wire, so there is no argv/env-var plumbing to add for
one hardcoded pair of input files.
"""

from std.math import sqrt
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from gemm.blocked import sgemm_flat
from gemm.contract import GEMM_OK
from normk.rmsnorm import rmsnorm_fwd_flat
from normk.contract import NORM_OK
from mlpk.embedding import embedding_fwd_flat
from mlpk.activation import gated_ffn_fwd_flat
from mlpk.contract import MLP_ACT_SWIGLU, MLP_OK
from attnk.rope import rope_apply_flat, rope_table
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat
from attnk.contract import ATTN_OK
from llmk.residual import residual_add_flat
from llmk.contract import LLMK_OK

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
comptime OUT_DIR: String = "/tmp/qwen3smoke/mojo_dump/"
comptime LM_HEAD_CHUNK: Int = 16384
"""Vocabulary columns per chunked lm_head call. `GEMM_MAX_DIM_ELEMS // d_model` is 21845 at
d_model=1024 (gemm.contract's own per-buffer ceiling on `k * n`); 16384 is a round number safely
under that with margin for any d_model this checkpoint family uses."""


fn _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_forward: " + ctx + " failed, status=" + String(status))


fn _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


fn _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("qwen3_forward: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


fn _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_forward: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


fn _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


fn _dump_f64(path: String, values: List[Float64]) raises:
    var n = len(values)
    var bp = values.unsafe_ptr().bitcast[UInt8]()
    var raw = List[UInt8](capacity=n * 8)
    for i in range(n * 8):
        raw.append(bp[i])
    var f = open(path, "w")
    f.write_bytes(raw)
    f.close()


fn _ms(ns: UInt) -> Float64:
    return Float64(Int(ns)) / 1.0e6


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
    var n_tok = json_get_int(config, "n_tokens", -1)

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 or vocab_size < 1 or n_tok < 1:
        raise Error("qwen3_forward: manifest config did not parse")

    print("qwen3_forward: d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q, "h_kv=", h_kv,
          "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size, "n_tok=", n_tok)

    var ids_arr = json_get_array(manifest, "input_ids")
    var id_tokens = json_array_tokens(ids_arr)
    var token_ids = List[Int]()
    for i in range(len(id_tokens)):
        token_ids.append(parse_int(id_tokens[i]))
    if len(token_ids) != n_tok:
        raise Error("qwen3_forward: input_ids length does not match config.n_tokens")

    var tensors_obj = json_get_object(manifest, "tensors")

    var t_load_ns: UInt = 0
    var t_compute_ns: UInt = 0
    var t_wall_start = perf_counter_ns()

    # ── embedding ──────────────────────────────────────────────────────────────
    var t0 = perf_counter_ns()
    var embed_loc = _tensor_loc(tensors_obj, "model.embed_tokens.weight")
    var embed_table = _read_f64_slice(BLOB_PATH, embed_loc.offset * 8, embed_loc.n_elements)
    var t1 = perf_counter_ns()
    t_load_ns += t1 - t0

    var embedded = embedding_fwd_flat(embed_table, token_ids, n_tok, vocab_size, d_model)
    _check(embedded.status, MLP_OK, "embedding_fwd_flat")
    var t2 = perf_counter_ns()
    t_compute_ns += t2 - t1

    _dump_f64(OUT_DIR + "hidden_0.bin", embedded.y)
    var hidden = embedded.y.copy()

    # ── shared RoPE table + causal mask, built once (frozen kernels, rule 3) ────
    var rt = rope_table(d_head, n_tok, theta)
    _check(rt.status, ATTN_OK, "rope_table")
    var positions = List[Int]()
    for t in range(n_tok):
        positions.append(t)
    var causal = mask_causal_flat(n_tok, n_tok, 0)
    _check(causal.status, ATTN_OK, "mask_causal_flat")
    var scale = 1.0 / sqrt(Float64(d_head))

    for layer in range(n_layers):
        var prefix = "model.layers." + String(layer) + "."

        var tl0 = perf_counter_ns()
        var in_norm_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "input_layernorm.weight")
        var q_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_proj.weight")
        var k_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_proj.weight")
        var v_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.v_proj.weight")
        var o_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.o_proj.weight")
        var qn_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_norm.weight")
        var kn_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_norm.weight")
        var post_norm_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "post_attention_layernorm.weight")
        var gate_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.gate_proj.weight")
        var up_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.up_proj.weight")
        var down_w = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.down_proj.weight")
        var tl1 = perf_counter_ns()
        t_load_ns += tl1 - tl0

        # -- attention block --
        var normed = rmsnorm_fwd_flat(hidden, in_norm_w, n_tok, d_model, eps)
        _check(normed.status, NORM_OK, "rmsnorm_fwd_flat(input_layernorm)")

        var q = sgemm_flat(normed.y, q_w, n_tok, h_q * d_head, d_model, 1.0, 0.0, False, False)
        _check(q.status, GEMM_OK, "sgemm_flat(q_proj)")
        var k = sgemm_flat(normed.y, k_w, n_tok, h_kv * d_head, d_model, 1.0, 0.0, False, False)
        _check(k.status, GEMM_OK, "sgemm_flat(k_proj)")
        var v = sgemm_flat(normed.y, v_w, n_tok, h_kv * d_head, d_model, 1.0, 0.0, False, False)
        _check(v.status, GEMM_OK, "sgemm_flat(v_proj)")

        # Qwen3's QK-Norm: RMSNorm per (token, head) row of head_dim, BEFORE RoPE.
        var qn = rmsnorm_fwd_flat(q.c, qn_w, n_tok * h_q, d_head, eps)
        _check(qn.status, NORM_OK, "rmsnorm_fwd_flat(q_norm)")
        var kn = rmsnorm_fwd_flat(k.c, kn_w, n_tok * h_kv, d_head, eps)
        _check(kn.status, NORM_OK, "rmsnorm_fwd_flat(k_norm)")

        # Half-split RoPE, `interleaved=False` -- Qwen3/Llama's `rotate_half` convention.
        var q_rot = rope_apply_flat(qn.y, rt.cos_table, rt.sin_table, n_tok, h_q, d_head, positions, False)
        _check(q_rot.status, ATTN_OK, "rope_apply_flat(q)")
        var k_rot = rope_apply_flat(kn.y, rt.cos_table, rt.sin_table, n_tok, h_kv, d_head, positions, False)
        _check(k_rot.status, ATTN_OK, "rope_apply_flat(k)")

        var attn = sdpa_forward_flat(
            q_rot.values, k_rot.values, v.c, causal.bias,
            n_tok, n_tok, h_q, h_kv, d_head, scale, True
        )
        _check(attn.status, ATTN_OK, "sdpa_forward_flat")

        var attn_proj = sgemm_flat(attn.out, o_w, n_tok, d_model, h_q * d_head, 1.0, 0.0, False, False)
        _check(attn_proj.status, GEMM_OK, "sgemm_flat(o_proj)")

        var resid1 = residual_add_flat(hidden, attn_proj.c, n_tok * d_model)
        _check(resid1.status, LLMK_OK, "residual_add_flat(post_attn)")
        hidden = resid1.out.copy()

        # -- feed-forward block --
        var normed2 = rmsnorm_fwd_flat(hidden, post_norm_w, n_tok, d_model, eps)
        _check(normed2.status, NORM_OK, "rmsnorm_fwd_flat(post_attention_layernorm)")

        var gate = sgemm_flat(normed2.y, gate_w, n_tok, d_ff, d_model, 1.0, 0.0, False, False)
        _check(gate.status, GEMM_OK, "sgemm_flat(gate_proj)")
        var up = sgemm_flat(normed2.y, up_w, n_tok, d_ff, d_model, 1.0, 0.0, False, False)
        _check(up.status, GEMM_OK, "sgemm_flat(up_proj)")

        var act = gated_ffn_fwd_flat(up.c, gate.c, n_tok, d_ff, MLP_ACT_SWIGLU)
        _check(act.status, MLP_OK, "gated_ffn_fwd_flat")

        var down = sgemm_flat(act.y, down_w, n_tok, d_model, d_ff, 1.0, 0.0, False, False)
        _check(down.status, GEMM_OK, "sgemm_flat(down_proj)")

        var resid2 = residual_add_flat(hidden, down.c, n_tok * d_model)
        _check(resid2.status, LLMK_OK, "residual_add_flat(post_ffn)")
        hidden = resid2.out.copy()
        var tl2 = perf_counter_ns()
        t_compute_ns += tl2 - tl1

        _dump_f64(OUT_DIR + "hidden_" + String(layer + 1) + ".bin", hidden)
        print("  layer", layer, "done (", _ms(tl2 - tl1), "ms compute,", _ms(tl1 - tl0), "ms load)")

    # ── final norm ─────────────────────────────────────────────────────────────
    var tf0 = perf_counter_ns()
    var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
    var tf1 = perf_counter_ns()
    t_load_ns += tf1 - tf0
    var final_normed = rmsnorm_fwd_flat(hidden, final_norm_w, n_tok, d_model, eps)
    _check(final_normed.status, NORM_OK, "rmsnorm_fwd_flat(final_norm)")
    var tf2 = perf_counter_ns()
    t_compute_ns += tf2 - tf1
    _dump_f64(OUT_DIR + "final_norm.bin", final_normed.y)

    # ── tied lm_head, chunked over the vocabulary (gemm.contract.GEMM_MAX_DIM_ELEMS) ──
    var logits = List[Float64](capacity=n_tok * vocab_size)
    for _ in range(n_tok * vocab_size):
        logits.append(0.0)

    var start = 0
    while start < vocab_size:
        var end = start + LM_HEAD_CHUNK
        if end > vocab_size:
            end = vocab_size
        var width = end - start

        var tc0 = perf_counter_ns()
        var b_chunk = _read_f64_slice(
            BLOB_PATH, (embed_loc.offset + start * d_model) * 8, width * d_model
        )
        var tc1 = perf_counter_ns()
        t_load_ns += tc1 - tc0

        var part = sgemm_flat(final_normed.y, b_chunk, n_tok, width, d_model, 1.0, 0.0, False, True)
        _check(part.status, GEMM_OK, "sgemm_flat(lm_head chunk)")
        for t in range(n_tok):
            for j in range(width):
                logits[t * vocab_size + start + j] = part.c[t * width + j]
        var tc2 = perf_counter_ns()
        t_compute_ns += tc2 - tc1

        start = end

    _dump_f64(OUT_DIR + "logits.bin", logits)
    var t_wall_end = perf_counter_ns()

    print("qwen3_forward: done.")
    print("  wall:", _ms(t_wall_end - t_wall_start), "ms for", n_tok, "tokens (prefill)")
    print("  of which weight-load (cold, from /tmp, no resident cache):", _ms(t_load_ns), "ms")
    print("  of which kernel compute (gemm/normk/attnk/mlpk/llmk):", _ms(t_compute_ns), "ms")
    print("  tokens/sec (wall, includes cold weight load -- NOT a resident-model serving number):",
          Float64(n_tok) / (_ms(t_wall_end - t_wall_start) / 1000.0))
