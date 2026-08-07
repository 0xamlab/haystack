"""metaldispatch.qwen3_prefill_decode — makes `_MBQwen3I8AllSimd7Prefill`'s batched-prefill Metal
GPU decode arm reachable from a real `pip install algenta` runtime, not only from a hand-run
benchmark driver.

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float, int
backend: mojo
surfaces: library_execute
golden_vectors: mojo/tests/libs/test_metaldispatch_session_prefill.mojo
benchmark: benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8_allsimd7_prefill.mojo
docs: gitbook/engine/qwen3-metal-decode.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Scope, stated precisely so nothing here overclaims -- IDENTICAL to `metaldispatch.qwen3_decode`'s
own scope statement (Qwen3-0.6B-Base, greedy decode, Apple Silicon Metal, refused by named status
rather than silently downgraded), with exactly one change: the prompt is processed by
`_MBQwen3I8AllSimd7Prefill.prefill_batch()` instead of a `for t in range(n_prompt): s.step(...)`
loop -- see `metaldispatch.session_prefill`'s own module docstring for what that struct adds over
`_MBQwen3I8AllSimd7` (which stays completely untouched; this file is new orchestration around a new,
additive kernel path, not a modification of the existing one).

Chunking: `prefill_batch()` itself is bounded to `metaldispatch.session_prefill.PREFILL_MAX_TILE`
rows per call (matching the KV cache's own default capacity). A prompt longer than that is processed
in multiple `prefill_batch()` calls, each writing the next `PREFILL_MAX_TILE`-row slice of the KV
cache at its own `pos_base` -- correctness of this chunking rests on EXACTLY the same cross-call
argument `metaldispatch.session_prefill`'s own module docstring makes for prefill-then-`step()`:
each call only ever depends on the KV cache and per-layer weights, which persist across calls on the
same struct instance, never on the PREVIOUS call's activation-buffer contents.

`max_ctx` is raised above `RESIDENT_DEFAULT_CONTEXT` (512) whenever `n_prompt + max_new_tokens`
would not fit in it, up to `RESIDENT_MAX_CONTEXT`'s own safety ceiling (65536) -- unlike
`qwen3_decode.qwen3_i8_allsimd7_decode_flat`, which always requests the default 512 regardless of
prompt length (never previously exercised past it, since that arm had no batched prefill fast
enough to make a long prompt practical to test at all).
"""

from std.math import sqrt
from std.sys import has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from residentk.contract import (
    RESIDENT_DEFAULT_CONTEXT,
    RESIDENT_MAX_CONTEXT,
    residentk_dispatch_budget_deep,
    residentk_splitk_should_split,
)
from metaldispatch.contract import (
    MB_ERR_CHECKPOINT_UNREADABLE,
    MB_ERR_DISPATCH_COUNT_MISMATCH,
    MB_ERR_NO_DEVICE,
    MB_ERR_SESSION_OPEN_FAILED,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_ERR_UNSUPPORTED_ARCHITECTURE,
    MB_OK,
    metaldispatch_dispatch_budget,
    metaldispatch_status_name,
)
from metaldispatch.session import _mb_preflight, MB_GPU_BUILD
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill, PREFILL_MAX_TILE

comptime QWEN3_0_6B_BASE_D_MODEL: Int = 1024
comptime QWEN3_0_6B_BASE_N_LAYERS: Int = 28
comptime QWEN3_0_6B_BASE_H_Q: Int = 16
comptime QWEN3_0_6B_BASE_H_KV: Int = 8
comptime QWEN3_0_6B_BASE_D_HEAD: Int = 128
comptime QWEN3_0_6B_BASE_D_FF: Int = 3072
comptime QWEN3_0_6B_BASE_VOCAB: Int = 151936
comptime QWEN3_0_6B_BASE_EOS_TOKEN_ID: Int = 151643


@fieldwise_init
struct Qwen3PrefillDecodeResult(Copyable, Movable):
    """Same shape as `qwen3_decode.Qwen3DecodeResult` -- see that struct's own docstring."""

    var status: Int
    var error_message: String
    var token_ids: List[Int]
    var n_prompt: Int
    var stopped_on_eos: Bool
    var dispatches_per_token: Int
    var decode_tokens_per_sec: Float64
    var prefill_tokens_per_sec: Float64
    var prefill_chunks: Int
    """How many `prefill_batch()` calls this run needed -- 1 for any prompt `<= PREFILL_MAX_TILE`
    (every prompt this arm has been raced against real opponents with, so far), `> 1` only once a
    prompt exceeds that ceiling."""


