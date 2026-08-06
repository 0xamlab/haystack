"""int4_stage_b_diag.mojo — diagnostic-only companion to `qwen3_generate_metal_i4.mojo`'s stage (b)
result. Not a golden-vector suite, not registered in `generate_mojo_tests.py`; a throwaway probe in
the same convention as `decode_metal_probe.mojo`/`int8_pack_probe.mojo`.

`qwen3_generate_metal_i4.mojo`'s stage (b) run found the int4 arm's first decode step disagrees with
the known-correct token (12095): its argmax picked 279 (logit 18.093505859375). `_lmhead_argmax_kernel_i8`
(reused as-is by `_ResidentQwen3I4` — the tied embed/lm_head table stays int8 in this arm) never
materializes the full 151,936-wide logits row, by design, so this file re-drives the IDENTICAL
prefill (same checkpoint, same weights, deterministic quantization -> bit-identical resident state)
and then runs ONE extra, diagnostic-only dispatch that computes the logit for a SPECIFIC row (12095)
using the exact same final-rmsnorm + dot-product + int8-dequant formula
`_lmhead_argmax_kernel_i8` uses internally, so the real logit GAP between the correct token and the
one int4 actually chose can be reported precisely, per this task's own requirement.
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import barrier, thread_idx, block_idx
from std.gpu.memory import AddressSpace
from std.gpu.host import DeviceContext
from std.math import sqrt
from std.memory import stack_allocation
from std.sys import has_accelerator
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_DEFAULT_CONTEXT, RESIDENT_OK, RESIDENT_MAX_D_MODEL
from residentk.session import RESIDENT_GPU_BUILD, _ResidentQwen3I4

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime _TG: Int = 256
comptime _STAGE: Int = RESIDENT_MAX_D_MODEL

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]


def _logit_for_row_kernel(
    out_val: _FP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP, k: Int, row: Int, eps: Float32
):
    """ONE threadgroup, ONE row: final rmsnorm(x) then the tied lm_head projection's dot product for
    exactly `row`, dequantized (`Float32(i8) * wscale[row]`) inside the loop — the identical formula
    `_lmhead_argmax_kernel_i8` uses per-row, restricted to a single caller-specified row instead of a
    grid-stride scan over the whole vocabulary. Single-threadgroup, scalar loop (no vectorization) —
    this file is a diagnostic, not a throughput probe, so clarity over speed."""
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var acc = Float32(0.0)
    var base = row * k
    var srow = wscale[row]
    var i2 = tid
    while i2 < k:
        acc += xs[i2] * (Float32(w[base + i2]) * srow)
        i2 += _TG
    red[tid] = acc
    barrier()
    var st = _TG // 2
    while st > 0:
        if tid < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if tid == 0:
        out_val[0] = red[0]


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
        raise Error("int4_stage_b_diag: tensor not found: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("int4_stage_b_diag: short read")
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def main() raises:
    print("=== int4 stage (b) diagnostic: exact logit gap at the argmax boundary ===")
    if not RESIDENT_GPU_BUILD or not has_accelerator():
        print("requires -D ALGENTA_GPU and a real accelerator")
        return

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
    var max_ctx = RESIDENT_DEFAULT_CONTEXT

    var ids_arr = json_get_array(manifest, "input_ids")
    var id_tokens = json_array_tokens(ids_arr)
    var prompt_ids = List[Int]()
    for i in range(len(id_tokens)):
        prompt_ids.append(parse_int(id_tokens[i]))

    var tensors_obj = json_get_object(manifest, "tensors")

    var s = _ResidentQwen3I4(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
    )
    var rt = rope_table(d_head, max_ctx, theta)
    if rt.status != ATTN_OK:
        raise Error("int4_stage_b_diag: rope_table failed")

    var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
    var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
    if s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx) != RESIDENT_OK:
        raise Error("int4_stage_b_diag: upload_globals failed")

    for layer in range(n_layers):
        var prefix = "model.layers." + String(layer) + "."
        var ln1 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "input_layernorm.weight")
        var ln2 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "post_attention_layernorm.weight")
        var qn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_norm.weight")
        var kn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_norm.weight")
        var wq = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_proj.weight")
        var wk = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_proj.weight")
        var wv = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.v_proj.weight")
        var wo = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.o_proj.weight")
        var wg = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.gate_proj.weight")
        var wu = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.up_proj.weight")
        var wd = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.down_proj.weight")
        if s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd) != RESIDENT_OK:
            raise Error("int4_stage_b_diag: upload_layer failed at " + String(layer))
    _ = s.seal()

    # ── prefill, IDENTICAL to qwen3_generate_metal_i4.mojo's own prefill loop ──
    var first_tok = -1
    var first_logit = 0.0
    for t in range(n_prompt):
        var r = s.step(prompt_ids[t], t)
        if r.status != RESIDENT_OK:
            raise Error("int4_stage_b_diag: step failed at prefill pos " + String(t))
        first_tok = r.token_id
        first_logit = r.logit
    print("  reproduced stage (b) argmax token:", first_tok, " logit:", first_logit,
          " (expect 279 / 18.093505859375, matching qwen3_generate_metal_i4.mojo's own run)")

    # ── diagnostic dispatch: the logit for the KNOWN-CORRECT reference token, 12095 ──
    var f_row = s.ctx.compile_function_unchecked[_logit_for_row_kernel]()
    var out_buf = s.ctx.enqueue_create_buffer[DType.float32](1)

    s.ctx.enqueue_function_unchecked(
        f_row, out_buf.unsafe_ptr(), s.hidden.unsafe_ptr(), s.final_norm.unsafe_ptr(),
        s.embed.unsafe_ptr(), s.embed_scale.unsafe_ptr(), s.d_model, 12095, s.eps,
        grid_dim=1, block_dim=_TG,
    )
    s.ctx.synchronize()
    var logit_12095 = 0.0
    with out_buf.map_to_host() as h:
        logit_12095 = Float64(h[0])

    s.ctx.enqueue_function_unchecked(
        f_row, out_buf.unsafe_ptr(), s.hidden.unsafe_ptr(), s.final_norm.unsafe_ptr(),
        s.embed.unsafe_ptr(), s.embed_scale.unsafe_ptr(), s.d_model, first_tok, s.eps,
        grid_dim=1, block_dim=_TG,
    )
    s.ctx.synchronize()
    var logit_winner_recomputed = 0.0
    with out_buf.map_to_host() as h:
        logit_winner_recomputed = Float64(h[0])

    print("")
    print("  int4 arm's own argmax winner, token", first_tok, ": logit =", first_logit,
        " (recomputed via the single-row diagnostic kernel:", logit_winner_recomputed, ")")
    print("  int4 arm's logit for the KNOWN-CORRECT reference token 12095:", logit_12095)
    print("  GAP (winner - reference token), under int4:", first_logit - logit_12095)
    print("  argmax agreement: ", "AGREES with reference" if first_tok == 12095 else "DISAGREES with reference -- this IS the divergence")

    # ── sanity scan: is 12095 genuinely int4's #2, or is there some OTHER row higher than it but
    # still below the winner? Check every token id that appears anywhere in either the reference's
    # or int4's own 16-step generated sequence, plus a few arbitrary common ids, as a
    # non-exhaustive but concrete check that 279/12095 are the real top-2, not an artifact of only
    # having looked at two rows. ──
    var candidates: List[Int] = [
        12095, 279, 13, 576, 6722, 315, 9625, 9856, 374, 19846, 15344, 21718, 785, 1,
    ]
    print("")
    print("  sanity scan over", len(candidates), "candidate token ids (not exhaustive over the",
          "151,936-word vocabulary, but covers every token that appears anywhere in either the",
          "reference's or int4's own generated sequence):")
    for c in candidates:
        s.ctx.enqueue_function_unchecked(
            f_row, out_buf.unsafe_ptr(), s.hidden.unsafe_ptr(), s.final_norm.unsafe_ptr(),
            s.embed.unsafe_ptr(), s.embed_scale.unsafe_ptr(), s.d_model, c, s.eps,
            grid_dim=1, block_dim=_TG,
        )
        s.ctx.synchronize()
        var lv = 0.0
        with out_buf.map_to_host() as h:
            lv = Float64(h[0])
        print("    token", c, ": int4 logit =", lv)
