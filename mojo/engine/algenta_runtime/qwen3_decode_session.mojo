"""
algenta_runtime.qwen3_decode_session — resident, step-by-step Qwen3 GPU decode sessions.

Why
---
`metaldispatch.qwen3_prefill_decode`'s `qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3` (what
`algenta.inference.decode()` actually calls today -- see the correction below) generates every
token of a `max_new_tokens` request inside ONE `library_execute` call: the whole prefill+decode
loop runs to completion before the caller sees a single token back. A caller that wants tokens as
they are produced (a streaming UI, an early-stop policy, a token budget the caller wants to watch
tick down) has no way to get that from a one-shot call.

Track C3 correction (read this before touching `_MBQwen3I8AllSimd7`): the design note this module
was commissioned against named `_MBQwen3I8AllSimd7` (`metaldispatch.session`, used by the OLDER,
narrower `metaldispatch.qwen3_decode` one-shot entry point) as the struct backing BOTH one-shot
entry points. Direct source reading during this change found that claim wrong: the ACTUAL struct
`qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3` uses is `_MBQwen3I8AllSimd7Prefill`
(`metaldispatch.session_prefill`), a separate, later struct with its own resolved-execution-plan
machinery (`resolve_plan`/`UnresolvedPrefillConfig`), batched `prefill_batch()`, and a global
resident-buffer cache (`metaldispatch.ffi`'s `_mb_get_resident_key`/`_mb_free_all_buffers` pair).
`metaldispatch.qwen3_prefill_decode.mojo`'s own module docstring (line ~26) already says as much:
"`_MBQwen3I8AllSimd7` ... stays completely untouched; this file is new orchestration around a new,
additive kernel path, not a modification of the existing one." This module therefore mirrors
`qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3`'s init/upload/prefill sequence byte-for-byte
(the private helpers below are IMPORTED from that file, not re-derived), so the byte-identical-
token proof this feature exists for (comparing against the real, unmodified `decode()`) is actually
comparing against the code path that runs.

Scope, stated precisely so nothing here overclaims
----------------------------------------------------
* GREEDY DECODE ONLY (temperature=0's code path). The sampled path
  (`qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3_sampled`) carries its own per-call RNG state
  and running penalty counts across a fresh vocabulary draw every step -- a materially different
  state machine to stream correctly, and out of scope for this change. `algenta.inference.
  decode_stream()` (the Python caller of this module) refuses `temperature > 0` accordingly.
* AT MOST ONE OPEN SESSION AT A TIME, per connection. `_MBQwen3I8AllSimd7Prefill` construction
  allocates a fresh set of GPU buffers every time it is NOT explicitly told to adopt an existing
  resident set (`metaldispatch.ffi._mb_begin_adopt`/`_mb_end_adopt`); this module never adopts (see
  next bullet), so `open_from_json` unconditionally frees whatever is resident before allocating.
  Freeing out from under a session the caller still believes is open would leave that session's
  struct holding dangling device pointers -- refused outright instead: `open_from_json` on a
  connection that already has an open session returns `qwen3_session_already_open` rather than
  silently tearing down a live session. This is an honest reflection of the underlying hardware
  layer's own design (one resident model's weights at a time, process-wide), not a limitation this
  module invents.
* NO cross-session resident-buffer reuse, and no `weights_i8.cache` disk-cache read/write.
  `qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3` skips re-quantizing weights when the SAME
  resident key is still current (parity gap 4) or a valid on-disk quantized-state cache exists
  (parity cheap wins); this module always takes the cold, f64-read-plus-quantize path, on every
  `open_from_json` call, identical to what a completely fresh worker process would do on its FIRST
  call for a given checkpoint. Purely a performance difference from the one-shot path (every
  `open_from_json` pays the full upload cost the one-shot path only pays once per resident model
  switch) -- never a correctness one: the resident-key cache and the quantized-state cache are both
  optimizations that skip re-doing work whose RESULT is unchanged, so skipping them here changes
  nothing about which tokens come out. A follow-up can wire adoption in once this simpler,
  exhaustively-verified baseline is landed.
* `warmup_prefills` (a benchmark-timing knob on the one-shot entry point, always 0 in real serving
  -- `algenta.inference.decode()`'s own default) is not exposed here at all.

Lifetime
--------
Sessions live for the connection, exactly like `algenta_runtime.session.ResidentDatasets` and
`algenta_runtime.stream.ResidentStreams`: the registry is created inside `run_server_loop` and
dropped when the loop exits, so a handle can never outlive the connection that opened it. Unlike
those two registries, closing a session here also releases real GPU state (`_mb_free_all_buffers`)
rather than only discarding a bookkeeping entry -- see `close_from_json`.

Wire format
-----------
    {"type":"qwen3_decode_open","checkpoint_dir":"/path/to/converted","prompt_token_ids":[1,2,3],
     "max_new_tokens":16}
      -> {"session":"qd_1","n_prompt":3,"max_new_tokens":16,"open_count":1}

    {"type":"qwen3_decode_next","session":"qd_1"}
      -> {"token_id":42,"position":4,"done":false,"stopped_on_eos":false,"dispatches":171}

    {"type":"qwen3_decode_close","session":"qd_1"} -> {"closed":true,"count":0}

`done` is true on the response that delivers the LAST token this session will ever produce (either
`max_new_tokens` was reached or the token was the checkpoint's own EOS id) -- a caller loops
`qwen3_decode_next` until `done`, exactly like `stream_next`'s own convention. A `qwen3_decode_next`
call made AFTER `done` was already returned once is answered idempotently (the same last token,
`done:true` again), never by advancing the session further -- mirroring `stream_next`'s own
past-the-end behavior. `checkpoint_dir` must already be the CONVERTED directory (`manifest.json` +
`weights.blob`, `algenta.qwen3_decode.prepare_checkpoint`/`algenta.inference.
prepare_model_checkpoint`'s output format) -- this module never reads a raw HuggingFace snapshot,
matching every other entry point over this kernel family. `prompt_token_ids` is required and always
used (this module has no "baked into the manifest" fallback -- unlike the one-shot entry point,
there is no ambiguity to preserve here: a streaming caller always has its own tokenized prompt in
hand before it opens a session).

A stale or unknown `session` handle on `qwen3_decode_next`/`qwen3_decode_close` fails cleanly with
`qwen3_session_not_found`, never a crash -- same contract as `stream_next`'s `cursor_not_found` /
`dataset_open`'s `dataset_not_found`.
"""
from std.math import sqrt
from std.sys import has_accelerator
from json.parser import (
    json_array_tokens,
    json_get_array,
    json_get_bool,
    json_get_float,
    json_get_int,
    json_get_object,
    json_get_string,
)
from conv import parse_int
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_MAX_CONTEXT,
    RESIDENT_OK,
    RESIDENT_ERR_CODE_OUT_OF_RANGE,
    residentk_status_name,
)
from metaldispatch.contract import (
    MB_ERR_CHECKPOINT_UNREADABLE,
    MB_ERR_DISPATCH_COUNT_MISMATCH,
    MB_ERR_NO_DEVICE,
    MB_ERR_SESSION_OPEN_FAILED,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_ERR_UNSUPPORTED_ARCHITECTURE,
    MB_OK,
    metaldispatch_status_name,
)
from metaldispatch.session import _mb_preflight, MB_GPU_BUILD
from metaldispatch.ffi import _mb_free_all_buffers
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill, PREFILL_MAX_TILE
from metaldispatch.session_prefill_policy import (
    PF_ATTN_OFF,
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_GEMM_ORIGINAL,
    PF_GEMM_VECLOAD4_ALL_ROLES,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    UnresolvedPrefillConfig,
)
# Reused, not re-derived (rule 3): the exact private helpers
# `qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3` itself calls for manifest/tensor IO, context
# sizing, and prompt-chunk slicing. `metaldispatch.qwen3_prefill_decode` stays completely untouched
# by this import -- Mojo has no access-control keyword, and cross-file underscore imports are an
# established pattern in this codebase (e.g. `optimization.routing` imports `optimization.model
# ._ceil_f`; `residentk.kernels_packed3` imports `residentk.kernels._TG`).
from metaldispatch.qwen3_prefill_decode import (
    _load_tensor,
    _read_text_file,
    _resident_ctx_bucket,
    _rope_table_from_manifest,
    _slice_ids,
)