def _decode_err(status: Int, message: String) -> Qwen3PrefillDecodeResult:
    return Qwen3PrefillDecodeResult(status, message, List[Int](), 0, False, 0, 0.0, 0.0, 0)


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct _TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


def _tensor_loc(tensors_obj: String, name: String) raises -> _TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("metaldispatch.qwen3_prefill_decode: tensor not found in manifest: " + name)
    return _TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("metaldispatch.qwen3_prefill_decode: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _slice_ids(ids: List[Int], start: Int, count: Int) -> List[Int]:
    var out = List[Int](capacity=count)
    for i in range(count):
        out.append(ids[start + i])
    return out^


def qwen3_i8_allsimd7_prefill_decode_flat(
    checkpoint_dir: String, max_new_tokens: Int
) -> Qwen3PrefillDecodeResult:
    """Greedy-decode a prompt already folded into `checkpoint_dir/manifest.json`'s own `input_ids`,
    through `_MBQwen3I8AllSimd7Prefill` -- batched `prefill_batch()` for the prompt, then the
    byte-identical `step()` for every generated token. Same failure-mode contract as
    `qwen3_decode.qwen3_i8_allsimd7_decode_flat`: every failure is a returned `status`, never a crash
    and never a silently-wrong answer."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
    try:
        var config = json_get_object(manifest, "config")
        d_model = json_get_int(config, "hidden_size", -1)
        n_layers = json_get_int(config, "num_hidden_layers", -1)
        h_q = json_get_int(config, "num_attention_heads", -1)
        h_kv = json_get_int(config, "num_key_value_heads", -1)
        d_head = json_get_int(config, "head_dim", -1)
        d_ff = json_get_int(config, "intermediate_size", -1)
        vocab_size = json_get_int(config, "vocab_size", -1)
        theta = json_get_float(config, "rope_theta", -1.0)
        eps = json_get_float(config, "rms_norm_eps", -1.0)
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat runs ONLY"
            + " Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = metaldispatch_dispatch_budget(n_layers)
                if residentk_splitk_should_split(n_keys_last):
                    expected_budget = residentk_dispatch_budget_deep(n_layers)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )


def qwen3_i8_allsimd7_prefill_decode_flat_af(
    checkpoint_dir: String, max_new_tokens: Int, use_native_grouped_fa_attn: Bool
) -> Qwen3PrefillDecodeResult:
    """Attention Compiler Plan v1.0, Phase 2C: byte-for-byte the SAME orchestration as
    `qwen3_i8_allsimd7_prefill_decode_flat` above (copy-and-extend, this file's own established
    precedent for `_MBQwen3I8AllSimd7Prefill`'s own relationship to `_MBQwen3I8AllSimd7`), with
    exactly one addition: `s.use_native_grouped_fa_attn = use_native_grouped_fa_attn`, set once,
    immediately after construction, before any weight upload or dispatch. The ORIGINAL function
    above is left completely untouched -- every existing caller (every benchmark/production build
    that does not know this function exists) keeps running the exact code it always has; this is a
    new, additive entry point, not a modified one.

    DECODE-AFTER-AF-PREFILL GAP, CLOSED (see `_MBQwen3I8AllSimd7Prefill.prefill_batch`'s own docstring
    addendum, and `use_native_grouped_fa_attn`'s own field docstring, for the full account): this
    function used to carry a known, itemized scope limit -- when `use_native_grouped_fa_attn=True`,
    the natural-layout `ck`/`cv` KV cache `step()` (decode) reads was never populated for the
    prompt's own rows, so a `step()` call issued past the prompt read stale/uninitialized cache and
    produced garbage. `_MBQwen3I8AllSimd7Prefill`'s own AF descriptor table now ALSO double-writes
    `ck`/`cv` (via a second, additive dispatch of the byte-unmodified `_pf_ropewrt_kernel`) every
    `prefill_batch()` call made while the flag is `True` -- `step()` itself is unmodified and now
    finds those buffers correctly populated, so `max_new_tokens > 1` with `use_native_grouped_fa_
    attn=True` is no longer expected to produce wrong decode tokens for a SINGLE-CHUNK prompt (one
    `prefill_batch()` call, i.e. `n_prompt <= PREFILL_MAX_TILE` so the `while pos_base < n_prompt`
    loop below runs its body exactly once).

    PRECISELY WHAT REMAINS UNVERIFIED, stated so this is not overclaimed: this function's own
    MULTI-CHUNK prefill loop (`n_prompt > PREFILL_MAX_TILE`, several `prefill_batch(chunk_ids,
    pos_base)` calls with increasing `pos_base`, ALL with the flag on) followed by decode has not
    been exercised end-to-end -- `test_metaldispatch_session_prefill_af.mojo`'s Gate C (the test that
    proves the gap is closed) covers only a single `prefill_batch()` call at `pos_base=0` followed by
    `step()`. Treat multi-chunk AF prefill + decode as not yet certified until that scenario is
    separately tested through this exact entry point."""
    if max_new_tokens < 1:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "max_new_tokens must be >= 1, got " + String(max_new_tokens),
        )

    var manifest_path = checkpoint_dir + "/manifest.json"
    var blob_path = checkpoint_dir + "/weights.blob"

    var manifest: String
    try:
        manifest = _read_text_file(manifest_path)
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, "could not read " + manifest_path + ": " + String(e)
        )

    var d_model: Int
    var n_layers: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var vocab_size: Int
    var theta: Float64
    var eps: Float64
    var n_prompt: Int
    var tensors_obj: String
    var prompt_ids: List[Int]
    try:
        var config = json_get_object(manifest, "config")
        d_model = json_get_int(config, "hidden_size", -1)
        n_layers = json_get_int(config, "num_hidden_layers", -1)
        h_q = json_get_int(config, "num_attention_heads", -1)
        h_kv = json_get_int(config, "num_key_value_heads", -1)
        d_head = json_get_int(config, "head_dim", -1)
        d_ff = json_get_int(config, "intermediate_size", -1)
        vocab_size = json_get_int(config, "vocab_size", -1)
        theta = json_get_float(config, "rope_theta", -1.0)
        eps = json_get_float(config, "rms_norm_eps", -1.0)
        n_prompt = json_get_int(config, "n_tokens", -1)
        tensors_obj = json_get_object(manifest, "tensors")

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
    except e:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " did not parse: " + String(e)
        )

    if (
        d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
        or vocab_size < 1 or n_prompt < 1 or theta <= 0.0 or eps <= 0.0
    ):
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE, manifest_path + " is missing a required config field"
        )
    if len(prompt_ids) != n_prompt:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            manifest_path + " declares n_tokens=" + String(n_prompt) + " but input_ids has "
            + String(len(prompt_ids)) + " entries",
        )

    if (
        d_model != QWEN3_0_6B_BASE_D_MODEL or n_layers != QWEN3_0_6B_BASE_N_LAYERS
        or h_q != QWEN3_0_6B_BASE_H_Q or h_kv != QWEN3_0_6B_BASE_H_KV
        or d_head != QWEN3_0_6B_BASE_D_HEAD or d_ff != QWEN3_0_6B_BASE_D_FF
        or vocab_size != QWEN3_0_6B_BASE_VOCAB
    ):
        return _decode_err(
            MB_ERR_UNSUPPORTED_ARCHITECTURE,
            "unsupported model architecture: qwen3_i8_allsimd7_prefill_decode_flat_af runs ONLY"
            + " Qwen3-0.6B-Base's exact shape (hidden_size=" + String(QWEN3_0_6B_BASE_D_MODEL)
            + ", num_hidden_layers=" + String(QWEN3_0_6B_BASE_N_LAYERS)
            + ", num_attention_heads=" + String(QWEN3_0_6B_BASE_H_Q)
            + ", num_key_value_heads=" + String(QWEN3_0_6B_BASE_H_KV)
            + ", head_dim=" + String(QWEN3_0_6B_BASE_D_HEAD)
            + ", intermediate_size=" + String(QWEN3_0_6B_BASE_D_FF)
            + ", vocab_size=" + String(QWEN3_0_6B_BASE_VOCAB)
            + "); this checkpoint declares hidden_size=" + String(d_model)
            + ", num_hidden_layers=" + String(n_layers)
            + ", num_attention_heads=" + String(h_q)
            + ", num_key_value_heads=" + String(h_kv)
            + ", head_dim=" + String(d_head)
            + ", intermediate_size=" + String(d_ff)
            + ", vocab_size=" + String(vocab_size),
        )

    var scale = 1.0 / sqrt(Float64(d_head))
    var needed_ctx = n_prompt + max_new_tokens
    var max_ctx = RESIDENT_DEFAULT_CONTEXT
    if needed_ctx > max_ctx:
        max_ctx = needed_ctx
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return _decode_err(
            MB_ERR_CHECKPOINT_UNREADABLE,
            "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
            + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
            + String(RESIDENT_MAX_CONTEXT),
        )
    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps, scale
    )
    if pre != MB_OK:
        return _decode_err(pre, "preflight refused this run: " + metaldispatch_status_name(pre))

    @parameter
    if not MB_GPU_BUILD:
        return _decode_err(
            MB_ERR_SHADER_TOOLCHAIN_ABSENT,
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU prefill+decode is "
            + "compiled out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7Prefill(
                d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
            )
            # ── the ONE addition over `qwen3_i8_allsimd7_prefill_decode_flat` above -- see this
            # function's own docstring for the full, honest scope-limit account.
            s.use_native_grouped_fa_attn = use_native_grouped_fa_attn

            var rt = rope_table(d_head, max_ctx, theta)
            var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
            var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")

            var up_status = s.upload_globals(
                embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
            )
            if up_status != MB_OK:
                return _decode_err(
                    up_status, "upload_globals failed: " + metaldispatch_status_name(up_status)
                )

            for layer in range(n_layers):
                var prefix = "model.layers." + String(layer) + "."
                var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                var ln2 = _load_tensor(
                    blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                )
                var qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                var kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                var wq = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_proj.weight")
                var wk = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_proj.weight")
                var wv = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.v_proj.weight")
                var wo = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.o_proj.weight")
                var wg = _load_tensor(blob_path, tensors_obj, prefix + "mlp.gate_proj.weight")
                var wu = _load_tensor(blob_path, tensors_obj, prefix + "mlp.up_proj.weight")
                var wd = _load_tensor(blob_path, tensors_obj, prefix + "mlp.down_proj.weight")
                var layer_status = s.upload_layer(
                    layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd
                )
                if layer_status != MB_OK:
                    return _decode_err(
                        layer_status,
                        "upload_layer " + String(layer) + " failed: "
                        + metaldispatch_status_name(layer_status),
                    )

            _ = s.seal()

            var generated_ids = List[Int]()
            for i in range(n_prompt):
                generated_ids.append(prompt_ids[i])

            var first_tok = -1
            var n_chunks = 0
            var t_prefill_start = perf_counter_ns()
            var pos_base = 0
            while pos_base < n_prompt:
                var chunk_len = PREFILL_MAX_TILE
                if n_prompt - pos_base < chunk_len:
                    chunk_len = n_prompt - pos_base
                var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                var r = s.prefill_batch(chunk_ids, pos_base)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "prefill_batch(pos_base=" + String(pos_base) + ", m_rows="
                        + String(chunk_len) + ") failed: " + metaldispatch_status_name(r.status),
                    )
                first_tok = r.token_id
                n_chunks += 1
                pos_base += chunk_len
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1
            var dispatches_per_token = 0

            var t_decode_start = perf_counter_ns()
            if not stopped_on_eos:
                for step in range(1, max_new_tokens):
                    var pos = n_prompt + step - 1
                    var r2 = s.step(generated_ids[len(generated_ids) - 1], pos)
                    if r2.status != MB_OK:
                        return _decode_err(
                            r2.status,
                            "step(decode pos " + String(pos) + ") failed: "
                            + metaldispatch_status_name(r2.status),
                        )
                    dispatches_per_token = r2.dispatches
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            if dispatches_per_token != 0:
                var n_keys_last = n_prompt + (n_decoded - 1)
                var expected_budget = metaldispatch_dispatch_budget(n_layers)
                if residentk_splitk_should_split(n_keys_last):
                    expected_budget = residentk_dispatch_budget_deep(n_layers)
                if dispatches_per_token != expected_budget:
                    return _decode_err(
                        MB_ERR_DISPATCH_COUNT_MISMATCH,
                        "the session issued " + String(dispatches_per_token) + " dispatches but "
                        + "the expected decode budget says " + String(expected_budget)
                        + " -- the design and the code disagree",
                    )

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3PrefillDecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec, n_chunks
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )
