"""qwen3_generate.mojo — real autoregressive decoding on top of the verified `qwen3_forward.mojo`
forward pass: prompt in, tokens out, one at a time, with a REAL per-layer KV cache, until EOS or a
length cap.

What is genuinely new here versus `qwen3_forward.mojo`
----------------------------------------------------------
`qwen3_forward.mojo` runs ONE forward pass over a fixed prompt and stops — prefill only, no decode
loop, no cache, nothing autoregressive. This file adds exactly three things on top of it, all
additive, nothing frozen touched:

1. A REAL KV cache, not a recompute-from-scratch loop. Every earlier token's post-RoPE K and
   post-projection V, per layer, are computed ONCE (during prefill or their own decode step) and
   never recomputed. Each decode step embeds only the ONE new token, projects Q/K/V for only that one
   token, appends the new K/V to the running per-layer cache with the new
   `llmk.generate.kv_cache_append_flat`, and calls `attnk.sdpa.sdpa_forward_flat` with
   `n_tok_q=1` against the FULL grown cache as `n_tok_k` — exactly the shape
   `attnk.mask.mask_causal_flat`'s `offset` parameter and `sdpa_forward_flat`'s independent
   `n_tok_q`/`n_tok_k` were already built to support (see `llmk/generate.mojo`'s docstring). Cost per
   decode step is O(cache_len) for attention plus O(1) for every other op — NOT O(prompt + step)
   through every projection and the FFN, which is what recomputing the whole sequence from scratch
   at every step would cost. Total cost across `n` decode steps is O(n) projections/FFN + O(n^2)
   attention (summed growing cache), the standard KV-cache decode complexity — not O(n^3) or worse,
   which a naive "recompute everything from scratch" loop would be.
2. GEMV, not GEMM, for every per-layer projection during decode. A decode step's activation is ONE
   row (`n_tok=1`); `gemm.blocked.gemv_flat` exists specifically for this ("the decode-shaped case:
   one vector, memory-bound" — its own docstring) and was unused by any driver before this file.
   Prefill still uses `gemm.blocked.sgemm_flat` (multiple rows at once), unchanged from
   `qwen3_forward.mojo`.
3. Greedy decoding via `llmk.generate.greedy_argmax_flat`, itself built ON `llm_sampling.greedy_token_id`
   (frozen, called not modified) — see that module's docstring for why a two-pass driver was needed
   around a per-candidate formula. Sampling (top-k/top-p/penalties) is explicitly out of scope here:
   greedy is the ONLY decoding strategy whose output sequence a reference implementation can be
   checked against exactly, without a matched RNG (temperature/top-p sampling both involve randomness
   that would need one).

Weight residency
------------------
Every layer's weights are read from `weights.blob` ONCE, into memory, before the prefill step —
`_load_all_layers` below — and then reused for prefill and every decode step. Re-reading them from
disk per decode step (as a per-step "cold load" driver would) would make the tokens/sec number
measure disk I/O, not the kernel plane; a real inference engine keeps weights resident and this driver
does too, honestly, so the decode-only tokens/sec this file reports is comparable to what a real
serving engine would report (steady-state decode throughput, weight load excluded).

I/O paths are hardcoded, same reasoning as `qwen3_forward.mojo`: this is a `mojo run` driver, not a
runtime-contract function.
"""

from std.math import sqrt
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from gemm.blocked import gemv_flat, sgemm_flat
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
from llmk.generate import greedy_argmax_flat, kv_cache_append_flat

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
"""Same shared, read-only, deterministic checkpoint dump `qwen3_forward.mojo` reads — see that
file's own comment on why reading a sibling worktree's data files is safe and writing into its output
directory is not."""

comptime OUT_DIR: String = "/tmp/bb/qwen3_ckpt/mojo_generate_llmfwd/"
"""This driver's OWN output directory — distinct from `qwen3_forward.mojo`'s
`mojo_dump_llmfwd/` (a different artifact: generated token ids, not per-layer hidden-state dumps) and
from the sibling worktree's `mojo_dump/` (a different worktree's run, never written to)."""

