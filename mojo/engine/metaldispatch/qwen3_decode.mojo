"""metaldispatch.qwen3_decode — makes `_MBQwen3I8AllSimd7`'s int8 Metal GPU decode arm reachable
from a real `pip install algenta` runtime, not only from a hand-run benchmark driver.

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float, int
backend: mojo
surfaces: library_execute
golden_vectors: none
benchmark: benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8_allsimd7.mojo
docs: gitbook/engine/qwen3-metal-decode.md
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Scope, stated precisely so nothing here overclaims
---------------------------------------------------
ONE model shape, ONE hardware family, ONE decode mode: Qwen3-0.6B-Base, greedy (argmax) decode,
Apple Silicon with Metal. This is not a general LLM-serving surface — it is today's real,
race-verified win (`_MBQwen3I8AllSimd7`, see `metaldispatch.session`'s own module docstring for the
full calibration record) made callable, and nothing more. A checkpoint of any other shape, or a
host with no Metal accelerator, or a binary built without `-D ALGENTA_GPU`, is refused with a named
status rather than silently run, downgraded, or faked (rule: no silent fallback).

`max_ctx` is raised above `RESIDENT_DEFAULT_CONTEXT` (512) whenever `n_prompt + max_new_tokens`
would not fit in it, up to `RESIDENT_MAX_CONTEXT`'s own safety ceiling -- the same auto-raise
contract the prefill+decode arm (`qwen3_prefill_decode.mojo`) applies, added here by the
2026-08-09 parity cheap-wins pass (this arm previously always requested the default 512, and had
never been exercised past it).

What this file does NOT do (rule 3 — call the frozen kernel, never re-derive it)
---------------------------------------------------------------------------------
Every kernel call below — `_MBQwen3I8AllSimd7.__init__`/`.upload_globals`/`.upload_layer`/`.seal`/
`.step` — is the exact same struct and the exact same methods
`benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8_allsimd7.mojo` already calls, byte
for byte. This file is NEW orchestration around an UNTOUCHED kernel: the prefill/decode loop below is
the driver's own loop, ported so it can run as a runtime-contract function instead of a `def main()`
that only a human typing a `pixi run mojo run` command can reach. See that benchmark file's own
docstring for the calibration and race history this kernel path rests on.

Checkpoint format this function reads
--------------------------------------
`checkpoint_dir` must contain `manifest.json` + `weights.blob`, in the exact shape
`benchmarks/llm_smoke/generate_manifest.py` and `algenta.qwen3_decode.prepare_checkpoint` both
produce (a byte-for-byte independent second implementation of the same safetensors -> flat-Float64
conversion, proven equivalent by direct diff — see `algenta.qwen3_decode`'s own module docstring for
that verification). This function does NOT read a raw HuggingFace snapshot (`config.json` +
`model.safetensors`) directly and does NOT download anything — the network-independent
artifact-acquisition step stays a separate, explicit stage on the Python side, matching this
project's existing checkpoint-preparation pattern.

Why one-shot, not open/step/close
----------------------------------
The kernel path this wraps has never supported step-by-step invocation from OUTSIDE one process:
every existing driver for this arm opens a session, prefills, decodes greedily until `max_new_tokens`
or EOS, and exits, all in one `def main()`. There is no resident-session-across-separate-wire-calls
design to preserve here, so a bespoke `qwen3_decode_open`/`_step`/`_close` message trio would be an
aspirational API this kernel does not actually back. One flat call — checkpoint dir, prompt token
ids folded into the checkpoint's own manifest, a token budget in, a token-id list out — is the
honest shape, and per `docs/mojo/new-kernel-package-rules.md` rule 2 a function whose params and
return are flat `String`/`Int`/`List[Int]`/struct-of-those needs no new message type at all: it is
callable as `execute("metaldispatch.qwen3_decode", "qwen3_i8_allsimd7_decode_flat", args)` through
the EXISTING `library_execute` message the moment it is discovered, exactly like the other 502+
`List`-shaped contract functions already are.
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
from metaldispatch.session import _MBQwen3I8AllSimd7, _mb_preflight, MB_GPU_BUILD

# ── the EXACT (and only) shape this kernel path was compiled for ──────────────────────────────────
# Mirrors `benchmarks/llm_smoke/generate_manifest.py`'s own module-level constants; kept as a second,
# independent literal (not an import of that benchmark script — this file must not depend on
# `benchmarks/`) and cross-checked against it by
# `tests/test_metaldispatch_qwen3_decode_architecture_gate.py`.
comptime QWEN3_0_6B_BASE_D_MODEL: Int = 1024
comptime QWEN3_0_6B_BASE_N_LAYERS: Int = 28
comptime QWEN3_0_6B_BASE_H_Q: Int = 16
comptime QWEN3_0_6B_BASE_H_KV: Int = 8
comptime QWEN3_0_6B_BASE_D_HEAD: Int = 128
comptime QWEN3_0_6B_BASE_D_FF: Int = 3072
comptime QWEN3_0_6B_BASE_VOCAB: Int = 151936
comptime QWEN3_0_6B_BASE_EOS_TOKEN_ID: Int = 151643
"""Qwen3's `<|endoftext|>` id — a property of the TOKENIZER/checkpoint, not of this manifest format,
so it is not a field `manifest.json` carries. Matches every existing driver for this arm (e.g.
`qwen3_generate_batch_i8_allsimd7.mojo`'s own `EOS_TOKEN_ID`) — restated here rather than imported
because that driver is a `benchmarks/` script, not a package this file may depend on."""


@fieldwise_init
struct Qwen3DecodeResult(Copyable, Movable):
    """One call's whole outcome: a status honest about which layer refused, plus the answer when
    there is one. `token_ids` is EMPTY on any non-`MB_OK` status — an empty list is itself a valid
    answer only when `status == MB_OK` and `stopped_on_eos` on the very first generated token, so the
    status field is what a caller must branch on, never the list's length."""

    var status: Int
    var error_message: String
    var token_ids: List[Int]
    """Prompt tokens followed by every generated token, in order — the same layout every existing
    `qwen3_generate_batch*.mojo` driver writes to its own `generated_ids.txt`."""
    var n_prompt: Int
    var stopped_on_eos: Bool
    var dispatches_per_token: Int
    var decode_tokens_per_sec: Float64
    var prefill_tokens_per_sec: Float64
    """Additive field (see this file's module docstring history): the prefill phase pays the exact
    same per-token dispatch cost as decode, one `step()` call per prompt token, so this number is not
    a different code path being timed -- it is the SAME loop, timed separately, because nothing
    previously measured it at all."""


def _decode_err(status: Int, message: String) -> Qwen3DecodeResult:
    return Qwen3DecodeResult(status, message, List[Int](), 0, False, 0, 0.0, 0.0)


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
        raise Error("metaldispatch.qwen3_decode: tensor not found in manifest: " + name)
    return _TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)  # Mojo 1.0.0: FileHandle.seek takes Int
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("metaldispatch.qwen3_decode: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def qwen3_i8_allsimd7_decode_flat(checkpoint_dir: String, max_new_tokens: Int) -> Qwen3DecodeResult:
    """Greedy-decode a prompt already folded into `checkpoint_dir/manifest.json`'s own `input_ids`,
    through `_MBQwen3I8AllSimd7`, and return every generated token id.

    Every failure mode is a returned `status`, never a crash and never a silently-wrong answer:
    `MB_ERR_CHECKPOINT_UNREADABLE` (bad path/format), `MB_ERR_UNSUPPORTED_ARCHITECTURE` (not
    Qwen3-0.6B-Base's exact shape), `MB_ERR_SHADER_TOOLCHAIN_ABSENT` (this binary was not built with
    `-D ALGENTA_GPU`), `MB_ERR_NO_DEVICE` (no Metal accelerator on this host), or one of
    `metaldispatch.contract`'s own shim-level codes (session/buffer/dispatch failures), each carrying
    `metaldispatch_status_name(status)` in `error_message` alongside any extra detail.
    """
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
            "unsupported model architecture: qwen3_i8_allsimd7_decode_flat runs ONLY"
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
    # Same auto-raise contract as the prefill+decode arm (qwen3_prefill_decode.mojo): a prompt
    # plus its requested generation that does not fit the 512 default gets exactly the context it
    # needs, up to RESIDENT_MAX_CONTEXT's ceiling -- never a silent KV-cache overflow, never a
    # hardcoded clamp that refuses a long prompt the session could otherwise serve.
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
            "this runtime worker was built without -D ALGENTA_GPU; Qwen3 GPU decode is compiled "
            + "out of this binary",
        )
    else:
        if not has_accelerator():
            return _decode_err(MB_ERR_NO_DEVICE, "no Metal accelerator was detected on this host")

        try:
            var s = _MBQwen3I8AllSimd7(
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

            var dispatches_per_token = 0
            var first_tok = -1
            var t_prefill_start = perf_counter_ns()
            for t in range(n_prompt):
                var r = s.step(prompt_ids[t], t)
                if r.status != MB_OK:
                    return _decode_err(
                        r.status,
                        "step(prefill pos " + String(t) + ") failed: "
                        + metaldispatch_status_name(r.status),
                    )
                dispatches_per_token = r.dispatches
                first_tok = r.token_id
            var t_prefill_end = perf_counter_ns()

            var prefill_tok_per_sec = 0.0
            if n_prompt > 0:
                var prefill_ms = Float64(Int(t_prefill_end - t_prefill_start)) / 1.0e6
                if prefill_ms > 0.0:
                    prefill_tok_per_sec = Float64(n_prompt) / (prefill_ms / 1000.0)

            # The LAST prefill step's own n_keys decides which of the two budgets applies -- see
            # `_MBQwen3I8AllSimd7.step`: `n_keys = pos + 1`, and at the last prefill iteration
            # `pos = n_prompt - 1`, so `n_keys = n_prompt` there. A prompt of more than
            # `RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS` (32) tokens crosses the split-K gate DURING
            # prefill itself, not only once decode runs deep -- this check used to assume the
            # shallow budget unconditionally, which made it fail on any prompt over ~32 tokens even
            # though the session was behaving exactly as designed. Never exercised before prefill
            # timing existed to prompt testing a real prompt longer than the fixed 5-token one.
            var expected_budget = metaldispatch_dispatch_budget(n_layers)
            if n_prompt > 0 and residentk_splitk_should_split(n_prompt):
                expected_budget = residentk_dispatch_budget_deep(n_layers)
            if dispatches_per_token != expected_budget:
                return _decode_err(
                    MB_ERR_DISPATCH_COUNT_MISMATCH,
                    "the session issued " + String(dispatches_per_token) + " dispatches but "
                    + "the expected budget for n_prompt=" + String(n_prompt) + " says "
                    + String(expected_budget)
                    + " -- the design and the code disagree",
                )

            generated_ids.append(first_tok)
            var stopped_on_eos = first_tok == QWEN3_0_6B_BASE_EOS_TOKEN_ID
            var n_decoded = 1

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
                    generated_ids.append(r2.token_id)
                    n_decoded += 1
                    if r2.token_id == QWEN3_0_6B_BASE_EOS_TOKEN_ID:
                        stopped_on_eos = True
                        break
            var t_decode_end = perf_counter_ns()

            var decode_steps = n_decoded - 1
            var tok_per_sec = 0.0
            if decode_steps > 0:
                var decode_ms = Float64(Int(t_decode_end - t_decode_start)) / 1.0e6
                if decode_ms > 0.0:
                    tok_per_sec = Float64(decode_steps) / (decode_ms / 1000.0)

            return Qwen3DecodeResult(
                MB_OK, "", generated_ids^, n_prompt, stopped_on_eos, dispatches_per_token,
                tok_per_sec, prefill_tok_per_sec
            )
        except e:
            return _decode_err(
                MB_ERR_SESSION_OPEN_FAILED, "metaldispatch session error: " + String(e)
            )