def _qwen3_session_error(code: String, message: String) -> String:
    return (
        '{"error":"'
        + code
        + ": "
        + message
        + '","error_code":"'
        + code
        + '","error_message":"'
        + message
        + '"}'
    )


struct Qwen3DecodeSessions(Movable):
    """Connection-scoped registry of open, post-prefill `_MBQwen3I8AllSimd7Prefill` instances,
    keyed by opaque handle -- the `open`/`next`(-repeated)/`close` shape `ResidentStreams` already
    proves over this wire protocol, applied to a resident decode session instead of a stream
    cursor. At most one entry is ever live at once (see module docstring); the registry is still
    handle-keyed (not a single optional slot) so the wire contract has room for real concurrent
    residency later without another protocol change -- only `open_from_json`'s single-entry guard
    would need to move.
    """

    var handles: List[String]
    var sessions: List[_MBQwen3I8AllSimd7Prefill]
    var n_prompts: List[Int]
    var max_new_tokens_list: List[Int]
    var eos_token_ids: List[Int]
    # Prompt tokens followed by every token generated SO FAR on this session (grows one element per
    # `next_from_json` call that actually advances the session). Position 0 is never removed, so
    # `generated_ids_list[i][n_prompts[i] + k]` is always the k-th generated token.
    var generated_ids_list: List[List[Int]]
    # How many of `generated_ids_list[i]`'s post-prompt tokens have been RETURNED to the caller.
    # The prefill phase already computes the first generated token as a side effect (same as the
    # one-shot entry point's own `first_tok`); `delivered_list[i] == 0` means that token is
    # computed but not yet handed back, so the first `next_from_json` call delivers it without
    # calling `.step()` at all -- exactly one `.step()` call per generated token from the SECOND
    # `next_from_json` call onward, matching the one-shot loop's own `for step in range(1,
    # max_new_tokens)` bound precisely.
    var delivered_list: List[Int]
    # True once a `qwen3_decode_next` response has returned this session's LAST token (max_new_tokens
    # reached, or EOS). Further `next_from_json` calls on this handle answer idempotently instead of
    # calling `.step()` again -- calling it again would decode past the caller's own budget and
    # mutate the KV cache for positions the caller never asked for.
    var done_list: List[Bool]
    var next_id: Int

    def __init__(out self):
        self.handles = List[String]()
        self.sessions = List[_MBQwen3I8AllSimd7Prefill]()
        self.n_prompts = List[Int]()
        self.max_new_tokens_list = List[Int]()
        self.eos_token_ids = List[Int]()
        self.generated_ids_list = List[List[Int]]()
        self.delivered_list = List[Int]()
        self.done_list = List[Bool]()
        self.next_id = 1

    def count(self) -> Int:
        return len(self.handles)

    def _index_of(self, handle: String) -> Int:
        for i in range(len(self.handles)):
            if self.handles[i] == handle:
                return i
        return -1

    def open_from_json(mut self, raw: String) raises -> String:
        if self.count() > 0:
            return _qwen3_session_error(
                "qwen3_session_already_open",
                "a qwen3 decode session (" + self.handles[0] + ") is already open on this"
                + " connection; close it before opening another.",
            )

        var checkpoint_dir = json_get_string(raw, "checkpoint_dir")
        if checkpoint_dir.byte_length() == 0:
            return _qwen3_session_error(
                "invalid_arguments", "qwen3_decode_open requires checkpoint_dir."
            )

        var prompt_arr = json_get_array(raw, "prompt_token_ids")
        if prompt_arr.byte_length() == 0:
            return _qwen3_session_error(
                "invalid_arguments",
                "qwen3_decode_open requires a non-empty prompt_token_ids array.",
            )

        var max_new_tokens = json_get_int(raw, "max_new_tokens", 0)
        if max_new_tokens < 1:
            return _qwen3_session_error(
                "invalid_arguments", "qwen3_decode_open requires max_new_tokens >= 1."
            )

        # Defaults match `algenta.inference.decode()`'s own greedy-path defaults, so a caller that
        # omits these gets the SAME resolved plan decode() would resolve for an equivalent call.
        var use_nomirror = json_get_bool(raw, "use_native_grouped_fa_attn_no_mirror", True)
        var use_msl = json_get_bool(raw, "use_msl_parity_all_roles", True)

        var prompt_ids: List[Int]
        try:
            var id_tokens = json_array_tokens(prompt_arr)
            prompt_ids = List[Int](capacity=len(id_tokens))
            for i in range(len(id_tokens)):
                prompt_ids.append(parse_int(id_tokens[i]))
        except e:
            return _qwen3_session_error(
                "invalid_arguments", "prompt_token_ids did not parse: " + String(e)
            )
        if len(prompt_ids) == 0:
            return _qwen3_session_error(
                "invalid_arguments",
                "qwen3_decode_open requires a non-empty prompt_token_ids array.",
            )

        var manifest_path = checkpoint_dir + "/manifest.json"
        var blob_path = checkpoint_dir + "/weights.blob"
        var manifest: String
        try:
            manifest = _read_text_file(manifest_path)
        except e:
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_CHECKPOINT_UNREADABLE),
                "could not read " + manifest_path + ": " + String(e),
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
        var has_qk_norm: Int
        var tied_embeddings: Int
        var eos_token_id: Int
        var tensors_obj: String
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
            has_qk_norm = json_get_int(config, "has_qk_norm", 1)
            tied_embeddings = json_get_int(config, "tie_word_embeddings", 1)
            eos_token_id = json_get_int(config, "eos_token_id", -1)
            tensors_obj = json_get_object(manifest, "tensors")
        except e:
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_CHECKPOINT_UNREADABLE),
                manifest_path + " did not parse: " + String(e),
            )

        if (
            d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1
            or vocab_size < 1 or theta <= 0.0 or eps <= 0.0
        ):
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_CHECKPOINT_UNREADABLE),
                manifest_path + " is missing a required config field",
            )
        if (has_qk_norm != 0 and has_qk_norm != 1) or (
            tied_embeddings != 0 and tied_embeddings != 1
        ):
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_CHECKPOINT_UNREADABLE),
                manifest_path + " carries a convention flag (has_qk_norm/tie_word_embeddings)"
                + " that is neither 0 nor 1",
            )
        if eos_token_id < -1 or eos_token_id >= vocab_size:
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_CHECKPOINT_UNREADABLE),
                manifest_path + " declares eos_token_id=" + String(eos_token_id)
                + " outside the vocab [0, " + String(vocab_size) + ")",
            )
        # Model-agnostic structural gates, byte-for-byte
        # `qwen3_prefill_decode_flat_af_nomirror_msl_anyqwen3`'s own (GQA divisibility + GEMM tile
        # alignment) -- see that function for why these degrade gracefully per-role rather than
        # needing to be exact-shape-pinned like the OLDER one-shot entry point.
        if (h_q % h_kv) != 0:
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_UNSUPPORTED_ARCHITECTURE),
                "model-agnostic prefill requires num_attention_heads % num_key_value_heads == 0"
                + " (GQA); got " + String(h_q) + " % " + String(h_kv),
            )
        if (d_model % 32) != 0 or (d_ff % 32) != 0 or ((h_q * d_head) % 32) != 0:
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_UNSUPPORTED_ARCHITECTURE),
                "model-agnostic prefill requires d_model, d_ff, and n_q=h_q*d_head all divisible"
                + " by 32 (GEMM tile alignment); got d_model=" + String(d_model) + " d_ff="
                + String(d_ff) + " n_q=" + String(h_q * d_head),
            )

        var n_prompt = len(prompt_ids)
        var scale = 1.0 / sqrt(Float64(d_head))
        var needed_ctx = n_prompt + max_new_tokens
        var max_ctx = _resident_ctx_bucket(needed_ctx)
        if max_ctx > RESIDENT_MAX_CONTEXT:
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_CHECKPOINT_UNREADABLE),
                "n_prompt=" + String(n_prompt) + " + max_new_tokens=" + String(max_new_tokens)
                + " needs max_ctx=" + String(needed_ctx) + ", past RESIDENT_MAX_CONTEXT="
                + String(RESIDENT_MAX_CONTEXT),
            )

        var pre = _mb_preflight(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, max_new_tokens, max_ctx, eps,
            scale,
        )
        if pre != MB_OK:
            # _mb_preflight returns codes from TWO namespaces: residentk.contract's
            # RESIDENT_OK..RESIDENT_ERR_CODE_OUT_OF_RANGE (600-610, from the shape/context
            # checks it reuses) or metaldispatch.contract's own MB_* codes (from its later,
            # own checks) -- metaldispatch_status_name only recognizes the latter and falls
            # back to a useless "code_out_of_range" for the former, which is exactly the
            # unhelpful error a too-large model's dims produced before this fix. Route by
            # range, not by blindly picking one status-name function.
            var status_name: String
            if pre >= RESIDENT_OK and pre <= RESIDENT_ERR_CODE_OUT_OF_RANGE:
                status_name = residentk_status_name(pre)
            else:
                status_name = metaldispatch_status_name(pre)
            return _qwen3_session_error(status_name, "preflight refused this run")

        @parameter
        if not MB_GPU_BUILD:
            return _qwen3_session_error(
                metaldispatch_status_name(MB_ERR_SHADER_TOOLCHAIN_ABSENT),
                "this runtime worker was built without -D ALGENTA_GPU -D ALGENTA_METAL; Qwen3"
                + " GPU decode is compiled out of this binary",
            )
        else:
            if not has_accelerator():
                return _qwen3_session_error(
                    metaldispatch_status_name(MB_ERR_NO_DEVICE),
                    "no Metal accelerator was detected on this host",
                )

            try:
                # Always-fresh policy (see module docstring's "NO cross-session resident-buffer
                # reuse" bullet): never adopt a previous call's buffers. Safe unconditionally --
                # the single-open-session guard above already ensures nothing this connection
                # still considers open is resident right now.
                _mb_free_all_buffers()

                var s = _MBQwen3I8AllSimd7Prefill(
                    d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale,
                    UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL),
                    has_qk_norm, tied_embeddings,
                )
                s.resolve_plan(UnresolvedPrefillConfig(
                    PF_ATTN_GROUPED_FA_NO_MIRROR if use_nomirror else PF_ATTN_OFF,
                    PF_GEMM_MSL_PARITY_ALL_ROLES if use_msl else PF_GEMM_VECLOAD4_ALL_ROLES,
                ))

                var rt = _rope_table_from_manifest(manifest, d_head, max_ctx, theta)
                if rt.status != ATTN_OK:
                    return _qwen3_session_error(
                        metaldispatch_status_name(MB_ERR_CHECKPOINT_UNREADABLE),
                        "the manifest's rope_scaling is unusable",
                    )

                var embed_table = _load_tensor(blob_path, tensors_obj, "model.embed_tokens.weight")
                var final_norm_w = _load_tensor(blob_path, tensors_obj, "model.norm.weight")
                var up_status = s.upload_globals(
                    embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx
                )
                if up_status != MB_OK:
                    return _qwen3_session_error(
                        metaldispatch_status_name(up_status), "upload_globals failed"
                    )

                if tied_embeddings == 0:
                    var lm_head_table = _load_tensor(blob_path, tensors_obj, "lm_head.weight")
                    var lm_status = s.upload_lm_head(lm_head_table)
                    if lm_status != MB_OK:
                        return _qwen3_session_error(
                            metaldispatch_status_name(lm_status), "upload_lm_head failed"
                        )

                for layer in range(n_layers):
                    var prefix = "model.layers." + String(layer) + "."
                    var ln1 = _load_tensor(blob_path, tensors_obj, prefix + "input_layernorm.weight")
                    var ln2 = _load_tensor(
                        blob_path, tensors_obj, prefix + "post_attention_layernorm.weight"
                    )
                    var qn = List[Float64]()
                    var kn = List[Float64]()
                    if has_qk_norm == 1:
                        qn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.q_norm.weight")
                        kn = _load_tensor(blob_path, tensors_obj, prefix + "self_attn.k_norm.weight")
                    else:
                        for _i in range(d_head):
                            qn.append(1.0)
                            kn.append(1.0)
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
                        return _qwen3_session_error(
                            metaldispatch_status_name(layer_status),
                            "upload_layer " + String(layer) + " failed",
                        )

                _ = s.seal()

                var generated_ids = List[Int](capacity=n_prompt + max_new_tokens)
                for i in range(n_prompt):
                    generated_ids.append(prompt_ids[i])

                var first_tok = -1
                var pos_base = 0
                while pos_base < n_prompt:
                    var chunk_len = PREFILL_MAX_TILE
                    if n_prompt - pos_base < chunk_len:
                        chunk_len = n_prompt - pos_base
                    var chunk_ids = _slice_ids(prompt_ids, pos_base, chunk_len)
                    var r = s.prefill_batch(chunk_ids, pos_base)
                    if r.status != MB_OK:
                        return _qwen3_session_error(
                            metaldispatch_status_name(r.status),
                            "prefill_batch(pos_base=" + String(pos_base) + ") failed",
                        )
                    first_tok = r.token_id
                    pos_base += chunk_len

                generated_ids.append(first_tok)

                var handle = "qd_" + String(self.next_id)
                self.next_id += 1
                self.handles.append(handle)
                self.sessions.append(s^)
                self.n_prompts.append(n_prompt)
                self.max_new_tokens_list.append(max_new_tokens)
                self.eos_token_ids.append(eos_token_id)
                self.generated_ids_list.append(generated_ids^)
                self.delivered_list.append(0)
                self.done_list.append(False)

                return (
                    '{"session":"' + handle + '","n_prompt":' + String(n_prompt)
                    + ',"max_new_tokens":' + String(max_new_tokens)
                    + ',"open_count":' + String(self.count()) + "}"
                )
            except e:
                return _qwen3_session_error(
                    metaldispatch_status_name(MB_ERR_SESSION_OPEN_FAILED),
                    "metaldispatch session error: " + String(e),
                )

    def next_from_json(mut self, raw: String) raises -> String:
        var handle = json_get_string(raw, "session")
        if handle.byte_length() == 0:
            return _qwen3_session_error(
                "invalid_arguments", "qwen3_decode_next requires a session."
            )
        var index = self._index_of(handle)
        if index < 0:
            return _qwen3_session_error(
                "qwen3_session_not_found", "no open qwen3 decode session " + handle + "."
            )

        var eos_id = self.eos_token_ids[index]

        if self.done_list[index]:
            # Idempotent past-the-end pull -- mirrors `stream_next`'s own behavior once a cursor
            # has already been drained: answer with the same last token again, never advance.
            ref gi_done = self.generated_ids_list[index]
            var last_tok_done = gi_done[len(gi_done) - 1]
            return (
                '{"token_id":' + String(last_tok_done)
                + ',"position":' + String(len(gi_done))
                + ',"done":true,"stopped_on_eos":'
                + ("true" if (eos_id >= 0 and last_tok_done == eos_id) else "false")
                + ',"dispatches":0}'
            )

        var n_prompt = self.n_prompts[index]
        var max_new = self.max_new_tokens_list[index]
        var delivered = self.delivered_list[index]

        var tok: Int
        var dispatches = 0
        var already_buffered = delivered < (len(self.generated_ids_list[index]) - n_prompt)
        if already_buffered:
            # The prefill phase already computed this token (the first generated token, always
            # index 0) -- deliver it without calling `.step()` at all.
            tok = self.generated_ids_list[index][n_prompt + delivered]
        else:
            var pos = n_prompt + delivered - 1
            try:
                ref s = self.sessions[index]
                ref gi = self.generated_ids_list[index]
                var last_tok = gi[len(gi) - 1]
                var r = s.step(last_tok, pos)
                if r.status != MB_OK:
                    return _qwen3_session_error(
                        metaldispatch_status_name(r.status),
                        "step(pos=" + String(pos) + ") failed",
                    )
                var n_keys = pos + 1
                var expected_budget = s.expected_decode_dispatch_count(n_keys)
                if r.dispatches != expected_budget:
                    return _qwen3_session_error(
                        metaldispatch_status_name(MB_ERR_DISPATCH_COUNT_MISMATCH),
                        "the session issued " + String(r.dispatches) + " dispatches but the"
                        + " expected decode budget at n_keys=" + String(n_keys) + " says "
                        + String(expected_budget) + " -- the design and the code disagree",
                    )
                tok = r.token_id
                dispatches = r.dispatches
                gi.append(tok)
            except e:
                return _qwen3_session_error(
                    metaldispatch_status_name(MB_ERR_SESSION_OPEN_FAILED),
                    "metaldispatch session error: " + String(e),
                )

        delivered += 1
        self.delivered_list[index] = delivered
        var is_eos = eos_id >= 0 and tok == eos_id
        var is_done = is_eos or delivered >= max_new
        self.done_list[index] = is_done

        return (
            '{"token_id":' + String(tok)
            + ',"position":' + String(n_prompt + delivered)
            + ',"done":' + ("true" if is_done else "false")
            + ',"stopped_on_eos":' + ("true" if is_eos else "false")
            + ',"dispatches":' + String(dispatches) + "}"
        )

    def close_from_json(mut self, raw: String) -> String:
        var handle = json_get_string(raw, "session")
        if handle.byte_length() == 0:
            return _qwen3_session_error(
                "invalid_arguments", "qwen3_decode_close requires a session."
            )
        var index = self._index_of(handle)
        if index < 0:
            return _qwen3_session_error(
                "qwen3_session_not_found", "no open qwen3 decode session " + handle + "."
            )

        # Real release, unlike `dataset_close`/`stream_close` (which only ever discard bookkeeping
        # over data owned by a SEPARATE registry): this handle's struct instance is the ONLY owner
        # of its GPU buffers, so closing it must actually free them -- safe unconditionally because
        # `open_from_json`'s single-open-session guard means this is always the one and only
        # resident session on this connection at the moment it closes.
        #
        # `@parameter if MB_GPU_BUILD` gate, matching every other `_mb_free_all_buffers()` call
        # site in this kernel family (`metaldispatch.qwen3_prefill_decode`, `metaldispatch.session`):
        # `_mb_free_all_buffers`'s `external_call["algenta_free_all_buffers", ...]` only resolves
        # when the Objective-C Metal shim was compiled and linked in (`MOJO_BUILD_METAL_GPU=1`) --
        # an unconditional call here is a LINK-TIME failure on every non-Metal build of main.mojo
        # (undefined reference to `algenta_free_all_buffers`), including the plain `mojo_build/
        # simulate` CPU binary CI builds elsewhere in this repo, not just a runtime one. Behaviorally
        # a no-op either way: on a non-GPU build, `open_from_json` always refuses before ever adding
        # a handle to this registry, so `index` (found just above) can never be reached on that build
        # in the first place -- this gate only fixes the link, it changes no reachable behavior.
        @parameter
        if MB_GPU_BUILD:
            _mb_free_all_buffers()
        _ = self.sessions.pop(index)
        _ = self.handles.pop(index)
        _ = self.n_prompts.pop(index)
        _ = self.max_new_tokens_list.pop(index)
        _ = self.eos_token_ids.pop(index)
        _ = self.generated_ids_list.pop(index)
        _ = self.delivered_list.pop(index)
        _ = self.done_list.pop(index)

        return '{"closed":true,"count":' + String(self.count()) + "}"