comptime N_NEW_MAX: Int = 16
"""Decode-step cap. Generation stops earlier on EOS; this is just the safety ceiling."""

comptime EOS_TOKEN_ID: Int = 151643
"""Qwen3-0.6B-Base's `eos_token_id` (== `bos_token_id`, a base model), read directly from the
checkpoint's own `config.json`/`generation_config.json` during the Prerequisite phase — not guessed."""


fn _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_generate: " + ctx + " failed, status=" + String(status))


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
        raise Error("qwen3_generate: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


fn _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_generate: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


fn _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


fn _write_text(path: String, text: String) raises:
    var f = open(path, "w")
    f.write_bytes(text.as_bytes())
    f.close()


fn _row_slice(x: List[Float64], row: Int, width: Int) -> List[Float64]:
    """Copy one `[width]`-wide row out of a flat `[n, width]` buffer -- the last-prefill-position
    slice prefill needs before it can hand off to the decode loop's one-row-at-a-time shape."""
    var out = List[Float64](capacity=width)
    var base = row * width
    for i in range(width):
        out.append(x[base + i])
    return out^


fn _ms(ns: UInt) -> Float64:
    return Float64(Int(ns)) / 1.0e6


@fieldwise_init
struct LayerWeights(Copyable, Movable):
    """Every weight one transformer block needs, loaded once and held resident across prefill and
    every decode step. `*_T` weights are pre-transposed `[in, out]` by the same Python loading glue
    `qwen3_forward.mojo` reads (see that file's module docstring) -- so both `sgemm_flat` (prefill,
    `trans_b=False`) and `gemv_flat` (decode, `trans=True`) hit their fast, non-transposed-read path."""

    var ln1: List[Float64]
    var ln2: List[Float64]
    var q: List[Float64]
    var k: List[Float64]
    var v: List[Float64]
    var o: List[Float64]
    var qn: List[Float64]
    var kn: List[Float64]
    var gate: List[Float64]
    var up: List[Float64]
    var down: List[Float64]


fn _load_all_layers(blob_path: String, tensors_obj: String, n_layers: Int) raises -> List[LayerWeights]:
    """Read every layer's weights from `weights.blob` exactly once. O(checkpoint size) disk I/O,
    O(1) per decode step afterward -- the residency this driver's own docstring is about."""
    var layers = List[LayerWeights]()
    for layer in range(n_layers):
        var prefix = "model.layers." + String(layer) + "."
        layers.append(LayerWeights(
            _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight"),
            _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight"),
        ))
    return layers^


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

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 or vocab_size < 1 or n_prompt < 1:
        raise Error("qwen3_generate: manifest config did not parse")

    print("qwen3_generate: d_model=", d_model, "n_layers=", n_layers, "h_q=", h_q, "h_kv=", h_kv,
          "d_head=", d_head, "d_ff=", d_ff, "vocab=", vocab_size, "n_prompt=", n_prompt,
          "n_new_max=", N_NEW_MAX)

    var ids_arr = json_get_array(manifest, "input_ids")
    var id_tokens = json_array_tokens(ids_arr)
    var prompt_ids = List[Int]()
    for i in range(len(id_tokens)):
        prompt_ids.append(parse_int(id_tokens[i]))
    if len(prompt_ids) != n_prompt:
        raise Error("qwen3_generate: input_ids length does not match config.n_tokens")

    var tensors_obj = json_get_object(manifest, "tensors")
    var scale = 1.0 / sqrt(Float64(d_head))

    var t_wall_start = perf_counter_ns()

    # ── weights, loaded ONCE, resident for prefill + every decode step ──────────
    var t0 = perf_counter_ns()
    var embed_loc = _tensor_loc(tensors_obj, "model.embed_tokens.weight")
    var embed_table = _read_f64_slice(BLOB_PATH, embed_loc.offset * 8, embed_loc.n_elements)
    var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
    var layers = _load_all_layers(BLOB_PATH, tensors_obj, n_layers)
    var t1 = perf_counter_ns()
    print("  weight load (once, resident):", _ms(t1 - t0), "ms")

    # ── shared RoPE table, sized for every position prefill + decode will ever query ──
    var max_pos = n_prompt + N_NEW_MAX
    var rt = rope_table(d_head, max_pos, theta)
    _check(rt.status, ATTN_OK, "rope_table")

    # ── per-layer KV cache: grows by exactly one token's worth per step, every layer in step ──
    var cache_k = List[List[Float64]]()
    var cache_v = List[List[Float64]]()
    for _ in range(n_layers):
        cache_k.append(List[Float64]())
        cache_v.append(List[Float64]())
    var cache_len_tokens = 0

    var generated_ids = List[Int]()
    for i in range(n_prompt):
        generated_ids.append(prompt_ids[i])

    var t_decode_start_ns: UInt = 0
    var per_step_ms = List[Float64]()
    var per_step_logit = List[Float64]()
    var stopped_on_eos = False

    # ═══ PREFILL: the whole prompt, all at once, exactly `qwen3_forward.mojo`'s per-layer body ═══
    var tp0 = perf_counter_ns()
    var embedded = embedding_fwd_flat(embed_table, prompt_ids, n_prompt, vocab_size, d_model)
    _check(embedded.status, MLP_OK, "embedding_fwd_flat(prefill)")
    var hidden = embedded.y.copy()

    var prefill_positions = List[Int]()
    for t in range(n_prompt):
        prefill_positions.append(t)
    var prefill_causal = mask_causal_flat(n_prompt, n_prompt, 0)
    _check(prefill_causal.status, ATTN_OK, "mask_causal_flat(prefill)")

    for layer in range(n_layers):

        var normed = rmsnorm_fwd_flat(hidden, layers[layer].ln1, n_prompt, d_model, eps)
        _check(normed.status, NORM_OK, "rmsnorm_fwd_flat(prefill input_layernorm)")

        var q = sgemm_flat(normed.y, layers[layer].q, n_prompt, h_q * d_head, d_model, 1.0, 0.0, False, False)
        _check(q.status, GEMM_OK, "sgemm_flat(prefill q_proj)")
        var k_new = sgemm_flat(normed.y, layers[layer].k, n_prompt, h_kv * d_head, d_model, 1.0, 0.0, False, False)
        _check(k_new.status, GEMM_OK, "sgemm_flat(prefill k_proj)")
        var v_new = sgemm_flat(normed.y, layers[layer].v, n_prompt, h_kv * d_head, d_model, 1.0, 0.0, False, False)
        _check(v_new.status, GEMM_OK, "sgemm_flat(prefill v_proj)")

        var qn = rmsnorm_fwd_flat(q.c, layers[layer].qn, n_prompt * h_q, d_head, eps)
        _check(qn.status, NORM_OK, "rmsnorm_fwd_flat(prefill q_norm)")
        var kn = rmsnorm_fwd_flat(k_new.c, layers[layer].kn, n_prompt * h_kv, d_head, eps)
        _check(kn.status, NORM_OK, "rmsnorm_fwd_flat(prefill k_norm)")

        var q_rot = rope_apply_flat(qn.y, rt.cos_table, rt.sin_table, n_prompt, h_q, d_head, prefill_positions, False)
        _check(q_rot.status, ATTN_OK, "rope_apply_flat(prefill q)")
        var k_rot = rope_apply_flat(kn.y, rt.cos_table, rt.sin_table, n_prompt, h_kv, d_head, prefill_positions, False)
        _check(k_rot.status, ATTN_OK, "rope_apply_flat(prefill k)")

        # Seed this layer's KV cache: append onto an empty cache, exactly the decode step's own
        # `kv_cache_append_flat` call, at cache_len=0 -- prefill and decode share the one growth path.
        var k_seeded = kv_cache_append_flat(cache_k[layer], k_rot.values, 0, n_prompt * h_kv * d_head)
        _check(k_seeded.status, LLMK_OK, "kv_cache_append_flat(prefill k)")
        var v_seeded = kv_cache_append_flat(cache_v[layer], v_new.c, 0, n_prompt * h_kv * d_head)
        _check(v_seeded.status, LLMK_OK, "kv_cache_append_flat(prefill v)")
        cache_k[layer] = k_seeded.out.copy()
        cache_v[layer] = v_seeded.out.copy()

        var attn = sdpa_forward_flat(
            q_rot.values, cache_k[layer], cache_v[layer], prefill_causal.bias,
            n_prompt, n_prompt, h_q, h_kv, d_head, scale, True
        )
        _check(attn.status, ATTN_OK, "sdpa_forward_flat(prefill)")

        var attn_proj = sgemm_flat(attn.out, layers[layer].o, n_prompt, d_model, h_q * d_head, 1.0, 0.0, False, False)
        _check(attn_proj.status, GEMM_OK, "sgemm_flat(prefill o_proj)")

        var resid1 = residual_add_flat(hidden, attn_proj.c, n_prompt * d_model)
        _check(resid1.status, LLMK_OK, "residual_add_flat(prefill post_attn)")
        hidden = resid1.out.copy()

        var normed2 = rmsnorm_fwd_flat(hidden, layers[layer].ln2, n_prompt, d_model, eps)
        _check(normed2.status, NORM_OK, "rmsnorm_fwd_flat(prefill post_attention_layernorm)")

        var gate = sgemm_flat(normed2.y, layers[layer].gate, n_prompt, d_ff, d_model, 1.0, 0.0, False, False)
        _check(gate.status, GEMM_OK, "sgemm_flat(prefill gate_proj)")
        var up = sgemm_flat(normed2.y, layers[layer].up, n_prompt, d_ff, d_model, 1.0, 0.0, False, False)
        _check(up.status, GEMM_OK, "sgemm_flat(prefill up_proj)")

        var act = gated_ffn_fwd_flat(up.c, gate.c, n_prompt, d_ff, MLP_ACT_SWIGLU)
        _check(act.status, MLP_OK, "gated_ffn_fwd_flat(prefill)")

        var down = sgemm_flat(act.y, layers[layer].down, n_prompt, d_model, d_ff, 1.0, 0.0, False, False)
        _check(down.status, GEMM_OK, "sgemm_flat(prefill down_proj)")

        var resid2 = residual_add_flat(hidden, down.c, n_prompt * d_model)
        _check(resid2.status, LLMK_OK, "residual_add_flat(prefill post_ffn)")
        hidden = resid2.out.copy()

    cache_len_tokens = n_prompt

    var prefill_normed = rmsnorm_fwd_flat(hidden, final_norm_w, n_prompt, d_model, eps)
    _check(prefill_normed.status, NORM_OK, "rmsnorm_fwd_flat(prefill final_norm)")
    var last_row = _row_slice(prefill_normed.y, n_prompt - 1, d_model)
    var prefill_logits = gemv_flat(embed_table, last_row, vocab_size, d_model, False)
    _check(prefill_logits.status, GEMM_OK, "gemv_flat(prefill lm_head)")
    var prefill_greedy = greedy_argmax_flat(prefill_logits.c, vocab_size)
    _check(prefill_greedy.status, LLMK_OK, "greedy_argmax_flat(prefill)")
    var tp1 = perf_counter_ns()

    generated_ids.append(prefill_greedy.token_id)
    per_step_ms.append(_ms(tp1 - tp0))
    per_step_logit.append(prefill_greedy.logit)
    print("  prefill: ", n_prompt, "tokens,", _ms(tp1 - tp0), "ms; first generated id=",
          prefill_greedy.token_id, "logit=", prefill_greedy.logit)
    if prefill_greedy.token_id == EOS_TOKEN_ID:
        stopped_on_eos = True

    # ═══ DECODE: one new token at a time, real KV cache, gemv_flat (decode-shaped), greedy ═══
    t_decode_start_ns = perf_counter_ns()
    var n_decoded = 1  # the prefill-produced token already counts as one generated token

    if not stopped_on_eos:
        for _step in range(1, N_NEW_MAX):
            var ts0 = perf_counter_ns()
            var pos = cache_len_tokens
            var new_token_id = generated_ids[len(generated_ids) - 1]
            var one_id = List[Int]()
            one_id.append(new_token_id)
            var one_pos = List[Int]()
            one_pos.append(pos)

            var embedded1 = embedding_fwd_flat(embed_table, one_id, 1, vocab_size, d_model)
            _check(embedded1.status, MLP_OK, "embedding_fwd_flat(decode)")
            var hidden1 = embedded1.y.copy()

            for layer in range(n_layers):

                var normed1 = rmsnorm_fwd_flat(hidden1, layers[layer].ln1, 1, d_model, eps)
                _check(normed1.status, NORM_OK, "rmsnorm_fwd_flat(decode input_layernorm)")

                var q1 = gemv_flat(layers[layer].q, normed1.y, d_model, h_q * d_head, True)
                _check(q1.status, GEMM_OK, "gemv_flat(decode q_proj)")
                var k1 = gemv_flat(layers[layer].k, normed1.y, d_model, h_kv * d_head, True)
                _check(k1.status, GEMM_OK, "gemv_flat(decode k_proj)")
                var v1 = gemv_flat(layers[layer].v, normed1.y, d_model, h_kv * d_head, True)
                _check(v1.status, GEMM_OK, "gemv_flat(decode v_proj)")

                var qn1 = rmsnorm_fwd_flat(q1.c, layers[layer].qn, h_q, d_head, eps)
                _check(qn1.status, NORM_OK, "rmsnorm_fwd_flat(decode q_norm)")
                var kn1 = rmsnorm_fwd_flat(k1.c, layers[layer].kn, h_kv, d_head, eps)
                _check(kn1.status, NORM_OK, "rmsnorm_fwd_flat(decode k_norm)")

                var q_rot1 = rope_apply_flat(qn1.y, rt.cos_table, rt.sin_table, 1, h_q, d_head, one_pos, False)
                _check(q_rot1.status, ATTN_OK, "rope_apply_flat(decode q)")
                var k_rot1 = rope_apply_flat(kn1.y, rt.cos_table, rt.sin_table, 1, h_kv, d_head, one_pos, False)
                _check(k_rot1.status, ATTN_OK, "rope_apply_flat(decode k)")

                var k_grown = kv_cache_append_flat(
                    cache_k[layer], k_rot1.values, cache_len_tokens * h_kv * d_head, h_kv * d_head
                )
                _check(k_grown.status, LLMK_OK, "kv_cache_append_flat(decode k)")
                var v_grown = kv_cache_append_flat(
                    cache_v[layer], v1.c, cache_len_tokens * h_kv * d_head, h_kv * d_head
                )
                _check(v_grown.status, LLMK_OK, "kv_cache_append_flat(decode v)")
                cache_k[layer] = k_grown.out.copy()
                cache_v[layer] = v_grown.out.copy()

                var total_k_tokens = cache_len_tokens + 1
                var decode_mask = mask_causal_flat(1, total_k_tokens, pos)
                _check(decode_mask.status, ATTN_OK, "mask_causal_flat(decode)")
                if decode_mask.n_masked != 0:
                    # A single query at the true current position sees every cached key by
                    # construction; a non-zero count here means the offset/cache bookkeeping is
                    # wrong, not that masking is doing real work -- fail loudly rather than generate
                    # silently-wrong tokens.
                    raise Error(
                        "qwen3_generate: decode mask masked " + String(decode_mask.n_masked) +
                        " keys at layer " + String(layer) + ", pos " + String(pos) +
                        " -- offset/cache-length bug"
                    )

                var attn1 = sdpa_forward_flat(
                    q_rot1.values, cache_k[layer], cache_v[layer], decode_mask.bias,
                    1, total_k_tokens, h_q, h_kv, d_head, scale, True
                )
                _check(attn1.status, ATTN_OK, "sdpa_forward_flat(decode)")

                var attn_proj1 = gemv_flat(layers[layer].o, attn1.out, h_q * d_head, d_model, True)
                _check(attn_proj1.status, GEMM_OK, "gemv_flat(decode o_proj)")

                var resid1a = residual_add_flat(hidden1, attn_proj1.c, d_model)
                _check(resid1a.status, LLMK_OK, "residual_add_flat(decode post_attn)")
                hidden1 = resid1a.out.copy()

                var normed2a = rmsnorm_fwd_flat(hidden1, layers[layer].ln2, 1, d_model, eps)
                _check(normed2a.status, NORM_OK, "rmsnorm_fwd_flat(decode post_attention_layernorm)")

                var gate1 = gemv_flat(layers[layer].gate, normed2a.y, d_model, d_ff, True)
                _check(gate1.status, GEMM_OK, "gemv_flat(decode gate_proj)")
                var up1 = gemv_flat(layers[layer].up, normed2a.y, d_model, d_ff, True)
                _check(up1.status, GEMM_OK, "gemv_flat(decode up_proj)")

                var act1 = gated_ffn_fwd_flat(up1.c, gate1.c, 1, d_ff, MLP_ACT_SWIGLU)
                _check(act1.status, MLP_OK, "gated_ffn_fwd_flat(decode)")

                var down1 = gemv_flat(layers[layer].down, act1.y, d_ff, d_model, True)
                _check(down1.status, GEMM_OK, "gemv_flat(decode down_proj)")

                var resid2a = residual_add_flat(hidden1, down1.c, d_model)
                _check(resid2a.status, LLMK_OK, "residual_add_flat(decode post_ffn)")
                hidden1 = resid2a.out.copy()

            cache_len_tokens += 1

            var final1 = rmsnorm_fwd_flat(hidden1, final_norm_w, 1, d_model, eps)
            _check(final1.status, NORM_OK, "rmsnorm_fwd_flat(decode final_norm)")
            var logits1 = gemv_flat(embed_table, final1.y, vocab_size, d_model, False)
            _check(logits1.status, GEMM_OK, "gemv_flat(decode lm_head)")
            var greedy1 = greedy_argmax_flat(logits1.c, vocab_size)
            _check(greedy1.status, LLMK_OK, "greedy_argmax_flat(decode)")

            var ts1 = perf_counter_ns()
            generated_ids.append(greedy1.token_id)
            per_step_ms.append(_ms(ts1 - ts0))
            per_step_logit.append(greedy1.logit)
            n_decoded += 1
            print("  decode step", _step, "pos=", pos, "-> id=", greedy1.token_id,
                  "logit=", greedy1.logit, _ms(ts1 - ts0), "ms")

            if greedy1.token_id == EOS_TOKEN_ID:
                stopped_on_eos = True
                break

    var t_wall_end = perf_counter_ns()
    var t_decode_end_ns = t_wall_end
    var decode_ms = _ms(t_decode_end_ns - t_decode_start_ns) if n_decoded > 1 else 0.0
    var decode_steps_after_prefill = n_decoded - 1

    print("qwen3_generate: done. stopped_on_eos=", stopped_on_eos)
    print("  total wall:", _ms(t_wall_end - t_wall_start), "ms (includes weight load + prefill + decode)")
    print("  generated", n_decoded, "new tokens (prefill's own first token included)")
    if decode_steps_after_prefill > 0:
        print("  decode-only (excludes weight load AND prefill):", decode_ms, "ms for",
              decode_steps_after_prefill, "steps ==",
              Float64(decode_steps_after_prefill) / (decode_ms / 1000.0), "tokens/sec")

    # ── dump the generated id sequence for the Python reference cross-check ─────
    # Columns: step_index absolute_position token_id logit step_ms
    var out_lines = String("n_prompt ") + String(n_prompt) + String("\n")
    out_lines += String("n_generated ") + String(n_decoded) + String("\n")
    out_lines += String("stopped_on_eos ") + (String("1") if stopped_on_eos else String("0")) + String("\n")
    for i in range(n_decoded):
        var step_ms = per_step_ms[i] if i < len(per_step_ms) else 0.0
        var step_logit = per_step_logit[i] if i < len(per_step_logit) else 0.0
        out_lines += String(i) + String(" ") + String(n_prompt + i) + String(" ") + \
            String(generated_ids[n_prompt + i]) + String(" ") + String(step_logit) + \
            String(" ") + String(step_ms) + String("\n")
    _write_text(OUT_DIR + "generated_ids.txt", out_lines)
    print("  generated ids written to", OUT_DIR + "generated_ids.txt")
